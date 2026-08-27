"""Externally stored, one-time attestations for Controller-issued review requests."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


def _review_root() -> Path:
    """Keep Gate attestations outside the project write surface.

    The environment override is intentionally test-only and is also useful for
    a managed host that supplies an isolated approval volume.
    """

    configured = os.environ.get("ARIS_REVIEW_ATTESTATION_ROOT")
    if configured:
        return Path(configured)
    return Path.home() / ".codex" / "aris-review-attestations"


def _project_key(root: str | Path) -> str:
    return hashlib.sha256(str(Path(root).resolve()).encode("utf-8")).hexdigest()[:20]


def review_attestation_path(
    root: str | Path, run_id: str, role: str, request_id: str
) -> Path:
    return _review_root() / _project_key(root) / run_id / role / f"{request_id}.json"


def load_review_attestation(
    root: str | Path,
    run_id: str,
    *,
    role: str,
    request_id: str,
    artifact_bindings: dict[str, str],
) -> dict[str, Any]:
    """Read (without consuming) a live reviewer response for Controller materialization."""

    source = review_attestation_path(root, run_id, role, request_id)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError("no externally attested reviewer result for the current Gate request") from exc
    expected = {
        "project_root": str(Path(root).resolve()),
        "run_id": run_id,
        "agent_type": role,
        "correlation_id": request_id,
        "artifact_bindings": artifact_bindings,
    }
    if not payload.get("agent_id") or not payload.get("turn_id") or not payload.get("payload_sha256"):
        raise ValueError("reviewer attestation lacks platform identity or payload integrity")
    if any(payload.get(key) != value for key, value in expected.items()):
        raise ValueError("reviewer attestation does not match the current Gate request")
    return payload


def consume_review_attestation(
    root: str | Path,
    run_id: str,
    *,
    role: str,
    request_id: str,
    reviewer: str,
    verdict_id: str,
    decision: str,
    artifact_bindings: dict[str, str],
) -> dict[str, Any]:
    """Consume an exact reviewer response bound to one live Gate request."""

    source = review_attestation_path(root, run_id, role, request_id)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError("no externally attested reviewer result for the current Gate request") from exc
    expected = {
        "project_root": str(Path(root).resolve()),
        "run_id": run_id,
        "agent_type": role,
        "correlation_id": request_id,
        "reviewer": reviewer,
        "verdict_id": verdict_id,
        "decision": decision,
        "artifact_bindings": artifact_bindings,
    }
    if not payload.get("agent_id") or not payload.get("turn_id") or not payload.get("payload_sha256"):
        raise ValueError("reviewer attestation lacks platform identity or payload integrity")
    if any(payload.get(key) != value for key, value in expected.items()):
        raise ValueError("reviewer attestation does not match the current Gate request")
    consumed = source.with_suffix(".consumed.json")
    try:
        source.replace(consumed)
    except OSError as exc:
        raise ValueError("reviewer attestation could not be consumed outside the project") from exc
    return payload


def restore_review_attestation(
    root: str | Path,
    run_id: str,
    *,
    role: str,
    request_id: str,
) -> None:
    """Undo an uncommitted attestation consumption without overwriting a new response."""

    source = review_attestation_path(root, run_id, role, request_id)
    consumed = source.with_suffix(".consumed.json")
    if source.exists():
        raise RuntimeError("cannot restore reviewer attestation because its live path is occupied")
    try:
        consumed.replace(source)
    except OSError as exc:
        raise RuntimeError("reviewer attestation could not be restored after a failed state commit") from exc
