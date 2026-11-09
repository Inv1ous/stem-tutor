"""Extraction-time gate for question images: data-sheet leaks out, tiny crops to review.

``classify(path)`` returns ``{'action': 'delete'|'review'|'keep', 'reason': str, ...}`` for one
image file. ``classify_many(paths)`` batches the OCR. Cheap signals run first (size, ink), then
on-device OCR (Apple Vision through build/ocr_batch.swift, compiled once into Work), rotated
when a large image reads almost no text (periodic tables are printed sideways).

delete  the text is reference matter - a periodic table, the "Important values, constants and
        standards" table, a formulae sheet, a single constant row such as "acceleration of free
        fall g = 9.81 m s-2" - and carries no question/answer markers.
        Boxed one-line table rows (MCQ key / mark-scheme rows: wide, three boxed cells,
        4 full-height cell borders, OCR ran and found no reference matter) are kept without review (VERSION 2, from the
        2026-11-07 visual review of 49 flagged images: every such row was real content).
review  excessively small, near-blank, or anything the gate could not check (any error is
        fail-safe: keep the image and flag it for an AI look).
keep    everything else.

The gate never removes anything itself; callers decide. It is pure apart from OCR and the
optional leak-signature file written by prune_question_leaks.py (near-duplicates of confirmed
leaks are deleted even when OCR fails). CLI: ``question_leak_gate.py IMAGE... [--json]``.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT.parent / 'Work' / 'Preparation'
OCR_BIN = WORK / 'source-migration' / 'bin' / 'ocr_batch'
OCR_SOURCE = Path(__file__).with_name('ocr_batch.swift')
SIGNATURES = WORK / 'question-leaks' / 'leak-signatures.json'
VERSION = 2

# Reference matter printed on CAIE 9701/9702 (and Edexcel formulae) pages; each phrase is one signal.
DATA_PHRASES = {
    'important_values': r'important\s+values',
    'constants_and_standards': r'constants\s+and\s+standards',
    'periodic_table': r'periodic\s+table\s+of(\s+the)?\s+elements',
    'lanthanoids': r'lanthan[oi]ids?',
    'actinoids': r'actin[oi]ids?',
    'atomic_symbol_key': r'atomic\s+symbol',
    'data_and_formulae': r'data\s+and\s+formulae',
    'formulae_heading': r'^\s*formulae\s*$',
    'data_heading': r'^\s*data\s*$',
    'copyright_notice': r'to\s+avoid\s+the\s+issue\s+of\s+disclosure',
    'free_fall': r'acceleration\s+of\s+free\s+fall',
    'speed_of_light': r'speed\s+of\s+light\s+in\s+free\s+space',
    'elementary_charge': r'elementary\s+charge\s*e\s*=',
    'molar_gas_constant': r'molar\s+gas\s+constant',
    'avogadro_constant': r'avogadro\s+constant\s+[nl]',
    'faraday_constant': r'faraday\s+constant',
    'planck_constant': r'planck\s+constant',
    'boltzmann_constant': r'boltzmann\s+constant',
    'gravitational_constant': r'gravitational\s+constant\s*g\s*=',
    'permittivity': r'permittivity\s+of\s+free\s+space',
    'unified_mass': r'unified\s+atomic\s+mass\s+unit',
    'rest_mass': r'rest\s+mass\s+of\s+(electron|proton)',
    'ionic_product_water': r'ionic\s+product\s+of\s+water',
    'shc_water': r'specific\s+heat\s+capacity\s+of\s+water',
    'molar_volume': r'molar\s+volume\s+of\s+gas',
    'electron_charge': r'charge\s+of\s+electron',
    'uniform_acceleration': r'uniformly\s+accelerated\s+motion',
    'hydrostatic': r'hydrostatic\s+pressure',
    'shm_heading': r'simple\s+harmonic\s+motion\s*$',
    'resistors_heading': r'resistors\s+in\s+(series|parallel)\s*$',
    'decay_heading': r'radioactive\s+decay\s*$',
    'doppler_heading': r'doppler\s+effect',
}
# Anything that shows the crop is (part of) a question or an answer.
QUESTION_MARKERS = {
    'marks': r'\[\s*\d{1,2}\s*\]',
    'part_label': r'^[ \t]*[\(\{\[]?[ \t]*(?:[a-h]|i{1,3}|iv|vi{0,3}|ix|x)[ \t]*\)',
    'question_number': r'^[ \t]*\d{1,2}[ \t]*(?:[\(\{][ \t]*[a-h][ \t]*\))?[ \t]+[A-Z][a-z]',
    'command_word': r'\b(?:which|what|calculate|determine|state|explain|suggest|describe|deduce|show\s+that|'
                    r'complete|draw|sketch|identify|define|predict|estimate|compare|outline|write|find|use\s+the)\b',
    'figure_ref': r'\bfig(?:ure)?\.?\s*\d',
    'table_ref': r'\btable\s+\d',
    'answer_line': r'\.{6,}|_{6,}',
    'mark_scheme': r'\bquestion\s+answer\s+marks?\b|\b(?:ecf|owtte)\b',
    'options': r'^[ \t]*[ABCD][ \t]+\S',
    'paper_header': r'\bqp[ _]?\d{2}\b|\bQ\.{1,2}\s*\d',
}
STRONG_MARKERS = {'marks', 'question_number', 'command_word', 'figure_ref', 'table_ref', 'paper_header'}
STRIP_WORDS = 25
PERIODIC = {'periodic_table', 'lanthanoids', 'actinoids', 'atomic_symbol_key', 'copyright_notice'}
MIN_HEIGHT, MIN_WIDTH, MIN_AREA = 70, 200, 40_000
BLANK_INK = 0.002
SPARSE_WORDS = 8
PHASH_DISTANCE = 6
# Mark-scheme/key rows are wide, one line high and boxed in three cells (four borders):
# question number | answer | marks. Data-sheet constant rows have two cells (three borders).
ROW_MIN_WIDTH, ROW_MIN_ASPECT, ROW_MIN_RULES, RULE_COVERAGE = 800, 12, 4, 0.85


def _rx(table):
    return {name: re.compile(pattern, re.IGNORECASE | re.MULTILINE) for name, pattern in table.items()}


_DATA, _MARKERS = _rx(DATA_PHRASES), _rx(QUESTION_MARKERS)


def data_signals(text: str) -> list[str]:
    return [name for name, rx in _DATA.items() if rx.search(text or '')]


def question_signals(text: str) -> list[str]:
    found = [name for name, rx in _MARKERS.items() if name != 'options' and rx.search(text or '')]
    if len(_MARKERS['options'].findall(text or '')) >= 2:
        found.append('options')
    if len(re.findall(r'\b[MABC][1-9]\b', text or '')) >= 2:
        found.append('mark_points')
    return found


def text_verdict(text: str) -> tuple[str, str] | None:
    """('delete', reason) when the text is reference matter only; None when the text decides nothing."""
    data, markers = data_signals(text), question_signals(text)
    if not data:
        return None
    strong = [m for m in markers if m in STRONG_MARKERS]
    words = len((text or '').split())
    reason = 'data-sheet text: ' + ','.join(data[:6])
    # The periodic-table key and its footnotes never appear inside a question; sideways OCR is noisy.
    if len([d for d in data if d in PERIODIC]) >= 2 and len(strong) <= 1:
        return 'delete', reason
    # A question may quote one constant; a whole data page may pick up a stray marker from OCR noise.
    if strong:
        return ('delete', reason) if len(data) >= 4 and len(data) > 2 * len(markers) else None
    if len(data) >= 2 or (words <= STRIP_WORDS and not markers):
        return 'delete', reason
    return None


def dhash(image, size: int = 8) -> str:
    """64-bit difference hash of the image (hex); identical pages from different papers land close."""
    small = image.convert('L').resize((size + 1, size))
    pixels = small.tobytes()
    bits = 0
    for row in range(size):
        for col in range(size):
            bits = (bits << 1) | (pixels[row * (size + 1) + col] > pixels[row * (size + 1) + col + 1])
    return f'{bits:016x}'


def hamming(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count('1')


def measure(path) -> dict:
    from PIL import Image
    with Image.open(path) as image:
        image.load()
        width, height = image.size
        gray = image.convert('L')
        gray.thumbnail((400, 400))
        histogram = gray.histogram()
        ink = sum(histogram[:160]) / max(1, gray.width * gray.height)
        features = {'width': width, 'height': height, 'ink': round(ink, 5), 'dhash': dhash(image),
                    'aspect': round(width / max(1, height), 3)}
        if height < MIN_HEIGHT:
            features['rules'] = vertical_rules(image)
        return features


def vertical_rules(image) -> int:
    """Full-height vertical lines (table cell borders) in a strip; adjacent dark columns count once."""
    gray = image.convert('L')
    width, height = gray.size
    pixels = gray.tobytes()
    rules, inside = 0, False
    for x in range(width):
        dark = sum(pixels[y * width + x] < 128 for y in range(height))
        line = dark >= RULE_COVERAGE * height
        rules += line and not inside
        inside = line
    return rules


def is_table_row(features: dict) -> bool:
    """A boxed one-line row (MCQ key, mark-scheme row): visually reviewed as real content, never junk."""
    return (features.get('rules', 0) >= ROW_MIN_RULES and features['width'] >= ROW_MIN_WIDTH
            and features['aspect'] >= ROW_MIN_ASPECT and features['ink'] >= BLANK_INK)


def _binary() -> Path | None:
    binary = Path(os.environ.get('STEM_OCR_BATCH') or OCR_BIN)
    if binary.is_file() and os.access(binary, os.X_OK):
        return binary
    try:
        binary.parent.mkdir(parents=True, exist_ok=True)
        built = subprocess.run(['swiftc', '-O', str(OCR_SOURCE), '-o', str(binary)], capture_output=True, timeout=600)
    except (OSError, subprocess.SubprocessError):
        return None
    return binary if built.returncode == 0 and binary.is_file() else None


def ocr(paths: list) -> dict[str, str]:
    """Literal OCR text per absolute path string; missing entries mean OCR was unavailable."""
    paths = [str(Path(p).resolve()) for p in paths]
    binary = _binary() if paths else None
    if binary is None:
        return {}
    done = subprocess.run([str(binary)], input='\n'.join(paths).encode(), capture_output=True, timeout=600)
    texts = {}
    for line in done.stdout.decode('utf-8', 'replace').splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        texts[row['path']] = row.get('text') or ''
    return texts


def rotated_text(path) -> str:
    """OCR of the image turned both ways (sideways periodic tables read as noise upright)."""
    from PIL import Image
    with tempfile.TemporaryDirectory(prefix='leak-gate-') as tmp, Image.open(path) as image:
        names = []
        for angle in (90, 270):
            target = Path(tmp) / f'r{angle}.png'
            image.rotate(angle, expand=True).save(target)
            names.append(target)
        texts = ocr(names)
    return max(texts.values(), key=lambda t: len(t.split()), default='')


def load_signatures(path: Path | None = None) -> list[dict]:
    path = Path(path or SIGNATURES)
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return []
    return [s for s in data.get('signatures', []) if isinstance(s, dict) and s.get('dhash')]


def signature_match(features: dict, signatures: list[dict]) -> dict | None:
    for signature in signatures:
        if (abs(signature['aspect'] - features['aspect']) <= 0.05 * signature['aspect']
                and hamming(signature['dhash'], features['dhash']) <= PHASH_DISTANCE):
            return signature
    return None


def decide(features: dict, text: str | None, rotated: str | None = None, signatures=()) -> dict:
    """Pure decision from measured features and OCR text (None = OCR unavailable)."""
    out = {'action': 'keep', 'reason': 'question content', 'gate_version': VERSION, **features}
    combined = '\n'.join(t for t in (text, rotated) if t) if rotated and text else None
    for candidate in (text, rotated, combined):
        if candidate:
            verdict = text_verdict(candidate)
            if verdict:
                out.update(action=verdict[0], reason=verdict[1] + ('' if candidate is text else ' (rotated)'))
                return out
    match = signature_match(features, signatures) if signatures else None
    if match:
        out.update(action='delete', reason=f"near-duplicate of confirmed leak {match.get('sha256', '')[:12]} ({match.get('reason', '')})")
        return out
    small = (features['height'] < MIN_HEIGHT or features['width'] < MIN_WIDTH
             or features['width'] * features['height'] < MIN_AREA)
    if small and text is not None and is_table_row(features):
        out.update(reason='boxed table row (mark-scheme or MCQ key strip)')
    elif small:
        out.update(action='review', reason=f"excessively small {features['width']}x{features['height']}")
    elif features['ink'] < BLANK_INK:
        out.update(action='review', reason='near-blank image')
    elif text is None:
        out.update(action='review', reason='OCR unavailable: data-sheet check not run')
    return out


def classify_many(paths, *, texts: dict | None = None, signatures=None) -> dict[str, dict]:
    """Classify several images; every failure is keep + review, never an exception."""
    paths = [str(Path(p).resolve()) for p in paths]
    signatures = load_signatures() if signatures is None else signatures
    results, measured = {}, {}
    for path in paths:
        try:
            measured[path] = measure(path)
        except Exception as exc:  # noqa: BLE001 - fail safe by contract
            results[path] = {'action': 'review', 'reason': f'gate error: {type(exc).__name__}: {exc}', 'gate_version': VERSION}
    try:
        found = dict(texts) if texts is not None else {}
        todo = [p for p in measured if p not in found]
        if todo:
            found.update(ocr(todo))
    except Exception as exc:  # noqa: BLE001
        found = {}
        for path in measured:
            results[path] = {'action': 'review', 'reason': f'gate error: OCR failed: {exc}', 'gate_version': VERSION,
                             **measured[path]}
    for path, features in measured.items():
        if path in results:
            continue
        try:
            text = found.get(path)
            rotated = None
            # Sideways pages (periodic tables) read as noise, or as just their upright footer.
            if (text is not None and not text_verdict(text) and min(features['width'], features['height']) >= 600
                    and (len(text.split()) < SPARSE_WORDS or data_signals(text))):
                rotated = rotated_text(path)
            results[path] = decide(features, text, rotated, signatures)
        except Exception as exc:  # noqa: BLE001
            results[path] = {'action': 'review', 'reason': f'gate error: {type(exc).__name__}: {exc}',
                             'gate_version': VERSION, **features}
    return results


def classify(path, **kwargs) -> dict:
    """{action: delete|review|keep, reason} for one image file; never raises."""
    try:
        return next(iter(classify_many([path], **kwargs).values()))
    except Exception as exc:  # noqa: BLE001
        return {'action': 'review', 'reason': f'gate error: {type(exc).__name__}: {exc}', 'gate_version': VERSION}


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('images', nargs='+', type=Path)
    parser.add_argument('--json', action='store_true', help='one JSON object per image')
    args = parser.parse_args(argv)
    for path, result in classify_many(args.images).items():
        print(json.dumps({'path': path, **result}) if args.json else f"{result['action']:6} {path}  {result['reason']}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
