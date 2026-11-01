"""Own existing worker data locations without relocating any artifacts.

FOUNDRY_ROOT selects the data tree for both workflows. Executable tools still
come from the checkout. Keeping that distinction here permits later relocation
without making one workflow depend on the other's module globals.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Mapping


def spec_of(subtopic: str) -> str:
    return subtopic.split('-', 1)[0]


def chapter_pack(packs: Path, subtopic: str) -> Path:
    return packs / spec_of(subtopic) / f'{subtopic}.json'


@dataclass(frozen=True)
class WorkerLocations:
    repository: Path
    data_root: Path

    @classmethod
    def from_environment(cls, repository: Path, environment: Mapping[str, str] | None = None):
        environment = os.environ if environment is None else environment
        return cls(Path(repository), Path(environment.get('FOUNDRY_ROOT', repository)))

    @property
    def python(self) -> str:
        return str(self.repository / '.venv/bin/python')

    @property
    def packs(self) -> Path:
        return self.data_root / 'build/out/packs'

    @property
    def specs(self) -> Path:
        return self.data_root / 'build/out/specs'

    @property
    def notes(self) -> Path:
        return self.data_root / 'build/out/notes'

    @property
    def blind(self) -> Path:
        return self.data_root / 'build/work/blind'

    @property
    def usage(self) -> Path:
        return self.data_root / 'foundry/usage.json'

    def _workflow(self, workflow: str) -> str:
        if workflow not in ('foundry', 'refine'):
            raise ValueError('unknown worker workflow')
        return workflow

    def state(self, workflow: str) -> Path:
        return self.data_root / self._workflow(workflow) / 'state'

    def logs(self, workflow: str) -> Path:
        return self.data_root / self._workflow(workflow) / 'logs'

    def work(self, workflow: str) -> Path:
        return self.data_root / 'build/work' / self._workflow(workflow)
