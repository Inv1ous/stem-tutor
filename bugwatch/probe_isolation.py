"""Opt-in machine isolation at pytest setup; module-level actions stay the caller's responsibility."""
import importlib.util
from pathlib import Path

_source = Path(__file__).resolve().parents[1] / 'tests/conftest.py'
_spec = importlib.util.spec_from_file_location('_bugwatch_machine_isolation_fixtures', _source)
_fixtures = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_fixtures)

_no_real_ipad_inbox = _fixtures._no_real_ipad_inbox
_no_real_tutor_vault = _fixtures._no_real_tutor_vault
_no_worker_checks_in_tests = _fixtures._no_worker_checks_in_tests
