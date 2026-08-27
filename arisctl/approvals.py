"""One-time receipts created only after Codex permits an out-of-sandbox approval command."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from .gateways import now


def _approval_root() -> Path:
    """Keep receipts outside a workspace-write sandbox; tests monkeypatch this function."""

    return Path.home() / ".codex" / "aris-human-approvals"


def _project_key(root: str | Path) -> str:
    return hashlib.sha256(str(Path(root).resolve()).encode("utf-8")).hexdigest()[:20]


def _receipt_path(root: str | Path, run_id: str, request_id: str) -> Path:
    return _approval_root() / _project_key(root) / run_id / f"{request_id}.json"


def issue_ui_approval_receipt(
    root: str | Path,
    run_id: str,
    gate: str,
    request_id: str,
    decision: str,
    *,
    selected_id: str | None = None,
    human_feedback: str | None = None,
    artifact_bindings: dict[str, str] | None = None,
) -> Path:
    """Create the local receipt after the Codex UI has approved this CLI invocation."""

    target = _receipt_path(root, run_id, request_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise ValueError("approval request already has a receipt")
    payload = {
        "project_root": str(Path(root).resolve()),
        "run_id": run_id,
        "gate": gate,
        "request_id": request_id,
        "decision": decision,
        "selected_id": selected_id,
        "human_feedback": human_feedback,
        "artifact_bindings": dict(artifact_bindings or {}),
        "confirmed_in": "codex_ui",
        "created_at": now(),
    }
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(target, flags, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    return target


def consume_ui_approval_receipt(
    root: str | Path,
    run_id: str,
    gate: str,
    request_id: str,
    decision: str,
    *,
    selected_id: str | None = None,
    human_feedback: str | None = None,
    artifact_bindings: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Atomically mark an exact receipt consumed and return its audit metadata."""

    source = _receipt_path(root, run_id, request_id)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(
            "no Codex UI approval receipt; keep the run WAITING_FOR_HUMAN"
        ) from exc
    expected = {
        "project_root": str(Path(root).resolve()),
        "run_id": run_id,
        "gate": gate,
        "request_id": request_id,
        "decision": decision,
        "selected_id": selected_id,
        "human_feedback": human_feedback,
        "artifact_bindings": dict(artifact_bindings or {}),
        "confirmed_in": "codex_ui",
    }
    if any(payload.get(key) != value for key, value in expected.items()):
        raise ValueError("Codex UI approval receipt does not match the pending Gate")
    consumed = source.with_suffix(".consumed.json")
    try:
        source.replace(consumed)
    except OSError as exc:
        raise ValueError("approval receipt could not be consumed outside the sandbox") from exc
    payload["consumed_at"] = now()
    return payload


def restore_ui_approval_receipt(
    root: str | Path,
    run_id: str,
    request_id: str,
) -> None:
    """Undo an uncommitted receipt consumption without overwriting a new receipt."""

    source = _receipt_path(root, run_id, request_id)
    consumed = source.with_suffix(".consumed.json")
    if source.exists():
        raise RuntimeError("cannot restore approval receipt because its live path is occupied")
    try:
        consumed.replace(source)
    except OSError as exc:
        raise RuntimeError("approval receipt could not be restored after a failed state commit") from exc
