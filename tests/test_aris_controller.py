from __future__ import annotations

import hashlib
import inspect
import json
import os
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest
import yaml

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 support
    import tomli as tomllib

from arisctl import ARISController, ControllerError
from arisctl import approvals, reviews
from arisctl.__main__ import build_parser, main
from arisctl.project_setup import install_project_codex_layer
from arisctl.gateways import (
    HumanSearchRequired,
    ProviderUnavailable,
    SearchOutcome,
    append_jsonl,
    ledger_event,
)
from arisctl.validators import (
    ValidationError,
    render_field_map,
    sha256_file,
    validate_candidate_verdict_artifact,
    validate_coverage_review,
    validate_evidence_card,
    validate_field_map,
    validate_method_design_packet,
    validate_method_test_result,
    validate_principle_test_plan,
    validate_principle_evaluation,
    validate_selected_principle,
    validate_query_plan,
    validate_root_cause_analysis,
    validate_root_cause_verdict,
    validate_source_admission_policy,
)
from arisctl.workflow import load_workflow
from tools.literature_coverage_audit import audit_landscape
from tools import run_state
from tests.test_batch4_final_method import final_packet as batch4_final_packet


REPO = Path(__file__).resolve().parents[1]
WORKFLOW = REPO / "skills" / "shared-references" / "idea-workflow.yaml"


@pytest.fixture(autouse=True)
def isolated_approval_receipts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(approvals, "_approval_root", lambda: tmp_path / "ui-receipts")
    monkeypatch.setenv("ARIS_REVIEW_ATTESTATION_ROOT", str(tmp_path / "review-attestations"))
    # Formal authorization uses Codex's inherited task cwd. The ordinary
    # fixtures model a correctly rooted formal project unless a test changes it.
    monkeypatch.chdir(tmp_path)


def test_scientific_core_plan_is_extensible_but_must_follow_dependencies(
    tmp_path: Path,
) -> None:
    workflow = json.loads(WORKFLOW.read_text(encoding="utf-8"))
    future_phase = {
        "phase": "future_causal_revision",
        "depends_on": ["root_cause_analysis"],
        "required_inputs": ["@artifact:root_cause_analysis"],
        "produced_artifacts": [],
        "gate_id": "future_causal_revision_completeness",
        "gate_owner": "future-research-module",
        "formal_gate": False,
        "human_checkpoint": False,
    }
    declared_index = next(
        index
        for index, item in enumerate(workflow["phases"])
        if item["phase"] == "root_cause_gate"
    )
    workflow["phases"].insert(declared_index, future_phase)
    core_index = workflow["scientific_core"]["phases"].index("root_cause_gate")
    workflow["scientific_core"]["phases"].insert(
        core_index, "future_causal_revision"
    )
    workflow["scientific_core"]["allowed_agents"]["future_causal_revision"] = [
        "main_research_agent"
    ]
    root_gate = next(
        item for item in workflow["phases"] if item["phase"] == "root_cause_gate"
    )
    root_gate["depends_on"] = ["future_causal_revision"]

    extensible = tmp_path / "extensible-workflow.json"
    extensible.write_text(json.dumps(workflow), encoding="utf-8")
    loaded = load_workflow(extensible)
    assert "future_causal_revision" in loaded["scientific_core"]["phases"]

    invalid = json.loads(json.dumps(workflow))
    phases = invalid["scientific_core"]["phases"]
    analysis_index = phases.index("root_cause_analysis")
    extension_index = phases.index("future_causal_revision")
    phases[analysis_index], phases[extension_index] = (
        phases[extension_index],
        phases[analysis_index],
    )
    invalid_path = tmp_path / "invalid-workflow.json"
    invalid_path.write_text(json.dumps(invalid), encoding="utf-8")
    with pytest.raises(ValueError, match="topologically compatible"):
        load_workflow(invalid_path)


def write_policy(root: Path) -> None:
    path = root / "idea-stage" / "SOURCE_ADMISSION_POLICY.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(policy_payload(), sort_keys=False), encoding="utf-8"
    )


def policy_payload() -> dict:
    return {
        "schema_version": 2,
        "approved_elite_venues": [
            {"canonical_name": "Test Elite Venue", "aliases": ["TEV"]}
        ],
        "high_citation_rule": {
            "thresholds": [
                {
                    "publication_year_max": 2030,
                    "citation_count_strictly_greater_than": 100,
                }
            ]
        },
        "source_tracks": {
            "user_supplied_material": {"decision": "USER_SUPPLIED_READ"}
        },
        "notes": "citation and elite gate; user supplied track",
    }


def test_source_admission_policy_rejects_overlapping_citation_year_ranges() -> None:
    policy = policy_payload()
    policy["high_citation_rule"]["thresholds"] = [
        {"publication_year_max": 2017, "citation_count_strictly_greater_than": 100},
        {
            "publication_year_min": 2017,
            "publication_year_max": 2020,
            "citation_count_strictly_greater_than": 60,
        },
    ]

    with pytest.raises(ValidationError, match="overlaps"):
        validate_source_admission_policy(policy)


def method_design_packet(*, cycle_id: str = "DESIGN-1", evidence_refs: list[str] | None = None) -> dict:
    """Return one target-state Candidate-Principle packet without concrete tests."""

    evidence_refs = list(evidence_refs or [])
    bridge_evidence = "E-BRIDGE"
    source_id = "SRC-CROSS-1"
    source_alignment_id = "ALIGN-CROSS-1"
    cross_domain_sources = []
    terminology_maps = []
    if evidence_refs:
        terminology_maps.append({
            "terminology_map_id": "TERM-1",
            "domain_hypothesis_id": "DH-MODEL-1",
            "canonical_problem_terms": ["canonical instability term"],
            "canonical_variable_state_relation_terms": ["canonical relation term"],
            "canonical_intervention_terms": ["canonical intervention term"],
            "canonical_method_families": ["canonical mechanism family"],
            "evidence_refs": evidence_refs,
            "search_read_provenance": ["query:terminology-grounding-1", "read:E-CROSS"],
            "query_plan_sha256": "2" * 64,
        })
        cross_domain_sources.append({
            "source_mechanism_id": source_id,
            "served_rmc_ids": ["RMC-1"],
            "served_capability_ids": ["CAP-1"],
            "served_obligation_ids": ["OBL-1"],
            "discovery_provenance": {
                "query_plan_sha256": "1" * 64,
                "plan_item_id": "domain-discovery-1",
                "target_mechanism_signature_ref": "TMS-1",
                "domain_hypothesis_id": "DH-MODEL-1",
                "terminology_map_id": "TERM-1",
            },
            "search_provenance": {
                "query_plan_sha256": "3" * 64,
                "plan_item_id": "source-search-1",
            },
            "genealogy": {
                "nodes": [{
                    "node_id": "GN-1",
                    "paper_id": evidence_refs[0],
                    "mechanism_role": "demonstrates the source intervention and outcome",
                    "evidence_refs": evidence_refs,
                }],
                "relations": [],
            },
            "mechanism_origin_or_stop_rationale": "The retained paper establishes the traceable mechanism origin.",
            "source_problem": "a source relation remains unstable",
            "source_root_cause": None,
            "source_intervention": "apply feedback to the unstable relation",
            "changed_variable_relation_or_structure": "the unstable relation becomes corrected",
            "causal_or_computational_effect": "feedback changes the state transition",
            "outcome": "the source failure is reduced",
            "assumptions": ["the relation is observable"],
            "activation_conditions": ["the unstable regime is active"],
            "boundaries": ["the relation must remain observable"],
            "evidence_refs": evidence_refs,
            "intervention_level_alignment": {
                "alignment_id": source_alignment_id,
                "rmc_id": "RMC-1",
                "source_mechanism_id": source_id,
                "variable_or_relation_role_mapping": "the source and Target interventions act on the same causal role",
                "change_direction_alignment": "both restore the failed relation",
                "intervention_position_alignment": "both act before the failure propagates",
                "activation_condition_alignment": "both activate in the declared unstable regime",
                "source_actual_effect": "the source relation is restored and the outcome improves",
                "assumption_boundary_mismatches": ["the physical substrate differs"],
                "decision": "PASS",
                "evidence_refs": evidence_refs,
                "solution_principle_abstraction": "Apply state-dependent feedback at the failed relation before propagation.",
                "failure_disposition": None,
            },
        })

    principles = []
    for suffix in ("A", "B"):
        source_origin = suffix == "B" and bool(evidence_refs)
        principle_id = f"PR-{suffix}"
        assumption_id = f"ASM-{suffix}"
        prediction_id = f"PRED-{suffix}"
        principles.append({
            "principle_id": principle_id,
            "principle_version": "1",
            "parent_version": None,
            "principle": (
                "Apply state-dependent feedback at the failed relation before propagation."
                if source_origin else f"Principle {suffix}"
            ),
            "origin_type": (
                "CROSS_DOMAIN_SOURCE" if source_origin
                else "FIRST_PRINCIPLES" if suffix == "A"
                else "REPRESENTATION_TRANSFORMATION"
            ),
            "origin_ref_id": source_id if source_origin else f"{'FP' if suffix == 'A' else 'REP'}-1",
            "alignment_ref_id": source_alignment_id if source_origin else None,
            "mechanism_change_ids": ["RMC-1"],
            "capability_ids": ["CAP-1"],
            "obligation_ids": ["OBL-1"],
            "causal_chain_ids": ["CHAIN-1"],
            "activation_conditions": ["declared operating condition"],
            "intervention": f"intervention {suffix}",
            "changed_structure": f"changed relation {suffix}",
            "root_cause_resolution_rationale": "closes the accepted causal chain",
            "failure_conditions": [f"failure boundary {suffix}"],
            "fatal_assumptions": [{
                "assumption_id": assumption_id,
                "assumption": f"assumption {suffix}",
                "failure_consequence": f"invalidates Principle {suffix}",
            }],
            "target_domain_operationalization": {"observable": f"signal {suffix}"},
            "target_intervention_novelty": {
                "novelty_closure_id": f"NOVELTY-{suffix}",
                "nearest_target_prior_evidence_refs": [bridge_evidence],
                "causal_equivalent_intervention_check": "UNCOVERED",
                "evidence_search_provenance": [{
                    "query_plan_sha256": "3" * 64,
                    "plan_item_id": "target-prior-1",
                    "query_id": "Q-TARGET-PRIOR",
                }],
                "uncovered_residual_delta": f"Target residual delta {suffix}",
                "mechanism_delta": f"Target mechanism delta {suffix}",
                "scientific_delta": f"Target scientific delta {suffix}",
                "disposition": "NOVEL_DELTA",
            },
            "provisional_scientific_delta": f"delta {suffix}",
            "substantive_difference": f"mechanism {suffix} changes a distinct relation",
            "predictions": [{
                "prediction_id": prediction_id,
                "assumption_ids": [assumption_id],
                "observable": f"signal {suffix}",
                "pattern_a": f"observation {suffix}",
                "rival_type": "PRINCIPLE",
                "rival_id": f"PR-{'B' if suffix == 'A' else 'A'}",
                "pattern_b": f"observation {'B' if suffix == 'A' else 'A'}",
                "activation_condition": "declared operating condition",
                "killer_criterion": f"Pattern A is absent for Principle {suffix}",
                "cheapest_informative_rationale": "One bounded observation distinguishes the mechanisms.",
            }],
            "evidence_refs": evidence_refs if source_origin else [],
            "status": "ACTIVE",
            "status_rationale": "awaiting discriminating Evidence",
        })
    return {
        "schema_version": 1,
        "design_cycle_id": cycle_id,
        "problem_binding": {
            "problem_id": "P-1",
            "problem_version": 1,
            "problem_contract_sha256": "a" * 64,
            "evidence_capsule_sha256": "b" * 64,
        },
        "root_cause_binding": {
            "analysis_id": "RCA-1",
            "analysis_sha256": "c" * 64,
            "causal_chain_ids": ["CHAIN-1"],
        },
        "primary_chain_dispositions": [{
            "causal_chain_id": "CHAIN-1",
            "disposition": "RMC",
            "mechanism_change_ids": ["RMC-1"],
            "evidence_refs": [],
            "rationale": "The accepted primary chain is consumed by RMC-1.",
        }],
        "required_mechanism_changes": [{
            "mechanism_change_id": "RMC-1",
            "causal_chain_ids": ["CHAIN-1"],
            "failed_relation_state_or_information_structure": "miscalibrated state",
            "required_mechanism_change": "restore calibrated state",
            "change_direction": "miscalibrated to calibrated",
            "causal_position": "before the failure propagates",
            "activation_condition": "the declared unstable regime",
            "root_cause_resolution_rationale": "directly intervenes on CHAIN-1",
            "capability_ids": ["CAP-1"],
            "obligation_ids": ["OBL-1"],
        }],
        "required_capabilities": [{
            "capability_id": "CAP-1",
            "mechanism_change_ids": ["RMC-1"],
            "required_capability": "represent calibrated uncertainty",
            "acceptance_conditions": ["uncertainty is calibrated"],
        }],
        "design_obligations": [{
            "obligation_id": "OBL-1",
            "mechanism_change_ids": ["RMC-1"],
            "capability_ids": ["CAP-1"],
            "design_obligation": "preserve calibration under shift",
            "acceptance_conditions": ["declared metric improves"],
        }],
        "principle_search_record": {
            "target_mechanism_signatures": [{
                "target_mechanism_signature_id": "TMS-1",
                "rmc_id": "RMC-1",
                "domain_neutral_failure_structure": "a failed relation propagates error",
                "causal_or_computational_variable_or_relation": "calibration relation",
                "current_relation_or_state": "miscalibrated",
                "required_intervention": "restore the calibration relation",
                "change_direction": "miscalibrated to calibrated",
                "causal_position": "before the failure propagates",
                "activation_condition": "the declared unstable regime",
            }],
            "first_principles": [{
                "origin_record_id": "FP-1",
                "rmc_id": "RMC-1",
                "premises": ["the failed relation is observable"],
                "derivation_steps": ["intervene before error propagation"],
                "formal_or_evidence_basis": ["bounded causal derivation"],
                "derived_intervention": "correct the relation before propagation",
                "rmc_resolution_rationale": "the intervention directly restores the failed relation",
                "assumptions": ["the relation is identifiable"],
                "boundaries": ["identifiability is retained"],
            }],
            "representation_transformations": [{
                "origin_record_id": "REP-1",
                "rmc_id": "RMC-1",
                "old_representation": "an uncalibrated scalar state",
                "new_representation": "a calibrated relational state",
                "failure_mechanism_resolution": "the new relation exposes the propagation error",
                "information_preserved": ["the target state"],
                "information_lost": [],
                "formal_or_evidence_basis": ["invertible relation on the declared envelope"],
                "assumptions": ["the mapping is identifiable"],
                "boundaries": ["the declared operating envelope"],
            }],
            "same_field_mechanisms": [],
            "cross_domain_structural_isomorphisms": cross_domain_sources,
            "discovery_executions": [{
                "discovery_execution_id": "DISC-MODEL-1",
                "rmc_id": "RMC-1",
                "target_mechanism_signature_ref": "TMS-1",
                "source_channel": "MODEL_PRIOR",
                "outcome": "HYPOTHESES_REGISTERED",
                "query_plan_sha256": None,
                "plan_item_ids": [],
                "evidence_refs": [],
                "registered_domain_hypothesis_ids": ["DH-MODEL-1"],
                "closure_rationale": "Model knowledge proposed one structural Search Hypothesis only.",
            }, {
                "discovery_execution_id": "DISC-BRIDGE-1",
                "rmc_id": "RMC-1",
                "target_mechanism_signature_ref": "TMS-1",
                "source_channel": "ACADEMIC_BRIDGE",
                "outcome": "NO_ADDITIONAL_DOMAIN_HYPOTHESIS",
                "query_plan_sha256": "1" * 64,
                "plan_item_ids": ["domain-discovery-1"],
                "evidence_refs": [bridge_evidence],
                "registered_domain_hypothesis_ids": [],
                "closure_rationale": "The scholarly bridge read yielded no additional high-value domain hypothesis.",
            }],
            "domain_hypotheses": [{
                "domain_hypothesis_id": "DH-MODEL-1",
                "rmc_id": "RMC-1",
                "target_mechanism_signature_ref": "TMS-1",
                "source_channel": "MODEL_PRIOR",
                "domain_or_research_community_or_paradigm": "relational state estimation",
                "structural_rationale": "the community intervenes on an equivalent relation",
                "expected_problem_structure": "an unstable relation propagates error",
                "expected_intervention_family": "state-dependent relational correction",
                "provenance_refs": [],
                "introduced_query_plan_sha256": "1" * 64,
                "disposition": "CLOSED",
                "closure_rationale": "The branch was searched or bounded in the accepted provenance.",
                "closure_provenance_refs": ["query:domain-discovery-1"],
            }],
            "terminology_maps": terminology_maps,
            "search_space_closures": [{
                "rmc_id": "RMC-1",
                "same_field_search_provenance": ["query:same-field-source-1"],
                "same_field_outcome": "NO_CREDIBLE_SOURCE_FOUND",
                "cross_domain_search_provenance": ["query:domain-discovery-1"],
                "cross_domain_outcome": (
                    "CREDIBLE_SOURCE_RETAINED" if evidence_refs else "NO_CREDIBLE_SOURCE_FOUND"
                ),
                "model_prior_executed": True,
                "academic_bridge_executed": True,
                "unresolved_high_value_branches": [],
                "literature_budget_disposition": "scientific closure reached before budget exhaustion",
                "closure_rationale": "Every high-value branch was explored or explicitly closed.",
            }],
            "closure_rationale": "all declared search families were recorded",
        },
        "solution_space_constraint_assessment": {
            "disposition": "UNDERCONSTRAINED",
            "constraint_basis": "The accepted RMC permits multiple distinct intervention mechanisms.",
        },
        "candidate_principles": principles,
        "relevant_history_refs": [],
        "return_feedback_refs": [],
    }


def method_design_query_provenance_fixture() -> dict[str, dict]:
    return {
        "1" * 64: {
            "order": 1,
            "is_current": False,
            "search_step_by_plan_item": {"domain-discovery-1": "DOMAIN_DISCOVERY"},
            "domain_hypothesis_ids": ["DH-MODEL-1"],
            "terminology_map_ids": [],
            "evidence_ids_by_plan_item": {"domain-discovery-1": ["E-BRIDGE"]},
            "completed_query_ids_by_plan_item": {
                "domain-discovery-1": ["Q-BRIDGE"]
            },
        },
        "2" * 64: {
            "order": 2,
            "is_current": False,
            "search_step_by_plan_item": {
                "terminology-grounding-1": "TERMINOLOGY_GROUNDING"
            },
            "domain_hypothesis_ids": [],
            "terminology_map_ids": ["TERM-1"],
            "evidence_ids_by_plan_item": {},
            "completed_query_ids_by_plan_item": {
                "terminology-grounding-1": ["Q-TERMINOLOGY"]
            },
        },
        "3" * 64: {
            "order": 3,
            "is_current": True,
            "search_step_by_plan_item": {
                "source-search-1": "SOURCE_SEARCH",
                "target-prior-1": "SOURCE_SEARCH",
            },
            "domain_hypothesis_ids": [],
            "terminology_map_ids": ["TERM-1"],
            "evidence_ids_by_plan_item": {},
            "completed_query_ids_by_plan_item": {
                "source-search-1": ["Q-SOURCE"],
                "target-prior-1": ["Q-TARGET-PRIOR"],
            },
        },
    }


def validate_packet_fixture(
    packet: dict,
    *,
    current_evidence_ids: set[str] | None = None,
    required_combine_sources: set[tuple[str, str]] | None = None,
    query_plan_provenance: dict[str, dict] | None = None,
) -> dict:
    workflow = json.loads(WORKFLOW.read_text(encoding="utf-8"))
    if query_plan_provenance is None:
        query_plan_provenance = method_design_query_provenance_fixture()
    return validate_method_design_packet(
        packet,
        contract=workflow["artifact_contracts"]["method_design_packet"],
        problem_version={
            "problem_id": "P-1", "version": 1,
            "contract_sha256": "a" * 64, "evidence_capsule_sha256": "b" * 64,
        },
        root_cause_analysis_id="RCA-1",
        root_cause_analysis_sha256="c" * 64,
        primary_causal_chain_ids={"CHAIN-1"},
        current_evidence_ids=current_evidence_ids,
        required_combine_sources=required_combine_sources,
        query_plan_provenance=query_plan_provenance,
    )


def principle_test_plan(
    selected_for_testing: dict,
    *,
    cycle_id: str = "CYCLE-1",
    relevant_history_refs: list[str] | None = None,
    return_feedback_refs: list[str] | None = None,
) -> dict:
    binding_fields = (
        "selection_request_id", "principle_id", "principle_version",
        "method_design_packet", "method_design_review",
    )
    return {
        "schema_version": 1,
        "cycle_id": cycle_id,
        "execution_set_id": f"EXEC-{cycle_id}",
        "selected_for_testing_binding": {
            field: deepcopy(selected_for_testing[field]) for field in binding_fields
        },
        "test_strategy": {
            "fatal_assumption_priority": ["ASM-A"],
            "minimum_sufficiency_rationale": "One existing-data probe resolves the fatal assumption.",
            "highest_information_gain_rationale": "The outcome directly separates survival from falsification.",
            "lower_cost_evidence_assessment": "Existing data is sufficient; no larger experiment is needed.",
            "physical_experiment_escalation_justification": "Not escalated because existing data can decide the question.",
        },
        "discriminating_tests": [{
            "test_id": "TEST-FATAL-A",
            "test_type": "existing_data_probe",
            "evidence_tier": "EXISTING_DATA_ANALYSIS",
            "killer_test_concept_ref": "PRED-A",
            "operationalization": "Measure the selected Candidate's predicted signal.",
            "test_only_concrete_realization": {"probe": "bounded analysis"},
            "observation_contract": {
                "observable": "signal A",
                "pattern_a": "observation A",
                "rival_type": "PRINCIPLE",
                "rival_id": "PR-B",
                "pattern_b": "observation B",
                "activation_condition": "declared operating condition",
            },
            "terminal_criteria": {
                "pattern_a_criterion": "The observation matches Pattern A.",
                "pattern_b_criterion": "The observation matches Pattern B.",
                "inconclusive_criterion": "Neither bounded pattern is resolved.",
            },
            "targets": [{
                "principle_id": "PR-A",
                "principle_version": "1",
                "assumption_id": "ASM-A",
                "prediction_id": "PRED-A",
                "mechanism_change_id": "RMC-1",
                "causal_chain_id": "CHAIN-1",
            }],
            "information_gain": "A contrary observation falsifies the fatal assumption.",
            "falsification_criterion": "The declared signal is absent under the activation condition.",
            "execution_requirements": {"budget": "one bounded analysis"},
            "estimated_cost": 1,
            "terminal_outcome_contract": ["RESULT_AVAILABLE", "NO_RESULT"],
        }],
        "recommended_execution_set": {
            "execution_set_id": f"EXEC-{cycle_id}",
            "test_ids": ["TEST-FATAL-A"],
            "estimated_total_cost": 1,
        },
        "estimated_total_cost": 1,
        "relevant_history_refs": list(relevant_history_refs or []),
        "return_feedback_refs": list(return_feedback_refs or []),
    }


def test_method_design_packet_closes_rmc_capability_obligation_and_candidate_bindings() -> None:
    validated = validate_packet_fixture(
        method_design_packet(evidence_refs=["E-CROSS"]),
        current_evidence_ids={"E-BRIDGE", "E-CROSS"},
    )
    assert validated["mechanism_change_ids"] == ["RMC-1"]
    assert validated["capability_ids"] == ["CAP-1"]
    assert validated["obligation_ids"] == ["OBL-1"]
    assert validated["principle_keys"] == [("PR-A", "1"), ("PR-B", "1")]
    assert validated["design_cycle_id"] == "DESIGN-1"
    assert not any(
        field in validated["packet"]
        for field in ("discriminating_tests", "recommended_execution_set", "estimated_total_cost")
    )
    with_tests = method_design_packet()
    with_tests["discriminating_tests"] = []
    with pytest.raises(ValidationError, match="must not contain test design fields"):
        validate_packet_fixture(with_tests)
    candidate_with_tests = method_design_packet()
    candidate_with_tests["candidate_principles"][0]["proposed_test_ids"] = ["TEST-OLD"]
    with pytest.raises(ValidationError, match="must not contain test design fields"):
        validate_packet_fixture(candidate_with_tests)


def test_solution_space_constraint_controls_real_competition_without_a_candidate_quota() -> None:
    packet = method_design_packet()
    packet["candidate_principles"] = packet["candidate_principles"][:1]
    packet["candidate_principles"][0]["predictions"][0].update(
        rival_type="RIVAL_RCA", rival_id="ALT-1", pattern_b="alternative RCA pattern"
    )
    with pytest.raises(ValidationError, match="UNDERCONSTRAINED.*multiple"):
        validate_packet_fixture(packet)

    packet["solution_space_constraint_assessment"] = {
        "disposition": "CONSTRAINED",
        "constraint_basis": "Only one intervention position remains compatible with the accepted RMC.",
    }
    validated = validate_packet_fixture(packet)
    assert validated["principle_keys"] == [("PR-A", "1")]

    semantically_false = method_design_packet()
    semantically_false["solution_space_constraint_assessment"] = {
        "disposition": "CONSTRAINED",
        "constraint_basis": "Both Candidates use different optimizer names.",
    }
    validate_packet_fixture(semantically_false)
    reviewer = (REPO / ".codex" / "agents" / "independent_method_reviewer.toml").read_text(encoding="utf-8")
    assert "module differences do not create competition" in reviewer


def test_killer_concept_stays_pre_selection_and_concrete_test_consumes_pattern_binding() -> None:
    packet = method_design_packet()
    candidate = packet["candidate_principles"][0]
    candidate["test_operationalization"] = "premature concrete procedure"
    with pytest.raises(ValidationError, match="must not contain test design fields"):
        validate_packet_fixture(packet)

    workflow = json.loads(WORKFLOW.read_text(encoding="utf-8"))
    selection = {
        "selection_request_id": "selection-1", "principle_id": "PR-A",
        "principle_version": "1",
        "method_design_packet": {"path": "idea-stage/METHOD_DESIGN_PACKET.json", "sha256": "a" * 64},
        "method_design_review": {"path": "idea-stage/METHOD_DESIGN_REVIEW.json", "sha256": "b" * 64},
    }
    plan = principle_test_plan(selection)
    validate_principle_test_plan(
        plan,
        contract=workflow["artifact_contracts"]["principle_test_plan"],
        selected_for_testing=selection,
        candidate=method_design_packet()["candidate_principles"][0],
    )
    stale = deepcopy(plan)
    stale["discriminating_tests"][0]["observation_contract"]["pattern_b"] = "post-selection rival rewrite"
    with pytest.raises(ValidationError, match="Pattern A/B"):
        validate_principle_test_plan(
            stale,
            contract=workflow["artifact_contracts"]["principle_test_plan"],
            selected_for_testing=selection,
            candidate=method_design_packet()["candidate_principles"][0],
        )

    performance_only = deepcopy(plan)
    performance_only["discriminating_tests"][0]["information_gain"] = "Reports aggregate performance only."
    validate_principle_test_plan(
        performance_only,
        contract=workflow["artifact_contracts"]["principle_test_plan"],
        selected_for_testing=selection,
        candidate=method_design_packet()["candidate_principles"][0],
    )
    reviewer = (REPO / ".codex" / "agents" / "independent_method_reviewer.toml").read_text(encoding="utf-8")
    assert "performance-only ablation is not automatically discriminating" in reviewer


def test_derivation_origins_need_no_literature_query_and_scientific_quality_is_reviewer_owned() -> None:
    packet = method_design_packet()
    packet["principle_search_record"]["first_principles"][0].update({
        "premises": ["placeholder premise"],
        "derivation_steps": ["placeholder inference"],
        "formal_or_evidence_basis": ["placeholder basis"],
        "derived_intervention": "placeholder intervention",
        "rmc_resolution_rationale": "placeholder rationale",
    })
    packet["principle_search_record"]["representation_transformations"][0].update({
        "old_representation": "placeholder old representation",
        "new_representation": "placeholder new representation",
        "failure_mechanism_resolution": "placeholder resolution",
        "formal_or_evidence_basis": ["placeholder basis"],
    })

    validated = validate_packet_fixture(packet)
    origins = {
        candidate["origin_type"] for candidate in validated["packet"]["candidate_principles"]
    }
    assert origins == {"FIRST_PRINCIPLES", "REPRESENTATION_TRANSFORMATION"}
    assert all(
        "query_plan_sha256" not in record
        for field in ("first_principles", "representation_transformations")
        for record in validated["packet"]["principle_search_record"][field]
    )
    reviewer = (REPO / ".codex" / "agents" / "independent_method_reviewer.toml").read_text(
        encoding="utf-8"
    )
    assert "structurally valid but scientifically empty derivation" in reviewer


def test_academic_bridge_can_close_without_fabricating_a_domain_hypothesis() -> None:
    plan_sha = "1" * 64
    provenance = method_design_query_provenance_fixture()
    packet = method_design_packet()
    validated = validate_packet_fixture(
        packet,
        current_evidence_ids={"E-BRIDGE"},
        query_plan_provenance=provenance,
    )
    bridge = validated["packet"]["principle_search_record"]["discovery_executions"][1]
    assert bridge["outcome"] == "NO_ADDITIONAL_DOMAIN_HYPOTHESIS"
    assert bridge["registered_domain_hypothesis_ids"] == []

    missing_read = deepcopy(provenance)
    missing_read[plan_sha]["evidence_ids_by_plan_item"] = {}
    with pytest.raises(ValidationError, match="scholarly read provenance"):
        validate_packet_fixture(
            packet,
            current_evidence_ids={"E-BRIDGE"},
            query_plan_provenance=missing_read,
        )


def test_early_target_novelty_accepts_real_current_completed_query_provenance() -> None:
    packet = method_design_packet()
    validated = validate_packet_fixture(
        packet,
        query_plan_provenance=method_design_query_provenance_fixture(),
    )
    assert validated["packet"]["candidate_principles"][0][
        "target_intervention_novelty"
    ]["evidence_search_provenance"] == [{
        "query_plan_sha256": "3" * 64,
        "plan_item_id": "target-prior-1",
        "query_id": "Q-TARGET-PRIOR",
    }]


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda packet, provenance: packet["candidate_principles"][0][
                "target_intervention_novelty"
            ].update(evidence_search_provenance=["query:forged-target-prior"]),
            "must be a JSON object",
        ),
        (
            lambda packet, provenance: packet["candidate_principles"][0][
                "target_intervention_novelty"
            ]["evidence_search_provenance"][0].update(query_plan_sha256="f" * 64),
            "unknown accepted Method Design Query Plan",
        ),
        (
            lambda packet, provenance: packet["candidate_principles"][0][
                "target_intervention_novelty"
            ]["evidence_search_provenance"][0].update(plan_item_id="missing-plan-item"),
            "unknown Method Design plan item",
        ),
        (
            lambda packet, provenance: provenance["3" * 64][
                "completed_query_ids_by_plan_item"
            ].update({"target-prior-1": []}),
            "completed current Method Design query event",
        ),
        (
            lambda packet, provenance: provenance["3" * 64].update(is_current=False),
            "stale Method Design Query Plan",
        ),
    ],
)
def test_early_target_novelty_rejects_forged_unknown_unfinished_or_stale_provenance(
    mutation,
    message: str,
) -> None:
    packet = method_design_packet()
    provenance = method_design_query_provenance_fixture()
    mutation(packet, provenance)
    with pytest.raises(ValidationError, match=message):
        validate_packet_fixture(packet, query_plan_provenance=provenance)


def test_source_efficacy_alignment_and_target_novelty_are_hard_machine_gates() -> None:
    packet = method_design_packet(evidence_refs=["E-CROSS"])
    source = packet["principle_search_record"]["cross_domain_structural_isomorphisms"][0]
    source["evidence_refs"] = []
    with pytest.raises(ValidationError, match="evidence_refs"):
        validate_packet_fixture(packet, current_evidence_ids={"E-BRIDGE", "E-CROSS"})

    packet = method_design_packet(evidence_refs=["E-CROSS"])
    alignment = packet["principle_search_record"]["cross_domain_structural_isomorphisms"][0][
        "intervention_level_alignment"
    ]
    alignment.update({
        "decision": "FAIL",
        "solution_principle_abstraction": None,
        "failure_disposition": "The intervention changes a different causal relation.",
    })
    with pytest.raises(ValidationError, match="accepted intervention-level alignment"):
        validate_packet_fixture(packet, current_evidence_ids={"E-BRIDGE", "E-CROSS"})

    packet = method_design_packet()
    novelty = packet["candidate_principles"][0]["target_intervention_novelty"]
    novelty.update({
        "causal_equivalent_intervention_check": "COVERED",
        "disposition": "REJECTED_AS_COVERED",
    })
    with pytest.raises(ValidationError, match="causal-equivalent intervention"):
        validate_packet_fixture(packet)


def test_post_hoc_cross_domain_discovery_and_unresolved_budget_closure_are_rejected() -> None:
    packet = method_design_packet(evidence_refs=["E-CROSS"])
    provenance = method_design_query_provenance_fixture()
    provenance["1" * 64]["order"] = 3
    provenance["3" * 64]["order"] = 1
    with pytest.raises(ValidationError, match="pre-Source discovery and terminology"):
        validate_packet_fixture(
            packet,
            current_evidence_ids={"E-BRIDGE", "E-CROSS"},
            query_plan_provenance=provenance,
        )

    packet = method_design_packet()
    packet["principle_search_record"]["search_space_closures"][0][
        "unresolved_high_value_branches"
    ] = ["a high-value intervention branch remains unread"]
    packet["principle_search_record"]["search_space_closures"][0][
        "literature_budget_disposition"
    ] = "fixed budget exhausted"
    with pytest.raises(ValidationError, match="fixed search budget"):
        validate_packet_fixture(packet)


def test_method_design_synthesis_lineage_requires_current_multi_candidate_sources() -> None:
    sources = {("PR-A", "1"), ("PR-B", "1")}
    packet = method_design_packet()
    old_synthesis = deepcopy(packet["candidate_principles"][0])
    old_synthesis.update(
        {
            "principle_id": "PR-S-OLD",
            "principle_version": "1",
            "parent_version": None,
            "principle": "Earlier Synthesis Principle",
            "intervention": "retain an earlier coupled causal intervention",
            "changed_structure": "the earlier coupled relation between mechanisms",
            "substantive_difference": "mechanism-level synthesis of historical sources",
            "derived_from_principles": [
                {"principle_id": "PR-C", "principle_version": "1"},
                {"principle_id": "PR-D", "principle_version": "1"},
            ],
        }
    )
    synthesis = deepcopy(packet["candidate_principles"][0])
    synthesis.update(
        {
            "principle_id": "PR-S",
            "principle_version": "1",
            "parent_version": None,
            "principle": "Synthesis Principle",
            "intervention": "synthesize the two causal interventions",
            "changed_structure": "the coupled relation between the two mechanisms",
            "substantive_difference": "mechanism-level synthesis of PR-A and PR-B",
            "derived_from_principles": [
                {"principle_id": "PR-A", "principle_version": "1"},
                {"principle_id": "PR-B", "principle_version": "1"},
            ],
        }
    )
    packet["candidate_principles"].append(old_synthesis)
    packet["candidate_principles"].append(synthesis)
    validate_packet_fixture(packet, required_combine_sources=sources)

    no_current_synthesis = deepcopy(packet)
    no_current_synthesis["candidate_principles"].pop()
    with pytest.raises(ValidationError, match="no synthesis Candidate"):
        validate_packet_fixture(no_current_synthesis, required_combine_sources=sources)

    too_few = deepcopy(packet)
    too_few["candidate_principles"][-1]["derived_from_principles"] = [
        {"principle_id": "PR-A", "principle_version": "1"}
    ]
    with pytest.raises(ValidationError, match="at least two sources"):
        validate_packet_fixture(too_few, required_combine_sources=sources)

    dangling = deepcopy(packet)
    dangling["candidate_principles"][-1]["derived_from_principles"][1] = {
        "principle_id": "PR-MISSING", "principle_version": "1"
    }
    with pytest.raises(ValidationError, match="no synthesis Candidate"):
        validate_packet_fixture(dangling, required_combine_sources=sources)

    stale = deepcopy(packet)
    stale["candidate_principles"][-1]["derived_from_principles"][1] = {
        "principle_id": "PR-B", "principle_version": "0"
    }
    with pytest.raises(ValidationError, match="no synthesis Candidate"):
        validate_packet_fixture(stale, required_combine_sources=sources)

    duplicate = deepcopy(packet)
    duplicate["candidate_principles"][-1]["derived_from_principles"] = [
        {"principle_id": "PR-A", "principle_version": "1"},
        {"principle_id": "PR-A", "principle_version": "1"},
    ]
    with pytest.raises(ValidationError, match="contains duplicates"):
        validate_packet_fixture(duplicate, required_combine_sources=sources)

    ordinary = method_design_packet()
    revision = deepcopy(ordinary["candidate_principles"][0])
    revision["principle_version"] = "2"
    revision["parent_version"] = "1"
    ordinary["candidate_principles"].append(revision)
    validate_packet_fixture(ordinary)


def test_principle_test_plan_is_selected_candidate_only_and_atomic() -> None:
    workflow = json.loads(WORKFLOW.read_text(encoding="utf-8"))
    packet = method_design_packet()
    selection = {
        "selection_request_id": "selection-1",
        "principle_id": "PR-A",
        "principle_version": "1",
        "method_design_packet": {"path": "idea-stage/METHOD_DESIGN_PACKET.json", "sha256": "a" * 64},
        "method_design_review": {"path": "idea-stage/METHOD_DESIGN_REVIEW.json", "sha256": "b" * 64},
    }
    plan = principle_test_plan(selection)
    validated = validate_principle_test_plan(
        plan,
        contract=workflow["artifact_contracts"]["principle_test_plan"],
        selected_for_testing=selection,
        candidate=packet["candidate_principles"][0],
    )
    assert validated["approved_test_ids"] == ["TEST-FATAL-A"]
    broken = deepcopy(plan)
    broken["discriminating_tests"][0]["targets"][0]["principle_id"] = "PR-B"
    with pytest.raises(ValidationError, match="non-selected"):
        validate_principle_test_plan(
            broken,
            contract=workflow["artifact_contracts"]["principle_test_plan"],
            selected_for_testing=selection,
            candidate=packet["candidate_principles"][0],
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda packet: packet["required_capabilities"][0].update(mechanism_change_ids=["RMC-MISSING"]), "unknown mechanism change"),
        (lambda packet: packet["candidate_principles"][0].update(causal_chain_ids=["CHAIN-MISSING"]), "unresolved ID"),
        (lambda packet: packet["candidate_principles"][0].update(substantive_difference=""), "substantive_difference"),
    ],
)
def test_method_design_packet_rejects_broken_machine_bindings(mutation, message: str) -> None:
    packet = method_design_packet()
    mutation(packet)
    with pytest.raises(ValidationError, match=message):
        validate_packet_fixture(packet)


def test_candidate_principle_version_lineage_and_cross_domain_evidence_are_mechanical() -> None:
    packet = method_design_packet(evidence_refs=["E-CROSS"])
    packet["candidate_principles"][0]["parent_version"] = "1"
    with pytest.raises(ValidationError, match="earlier version"):
        validate_packet_fixture(packet, current_evidence_ids={"E-BRIDGE", "E-CROSS"})
    packet = method_design_packet(evidence_refs=["E-CROSS"])
    with pytest.raises(ValidationError, match="outside the current formal context"):
        validate_packet_fixture(packet, current_evidence_ids={"E-OTHER"})


def test_terminal_result_identity_and_no_result_do_not_mechanically_reject_a_principle() -> None:
    no_result = {
        "schema_version": 1,
        "cycle_id": "CYCLE-1",
        "execution_set_id": "EXEC-CYCLE-1",
        "test_id": "TEST-SHARED",
        "outcome": "NO_RESULT",
        "result_refs": [],
        "reason": "unavailable",
        "execution_metadata": {"runner": "fixture"},
    }
    validated = validate_method_test_result(
        no_result,
        cycle_id="CYCLE-1",
        execution_set_id="EXEC-CYCLE-1",
        approved_test_ids={"TEST-SHARED"},
        no_result_reasons={"unavailable"},
    )
    assert validated["outcome"] == "NO_RESULT"
    assert "decision" not in validated

    wrong_test = {**no_result, "test_id": "TEST-UNAPPROVED"}
    with pytest.raises(ValidationError, match="approved execution set"):
        validate_method_test_result(
            wrong_test,
            cycle_id="CYCLE-1",
            execution_set_id="EXEC-CYCLE-1",
            approved_test_ids={"TEST-SHARED"},
            no_result_reasons={"unavailable"},
        )

    workflow = json.loads(WORKFLOW.read_text(encoding="utf-8"))
    evaluation = {
        "schema_version": 1,
        "cycle_id": "CYCLE-1",
        "execution_set_id": "EXEC-CYCLE-1",
        "evidence_context_ref": {"path": "idea-stage/PRINCIPLE_EVIDENCE_CONTEXT.json", "sha256": "d" * 64},
        "operationalization_assessments": [{
            "test_id": "TEST-FATAL-A", "status": "UNRESOLVED", "evidence_refs": [],
            "rationale": "No usable result was produced.",
        }],
        "test_validity_assessments": [{
            "test_id": "TEST-FATAL-A", "status": "UNRESOLVED",
            "discriminativeness": "UNRESOLVED", "evidence_refs": [],
            "rationale": "The terminal outcome was uninformative.",
        }],
        "activation_condition_assessments": [{
            "test_id": "TEST-FATAL-A", "prediction_id": "PRED-A",
            "status": "UNRESOLVED", "evidence_refs": [],
            "rationale": "Activation was not observed.",
        }],
        "prediction_comparisons": [{
            "test_id": "TEST-FATAL-A", "prediction_id": "PRED-A",
            "observable": "signal A", "observed_pattern": "No result",
            "rival_type": "PRINCIPLE", "rival_id": "PR-B",
            "rival_discrimination": "INCONCLUSIVE", "evidence_refs": [],
            "rationale": "No Pattern A/B comparison is available.",
        }],
        "scientific_updates": [{
            "update_id": "UPDATE-1", "target_type": "PRINCIPLE", "target_id": "PR-A@1",
            "before": "untested", "proposed_after": "unresolved", "evidence_refs": [],
            "consequence": "MORE_EVIDENCE", "rationale": "NO_RESULT carries no Principle judgment.",
        }],
        "remaining_uncertainties": ["test remains unresolved"],
        "relevant_history_refs": [],
        "return_feedback_refs": [],
    }
    validate_principle_evaluation(
        evaluation,
        contract=workflow["artifact_contracts"]["principle_evaluation"],
        cycle_id="CYCLE-1",
        execution_set_id="EXEC-CYCLE-1",
        evidence_context_ref=evaluation["evidence_context_ref"],
        test_plan=principle_test_plan({
            "selection_request_id": "selection-1", "principle_id": "PR-A",
            "principle_version": "1",
            "method_design_packet": {"path": "idea-stage/METHOD_DESIGN_PACKET.json", "sha256": "a" * 64},
            "method_design_review": {"path": "idea-stage/METHOD_DESIGN_REVIEW.json", "sha256": "b" * 64},
        }),
        candidate=method_design_packet()["candidate_principles"][0],
        root_cause_analysis_id="RCA-1",
        necessity_residual_ids={"RF-1"},
        current_evidence_refs=set(),
    )
    rejected = deepcopy(evaluation)
    rejected["scientific_updates"][0]["consequence"] = "RETURN_METHOD_DESIGN"
    validate_principle_evaluation(
        rejected,
        contract=workflow["artifact_contracts"]["principle_evaluation"],
        cycle_id="CYCLE-1",
        execution_set_id="EXEC-CYCLE-1",
        evidence_context_ref=evaluation["evidence_context_ref"],
        test_plan=principle_test_plan({
            "selection_request_id": "selection-1", "principle_id": "PR-A",
            "principle_version": "1",
            "method_design_packet": {"path": "idea-stage/METHOD_DESIGN_PACKET.json", "sha256": "a" * 64},
            "method_design_review": {"path": "idea-stage/METHOD_DESIGN_REVIEW.json", "sha256": "b" * 64},
        }),
        candidate=method_design_packet()["candidate_principles"][0],
        root_cause_analysis_id="RCA-1",
        necessity_residual_ids={"RF-1"},
        current_evidence_refs=set(),
    )
    reviewer = (REPO / ".codex" / "agents" / "independent_method_reviewer.toml").read_text(encoding="utf-8")
    assert "NO_RESULT` cannot support or reject" in reviewer


def test_selected_principle_recovers_reviewed_obligations() -> None:
    workflow = json.loads(WORKFLOW.read_text(encoding="utf-8"))
    packet = method_design_packet()
    candidate = packet["candidate_principles"][0]
    evaluation = {
        "scientific_updates": [
            {
                "update_id": "UPDATE-BOUNDARY", "target_type": "APPLICABILITY_BOUNDARY",
                "target_id": "PR-A@1", "before": "broad", "proposed_after": "declared scope",
                "evidence_refs": ["results/principle.json"], "consequence": "UPDATE_BOUNDARY",
                "rationale": "The bound Evidence supports this boundary.",
            },
            {
                "update_id": "UPDATE-PROPOSAL", "target_type": "APPLICABILITY_BOUNDARY",
                "target_id": "PR-A@1", "before": "declared scope",
                "proposed_after": "narrower proposed scope",
                "evidence_refs": ["results/principle.json"],
                "consequence": "UPDATE_BOUNDARY",
                "rationale": "This unaccepted boundary proposal remains outside selected authority.",
            },
        ]
    }
    selected = {
        "schema_version": 1,
        "principle_id": "PR-A",
        "principle_version": "1",
        "principle": candidate["principle"],
        "intervention": candidate["intervention"],
        "changed_structure": candidate["changed_structure"],
        "problem_binding": packet["problem_binding"],
        "root_cause_binding": packet["root_cause_binding"],
        "causal_chain_ids": candidate["causal_chain_ids"],
        "mechanism_change_ids": candidate["mechanism_change_ids"],
        "capability_ids": candidate["capability_ids"],
        "obligation_ids": candidate["obligation_ids"],
        "origin_binding": {
            "origin_type": candidate["origin_type"],
            "origin_ref_id": candidate["origin_ref_id"],
            "alignment_ref_id": candidate["alignment_ref_id"],
        },
        "origin_closure": packet["principle_search_record"]["first_principles"][0],
        "intervention_alignment": None,
        "target_intervention_novelty": candidate["target_intervention_novelty"],
        "accepted_assumptions": candidate["fatal_assumptions"],
        "accepted_predictions": candidate["predictions"],
        "provisional_scientific_delta": candidate["provisional_scientific_delta"],
        "evidence_closure": {"evidence_refs": ["results/principle.json"]},
        "activation_conditions": candidate["activation_conditions"],
        "failure_conditions": candidate["failure_conditions"],
        "applicability_boundaries": {
            "activation_conditions": candidate["activation_conditions"],
            "failure_conditions": candidate["failure_conditions"],
            "accepted_boundary_updates": evaluation["scientific_updates"][:1],
        },
        "remaining_uncertainty": ["external validity"],
    }
    validate_selected_principle(
        selected,
        contract=workflow["artifact_contracts"]["selected_principle"],
        expected_principle_id="PR-A",
        expected_principle_version="1",
        packet=packet,
        evaluation=evaluation,
        accepted_boundary_update_ids={"UPDATE-BOUNDARY"},
    )
def test_diagnosis_ready_requires_every_root_cause_rubric_to_pass() -> None:
    verdict = {
        "schema_version": 1, "run_id": "run-1", "verdict_id": "RCA-V-1",
        "reviewer": "independent-reviewer", "analysis_id": "RCA-1",
        "reviewed_analysis_sha256": "a" * 64,
        "problem_contract_sha256": "b" * 64,
        "evidence_capsule_sha256": "c" * 64,
        "necessity_closure_sha256": "d" * 64,
        "necessity_verdict_sha256": "e" * 64,
        "decision": "DIAGNOSIS_READY", "reasons": ["adequate for method design"],
        "issues": [], "observation_fidelity": "PASS", "grouping_adequacy": "PASS",
        "causal_depth": "PASS", "explanatory_coverage": "PASS",
        "evidence_calibration": "PASS", "intervention_relevance": "PASS",
        "falsifiability": "PASS", "residual_failure_alignment": "UNCERTAIN",
    }
    with pytest.raises(ValidationError, match="all root-cause"):
        validate_root_cause_verdict(
            verdict, run_id="run-1", analysis_id="RCA-1", reviewed_analysis_sha256="a" * 64,
            problem_contract_sha256="b" * 64, evidence_capsule_sha256="c" * 64,
            necessity_closure_sha256="d" * 64,
            necessity_verdict_sha256="e" * 64,
        )
    legacy = deepcopy(verdict)
    legacy.pop("residual_failure_alignment")
    legacy["residual_failure_fidelity"] = "PASS"
    with pytest.raises(ValidationError, match="residual_failure_alignment"):
        validate_root_cause_verdict(
            legacy, run_id="run-1", analysis_id="RCA-1",
            reviewed_analysis_sha256="a" * 64,
            problem_contract_sha256="b" * 64, evidence_capsule_sha256="c" * 64,
            necessity_closure_sha256="d" * 64,
            necessity_verdict_sha256="e" * 64,
        )


def approve(controller: ARISController, gate: str, *, selected_id: str | None = None) -> dict:
    request = controller.validate_human_gate_request(gate)
    decision = "select" if gate == "principle_selection" else "approve"
    approvals.issue_ui_approval_receipt(
        controller.root,
        controller.run_id,
        gate,
        request["id"],
        decision,
        selected_id=selected_id,
        artifact_bindings=request["artifact_bindings"],
    )
    return controller.human_approve(gate, decision, selected_id=selected_id)


def request_human_gate_revision(
    controller: ARISController,
    gate: str,
    *,
    selected_id: str | None = None,
    human_feedback: str = "Correct the selected problem's stated scope.",
) -> dict:
    if gate == "problem_acceptance" and selected_id is None:
        selected_id = "P-1"
    feedback = human_feedback if gate in {
        "problem_acceptance", "principle_selection", "principle_test_approval"
    } else None
    request = controller.validate_human_gate_decision(
        gate, "request_revision", selected_id=selected_id, human_feedback=feedback
    )
    approvals.issue_ui_approval_receipt(
        controller.root,
        controller.run_id,
        gate,
        request["id"],
        "request_revision",
        selected_id=selected_id,
        human_feedback=feedback,
        artifact_bindings=request["artifact_bindings"],
    )
    return controller.human_approve(
        gate, "request_revision", selected_id=selected_id, human_feedback=feedback
    )


def reject_problem_candidate(
    controller: ARISController,
    *,
    selected_id: str = "P-1",
    human_feedback: str = "The selected problem premise does not hold.",
) -> dict:
    request = controller.validate_human_gate_decision(
        "problem_acceptance",
        "reject",
        selected_id=selected_id,
        human_feedback=human_feedback,
    )
    receipt_path = approvals.issue_ui_approval_receipt(
        controller.root,
        controller.run_id,
        "problem_acceptance",
        request["id"],
        "reject",
        selected_id=selected_id,
        human_feedback=human_feedback,
        artifact_bindings=request["artifact_bindings"],
    )
    return controller.human_approve(
        "problem_acceptance",
        "reject",
        selected_id=selected_id,
        human_feedback=human_feedback,
    )


def request_source_policy_revision(controller: ARISController) -> dict:
    request = controller.validate_human_gate_request("source_policy_approval")
    approvals.issue_ui_approval_receipt(
        controller.root,
        controller.run_id,
        "source_policy_approval",
        request["id"],
        "request_revision",
        artifact_bindings=request["artifact_bindings"],
    )
    return controller.request_source_policy_revision()


def revise_problem(controller: ARISController, reason: str) -> dict:
    request = controller.request_problem_revision(reason)
    approvals.issue_ui_approval_receipt(
        controller.root,
        controller.run_id,
        "problem_revision",
        request["id"],
        "approve",
        artifact_bindings=request["artifact_bindings"],
    )
    return controller.revise_problem(reason)


def attest(
    controller: ARISController,
    role: str,
    payload: dict,
    *,
    isolated_import: bool = False,
) -> None:
    hook = REPO / ".codex" / "hooks" / "subagent_attestation.py"
    command = [sys.executable]
    if isolated_import:
        command.extend(
            [
                "-I",
                "-S",
                "-c",
                (
                    "import runpy, sys, types; "
                    "sys.modules['yaml'] = types.ModuleType('yaml'); "
                    "runpy.run_path(sys.argv[1], run_name='__main__')"
                ),
                str(hook),
            ]
        )
    else:
        command.append(str(hook))
    result = subprocess.run(
        command,
        input=json.dumps(
            {
                "hook_event_name": "SubagentStop",
                "cwd": str(controller.root),
                "turn_id": "turn-test",
                "agent_id": f"agent-{role}-test",
                "agent_type": role,
                "last_assistant_message": json.dumps(payload),
            }
        ),
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0 and result.stdout == ""


def test_subagent_attestation_is_ascii_safe_for_unicode_project_path(tmp_path: Path) -> None:
    root = tmp_path / "科研项目"
    root.mkdir()
    hook = REPO / ".codex" / "hooks" / "subagent_attestation.py"
    payload = {"read_event_id": "unicode-read", "claim": "阻抗控制—evidence"}
    result = subprocess.run(
        [sys.executable, str(hook)],
        input=json.dumps(
            {
                "hook_event_name": "SubagentStop",
                "cwd": str(root),
                "turn_id": "turn-unicode",
                "agent_id": "agent-paper-reader",
                "agent_type": "paper_reader",
                "last_assistant_message": json.dumps(payload, ensure_ascii=False),
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0 and result.stdout == b""
    receipt = root / ".aris" / "agent-attestations" / "paper_reader" / "unicode-read.json"
    raw = receipt.read_bytes()
    raw.decode("ascii")
    assert json.loads(raw)["project_root"] == str(root.resolve())


def test_natural_subagent_stop_uses_transcript_role_and_is_idempotent(
    tmp_path: Path,
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    transcript = tmp_path / "rollout.jsonl"
    transcript.write_text(
        json.dumps(
            {
                "type": "session_meta",
                "payload": {
                    "id": "thread-paper-reader",
                    "thread_source": "subagent",
                    "agent_role": "paper_reader",
                    "source": {
                        "subagent": {
                            "thread_spawn": {"agent_role": "paper_reader"}
                        }
                    },
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    payload = {"read_event_id": "natural-stop-read", "claim": "evidence"}
    hook = REPO / ".codex" / "hooks" / "subagent_attestation.py"
    event = {
        "hook_event_name": "Stop",
        "cwd": str(root),
        "turn_id": "turn-natural-stop",
        "transcript_path": str(transcript),
        "last_assistant_message": json.dumps(payload),
    }
    first = subprocess.run(
        [sys.executable, str(hook)],
        input=json.dumps(event),
        text=True,
        capture_output=True,
        check=False,
    )
    second = subprocess.run(
        [sys.executable, str(hook)],
        input=json.dumps(event),
        text=True,
        capture_output=True,
        check=False,
    )
    assert first.returncode == 0 and first.stdout == ""
    assert second.returncode == 0 and second.stdout == ""
    receipt = (
        root
        / ".aris"
        / "agent-attestations"
        / "paper_reader"
        / "natural-stop-read.json"
    )
    attestation = json.loads(receipt.read_text(encoding="utf-8"))
    assert attestation["agent_type"] == "paper_reader"
    assert attestation["agent_id"] == "thread-paper-reader"


def _native_generic_compat_event(
    root: Path,
    *,
    binding: dict,
    payload: dict,
    role: str,
    tool_name: str | None = None,
    child_id: str = "native-generic-child",
) -> dict:
    contract = tomllib.loads(
        (root / ".codex" / "agents" / f"{role}.toml").read_text(encoding="utf-8")
    )["developer_instructions"]
    binding = {
        **binding,
        "dispatch_mode": "native_generic_compat",
        "formal_role": role,
        "role_contract_sha256": hashlib.sha256(contract.encode("utf-8")).hexdigest(),
    }
    task = f"ARIS_NATIVE_GENERIC_COMPAT:{json.dumps(binding, sort_keys=True)}\n{contract}"
    records = [
        {
            "type": "session_meta",
            "payload": {
                "id": child_id,
                "thread_source": "subagent",
                "source": {"subagent": {"thread_spawn": {"task_name": "aris-compat"}}},
            },
        },
        {
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": task}],
            },
        },
    ]
    if tool_name:
        records.append(
            {"type": "response_item", "payload": {"type": "function_call", "name": tool_name}}
        )
    transcript = root / f"{role}-native-generic.jsonl"
    transcript.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")
    return {
        "hook_event_name": "Stop",
        "cwd": str(root),
        "turn_id": "native-turn",
        "agent_id": child_id,
        "transcript_path": str(transcript),
        "last_assistant_message": json.dumps(payload),
    }


def _run_attestation_hook(event: dict) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(REPO / ".codex" / "hooks" / "subagent_attestation.py")],
        input=json.dumps(event),
        text=True,
        capture_output=True,
        check=False,
    )


def test_configured_paper_reader_attestation_path_is_unchanged(tmp_path: Path) -> None:
    controller = start_controller(tmp_path)
    reach_reading(controller)
    read = controller.read_full_text("P1", "fake-paper", lambda _: "full paper")
    evidence = card(read)
    attest(controller, "paper_reader", evidence)
    receipt = json.loads(
        (tmp_path / ".aris" / "agent-attestations" / "paper_reader" / f"{read['read_event_id']}.json").read_text(encoding="utf-8")
    )
    assert receipt["agent_type"] == "paper_reader"
    assert "dispatch_mode" not in receipt


def test_native_generic_paper_reader_attestation_binds_task_and_has_no_tools(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller = start_controller(tmp_path)
    install_project_codex_layer(tmp_path)
    reach_reading(controller)
    read = controller.read_full_text("P1", "fake-paper", lambda _: "full paper")
    evidence = card(read)
    event = _native_generic_compat_event(
        tmp_path,
        role="paper_reader",
        payload=evidence,
        binding={"paper_id": "P1", "read_event_id": read["read_event_id"], "content_sha256": read["content_sha256"]},
    )
    result = _run_attestation_hook(event)
    assert result.returncode == 0 and result.stdout == ""
    receipt_path = tmp_path / ".aris" / "agent-attestations" / "paper_reader" / f"{read['read_event_id']}.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["dispatch_mode"] == "native_generic_compat"
    assert receipt["agent_id"] == receipt["child_session_identity"] == "native-generic-child"
    assert receipt["observed_tool_calls"] == []
    controller.submit_evidence_card("P1", evidence)
    assert receipt_path.with_suffix(".consumed.json").is_file()
    assert _run_attestation_hook(event).stdout == ""
    assert not receipt_path.exists()


def test_native_reader_authorization_rejects_wrong_root_before_child_or_formal_evidence_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller = start_controller(tmp_path)
    install_project_codex_layer(tmp_path)
    reach_reading(controller)
    state_before = controller.status()

    monkeypatch.chdir(tmp_path.parent)
    with pytest.raises(ControllerError, match="runtime project root"):
        controller.read_full_text("P1", "fake-paper", lambda _: "must not run")

    assert controller.status() == state_before
    assert not (tmp_path / ".aris" / "agent-attestations").exists()
    assert not (
        tmp_path / ".aris" / "canonical" / controller.run_id / "evidence-P1.json"
    ).exists()


def test_coverage_request_authorization_rejects_wrong_root_without_state_side_effects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller = start_controller(tmp_path)
    reach_synthesis(controller)
    state_before = controller.status()

    monkeypatch.chdir(tmp_path.parent)
    with pytest.raises(ControllerError, match="runtime project root"):
        controller.submit_field_map(field_map())

    assert controller.status() == state_before


def test_all_core_reviewer_request_authorizations_reject_wrong_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller = start_controller(tmp_path)
    state_before = controller.status()
    formal_specs = [
        spec
        for spec in controller.workflow["phases"]
        if spec.get("formal_gate") and isinstance(spec.get("reviewer_role"), str)
    ]
    assert formal_specs

    monkeypatch.chdir(tmp_path.parent)
    for spec in formal_specs:
        with pytest.raises(ControllerError, match="runtime project root"):
            controller._new_core_review_request({}, {"phase": spec["phase"]}, spec)
    assert controller.status() == state_before


def test_validation_reviewer_request_authorization_rejects_wrong_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller = confirmed_validation_controller(tmp_path)
    state_before = controller.status()

    monkeypatch.chdir(tmp_path.parent)
    with pytest.raises(ControllerError, match="runtime project root"):
        controller.validation_handoff()

    assert controller.status() == state_before


def test_non_native_main_phase_is_not_subject_to_runtime_root_invariant(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller = start_controller(tmp_path)
    digest, request_id = reach_coverage(controller)
    review = coverage_review(digest, request_id)
    attest(controller, "coverage_reviewer", review)
    controller.submit_coverage_review(review)
    approve(controller, "scope_human_approval")

    monkeypatch.chdir(tmp_path.parent)
    controller.start_current_phase()
    phase = run_state._find_phase(controller.status(), "problem_generation")
    assert phase["status"] == "running"


@pytest.mark.parametrize("binding_change", [{"read_event_id": "wrong-read"}, {"paper_id": "wrong-paper"}, {"content_sha256": "0" * 64}])
def test_native_generic_paper_reader_rejects_task_or_payload_binding_mismatch(
    tmp_path: Path, binding_change: dict[str, str]
) -> None:
    install_project_codex_layer(tmp_path)
    evidence = {"source_id": "P1", "read_event_id": "read-1", "content_sha256": "a" * 64}
    event = _native_generic_compat_event(
        tmp_path,
        role="paper_reader",
        payload=evidence,
        binding={"paper_id": "P1", "read_event_id": "read-1", "content_sha256": "a" * 64, **binding_change},
    )
    result = _run_attestation_hook(event)
    assert json.loads(result.stdout)["decision"] == "block"
    assert not (tmp_path / ".aris" / "agent-attestations" / "paper_reader" / "read-1.json").exists()


def test_native_generic_paper_reader_rejects_any_tool_call(tmp_path: Path) -> None:
    install_project_codex_layer(tmp_path)
    evidence = {"source_id": "P1", "read_event_id": "read-1", "content_sha256": "a" * 64}
    event = _native_generic_compat_event(
        tmp_path, role="paper_reader", payload=evidence,
        binding={"paper_id": "P1", "read_event_id": "read-1", "content_sha256": "a" * 64}, tool_name="Read",
    )
    assert json.loads(_run_attestation_hook(event).stdout)["decision"] == "block"


def test_native_generic_coverage_reviewer_accepts_only_contract_capabilities(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller = start_controller(tmp_path)
    install_project_codex_layer(tmp_path)
    digest, request_id = reach_coverage(controller)
    review = coverage_review(digest, request_id)
    binding = {"run_id": controller.run_id, "review_request_id": request_id, "reviewed_artifact_hashes": dict(digest.bindings)}
    event = _native_generic_compat_event(tmp_path, role="coverage_reviewer", payload=review, binding=binding, tool_name="WebSearch")
    result = _run_attestation_hook(event)
    assert result.returncode == 0 and result.stdout == ""
    receipt = reviews.review_attestation_path(tmp_path, controller.run_id, "coverage_reviewer", request_id)
    assert json.loads(receipt.read_text(encoding="utf-8"))["dispatch_mode"] == "native_generic_compat"
    controller.submit_coverage_review(review)
    assert receipt.with_suffix(".consumed.json").is_file()

    bad_review = coverage_review(digest, "bad-request")
    bad_event = _native_generic_compat_event(
        tmp_path, role="coverage_reviewer", payload=bad_review,
        binding={"run_id": controller.run_id, "review_request_id": "bad-request", "reviewed_artifact_hashes": dict(digest.bindings)}, tool_name="Bash",
    )
    assert json.loads(_run_attestation_hook(bad_event).stdout)["decision"] == "block"


def test_root_or_unbound_generic_stop_cannot_create_aris_attestation(tmp_path: Path) -> None:
    install_project_codex_layer(tmp_path)
    root_stop = {
        "hook_event_name": "Stop", "cwd": str(tmp_path), "turn_id": "root-turn",
        "agent_id": "root", "last_assistant_message": json.dumps({"read_event_id": "read-1"}),
    }
    generic_transcript = tmp_path / "ordinary-generic.jsonl"
    generic_transcript.write_text(
        json.dumps({"type": "session_meta", "payload": {"id": "ordinary", "thread_source": "subagent", "source": {"subagent": {"thread_spawn": {}}}}}) + "\n",
        encoding="utf-8",
    )
    generic_stop = {**root_stop, "agent_id": "ordinary", "transcript_path": str(generic_transcript)}
    assert _run_attestation_hook(root_stop).stdout == ""
    assert _run_attestation_hook(generic_stop).stdout == ""
    assert not (tmp_path / ".aris" / "agent-attestations").exists()


def test_reviewer_hook_resolves_the_checkout_without_an_editable_install(
    tmp_path: Path,
) -> None:
    controller = ARISController.start(tmp_path, "hook-import", executor="codex")
    payload = {
        "run_id": controller.run_id,
        "review_request_id": "request-1",
        "reviewer": "claude-sonnet-4",
        "verdict_id": "verdict-1",
        "decision": "CERTIFIED",
        "reviewed_artifact_hashes": {"idea-stage/PROBLEM_CANDIDATES.md": "a" * 64},
        "verdict_records": [{"record_type": "phase_verdict"}],
    }

    attest(
        controller,
        "independent_problem_reviewer",
        payload,
        isolated_import=True,
    )

    path = reviews.review_attestation_path(
        controller.root,
        controller.run_id,
        "independent_problem_reviewer",
        payload["review_request_id"],
    )
    recorded = json.loads(path.read_text(encoding="utf-8"))
    assert recorded["agent_type"] == "independent_problem_reviewer"
    assert recorded["artifact_bindings"] == payload["reviewed_artifact_hashes"]


def test_novelty_hook_keeps_final_method_compact_verdict_contract(tmp_path: Path) -> None:
    controller = ARISController.start(tmp_path, "final-novelty-hook", executor="codex")
    payload = {
        "run_id": controller.run_id,
        "review_request_id": "final-method-request",
        "reviewer": "claude-sonnet-4",
        "verdict_id": "final-method-verdict",
        "decision": "NOVEL",
        "reviewed_artifact_hashes": {"refine-logs/FINAL_PROPOSAL.md": "a" * 64},
    }
    attest(controller, "independent_novelty_reviewer", payload)
    receipt = reviews.load_review_attestation(
        controller.root,
        controller.run_id,
        role="independent_novelty_reviewer",
        request_id="final-method-request",
        artifact_bindings=payload["reviewed_artifact_hashes"],
    )
    assert receipt["verdict_payload"] == payload


def attest_current_review(
    controller: ARISController, verdict_id: str, reviewer: str, *, decision: str | None = None
) -> None:
    phase = controller.status()["scientific_core"]
    current = run_state._find_phase(controller.status(), phase["current_phase"])
    request = current["review_request"]
    decision = decision or current.get("gate_verdict") or request["accepted_verdicts"][0]
    if request["required_reviewer_role"] == "independent_root_cause_reviewer":
        payload = json.loads(
            (controller.root / "idea-stage" / "ROOT_CAUSE_VERDICT.json").read_text(encoding="utf-8")
        )
        payload.update(
            {
                "run_id": controller.run_id,
                "review_request_id": request["id"],
                "reviewer": reviewer,
                "verdict_id": verdict_id,
                "decision": decision,
                "reviewed_artifact_hashes": request["artifact_bindings"],
            }
        )
    elif current["phase"] == "final_method_novelty_gate":
        text = (controller.root / "idea-stage" / "FINAL_METHOD_NOVELTY_VERDICT.md").read_text(
            encoding="utf-8"
        )
        payload = json.loads(text.split("```json\n", 1)[1].split("\n```", 1)[0])
    elif current["phase"] == "top_venue_method_strength_gate":
        payload = json.loads(
            (
                controller.root
                / "idea-stage"
                / "TOP_VENUE_METHOD_STRENGTH_VERDICT.json"
            ).read_text(encoding="utf-8")
        )
    elif request["required_reviewer_role"] in {
        "independent_problem_reviewer", "independent_novelty_reviewer",
    }:
        output = controller.root / (
            "idea-stage/PROBLEM_QUALITY_VERDICTS.jsonl"
            if current["phase"] == "problem_quality_gate"
            else "idea-stage/PROBLEM_NOVELTY_VERDICTS.jsonl"
        )
        payload = {
            "run_id": controller.run_id,
            "review_request_id": request["id"],
            "reviewer": reviewer,
            "verdict_id": verdict_id,
            "decision": decision,
            "reviewed_artifact_hashes": request["artifact_bindings"],
            "verdict_records": [
                json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ],
        }
    else:
        payload = {
            "run_id": controller.run_id,
            "review_request_id": request["id"],
            "reviewer": reviewer,
            "verdict_id": verdict_id,
            "decision": decision,
            "reviewed_artifact_hashes": request["artifact_bindings"],
        }
    attest(controller, request["required_reviewer_role"], payload)
    return None


def accept_formal(controller: ARISController, verdict_id: str, reviewer: str) -> dict:
    attest_current_review(controller, verdict_id, reviewer)
    return controller.accept_current_phase(verdict_id, reviewer)


def formal_verdict_artifact(
    controller: ARISController,
    *,
    verdict_id: str,
    candidate_id: str = "P-1",
    reviewer: str = "claude-sonnet-4",
    decision: str | None = None,
) -> str:
    """Build the declared on-disk verdict from the live Controller request."""

    core = controller.status()["scientific_core"]
    phase = run_state._find_phase(controller.status(), core["current_phase"])
    request = phase["review_request"]
    bindings = dict(request["artifact_bindings"])
    decision = decision or request["accepted_verdicts"][0]
    metadata = {
        "schema_version": 1,
        "run_id": controller.run_id,
        "review_request_id": request["id"],
        "reviewer": reviewer,
        "verdict_id": verdict_id,
        "decision": decision,
        "reviewed_artifact_hashes": bindings,
    }
    spec = controller._phase_spec(controller.status(), phase["phase"])
    return_target = (spec.get("return_targets") or {}).get(decision)
    if return_target:
        metadata["return_guidance"] = {
            "missing_evidence": ["The formal review identified an unresolved scientific conflict."],
            "decision_target": return_target,
            "required_check": ["Re-evaluate the invalidated premise against current formal Evidence."],
        }
    if phase["phase"] == "final_method_novelty_gate":
        metadata["run_id"] = controller.run_id
    if phase["phase"] in {"problem_quality_gate", "problem_novelty_gate"}:
        if phase["phase"] == "problem_quality_gate":
            assessment = {
                "quality_assessment": {
                    dimension: {
                        "judgment": "PASS",
                        "rationale": f"{dimension} is assessed against the bound evidence.",
                        "evidence_ids": ["P1"],
                        "issue_ids": [],
                    }
                    for dimension in (
                        "Reality", "Importance", "Unresolvedness", "Precision",
                        "Falsifiability", "Answerability",
                    )
                }
            }
        else:
            coverage_paths = [
                path for path in bindings
                if path.replace("\\", "/")
                in {"idea-stage/LITERATURE_CORPUS.jsonl", "idea-stage/SEARCH_LEDGER.jsonl"}
            ]
            assessment = {
                "novelty_assessment": {
                    "closest_priors": [{
                        "paper_id": "P1",
                        "evidence_id": "P1",
                        "verification_status": "decision_grade",
                        "potentially_decisive": True,
                        "overlap": "nearest known framing",
                        "residual_delta": "The scoped question remains unresolved.",
                    }],
                    "search_coverage": {
                        "summary": "Reviewed the Controller-bound corpus and query ledger.",
                        "artifact_paths": coverage_paths,
                    },
                    "residual_unresolved_delta": "The candidate's scoped question remains open.",
                    "evidence_ids": ["P1"],
                    "issue_ids": [],
                }
            }
            if decision == "NOT_NOVEL":
                assessment["novelty_assessment"]["revision_guidance"] = {
                    "closest_prior_ids": ["P1"],
                    "key_overlap": "The closest framing already asks the same question.",
                    "residual_delta": "No material delta remains at the current scope.",
                    "recommended_reframing": ["Narrow to a condition not covered by the closest prior."],
                }
            elif decision == "UNCERTAIN":
                assessment["novelty_assessment"]["revision_guidance"] = {
                    "missing_evidence": ["Verify the potentially decisive closest prior."],
                    "required_checks": ["Read and compare the closest prior at decision grade."],
                    "search_targets": ["the candidate's precise boundary condition"],
                }
        candidate = {
            **metadata,
            "record_type": "candidate_verdict",
            "candidate_id": candidate_id,
            **assessment,
        }
        summary = {
            **metadata,
            "record_type": "phase_verdict",
            "survivor_ids": [candidate_id],
            **(
                {
                    "return_guidance": {
                        "missing_evidence": ["targeted decision-grade evidence"],
                        "decision_target": "Resolve the candidate's blocking evidence gap.",
                        "required_check": ["run the targeted evidence check"],
                    }
                }
                if decision in {"HOLD", "UNCERTAIN"}
                else {}
            ),
        }
        return "\n".join(json.dumps(row) for row in (candidate, summary)) + "\n"
    return "# Formal review\n\n```json\n" + json.dumps(metadata) + "\n```\n"


def top_venue_verdict_artifact(
    controller: ARISController,
    *,
    verdict_id: str,
    decision: str = "TOP_VENUE_READY",
    reviewer: str = "claude-sonnet-4",
    failed_dimension: str = "problem_value",
    no_go: dict | None = None,
) -> dict:
    state = controller.status()
    request = run_state._find_phase(
        state, "top_venue_method_strength_gate"
    )["review_request"]
    contract = controller.workflow["artifact_contracts"][
        "top_venue_method_strength_verdict"
    ]
    payload = {
        "schema_version": 1,
        "run_id": controller.run_id,
        "review_request_id": request["id"],
        "reviewer": reviewer,
        "verdict_id": verdict_id,
        "decision": decision,
        "reviewed_artifact_hashes": request["artifact_bindings"],
        "dimensions": {
            dimension: {
                "judgment": (
                    "FAIL"
                    if decision != "TOP_VENUE_READY"
                    and dimension == failed_dimension
                    else "PASS"
                ),
                "rationale": f"Independent scientific judgment for {dimension}.",
            }
            for dimension in contract["required_dimensions"]
        },
        "findings": [],
        "return_guidance": None,
    }
    target = controller._phase_spec(
        state, "top_venue_method_strength_gate"
    ).get("return_targets", {}).get(decision)
    if target:
        payload["return_guidance"] = {
            "missing_evidence": ["The failed scientific dimension requires recovery."],
            "required_check": ["Repair the failed dimension at its canonical layer."],
            "decision_target": target,
        }
    if no_go is not None:
        payload["no_go"] = no_go
    return payload


def start_controller(
    root: Path,
    *,
    queries: list[str] | None = None,
    run_id: str = "run-1",
    executor: str = "codex-gpt-5.6-sol",
) -> ARISController:
    write_policy(root)
    controller = ARISController.start(root, run_id, executor=executor)
    approve(controller, "source_policy_approval")
    query_texts = queries or ["test field"]
    controller.submit_query_plan(
        {
            "coverage_gaps": ["anchor"],
            "queries": [
                {"query": query, "purpose": "close explicit gap"}
                for query in query_texts
            ],
        }
    )
    return controller


def necessity_fixture_artifacts(
    *, run_id: str, problem_contract_sha256: str, evidence_capsule_sha256: str
) -> tuple[str, str, dict[str, object]]:
    """Return a current accepted residual-failure Necessity handoff for state fixtures."""

    closure = {
        "schema_version": 1,
        "run_id": run_id,
        "necessity_id": "NEC-1",
        "problem_binding": {
            "problem_id": "P-1",
            "problem_version": 1,
            "problem_contract_sha256": problem_contract_sha256,
            "evidence_capsule_sha256": evidence_capsule_sha256,
        },
        "residual_failure_envelope": [{"residual_failure_id": "RF-1"}],
    }
    closure_text = json.dumps(closure) + "\n"
    closure_sha256 = hashlib.sha256(closure_text.encode("utf-8")).hexdigest()
    verdict = {
        "schema_version": 1,
        "run_id": run_id,
        "necessity_id": "NEC-1",
        "verdict_id": "NEC-V-1",
        "decision": "RESIDUAL_SAME_PROBLEM",
        "reviewed_closure_sha256": closure_sha256,
    }
    verdict_text = json.dumps(verdict) + "\n"
    return closure_text, verdict_text, {
        "necessity_id": "NEC-1",
        "closure_sha256": closure_sha256,
        "verdict_id": "NEC-V-1",
        "verdict_sha256": hashlib.sha256(verdict_text.encode("utf-8")).hexdigest(),
        "residual_failure_ids": ["RF-1"],
    }


def confirmed_validation_controller(root: Path) -> ARISController:
    """Construct a Controller-registered final handoff for validation tests."""

    controller = start_controller(root)
    selected = {
        "schema_version": 1,
        "principle_id": "PR-A",
        "principle_version": "1",
        "principle": "Principle A",
        "intervention": "intervention A",
        "changed_structure": "changed relation A",
        "problem_binding": {
            "problem_id": "P-1", "problem_version": 1,
            "problem_contract_sha256": "pending", "evidence_capsule_sha256": "pending",
        },
        "root_cause_binding": {
            "analysis_id": "RCA-1", "analysis_sha256": "pending",
            "causal_chain_ids": ["CHAIN-1"],
        },
        "causal_chain_ids": ["CHAIN-1"],
        "mechanism_change_ids": ["RMC-1"],
        "capability_ids": ["CAP-1"],
        "obligation_ids": ["OBL-1"],
        "evidence_closure": {"evidence_refs": ["results/principle.json"]},
        "activation_conditions": ["declared condition"],
        "failure_conditions": ["declared boundary"],
        "applicability_boundaries": ["declared scope"],
        "remaining_uncertainty": ["external validity"],
    }
    proposal = "\n\n".join(
        f"## {section}\nPR-A v1; CHAIN-1; RMC-1; CAP-1; OBL-1; {section} content."
        for section in controller.workflow["artifact_contracts"]["final_proposal"]["required_sections"]
    ) + "\n"
    contract_text = "# Contract\n"
    capsule_text = "# Evidence\n"
    necessity_closure, necessity_verdict, necessity_binding = necessity_fixture_artifacts(
        run_id=controller.run_id,
        problem_contract_sha256=hashlib.sha256(contract_text.encode("utf-8")).hexdigest(),
        evidence_capsule_sha256=hashlib.sha256(capsule_text.encode("utf-8")).hexdigest(),
    )
    artifacts = {
        "idea-stage/ACTIVE_FIELD_MAP.md": "# Accepted field map\n",
        "idea-stage/RESEARCH_CONTRACT.md": contract_text,
        "idea-stage/PROBLEM_EVIDENCE_CAPSULE.md": capsule_text,
        "idea-stage/NECESSITY_CLOSURE.json": necessity_closure,
        "idea-stage/NECESSITY_VERDICT.json": necessity_verdict,
        "idea-stage/ROOT_CAUSE_ANALYSIS.json": json.dumps({
            "analysis_id": "RCA-1", "necessity_binding": necessity_binding,
            "primary_causal_chain_ids": ["CHAIN-1"],
        }) + "\n",
        "idea-stage/ROOT_CAUSE_VERDICT.json": json.dumps({
            "decision": "DIAGNOSIS_READY", "verdict_id": "RCA-V-1"
        }) + "\n",
        "idea-stage/PRINCIPLE_EVALUATION.json": json.dumps({"cycle_id": "CYCLE-1"}) + "\n",
        "idea-stage/PRINCIPLE_EVALUATION_VERDICT.json": json.dumps({"decision": "PRINCIPLE_CONVERGED"}) + "\n",
        "idea-stage/SELECTED_PRINCIPLE.yaml": yaml.safe_dump(selected, sort_keys=False),
        "refine-logs/FINAL_PROPOSAL.md": proposal,
        "refine-logs/FINAL_BLIND_REVIEW.md": "# Accepted method review\n",
        "idea-stage/FINAL_METHOD_NOVELTY_VERDICT.md": "# Novelty\n",
        "idea-stage/TOP_VENUE_METHOD_STRENGTH_VERDICT.json": json.dumps(
            {"decision": "TOP_VENUE_READY"}
        ) + "\n",
        "idea-stage/IDEA_REPORT.md": "# Accepted\n",
    }
    for raw_path, content in artifacts.items():
        path = root / raw_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    necessity_path = root / "idea-stage" / "NECESSITY_CLOSURE.json"
    necessity_verdict_path = root / "idea-stage" / "NECESSITY_VERDICT.json"
    necessity_verdict_payload = json.loads(
        necessity_verdict_path.read_text(encoding="utf-8")
    )
    necessity_verdict_payload["reviewed_closure_sha256"] = sha256_file(
        necessity_path
    )
    necessity_verdict_path.write_text(
        json.dumps(necessity_verdict_payload) + "\n", encoding="utf-8"
    )
    necessity_binding.update(
        closure_sha256=sha256_file(necessity_path),
        verdict_sha256=sha256_file(necessity_verdict_path),
    )
    root_payload_path = root / "idea-stage" / "ROOT_CAUSE_ANALYSIS.json"
    root_payload = json.loads(root_payload_path.read_text(encoding="utf-8"))
    root_payload["necessity_binding"] = deepcopy(necessity_binding)
    root_payload_path.write_text(
        json.dumps(root_payload) + "\n", encoding="utf-8"
    )
    phase_statuses = {
        "problem_human_acceptance": "human_accepted",
        "problem_necessity": "accepted",
        "root_cause_analysis": "done",
        "root_cause_gate": "accepted",
        "method_design": "accepted",
        "principle_human_selection": "human_accepted",
        "principle_test_design": "accepted",
        "principle_test_human_approval": "human_accepted",
        "principle_evaluation": "accepted",
        "method_refinement": "accepted",
        "final_method_novelty_gate": "accepted",
        "top_venue_method_strength_gate": "accepted",
        "final_method_human_acceptance": "human_accepted",
    }
    producers = {
        "idea-stage/ACTIVE_FIELD_MAP.md": "landscape",
        "idea-stage/RESEARCH_CONTRACT.md": "problem_human_acceptance",
        "idea-stage/PROBLEM_EVIDENCE_CAPSULE.md": "problem_human_acceptance",
        "idea-stage/NECESSITY_CLOSURE.json": "problem_necessity",
        "idea-stage/NECESSITY_VERDICT.json": "problem_necessity",
        "idea-stage/ROOT_CAUSE_ANALYSIS.json": "root_cause_analysis",
        "idea-stage/ROOT_CAUSE_VERDICT.json": "root_cause_gate",
        "idea-stage/PRINCIPLE_EVALUATION.json": "principle_evaluation",
        "idea-stage/PRINCIPLE_EVALUATION_VERDICT.json": "principle_evaluation",
        "idea-stage/SELECTED_PRINCIPLE.yaml": "principle_evaluation",
        "refine-logs/FINAL_PROPOSAL.md": "method_refinement",
        "refine-logs/FINAL_BLIND_REVIEW.md": "method_refinement",
        "idea-stage/FINAL_METHOD_NOVELTY_VERDICT.md": "final_method_novelty_gate",
        "idea-stage/TOP_VENUE_METHOD_STRENGTH_VERDICT.json": (
            "top_venue_method_strength_gate"
        ),
        "idea-stage/IDEA_REPORT.md": "final_method_human_acceptance",
    }
    with controller._store.mutate() as state:
        core = state["scientific_core"]
        for phase_name, status in phase_statuses.items():
            run_state._find_phase(state, phase_name)["status"] = status
        accepted = {}
        for raw_path, producer in producers.items():
            accepted[raw_path] = controller._artifact_record(
                raw_path,
                producer_phase=producer,
                provenance={"controller": "ARISController", "run_id": controller.run_id},
                upstream_snapshot={},
            )
        problem_binding = {
            "problem_id": "P-1",
            "version": 1,
            "contract_sha256": accepted["idea-stage/RESEARCH_CONTRACT.md"]["sha256"],
            "evidence_capsule_sha256": accepted["idea-stage/PROBLEM_EVIDENCE_CAPSULE.md"]["sha256"],
        }
        selected["problem_binding"] = {
            "problem_id": "P-1", "problem_version": 1,
            "problem_contract_sha256": problem_binding["contract_sha256"],
            "evidence_capsule_sha256": problem_binding["evidence_capsule_sha256"],
        }
        selected["root_cause_binding"]["analysis_sha256"] = accepted[
            "idea-stage/ROOT_CAUSE_ANALYSIS.json"
        ]["sha256"]
        selected_path = root / "idea-stage" / "SELECTED_PRINCIPLE.yaml"
        selected_path.write_text(yaml.safe_dump(selected, sort_keys=False), encoding="utf-8")
        accepted["idea-stage/SELECTED_PRINCIPLE.yaml"] = controller._artifact_record(
            "idea-stage/SELECTED_PRINCIPLE.yaml",
            producer_phase="principle_evaluation",
            provenance={"controller": "ARISController", "run_id": controller.run_id},
            upstream_snapshot={},
        )
        accepted["refine-logs/FINAL_PROPOSAL.md"]["problem_version_binding"] = dict(problem_binding)
        core["accepted_artifacts"] = accepted
        run_state._find_phase(state, "principle_evaluation")["validated_artifacts"] = {
            raw_path: accepted[raw_path]["sha256"]
            for raw_path in (
                "idea-stage/PRINCIPLE_EVALUATION.json",
                "idea-stage/PRINCIPLE_EVALUATION_VERDICT.json",
            )
        }
        run_state._find_phase(state, "problem_necessity")["validated_artifacts"] = {
            raw_path: accepted[raw_path]["sha256"]
            for raw_path in (
                "idea-stage/NECESSITY_CLOSURE.json",
                "idea-stage/NECESSITY_VERDICT.json",
            )
        }
        run_state._find_phase(state, "root_cause_analysis")["validated_artifacts"] = {
            raw_path: accepted[raw_path]["sha256"]
            for raw_path in (
                "idea-stage/RESEARCH_CONTRACT.md",
                "idea-stage/PROBLEM_EVIDENCE_CAPSULE.md",
                "idea-stage/NECESSITY_CLOSURE.json",
                "idea-stage/NECESSITY_VERDICT.json",
                "idea-stage/ROOT_CAUSE_ANALYSIS.json",
            )
        }
        run_state._find_phase(state, "root_cause_gate")["validated_artifacts"] = {
            "idea-stage/ROOT_CAUSE_VERDICT.json": accepted[
                "idea-stage/ROOT_CAUSE_VERDICT.json"
            ]["sha256"]
        }
        core["active_problem_version"] = {
            **problem_binding,
            "status": "accepted",
            "contract_path": "idea-stage/RESEARCH_CONTRACT.md",
            "evidence_capsule_path": "idea-stage/PROBLEM_EVIDENCE_CAPSULE.md",
        }
        core["status"] = "METHOD_CONFIRMED_AWAITING_USER_VALIDATION"
        core["current_phase"] = None
        core["validation_entry"] = {
            "status": "AWAITING_USER_INITIATION",
            "entry_policy": "human_initiated_only",
            "accepted_method_artifacts": {
                raw_path: dict(accepted[raw_path])
                for raw_path in (
                    "refine-logs/FINAL_PROPOSAL.md",
                    "idea-stage/FINAL_METHOD_NOVELTY_VERDICT.md",
                    "idea-stage/IDEA_REPORT.md",
                )
            },
        }
    return controller


def write_batch4_final_packet(controller: ARISController) -> Path:
    """Materialize a current zero-residual Packet for refinement integration tests."""

    packet = batch4_final_packet()
    selected_path = controller.root / "idea-stage" / "SELECTED_PRINCIPLE.yaml"
    selected = yaml.safe_load(selected_path.read_text(encoding="utf-8"))
    selected_changed = "accepted_assumptions" not in selected
    if selected_changed:
        selected["accepted_assumptions"] = [
            {"assumption_id": "ASM-1", "assumption": "assumption A"}
        ]
        selected_path.write_text(
            yaml.safe_dump(selected, sort_keys=False), encoding="utf-8"
        )

    necessity_path = controller.root / "idea-stage" / "NECESSITY_CLOSURE.json"
    necessity_verdict_path = controller.root / "idea-stage" / "NECESSITY_VERDICT.json"
    root_path = controller.root / "idea-stage" / "ROOT_CAUSE_ANALYSIS.json"
    root_verdict_path = controller.root / "idea-stage" / "ROOT_CAUSE_VERDICT.json"
    necessity = json.loads(necessity_path.read_text(encoding="utf-8"))
    necessity_verdict = json.loads(necessity_verdict_path.read_text(encoding="utf-8"))
    root = json.loads(root_path.read_text(encoding="utf-8"))
    root_verdict = json.loads(root_verdict_path.read_text(encoding="utf-8"))

    packet["problem_binding"] = deepcopy(selected["problem_binding"])
    packet["necessity_binding"] = {
        "necessity_id": necessity["necessity_id"],
        "closure_sha256": sha256_file(necessity_path),
        "verdict_id": necessity_verdict["verdict_id"],
        "verdict_sha256": sha256_file(necessity_verdict_path),
        "residual_failure_ids": [
            item["residual_failure_id"]
            for item in necessity["residual_failure_envelope"]
        ],
    }
    packet["root_cause_binding"] = {
        "analysis_id": root["analysis_id"],
        "analysis_sha256": sha256_file(root_path),
        "verdict_id": root_verdict["verdict_id"],
        "verdict_sha256": sha256_file(root_verdict_path),
        "primary_causal_chain_ids": root["primary_causal_chain_ids"],
    }
    packet["selected_principle_binding"] = {
        "principle_id": selected["principle_id"],
        "principle_version": selected["principle_version"],
        "selected_principle_sha256": sha256_file(selected_path),
    }
    packet["minimal_faithful_realization"]["selected_intervention"] = selected[
        "intervention"
    ]
    packet["intervention_alignment"][0]["selected_intervention"] = selected[
        "intervention"
    ]
    for closure in packet["principle_only_closure"]:
        if closure["subject_type"] == "ACTIVATION_CONDITION":
            closure["subject_id"] = selected["activation_conditions"][0]
        elif closure["subject_type"] == "FAILURE_CONDITION":
            closure["subject_id"] = selected["failure_conditions"][0]

    evidence_path = controller.root / "idea-stage" / "batch4-evidence.json"
    evidence_path.write_text('{"source_id":"E1"}\n', encoding="utf-8")
    with controller._store.mutate() as state:
        if selected_changed:
            state["scientific_core"]["accepted_artifacts"][
                "idea-stage/SELECTED_PRINCIPLE.yaml"
            ] = controller._artifact_record(
                "idea-stage/SELECTED_PRINCIPLE.yaml",
                producer_phase="principle_evaluation",
                provenance={"controller": "ARISController", "run_id": controller.run_id},
                upstream_snapshot={},
            )
        state["research_lit"]["accepted_artifacts"]["evidence:E1"] = {
            "path": "idea-stage/batch4-evidence.json",
            "sha256": sha256_file(evidence_path),
            "validator_result": "PASS",
        }
        state["research_lit"]["landscape_evidence_ids"] = [
            *state["research_lit"].get("landscape_evidence_ids", []),
            "E1",
        ]

    packet_path = controller.root / "refine-logs" / "FINAL_METHOD_PACKET.json"
    packet_path.parent.mkdir(parents=True, exist_ok=True)
    packet_path.write_text(
        json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return packet_path


def validation_result(
    controller: ARISController,
    *,
    decision: str,
    handoff_sha256: str | None = None,
    issue_handoff: bool = True,
) -> dict:
    evidence = controller.root / "results" / "validation.json"
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text('{"metric": 1}\n', encoding="utf-8")
    handoff = (
        controller.validation_handoff()
        if issue_handoff
        else controller._build_validation_handoff(controller.status())
    )
    review_request = handoff.get("validation_review_request") or {}
    result = {
        "schema_version": 1,
        "validation_result_id": "validation-result-1",
        "run_id": controller.run_id,
        "workflow_sha256": handoff["workflow_sha256"],
        "handoff_sha256": handoff_sha256 or handoff["handoff_sha256"],
        "review_request_id": review_request.get("id", "unissued-validation-request"),
        "reviewed_artifact_hashes": dict(review_request.get("artifact_bindings") or {}),
        "reviewer": "gpt-5.6-sol",
        "verdict_id": "validation-verdict-1",
        "decision": decision,
        "rationale": "Controlled validation result.",
        "evidence_artifacts": [
            {"path": "results/validation.json", "sha256": sha256_file(evidence)}
        ],
        "evidence_refs": ["results/validation.json"],
        "findings": [{"finding_id": "VAL-F-1", "summary": "Bound validation finding."}],
        "return_guidance": None if decision == "VALIDATED" else {
            "decision_target": "Revisit the declared failing layer.",
            "required_checks": ["Consume the bound validation Evidence."],
        },
    }
    if decision == "VALIDATED":
        result["mechanism_evidence_closure"] = [{
            "causal_chain_id": "CHAIN-1",
            "mechanism_change_ids": ["RMC-1"],
            "obligation_ids": ["OBL-1"],
            "predicted_mechanism_change": "The targeted mechanism changes.",
            "observed_mechanism_change": "The mechanism changed as predicted.",
            "explanation_status": "EXPLANATION_SUPPORTED",
            "mechanism_match": "MATCHES_PREDICTION",
            "discriminating_evidence": {
                "method": "controlled_intervention",
                "artifact_paths": ["results/validation.json"],
            },
            "performance_consequence": "The original failure improves under intervention.",
        }]
        result.update(
            supported_claim_elements=["mechanism and consequence"],
            applicability_boundaries=["declared scope"],
            retained_limitations=["external validity"],
            remaining_uncertainties=["transfer scale"],
            established_scientific_delta="Bound mechanism-to-outcome delta.",
        )
    return result


def attest_validation_verdict(controller: ARISController, verdict: dict) -> None:
    attest(controller, "result_to_claim_reviewer", verdict)


def problem_candidate(problem_id: str = "P-1") -> str:
    return json.dumps(
        {
            "problem_id": problem_id,
            "source_class": "self_discovered",
            "research_question": "Why does the measured capability fail in the stated setting?",
            "observed_phenomenon": "The capability fails under the stated condition.",
            "scope_and_conditions": "The declared benchmark setting and boundary.",
            "evidence_refs": ["P1"],
            "why_it_matters": "The result changes a material scientific decision.",
            "value_if_yes": "It identifies a reproducible boundary.",
            "value_if_no": "It rules out the proposed boundary.",
            "plausible_explanations": [
                {"explanation": "mechanism A", "epistemic_status": "preliminary"},
                {"explanation": "mechanism B", "epistemic_status": "speculative"},
            ],
            "measurement_validity": "The measure operationalizes the capability.",
            "artifact_or_confound_alternatives": ["measurement artifact"],
            "independent_support": ["independent replication"],
            "phenomenon_prevalence_or_effect_scale": "Material in the scoped setting.",
            "decision_owner_and_threshold": "Benchmark owner changes a release decision at the threshold.",
            "falsifier": "A stable result under the claimed failure condition falsifies it.",
            "feasible_discriminating_probe": "A controlled comparison separates the explanations.",
            "closest_prior_answer": "Nearest work leaves this condition unresolved.",
            "uncertainties": ["external validity"],
            "dedup_key": "capability-failure|declared-setting",
            "provenance": {"lens": "failure_boundary", "source": "field_map"},
        }
    ) + "\n"


def write_problem_handoffs(controller: ARISController, problem_id: str = "P-1") -> None:
    """Write the minimum mechanically closed problem-acceptance pair."""

    root = controller.root
    candidate_path = "idea-stage/PROBLEM_CANDIDATES.jsonl"
    quality_path = "idea-stage/PROBLEM_QUALITY_VERDICTS.jsonl"
    novelty_path = "idea-stage/PROBLEM_NOVELTY_VERDICTS.jsonl"
    candidate_hash = sha256_file(root / candidate_path)
    quality_hash = sha256_file(root / quality_path)
    novelty_hash = sha256_file(root / novelty_path)
    quality = run_state._find_phase(controller.status(), "problem_quality_gate")
    novelty = run_state._find_phase(controller.status(), "problem_novelty_gate")
    novelty_rows = [
        json.loads(line)
        for line in (root / novelty_path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    novelty_decision = next(
        row["decision"] for row in novelty_rows
        if row.get("record_type") == "candidate_verdict"
        and row.get("candidate_id") == problem_id
    )
    contract_path = root / "idea-stage" / "RESEARCH_CONTRACT.md"
    contract_path.parent.mkdir(parents=True, exist_ok=True)
    contract_path.write_text(
        "\n".join(
            [
                "# Contract",
                f"- **Problem ID**: {problem_id}",
                f"- **Candidate registry path**: {candidate_path}",
                f"- **Candidate registry SHA-256**: {candidate_hash}",
                f"- **Quality verdict path**: {quality_path}",
                f"- **Quality verdict SHA-256**: {quality_hash}",
                f"- **Quality verdict ID**: {quality['verdict_id']}",
                f"- **Novelty verdict path**: {novelty_path}",
                f"- **Novelty verdict SHA-256**: {novelty_hash}",
                f"- **Novelty verdict ID**: {novelty['verdict_id']}",
                f"- **Problem ID / source class**: {problem_id} / self_discovered",
                "- **Research question**: Why does the capability fail?",
                "- **Observed phenomenon**: The capability fails in the scoped setting.",
                "- **Evidence-backed phenomenon**: P1 reports the scoped observation.",
                "- **Evidence status**: supported",
                "- **Decisive evidence tier**: P1 decision_grade with locator",
                "- **Measurement validity**: The measure operationalizes the capability.",
                "- **Artifact/confound alternatives**: measurement artifact",
                "- **Independent support**: independent replication",
                "- **Prevalence/effect scale**: material in scope",
                "- **Scope and boundary**: declared benchmark setting only",
                "- **Why it matters**: it changes a material decision",
                "- **Value if yes / value if no**: identifies or rules out a boundary",
                "- **Decision owner / threshold**: benchmark owner / declared threshold",
                "- **Plausible explanations**: mechanism A; mechanism B",
                "- **Decisive probe or falsifier**: stable result under condition",
                "- **Feasible discriminating probe**: controlled comparison",
                "- **Closest prior / residual delta**: P1 leaves the condition unresolved",
                "- **Uncertainties**: external validity",
                "- **Problem quality verdict**: CERTIFIED with six dimensions",
                f"- **Problem novelty verdict**: {novelty_decision}",
                "- **Acceptance status**: provisional",
                "- **Verdict ID / acceptance authority**: human receipt / human",
                "- **Evidence snapshot / novelty cutoff date**: registry snapshot / 2026-01-01",
                "- **Source**: candidate, quality, and novelty artifacts",
                "",
            ]
        ),
        encoding="utf-8",
    )
    capsule_path = root / "idea-stage" / "PROBLEM_EVIDENCE_CAPSULE.md"
    capsule_path.write_text(
        "\n".join(
            [
                "# Evidence",
                f"- **Problem ID**: {problem_id}",
                "- **Linked Contract path**: idea-stage/RESEARCH_CONTRACT.md",
                f"- **Linked Contract SHA-256**: {sha256_file(contract_path)}",
                "- **Included evidence IDs**: P1",
                "- **Excluded uncertainty / boundary IDs**: none",
                "- **Snapshot source**: Evidence Registry and accepted verdict artifacts",
                "- **Known gaps and contested evidence**: external validity remains bounded",
                "",
            ]
        ),
        encoding="utf-8",
    )


def controller_at_method_design(root: Path) -> ARISController:
    """Create a Controller-owned accepted prefix and leave the real suffix pending."""

    controller = start_controller(root)
    contract_text = "# Accepted problem P-1\n"
    capsule_text = "# Accepted evidence capsule\n"
    necessity_closure, necessity_verdict, necessity_binding = necessity_fixture_artifacts(
        run_id=controller.run_id,
        problem_contract_sha256=hashlib.sha256(contract_text.encode("utf-8")).hexdigest(),
        evidence_capsule_sha256=hashlib.sha256(capsule_text.encode("utf-8")).hexdigest(),
    )
    necessity_tokens = "; ".join(
        [
            str(necessity_binding["necessity_id"]),
            str(necessity_binding["closure_sha256"]),
            str(necessity_binding["verdict_id"]),
            str(necessity_binding["verdict_sha256"]),
            *[str(item) for item in necessity_binding["residual_failure_ids"]],
        ]
    )
    artifacts = {
        "idea-stage/ACTIVE_FIELD_MAP.md": "# Accepted field map\n",
        "idea-stage/RESEARCH_CONTRACT.md": contract_text,
        "idea-stage/PROBLEM_EVIDENCE_CAPSULE.md": capsule_text,
        "idea-stage/NECESSITY_CLOSURE.json": necessity_closure,
        "idea-stage/NECESSITY_VERDICT.json": necessity_verdict,
        "idea-stage/ROOT_CAUSE_ANALYSIS.json": json.dumps({
            "analysis_id": "RCA-1", "primary_causal_chain_ids": ["CHAIN-1"],
            "necessity_binding": necessity_binding,
        }) + "\n",
        "idea-stage/ROOT_CAUSE_ANALYSIS.md": f"# RCA-1\nCHAIN-1; {necessity_tokens}\n",
        "idea-stage/ROOT_CAUSE_VERDICT.json": json.dumps({"decision": "DIAGNOSIS_READY"}) + "\n",
    }
    for raw_path, content in artifacts.items():
        path = root / raw_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    producers = {
        "idea-stage/ACTIVE_FIELD_MAP.md": "landscape",
        "idea-stage/RESEARCH_CONTRACT.md": "problem_human_acceptance",
        "idea-stage/PROBLEM_EVIDENCE_CAPSULE.md": "problem_human_acceptance",
        "idea-stage/NECESSITY_CLOSURE.json": "problem_necessity",
        "idea-stage/NECESSITY_VERDICT.json": "problem_necessity",
        "idea-stage/ROOT_CAUSE_ANALYSIS.json": "root_cause_analysis",
        "idea-stage/ROOT_CAUSE_ANALYSIS.md": "root_cause_analysis",
        "idea-stage/ROOT_CAUSE_VERDICT.json": "root_cause_gate",
    }
    with controller._store.mutate() as state:
        state["research_lit"]["current_stage"] = "LANDSCAPE_ACCEPTED"
        core = state["scientific_core"]
        core["status"] = "ACTIVE"
        core["current_phase"] = "method_design"
        prefix_statuses = {
            "landscape": "accepted",
            "scope_human_approval": "human_accepted",
            "problem_generation": "done",
            "problem_quality_gate": "accepted",
            "problem_novelty_gate": "accepted",
            "problem_human_acceptance": "human_accepted",
            "problem_necessity": "accepted",
            "root_cause_analysis": "done",
            "root_cause_gate": "accepted",
        }
        for phase_name, status in prefix_statuses.items():
            run_state._find_phase(state, phase_name)["status"] = status
        accepted = {
            raw_path: controller._artifact_record(
                raw_path,
                producer_phase=producer,
                provenance={"controller": "ARISController", "run_id": controller.run_id},
                upstream_snapshot={},
            )
            for raw_path, producer in producers.items()
        }
        contract = accepted["idea-stage/RESEARCH_CONTRACT.md"]
        capsule = accepted["idea-stage/PROBLEM_EVIDENCE_CAPSULE.md"]
        binding = {
            "problem_id": "P-1", "version": 1,
            "contract_sha256": contract["sha256"],
            "evidence_capsule_sha256": capsule["sha256"],
        }
        contract["problem_version"] = dict(binding)
        capsule["problem_version"] = dict(binding)
        run_state._find_phase(state, "root_cause_analysis")["validated_artifacts"] = {
            raw_path: accepted[raw_path]["sha256"]
            for raw_path in (
                "idea-stage/RESEARCH_CONTRACT.md",
                "idea-stage/PROBLEM_EVIDENCE_CAPSULE.md",
                "idea-stage/NECESSITY_CLOSURE.json",
                "idea-stage/NECESSITY_VERDICT.json",
                "idea-stage/ROOT_CAUSE_ANALYSIS.json",
            )
        }
        run_state._find_phase(state, "problem_necessity")["validated_artifacts"] = {
            raw_path: accepted[raw_path]["sha256"]
            for raw_path in (
                "idea-stage/NECESSITY_CLOSURE.json",
                "idea-stage/NECESSITY_VERDICT.json",
            )
        }
        run_state._find_phase(state, "root_cause_gate")["validated_artifacts"] = {
            "idea-stage/ROOT_CAUSE_VERDICT.json": accepted[
                "idea-stage/ROOT_CAUSE_VERDICT.json"
            ]["sha256"]
        }
        core["accepted_artifacts"] = accepted
        core["active_problem_version"] = {
            **binding,
            "status": "accepted",
            "contract_path": "idea-stage/RESEARCH_CONTRACT.md",
            "evidence_capsule_path": "idea-stage/PROBLEM_EVIDENCE_CAPSULE.md",
        }
        packet_template = method_design_packet()
        _, query_plan = principle_search_plan_fixture()
        query_plan["method_design_context"].update({
            "root_cause_analysis_sha256": accepted[
                "idea-stage/ROOT_CAUSE_ANALYSIS.json"
            ]["sha256"],
            "active_field_map_sha256": accepted[
                "idea-stage/ACTIVE_FIELD_MAP.md"
            ]["sha256"],
            "problem_id": binding["problem_id"],
            "problem_version": binding["version"],
            "problem_contract_sha256": binding["contract_sha256"],
            "evidence_capsule_sha256": binding["evidence_capsule_sha256"],
            "required_mechanism_changes": deepcopy(
                packet_template["required_mechanism_changes"]
            ),
            "required_capabilities": deepcopy(packet_template["required_capabilities"]),
            "design_obligations": deepcopy(packet_template["design_obligations"]),
        })
        principle_context = query_plan["method_design_context"]["principle_search_context"]
        principle_context["target_mechanism_signatures"] = deepcopy(
            packet_template["principle_search_record"]["target_mechanism_signatures"]
        )
        principle_context["domain_hypotheses"][0]["domain_hypothesis_id"] = "DH-MODEL-1"
        principle_context["domain_hypotheses"][0][
            "target_mechanism_signature_ref"
        ] = "TMS-1"
        principle_context["terminology_maps"][0]["domain_hypothesis_id"] = "DH-MODEL-1"
        for item in query_plan["queries"]:
            item["domain_hypothesis_ids"] = [
                "DH-MODEL-1" if value == "DH-1" else value
                for value in item["domain_hypothesis_ids"]
            ]
        for index, item in enumerate(query_plan["queries"], 1):
            item["plan_item_id"] = f"method-search-{index}"
        domain_item = next(
            item
            for item in query_plan["queries"]
            if item["search_step"] == "DOMAIN_DISCOVERY"
        )
        domain_item["plan_item_id"] = "domain-discovery-1"
        target_prior_item = next(
            item
            for item in query_plan["queries"]
            if item["search_dimension"] == "SAME_FIELD_MECHANISM"
            and item["search_step"] == "SOURCE_SEARCH"
        )
        plan_path = root / "idea-stage" / "QUERY_PLAN_METHOD_DESIGN_FIXTURE.json"
        plan_path.write_text(json.dumps(query_plan, indent=2), encoding="utf-8")
        plan_sha256 = sha256_file(plan_path)
        plan_record = {
            "path": str(plan_path.relative_to(root)),
            "sha256": plan_sha256,
            "accepted_at": "2026-08-30T00:00:00Z",
            "validator_result": "PASS",
        }
        state["research_lit"]["accepted_artifacts"][
            "incremental-query-plan-method_design"
        ] = dict(plan_record)
        state["research_lit"]["query_plan_history"] = [dict(plan_record)]

        evidence_card = {
            "source_id": "E-BRIDGE",
            "read_event_id": "READ-BRIDGE",
            "content_sha256": "e" * 64,
            "method_design_search_context": {
                "query_plan_sha256": plan_sha256,
                "actual_hit_query_ids": ["Q-BRIDGE"],
            },
        }
        evidence_path = root / "idea-stage" / "EVIDENCE_CARD_E-BRIDGE.json"
        evidence_path.write_text(json.dumps(evidence_card), encoding="utf-8")
        evidence_record = {
            "path": str(evidence_path.relative_to(root)),
            "sha256": sha256_file(evidence_path),
            "validator_result": "PASS",
            "read_event_id": "READ-BRIDGE",
            "accepted_at": "2026-08-30T00:01:00Z",
        }
        state["research_lit"]["accepted_artifacts"]["evidence:E-BRIDGE"] = dict(
            evidence_record
        )
        state["research_lit"]["query_events"]["Q-BRIDGE"] = {
            "query_plan_sha256": plan_sha256,
            "plan_item_id": "domain-discovery-1",
            "status": "complete",
        }
        state["research_lit"]["query_events"]["Q-TARGET-PRIOR"] = {
            "query_plan_sha256": plan_sha256,
            "plan_item_id": target_prior_item["plan_item_id"],
            "status": "complete",
        }
        append_jsonl(
            root / "idea-stage" / "SEARCH_LEDGER.jsonl",
            ledger_event(
                run_id=controller.run_id,
                stage="METADATA_RETRIEVAL",
                action="query",
                query_id="Q-TARGET-PRIOR",
                query=target_prior_item["query"],
                tool="fixture-search",
                result_status="complete",
                event_id="EVENT-TARGET-PRIOR",
                details={"plan_item_id": target_prior_item["plan_item_id"]},
            ),
        )
        state["research_lit"]["read_events"]["READ-BRIDGE"] = {
            "paper_id": "E-BRIDGE",
            "status": "complete",
            "content_sha256": "e" * 64,
        }
        phase_anchor = controller._phase_evidence_anchor(state, "method_design")
        state["research_lit"].setdefault("incremental_evidence_by_phase", {})[
            "method_design"
        ] = {
            "evidence:E-BRIDGE": {
                **evidence_record,
                "evidence_key": "evidence:E-BRIDGE",
                "phase_binding_anchor": phase_anchor,
            }
        }
    return controller


def bound_method_design_packet(controller: ARISController, *, cycle_id: str = "DESIGN-1") -> dict:
    with controller._store.mutate() as live_state:
        binding = live_state["research_lit"]["incremental_evidence_by_phase"][
            "method_design"
        ]["evidence:E-BRIDGE"]
        binding["phase_binding_anchor"] = controller._phase_evidence_anchor(
            live_state, "method_design"
        )
    packet = method_design_packet(cycle_id=cycle_id)
    active = controller.status()["scientific_core"]["active_problem_version"]
    packet["problem_binding"] = {
        "problem_id": active["problem_id"],
        "problem_version": active["version"],
        "problem_contract_sha256": active["contract_sha256"],
        "evidence_capsule_sha256": active["evidence_capsule_sha256"],
    }
    packet["root_cause_binding"]["analysis_sha256"] = sha256_file(
        controller.root / "idea-stage" / "ROOT_CAUSE_ANALYSIS.json"
    )
    state = controller.status()
    plan_sha256 = state["research_lit"]["accepted_artifacts"][
        "incremental-query-plan-method_design"
    ]["sha256"]
    packet["principle_search_record"]["domain_hypotheses"][0][
        "introduced_query_plan_sha256"
    ] = plan_sha256
    packet["principle_search_record"]["discovery_executions"][1][
        "query_plan_sha256"
    ] = plan_sha256
    plan_record = state["research_lit"]["accepted_artifacts"][
        "incremental-query-plan-method_design"
    ]
    plan = json.loads(
        (controller.root / plan_record["path"]).read_text(encoding="utf-8")
    )
    target_prior_item = next(
        item
        for item in plan["queries"]
        if item["search_dimension"] == "SAME_FIELD_MECHANISM"
        and item["search_step"] == "SOURCE_SEARCH"
    )
    for candidate in packet["candidate_principles"]:
        candidate["target_intervention_novelty"]["evidence_search_provenance"] = [{
            "query_plan_sha256": plan_sha256,
            "plan_item_id": target_prior_item["plan_item_id"],
            "query_id": "Q-TARGET-PRIOR",
        }]
    packet["relevant_history_refs"] = sorted(
        run_state._relevant_scientific_history_refs(str(controller.root), state, packet)
    )
    feedback_ref = run_state._latest_return_feedback_ref(state, "method_design")
    packet["return_feedback_refs"] = [feedback_ref] if feedback_ref else []
    return packet


def test_method_design_query_plan_provenance_indexes_only_real_terminal_queries(
    tmp_path: Path,
) -> None:
    controller = controller_at_method_design(tmp_path)
    state = controller.status()
    plan_sha256 = state["research_lit"]["accepted_artifacts"][
        "incremental-query-plan-method_design"
    ]["sha256"]
    provenance = run_state._method_design_query_plan_provenance(
        str(controller.root), state
    )
    current = provenance[plan_sha256]
    assert current["is_current"] is True
    assert current["completed_query_ids_by_plan_item"]["method-search-1"] == [
        "Q-TARGET-PRIOR"
    ]

    with controller._store.mutate() as live_state:
        live_state["research_lit"]["query_events"]["Q-TARGET-PRIOR"][
            "status"
        ] = "started"
    unfinished = run_state._method_design_query_plan_provenance(
        str(controller.root), controller.status()
    )
    assert "method-search-1" not in unfinished[plan_sha256][
        "completed_query_ids_by_plan_item"
    ]


def activate_method_design_admission_context(
    controller: ARISController,
    paper_id: str,
    *,
    prior_decisions: list[dict] | None = None,
) -> dict:
    with controller._store.mutate() as state:
        research = state["research_lit"]
        plan_record = research["accepted_artifacts"]["incremental-query-plan-method_design"]
        anchor = controller._phase_evidence_anchor(state, "method_design")
        context = {
            "phase": "method_design",
            "query_plan_sha256": plan_record["sha256"],
            "phase_binding_anchor": anchor,
        }
        research["incremental_literature_active"] = {
            "phase": "method_design",
            "query_plan_path": plan_record["path"],
            "query_plan_sha256": plan_record["sha256"],
            "phase_binding_anchor": anchor,
            "decision_context": deepcopy(context),
            "paper_ids": [paper_id],
            "paper_decision_ids": {},
            "evidence_artifacts": {},
        }
        research["current_stage"] = "METADATA_RETRIEVAL"
        paper = {
            **metadata(paper_id, venue="Ordinary"),
            "source_id": paper_id,
            "source_origin": "gateway_discovery",
            "found_by_query_ids": ["Q-BRIDGE"],
            "context_decisions": deepcopy(prior_decisions or []),
        }
        research["papers"][paper_id] = paper
        return context


def json_review_payload(
    controller: ARISController,
    *,
    decision: str,
    verdict_id: str,
    selected_principle: tuple[str, str] | None = None,
) -> dict:
    state = controller.status()
    phase = run_state._find_phase(state, state["scientific_core"]["current_phase"])
    request = phase["review_request"]
    main_path = {
        "method_design": "idea-stage/METHOD_DESIGN_PACKET.json",
        "principle_test_design": "idea-stage/PRINCIPLE_TEST_PLAN.json",
        "principle_evaluation": "idea-stage/PRINCIPLE_EVALUATION.json",
    }[phase["phase"]]
    payload = {
        "schema_version": 1,
        "run_id": controller.run_id,
        "review_request_id": request["id"],
        "reviewer": "claude-sonnet-4",
        "verdict_id": verdict_id,
        "decision": decision,
        "reviewed_artifact_hashes": dict(request["artifact_bindings"]),
        "reviewed_artifact": {
            "path": main_path,
            "sha256": request["artifact_bindings"][main_path],
        },
        "findings": [{"finding_id": "F-1", "summary": "mechanical review finding"}],
        "return_guidance": None if decision in {
            "PRINCIPLE_PACKET_READY", "TEST_PLAN_READY", "PRINCIPLE_CONVERGED"
        } else {
            "missing_evidence": ["A declared uncertainty remains unresolved."],
            "decision_target": "Revise the declared scientific artifact.",
            "required_check": ["Consume this formal feedback."],
        },
    }
    if selected_principle is not None:
        payload["selected_principle_id"], payload["selected_principle_version"] = selected_principle
        payload["accepted_boundary_update_ids"] = ["UPDATE-PR-A"]
    return payload


def write_and_complete_method_design(
    controller: ARISController,
    *,
    decision: str = "PRINCIPLE_PACKET_READY",
    cycle_id: str = "DESIGN-1",
    verdict_id: str = "method-review-1",
    packet: dict | None = None,
) -> dict:
    controller.start_current_phase()
    packet = packet or bound_method_design_packet(controller, cycle_id=cycle_id)
    path = controller.root / "idea-stage" / "METHOD_DESIGN_PACKET.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(packet), encoding="utf-8")
    request = controller.refresh_current_review_request()
    assert request["artifact_bindings"]["idea-stage/METHOD_DESIGN_PACKET.json"] == sha256_file(path)
    verdict = json_review_payload(controller, decision=decision, verdict_id=verdict_id)
    (controller.root / "idea-stage" / "METHOD_DESIGN_REVIEW.json").write_text(
        json.dumps(verdict), encoding="utf-8"
    )
    controller.complete_current_phase()
    attest_current_review(controller, verdict_id, "claude-sonnet-4", decision=decision)
    return packet


def select_candidate_for_testing(
    controller: ARISController, *, selected_id: str = "PR-A@1"
) -> dict:
    selected = approve(controller, "principle_selection", selected_id=selected_id)
    assert selected["scientific_core"]["method_test_cycle"] is None
    assert not (controller.root / "idea-stage" / "SELECTED_PRINCIPLE.yaml").exists()
    return selected


def write_and_complete_principle_test_design(
    controller: ARISController,
    *,
    decision: str = "TEST_PLAN_READY",
    cycle_id: str = "CYCLE-1",
    verdict_id: str = "test-plan-review-1",
) -> dict:
    controller.start_current_phase()
    state = controller.status()
    packet = json.loads(
        (controller.root / "idea-stage" / "METHOD_DESIGN_PACKET.json").read_text(encoding="utf-8")
    )
    history_refs = sorted(
        run_state._relevant_scientific_history_refs(str(controller.root), state, packet)
    )
    feedback_ref = run_state._latest_return_feedback_ref(state, "principle_test_design")
    plan = principle_test_plan(
        state["scientific_core"]["selected_for_testing"],
        cycle_id=cycle_id,
        relevant_history_refs=history_refs,
        return_feedback_refs=[feedback_ref] if feedback_ref else [],
    )
    path = controller.root / "idea-stage" / "PRINCIPLE_TEST_PLAN.json"
    path.write_text(json.dumps(plan), encoding="utf-8")
    request = controller.refresh_current_review_request()
    assert request["artifact_bindings"]["idea-stage/PRINCIPLE_TEST_PLAN.json"] == sha256_file(path)
    verdict = json_review_payload(controller, decision=decision, verdict_id=verdict_id)
    (controller.root / "idea-stage" / "PRINCIPLE_TEST_PLAN_REVIEW.json").write_text(
        json.dumps(verdict), encoding="utf-8"
    )
    controller.complete_current_phase()
    attest_current_review(controller, verdict_id, "claude-sonnet-4", decision=decision)
    return plan


def reach_principle_test_human_approval(
    controller: ARISController,
    *,
    cycle_id: str = "CYCLE-1",
    test_plan_verdict_id: str = "test-plan-review-1",
) -> dict:
    write_and_complete_method_design(controller)
    accept_current_scientific_gate_from_validated_prefix_fixture(
        controller, verdict_id="method-review-1"
    )
    select_candidate_for_testing(controller)
    plan = write_and_complete_principle_test_design(
        controller, cycle_id=cycle_id, verdict_id=test_plan_verdict_id
    )
    accept_current_scientific_gate_from_validated_prefix_fixture(
        controller, verdict_id=test_plan_verdict_id
    )
    assert controller.current_stage() == "PRINCIPLE_TEST_HUMAN_APPROVAL"
    return plan


def accept_current_scientific_gate_from_validated_prefix_fixture(
    controller: ARISController,
    *,
    verdict_id: str,
) -> dict:
    """Supply the exact source snapshot needed to isolate downstream unit behavior."""

    state = controller.status()
    phase_name = state["scientific_core"]["current_phase"]
    phase_spec = next(item for item in controller.workflow["phases"] if item["phase"] == phase_name)
    output_paths = run_state._resolve_artifact_refs(
        controller.workflow, phase_spec["produced_artifacts"], phase_name
    )
    with controller._store.mutate() as mutable:
        mutable_phase = run_state._find_phase(mutable, phase_name)
        mutable_phase["validated_artifacts"] = {
            raw_path: sha256_file(controller.root / raw_path) for raw_path in output_paths
        }
    return controller.accept_current_phase(verdict_id, "claude-sonnet-4")


def terminal_result(
    controller: ARISController,
    *,
    outcome: str = "RESULT_AVAILABLE",
) -> dict:
    cycle = controller.status()["scientific_core"]["method_test_cycle"]
    refs: list[dict[str, str]] = []
    if outcome == "RESULT_AVAILABLE":
        result_path = controller.root / "results" / f"{cycle['cycle_id']}.json"
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text('{"observation": 1}\n', encoding="utf-8")
        refs = [{"path": result_path.relative_to(controller.root).as_posix(), "sha256": sha256_file(result_path)}]
    return {
        "schema_version": 1,
        "cycle_id": cycle["cycle_id"],
        "execution_set_id": cycle["execution_set_id"],
        "test_id": cycle["approved_test_ids"][0],
        "outcome": outcome,
        "result_refs": refs,
        "reason": "unavailable" if outcome == "NO_RESULT" else None,
        "execution_metadata": {"runner": "fixture"},
    }


def principle_evaluation_payload(controller: ARISController) -> dict:
    cycle = controller.status()["scientific_core"]["method_test_cycle"]
    context = cycle["evidence_context"]
    evidence_path = "results/" + cycle["cycle_id"] + ".json"
    packet = json.loads(
        (controller.root / "idea-stage" / "METHOD_DESIGN_PACKET.json").read_text(encoding="utf-8")
    )
    state = controller.status()
    payload = {
        "schema_version": 1,
        "cycle_id": cycle["cycle_id"],
        "execution_set_id": cycle["execution_set_id"],
        "evidence_context_ref": dict(context),
        "operationalization_assessments": [{
            "test_id": "TEST-FATAL-A", "status": "FAITHFUL",
            "evidence_refs": [evidence_path], "rationale": "The approved observable was measured.",
        }],
        "test_validity_assessments": [{
            "test_id": "TEST-FATAL-A", "status": "VALID",
            "discriminativeness": "DISCRIMINATING", "evidence_refs": [evidence_path],
            "rationale": "The result separates Pattern A from Pattern B.",
        }],
        "activation_condition_assessments": [{
            "test_id": "TEST-FATAL-A", "prediction_id": "PRED-A", "status": "HELD",
            "evidence_refs": [evidence_path], "rationale": "The declared condition was active.",
        }],
        "prediction_comparisons": [{
            "test_id": "TEST-FATAL-A", "prediction_id": "PRED-A",
            "observable": "signal A", "observed_pattern": "observation A",
            "rival_type": "PRINCIPLE", "rival_id": "PR-B",
            "rival_discrimination": "FAVORS_PATTERN_A", "evidence_refs": [evidence_path],
            "rationale": "The observed Pattern A differs from the Rival Pattern B.",
        }],
        "scientific_updates": [{
            "update_id": "UPDATE-PR-A", "target_type": "APPLICABILITY_BOUNDARY",
            "target_id": "PR-A@1", "before": "declared operating envelope",
            "proposed_after": "declared operating condition with observed activation",
            "evidence_refs": [evidence_path], "consequence": "UPDATE_BOUNDARY",
            "rationale": "Current Evidence supports a bounded applicability update.",
        }, {
            "update_id": "UPDATE-UNACCEPTED", "target_type": "APPLICABILITY_BOUNDARY",
            "target_id": "PR-A@1", "before": "observed activation condition",
            "proposed_after": "narrower proposed activation condition",
            "evidence_refs": [evidence_path], "consequence": "UPDATE_BOUNDARY",
            "rationale": "This unaccepted boundary interpretation remains a proposal.",
        }],
        "remaining_uncertainties": ["external validity"],
        "relevant_history_refs": sorted(
            run_state._relevant_scientific_history_refs(str(controller.root), state, packet)
        ),
        "return_feedback_refs": [],
    }
    feedback_ref = run_state._latest_return_feedback_ref(state, "principle_evaluation")
    payload["return_feedback_refs"] = [feedback_ref] if feedback_ref else []
    return payload


def write_and_complete_principle_evaluation(
    controller: ARISController,
    *,
    decision: str,
    verdict_id: str,
) -> tuple[dict, dict]:
    controller.start_current_phase()
    evaluation = principle_evaluation_payload(controller)
    evaluation_path = controller.root / "idea-stage" / "PRINCIPLE_EVALUATION.json"
    evaluation_path.write_text(json.dumps(evaluation), encoding="utf-8")
    request = controller.refresh_current_review_request()
    assert request["artifact_bindings"]["idea-stage/PRINCIPLE_EVALUATION.json"] == sha256_file(
        evaluation_path
    )
    verdict = json_review_payload(
        controller,
        decision=decision,
        verdict_id=verdict_id,
        selected_principle=("PR-A", "1") if decision == "PRINCIPLE_CONVERGED" else None,
    )
    (controller.root / "idea-stage" / "PRINCIPLE_EVALUATION_VERDICT.json").write_text(
        json.dumps(verdict), encoding="utf-8"
    )
    controller.complete_current_phase()
    attest_current_review(controller, verdict_id, "claude-sonnet-4", decision=decision)
    return evaluation, verdict


def root_cause_payload(
    *,
    problem_id: str = "P-1",
    evidence_source_type: str = "literature",
    evidence_ref: str = "LIT-1",
) -> dict:
    return {
        "schema_version": 1,
        "run_id": "run-1",
        "analysis_id": "RCA-1",
        "problem_id": problem_id,
        "problem_contract_sha256": "a" * 64,
        "evidence_capsule_sha256": "b" * 64,
        "necessity_binding": {
            "necessity_id": "NEC-1",
            "closure_sha256": "d" * 64,
            "verdict_id": "NEC-V-1",
            "verdict_sha256": "e" * 64,
            "residual_failure_ids": ["RF-1"],
        },
        "failure_observations": [{
            "observation_id": "O-1", "phenomenon": "failure", "conditions": "shift",
            "abnormal_variables": ["error"], "evidence_source_type": evidence_source_type,
            "evidence_refs": [evidence_ref], "epistemic_status": "supported",
        }],
        "phenomenon_clusters": [{
            "cluster_id": "C-1", "observation_ids": ["O-1"],
            "grouping_rationale": "shared observed failure",
        }],
        "causal_depth_traces": [{
            "trace_id": "T-1", "cluster_id": "C-1", "why_steps": [{
                "step_id": "W-1", "effect": "failure", "candidate_cause": "miscalibration",
                "evidence_refs": [evidence_ref], "epistemic_status": "supported",
                "discriminating_observation": "calibration remains stable",
            }],
        }],
        "causal_chains": [{
            "chain_id": "CHAIN-1", "cluster_ids": ["C-1"],
            "conditions_or_input_change": "shift", "mechanism_failure": "miscalibration",
            "intermediate_state_abnormality": "underestimated uncertainty",
            "final_failure_phenomenon": "failure", "evidence_refs": [evidence_ref],
            "alternative_explanations": [{
                "explanation_id": "ALT-1", "mechanism": "noise",
                "epistemic_status": "preliminary", "discriminating_evidence": "clean data",
            }],
            "intervention_target": "calibration", "falsifier": "correction has no effect",
            "epistemic_status": "supported",
        }],
        "primary_causal_chain_ids": ["CHAIN-1"],
        "unresolved_questions": [],
        "analysis_provenance": {
            "author_role": "main_research_agent", "created_at": "2026-08-10T00:00:00Z",
            "source_artifact_ids": [evidence_ref],
        },
    }


@pytest.mark.parametrize(
    ("source_type", "reference"),
    [
        ("literature", "LIT-1"),
        ("existing_experiment", "EXP-1"),
        ("dataset", "DATA-1"),
        ("real_world", "REAL-1"),
        ("diagnostic_pilot", "PILOT-1"),
    ],
)
def test_root_cause_analysis_closes_current_problem_and_formal_evidence_references(
    source_type: str, reference: str,
) -> None:
    sources = {
        "LIT-1": "literature",
        "EXP-1": "existing_experiment",
        "DATA-1": "dataset",
        "REAL-1": "real_world",
        "PILOT-1": "diagnostic_pilot",
    }
    analysis = root_cause_payload(
        evidence_source_type=source_type, evidence_ref=reference
    )
    validate_root_cause_analysis(
        analysis,
        run_id="run-1",
        problem_contract_sha256="a" * 64,
        evidence_capsule_sha256="b" * 64,
        active_problem_id="P-1",
        formal_evidence_sources=sources,
        necessity_binding=analysis["necessity_binding"],
    )

    stale = deepcopy(analysis)
    stale["necessity_binding"]["closure_sha256"] = "f" * 64
    with pytest.raises(ValidationError, match="necessity_binding is stale"):
        validate_root_cause_analysis(
            stale,
            run_id="run-1",
            problem_contract_sha256="a" * 64,
            evidence_capsule_sha256="b" * 64,
            active_problem_id="P-1",
            formal_evidence_sources=sources,
            necessity_binding=analysis["necessity_binding"],
        )

    analysis["problem_id"] = "P-other"
    with pytest.raises(ValidationError, match="active accepted problem"):
        validate_root_cause_analysis(
            analysis,
            run_id="run-1",
            problem_contract_sha256="a" * 64,
            evidence_capsule_sha256="b" * 64,
            active_problem_id="P-1",
            formal_evidence_sources=sources,
        )
    analysis["problem_id"] = "P-1"
    analysis["failure_observations"][0]["evidence_refs"] = ["foreign-evidence"]
    with pytest.raises(ValidationError, match="outside the active problem"):
        validate_root_cause_analysis(
            analysis,
            run_id="run-1",
            problem_contract_sha256="a" * 64,
            evidence_capsule_sha256="b" * 64,
            active_problem_id="P-1",
            formal_evidence_sources=sources,
        )
    analysis["failure_observations"][0]["evidence_refs"] = ["EXP-1"]
    analysis["failure_observations"][0]["evidence_source_type"] = "existing_experiment"
    analysis["analysis_provenance"]["source_artifact_ids"] = ["EXP-1"]
    analysis["analysis_provenance"]["new_diagnostic_pilot_artifacts"] = [{
        "artifact_id": "EXP-1",
        "path": "idea-stage/experiment.json",
        "sha256": "c" * 64,
        "evidence_source_type": "existing_experiment",
    }]
    with pytest.raises(ValidationError, match="must be diagnostic_pilot"):
        validate_root_cause_analysis(
            analysis,
            run_id="run-1",
            problem_contract_sha256="a" * 64,
            evidence_capsule_sha256="b" * 64,
            active_problem_id="P-1",
            formal_evidence_sources=sources,
        )


def metadata(paper_id: str = "P1", *, venue: str = "Test Elite Venue") -> dict:
    return {
        "paper_id": paper_id,
        "title": "Test paper",
        "authors": ["A. Author"],
        "year": 2025,
        "venue": venue,
        "doi_or_stable_url": "https://doi.org/10.1/test",
        "citation_count": 0,
        "identity_status": "verified",
        "abstract": "This paper studies a test mechanism in the declared field.",
        "abstract_source": "test_fixture",
    }


def latest_paper_decision(controller: ARISController, paper_id: str) -> dict:
    paper = controller.status()["research_lit"]["papers"][paper_id]
    decisions = paper.get("context_decisions") or []
    assert decisions
    return decisions[-1]


def card(read: dict, paper_id: str = "P1") -> dict:
    return {
        "source_id": paper_id,
        "read_event_id": read["read_event_id"],
        "content_sha256": read["content_sha256"],
        "claim": "Mechanism M addresses B under A.",
        "claim_locator": "Section 3, p.4",
        "access_level": "full_text",
        "decision_grade": "decision_grade",
        "epistemic_status": "supported",
        "problem_and_setting": "problem",
        "method_or_mechanism": "mechanism",
        "content_summary": "summary",
        "synthesis_role": "turning point",
        "development_link": "extends P0",
        "evidence": "experiment",
        "evidence_kind": "controlled experiment",
        "boundary_conditions": "bounded setting",
        "assumptions": ["A"],
        "reported_or_inferred_failures": {"reported": ["F"], "inferred": []},
        "conflicts_with": [],
        "verification_status": "verified",
    }


def development_trace(
    transition_id: str = "T1",
    *,
    family: str | None = "M",
    evidence_ids: list[str] | None = None,
) -> dict:
    trace = {
        "transition_id": transition_id,
        "previous_problem_or_bottleneck": "B remained unresolved under condition A",
        "progress_and_conditions": "Mechanism M improved E under condition A",
        "residual_or_new_bottleneck": "F remained outside condition A",
        "research_question_shift": "The field shifted from improving E to resolving F",
        "subsequent_direction": "Methods targeting F under relaxed assumptions",
        "transition_problem_status": "partially_addressed",
        "evidence_ids": evidence_ids or ["P1"],
    }
    if family is not None:
        trace["family"] = family
    return trace


def field_map(status: str = "SUFFICIENT") -> dict:
    return {
        "field_core_purposes": ["purpose"],
        "typical_tasks_and_scenarios": ["task"],
        "core_bottlenecks": [{"id": "B", "text": "bottleneck"}],
        "method_families": [{"id": "M", "mechanism": "mechanism"}],
        "family_development_traces": [development_trace()],
        "problem_method_matrix": [{"problem": "B", "method": "M", "mechanism": "mechanism"}],
        "assumption_effectiveness_failure_matrix": [
            {
                "family": "M",
                "assumptions": ["A"],
                "effective": ["E"],
                "failure": ["F"],
                "source_ids": ["P1"],
            }
        ],
        "consensus": ["supported consensus"],
        "unresolved_contradictions": ["contradiction"],
        "coverage_record": {
            "coverage_status": status,
            "research_effort_budget": {"queries": 1, "fulltext": 1},
            "stopping_reason": "follow-up cycle stable",
            "coverage_gaps": (
                []
                if status == "SUFFICIENT"
                else ["The evidence boundary for the reported failure regime is unresolved."]
            ),
        },
        "unresolved_problem_leads": ["lead"],
    }


def reach_reading(controller: ARISController) -> None:
    controller.execute_query(
        "test field",
        "fake-search",
        lambda _: [metadata()],
        plan_item_id="QP-1",
        query_options={
            "year_from": 2000,
            "year_to": 2026,
            "exact_title": False,
            "page": 1,
        },
    )
    assert controller.decide_admission(
        "P1",
        screening_in_scope=True,
        screening_basis="TITLE_ABSTRACT",
        screening_reason="directly addresses the declared mechanism",
        reading_priority="RECENT_ELITE_FRONTIER",
    ) == "ADMIT_FOR_READING"
    controller.select_reading_subset(
        ["P1"],
        rationale="the screened corpus requires this minimal initial cognition source",
        initial=True,
    )
    controller.finish_retrieval()


def reach_synthesis(controller: ARISController) -> None:
    old_cwd = Path.cwd()
    os.chdir(controller.root)
    try:
        reach_reading(controller)
        read = controller.read_full_text("P1", "fake-paper", lambda _: "full paper")
        evidence = card(read)
        controller.submit_evidence_card("P1", evidence)
        controller.finish_reading()
        provisional = field_map()
        provisional.pop("coverage_record")
        controller.submit_field_map(provisional)
        controller.select_formal_primary_subset(
            ["P1"],
            rationale="the Initial Map identifies this screened paper as a formal Primary anchor",
        )
        controller.finish_reading()
    finally:
        os.chdir(old_cwd)


class CoverageDigest(str):
    def __new__(
        cls,
        value: str,
        bindings: dict[str, str],
        development_trace_count: int = 1,
    ):
        instance = str.__new__(cls, value)
        instance.bindings = dict(bindings)
        instance.development_trace_count = development_trace_count
        return instance


def reach_coverage(controller: ARISController) -> tuple[str, str]:
    old_cwd = Path.cwd()
    os.chdir(controller.root)
    try:
        reach_synthesis(controller)
        controller.submit_field_map(field_map())
        research = controller.status()["research_lit"]
        request = research["coverage_review_request"]
        return (
            CoverageDigest(
                research["accepted_artifacts"]["active_field_map"]["sha256"],
                request["artifact_bindings"],
                request["development_trace_count"],
            ),
            request["id"],
        )
    finally:
        os.chdir(old_cwd)


def coverage_review(
    digest: str,
    request_id: str,
    decision: str = "CANDIDATE_SUFFICIENT",
    *,
    run_id: str = "run-1",
    bindings: dict[str, str] | None = None,
    development_trace_count: int | None = None,
) -> dict:
    trace_count = (
        development_trace_count
        if development_trace_count is not None
        else getattr(digest, "development_trace_count", 1)
    )
    transition_basis = (
        "DECLARED_TRACES_REVIEWED"
        if trace_count > 0
        else "NO_MATERIAL_TRANSITION_SUPPORTED"
    )
    return {
        "decision": decision,
        "reasons": ["stable after follow-up"],
        "gaps": [],
        "reviewer_run_id": "independent-review-1",
        "review_request_id": request_id,
        "reviewed_artifact_sha256": digest,
        "run_id": run_id,
        "reviewer": "claude-sonnet-4",
        "verdict_id": "coverage-verdict-1",
        "evolution_assessment": {
            "foundation_to_frontier": {
                "status": "PASS",
                "rationale": "Foundational work and the current frontier are evidenced.",
            },
            "key_nodes_and_branches": {
                "status": "PASS",
                "rationale": "The material nodes and parallel branches are represented.",
            },
            "transition_causality": {
                "status": "PASS",
                "rationale": (
                    "Declared traces explain the evidence-supported transitions."
                    if trace_count > 0
                    else "The evidence supports continuous progress without a material transition."
                ),
                "basis": transition_basis,
            },
            "explanatory_coherence": {
                "status": "PASS",
                "rationale": "The map explains the field's present form and frontier position.",
            },
            "material_evolution_gaps": [],
        },
        "reviewed_artifact_hashes": bindings
        or getattr(digest, "bindings", None)
        or {"idea-stage\\ACTIVE_FIELD_MAP.md": digest},
    }


def complete_landscape_from_metadata(controller: ARISController) -> dict:
    assert controller.decide_admission(
        "P1",
        screening_in_scope=True,
        screening_basis="TITLE_ABSTRACT",
        screening_reason="directly addresses the declared mechanism",
        reading_priority="RECENT_ELITE_FRONTIER",
    ) == "ADMIT_FOR_READING"
    controller.select_reading_subset(
        ["P1"],
        rationale="the screened corpus requires this minimal initial cognition source",
        initial=True,
    )
    controller.finish_retrieval()
    read = controller.read_full_text("P1", "fake-paper", lambda _: "full paper")
    evidence = card(read)
    attest(controller, "paper_reader", evidence)
    controller.submit_evidence_card("P1", evidence)
    controller.finish_reading()
    provisional = field_map()
    provisional.pop("coverage_record")
    controller.submit_field_map(provisional)
    controller.select_formal_primary_subset(
        ["P1"],
        rationale="the Initial Map confirms this Primary as the formal anchor",
    )
    controller.finish_reading()
    controller.submit_field_map(field_map())
    research = controller.status()["research_lit"]
    request = research["coverage_review_request"]
    review = coverage_review(
        CoverageDigest(
            research["accepted_artifacts"]["active_field_map"]["sha256"],
            request["artifact_bindings"],
        ),
        request["id"],
    )
    attest(controller, "coverage_reviewer", review)
    return controller.submit_coverage_review(review)


def _reach_problem_quality_gate(
    controller: ARISController,
    *,
    reviewer: str = "claude-sonnet-4",
    decision: str | None = None,
    verdict_id: str = "quality-recovery-verdict",
) -> None:
    digest, request_id = reach_coverage(controller)
    review = coverage_review(digest, request_id)
    attest(controller, "coverage_reviewer", review)
    controller.submit_coverage_review(review)
    approve(controller, "scope_human_approval")

    def complete(files: dict[str, object]) -> None:
        controller.start_current_phase()
        for relative, content in files.items():
            path = controller.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content() if callable(content) else str(content), encoding="utf-8")
        controller.complete_current_phase()

    complete(
        {
            "idea-stage/PROBLEM_CANDIDATES.md": "# Problems\nP-1",
            "idea-stage/PROBLEM_CANDIDATES.jsonl": problem_candidate(),
        }
    )
    complete(
        {
            "idea-stage/PROBLEM_QUALITY_VERDICTS.jsonl": lambda: formal_verdict_artifact(
                controller,
                verdict_id=verdict_id,
                reviewer=reviewer,
                decision=decision,
            )
        }
    )


def reach_problem_quality_gate(
    controller: ARISController,
    *,
    reviewer: str = "claude-sonnet-4",
    decision: str | None = None,
    verdict_id: str = "quality-recovery-verdict",
) -> None:
    """Run formal reviewer fixtures from the Controller-managed project root."""

    old_cwd = Path.cwd()
    os.chdir(controller.root)
    try:
        _reach_problem_quality_gate(
            controller,
            reviewer=reviewer,
            decision=decision,
            verdict_id=verdict_id,
        )
    finally:
        os.chdir(old_cwd)


def _reach_problem_human_acceptance(controller: ARISController) -> None:
    reach_problem_quality_gate(controller)
    accept_formal(controller, "quality-recovery-verdict", "claude-sonnet-4")
    controller.start_current_phase()
    novelty_verdict = controller.root / "idea-stage" / "PROBLEM_NOVELTY_VERDICTS.jsonl"
    novelty_verdict.write_text(
        formal_verdict_artifact(controller, verdict_id="novelty-recovery-verdict"),
        encoding="utf-8",
    )
    controller.complete_current_phase()
    accept_formal(controller, "novelty-recovery-verdict", "claude-sonnet-4")
    write_problem_handoffs(controller)
    assert controller.current_stage() == "PROBLEM_HUMAN_ACCEPTANCE"


def reach_problem_human_acceptance(controller: ARISController) -> None:
    """Reach the formal problem checkpoint from its managed project root."""

    old_cwd = Path.cwd()
    os.chdir(controller.root)
    try:
        _reach_problem_human_acceptance(controller)
    finally:
        os.chdir(old_cwd)


def complete_problem_necessity(
    controller: ARISController,
    *,
    decision: str = "RESIDUAL_SAME_PROBLEM",
) -> tuple[str, str]:
    """Complete the Controller-owned Necessity Producer -> Reviewer handoff."""

    active = controller.status()["scientific_core"]["active_problem_version"]
    with_residual = decision != "FULLY_COVERED"
    disposition = {
        "FULLY_COVERED": "NO_RESIDUAL_FAILURE",
        "RESIDUAL_SAME_PROBLEM": "SAME_ACCEPTED_PROBLEM",
        "RESIDUAL_REDEFINES_PROBLEM": "REDEFINES_PROBLEM",
        "UNRESOLVED": "UNRESOLVED",
    }[decision]
    residual = [{
        "residual_failure_id": "RF-1",
        "source_failure_ids": ["F-1"],
        "condition": "the accepted operating shift",
        "observable_failure": "the accepted error remains above threshold",
        "consequence": "the accepted decision remains unreliable",
        "uncovered_by_repair_assessment_ids": ["SR-1"],
        "evidence_refs": ["P1"],
    }] if with_residual else []
    closure = {
        "schema_version": 1,
        "run_id": controller.run_id,
        "necessity_id": "NEC-1",
        "problem_binding": {
            "problem_id": active["problem_id"],
            "problem_version": active["version"],
            "problem_contract_sha256": active["contract_sha256"],
            "evidence_capsule_sha256": active["evidence_capsule_sha256"],
        },
        "active_failures": [{
            "failure_id": "F-1",
            "condition": "the accepted operating shift",
            "observable_failure": "the accepted error exceeds threshold",
            "consequence": "the accepted decision is unreliable",
            "evidence_refs": ["P1"],
        }],
        "operating_envelope": {"conditions": ["the accepted operating shift"]},
        "simple_repair_assessments": [{
            "assessment_id": "SR-1",
            "repair": "conventional parameter tuning",
            "applicable_failure_ids": ["F-1"],
            "preserves_core_causal_or_computational_relation": True,
            "evidence_refs": ["P1"],
            "coverage_boundary": (
                "the entire accepted Failure" if not with_residual else "the nominal subset only"
            ),
            "coverage_conclusion": "FULL_COVERAGE" if not with_residual else "PARTIAL_COVERAGE",
            "residual_failure_ids": ["RF-1"] if with_residual else [],
        }],
        "residual_failure_envelope": residual,
        "problem_identity_disposition": disposition,
        "analysis_provenance": {
            "author_role": "main_research_agent",
            "created_at": "2026-08-30T00:00:00Z",
            "analysis_modes": ["EXISTING_FORMAL_EVIDENCE", "FORMAL_ANALYSIS"],
            "source_artifact_ids": ["P1"],
        },
    }
    controller.start_current_phase()
    closure_path = controller.root / "idea-stage" / "NECESSITY_CLOSURE.json"
    closure_path.write_text(json.dumps(closure), encoding="utf-8")
    request = controller.refresh_current_review_request()
    assert request["allowed_review_verdicts"] == [
        "RESIDUAL_SAME_PROBLEM",
        "FULLY_COVERED",
        "RESIDUAL_REDEFINES_PROBLEM",
        "UNRESOLVED",
    ]
    reviewer = "claude-sonnet-4"
    verdict_id = f"necessity-{decision.lower()}"
    verdict = {
        "schema_version": 1,
        "run_id": controller.run_id,
        "review_request_id": request["id"],
        "reviewer": reviewer,
        "verdict_id": verdict_id,
        "necessity_id": "NEC-1",
        "reviewed_closure_sha256": sha256_file(closure_path),
        "problem_contract_sha256": active["contract_sha256"],
        "evidence_capsule_sha256": active["evidence_capsule_sha256"],
        "decision": decision,
        "reasons": ["the reviewed Evidence supports this fixed disposition"],
        "issues": ([{
            "issue_id": "NEC-EVIDENCE-1",
            "severity": "BLOCKING",
            "message": "current formal Evidence cannot resolve coverage",
        }] if decision == "UNRESOLVED" else []),
        "failure_reality": "PASS",
        "operating_envelope_fidelity": "PASS",
        "simple_repair_coverage": "PASS",
        "residual_failure_fidelity": "PASS",
        "problem_identity_fidelity": "PASS",
        "evidence_sufficiency": "UNCERTAIN" if decision == "UNRESOLVED" else "PASS",
        "reviewed_artifact_hashes": request["artifact_bindings"],
    }
    attest(controller, "independent_problem_reviewer", verdict)
    controller.complete_current_phase()
    return verdict_id, reviewer


@pytest.mark.parametrize(
    ("decision", "expected_phase", "accepted"),
    [
        ("RESIDUAL_SAME_PROBLEM", "root_cause_analysis", True),
        ("FULLY_COVERED", "problem_generation", False),
        ("RESIDUAL_REDEFINES_PROBLEM", "problem_generation", False),
        ("UNRESOLVED", "problem_necessity", False),
    ],
)
def test_problem_necessity_producer_reviewer_controller_fixed_transitions(
    tmp_path: Path,
    decision: str,
    expected_phase: str,
    accepted: bool,
) -> None:
    controller = start_controller(tmp_path)
    reach_problem_human_acceptance(controller)
    approve(controller, "problem_acceptance", selected_id="P-1")
    verdict_id, reviewer = complete_problem_necessity(controller, decision=decision)
    if accepted:
        controller.accept_current_phase(verdict_id, reviewer)
    else:
        controller.return_current_phase(verdict_id, reviewer)
    core = controller.status()["scientific_core"]
    assert core["current_phase"] == expected_phase
    if decision == "FULLY_COVERED":
        assert core["status"] == "ACTIVE"
        assert core["return_history"][-1]["no_new_method_needed"] is True


def test_problem_acceptance_registers_one_independent_contract_and_capsule(
    tmp_path: Path,
) -> None:
    controller = start_controller(tmp_path)
    reach_problem_human_acceptance(controller)

    approve(controller, "problem_acceptance", selected_id="P-1")

    core = controller.status()["scientific_core"]
    active = core["active_problem_version"]
    contract_path = "idea-stage/RESEARCH_CONTRACT.md"
    capsule_path = "idea-stage/PROBLEM_EVIDENCE_CAPSULE.md"
    assert active["contract_path"] == contract_path
    assert active["evidence_capsule_path"] == capsule_path
    assert active["contract_sha256"] != active["evidence_capsule_sha256"]
    assert core["accepted_artifacts"][contract_path]["sha256"] == active["contract_sha256"]
    assert core["accepted_artifacts"][capsule_path]["sha256"] == active["evidence_capsule_sha256"]
    decision = run_state._find_phase(
        controller.status(), "problem_human_acceptance"
    )["human_decision"]
    assert decision["artifact_bindings"][contract_path] == active["contract_sha256"]
    assert decision["artifact_bindings"][capsule_path] == active["evidence_capsule_sha256"]

    root_cause = next(
        item for item in controller.workflow["phases"]
        if item["phase"] == "root_cause_analysis"
    )
    method = next(
        item for item in controller.workflow["phases"]
        if item["phase"] == "method_design"
    )
    assert root_cause["required_inputs"] == [
        contract_path, capsule_path,
        "@artifact:necessity_closure", "@artifact:necessity_verdict",
    ]
    assert method["required_inputs"] == [
        "idea-stage/ACTIVE_FIELD_MAP.md", contract_path, capsule_path,
        "@artifact:necessity_closure", "@artifact:necessity_verdict",
        "@artifact:root_cause_analysis", "@artifact:root_cause_verdict",
    ]


def test_root_cause_registers_nonliterature_evidence_and_binds_it_to_review(
    tmp_path: Path,
) -> None:
    controller = start_controller(tmp_path)
    reach_problem_human_acceptance(controller)
    approve(controller, "problem_acceptance", selected_id="P-1")
    verdict_id, reviewer = complete_problem_necessity(controller)
    controller.accept_current_phase(verdict_id, reviewer)
    necessity_binding = run_state._accepted_necessity_binding(
        str(controller.root), controller.status()
    )

    pilot = tmp_path / "idea-stage" / "diagnostic-pilot.json"
    pilot.write_text('{"observation": "shift failure"}\n', encoding="utf-8")
    analysis = root_cause_payload(
        evidence_source_type="diagnostic_pilot", evidence_ref="PILOT-1"
    )
    analysis["problem_contract_sha256"] = sha256_file(
        tmp_path / "idea-stage" / "RESEARCH_CONTRACT.md"
    )
    analysis["evidence_capsule_sha256"] = sha256_file(
        tmp_path / "idea-stage" / "PROBLEM_EVIDENCE_CAPSULE.md"
    )
    analysis["necessity_binding"] = necessity_binding
    analysis["analysis_provenance"]["source_artifact_ids"] = ["PILOT-1"]
    analysis["analysis_provenance"]["new_diagnostic_pilot_artifacts"] = [{
        "artifact_id": "PILOT-1",
        "path": "idea-stage/diagnostic-pilot.json",
        "sha256": sha256_file(pilot),
        "evidence_source_type": "diagnostic_pilot",
    }]

    controller.start_current_phase()
    (tmp_path / "idea-stage" / "ROOT_CAUSE_ANALYSIS.json").write_text(
        json.dumps(analysis), encoding="utf-8"
    )
    (tmp_path / "idea-stage" / "ROOT_CAUSE_ANALYSIS.md").write_text(
        "# Root cause\n"
        f"RCA-1; P-1; CHAIN-1; {analysis['problem_contract_sha256']}; "
        f"{analysis['evidence_capsule_sha256']}; "
        + "; ".join(
            [
                str(necessity_binding["necessity_id"]),
                str(necessity_binding["closure_sha256"]),
                str(necessity_binding["verdict_id"]),
                str(necessity_binding["verdict_sha256"]),
                *[str(item) for item in necessity_binding["residual_failure_ids"]],
            ]
        ),
        encoding="utf-8",
    )
    controller.complete_current_phase()

    source_record = controller.status()["scientific_core"]["accepted_artifacts"][
        "idea-stage/diagnostic-pilot.json"
    ]
    assert source_record["artifact_id"] == "PILOT-1"
    assert source_record["evidence_source_type"] == "diagnostic_pilot"
    assert source_record["problem_version_binding"]["problem_id"] == "P-1"

    controller.start_current_phase()
    request = run_state._find_phase(controller.status(), "root_cause_gate")["review_request"]
    assert request["artifact_bindings"]["idea-stage/diagnostic-pilot.json"] == source_record["sha256"]
    pilot.write_text('{"observation": "tampered"}\n', encoding="utf-8")
    with pytest.raises(ControllerError, match="diagnostic pilot changed"):
        controller.complete_current_phase()


def test_root_cause_reuses_only_capsule_bound_existing_nonliterature_evidence(
    tmp_path: Path,
) -> None:
    controller = start_controller(tmp_path)
    reach_problem_human_acceptance(controller)
    experiment = tmp_path / "idea-stage" / "accepted-experiment.json"
    experiment.write_text('{"result": "observed failure"}\n', encoding="utf-8")
    capsule = tmp_path / "idea-stage" / "PROBLEM_EVIDENCE_CAPSULE.md"
    capsule.write_text(
        capsule.read_text(encoding="utf-8").replace(
            "**Included evidence IDs**: P1",
            "**Included evidence IDs**: P1, EXP-1\n\n"
            "## Registered Non-Literature Artifacts\n\n```json\n"
            + json.dumps(
                [{
                    "artifact_id": "EXP-1",
                    "path": "idea-stage/accepted-experiment.json",
                    "sha256": sha256_file(experiment),
                    "evidence_source_type": "existing_experiment",
                }]
            )
            + "\n```",
        ),
        encoding="utf-8",
    )
    approve(controller, "problem_acceptance", selected_id="P-1")
    registered = controller.status()["scientific_core"]["accepted_artifacts"]
    assert registered["idea-stage/accepted-experiment.json"]["artifact_id"] == "EXP-1"
    verdict_id, reviewer = complete_problem_necessity(controller)
    controller.accept_current_phase(verdict_id, reviewer)
    necessity_binding = run_state._accepted_necessity_binding(
        str(controller.root), controller.status()
    )

    analysis = root_cause_payload(
        evidence_source_type="existing_experiment", evidence_ref="EXP-1"
    )
    analysis["problem_contract_sha256"] = sha256_file(
        tmp_path / "idea-stage" / "RESEARCH_CONTRACT.md"
    )
    analysis["evidence_capsule_sha256"] = sha256_file(capsule)
    analysis["necessity_binding"] = necessity_binding
    controller.start_current_phase()
    (tmp_path / "idea-stage" / "ROOT_CAUSE_ANALYSIS.json").write_text(
        json.dumps(analysis), encoding="utf-8"
    )
    (tmp_path / "idea-stage" / "ROOT_CAUSE_ANALYSIS.md").write_text(
        "# Root cause\n"
        f"RCA-1; P-1; CHAIN-1; {analysis['problem_contract_sha256']}; "
        f"{analysis['evidence_capsule_sha256']}; "
        + "; ".join(
            [
                str(necessity_binding["necessity_id"]),
                str(necessity_binding["closure_sha256"]),
                str(necessity_binding["verdict_id"]),
                str(necessity_binding["verdict_sha256"]),
                *[str(item) for item in necessity_binding["residual_failure_ids"]],
            ]
        ),
        encoding="utf-8",
    )
    controller.complete_current_phase()


def test_problem_chain_rejects_unknown_selection_and_mismatched_capsule(
    tmp_path: Path,
) -> None:
    controller = start_controller(tmp_path)
    reach_problem_human_acceptance(controller)

    request = controller.validate_human_gate_request("problem_acceptance")
    approvals.issue_ui_approval_receipt(
        controller.root,
        controller.run_id,
        "problem_acceptance",
        request["id"],
        "approve",
        selected_id="P-404",
        artifact_bindings=request["artifact_bindings"],
    )
    with pytest.raises(ControllerError, match="quality-certified and covered"):
        controller.human_approve("problem_acceptance", "approve", selected_id="P-404")


def test_problem_contract_must_bind_the_selected_candidate_novelty_decision(
    tmp_path: Path,
) -> None:
    controller = start_controller(tmp_path)
    reach_problem_human_acceptance(controller)
    contract = controller.root / "idea-stage" / "RESEARCH_CONTRACT.md"
    capsule = controller.root / "idea-stage" / "PROBLEM_EVIDENCE_CAPSULE.md"
    original_hash = sha256_file(contract)
    contract.write_text(
        contract.read_text(encoding="utf-8").replace(
            "- **Problem novelty verdict**: NOVEL",
            "- **Problem novelty verdict**: NOT_NOVEL",
        ),
        encoding="utf-8",
    )
    capsule.write_text(
        capsule.read_text(encoding="utf-8").replace(
            original_hash, sha256_file(contract)
        ),
        encoding="utf-8",
    )

    with pytest.raises(ControllerError, match="Problem novelty verdict"):
        approve(controller, "problem_acceptance", selected_id="P-1")

    controller = start_controller(tmp_path / "capsule")
    reach_problem_human_acceptance(controller)
    capsule = controller.root / "idea-stage" / "PROBLEM_EVIDENCE_CAPSULE.md"
    capsule.write_text(
        capsule.read_text(encoding="utf-8").replace("**Problem ID**: P-1", "**Problem ID**: P-404"),
        encoding="utf-8",
    )
    request = controller.validate_human_gate_request("problem_acceptance")
    approvals.issue_ui_approval_receipt(
        controller.root,
        controller.run_id,
        "problem_acceptance",
        request["id"],
        "approve",
        selected_id="P-1",
        artifact_bindings=request["artifact_bindings"],
    )
    with pytest.raises(ControllerError, match="Problem ID does not match"):
        controller.human_approve("problem_acceptance", "approve", selected_id="P-1")


def test_problem_acceptance_rejects_incomplete_contract_or_unresolved_capsule_evidence(
    tmp_path: Path,
) -> None:
    controller = start_controller(tmp_path)
    reach_problem_human_acceptance(controller)
    contract = controller.root / "idea-stage" / "RESEARCH_CONTRACT.md"
    contract.write_text(
        contract.read_text(encoding="utf-8").replace(
            "- **Feasible discriminating probe**: controlled comparison\n", ""
        ),
        encoding="utf-8",
    )
    request = controller.validate_human_gate_request("problem_acceptance")
    approvals.issue_ui_approval_receipt(
        controller.root, controller.run_id, "problem_acceptance", request["id"], "approve",
        selected_id="P-1", artifact_bindings=request["artifact_bindings"],
    )
    with pytest.raises(ControllerError, match="Feasible discriminating probe"):
        controller.human_approve("problem_acceptance", "approve", selected_id="P-1")

    controller = start_controller(tmp_path / "unknown-evidence")
    reach_problem_human_acceptance(controller)
    capsule = controller.root / "idea-stage" / "PROBLEM_EVIDENCE_CAPSULE.md"
    capsule.write_text(
        capsule.read_text(encoding="utf-8").replace("**Included evidence IDs**: P1", "**Included evidence IDs**: P404"),
        encoding="utf-8",
    )
    request = controller.validate_human_gate_request("problem_acceptance")
    approvals.issue_ui_approval_receipt(
        controller.root, controller.run_id, "problem_acceptance", request["id"], "approve",
        selected_id="P-1", artifact_bindings=request["artifact_bindings"],
    )
    with pytest.raises(ControllerError, match="do not resolve"):
        controller.human_approve("problem_acceptance", "approve", selected_id="P-1")


def test_problem_quality_verdict_must_cover_the_registered_candidate_set(tmp_path: Path) -> None:
    controller = start_controller(tmp_path)
    reach_problem_quality_gate(controller)
    verdict = controller.root / "idea-stage" / "PROBLEM_QUALITY_VERDICTS.jsonl"
    verdict.write_text(
        formal_verdict_artifact(controller, verdict_id="wrong-candidate", candidate_id="P-404"),
        encoding="utf-8",
    )
    with pytest.raises(ControllerError, match="expected candidate set"):
        controller.accept_current_phase("wrong-candidate", "claude-sonnet-4")


def test_coverage_canonical_payload_cannot_rewrite_attested_gaps(tmp_path: Path) -> None:
    controller = start_controller(tmp_path)
    digest, request_id = reach_coverage(controller)
    review = coverage_review(digest, request_id)
    attest(controller, "coverage_reviewer", review)
    tampered = dict(review)
    tampered["gaps"] = ["a different downstream search direction"]
    with pytest.raises(ControllerError, match="differs from the attested reviewer payload"):
        controller.submit_coverage_review(tampered)


def test_problem_gate_canonical_records_must_match_attested_reviewer_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller = start_controller(tmp_path)
    reach_problem_quality_gate(controller)
    attest_current_review(controller, "quality-recovery-verdict", "claude-sonnet-4")
    quality = controller.root / "idea-stage/PROBLEM_QUALITY_VERDICTS.jsonl"
    rows = [json.loads(line) for line in quality.read_text(encoding="utf-8").splitlines()]
    rows[0]["quality_assessment"]["Reality"]["rationale"] = "rewritten after review"
    quality.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    with pytest.raises(ControllerError, match="differs from the attested reviewer payload"):
        controller.accept_current_phase("quality-recovery-verdict", "claude-sonnet-4")

    novelty_root = tmp_path / "novelty"
    novelty_root.mkdir()
    monkeypatch.chdir(novelty_root)
    controller = start_controller(novelty_root)
    reach_problem_quality_gate(controller)
    accept_formal(controller, "quality-recovery-verdict", "claude-sonnet-4")
    controller.start_current_phase()
    novelty = controller.root / "idea-stage/PROBLEM_NOVELTY_VERDICTS.jsonl"
    novelty.write_text(formal_verdict_artifact(controller, verdict_id="novelty-payload"), encoding="utf-8")
    controller.complete_current_phase()
    attest_current_review(controller, "novelty-payload", "claude-sonnet-4")
    rows = [json.loads(line) for line in novelty.read_text(encoding="utf-8").splitlines()]
    rows[1]["survivor_ids"] = []
    novelty.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    with pytest.raises(ControllerError, match="survivor_ids"):
        controller.accept_current_phase("novelty-payload", "claude-sonnet-4")


def test_problem_generation_rejects_incomplete_p2_candidate_contract(tmp_path: Path) -> None:
    controller = start_controller(tmp_path)
    digest, request_id = reach_coverage(controller)
    review = coverage_review(digest, request_id)
    attest(controller, "coverage_reviewer", review)
    controller.submit_coverage_review(review)
    approve(controller, "scope_human_approval")
    controller.start_current_phase()
    candidate = controller.root / "idea-stage" / "PROBLEM_CANDIDATES.jsonl"
    candidate.parent.mkdir(parents=True, exist_ok=True)
    candidate.write_text(json.dumps({"problem_id": "P-1", "source_class": "self_discovered"}) + "\n", encoding="utf-8")
    (controller.root / "idea-stage" / "PROBLEM_CANDIDATES.md").write_text("# Problems\nP-1", encoding="utf-8")
    with pytest.raises(ControllerError, match="missing required fields"):
        controller.complete_current_phase()


def test_problem_quality_requires_judgments_but_allows_structural_dimensions_without_evidence(
    tmp_path: Path,
) -> None:
    controller = start_controller(tmp_path)
    reach_problem_quality_gate(controller)
    rows = [
        json.loads(line)
        for line in formal_verdict_artifact(controller, verdict_id="structural-quality").splitlines()
    ]
    for dimension in ("Precision", "Falsifiability", "Answerability"):
        rows[0]["quality_assessment"][dimension]["evidence_ids"] = []
    phase = run_state._find_phase(controller.status(), "problem_quality_gate")
    request = phase["review_request"]
    kwargs = {
        "label": "quality verdict",
        "request_id": request["id"],
        "artifact_bindings": request["artifact_bindings"],
        "phase_decisions": {"CERTIFIED", "HOLD", "REJECT", "BLOCKED"},
        "candidate_decisions": {"CERTIFIED", "HOLD", "REJECT", "BLOCKED"},
        "expected_candidate_ids": {"P-1"},
        "review_kind": "quality",
        "formal_evidence_paths": run_state._current_formal_evidence_paths(
            str(controller.root), controller.status()
        ),
        "formal_evidence_source_ids": run_state._current_decision_grade_evidence_card_source_ids(
            str(controller.root), controller.status()
        ),
    }
    validate_candidate_verdict_artifact(
        "\n".join(json.dumps(row) for row in rows),
        **kwargs,
    )

    del rows[0]["quality_assessment"]["Reality"]["judgment"]
    with pytest.raises(ValidationError, match="missing required fields"):
        validate_candidate_verdict_artifact(
            "\n".join(json.dumps(row) for row in rows),
            **kwargs,
        )


def test_problem_novelty_cannot_mark_unverified_decisive_prior_novel(tmp_path: Path) -> None:
    controller = start_controller(tmp_path)
    reach_problem_quality_gate(controller)
    accept_formal(controller, "quality-recovery-verdict", "claude-sonnet-4")
    controller.start_current_phase()
    verdict = controller.root / "idea-stage" / "PROBLEM_NOVELTY_VERDICTS.jsonl"
    rows = [json.loads(line) for line in formal_verdict_artifact(controller, verdict_id="unverified-prior").splitlines()]
    rows[0]["novelty_assessment"]["closest_priors"][0].update(
        {"evidence_id": None, "verification_status": "unverified_or_unavailable"}
    )
    verdict.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    with pytest.raises(ControllerError, match="cannot return NOVEL"):
        controller.complete_current_phase()


def test_problem_novelty_rejects_decision_grade_evidence_for_different_prior(tmp_path: Path) -> None:
    controller = start_controller(tmp_path)
    reach_problem_quality_gate(controller)
    accept_formal(controller, "quality-recovery-verdict", "claude-sonnet-4")
    controller.start_current_phase()
    verdict = controller.root / "idea-stage" / "PROBLEM_NOVELTY_VERDICTS.jsonl"
    rows = [
        json.loads(line)
        for line in formal_verdict_artifact(controller, verdict_id="mismatched-prior").splitlines()
    ]
    rows[0]["novelty_assessment"]["closest_priors"][0]["paper_id"] = "DIFFERENT-PAPER"
    verdict.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    with pytest.raises(ControllerError, match="paper_id must match"):
        controller.complete_current_phase()


def test_problem_novelty_cannot_block_consumable_candidate_audits(tmp_path: Path) -> None:
    controller = start_controller(tmp_path)
    reach_problem_quality_gate(controller)
    accept_formal(controller, "quality-recovery-verdict", "claude-sonnet-4")
    controller.start_current_phase()
    rows = [
        json.loads(line)
        for line in formal_verdict_artifact(controller, verdict_id="mixed-novelty").splitlines()
    ]
    blocked = json.loads(json.dumps(rows[0]))
    blocked["candidate_id"] = "P-2"
    blocked["decision"] = "BLOCKED"
    rows[1]["decision"] = "BLOCKED"
    rows[1]["survivor_ids"] = ["P-2"]
    phase = run_state._find_phase(controller.status(), "problem_novelty_gate")
    request = phase["review_request"]
    kwargs = {
        "label": "novelty verdict",
        "request_id": request["id"],
        "artifact_bindings": request["artifact_bindings"],
        "phase_decisions": {"NOVEL", "UNCERTAIN", "NOT_NOVEL", "BLOCKED"},
        "candidate_decisions": {"NOVEL", "UNCERTAIN", "NOT_NOVEL", "BLOCKED"},
        "expected_candidate_ids": {"P-1", "P-2"},
        "review_kind": "novelty",
        "formal_evidence_paths": run_state._current_formal_evidence_paths(
            str(controller.root), controller.status()
        ),
        "formal_evidence_source_ids": run_state._current_decision_grade_evidence_card_source_ids(
            str(controller.root), controller.status()
        ),
    }
    with pytest.raises(ValidationError, match="only when every candidate novelty audit is BLOCKED"):
        validate_candidate_verdict_artifact(
            "\n".join(json.dumps(row) for row in [rows[0], blocked, rows[1]]),
            **kwargs,
        )


def test_problem_novelty_uncertain_candidate_requires_uncertain_phase(tmp_path: Path) -> None:
    controller = start_controller(tmp_path)
    reach_problem_quality_gate(controller)
    accept_formal(controller, "quality-recovery-verdict", "claude-sonnet-4")
    controller.start_current_phase()
    rows = [
        json.loads(line)
        for line in formal_verdict_artifact(controller, verdict_id="mixed-uncertain").splitlines()
    ]
    uncertain = json.loads(json.dumps(rows[0]))
    uncertain["candidate_id"] = "P-2"
    uncertain["decision"] = "UNCERTAIN"
    phase = run_state._find_phase(controller.status(), "problem_novelty_gate")
    request = phase["review_request"]
    kwargs = {
        "label": "novelty verdict",
        "request_id": request["id"],
        "artifact_bindings": request["artifact_bindings"],
        "phase_decisions": {"NOVEL", "UNCERTAIN", "NOT_NOVEL", "BLOCKED"},
        "candidate_decisions": {"NOVEL", "UNCERTAIN", "NOT_NOVEL", "BLOCKED"},
        "expected_candidate_ids": {"P-1", "P-2"},
        "review_kind": "novelty",
        "formal_evidence_paths": run_state._current_formal_evidence_paths(
            str(controller.root), controller.status()
        ),
        "formal_evidence_source_ids": run_state._current_decision_grade_evidence_card_source_ids(
            str(controller.root), controller.status()
        ),
    }
    with pytest.raises(ValidationError, match="must be UNCERTAIN"):
        validate_candidate_verdict_artifact(
            "\n".join(json.dumps(row) for row in [rows[0], uncertain, rows[1]]),
            **kwargs,
        )


def test_scientific_core_incremental_literature_reuses_gateway_and_binds_evidence(
    tmp_path: Path,
) -> None:
    controller = start_controller(tmp_path)
    reach_problem_quality_gate(controller)
    with pytest.raises(ControllerError, match="allowed only before an eligible phase"):
        controller.submit_query_plan(
            {"coverage_gaps": ["bypass"], "queries": [{"query": "bypass", "purpose": "bypass"}]}
        )
    accept_formal(controller, "quality-recovery-verdict", "claude-sonnet-4")

    assert controller.current_stage() == "PROBLEM_NOVELTY_GATE"
    assert controller.allowed_actions() == ["submit_query_plan", "start_phase"]
    controller.submit_query_plan(
        {
            "coverage_gaps": ["closest problem framing"],
            "queries": [{"query": "novel problem framing", "purpose": "test closest prior claim"}],
        }
    )
    assert controller.status()["research_lit"]["current_stage"] == "METADATA_RETRIEVAL"
    assert controller.allowed_actions() == [
        "execute_query", "register_user_source", "decide_admission",
        "select_reading_subset", "finish_retrieval",
    ]
    with pytest.raises(ControllerError, match="complete the active incremental literature"):
        controller.start_current_phase()

    controller.execute_query("novel problem framing", "gateway", lambda _: [metadata("P2")])
    assert controller.decide_admission(
        "P2",
        screening_in_scope=True,
        screening_basis="TITLE_ABSTRACT",
        screening_reason="the closest-prior claim requires an inspected source",
        reading_priority="RECENT_ELITE_FRONTIER",
        fulltext_selected=True,
    ) == "ADMIT_FOR_READING"
    controller.finish_retrieval()
    read = controller.read_full_text("P2", "gateway-fulltext", lambda _: "incremental paper")
    evidence = card(read, paper_id="P2")
    attest(controller, "paper_reader", evidence)
    controller.submit_evidence_card("P2", evidence)
    controller.finish_reading()

    state = controller.status()
    research = state["research_lit"]
    incremental = research["incremental_evidence_by_phase"]["problem_novelty_gate"]
    evidence_path = incremental["evidence:P2"]["path"]
    evidence_hash = incremental["evidence:P2"]["sha256"]
    assert research["current_stage"] == "LANDSCAPE_ACCEPTED"
    assert research["coverage_review_request"] is None
    assert '"action": "query"' in (tmp_path / "idea-stage" / "SEARCH_LEDGER.jsonl").read_text(encoding="utf-8")
    assert '"action": "fulltext"' in (tmp_path / "idea-stage" / "SEARCH_LEDGER.jsonl").read_text(encoding="utf-8")
    assert '"source_id": "P2"' in (tmp_path / "idea-stage" / "EVIDENCE_REGISTRY.jsonl").read_text(encoding="utf-8")

    controller.start_current_phase()
    request = run_state._find_phase(controller.status(), "problem_novelty_gate")["review_request"]
    assert request["artifact_bindings"][evidence_path] == evidence_hash
    assert "idea-stage/ACTIVE_FIELD_MAP.md" in request["artifact_bindings"]
    assert "idea-stage/PROBLEM_CANDIDATES.jsonl" in request["artifact_bindings"]
    assert "idea-stage/PROBLEM_QUALITY_VERDICTS.jsonl" in request["artifact_bindings"]
    assert any(path.replace("\\", "/").endswith("LITERATURE_CORPUS.jsonl") for path in request["artifact_bindings"])
    assert any(path.replace("\\", "/").endswith("SEARCH_LEDGER.jsonl") for path in request["artifact_bindings"])
    verdict = tmp_path / "idea-stage" / "PROBLEM_NOVELTY_VERDICTS.jsonl"
    verdict.write_text(
        formal_verdict_artifact(controller, verdict_id="incremental-novelty-verdict"),
        encoding="utf-8",
    )
    controller.complete_current_phase()
    output = controller.status()["scientific_core"]["accepted_artifacts"][
        "idea-stage/PROBLEM_NOVELTY_VERDICTS.jsonl"
    ]
    assert output["upstream_snapshot"][evidence_path] == evidence_hash


def test_root_cause_running_may_reenter_literature_gateway_and_keeps_prior_evidence(
    tmp_path: Path,
) -> None:
    controller = start_controller(tmp_path)
    with controller._store.mutate() as mutable:
        mutable["research_lit"]["current_stage"] = "LANDSCAPE_ACCEPTED"
    state = controller.status()
    root_phase = {"phase": "root_cause_analysis", "status": "running"}
    other_running_phase = {"phase": "method_design", "status": "running"}
    assert controller._incremental_literature_phase_allowed(state, root_phase)
    assert controller._incremental_literature_phase_allowed(state, other_running_phase)

    first = tmp_path / "idea-stage" / "EVIDENCE_CARD_RCA-FIRST.json"
    second = tmp_path / "idea-stage" / "EVIDENCE_CARD_RCA-SECOND.json"
    first.write_text('{"card":"first"}\n', encoding="utf-8")
    second.write_text('{"card":"second"}\n', encoding="utf-8")
    with controller._store.mutate() as mutable:
        mutable["research_lit"]["incremental_evidence_by_phase"]["root_cause_analysis"] = {
            "evidence:RCA-FIRST": {
                "path": "idea-stage/EVIDENCE_CARD_RCA-FIRST.json",
                "sha256": sha256_file(first),
            }
        }
        mutable["research_lit"]["current_stage"] = "PAPER_READING"
        mutable["research_lit"]["incremental_literature_active"] = {
            "phase": "root_cause_analysis",
            "paper_ids": [],
            "evidence_artifacts": {
                "evidence:RCA-SECOND": {
                "path": "idea-stage/EVIDENCE_CARD_RCA-SECOND.json",
                "sha256": sha256_file(second),
                }
            },
        }

    controller.finish_reading()

    bindings = controller._incremental_evidence_bindings(
        controller.status(), "root_cause_analysis"
    )
    assert bindings == {
        "idea-stage/EVIDENCE_CARD_RCA-FIRST.json": sha256_file(first),
        "idea-stage/EVIDENCE_CARD_RCA-SECOND.json": sha256_file(second),
    }


def principle_search_plan_fixture() -> tuple[dict, dict]:
    context = {
        "root_cause_analysis_id": "RCA-1",
        "root_cause_analysis_sha256": "b" * 64,
        "active_field_map_sha256": "a" * 64,
        "primary_causal_chain_ids": {"CHAIN-1"},
        "problem_version": {
            "problem_id": "P-1", "version": 1,
            "contract_sha256": "c" * 64, "evidence_capsule_sha256": "d" * 64,
        },
        "required_mechanism_changes": [{
            "mechanism_change_id": "RMC-1",
            "causal_chain_ids": ["CHAIN-1"],
            "failed_relation_state_or_information_structure": "miscalibrated state",
            "required_mechanism_change": "restore calibrated state",
            "change_direction": "miscalibrated to calibrated",
            "causal_position": "before failure propagation",
            "activation_condition": "the unstable regime",
            "root_cause_resolution_rationale": "directly resolves CHAIN-1",
            "capability_ids": ["CAP-1"],
            "obligation_ids": ["OBL-1"],
        }],
        "required_capabilities": [{
            "capability_id": "CAP-1", "mechanism_change_ids": ["RMC-1"],
        }],
        "design_obligations": [{
            "obligation_id": "OBL-1",
            "mechanism_change_ids": ["RMC-1"],
            "capability_ids": ["CAP-1"],
        }],
    }
    method_context = {
        "root_cause_analysis_id": "RCA-1",
        "root_cause_analysis_sha256": "b" * 64,
        "active_field_map_sha256": "a" * 64,
        "search_mode": "PRINCIPLE_SEARCH",
        "problem_id": "P-1",
        "problem_version": 1,
        "problem_contract_sha256": "c" * 64,
        "evidence_capsule_sha256": "d" * 64,
        "causal_chain_ids": ["CHAIN-1"],
        "required_mechanism_changes": deepcopy(context["required_mechanism_changes"]),
        "required_capabilities": deepcopy(context["required_capabilities"]),
        "design_obligations": deepcopy(context["design_obligations"]),
        "principle_search_context": {
            "target_mechanism_signatures": [{
                "target_mechanism_signature_id": "TMS-1",
                "rmc_id": "RMC-1",
                "domain_neutral_failure_structure": "a failed relation propagates error",
                "causal_or_computational_variable_or_relation": "calibration relation",
                "current_relation_or_state": "miscalibrated",
                "required_intervention": "restore the calibration relation",
                "change_direction": "miscalibrated to calibrated",
                "causal_position": "before failure propagation",
                "activation_condition": "the unstable regime",
            }],
            "domain_hypotheses": [{
                "domain_hypothesis_id": "DH-1",
                "rmc_id": "RMC-1",
                "target_mechanism_signature_ref": "TMS-1",
                "source_channel": "MODEL_PRIOR",
                "domain_or_research_community_or_paradigm": "relational estimation",
                "structural_rationale": "the same relation role is corrected",
                "expected_problem_structure": "unstable relational state",
                "expected_intervention_family": "state-dependent correction",
                "provenance_refs": [],
                "disposition": "EXPLORE",
            }],
            "terminology_maps": [{
                "terminology_map_id": "TERM-1",
                "domain_hypothesis_id": "DH-1",
                "canonical_problem_terms": ["canonical instability"],
                "canonical_variable_state_relation_terms": ["canonical relation"],
                "canonical_intervention_terms": ["canonical correction"],
                "canonical_method_families": ["relational estimator"],
                "evidence_refs": ["E-TERM"],
                "search_read_provenance": ["read:E-TERM"],
                "query_plan_sha256": "1" * 64,
            }],
            "decision_targets": ["source:RMC-1", "same-field:RMC-1"],
        },
    }
    queries = [
        {
            "query": "same-field calibrated relation intervention",
            "purpose": "search same-field mechanisms",
            "search_dimension": "SAME_FIELD_MECHANISM",
            "mechanism_change_ids": ["RMC-1"],
            "capability_ids": ["CAP-1"],
            "obligation_ids": ["OBL-1"],
            "causal_chain_ids": ["CHAIN-1"],
            "search_step": "SOURCE_SEARCH",
            "target_mechanism_signature_refs": ["TMS-1"],
            "domain_hypothesis_ids": [],
            "terminology_map_ids": [],
            "decision_target": "same-field:RMC-1",
        },
        {
            "query": "domain-neutral failed relation intervention review",
            "purpose": "execute the scholarly ACADEMIC_BRIDGE discovery",
            "search_dimension": "CROSS_DOMAIN_STRUCTURAL_ISOMORPHISM",
            "mechanism_change_ids": ["RMC-1"],
            "capability_ids": ["CAP-1"],
            "obligation_ids": ["OBL-1"],
            "causal_chain_ids": ["CHAIN-1"],
            "search_step": "DOMAIN_DISCOVERY",
            "target_mechanism_signature_refs": ["TMS-1"],
            "domain_hypothesis_ids": [],
            "terminology_map_ids": [],
            "decision_target": "source:RMC-1",
        },
        {
            "query": "canonical instability canonical correction",
            "purpose": "ground the candidate domain's canonical terminology",
            "search_dimension": "CROSS_DOMAIN_STRUCTURAL_ISOMORPHISM",
            "mechanism_change_ids": ["RMC-1"],
            "capability_ids": ["CAP-1"],
            "obligation_ids": ["OBL-1"],
            "causal_chain_ids": ["CHAIN-1"],
            "search_step": "TERMINOLOGY_GROUNDING",
            "target_mechanism_signature_refs": ["TMS-1"],
            "domain_hypothesis_ids": ["DH-1"],
            "terminology_map_ids": [],
            "decision_target": "source:RMC-1",
        },
        {
            "query": "canonical instability canonical correction intervention outcome",
            "purpose": "search a local Problem-Intervention pair",
            "search_dimension": "CROSS_DOMAIN_STRUCTURAL_ISOMORPHISM",
            "mechanism_change_ids": ["RMC-1"],
            "capability_ids": ["CAP-1"],
            "obligation_ids": ["OBL-1"],
            "causal_chain_ids": ["CHAIN-1"],
            "search_step": "SOURCE_SEARCH",
            "target_mechanism_signature_refs": ["TMS-1"],
            "domain_hypothesis_ids": ["DH-1"],
            "terminology_map_ids": ["TERM-1"],
            "decision_target": "source:RMC-1",
        },
    ]
    return context, {
        "coverage_gaps": [],
        "method_design_context": method_context,
        "queries": queries,
    }


def test_method_design_principle_search_consumes_complete_rmc_context() -> None:
    context, plan = principle_search_plan_fixture()
    validated = validate_query_plan(plan, method_design_context=context)
    assert validated["queries"] == plan["queries"]
    assert plan["method_design_context"]["search_mode"] == "PRINCIPLE_SEARCH"
    assert {query["search_dimension"] for query in plan["queries"]} == {
        "SAME_FIELD_MECHANISM", "CROSS_DOMAIN_STRUCTURAL_ISOMORPHISM",
    }
    assert {query["search_step"] for query in plan["queries"]} == {
        "DOMAIN_DISCOVERY", "TERMINOLOGY_GROUNDING", "SOURCE_SEARCH",
    }


def test_terminology_grounding_is_required_only_when_an_explore_domain_enters_source_search() -> None:
    context, plan = principle_search_plan_fixture()
    plan["method_design_context"]["principle_search_context"]["terminology_maps"] = []
    plan["queries"] = [
        item
        for item in plan["queries"]
        if not (
            item["search_dimension"] == "CROSS_DOMAIN_STRUCTURAL_ISOMORPHISM"
            and item["search_step"] in {"TERMINOLOGY_GROUNDING", "SOURCE_SEARCH"}
        )
    ]
    validate_query_plan(plan, method_design_context=context)

    _, source_plan = principle_search_plan_fixture()
    source_plan["method_design_context"]["principle_search_context"]["terminology_maps"] = []
    source_plan["queries"] = [
        item for item in source_plan["queries"]
        if item["search_step"] != "TERMINOLOGY_GROUNDING"
    ]
    source_query = next(
        item
        for item in source_plan["queries"]
        if item["search_dimension"] == "CROSS_DOMAIN_STRUCTURAL_ISOMORPHISM"
        and item["search_step"] == "SOURCE_SEARCH"
    )
    source_query["terminology_map_ids"] = []
    with pytest.raises(ValidationError, match="Terminology Map"):
        validate_query_plan(source_plan, method_design_context=context)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda plan: plan["method_design_context"].update(search_mode="ADAPTATION_GAP_SEARCH"),
            "must be PRINCIPLE_SEARCH",
        ),
        (
            lambda plan: plan["method_design_context"]["required_capabilities"][0].update(
                mechanism_change_ids=["RMC-MISSING"]
            ),
            "unresolved mechanism-change binding",
        ),
        (
            lambda plan: plan.update(
                queries=[
                    query for query in plan["queries"]
                    if query["search_dimension"] != "SAME_FIELD_MECHANISM"
                ]
            ),
            "formal SAME_FIELD_MECHANISM",
        ),
        (
            lambda plan: plan["queries"][0].update(obligation_ids=["OBL-MISSING"]),
            "unresolved ID",
        ),
    ],
)
def test_method_design_principle_search_rejects_incomplete_or_broken_context(
    mutate, message: str
) -> None:
    context, plan = principle_search_plan_fixture()
    mutate(plan)
    with pytest.raises(ValidationError, match=message):
        validate_query_plan(plan, method_design_context=context)


@pytest.mark.parametrize(
    ("phase", "decision", "verdict_id", "verdict_path"),
    [
        (
            "problem_quality_gate",
            "HOLD",
            "quality-return-verdict",
            "idea-stage/PROBLEM_QUALITY_VERDICTS.jsonl",
        ),
        (
            "problem_novelty_gate",
            "BLOCKED",
            "novelty-return-verdict",
            "idea-stage/PROBLEM_NOVELTY_VERDICTS.jsonl",
        ),
    ],
)
def test_negative_problem_reviewer_verdicts_return_to_problem_generation(
    tmp_path: Path,
    phase: str,
    decision: str,
    verdict_id: str,
    verdict_path: str,
) -> None:
    controller = start_controller(tmp_path)
    reach_problem_quality_gate(
        controller,
        decision=decision if phase == "problem_quality_gate" else None,
        verdict_id=verdict_id if phase == "problem_quality_gate" else "quality-recovery-verdict",
    )
    if phase == "problem_novelty_gate":
        accept_formal(controller, "quality-recovery-verdict", "claude-sonnet-4")
        controller.start_current_phase()
        novelty_path = tmp_path / verdict_path
        novelty_path.parent.mkdir(parents=True, exist_ok=True)
        novelty_path.write_text(
            formal_verdict_artifact(
                controller,
                verdict_id=verdict_id,
                decision=decision,
            ),
            encoding="utf-8",
        )
        controller.complete_current_phase()
    request = run_state._find_phase(controller.status(), phase)["review_request"]
    assert decision in request["allowed_review_verdicts"]
    assert controller.allowed_actions() == ["return_phase"]
    with pytest.raises(ControllerError, match="does not authorize acceptance"):
        controller.accept_current_phase(verdict_id, "claude-sonnet-4")
    attest_current_review(controller, verdict_id, "claude-sonnet-4", decision=decision)
    returned = controller.return_current_phase(verdict_id, "claude-sonnet-4")
    core = returned["scientific_core"]
    assert controller.current_stage() == "PROBLEM_GENERATION"
    assert core["return_history"][-1]["return_target"] == "problem_generation"
    if decision == "HOLD":
        assert core["return_history"][-1]["return_guidance"]["missing_evidence"] == [
            "targeted decision-grade evidence"
        ]
        assert "lesson_id" not in core["return_history"][-1]
    assert verdict_path in {
        Path(path).as_posix()
        for path in core["return_history"][-1]["invalidated_artifact_paths"]
    }
    assert core["active_problem_version"] is None
    assert core["pending_problem_revision"] is None
    assert not (tmp_path / verdict_path).exists()


@pytest.mark.parametrize("decision", ["NOT_NOVEL", "UNCERTAIN"])
def test_completed_non_novel_problem_audits_advance_to_human_gate(
    tmp_path: Path, decision: str
) -> None:
    controller = start_controller(tmp_path)
    reach_problem_quality_gate(controller)
    accept_formal(controller, "quality-recovery-verdict", "claude-sonnet-4")
    controller.start_current_phase()
    verdict_path = controller.root / "idea-stage" / "PROBLEM_NOVELTY_VERDICTS.jsonl"
    verdict_path.write_text(
        formal_verdict_artifact(
            controller, verdict_id=f"novelty-{decision.lower()}", decision=decision
        ),
        encoding="utf-8",
    )
    controller.complete_current_phase()
    assert controller.allowed_actions() == ["accept_phase"]
    accept_formal(controller, f"novelty-{decision.lower()}", "claude-sonnet-4")
    assert controller.current_stage() == "PROBLEM_HUMAN_ACCEPTANCE"


def test_problem_human_selection_requires_quality_and_completed_novelty_audit(
    tmp_path: Path,
) -> None:
    controller = start_controller(tmp_path)
    reach_problem_human_acceptance(controller)
    with controller._store.mutate() as state:
        novelty = run_state._find_phase(state, "problem_novelty_gate")
        novelty["candidate_ids"] = ["P-1"]
        novelty["survivor_ids"] = []

    approve(controller, "problem_acceptance", selected_id="P-1")
    assert controller.status()["scientific_core"]["active_problem_version"]["problem_id"] == "P-1"


def test_problem_human_revision_preserves_selected_uncertain_novelty_audit(
    tmp_path: Path,
) -> None:
    controller = start_controller(tmp_path)
    reach_problem_quality_gate(controller)
    accept_formal(controller, "quality-recovery-verdict", "claude-sonnet-4")
    controller.start_current_phase()
    verdict_path = controller.root / "idea-stage" / "PROBLEM_NOVELTY_VERDICTS.jsonl"
    verdict_path.write_text(
        formal_verdict_artifact(
            controller, verdict_id="novelty-uncertain", decision="UNCERTAIN"
        ),
        encoding="utf-8",
    )
    controller.complete_current_phase()
    accept_formal(controller, "novelty-uncertain", "claude-sonnet-4")
    write_problem_handoffs(controller)

    returned = request_human_gate_revision(controller, "problem_acceptance")
    audit = returned["scientific_core"]["return_history"][-1]["novelty_audit"]
    assert audit["candidate_id"] == "P-1"
    assert audit["candidate_verdict"] == "UNCERTAIN"
    assert audit["verdict_id"] == "novelty-uncertain"
    assert audit["artifact"]["path"] == "idea-stage/PROBLEM_NOVELTY_VERDICTS.jsonl"
    assert audit["novelty_assessment"]["revision_guidance"]["missing_evidence"] == [
        "Verify the potentially decisive closest prior."
    ]
    novelty = run_state._find_phase(returned, "problem_novelty_gate")
    assert novelty["return_guidance"] is None


def test_problem_human_revision_binds_only_the_selected_candidate_novelty_audit(
    tmp_path: Path,
) -> None:
    controller = start_controller(tmp_path)
    digest, request_id = reach_coverage(controller)
    review = coverage_review(digest, request_id)
    attest(controller, "coverage_reviewer", review)
    controller.submit_coverage_review(review)
    approve(controller, "scope_human_approval")

    controller.start_current_phase()
    candidate_path = controller.root / "idea-stage/PROBLEM_CANDIDATES.jsonl"
    candidate_path.write_text(
        problem_candidate("P-1") + problem_candidate("P-2"), encoding="utf-8"
    )
    (controller.root / "idea-stage/PROBLEM_CANDIDATES.md").write_text(
        "# Problems\nP-1\nP-2", encoding="utf-8"
    )
    controller.complete_current_phase()
    controller.start_current_phase()
    quality_path = controller.root / "idea-stage/PROBLEM_QUALITY_VERDICTS.jsonl"
    quality_rows = [
        json.loads(line)
        for line in formal_verdict_artifact(controller, verdict_id="quality-mixed").splitlines()
    ]
    quality_second = json.loads(json.dumps(quality_rows[0]))
    quality_second["candidate_id"] = "P-2"
    quality_rows[1]["survivor_ids"] = ["P-1", "P-2"]
    quality_path.write_text(
        "\n".join(json.dumps(row) for row in (quality_rows[0], quality_second, quality_rows[1])) + "\n",
        encoding="utf-8",
    )
    controller.complete_current_phase()
    accept_formal(controller, "quality-mixed", "claude-sonnet-4")

    controller.start_current_phase()
    novelty_path = controller.root / "idea-stage/PROBLEM_NOVELTY_VERDICTS.jsonl"
    novelty_rows = [
        json.loads(line)
        for line in formal_verdict_artifact(controller, verdict_id="novelty-mixed").splitlines()
    ]
    not_novel = json.loads(json.dumps(novelty_rows[0]))
    not_novel["candidate_id"] = "P-2"
    not_novel["decision"] = "NOT_NOVEL"
    not_novel["novelty_assessment"]["closest_priors"][0]["overlap"] = "P-2 overlap only"
    not_novel["novelty_assessment"]["revision_guidance"] = {
        "closest_prior_ids": ["P1"],
        "key_overlap": "P-2 duplicates the closest prior's framing.",
        "residual_delta": "P-2 has no remaining delta.",
        "recommended_reframing": ["Test a different operating condition."],
    }
    novelty_path.write_text(
        "\n".join(json.dumps(row) for row in (novelty_rows[0], not_novel, novelty_rows[1])) + "\n",
        encoding="utf-8",
    )
    controller.complete_current_phase()
    accept_formal(controller, "novelty-mixed", "claude-sonnet-4")
    write_problem_handoffs(controller)

    returned = request_human_gate_revision(
        controller, "problem_acceptance", selected_id="P-2"
    )
    record = returned["scientific_core"]["return_history"][-1]
    audit = record["novelty_audit"]
    assert controller.current_stage() == "PROBLEM_GENERATION"
    assert record["selected_id"] == "P-2"
    assert audit["candidate_id"] == "P-2"
    assert audit["candidate_verdict"] == "NOT_NOVEL"
    assert audit["novelty_assessment"]["closest_priors"][0]["overlap"] == "P-2 overlap only"
    assert audit["novelty_assessment"]["revision_guidance"]["recommended_reframing"] == [
        "Test a different operating condition."
    ]
    assert "P-1" not in json.dumps(audit["novelty_assessment"])


def test_problem_human_revision_of_novel_candidate_has_no_other_candidate_guidance(
    tmp_path: Path,
) -> None:
    controller = start_controller(tmp_path)
    reach_problem_human_acceptance(controller)

    returned = request_human_gate_revision(controller, "problem_acceptance", selected_id="P-1")
    audit = returned["scientific_core"]["return_history"][-1]["novelty_audit"]
    assert audit["candidate_id"] == "P-1"
    assert audit["candidate_verdict"] == "NOVEL"
    assert "revision_guidance" not in audit["novelty_assessment"]


def test_human_gate_requires_one_time_codex_ui_receipt(tmp_path: Path) -> None:
    write_policy(tmp_path)
    controller = ARISController.start(tmp_path, "run-human", executor="codex")
    with pytest.raises(ControllerError, match="no Codex UI approval receipt"):
        controller.human_approve("source_policy_approval", "approve")
    assert controller.current_stage() == "WAITING_FOR_HUMAN"
    approve(controller, "source_policy_approval")
    assert controller.current_stage() == "QUERY_PLANNING"
    with pytest.raises(ControllerError):
        controller.human_approve("source_policy_approval", "approve")


def test_scope_and_problem_human_gate_revision_return_through_declared_targets(
    tmp_path: Path,
) -> None:
    controller = start_controller(tmp_path)
    digest, request_id = reach_coverage(controller)
    review = coverage_review(digest, request_id)
    attest(controller, "coverage_reviewer", review)
    controller.submit_coverage_review(review)

    request_human_gate_revision(controller, "scope_human_approval")
    assert controller.current_stage() == "QUERY_PLANNING"
    scope = run_state._find_phase(controller.status(), "scope_human_approval")
    assert scope["status"] == "pending"
    assert controller.status()["research_lit"]["approvals"][-1]["decision"] == "request_revision"

    controller = start_controller(tmp_path / "problem")
    reach_problem_human_acceptance(controller)
    (controller.root / "idea-stage" / "RESEARCH_CONTRACT.md").unlink()
    request = controller.validate_human_gate_decision(
        "problem_acceptance",
        "request_revision",
        selected_id="P-1",
        human_feedback="Correct the selected problem's stated scope.",
    )
    receipt_path = approvals._receipt_path(controller.root, controller.run_id, request["id"])
    returned = request_human_gate_revision(controller, "problem_acceptance")
    assert controller.current_stage() == "PROBLEM_GENERATION"
    core = returned["scientific_core"]
    record = core["return_history"][-1]
    assert record["return_target"] == "problem_generation"
    assert record["decision"] == "request_revision"
    assert record["approval_request_id"] == request["id"]
    assert not receipt_path.exists()
    assert receipt_path.with_suffix(".consumed.json").is_file()
    assert not (controller.root / "idea-stage" / "RESEARCH_CONTRACT.md").exists()
    assert not (controller.root / "idea-stage" / "PROBLEM_EVIDENCE_CAPSULE.md").exists()
    assert core["active_problem_version"] is None
    assert controller.allowed_actions() == ["start_phase"]


def test_problem_human_return_readopts_only_prior_problem_generation_evidence(
    tmp_path: Path,
) -> None:
    controller = start_controller(tmp_path)
    reach_problem_human_acceptance(controller)
    request_human_gate_revision(controller, "problem_acceptance")
    controller.start_current_phase()

    card_path = tmp_path / ".aris" / "canonical" / "run-1" / "evidence-P2.json"
    card_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_card = {"source_id": "P2", "read_event_id": "R-P2"}
    card_path.write_text(json.dumps(evidence_card), encoding="utf-8")
    registry = tmp_path / "idea-stage" / "EVIDENCE_REGISTRY.jsonl"
    with registry.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(evidence_card) + "\n")
    with controller._store.mutate() as state:
        research = state["research_lit"]
        record = {
            "path": str(card_path.relative_to(tmp_path)),
            "sha256": sha256_file(card_path),
            "read_event_id": "R-P2",
            "validator_result": "PASS",
        }
        research["accepted_artifacts"]["evidence:P2"] = record
        research["read_events"]["R-P2"] = {"paper_id": "P2", "status": "complete"}
        research["papers"]["P2"] = {
            "source_origin": "user_supplied",
            "found_by_query_ids": [],
        }
        old_anchor = {
            "phase": "problem_generation",
            "required_inputs": {
                "idea-stage/ACTIVE_FIELD_MAP.md": controller._binding_artifact_identity(
                    controller._registered_artifact_by_path(state, "idea-stage/ACTIVE_FIELD_MAP.md")
                )
            },
            "lifecycle_return_event_id": None,
        }
        research.setdefault("incremental_evidence_by_phase", {}).setdefault(
            "problem_generation", {}
        )["evidence:P2"] = {
            **record,
            "evidence_key": "evidence:P2",
            "phase_binding_anchor": old_anchor,
        }

    assert "P2" not in controller._current_phase_evidence_ids(
        controller.status(), "problem_generation"
    )
    assert "readopt_evidence" in controller.allowed_actions()
    assert controller.readopt_incremental_evidence("P2") == {
        "status": "RE_ADOPTED", "evidence_id": "P2", "phase": "problem_generation"
    }
    assert "P2" in controller._current_phase_evidence_ids(
        controller.status(), "problem_generation"
    )
    with pytest.raises(ControllerError, match="prior binding in problem_generation"):
        controller.readopt_incremental_evidence("P1")


def test_problem_human_returns_require_feedback_and_bind_the_exact_receipt(
    tmp_path: Path,
) -> None:
    controller = start_controller(tmp_path)
    reach_problem_human_acceptance(controller)
    for decision in ("request_revision", "reject"):
        with pytest.raises(ControllerError, match="non-empty human_feedback"):
            controller.validate_human_gate_decision(
                "problem_acceptance", decision, selected_id="P-1"
            )
        with pytest.raises(ControllerError, match="explicit selected_id"):
            controller.validate_human_gate_decision(
                "problem_acceptance", decision, human_feedback="Human reason."
            )

    feedback = "Limit the claim to the measured contact regime."
    request = controller.validate_human_gate_decision(
        "problem_acceptance",
        "request_revision",
        selected_id="P-1",
        human_feedback=feedback,
    )
    receipt_path = approvals.issue_ui_approval_receipt(
        controller.root,
        controller.run_id,
        "problem_acceptance",
        request["id"],
        "request_revision",
        selected_id="P-1",
        human_feedback=feedback,
        artifact_bindings=request["artifact_bindings"],
    )
    tampered = json.loads(receipt_path.read_text(encoding="utf-8"))
    tampered["human_feedback"] = "Different feedback."
    receipt_path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(ControllerError, match="does not match the pending Gate"):
        controller.human_approve(
            "problem_acceptance",
            "request_revision",
            selected_id="P-1",
            human_feedback=feedback,
        )
    assert controller.current_stage() == "PROBLEM_HUMAN_ACCEPTANCE"

    missing = start_controller(tmp_path / "missing-feedback")
    reach_problem_human_acceptance(missing)
    request = missing.validate_human_gate_decision(
        "problem_acceptance",
        "request_revision",
        selected_id="P-1",
        human_feedback=feedback,
    )
    approvals.issue_ui_approval_receipt(
        missing.root,
        missing.run_id,
        "problem_acceptance",
        request["id"],
        "request_revision",
        selected_id="P-1",
        artifact_bindings=request["artifact_bindings"],
    )
    with pytest.raises(ControllerError, match="does not match the pending Gate"):
        missing.human_approve(
            "problem_acceptance",
            "request_revision",
            selected_id="P-1",
            human_feedback=feedback,
        )


def test_problem_human_request_revision_preserves_the_selected_candidate_baseline(
    tmp_path: Path,
) -> None:
    controller = start_controller(tmp_path)
    reach_problem_human_acceptance(controller)
    candidate_path = "idea-stage/PROBLEM_CANDIDATES.jsonl"
    candidate_sha256 = controller.status()["scientific_core"]["accepted_artifacts"][
        candidate_path
    ]["sha256"]

    returned = request_human_gate_revision(
        controller,
        "problem_acceptance",
        selected_id="P-1",
        human_feedback="Correct the claimed operating regime only.",
    )
    core = returned["scientific_core"]
    record = core["return_history"][-1]
    baseline = record["candidate_baseline"]
    assert record["decision"] == "request_revision"
    assert record["human_feedback"] == "Correct the claimed operating regime only."
    assert baseline["selected_id"] == "P-1"
    assert baseline["candidate_artifact"] == {
        "path": candidate_path,
        "sha256": candidate_sha256,
        "archive_path": (
            Path(record["archive_root"]).as_posix() + "/artifacts/" + candidate_path
        ),
    }
    assert (controller.root / baseline["candidate_artifact"]["archive_path"]).is_file()
    assert core["active_problem_version"] is None
    assert core["pending_problem_revision"] is None
    assert [
        run_state._find_phase(returned, phase)["status"]
        for phase in (
            "problem_generation",
            "problem_quality_gate",
            "problem_novelty_gate",
            "problem_human_acceptance",
        )
    ] == ["pending", "pending", "pending", "pending"]
    assert returned["research_lit"]["incremental_literature_active"] is None


def test_problem_human_reject_reopens_without_a_candidate_inheritance_constraint(
    tmp_path: Path,
) -> None:
    controller = start_controller(tmp_path)
    reach_problem_human_acceptance(controller)
    (controller.root / "idea-stage" / "RESEARCH_CONTRACT.md").unlink()
    (controller.root / "idea-stage" / "PROBLEM_EVIDENCE_CAPSULE.md").unlink()

    returned = reject_problem_candidate(
        controller,
        human_feedback="The selected candidate's central premise is not established.",
    )
    core = returned["scientific_core"]
    record = core["return_history"][-1]
    assert controller.current_stage() == "PROBLEM_GENERATION"
    assert record["decision"] == "reject"
    assert record["selected_id"] == "P-1"
    assert record["human_feedback"] == "The selected candidate's central premise is not established."
    assert "candidate_baseline" not in record
    assert core["active_problem_version"] is None
    assert core["pending_problem_revision"] is None
    assert returned["research_lit"]["incremental_literature_active"] is None


def test_reject_is_not_a_decision_of_other_human_gates(tmp_path: Path) -> None:
    controller = start_controller(tmp_path)
    digest, request_id = reach_coverage(controller)
    review = coverage_review(digest, request_id)
    attest(controller, "coverage_reviewer", review)
    controller.submit_coverage_review(review)
    with pytest.raises(ControllerError, match="not declared"):
        controller.validate_human_gate_decision("scope_human_approval", "reject")


def test_scope_revision_remains_available_when_new_audit_finds_coverage_gap(
    tmp_path: Path,
) -> None:
    controller = start_controller(tmp_path)
    digest, request_id = reach_coverage(controller)
    review = coverage_review(digest, request_id)
    attest(controller, "coverage_reviewer", review)
    controller.submit_coverage_review(review)
    append_jsonl(
        tmp_path / "idea-stage" / "LITERATURE_CORPUS.jsonl",
        {
            **metadata("UNSCREENED"),
            "source_id": "UNSCREENED",
            "admission_status": "DISCOVERY_METADATA_ONLY",
        },
    )

    request_human_gate_revision(controller, "scope_human_approval")

    assert controller.current_stage() == "QUERY_PLANNING"


def test_human_receipt_with_wrong_artifact_binding_cannot_approve(tmp_path: Path) -> None:
    write_policy(tmp_path)
    controller = ARISController.start(tmp_path, "run-bound-human", executor="codex")
    request = controller.validate_human_gate_request("source_policy_approval")
    approvals.issue_ui_approval_receipt(
        controller.root,
        controller.run_id,
        "source_policy_approval",
        request["id"],
        "approve",
        artifact_bindings={"idea-stage\\SOURCE_ADMISSION_POLICY.yaml": "0" * 64},
    )
    with pytest.raises(ControllerError, match="does not match the pending Gate"):
        controller.human_approve("source_policy_approval", "approve")
    assert controller.current_stage() == "WAITING_FOR_HUMAN"


def test_human_receipt_is_restored_when_bound_outputs_disappear_after_consumption(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller = start_controller(tmp_path)
    reach_problem_human_acceptance(controller)
    request = controller.validate_human_gate_request("problem_acceptance")
    approvals.issue_ui_approval_receipt(
        controller.root,
        controller.run_id,
        "problem_acceptance",
        request["id"],
        "approve",
        selected_id="P-1",
        artifact_bindings=request["artifact_bindings"],
    )
    receipt_path = approvals._receipt_path(controller.root, controller.run_id, request["id"])
    contract = controller.root / "idea-stage" / "RESEARCH_CONTRACT.md"
    contract_text = contract.read_text(encoding="utf-8")
    consume = approvals.consume_ui_approval_receipt

    def consume_then_remove_output(*args: object, **kwargs: object) -> dict:
        receipt = consume(*args, **kwargs)
        contract.unlink()
        return receipt

    monkeypatch.setattr(approvals, "consume_ui_approval_receipt", consume_then_remove_output)
    with pytest.raises(ControllerError, match="missing required"):
        controller.human_approve("problem_acceptance", "approve", selected_id="P-1")
    assert receipt_path.is_file()
    assert not receipt_path.with_suffix(".consumed.json").exists()

    monkeypatch.setattr(approvals, "consume_ui_approval_receipt", consume)
    contract.write_text(contract_text, encoding="utf-8")
    controller.human_approve("problem_acceptance", "approve", selected_id="P-1")
    assert not receipt_path.exists()
    assert receipt_path.with_suffix(".consumed.json").is_file()


def test_state_save_failure_restores_receipt_and_successful_retry_consumes_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_policy(tmp_path)
    controller = ARISController.start(tmp_path, "save-recovery", executor="codex")
    request = controller.validate_human_gate_request("source_policy_approval")
    approvals.issue_ui_approval_receipt(
        controller.root,
        controller.run_id,
        "source_policy_approval",
        request["id"],
        "approve",
        artifact_bindings=request["artifact_bindings"],
    )
    receipt_path = approvals._receipt_path(controller.root, controller.run_id, request["id"])
    save = run_state._save
    failed = False

    def fail_once(*args: object, **kwargs: object) -> None:
        nonlocal failed
        if not failed:
            failed = True
            raise OSError("simulated state save failure")
        save(*args, **kwargs)

    monkeypatch.setattr(run_state, "_save", fail_once)
    with pytest.raises(OSError, match="simulated state save failure"):
        controller.human_approve("source_policy_approval", "approve")
    assert receipt_path.is_file()
    assert controller.current_stage() == "WAITING_FOR_HUMAN"

    controller.human_approve("source_policy_approval", "approve")
    assert not receipt_path.exists()
    assert receipt_path.with_suffix(".consumed.json").is_file()
    with pytest.raises(ValueError, match="no Codex UI approval receipt"):
        approvals.consume_ui_approval_receipt(
            controller.root,
            controller.run_id,
            "source_policy_approval",
            request["id"],
            "approve",
            artifact_bindings=request["artifact_bindings"],
        )


def test_same_family_reviewer_attestation_is_accepted(
    tmp_path: Path,
) -> None:
    controller = start_controller(tmp_path)
    reviewer = "codex-gpt-5.6-sol"
    reach_problem_quality_gate(controller, reviewer=reviewer)
    core = controller.status()["scientific_core"]
    phase = run_state._find_phase(controller.status(), core["current_phase"])
    request = phase["review_request"]
    attest_current_review(
        controller,
        "quality-recovery-verdict",
        reviewer,
    )
    path = reviews.review_attestation_path(
        controller.root,
        controller.run_id,
        request["required_reviewer_role"],
        request["id"],
    )
    state = controller.accept_current_phase("quality-recovery-verdict", reviewer)
    assert not path.is_file()
    assert path.with_suffix(".consumed.json").is_file()
    accepted = run_state._find_phase(state, "problem_quality_gate")
    assert accepted["status"] == "accepted"
    assert accepted["review_independence"] == "independent-context"


def test_problem_quality_codex_cli_reviewer_payload_passes_existing_gate_pipeline(
    tmp_path: Path,
) -> None:
    """A direct Codex reviewer payload keeps the artifact/attestation flow intact."""

    reviewer = "codex-gpt-5.6-sol"
    controller = start_controller(tmp_path, executor="gemini-3.1-pro")
    reach_problem_quality_gate(controller, reviewer=reviewer, verdict_id="codex-quality-1")

    phase = run_state._find_phase(controller.status(), "problem_quality_gate")
    request = phase["review_request"]
    attest_current_review(controller, "codex-quality-1", reviewer)
    state = controller.accept_current_phase("codex-quality-1", reviewer)

    assert phase["status"] == "done"
    assert state["scientific_core"]["current_phase"] == "problem_novelty_gate"
    accepted = run_state._find_phase(state, "problem_quality_gate")
    assert accepted["status"] == "accepted"
    assert accepted["reviewer"] == reviewer
    assert accepted["review_independence"] == "cross-family"
    receipt = reviews.review_attestation_path(
        controller.root,
        controller.run_id,
        "independent_problem_reviewer",
        request["id"],
    )
    assert receipt.with_suffix(".consumed.json").is_file()


def test_fresh_project_drafts_validates_and_human_approves_policy_before_query(
    tmp_path: Path,
) -> None:
    controller = ARISController.start(tmp_path, "fresh-policy", executor="codex")
    policy_path = tmp_path / "idea-stage" / "SOURCE_ADMISSION_POLICY.yaml"

    assert controller.current_stage() == "SOURCE_POLICY_DRAFTING"
    assert controller.allowed_actions() == ["submit_source_admission_policy"]
    assert controller.allowed_agents() == ["main_research_agent"]
    assert not policy_path.exists()
    assert controller.status()["research_lit"]["approval_request"] is None
    with pytest.raises(ControllerError, match="WAITING_FOR_HUMAN"):
        controller.pending_human_approval()

    invalid = policy_payload()
    invalid.pop("high_citation_rule")
    with pytest.raises(ControllerError, match="citation threshold"):
        controller.submit_source_admission_policy(invalid)
    assert controller.current_stage() == "SOURCE_POLICY_DRAFTING"
    assert not policy_path.exists()

    controller.submit_source_admission_policy(policy_payload())
    research = controller.status()["research_lit"]
    assert controller.current_stage() == "WAITING_FOR_HUMAN"
    assert controller.allowed_actions() == ["human_approve", "request_source_policy_revision"]
    assert controller.allowed_agents() == []
    assert research["waiting_for"] == "source_policy_approval"
    assert research["pending_source_policy"]["validator_result"] == "PASS"
    assert research["pending_source_policy"]["author_role"] == "main_research_agent"
    assert "source_admission_policy" not in research["accepted_artifacts"]
    assert research["approval_request"]["artifact_sha256"] == research[
        "pending_source_policy"
    ]["sha256"]

    calls: list[str] = []
    with pytest.raises(ControllerError, match="METADATA_RETRIEVAL"):
        controller.execute_query(
            "test field", "fake", lambda value: calls.append(value) or []
        )
    assert calls == []
    with pytest.raises(ControllerError, match="no Codex UI approval receipt"):
        controller.human_approve("source_policy_approval", "approve")
    assert controller.current_stage() == "WAITING_FOR_HUMAN"

    approve(controller, "source_policy_approval")
    approved = controller.status()["research_lit"]
    assert controller.current_stage() == "QUERY_PLANNING"
    assert approved["accepted_artifacts"]["source_admission_policy"][
        "approved_by"
    ] == "codex_ui_user"
    assert approved["pending_source_policy"] is None

    controller.submit_query_plan(
        {
            "coverage_gaps": ["anchor"],
            "queries": [{"query": "test field", "purpose": "close explicit gap"}],
        }
    )
    controller.execute_query(
        "test field", "fake", lambda value: calls.append(value) or []
    )
    assert calls == ["test field"]


def test_existing_valid_policy_can_be_revised_only_through_human_gate(tmp_path: Path) -> None:
    write_policy(tmp_path)
    controller = ARISController.start(tmp_path, "policy-revision", executor="codex")
    original = controller.status()["research_lit"]
    original_hash = original["pending_source_policy"]["sha256"]

    assert controller.current_stage() == "WAITING_FOR_HUMAN"
    assert controller.allowed_actions() == ["human_approve", "request_source_policy_revision"]
    assert controller.allowed_agents() == []
    with pytest.raises(ControllerError, match="SOURCE_POLICY_DRAFTING"):
        controller.submit_source_admission_policy(policy_payload())
    with pytest.raises(ControllerError, match="no Codex UI approval receipt"):
        controller.request_source_policy_revision()

    with controller._store.mutate() as state:
        state["research_lit"]["human_fulltext_request"] = {"papers": [{"paper_id": "stale"}]}

    request_source_policy_revision(controller)
    revised = controller.status()["research_lit"]
    assert controller.current_stage() == "SOURCE_POLICY_DRAFTING"
    assert controller.allowed_actions() == ["submit_source_admission_policy"]
    assert controller.allowed_agents() == ["main_research_agent"]
    assert revised["waiting_for"] is None
    assert revised["approval_request"] is None
    assert revised["pending_source_policy"] is None
    assert revised["human_fulltext_request"] is None
    assert revised["approvals"][-1]["decision"] == "request_revision"
    assert revised["approvals"][-1]["artifact_sha256"] == original_hash

    updated_policy = policy_payload()
    updated_policy["high_citation_rule"]["thresholds"][0][
        "citation_count_strictly_greater_than"
    ] = 101
    controller.submit_source_admission_policy(updated_policy)
    revalidated = controller.status()["research_lit"]
    new_hash = revalidated["pending_source_policy"]["sha256"]
    assert new_hash != original_hash
    assert revalidated["pending_source_policy"]["validator_result"] == "PASS"
    assert revalidated["approval_request"]["artifact_sha256"] == new_hash
    assert controller.current_stage() == "WAITING_FOR_HUMAN"

    with controller._store.mutate() as state:
        state["research_lit"]["human_fulltext_request"] = {"papers": [{"paper_id": "stale"}]}

    approve(controller, "source_policy_approval")
    accepted = controller.status()["research_lit"]
    assert controller.current_stage() == "QUERY_PLANNING"
    assert accepted["accepted_artifacts"]["source_admission_policy"]["sha256"] == new_hash
    assert accepted["human_fulltext_request"] is None


def test_default_budget_blocks_81st_query_before_tool_call(tmp_path: Path) -> None:
    queries = [f"q{index}" for index in range(1, 82)]
    controller = start_controller(tmp_path, queries=queries, run_id="run-80")
    calls: list[str] = []
    for query in queries[:80]:
        controller.execute_query(query, "fake", lambda value: calls.append(value) or [])
    with pytest.raises(ControllerError, match="80/80"):
        controller.execute_query(queries[80], "fake", lambda value: calls.append(value) or [])
    assert len(calls) == 80


def test_source_policy_cannot_define_a_second_runtime_budget(tmp_path: Path) -> None:
    write_policy(tmp_path)
    policy = yaml.safe_load(
        (tmp_path / "idea-stage" / "SOURCE_ADMISSION_POLICY.yaml").read_text(
            encoding="utf-8"
        )
    )
    policy["research_effort_budget"] = {"max_queries": 40}
    with pytest.raises(ValidationError, match="canonical workflow"):
        validate_source_admission_policy(policy)


def test_unplanned_query_is_rejected_before_gateway(tmp_path: Path) -> None:
    controller = start_controller(tmp_path)
    calls: list[str] = []
    with pytest.raises(ControllerError, match="not accepted"):
        controller.execute_query("invented query", "fake", lambda value: calls.append(value) or [])
    assert not calls


def test_rediscovery_does_not_rollback_verified_admission(tmp_path: Path) -> None:
    controller = start_controller(tmp_path, queries=["first query", "second query"])
    controller.execute_query("first query", "fake", lambda _: [metadata()])
    assert controller.decide_admission("P1", screening_in_scope=True) == "ADMIT_FOR_READING"

    rediscovered = metadata()
    rediscovered.update(
        {
            "title": "test paper",
            "citation_count": 42,
            "identity_status": "verify_pending",
        }
    )
    controller.execute_query("second query", "fake", lambda _: [rediscovered])

    paper = controller.status()["research_lit"]["papers"]["P1"]
    assert paper["context_decisions"][-1]["admission_status"] == "ADMIT_FOR_READING"
    assert paper["identity_status"] == "verified"
    assert paper["title"] == "Test paper"
    assert paper["citation_count"] == 42
    assert paper["found_by_query_ids"] == ["Q0001", "Q0002"]


def test_finish_retrieval_repairs_pre_fix_accepted_evidence_rollback(
    tmp_path: Path,
) -> None:
    controller = start_controller(tmp_path)
    reach_synthesis(controller)
    with controller._store.mutate() as state:
        research = state["research_lit"]
        research["current_stage"] = "METADATA_RETRIEVAL"
        research["papers"]["P1"] = {
            **metadata(),
            "source_id": "P1",
            "identity_status": "verify_pending",
            "found_by_query_ids": ["Q0001", "Q0002"],
        }

    with controller._store.mutate() as state:
        restored = controller._reconcile_accepted_evidence_papers(state["research_lit"])

    paper = controller.status()["research_lit"]["papers"]["P1"]
    assert restored == ["P1"]
    assert paper["identity_status"] == "verified"
    assert paper["context_decisions"][-1]["admission_status"] == "ADMIT_DECISION_GRADE"
    assert paper["found_by_query_ids"] == ["Q0001", "Q0002"]
    assert "record_sha256" not in paper
    assert "previous_record_sha256" not in paper
    ledger = (tmp_path / "idea-stage" / "SEARCH_LEDGER.jsonl").read_text(
        encoding="utf-8"
    )
    assert '"action": "rediscovery_reconciliation"' in ledger


def test_accepted_user_source_does_not_require_gateway_identity_for_reconciliation(
    tmp_path: Path,
) -> None:
    controller = start_controller(tmp_path)
    source = tmp_path / "source-materials" / "user-paper.txt"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("user supplied paper", encoding="utf-8")
    supplied = metadata("USER1")
    supplied["source_path"] = "source-materials/user-paper.txt"
    controller.register_user_source(supplied)
    with controller._store.mutate() as state:
        research = state["research_lit"]
        research["accepted_artifacts"]["evidence:USER1"] = {"path": "evidence.json"}
        restored = controller._reconcile_accepted_evidence_papers(research)

    assert restored == []
    assert controller.status()["research_lit"]["papers"]["USER1"]["source_origin"] == (
        "user_supplied"
    )


def test_evidence_artifact_name_safely_encodes_external_paper_ids(tmp_path: Path) -> None:
    controller = start_controller(tmp_path)
    ordinary = controller._evidence_artifact_name("P1")
    external = controller._evidence_artifact_name("scholar:15965392972228430987")

    assert ordinary == "evidence-P1"
    assert external.startswith("evidence-external-")
    assert ":" not in external
    assert external == controller._evidence_artifact_name("scholar:15965392972228430987")


def test_formal_preflight_rollback_allows_full_access_without_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller = start_controller(tmp_path)
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    monkeypatch.setenv("CODEX_PERMISSION_PROFILE", ":danger-full-access")
    calls: list[str] = []
    controller.execute_query(
        "test field", "fake", lambda value: calls.append(value) or []
    )
    assert calls == ["test field"]
    assert controller.status()["research_lit"]["query_count"] == 1
    assert not (tmp_path / ".aris" / "formal-preflight").exists()


def test_paper_reader_evidence_accepts_valid_card_without_attestation(
    tmp_path: Path,
) -> None:
    controller = start_controller(tmp_path)
    reach_reading(controller)
    read = controller.read_full_text("P1", "fake-paper", lambda _: "full paper")
    evidence = card(read)
    controller.submit_evidence_card("P1", evidence)
    accepted = controller.status()["research_lit"]["accepted_artifacts"]["evidence:P1"]
    assert accepted["read_event_id"] == read["read_event_id"]
    assert "paper_reader_agent_id" not in accepted


def test_paper_reader_evidence_consumes_valid_attestation_and_records_agent(
    tmp_path: Path,
) -> None:
    controller = start_controller(tmp_path)
    reach_reading(controller)
    read = controller.read_full_text("P1", "fake-paper", lambda _: "full paper")
    evidence = card(read)
    attest(controller, "paper_reader", evidence)
    receipt = (
        tmp_path / ".aris" / "agent-attestations" / "paper_reader" / f"{read['read_event_id']}.json"
    )
    controller.submit_evidence_card("P1", evidence)
    accepted = controller.status()["research_lit"]["accepted_artifacts"]["evidence:P1"]
    assert accepted["paper_reader_agent_id"] == "agent-paper_reader-test"
    assert not receipt.exists()
    assert receipt.with_suffix(".consumed.json").is_file()


def test_paper_reader_evidence_rejects_mismatched_attestation(
    tmp_path: Path,
) -> None:
    controller = start_controller(tmp_path)
    reach_reading(controller)
    read = controller.read_full_text("P1", "fake-paper", lambda _: "full paper")
    evidence = card(read)
    attest(controller, "paper_reader", evidence)
    receipt = (
        tmp_path / ".aris" / "agent-attestations" / "paper_reader" / f"{read['read_event_id']}.json"
    )
    malformed = json.loads(receipt.read_text(encoding="utf-8"))
    malformed["payload_sha256"] = "0" * 64
    receipt.write_text(json.dumps(malformed), encoding="utf-8")
    with pytest.raises(ControllerError, match="invalid or mismatched paper_reader attestation"):
        controller.submit_evidence_card("P1", evidence)
    assert receipt.is_file()
    assert "evidence:P1" not in controller.status()["research_lit"]["accepted_artifacts"]


def test_all_provider_failures_stop_for_human_search_and_resume_with_results(
    tmp_path: Path,
) -> None:
    controller = start_controller(tmp_path)
    attempts = [
        {"provider": "serpapi_google_scholar", "status": "unavailable", "reason": "key"},
        {"provider": "scholar_google_hk", "status": "blocked", "reason": "403"},
        {"provider": "arxiv", "status": "unavailable", "reason": "network"},
        {"provider": "ieee_xplore", "status": "unavailable", "reason": "key"},
    ]

    with pytest.raises(HumanSearchRequired):
        controller.execute_query(
            "test field",
            "research-lit-provider-cascade",
            lambda _: (_ for _ in ()).throw(HumanSearchRequired(attempts)),
        )

    research = controller.status()["research_lit"]
    assert research["current_stage"] == "HUMAN_SEARCH_REQUIRED"
    assert research["human_search_request"]["query"] == "test field"
    assert research["human_search_request"]["purpose"] == "close explicit gap"
    assert research["human_search_request"]["evidence_gaps"] == ["anchor"]
    rows = controller.submit_human_search_results(
        {"query": "test field", "results": [metadata()]}
    )
    assert rows[0]["search_route"] == "human_google_scholar"
    assert controller.current_stage() == "METADATA_RETRIEVAL"
    research = controller.status()["research_lit"]
    assert research["query_count"] == 1
    assert research["query_events"]["Q0001"]["status"] == "complete_human"
    ledger = (tmp_path / "idea-stage" / "SEARCH_LEDGER.jsonl").read_text(
        encoding="utf-8"
    )
    assert '"result_status": "complete_human"' in ledger


def level_three_outcome(rows: list[dict]) -> SearchOutcome:
    return SearchOutcome(
        rows,
        "arxiv+ieee_xplore",
        False,
        [
            {"provider": "serpapi_google_scholar", "status": "unavailable", "reason": "key"},
            {"provider": "scholar_google_hk", "status": "unavailable", "reason": "no browser"},
            {"provider": "arxiv", "status": "complete", "reason": ""},
            {"provider": "ieee_xplore", "status": "complete", "reason": ""},
        ],
    )


def test_partial_automatic_discovery_stops_for_one_batch_human_search(
    tmp_path: Path,
) -> None:
    controller = start_controller(tmp_path)
    with pytest.raises(HumanSearchRequired):
        controller.execute_query(
            "test field",
            "research-lit-provider-cascade",
            lambda _: level_three_outcome([metadata(venue="Ordinary")]),
        )
    research = controller.status()["research_lit"]
    assert research["current_stage"] == "HUMAN_SEARCH_REQUIRED"
    assert research["human_search_request"]["query"] == "test field"
    assert research["human_search_request"]["kind"] == "metadata_search_batch"
    assert research["human_search_request"]["queries"][0]["query"] == "test field"
    assert research["papers"]["P1"]["venue"] == "Ordinary"


def test_all_provider_failure_human_fallback_passes_final_landscape_audit(
    tmp_path: Path,
) -> None:
    controller = start_controller(tmp_path)
    attempts = [
        {"provider": "serpapi_google_scholar", "status": "unavailable", "reason": "key"},
        {"provider": "scholar_google_hk", "status": "blocked", "reason": "403"},
        {"provider": "arxiv", "status": "unavailable", "reason": "network"},
        {"provider": "ieee_xplore", "status": "unavailable", "reason": "key"},
    ]
    with pytest.raises(HumanSearchRequired):
        controller.execute_query(
            "test field",
            "research-lit-provider-cascade",
            lambda _: (_ for _ in ()).throw(HumanSearchRequired(attempts)),
        )
    controller.submit_human_search_results(
        {"query": "test field", "results": [metadata()]}
    )

    state = complete_landscape_from_metadata(controller)

    assert state["research_lit"]["waiting_for"] == "scope_human_approval"
    assert state["research_lit"]["query_count"] == 1


def test_lower_priority_success_human_followup_passes_final_landscape_audit(
    tmp_path: Path,
) -> None:
    controller = start_controller(tmp_path)
    with pytest.raises(HumanSearchRequired):
        controller.execute_query(
            "test field",
            "research-lit-provider-cascade",
            lambda _: level_three_outcome([metadata()]),
        )
    controller.submit_human_search_results(
        {"query": "test field", "results": []}
    )

    state = complete_landscape_from_metadata(controller)

    assert state["research_lit"]["waiting_for"] == "scope_human_approval"
    assert state["research_lit"]["query_count"] == 1


def test_all_provider_failures_request_the_entire_planned_query_batch(
    tmp_path: Path,
) -> None:
    controller = start_controller(tmp_path, queries=["test field", "related field"])
    with pytest.raises(HumanSearchRequired):
        controller.execute_query(
            "test field",
            "research-lit-provider-cascade",
            lambda _: (_ for _ in ()).throw(
                HumanSearchRequired(
                    [{"provider": "serpapi_google_scholar", "status": "unavailable", "reason": "network"}],
                    query_options={"year_from": 2020, "year_to": 2025, "exact_title": False},
                )
            ),
        )
    research = controller.status()["research_lit"]
    assert research["current_stage"] == "HUMAN_SEARCH_REQUIRED"
    assert [item["query"] for item in research["human_search_request"]["queries"]] == [
        "test field",
        "related field",
    ]
    assert research["human_search_request"]["queries"][0]["constraints"]["year_from"] == 2020
    rows = controller.submit_human_search_results(
        {
            "queries": [
                {"query": "test field", "results": [metadata("P1")]},
                {"query": "related field", "results": []},
            ]
        }
    )
    assert [row["paper_id"] for row in rows] == ["P1"]
    assert controller.current_stage() == "METADATA_RETRIEVAL"
    research = controller.status()["research_lit"]
    assert research["query_count"] == 2
    assert set(research["query_events"]) == {"Q0001", "Q0002"}
    assert all(
        event["status"] == "complete_human"
        for event in research["query_events"].values()
    )


def test_added_provider_credential_resumes_pending_query_without_state_edit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("SERPAPI_KEY", raising=False)
    controller = start_controller(tmp_path)
    attempts = [
        {
            "provider": "serpapi_google_scholar",
            "status": "unavailable",
            "reason": "SERPAPI_KEY is missing",
        },
        {
            "provider": "scholar_google_hk",
            "status": "unavailable",
            "reason": "browser unavailable",
        },
    ]
    with pytest.raises(HumanSearchRequired):
        controller.execute_query(
            "test field",
            "research-lit-provider-cascade",
            lambda _: (_ for _ in ()).throw(HumanSearchRequired(attempts)),
        )
    with pytest.raises(ControllerError, match="SERPAPI_KEY is still missing"):
        controller.submit_human_search_results(
            {
                "query": "test field",
                "retry_provider": "serpapi_google_scholar",
            }
        )
    assert controller.current_stage() == "HUMAN_SEARCH_REQUIRED"

    monkeypatch.setenv("SERPAPI_KEY", "test-secret")
    recovery = controller.submit_human_search_results(
        {
            "query": "test field",
            "retry_provider": "serpapi_google_scholar",
        }
    )
    assert recovery["status"] == "PROVIDER_REENABLED"
    research = controller.status()["research_lit"]
    assert research["current_stage"] == "METADATA_RETRIEVAL"
    assert research["query_count"] == 1
    assert research["planned_queries"][0]["status"] == "planned"
    assert "unavailable_providers" not in research

    controller.execute_query("test field", "fake-recovered-provider", lambda _: [metadata()])
    recovered = controller.status()["research_lit"]
    assert recovered["query_count"] == 1
    assert set(recovered["query_events"]) == {"Q0001"}
    ledger = (tmp_path / "idea-stage" / "SEARCH_LEDGER.jsonl").read_text(
        encoding="utf-8"
    )
    assert '"action": "provider_reenabled"' in ledger
    assert "test-secret" not in ledger
    state = complete_landscape_from_metadata(controller)
    assert state["research_lit"]["waiting_for"] == "scope_human_approval"


def test_unadmitted_fulltext_is_rejected_before_reader(tmp_path: Path) -> None:
    controller = start_controller(tmp_path)
    controller.execute_query("test field", "fake", lambda _: [metadata(venue="Ordinary")])
    assert controller.decide_admission(
        "P1",
        screening_in_scope=True,
        screening_basis="TITLE_ABSTRACT",
        screening_reason="the paper is in scope but does not satisfy the source policy",
        reading_priority="RECENT_ELITE_FRONTIER",
        fulltext_selected=False,
        fulltext_selection_reason="retain metadata for coverage but do not schedule an ineligible full-text read",
    ) == "ADMIT_DISCOVERY_ONLY"
    assert controller.current_stage() == "METADATA_RETRIEVAL"
    state = controller.finish_retrieval()
    assert state["research_lit"]["current_stage"] == "HUMAN_SEARCH_REQUIRED"
    assert state["research_lit"]["human_search_request"]["kind"] == "metadata_search_batch"


def test_decisive_low_citation_source_requires_and_records_bounded_exception(
    tmp_path: Path,
) -> None:
    controller = start_controller(tmp_path)
    controller.execute_query(
        "test field", "fake", lambda _: [metadata(venue="Ordinary")]
    )
    with pytest.raises(ControllerError, match="scientific reason"):
        controller.decide_admission(
            "P1",
            screening_in_scope=True,
            decision_grade_exception="decisive_closest_prior_or_concurrent",
        )

    decision = controller.decide_admission(
        "P1",
        screening_in_scope=True,
        decision_grade_exception="decisive_closest_prior_or_concurrent",
        exception_reason=(
            "Identity-verified concurrent work may already implement the nearest "
            "mechanism and can change the unresolvedness judgment."
        ),
        decision_targets=["problem_novelty:P-1", "coverage:recent_prior_work"],
    )

    assert decision == "ADMIT_FOR_READING"
    context_decision = latest_paper_decision(controller, "P1")
    assert context_decision["admission_exception"]["kind"] == "decisive_closest_prior_or_concurrent"
    assert context_decision["admission_exception"]["decision_targets"] == [
        "coverage:recent_prior_work",
        "problem_novelty:P-1",
    ]
    ledger = (tmp_path / "idea-stage" / "SEARCH_LEDGER.jsonl").read_text(
        encoding="utf-8"
    )
    assert '"admission_exception"' in ledger


def test_rmc_bound_exception_closes_cli_policy_and_current_read_execution_path(
    tmp_path: Path,
) -> None:
    controller = controller_at_method_design(tmp_path)
    context = activate_method_design_admission_context(controller, "P-METHOD")
    decision = controller.decide_admission(
        "P-METHOD",
        screening_in_scope=True,
        screening_basis="TITLE_ABSTRACT",
        screening_reason="The paper may establish the RMC-bound source mechanism genealogy.",
        reading_priority="TARGETED_GAP_FOLLOWUP",
        decision_grade_exception="rmc_bound_source_mechanism_or_genealogy",
        exception_reason="The identity-verified source may change the RMC-1 transfer decision.",
        decision_targets=["source:RMC-1"],
    )
    assert decision == "ADMIT_FOR_READING"
    recorded = latest_paper_decision(controller, "P-METHOD")
    assert recorded["context"] == {
        **context,
        "paper_id": "P-METHOD",
        "decision_targets": ["source:RMC-1"],
    }
    assert recorded["admission_exception"]["kind"] == (
        "rmc_bound_source_mechanism_or_genealogy"
    )
    assert controller._paper_readable_in_active_session(
        controller.status()["research_lit"], "P-METHOD"
    )

    parsed = build_parser().parse_args([
        "admit",
        controller.run_id,
        "P-METHOD",
        "--screening-basis",
        "TITLE_ABSTRACT",
        "--screening-reason",
        "source mechanism",
        "--reading-priority",
        "TARGETED_GAP_FOLLOWUP",
        "--decision-grade-exception",
        "rmc_bound_source_mechanism_or_genealogy",
    ])
    assert parsed.decision_grade_exception == "rmc_bound_source_mechanism_or_genealogy"


def test_context_bound_admissions_keep_landscape_and_rmc_decisions_distinct_and_reject_stale_plan(
    tmp_path: Path,
) -> None:
    controller = controller_at_method_design(tmp_path)
    landscape_decision = {
        "decision_id": "admission-landscape-out",
        "context": {
            "paper_id": "P-CONTEXT",
            "phase": "landscape",
            "query_plan_sha256": "f" * 64,
            "phase_binding_anchor": {"query_plan_sha256": "f" * 64},
            "decision_targets": [],
        },
        "admission_status": "EXCLUDE_IRRELEVANT",
        "screening_status": "OUT_OF_SCOPE",
        "screening_in_scope": False,
        "duplicate": False,
    }
    context = activate_method_design_admission_context(
        controller,
        "P-CONTEXT",
        prior_decisions=[landscape_decision],
    )
    assert controller.decide_admission(
        "P-CONTEXT",
        screening_in_scope=True,
        screening_basis="TITLE_ABSTRACT",
        screening_reason="In scope for the RMC-bound source mechanism.",
        reading_priority="TARGETED_GAP_FOLLOWUP",
        decision_grade_exception="rmc_bound_source_mechanism_or_genealogy",
        exception_reason="May change the RMC-1 mechanism-origin decision.",
        decision_targets=["source:RMC-1"],
    ) == "ADMIT_FOR_READING"
    paper = controller.status()["research_lit"]["papers"]["P-CONTEXT"]
    assert [item["screening_status"] for item in paper["context_decisions"]] == [
        "OUT_OF_SCOPE",
        "IN_SCOPE",
    ]

    rmc_one = deepcopy(paper["context_decisions"][-1])
    rmc_one["decision_id"] = "admission-rmc-one"
    rmc_one["context"]["decision_targets"] = ["source:RMC-1"]
    rmc_two = deepcopy(rmc_one)
    rmc_two["decision_id"] = "admission-rmc-two"
    rmc_two["context"]["decision_targets"] = ["source:RMC-2"]
    paper["context_decisions"].extend([rmc_one, rmc_two])
    assert controller._paper_context_decision(
        paper, context={**context, "decision_targets": ["source:RMC-1"]}
    )["decision_id"] == "admission-rmc-one"
    assert controller._paper_context_decision(
        paper, context={**context, "decision_targets": ["source:RMC-2"]}
    )["decision_id"] == "admission-rmc-two"

    with controller._store.mutate() as state:
        active = state["research_lit"]["incremental_literature_active"]
        active["paper_decision_ids"]["P-CONTEXT"] = paper["context_decisions"][1][
            "decision_id"
        ]
        active["decision_context"] = {
            **active["decision_context"],
            "query_plan_sha256": "0" * 64,
        }
    assert not controller._paper_readable_in_active_session(
        controller.status()["research_lit"], "P-CONTEXT"
    )


def test_unadmitted_fulltext_never_calls_gateway_when_other_paper_allows_reading(
    tmp_path: Path,
) -> None:
    controller = start_controller(tmp_path)
    reach_reading(controller)
    with controller._store.mutate() as state:
        state["research_lit"]["papers"]["P2"] = metadata(
            paper_id="P2", venue="Ordinary"
        )
    called = False

    def forbidden_gateway(_: dict) -> str:
        nonlocal called
        called = True
        return "must not run"

    with pytest.raises(ControllerError, match="denied before tool call"):
        controller.read_full_text("P2", "network", forbidden_gateway)
    assert called is False


def test_evidence_requires_completed_fulltext_event(tmp_path: Path) -> None:
    controller = start_controller(tmp_path)
    reach_reading(controller)
    fake = card({"read_event_id": "fake", "content_sha256": "0" * 64})
    with pytest.raises(ControllerError, match="completed full-text gateway event"):
        controller.submit_evidence_card("P1", fake)
    assert controller.current_stage() == "PAPER_READING"


def test_real_read_receipt_allows_evidence_and_promotes_decision_grade(tmp_path: Path) -> None:
    controller = start_controller(tmp_path)
    reach_reading(controller)
    read = controller.read_full_text("P1", "fake-paper", lambda _: "full paper")
    evidence = card(read)
    attest(controller, "paper_reader", evidence)
    controller.submit_evidence_card("P1", evidence)
    state = controller.status()["research_lit"]
    assert latest_paper_decision(controller, "P1")["admission_status"] == "ADMIT_DECISION_GRADE"
    assert state["accepted_artifacts"]["evidence:P1"]["read_event_id"] == read["read_event_id"]


def test_accepted_evidence_can_be_rescreened_without_duplicate_read(tmp_path: Path) -> None:
    controller = start_controller(tmp_path)
    reach_reading(controller)
    read = controller.read_full_text("P1", "fake-paper", lambda _: "full paper")
    evidence = card(read)
    attest(controller, "paper_reader", evidence)
    controller.submit_evidence_card("P1", evidence)
    with controller._store.mutate() as state:
        state["research_lit"]["current_stage"] = "METADATA_RETRIEVAL"

    verifier_called = False

    def forbidden_verifier(_: dict) -> dict:
        nonlocal verifier_called
        verifier_called = True
        raise AssertionError("accepted full-text evidence must not require abstract enrichment")

    assert controller.decide_admission(
        "P1",
        screening_in_scope=True,
        screening_basis="FULL_TEXT",
        screening_reason="accepted Evidence remains directly relevant to the revised scope",
        reading_priority="HIGH_CITATION_BACKBONE",
        fulltext_selected=True,
        identity_verifier=forbidden_verifier,
    ) == "ADMIT_DECISION_GRADE"
    assert verifier_called is False
    assert latest_paper_decision(controller, "P1")["screening_basis"] == "FULL_TEXT"


def test_revised_scope_can_exclude_a_paper_with_old_accepted_evidence(tmp_path: Path) -> None:
    controller = start_controller(tmp_path)
    reach_reading(controller)
    read = controller.read_full_text("P1", "fake-paper", lambda _: "full paper")
    evidence = card(read)
    attest(controller, "paper_reader", evidence)
    controller.submit_evidence_card("P1", evidence)
    with controller._store.mutate() as state:
        state["research_lit"]["current_stage"] = "METADATA_RETRIEVAL"

    assert controller.decide_admission(
        "P1",
        screening_in_scope=False,
        screening_basis="FULL_TEXT",
        screening_reason="the revised brief excludes this peripheral branch",
        reading_priority="RECENT_ELITE_FRONTIER",
        fulltext_selected=False,
    ) == "EXCLUDE_IRRELEVANT"
    with controller._store.mutate() as state:
        restored = controller._reconcile_accepted_evidence_papers(state["research_lit"])
    assert restored == []
    assert latest_paper_decision(controller, "P1")["admission_status"] == (
        "EXCLUDE_IRRELEVANT"
    )


def test_research_lit_ids_are_unique_and_cross_references_resolve(tmp_path: Path) -> None:
    blank_id_card = card({"read_event_id": "read", "content_sha256": "a" * 64})
    blank_id_card["source_id"] = " "
    with pytest.raises(ValidationError, match="non-empty evidence identifier"):
        validate_evidence_card(blank_id_card, " ")
    with pytest.raises(ValidationError, match="unique among accepted"):
        validate_evidence_card(card({"read_event_id": "read", "content_sha256": "a" * 64}), "P1", existing_evidence_ids={"P1"})

    controller = start_controller(tmp_path)
    reach_synthesis(controller)

    duplicate_method = field_map("PARTIAL")
    duplicate_method["method_families"].append({"id": "M", "mechanism": "other"})
    with pytest.raises(ControllerError, match="method_families.id values must be unique"):
        controller.submit_field_map(duplicate_method)

    dangling_method = field_map("PARTIAL")
    dangling_method["problem_method_matrix"][0]["method"] = "missing"
    with pytest.raises(ControllerError, match="problem_method_matrix row 1.method does not resolve"):
        controller.submit_field_map(dangling_method)

    dangling_evidence = field_map("PARTIAL")
    dangling_evidence["family_development_traces"][0]["evidence_ids"] = ["missing"]
    with pytest.raises(ControllerError, match="unresolved evidence IDs"):
        controller.submit_field_map(dangling_evidence)

    assert controller.submit_field_map(field_map("PARTIAL"))["research_lit"]["current_stage"] == "QUERY_PLANNING"


def test_field_map_requires_complete_declared_traces_but_not_a_fixed_history() -> None:
    classification_only = field_map()
    classification_only["family_development_traces"] = [
        {"family": "M", "evidence_ids": ["P1"]}
    ]
    with pytest.raises(ValidationError, match="missing required fields"):
        validate_field_map(classification_only, evidence_ids={"P1"})

    no_material_transition = field_map()
    no_material_transition["family_development_traces"] = []
    assert validate_field_map(no_material_transition, evidence_ids={"P1"}) is no_material_transition

    parallel = field_map()
    parallel["family_development_traces"].append(
        development_trace("T2", family=None)
    )
    validated = validate_field_map(parallel, evidence_ids={"P1"})
    assert len(validated["family_development_traces"]) == 2
    assert all("year" not in trace and "stage" not in trace for trace in validated["family_development_traces"])

    duplicate_transition = field_map()
    duplicate_transition["family_development_traces"].append(development_trace("T1"))
    with pytest.raises(ValidationError, match="transition_id values must be unique"):
        validate_field_map(duplicate_transition, evidence_ids={"P1"})

    invalid_status = field_map()
    invalid_status["family_development_traces"][0]["transition_problem_status"] = "complete"
    with pytest.raises(ValidationError, match="transition_problem_status is invalid"):
        validate_field_map(invalid_status, evidence_ids={"P1"})


def test_coverage_review_enforces_evolution_assessment_without_forcing_traces() -> None:
    empty_trace_review = coverage_review(
        "a" * 64,
        "request",
        development_trace_count=0,
    )
    assert validate_coverage_review(
        empty_trace_review,
        development_trace_count=0,
    ) is empty_trace_review

    wrong_empty_basis = json.loads(json.dumps(empty_trace_review))
    wrong_empty_basis["evolution_assessment"]["transition_causality"]["basis"] = (
        "DECLARED_TRACES_REVIEWED"
    )
    with pytest.raises(ValidationError, match="NO_MATERIAL_TRANSITION_SUPPORTED"):
        validate_coverage_review(wrong_empty_basis, development_trace_count=0)

    wrong_nonempty_basis = coverage_review(
        "a" * 64,
        "request",
        development_trace_count=1,
    )
    wrong_nonempty_basis["evolution_assessment"]["transition_causality"]["basis"] = (
        "NO_MATERIAL_TRANSITION_SUPPORTED"
    )
    with pytest.raises(ValidationError, match="DECLARED_TRACES_REVIEWED"):
        validate_coverage_review(wrong_nonempty_basis, development_trace_count=1)

    coherence_gap = coverage_review("a" * 64, "request", development_trace_count=1)
    coherence_gap["evolution_assessment"]["explanatory_coherence"] = {
        "status": "GAP",
        "rationale": "The frontier is not connected to the recovered history.",
    }
    gap = "The current frontier is not connected to the recovered history."
    coherence_gap["evolution_assessment"]["material_evolution_gaps"] = [gap]
    coherence_gap["gaps"] = [gap]
    with pytest.raises(ValidationError, match="requires CONTINUE"):
        validate_coverage_review(coherence_gap, development_trace_count=1)

    coherence_gap["decision"] = "CONTINUE"
    assert validate_coverage_review(coherence_gap, development_trace_count=1) is coherence_gap

    unforwarded_gap = json.loads(json.dumps(coherence_gap))
    unforwarded_gap["gaps"] = ["A different top-level gap."]
    with pytest.raises(ValidationError, match="appear verbatim"):
        validate_coverage_review(unforwarded_gap, development_trace_count=1)

    missing_material_gap = coverage_review(
        "a" * 64,
        "request",
        decision="CONTINUE",
        development_trace_count=1,
    )
    missing_material_gap["gaps"] = ["A non-evolution evidence boundary remains open."]
    missing_material_gap["evolution_assessment"]["foundation_to_frontier"]["status"] = "GAP"
    with pytest.raises(ValidationError, match="mutually consistent"):
        validate_coverage_review(missing_material_gap, development_trace_count=1)

    missing_material_gap["evolution_assessment"]["foundation_to_frontier"]["status"] = "PASS"
    missing_material_gap["evolution_assessment"]["material_evolution_gaps"] = [
        "An important foundational node is missing."
    ]
    with pytest.raises(ValidationError, match="mutually consistent"):
        validate_coverage_review(missing_material_gap, development_trace_count=1)

    all_evolution_pass = coverage_review(
        "a" * 64,
        "request",
        decision="CONTINUE",
        development_trace_count=1,
    )
    all_evolution_pass["gaps"] = ["A non-evolution evidence boundary remains open."]
    assert validate_coverage_review(all_evolution_pass, development_trace_count=1) is all_evolution_pass


def test_landscape_audit_rejects_duplicate_evidence_ids_and_dangling_references(
    tmp_path: Path,
) -> None:
    stage = tmp_path / "idea-stage"
    stage.mkdir()
    (stage / "ACTIVE_FIELD_MAP.md").write_text(render_field_map(field_map()), encoding="utf-8")
    evidence = card({"read_event_id": "read", "content_sha256": "a" * 64})
    (stage / "EVIDENCE_REGISTRY.jsonl").write_text(
        json.dumps(evidence) + "\n", encoding="utf-8"
    )
    (stage / "LITERATURE_CORPUS.jsonl").write_text(
        json.dumps({
            "source_id": "P1",
            "context_decisions": [{
                "decision_id": "admission-landscape-p1",
                "context": {
                    "paper_id": "P1",
                    "phase": "landscape",
                    "query_plan_sha256": "a" * 64,
                    "phase_binding_anchor": {"query_plan_sha256": "a" * 64},
                    "decision_targets": [],
                },
                "admission_status": "ADMIT_DECISION_GRADE",
                "screening_status": "IN_SCOPE",
                "screening_reason": "fixture decision-grade source",
            }],
        }) + "\n",
        encoding="utf-8",
    )
    (stage / "SOURCE_ADMISSION_POLICY.yaml").write_text(
        "citation threshold\nelite venues\nuser supplied track\n", encoding="utf-8"
    )
    (stage / "SEARCH_LEDGER.jsonl").write_text(
        json.dumps(
            {
                "timestamp": "now",
                "run_id": "run",
                "stage": "METADATA_RETRIEVAL",
                "action": "query",
                "query_id": "query-1",
                "query": "topic",
                "paper_id": None,
                "tool": "test",
                "result_status": "complete",
                "admission_decision": None,
                "budget_before": 0,
                "budget_after": 1,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    workflow = {
        "artifact_manifest": {
            "active_field_map": "idea-stage/ACTIVE_FIELD_MAP.md",
            "evidence_registry": "idea-stage/EVIDENCE_REGISTRY.jsonl",
            "literature_corpus": "idea-stage/LITERATURE_CORPUS.jsonl",
            "source_admission_policy": "idea-stage/SOURCE_ADMISSION_POLICY.yaml",
            "search_log": "idea-stage/SEARCH_LEDGER.jsonl",
        }
    }

    assert audit_landscape(tmp_path, workflow)["ok"] is True

    dangling = field_map()
    dangling["assumption_effectiveness_failure_matrix"][0]["source_ids"] = ["missing"]
    (stage / "ACTIVE_FIELD_MAP.md").write_text(render_field_map(dangling), encoding="utf-8")
    result = audit_landscape(tmp_path, workflow)
    assert result["ok"] is False
    assert any("unresolved evidence IDs" in error for error in result["errors"])

    (stage / "ACTIVE_FIELD_MAP.md").write_text(render_field_map(field_map()), encoding="utf-8")
    (stage / "EVIDENCE_REGISTRY.jsonl").write_text(
        json.dumps(evidence) + "\n" + json.dumps(evidence) + "\n", encoding="utf-8"
    )
    result = audit_landscape(tmp_path, workflow)
    assert result["ok"] is False
    assert any("duplicates Evidence Card source_id" in error for error in result["errors"])


def test_provider_unavailable_requests_a_fulltext_batch_and_resumes_reading(
    tmp_path: Path,
) -> None:
    controller = start_controller(tmp_path)
    controller.execute_query(
        "test field", "fake", lambda _: [metadata(), metadata(paper_id="P2")]
    )
    for paper_id in ("P1", "P2"):
        assert controller.decide_admission(
            paper_id,
            screening_in_scope=True,
            screening_basis="TITLE_ABSTRACT",
            screening_reason="the source is in scope for the initial cognition pass",
            reading_priority="RECENT_ELITE_FRONTIER",
        ) == "ADMIT_FOR_READING"
    controller.select_reading_subset(
        ["P1", "P2"],
        rationale="the initial cognition pass needs both complementary sources",
        initial=True,
    )
    controller.finish_retrieval()
    read = controller.read_full_text("P1", "fake-paper", lambda _: "full paper")
    evidence = card(read)
    attest(controller, "paper_reader", evidence)
    controller.submit_evidence_card("P1", evidence)

    def unavailable(_: dict) -> str:
        raise ProviderUnavailable("test_fulltext", "no open copy")

    result = controller.read_full_text("P2", "network", unavailable)
    assert result["status"] == "FULLTEXT_PROVIDER_UNAVAILABLE"
    assert controller.current_stage() == "PAPER_READING"
    controller.finish_reading()
    assert controller.allowed_actions() == [
        "submit_human_search_results",
        "submit_human_fulltext_batch",
        "promote_user_source",
        "reverify_admission",
        "withdraw_admission",
    ]
    state = controller.status()["research_lit"]
    assert latest_paper_decision(controller, "P2")["admission_status"] == "ADMIT_FOR_READING"
    assert state["papers"]["P2"]["fulltext_failure"]["read_event_id"]
    assert [item["paper_id"] for item in state["human_fulltext_request"]["papers"]] == ["P2"]
    source = tmp_path / "source-materials" / "p2.txt"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("user supplied full paper", encoding="utf-8")
    controller.submit_human_fulltext_batch(
        {
            "papers": [
                {
                    "paper_id": "P2",
                    "source_path": "source-materials/p2.txt",
                    "media_type": "text/plain",
                }
            ]
        }
    )
    user_read = controller.read_registered_user_fulltext("P2")
    user_evidence = card(user_read, paper_id="P2")
    attest(controller, "paper_reader", user_evidence)
    controller.submit_evidence_card("P2", user_evidence)
    controller.finish_reading()
    assert controller.current_stage() == "FIELD_SYNTHESIS"


def test_fulltext_batch_combines_deferred_non_arxiv_after_arxiv_reads(
    tmp_path: Path,
) -> None:
    controller = start_controller(tmp_path)
    controller.execute_query(
        "test field",
        "fake",
        lambda _: [metadata(), metadata(paper_id="P2"), metadata(paper_id="P3")],
    )
    for paper_id in ("P1", "P2", "P3"):
        assert controller.decide_admission(
            paper_id,
            screening_in_scope=True,
            screening_basis="TITLE_ABSTRACT",
            screening_reason="the source is in scope for the initial cognition pass",
            reading_priority="RECENT_ELITE_FRONTIER",
        ) == "ADMIT_FOR_READING"
    controller.select_reading_subset(
        ["P1", "P2", "P3"],
        rationale="the initial cognition pass needs the complete selected cohort",
        initial=True,
    )
    controller.finish_retrieval()

    p1_read = controller.read_full_text("P1", "arxiv", lambda _: "paper one")
    deferred = controller.defer_fulltext_to_human_batch(
        ["P2", "P3"], reason="non-arXiv admitted papers require user download"
    )
    assert deferred["deferred_paper_ids"] == ["P2", "P3"]
    assert controller.current_stage() == "PAPER_READING"
    assert controller.status()["research_lit"]["human_fulltext_request"] is None

    evidence = card(p1_read, paper_id="P1")
    attest(controller, "paper_reader", evidence)
    controller.submit_evidence_card("P1", evidence)

    state = controller.finish_reading()["research_lit"]
    assert state["current_stage"] == "HUMAN_SEARCH_REQUIRED"
    assert [
        item["paper_id"] for item in state["human_fulltext_request"]["papers"]
    ] == ["P2", "P3"]
    assert state["human_fulltext_request"]["target_directory"] == "source-materials/"


def test_user_can_withdraw_unread_admission_during_paper_reading(tmp_path: Path) -> None:
    controller = start_controller(tmp_path)
    controller.execute_query(
        "test field",
        "fake-search",
        lambda _: [metadata("P1"), metadata("P2")],
    )
    for paper_id in ("P1", "P2"):
        assert controller.decide_admission(
            paper_id,
            screening_in_scope=True,
            screening_basis="TITLE_ABSTRACT",
            screening_reason="the source is in scope for the initial cognition pass",
            reading_priority="RECENT_ELITE_FRONTIER",
        ) == "ADMIT_FOR_READING"
    controller.select_reading_subset(
        ["P1", "P2"],
        rationale="the initial cognition pass needs both selected sources",
        initial=True,
    )
    controller.finish_retrieval()
    read = controller.read_full_text("P1", "fake-paper", lambda _: "full paper")
    evidence = card(read)
    attest(controller, "paper_reader", evidence)
    controller.submit_evidence_card("P1", evidence)

    assert controller.withdraw_admission("P2", reason="user corrected the reading scope") == (
        "EXCLUDE_USER_WITHDRAWN"
    )
    state = controller.finish_reading()["research_lit"]
    assert state["current_stage"] == "FIELD_SYNTHESIS"
    assert latest_paper_decision(controller, "P2")["admission_status"] == "EXCLUDE_USER_WITHDRAWN"
    assert state["papers"]["P2"]["admission_withdrawal"]["reason"] == (
        "user corrected the reading scope"
    )


def test_admission_withdrawal_updates_pending_fulltext_batch_and_protects_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller = start_controller(tmp_path)
    reach_reading(controller)

    def unavailable(_: dict) -> str:
        raise ProviderUnavailable("test_fulltext", "no open copy")

    controller.read_full_text("P1", "network", unavailable)
    controller.finish_reading()
    assert controller.current_stage() == "HUMAN_SEARCH_REQUIRED"
    controller.withdraw_admission("P1", reason="user removed the paper from scope")
    state = controller.status()["research_lit"]
    assert state["current_stage"] == "PAPER_READING"
    assert state["human_fulltext_request"] is None

    accepted_root = tmp_path / "accepted"
    accepted_root.mkdir()
    monkeypatch.chdir(accepted_root)
    controller = start_controller(accepted_root)
    reach_reading(controller)
    read = controller.read_full_text("P1", "fake-paper", lambda _: "full paper")
    evidence = card(read)
    attest(controller, "paper_reader", evidence)
    controller.submit_evidence_card("P1", evidence)
    with pytest.raises(ControllerError, match="accepted Evidence Card"):
        controller.withdraw_admission("P1", reason="too late")


def test_admitted_identity_can_be_corrected_only_before_evidence(tmp_path: Path) -> None:
    controller = start_controller(tmp_path)
    reach_reading(controller)

    correction = controller.reverify_admission(
        "P1",
        reason="duplicate-title verifier selected the conference version",
        identity_verifier=lambda _: {
            "identity_status": "verified",
            "identity_provider": "crossref_metadata",
            "title": "Test paper",
            "authors": ["A. Author"],
            "year": 2025,
            "venue": "Test Elite Venue",
            "doi": "10.1/corrected",
            "doi_or_stable_url": "https://doi.org/10.1/corrected",
            "publication_type": "journal-article",
        },
    )
    assert correction["previous"]["doi_or_stable_url"] == "https://doi.org/10.1/test"
    assert correction["corrected"]["doi"] == "10.1/corrected"
    assert latest_paper_decision(controller, "P1")["admission_status"] == (
        "ADMIT_FOR_READING"
    )

    read = controller.read_full_text("P1", "fake-paper", lambda _: "full paper")
    evidence = card(read)
    attest(controller, "paper_reader", evidence)
    controller.submit_evidence_card("P1", evidence)
    with pytest.raises(ControllerError, match="accepted Evidence Card"):
        controller.reverify_admission(
            "P1",
            reason="too late",
            identity_verifier=lambda paper: paper,
        )


def test_discovered_paper_can_be_promoted_when_user_later_supplies_fulltext(
    tmp_path: Path,
) -> None:
    controller = start_controller(tmp_path)
    controller.execute_query(
        "test field",
        "fake-search",
        lambda _: [metadata("P1"), {**metadata("P2"), "identity_status": "verify_pending"}],
    )
    assert controller.decide_admission(
        "P1",
        screening_in_scope=True,
        screening_basis="TITLE_ABSTRACT",
        screening_reason="the source is in scope for the initial cognition pass",
        reading_priority="RECENT_ELITE_FRONTIER",
    ) == "ADMIT_FOR_READING"
    assert controller.decide_admission(
        "P2",
        screening_in_scope=True,
        screening_basis="TITLE_ABSTRACT",
        screening_reason="the discovered source remains in scope pending identity verification",
        reading_priority="RECENT_ELITE_FRONTIER",
        fulltext_selected=False,
        fulltext_selection_reason="defer full-text selection until the user supplies the identified source",
    ) == "HOLD_IDENTITY"
    controller.select_reading_subset(
        ["P1"],
        rationale="the verified source provides the minimal initial cognition pass",
        initial=True,
    )
    controller.finish_retrieval()
    source = tmp_path / "source-materials" / "p2.pdf"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"user supplied paper")

    promoted = controller.promote_user_source(
        "P2",
        source_path="source-materials/p2.pdf",
        reason="user identified this paper as required high-impact evidence",
        media_type="application/pdf",
        identity_verifier=lambda paper: {
            **paper,
            "identity_status": "verified",
            "identity_provider": "test_verifier",
            "doi": "10.1/promoted",
        },
    )

    assert promoted["context_decisions"][-1]["admission_status"] == "USER_SUPPLIED_READ"
    assert promoted["source_origin"] == "gateway_discovery"
    assert promoted["identity_status"] == "verified"
    assert Path(promoted["user_fulltext"]["source_path"]) == Path("source-materials/p2.pdf")
    controller.select_reading_subset(
        ["P2"],
        rationale="the user-supplied in-scope source now completes the initial cognition pass",
    )
    assert controller.read_registered_user_fulltext("P2")["read_event_id"]
    ledger = (tmp_path / "idea-stage" / "SEARCH_LEDGER.jsonl").read_text(
        encoding="utf-8"
    )
    assert '"action": "user_source_promotion"' in ledger
    assert '"admission_decision": "USER_SUPPLIED_READ"' in ledger


def test_user_source_promotion_keeps_scope_and_evidence_guards(tmp_path: Path) -> None:
    controller = start_controller(tmp_path)
    controller.execute_query("test field", "fake-search", lambda _: [metadata("P1")])
    controller.decide_admission("P1", screening_in_scope=False)
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"paper")
    with pytest.raises(ControllerError, match="inside source-materials"):
        controller.promote_user_source(
            "P1", source_path="outside.pdf", reason="user supplied the paper"
        )


def test_all_unavailable_reads_cannot_create_evidence_free_field_map(tmp_path: Path) -> None:
    controller = start_controller(tmp_path)
    reach_reading(controller)

    def unavailable(_: dict) -> str:
        raise ProviderUnavailable("test_fulltext", "no open copy")

    result = controller.read_full_text("P1", "network", unavailable)
    assert result["status"] == "FULLTEXT_PROVIDER_UNAVAILABLE"
    assert controller.current_stage() == "PAPER_READING"
    controller.finish_reading()
    assert controller.current_stage() == "HUMAN_SEARCH_REQUIRED"
    assert controller.status()["research_lit"]["human_fulltext_request"]["papers"][0]["paper_id"] == "P1"


def test_main_agent_handles_planning_and_routine_synthesis_without_subagent(tmp_path: Path) -> None:
    controller = start_controller(tmp_path)
    reach_synthesis(controller)
    state = controller.submit_field_map(field_map("PARTIAL"))
    assert state["research_lit"]["current_stage"] == "QUERY_PLANNING"
    assert state["research_lit"]["coverage_review_request"] is None
    assert controller.allowed_agents() == ["main_research_agent"]


def test_reviewer_runs_only_with_controller_request_and_exact_hash(tmp_path: Path) -> None:
    controller = start_controller(tmp_path)
    digest, request_id = reach_coverage(controller)
    with pytest.raises(ControllerError, match="stale or unknown"):
        controller.submit_coverage_review(coverage_review(digest, "forged"))
    with pytest.raises(ControllerError, match="does not match"):
        controller.submit_coverage_review(coverage_review("0" * 64, request_id))
    with pytest.raises(ControllerError, match="no externally attested reviewer result"):
        controller.submit_coverage_review(coverage_review(digest, request_id))
    assert controller.current_stage() == "COVERAGE_REVIEW"


def test_formal_gate_rejects_workspace_forgery_and_input_hash_drift(tmp_path: Path) -> None:
    controller = start_controller(tmp_path)
    digest, request_id = reach_coverage(controller)
    review = coverage_review(digest, request_id)
    attest(controller, "coverage_reviewer", review)
    controller.submit_coverage_review(review)
    approve(controller, "scope_human_approval")

    controller.start_current_phase()
    candidate = tmp_path / "idea-stage" / "PROBLEM_CANDIDATES.md"
    candidate.write_text("# Problems\nP-1", encoding="utf-8")
    (tmp_path / "idea-stage" / "PROBLEM_CANDIDATES.jsonl").write_text(
        problem_candidate(), encoding="utf-8"
    )
    controller.complete_current_phase()
    controller.start_current_phase()
    verdict_path = tmp_path / "idea-stage" / "PROBLEM_QUALITY_VERDICTS.jsonl"
    request = run_state._find_phase(
        controller.status(), "problem_quality_gate"
    )["review_request"]
    valid_verdict = formal_verdict_artifact(controller, verdict_id="forged-verdict")
    verdict_path.write_text(
        valid_verdict.replace(request["id"], "wrong-request-id"), encoding="utf-8"
    )
    with pytest.raises(ControllerError, match="review_request_id"):
        controller.complete_current_phase()
    reviewed_hash = next(iter(request["artifact_bindings"].values()))
    verdict_path.write_text(
        valid_verdict.replace(reviewed_hash, "0" * 64), encoding="utf-8"
    )
    with pytest.raises(ControllerError, match="reviewed_artifact_hashes"):
        controller.complete_current_phase()
    verdict_path.write_text(valid_verdict, encoding="utf-8")
    controller.complete_current_phase()
    verdict_path.write_text(
        formal_verdict_artifact(
            controller, verdict_id="forged-verdict", reviewer="gemini-2.5-pro"
        ),
        encoding="utf-8",
    )
    with pytest.raises(ControllerError, match="acceptance provenance"):
        controller.accept_current_phase("forged-verdict", "claude-sonnet-4")
    verdict_path.write_text(valid_verdict, encoding="utf-8")
    forged = (
        tmp_path / ".aris" / "agent-attestations" / "independent_problem_reviewer"
        / f"{request['id']}.json"
    )
    forged.parent.mkdir(parents=True, exist_ok=True)
    forged.write_text('{"agent_id":"forged"}', encoding="utf-8")
    with pytest.raises(ControllerError, match="no externally attested reviewer result"):
        controller.accept_current_phase("forged-verdict", "claude-sonnet-4")

    candidate.write_text("# Problems\nP-1 tampered", encoding="utf-8")
    with pytest.raises(ControllerError, match="changed after acceptance"):
        controller.accept_current_phase("forged-verdict", "claude-sonnet-4")


def test_happy_path_reaches_and_passes_real_scope_human_gate(tmp_path: Path) -> None:
    controller = start_controller(tmp_path)
    digest, request_id = reach_coverage(controller)
    review = coverage_review(digest, request_id)
    attest(controller, "coverage_reviewer", review)
    state = controller.submit_coverage_review(review)
    assert state["research_lit"]["waiting_for"] == "scope_human_approval"
    with pytest.raises(ControllerError, match="no Codex UI approval receipt"):
        controller.human_approve("scope_human_approval", "approve")
    final = approve(controller, "scope_human_approval")
    assert final["research_lit"]["current_stage"] == "LANDSCAPE_ACCEPTED"
    assert run_state._find_phase(final, "scope_human_approval")["status"] == "human_accepted"
    assert controller.current_stage() == "PROBLEM_GENERATION"
    assert controller.allowed_actions() == ["start_phase"]
    handoff = final["scientific_core"]["landscape_handoff"]
    assert handoff["scope_approval"]["request_id"]
    assert handoff["artifacts"]["idea-stage/ACTIVE_FIELD_MAP.md"]["sha256"]


def test_running_problem_lead_queries_preserve_context_and_query_plan_history(
    tmp_path: Path,
) -> None:
    controller = start_controller(tmp_path)
    digest, request_id = reach_coverage(controller)
    review = coverage_review(digest, request_id)
    attest(controller, "coverage_reviewer", review)
    controller.submit_coverage_review(review)
    approve(controller, "scope_human_approval")

    field_map_sha256 = controller.status()["research_lit"]["accepted_artifacts"][
        "active_field_map"
    ]["sha256"]

    def lead_plan(*, statement: str, dimension: str = "Unresolvedness") -> dict:
        return {
            "coverage_gaps": [],
            "queries": [{
                "query": "calibration failure closest prior",
                "purpose": "test the closest prior residual delta",
                "expected_close_condition": "identify whether the stated scope remains unresolved",
                "lead_id": "lead-calibration-boundary",
                "lead_statement": statement,
                "active_field_map_sha256": field_map_sha256,
                "decision_dimension": dimension,
            }],
        }

    # Pending problem generation cannot initiate an incremental literature pass.
    with pytest.raises(ControllerError, match="incremental literature is allowed"):
        controller.submit_query_plan(lead_plan(statement="Calibration fails under shift."))
    assert controller.allowed_actions() == ["start_phase"]

    controller.start_current_phase()
    with pytest.raises(ControllerError, match="decision_dimension"):
        controller.submit_query_plan(
            lead_plan(statement="Calibration fails under shift.", dimension="Novelty")
        )
    first_plan = lead_plan(statement="Calibration fails under shift.")
    controller.submit_query_plan(first_plan)
    first_path = tmp_path / ".aris" / "canonical" / "run-1" / "incremental-query-plan-problem_generation.json"
    first_bytes = first_path.read_bytes()
    controller.execute_query("calibration failure closest prior", "fake", lambda _: [metadata("P2")])
    automatic = controller.status()["research_lit"]["query_events"]["Q0002"]
    expected_context = {
        "phase": "problem_generation",
        "query_plan_sha256": sha256_file(first_path),
        "lead_id": "lead-calibration-boundary",
        "lead_statement": "Calibration fails under shift.",
        "active_field_map_sha256": field_map_sha256,
        "decision_dimension": "Unresolvedness",
        "purpose": "test the closest prior residual delta",
        "expected_close_condition": "identify whether the stated scope remains unresolved",
    }
    assert automatic["query_context"] == expected_context
    assert automatic["query_plan_sha256"] == expected_context["query_plan_sha256"]

    # No mature Candidate was produced: the Lead may simply be rejected and
    # the running phase can continue its ordinary cognition loop.
    controller.decide_admission(
        "P2",
        screening_in_scope=True,
        screening_basis="TITLE_ABSTRACT",
        screening_reason="the Lead requires a direct closest-prior check",
        reading_priority="RECENT_ELITE_FRONTIER",
    )
    controller.finish_retrieval()
    evidence = card(controller.read_full_text("P2", "fake-paper", lambda _: "full paper"), "P2")
    controller.submit_evidence_card("P2", evidence)
    accepted_card = json.loads(
        (tmp_path / ".aris" / "canonical" / "run-1" / "evidence-P2.json").read_text(encoding="utf-8")
    )
    assert accepted_card["problem_lead_search_contexts"] == [expected_context]
    controller.finish_reading()
    assert controller.current_stage() == "PROBLEM_GENERATION"
    assert not (tmp_path / "idea-stage" / "PROBLEM_CANDIDATES.jsonl").exists()

    # Narrow/reframe uses the same running derivation.  The old accepted bytes
    # survive because the first plan was formally referenced by Q0002.
    controller.submit_query_plan(lead_plan(statement="Calibration fails only under covariate shift."))
    history = controller.status()["research_lit"]["query_plan_history"]
    assert history[-1]["sha256"] == expected_context["query_plan_sha256"]
    archive = tmp_path / history[-1]["archive_path"]
    assert archive.read_bytes() == first_bytes
    assert "evidence:P2" in controller.status()["research_lit"]["incremental_evidence_by_phase"]["problem_generation"]

    with pytest.raises(HumanSearchRequired) as required:
        controller.execute_query(
            "calibration failure closest prior",
            "fake",
            lambda _: (_ for _ in ()).throw(HumanSearchRequired([])),
        )
    human_query = required.value.request["queries"][0]
    assert human_query["query_context"]["lead_statement"] == "Calibration fails only under covariate shift."
    controller.submit_human_search_results(
        {"queries": [{"query_id": human_query["query_id"], "results": []}]}
    )
    human_event = controller.status()["research_lit"]["query_events"][human_query["query_id"]]
    assert human_event["query_context"] == human_query["query_context"]
    assert controller.status()["scientific_core"]["current_phase"] == "problem_generation"


def test_incremental_reading_deferred_fulltext_enters_human_batch(
    tmp_path: Path,
) -> None:
    controller = start_controller(tmp_path)
    digest, request_id = reach_coverage(controller)
    review = coverage_review(digest, request_id)
    attest(controller, "coverage_reviewer", review)
    controller.submit_coverage_review(review)
    approve(controller, "scope_human_approval")
    controller.start_current_phase()

    field_map_sha256 = controller.status()["research_lit"]["accepted_artifacts"][
        "active_field_map"
    ]["sha256"]
    controller.submit_query_plan({
        "coverage_gaps": [],
        "queries": [{
            "query": "calibration failure closest prior",
            "purpose": "test the closest prior residual delta",
            "expected_close_condition": "identify whether the stated scope remains unresolved",
            "lead_id": "lead-calibration-boundary",
            "lead_statement": "Calibration fails under shift.",
            "active_field_map_sha256": field_map_sha256,
            "decision_dimension": "Unresolvedness",
        }],
    })
    controller.execute_query(
        "calibration failure closest prior", "fake", lambda _: [metadata("P2")]
    )
    controller.decide_admission(
        "P2",
        screening_in_scope=True,
        screening_basis="TITLE_ABSTRACT",
        screening_reason="the Lead requires a direct closest-prior check",
        reading_priority="RECENT_ELITE_FRONTIER",
    )
    controller.finish_retrieval()
    controller.defer_fulltext_to_human_batch(
        ["P2"], reason="non-arXiv admitted paper requires user download"
    )

    state = controller.finish_reading()["research_lit"]

    assert state["current_stage"] == "HUMAN_SEARCH_REQUIRED"
    assert state["incremental_literature_active"]["phase"] == "problem_generation"
    assert [
        item["paper_id"] for item in state["human_fulltext_request"]["papers"]
    ] == ["P2"]
    assert state["human_fulltext_request"]["target_directory"] == "source-materials/"


def test_query_plan_history_boundary_is_phase_agnostic(tmp_path: Path) -> None:
    """The one history boundary also preserves another incremental phase's plan."""

    controller = start_controller(tmp_path)
    plan_path = tmp_path / ".aris" / "canonical" / "run-1" / "incremental-query-plan-root_cause_analysis.json"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text('{"queries":["diagnostic gap"]}\n', encoding="utf-8")
    plan_sha256 = sha256_file(plan_path)
    with controller._store.mutate() as state:
        research = state["research_lit"]
        research["accepted_artifacts"]["incremental-query-plan-root_cause_analysis"] = {
            "path": str(plan_path.relative_to(tmp_path)),
            "validator_result": "PASS",
            "sha256": plan_sha256,
            "accepted_at": "2026-08-20T00:00:00Z",
        }
        research["query_events"]["Q9999"] = {"query_plan_sha256": plan_sha256}
        controller._archive_accepted_query_plan_if_referenced(
            research, "incremental-query-plan-root_cause_analysis"
        )
        history = research["query_plan_history"]
    archive = tmp_path / history[-1]["archive_path"]
    assert archive.read_bytes() == plan_path.read_bytes()


def test_explicit_problem_revision_creates_a_draft_version_and_requires_reacceptance(
    tmp_path: Path,
) -> None:
    controller = start_controller(tmp_path)
    digest, request_id = reach_coverage(controller)
    review = coverage_review(digest, request_id)
    attest(controller, "coverage_reviewer", review)
    controller.submit_coverage_review(review)
    approve(controller, "scope_human_approval")

    def write(relative: str, content: str) -> None:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def execute(files: dict[str, str]) -> None:
        controller.start_current_phase()
        for relative, content in files.items():
            write(relative, content() if callable(content) else content)
        controller.complete_current_phase()

    execute({
        "idea-stage/PROBLEM_CANDIDATES.md": "# Problems\nP-1",
        "idea-stage/PROBLEM_CANDIDATES.jsonl": problem_candidate(),
    })
    execute({"idea-stage/PROBLEM_QUALITY_VERDICTS.jsonl": lambda: formal_verdict_artifact(controller, verdict_id="quality-v1")})
    accept_formal(controller, "quality-v1", "claude-sonnet-4")
    execute({"idea-stage/PROBLEM_NOVELTY_VERDICTS.jsonl": lambda: formal_verdict_artifact(controller, verdict_id="novelty-v1")})
    accept_formal(controller, "novelty-v1", "claude-sonnet-4")
    write_problem_handoffs(controller)
    approve(controller, "problem_acceptance", selected_id="P-1")
    assert controller.status()["scientific_core"]["active_problem_version"]["version"] == 1

    with pytest.raises(ControllerError, match="no Codex UI approval receipt"):
        controller.revise_problem("New evidence narrows the accepted phenomenon boundary.")
    revised = revise_problem(
        controller, "New evidence narrows the accepted phenomenon boundary."
    )
    core = revised["scientific_core"]
    assert controller.current_stage() == "PROBLEM_GENERATION"
    assert core["active_problem_version"] is None
    pending = core["pending_problem_revision"]
    assert pending["problem_id"] == "P-1"
    assert pending["version"] == 2 and pending["parent_version"] == 1
    assert pending["status"] == "draft"
    assert pending["reason"] == "New evidence narrows the accepted phenomenon boundary."
    assert pending["source"] == "explicit_user_revision"
    assert pending["allow_problem_replacement"] is False
    assert core["problem_versions"][-1]["status"] == "superseded"
    assert core["approvals"][-1]["gate"] == "problem_revision"
    assert core["approvals"][-1]["decision"] == "approve"

    execute({
        "idea-stage/PROBLEM_CANDIDATES.md": "# Problems\nP-1 revised",
        "idea-stage/PROBLEM_CANDIDATES.jsonl": problem_candidate(),
    })
    execute({"idea-stage/PROBLEM_QUALITY_VERDICTS.jsonl": lambda: formal_verdict_artifact(controller, verdict_id="quality-v2")})
    accept_formal(controller, "quality-v2", "claude-sonnet-4")
    execute({"idea-stage/PROBLEM_NOVELTY_VERDICTS.jsonl": lambda: formal_verdict_artifact(controller, verdict_id="novelty-v2")})
    accept_formal(controller, "novelty-v2", "claude-sonnet-4")
    write_problem_handoffs(controller)
    assert controller.current_stage() == "PROBLEM_HUMAN_ACCEPTANCE"
    with pytest.raises(ControllerError, match="human checkpoint"):
        controller.start_current_phase()
    assert controller.status()["scientific_core"]["active_problem_version"] is None
    approve(controller, "problem_acceptance", selected_id="P-1")
    active = controller.status()["scientific_core"]["active_problem_version"]
    assert active["problem_id"] == "P-1" and active["version"] == 2


def test_method_design_completion_registers_validated_snapshot_for_human_gate(
    tmp_path: Path,
) -> None:
    controller = controller_at_method_design(tmp_path)
    write_and_complete_method_design(controller)
    phase = run_state._find_phase(controller.status(), "method_design")
    assert phase["validated_artifacts"] == {
        raw_path: sha256_file(tmp_path / raw_path)
        for raw_path in (
            "idea-stage/METHOD_DESIGN_PACKET.json",
            "idea-stage/METHOD_DESIGN.md",
            "idea-stage/METHOD_DESIGN_REVIEW.json",
        )
    }
    controller.accept_current_phase("method-review-1", "claude-sonnet-4")
    assert controller.current_stage() == "PRINCIPLE_HUMAN_SELECTION"
    assert controller.status()["scientific_core"]["method_test_cycle"] is None
    assert not (tmp_path / "idea-stage" / "SELECTED_PRINCIPLE.yaml").exists()


def test_human_candidate_selection_binds_one_version_without_test_cycle_or_convergence(
    tmp_path: Path,
) -> None:
    controller = controller_at_method_design(tmp_path)
    write_and_complete_method_design(controller)
    accept_current_scientific_gate_from_validated_prefix_fixture(
        controller, verdict_id="method-review-1"
    )
    with pytest.raises(ControllerError, match="resolve exactly one"):
        controller.validate_human_gate_decision(
            "principle_selection", "select", selected_id="PR-MISSING@1"
        )
    selected = select_candidate_for_testing(controller)
    binding = selected["scientific_core"]["selected_for_testing"]
    assert binding["binding_type"] == "selected_for_testing"
    assert (binding["principle_id"], binding["principle_version"]) == ("PR-A", "1")
    assert selected["scientific_core"]["current_phase"] == "principle_test_design"
    assert selected["scientific_core"]["method_test_cycle"] is None
    assert not (tmp_path / "idea-stage" / "SELECTED_PRINCIPLE.yaml").exists()


@pytest.mark.parametrize("decision", ["request_revision", "combine", "reject"])
def test_human_candidate_revision_paths_return_feedback_to_method_design(
    tmp_path: Path, decision: str
) -> None:
    controller = controller_at_method_design(tmp_path)
    write_and_complete_method_design(controller)
    accept_current_scientific_gate_from_validated_prefix_fixture(
        controller, verdict_id="method-review-1"
    )
    feedback = f"{decision}: revise or combine the Candidate mechanisms using current Evidence."
    if decision == "combine":
        with pytest.raises(ControllerError, match="current reviewed Candidate ID@version"):
            controller.validate_human_gate_decision(
                "principle_selection",
                "combine",
                selected_id="PR-A@1,PR-B@0",
                human_feedback=feedback,
            )
    selected_id = "PR-A@1,PR-B@1" if decision == "combine" else None
    request = controller.validate_human_gate_decision(
        "principle_selection", decision, selected_id=selected_id, human_feedback=feedback
    )
    approvals.issue_ui_approval_receipt(
        controller.root,
        controller.run_id,
        "principle_selection",
        request["id"],
        decision,
        selected_id=selected_id,
        human_feedback=feedback,
        artifact_bindings=request["artifact_bindings"],
    )
    returned = controller.human_approve(
        "principle_selection", decision, selected_id=selected_id, human_feedback=feedback
    )
    event = returned["scientific_core"]["return_history"][-1]
    assert returned["scientific_core"]["current_phase"] == "method_design"
    assert returned["scientific_core"]["selected_for_testing"] is None
    assert event["human_feedback"] == feedback
    if decision == "combine":
        assert event["combine_source_candidates"] == [
            {"principle_id": "PR-A", "principle_version": "1"},
            {"principle_id": "PR-B", "principle_version": "1"},
        ]
        assert event["combine_source_packet"] == {
            "path": "idea-stage/METHOD_DESIGN_PACKET.json",
            "sha256": request["artifact_bindings"]["idea-stage/METHOD_DESIGN_PACKET.json"],
        }
        revised_packet = bound_method_design_packet(controller, cycle_id="DESIGN-2")
        synthesis = deepcopy(revised_packet["candidate_principles"][0])
        synthesis.update(
            {
                "principle_id": "PR-S",
                "principle_version": "1",
                "parent_version": None,
                "principle": "Synthesis Principle",
                "intervention": "synthesize the two causal interventions",
                "changed_structure": "the coupled relation between the two mechanisms",
                "substantive_difference": "mechanism-level synthesis of PR-A and PR-B",
                "derived_from_principles": event["combine_source_candidates"],
            }
        )
        revised_packet["candidate_principles"].append(synthesis)
        revised = write_and_complete_method_design(
            controller,
            cycle_id="DESIGN-2",
            verdict_id=f"method-review-{decision}",
            packet=revised_packet,
        )
    else:
        revised = write_and_complete_method_design(
            controller, cycle_id="DESIGN-2", verdict_id=f"method-review-{decision}"
        )
    assert event["id"] in revised["return_feedback_refs"]


def test_principle_test_design_fails_closed_without_human_selection(tmp_path: Path) -> None:
    controller = controller_at_method_design(tmp_path)
    write_and_complete_method_design(controller)
    accept_current_scientific_gate_from_validated_prefix_fixture(
        controller, verdict_id="method-review-1"
    )
    with controller._store.mutate() as state:
        selection_phase = run_state._find_phase(state, "principle_human_selection")
        selection_phase["status"] = "human_accepted"
        state["scientific_core"]["current_phase"] = "principle_test_design"
        state["scientific_core"]["approval_request"] = None
        state["scientific_core"]["selected_for_testing"] = None
    with pytest.raises(ControllerError, match="Human-selected Candidate"):
        controller.start_current_phase()


def test_method_test_window_is_human_gated_atomic_and_terminal_outcomes_form_context(
    tmp_path: Path,
) -> None:
    controller = controller_at_method_design(tmp_path)
    with pytest.raises(ControllerError, match="pending principle_evaluation"):
        controller.method_test_handoff()
    plan = reach_principle_test_human_approval(controller)
    assert not (tmp_path / "idea-stage" / "SELECTED_PRINCIPLE.yaml").exists()
    with pytest.raises(ControllerError, match="pending principle_evaluation"):
        controller.method_test_handoff()

    approve(controller, "principle_test_approval")
    cycle = controller.status()["scientific_core"]["method_test_cycle"]
    assert cycle["approved_test_ids"] == plan["recommended_execution_set"]["test_ids"]
    assert cycle["execution_set_id"] == plan["execution_set_id"]
    assert cycle["estimated_total_cost"] == plan["estimated_total_cost"]
    handoff = controller.method_test_handoff()
    assert handoff["approved_test_ids"] == ["TEST-FATAL-A"]
    assert handoff["tests"][0]["test_only_concrete_realization"] == {
        "probe": "bounded analysis"
    }
    assert not (tmp_path / "idea-stage" / "SELECTED_PRINCIPLE.yaml").exists()

    outside = terminal_result(controller)
    outside["test_id"] = "TEST-UNAPPROVED"
    with pytest.raises(ControllerError, match="not in the approved execution set"):
        controller.submit_method_test_result(outside)
    assert set(controller.status()["scientific_core"]["method_test_cycle"]["terminal_outcomes"]) != {
        "TEST-FATAL-A"
    }
    assert "start_phase" not in controller.allowed_actions()
    with pytest.raises(ControllerError, match="missing required input|all approved tests must be terminal"):
        controller.start_current_phase()

    terminal = terminal_result(controller, outcome="NO_RESULT")
    completed_cycle = controller.submit_method_test_result(terminal)
    assert completed_cycle["status"] == "TERMINAL"
    context = json.loads(
        (tmp_path / "idea-stage" / "PRINCIPLE_EVIDENCE_CONTEXT.json").read_text(encoding="utf-8")
    )
    assert context["terminal_outcomes"] == [
        {"test_id": "TEST-FATAL-A", "outcome": "NO_RESULT", "reason": "unavailable"}
    ]
    assert context["active_principles"] == [
        {"principle_id": "PR-A", "principle_version": "1"},
    ]
    assert len(context["test_targets"]) == 1
    assert "decision" not in context["terminal_outcomes"][0]
    controller.start_current_phase()


def test_human_revision_replaces_the_atomic_execution_set_before_any_test(
    tmp_path: Path,
) -> None:
    controller = controller_at_method_design(tmp_path)
    reach_principle_test_human_approval(controller)
    selection_before = deepcopy(controller.status()["scientific_core"]["selected_for_testing"])
    request_human_gate_revision(controller, "principle_test_approval")
    state = controller.status()
    assert state["scientific_core"]["current_phase"] == "principle_test_design"
    assert state["scientific_core"]["method_test_cycle"] is None
    assert state["scientific_core"]["selected_for_testing"] == selection_before
    assert not (tmp_path / "idea-stage" / "PRINCIPLE_EVIDENCE_CONTEXT.json").exists()

    plan = write_and_complete_principle_test_design(
        controller, cycle_id="CYCLE-2", verdict_id="test-plan-review-2"
    )
    assert state["scientific_core"]["return_history"][-1]["id"] in plan["return_feedback_refs"]
    accept_current_scientific_gate_from_validated_prefix_fixture(
        controller, verdict_id="test-plan-review-2"
    )
    approve(controller, "principle_test_approval")
    cycle = controller.status()["scientific_core"]["method_test_cycle"]
    assert cycle["cycle_id"] == "CYCLE-2"
    assert cycle["execution_set_id"] == "EXEC-CYCLE-2"


def test_revise_principles_returns_to_same_phase_and_requires_feedback_consumption(
    tmp_path: Path,
) -> None:
    controller = controller_at_method_design(tmp_path)
    write_and_complete_method_design(
        controller, decision="REVISE_PRINCIPLES", verdict_id="method-revise-1"
    )
    returned = controller.return_current_phase("method-revise-1", "claude-sonnet-4")
    event = returned["scientific_core"]["return_history"][-1]
    assert event["return_target"] == "method_design"
    revised = write_and_complete_method_design(
        controller, cycle_id="CYCLE-2", verdict_id="method-review-2"
    )
    assert revised["return_feedback_refs"] == [event["id"]]


def test_revise_evaluation_reuses_cycle_results_and_equivalent_context_without_retest(
    tmp_path: Path,
) -> None:
    controller = controller_at_method_design(tmp_path)
    reach_principle_test_human_approval(controller)
    approve(controller, "principle_test_approval")
    controller.method_test_handoff()
    controller.submit_method_test_result(terminal_result(controller))
    before = controller.status()["scientific_core"]["method_test_cycle"]
    context_payload = json.loads(
        (tmp_path / "idea-stage" / "PRINCIPLE_EVIDENCE_CONTEXT.json").read_text(encoding="utf-8")
    )
    evaluation, _ = write_and_complete_principle_evaluation(
        controller, decision="REVISE_EVALUATION", verdict_id="evaluation-revise-1"
    )
    review_request = run_state._find_phase(
        controller.status(), "principle_evaluation"
    )["review_request"]
    assert review_request["artifact_bindings"]["idea-stage/PRINCIPLE_EVALUATION.json"] == sha256_file(
        tmp_path / "idea-stage" / "PRINCIPLE_EVALUATION.json"
    )
    controller.return_current_phase("evaluation-revise-1", "claude-sonnet-4")
    after = controller.status()["scientific_core"]["method_test_cycle"]
    rebuilt = json.loads(
        (tmp_path / "idea-stage" / "PRINCIPLE_EVIDENCE_CONTEXT.json").read_text(encoding="utf-8")
    )
    assert after["cycle_id"] == before["cycle_id"]
    assert after["execution_set_id"] == before["execution_set_id"]
    assert after["terminal_outcomes"] == before["terminal_outcomes"]
    assert rebuilt == context_payload
    assert controller.allowed_actions() == ["start_phase", "revise_problem"]
    assert evaluation["evidence_context_ref"] == after["evidence_context"]

    second, _ = write_and_complete_principle_evaluation(
        controller, decision="PRINCIPLE_CONVERGED", verdict_id="evaluation-converged-1"
    )
    assert second["return_feedback_refs"] == [
        controller.status()["scientific_core"]["return_history"][-1]["id"]
    ]
    accepted = accept_current_scientific_gate_from_validated_prefix_fixture(
        controller,
        verdict_id="evaluation-converged-1",
    )
    selected = yaml.safe_load(
        (tmp_path / "idea-stage" / "SELECTED_PRINCIPLE.yaml").read_text(encoding="utf-8")
    )
    assert selected["principle_id"] == "PR-A"
    assert selected["principle_version"] == "1"
    assert accepted["scientific_core"]["current_phase"] == "method_refinement"
    assert not (tmp_path / "idea-stage" / "PRINCIPLE_EVIDENCE_CONTEXT.json").exists()


def test_principle_evaluation_rejects_missing_test_coverage_and_stale_update_target(
    tmp_path: Path,
) -> None:
    controller = controller_at_method_design(tmp_path)
    reach_principle_test_human_approval(controller)
    approve(controller, "principle_test_approval")
    controller.method_test_handoff()
    controller.submit_method_test_result(terminal_result(controller))
    controller.start_current_phase()
    evaluation = principle_evaluation_payload(controller)
    path = tmp_path / "idea-stage" / "PRINCIPLE_EVALUATION.json"

    missing_coverage = deepcopy(evaluation)
    missing_coverage["test_validity_assessments"] = []
    path.write_text(json.dumps(missing_coverage), encoding="utf-8")
    with pytest.raises(ControllerError, match="test_validity_assessments"):
        controller.refresh_current_review_request()

    stale_target = deepcopy(evaluation)
    stale_target["scientific_updates"][0]["target_id"] = "PR-STALE@9"
    path.write_text(json.dumps(stale_target), encoding="utf-8")
    with pytest.raises(ControllerError, match="stale or unknown target"):
        controller.refresh_current_review_request()


def test_accepted_convergence_initializes_acceptance_artifacts_and_materializes_principle(
    tmp_path: Path,
) -> None:
    controller = controller_at_method_design(tmp_path)
    reach_principle_test_human_approval(controller)
    approve(controller, "principle_test_approval")
    controller.method_test_handoff()
    controller.submit_method_test_result(terminal_result(controller))
    write_and_complete_principle_evaluation(
        controller, decision="PRINCIPLE_CONVERGED", verdict_id="evaluation-converged-1"
    )

    accepted = accept_current_scientific_gate_from_validated_prefix_fixture(
        controller, verdict_id="evaluation-converged-1"
    )
    phase = run_state._find_phase(accepted, "principle_evaluation")
    assert "idea-stage/SELECTED_PRINCIPLE.yaml" in phase["acceptance_artifacts"]
    assert (tmp_path / "idea-stage" / "SELECTED_PRINCIPLE.yaml").is_file()
    selected = yaml.safe_load(
        (tmp_path / "idea-stage" / "SELECTED_PRINCIPLE.yaml").read_text(encoding="utf-8")
    )
    assert selected["origin_binding"] == {
        "origin_type": "FIRST_PRINCIPLES",
        "origin_ref_id": "FP-1",
        "alignment_ref_id": None,
    }
    assert selected["origin_closure"]["origin_record_id"] == "FP-1"
    assert selected["intervention_alignment"] is None
    assert selected["target_intervention_novelty"]["novelty_closure_id"] == "NOVELTY-A"
    assert selected["accepted_assumptions"][0]["assumption_id"] == "ASM-A"
    assert selected["accepted_predictions"][0]["prediction_id"] == "PRED-A"
    assert selected["provisional_scientific_delta"] == "delta A"
    assert "accepted_scientific_updates" not in selected
    assert selected["applicability_boundaries"]["accepted_boundary_updates"][0][
        "update_id"
    ] == "UPDATE-PR-A"
    assert len(selected["applicability_boundaries"]["accepted_boundary_updates"]) == 1
    evaluation = json.loads(
        (tmp_path / "idea-stage" / "PRINCIPLE_EVALUATION.json").read_text(encoding="utf-8")
    )
    assert {item["update_id"] for item in evaluation["scientific_updates"]} == {
        "UPDATE-PR-A", "UPDATE-UNACCEPTED",
    }
    history = [
        json.loads(line)
        for line in (tmp_path / "idea-stage" / "METHOD_PRINCIPLES.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]
    assert "UPDATE-UNACCEPTED" in {
        item.get("scientific_update_id") for item in history
    }
    assert selected["evidence_closure"]["evidence_context"]["sha256"]

    refine = (REPO / "skills" / "research-refine" / "SKILL.md").read_text(encoding="utf-8")
    assert "origin/alignment, novelty, assumptions, predictions" in refine


def test_principle_convergence_requires_one_selected_principle_id_and_version(
    tmp_path: Path,
) -> None:
    controller = controller_at_method_design(tmp_path)
    reach_principle_test_human_approval(controller)
    approve(controller, "principle_test_approval")
    controller.method_test_handoff()
    controller.submit_method_test_result(terminal_result(controller))
    controller.start_current_phase()
    evaluation = principle_evaluation_payload(controller)
    evaluation_path = tmp_path / "idea-stage" / "PRINCIPLE_EVALUATION.json"
    evaluation_path.write_text(json.dumps(evaluation), encoding="utf-8")
    controller.refresh_current_review_request()
    verdict = json_review_payload(
        controller, decision="PRINCIPLE_CONVERGED", verdict_id="missing-selection"
    )
    (tmp_path / "idea-stage" / "PRINCIPLE_EVALUATION_VERDICT.json").write_text(
        json.dumps(verdict), encoding="utf-8"
    )
    with pytest.raises(ControllerError, match="one selected Principle ID/version"):
        controller.complete_current_phase()


@pytest.mark.parametrize(
    ("decision", "target"),
    [
        ("MORE_EVIDENCE", "principle_test_design"),
        ("CANDIDATE_REJECTED", "method_design"),
        ("RCA_CONFLICT", "root_cause_analysis"),
        ("NECESSITY_CONFLICT", "problem_necessity"),
        ("PROBLEM_CONFLICT", "problem_generation"),
    ],
)
def test_evaluation_returns_deactivate_context_preserve_ledgers_and_bind_feedback(
    tmp_path: Path, decision: str, target: str
) -> None:
    controller = controller_at_method_design(tmp_path)
    reach_principle_test_human_approval(controller)
    approve(controller, "principle_test_approval")
    controller.method_test_handoff()
    controller.submit_method_test_result(terminal_result(controller))
    evaluation, _ = write_and_complete_principle_evaluation(
        controller, decision=decision, verdict_id=f"evaluation-{decision.lower()}"
    )
    returned = controller.return_current_phase(
        f"evaluation-{decision.lower()}", "claude-sonnet-4"
    )
    core = returned["scientific_core"]
    assert core["current_phase"] == target
    assert not (tmp_path / "idea-stage" / "PRINCIPLE_EVIDENCE_CONTEXT.json").exists()
    assert (tmp_path / "idea-stage" / "METHOD_PRINCIPLES.jsonl").is_file()
    assert (tmp_path / "idea-stage" / "METHOD_TEST_EVIDENCE.jsonl").is_file()
    event = core["return_history"][-1]
    assert event["return_guidance"]["decision_target"]
    assert event["decision"] == decision
    assert evaluation["scientific_updates"][0]["consequence"] == "UPDATE_BOUNDARY"

    if decision == "MORE_EVIDENCE":
        assert core["method_test_cycle"] is None
        assert core["last_method_test_cycle_id"] == "CYCLE-1"
        plan = write_and_complete_principle_test_design(
            controller, cycle_id="CYCLE-2", verdict_id="test-plan-review-2"
        )
        assert event["id"] in plan["return_feedback_refs"]
        assert plan["relevant_history_refs"]
        accept_current_scientific_gate_from_validated_prefix_fixture(
            controller, verdict_id="test-plan-review-2"
        )
        assert controller.current_stage() == "PRINCIPLE_TEST_HUMAN_APPROVAL"
        approve(controller, "principle_test_approval")
        assert controller.status()["scientific_core"]["method_test_cycle"]["cycle_id"] == "CYCLE-2"
        assert controller.status()["scientific_core"]["selected_for_testing"]["status"] == "ACTIVE"
    else:
        assert core["selected_for_testing"] is None
    if decision == "PROBLEM_CONFLICT":
        assert core["active_problem_version"] is None
    if decision == "CANDIDATE_REJECTED":
        history = (tmp_path / "idea-stage" / "METHOD_PRINCIPLES.jsonl").read_text(encoding="utf-8")
        assert '"event_type": "REJECTED"' in history


def test_validation_handoff_rejects_prompt_or_legacy_files_without_formal_route(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller = start_controller(tmp_path)
    proposal = tmp_path / "refine-logs" / "FINAL_PROPOSAL.md"
    proposal.parent.mkdir(parents=True, exist_ok=True)
    proposal.write_text("# Complete method supplied in prompt", encoding="utf-8")
    legacy = tmp_path / "idea-stage" / "docs" / "research_contract.md"
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text("# Historic report-derived contract", encoding="utf-8")

    with pytest.raises(
        ControllerError, match="METHOD_CONFIRMED_AWAITING_USER_VALIDATION"
    ):
        controller.validation_handoff()

    legacy_root = tmp_path / "legacy-ad-hoc"
    run_state.start_run(legacy_root, "legacy", ["experiment"], executor="codex")
    monkeypatch.chdir(legacy_root)
    legacy_plan = legacy_root / "refine-logs" / "EXPERIMENT_PLAN.md"
    legacy_plan.parent.mkdir(parents=True, exist_ok=True)
    legacy_plan.write_text(
        "execution_context: NON_CANONICAL_AD_HOC\n# user-supplied method\n",
        encoding="utf-8",
    )
    with pytest.raises(ControllerError, match="managed .codex layer"):
        ARISController(legacy_root, "legacy").validation_handoff()
    assert legacy_plan.is_file()
    assert build_parser().parse_args(["validation-handoff", "run-1"]).command == (
        "validation-handoff"
    )
    assert build_parser().parse_args(
        ["submit-validation-result", "run-1", "VALIDATION_RESULT.json"]
    ).command == "submit-validation-result"


def test_validation_result_closes_a_bound_canonical_handoff(tmp_path: Path) -> None:
    controller = confirmed_validation_controller(tmp_path)
    assert controller.allowed_actions() == ["validation_handoff"]
    with pytest.raises(ControllerError, match="Controller-issued validation handoff"):
        controller.submit_validation_result(
            validation_result(controller, decision="VALIDATED", issue_handoff=False)
        )

    handoff = controller.validation_handoff()
    assert controller.allowed_actions() == ["validation_handoff", "submit_validation_result"]
    assert controller.allowed_agents() == ["result_to_claim_reviewer"]
    reviewer_owned = validation_result(controller, decision="VALIDATED")
    attest_validation_verdict(controller, reviewer_owned)
    wrong_run = dict(reviewer_owned)
    wrong_run["run_id"] = "other-run"
    with pytest.raises(ControllerError, match="exact externally attested"):
        controller.submit_validation_result(wrong_run)
    wrong_handoff = dict(reviewer_owned)
    wrong_handoff["handoff_sha256"] = "0" * 64
    with pytest.raises(ControllerError, match="exact externally attested"):
        controller.submit_validation_result(wrong_handoff)
    main_rewrite = json.loads(json.dumps(reviewer_owned))
    main_rewrite["mechanism_evidence_closure"][0]["observed_mechanism_change"] = (
        "No mechanism change was observed."
    )
    with pytest.raises(ControllerError, match="exact externally attested"):
        controller.submit_validation_result(main_rewrite)

    stale = reviewer_owned
    proposal = tmp_path / "refine-logs" / "FINAL_PROPOSAL.md"
    original_proposal = proposal.read_text(encoding="utf-8")
    proposal.write_text("# changed after handoff\n", encoding="utf-8")
    with pytest.raises(ControllerError, match="missing or changed"):
        controller.submit_validation_result(stale)
    proposal.write_text(original_proposal, encoding="utf-8")

    completed = controller.submit_validation_result(reviewer_owned)
    core = completed["scientific_core"]
    assert controller.current_stage() == "VALIDATION_CONFIRMED"
    assert controller.allowed_actions() == []
    assert core["validation_entry"]["handoff_sha256"] == handoff["handoff_sha256"]
    result = core["validation_results"][-1]
    assert result["decision"] == "VALIDATED"
    assert (tmp_path / result["path"]).is_file()
    with pytest.raises(ControllerError, match="METHOD_CONFIRMED_AWAITING_USER_VALIDATION"):
        controller.validation_handoff()


@pytest.mark.parametrize("invalid_obligation_id", ["OBL-MISSING", "OBL-OTHER-SET"])
def test_validated_rejects_obligation_ids_outside_selected_principle(
    tmp_path: Path, invalid_obligation_id: str
) -> None:
    controller = confirmed_validation_controller(tmp_path)
    controller.validation_handoff()
    result = validation_result(controller, decision="VALIDATED")
    result["mechanism_evidence_closure"][0]["obligation_ids"] = [invalid_obligation_id]
    attest_validation_verdict(controller, result)

    with pytest.raises(ControllerError, match="obligation IDs are invalid"):
        controller.submit_validation_result(result)


def test_validated_rejects_a_performance_only_mechanism_closure(tmp_path: Path) -> None:
    controller = confirmed_validation_controller(tmp_path)
    controller.validation_handoff()
    result = validation_result(controller, decision="VALIDATED")
    closure = result["mechanism_evidence_closure"][0]
    closure["observed_mechanism_change"] = "No mechanism change was observed."
    closure["performance_consequence"] = "Performance improved anyway."
    closure["explanation_status"] = "PERFORMANCE_ONLY"
    closure["mechanism_match"] = "DOES_NOT_MATCH_PREDICTION"
    attest_validation_verdict(controller, result)
    with pytest.raises(ControllerError, match="EXPLANATION_SUPPORTED"):
        controller.submit_validation_result(result)


@pytest.mark.parametrize(
    ("decision", "target"),
    [
        ("METHOD_REFINEMENT_REQUIRED", "method_refinement"),
        ("SELECTED_PRINCIPLE_REJECTED", "method_design"),
        ("ROOT_CAUSE_REJECTED", "root_cause_analysis"),
        ("PROBLEM_PREMISE_REJECTED", "problem_generation"),
    ],
)
def test_validation_result_uses_fixed_canonical_return_targets(
    tmp_path: Path, decision: str, target: str
) -> None:
    controller = confirmed_validation_controller(tmp_path)
    verdict = validation_result(controller, decision=decision)
    attest_validation_verdict(controller, verdict)
    returned = controller.submit_validation_result(verdict)
    core = returned["scientific_core"]
    assert core["status"] == "ACTIVE"
    assert core["current_phase"] == target
    assert controller.current_stage() == target.upper()
    return_record = core["return_history"][-1]
    assert return_record["decision"] == decision
    assert return_record["return_target"] == target
    assert return_record["validation_result_id"] == core["validation_results"][-1]["id"]
    assert run_state._latest_return_feedback_ref(returned, target) == return_record["id"]
    assert controller._current_return_feedback(returned, target)["evidence_refs"] == [
        "results/validation.json"
    ]
    assert any(Path(path).as_posix() == "idea-stage/IDEA_REPORT.md" for path in return_record["invalidated_artifact_paths"])
    assert not (tmp_path / "idea-stage" / "IDEA_REPORT.md").exists()
    selected_path = tmp_path / "idea-stage" / "SELECTED_PRINCIPLE.yaml"
    selected_record = core["accepted_artifacts"].get("idea-stage/SELECTED_PRINCIPLE.yaml")
    if target == "method_refinement":
        assert selected_path.is_file()
        assert selected_record is not None
    else:
        assert not selected_path.exists()
        assert selected_record is None
    if target == "problem_generation":
        assert core["active_problem_version"] is None
        assert core["pending_problem_revision"]["allow_problem_replacement"] is True
    else:
        assert core["active_problem_version"]["problem_id"] == "P-1"


@pytest.mark.parametrize(
    ("decision", "target", "selected_remains"),
    [
        ("REVISE_METHOD_DELTA", "method_refinement", True),
        ("RETHINK_PRINCIPLE_DELTA", "method_design", False),
        ("HOLD", "final_method_novelty_gate", True),
    ],
)
def test_final_method_novelty_uses_layered_return_targets(
    tmp_path: Path, decision: str, target: str, selected_remains: bool
) -> None:
    controller = confirmed_validation_controller(tmp_path)
    packet_path = write_batch4_final_packet(controller)
    with controller._store.mutate() as state:
        core = state["scientific_core"]
        core["accepted_artifacts"]["refine-logs/FINAL_METHOD_PACKET.json"] = (
            controller._artifact_record(
                "refine-logs/FINAL_METHOD_PACKET.json",
                producer_phase="method_refinement",
                provenance={
                    "controller": "ARISController",
                    "run_id": controller.run_id,
                },
                upstream_snapshot={},
            )
        )
        core["status"] = "ACTIVE"
        core["current_phase"] = "final_method_novelty_gate"
        core["validation_entry"] = None
        core["approval_request"] = None
        state["research_lit"]["current_stage"] = "LANDSCAPE_ACCEPTED"
        phase = run_state._find_phase(state, "final_method_novelty_gate")
        phase["status"] = "pending"
        phase["review_request"] = None
        run_state._find_phase(state, "final_method_human_acceptance")["status"] = "pending"
    assert packet_path.is_file()

    controller.start_current_phase()
    verdict_id = f"final-novelty-{decision.lower()}"
    verdict_path = tmp_path / "idea-stage" / "FINAL_METHOD_NOVELTY_VERDICT.md"
    verdict_path.write_text(
        formal_verdict_artifact(
            controller, verdict_id=verdict_id, decision=decision
        ),
        encoding="utf-8",
    )
    controller.complete_current_phase()
    attest_current_review(
        controller, verdict_id, "claude-sonnet-4", decision=decision
    )
    returned = controller.return_current_phase(verdict_id, "claude-sonnet-4")

    core = returned["scientific_core"]
    event = core["return_history"][-1]
    assert core["current_phase"] == target
    assert run_state._find_phase(returned, target)["status"] == "pending"
    assert event["decision"] == decision
    assert event["return_target"] == target
    assert event["return_guidance"]["decision_target"]
    selected_path = tmp_path / "idea-stage" / "SELECTED_PRINCIPLE.yaml"
    selected_record = core["accepted_artifacts"].get(
        "idea-stage/SELECTED_PRINCIPLE.yaml"
    )
    assert selected_path.exists() is selected_remains
    assert (selected_record is not None) is selected_remains


def test_final_method_novelty_return_guidance_must_match_reviewer_payload(
    tmp_path: Path,
) -> None:
    controller = confirmed_validation_controller(tmp_path)
    activate_method_refinement_review(controller)
    method_verdict_id = "method-ready-before-novelty-closure"
    (tmp_path / "refine-logs" / "FINAL_BLIND_REVIEW.md").write_text(
        formal_verdict_artifact(controller, verdict_id=method_verdict_id),
        encoding="utf-8",
    )
    controller.complete_current_phase()
    accept_formal(controller, method_verdict_id, "claude-sonnet-4")

    controller.start_current_phase()
    verdict_id = "final-novelty-reviewer-guidance"
    verdict_path = tmp_path / "idea-stage" / "FINAL_METHOD_NOVELTY_VERDICT.md"
    verdict_path.write_text(
        formal_verdict_artifact(
            controller,
            verdict_id=verdict_id,
            decision="REVISE_METHOD_DELTA",
        ),
        encoding="utf-8",
    )
    controller.complete_current_phase()
    request = run_state._find_phase(
        controller.status(), "final_method_novelty_gate"
    )["review_request"]
    metadata = json.loads(
        verdict_path.read_text(encoding="utf-8")
        .split("```json\n", 1)[1]
        .split("\n```", 1)[0]
    )
    reviewer_payload = deepcopy(metadata)
    reviewer_payload["return_guidance"]["required_check"] = [
        "Apply the independent reviewer's required novelty repair."
    ]
    attest(controller, request["required_reviewer_role"], reviewer_payload)

    with pytest.raises(
        ControllerError,
        match="Final method novelty verdict artifact differs from the reviewer payload",
    ):
        controller.return_current_phase(verdict_id, "claude-sonnet-4")

    state = controller.status()
    assert state["scientific_core"]["current_phase"] == "final_method_novelty_gate"
    assert run_state._find_phase(
        state, "final_method_novelty_gate"
    )["status"] == "done"


def activate_method_refinement_review(controller: ARISController) -> dict:
    """Reopen the Batch 4 fixture at a clean current refinement review."""

    with controller._store.mutate() as state:
        core = state["scientific_core"]
        core["status"] = "ACTIVE"
        core["current_phase"] = "method_refinement"
        core["validation_entry"] = None
        core["approval_request"] = None
        state["research_lit"]["current_stage"] = "LANDSCAPE_ACCEPTED"
        for phase_name in (
            "method_refinement",
            "final_method_novelty_gate",
            "top_venue_method_strength_gate",
            "final_method_human_acceptance",
        ):
            phase = run_state._find_phase(state, phase_name)
            phase["status"] = "pending"
            phase["review_request"] = None
        for raw_path in (
            "refine-logs/FINAL_METHOD_PACKET.json",
            "refine-logs/FINAL_PROPOSAL.md",
            "refine-logs/FINAL_BLIND_REVIEW.md",
            "refine-logs/REFINE_STATE.json",
            "idea-stage/FINAL_METHOD_NOVELTY_VERDICT.md",
            "idea-stage/TOP_VENUE_METHOD_STRENGTH_VERDICT.json",
            "idea-stage/IDEA_REPORT.md",
        ):
            core["accepted_artifacts"].pop(raw_path, None)
            path = controller.root / raw_path
            if path.is_file():
                path.unlink()

    controller.start_current_phase()
    (controller.root / "refine-logs" / "REFINE_STATE.json").write_text(
        '{"status":"final_review"}\n', encoding="utf-8"
    )
    write_batch4_final_packet(controller)
    return controller.refresh_current_review_request()


@pytest.mark.parametrize(
    ("decision", "target"),
    [
        ("NECESSITY_CONFLICT", "problem_necessity"),
        ("PROBLEM_CONFLICT", "problem_generation"),
    ],
)
def test_method_refinement_upstream_conflicts_use_canonical_return_lifecycle(
    tmp_path: Path, decision: str, target: str
) -> None:
    controller = confirmed_validation_controller(tmp_path)
    activate_method_refinement_review(controller)
    verdict_id = f"refinement-{decision.lower()}"
    (tmp_path / "refine-logs" / "FINAL_BLIND_REVIEW.md").write_text(
        formal_verdict_artifact(
            controller, verdict_id=verdict_id, decision=decision
        ),
        encoding="utf-8",
    )
    controller.complete_current_phase()
    attest_current_review(
        controller, verdict_id, "claude-sonnet-4", decision=decision
    )
    returned = controller.return_current_phase(verdict_id, "claude-sonnet-4")

    core = returned["scientific_core"]
    event = core["return_history"][-1]
    assert core["current_phase"] == target
    assert event["decision"] == decision
    assert event["return_target"] == target
    assert event["return_guidance"]["decision_target"] == target
    assert (tmp_path / "idea-stage" / "ACTIVE_FIELD_MAP.md").is_file()
    assert (tmp_path / "idea-stage" / "RESEARCH_CONTRACT.md").is_file() is (
        decision == "NECESSITY_CONFLICT"
    )
    assert (core["active_problem_version"] is not None) is (
        decision == "NECESSITY_CONFLICT"
    )
    if decision == "PROBLEM_CONFLICT":
        assert core["pending_problem_revision"]["allow_problem_replacement"] is True
    for raw_path in (
        "idea-stage/NECESSITY_CLOSURE.json",
        "idea-stage/NECESSITY_VERDICT.json",
        "idea-stage/ROOT_CAUSE_ANALYSIS.json",
        "idea-stage/ROOT_CAUSE_VERDICT.json",
        "idea-stage/SELECTED_PRINCIPLE.yaml",
        "refine-logs/FINAL_METHOD_PACKET.json",
        "refine-logs/FINAL_BLIND_REVIEW.md",
    ):
        assert not (tmp_path / raw_path).exists()
        assert raw_path not in core["accepted_artifacts"]
    assert core["selected_for_testing"] is None


@pytest.mark.parametrize(
    ("decision", "guidance", "error"),
    [
        ("NECESSITY_CONFLICT", None, "return_guidance"),
        ("PROBLEM_CONFLICT", None, "return_guidance"),
        (
            "NECESSITY_CONFLICT",
            {
                "missing_evidence": ["conflicting Evidence"],
                "required_check": ["recheck Necessity"],
                "decision_target": "root_cause_analysis",
            },
            "canonical return target",
        ),
        (
            "PROBLEM_CONFLICT",
            {
                "missing_evidence": ["conflicting Evidence"],
                "required_check": ["recheck Problem"],
                "decision_target": "problem_necessity",
            },
            "canonical return target",
        ),
    ],
)
def test_method_refinement_conflict_guidance_is_structured_and_target_bound(
    tmp_path: Path, decision: str, guidance: dict | None, error: str
) -> None:
    controller = confirmed_validation_controller(tmp_path)
    request = activate_method_refinement_review(controller)
    metadata = {
        "schema_version": 1,
        "run_id": controller.run_id,
        "review_request_id": request["id"],
        "reviewer": "claude-sonnet-4",
        "verdict_id": f"invalid-{decision.lower()}-guidance",
        "decision": decision,
        "reviewed_artifact_hashes": request["artifact_bindings"],
    }
    if guidance is not None:
        metadata["return_guidance"] = guidance
    (tmp_path / "refine-logs" / "FINAL_BLIND_REVIEW.md").write_text(
        "# Final review\n\n```json\n" + json.dumps(metadata) + "\n```\n",
        encoding="utf-8",
    )
    with pytest.raises(ControllerError, match=error):
        controller.complete_current_phase()
    assert controller.status()["scientific_core"]["current_phase"] == (
        "method_refinement"
    )


def test_method_refinement_main_finding_or_unknown_conflict_cannot_return(
    tmp_path: Path,
) -> None:
    controller = confirmed_validation_controller(tmp_path)
    activate_method_refinement_review(controller)
    (tmp_path / "refine-logs" / "ACTIVE_PROPOSAL.md").write_text(
        "Main finding: PROBLEM_CONFLICT should return to problem_generation.\n",
        encoding="utf-8",
    )
    with pytest.raises(ControllerError, match="must be done before return"):
        controller.return_current_phase("main-finding", "main_research_agent")
    assert controller.status()["scientific_core"]["current_phase"] == (
        "method_refinement"
    )

    (tmp_path / "refine-logs" / "FINAL_BLIND_REVIEW.md").write_text(
        formal_verdict_artifact(
            controller,
            verdict_id="unknown-conflict",
            decision="UPSTREAM_CONFLICT",
        ),
        encoding="utf-8",
    )
    with pytest.raises(ControllerError, match="decision is not allowed"):
        controller.complete_current_phase()


def test_current_packet_first_downstream_reaches_existing_final_human_boundary(
    tmp_path: Path,
) -> None:
    controller = confirmed_validation_controller(tmp_path)
    packet_path = tmp_path / "refine-logs" / "FINAL_METHOD_PACKET.json"
    assert not packet_path.exists()
    with controller._store.mutate() as state:
        core = state["scientific_core"]
        core["status"] = "ACTIVE"
        core["current_phase"] = "method_refinement"
        core["validation_entry"] = None
        core["approval_request"] = None
        state["research_lit"]["current_stage"] = "LANDSCAPE_ACCEPTED"
        for phase_name in (
            "method_refinement",
            "final_method_novelty_gate",
            "top_venue_method_strength_gate",
            "final_method_human_acceptance",
        ):
            phase = run_state._find_phase(state, phase_name)
            phase["status"] = "pending"
            phase["review_request"] = None
        for raw_path in (
            "refine-logs/FINAL_PROPOSAL.md",
            "refine-logs/FINAL_BLIND_REVIEW.md",
            "idea-stage/FINAL_METHOD_NOVELTY_VERDICT.md",
            "idea-stage/TOP_VENUE_METHOD_STRENGTH_VERDICT.json",
            "idea-stage/IDEA_REPORT.md",
        ):
            core["accepted_artifacts"].pop(raw_path, None)

    controller.start_current_phase()
    refine_state = tmp_path / "refine-logs" / "REFINE_STATE.json"
    refine_state.write_text('{"status":"final_review"}\n', encoding="utf-8")
    write_batch4_final_packet(controller)
    method_request = controller.refresh_current_review_request()
    assert method_request["artifact_bindings"][
        "refine-logs/FINAL_METHOD_PACKET.json"
    ] == sha256_file(packet_path)
    assert "refine-logs/FINAL_PROPOSAL.md" not in method_request["artifact_bindings"]
    method_verdict_id = "method-ready-packet-first"
    (tmp_path / "refine-logs" / "FINAL_BLIND_REVIEW.md").write_text(
        formal_verdict_artifact(controller, verdict_id=method_verdict_id),
        encoding="utf-8",
    )
    controller.complete_current_phase()
    accept_formal(controller, method_verdict_id, "claude-sonnet-4")
    assert controller.status()["scientific_core"]["current_phase"] == (
        "final_method_novelty_gate"
    )

    controller.start_current_phase()
    novelty_request = run_state._find_phase(
        controller.status(), "final_method_novelty_gate"
    )["review_request"]
    assert "refine-logs/FINAL_METHOD_PACKET.json" in novelty_request["artifact_bindings"]
    assert "refine-logs/FINAL_PROPOSAL.md" not in novelty_request["artifact_bindings"]
    novelty_verdict_id = "novel-after-packet"
    (tmp_path / "idea-stage" / "FINAL_METHOD_NOVELTY_VERDICT.md").write_text(
        formal_verdict_artifact(controller, verdict_id=novelty_verdict_id),
        encoding="utf-8",
    )
    controller.complete_current_phase()
    accept_formal(controller, novelty_verdict_id, "claude-sonnet-4")
    assert controller.status()["scientific_core"]["current_phase"] == (
        "top_venue_method_strength_gate"
    )

    for history_name in ("METHOD_PRINCIPLES.jsonl", "METHOD_TEST_EVIDENCE.jsonl"):
        (tmp_path / "idea-stage" / history_name).write_text("{}\n", encoding="utf-8")
    controller.start_current_phase()
    top_request = run_state._find_phase(
        controller.status(), "top_venue_method_strength_gate"
    )["review_request"]
    assert "idea-stage/METHOD_PRINCIPLES.jsonl" in top_request["artifact_bindings"]
    assert "idea-stage/METHOD_TEST_EVIDENCE.jsonl" in top_request["artifact_bindings"]
    top_venue_verdict_id = "top-venue-ready-after-packet"
    top_venue_path = (
        tmp_path / "idea-stage" / "TOP_VENUE_METHOD_STRENGTH_VERDICT.json"
    )
    top_venue_path.write_text(
        json.dumps(
            top_venue_verdict_artifact(
                controller, verdict_id=top_venue_verdict_id
            )
        )
        + "\n",
        encoding="utf-8",
    )
    controller.complete_current_phase()
    accept_formal(controller, top_venue_verdict_id, "claude-sonnet-4")
    state = controller.status()
    assert state["scientific_core"]["current_phase"] == "final_method_human_acceptance"
    human_request = controller.validate_human_gate_request("method_acceptance")
    assert "idea-stage/TOP_VENUE_METHOD_STRENGTH_VERDICT.json" in (
        human_request["artifact_bindings"]
    )
    approve(controller, "method_acceptance")
    assert controller.status()["scientific_core"]["status"] == (
        "METHOD_CONFIRMED_AWAITING_USER_VALIDATION"
    )


def reach_top_venue_gate(controller: ARISController) -> dict:
    activate_method_refinement_review(controller)
    method_verdict_id = "method-ready-for-top-venue"
    (controller.root / "refine-logs" / "FINAL_BLIND_REVIEW.md").write_text(
        formal_verdict_artifact(controller, verdict_id=method_verdict_id),
        encoding="utf-8",
    )
    controller.complete_current_phase()
    accept_formal(controller, method_verdict_id, "claude-sonnet-4")

    controller.start_current_phase()
    novelty_verdict_id = "novel-for-top-venue"
    (
        controller.root / "idea-stage" / "FINAL_METHOD_NOVELTY_VERDICT.md"
    ).write_text(
        formal_verdict_artifact(controller, verdict_id=novelty_verdict_id),
        encoding="utf-8",
    )
    controller.complete_current_phase()
    accept_formal(controller, novelty_verdict_id, "claude-sonnet-4")
    assert controller.status()["scientific_core"]["current_phase"] == (
        "top_venue_method_strength_gate"
    )
    controller.start_current_phase()
    return run_state._find_phase(
        controller.status(), "top_venue_method_strength_gate"
    )["review_request"]


@pytest.mark.parametrize(
    ("decision", "target", "selected_remains"),
    [
        ("REVISE_METHOD", "method_refinement", True),
        ("RETHINK_PRINCIPLE", "method_design", False),
        ("REOPEN_RCA", "root_cause_analysis", False),
        ("REOPEN_NECESSITY", "problem_necessity", False),
        ("REDEFINE_PROBLEM", "problem_generation", False),
    ],
)
def test_top_venue_returns_reuse_canonical_lifecycle(
    tmp_path: Path, decision: str, target: str, selected_remains: bool
) -> None:
    controller = confirmed_validation_controller(tmp_path)
    reach_top_venue_gate(controller)
    verdict_id = f"top-venue-{decision.lower()}"
    verdict_path = (
        tmp_path / "idea-stage" / "TOP_VENUE_METHOD_STRENGTH_VERDICT.json"
    )
    verdict_path.write_text(
        json.dumps(
            top_venue_verdict_artifact(
                controller, verdict_id=verdict_id, decision=decision
            )
        )
        + "\n",
        encoding="utf-8",
    )
    controller.complete_current_phase()
    attest_current_review(
        controller, verdict_id, "claude-sonnet-4", decision=decision
    )
    returned = controller.return_current_phase(verdict_id, "claude-sonnet-4")

    core = returned["scientific_core"]
    assert core["current_phase"] == target
    assert core["return_history"][-1]["return_target"] == target
    selected_path = tmp_path / "idea-stage" / "SELECTED_PRINCIPLE.yaml"
    assert selected_path.exists() is selected_remains
    assert (
        "idea-stage/SELECTED_PRINCIPLE.yaml" in core["accepted_artifacts"]
    ) is selected_remains


def test_top_venue_ready_cannot_hide_a_hard_dimension_fail(tmp_path: Path) -> None:
    controller = confirmed_validation_controller(tmp_path)
    reach_top_venue_gate(controller)
    payload = top_venue_verdict_artifact(
        controller, verdict_id="invalid-ready-with-fail"
    )
    payload["dimensions"]["minimality"]["judgment"] = "FAIL"
    (
        tmp_path / "idea-stage" / "TOP_VENUE_METHOD_STRENGTH_VERDICT.json"
    ).write_text(json.dumps(payload) + "\n", encoding="utf-8")

    with pytest.raises(ControllerError, match="requires PASS on every hard dimension"):
        controller.complete_current_phase()
    assert controller.status()["scientific_core"]["current_phase"] == (
        "top_venue_method_strength_gate"
    )


def test_top_venue_acceptance_consumes_the_reviewer_owned_dimension_payload(
    tmp_path: Path,
) -> None:
    controller = confirmed_validation_controller(tmp_path)
    request = reach_top_venue_gate(controller)
    verdict_id = "reviewer-owned-top-venue"
    payload = top_venue_verdict_artifact(controller, verdict_id=verdict_id)
    path = tmp_path / "idea-stage" / "TOP_VENUE_METHOD_STRENGTH_VERDICT.json"
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    controller.complete_current_phase()

    altered = deepcopy(payload)
    altered["dimensions"]["minimality"]["rationale"] = "Different rationale."
    attest(controller, request["required_reviewer_role"], altered)
    with pytest.raises(
        ControllerError,
        match="differs from the reviewer payload",
    ):
        controller.accept_current_phase(verdict_id, "claude-sonnet-4")


def test_top_venue_no_go_reuses_existing_scientific_terminal(tmp_path: Path) -> None:
    controller = confirmed_validation_controller(tmp_path)
    request = reach_top_venue_gate(controller)
    no_go = {
        "subject": {
            "final_method_id": "FM-1",
            "failed_dimensions": ["problem_value"],
        },
        "reason": "Current formal Evidence establishes a fatal scientific weakness.",
        "evidence_refs": ["E1"],
        "excluded_recoveries": [
            "REVISE_METHOD",
            "RETHINK_PRINCIPLE",
            "REOPEN_RCA",
            "REOPEN_NECESSITY",
            "REDEFINE_PROBLEM",
        ],
    }
    verdict_id = "top-venue-no-go"
    payload = top_venue_verdict_artifact(
        controller,
        verdict_id=verdict_id,
        decision="NO_GO",
        no_go=no_go,
    )
    path = tmp_path / "idea-stage" / "TOP_VENUE_METHOD_STRENGTH_VERDICT.json"

    incomplete = deepcopy(payload)
    incomplete["no_go"]["excluded_recoveries"].remove("REVISE_METHOD")
    path.write_text(json.dumps(incomplete) + "\n", encoding="utf-8")
    with pytest.raises(ControllerError, match="exclude every reasonable fixed return"):
        controller.complete_current_phase()

    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    controller.complete_current_phase()
    attest(controller, request["required_reviewer_role"], payload)
    state = controller.terminate_scientific_core(
        verdict_id, "claude-sonnet-4"
    )
    core = state["scientific_core"]
    assert core["status"] == "SCIENTIFIC_NO_GO"
    assert core["current_phase"] is None
    assert core["validation_entry"] is None
    assert core["no_go_record"]["no_go"] == no_go


@pytest.mark.parametrize(
    "fatality,terminal_allowed",
    [
        ("FATAL_UNRECOVERABLE", True),
        ("FATAL_REPAIRABLE_OR_RESTRICTED", False),
    ],
)
def test_method_refinement_no_go_requires_unrecoverable_fatal_feasibility(
    tmp_path: Path, fatality: str, terminal_allowed: bool
) -> None:
    controller = confirmed_validation_controller(tmp_path)
    with controller._store.mutate() as state:
        core = state["scientific_core"]
        core["status"] = "ACTIVE"
        core["current_phase"] = "method_refinement"
        core["validation_entry"] = None
        core["approval_request"] = None
        state["research_lit"]["current_stage"] = "LANDSCAPE_ACCEPTED"
        for phase_name in (
            "method_refinement", "final_method_novelty_gate",
            "top_venue_method_strength_gate",
            "final_method_human_acceptance",
        ):
            phase = run_state._find_phase(state, phase_name)
            phase["status"] = "pending"
            phase["review_request"] = None
        for raw_path in (
            "refine-logs/FINAL_PROPOSAL.md",
            "refine-logs/FINAL_BLIND_REVIEW.md",
            "idea-stage/FINAL_METHOD_NOVELTY_VERDICT.md",
            "idea-stage/TOP_VENUE_METHOD_STRENGTH_VERDICT.json",
            "idea-stage/IDEA_REPORT.md",
        ):
            core["accepted_artifacts"].pop(raw_path, None)

    controller.start_current_phase()
    (tmp_path / "refine-logs" / "REFINE_STATE.json").write_text(
        '{"status":"final_review"}\n', encoding="utf-8"
    )
    packet_path = write_batch4_final_packet(controller)
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    restriction_ids = [] if terminal_allowed else ["RESTRICT-1"]
    if not terminal_allowed:
        packet["failure_and_applicability_boundaries"].append(
            {
                "boundary_id": "BND-RESTRICT-1",
                "boundary_type": "CLAIM_RESTRICTION",
                "boundary": "restrict the claim to the observable envelope",
                "source_refs": ["DEBT-1"],
            }
        )
        packet["final_scientific_delta_claim"]["claim_elements"][0][
            "boundary_refs"
        ].append("BND-RESTRICT-1")
    packet["feasibility_closure"] = {
        "supported_conditions": ["observable in the accepted envelope"],
        "unresolved_feasibility_debts": [
            {
                "debt_id": "DEBT-1",
                "dimension": "observability",
                "debt": "fatal feasibility debt",
                "fatal": True,
                "evidence_refs": ["E1"],
                "restriction_ids": restriction_ids,
                "repair_disposition": (
                    "EVIDENCE_EXCLUDED" if terminal_allowed else "REPAIR_AVAILABLE"
                ),
                "claim_restriction_disposition": (
                    "CANNOT_PRESERVE_CORE_SEED"
                    if terminal_allowed
                    else "RESTRICTION_PRESERVES_SEED"
                ),
                "excluded_recovery_evidence_refs": ["E1"] if terminal_allowed else [],
            }
        ],
        "claim_restrictions": (
            []
            if terminal_allowed
            else [
                {
                    "restriction_id": "RESTRICT-1",
                    "claim_element_ids": ["CLAIM-1"],
                    "debt_ids": ["DEBT-1"],
                    "boundary_id": "BND-RESTRICT-1",
                }
            ]
        ),
        "fatality_disposition": fatality,
    }
    packet_path.write_text(
        json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    request = controller.refresh_current_review_request()
    no_go = {
        "subject": {
            "final_method_id": "FM-1",
            "fatal_feasibility_debt_ids": ["DEBT-1"],
        },
        "reason": "the fatal debt destroys the core seed",
        "evidence_refs": ["E1"],
        "excluded_recoveries": [
            "REVISE", "RETHINK", "HOLD", "RCA_CONFLICT",
            "NECESSITY_CONFLICT", "PROBLEM_CONFLICT",
        ],
    }
    verdict_id = f"no-go-{fatality.lower()}"
    metadata = {
        "schema_version": 1,
        "run_id": controller.run_id,
        "review_request_id": request["id"],
        "reviewer": "codex-gpt-5.6-sol",
        "verdict_id": verdict_id,
        "decision": "NO_GO",
        "reviewed_artifact_hashes": request["artifact_bindings"],
        "no_go": no_go,
    }
    (tmp_path / "refine-logs" / "FINAL_BLIND_REVIEW.md").write_text(
        "# Final review\n\n```json\n" + json.dumps(metadata) + "\n```\n",
        encoding="utf-8",
    )

    if terminal_allowed:
        incomplete = deepcopy(metadata)
        incomplete["no_go"] = deepcopy(no_go)
        incomplete["no_go"]["excluded_recoveries"] = [
            "REVISE", "RETHINK", "HOLD", "RCA_CONFLICT",
        ]
        (tmp_path / "refine-logs" / "FINAL_BLIND_REVIEW.md").write_text(
            "# Final review\n\n```json\n" + json.dumps(incomplete) + "\n```\n",
            encoding="utf-8",
        )
        with pytest.raises(ControllerError, match="exclude every reasonable fixed return"):
            controller.complete_current_phase()
        (tmp_path / "refine-logs" / "FINAL_BLIND_REVIEW.md").write_text(
            "# Final review\n\n```json\n" + json.dumps(metadata) + "\n```\n",
            encoding="utf-8",
        )

    if not terminal_allowed:
        with pytest.raises(ControllerError, match="fatal-unrecoverable"):
            controller.complete_current_phase()
        return

    controller.complete_current_phase()
    attest(controller, request["required_reviewer_role"], metadata)
    state = controller.terminate_scientific_core(
        verdict_id, "codex-gpt-5.6-sol"
    )
    assert state["scientific_core"]["status"] == "SCIENTIFIC_NO_GO"
    assert state["scientific_core"]["current_phase"] is None
    assert state["scientific_core"]["validation_entry"] is None
    assert state["scientific_core"]["no_go_record"]["no_go"] == no_go


def test_tampering_accepted_policy_or_field_map_blocks_transition(tmp_path: Path) -> None:
    controller = start_controller(tmp_path)
    policy = tmp_path / "idea-stage" / "SOURCE_ADMISSION_POLICY.yaml"
    policy.write_text(policy.read_text(encoding="utf-8") + "\n# changed", encoding="utf-8")
    with pytest.raises(ControllerError, match="changed after validation"):
        controller.execute_query("test field", "fake", lambda _: [])

    other = start_controller(tmp_path / "other")
    digest, request_id = reach_coverage(other)
    (other.root / "idea-stage" / "ACTIVE_FIELD_MAP.md").write_text("tampered", encoding="utf-8")
    with pytest.raises(ControllerError, match="changed after validation"):
        other.submit_coverage_review(coverage_review(digest, request_id))


def test_alternate_workflow_and_legacy_in_place_conversion_are_rejected(tmp_path: Path) -> None:
    alternate = tmp_path / "alternate.yaml"
    alternate.write_text(WORKFLOW.read_text(encoding="utf-8"), encoding="utf-8")
    with pytest.raises(ControllerError, match="canonical"):
        ARISController.start(tmp_path, "alternate", alternate, executor="codex")
    run_state.start_run(tmp_path, "legacy", ["landscape"], executor="codex")
    with pytest.raises(ControllerError, match="legacy run"):
        ARISController.start(tmp_path, "legacy", executor="codex")


def test_workflow_hash_mismatch_requires_compatible_migration(tmp_path: Path) -> None:
    write_policy(tmp_path)
    controller = ARISController.start(tmp_path, "upgrade", executor="codex")
    state = run_state._load(tmp_path, "upgrade")
    old_sha256 = "1" * 64
    state["workflow_sha256"] = old_sha256
    state["workflow"]["workflow_id"] = "semantically-different-workflow"
    run_state._save(tmp_path, "upgrade", state)
    with pytest.raises(ValueError, match="canonical workflow"):
        controller.status()
    assert not hasattr(ARISController, "upgrade_workflow_at_initial_gate")
    parser = build_parser()
    commands = parser._subparsers._group_actions[0].choices
    assert "upgrade-workflow" not in commands
    assert "migrate-workflow" in commands
    migrated = controller.migrate_workflow_if_compatible()
    restored = controller.status()
    assert migrated["migration"]["from_workflow_sha256"] == old_sha256
    assert migrated["migration"]["from_workflow_id"] == "semantically-different-workflow"
    assert migrated["migration"]["to_workflow_id"] == controller.workflow["workflow_id"]
    assert restored["workflow"] == controller.workflow
    assert restored["workflow_sha256"] == controller.workflow_sha256


def test_compatible_workflow_migration_preserves_run_history(tmp_path: Path) -> None:
    controller = start_controller(tmp_path)
    state = run_state._load(tmp_path, controller.run_id)
    executed_landscape = deepcopy(state["phases"][0])
    state["phases"] = [
        executed_landscape,
        {"phase": "legacy_pending_suffix", "status": "pending", "updated": None},
    ]
    state["workflow_sha256"] = "1" * 64
    state["workflow"]["scientific_core"]["incremental_literature"]["permitted_phases"] = [
        "method_design"
    ]
    run_state._save(tmp_path, controller.run_id, state)

    migrated = controller.migrate_workflow_if_compatible()

    assert migrated["migration"]["from_workflow_sha256"] == "1" * 64
    assert migrated["migration"]["to_workflow_sha256"] == controller.workflow_sha256
    assert migrated["migration"]["executed_phases"] == ["landscape"]
    restored = controller.status()
    assert restored["workflow"] == controller.workflow
    assert restored["workflow_migrations"][-1] == migrated["migration"]
    assert restored["phases"][0] == executed_landscape
    assert [phase["phase"] for phase in restored["phases"]] == [
        phase["phase"] for phase in controller.workflow["phases"]
    ]
    assert all(phase["status"] == "pending" for phase in restored["phases"][1:])


def test_compatible_migration_allows_new_identity_and_unexecuted_suffix_mapping(
    tmp_path: Path,
) -> None:
    controller = start_controller(tmp_path)
    state = run_state._load(tmp_path, controller.run_id)
    state["workflow_sha256"] = "1" * 64
    state["workflow"]["workflow_id"] = "idea-discovery-v3"
    for phase_name in ("principle_human_selection", "principle_test_design"):
        state["workflow"]["scientific_core"]["phases"].remove(phase_name)
        state["workflow"]["phases"] = [
            spec for spec in state["workflow"]["phases"] if spec["phase"] != phase_name
        ]
        state["phases"] = [
            phase for phase in state["phases"] if phase["phase"] != phase_name
        ]
    state["workflow"]["artifact_manifest"]["method_design_packet"] = (
        "idea-stage/LEGACY_PENDING_METHOD_PACKET.json"
    )
    run_state._save(tmp_path, controller.run_id, state)

    migrated = controller.migrate_workflow_if_compatible()
    restored = controller.status()
    assert migrated["migration"]["from_workflow_sha256"] == "1" * 64
    assert restored["workflow"]["workflow_id"] == controller.workflow["workflow_id"]
    assert restored["workflow"]["artifact_manifest"]["method_design_packet"] == (
        controller.workflow["artifact_manifest"]["method_design_packet"]
    )
    assert restored["workflow"]["workflow_id"] == "idea-discovery-v4"
    assert restored["scientific_core"]["selected_for_testing"] is None
    phase_names = [phase["phase"] for phase in restored["phases"]]
    method_index = phase_names.index("method_design")
    assert phase_names[method_index : method_index + 5] == [
        "method_design",
        "principle_human_selection",
        "principle_test_design",
        "principle_test_human_approval",
        "principle_evaluation",
    ]


def test_compatible_migration_skips_completed_non_gate_done_prefix(
    tmp_path: Path,
) -> None:
    controller = controller_at_method_design(tmp_path)
    state = run_state._load(tmp_path, controller.run_id)
    state["workflow_sha256"] = "1" * 64
    run_state._save(tmp_path, controller.run_id, state)

    controller.migrate_workflow_if_compatible()

    restored = controller.status()
    assert restored["scientific_core"]["current_phase"] == "method_design"
    assert "start_phase" in controller.allowed_actions()


def test_compatible_workflow_migration_rejects_changed_literature_protocol(tmp_path: Path) -> None:
    controller = start_controller(tmp_path)
    state = run_state._load(tmp_path, controller.run_id)
    state["workflow_sha256"] = "1" * 64
    state["workflow"]["research_lit"]["allowed_actions"]["METADATA_RETRIEVAL"].append(
        "unreviewed_action"
    )
    run_state._save(tmp_path, controller.run_id, state)

    with pytest.raises(ControllerError, match="research_lit"):
        controller.migrate_workflow_if_compatible()


def test_structural_paper_reading_migration_reuses_completed_events_and_resynthesizes_map(
    tmp_path: Path,
) -> None:
    controller = start_controller(tmp_path)
    reach_reading(controller)
    read = controller.read_full_text("P1", "fake-paper", lambda _: "full paper")
    source = tmp_path / "source-materials" / "legacy-p1.txt"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("full paper", encoding="utf-8")
    active_map = tmp_path / "idea-stage" / "ACTIVE_FIELD_MAP.md"
    active_map.write_text(render_field_map(field_map()), encoding="utf-8")
    fulltext_before = controller.status()["research_lit"]["fulltext_count"]
    read_events_before = controller.status()["research_lit"]["read_events"]

    with controller._store.mutate() as state:
        research = state["research_lit"]
        research["papers"]["P1"]["user_fulltext"] = {
            "paper_id": "P1",
            "source_path": "source-materials/legacy-p1.txt",
            "source_sha256": read["content_sha256"],
            "media_type": "text/plain",
        }
        research["active_reading_session"] = None
        research["initial_screened_corpus_ids"] = None
        research["initial_field_map_binding"] = None
        research["initial_screening_context"] = None
        research["formal_primary_selection"] = None
        research["landscape_evidence_ids"] = []
        research["accepted_artifacts"]["active_field_map"] = {
            "path": "idea-stage/ACTIVE_FIELD_MAP.md",
            "validator_result": "PASS",
            "sha256": sha256_file(active_map),
            "accepted_at": "2026-08-12T00:00:00Z",
            "author_role": "main_research_agent",
        }
        screening_context = controller._active_screening_context(research)
        prior_decision = deepcopy(research["papers"]["P1"]["context_decisions"][-1])
        prior_decision.update({
            "decision_id": "admission-current-structural-migration",
            "context": {
                **screening_context,
                "paper_id": "P1",
                "decision_targets": [],
            },
        })
        research["papers"]["P1"]["context_decisions"].append(prior_decision)
        state["workflow"] = json.loads(json.dumps(state["workflow"]))
        state["workflow"]["research_lit"]["allowed_agents"]["PAPER_READING"] = [
            "paper_reader"
        ]
        state["workflow_sha256"] = "1" * 64

    migrated = controller.migrate_workflow_if_compatible()
    migrated_state = controller.status()["research_lit"]
    assert migrated["migration"]["migration_type"] == "STRUCTURAL_PAPER_READING_CONTINUATION"
    assert migrated_state["current_stage"] == "PAPER_READING"
    assert migrated_state["active_reading_session"]["paper_ids"] == ["P1"]
    assert migrated_state["initial_field_map_binding"] is None
    assert migrated_state["formal_primary_selection"] is None

    replayed = controller.materialize_completed_read_event("P1", read["read_event_id"])
    assert replayed["paper_id"] == "P1"
    assert replayed["read_event_id"] == read["read_event_id"]
    assert replayed["content_sha256"] == read["content_sha256"]
    assert replayed["content"] == "full paper"
    assert controller.status()["research_lit"]["read_events"] == read_events_before
    assert controller.status()["research_lit"]["fulltext_count"] == fulltext_before

    controller.submit_evidence_card("P1", card(replayed))
    assert controller.status()["research_lit"]["read_events"] == read_events_before
    assert controller.status()["research_lit"]["fulltext_count"] == fulltext_before
    controller.finish_reading()
    assert controller.current_stage() == "FIELD_SYNTHESIS"

    controller.submit_field_map(field_map("PARTIAL"))
    continued = controller.status()["research_lit"]
    assert continued["current_stage"] == "QUERY_PLANNING"
    assert continued["initial_field_map_binding"] is None
    assert continued["formal_primary_selection"] is None
    assert continued["last_coverage_status"] == "PARTIAL"


def test_materialize_completed_read_event_cli_emits_original_reader_binding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    controller = start_controller(tmp_path)
    reach_reading(controller)
    read = controller.read_full_text("P1", "fake-paper", lambda _: "full paper")
    source = tmp_path / "source-materials" / "replay.txt"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("full paper", encoding="utf-8")
    with controller._store.mutate() as state:
        state["research_lit"]["papers"]["P1"]["user_fulltext"] = {
            "paper_id": "P1",
            "source_path": "source-materials/replay.txt",
            "source_sha256": read["content_sha256"],
            "media_type": "text/plain",
        }

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "arisctl",
            "--root",
            str(tmp_path),
            "materialize-completed-read-event",
            controller.run_id,
            "P1",
            read["read_event_id"],
        ],
    )
    assert main() == 0
    result = json.loads(capfd.readouterr().out)
    assert result == {
        "paper_id": "P1",
        "read_event_id": read["read_event_id"],
        "content_sha256": read["content_sha256"],
        "content": "full paper",
    }


def test_legacy_migration_archives_history_and_bootstraps_clean_formal_run(tmp_path: Path) -> None:
    write_policy(tmp_path)
    idea = tmp_path / "idea-stage"
    (idea / "SEARCH_LEDGER.jsonl").write_text('{"legacy": true}\n', encoding="utf-8")
    (idea / "ACTIVE_FIELD_MAP.md").write_text("# legacy map", encoding="utf-8")
    manifest = tmp_path / ".aris" / "LEGACY_MIGRATION.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        json.dumps({"schema_version": 1, "migration_status": "legacy_archive_classified"}),
        encoding="utf-8",
    )
    controller = ARISController.migrate_legacy(
        tmp_path, "formal-v2", executor="codex-gpt-5.6-sol"
    )
    assert controller.current_stage() == "WAITING_FOR_HUMAN"
    archive = tmp_path / ".aris" / "legacy" / "formal-v2" / "idea-stage"
    assert (archive / "SEARCH_LEDGER.jsonl").is_file()
    assert (archive / "ACTIVE_FIELD_MAP.md").is_file()
    assert not (idea / "SEARCH_LEDGER.jsonl").exists()
    assert not (idea / "ACTIVE_FIELD_MAP.md").exists()
    assert (idea / "SOURCE_ADMISSION_POLICY.yaml").is_file()
    updated = json.loads(manifest.read_text(encoding="utf-8"))
    assert updated["migration_status"] == "formal_rerun_bootstrapped"
    assert updated["formal_run_controller_compliance"] is True
    assert updated["historical_artifacts_formal_controller_compliance"] is False


def test_metadata_and_user_supplied_status_cannot_be_relabelled_by_admit(tmp_path: Path) -> None:
    controller = start_controller(tmp_path)
    assert not hasattr(controller, "register_metadata")
    assert "user_supplied" not in inspect.signature(controller.decide_admission).parameters
    source = tmp_path / "source-materials" / "user-paper.txt"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("user supplied paper", encoding="utf-8")
    supplied = metadata("USER1")
    supplied["source_path"] = "source-materials/user-paper.txt"
    row = controller.register_user_source(supplied)
    assert row["source_origin"] == "user_supplied"
    assert controller.decide_admission("USER1", screening_in_scope=True) == "USER_SUPPLIED_READ"


def test_admission_can_use_ledgered_identity_verification_gateway(tmp_path: Path) -> None:
    controller = start_controller(tmp_path)
    pending = metadata()
    pending["identity_status"] = "verify_pending"
    pending["discovery_provider"] = "serpapi_google_scholar"
    controller.execute_query("test field", "fake", lambda _: [pending])
    calls: list[str] = []

    def verify(paper: dict) -> dict:
        calls.append(paper["paper_id"])
        return {
            "identity_status": "verified",
            "identity_provider": "crossref_metadata",
            "title": paper["title"],
            "authors": paper["authors"],
            "year": paper["year"],
            "venue": paper["venue"],
            "doi_or_stable_url": paper["doi_or_stable_url"],
        }

    assert controller.decide_admission(
        "P1", screening_in_scope=True, identity_verifier=verify
    ) == "ADMIT_FOR_READING"
    assert calls == ["P1"]
    paper = controller.status()["research_lit"]["papers"]["P1"]
    assert paper["identity_status"] == "verified"
    assert paper["identity_verification_status"] == "complete"
    assert paper["source_origin"] == "gateway_discovery"
    assert paper["discovery_provider"] == "serpapi_google_scholar"
    ledger = (tmp_path / "idea-stage" / "SEARCH_LEDGER.jsonl").read_text(
        encoding="utf-8"
    )
    assert '"action": "metadata_identity_verification"' in ledger


def test_coverage_audit_rejects_corrupted_system_ledger(tmp_path: Path) -> None:
    controller = start_controller(tmp_path)
    digest, request_id = reach_coverage(controller)
    ledger_path = tmp_path / "idea-stage" / "SEARCH_LEDGER.jsonl"
    ledger = ledger_path.read_text(encoding="utf-8")
    ledger_path.write_text("{}\n", encoding="utf-8")
    review = coverage_review(digest, request_id)
    attest(controller, "coverage_reviewer", review)
    attestation_path = reviews.review_attestation_path(
        controller.root, controller.run_id, "coverage_reviewer", request_id
    )
    with pytest.raises(
        ControllerError,
        match="coverage validator FAIL|current artifact bindings",
    ):
        controller.submit_coverage_review(review)
    assert attestation_path.is_file()
    assert not attestation_path.with_suffix(".consumed.json").exists()
    assert run_state._find_phase(controller.status(), "landscape")["status"] == "running"
    ledger_path.write_text(ledger, encoding="utf-8")
    controller.submit_coverage_review(review)
    assert not attestation_path.exists()
    assert attestation_path.with_suffix(".consumed.json").is_file()


def test_legacy_mutators_and_complete_looking_markdown_do_not_advance(tmp_path: Path) -> None:
    controller = start_controller(tmp_path)
    for mutation in (
        lambda: run_state.set_status(tmp_path, "run-1", "landscape", "done"),
        lambda: run_state.accept(tmp_path, "run-1", "landscape", "v", "deterministic:test", force=True),
        lambda: run_state.approve_human(tmp_path, "run-1", "scope_human_approval", "spoof"),
    ):
        with pytest.raises(ValueError, match="Controller-managed"):
            mutation()
    (tmp_path / "idea-stage" / "FINAL_LANDSCAPE.md").write_text("# Complete", encoding="utf-8")
    assert controller.current_stage() == "METADATA_RETRIEVAL"


def test_hook_protects_formal_boundaries_without_allowlisting_research_execution() -> None:
    hook = REPO / ".codex" / "hooks" / "pre_tool_use_policy.py"
    blocked = (
        "python -c \"controller.human_approve('scope', 'approve')\"",
        "python -c \"controller.request_source_policy_revision()\"",
        "python -c \"from arisctl import ARISController; ARISController.start('.')\"",
        "python -c \"from tools import run_state; run_state._save('.', 'run-1', {})\"",
        "python -c \"from arisctl.gateways import append_jsonl; append_jsonl('x', {})\"",
        "curl https://example.com/paper.pdf > source-materials/paper.pdf",
        "Set-Content .aris/runs/run-1.json spoof",
        "Set-Content idea-stage/SEARCH_LEDGER.jsonl spoof",
        "Set-Content .aris/canonical/run/map.json spoof",
    )
    for command in blocked:
        result = subprocess.run(
            [sys.executable, str(hook)],
            input=json.dumps({"tool_name": "Bash", "tool_input": {"command": command}}),
            text=True,
            capture_output=True,
            check=False,
        )
        payload = json.loads(result.stdout)
        assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"

    # Network retrieval becomes formal only when it tries to enter a protected
    # evidence surface.  A bare web tool result has no canonical effect; the
    # Controller rejects unregistered sources when formal evidence is admitted.
    for network_tool, tool_input in (
        ("WebSearch", {"query": "CUDA error documentation"}),
        ("WebFetch", {"url": "https://example.com/docs"}),
    ):
        result = subprocess.run(
            [sys.executable, str(hook)],
            input=json.dumps({"tool_name": network_tool, "tool_input": tool_input}),
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0
        assert result.stdout == ""

    for command in (
        "Get-Item source-materials/paper.pdf",
        "Get-FileHash source-materials/paper.pdf",
        "Get-Content .aris/runs/run-1.json",
        "pytest -q tests/test_aris_controller.py",
        "python scripts/simulate.py --steps 10",
        "python train.py --epochs 1",
        "git status --short",
        "ssh gpu.example.org 'python train.py --epochs 1'",
        "nvidia-smi",
    ):
        result = subprocess.run(
            [sys.executable, str(hook)],
            input=json.dumps({"tool_name": "Bash", "tool_input": {"command": command}}),
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0
        assert result.stdout == ""

    hooks = json.loads((REPO / ".codex" / "hooks.json").read_text(encoding="utf-8"))
    assert hooks["hooks"]["SubagentStop"][0]["matcher"] == ".*"
    assert hooks["hooks"]["Stop"][0]["matcher"] == ".*"
    exact = subprocess.run(
        [sys.executable, str(hook)],
        input=json.dumps(
            {
                "tool_name": "Bash",
                "tool_input": {
                    "command": "python -m arisctl human-approve run-1 source_policy_approval --decision approve"
                },
            }
        ),
        text=True,
        capture_output=True,
        check=False,
    )
    assert exact.returncode == 0
    assert exact.stdout == ""
    revision = subprocess.run(
        [sys.executable, str(hook)],
        input=json.dumps(
            {
                "tool_name": "Bash",
                "tool_input": {
                    "command": "python -m arisctl request-source-policy-revision run-1"
                },
            }
        ),
        text=True,
        capture_output=True,
        check=False,
    )
    assert revision.returncode == 0
    assert revision.stdout == ""
    problem_revision = subprocess.run(
        [sys.executable, str(hook)],
        input=json.dumps(
            {
                "tool_name": "Bash",
                "tool_input": {
                    "command": "python -m arisctl revise-problem run-1 --reason 'new evidence'"
                },
            }
        ),
        text=True,
        capture_output=True,
        check=False,
    )
    assert problem_revision.returncode == 0
    assert problem_revision.stdout == ""
    gateway = subprocess.run(
        [sys.executable, str(hook)],
        input=json.dumps(
            {
                "tool_name": "Bash",
                "tool_input": {"command": "python -m arisctl query run-1 topic"},
            }
        ),
        text=True,
        capture_output=True,
        check=False,
    )
    assert gateway.returncode == 0
    assert gateway.stdout == ""
    gateway_with_root = subprocess.run(
        [sys.executable, str(hook)],
        input=json.dumps(
            {
                "tool_name": "Bash",
                "tool_input": {
                    "command": "python -m arisctl --root D:/project query run-1 topic"
                },
            }
        ),
        text=True,
        capture_output=True,
        check=False,
    )
    assert gateway_with_root.returncode == 0
    assert gateway_with_root.stdout == ""


def test_hook_allows_protected_path_literals_in_ordinary_write_content() -> None:
    hook = REPO / ".codex" / "hooks" / "pre_tool_use_policy.py"
    ordinary_path = "notes/ordinary.md"
    protected_path_text = "See source-materials/paper.pdf and .aris/runs/run-1.json."
    payloads = (
        ("Write", {"file_path": ordinary_path, "content": protected_path_text}),
        (
            "Edit",
            {
                "file_path": ordinary_path,
                "old_string": "old",
                "new_string": protected_path_text,
            },
        ),
        (
            "apply_patch",
            {
                "patch": "\n".join(
                    (
                        "*** Begin Patch",
                        f"*** Update File: {ordinary_path}",
                        "@@",
                        f"+{protected_path_text}",
                        "*** End Patch",
                    )
                )
            },
        ),
    )
    for tool_name, tool_input in payloads:
        result = subprocess.run(
            [sys.executable, str(hook)],
            input=json.dumps({"tool_name": tool_name, "tool_input": tool_input}),
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0
        assert result.stdout == ""


def test_hook_still_denies_protected_write_targets() -> None:
    hook = REPO / ".codex" / "hooks" / "pre_tool_use_policy.py"
    payloads = (
        ("Write", {"file_path": ".aris/runs/run-1.json", "content": "{}"}),
        (
            "Edit",
            {
                "file_path": "source-materials/paper.pdf",
                "old_string": "old",
                "new_string": "new",
            },
        ),
        (
            "apply_patch",
            {
                "patch": "\n".join(
                    (
                        "*** Begin Patch",
                        "*** Update File: .aris/canonical/run/map.json",
                        "@@",
                        "+changed",
                        "*** End Patch",
                    )
                )
            },
        ),
    )
    for tool_name, tool_input in payloads:
        result = subprocess.run(
            [sys.executable, str(hook)],
            input=json.dumps({"tool_name": tool_name, "tool_input": tool_input}),
            text=True,
            capture_output=True,
            check=False,
        )
        payload = json.loads(result.stdout)
        assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_codex_configuration_registers_all_declared_subagents_and_ui_prompt_rules() -> None:
    agents = {path.stem for path in (REPO / ".codex" / "agents").glob("*.toml")}
    assert agents == {
        "paper_reader",
        "coverage_reviewer",
        "independent_problem_reviewer",
        "independent_novelty_reviewer",
        "independent_root_cause_reviewer",
        "independent_method_reviewer",
        "result_to_claim_reviewer",
    }
    config = (REPO / ".codex" / "config.toml").read_text(encoding="utf-8")
    assert "query_planner" not in config and "field_synthesizer" not in config
    assert 'approval_policy = "on-request"' in config
    for role in agents - {"paper_reader", "coverage_reviewer"}:
        assert f"[agents.{role}]" in config
        agent_config = (REPO / ".codex" / "agents" / f"{role}.toml").read_text(
            encoding="utf-8"
        )
        assert 'sandbox_mode = "read-only"' in agent_config
        assert 'approval_policy = "never"' in agent_config
        assert "review_request_id" in agent_config
        assert "reviewed_artifact_hashes" in agent_config
    hooks = json.loads((REPO / ".codex" / "hooks.json").read_text(encoding="utf-8"))
    matcher = hooks["hooks"]["SubagentStop"][0]["matcher"]
    assert matcher == ".*"
    assert hooks["hooks"]["Stop"][0]["matcher"] == ".*"
    rules = (REPO / ".codex" / "rules" / "aris.rules").read_text(encoding="utf-8")
    assert 'decision = "prompt"' in rules
    workflow = json.loads(WORKFLOW.read_text(encoding="utf-8"))
    assert workflow["research_lit"]["stages"][:2] == [
        "SOURCE_POLICY_DRAFTING",
        "WAITING_FOR_HUMAN",
    ]
    assert workflow["research_lit"]["allowed_actions"][
        "SOURCE_POLICY_DRAFTING"
    ] == ["submit_source_admission_policy"]
    assert workflow["research_lit"]["allowed_agents"][
        "SOURCE_POLICY_DRAFTING"
    ] == ["main_research_agent"]
    assert workflow["research_lit"]["allowed_actions"]["WAITING_FOR_HUMAN"] == [
        "human_approve", "request_source_policy_revision"
    ]
    assert workflow["research_lit"]["allowed_agents"]["WAITING_FOR_HUMAN"] == []
    assert workflow["research_lit"]["allowed_agents"]["QUERY_PLANNING"] == ["main_research_agent"]
    assert workflow["research_lit"]["allowed_agents"]["FIELD_SYNTHESIS"] == ["main_research_agent"]
    assert workflow["scientific_core"]["phases"][0] == "problem_generation"
    assert workflow["scientific_core"]["completion_state"] == (
        "METHOD_CONFIRMED_AWAITING_USER_VALIDATION"
    )
    assert workflow["scientific_core"]["validation_entry_policy"] == (
        "human_initiated_only_after_method_confirmation"
    )
    parsed = build_parser().parse_args(
        ["submit-source-policy", "run-1", "candidate-policy.yaml"]
    )
    assert parsed.command == "submit-source-policy"
    revision = build_parser().parse_args(["request-source-policy-revision", "run-1"])
    assert revision.command == "request-source-policy-revision"
    problem_revision = build_parser().parse_args(
        ["revise-problem", "run-1", "--reason", "new evidence narrows scope"]
    )
    assert problem_revision.command == "revise-problem"
    human_revision = build_parser().parse_args(
        [
            "human-approve",
            "run-1",
            "principle_test_approval",
            "--decision",
            "request_revision",
        ]
    )
    assert human_revision.decision == "request_revision"
    human_selection = build_parser().parse_args(
        [
            "human-approve",
            "run-1",
            "principle_selection",
            "--decision",
            "combine",
            "--human-feedback",
            "Combine PR-A and PR-B around the shared invariant.",
        ]
    )
    assert human_selection.gate == "principle_selection"
    assert human_selection.decision == "combine"
    assert build_parser().parse_args(["start-phase", "run-1"]).command == "start-phase"
    accepted = build_parser().parse_args(
        [
            "accept-phase",
            "run-1",
            "--verdict-id",
            "verdict-1",
            "--reviewer",
            "claude-sonnet-4",
        ]
    )
    assert accepted.command == "accept-phase"
    returned = build_parser().parse_args(
        [
            "return-phase",
            "run-1",
            "--verdict-id",
            "verdict-2",
            "--reviewer",
            "claude-sonnet-4",
            "--lesson-file",
            "reusable-lesson.json",
        ]
    )
    assert returned.lesson_file == "reusable-lesson.json"


def test_query_plan_v2_enforces_executable_pagination_before_gateway(tmp_path: Path) -> None:
    write_policy(tmp_path)
    controller = ARISController.start(
        tmp_path, "run-v2", executor="codex-gpt-5.6-sol"
    )
    approve(controller, "source_policy_approval")
    controller.submit_query_plan(
        {
            "schema_version": 2,
            "search_strategy": {
                "priority_order": [
                    "RECENT_AUTHORITATIVE_REVIEWS",
                    "HIGH_CITATION_BACKBONE",
                    "RECENT_ELITE_FRONTIER",
                    "TARGETED_GAP_FOLLOWUP",
                ],
                "discovery_sources": ["Google Scholar"],
                "time_range": {"year_from": 2021, "year_to": 2026},
                "screening_requirement": "TITLE_ABSTRACT_FOR_ALL_RETRIEVED_CANDIDATES",
                "saturation_criteria": ["follow-up adds no major branch"],
            },
            "coverage_gaps": ["recent frontier"],
            "queries": [
                {
                    "plan_item_id": "frontier-page-2",
                    "query": "impedance control learning",
                    "purpose": "cover the second result page",
                    "priority_tier": "RECENT_ELITE_FRONTIER",
                    "year_from": 2021,
                    "year_to": 2026,
                    "page": 2,
                    "exact_title": False,
                    "target_venues": ["Test Elite Venue"],
                    "expected_close_condition": "no new mechanism family",
                }
            ],
        }
    )
    calls: list[str] = []
    with pytest.raises(ControllerError, match="do not match"):
        controller.execute_query(
            "impedance control learning",
            "fake",
            lambda query: calls.append(query) or [],
            plan_item_id="frontier-page-2",
            query_options={
                "year_from": 2021,
                "year_to": 2026,
                "exact_title": False,
                "page": 1,
            },
        )
    assert calls == []


def test_high_citation_backbone_can_wait_for_a_later_fulltext_pass(tmp_path: Path) -> None:
    controller = start_controller(tmp_path)
    paper = metadata(venue="Ordinary")
    paper["citation_count"] = 200
    controller.execute_query("test field", "fake", lambda _: [paper])
    assert controller.decide_admission(
        "P1",
        screening_in_scope=True,
        screening_basis="TITLE_ABSTRACT",
        screening_reason="foundational mechanism paper",
        reading_priority="HIGH_CITATION_BACKBONE",
        fulltext_selected=False,
        fulltext_selection_reason="A complementary review is selected for the current initial pass first.",
    ) == "ADMIT_DISCOVERY_ONLY"


def test_high_citation_candidate_can_remain_abstract_only_when_not_a_backbone(
    tmp_path: Path,
) -> None:
    controller = start_controller(tmp_path)
    paper = metadata(venue="Ordinary")
    paper["citation_count"] = 200
    controller.execute_query("test field", "fake", lambda _: [paper])

    assert controller.decide_admission(
        "P1",
        screening_in_scope=True,
        screening_basis="TITLE_ABSTRACT",
        screening_reason="The paper is a task-specific application of an already covered mechanism.",
        reading_priority="RECENT_ELITE_FRONTIER",
        fulltext_selected=False,
        fulltext_selection_reason=(
            "Application implementation; no uncovered mechanism, contradiction, "
            "or decision target remains."
        ),
    ) == "ADMIT_DISCOVERY_ONLY"
    assert controller.finish_retrieval()["research_lit"]["current_stage"] == "HUMAN_SEARCH_REQUIRED"


def test_high_citation_backbone_label_requires_high_citation_threshold(tmp_path: Path) -> None:
    controller = start_controller(tmp_path)
    paper = metadata(venue="Test Elite Venue")
    paper["citation_count"] = 0
    controller.execute_query("test field", "fake", lambda _: [paper])

    with pytest.raises(ControllerError, match="requires the source-policy high-citation threshold"):
        controller.decide_admission(
            "P1",
            screening_in_scope=True,
            screening_basis="TITLE_ABSTRACT",
            screening_reason="claimed backbone",
            reading_priority="HIGH_CITATION_BACKBONE",
            fulltext_selected=True,
        )


def test_coverage_continue_requires_concrete_gap_and_reenters_query_planning(
    tmp_path: Path,
) -> None:
    controller = start_controller(tmp_path)
    digest, request_id = reach_coverage(controller)
    review = coverage_review(digest, request_id, decision="CONTINUE")
    attest(controller, "coverage_reviewer", review)
    with pytest.raises(ControllerError, match="requires at least one concrete gap"):
        controller.submit_coverage_review(review)

    review["gaps"] = ["The field map lacks evidence for the reported failure boundary."]
    attest(controller, "coverage_reviewer", review)
    state = controller.submit_coverage_review(review)
    assert state["research_lit"]["current_stage"] == "QUERY_PLANNING"
    assert state["research_lit"]["last_coverage_review_decision"] == "CONTINUE"
    with pytest.raises(ControllerError, match="must retain every concrete CONTINUE gap"):
        controller.submit_query_plan(
            {
                "coverage_gaps": ["unrelated gap"],
                "queries": [{"query": "unrelated", "purpose": "bypass the review"}],
            }
        )
    controller.submit_query_plan(
        {
            "coverage_gaps": review["gaps"],
            "queries": [
                {
                    "query": "reported failure boundary",
                    "purpose": "resolve the coverage-review gap",
                    "coverage_gaps": review["gaps"],
                }
            ],
        }
    )
    assert controller.status()["research_lit"]["current_stage"] == "METADATA_RETRIEVAL"


def test_field_map_gaps_are_bound_to_targeted_queries_and_the_same_map_is_revised(
    tmp_path: Path,
) -> None:
    for status in ("PARTIAL", "INSUFFICIENT"):
        missing_gaps = field_map(status)
        del missing_gaps["coverage_record"]["coverage_gaps"]
        with pytest.raises(ValidationError, match="coverage_record.coverage_gaps"):
            validate_field_map(missing_gaps, evidence_ids={"P1"})
    sufficient_with_live_gap = field_map()
    sufficient_with_live_gap["coverage_record"]["coverage_gaps"] = ["live gap"]
    with pytest.raises(ValidationError, match="SUFFICIENT requires coverage_gaps to be empty"):
        validate_field_map(sufficient_with_live_gap, evidence_ids={"P1"})
    sufficient_without_gap_field = field_map()
    del sufficient_without_gap_field["coverage_record"]["coverage_gaps"]
    assert validate_field_map(sufficient_without_gap_field, evidence_ids={"P1"}) is (
        sufficient_without_gap_field
    )

    controller = start_controller(tmp_path)
    reach_synthesis(controller)
    map_v1 = field_map("PARTIAL")
    gap = map_v1["coverage_record"]["coverage_gaps"][0]
    state = controller.submit_field_map(map_v1)
    assert state["research_lit"]["required_coverage_gaps"] == [gap]

    with pytest.raises(ControllerError, match="must retain every required coverage gap"):
        controller.submit_query_plan(
            {
                "coverage_gaps": ["unrelated gap"],
                "queries": [{"query": "unrelated", "purpose": "bypass map gap"}],
            }
        )
    with pytest.raises(ControllerError, match="missing required fields"):
        controller.submit_query_plan(
            {
                "coverage_gaps": [gap],
                "queries": [
                    {"query": "reported failure regime", "purpose": "resolve map gap"}
                ],
            }
        )

    controller.submit_query_plan(
        {
            "schema_version": 2,
            "search_strategy": {
                "priority_order": [
                    "RECENT_AUTHORITATIVE_REVIEWS",
                    "HIGH_CITATION_BACKBONE",
                    "RECENT_ELITE_FRONTIER",
                    "TARGETED_GAP_FOLLOWUP",
                ],
                "discovery_sources": ["Google Scholar"],
                "time_range": {"year_from": 2000, "year_to": 2026},
                "screening_requirement": "TITLE_ABSTRACT_FOR_ALL_RETRIEVED_CANDIDATES",
                "saturation_criteria": ["the gap is resolved or reframed by new evidence"],
            },
            "coverage_gaps": [gap],
            "queries": [
                {
                    "plan_item_id": "field-map-gap-p2",
                    "query": "reported failure regime mechanism boundary",
                    "purpose": "test the unresolved failure regime boundary",
                    "coverage_gaps": [gap],
                    "priority_tier": "TARGETED_GAP_FOLLOWUP",
                    "year_from": 2000,
                    "year_to": 2026,
                    "page": 1,
                    "exact_title": False,
                    "target_venues": ["Test Elite Venue"],
                    "expected_close_condition": "evidence discriminates the failure boundary",
                }
            ],
        }
    )
    controller.execute_query(
        "reported failure regime mechanism boundary",
        "fake",
        lambda _: [metadata("P2")],
        plan_item_id="field-map-gap-p2",
        query_options={
            "year_from": 2000,
            "year_to": 2026,
            "exact_title": False,
            "page": 1,
        },
    )
    assert controller.status()["research_lit"]["query_events"]["Q0002"]["plan_item_id"] == (
        "field-map-gap-p2"
    )
    assert controller.decide_admission(
        "P2",
        screening_in_scope=True,
        screening_basis="TITLE_ABSTRACT",
        screening_reason="direct evidence for the unresolved failure regime",
        reading_priority="TARGETED_GAP_FOLLOWUP",
    ) == "ADMIT_FOR_READING"
    assert controller.decide_admission(
        "P1",
        screening_in_scope=True,
        screening_basis="FULL_TEXT",
        screening_reason="accepted Evidence remains in scope under the revised Landscape Query Plan",
        reading_priority="HIGH_CITATION_BACKBONE",
        fulltext_selected=False,
        fulltext_selection_reason="the accepted Evidence Card already contains the completed read",
    ) == "ADMIT_DECISION_GRADE"
    controller.select_reading_subset(
        ["P2"],
        rationale="The targeted failure-boundary paper is the next coverage pass.",
    )
    controller.finish_retrieval()
    read = controller.read_full_text("P2", "fake-paper", lambda _: "full paper P2")
    evidence = card(read, "P2")
    attest(controller, "paper_reader", evidence)
    controller.submit_evidence_card("P2", evidence)
    controller.finish_reading()

    map_v2 = field_map("PARTIAL")
    map_v2["family_development_traces"][0]["evidence_ids"] = ["P1", "P2"]
    map_v2["assumption_effectiveness_failure_matrix"][0]["source_ids"] = ["P1", "P2"]
    map_v2["consensus"] = ["P2 revises the failure-boundary classification."]
    state = controller.submit_field_map(map_v2)
    canonical = tmp_path / "idea-stage" / "ACTIVE_FIELD_MAP.md"
    assert Path(state["research_lit"]["accepted_artifacts"]["active_field_map"]["path"]).name == (
        "ACTIVE_FIELD_MAP.md"
    )
    assert canonical.is_file()
    assert '"P2"' in canonical.read_text(encoding="utf-8")
    assert list((tmp_path / "idea-stage").glob("ACTIVE_FIELD_MAP*.md")) == [canonical]
    assert state["research_lit"]["current_stage"] == "QUERY_PLANNING"


def test_gap_bound_plan_cannot_finish_without_a_completed_targeted_search(
    tmp_path: Path,
) -> None:
    controller = start_controller(tmp_path)
    reach_synthesis(controller)
    map_v1 = field_map("PARTIAL")
    gap = map_v1["coverage_record"]["coverage_gaps"][0]
    controller.submit_field_map(map_v1)
    controller.submit_query_plan(
        {
            "coverage_gaps": [gap],
            "queries": [
                {
                    "query": "failure regime targeted evidence",
                    "purpose": "resolve the Field Map gap",
                    "coverage_gaps": [gap],
                }
            ],
        }
    )
    with controller._store.mutate() as state:
        state["research_lit"]["planned_queries"][0]["status"] = "failed"
    with pytest.raises(ControllerError, match="every required coverage gap has a completed bound query"):
        controller.finish_retrieval()


def test_missing_historical_transition_reenters_query_planning_as_targeted_gap(
    tmp_path: Path,
) -> None:
    controller = start_controller(tmp_path)
    reach_synthesis(controller)
    empty_map = field_map()
    empty_map["family_development_traces"] = []
    controller.submit_field_map(empty_map)
    research = controller.status()["research_lit"]
    request = research["coverage_review_request"]
    assert request["development_trace_count"] == 0

    digest = CoverageDigest(
        research["accepted_artifacts"]["active_field_map"]["sha256"],
        request["artifact_bindings"],
        request["development_trace_count"],
    )
    review = coverage_review(
        digest,
        request["id"],
        decision="CONTINUE",
        development_trace_count=0,
    )
    gap = "The transition from the foundational bottleneck to the current branch is missing."
    review["gaps"] = [gap]
    review["evolution_assessment"]["transition_causality"] = {
        "status": "GAP",
        "rationale": "Accepted evidence indicates a material question shift that the map omits.",
        "basis": "MATERIAL_TRANSITION_MISSING",
    }
    review["evolution_assessment"]["material_evolution_gaps"] = [gap]
    attest(controller, "coverage_reviewer", review)
    state = controller.submit_coverage_review(review)
    assert state["research_lit"]["current_stage"] == "QUERY_PLANNING"

    with pytest.raises(ControllerError, match="must retain every concrete CONTINUE gap"):
        controller.submit_query_plan(
            {
                "coverage_gaps": ["unrelated"],
                "queries": [{"query": "unrelated", "purpose": "avoid the historical gap"}],
            }
        )
    controller.submit_query_plan(
        {
            "coverage_gaps": [gap],
            "queries": [
                {
                    "query": "foundational bottleneck current branch transition",
                    "purpose": "recover evidence for the missing historical transition",
                    "coverage_gaps": [gap],
                }
            ],
        }
    )
    assert controller.current_stage() == "METADATA_RETRIEVAL"


def test_elite_venue_alias_matches_provider_bibliographic_venue_string() -> None:
    policy = {
        "approved_elite_venues": [
            {
                "canonical_name": "IEEE International Conference on Robotics and Automation",
                "aliases": ["ICRA"],
            }
        ]
    }
    assert ARISController._venue_eligible(
        policy,
        "2022 International Conference on Robotics and Automation (ICRA)",
    )
    assert not ARISController._venue_eligible(policy, "Micra Biology Workshop")
    ijrr_policy = {
        "approved_elite_venues": [
            {
                "canonical_name": "The International Journal of Robotics Research",
                "aliases": ["IJRR"],
            }
        ]
    }
    assert not ARISController._venue_eligible(
        ijrr_policy,
        "Industrial Robot: the international journal of robotics research and application",
    )


def test_candidate_can_be_enriched_before_screening_decision(tmp_path: Path) -> None:
    controller = start_controller(tmp_path)
    controller.execute_query("test field", "fake", lambda _: [metadata()])
    with controller._store.mutate() as state:
        paper = state["research_lit"]["papers"]["P1"]
        paper["identity_status"] = "verify_pending"
        paper.pop("abstract", None)
    enriched = controller.enrich_candidate_metadata(
        "P1",
        identity_verifier=lambda paper: {
            **paper,
            "identity_status": "verified",
            "identity_provider": "test",
            "abstract": "A retrieved abstract that can now be judged before admission.",
            "abstract_source": "test",
        },
    )
    assert enriched["abstract"].startswith("A retrieved abstract")
    assert not controller.status()["research_lit"]["papers"]["P1"].get("context_decisions")


def test_verified_candidate_without_abstract_can_route_to_mandatory_fulltext(
    tmp_path: Path,
) -> None:
    controller = start_controller(tmp_path)
    paper = metadata()
    paper["citation_count"] = 200
    paper.pop("abstract", None)
    paper["identity_status"] = "verify_pending"
    controller.execute_query("test field", "fake", lambda _: [paper])
    controller.enrich_candidate_metadata(
        "P1",
        identity_verifier=lambda candidate: {
            **candidate,
            "identity_status": "verified",
            "identity_provider": "test",
        },
    )
    assert controller.decide_admission(
        "P1",
        screening_in_scope=True,
        screening_basis="TITLE_ONLY_ABSTRACT_UNAVAILABLE",
        screening_reason="metadata sources expose no abstract; the high-citation paper requires full-text screening",
        reading_priority="HIGH_CITATION_BACKBONE",
        fulltext_selected=True,
    ) == "ADMIT_FOR_READING"


def test_interrupted_query_recovery_reuses_query_id_and_budget(tmp_path: Path) -> None:
    controller = start_controller(tmp_path)
    with controller._store.mutate() as state:
        research = state["research_lit"]
        planned = research["planned_queries"][0]
        planned["plan_item_id"] = "plan-1"
        planned["status"] = "started"
        planned["query_id"] = "Q0001"
        research["query_count"] = 1
        research["query_events"]["Q0001"] = {
            "event_id": "orphaned",
            "query": planned["query"],
            "status": "started",
        }

    recovered = controller.recover_interrupted_query(
        "plan-1",
        reason="the gateway process was terminated before it could report completion",
    )
    assert recovered["query_id"] == "Q0001"
    assert controller.status()["research_lit"]["query_count"] == 1


def test_query_plan_event_reconciliation_restores_reset_terminal_statuses(
    tmp_path: Path,
) -> None:
    write_policy(tmp_path)
    controller = ARISController.start(
        tmp_path, "run-reconcile", executor="codex-gpt-5.6-sol"
    )
    approve(controller, "source_policy_approval")
    controller.submit_query_plan(
        {
            "schema_version": 2,
            "search_strategy": {
                "priority_order": [
                    "RECENT_AUTHORITATIVE_REVIEWS",
                    "HIGH_CITATION_BACKBONE",
                    "RECENT_ELITE_FRONTIER",
                    "TARGETED_GAP_FOLLOWUP",
                ],
                "discovery_sources": ["Google Scholar"],
                "time_range": {"year_from": 2021, "year_to": 2026},
                "screening_requirement": "TITLE_ABSTRACT_FOR_ALL_RETRIEVED_CANDIDATES",
                "saturation_criteria": ["follow-up adds no major branch"],
            },
            "coverage_gaps": ["recent frontier"],
            "queries": [
                {
                    "plan_item_id": "frontier-page-1",
                    "query": "impedance control learning",
                    "purpose": "cover the first result page",
                    "priority_tier": "RECENT_ELITE_FRONTIER",
                    "year_from": 2021,
                    "year_to": 2026,
                    "page": 1,
                    "exact_title": False,
                    "target_venues": ["Test Elite Venue"],
                    "expected_close_condition": "no new mechanism family",
                }
            ],
        }
    )
    controller.execute_query(
        "impedance control learning",
        "fake",
        lambda _: [metadata()],
        plan_item_id="frontier-page-1",
        query_options={
            "year_from": 2021,
            "year_to": 2026,
            "exact_title": False,
            "page": 1,
        },
    )
    before = controller.status()["research_lit"]
    with controller._store.mutate() as state:
        planned = state["research_lit"]["planned_queries"][0]
        planned["status"] = "planned"
        planned["constraints"] = {
            "year_from": 2021,
            "year_to": 2026,
            "exact_title": False,
            "page": 1,
        }
        planned.pop("query_id", None)

    assert "reconcile_query_plan_events" in controller.allowed_actions()
    result = controller.reconcile_query_plan_events(
        reason="accepted query plan was resubmitted during workflow migration"
    )
    after = controller.status()["research_lit"]

    assert result["reconciled"] == [
        {
            "plan_item_id": "frontier-page-1",
            "query_id": "Q0001",
            "event_status": "complete",
            "plan_status": "complete",
        }
    ]
    assert after["planned_queries"][0]["status"] == "complete"
    assert after["planned_queries"][0]["query_id"] == "Q0001"
    assert after["query_count"] == before["query_count"]
    assert after["query_events"] == before["query_events"]
    assert after["papers"] == before["papers"]
    assert "reconcile_query_plan_events" not in controller.allowed_actions()
    assert '"action": "query_plan_event_reconciliation"' in (
        tmp_path / "idea-stage" / "SEARCH_LEDGER.jsonl"
    ).read_text(encoding="utf-8")


def test_literature_budget_extension_is_monotonic_and_logged(tmp_path: Path) -> None:
    controller = start_controller(tmp_path)
    old_limit = controller.status()["research_lit"]["max_fulltext_papers"]
    result = controller.extend_literature_budget(
        max_fulltext_papers=old_limit + 20,
        reason="the approved evidence strategy requires additional high-citation full texts",
    )
    assert result["after"]["max_fulltext_papers"] == old_limit + 20
    with pytest.raises(ControllerError, match="strictly increase"):
        controller.extend_literature_budget(
            max_fulltext_papers=old_limit,
            reason="must not reduce the formal limit",
        )
    assert '"action": "budget_extension"' in (
        tmp_path / "idea-stage" / "SEARCH_LEDGER.jsonl"
    ).read_text(encoding="utf-8")


def test_incremental_problem_binding_uses_field_map_then_existing_reopen_provenance(
    tmp_path: Path,
) -> None:
    controller = start_controller(tmp_path)
    digest, request_id = reach_coverage(controller)
    review = coverage_review(digest, request_id)
    attest(controller, "coverage_reviewer", review)
    controller.submit_coverage_review(review)
    approve(controller, "scope_human_approval")
    controller.start_current_phase()

    plan = {
        "coverage_gaps": [],
        "queries": [{
            "query": "targeted closest prior",
            "purpose": "test the current Lead boundary",
            "expected_close_condition": "resolve the Lead's closest-prior uncertainty",
            "lead_id": "L-1",
            "lead_statement": "The current field boundary remains unresolved.",
            "active_field_map_sha256": controller.status()["research_lit"]["accepted_artifacts"]["active_field_map"]["sha256"],
            "decision_dimension": "Unresolvedness",
        }],
    }
    controller.submit_query_plan(plan)
    state = controller.status()
    anchor = state["research_lit"]["incremental_literature_active"]["phase_binding_anchor"]
    assert "active_problem_binding" not in anchor
    assert "idea-stage/ACTIVE_FIELD_MAP.md" in anchor["required_inputs"]

    with controller._store.mutate() as mutable:
        mutable["research_lit"]["incremental_literature_active"] = None
        mutable["research_lit"]["current_stage"] = "LANDSCAPE_ACCEPTED"
        mutable["scientific_core"]["pending_problem_revision"] = {
            "problem_id": "P-1", "version": 2, "parent_version": 1,
            "return_event_id": "return-problem-1",
        }
        mutable["scientific_core"]["return_history"].append({
            "id": "return-problem-1", "invalidated_phases": ["problem_generation"],
        })
        evidence_path = tmp_path / ".aris" / "canonical" / "run-1" / "evidence-P2.json"
        evidence_path.write_text('{"source_id":"P2"}\n', encoding="utf-8")
        mutable["research_lit"]["accepted_artifacts"]["evidence:P2"] = {
            "path": str(evidence_path.relative_to(tmp_path)),
            "sha256": sha256_file(evidence_path),
            "validator_result": "PASS",
        }
        mutable["research_lit"]["incremental_evidence_by_phase"] = {
            "problem_generation": {
                "evidence:P2": {
                    **mutable["research_lit"]["accepted_artifacts"]["evidence:P2"],
                    "evidence_key": "evidence:P2",
                    "phase_binding_anchor": anchor,
                }
            }
        }
        assert "P2" not in controller._current_phase_evidence_ids(
            mutable, "problem_generation"
        )
    controller.submit_query_plan(plan)
    reopened = controller.status()["research_lit"]["incremental_literature_active"]["phase_binding_anchor"]
    assert reopened["pending_problem_revision"]["return_event_id"] == "return-problem-1"
    assert reopened["problem_return_event_id"] == "return-problem-1"


def _register_re_adoption_test_evidence(
    controller: ARISController, source_id: str = "P2"
) -> dict[str, str]:
    card_path = (
        controller.root / ".aris" / "canonical" / controller.run_id / f"evidence-{source_id}.json"
    )
    card_path.parent.mkdir(parents=True, exist_ok=True)
    read_event_id = f"R-{source_id}"
    card = {"source_id": source_id, "read_event_id": read_event_id}
    card_path.write_text(json.dumps(card), encoding="utf-8")
    registry = controller.root / "idea-stage" / "EVIDENCE_REGISTRY.jsonl"
    with registry.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(card) + "\n")
    record = {
        "path": str(card_path.relative_to(controller.root)),
        "sha256": sha256_file(card_path),
        "read_event_id": read_event_id,
        "validator_result": "PASS",
    }
    with controller._store.mutate() as state:
        research = state["research_lit"]
        research["accepted_artifacts"][f"evidence:{source_id}"] = record
        research["read_events"][read_event_id] = {
            "paper_id": source_id,
            "status": "complete",
        }
        research["papers"][source_id] = {"source_origin": "user_supplied"}
    return record


def _activate_re_adoption_method_phase(
    controller: ARISController, phase_name: str
) -> None:
    with controller._store.mutate() as state:
        core = state["scientific_core"]
        core["status"] = "ACTIVE"
        core["current_phase"] = phase_name
        core["validation_entry"] = None
        run_state._find_phase(state, phase_name)["status"] = "running"
        run_state._find_phase(state, "problem_necessity")["validated_artifacts"] = {
            raw_path: core["accepted_artifacts"][raw_path]["sha256"]
            for raw_path in (
                "idea-stage/NECESSITY_CLOSURE.json",
                "idea-stage/NECESSITY_VERDICT.json",
            )
        }
        run_state._find_phase(state, "root_cause_analysis")["validated_artifacts"] = {
            raw_path: core["accepted_artifacts"][raw_path]["sha256"]
            for raw_path in (
                "idea-stage/RESEARCH_CONTRACT.md",
                "idea-stage/PROBLEM_EVIDENCE_CAPSULE.md",
                "idea-stage/NECESSITY_CLOSURE.json",
                "idea-stage/NECESSITY_VERDICT.json",
                "idea-stage/ROOT_CAUSE_ANALYSIS.json",
            )
        }
        run_state._find_phase(state, "root_cause_gate")["validated_artifacts"] = {
            "idea-stage/ROOT_CAUSE_VERDICT.json": core["accepted_artifacts"][
                "idea-stage/ROOT_CAUSE_VERDICT.json"
            ]["sha256"]
        }
        state["research_lit"]["current_stage"] = "LANDSCAPE_ACCEPTED"


def test_method_re_adoption_discovery_requires_current_design_obligations(
    tmp_path: Path,
) -> None:
    controller = confirmed_validation_controller(tmp_path)
    record = _register_re_adoption_test_evidence(controller)
    _activate_re_adoption_method_phase(controller, "method_design")
    with controller._store.mutate() as state:
        state["research_lit"]["incremental_evidence_by_phase"] = {
            "method_design": {
                "evidence:P2": {
                    **record,
                    "evidence_key": "evidence:P2",
                    "phase_binding_anchor": {
                        "phase": "method_design",
                        "required_inputs": {},
                        "design_obligation_binding": {
                            "source": "historical_test_context",
                            "obligation_ids": ["OBL-OLD"],
                        },
                    },
                }
            }
        }

    assert controller._current_method_obligation_binding(
        controller.status(), "method_design"
    ) is None
    assert "readopt_evidence" not in controller.allowed_actions()


def test_method_re_adoption_rejects_registered_evidence_never_phase_bound(
    tmp_path: Path,
) -> None:
    controller = confirmed_validation_controller(tmp_path)
    _register_re_adoption_test_evidence(controller)
    _activate_re_adoption_method_phase(controller, "method_refinement")

    assert "readopt_evidence" not in controller.allowed_actions()
    with pytest.raises(ControllerError, match="prior formal phase-scoped binding"):
        controller.readopt_incremental_evidence("P2", obligation_ids=["OBL-1"])

    assert "method_refinement" not in (
        controller.status()["research_lit"].get("incremental_evidence_by_phase") or {}
    )


def test_method_re_adopts_historical_problem_phase_evidence(
    tmp_path: Path,
) -> None:
    controller = confirmed_validation_controller(tmp_path)
    record = _register_re_adoption_test_evidence(controller)
    _activate_re_adoption_method_phase(controller, "method_refinement")
    with controller._store.mutate() as state:
        state["research_lit"]["incremental_evidence_by_phase"] = {
            "problem_generation": {
                "evidence:P2": {
                    **record,
                    "evidence_key": "evidence:P2",
                    "phase_binding_anchor": {
                        "phase": "problem_generation",
                        "required_inputs": {},
                        "lifecycle_return_event_id": None,
                    },
                }
            }
        }

    assert "readopt_evidence" in controller.allowed_actions()
    assert controller.readopt_incremental_evidence(
        "P2", obligation_ids=["OBL-1"]
    ) == {
        "status": "RE_ADOPTED",
        "evidence_id": "P2",
        "phase": "method_refinement",
    }
    assert "P2" in controller._current_phase_evidence_ids(
        controller.status(), "method_refinement"
    )
    assert "readopt_evidence" not in controller.allowed_actions()


def test_re_adoption_preserves_history_and_search_cycle_authorization_is_boundary_only(
    tmp_path: Path,
) -> None:
    controller = confirmed_validation_controller(tmp_path)
    card_path = tmp_path / ".aris" / "canonical" / "run-1" / "evidence-P2.json"
    card_path.parent.mkdir(parents=True, exist_ok=True)
    original_card = {
        "source_id": "P2",
        "read_event_id": "R-P2",
        "method_design_search_context": {"residual": "OBL-1"},
    }
    card_path.write_text(json.dumps(original_card), encoding="utf-8")
    original_bytes = card_path.read_bytes()
    (tmp_path / "idea-stage" / "EVIDENCE_REGISTRY.jsonl").write_text(
        json.dumps(original_card) + "\n", encoding="utf-8"
    )

    with controller._store.mutate() as state:
        core = state["scientific_core"]
        core["status"] = "ACTIVE"
        core["current_phase"] = "method_refinement"
        run_state._find_phase(state, "method_refinement")["status"] = "running"
        run_state._find_phase(state, "root_cause_analysis")["validated_artifacts"] = {
            raw_path: core["accepted_artifacts"][raw_path]["sha256"]
            for raw_path in (
                "idea-stage/RESEARCH_CONTRACT.md",
                "idea-stage/PROBLEM_EVIDENCE_CAPSULE.md",
                "idea-stage/NECESSITY_CLOSURE.json",
                "idea-stage/NECESSITY_VERDICT.json",
                "idea-stage/ROOT_CAUSE_ANALYSIS.json",
            )
        }
        run_state._find_phase(state, "root_cause_gate")["validated_artifacts"] = {
            "idea-stage/ROOT_CAUSE_VERDICT.json": core["accepted_artifacts"][
                "idea-stage/ROOT_CAUSE_VERDICT.json"
            ]["sha256"]
        }
        research = state["research_lit"]
        research["current_stage"] = "LANDSCAPE_ACCEPTED"
        research["accepted_artifacts"]["evidence:P2"] = {
            "path": str(card_path.relative_to(tmp_path)),
            "sha256": sha256_file(card_path),
            "read_event_id": "R-P2",
            "validator_result": "PASS",
        }
        research["read_events"]["R-P2"] = {"paper_id": "P2", "status": "complete"}
        research["papers"]["P2"] = {"found_by_query_ids": ["Q-P2"]}
        research["query_events"]["Q-P2"] = {"status": "complete"}
        first_anchor = controller._phase_evidence_anchor(state, "method_refinement")
        research["incremental_evidence_by_phase"] = {
            "method_refinement": {
                "evidence:P2": {
                    **research["accepted_artifacts"]["evidence:P2"],
                    "evidence_key": "evidence:P2",
                    "phase_binding_anchor": first_anchor,
                }
            }
        }
        research["search_cycle_count"] = research["max_search_cycles"]

    # Replace only the current formal Selected Principle binding. The Card
    # stays immutable and the old obligation context must not become current by hash.
    selected_path = tmp_path / "idea-stage" / "SELECTED_PRINCIPLE.yaml"
    selected = yaml.safe_load(selected_path.read_text(encoding="utf-8"))
    selected["principle_id"] = "PR-B"
    selected["principle_version"] = "2"
    selected["obligation_ids"] = ["OBL-B"]
    selected_path.write_text(yaml.safe_dump(selected, sort_keys=False), encoding="utf-8")
    with controller._store.mutate() as state:
        state["scientific_core"]["accepted_artifacts"]["idea-stage/SELECTED_PRINCIPLE.yaml"] = controller._artifact_record(
            "idea-stage/SELECTED_PRINCIPLE.yaml",
            producer_phase="principle_evaluation",
            provenance={},
            upstream_snapshot={},
        )
    assert controller._incremental_evidence_bindings(controller.status(), "method_refinement") == {}

    adopted = controller.readopt_incremental_evidence("P2", obligation_ids=["OBL-B"])
    assert adopted["status"] == "RE_ADOPTED"
    state = controller.status()
    bindings = state["research_lit"]["incremental_evidence_by_phase"]["method_refinement"]
    assert len(bindings) == 2
    assert bindings["evidence:P2"]["phase_binding_anchor"] != next(
        item["phase_binding_anchor"] for key, item in bindings.items() if key != "evidence:P2"
    )
    assert card_path.read_bytes() == original_bytes

    # A formal lifecycle return ends the downstream current binding even when
    # regenerated method files would be byte-identical.
    with controller._store.mutate() as state:
        state["scientific_core"]["return_history"].append({
            "id": "return-method-1", "invalidated_phases": ["method_refinement"],
        })
    assert controller._incremental_evidence_bindings(controller.status(), "method_refinement") == {}

    # The same Card may support a formally reopened RCA without making its old
    # Design Obligation context a currentness prerequisite.
    with controller._store.mutate() as state:
        state["scientific_core"]["current_phase"] = "root_cause_analysis"
        run_state._find_phase(state, "root_cause_analysis")["status"] = "running"
        state["scientific_core"]["return_history"].append({
            "id": "return-rca-1", "invalidated_phases": ["root_cause_analysis"],
        })
    rca_adopted = controller.readopt_incremental_evidence("P2")
    assert rca_adopted == {"status": "RE_ADOPTED", "evidence_id": "P2", "phase": "root_cause_analysis"}
    assert controller._incremental_evidence_bindings(controller.status(), "root_cause_analysis")
    with controller._store.mutate() as state:
        research = state["research_lit"]
        research["incremental_evidence_by_phase"]["root_cause_analysis"]["evidence:P2-diagnostic"] = {
            **research["accepted_artifacts"]["evidence:P2"],
            "evidence_key": "evidence:P2",
            "phase_binding_anchor": controller._phase_evidence_anchor(state, "root_cause_analysis"),
        }
        state["scientific_core"]["return_history"].append({
            "id": "return-rca-2", "invalidated_phases": ["root_cause_analysis"],
        })
    # A same-Problem RCA revision does not clear a still-relevant diagnostic
    # binding; only the prior re-adoption was tied to its older reopen receipt.
    assert controller._incremental_evidence_bindings(controller.status(), "root_cause_analysis")
    assert controller.readopt_incremental_evidence("P2") == {
        "status": "ALREADY_CURRENT", "evidence_id": "P2", "phase": "root_cause_analysis"
    }

    with controller._store.mutate() as state:
        state["scientific_core"]["current_phase"] = "method_refinement"
        run_state._find_phase(state, "method_refinement")["status"] = "running"
    result = controller.extend_literature_budget(
        max_search_cycles=controller.status()["research_lit"]["max_search_cycles"] + 1,
        reason="authorized targeted retrieval is blocked only by the global cycle limit",
    )
    assert result["after"]["max_search_cycles"] == result["before"]["max_search_cycles"] + 1
    with controller._store.mutate() as state:
        state["research_lit"]["current_stage"] = "METADATA_RETRIEVAL"
    with pytest.raises(ControllerError, match="idle incremental retrieval boundary"):
        controller.extend_literature_budget(
            max_search_cycles=result["after"]["max_search_cycles"] + 1,
            reason="must not rewrite an active retrieval plan",
        )


def test_adaptation_gap_evidence_refreshes_the_current_final_review_binding(
    tmp_path: Path,
) -> None:
    controller = confirmed_validation_controller(tmp_path)
    root_cause_path = tmp_path / "idea-stage" / "ROOT_CAUSE_ANALYSIS.json"
    root_cause_path.write_text(
        json.dumps({"analysis_id": "RCA-1", "primary_causal_chain_ids": ["CHAIN-1"]}) + "\n",
        encoding="utf-8",
    )
    selected_path = tmp_path / "idea-stage" / "SELECTED_PRINCIPLE.yaml"
    selected = yaml.safe_load(selected_path.read_text(encoding="utf-8"))
    selected["root_cause_binding"]["analysis_sha256"] = sha256_file(root_cause_path)
    selected["accepted_assumptions"] = [
        {"assumption_id": "ASM-1", "assumption": "assumption A"}
    ]
    selected_path.write_text(yaml.safe_dump(selected, sort_keys=False), encoding="utf-8")
    card_path = tmp_path / ".aris" / "canonical" / "run-1" / "evidence-P2.json"
    card_path.parent.mkdir(parents=True, exist_ok=True)
    card = {
        "source_id": "P2",
        "read_event_id": "R-P2",
        "method_refinement_search_context": {
            "search_mode": "ADAPTATION_GAP_SEARCH",
            "principle_id": "PR-A",
            "principle_version": "1",
            "selected_principle_sha256": sha256_file(
                tmp_path / "idea-stage" / "SELECTED_PRINCIPLE.yaml"
            ),
            "actual_hit_query_ids": ["Q-P2"],
            "residual_adaptation_gap_ids": ["GAP-1"],
        },
    }
    card_path.write_text(json.dumps(card), encoding="utf-8")
    (tmp_path / "idea-stage" / "EVIDENCE_REGISTRY.jsonl").write_text(
        json.dumps(card) + "\n", encoding="utf-8"
    )

    with controller._store.mutate() as state:
        core = state["scientific_core"]
        core["status"] = "ACTIVE"
        core["current_phase"] = "method_refinement"
        core["validation_entry"] = None
        phase = run_state._find_phase(state, "method_refinement")
        phase["status"] = "pending"
        phase["review_request"] = None
        state["research_lit"]["current_stage"] = "LANDSCAPE_ACCEPTED"
        core["accepted_artifacts"]["idea-stage/ROOT_CAUSE_ANALYSIS.json"] = (
            controller._artifact_record(
                "idea-stage/ROOT_CAUSE_ANALYSIS.json",
                producer_phase="root_cause_analysis",
                provenance={},
                upstream_snapshot={},
            )
        )
        core["accepted_artifacts"]["idea-stage/SELECTED_PRINCIPLE.yaml"] = (
            controller._artifact_record(
                "idea-stage/SELECTED_PRINCIPLE.yaml",
                producer_phase="principle_evaluation",
                provenance={},
                upstream_snapshot={},
            )
        )
        root_cause_phase = run_state._find_phase(state, "root_cause_analysis")
        root_cause_phase["analysis_id"] = "RCA-1"
        root_cause_phase["validated_artifacts"] = {
            raw_path: core["accepted_artifacts"][raw_path]["sha256"]
            for raw_path in (
                "idea-stage/RESEARCH_CONTRACT.md",
                "idea-stage/PROBLEM_EVIDENCE_CAPSULE.md",
                "idea-stage/NECESSITY_CLOSURE.json",
                "idea-stage/NECESSITY_VERDICT.json",
                "idea-stage/ROOT_CAUSE_ANALYSIS.json",
            )
        }
        run_state._find_phase(state, "root_cause_gate")["validated_artifacts"] = {
            "idea-stage/ROOT_CAUSE_VERDICT.json": core["accepted_artifacts"][
                "idea-stage/ROOT_CAUSE_VERDICT.json"
            ]["sha256"]
        }
        research = state["research_lit"]
        research["accepted_artifacts"]["evidence:P2"] = {
            "path": str(card_path.relative_to(tmp_path)),
            "sha256": sha256_file(card_path),
            "read_event_id": "R-P2",
            "validator_result": "PASS",
        }
        research["read_events"]["R-P2"] = {"paper_id": "P2", "status": "complete"}
        research["papers"]["P2"] = {"found_by_query_ids": ["Q-P2"]}
        research["query_events"]["Q-P2"] = {"status": "complete"}
        old_anchor = controller._phase_evidence_anchor(state, "method_refinement")
        research["incremental_evidence_by_phase"] = {
            "method_refinement": {
                "evidence:P2": {
                    **research["accepted_artifacts"]["evidence:P2"],
                    "evidence_key": "evidence:P2",
                    "phase_binding_anchor": old_anchor,
                }
            }
        }

    selected = yaml.safe_load(selected_path.read_text(encoding="utf-8"))
    selected["remaining_uncertainty"].append("adaptation-gap transfer")
    selected_path.write_text(yaml.safe_dump(selected, sort_keys=False), encoding="utf-8")
    with controller._store.mutate() as state:
        state["scientific_core"]["accepted_artifacts"][
            "idea-stage/SELECTED_PRINCIPLE.yaml"
        ] = controller._artifact_record(
            "idea-stage/SELECTED_PRINCIPLE.yaml",
            producer_phase="principle_evaluation",
            provenance={},
            upstream_snapshot={},
        )

    controller.start_current_phase()
    assert controller._incremental_evidence_bindings(
        controller.status(), "method_refinement"
    ) == {}
    assert controller.readopt_incremental_evidence(
        "P2", obligation_ids=["OBL-1"]
    )["status"] == "RE_ADOPTED"

    packet_path = write_batch4_final_packet(controller)
    request = controller.refresh_current_review_request()
    assert request["artifact_bindings"]["refine-logs/FINAL_METHOD_PACKET.json"] == sha256_file(
        packet_path
    )
    assert request["artifact_bindings"]["idea-stage/SELECTED_PRINCIPLE.yaml"] == sha256_file(
        selected_path
    )
    assert request["artifact_bindings"][str(card_path.relative_to(tmp_path))] == sha256_file(
        card_path
    )


def test_method_to_rca_reopen_records_method_evidence_and_uses_existing_readoption(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    controller = confirmed_validation_controller(tmp_path)
    field_map = tmp_path / "idea-stage" / "ACTIVE_FIELD_MAP.md"
    field_map.write_text("# Accepted field map\n", encoding="utf-8")
    card_path = tmp_path / ".aris" / "canonical" / "run-1" / "evidence-P2.json"
    card_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_card = {
        "source_id": "P2",
        "read_event_id": "R-P2",
        "method_design_search_context": {"search_mode": "PRINCIPLE_SEARCH"},
    }
    card_path.write_text(json.dumps(evidence_card), encoding="utf-8")
    registry = tmp_path / "idea-stage" / "EVIDENCE_REGISTRY.jsonl"
    registry.write_text(json.dumps(evidence_card) + "\n", encoding="utf-8")

    with controller._store.mutate() as state:
        core = state["scientific_core"]
        core["status"] = "ACTIVE"
        core["current_phase"] = "method_design"
        run_state._find_phase(state, "method_design")["status"] = "running"
        core["accepted_artifacts"]["idea-stage/ACTIVE_FIELD_MAP.md"] = controller._artifact_record(
            "idea-stage/ACTIVE_FIELD_MAP.md",
            producer_phase="landscape",
            provenance={},
            upstream_snapshot={},
        )
        root_analysis = run_state._find_phase(state, "root_cause_analysis")
        root_analysis["validated_artifacts"] = {
            raw_path: core["accepted_artifacts"][raw_path]["sha256"]
            for raw_path in (
                "idea-stage/RESEARCH_CONTRACT.md",
                "idea-stage/PROBLEM_EVIDENCE_CAPSULE.md",
                "idea-stage/NECESSITY_CLOSURE.json",
                "idea-stage/NECESSITY_VERDICT.json",
                "idea-stage/ROOT_CAUSE_ANALYSIS.json",
            )
        }
        run_state._find_phase(state, "root_cause_gate")["validated_artifacts"] = {
            "idea-stage/ROOT_CAUSE_VERDICT.json": core["accepted_artifacts"][
                "idea-stage/ROOT_CAUSE_VERDICT.json"
            ]["sha256"]
        }
        research = state["research_lit"]
        research["current_stage"] = "LANDSCAPE_ACCEPTED"
        research["accepted_artifacts"]["evidence:P2"] = {
            "path": str(card_path.relative_to(tmp_path)),
            "sha256": sha256_file(card_path),
            "read_event_id": "R-P2",
            "validator_result": "PASS",
        }
        research["read_events"]["R-P2"] = {"paper_id": "P2", "status": "complete"}
        research["papers"]["P2"] = {"found_by_query_ids": ["Q-P2"]}
        research["query_events"]["Q-P2"] = {"status": "complete"}

    assert controller.allowed_actions() == [
        "submit_query_plan", "reopen_root_cause", "complete_phase", "refresh_review_request",
    ]
    monkeypatch.setattr(sys, "argv", [
        "arisctl", "--root", str(tmp_path), "reopen-root-cause", "run-1",
        "--reason", "The method evidence exposes an incompatible causal mechanism.",
        "--evidence-id", "P2",
    ])
    assert main() == 0
    result = controller.status()
    returned = next(
        item for item in result["scientific_core"]["return_history"]
        if item["id"] == result["scientific_core"]["transition_log"][-1]["return_event_id"]
    )
    assert returned["from_phase"] == "method_design"
    assert returned["return_target"] == "root_cause_analysis"
    assert returned["reason"] == "The method evidence exposes an incompatible causal mechanism."
    assert returned["trigger_evidence_ids"] == ["P2"]
    assert result["scientific_core"]["current_phase"] == "root_cause_analysis"
    assert run_state._find_phase(result, "root_cause_analysis")["status"] == "pending"

    assert controller.readopt_incremental_evidence("P2") == {
        "status": "RE_ADOPTED", "evidence_id": "P2", "phase": "root_cause_analysis",
    }
    parser_args = build_parser().parse_args(["reopen-root-cause", "run-1", "--reason", "new causal conflict"])
    assert parser_args.evidence_ids is None


def _map_for_evidence(paper_id: str, *, coverage: bool) -> dict:
    result = field_map()
    result["family_development_traces"][0]["evidence_ids"] = [paper_id]
    result["assumption_effectiveness_failure_matrix"][0]["source_ids"] = [paper_id]
    if not coverage:
        result.pop("coverage_record")
    return result


def _screen(
    controller: ARISController,
    paper_id: str,
    *,
    selected: bool = False,
    unavailable_abstract: bool = False,
    duplicate: bool = False,
) -> None:
    basis = "TITLE_ONLY_ABSTRACT_UNAVAILABLE" if unavailable_abstract else "TITLE_ABSTRACT"
    controller.decide_admission(
        paper_id,
        screening_in_scope=not duplicate,
        duplicate=duplicate,
        screening_basis=basis,
        screening_reason="screened against the declared initial field boundary",
        reading_priority="RECENT_ELITE_FRONTIER",
        fulltext_selected=selected,
        fulltext_selection_reason=("not in the current active reading subset" if not selected else None),
    )


def test_review_led_initial_map_then_formal_primary_reuses_evidence_and_archives_map(
    tmp_path: Path,
) -> None:
    controller = start_controller(tmp_path)
    no_abstract = metadata("T1")
    no_abstract.pop("abstract")
    no_abstract["identity_verification_status"] = "complete"
    controller.execute_query("test field", "fake", lambda _: [metadata("R1"), metadata("P1"), no_abstract])
    _screen(controller, "R1", selected=True)
    _screen(controller, "P1", selected=True)
    _screen(controller, "T1", unavailable_abstract=True)

    with pytest.raises(ControllerError, match="must select"):
        controller.finish_retrieval()
    controller.select_reading_subset(["R1"], rationale="complementary authoritative Review", initial=True)
    controller.finish_retrieval()
    with pytest.raises(ControllerError, match="active readable subset"):
        controller.read_full_text("P1", "fake", lambda _: "must not read")

    review_read = controller.read_full_text("R1", "fake", lambda _: "review")
    controller.submit_evidence_card("R1", card(review_read, "R1"))
    controller.finish_reading()
    controller.submit_field_map(_map_for_evidence("R1", coverage=False))
    initial_bytes = (tmp_path / "idea-stage" / "ACTIVE_FIELD_MAP.md").read_bytes()
    initial_sha = controller.status()["research_lit"]["initial_field_map_binding"]["sha256"]
    assert controller.status()["research_lit"]["coverage_review_request"] is None

    controller.select_formal_primary_subset(
        ["P1", "R1"],
        rationale="Initial Map requires a foundational anchor and the Review remains complementary",
    )
    before_reuse = controller.status()["research_lit"]["fulltext_count"]
    primary_read = controller.read_full_text("P1", "fake", lambda _: "primary")
    controller.submit_evidence_card("P1", card(primary_read, "P1"))
    controller.finish_reading()
    # R1 was selected again but did not create a second read event or Evidence Card.
    assert controller.status()["research_lit"]["fulltext_count"] == before_reuse + 1
    assert controller.status()["research_lit"]["formal_primary_selection"]["rationale"].startswith(
        "Initial Map requires"
    )
    controller.submit_field_map(_map_for_evidence("P1", coverage=True))
    history = controller.status()["research_lit"]["field_map_history"]
    archived = next(item for item in history if item["sha256"] == initial_sha)
    assert (tmp_path / archived["archive_path"]).read_bytes() == initial_bytes


def test_initial_review_fallback_and_direct_primary_fallback_are_nonempty_active_passes(
    tmp_path: Path,
) -> None:
    controller = start_controller(tmp_path)
    controller.execute_query("test field", "fake", lambda _: [metadata("R1"), metadata("P1")])
    _screen(controller, "R1", selected=True)
    _screen(controller, "P1", selected=True)
    controller.select_reading_subset(["R1"], rationale="first Review cognition", initial=True)
    controller.finish_retrieval()
    review_read = controller.read_full_text("R1", "fake", lambda _: "review")
    controller.submit_evidence_card("R1", card(review_read, "R1"))
    controller.select_reading_subset(["P1"], rationale="Review Evidence leaves a foundational mechanism unresolved")
    primary_read = controller.read_full_text("P1", "fake", lambda _: "primary fallback")
    controller.submit_evidence_card("P1", card(primary_read, "P1"))
    controller.finish_reading()
    controller.submit_field_map(_map_for_evidence("P1", coverage=False))

    direct = start_controller(tmp_path / "direct")
    # This test's formal runtime root is the nested project.
    old_cwd = Path.cwd()
    os.chdir(direct.root)
    try:
        direct.execute_query("test field", "fake", lambda _: [metadata("P1")])
        _screen(direct, "P1", selected=True)
        direct.select_reading_subset(["P1"], rationale="no usable Review; minimal foundational Primary fallback", initial=True)
        direct.finish_retrieval()
        primary_read = direct.read_full_text("P1", "fake", lambda _: "primary fallback")
        direct.submit_evidence_card("P1", card(primary_read, "P1"))
        direct.finish_reading()
        direct.submit_field_map(_map_for_evidence("P1", coverage=False))
    finally:
        os.chdir(old_cwd)


def test_active_selection_cannot_reactivate_excluded_candidate(tmp_path: Path) -> None:
    controller = start_controller(tmp_path)
    controller.execute_query("test field", "fake", lambda _: [metadata("P1"), metadata("D1")])
    _screen(controller, "P1")
    _screen(controller, "D1", duplicate=True)
    with pytest.raises(ControllerError, match="excluded, duplicate, or out of scope"):
        controller.select_reading_subset(["D1"], rationale="must never wash a duplicate", initial=True)
