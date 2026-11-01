import json


def test_bugwatch_includes_immutable_repair_proof_dependencies():
    from bugwatch.sandbox import _references
    data = {'review': 'Library/Shared/review.json',
            'batches': [{'proposal': 'Library/Shared/proposal.json'}],
            'corrections': [{'image_reference': 'Assets/mcq/question.png'}]}
    assert set(_references(data)) == {'Library/Shared/review.json',
        'Library/Shared/proposal.json', 'Assets/mcq/question.png'}


def test_scratch_copy_includes_active_source_repair_proof_closure(tmp_path):
    from tutorlib.asset_library import AssetLibrary, write_asset
    from bugwatch.sandbox import copy_current

    source, target = tmp_path / 'source', tmp_path / 'scratch'
    source.mkdir()
    write_asset(source, 'Library/Releases/v1/manifest.json', b'{}')
    pointer = source / '.tutor/packs/CURRENT'
    pointer.parent.mkdir(parents=True)
    pointer.write_text('v1')

    image = 'Library/Courses/9702/Questions/Media/q.png'
    image_bytes = b'question image bytes'
    write_asset(source, image, image_bytes, aliases=['Assets/mcq/q.png'])
    proposal = 'Library/Courses/9702/Questions/Reviews/proposal.json'
    review = 'Library/Courses/9702/Questions/Reviews/review.json'
    write_asset(source, proposal, json.dumps({'corrections': [
        {'image_reference': 'Assets/mcq/q.png'}]}).encode())
    write_asset(source, review, json.dumps({'proposal': proposal}).encode())
    active = 'Library/Courses/9702/Questions/Reviews/source-repair-active.json'
    write_asset(source, active, json.dumps({'format_version': 1, 'batches': [
        {'proposal': proposal, 'review': review}]}).encode(), metadata={
            'kind': 'source_repair', 'subtopic': '9702-1.1'})
    superseded = 'Library/Courses/9702/Questions/Reviews/source-repair-old.json'
    write_asset(source, superseded, b'{"format_version":1,"batches":[]}', metadata={
        'kind': 'source_repair', 'subtopic': '9702-1.1', 'repair_status': 'superseded'})

    result = copy_current(source, target)
    scratch = AssetLibrary(target)
    assert result['version'] == 'v1'
    assert scratch.read(active) == (source / active).read_bytes()
    assert scratch.read(proposal) == (source / proposal).read_bytes()
    assert scratch.read(review) == (source / review).read_bytes()
    assert scratch.read('Assets/mcq/q.png') == image_bytes
    assert superseded not in {record['path'] for record in scratch.records().values()}
