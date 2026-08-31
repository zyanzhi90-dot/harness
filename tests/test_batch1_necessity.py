from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from types import MethodType

import pytest

from arisctl import ARISController
from arisctl.validators import (
    ValidationError,
    validate_necessity_closure,
    validate_necessity_verdict,
    validate_query_plan,
)
from arisctl.workflow import load_workflow
from tools import run_state


REPO = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = REPO / "skills" / "shared-references" / "idea-workflow.yaml"


def workflow() -> dict:
    return load_workflow(WORKFLOW_PATH)


def problem_version() -> dict:
    return {
        "problem_id": "P-1",
        "version": 1,
        "contract_sha256": "a" * 64,
        "evidence_capsule_sha256": "b" * 64,
    }


def closure_payload(*, disposition: str = "SAME_ACCEPTED_PROBLEM") -> dict:
    residuals = [] if disposition == "NO_RESIDUAL_FAILURE" else [{
        "residual_failure_id": "RF-1",
        "source_failure_ids": ["F-1"],
        "condition": "shifted operating condition",
        "observable_failure": "error remains above the accepted threshold",
        "consequence": "the accepted decision fails",
        "uncovered_by_repair_assessment_ids": ["SR-1"],
        "evidence_refs": ["E-1"],
    }]
    conclusion = "FULL_COVERAGE" if disposition == "NO_RESIDUAL_FAILURE" else "PARTIAL_COVERAGE"
    return {
        "schema_version": 1,
        "run_id": "run-1",
        "necessity_id": "NEC-1",
        "problem_binding": {
            "problem_id": "P-1",
            "problem_version": 1,
            "problem_contract_sha256": "a" * 64,
            "evidence_capsule_sha256": "b" * 64,
        },
        "active_failures": [{
            "failure_id": "F-1",
            "condition": "shifted operating condition",
            "observable_failure": "error exceeds the accepted threshold",
            "consequence": "the accepted decision fails",
            "evidence_refs": ["E-1"],
        }],
        "operating_envelope": {"conditions": ["shifted operating condition"]},
        "simple_repair_assessments": [{
            "assessment_id": "SR-1",
            "repair": "conventional parameter tuning",
            "applicable_failure_ids": ["F-1"],
            "preserves_core_causal_or_computational_relation": True,
            "evidence_refs": ["E-1"],
            "coverage_boundary": "covers the nominal subset only",
            "coverage_conclusion": conclusion,
            "residual_failure_ids": [] if not residuals else ["RF-1"],
        }],
        "residual_failure_envelope": residuals,
        "problem_identity_disposition": disposition,
        "analysis_provenance": {
            "author_role": "main_research_agent",
            "created_at": "2026-08-30T00:00:00Z",
            "analysis_modes": ["EXISTING_FORMAL_EVIDENCE", "FORMAL_ANALYSIS"],
            "source_artifact_ids": ["E-1"],
        },
    }


def test_partial_repair_requires_explicit_residual_failure_envelope() -> None:
    contract = workflow()["artifact_contracts"]["necessity_closure"]
    closure = closure_payload()
    closure["residual_failure_envelope"] = []
    closure["simple_repair_assessments"][0]["residual_failure_ids"] = []
    with pytest.raises(ValidationError, match="explicit Residual Failure Envelope"):
        validate_necessity_closure(
            closure,
            contract=contract,
            run_id="run-1",
            problem_version=problem_version(),
            current_evidence_ids={"E-1"},
        )


def test_necessity_closure_and_reviewer_verdict_form_bound_residual_handoff() -> None:
    contracts = workflow()["artifact_contracts"]
    closure = validate_necessity_closure(
        closure_payload(),
        contract=contracts["necessity_closure"],
        run_id="run-1",
        problem_version=problem_version(),
        current_evidence_ids={"E-1"},
    )
    closure_sha256 = hashlib.sha256(
        json.dumps(closure, sort_keys=True).encode("utf-8")
    ).hexdigest()
    bindings = {
        "idea-stage/RESEARCH_CONTRACT.md": "a" * 64,
        "idea-stage/PROBLEM_EVIDENCE_CAPSULE.md": "b" * 64,
        "idea-stage/NECESSITY_CLOSURE.json": closure_sha256,
    }
    verdict = {
        "schema_version": 1,
        "run_id": "run-1",
        "review_request_id": "REQ-1",
        "reviewer": "codex-gpt-5.6-sol",
        "verdict_id": "NEC-V-1",
        "necessity_id": "NEC-1",
        "reviewed_closure_sha256": closure_sha256,
        "problem_contract_sha256": "a" * 64,
        "evidence_capsule_sha256": "b" * 64,
        "decision": "RESIDUAL_SAME_PROBLEM",
        "reasons": ["a material residual remains"],
        "issues": [],
        "failure_reality": "PASS",
        "operating_envelope_fidelity": "PASS",
        "simple_repair_coverage": "PASS",
        "residual_failure_fidelity": "PASS",
        "problem_identity_fidelity": "PASS",
        "evidence_sufficiency": "PASS",
        "reviewed_artifact_hashes": bindings,
    }
    validated = validate_necessity_verdict(
        verdict,
        contract=contracts["necessity_verdict"],
        run_id="run-1",
        request_id="REQ-1",
        artifact_bindings=bindings,
        closure=closure,
        reviewed_closure_sha256=closure_sha256,
        problem_contract_sha256="a" * 64,
        evidence_capsule_sha256="b" * 64,
    )
    assert validated["decision"] == "RESIDUAL_SAME_PROBLEM"


def test_fully_covered_is_a_problem_return_not_a_terminal_verdict() -> None:
    w = workflow()
    spec = next(item for item in w["phases"] if item["phase"] == "problem_necessity")
    assert spec["return_targets"]["FULLY_COVERED"] == "problem_generation"
    assert "FULLY_COVERED" not in (spec.get("terminal_verdicts") or {})
    validate_necessity_closure(
        closure_payload(disposition="NO_RESIDUAL_FAILURE"),
        contract=w["artifact_contracts"]["necessity_closure"],
        run_id="run-1",
        problem_version=problem_version(),
        current_evidence_ids={"E-1"},
    )


def test_necessity_query_plan_binds_problem_and_each_failure_repair_target() -> None:
    context = {
        "problem_id": "P-1",
        "problem_version": 1,
        "problem_contract_sha256": "a" * 64,
        "evidence_capsule_sha256": "b" * 64,
    }
    plan = {
        "schema_version": 1,
        "coverage_gaps": [],
        "problem_necessity_context": {
            "search_mode": "NECESSITY_EVIDENCE_RECOVERY",
            **context,
            "decision_targets": [{
                "decision_target_id": "DT-1",
                "failure_id": "F-1",
                "simple_repair_decision_target": "whether conventional tuning covers F-1",
            }],
        },
        "queries": [{
            "query": "conventional tuning failure boundary under shift",
            "purpose": "resolve Simple Repair coverage",
            "decision_target_ids": ["DT-1"],
        }],
    }
    validate_query_plan(plan, problem_necessity_context=context)
    plan["queries"][0]["decision_target_ids"] = []
    with pytest.raises(ValidationError, match="non-empty list"):
        validate_query_plan(plan, problem_necessity_context=context)


def test_workflow_loader_enforces_disjoint_accept_return_terminal_decisions(
    tmp_path: Path,
) -> None:
    w = json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))
    refinement = next(item for item in w["phases"] if item["phase"] == "method_refinement")
    refinement["terminal_verdicts"] = {
        "NO_GO": {
            "action": "terminate_scientific_core",
            "status": "SCIENTIFIC_NO_GO",
        }
    }
    refinement["terminal_verdicts"]["METHOD_READY"] = {
        "action": "terminate_scientific_core",
        "status": "SCIENTIFIC_NO_GO",
    }
    path = tmp_path / "workflow.json"
    path.write_text(json.dumps(w), encoding="utf-8")
    with pytest.raises(ValueError, match="pairwise disjoint"):
        load_workflow(path)


def test_controller_review_request_uses_accept_return_terminal_union() -> None:
    w = workflow()
    spec = deepcopy(
        next(item for item in w["phases"] if item["phase"] == "method_refinement")
    )
    spec["terminal_verdicts"] = {
        "NO_GO": {
            "action": "terminate_scientific_core",
            "status": "SCIENTIFIC_NO_GO",
        }
    }
    controller = object.__new__(ARISController)
    controller.run_id = "run-1"
    controller._require_formal_native_runtime = MethodType(lambda self, role: None, controller)
    controller._phase_input_bindings = MethodType(
        lambda self, state, phase: {"artifact.json": "a" * 64}, controller
    )
    controller._resolved_phase_paths = MethodType(
        lambda self, state, phase, field: [], controller
    )
    request = controller._new_core_review_request(
        {}, {"phase": "method_refinement"}, spec
    )
    assert request["allowed_review_verdicts"] == [
        *spec["accepted_verdicts"],
        *spec["return_targets"].keys(),
        *spec["terminal_verdicts"].keys(),
    ]


class _Store:
    def __init__(self, state: dict):
        self.state = state

    @contextmanager
    def mutate(self):
        yield self.state


def test_controller_terminal_verdict_cannot_take_accept_or_return_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    w = workflow()
    spec = deepcopy(
        next(item for item in w["phases"] if item["phase"] == "method_refinement")
    )
    spec["terminal_verdicts"] = {
        "NO_GO": {
            "action": "terminate_scientific_core",
            "status": "SCIENTIFIC_NO_GO",
        }
    }
    phase = {
        "phase": "method_refinement",
        "status": "done",
        "gate_verdict": "NO_GO",
        "review_request": {"id": "REQ-1"},
    }
    request = {
        "id": "REQ-1",
        "required_reviewer_role": "independent_method_reviewer",
        "terminal_verdicts": ["NO_GO"],
        "artifact_bindings": {"packet.json": "a" * 64},
    }
    state = {
        "scientific_core": {
            "status": "ACTIVE",
            "current_phase": "method_refinement",
            "approval_request": None,
            "problem_revision_request": None,
            "validation_entry": {"status": "BLOCKED_UNTIL_METHOD_CONFIRMATION"},
            "transition_log": [],
        }
    }
    controller = object.__new__(ARISController)
    controller.root = Path(".").resolve()
    controller.run_id = "run-1"
    controller.workflow = w
    controller._store = _Store(state)
    controller._current_core_phase = MethodType(lambda self, current: phase, controller)
    controller._phase_spec = MethodType(lambda self, current, name: spec, controller)
    controller._assert_phase_inputs_current = MethodType(
        lambda self, current, name: None, controller
    )
    controller._assert_core_review_request_current = MethodType(
        lambda self, current, current_phase, current_spec: request, controller
    )
    controller._assert_candidate_verdict_attested = MethodType(
        lambda self, current, current_phase, current_request, result: None, controller
    )
    controller._current_phase_evidence_ids = MethodType(
        lambda self, current, name: {"E-1"}, controller
    )
    no_go = {
        "subject": {
            "final_method_id": "FM-1",
            "fatal_feasibility_debt_ids": ["DEBT-1"],
        },
        "reason": "fatal feasibility excludes the core seed",
        "evidence_refs": ["E-1"],
        "excluded_recoveries": [
            "REVISE", "HOLD", "RETHINK", "RCA_CONFLICT",
            "NECESSITY_CONFLICT", "PROBLEM_CONFLICT",
        ],
    }
    controller._attested_reviewer_payload = MethodType(
        lambda self, **kwargs: {"no_go": deepcopy(no_go)}, controller
    )
    controller._consume_review_attestation = MethodType(
        lambda self, **kwargs: {"payload_sha256": "f" * 64}, controller
    )
    monkeypatch.setattr(
        run_state,
        "_assert_outputs",
        lambda *args, **kwargs: {
            "gate_verdict": "NO_GO",
            "verdict_id": "V-1",
            "reviewer": "codex-gpt-5.6-sol",
            "no_go": deepcopy(no_go),
        },
    )
    result = controller.terminate_scientific_core("V-1", "codex-gpt-5.6-sol")
    core = result["scientific_core"]
    assert core["status"] == "SCIENTIFIC_NO_GO"
    assert core["current_phase"] is None
    assert core["validation_entry"] is None
    assert phase["status"] == "done"
    assert phase["terminal_decision"]["decision"] == "NO_GO"


def test_no_necessity_active_experiment_lifecycle_is_declared() -> None:
    w = workflow()
    serialized = json.dumps(w).lower()
    forbidden = (
        "necessity_test_plan",
        "necessity_execution_approval",
        "necessity_experiment_handoff",
        "necessity_result_submission",
        "necessity_test_evidence_registry",
    )
    assert all(name not in serialized for name in forbidden)
