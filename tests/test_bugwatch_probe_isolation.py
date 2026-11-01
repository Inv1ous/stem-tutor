"""Scratch probes explicitly opt into the existing machine-isolation fixtures."""
import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def assert_repo_isolation(tmp_path):
    from tutor_app import config
    assert config.ICLOUD_INBOX == tmp_path / 'ipad-inbox'
    assert config.DOWNLOADS == tmp_path / 'downloads'
    assert config.CLAUDE_STATE == tmp_path / 'no-claude.json'
    assert os.environ['STEM_TUTOR_VAULT'] == str(tmp_path / 'STEM Tutor')
    assert 'TERM_PROGRAM' not in os.environ
    assert os.environ['FOUNDRY_EVIDENCE'] == '0'
    assert os.environ['FOUNDRY_PREFLIGHT'] == '0'
    assert os.environ['FOUNDRY_CLAUDE_APPS'] == str(tmp_path / 'no-claude-apps')


def test_in_repo_machine_isolation_is_unchanged(tmp_path):
    assert_repo_isolation(tmp_path)


def test_opt_in_plugin_isolates_external_probe_without_changing_repo_fixtures(tmp_path):
    # Replace all machine defaults before pytest or any repository fixture loads.
    # Neither subprocess imports the real app config or mounts an app.
    support = tmp_path / 'external'
    support.mkdir()
    defaults = support / 'machine-defaults'
    (support / 'sitecustomize.py').write_text(f'''
import os
from pathlib import Path
import sys
import types
base = Path({str(defaults)!r})
app = types.ModuleType('tutor_app')
app.__path__ = []
config = types.ModuleType('tutor_app.config')
config.ICLOUD_INBOX = base / 'inbox'
config.DOWNLOADS = base / 'downloads'
config.CLAUDE_STATE = base / 'claude.json'
panels = types.ModuleType('tutor_app.panels')
panels.Settling = type('Settling', (), {{'SETTLE': 1}})
app.config, app.panels = config, panels
sys.modules.update({{'tutor_app': app, 'tutor_app.config': config, 'tutor_app.panels': panels}})
os.environ.update({{
    'STEM_TUTOR_VAULT': str(base / 'vault'), 'TERM_PROGRAM': 'sentinel-terminal',
    'FOUNDRY_EVIDENCE': 'sentinel', 'FOUNDRY_PREFLIGHT': 'sentinel',
    'FOUNDRY_CLAUDE_APPS': str(base / 'workers'),
}})
''')
    probe = support / 'test_external.py'
    probe.write_text(f'''
import os
from pathlib import Path
from tutor_app import config


def test_external_defaults_or_opt_in_isolation(tmp_path):
    if os.environ['EXPECT_ISOLATED'] == '1':
        assert config.ICLOUD_INBOX == tmp_path / 'ipad-inbox'
        assert config.DOWNLOADS == tmp_path / 'downloads'
        assert config.CLAUDE_STATE == tmp_path / 'no-claude.json'
        assert os.environ['STEM_TUTOR_VAULT'] == str(tmp_path / 'STEM Tutor')
        assert 'TERM_PROGRAM' not in os.environ
        assert os.environ['FOUNDRY_EVIDENCE'] == '0'
        assert os.environ['FOUNDRY_PREFLIGHT'] == '0'
        assert os.environ['FOUNDRY_CLAUDE_APPS'] == str(tmp_path / 'no-claude-apps')
    else:
        base = Path({str(defaults)!r})
        assert config.ICLOUD_INBOX == base / 'inbox'
        assert config.DOWNLOADS == base / 'downloads'
        assert config.CLAUDE_STATE == base / 'claude.json'
        assert os.environ['STEM_TUTOR_VAULT'] == str(base / 'vault')
        assert os.environ['TERM_PROGRAM'] == 'sentinel-terminal'
        assert os.environ['FOUNDRY_EVIDENCE'] == 'sentinel'
        assert os.environ['FOUNDRY_PREFLIGHT'] == 'sentinel'
        assert os.environ['FOUNDRY_CLAUDE_APPS'] == str(base / 'workers')
''')
    existing = 'tests/test_bugwatch_probe_isolation.py::test_in_repo_machine_isolation_is_unchanged'
    for isolated in (False, True):
        env = {**os.environ, 'PYTHONPATH': os.pathsep.join((str(support), str(ROOT))),
               'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1', 'EXPECT_ISOLATED': str(int(isolated))}
        args = ['bash', str(ROOT / 'bugwatch/check.sh')]
        if isolated:
            args.extend(['-p', 'bugwatch.probe_isolation'])
        result = subprocess.run([*args, str(probe), existing, '-q', '--tb=short'],
                                cwd=ROOT, env=env, text=True, capture_output=True, timeout=30)
        assert result.returncode == 0, result.stdout + result.stderr
        assert '2 passed' in result.stdout
    assert not defaults.exists(), 'The probe must never access its fake machine-default folders.'
