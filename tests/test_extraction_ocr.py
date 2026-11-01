"""Unreviewed OCR is an opt-in, immutable-job-bound extraction aid only."""
import hashlib
import json
from pathlib import Path

import pytest
from PIL import Image

from test_extraction import extraction, make_pdf


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, sort_keys=True) + '\n')


def prepared(tmp_path, monkeypatch):
    ex = extraction()
    monkeypatch.setenv('STEM_EXTRACT_ROOT', str(tmp_path / 'Work'))
    monkeypatch.setenv('STEM_LIBRARY_ROOT', str(tmp_path / 'sources'))
    make_pdf(tmp_path / 'sources/scan.pdf', ['', '', ''])
    ex.create('scan', '9702', provider='codex', scope='questions')
    state = ex.inventory('scan'); source = state['sources'][0]
    assert source['status'] == 'pending_ocr'
    folder = ex.work_root() / 'Workers/extraction/ocr-cache' / source['sha256']
    folder.mkdir(parents=True)
    manifest = {'format_version': 1, 'source_id': source['id'], 'source_sha256': source['sha256'],
                'total_pages': 3, 'dpi': 180,
                'renderer': {'name': 'PyMuPDF', 'version': 'test', 'process_isolated': True},
                'native_helper_source_sha256': 'a' * 64, 'native_helper_sha256': 'b' * 64,
                'unreviewed': True, 'teaching_approved': False, 'pages': {}}
    for page in range(1, 4):
        render = folder / f'p{page:04d}.png'
        Image.new('RGB', (64, 48), 'white').save(render)
        payload = {'source_id': source['id'], 'source_sha256': source['sha256'], 'page': page,
                   'render_sha256': sha(render), 'dpi': 180, 'geometry': {'rotation': 0},
                   'width': 64, 'height': 48, 'native_helper_source_sha256': 'a' * 64,
                   'native_helper_sha256': 'b' * 64, 'unreviewed': True, 'teaching_approved': False,
                   'lines': [{'text': f'Unreviewed literal page {page}: x²', 'confidence': .91,
                              'box': {'x': .1, 'y': .5, 'width': .7, 'height': .1}}]}
        sidecar = folder / f'p{page:04d}.json'; write_json(sidecar, payload)
        manifest['pages'][str(page)] = {'path': sidecar.name, 'sha256': sha(sidecar),
                                       'render': render.name, 'render_sha256': sha(render)}
    write_json(folder / 'manifest.json', manifest)
    return ex, state, source, folder


def test_ocr_requires_opt_in_and_preserves_original_scan_status(tmp_path, monkeypatch):
    ex, state, source, folder = prepared(tmp_path, monkeypatch)
    assert callable(getattr(ex, 'enable_ocr', None)), 'job-local OCR binding is missing'
    original = Path(source['path']).read_bytes()
    with pytest.raises(ValueError, match='not enabled'):
        ex.ocr_text('scan', source['id'])
    enabled = ex.enable_ocr('scan', source['id'])
    assert enabled['sources'][0]['status'] == 'pending_ocr'
    binding = enabled['sources'][0]['ocr']
    assert binding['manifest_sha256'] == sha(folder / 'manifest.json')
    assert set(binding['pages']) == {'1', '2', '3'}
    result = ex.ocr_text('scan', source['id'], pages='2')
    assert result['unreviewed'] is True and result['teaching_approved'] is False
    assert 'UNREVIEWED' in result['warning']
    assert [row['page'] for row in result['pages']] == [2]
    assert result['pages'][0]['text'] == 'Unreviewed literal page 2: x²'
    assert result['pages'][0]['sidecar_sha256'] == binding['pages']['2']['sha256']
    assert 'lines' not in result['pages'][0]
    assert result['pages'][0]['line_count'] == 1
    assert result['pages'][0]['minimum_line_confidence'] == .91
    assert Path(source['path']).read_bytes() == original
    import library
    assert library.load(Path(source['path']), quiet=True)['scanned'] is True
    planned = ex.plan('scan')
    contract = json.loads(ex._prompt(planned, 'extract').split('JOB CONTRACT:\n')[1])
    assert 'ocr_text' in contract['source_read_commands']
    assert ex.check('scan')['stage'] == 'pending'
    assert not ex.load('scan')['teaching_approved']


@pytest.mark.parametrize('change', ['wrong-source', 'wrong-page', 'bad-confidence', 'missing-page',
                                    'render-hash', 'path-escape', 'claims-approved', 'threaded-renderer'])
def test_invalid_ocr_cache_cannot_be_bound(tmp_path, monkeypatch, change):
    ex, state, source, folder = prepared(tmp_path, monkeypatch)
    manifest = json.loads((folder / 'manifest.json').read_text())
    sidecar = folder / 'p0001.json'; payload = json.loads(sidecar.read_text())
    if change == 'wrong-source':
        payload['source_sha256'] = 'c' * 64
    elif change == 'wrong-page':
        payload['page'] = 2
    elif change == 'bad-confidence':
        payload['lines'][0]['confidence'] = 1.1
    elif change == 'missing-page':
        (folder / 'p0002.json').unlink()
    elif change == 'render-hash':
        payload['render_sha256'] = 'd' * 64
    elif change == 'path-escape':
        manifest['pages']['1']['path'] = '../outside.json'
    elif change == 'claims-approved':
        payload['teaching_approved'] = True
    else:
        manifest['renderer']['process_isolated'] = False
    write_json(sidecar, payload)
    manifest['pages']['1']['sha256'] = sha(sidecar)
    write_json(folder / 'manifest.json', manifest)
    with pytest.raises((ValueError, OSError)):
        ex.enable_ocr('scan', source['id'])
    assert 'ocr' not in ex.load('scan')['sources'][0]


@pytest.mark.parametrize('target', ['manifest.json', 'p0001.json', 'p0001.png'])
def test_bound_ocr_bytes_cannot_change_before_read_or_worker(tmp_path, monkeypatch, target):
    ex, state, source, folder = prepared(tmp_path, monkeypatch)
    ex.enable_ocr('scan', source['id'])
    path = folder / target; path.write_bytes(path.read_bytes() + b'\nchanged')
    with pytest.raises((ValueError, OSError)):
        ex.ocr_text('scan', source['id'], pages='2')
    with pytest.raises((ValueError, OSError)):
        ex._verify_sources(ex.load('scan'))


def test_ocr_selected_pages_are_frozen_before_plan(tmp_path, monkeypatch):
    ex, state, source, folder = prepared(tmp_path, monkeypatch)
    with ex.state_lock('scan') as current:
        current['sources'][0]['selected_pages'] = [2, 3]
    ex.enable_ocr('scan', source['id'])
    assert set(ex.load('scan')['sources'][0]['ocr']['pages']) == {'2', '3'}
    with pytest.raises(ValueError, match='selected'):
        ex.ocr_text('scan', source['id'], pages='1')
    ex.plan('scan')
    with pytest.raises(ValueError, match='before planning'):
        ex.enable_ocr('scan', source['id'])


def test_ocr_cli_returns_unreviewed_provenance(tmp_path, monkeypatch, capsys):
    ex, state, source, folder = prepared(tmp_path, monkeypatch)
    assert ex.main(['enable-ocr', 'scan', '--source', source['id']]) == 0
    capsys.readouterr()
    assert ex.main(['ocr-text', 'scan', '--source', source['id'], '--pages', '3']) == 0
    output = json.loads(capsys.readouterr().out)
    assert output['source_sha256'] == source['sha256']
    assert output['unreviewed'] is True and output['teaching_approved'] is False
    assert [row['page'] for row in output['pages']] == [3]


def test_page_renderer_fallback_metadata_is_preserved_without_approval(tmp_path, monkeypatch):
    ex, state, source, folder = prepared(tmp_path, monkeypatch)
    manifest = json.loads((folder / 'manifest.json').read_text())
    manifest['renderer']['fallback'] = 'Poppler'
    payload = json.loads((folder / 'p0001.json').read_text())
    payload['renderer'] = {'name': 'Poppler', 'version': 'test', 'process_isolated': True}
    payload['primary_diagnostic'] = {'renderer': 'PyMuPDF', 'warnings': ['source xref warning']}
    payload['uncertainties'] = ['Source renderer warning retained; OCR remains unreviewed.']
    write_json(folder / 'p0001.json', payload)
    manifest['pages']['1']['sha256'] = sha(folder / 'p0001.json')
    write_json(folder / 'manifest.json', manifest)
    ex.enable_ocr('scan', source['id'])
    output = ex.ocr_text('scan', source['id'], pages='1')
    assert output['pages'][0]['renderer'] == payload['renderer']
    assert output['pages'][0]['primary_diagnostic'] == payload['primary_diagnostic']
    assert output['pages'][0]['uncertainties'] == payload['uncertainties']
    assert output['unreviewed'] is True and output['teaching_approved'] is False


def test_unbound_scan_does_not_advertise_an_ocr_fallback(tmp_path, monkeypatch):
    ex, state, source, folder = prepared(tmp_path, monkeypatch)
    planned = ex.plan('scan')
    contract = json.loads(ex._prompt(planned, 'extract').split('JOB CONTRACT:\n')[1])
    assert 'ocr_text' not in contract['source_read_commands']
    assert planned['sources'][0]['status'] == 'pending_ocr'
