"""Disposable schema sentinels, never native Q1 transcription or content approval."""
import json

import library_assets
from tutorlib.asset_library import AssetLibrary, register_asset

QID = 'P1_pearson-edexcel-ial_WMA11_2019-01_01_q1'
QP = 'asset:legacy-5433803d0abf868d346949c8'
MS = 'asset:legacy-49fc389000ec4447e3b10835'


def source_fixture(vault):
    """Copy verified resources via the shared helper, retaining IDs and aliases."""
    real = library_assets._library()
    for ref in (QP, MS):
        original = real.record(ref)
        library_assets.copy_to_vault(original['path'], vault)
        catalog_path = vault / 'Library/catalog.json'
        catalog = json.loads(catalog_path.read_text())
        key = next(k for k, v in catalog['assets'].items() if v['path'] == original['path'])
        catalog['assets'].pop(key)
        catalog['assets'][ref.removeprefix('asset:')] = original
        catalog_path.write_text(json.dumps(catalog))
    return AssetLibrary(vault)


def regions(library, ref):
    return [{'source_id': ref, 'source_sha256': library.record(ref)['sha256'],
             'page': 1, 'box': [0, 0, 1, 1]}]


def p1_case(tmp_path, monkeypatch, *, whole=False):
    from test_extraction_structured import structured_case
    ex, path, q, vault, _ = structured_case(tmp_path, monkeypatch)
    lib = source_fixture(vault)
    # Real graph and generated pack are copied unchanged; KC choice is a schema
    # sentinel and asserts no relationship to the native question's mathematics.
    library_assets.install_course(vault, 'P1', 'P1-1')
    for resource in (vault / 'Library/Releases/v1').rglob('*.json'):
        register_asset(vault, resource.relative_to(vault).as_posix())
    monkeypatch.delenv('STEM_LIBRARY_ROOT', raising=False)
    q.update(id='synthetic-p1-schema-sentinel', official_qid=QID, part='',
             stem='Synthetic schema sentinel; not a native question transcription.',
             answer='Synthetic answer sentinel.', marks=1,
             scheme=[{'point': 'Synthetic schema point; not an official rubric.'}],
             syllabus=['P1-1'], kcs=['P1-1.1'], prerequisites=[],
             regions=regions(lib, QP), mark_scheme_regions=regions(lib, MS))
    if whole:
        q['scheme'] = [{'point': 'Synthetic unallocated schema sentinel.',
                        'whole_rubric': {'version': 1, 'max_marks': 1, 'media': ['official-ms.png']}}]
    with ex.state_lock('diagram') as state:
        state.update(course='P1', scope='questions', stage='planned', sources=[
            {'id': ref, 'sha256': lib.record(ref)['sha256'], 'path': str(vault / lib.record(ref)['path']),
             'kind': 'pastpapers', 'aliases': lib.record(ref)['aliases'], 'pages': pages,
             'selected_page_numbers': [1], 'status': 'available', 'error': ''}
            for ref, pages in ((QP, 28), (MS, 29))])

    def save():
        state = ex.load('diagram')
        path.write_text(json.dumps({'questions': [q], 'diagrams': [], 'source_coverage': [
            {'source_id': s['id'], 'source_sha256': s['sha256'], 'inspected_pages': [1],
             'no_relevant_content': False, 'reason': ''} for s in state['sources']]}))
        (ex.job_dir('diagram') / 'review.json').write_text(json.dumps({
            'candidate_sha256': ex.digest(path), 'verdict': 'pass', 'findings': [],
            'inspected_images': [ex.digest(path.parent / name) for name in q['media']]}))
    save()
    return ex, path, q, vault, save
