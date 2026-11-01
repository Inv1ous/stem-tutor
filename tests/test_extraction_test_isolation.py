"""Default extraction tests must not discover a real paid provider CLI."""
import shlex

import pytest

from test_extraction import extraction, make_pdf


@pytest.mark.parametrize('provider', ['codex', 'claude'])
def test_default_test_worker_cannot_fall_back_to_a_discovered_provider(tmp_path, monkeypatch, provider):
    ex = extraction()
    monkeypatch.setenv('STEM_EXTRACT_ROOT', str(tmp_path / 'Work'))
    monkeypatch.setenv('STEM_LIBRARY_ROOT', str(tmp_path / 'sources'))
    make_pdf(tmp_path / 'sources/book.pdf', ['Synthetic test input'])
    marker = tmp_path / 'discovered-provider-was-launched'
    discovered = tmp_path / provider
    discovered.write_text('#!/bin/sh\n: > ' + shlex.quote(str(marker)) + '\n')
    discovered.chmod(0o755)
    ex.create('isolation', '9702', provider=provider)
    ex.inventory('isolation')
    state = ex.plan('isolation')
    ex.candidate_path(state).parent.mkdir(parents=True)
    monkeypatch.setattr(ex.shutil, 'which', lambda name: str(discovered))

    ex._worker('isolation', 'extract')

    assert not marker.exists(), 'A test without an explicit fake CLI discovered and launched a provider.'
    result = ex.load('isolation')
    assert result['stage'] == 'pending'
    assert result['jobs']['extract']['finished']
    assert result['jobs']['extract']['exit'] != 0
