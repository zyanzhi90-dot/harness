"""Small, file-based recovery snapshots for one formal ARIS project run.

This is deliberately not a second State system.  A snapshot is simply a copy
of the project working tree at a stable point, plus a tiny note identifying the
run to resume.  The normal Controller continues to own all state transitions.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from typing import Any


RECOVERY_MANIFEST = "ARIS_RECOVERY.json"


def _run_state_path(root: Path, run_id: str) -> Path:
    safe = "".join(char for char in run_id if char.isalnum() or char in "-_.")
    if not safe or safe != run_id or run_id in {".", ".."}:
        raise ValueError(f"invalid run_id {run_id!r}")
    return root / ".aris" / "runs" / f"{run_id}.json"


def _is_within(candidate: Path, parent: Path) -> bool:
    try:
        candidate.relative_to(parent)
        return True
    except ValueError:
        return False


def save_recovery_snapshot(
    root: str | Path,
    run_id: str,
    destination: str | Path,
) -> dict[str, Any]:
    """Copy a formal project into a self-contained recovery working directory.

    The caller chooses a stable point.  No State is written or interpreted
    beyond checking that the requested Controller-managed run exists.  The
    resulting directory can be copied or moved manually and opened directly as
    the next ARIS project root.
    """

    source = Path(root).resolve()
    if not source.is_dir():
        raise ValueError(f"project root does not exist: {source}")
    state_path = _run_state_path(source, run_id)
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"no run state to save: {state_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"run state is not valid JSON: {state_path}") from exc
    if not isinstance(state, dict) or state.get("run_id") != run_id:
        raise ValueError("saved State does not match the requested run_id")
    if not state.get("controller_managed"):
        raise ValueError("recovery snapshots require a Controller-managed formal run")

    target = Path(destination).expanduser().resolve()
    if target == source or _is_within(target, source) or _is_within(source, target):
        raise ValueError("recovery destination must be a separate directory")
    if target.exists() and any(target.iterdir()):
        raise ValueError(f"recovery destination must be empty: {target}")
    target.mkdir(parents=True, exist_ok=True)

    ignored_names = {".git", "__pycache__", ".pytest_cache"}
    copied: list[str] = []
    for item in source.iterdir():
        if item.name in ignored_names:
            continue
        output = target / item.name
        if item.is_dir():
            shutil.copytree(item, output, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
        elif item.is_file():
            shutil.copy2(item, output)
        else:
            continue
        copied.append(item.name)

    manifest = {
        "schema_version": 1,
        "kind": "ARIS_PROJECT_RECOVERY_SNAPSHOT",
        "run_id": run_id,
        "source_project_root": str(source),
        "workflow_sha256": state.get("workflow_sha256"),
        "saved_research_stage": (state.get("research_lit") or {}).get("current_stage"),
        "saved_workflow_phase": (state.get("scientific_core") or {}).get("current_phase"),
        "saved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "included_project_entries": sorted(copied),
        "resume": {
            "working_directory": ".",
            "status_command": f"python -m arisctl status {run_id}",
            "start_command": f"python -m arisctl start {run_id} --executor <current-executor>",
            "note": "The copied .aris/runs State already exists; start loads it and does not create a new run.",
        },
    }
    (target / RECOVERY_MANIFEST).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "run_id": run_id,
        "snapshot_directory": str(target),
        "manifest": RECOVERY_MANIFEST,
        "copied_project_entries": sorted(copied),
    }
