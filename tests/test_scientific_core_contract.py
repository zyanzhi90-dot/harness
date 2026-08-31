from __future__ import annotations

import json
from pathlib import Path
import re


REPO_ROOT = Path(__file__).resolve().parents[1]
MAIN = REPO_ROOT / "skills"
CODEX = MAIN / "skills-codex"
CLAUDE_OVERLAY = MAIN / "skills-codex-claude-review"
GEMINI_OVERLAY = MAIN / "skills-codex-gemini-review"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def skill(root: Path, name: str) -> str:
    return read(root / name / "SKILL.md")


def test_problem_discovery_contract_is_mirrored_and_hands_off_method_design() -> None:
    for root in (MAIN, CODEX):
        text = read(root / "shared-references" / "problem-discovery-contract.md")
        assert "P1 — Evidence Map" in text
        assert "P3 — Problem Quality Gate" in text
        assert "Reality" in text and "Answerability" in text
        assert "community_open_problem" in text
        assert "self_discovered" in text
        assert "problem_migration" in text
        assert "method-design-contract.md" in text
        assert "P4" not in text
        assert "problem novelty" in text.lower()
        assert "Active Field Map" in text
        assert "Evidence Registry" in text
        assert "claim_locator" in text
        assert "access_level" in text
        assert "decision_grade" in text
        assert "discovery_only" in text
        assert "INSUFFICIENT_EVIDENCE" in text
        assert "do not add irrelevant literature anchors" in text
        assert "formal Evidence Card `source_id` equals" in text
        assert "epistemic_status" in text
        assert "disanalogy_and_transfer_limit" in text
        assert "`request_revision` and `reject`" in text
        assert "human feedback" in text
        assert "Candidate registry baseline" in text
        assert "fresh review context" in text
        assert "field_core_purposes" in text
        assert "typical_tasks_and_scenarios" in text
        assert "core_bottlenecks" in text
        assert "assumption_effectiveness_failure_matrix" in text
        assert "family_development_traces" in text
        assert "triangulating high-quality reviews" in text
        assert "perspective rather than authority" in text
        assert "evidence-conditioned working model" in text
        assert "consensus is useful but neither mandatory nor permanent" in " ".join(text.split()).lower()
        assert "weighted reading depth" in text
        assert "do not load the whole corpus into active context" in text.lower()
        assert "development_link" in text
        assert "source_problem_formation_mechanism" in text
        assert "target_structural_isomorphism" in text
        assert "target_problem_evidence" in text
        assert "solution_transfer_status" in text
        assert "horizontally across papers and families" in text
        assert "paper limitation or future-work sentence" in text
        assert "attempted disconfirmation" in text
        assert "P2: discover and mature Leads" in text
        lead_chain = (
            "unresolved contradictions",
            "Lead discovery and triage",
            "targeted deep dive, evidence, and reframing",
            "mature problem candidates",
        )
        positions = [text.index(item) for item in lead_chain]
        assert positions == sorted(positions)


def test_problem_agent_path_matures_leads_before_candidates() -> None:
    for root in (MAIN, CODEX):
        creator = skill(root, "idea-creator")
        discovery = skill(root, "idea-discovery")
        compact_creator = " ".join(creator.split()).lower()
        compact_discovery = " ".join(discovery.split()).lower()
        assert "horizontal" in compact_creator
        assert "targeted deep dive" in compact_creator
        assert "only a lead" in compact_creator or "formal candidate" in compact_creator
        assert "targeted deep dive" in compact_discovery
        assert "only a lead" in compact_discovery
        assert "only mature" in compact_discovery


def test_method_design_contract_is_mirrored_and_declares_principle_first_lifecycle() -> None:
    main = read(MAIN / "shared-references" / "method-design-contract.md")
    assert main == read(CODEX / "shared-references" / "method-design-contract.md")
    for marker in (
        "Required Mechanism Changes",
        "Capability/Obligation",
        "search_mode: PRINCIPLE_SEARCH",
        "Candidate Principles",
        "test-only operationalization",
        "method-test-handoff",
        "PRINCIPLE_EVIDENCE_CONTEXT.json",
        "PRINCIPLE_CONVERGED",
        "MORE_EVIDENCE",
        "RCA_CONFLICT",
        "SELECTED_PRINCIPLE.yaml",
    ):
        assert marker in main
    reviewer = read(REPO_ROOT / ".codex" / "agents" / "independent_method_reviewer.toml")
    for marker in (
        "NO_ADDITIONAL_DOMAIN_HYPOTHESIS",
        "task, algorithm, architecture, venue, popularity, or buzzword similarity is insufficient",
        "Source Intervention -> Mechanism Change -> Outcome",
        "FAIL forbids an active Candidate",
        "A Target causal-equivalent intervention rejects or restructures the Candidate",
        "an old Source primitive, or small Target adaptation cannot by itself weaken a Candidate",
        "structurally valid but scientifically empty derivation",
        "post-hoc discovery story",
    ):
        assert marker in reviewer

def test_literature_stage_builds_an_evidence_map_before_methods() -> None:
    for root in (MAIN, CODEX):
        text = skill(root, "research-lit")
        assert "Active Field Map" in text
        assert "Problem × method relation" in text
        assert "coverage record" in text.lower()
        assert "not found" in text.lower()
        assert "Metadata, snippets, abstracts" in text
        assert "field core purposes -> typical tasks and scenarios" in text
        assert "Assumption × effective-condition × failure-condition relation" in text
        compact = " ".join(text.split()).lower()
        assert "read only the admitted paper content" in compact
        assert "small number of field-recognized broad families" in compact
        assert "problem-discovery-contract.md" in compact
        assert "update one working active field map" in compact
        assert "causal development trace" in compact
        assert "research problem -> method -> evidence -> bottleneck -> transition -> subsequent evolution" in compact
        assert "never create a stage from year boundaries alone" in compact
        assert "parallel branches, forks, merges" in compact
        assert "progress_and_conditions" in compact and "method or mechanism" in compact
        assert "explanatory_coherence" in text
        assert "NO_MATERIAL_TRANSITION_SUPPORTED" in text
        assert "MATERIAL_TRANSITION_MISSING" in text
        assert "development_trace_count" in text
        assert "backward/forward citation expansion" in compact
        assert "paper-level links only for foundational" in compact
        assert "development link" in compact
        assert "controller/gateway concern" in compact
        assert "never search, fetch full text" in compact
        assert "stage order" in compact and "schema validation" in compact
        assert "max_queries" not in text
        assert "MAX_FULLTEXT_BATCH" not in text
        discovery = skill(root, "idea-discovery")
        assert "compact causal development traces" in discovery

        contract = read(root / "shared-references" / "problem-discovery-contract.md")
        assert "previous_problem_or_bottleneck" in contract
        assert "progress_and_conditions" in contract
        assert "residual_or_new_bottleneck" in contract
        assert "research_question_shift" in contract
        assert "subsequent_direction" in contract
        assert "transition_problem_status: still_open | partially_addressed | mature_under_specific_conditions | reframed" in contract
        assert "still open" in contract and "mature under specific conditions" in contract
        assert "evidence_ids" in contract
        assert "stage counts, time spans, branch" in contract
        assert "need not have one landmark paper" in contract
        assert "an empty trace is\nvalid when the literature supports no material transition" in contract

    reviewer = read(REPO_ROOT / ".codex" / "agents" / "coverage_reviewer.toml")
    for marker in (
        "foundation_to_frontier",
        "key_nodes_and_branches",
        "transition_causality",
        "explanatory_coherence",
        "material_evolution_gaps",
        "development_trace_count",
    ):
        assert marker in reviewer


def test_landscape_search_log_uses_the_workflow_artifact_manifest() -> None:
    expected_landscape = {
        "active_field_map": "idea-stage/ACTIVE_FIELD_MAP.md",
        "evidence_registry": "idea-stage/EVIDENCE_REGISTRY.jsonl",
        "literature_corpus": "idea-stage/LITERATURE_CORPUS.jsonl",
        "source_admission_policy": "idea-stage/SOURCE_ADMISSION_POLICY.yaml",
        "search_log": "idea-stage/SEARCH_LEDGER.jsonl",
    }
    for root in (MAIN, CODEX):
        workflow = json.loads(read(root / "shared-references" / "idea-workflow.yaml"))
        assert {key: workflow["artifact_manifest"][key] for key in expected_landscape} == expected_landscape
        assert workflow["artifact_manifest"]["method_design_packet"] == "idea-stage/METHOD_DESIGN_PACKET.json"
        assert workflow["artifact_manifest"]["selected_principle"] == "idea-stage/SELECTED_PRINCIPLE.yaml"

def test_problem_human_return_guidance_is_synced_to_the_codex_adapter() -> None:
    for root in (MAIN, CODEX):
        text = skill(root, "idea-creator")
        assert "request_revision" in text
        assert "reject" in text
        assert "human feedback" in text
        assert "incremental-literature" in text or "incremental literature" in text


def test_source_admission_policy_is_strict_for_search_and_reads_user_materials() -> None:
    main_policy = read(MAIN / "shared-references" / "source-admission-policy.md")
    codex_policy = read(CODEX / "shared-references" / "source-admission-policy.md")
    assert main_policy == codex_policy

    compact = " ".join(main_policy.split()).lower()
    assert "screen every candidate from title and actual abstract" in compact
    assert "admission eligibility and reading priority are separate decisions" in compact
    assert "hard active-reading gate" in compact
    assert "high citation impact or approved elite-venue" in compact
    assert "`discovery_metadata_only`" in compact
    assert "admit_decision_grade" in compact
    assert "admit_discovery_only" in compact
    assert "negative/null results" in compact
    assert "replications" in compact
    assert "user-supplied papers and notes" in compact
    assert "`user_supplied_read`" in compact
    assert "never discard user-supplied material before content inspection" in compact
    assert "`rmc_bound_source_mechanism_or_genealogy`" in compact
    assert "it only permits the full-text read needed to judge" in compact
    assert "nor an exception establishes relevance, source causal efficacy" in compact
    assert "keep paper identity, metadata, full text, and canonical evidence globally unique" in compact
    assert "query_plan_sha256" in compact and "phase_binding_anchor" in compact


def test_source_admission_gate_precedes_all_scientific_reading_paths() -> None:
    for root in (MAIN, CODEX):
        literature = skill(root, "research-lit")
        assert "source-admission-policy.md" in literature
        compact_lit = " ".join(literature.split())
        assert "Read only the admitted paper content supplied by the Controller" in compact_lit
        assert "never search, fetch full text, admit a paper" in compact_lit
        assert "do not silently downgrade" in compact_lit

        problem = read(root / "shared-references" / "problem-discovery-contract.md")
        method = read(root / "shared-references" / "method-design-contract.md")
        discovery = skill(root, "idea-discovery")
        assert "source-admission-policy.md" in problem
        assert "source-admission-policy.md" in method
        assert "For a proactively retrieved reference" in discovery
        assert "`USER_SUPPLIED_READ`" in discovery

    for root in (MAIN, CODEX, CLAUDE_OVERLAY, GEMINI_OVERLAY):
        novelty = skill(root, "novelty-check")
        assert "source-admission-policy.md" in novelty
        assert (
            "ADMIT_DECISION_GRADE" in novelty
            or "Immediately remove every `DISCARD` result" in novelty
        )
        assert "without a recency exception" not in novelty
        assert "most recent 6 months of arXiv" not in novelty


def test_landscape_completion_requires_auditable_branch_and_lineage_saturation() -> None:
    for root in (MAIN, CODEX):
        problem = read(root / "shared-references" / "problem-discovery-contract.md")
        compact = " ".join(problem.split()).lower()
        assert "search log and complete candidate corpus" in compact
        assert "failed or low-precision routes" in compact
        assert "foundational, influential or turning-point" in compact
        assert "targeted query refinement and backward/forward citation expansion" in compact
        assert "further reading reveals no uncovered important branch" in compact
        assert "every cited paper identity is verified" in compact
        assert "must not be presented as a complete research-state survey" in compact

        fanout = read(root / "shared-references" / "fan-out-pattern.md")
        fanout_compact = " ".join(fanout.split()).lower()
        assert "serpapi google scholar as its default discovery backbone" in fanout_compact
        assert "do not fan out overlapping providers" in fanout_compact
        assert "arxiv + ieee xplore" in fanout_compact
        assert "human_search_required" in fanout_compact
        assert "does not verify full bibliographic identity" in fanout_compact


def test_field_mapping_and_principle_search_orders_are_enforced() -> None:
    for root in (MAIN, CODEX):
        problem = read(root / "shared-references" / "problem-discovery-contract.md")
        field_block = problem[problem.index("Build the landscape in this order") :]
        field_chain = (
            "field core purposes", "typical tasks and scenarios", "core bottlenecks",
            "method families", "which bottleneck each family addresses and by what mechanism",
            "assumptions each family requires", "conditions where each family is effective",
            "conditions where each family fails", "unresolved contradictions",
        )
        positions = [field_block.index(item) for item in field_chain]
        assert positions == sorted(positions)
        method = read(root / "shared-references" / "method-design-contract.md")
        search = method[method.index("## D1") :]
        assert all(item in search for item in (
            "FIRST_PRINCIPLES", "REPRESENTATION_TRANSFORMATION",
            "SAME_FIELD_MECHANISM", "CROSS_DOMAIN_STRUCTURAL_ISOMORPHISM",
        ))

def test_idea_creator_declares_problem_diagnosis_and_principle_modes() -> None:
    for root in (MAIN, CODEX):
        text = skill(root, "idea-creator")
        assert all(marker in text for marker in (
            "mode: problem", "mode: diagnosis", "mode: method",
            "METHOD_DESIGN_PACKET.json", "PRINCIPLE_EVALUATION.json",
            "/method-test", "PRINCIPLE_PACKET_READY",
        ))

def test_novelty_and_review_keep_problem_principle_and_method_verdicts_separate() -> None:
    for root in (MAIN, CODEX):
        novelty = skill(root, "novelty-check")
        review = skill(root, "research-review")
        assert "mode: problem" in novelty and "mode: method" in novelty
        assert "REVISE_METHOD_DELTA" in novelty
        assert "RETHINK_PRINCIPLE_DELTA" in novelty
        assert "RMC/Capability/Obligation" in review
        assert "stage: method" in review
        assert "Capability/Obligation" in review

def test_refine_consumes_one_controller_selected_principle() -> None:
    for root in (MAIN, CODEX):
        text = skill(root, "research-refine")
        assert all(marker in text for marker in (
            "Controller-materialized Selected Principle",
            "accepted Principle convergence",
            "minimal faithful realization",
            "Principle-only closure",
            "ADAPTATION_GAP_SEARCH",
            "METHOD_READY",
        ))

def test_problem_contract_and_method_proposal_are_separate() -> None:
    contract = read(REPO_ROOT / "templates" / "RESEARCH_CONTRACT_TEMPLATE.md")
    capsule = read(REPO_ROOT / "templates" / "PROBLEM_EVIDENCE_CAPSULE_TEMPLATE.md")
    proposal = read(REPO_ROOT / "templates" / "METHOD_PROPOSAL_TEMPLATE.md")
    assert "## Certified Problem Contract" in contract
    assert "## Problem Evidence Capsule" not in contract
    assert "# Problem Evidence Capsule" in capsule
    assert "FINAL_METHOD_PACKET.json" in proposal
    assert "Packet is the only" in proposal
    assert "Controller deterministically renders" in proposal
    assert "Target RMC" in proposal
    assert "principle_only_closure" in proposal
    assert "claim-validation obligations" in proposal
    assert "Established Scientific Delta" in proposal

def test_problem_evidence_capsule_has_one_documented_form_across_active_skills() -> None:
    skill_paths = (
        REPO_ROOT / "skills" / "idea-creator" / "SKILL.md",
        REPO_ROOT / "skills" / "idea-discovery" / "SKILL.md",
        REPO_ROOT / "skills" / "skills-codex" / "idea-creator" / "SKILL.md",
        REPO_ROOT / "skills" / "skills-codex" / "idea-discovery" / "SKILL.md",
        REPO_ROOT / "skills" / "skills-codex-gemini-review" / "idea-creator" / "SKILL.md",
        REPO_ROOT / "skills" / "skills-codex-gemini-review" / "idea-discovery" / "SKILL.md",
    )
    for path in skill_paths:
        text = read(path)
        assert "PROBLEM_EVIDENCE_CAPSULE.md" in text
        assert "must not embed" in text.lower()
        assert "before the controller records human acceptance" in " ".join(text.lower().split())


def test_cross_family_overlays_preserve_scientific_semantics_and_backend_adaptation() -> None:
    for root in (CLAUDE_OVERLAY, GEMINI_OVERLAY):
        novelty = skill(root, "novelty-check")
        review = skill(root, "research-review")
        refine = skill(root, "research-refine")
        assert "RETHINK_PRINCIPLE_DELTA" in novelty
        assert "RMC/Capability/Obligation" in review
        assert "Selected Principle" in refine

def test_source_admission_exception_is_narrow_and_consistent_across_codex_paths() -> None:
    shared = read(REPO_ROOT / "skills" / "shared-references" / "source-admission-policy.md")
    mirror = read(
        REPO_ROOT
        / "skills"
        / "skills-codex"
        / "shared-references"
        / "source-admission-policy.md"
    )
    assert shared == mirror
    for token in (
        "decisive_closest_prior_or_concurrent",
        "negative_or_contradictory_result",
        "diagnostic_or_replication_evidence",
        "Recency or relevance alone is not an exception",
    ):
        assert token in shared
    gemini = skill(GEMINI_OVERLAY, "idea-discovery")
    assert "default hard" in gemini
    assert "recency or relevance alone is insufficient" in " ".join(
        gemini.lower().split()
    )


def test_refinement_protocol_is_mirrored_and_preserves_selected_principle_semantics() -> None:
    main = read(MAIN / "shared-references" / "method-refinement-protocol.md")
    assert main == read(CODEX / "shared-references" / "method-refinement-protocol.md")
    assert all(marker in main for marker in (
        "SELECTED_PRINCIPLE.yaml", "minimal faithful realization",
        "Principle-only closure", "ADAPTATION_GAP_SEARCH",
        "REVISE_METHOD_DELTA", "RETHINK_PRINCIPLE_DELTA",
        "METHOD_REFINEMENT_REQUIRED",
    ))

def test_runtime_method_skills_declare_their_principle_first_roles() -> None:
    required = {
        "idea-creator": ("Required Mechanism Changes", "PRINCIPLE_SEARCH", "Candidate Principles"),
        "research-refine": ("Selected Principle", "ADAPTATION_GAP_SEARCH", "minimal faithful realization"),
        "research-refine-pipeline": ("Selected Principle", "METHOD_READY", "validation-handoff"),
        "novelty-check": ("REVISE_METHOD_DELTA", "RETHINK_PRINCIPLE_DELTA"),
        "research-review": ("stage: principle", "stage: method"),
        "method-test": ("method-test-handoff", "submit-method-test-result", "NO_RESULT"),
    }
    for root in (MAIN, CODEX):
        for name, markers in required.items():
            text = skill(root, name)
            assert all(marker in text for marker in markers), name

def test_generator_and_problem_jury_are_independent() -> None:
    for root in (MAIN, CODEX):
        workflow = json.loads(read(root / "shared-references" / "idea-workflow.yaml"))
        assert workflow["scientific_core"]["allowed_agents"]["problem_generation"] == ["main_research_agent"]
        assert workflow["scientific_core"]["allowed_agents"]["problem_quality_gate"] == ["independent_problem_reviewer"]
        assert workflow["scientific_core"]["allowed_agents"]["method_design"] == [
            "main_research_agent", "independent_method_reviewer"
        ]

def test_refine_routing_requires_an_accepted_selected_principle() -> None:
    for root in (MAIN, CODEX):
        refine = skill(root, "research-refine")
        pipeline = skill(root, "research-refine-pipeline")
        assert "accepted Principle convergence" in refine
        assert "SELECTED_PRINCIPLE.yaml" in refine
        assert "Candidate Principle" in pipeline
        assert "pre-convergence" in pipeline

def test_default_discovery_cannot_cross_human_or_test_gates() -> None:
    for root in (MAIN, CODEX):
        workflow = json.loads(read(root / "shared-references" / "idea-workflow.yaml"))
        approval = next(item for item in workflow["phases"] if item["phase"] == "principle_test_human_approval")
        selection = next(item for item in workflow["phases"] if item["phase"] == "principle_human_selection")
        test_design = next(item for item in workflow["phases"] if item["phase"] == "principle_test_design")
        evaluation = next(item for item in workflow["phases"] if item["phase"] == "principle_evaluation")
        assert selection["human_checkpoint"] is True
        assert selection["accepted_decisions"] == ["select"]
        assert test_design["reviewer_role"] == "independent_method_reviewer"
        assert approval["human_checkpoint"] is True
        assert approval["approval_subject"] == "principle_test_plan.recommended_execution_set_and_estimated_total_cost"
        assert evaluation["pre_start_conditions"] == [
            "approved_execution_set_all_tests_terminal",
            "active_principle_evidence_context_matches_approved_cycle",
        ]

def test_refine_phase_mapping_matches_shared_protocol() -> None:
    assert read(MAIN / "shared-references" / "idea-workflow.yaml") == read(
        CODEX / "shared-references" / "idea-workflow.yaml"
    )
    for root in (MAIN, CODEX):
        workflow = json.loads(read(root / "shared-references" / "idea-workflow.yaml"))
        selected_principle = workflow["artifact_contracts"]["selected_principle"]
        assert selected_principle["invalidate_on"] == [
            "RETHINK",
            "RETHINK_PRINCIPLE_DELTA",
            "SELECTED_PRINCIPLE_REJECTED",
            "RCA_CONFLICT",
            "NECESSITY_CONFLICT",
            "PROBLEM_CONFLICT",
            "ROOT_CAUSE_REJECTED",
            "PROBLEM_PREMISE_REJECTED",
        ]
        refinement = next(item for item in workflow["phases"] if item["phase"] == "method_refinement")
        assert refinement["required_inputs"][-1] == "@artifact:selected_principle"
        assert refinement["produced_artifacts"] == [
            "@artifact:final_method_packet", "@artifact:final_proposal",
            "@artifact:final_method_review", "@artifact:refine_state",
        ]
        assert refinement["reviewed_artifacts"] == ["@artifact:final_method_packet"]
        assert refinement["accepted_verdicts"] == ["METHOD_READY"]
        assert refinement["return_targets"] == {
            "REVISE": "method_refinement",
            "RETHINK": "method_design",
            "HOLD": "method_refinement",
            "RCA_CONFLICT": "root_cause_analysis",
            "NECESSITY_CONFLICT": "problem_necessity",
            "PROBLEM_CONFLICT": "problem_generation",
        }
        assert refinement["terminal_verdicts"] == {
            "NO_GO": {
                "action": "terminate_scientific_core",
                "status": "SCIENTIFIC_NO_GO",
            }
        }
        assert "top_venue_method_strength_gate" not in workflow["scientific_core"]["phases"]
        assert all(
            item["phase"] != "top_venue_method_strength_gate"
            for item in workflow["phases"]
        )
        final_human = next(
            item for item in workflow["phases"]
            if item["phase"] == "final_method_human_acceptance"
        )
        assert final_human["depends_on"] == ["final_method_novelty_gate"]
        assert "@artifact:final_method_packet" in json.dumps(
            {
                "scientific_core": workflow["scientific_core"],
                "phases": workflow["phases"],
            }
        )
        assert "final_method_packet" in workflow["artifact_manifest"]
        assert "final_method_packet" in workflow["artifact_contracts"]
        assert "top_venue_method_strength_verdict" in workflow["artifact_manifest"]
        assert "top_venue_method_strength_verdict" in workflow["artifact_contracts"]

def test_core_codex_adapters_reference_canonical_shared_contracts_and_templates() -> None:
    expected = {
        "idea-creator": ("../shared-references/method-design-contract.md",),
        "research-refine": (
            "../shared-references/method-refinement-protocol.md",
            "../../templates/METHOD_PROPOSAL_TEMPLATE.md",
        ),
    }
    for name, references in expected.items():
        text = skill(CODEX, name)
        assert all(reference in text for reference in references), name

def test_restored_idea_modules_are_mirrored_and_keep_stage_boundaries() -> None:
    module_names = (
        "idea-fanout-module.md", "idea-wiki-integration.md",
        "reference-paper-intake.md", "idea-output-composition.md",
    )
    for name in module_names:
        assert read(MAIN / "shared-references" / name) == read(
            CODEX / "shared-references" / name
        )
    composition = read(MAIN / "shared-references" / "idea-output-composition.md")
    assert "PRINCIPLE_EVALUATION.json" in composition
    assert "SELECTED_PRINCIPLE.yaml" in composition
    assert "final proposal" in composition.lower()
    assert "convergence has been" in composition

def test_root_cause_contract_is_mirrored_and_precedes_principle_design() -> None:
    main = read(MAIN / "shared-references" / "root-cause-analysis-contract.md")
    assert main == read(CODEX / "shared-references" / "root-cause-analysis-contract.md")
    assert "DIAGNOSIS_READY | REVISE_DIAGNOSIS | REOPEN_PROBLEM" in main
    assert "primary_causal_chain_ids" in main
    method = read(MAIN / "shared-references" / "method-design-contract.md")
    assert "only after the independent Root-Cause Gate" in method
    assert "Required Mechanism Changes" in method
    assert "causal_chain_ids" in method


def test_problem_necessity_contract_is_mirrored_and_precedes_rca() -> None:
    main = read(MAIN / "shared-references" / "problem-necessity-contract.md")
    assert main == read(CODEX / "shared-references" / "problem-necessity-contract.md")
    assert "There is no necessity-specific test" in main
    workflow = json.loads(read(MAIN / "shared-references" / "idea-workflow.yaml"))
    phases = workflow["scientific_core"]["phases"]
    assert phases.index("problem_human_acceptance") < phases.index("problem_necessity")
    assert phases.index("problem_necessity") < phases.index("root_cause_analysis")
    necessity = next(item for item in workflow["phases"] if item["phase"] == "problem_necessity")
    assert necessity["accepted_verdicts"] == ["RESIDUAL_SAME_PROBLEM"]
    assert necessity["return_targets"] == {
        "FULLY_COVERED": "problem_generation",
        "RESIDUAL_REDEFINES_PROBLEM": "problem_generation",
        "UNRESOLVED": "problem_necessity",
    }

def test_formal_reviewer_gates_declare_roles_and_fixed_verdict_enums() -> None:
    for root in (MAIN, CODEX):
        workflow = json.loads(read(root / "shared-references" / "idea-workflow.yaml"))
        core_agents = workflow["scientific_core"]["allowed_agents"]
        for phase in workflow["phases"]:
            if not phase.get("formal_gate") or phase.get("human_checkpoint"):
                continue
            if phase["phase"] == "landscape":
                continue  # coverage review is owned by research_lit, not scientific_core.
            assert phase["reviewer_role"] in core_agents[phase["phase"]]
            assert phase["accepted_verdicts"]


def test_formal_negative_verdicts_have_fixed_earlier_return_targets() -> None:
    workflow = json.loads(read(MAIN / "shared-references" / "idea-workflow.yaml"))
    by_phase = {item["phase"]: item for item in workflow["phases"]}
    assert by_phase["method_design"]["return_targets"] == {
        "REVISE_PRINCIPLES": "method_design",
        "RCA_CONFLICT": "root_cause_analysis",
    }
    assert by_phase["principle_evaluation"]["return_targets"] == {
        "REVISE_EVALUATION": "principle_evaluation",
        "MORE_EVIDENCE": "principle_test_design",
        "CANDIDATE_REJECTED": "method_design",
        "RCA_CONFLICT": "root_cause_analysis",
        "NECESSITY_CONFLICT": "problem_necessity",
        "PROBLEM_CONFLICT": "problem_generation",
    }
    assert by_phase["method_refinement"]["return_targets"] == {
        "REVISE": "method_refinement",
        "RETHINK": "method_design",
        "HOLD": "method_refinement",
        "RCA_CONFLICT": "root_cause_analysis",
        "NECESSITY_CONFLICT": "problem_necessity",
        "PROBLEM_CONFLICT": "problem_generation",
    }
    assert by_phase["final_method_novelty_gate"]["return_targets"] == {
        "REVISE_METHOD_DELTA": "method_refinement",
        "RETHINK_PRINCIPLE_DELTA": "method_design",
        "HOLD": "final_method_novelty_gate",
    }

def test_formal_test_and_validation_contracts_separate_execution_from_interpretation() -> None:
    workflow = json.loads(read(MAIN / "shared-references" / "idea-workflow.yaml"))
    test_contract = workflow["artifact_contracts"]["method_test_evidence"]
    evaluation = workflow["artifact_contracts"]["principle_evaluation"]
    validation = workflow["artifact_contracts"]["validation_result"]
    assert test_contract["terminal_outcomes"] == ["RESULT_AVAILABLE", "NO_RESULT"]
    assert "PRINCIPLE_DECISION_RECORDED" in test_contract["event_types"]
    assert "scientific_updates" in evaluation["required_fields"]
    assert evaluation["scientific_update_consequence_enum"] == [
        "REVISE_EVALUATION", "MORE_EVIDENCE", "UPDATE_BOUNDARY",
        "RETURN_METHOD_DESIGN", "REOPEN_RCA", "REOPEN_NECESSITY",
        "REDEFINE_PROBLEM",
    ]
    assert validation["decision_enum"] == [
        "VALIDATED", "METHOD_REFINEMENT_REQUIRED",
        "SELECTED_PRINCIPLE_REJECTED", "ROOT_CAUSE_REJECTED",
        "PROBLEM_PREMISE_REJECTED",
    ]

def test_method_test_and_validation_skills_fail_closed_for_formal_inputs() -> None:
    for root in (MAIN, CODEX):
        method_test = skill(root, "method-test")
        result_to_claim = skill(root, "result-to-claim")
        experiment = skill(root, "experiment-plan")
        assert "method-test-handoff" in method_test
        assert "approved_test_ids" in method_test
        assert "Do not turn `NO_RESULT`" in method_test
        assert "validation-handoff" in result_to_claim
        assert "NON_CANONICAL_AD_HOC" in experiment

def test_research_pipeline_cannot_bypass_the_canonical_scientific_lifecycle() -> None:
    for root in (MAIN, CODEX):
        workflow = json.loads(read(root / "shared-references" / "idea-workflow.yaml"))
        phases = workflow["scientific_core"]["phases"]
        start = phases.index("method_design")
        assert phases[start:start + 6] == [
            "method_design", "principle_human_selection", "principle_test_design",
            "principle_test_human_approval", "principle_evaluation", "method_refinement",
        ]
        pipeline = skill(root, "research-refine-pipeline")
        assert "accepted Selected Principle" in pipeline
        assert "explicitly initiates" in pipeline

def test_public_routing_and_iteration_log_are_consistent_with_principle_first_workflow() -> None:
    for root in (MAIN, CODEX):
        workflow = json.loads(read(root / "shared-references" / "idea-workflow.yaml"))
        assert workflow["workflow_id"] == "idea-discovery-v4"
        discovery = skill(root, "idea-discovery")
        assert "human Candidate selection" in discovery
        assert "independent Principle test-plan review" in discovery
        assert "/method-test" in discovery
        assert "Principle convergence" in discovery
        assert "Selected Principle" in skill(root, "research-refine-pipeline")

def test_idea_workflow_references_canonical_principle_first_modules() -> None:
    for root in (MAIN, CODEX):
        creator = skill(root, "idea-creator")
        workflow = json.loads(read(root / "shared-references" / "idea-workflow.yaml"))
        assert "problem-discovery-contract.md" in creator
        assert "root-cause-analysis-contract.md" in creator
        assert "method-design-contract.md" in creator
        assert workflow["artifact_manifest"]["method_design_packet"].endswith("METHOD_DESIGN_PACKET.json")
        assert workflow["artifact_manifest"]["principle_evaluation"].endswith("PRINCIPLE_EVALUATION.json")
