import json
from pathlib import Path

import pytest


def test_publication_rejects_source_debris_before_touching_vault(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'build'))
    from build import topicals
    batch = tmp_path / 'batch'
    batch.mkdir()
    (batch / 'bank.json').write_text(json.dumps({'format_version': 1,
        'items': [{'id': 'q', 'stem': '2\x01 10'}]}))
    vault = tmp_path / 'vault'
    with pytest.raises(ValueError, match='source text'):
        topicals.publish(batch, vault, expected_current=None)
    assert not vault.exists()


def test_parallel_publication_keeps_one_winner_without_overwriting(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'build'))
    from build import topicals
    base = tmp_path / 'banks'
    base.mkdir()
    (base / 'CURRENT').write_text('old')
    def publish(version):
        try:
            topicals._activate_current(base, version, 'old')
            return version
        except ValueError:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(publish, ['first', 'second']))
    winners = [version for version in results if version]
    assert len(winners) == 1 and (base / 'CURRENT').read_text().strip() == winners[0]
