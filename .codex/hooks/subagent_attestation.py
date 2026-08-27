#!/usr/bin/env python3
"""Attest structured outputs from ARIS reader and reviewer subagent roles."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

# Hooks run as standalone scripts. Resolve the checkout from this hook rather
# than relying on an editable arisctl installation or the caller's cwd.
CHECKOUT_ROOT = Path(__file__).resolve().parents[2]
if str(CHECKOUT_ROOT) not in sys.path:
    sys.path.insert(0, str(CHECKOUT_ROOT))

from arisctl.reviews import review_attestation_path


ROLE_KEYS = {
    "paper_reader": "read_event_id",
}

REVIEWER_ROLES = {
    "coverage_reviewer",
    "independent_problem_reviewer",
    "independent_novelty_reviewer",
    "independent_root_cause_reviewer",
    "independent_method_reviewer",
    "result_to_claim_reviewer",
}

COMPATIBILITY_ROLES = {"paper_reader", "coverage_reviewer"}
COMPATIBILITY_MARKER = "ARIS_NATIVE_GENERIC_COMPAT:"
TOOL_EVENT_TYPES = {
    "function_call",
    "function_call_output",
    "tool_call",
    "tool_use",
    "custom_tool_call",
    "mcp_call",
}
COMPATIBILITY_ALLOWED_TOOLS = {
    "paper_reader": set(),
    "coverage_reviewer": {"websearch", "web_search", "web.run", "web__run"},
}


def _payload(message: str) -> dict:
    text = message.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == "```":
            text = "\n".join(lines[1:-1])
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("subagent output must be one JSON object")
    return value


def _configured_agent_context(event: dict) -> tuple[str, object]:
    """Resolve the configured role for both close and natural-turn events."""
    role = str(event.get("agent_type") or "")
    agent_id = event.get("agent_id")
    if role or event.get("hook_event_name") != "Stop":
        return role, agent_id

    transcript_path = event.get("transcript_path")
    if not isinstance(transcript_path, str) or not transcript_path:
        return "", agent_id
    try:
        with Path(transcript_path).open(encoding="utf-8-sig") as stream:
            session_meta = json.loads(stream.readline())
        if session_meta.get("type") != "session_meta":
            return "", agent_id
        metadata = session_meta.get("payload")
        if not isinstance(metadata, dict) or metadata.get("thread_source") != "subagent":
            return "", agent_id
        source = metadata.get("source")
        spawn = (
            source.get("subagent", {}).get("thread_spawn", {})
            if isinstance(source, dict)
            else {}
        )
        role = str(metadata.get("agent_role") or "")
        if not role or spawn.get("agent_role") != role:
            return "", agent_id
        return role, metadata.get("id") or agent_id
    except (OSError, json.JSONDecodeError):
        return "", agent_id


def _role_contract(root: Path, role: str) -> str:
    """Load the one configured role contract; compatibility never owns a copy."""
    try:
        definition = (root / ".codex" / "agents" / f"{role}.toml").read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"cannot load configured {role} role contract") from exc
    match = re.search(r'(?ms)^developer_instructions\s*=\s*"""\r?\n?(.*?)"""', definition)
    if match is None or not match.group(1):
        raise ValueError(f"configured {role} role contract is unavailable")
    return match.group(1)


def _text_fragments(value: object) -> list[str]:
    """Extract only user task text from Codex transcript response items."""
    if not isinstance(value, dict):
        return []
    if value.get("role") == "user":
        content = value.get("content")
        if isinstance(content, str):
            return [content]
        if isinstance(content, list):
            texts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    texts.append(item)
                elif isinstance(item, dict) and isinstance(item.get("text"), str):
                    texts.append(item["text"])
            return texts
    payload = value.get("payload")
    if isinstance(payload, dict) and payload.get("role") == "user":
        return _text_fragments(payload)
    return []


def _tool_names(value: object) -> set[str]:
    """Return every actual tool call recorded in a transcript item."""
    if not isinstance(value, dict):
        return set()
    kind = str(value.get("type") or "").lower()
    if kind not in TOOL_EVENT_TYPES:
        payload = value.get("payload")
        if isinstance(payload, dict):
            return _tool_names(payload)
        return set()
    name = value.get("name") or value.get("tool_name") or value.get("tool")
    if not isinstance(name, str) or not name:
        # A recorded tool lifecycle with no name is not auditable.
        return {"<unverifiable>"}
    return {name.lower()}


def _compatibility_context(event: dict, root: Path) -> tuple[str, object, dict[str, Any]]:
    """Recognize only a transcript-bound native generic ARIS child.

    The compatibility route deliberately relies on the platform's own child
    session metadata and user task record.  It never treats a task name, root
    Stop, or a manually supplied role label as evidence of a configured role.
    """
    transcript_path = event.get("transcript_path")
    if not isinstance(transcript_path, str) or not transcript_path:
        raise ValueError("native generic compatibility requires a transcript")
    try:
        records = [json.loads(line) for line in Path(transcript_path).read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("native generic compatibility transcript is unreadable") from exc
    if not records or records[0].get("type") != "session_meta":
        raise ValueError("native generic compatibility lacks child session metadata")
    metadata = records[0].get("payload")
    if not isinstance(metadata, dict) or metadata.get("thread_source") != "subagent":
        raise ValueError("native generic compatibility is not a child session")
    source = metadata.get("source")
    if not isinstance(source, dict) or not isinstance(
        source.get("subagent", {}).get("thread_spawn"), dict
    ):
        raise ValueError("native generic compatibility lacks native spawn lifecycle")
    child_id = metadata.get("id")
    if not isinstance(child_id, str) or not child_id:
        raise ValueError("native generic compatibility lacks child identity")
    runtime_id = event.get("agent_id")
    if runtime_id is not None and runtime_id != child_id:
        raise ValueError("native generic compatibility child identity mismatch")
    # A configured profile remains on the original path and cannot be relabelled
    # as generic compatibility.
    if metadata.get("agent_role"):
        raise ValueError("native generic compatibility loaded a configured role")
    tools = set().union(*(_tool_names(record) for record in records))
    bindings: list[dict[str, Any]] = []
    for record in records:
        for text in _text_fragments(record):
            index = text.find(COMPATIBILITY_MARKER)
            if index < 0:
                continue
            raw = text[index + len(COMPATIBILITY_MARKER):].splitlines()[0].strip()
            try:
                candidate = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError("native generic compatibility task binding is invalid") from exc
            if not isinstance(candidate, dict):
                raise ValueError("native generic compatibility task binding is invalid")
            bindings.append(candidate)
    if len(bindings) != 1:
        raise ValueError("native generic compatibility requires exactly one task binding")
    binding = bindings[0]
    role = binding.get("formal_role")
    if (
        binding.get("dispatch_mode") != "native_generic_compat"
        or role not in COMPATIBILITY_ROLES
    ):
        raise ValueError("native generic compatibility has no formal ARIS binding")
    contract = _role_contract(root, str(role))
    if binding.get("role_contract_sha256") != hashlib.sha256(contract.encode("utf-8")).hexdigest():
        raise ValueError("native generic compatibility role contract hash mismatch")
    task_text = "\n".join(text for record in records for text in _text_fragments(record))
    if contract not in task_text:
        raise ValueError("native generic compatibility task does not reuse the configured role contract")
    allowed = COMPATIBILITY_ALLOWED_TOOLS[str(role)]
    unauthorized = tools - allowed
    if unauthorized:
        raise ValueError(
            "native generic compatibility used unauthorized tools: " + ", ".join(sorted(unauthorized))
        )
    return str(role), child_id, {
        "dispatch_mode": "native_generic_compat",
        "runtime_agent_identity": runtime_id or child_id,
        "child_session_identity": child_id,
        "transcript_sha256": hashlib.sha256(Path(transcript_path).read_bytes()).hexdigest(),
        "task_binding": binding,
        "observed_tool_calls": sorted(tools),
    }


def _write_once(target: Path, attestation: dict) -> None:
    """Keep Stop/SubagentStop delivery idempotent without reopening consumed proof."""
    consumed = target.with_suffix(".consumed.json")
    if consumed.exists():
        return
    if target.exists():
        try:
            existing = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            print(json.dumps({"decision": "block", "reason": "existing attestation is unreadable"}))
            return
        identity = ("agent_type", "correlation_id")
        if any(existing.get(name) != attestation.get(name) for name in identity):
            print(json.dumps({"decision": "block", "reason": "conflicting live attestation"}))
            return
        if existing.get("payload_sha256") != attestation.get("payload_sha256"):
            target.write_text(
                json.dumps(attestation, ensure_ascii=True, indent=2), encoding="utf-8"
            )
        return
    try:
        with target.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(attestation, ensure_ascii=True, indent=2))
    except FileExistsError:
        _write_once(target, attestation)


def main() -> int:
    # Codex hook events are UTF-8 JSON. Reading the byte stream explicitly
    # avoids Windows locale decoding changing non-ASCII payload characters
    # before the provenance hash is calculated.
    event = json.loads(sys.stdin.buffer.read().decode("utf-8-sig"))
    root = Path(str(event.get("cwd") or ".")).resolve()
    role, agent_id = _configured_agent_context(event)
    receipt_details: dict[str, Any] = {"dispatch_mode": "configured_role"}
    if role not in ROLE_KEYS and role not in REVIEWER_ROLES:
        try:
            role, agent_id, receipt_details = _compatibility_context(event, root)
        except ValueError as exc:
            # Only a transcript which actually requests compatibility is a
            # blocking malformed formal attempt. Ordinary generic/root Stops
            # remain unrelated and must not receive a formal ARIS receipt.
            transcript_path = event.get("transcript_path")
            if isinstance(transcript_path, str) and transcript_path:
                try:
                    transcript_text = Path(transcript_path).read_text(encoding="utf-8-sig")
                except OSError:
                    transcript_text = ""
                if COMPATIBILITY_MARKER in transcript_text:
                    print(json.dumps({"decision": "block", "reason": str(exc)}))
            return 0
    key_name = ROLE_KEYS.get(role)
    is_reviewer = role in REVIEWER_ROLES
    if key_name is None and not is_reviewer:
        return 0
    try:
        payload = _payload(str(event.get("last_assistant_message") or ""))
        correlation_id = payload.get("review_request_id") if is_reviewer else payload.get(key_name)
        if not isinstance(correlation_id, str) or not correlation_id:
            required = "review_request_id" if is_reviewer else key_name
            raise ValueError(f"{role} output requires {required}")
    except (json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"decision": "block", "reason": str(exc)}))
        return 0
    canonical = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    if is_reviewer:
        run_id = payload.get("run_id")
        bindings = payload.get("reviewed_artifact_hashes")
        for name in ("reviewer", "verdict_id", "decision"):
            if not isinstance(payload.get(name), str) or not payload[name]:
                raise ValueError(f"{role} output requires {name}")
        if not isinstance(run_id, str) or not run_id or not isinstance(bindings, dict):
            raise ValueError(f"{role} output requires run_id and reviewed_artifact_hashes")
        if role == "independent_root_cause_reviewer":
            required_verdict_fields = {
                "schema_version", "analysis_id", "reviewed_analysis_sha256",
                "problem_contract_sha256", "evidence_capsule_sha256", "reasons", "issues",
                "observation_fidelity", "grouping_adequacy", "causal_depth",
                "explanatory_coverage", "evidence_calibration", "intervention_relevance",
                "falsifiability",
            }
            missing = sorted(required_verdict_fields - set(payload))
            if missing:
                raise ValueError(
                    "independent_root_cause_reviewer must return the complete canonical verdict payload: "
                    + ", ".join(missing)
                )
        if role == "coverage_reviewer":
            required_verdict_fields = {
                "reasons", "gaps", "evolution_assessment", "reviewer_run_id",
                "reviewed_artifact_sha256",
            }
            missing = sorted(required_verdict_fields - set(payload))
            if missing:
                raise ValueError(
                    "coverage_reviewer must return the complete canonical coverage payload: "
                    + ", ".join(missing)
                )
        if role == "independent_problem_reviewer":
            records = payload.get("verdict_records")
            if not isinstance(records, list) or not records:
                raise ValueError(
                    f"{role} must return complete reviewer-owned verdict_records"
                )
        if role == "result_to_claim_reviewer":
            required_verdict_fields = {
                "schema_version", "workflow_sha256", "handoff_sha256", "rationale",
                "evidence_artifacts", "reviewed_artifact_hashes",
            }
            missing = sorted(required_verdict_fields - set(payload))
            if missing:
                raise ValueError(
                    "result_to_claim_reviewer must return the complete canonical validation verdict payload: "
                    + ", ".join(missing)
                )
            if payload.get("decision") == "VALIDATED" and "mechanism_evidence_closure" not in payload:
                raise ValueError(
                    "result_to_claim_reviewer VALIDATED payload requires mechanism_evidence_closure"
                )
        target = review_attestation_path(root, run_id, role, correlation_id)
    else:
        target = root / ".aris" / "agent-attestations" / role / f"{correlation_id}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    attestation = {
        "project_root": str(root),
        "agent_type": role,
        "agent_id": agent_id,
        "turn_id": event.get("turn_id"),
        "correlation_id": correlation_id,
        "payload_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    }
    if receipt_details["dispatch_mode"] == "native_generic_compat":
        binding = receipt_details["task_binding"]
        if role == "paper_reader":
            required = ("paper_id", "read_event_id", "content_sha256")
            if any(
                not isinstance(binding.get(name), str)
                or binding.get(name) != payload.get({"paper_id": "source_id"}.get(name, name))
                for name in required
            ):
                print(json.dumps({"decision": "block", "reason": "native generic paper_reader binding does not match Evidence Card"}))
                return 0
        else:
            if (
                binding.get("run_id") != payload.get("run_id")
                or binding.get("review_request_id") != payload.get("review_request_id")
                or binding.get("reviewed_artifact_hashes") != payload.get("reviewed_artifact_hashes")
            ):
                print(json.dumps({"decision": "block", "reason": "native generic coverage_reviewer binding does not match verdict"}))
                return 0
        attestation.update(receipt_details)
    if is_reviewer:
        attestation.update(
            {
                "run_id": payload["run_id"],
                "reviewer": payload["reviewer"],
                "verdict_id": payload["verdict_id"],
                "decision": payload["decision"],
                "artifact_bindings": payload["reviewed_artifact_hashes"],
            }
        )
        if role in {
            "coverage_reviewer", "independent_problem_reviewer",
            "independent_novelty_reviewer", "independent_root_cause_reviewer",
            "result_to_claim_reviewer",
        }:
            # The Controller, rather than Main, will validate and atomically
            # materialize this exact reviewer-owned verdict payload.
            attestation["verdict_payload"] = payload
    # Attestations are machine receipts. ASCII escapes keep the write boundary
    # stable on Windows even when project paths or agent metadata contain
    # Unicode/surrogate code units; JSON readers reconstruct the original text.
    _write_once(target, attestation)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
