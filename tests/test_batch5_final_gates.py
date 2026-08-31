from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / "skills" / "shared-references" / "idea-workflow.yaml"
WORKFLOW = json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))


def phase(name: str) -> dict:
    return next(item for item in WORKFLOW["phases"] if item["phase"] == name)


def test_final_novelty_uses_only_canonical_final_method_scientific_authority() -> None:
    novelty = phase("final_method_novelty_gate")
    assert novelty["required_inputs"] == [
        "@artifact:selected_principle",
        "@artifact:final_method_packet",
        "@artifact:final_method_review",
    ]
    assert "@artifact:final_proposal" not in novelty["required_inputs"]
    assert WORKFLOW["artifact_contracts"]["final_method_packet"]["lifecycle"] == (
        "method_refinement_canonical_machine_authority"
    )
    assert WORKFLOW["artifact_contracts"]["final_proposal"]["authority"] == (
        "deterministic_view_of_final_method_packet"
    )


def test_top_venue_gate_is_the_single_canonical_pre_human_strength_gate() -> None:
    phases = WORKFLOW["scientific_core"]["phases"]
    start = phases.index("final_method_novelty_gate")
    assert phases[start : start + 3] == [
        "final_method_novelty_gate",
        "top_venue_method_strength_gate",
        "final_method_human_acceptance",
    ]
    top = phase("top_venue_method_strength_gate")
    assert top["reviewer_role"] == "independent_method_reviewer"
    assert top["scientific_history_inputs"] == [
        "@artifact:method_principles",
        "@artifact:method_test_evidence",
    ]
    assert top["produced_artifacts"] == [
        "@artifact:top_venue_method_strength_verdict"
    ]
    verdict_path = "idea-stage/TOP_VENUE_METHOD_STRENGTH_VERDICT.json"
    assert WORKFLOW["artifact_manifest"][
        "top_venue_method_strength_verdict"
    ] == verdict_path
    assert list(WORKFLOW["artifact_manifest"].values()).count(verdict_path) == 1
    assert top["accepted_verdicts"] == ["TOP_VENUE_READY"]
    assert top["return_targets"] == {
        "REVISE_METHOD": "method_refinement",
        "RETHINK_PRINCIPLE": "method_design",
        "REOPEN_RCA": "root_cause_analysis",
        "REOPEN_NECESSITY": "problem_necessity",
        "REDEFINE_PROBLEM": "problem_generation",
    }
    assert top["terminal_verdicts"] == {
        "NO_GO": {
            "action": "terminate_scientific_core",
            "status": "SCIENTIFIC_NO_GO",
        }
    }


def test_top_venue_contract_has_twelve_unscored_hard_dimensions() -> None:
    contract = WORKFLOW["artifact_contracts"]["top_venue_method_strength_verdict"]
    assert len(contract["required_dimensions"]) == 12
    assert contract["dimension_fields"] == ["judgment", "rationale"]
    assert contract["dimension_judgment_enum"] == ["PASS", "FAIL"]
    assert set(contract["forbidden_score_fields"]) == {
        "score",
        "weighted_score",
        "aggregate_score",
        "overall_score",
    }


def test_final_human_gate_requires_both_scientific_gates_and_keeps_human_view() -> None:
    human = phase("final_method_human_acceptance")
    assert human["depends_on"] == ["top_venue_method_strength_gate"]
    assert human["required_inputs"] == [
        "@artifact:selected_principle",
        "@artifact:final_proposal",
        "@artifact:final_method_novelty_verdict",
        "@artifact:top_venue_method_strength_verdict",
    ]
    assert human["accepted_decisions"] == ["approve"]
    assert human["return_targets"] == {"request_revision": "method_refinement"}


def test_batch5_contracts_and_reviewer_rules_are_mirrored() -> None:
    mirror = (
        ROOT
        / "skills"
        / "skills-codex"
        / "shared-references"
        / "idea-workflow.yaml"
    )
    assert WORKFLOW_PATH.read_text(encoding="utf-8") == mirror.read_text(
        encoding="utf-8"
    )
    assert (
        ROOT / "skills" / "shared-references" / "method-refinement-protocol.md"
    ).read_text(encoding="utf-8") == (
        ROOT
        / "skills"
        / "skills-codex"
        / "shared-references"
        / "method-refinement-protocol.md"
    ).read_text(encoding="utf-8")

    novelty = (ROOT / ".codex" / "agents" / "independent_novelty_reviewer.toml").read_text(
        encoding="utf-8"
    )
    method = (ROOT / ".codex" / "agents" / "independent_method_reviewer.toml").read_text(
        encoding="utf-8"
    )
    assert "canonical `FINAL_METHOD_PACKET.json`" in novelty
    assert "`FINAL_PROPOSAL.md` is a deterministic Human view" in novelty
    assert "Target intervention together with Mechanism Delta" in novelty
    assert "For `top_venue_method_strength_gate`" in method
    for dimension in WORKFLOW["artifact_contracts"][
        "top_venue_method_strength_verdict"
    ]["required_dimensions"]:
        assert f"`{dimension}`" in method
    assert "No weighted or aggregate score" in method


def test_selected_principle_lifecycle_matches_top_venue_return_level() -> None:
    contract = WORKFLOW["artifact_contracts"]["selected_principle"]
    assert "REVISE_METHOD" in contract["preserve_on"]
    for decision in (
        "RETHINK_PRINCIPLE",
        "REOPEN_RCA",
        "REOPEN_NECESSITY",
        "REDEFINE_PROBLEM",
    ):
        assert decision in contract["invalidate_on"]
