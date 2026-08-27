"""Fallback attestations derived from a completed native child transcript."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .reviews import review_attestation_path


_GENERIC_COMPAT_MARKER = "ARIS_NATIVE_GENERIC_COMPAT:"


def _generic_coverage_reviewer_id(
    records: list[dict[str, Any]], metadata: dict[str, Any], payload: dict[str, Any]
) -> str | None:
    """Recognize the existing generic coverage-reviewer dispatch binding."""

    if metadata.get("agent_role"):
        return None
    child_id = metadata.get("id")
    source = metadata.get("source")
    if (
        not isinstance(child_id, str)
        or not child_id
        or not isinstance(source, dict)
        or not isinstance(source.get("subagent", {}).get("thread_spawn"), dict)
    ):
        return None
    bindings: list[dict[str, Any]] = []
    for record in records:
        item = record.get("payload")
        content = item.get("content") if isinstance(item, dict) else None
        if not isinstance(content, list):
            continue
        for part in content:
            text = part.get("text") if isinstance(part, dict) else part
            if not isinstance(text, str) or _GENERIC_COMPAT_MARKER not in text:
                continue
            raw = text.split(_GENERIC_COMPAT_MARKER, 1)[1].splitlines()[0].strip()
            try:
                binding = json.loads(raw)
            except json.JSONDecodeError:
                return None
            if isinstance(binding, dict):
                bindings.append(binding)
    if len(bindings) != 1:
        return None
    binding = bindings[0]
    if (
        binding.get("dispatch_mode") != "native_generic_compat"
        or binding.get("formal_role") != "coverage_reviewer"
        or binding.get("run_id") != payload.get("run_id")
        or binding.get("review_request_id") != payload.get("review_request_id")
        or binding.get("reviewed_artifact_hashes") != payload.get("reviewed_artifact_hashes")
    ):
        return None
    return child_id


def attest_review_transcript(
    root: str | Path, run_id: str, role: str, transcript_path: str | Path
) -> dict[str, Any]:
    """Write one externally stored review receipt from an immutable child log.

    This is intentionally a distinct source from a Codex Hook: it never claims
    that a lifecycle event was dispatched.
    """
    root_path = Path(root).resolve()
    transcript = Path(transcript_path).resolve()
    records = [json.loads(line) for line in transcript.read_text(encoding="utf-8-sig").splitlines() if line]
    if not records or records[0].get("type") != "session_meta":
        raise ValueError("transcript lacks native child session metadata")
    metadata = records[0].get("payload")
    if not isinstance(metadata, dict) or metadata.get("thread_source") != "subagent":
        raise ValueError("transcript is not a native subagent session")
    completed = [record.get("payload") for record in records if record.get("type") == "event_msg"]
    task_complete = next((item for item in reversed(completed) if isinstance(item, dict) and item.get("type") == "task_complete"), None)
    if task_complete is None:
        raise ValueError("transcript has no completed child result")
    message = task_complete.get("last_agent_message")
    if not isinstance(message, str):
        raise ValueError("completed child result is unavailable")
    payload = json.loads(message)
    if not isinstance(payload, dict):
        raise ValueError("completed child result must be a JSON object")
    agent_id = metadata.get("id")
    if metadata.get("agent_role") != role:
        agent_id = (
            _generic_coverage_reviewer_id(records, metadata, payload)
            if role == "coverage_reviewer"
            else None
        )
    if not isinstance(agent_id, str) or not agent_id:
        raise ValueError("transcript role does not match requested reviewer role")
    request_id = payload.get("review_request_id")
    if not isinstance(request_id, str) or not request_id:
        raise ValueError("review payload lacks review_request_id")
    # ``role`` identifies the native Codex transport agent.  The payload's
    # ``reviewer`` identifies the independent judgment backend (including the
    # direct Codex CLI model used by the problem-quality role), so the two
    # identities must not be conflated here.  The Controller binds that value
    # to the receipt when it consumes the live Gate request.
    if payload.get("run_id") != run_id:
        raise ValueError("review payload does not match the requested run")
    reviewer = payload.get("reviewer")
    if not isinstance(reviewer, str) or not reviewer:
        raise ValueError("review payload lacks the scientific reviewer identity")
    bindings = payload.get("reviewed_artifact_hashes")
    if not isinstance(bindings, dict):
        raise ValueError("review payload lacks reviewed artifact bindings")
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    receipt = {
        "project_root": str(root_path),
        "agent_type": role,
        "agent_id": agent_id,
        "turn_id": task_complete.get("turn_id"),
        "correlation_id": request_id,
        "payload_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "run_id": run_id,
        "reviewer": reviewer,
        "verdict_id": payload.get("verdict_id"),
        "decision": payload.get("decision"),
        "artifact_bindings": bindings,
        "verdict_payload": payload,
        "attestation_source": "transcript_verifier",
        "transcript_path": str(transcript),
        "transcript_sha256": hashlib.sha256(transcript.read_bytes()).hexdigest(),
    }
    if not receipt["turn_id"] or not isinstance(receipt["verdict_id"], str) or not isinstance(receipt["decision"], str):
        raise ValueError("review payload lacks verdict identity")
    target = review_attestation_path(root_path, run_id, role, request_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.with_suffix(".consumed.json").exists():
        raise ValueError("an attestation already exists for this review request")
    target.write_text(json.dumps(receipt, ensure_ascii=True, indent=2), encoding="utf-8")
    return receipt
