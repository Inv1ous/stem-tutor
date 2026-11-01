"""Read hash-bound native OCR aids without changing PDF text or source approval."""
from __future__ import annotations

import copy
import hashlib
import io
import json
import math
from pathlib import Path
import re


WARNING = ('UNREVIEWED NATIVE OCR: mathematical symbols, option letters and diagrams may be misread. '
           'Confidence and decoding are not visual review or teaching approval. Inspect the original PDF page.')


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _digest(value):
    return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value) is not None


def _bytes(folder, name, limit):
    if not isinstance(name, str) or Path(name).name != name or name in ('.', '..'):
        raise ValueError('unsafe OCR cache filename')
    path = folder / name
    if path.is_symlink() or path.stat().st_size > limit:
        raise ValueError('unsafe or oversized OCR cache file')
    return path.read_bytes()


def _selected(source):
    bounds = source.get('selected_pages') or [1, source['pages']]
    if (not isinstance(bounds, (list, tuple)) or len(bounds) != 2
            or any(type(v) is not int for v in bounds)
            or not 1 <= bounds[0] <= bounds[1] <= source['pages']):
        raise ValueError('invalid selected OCR source pages')
    return list(range(bounds[0], bounds[1] + 1))


def _manifest(source, root):
    if not _digest(source.get('sha256')):
        raise ValueError('invalid OCR source hash')
    folder = Path(root).resolve() / source['sha256']
    if folder.is_symlink():
        raise ValueError('unsafe OCR cache directory')
    raw = _bytes(folder, 'manifest.json', 8 * 1024 * 1024)
    data = json.loads(raw)
    renderer = data.get('renderer', {}) if isinstance(data, dict) else {}
    if (not isinstance(data, dict) or type(data.get('format_version')) is not int or data['format_version'] != 1
            or data.get('source_id') != source['id'] or data.get('source_sha256') != source['sha256']
            or type(data.get('total_pages')) is not int or data['total_pages'] != source['pages']
            or type(data.get('dpi')) is not int or data['dpi'] != 180
            or not isinstance(renderer, dict) or renderer.get('name') != 'PyMuPDF'
            or not isinstance(renderer.get('version'), str) or not renderer['version']
            or renderer.get('process_isolated') is not True
            or data.get('unreviewed') is not True or data.get('teaching_approved') is not False
            or not _digest(data.get('native_helper_source_sha256'))
            or not _digest(data.get('native_helper_sha256')) or not isinstance(data.get('pages'), dict)):
        raise ValueError('OCR manifest source, renderer or unreviewed provenance is invalid')
    return folder, raw, data


def _page(source, folder, manifest, page, entry):
    if (not isinstance(entry, dict) or entry.get('path') != f'p{page:04d}.json'
            or entry.get('render') != f'p{page:04d}.png'
            or not _digest(entry.get('sha256')) or not _digest(entry.get('render_sha256'))):
        raise ValueError(f'OCR page {page} has invalid cache paths or hashes')
    raw = _bytes(folder, entry['path'], 4 * 1024 * 1024)
    if _sha(raw) != entry['sha256']:
        raise ValueError(f'OCR page {page} sidecar hash changed')
    data = json.loads(raw)
    if (not isinstance(data, dict) or data.get('source_id') != source['id']
            or data.get('source_sha256') != source['sha256']
            or type(data.get('page')) is not int or data['page'] != page
            or data.get('render_sha256') != entry['render_sha256'] or data.get('dpi') != manifest['dpi']
            or data.get('native_helper_source_sha256') != manifest['native_helper_source_sha256']
            or data.get('native_helper_sha256') != manifest['native_helper_sha256']
            or data.get('unreviewed') is not True or data.get('teaching_approved') is not False
            or not isinstance(data.get('geometry'), dict)
            or any(type(data.get(k)) is not int or data[k] <= 0 for k in ('width', 'height'))
            or not isinstance(data.get('lines'), list)):
        raise ValueError(f'OCR page {page} source or unreviewed provenance is invalid')
    def number(value):
        return type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1
    for line in data['lines']:
        if (not isinstance(line, dict) or not isinstance(line.get('text'), str)
                or not number(line.get('confidence')) or not isinstance(line.get('box'), dict)
                or set(line['box']) != {'x', 'y', 'width', 'height'}
                or not all(number(value) for value in line['box'].values())):
            raise ValueError(f'OCR page {page} has invalid literal lines or confidence')
    render = _bytes(folder, entry['render'], 64 * 1024 * 1024)
    if _sha(render) != entry['render_sha256']:
        raise ValueError(f'OCR page {page} render hash changed')
    from PIL import Image
    try:
        with Image.open(io.BytesIO(render)) as image:
            if image.size != (data['width'], data['height']):
                raise ValueError(f'OCR page {page} render dimensions differ')
            image.verify()
    except (OSError, SyntaxError, ValueError, Image.DecompressionBombError) as exc:
        raise ValueError(f'OCR page {page} render cannot be decoded: {exc}') from exc
    return {'page': page, 'sidecar_sha256': entry['sha256'], 'render_sha256': entry['render_sha256'],
            'text': '\n'.join(line['text'] for line in data['lines']), 'lines': data['lines'],
            'geometry': data['geometry'], 'width': data['width'], 'height': data['height'],
            'renderer': copy.deepcopy(data.get('renderer')),
            'primary_diagnostic': copy.deepcopy(data.get('primary_diagnostic')),
            'uncertainties': copy.deepcopy(data.get('uncertainties', []))}


def freeze(source, root):
    """Freeze exact selected derived bytes; keep the original source status intact."""
    folder, raw, manifest = _manifest(source, root)
    entries = {}
    for page in _selected(source):
        entry = manifest['pages'].get(str(page))
        _page(source, folder, manifest, page, entry)
        entries[str(page)] = copy.deepcopy(entry)
    return {'format_version': 1, 'source_id': source['id'], 'source_sha256': source['sha256'],
            'manifest': source['sha256'] + '/manifest.json', 'manifest_sha256': _sha(raw),
            'pages': entries, 'unreviewed': True, 'teaching_approved': False}


def read(source, root, pages=None):
    """Verify all frozen input bytes before returning an optional selected subset."""
    binding = source.get('ocr')
    if not isinstance(binding, dict):
        raise ValueError('native OCR is not enabled for this job source')
    folder, raw, manifest = _manifest(source, root)
    selected = _selected(source)
    if (binding.get('format_version') != 1 or binding.get('source_id') != source['id']
            or binding.get('source_sha256') != source['sha256']
            or binding.get('manifest') != source['sha256'] + '/manifest.json'
            or binding.get('manifest_sha256') != _sha(raw)
            or binding.get('unreviewed') is not True or binding.get('teaching_approved') is not False
            or not isinstance(binding.get('pages'), dict)
            or set(binding['pages']) != {str(p) for p in selected}):
        raise ValueError('frozen OCR manifest or selected source binding changed')
    requested = selected if pages is None else list(pages)
    if any(type(p) is not int or p not in selected for p in requested):
        raise ValueError('OCR read is outside the selected source pages')
    output = []
    for page in selected:
        entry = binding['pages'][str(page)]
        if entry != manifest['pages'].get(str(page)):
            raise ValueError(f'frozen OCR page {page} manifest entry changed')
        data = _page(source, folder, manifest, page, entry)
        if page in requested:
            output.append(data)
    return {'source_id': source['id'], 'source_sha256': source['sha256'],
            'manifest_sha256': binding['manifest_sha256'], 'warning': WARNING,
            'unreviewed': True, 'visually_reviewed': False, 'teaching_approved': False, 'pages': output}
