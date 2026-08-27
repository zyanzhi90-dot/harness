"""Atomic state access for controller-managed runs."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator

from tools import run_state


class _StateStore:
    def __init__(
        self,
        root: str | Path,
        run_id: str,
        workflow_sha256: str,
        workflow: dict[str, Any],
    ):
        self.root = str(Path(root))
        self.run_id = run_id
        self.workflow_sha256 = workflow_sha256
        self.workflow = workflow
        self._failure_recovery: list[Callable[[], None]] | None = None

    def _verify(self, state: dict) -> None:
        if not state.get("controller_managed"):
            raise ValueError("run is not controller-managed")
        if state.get("controller_version") != 2:
            raise ValueError("run is not managed by the current Controller version")
        if (
            state.get("workflow_sha256") != self.workflow_sha256
            and state.get("workflow") != self.workflow
        ):
            raise ValueError("formal run workflow does not match the canonical workflow")

    def load(self) -> dict:
        state = run_state._load(self.root, self.run_id)
        self._verify(state)
        return state

    @contextmanager
    def mutate(self) -> Iterator[dict]:
        with run_state._lock(self.root, self.run_id):
            state = run_state._load(self.root, self.run_id)
            self._verify(state)
            if self._failure_recovery is not None:
                raise RuntimeError("state mutations cannot be nested")
            self._failure_recovery = []
            try:
                yield state
                run_state._save(self.root, self.run_id, state)
            except BaseException:
                for recover in reversed(self._failure_recovery):
                    recover()
                raise
            finally:
                self._failure_recovery = None

    def recover_on_mutation_failure(self, recover: Callable[[], None]) -> None:
        """Restore an externally consumed proof if this state commit does not finish."""

        if self._failure_recovery is None:
            raise RuntimeError("proof recovery must be registered inside a state mutation")
        self._failure_recovery.append(recover)
