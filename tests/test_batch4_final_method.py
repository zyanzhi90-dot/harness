from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from arisctl.validators import (
    ValidationError,
    render_final_method_view,
    validate_final_method_packet,
    validate_final_method_view,
)


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = json.loads(
    (ROOT / "skills" / "shared-references" / "idea-workflow.yaml").read_text(
        encoding="utf-8"
    )
)
CONTRACT = WORKFLOW["artifact_contracts"]["final_method_packet"]


def selected_principle() -> dict:
    return {
        "principle_id": "PR-1",
        "principle_version": "1",
        "intervention": "intervene on the failed relation",
        "causal_chain_ids": ["CHAIN-1"],
        "mechanism_change_ids": ["RMC-1"],
        "capability_ids": ["CAP-1"],
        "obligation_ids": ["OBL-1"],
        "activation_conditions": ["activation-A"],
        "failure_conditions": ["failure-A"],
        "accepted_assumptions": [
            {"assumption_id": "ASM-1", "assumption": "assumption A"}
        ],
    }


PROBLEM_BINDING = {
    "problem_id": "P-1",
    "problem_version": 1,
    "problem_contract_sha256": "1" * 64,
    "evidence_capsule_sha256": "2" * 64,
}
NECESSITY_BINDING = {
    "necessity_id": "NEC-1",
    "closure_sha256": "3" * 64,
    "verdict_id": "NEC-V-1",
    "verdict_sha256": "4" * 64,
    "residual_failure_ids": ["RF-1"],
}
ROOT_BINDING = {
    "analysis_id": "RCA-1",
    "analysis_sha256": "5" * 64,
    "verdict_id": "RCA-V-1",
    "verdict_sha256": "6" * 64,
    "primary_causal_chain_ids": ["CHAIN-1"],
}
SELECTED_SHA = "7" * 64


def final_packet() -> dict:
    closure_subjects = [
        ("CAUSAL_CHAIN", "CHAIN-1"),
        ("RMC", "RMC-1"),
        ("CAPABILITY", "CAP-1"),
        ("OBLIGATION", "OBL-1"),
        ("ACTIVATION_CONDITION", "activation-A"),
        ("FAILURE_CONDITION", "failure-A"),
        ("APPLICABILITY_BOUNDARY", "BND-1"),
    ]
    return {
        "schema_version": 1,
        "final_method_id": "FM-1",
        "problem_binding": copy.deepcopy(PROBLEM_BINDING),
        "necessity_binding": copy.deepcopy(NECESSITY_BINDING),
        "root_cause_binding": copy.deepcopy(ROOT_BINDING),
        "selected_principle_binding": {
            "principle_id": "PR-1",
            "principle_version": "1",
            "selected_principle_sha256": SELECTED_SHA,
        },
        "target_constraints": [
            {
                "constraint_id": "TC-1",
                "constraint": "target constraint A",
                "source_ref_ids": ["RF-1"],
                "evidence_refs": ["E1"],
            }
        ],
        "assumption_constraint_collisions": [
            {
                "collision_id": "COL-1",
                "assumption_id": "ASM-1",
                "target_constraint_id": "TC-1",
                "disposition": "ADAPTED",
                "rationale": "the faithful realization adapts the assumption",
                "residual_must_ids": [],
            }
        ],
        "minimal_faithful_realization": {
            "selected_intervention": "intervene on the failed relation",
            "target_realization": "minimal target realization",
            "reused_implementation_machinery": ["ordinary runtime"],
            "core_method_change_ids": ["CMC-1"],
            "fidelity_rationale": "directly realizes the selected intervention",
        },
        "principle_only_closure": [
            {
                "closure_id": f"CLOSE-{index}",
                "subject_type": subject_type,
                "subject_id": subject_id,
                "status": "CLOSED",
                "predicted_mechanism_change": f"change for {subject_id}",
                "rationale": f"closure for {subject_id}",
                "residual_must_ids": [],
            }
            for index, (subject_type, subject_id) in enumerate(closure_subjects, 1)
        ],
        "residual_musts": [],
        "minimal_necessary_composition": [],
        "core_method_changes": [
            {
                "core_method_change_id": "CMC-1",
                "change": "change the failed relation",
                "change_type": "PRINCIPLE_REALIZATION",
                "causal_parent_refs": ["CHAIN-1"],
                "served_rmc_ids": ["RMC-1"],
                "served_capability_ids": ["CAP-1"],
                "served_obligation_ids": ["OBL-1"],
            }
        ],
        "causal_repair_dag": {
            "nodes": [
                {
                    "node_id": "NODE-RCA",
                    "node_type": "PRIMARY_ROOT_CAUSE",
                    "ref_id": "CHAIN-1",
                },
                {
                    "node_id": "NODE-CMC-1",
                    "node_type": "CORE_METHOD_CHANGE",
                    "ref_id": "CMC-1",
                },
            ],
            "edges": [
                {
                    "edge_id": "EDGE-1",
                    "from_node_id": "NODE-RCA",
                    "to_node_id": "NODE-CMC-1",
                    "validation_obligation_id": "VAL-1",
                }
            ],
        },
        "mechanism_delta": {
            "existing_causal_or_computational_relation": "input is statically related to state",
            "new_causal_or_computational_relation": "input is conditioned on the causal state",
            "intervention_change": "make the relation state-conditioned",
            "nearest_prior_separation": [
                {
                    "prior_id": "PRIOR-1",
                    "evidence_refs": ["E1"],
                    "existing_intervention": "static intervention",
                    "existing_mechanism_or_relation": "static relation",
                    "final_separation": "causal-state conditioning at the required position",
                }
            ],
        },
        "intervention_alignment": [
            {
                "alignment_id": "ALIGN-1",
                "rmc_id": "RMC-1",
                "selected_intervention": "intervene on the failed relation",
                "source_intervention": None,
                "final_computational_change_ids": ["CMC-1"],
                "rationale": "the final change implements the selected RMC intervention",
            }
        ],
        "target_only_natural_derivation": {
            "residual_failure_ids": ["RF-1"],
            "root_cause_refs": ["CHAIN-1"],
            "rmc_ids": ["RMC-1"],
            "target_constraint_ids": ["TC-1"],
            "core_method_change_ids": ["CMC-1"],
            "derivation": "RF-1 requires CHAIN-1 repair through RMC-1 under TC-1, yielding CMC-1",
            "source_story_removed": True,
        },
        "feasibility_closure": {
            "supported_conditions": ["observable in the accepted envelope"],
            "unresolved_feasibility_debts": [],
            "claim_restrictions": [],
            "fatality_disposition": "NO_FATAL_DEBT",
        },
        "counterfactual_necessity_obligations": [],
        "final_scientific_delta_claim": {
            "claim_status": "FINAL_PENDING_VALIDATION",
            "claim_elements": [
                {
                    "claim_element_id": "CLAIM-1",
                    "claim": "the state-conditioned relation repairs the causal failure",
                    "causal_chain_ids": ["CHAIN-1"],
                    "mechanism_change_ids": ["RMC-1"],
                    "capability_ids": ["CAP-1"],
                    "obligation_ids": ["OBL-1"],
                    "core_method_change_ids": ["CMC-1"],
                    "boundary_refs": ["BND-1"],
                }
            ],
        },
        "claim_validation_obligations": [
            {
                "validation_obligation_id": "VAL-1",
                "claim_element_id": "CLAIM-1",
                "predicted_mechanism_change": "relation becomes state-conditioned",
                "observed_mechanism_change_required": "observe causal-state conditioning",
                "discriminating_evidence_required": "distinguish from a static relation",
                "performance_consequence_required": "failure decreases in the active envelope",
                "falsifying_pattern": "performance changes without the predicted relation change",
            }
        ],
        "failure_and_applicability_boundaries": [
            {
                "boundary_id": "BND-1",
                "boundary_type": "APPLICABILITY_BOUNDARY",
                "boundary": "accepted operating envelope only",
                "source_refs": ["failure-A"],
            }
        ],
    }


def validate(packet: dict) -> dict:
    return validate_final_method_packet(
        packet,
        contract=CONTRACT,
        problem_binding=PROBLEM_BINDING,
        necessity_binding=NECESSITY_BINDING,
        root_cause_binding=ROOT_BINDING,
        selected_principle=selected_principle(),
        selected_principle_sha256=SELECTED_SHA,
        current_evidence_ids={"E1"},
    )


def test_valid_zero_residual_packet_and_deterministic_view_pass() -> None:
    packet = final_packet()
    result = validate(packet)
    assert result["final_method_id"] == "FM-1"
    assert packet["residual_musts"] == []
    assert packet["minimal_necessary_composition"] == []
    first = render_final_method_view(packet)
    assert first == render_final_method_view(packet)
    assert validate_final_method_view(first, packet) == first
    with pytest.raises(ValidationError, match="exactly match"):
        validate_final_method_view(first + "manual edit\n", packet)


@pytest.mark.parametrize(
    "mutator,match",
    [
        (lambda p: p["problem_binding"].update(problem_version=2), "stale"),
        (
            lambda p: p["final_scientific_delta_claim"]["claim_elements"][0].update(
                mechanism_change_ids=["RMC-UNKNOWN"]
            ),
            "unknown references",
        ),
        (
            lambda p: p["assumption_constraint_collisions"][0].pop("disposition"),
            "missing required fields",
        ),
        (
            lambda p: p["causal_repair_dag"]["edges"][0].update(
                validation_obligation_id="VAL-UNKNOWN"
            ),
            "requires a claim-validation obligation",
        ),
        (
            lambda p: p["target_constraints"][0].update(
                source_ref_ids=["SOURCE-UNKNOWN"]
            ),
            "unknown references",
        ),
    ],
)
def test_packet_rejects_stale_missing_and_unknown_bindings(mutator, match: str) -> None:
    packet = final_packet()
    mutator(packet)
    with pytest.raises(ValidationError, match=match):
        validate(packet)


def test_packet_rejects_cycle_or_structural_orphan() -> None:
    cyclic = final_packet()
    cyclic["causal_repair_dag"]["edges"].append(
        {
            "edge_id": "EDGE-2",
            "from_node_id": "NODE-CMC-1",
            "to_node_id": "NODE-RCA",
            "validation_obligation_id": "VAL-1",
        }
    )
    with pytest.raises(ValidationError, match="acyclic"):
        validate(cyclic)

    orphan = final_packet()
    orphan["target_constraints"].append(
        {
            "constraint_id": "TC-ORPHAN",
            "constraint": "another target constraint",
            "source_ref_ids": ["RF-1"],
            "evidence_refs": [],
        }
    )
    orphan["causal_repair_dag"]["nodes"].append(
        {
            "node_id": "NODE-ORPHAN",
            "node_type": "TARGET_CONSTRAINT",
            "ref_id": "TC-ORPHAN",
        }
    )
    orphan["target_only_natural_derivation"]["target_constraint_ids"].append(
        "TC-ORPHAN"
    )
    with pytest.raises(ValidationError, match="structural orphan"):
        validate(orphan)


def test_support_without_residual_must_is_rejected() -> None:
    packet = final_packet()
    packet["minimal_necessary_composition"] = [
        {
            "support_id": "SUP-1",
            "residual_must_ids": ["MUST-UNKNOWN"],
            "mechanism": "convenience support",
            "activation_conditions": ["always"],
            "integration_interface": "interface",
            "assumption_compatibility": "compatible",
            "core_method_change_ids": ["CMC-1"],
        }
    ]
    with pytest.raises(ValidationError, match="unknown references"):
        validate(packet)


def packet_with_necessary_residual_support() -> dict:
    packet = final_packet()
    chain_closure = next(
        item
        for item in packet["principle_only_closure"]
        if item["subject_type"] == "CAUSAL_CHAIN"
    )
    chain_closure.update(status="RESIDUAL_GAP", residual_must_ids=["MUST-1"])
    packet["residual_musts"] = [
        {
            "residual_must_id": "MUST-1",
            "closure_id": chain_closure["closure_id"],
            "gap": "the principle alone leaves an interface obligation open",
            "acceptance_condition": "the support closes only that interface obligation",
        }
    ]
    packet["minimal_necessary_composition"] = [
        {
            "support_id": "SUP-1",
            "residual_must_ids": ["MUST-1"],
            "mechanism": "bridge the residual interface",
            "activation_conditions": ["activation-A"],
            "integration_interface": "the retained principle output",
            "assumption_compatibility": "does not alter the selected intervention",
            "core_method_change_ids": ["CMC-2"],
        }
    ]
    packet["core_method_changes"].append(
        {
            "core_method_change_id": "CMC-2",
            "change": "add the minimal residual interface bridge",
            "change_type": "RESIDUAL_SUPPORT",
            "causal_parent_refs": ["CHAIN-1"],
            "served_rmc_ids": ["RMC-1"],
            "served_capability_ids": ["CAP-1"],
            "served_obligation_ids": ["OBL-1"],
        }
    )
    packet["causal_repair_dag"]["nodes"].append(
        {
            "node_id": "NODE-CMC-2",
            "node_type": "CORE_METHOD_CHANGE",
            "ref_id": "CMC-2",
        }
    )
    packet["causal_repair_dag"]["edges"].append(
        {
            "edge_id": "EDGE-2",
            "from_node_id": "NODE-RCA",
            "to_node_id": "NODE-CMC-2",
            "validation_obligation_id": "VAL-1",
        }
    )
    packet["intervention_alignment"][0]["final_computational_change_ids"].append(
        "CMC-2"
    )
    packet["target_only_natural_derivation"]["core_method_change_ids"].append(
        "CMC-2"
    )
    packet["final_scientific_delta_claim"]["claim_elements"][0][
        "core_method_change_ids"
    ].append("CMC-2")
    packet["counterfactual_necessity_obligations"] = [
        {
            "counterfactual_obligation_id": "CF-1",
            "support_id": "SUP-1",
            "removal_condition": "remove CMC-2 while retaining the principle realization",
            "expected_failed_closure_ids": [chain_closure["closure_id"]],
            "discriminating_consequence": "the residual interface obligation reopens",
            "evidence_status": "FUTURE_OBLIGATION",
        }
    ]
    return packet


def test_residual_support_requires_a_future_counterfactual_obligation() -> None:
    packet = packet_with_necessary_residual_support()
    assert validate(packet)["final_method_id"] == "FM-1"

    packet["counterfactual_necessity_obligations"][0]["evidence_status"] = "SUPPORTED"
    with pytest.raises(ValidationError, match="future obligation"):
        validate(packet)

    packet = packet_with_necessary_residual_support()
    packet["minimal_necessary_composition"] = []
    packet["core_method_changes"] = [packet["core_method_changes"][0]]
    packet["causal_repair_dag"]["nodes"] = packet["causal_repair_dag"]["nodes"][:2]
    packet["causal_repair_dag"]["edges"] = packet["causal_repair_dag"]["edges"][:1]
    packet["intervention_alignment"][0]["final_computational_change_ids"] = ["CMC-1"]
    packet["target_only_natural_derivation"]["core_method_change_ids"] = ["CMC-1"]
    packet["final_scientific_delta_claim"]["claim_elements"][0][
        "core_method_change_ids"
    ] = ["CMC-1"]
    packet["counterfactual_necessity_obligations"] = []
    with pytest.raises(ValidationError, match="cover every Residual MUST"):
        validate(packet)


def packet_with_claim_restriction() -> dict:
    packet = final_packet()
    packet["failure_and_applicability_boundaries"].append(
        {
            "boundary_id": "BND-RESTRICT-1",
            "boundary_type": "CLAIM_RESTRICTION",
            "boundary": "claim only inside the accepted observable envelope",
            "source_refs": ["DEBT-1"],
        }
    )
    packet["final_scientific_delta_claim"]["claim_elements"][0]["boundary_refs"].append(
        "BND-RESTRICT-1"
    )
    packet["feasibility_closure"].update(
        unresolved_feasibility_debts=[
            {
                "debt_id": "DEBT-1",
                "dimension": "observability",
                "debt": "the mechanism is observable only inside the accepted envelope",
                "fatal": False,
                "evidence_refs": ["E1"],
                "restriction_ids": ["RESTRICT-1"],
                "repair_disposition": "REPAIR_NOT_REQUIRED_FOR_BOUNDED_CLAIM",
                "claim_restriction_disposition": "RESTRICT_TO_ACCEPTED_ENVELOPE",
                "excluded_recovery_evidence_refs": [],
            }
        ],
        claim_restrictions=[
            {
                "restriction_id": "RESTRICT-1",
                "claim_element_ids": ["CLAIM-1"],
                "debt_ids": ["DEBT-1"],
                "boundary_id": "BND-RESTRICT-1",
            }
        ],
    )
    return packet


def test_nonfatal_feasibility_debt_claim_restriction_closes_to_claim_boundary() -> None:
    packet = packet_with_claim_restriction()
    assert validate(packet)["fatality_disposition"] == "NO_FATAL_DEBT"
    assert {
        (item["subject_type"], item["subject_id"])
        for item in packet["principle_only_closure"]
    } == {
        ("CAUSAL_CHAIN", "CHAIN-1"),
        ("RMC", "RMC-1"),
        ("CAPABILITY", "CAP-1"),
        ("OBLIGATION", "OBL-1"),
        ("ACTIVATION_CONDITION", "activation-A"),
        ("FAILURE_CONDITION", "failure-A"),
        ("APPLICABILITY_BOUNDARY", "BND-1"),
    }

    packet["feasibility_closure"]["claim_restrictions"] = []
    with pytest.raises(ValidationError, match="without a formal claim restriction"):
        validate(packet)


@pytest.mark.parametrize(
    "mutator,match",
    [
        (
            lambda p: p["feasibility_closure"]["claim_restrictions"][0].update(
                boundary_id="BND-UNKNOWN"
            ),
            "unknown boundary",
        ),
        (
            lambda p: p["feasibility_closure"]["claim_restrictions"][0].update(
                boundary_id="BND-1"
            ),
            "must reference a CLAIM_RESTRICTION boundary",
        ),
        (
            lambda p: p["final_scientific_delta_claim"]["claim_elements"][0][
                "boundary_refs"
            ].remove("BND-RESTRICT-1"),
            "must be referenced by every restricted claim element",
        ),
        (
            lambda p: p["feasibility_closure"]["claim_restrictions"][0].pop(
                "boundary_id"
            ),
            "missing required fields",
        ),
        (
            lambda p: p["feasibility_closure"]["claim_restrictions"][0].update(
                boundary="legacy duplicate scientific truth"
            ),
            "unsupported fields",
        ),
    ],
)
def test_claim_restriction_reference_contract_rejects_invalid_links(mutator, match: str) -> None:
    packet = packet_with_claim_restriction()
    mutator(packet)
    with pytest.raises(ValidationError, match=match):
        validate(packet)


def test_claim_restriction_boundaries_require_restriction_and_claim_links() -> None:
    packet = packet_with_claim_restriction()
    packet["feasibility_closure"]["claim_restrictions"] = []
    packet["feasibility_closure"]["unresolved_feasibility_debts"] = []
    with pytest.raises(ValidationError, match="without a formal claim restriction"):
        validate(packet)

    packet = final_packet()
    packet["failure_and_applicability_boundaries"].append(
        {
            "boundary_id": "BND-ORPHAN",
            "boundary_type": "CLAIM_RESTRICTION",
            "boundary": "canonical restriction with no restriction record",
            "source_refs": ["DEBT-1"],
        }
    )
    with pytest.raises(ValidationError, match="not referenced by a formal claim restriction"):
        validate(packet)


def test_claim_restrictions_may_share_a_canonical_boundary() -> None:
    packet = packet_with_claim_restriction()
    packet["feasibility_closure"]["unresolved_feasibility_debts"].append(
        {
            "debt_id": "DEBT-2",
            "dimension": "measurement",
            "debt": "measurement remains bounded by the accepted observable envelope",
            "fatal": False,
            "evidence_refs": ["E1"],
            "restriction_ids": ["RESTRICT-2"],
            "repair_disposition": "REPAIR_NOT_REQUIRED_FOR_BOUNDED_CLAIM",
            "claim_restriction_disposition": "RESTRICT_TO_ACCEPTED_ENVELOPE",
            "excluded_recovery_evidence_refs": [],
        }
    )
    packet["feasibility_closure"]["claim_restrictions"].append(
        {
            "restriction_id": "RESTRICT-2",
            "claim_element_ids": ["CLAIM-1"],
            "debt_ids": ["DEBT-2"],
            "boundary_id": "BND-RESTRICT-1",
        }
    )
    assert validate(packet)["fatality_disposition"] == "NO_FATAL_DEBT"


def test_mechanically_legal_but_scientifically_unnecessary_change_stays_validator_pass() -> None:
    packet = final_packet()
    packet["target_constraints"].append(
        {
            "constraint_id": "TC-2",
            "constraint": "claimed target constraint requiring semantic review",
            "source_ref_ids": ["RF-1"],
            "evidence_refs": ["E1"],
        }
    )
    packet["core_method_changes"].append(
        {
            "core_method_change_id": "CMC-2",
            "change": "scientifically unnecessary but structurally well-formed module",
            "change_type": "PRINCIPLE_REALIZATION",
            "causal_parent_refs": ["TC-2"],
            "served_rmc_ids": ["RMC-1"],
            "served_capability_ids": ["CAP-1"],
            "served_obligation_ids": ["OBL-1"],
        }
    )
    packet["minimal_faithful_realization"]["core_method_change_ids"].append("CMC-2")
    packet["final_scientific_delta_claim"]["claim_elements"][0][
        "core_method_change_ids"
    ].append("CMC-2")
    packet["target_only_natural_derivation"]["target_constraint_ids"].append("TC-2")
    packet["target_only_natural_derivation"]["core_method_change_ids"].append("CMC-2")
    packet["intervention_alignment"][0]["final_computational_change_ids"].append(
        "CMC-2"
    )
    packet["causal_repair_dag"]["nodes"].extend(
        [
            {
                "node_id": "NODE-TC-2",
                "node_type": "TARGET_CONSTRAINT",
                "ref_id": "TC-2",
            },
            {
                "node_id": "NODE-CMC-2",
                "node_type": "CORE_METHOD_CHANGE",
                "ref_id": "CMC-2",
            },
        ]
    )
    packet["causal_repair_dag"]["edges"].append(
        {
            "edge_id": "EDGE-2",
            "from_node_id": "NODE-TC-2",
            "to_node_id": "NODE-CMC-2",
            "validation_obligation_id": "VAL-1",
        }
    )
    assert validate(packet)["final_method_id"] == "FM-1"
    # Scientific necessity is intentionally left to independent_method_reviewer.


def test_workflow_binds_formal_review_to_packet_and_declares_no_go() -> None:
    phase = next(
        item for item in WORKFLOW["phases"] if item["phase"] == "method_refinement"
    )
    assert phase["produced_artifacts"] == [
        "@artifact:final_method_packet",
        "@artifact:final_proposal",
        "@artifact:final_method_review",
        "@artifact:refine_state",
    ]
    assert phase["reviewed_artifacts"] == ["@artifact:final_method_packet"]
    assert phase["return_targets"] == {
        "REVISE": "method_refinement",
        "RETHINK": "method_design",
        "HOLD": "method_refinement",
        "RCA_CONFLICT": "root_cause_analysis",
        "NECESSITY_CONFLICT": "problem_necessity",
        "PROBLEM_CONFLICT": "problem_generation",
    }
    assert phase["terminal_verdicts"] == {
        "NO_GO": {
            "action": "terminate_scientific_core",
            "status": "SCIENTIFIC_NO_GO",
        }
    }
    assert "top_venue_method_strength_gate" not in WORKFLOW["scientific_core"]["phases"]


def test_refinement_reviewer_owns_the_most_upstream_conflict_layer() -> None:
    reviewer = (
        ROOT / ".codex" / "agents" / "independent_method_reviewer.toml"
    ).read_text(encoding="utf-8")
    protocol = (
        ROOT / "skills" / "shared-references" / "method-refinement-protocol.md"
    ).read_text(encoding="utf-8")
    for marker in (
        "`PROBLEM_CONFLICT` when the accepted Problem identity or premise fails",
        "`NECESSITY_CONFLICT` when the Problem remains valid but the accepted Necessity premise or residual failure envelope fails",
        "`RCA_CONFLICT` when Problem and Necessity remain valid but RCA fails",
        "`RETHINK` when those upstream premises remain valid but the Selected Principle fails",
        "`REVISE` or `HOLD` when only the final Method realization or refinement is defective",
        "Main analysis, findings, warnings, and proposed consequences have no transition authority",
    ):
        assert marker in reviewer
    assert "most upstream accepted scientific premise" in protocol
    assert "merely involves an upstream object does not justify escalation" in protocol
    assert "Validator" not in reviewer.split(
        "Return the most upstream accepted scientific premise", 1
    )[1].split("`METHOD_READY` advances", 1)[0]
