"""Deterministic syllabus tagging of the sealed source-verified practice release.

Read-only over the vault.  No model calls.  Evidence, strongest first:

1. ``topical_bank``  reviewed past-paper -> KC mapping (``.tutor/topicals`` CURRENT bank)
2. ``course_pack``   past-paper items already placed in course question packs
3. ``text``          TF-IDF of question text against the course KC graph, only above
                     calibrated confidence thresholds
4. nothing           item stays ``unmapped`` with a reason (never guessed)

Each item is also split into parts ((a), (b)(i) ...) and each part is tagged on its own
text.  Output (default ``Work/Preparation/source-migration/source_topics.json``) is NOT a
Library resource; ``migrate_source_questions.py`` consumes it.

    .venv/bin/python build/source_topics.py            # build + coverage report
    .venv/bin/python build/source_topics.py --evaluate # + precision against reviewed ground truth
"""
from __future__ import annotations

import argparse
import collections
import glob
import hashlib
import json
import math
import os
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

SCHEMA = 1
WORK = ROOT.parent / 'Work/Preparation/source-migration'
DEFAULT_VAULT = Path(os.environ.get('STEM_TUTOR_VAULT') or ROOT.parent / 'STEM Tutor')

# Calibrated on the reviewed topical bank (see --evaluate).  Whole-question text matching
# is accepted only at/above these; part matching uses the stricter PART thresholds.
THRESHOLDS = {
    # CAIE: KC-statement matching alone was only 40-65% precise against reviewed truth, so a KC is accepted only when
    # already-tagged questions agree (knn); doc-text matching is advisory (text_only False).
    'caie': {'score': 0.30, 'margin': 0.30, 'keep_ratio': 0.80, 'max_kcs': 2, 'knn_sim': 0.50, 'knn_share': 0.50,
             'label_score': 0.15, 'label_ratio': 0.85, 'text_only': False},
    'maths': {'score': 0.25, 'margin': 0.30, 'keep_ratio': 0.80, 'max_kcs': 2, 'knn_sim': 0.50, 'knn_share': 0.50,
              'label_score': 0.15, 'label_ratio': 0.85, 'text_only': True},
}
# When the source's own topic label already fixes the subtopic, candidates are restricted to it: lower bars.
HINTED = {'score': 0.12, 'margin': 0.12, 'keep_ratio': 0.85, 'max_kcs': 2, 'knn_sim': 0.40, 'knn_share': 0.50,
          'text_only': True}
PART_THRESHOLDS = {
    'caie': {'score': 0.30, 'margin': 0.30, 'keep_ratio': 0.80, 'max_kcs': 2},
    'maths': {'score': 0.25, 'margin': 0.30, 'keep_ratio': 0.80, 'max_kcs': 2},
}
PART_HINTED = {'score': 0.14, 'margin': 0.15, 'keep_ratio': 0.85, 'max_kcs': 2}
MIN_TEXT_TOKENS = 4
CONTEXT_WEIGHT = 0.35

STOP = set('''a an the of to in on at by for and or is are was were be been it its this that these those with as from
into than then so if which what when where how why do does did can could will would should shall may might must not no
 find show given give state write determine calculate use using hence leave blank total marks mark answer question
 turn over page figure diagram table above below each one two three four five six your you we our their there here
 also only any all both either other such'''.split())
_SUFFIX = ('ational', 'ations', 'ation', 'ising', 'ised', 'ises', 'izing', 'ized', 'ments', 'ment', 'ings', 'ing',
           'ied', 'ies', 'ity', 'ive', 'ous', 'ers', 'ed', 'es', 'er', 'ly', 'al', 's')


def course_family(course: str) -> str:
    return 'caie' if course in ('9701', '9702') else 'maths'


def stem(word: str) -> str:
    for suffix in _SUFFIX:
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            return word[:-len(suffix)]
    return word


_PDF_GLYPH = {'': ' plusminus ', '': ' pi ', '': ' theta ', '': ' lambda ', '': ' rho ',
              '': ' sigma ', '': ' mu ', '': ' alpha ', '': ' beta ', '': ' gamma ',
              '': ' delta ', '': ' omega ', '': ' phi ', '': ' times '}


def tokens(text: str) -> list[str]:
    for glyph, name in _PDF_GLYPH.items():
        text = text.replace(glyph, name)
    text = text.lower().replace('√', ' sqrt ').replace('∫', ' integral ').replace('∑', ' sum ').replace('π', ' pi ')
    text = re.sub(r'physicsandmathstutor\.com|examinent\.com|edexcel internal review|pmt', ' ', text)
    text = re.sub(r'\b[a-z]\d\b', lambda m: m[0] if m[0][0] in 'cdmsfp' else ' ', text)
    words = re.findall(r"[a-z]{2,}|\bd[a-z]?\s*/\s*d[a-z]\b", text)
    out = [stem(w) for w in words if w not in STOP]
    # calculus shorthands lost to PDF extraction ("dy/dx", stacked "d y d x")
    if re.search(r'\bdy\s*/?\s*dx\b|\bd\s*y\s*d\s*x\b|\bdd\b', text):
        out += ['differentiat', 'deriv']
    return out


def bigrams(toks: list[str]) -> list[str]:
    return [a + '_' + b for a, b in zip(toks, toks[1:])]


# --------------------------------------------------------------------------- loading

def read_json(path: Path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def pointer(vault: Path, relative: str) -> str:
    return (Path(vault) / relative).read_text().strip()


def load_release(vault: Path, release: str | None = None) -> tuple[str, dict]:
    release = release or pointer(vault, '.tutor/source_practice/CURRENT')
    if not re.fullmatch(r'Library/SourcePractice/Releases/[a-f0-9]{64}\.json', release):
        raise ValueError('invalid source practice release path')
    raw = (Path(vault) / release).read_bytes()
    if hashlib.sha256(raw).hexdigest() != Path(release).stem:
        raise ValueError('source practice release digest mismatch')
    return release, json.loads(raw)


def load_graph(vault: Path, spec: str) -> dict | None:
    try:
        version = pointer(vault, '.tutor/packs/CURRENT')
    except OSError:
        return None
    path = Path(vault) / 'Library/Releases' / version / 'specs' / spec / 'graph.json'
    return read_json(path) if path.is_file() else None


def load_topical_truth(vault: Path) -> dict[str, dict]:
    """qid -> {'kcs': [...], 'chapters': [...]} from the CURRENT reviewed topical bank."""
    try:
        version = pointer(vault, '.tutor/topicals/CURRENT')
        bank = read_json(Path(vault) / 'Library/Shared/Topicals/Releases' / version / 'bank.json')
    except (OSError, ValueError):
        return {}
    result: dict[str, dict] = {}
    for item in bank.get('items', []):
        qid = (item.get('source') or {}).get('qid')
        if not qid or not item.get('kcs'):
            continue
        slot = result.setdefault(qid, {'kcs': [], 'chapters': [], 'items': []})
        for kc in item['kcs']:
            if kc not in slot['kcs']:
                slot['kcs'].append(kc)
        for chapter in (item.get('topical') or {}).get('chapters', []):
            if chapter not in slot['chapters']:
                slot['chapters'].append(chapter)
        slot['items'].append(item['id'])
    return result


def load_pack_truth(vault: Path) -> dict[str, dict]:
    """qid -> kcs for past-paper items already placed in course question packs."""
    result: dict[str, dict] = {}
    for path in sorted(glob.glob(str(Path(vault) / 'Library/Courses/*/Questions/Packs/*/*.json'))):
        try:
            pack = read_json(path)
        except ValueError:
            continue
        for item in pack.get('items', []):
            source = item.get('source') or {}
            qid = source.get('qid')
            if source.get('type') != 'past' or not qid or not item.get('kcs'):
                continue
            slot = result.setdefault(qid, {'kcs': [], 'items': []})
            for kc in item['kcs']:
                if kc not in slot['kcs']:
                    slot['kcs'].append(kc)
            slot['items'].append(item.get('id'))
    return result


# --------------------------------------------------------------------------- TF-IDF index

def _tf(terms: list[str]) -> collections.Counter:
    return collections.Counter(terms + bigrams(terms))


def _unit(counts, idf) -> dict:
    vec = {t: (1 + math.log(c)) * idf[t] for t, c in counts.items() if t in idf}
    norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
    return {t: v / norm for t, v in vec.items()}


def _dot(a: dict, b: dict) -> float:
    small, large = (a, b) if len(a) < len(b) else (b, a)
    return sum(v * large[t] for t, v in small.items() if t in large)


class KcIndex:
    """TF-IDF over KC statements plus (optionally) already-tagged example questions of the same syllabus.

    ``rank`` scores a text against the KC statements/titles/glossary.  ``neighbours`` finds the most
    similar already-tagged questions (course packs, reviewed topical bank) and lets them vote.
    """

    def __init__(self, graph: dict, examples: list[dict] | None = None):
        self.graph = graph
        self.kcs = {kc['id']: kc for kc in graph['kcs']}
        self.subtopic = {kc['id']: kc.get('subtopic') for kc in graph['kcs']}
        self.subtopic_title = {s['id']: s.get('title', '') for s in graph.get('subtopics', [])}
        docs = {}
        for kc in graph['kcs']:
            title = tokens(kc.get('title', ''))
            statement = tokens(kc.get('statement', ''))
            gloss = [tokens(term) for term in kc.get('glossary', [])]
            guide = tokens(kc.get('guidance', ''))
            words = title * 3 + statement * 2 + [t for g in gloss for t in g] * 2 + guide + tokens(self.subtopic_title.get(kc.get('subtopic'), ''))
            grams = bigrams(title) * 3 + bigrams(statement) * 2 + bigrams(guide) + [b for g in gloss for b in bigrams(g)] * 2
            docs[kc['id']] = collections.Counter(words + grams)
        self.examples = [e for e in (examples or []) if e.get('text') and e.get('kcs')]
        example_counts = [_tf(tokens(e['text'])) for e in self.examples]
        df = collections.Counter()
        for doc in list(docs.values()) + example_counts:
            df.update(doc.keys())
        n = len(docs) + len(example_counts)
        self.idf = {term: math.log((1 + n) / (1 + count)) + 1 for term, count in df.items()}
        self.vectors = {kid: _unit(doc, self.idf) for kid, doc in docs.items()}
        self.example_vectors = [_unit(c, self.idf) for c in example_counts]

    def vector(self, text: str) -> tuple[dict, int]:
        toks = tokens(text)
        return _unit(_tf(toks), self.idf), len(toks)

    def rank(self, text: str, context: str = '', restrict=None) -> tuple[list[tuple[str, float]], int]:
        vec, count = self.vector(text)
        if context and CONTEXT_WEIGHT:
            cvec, _ = self.vector(context)
            for term, value in cvec.items():
                vec[term] = vec.get(term, 0.0) + CONTEXT_WEIGHT * value
        scores = []
        for kid, kvec in self.vectors.items():
            if restrict is not None and kid not in restrict:
                continue
            score = _dot(vec, kvec)
            if score > 0:
                scores.append((kid, round(score, 4)))
        scores.sort(key=lambda row: (-row[1], row[0]))
        return scores, count

    def neighbours(self, text: str, exclude=(), k: int = 5):
        """(kc votes sorted, best similarity, count) from the k most similar tagged examples."""
        vec, count = self.vector(text)
        sims = []
        for example, evec in zip(self.examples, self.example_vectors):
            if example.get('qid') in exclude or example.get('id') in exclude:
                continue
            s = _dot(vec, evec)
            if s > 0:
                sims.append((s, example['id'], example['kcs']))
        sims.sort(key=lambda row: (-row[0], row[1]))
        sims = sims[:k]
        votes = collections.defaultdict(float)
        for s, _, kcs in sims:
            for kc in kcs:
                votes[kc] += s
        total = sum(votes.values()) or 1.0
        ranked = sorted(((kc, round(v / total, 4)) for kc, v in votes.items()), key=lambda row: (-row[1], row[0]))
        return ranked, (round(sims[0][0], 4) if sims else 0.0), count


def decide(ranked: list[tuple[str, float]], threshold: dict) -> tuple[list[str], float, str]:
    """Accept only a clearly leading KC (and near-ties of it); otherwise explain the refusal."""
    if not ranked:
        return [], 0.0, 'no_keyword_overlap'
    top = ranked[0][1]
    if top < threshold['score']:
        return [], top, 'below_score_threshold'
    second = ranked[1][1] if len(ranked) > 1 else 0.0
    near = [kid for kid, score in ranked if score >= top * threshold['keep_ratio']]
    if len(near) > threshold['max_kcs']:
        return [], top, 'ambiguous_many_kcs'
    if len(near) == 1 and (top - second) / top < threshold['margin']:
        return [], top, 'ambiguous_margin'
    return near, top, 'ok'


def decide_neighbours(votes, best_sim: float, threshold: dict) -> tuple[list[str], float, str]:
    if not votes or best_sim < threshold['knn_sim']:
        return [], best_sim, 'no_similar_tagged_question'
    kc, share = votes[0]
    if share < threshold['knn_share']:
        return [], best_sim, 'neighbours_disagree'
    return [kc], best_sim, 'ok'


# --------------------------------------------------------------------------- part splitting

ROMAN = ['i', 'ii', 'iii', 'iv', 'v', 'vi', 'vii', 'viii']
_LABEL = re.compile(r'^[ \t]*(?:\d{1,2}\.?[ \t]+)?\(([a-z]|i{1,3}|iv|vi{0,3})\)(?=[ \t\n]|$)', re.M)
_INLINE = re.compile(r'(?<=[\s.,;:)])\(([a-z]|i{1,3}|iv|vi{0,3})\)(?=[ \t]+[A-Z\\$])')
_MARKS = re.compile(r'^\s*\(\d{1,2}\)\s*$', re.M)
_TOTAL = re.compile(r'\(Total for Question[^)]*\)|\(Total \d+ marks?\)|\(Total\)', re.I)


def split_parts(text: str) -> tuple[str, list[dict]]:
    """Return (preamble, leaf parts).  Parts are labelled 'a', 'b(i)', ... in order."""
    line_based, inline = _split(text, _LABEL), _split(text, _INLINE)
    return inline if len(inline[1]) > len(line_based[1]) else line_based


def _split(text: str, pattern) -> tuple[str, list[dict]]:
    found = []
    letter, roman = None, None
    for match in pattern.finditer(text):
        label = match[1]
        expected_letter = 'a' if letter is None else chr(ord(letter) + 1)
        expected_roman = ROMAN[0] if roman is None else (ROMAN[ROMAN.index(roman) + 1] if roman != ROMAN[-1] else None)
        if label == expected_roman and letter is not None:
            roman = label
            found.append((match.start(), match.end(), letter, label))
        elif label == expected_letter:
            letter, roman = label, None
            found.append((match.start(), match.end(), label, None))
    if not found or found[0][2] != 'a':
        return text, []
    preamble = text[:found[0][0]]
    parts = []
    for index, (start, end, lett, rom) in enumerate(found):
        stop = found[index + 1][0] if index + 1 < len(found) else len(text)
        body = text[end:stop]
        parts.append({'letter': lett, 'roman': rom, 'text': body})
    # leaf parts: a letter part followed by its roman sub-parts contributes its own intro as context only
    leaves = []
    for index, part in enumerate(parts):
        nxt = parts[index + 1] if index + 1 < len(parts) else None
        parent_has_children = part['roman'] is None and nxt is not None and nxt['letter'] == part['letter'] and nxt['roman']
        if parent_has_children:
            continue
        intro = ''
        if part['roman']:
            for earlier in reversed(parts[:index]):
                if earlier['letter'] == part['letter'] and earlier['roman'] is None:
                    intro = earlier['text']
                    break
        label = part['letter'] + (f"({part['roman']})" if part['roman'] else '')
        body = _TOTAL.sub(' ', _MARKS.sub(' ', part['text']))
        leaves.append({'label': label, 'text': body.strip(), 'context': intro.strip()})
    return preamble, leaves


# --------------------------------------------------------------------------- tagging

def clean_question_text(text: str) -> str:
    text = _TOTAL.sub(' ', text)
    return re.sub(r'_{5,}', ' ', text)


_PAPER_SOURCE = re.compile(r'pearson-edexcel|^\d{4}_[a-z]\d\d_\d\d$|Examinent', re.I)


def source_label(item: dict) -> str | None:
    """Human topic label carried by PMT topic compilations, e.g. 'M1 Kinematics - Uniform acceleration formulae'."""
    label = item.get('source') or ''
    if not label or _PAPER_SOURCE.search(label):
        return None
    label = re.sub(r'^[A-Z]{1,2}\d\b[\s:–-]*', '', label)
    return label if len(tokens(label)) >= 1 else None


def load_examples(vault: Path, spec: str) -> list[dict]:
    """Already-tagged questions of this syllabus: course-pack items and reviewed topical-bank items."""
    examples = []
    for path in sorted(glob.glob(str(Path(vault) / f'Library/Courses/*/Questions/Packs/{spec}/*.json'))):
        try:
            pack = read_json(path)
        except ValueError:
            continue
        for q in pack.get('items', []):
            text = (q.get('stem') or '') + ' ' + ' '.join((q.get('options') or {}).values())
            examples.append({'id': q.get('id'), 'kcs': q.get('kcs', []), 'text': text,
                             'qid': (q.get('source') or {}).get('qid') if (q.get('source') or {}).get('type') == 'past' else None})
    return examples


class Tagger:
    """Everything needed to tag items of one course; built once per course."""

    def __init__(self, course: str, graph: dict | None, vault: Path | None = None, truth=None, packs=None,
                 examples=None, thresholds=None):
        self.course, self.family = course, course_family(course)
        self.truth, self.packs = truth or {}, packs or {}
        self.index = KcIndex(graph, examples) if graph else None
        self.thr = (thresholds or {}).get('whole', THRESHOLDS)[self.family]
        self.part_thr = (thresholds or {}).get('part', PART_THRESHOLDS)[self.family]

    # -- evidence ---------------------------------------------------------
    def label_hint(self, item: dict):
        """Subtopic(s) named by the source's own topic label (independent of the question body)."""
        label = source_label(item)
        if not label or not self.index:
            return [], None
        ranked, count = self.index.rank(label)
        if not ranked:
            return [], label
        by_sub = collections.defaultdict(float)
        for kid, score in ranked:
            by_sub[self.index.subtopic[kid]] = max(by_sub[self.index.subtopic[kid]], score)
        order = sorted(by_sub.items(), key=lambda r: (-r[1], r[0]))
        top = order[0][1]
        if top < self.thr['label_score'] or (len(order) > 1 and order[1][1] >= top * self.thr['label_ratio']):
            return [], label
        return [order[0][0]], label

    def whole_text(self, text: str, exclude=(), restrict=None, thr=None):
        """-> (kcs, confidence, method, reason)."""
        index, thr = self.index, thr or self.thr
        ranked, count = index.rank(text, restrict=restrict)
        if count < MIN_TEXT_TOKENS:
            return [], 0.0, None, 'no_extractable_text'
        votes, best, _ = index.neighbours(text, exclude=exclude)
        if restrict is not None:
            votes = [(k, v) for k, v in votes if k in restrict]
        nn, nn_conf, nn_why = decide_neighbours(votes, best, thr)
        dk, dk_conf, dk_why = decide(ranked, thr)
        if not thr.get('text_only', True) and not nn:
            return [], round(dk_conf, 3), None, 'text_only_not_trusted' if dk else dk_why
        if nn and dk and not set(nn) & set(dk):
            return [], max(nn_conf, dk_conf), None, 'conflicting_signals'
        if nn:
            kcs = list(dict.fromkeys(nn + [k for k in dk if k not in nn]))
            return kcs, round(nn_conf, 3), 'knn+text' if dk else 'knn', 'neighbour_vote'
        if dk:
            return dk, round(dk_conf, 3), 'text', 'tfidf_above_threshold'
        return [], round(max(dk_conf, nn_conf), 3), None, dk_why if dk_conf >= nn_conf else nn_why

    # -- one item ---------------------------------------------------------
    def tag(self, item: dict, *, use_truth: bool = True) -> dict:
        index = self.index
        qids = [v for v in (item.get('official_qid'), item.get('canonical_id'), item['id']) if v]
        record = {'id': item['id'], 'course': item['course'], 'kcs_required': [], 'subtopics': [], 'parts': [],
                  'status': 'unmapped', 'method': None, 'confidence': 0.0, 'reason': None, 'evidence': {}}
        allowed = set(index.kcs) if index else None
        joined, source = [], None
        if use_truth:
            for table, name in ((self.truth, 'topical_bank'), (self.packs, 'course_pack')):
                for qid in qids:
                    if qid in table:
                        joined = [k for k in table[qid]['kcs'] if allowed is None or k in allowed]
                        if joined:
                            source = name
                            record['evidence'] = {'items': [i for i in table[qid]['items'][:3] if i]}
                            break
                if joined:
                    break
        text = clean_question_text(item.get('question_text') or '')
        preamble, parts = split_parts(text) if item.get('kind') != 'mcq' else (text, [])
        hint, label = self.label_hint(item)
        if label:
            record['evidence']['source_label'] = label
        if joined:
            record.update(kcs_required=joined, method=source, status='mapped',
                          confidence=1.0 if source == 'topical_bank' else 0.9,
                          reason='existing_reviewed_mapping' if source == 'topical_bank' else 'existing_pack_mapping')
        elif index is None:
            record['reason'] = 'no_kc_graph_for_course'
        else:
            restrict = {k for k, sub in index.subtopic.items() if sub in hint} if hint else None
            kcs, conf, method, why = self.whole_text(text, exclude=set(qids), restrict=restrict,
                                                     thr=HINTED if restrict else None)
            record['confidence'] = conf
            if kcs:
                record.update(kcs_required=kcs, method=method, status='mapped', reason=why)
                if hint:
                    record['evidence']['label_subtopic'] = hint[0]
            else:
                record['reason'] = why
        scope = {k for k, sub in index.subtopic.items() if sub in hint} if (index and hint) else None
        for part in parts:
            entry = {'label': part['label'], 'kcs': [], 'confidence': 0.0, 'method': 'unmapped', 'reason': None}
            if index is None:
                entry['reason'] = 'no_kc_graph_for_course'
            else:
                restrict = set(record['kcs_required']) if joined else scope
                ranked, count = index.rank(part['text'], context=(preamble + ' ' + part['context']).strip(), restrict=restrict)
                if count < MIN_TEXT_TOKENS:
                    entry['reason'] = 'part_text_too_short'
                else:
                    kcs, top, why = decide(ranked, PART_HINTED if (restrict and not joined) else self.part_thr)
                    entry['confidence'] = round(top, 3)
                    entry['reason'] = why if not kcs else 'tfidf_above_threshold'
                    if kcs:
                        entry.update(kcs=kcs, method='text')
            record['parts'].append(entry)
        part_kcs = [k for p in record['parts'] for k in p['kcs']]
        if part_kcs and not joined:
            record['kcs_required'] = list(dict.fromkeys(record['kcs_required'] + part_kcs))
            if record['status'] == 'unmapped':
                record.update(status='mapped', method='text_parts', reason='union_of_part_tags',
                              confidence=max(p['confidence'] for p in record['parts']))
        if record['status'] == 'mapped' and record['parts'] and any(not p['kcs'] for p in record['parts']):
            record['status'] = 'partial'
        record['trust'] = {'topical_bank': 'reviewed', 'course_pack': 'curated', 'knn': 'high', 'knn+text': 'high',
                           'text': 'medium', 'text_parts': 'low'}.get(record['method'], 'none')
        if index is not None:
            subs = [index.subtopic[k] for k in record['kcs_required'] if k in index.subtopic]
            record['subtopics'] = list(dict.fromkeys(subs))
            if record['status'] == 'unmapped' and hint:
                record['subtopics'] = hint
                record['status'] = 'subtopic_only'
                record['method'] = 'source_label'
                record['reason'] = 'subtopic_from_source_label_only'
        return record


def build_taggers(vault: Path, courses, *, use_truth: bool = True, thresholds=None) -> dict[str, Tagger]:
    truth, packs = (load_topical_truth(vault), load_pack_truth(vault)) if use_truth else ({}, {})
    taggers = {}
    for course in sorted(courses):
        graph = load_graph(vault, course)
        taggers[course] = Tagger(course, graph, vault, truth, packs, load_examples(vault, course) if graph else [],
                                 thresholds)
    return taggers


def build(vault: Path, release: str | None = None, *, use_truth: bool = True, thresholds=None) -> dict:
    release, data = load_release(vault, release)
    taggers = build_taggers(vault, {i['course'] for i in data['items']}, use_truth=use_truth, thresholds=thresholds)
    records = [taggers[i['course']].tag(i, use_truth=use_truth) for i in sorted(data['items'], key=lambda i: i['id'])]
    return {'schema_version': SCHEMA, 'release': release, 'generator': 'build/source_topics.py',
            'thresholds': {'whole': THRESHOLDS, 'hinted': HINTED, 'part': PART_THRESHOLDS, 'part_hinted': PART_HINTED},
            'counts': coverage(records), 'items': records}


# --------------------------------------------------------------------------- reports

def coverage(records: list[dict]) -> dict:
    table: dict[str, collections.Counter] = {}
    for rec in records:
        row = table.setdefault(rec['course'], collections.Counter())
        row['items'] += 1
        row[rec['status']] += 1
        row['via_' + str(rec['method'])] += 1
        if rec['reason'] and rec['status'] == 'unmapped':
            row['why_' + rec['reason']] += 1
        row['parts'] += len(rec['parts'])
        row['parts_tagged'] += sum(1 for p in rec['parts'] if p['kcs'])
    return {course: dict(row) for course, row in sorted(table.items())}


def format_coverage(counts: dict) -> str:
    lines = ['course  items mapped partial unmapped  via_bank via_pack via_text  parts parts_tagged']
    for course, row in counts.items():
        lines.append(f"{course:6} {row['items']:6} {row.get('mapped', 0):6} {row.get('partial', 0):7} {row.get('unmapped', 0):8}"
                     f"  {row.get('via_topical_bank', 0):8} {row.get('via_course_pack', 0):8} "
                     f"{row.get('via_text', 0) + row.get('via_text_parts', 0):8}  {row['parts']:5} {row['parts_tagged']:11}")
    return '\n'.join(lines)


def evaluate(vault: Path, release: str | None = None, sample: int = 30, seed: int = 20261106, thresholds=None) -> dict:
    """Matcher scored against independent evidence with that evidence withheld.

    CAIE: reviewed topical bank + pack KCs (the item's own qid is excluded from the neighbour examples).
    Edexcel maths: the source's own PMT topic label (subtopic level) and the few reviewed bank items.
    """
    release, data = load_release(vault, release)
    truth = load_topical_truth(vault)
    truth.update({k: v for k, v in load_pack_truth(vault).items() if k not in truth})
    taggers = build_taggers(vault, {i['course'] for i in data['items']}, use_truth=False, thresholds=thresholds)
    report = {}
    for course, tagger in taggers.items():
        if tagger.index is None:
            continue
        index = tagger.index
        rows = []
        for item in data['items']:
            if item['course'] != course:
                continue
            ref = next((truth[q]['kcs'] for q in (item.get('official_qid'), item.get('canonical_id'), item['id']) if q in truth), None)
            kind = 'kc'
            if ref is None:
                hint, _ = tagger.label_hint(item)
                if not hint:
                    continue
                ref, kind = hint, 'label_subtopic'
            # label-derived truth must not leak into the prediction: tag without the label restriction
            rec = tagger.tag(dict(item, source=''), use_truth=False)
            rows.append((item['id'], ref, kind, rec))
        mapped = [r for r in rows if r[3]['kcs_required']]

        def hit(ref, kind, rec):
            if kind == 'kc':
                return bool(set(rec['kcs_required']) & set(ref))
            return bool({index.subtopic.get(k) for k in rec['kcs_required']} & set(ref))

        def sub_hit(ref, kind, rec):
            refs = {index.subtopic.get(k) for k in ref} if kind == 'kc' else set(ref)
            return bool({index.subtopic.get(k) for k in rec['kcs_required']} & refs)
        random.Random(seed).shuffle(mapped)
        by_method = collections.defaultdict(lambda: [0, 0])
        for _, ref, kind, rec in mapped:
            by_method[rec['method']][0] += 1
            by_method[rec['method']][1] += hit(ref, kind, rec)
        report[course] = {
            'reference_items': len(rows), 'reference_kind': collections.Counter(r[2] for r in rows).most_common(1)[0][0] if rows else None,
            'text_mapped': len(mapped), 'text_coverage_on_reference': round(len(mapped) / len(rows), 3) if rows else None,
            'precision': round(sum(hit(*r[1:]) for r in mapped) / len(mapped), 3) if mapped else None,
            'precision_subtopic': round(sum(sub_hit(*r[1:]) for r in mapped) / len(mapped), 3) if mapped else None,
            'by_method': {m: {'n': n, 'precision': round(h / n, 3)} for m, (n, h) in sorted(by_method.items(), key=str)},
            'spot_check': [{'id': i, 'reference': ref, 'kind': kind, 'predicted': rec['kcs_required'],
                            'method': rec['method'], 'confidence': rec['confidence'], 'hit': hit(ref, kind, rec)}
                           for i, ref, kind, rec in mapped[:sample]],
        }
    return report


def spot_sample(mapping: dict, vault: Path, per_course: int = 30, seed: int = 20261106) -> dict:
    """Random mapped items per course for human/cheap-reviewer inspection (id, kcs, snippet)."""
    _, data = load_release(vault, mapping['release'])
    text = {i['id']: i.get('question_text', '') for i in data['items']}
    pool = collections.defaultdict(list)
    for rec in mapping['items']:
        if rec['status'] in ('mapped', 'partial'):
            pool[rec['course']].append(rec)
    result = {}
    for course, recs in sorted(pool.items()):
        random.Random(seed).shuffle(recs)
        result[course] = [{'id': r['id'], 'method': r['method'], 'kcs': r['kcs_required'], 'confidence': r['confidence'],
                           'text': re.sub(r'\s+', ' ', text[r['id']])[:160]} for r in recs[:per_course]]
    return result


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    os.replace(tmp, path)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--vault', type=Path, default=DEFAULT_VAULT)
    ap.add_argument('--release', help='Library-relative sealed release path (default: CURRENT)')
    ap.add_argument('--out', type=Path, default=WORK / 'source_topics.json')
    ap.add_argument('--evaluate', action='store_true', help='write precision report against reviewed ground truth')
    ap.add_argument('--sample', type=int, default=30)
    args = ap.parse_args(argv)
    mapping = build(args.vault, args.release)
    write_json(args.out, mapping)
    print(format_coverage(mapping['counts']))
    print('wrote', args.out)
    if args.evaluate:
        report = {'precision_against_truth': evaluate(args.vault, args.release, args.sample),
                  'mapped_samples': spot_sample(mapping, args.vault, args.sample)}
        path = args.out.with_name('source_topics_evaluation.json')
        write_json(path, report)
        for course, row in report['precision_against_truth'].items():
            print(course, {k: v for k, v in row.items() if k != 'spot_check'})
        print('wrote', path)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
