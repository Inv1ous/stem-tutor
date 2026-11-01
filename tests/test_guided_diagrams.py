from build import diagrams
import json

import pytest

from tutorlib.asset_library import AssetLibrary


def test_case_split_diagram_renders_all_labels(tmp_path, monkeypatch):
    monkeypatch.setattr(diagrams, "OUT", tmp_path)
    request = {"file": "Assets/P2/cases.svg", "type": "case_split", "params": {
        "start": "Any integer n", "cases": ["n is even", "n is odd"], "end": "Both cases covered"}}
    path = diagrams.render(request)
    svg = path.read_text()
    assert all(label in svg for label in ("Any integer n", "n is even", "n is odd", "Both cases covered"))
    assert path.is_relative_to(tmp_path / 'Library/Courses/P2/Diagrams')
    assert AssetLibrary(tmp_path).read(path.relative_to(tmp_path).as_posix()) == path.read_bytes()
    assert not (tmp_path / 'Assets').exists()


def test_proof_flow_diagram_renders_each_stage(tmp_path, monkeypatch):
    monkeypatch.setattr(diagrams, "OUT", tmp_path)
    request = {"file": "Assets/P2/proof.svg", "type": "proof_flow", "params": {
        "steps": ["Given assumptions", "Logical steps", "Required conclusion"]}}
    svg = diagrams.render(request).read_text()
    assert all(label in svg for label in request["params"]["steps"])


def test_graph_sketch_can_hide_axes_for_a_schematic_net():
    figure = diagrams.graph_sketch({'lines': [{'points': [[1, 1], [2, 1]]}],
                                     'xlim': [0, 3], 'ylim': [0, 3], 'hide_axes': True})
    try:
        assert not figure.axes[0].axison
    finally:
        diagrams.plt.close(figure)


def test_graph_sketch_can_use_equal_axis_scale_for_geometry():
    figure = diagrams.graph_sketch({'lines': [{'points': [[1, 1], [2, 1]]}],
                                     'xlim': [0, 3], 'ylim': [0, 3], 'equal_aspect': True})
    try:
        assert figure.axes[0].get_aspect() == 1.0
    finally:
        diagrams.plt.close(figure)


def test_same_requested_name_never_replaces_earlier_rendered_content(tmp_path, monkeypatch):
    monkeypatch.setattr(diagrams, 'OUT', tmp_path)
    request = {'file': 'Assets/P2/proof.svg', 'type': 'proof_flow', 'params': {'steps': ['Start', 'Finish']}}
    first = diagrams.render(request)
    before = first.read_bytes()
    assert diagrams.render(request) == first
    request['params']['steps'] = ['Different start', 'New finish']
    second = diagrams.render(request)
    assert second != first
    assert first.read_bytes() == before
    assert not (tmp_path / 'Assets').exists()


def test_circuit_render_uses_registered_library_svg(tmp_path, monkeypatch):
    monkeypatch.setattr(diagrams, 'OUT', tmp_path)
    path = diagrams.render({'file': 'Assets/9702/circuit.svg', 'type': 'circuit',
                            'params': {'elements': [{'type': 'resistor', 'label': 'R'}]}})
    assert path.is_relative_to(tmp_path / 'Library/Courses/9702/Diagrams')
    assert b'<svg' in AssetLibrary(tmp_path).read(path.relative_to(tmp_path).as_posix())


def test_cli_reports_canonical_paths_without_mutating_pack(tmp_path, capsys):
    vault = tmp_path / 'STEM Tutor'
    vault.mkdir()
    pack = tmp_path / 'pack.json'
    pack.write_text(json.dumps({'diagrams': [{'file': 'Assets/generated/flow.svg', 'type': 'proof_flow',
                                            'params': {'steps': ['Start', 'Finish']}}]}))
    before = pack.read_bytes()
    diagrams.main([str(pack), '--vault', str(vault)])
    output = json.loads(capsys.readouterr().out)
    assert output['canonical'].startswith('Library/Shared/Diagrams/')
    assert output['requested'] == 'Assets/generated/flow.svg'
    assert pack.read_bytes() == before
    assert (vault / output['canonical']).is_file()


def test_renderer_refuses_symlink_library_and_traversal_request(tmp_path, monkeypatch):
    monkeypatch.setattr(diagrams, 'OUT', tmp_path)
    with pytest.raises(ValueError, match='invalid requested'):
        diagrams.render({'file': '../outside.svg', 'type': 'proof_flow', 'params': {'steps': ['Start']}})
    outside = tmp_path / 'outside'
    outside.mkdir()
    (tmp_path / 'Library').symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        diagrams.render({'file': 'Assets/P2/flow.svg', 'type': 'proof_flow', 'params': {'steps': ['Start', 'End']}})
    assert list(outside.iterdir()) == []
