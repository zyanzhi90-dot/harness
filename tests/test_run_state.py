"""Tests for tools/run_state.py — resumable run-state with the done/accepted split."""

import sys
import tempfile
import json
import hashlib
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import run_state as rs  # noqa: E402

PHASES = ["W1", "W1.5", "W2", "W3"]


def _tmp():
    return tempfile.TemporaryDirectory()


def _workflow_artifact(path: str, name: str) -> str:
    workflow = json.loads(Path(path).read_text(encoding="utf-8"))
    return workflow["artifact_manifest"][name]


def _write_landscape_artifacts(root: str, workflow: str, status: str = "SUFFICIENT") -> None:
    evidence = {
        "source_id": "S1",
        "claim": "test",
        "claim_locator": "p.1",
        "access_level": "full_text",
        "decision_grade": "decision_grade",
        "epistemic_status": "supported",
        "problem_and_setting": "test",
        "method_or_mechanism": "test",
        "content_summary": "test",
        "synthesis_role": "anchor",
        "development_link": "origin",
        "evidence": "test",
        "evidence_kind": "experiment",
        "boundary_conditions": "test",
        "assumptions": ["test"],
        "reported_or_inferred_failures": {"reported": [], "inferred": []},
        "conflicts_with": [],
        "verification_status": "verified",
    }
    ledger = {
        "timestamp": "2026-08-09T00:00:00Z",
        "run_id": "legacy-test",
        "stage": "METADATA_RETRIEVAL",
        "action": "query",
        "query_id": "Q0001",
        "query": "test",
        "paper_id": None,
        "tool": "test-gateway",
        "result_status": "complete",
        "admission_decision": None,
        "budget_before": {"queries": 0, "fulltext": 0},
        "budget_after": {"queries": 1, "fulltext": 0},
    }
    payloads = {
        "active_field_map": f"coverage_status: {status}\ncoverage_record:\n  query_id: q1\n  research_effort_budget: default\n  stopping_reason: tested\n",
        "evidence_registry": json.dumps(evidence) + "\n",
        "literature_corpus": json.dumps({
            "source_id": "S1",
            "context_decisions": [{
                "decision_id": "admission-landscape-s1",
                "context": {
                    "paper_id": "S1",
                    "phase": "landscape",
                    "query_plan_sha256": "a" * 64,
                    "phase_binding_anchor": {"query_plan_sha256": "a" * 64},
                    "decision_targets": [],
                },
                "admission_status": "ADMIT_DECISION_GRADE",
                "screening_in_scope": True,
                "screening_status": "IN_SCOPE",
                "duplicate": False,
                "screening_basis": "FULL_TEXT",
                "screening_reason": "fixture source supports the landscape map",
                "reading_priority": "TARGETED_GAP_FOLLOWUP",
                "fulltext_selected": True,
                "fulltext_selection_reason": None,
                "admission_exception": None,
            }],
        }) + "\n",
        "source_admission_policy": "field: test\nactive_read_gate: high_citation_or_elite_venue\nuser_supplied: exempt\n",
        "search_log": json.dumps(ledger) + "\n",
    }
    for name, content in payloads.items():
        path = Path(root) / _workflow_artifact(workflow, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _accept_necessity_fixture(root: str, run_id: str) -> dict:
    stage = Path(root) / "idea-stage"
    stage.mkdir(parents=True, exist_ok=True)
    closure_path = stage / "NECESSITY_CLOSURE.json"
    verdict_path = stage / "NECESSITY_VERDICT.json"
    closure = {
        "necessity_id": "NEC-1",
        "residual_failure_envelope": [{"residual_failure_id": "RF-1"}],
    }
    closure_path.write_text(json.dumps(closure), encoding="utf-8")
    verdict = {
        "verdict_id": "NEC-V-1",
        "necessity_id": "NEC-1",
        "reviewed_closure_sha256": _file_sha256(closure_path),
        "decision": "RESIDUAL_SAME_PROBLEM",
    }
    verdict_path.write_text(json.dumps(verdict), encoding="utf-8")
    state = rs._load(root, run_id)
    phase = rs._find_phase(state, "problem_necessity")
    phase["status"] = "accepted"
    phase["validated_artifacts"] = {
        "idea-stage/NECESSITY_CLOSURE.json": _file_sha256(closure_path),
        "idea-stage/NECESSITY_VERDICT.json": _file_sha256(verdict_path),
    }
    rs._save(root, run_id, state)
    return {
        "necessity_id": "NEC-1",
        "closure_sha256": _file_sha256(closure_path),
        "verdict_id": "NEC-V-1",
        "verdict_sha256": _file_sha256(verdict_path),
        "residual_failure_ids": ["RF-1"],
    }


def _write_root_cause_artifacts(
    root: str,
    run_id: str,
    *,
    decision: str = "DIAGNOSIS_READY",
    reviewer: str = "codex-gpt-5.5",
) -> tuple[str, str]:
    stage = Path(root) / "idea-stage"
    contract = stage / "RESEARCH_CONTRACT.md"
    capsule = stage / "PROBLEM_EVIDENCE_CAPSULE.md"
    analysis_path = stage / "ROOT_CAUSE_ANALYSIS.json"
    view_path = stage / "ROOT_CAUSE_ANALYSIS.md"
    verdict_path = stage / "ROOT_CAUSE_VERDICT.json"
    necessity_binding = _accept_necessity_fixture(root, run_id)
    analysis = {
        "schema_version": 1,
        "run_id": run_id,
        "analysis_id": "RCA-1",
        "problem_id": "P1",
        "problem_contract_sha256": _file_sha256(contract),
        "evidence_capsule_sha256": _file_sha256(capsule),
        "necessity_binding": necessity_binding,
        "failure_observations": [{
            "observation_id": "O1",
            "phenomenon": "output degrades under shift",
            "conditions": "shifted input",
            "abnormal_variables": ["error_rate"],
            "evidence_source_type": "literature",
            "evidence_refs": ["E1"],
            "epistemic_status": "supported",
        }],
        "phenomenon_clusters": [{
            "cluster_id": "C1",
            "observation_ids": ["O1"],
            "grouping_rationale": "one evidenced failure mode",
        }],
        "causal_depth_traces": [{
            "trace_id": "T1",
            "cluster_id": "C1",
            "why_steps": [{
                "step_id": "W1",
                "effect": "output degradation",
                "candidate_cause": "state estimator loses calibration",
                "evidence_refs": ["E1"],
                "epistemic_status": "supported",
                "discriminating_observation": "calibration remains stable under matched shift",
            }],
        }],
        "causal_chains": [{
            "chain_id": "CHAIN-1",
            "cluster_ids": ["C1"],
            "conditions_or_input_change": "shifted input",
            "mechanism_failure": "state estimator loses calibration",
            "intermediate_state_abnormality": "uncertainty is underestimated",
            "final_failure_phenomenon": "output degrades",
            "evidence_refs": ["E1"],
            "alternative_explanations": [{
                "explanation_id": "ALT-1",
                "mechanism": "label noise",
                "epistemic_status": "preliminary",
                "discriminating_evidence": "clean-label shifted evaluation",
            }],
            "intervention_target": "state calibration mechanism",
            "falsifier": "calibration correction does not change the failure",
            "epistemic_status": "supported",
        }],
        "primary_causal_chain_ids": ["CHAIN-1"],
        "unresolved_questions": [],
        "analysis_provenance": {
            "author_role": "main_research_agent",
            "created_at": "2026-08-10T00:00:00Z",
            "source_artifact_ids": ["P1", "E1"],
        },
    }
    analysis_path.write_text(json.dumps(analysis), encoding="utf-8")
    view_path.write_text(
        "# Root Cause\n\n"
        f"RCA-1; P1; CHAIN-1; {analysis['problem_contract_sha256']}; "
        f"{analysis['evidence_capsule_sha256']}; NEC-1; NEC-V-1; RF-1; "
        f"{necessity_binding['closure_sha256']}; {necessity_binding['verdict_sha256']}",
        encoding="utf-8",
    )
    verdict = {
        "schema_version": 1,
        "run_id": run_id,
        "verdict_id": "RCA-V-1",
        "reviewer": reviewer,
        "analysis_id": "RCA-1",
        "reviewed_analysis_sha256": _file_sha256(analysis_path),
        "problem_contract_sha256": _file_sha256(contract),
        "evidence_capsule_sha256": _file_sha256(capsule),
        "necessity_closure_sha256": necessity_binding["closure_sha256"],
        "necessity_verdict_sha256": necessity_binding["verdict_sha256"],
        "decision": decision,
        "reasons": ["fixture review"],
        "issues": [] if decision == "DIAGNOSIS_READY" else [{
            "issue_id": "I1", "severity": "BLOCKING", "message": "revise diagnosis"
        }],
        "observation_fidelity": "PASS",
        "grouping_adequacy": "PASS",
        "causal_depth": "PASS",
        "explanatory_coverage": "PASS",
        "evidence_calibration": "PASS",
        "intervention_relevance": "PASS",
        "falsifiability": "PASS",
        "residual_failure_fidelity": "PASS",
    }
    verdict_path.write_text(json.dumps(verdict), encoding="utf-8")
    return verdict["verdict_id"], reviewer


def _advance_through_root_cause(root: str, run_id: str, *, decision: str = "DIAGNOSIS_READY") -> None:
    _accept_necessity_fixture(root, run_id)
    rs.set_status(root, run_id, "root_cause_analysis", "running")
    verdict_id, reviewer = _write_root_cause_artifacts(root, run_id, decision=decision)
    rs.set_status(root, run_id, "root_cause_analysis", "done")
    rs.set_status(root, run_id, "root_cause_gate", "running")
    rs.set_status(root, run_id, "root_cause_gate", "done")
    rs.accept(root, run_id, "root_cause_gate", verdict_id, reviewer)


def test_start_creates_pending_phases():
    with _tmp() as d:
        st = rs.start_run(d, "run-a", PHASES)
        assert [p["phase"] for p in st["phases"]] == PHASES
        assert all(p["status"] == "pending" for p in st["phases"])
        # resume of a fresh run points at the first phase
        assert rs.resume_point(d, "run-a")["phase"] == "W1"


def test_start_is_idempotent():
    with _tmp() as d:
        rs.start_run(d, "run-a", PHASES)
        rs.set_status(d, "run-a", "W1", "done")
        again = rs.start_run(d, "run-a", PHASES)  # must NOT clobber progress
        assert rs._find_phase(again, "W1")["status"] == "done"


def test_set_status_cannot_write_accepted():
    with _tmp() as d:
        rs.start_run(d, "run-a", PHASES)
        for ok in ("running", "done", "failed"):
            rs.set_status(d, "run-a", "W1", ok)
        for reserved in ("accepted", "provisional"):
            try:
                rs.set_status(d, "run-a", "W1", reserved)
                raised = False
            except ValueError:
                raised = True
            assert raised, f"set_status must refuse to write {reserved!r}"


def test_accept_requires_verdict_and_reviewer():
    with _tmp() as d:
        rs.start_run(d, "run-a", PHASES)
        for vid, rev in (("", "codex"), ("codex:1", ""), ("", "")):
            try:
                rs.accept(d, "run-a", "W1", vid, rev)
                raised = False
            except ValueError:
                raised = True
            assert raised, f"accept must require both verdict_id and reviewer (got {vid!r},{rev!r})"
        rs.set_status(d, "run-a", "W1", "done")  # accept now requires the phase be done
        st = rs.accept(d, "run-a", "W1", "codex:019e", "codex-gpt-5.5")
        ph = rs._find_phase(st, "W1")
        assert ph["status"] == "accepted" and ph["verdict_id"] == "codex:019e" and ph["reviewer"] == "codex-gpt-5.5"


def test_accept_requires_phase_done():
    with _tmp() as d:
        rs.start_run(d, "run-a", PHASES)
        # Cannot accept a phase that never ran (still pending).
        try:
            rs.accept(d, "run-a", "W1", "v:1", "codex")
            raised = False
        except ValueError:
            raised = True
        assert raised, "accept must refuse a non-done phase without force"
        # --force overrides (e.g. a purely deterministic phase with no executor step).
        rs.accept(d, "run-a", "W1", "v:1", "deterministic:x", force=True)
        assert rs._find_phase(rs._load(d, "run-a"), "W1")["status"] == "accepted"
        # The normal path: done → accept.
        rs.set_status(d, "run-a", "W2", "done")
        rs.accept(d, "run-a", "W2", "v:2", "codex")
        assert rs._find_phase(rs._load(d, "run-a"), "W2")["status"] == "accepted"


def test_accept_uses_recorded_executor_family_when_available():
    with _tmp() as d:
        rs.start_run(d, "run-a", PHASES, executor="codex-gpt-5.5")
        rs.set_status(d, "run-a", "W1", "done")
        try:
            rs.accept(d, "run-a", "W1", "agent:self", "gpt-5.5")
            raised = False
        except ValueError:
            raised = True
        assert raised, "known same-family review must use mark_provisional"

        accepted = rs.accept(d, "run-a", "W1", "claude:1", "claude-opus-4-8")
        phase = rs._find_phase(accepted, "W1")
        assert phase["status"] == "accepted"
        assert phase["review_independence"] == "cross-family"
        assert phase["reviewer_family"] == "anthropic"


def test_legacy_state_defaults_to_claude_and_rejects_unknown_reviewer():
    import json
    with _tmp() as d:
        # Pre-provenance JSON had no executor/family/acceptance fields. Its
        # historical mainline executor was Claude, so a Codex verdict remains
        # compatible and becomes explicit rather than unclassified.
        run_path = Path(d) / ".aris" / "runs" / "run-a.json"
        run_path.parent.mkdir(parents=True)
        legacy = {
            "run_id": "run-a",
            "created": "2026-01-01T00:00:00Z",
            "updated": "2026-01-01T00:00:00Z",
            "phases": [
                {"phase": phase, "status": "done" if phase == "W1" else "pending",
                 "artifact": None, "verdict_id": None, "reviewer": None,
                 "updated": "2026-01-01T00:00:00Z"}
                for phase in PHASES
            ],
        }
        run_path.write_text(json.dumps(legacy), encoding="utf-8")
        state = rs.accept(d, "run-a", "W1", "codex:1", "codex-gpt-5.5")
        phase = rs._find_phase(state, "W1")
        assert phase["executor_model"] == "claude"
        assert phase["executor_family"] == "anthropic"

        rs.set_status(d, "run-a", "W1.5", "done")
        try:
            rs.accept(d, "run-a", "W1.5", "mystery:1", "mystery-reviewer")
            raised = False
        except ValueError:
            raised = True
        assert raised, "unclassified reviewers must never receive accepted status"


def test_skipped_is_terminal_for_resume():
    with _tmp() as d:
        rs.start_run(d, "run-a", PHASES)
        rs.set_status(d, "run-a", "W1", "done"); rs.accept(d, "run-a", "W1", "v", "codex")
        rs.set_status(d, "run-a", "W1.5", "skipped")   # phase doesn't apply to this run
        rs.set_status(d, "run-a", "W2", "done"); rs.accept(d, "run-a", "W2", "v", "codex")
        rs.set_status(d, "run-a", "W3", "skipped")
        # Only accepted/skipped are terminal → all terminal → resume COMPLETE.
        assert rs.resume_point(d, "run-a") is None


def test_resume_skips_only_accepted_not_done():
    """The load-bearing invariant: a `done`-but-unaccepted phase is STILL a resume target."""
    with _tmp() as d:
        rs.start_run(d, "run-a", PHASES)
        rs.set_status(d, "run-a", "W1", "done")
        rs.accept(d, "run-a", "W1", "codex:1", "codex")     # W1 accepted
        rs.set_status(d, "run-a", "W1.5", "done")           # W1.5 done but NOT accepted (crashed before audit)
        # resume must return W1.5 (first non-accepted), NOT W2 — done != accepted.
        assert rs.resume_point(d, "run-a")["phase"] == "W1.5"
        # accept W1.5, then resume advances to W2 (still pending).
        rs.accept(d, "run-a", "W1.5", "codex:2", "codex")
        assert rs.resume_point(d, "run-a")["phase"] == "W2"


def test_mark_provisional_records_same_family_review():
    with _tmp() as d:
        rs.start_run(d, "run-a", PHASES, executor="codex-gpt-5.5")
        rs.set_status(d, "run-a", "W1", "done", artifact="idea-stage/IDEA_REPORT.md")
        state = rs.mark_provisional(
            d,
            "run-a",
            "W1",
            verdict_id="agent:019f",
            reviewer="gpt-5.5",
        )
        phase = rs._find_phase(state, "W1")
        assert phase["status"] == "provisional"
        assert phase["acceptance_status"] == "provisional"
        assert phase["review_independence"] == "same-family"
        assert phase["executor_model"] == "codex-gpt-5.5"
        assert phase["executor_family"] == "openai"
        assert phase["reviewer"] == "gpt-5.5"
        assert phase["reviewer_family"] == "openai"


def test_mark_provisional_requires_done_and_same_family():
    with _tmp() as d:
        rs.start_run(d, "run-a", PHASES, executor="codex-gpt-5.5")
        for reviewer in ("gpt-5.5", "gemini-3.1-pro", "mystery-model"):
            try:
                rs.mark_provisional(d, "run-a", "W1", "agent:1", reviewer)
                raised = False
            except ValueError:
                raised = True
            assert raised, "a pending phase cannot be marked provisional"

        rs.set_status(d, "run-a", "W1", "done")
        for reviewer in ("gemini-3.1-pro", "mystery-model", "deterministic:pytest"):
            try:
                rs.mark_provisional(d, "run-a", "W1", "agent:1", reviewer)
                raised = False
            except ValueError:
                raised = True
            assert raised, f"reviewer {reviewer!r} is not a same-family Codex review"


def test_provisional_advances_only_under_explicit_policy():
    # Codex-native mirror: start_run opts IN, provisional closes the phase for resume
    with _tmp() as d:
        rs.start_run(d, "run-a", PHASES, executor="codex", provisional_advances=True)
        rs.set_status(d, "run-a", "W1", "done")
        rs.mark_provisional(d, "run-a", "W1", "agent:1", "gpt-5.6-sol")
        assert rs.resume_point(d, "run-a")["phase"] == "W1.5"
        for phase in PHASES[1:]:
            rs.set_status(d, "run-a", phase, "skipped")
        assert rs.resume_point(d, "run-a") is None


def test_provisional_does_not_advance_mainline_default():
    # mainline default policy: a same-family provisional verdict is NOT terminal —
    # the phase remains the resume target until a cross-family acceptance lands
    with _tmp() as d:
        rs.start_run(d, "run-a", PHASES, executor="codex")
        rs.set_status(d, "run-a", "W1", "done")
        rs.mark_provisional(d, "run-a", "W1", "agent:1", "gpt-5.6-sol")
        assert rs.resume_point(d, "run-a")["phase"] == "W1"


def test_provisional_upgrades_to_accepted_by_cross_family():
    # the monotonic path: a later Claude/Gemini overlay acquits a provisional phase
    with _tmp() as d:
        rs.start_run(d, "run-a", PHASES, executor="codex")
        rs.set_status(d, "run-a", "W1", "done")
        rs.mark_provisional(d, "run-a", "W1", "agent:1", "gpt-5.6-sol")
        st = rs.accept(d, "run-a", "W1", "claude:v1", "claude-opus-4-8")
        ph = next(p for p in st["phases"] if p["phase"] == "W1")
        assert ph["status"] == "accepted"
        assert ph["review_independence"] == "cross-family"
        assert rs.resume_point(d, "run-a")["phase"] == "W1.5"


def test_resume_none_when_all_accepted():
    with _tmp() as d:
        rs.start_run(d, "run-a", PHASES)
        for ph in PHASES:
            rs.set_status(d, "run-a", ph, "done")
            rs.accept(d, "run-a", ph, f"v:{ph}", "deterministic:test")
        assert rs.resume_point(d, "run-a") is None


def test_invalid_run_id_rejected():
    with _tmp() as d:
        for bad in ("../escape", "a/b", "a b", "a;rm"):
            try:
                rs.start_run(d, bad, PHASES)
                raised = False
            except ValueError:
                raised = True
            assert raised, f"invalid run_id {bad!r} must be rejected"


def test_unknown_phase_raises():
    with _tmp() as d:
        rs.start_run(d, "run-a", PHASES)
        try:
            rs.set_status(d, "run-a", "W9", "done")
            raised = False
        except KeyError:
            raised = True
        assert raised


def test_state_is_valid_json_on_disk():
    import json
    with _tmp() as d:
        rs.start_run(d, "run-a", PHASES)
        rs.set_status(d, "run-a", "W1", "done", artifact="x/y.md")
        p = Path(d) / ".aris" / "runs" / "run-a.json"
        state = json.loads(p.read_text())  # must parse
        assert rs._find_phase(state, "W1")["artifact"] == "x/y.md"


def test_declared_workflow_enforces_dependencies_and_human_checkpoint():
    repo = Path(__file__).resolve().parents[1]
    workflow = str(repo / "skills" / "shared-references" / "idea-workflow.yaml")
    with _tmp() as d:
        state = rs.start_run(d, "idea-v2", [], workflow_path=workflow)
        assert state["phases"][0]["phase"] == "landscape"

        rs.set_status(d, "idea-v2", "landscape", "running")
        _write_landscape_artifacts(d, workflow)
        rs.set_status(d, "idea-v2", "landscape", "done")
        rs.accept(d, "idea-v2", "landscape", "map:1", "deterministic:pytest")

        with pytest.raises(ValueError, match="force is limited"):
            rs.accept(d, "idea-v2", "problem_quality_gate", "spoof:1", "deterministic:pytest", force=True)

        with pytest.raises(ValueError, match="human checkpoint"):
            rs.accept(d, "idea-v2", "scope_human_approval", "spoof:1", "deterministic:pytest", force=True)
        rs.approve_human(d, "idea-v2", "scope_human_approval", "scope accepted")
        phase = rs._find_phase(rs._load(d, "idea-v2"), "scope_human_approval")
        assert phase["status"] == "human_accepted"
        assert phase["acceptance_status"] == "human_accepted"
        assert rs.resume_point(d, "idea-v2")["phase"] == "problem_generation"


def test_declared_workflow_blocks_nonterminal_dependencies_and_missing_handoffs():
    repo = Path(__file__).resolve().parents[1]
    workflow = str(repo / "skills" / "shared-references" / "idea-workflow.yaml")
    with _tmp() as d:
        rs.start_run(d, "idea-v2", [], workflow_path=workflow)
        try:
            rs.set_status(d, "idea-v2", "problem_generation", "running")
            raised = False
        except ValueError:
            raised = True
        assert raised, "a module must not run before its human and formal gates"

        rs.set_status(d, "idea-v2", "landscape", "running")
        try:
            rs.set_status(d, "idea-v2", "landscape", "done")
            raised = False
        except ValueError:
            raised = True
        assert raised, "a workflow phase must not close without declared handoff artifacts"


def test_landscape_handoff_rejects_non_lineage_content():
    repo = Path(__file__).resolve().parents[1]
    workflow = str(repo / "skills" / "shared-references" / "idea-workflow.yaml")
    with _tmp() as d:
        rs.start_run(d, "bad-landscape", [], workflow_path=workflow)
        rs.set_status(d, "bad-landscape", "landscape", "running")
        _write_landscape_artifacts(d, workflow)
        corpus = Path(d) / _workflow_artifact(workflow, "literature_corpus")
        corpus.write_text(json.dumps({
            "source_id": "ORPHAN",
            "context_decisions": [{
                "decision_id": "admission-landscape-orphan",
                "context": {
                    "paper_id": "ORPHAN",
                    "phase": "landscape",
                    "query_plan_sha256": "a" * 64,
                    "phase_binding_anchor": {"query_plan_sha256": "a" * 64},
                    "decision_targets": [],
                },
                "admission_status": "ADMIT_DECISION_GRADE",
                "screening_status": "IN_SCOPE",
                "screening_reason": "fixture orphan",
            }],
        }) + "\n", encoding="utf-8")
        with pytest.raises(ValueError, match="without an evidence card"):
            rs.set_status(d, "bad-landscape", "landscape", "done")


def test_method_design_is_hard_blocked_until_root_cause_is_accepted():
    repo = Path(__file__).resolve().parents[1]
    workflow = str(repo / "skills" / "shared-references" / "idea-workflow.yaml")

    def touch(root: str, *paths: str) -> None:
        for relative in paths:
            path = Path(root) / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("artifact", encoding="utf-8")

    with _tmp() as d:
        rs.start_run(d, "gate-order", [], workflow_path=workflow)
        rs.set_status(d, "gate-order", "landscape", "running")
        _write_landscape_artifacts(d, workflow)
        rs.set_status(d, "gate-order", "landscape", "done")
        rs.accept(d, "gate-order", "landscape", "landscape:1", "deterministic:pytest")
        rs.approve_human(d, "gate-order", "scope_human_approval", "scope accepted")

        rs.set_status(d, "gate-order", "problem_generation", "running")
        touch(d, "idea-stage/PROBLEM_CANDIDATES.md", "idea-stage/PROBLEM_CANDIDATES.jsonl")
        (Path(d) / "idea-stage" / "PROBLEM_CANDIDATES.jsonl").write_text(
            json.dumps({
                "problem_id": "P-1", "source_class": "self_discovered",
                "research_question": "Why does the capability fail?",
                "observed_phenomenon": "A scoped failure is observed.",
                "scope_and_conditions": "Declared setting.", "evidence_refs": ["P1"],
                "why_it_matters": "Decision consequence.", "value_if_yes": "Boundary learned.",
                "value_if_no": "Boundary ruled out.", "plausible_explanations": [
                    {"explanation": "A", "epistemic_status": "preliminary"},
                    {"explanation": "B", "epistemic_status": "speculative"},
                ],
                "measurement_validity": "Measure is valid.",
                "artifact_or_confound_alternatives": ["artifact"],
                "independent_support": ["replication"],
                "phenomenon_prevalence_or_effect_scale": "material",
                "decision_owner_and_threshold": "owner / threshold",
                "falsifier": "stable result", "feasible_discriminating_probe": "controlled probe",
                "closest_prior_answer": "nearest work is incomplete", "uncertainties": ["scope"],
                "dedup_key": "failure|setting", "provenance": {"lens": "test"},
            }) + "\n",
            encoding="utf-8",
        )
        rs.set_status(d, "gate-order", "problem_generation", "done")
        rs.set_status(d, "gate-order", "problem_quality_gate", "running")
        touch(d, "idea-stage/PROBLEM_QUALITY_VERDICTS.jsonl")
        rs.set_status(d, "gate-order", "problem_quality_gate", "done")
        rs.accept(d, "gate-order", "problem_quality_gate", "quality:1", "deterministic:pytest")
        rs.set_status(d, "gate-order", "problem_novelty_gate", "running")
        touch(d, "idea-stage/PROBLEM_NOVELTY_VERDICTS.jsonl")
        rs.set_status(d, "gate-order", "problem_novelty_gate", "done")
        rs.accept(d, "gate-order", "problem_novelty_gate", "novelty:1", "deterministic:pytest")

        with pytest.raises(ValueError, match="non-terminal dependencies"):
            rs.set_status(d, "gate-order", "method_design", "running")
        with pytest.raises(ValueError, match="requires selected_id"):
            rs.approve_human(d, "gate-order", "problem_human_acceptance", "accept problem")

        # Human problem acceptance is necessary but cannot bypass diagnosis.
        rs.approve_human(d, "gate-order", "problem_human_acceptance", "accept problem", selected_id="P1")
        with pytest.raises(ValueError, match="non-terminal dependencies"):
            rs.set_status(d, "gate-order", "method_design", "running")
        touch(d, "idea-stage/RESEARCH_CONTRACT.md", "idea-stage/PROBLEM_EVIDENCE_CAPSULE.md")
        _advance_through_root_cause(d, "gate-order")
        rs.set_status(d, "gate-order", "method_design", "running")


def test_root_cause_gate_rejects_non_ready_verdict_and_detects_tampering():
    repo = Path(__file__).resolve().parents[1]
    workflow = str(repo / "skills" / "shared-references" / "idea-workflow.yaml")
    with _tmp() as d:
        rs.start_run(d, "diagnosis-guard", [], workflow_path=workflow)
        state = rs._load(d, "diagnosis-guard")
        for phase in ("landscape", "scope_human_approval", "problem_generation",
                      "problem_quality_gate", "problem_novelty_gate", "problem_human_acceptance"):
            rs._find_phase(state, phase)["status"] = (
                "human_accepted" if phase in ("scope_human_approval", "problem_human_acceptance") else "accepted"
            )
        Path(d, ".aris", "runs", "diagnosis-guard.json").write_text(json.dumps(state), encoding="utf-8")
        stage = Path(d, "idea-stage")
        stage.mkdir(parents=True, exist_ok=True)
        (stage / "ACTIVE_FIELD_MAP.md").write_text("accepted field map", encoding="utf-8")
        (stage / "RESEARCH_CONTRACT.md").write_text("accepted", encoding="utf-8")
        (stage / "PROBLEM_EVIDENCE_CAPSULE.md").write_text("evidence", encoding="utf-8")

        _accept_necessity_fixture(d, "diagnosis-guard")
        rs.set_status(d, "diagnosis-guard", "root_cause_analysis", "running")
        verdict_id, reviewer = _write_root_cause_artifacts(d, "diagnosis-guard", decision="HOLD")
        rs.set_status(d, "diagnosis-guard", "root_cause_analysis", "done")
        rs.set_status(d, "diagnosis-guard", "root_cause_gate", "running")
        with pytest.raises(ValueError, match="decision is invalid"):
            rs.set_status(d, "diagnosis-guard", "root_cause_gate", "done")

        verdict_id, reviewer = _write_root_cause_artifacts(
            d, "diagnosis-guard", decision="REVISE_DIAGNOSIS"
        )
        rs.set_status(d, "diagnosis-guard", "root_cause_gate", "done")
        with pytest.raises(ValueError, match="does not authorize acceptance"):
            rs.accept(d, "diagnosis-guard", "root_cause_gate", verdict_id, reviewer)

        verdict_id, reviewer = _write_root_cause_artifacts(d, "diagnosis-guard")
        rs.set_status(d, "diagnosis-guard", "root_cause_analysis", "done")
        rs.set_status(d, "diagnosis-guard", "root_cause_gate", "done")
        rs.accept(d, "diagnosis-guard", "root_cause_gate", verdict_id, reviewer)
        (stage / "ROOT_CAUSE_ANALYSIS.json").write_text("{}", encoding="utf-8")
        with pytest.raises(ValueError, match="has changed"):
            rs.set_status(d, "diagnosis-guard", "method_design", "running")


def test_partial_landscape_can_progress_but_cannot_certify_a_problem():
    repo = Path(__file__).resolve().parents[1]
    workflow = str(repo / "skills" / "shared-references" / "idea-workflow.yaml")
    with _tmp() as d:
        rs.start_run(d, "partial", [], workflow_path=workflow)
        rs.set_status(d, "partial", "landscape", "running")
        _write_landscape_artifacts(d, workflow, status="PARTIAL")
        state = rs.set_status(d, "partial", "landscape", "done")
        assert rs._find_phase(state, "landscape")["coverage_status"] == "PARTIAL"
        rs.accept(d, "partial", "landscape", "landscape:partial", "deterministic:pytest")
        rs.approve_human(d, "partial", "scope_human_approval", "scope accepted")
        state = rs._load(d, "partial")
        for phase in ("problem_generation", "problem_quality_gate", "problem_novelty_gate"):
            current = rs._find_phase(state, phase)
            current["status"] = "accepted"
        novelty = Path(d) / "idea-stage" / "PROBLEM_NOVELTY_VERDICTS.jsonl"
        novelty.parent.mkdir(parents=True, exist_ok=True)
        novelty.write_text("verdict", encoding="utf-8")
        state_path = Path(d) / ".aris" / "runs" / "partial.json"
        state_path.write_text(json.dumps(state), encoding="utf-8")
        with pytest.raises(ValueError, match="requires coverage status"):
            rs.approve_human(d, "partial", "problem_human_acceptance", "accept", selected_id="P1")


def test_refinement_is_hard_blocked_until_principle_convergence_is_accepted_and_materialized():
    repo = Path(__file__).resolve().parents[1]
    workflow = str(repo / "skills" / "shared-references" / "idea-workflow.yaml")
    with _tmp() as d:
        rs.start_run(d, "principle-gate", [], workflow_path=workflow)
        state = rs._load(d, "principle-gate")
        # Isolate the declared convergence dependency and its Controller-owned
        # Selected Principle artifact without inventing a second lifecycle.
        for phase in ("landscape", "scope_human_approval", "problem_generation",
                      "problem_quality_gate", "problem_novelty_gate", "problem_human_acceptance",
                      "problem_necessity", "root_cause_analysis", "root_cause_gate", "method_design",
                      "principle_test_human_approval"):
            current = rs._find_phase(state, phase)
            current["status"] = (
                "human_accepted"
                if phase in ("scope_human_approval", "problem_human_acceptance", "principle_test_human_approval")
                else "done" if phase in ("root_cause_analysis",) else "accepted"
            )
        Path(d, ".aris", "runs", "principle-gate.json").write_text(
            json.dumps(state), encoding="utf-8"
        )
        contract = Path(d, "idea-stage", "RESEARCH_CONTRACT.md")
        contract.parent.mkdir(parents=True, exist_ok=True)
        contract.write_text("acceptance_status: human_accepted", encoding="utf-8")
        Path(d, "idea-stage", "ACTIVE_FIELD_MAP.md").write_text(
            "accepted field map", encoding="utf-8"
        )
        Path(d, "idea-stage", "PROBLEM_EVIDENCE_CAPSULE.md").write_text("evidence", encoding="utf-8")
        Path(d, "idea-stage", "NECESSITY_CLOSURE.json").write_text("{}", encoding="utf-8")
        Path(d, "idea-stage", "NECESSITY_VERDICT.json").write_text("{}", encoding="utf-8")
        Path(d, "idea-stage", "ROOT_CAUSE_ANALYSIS.json").write_text("{}", encoding="utf-8")
        Path(d, "idea-stage", "ROOT_CAUSE_VERDICT.json").write_text("{}", encoding="utf-8")
        Path(d, "idea-stage", "PRINCIPLE_EVALUATION.json").write_text("{}", encoding="utf-8")
        Path(d, "idea-stage", "PRINCIPLE_EVALUATION_VERDICT.json").write_text("{}", encoding="utf-8")
        state = rs._load(d, "principle-gate")
        rs._find_phase(state, "problem_necessity")["validated_artifacts"] = {
            "idea-stage/NECESSITY_CLOSURE.json": _file_sha256(
                Path(d, "idea-stage", "NECESSITY_CLOSURE.json")
            ),
            "idea-stage/NECESSITY_VERDICT.json": _file_sha256(
                Path(d, "idea-stage", "NECESSITY_VERDICT.json")
            ),
        }
        rs._find_phase(state, "root_cause_analysis")["validated_artifacts"] = {
            "idea-stage/RESEARCH_CONTRACT.md": _file_sha256(contract),
            "idea-stage/NECESSITY_CLOSURE.json": _file_sha256(
                Path(d, "idea-stage", "NECESSITY_CLOSURE.json")
            ),
            "idea-stage/NECESSITY_VERDICT.json": _file_sha256(
                Path(d, "idea-stage", "NECESSITY_VERDICT.json")
            ),
            "idea-stage/ROOT_CAUSE_ANALYSIS.json": _file_sha256(
                Path(d, "idea-stage", "ROOT_CAUSE_ANALYSIS.json")
            ),
        }
        rs._find_phase(state, "root_cause_gate")["validated_artifacts"] = {
            "idea-stage/ROOT_CAUSE_VERDICT.json": _file_sha256(
                Path(d, "idea-stage", "ROOT_CAUSE_VERDICT.json")
            )
        }
        rs._find_phase(state, "principle_evaluation")["validated_artifacts"] = {
            "idea-stage/PRINCIPLE_EVALUATION.json": _file_sha256(
                Path(d, "idea-stage", "PRINCIPLE_EVALUATION.json")
            ),
            "idea-stage/PRINCIPLE_EVALUATION_VERDICT.json": _file_sha256(
                Path(d, "idea-stage", "PRINCIPLE_EVALUATION_VERDICT.json")
            ),
        }
        Path(d, ".aris", "runs", "principle-gate.json").write_text(
            json.dumps(state), encoding="utf-8"
        )
        with pytest.raises(ValueError, match="non-terminal dependencies"):
            rs.set_status(d, "principle-gate", "method_refinement", "running")
        state = rs._load(d, "principle-gate")
        rs._find_phase(state, "principle_evaluation")["status"] = "accepted"
        Path(d, ".aris", "runs", "principle-gate.json").write_text(
            json.dumps(state), encoding="utf-8"
        )
        with pytest.raises(ValueError, match="missing required input"):
            rs.set_status(d, "principle-gate", "method_refinement", "running")
        Path(d, "idea-stage", "SELECTED_PRINCIPLE.yaml").write_text(
            "principle_id: PR-A\nprinciple_version: '1'\n", encoding="utf-8"
        )
        rs.set_status(d, "principle-gate", "method_refinement", "running")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = failed = 0
    for t in tests:
        try:
            t(); print(f"  PASS {t.__name__}"); passed += 1
        except Exception as e:  # noqa: BLE001
            print(f"  FAIL {t.__name__}: {e}"); failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
