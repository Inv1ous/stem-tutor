"""Source, legacy plugin, and standalone publication share one engine."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from fixtures import make_vault


ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT / "plugin/stem-tutor/skills/tutor/scripts"


def imported_from(search, code, *, environment=None):
    env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    env.update(environment or {})
    script = "import sys; sys.path.insert(0, " + repr(str(search)) + "); " + code
    result = subprocess.run([sys.executable, "-B", "-c", script], cwd=search, env=env,
                            capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def test_source_and_legacy_imports_share_canonical_content_and_dependencies():
    code = ("from pathlib import Path; import json; from tutorlib import deps, teach_actions; "
            "print(json.dumps({'module': str(Path(teach_actions.__file__).resolve()), "
            "'repo': str(teach_actions._repo()), 'wheels': str(deps.WHEELS)}))")
    source = imported_from(ROOT / "src", code)
    legacy = imported_from(LEGACY, code)
    assert source == legacy
    assert source["module"] == str(ROOT / "src/tutorlib/teach_actions.py")
    assert source["repo"] == str(ROOT)
    assert Path(source["wheels"]).is_dir()


def test_standalone_copy_contains_regular_engine_files_and_adjacent_wheels(tmp_path):
    installed = tmp_path / "standalone-engine"
    shutil.copytree(LEGACY, installed, ignore=shutil.ignore_patterns("__pycache__"))
    assert not (installed / "tutorlib").is_symlink()
    assert not any(path.is_symlink() for path in (installed / "tutorlib").rglob("*"))
    result = imported_from(installed,
        "from pathlib import Path; import json; from tutorlib import deps, grade; "
        "print(json.dumps({'wheels': str(deps.WHEELS), 'engine': str(Path(grade.__file__).parent), "
        "'wheel_count': len(list(deps.WHEELS.glob('*.whl')))}))")
    assert result["engine"] == str(installed / "tutorlib")
    assert result["wheels"] == str(installed / "wheels")
    assert result["wheel_count"] > 0


def test_standalone_engine_cli_can_read_a_scratch_vault_without_checkout(tmp_path):
    installed = tmp_path / "engine"
    shutil.copytree(LEGACY, installed, ignore=shutil.ignore_patterns("__pycache__"))
    vault = make_vault(tmp_path / "learner")
    env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    env["STEM_TUTOR_VAULT"] = str(vault)
    env["STEM_TUTOR_DEPS"] = str(tmp_path / "isolated-wheel-cache")
    # Disable site packages so this proves vendored dependencies can bootstrap
    # the copied engine, rather than accidentally using this checkout's venv.
    result = subprocess.run([sys.executable, "-B", "-S", str(installed / "tutor.py"), "doctor"],
                            cwd=installed, env=env, capture_output=True, text=True, check=True)
    assert json.loads(result.stdout)["ok"] is True
    assert json.loads(result.stdout)["vault"] == str(vault)


def test_standalone_engine_keeps_copied_vault_guard_and_diagram_fallback(tmp_path):
    vault = tmp_path / "copied-vault"
    (vault / ".tutor").mkdir(parents=True)
    (vault / ".tutor/config.json").write_text("{}")
    installed = vault / ".tutor/engine"
    shutil.copytree(LEGACY, installed, ignore=shutil.ignore_patterns("__pycache__"))
    result = imported_from(installed,
        "import json; from tutorlib import store, teach_actions; "
        "exec(\"try:\\n store.find_vault([])\\nexcept store.VaultNotFound as exc:\\n "
        "print(json.dumps({'guarded': 'copy' in str(exc), 'drawing': "
        "teach_actions.generate_diagram(" + repr(str(vault)) + ", 'case_split', "
        "{'start':'n', 'cases':['even','odd'], 'end':'done'})[0]}))\")",
        environment={"STEM_TUTOR_VAULT": ""})
    assert result == {"guarded": True, "drawing": None}
