import json

import pytest

from arisctl.transcript_attestation import attest_review_transcript
from arisctl.reviews import load_review_attestation


BLOCKING_REVIEWER_ROLES = (
    "coverage_reviewer",
    "independent_problem_reviewer",
    "independent_novelty_reviewer",
    "independent_root_cause_reviewer",
    "independent_method_reviewer",
    "result_to_claim_reviewer",
)


def _transcript(path, role="coverage_reviewer", reviewer="coverage_reviewer"):
    payload = {
        "run_id": "run-1", "reviewer": reviewer, "verdict_id": "v-1",
        "decision": "CANDIDATE_SUFFICIENT", "review_request_id": "request-1",
        "reviewed_artifact_hashes": {"map": "abc"},
    }
    path.write_text("\n".join(json.dumps(item) for item in (
        {"type": "session_meta", "payload": {"thread_source": "subagent", "agent_role": role, "id": "child-1"}},
        {"type": "event_msg", "payload": {"type": "task_complete", "turn_id": "turn-1", "last_agent_message": json.dumps(payload)}},
    )), encoding="utf-8")


def _generic_coverage_transcript(path):
    payload = {
        "run_id": "run-1", "reviewer": "coverage_reviewer", "verdict_id": "v-1",
        "decision": "CANDIDATE_SUFFICIENT", "review_request_id": "request-1",
        "reviewed_artifact_hashes": {"map": "abc"},
    }
    binding = {
        "dispatch_mode": "native_generic_compat",
        "formal_role": "coverage_reviewer",
        "run_id": "run-1",
        "review_request_id": "request-1",
        "reviewed_artifact_hashes": {"map": "abc"},
    }
    path.write_text("\n".join(json.dumps(item) for item in (
        {
            "type": "session_meta",
            "payload": {
                "thread_source": "subagent",
                "id": "generic-child-1",
                "source": {"subagent": {"thread_spawn": {"task_name": "coverage"}}},
            },
        },
        {
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "user",
                "content": [{
                    "type": "input_text",
                    "text": f"ARIS_NATIVE_GENERIC_COMPAT:{json.dumps(binding)}\nreview task",
                }],
            },
        },
        {"type": "event_msg", "payload": {"type": "task_complete", "turn_id": "turn-1", "last_agent_message": json.dumps(payload)}},
    )), encoding="utf-8")


def test_transcript_verifier_writes_distinct_external_review_receipt(tmp_path, monkeypatch):
    monkeypatch.setenv("ARIS_REVIEW_ATTESTATION_ROOT", str(tmp_path / "external"))
    transcript = tmp_path / "child.jsonl"
    _transcript(transcript)
    receipt = attest_review_transcript(tmp_path, "run-1", "coverage_reviewer", transcript)
    assert receipt["attestation_source"] == "transcript_verifier"
    assert receipt["agent_id"] == "child-1"
    assert receipt["verdict_payload"]["review_request_id"] == "request-1"


def test_transcript_verifier_rejects_wrong_configured_role(tmp_path, monkeypatch):
    monkeypatch.setenv("ARIS_REVIEW_ATTESTATION_ROOT", str(tmp_path / "external"))
    transcript = tmp_path / "child.jsonl"
    _transcript(transcript, role="paper_reader")
    with pytest.raises(ValueError, match="role"):
        attest_review_transcript(tmp_path, "run-1", "coverage_reviewer", transcript)


def test_transcript_verifier_accepts_existing_generic_coverage_dispatch(tmp_path, monkeypatch):
    monkeypatch.setenv("ARIS_REVIEW_ATTESTATION_ROOT", str(tmp_path / "external"))
    transcript = tmp_path / "child.jsonl"
    _generic_coverage_transcript(transcript)

    receipt = attest_review_transcript(tmp_path, "run-1", "coverage_reviewer", transcript)

    assert receipt["agent_id"] == "generic-child-1"
    assert receipt["reviewer"] == "coverage_reviewer"


@pytest.mark.parametrize("role", BLOCKING_REVIEWER_ROLES)
def test_transcript_verifier_covers_every_blocking_gate_role(tmp_path, monkeypatch, role):
    monkeypatch.setenv("ARIS_REVIEW_ATTESTATION_ROOT", str(tmp_path / "external"))
    transcript = tmp_path / "child.jsonl"
    # The problem-quality role reports its own Codex CLI model; other current
    # scientific-core roles continue to report their independent backend model.
    reviewer = (
        "codex-gpt-5.6-sol"
        if role == "independent_problem_reviewer"
        else "gemini-verified-model"
    )
    _transcript(transcript, role=role, reviewer=reviewer)
    receipt = attest_review_transcript(tmp_path, "run-1", role, transcript)
    loaded = load_review_attestation(
        tmp_path,
        "run-1",
        role=role,
        request_id="request-1",
        artifact_bindings={"map": "abc"},
    )
    assert loaded["attestation_source"] == "transcript_verifier"
    assert loaded["verdict_payload"]["reviewer"] == reviewer
    assert loaded["reviewer"] == reviewer
    assert receipt["agent_type"] == role
