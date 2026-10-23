from abc import ABC, abstractmethod
from typing import Any, ClassVar

from pydantic import BaseModel

from .contracts import SceneWorkspace


class StageAlgorithm(ABC):
    """Workspace transformation shared by real and fake Algorithms; no transport or persistence."""

    name: ClassVar[str]
    stage: ClassVar[str]
    manifest_type: ClassVar[type[BaseModel]]
    reads: ClassVar[list[str]]
    writes: ClassVar[list[str]]

    def setup(self) -> None:
        """Optional lifecycle hook; CPU Algorithms need no model initialization."""
        return None

    def download_weights(self) -> None:
        """Optional lifecycle hook; Algorithms without weights need no override (ISP)."""
        return None

    _progress = None

    def progress(self, done: int, total: int, unit: str) -> None:
        """Report progress within the current run as done of total units; a no-op without a sink."""
        if self._progress is not None:
            self._progress({"done": int(done), "total": int(total), "unit": unit})

    @abstractmethod
    def run(self, workspace: SceneWorkspace, params: dict[str, Any]) -> BaseModel: ...
