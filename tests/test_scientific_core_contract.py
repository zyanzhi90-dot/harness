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


def test_method_design_contract_is_mirrored_and_preserves_core_doctrine() -> None:
    for root in (MAIN, CODEX):
        text = read(root / "shared-references" / "method-design-contract.md")
        compact = " ".join(text.split()).lower()
        assert "falsifiable scientific hypothesis" in compact
        assert "dominant method" in compact
        assert "implementation_backbone" in text
        assert "innovation_carrier" in text
        assert "integration_interface" in text
        assert "removal_failure_prediction" in text
        assert "targeted_validation" in text
        assert "same-field" in compact and "cross-field" in compact
        assert "high-efficiency decision order" in compact
        assert "not a default design goal or innovation target" in compact
        assert "scientific_delta_novelty" in text
        assert "technical_route_novelty" in text
        assert "average performance" in compact
        assert "candidate_explanations" in text
        assert "claim_type: causal | mechanistic | functional | descriptive" in text
        assert "contribution_type:" in text
        assert "disanalogy_and_transfer_limit" in text
        assert "counterfactual intervention" in compact
        assert "dominant-only closure attempt" in compact
        assert "causal_identification" in text
        assert "claim_validation_obligation" in text
        assert "route_comparison" in text
        assert "target-problem confirmation must precede solution borrowing" in compact
        assert "problem-method fit" in compact
        assert "minimum-sufficient-method audit" in compact
        assert "active_field_map.md" in compact
        assert "targeted decision action" in compact
        assert "no residual `must` id has no" in compact
        assert "record_type: design_obligation_set" in text
        assert "candidate routes must not restate or edit it" in compact
        assert "upstream method-design derivation, not a route-local edit" in compact
        assert "novelty pressure must never reverse this order" in compact
        causal_order = (
            "minimal sufficient dominant solution",
            "dominant-only closure and residual must gaps",
            "accepted field map and same-field completion search",
            "only if same-field options cannot reasonably close that gap: cross-field structural search",
        )
        positions = [compact.index(item) for item in causal_order]
        assert positions == sorted(positions)
        assert "combination is the default preferred" not in compact
        assert "operational_feasibility_gap" in text.lower()
        assert "problem -> mechanism -> method -> boundary" in compact
        assert "multiplicity_control" not in text
        assert "power_mde_or_precision_rationale" not in text
        assert "randomization_seeds_and_independent_replication" not in text


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
    for root in (MAIN, CODEX):
        workflow = json.loads(read(root / "shared-references" / "idea-workflow.yaml"))
        assert workflow["artifact_manifest"] == {
            "active_field_map": "idea-stage/ACTIVE_FIELD_MAP.md",
            "evidence_registry": "idea-stage/EVIDENCE_REGISTRY.jsonl",
            "literature_corpus": "idea-stage/LITERATURE_CORPUS.jsonl",
            "source_admission_policy": "idea-stage/SOURCE_ADMISSION_POLICY.yaml",
            "search_log": "idea-stage/SEARCH_LEDGER.jsonl",
            "root_cause_analysis": "idea-stage/ROOT_CAUSE_ANALYSIS.json",
            "root_cause_analysis_view": "idea-stage/ROOT_CAUSE_ANALYSIS.md",
            "root_cause_verdict": "idea-stage/ROOT_CAUSE_VERDICT.json",
        }
        landscape = next(item for item in workflow["phases"] if item["phase"] == "landscape")
        assert "@artifact:search_log" in landscape["produced_artifacts"]
        assert "@artifact:literature_corpus" in landscape["produced_artifacts"]
        acceptance = next(item for item in workflow["phases"] if item["phase"] == "problem_human_acceptance")
        assert acceptance["requires_coverage"] == {"phase": "landscape", "statuses": ["SUFFICIENT"]}
        phase_names = [item["phase"] for item in workflow["phases"]]
        assert phase_names.index("problem_human_acceptance") < phase_names.index("root_cause_analysis")
        assert phase_names.index("root_cause_analysis") < phase_names.index("root_cause_gate")
        assert phase_names.index("root_cause_gate") < phase_names.index("method_design")
        root_gate = next(item for item in workflow["phases"] if item["phase"] == "root_cause_gate")
        assert root_gate["accepted_verdicts"] == ["DIAGNOSIS_READY"]
        assert root_gate["return_targets"] == {
            "REVISE_DIAGNOSIS": "root_cause_analysis",
            "REOPEN_PROBLEM": "problem_generation",
        }
        human_return_targets = {
            item["phase"]: item["return_targets"]
            for item in workflow["phases"]
            if item.get("human_checkpoint")
        }
        assert human_return_targets == {
            "scope_human_approval": {"request_revision": "landscape"},
            "problem_human_acceptance": {
                "request_revision": "problem_generation",
                "reject": "problem_generation",
            },
            "route_human_selection": {"request_revision": "method_design"},
            "final_method_human_acceptance": {"request_revision": "method_refinement"},
        }
        for phase in workflow["phases"]:
            if phase.get("human_checkpoint"):
                assert phase["accepted_decisions"] == ["approve"]
        research = workflow["research_lit"]
        assert research["controller"] == "arisctl.controller.ARISController"
        assert research["ledger_source"] == "gateway_events_only"
        assert research["canonicalization"] == "staging_then_validator_then_controller_acceptance"
        incremental = workflow["scientific_core"]["incremental_literature"]
        assert incremental["permitted_phases"] == [
            "problem_generation", "problem_novelty_gate", "root_cause_analysis",
            "method_design", "method_refinement", "final_method_novelty_gate"
        ]
        assert incremental["completion"] == "return_to_landscape_accepted_without_coverage_review"
        assert "method_design_may_reenter_while_running" in incremental["entry_policy"]
        method_design = next(item for item in workflow["phases"] if item["phase"] == "method_design")
        assert "idea-stage/ACTIVE_FIELD_MAP.md" in method_design["required_inputs"]


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


def test_field_mapping_and_migration_orders_are_enforced() -> None:
    for root in (MAIN, CODEX):
        problem = read(root / "shared-references" / "problem-discovery-contract.md")
        field_block = problem[problem.index("Build the landscape in this order") :]
        field_chain = (
            "field core purposes",
            "typical tasks and scenarios",
            "core bottlenecks",
            "method families",
            "which bottleneck each family addresses and by what mechanism",
            "assumptions each family requires",
            "conditions where each family is effective",
            "conditions where each family fails",
            "unresolved contradictions",
        )
        positions = [field_block.index(item) for item in field_chain]
        assert positions == sorted(positions)

        migration_block = problem[problem.index("Enforce this order") :]
        migration_chain = (
            "observe problem P in a source field",
            "extract the mechanism that produces P",
            "structurally isomorphic mechanism",
            "confirm with target-field data",
            "only then consider transferring a solution",
        )
        positions = [migration_block.index(item) for item in migration_chain]
        assert positions == sorted(positions)

        method = read(root / "shared-references" / "method-design-contract.md")
        transfer_block = method[method.index("For a cross-field route") :]
        transfer_chain = (
            "source-field problem",
            "source problem-formation mechanism",
            "structurally isomorphic target mechanism",
            "target-field data confirming the problem",
            "residual target design obligation",
            "source solution mechanism",
            "transferred method or idea",
        )
        positions = [transfer_block.index(item) for item in transfer_chain]
        assert positions == sorted(positions)


def test_idea_creator_is_problem_first_and_keeps_combination_strategy() -> None:
    for root in (MAIN, CODEX):
        text = skill(root, "idea-creator")
        assert "Problem-First Ranked Idea Report" in text
        assert "Certified Problems and Derived Routes" in text
        assert "Design obligations" in text
        assert "Scientific mainline" in text
        assert "dominant" in text and "minimal" in text
        assert "residual MUST gap" in text
        assert "supporting-mechanism ledger" in text.lower()
        assert "Scientific-delta novelty" in text
        assert "Lead every recommended idea with its method" not in text
        assert "Quantity first, quality second" not in text


def test_novelty_and_review_keep_problem_and_method_verdicts_separate() -> None:
    for root in (MAIN, CODEX):
        novelty = skill(root, "novelty-check")
        review = skill(root, "research-review")
        assert "mode: problem|method|combined" in novelty
        assert "### Problem Novelty" in novelty
        assert "### Method Novelty" in novelty
        assert "stage: problem|method|project" in review
        assert "Reality, Importance, Unresolvedness, Precision" in review
        assert "stage separation" in review.lower()
        assert "different decisions" in review or "distinct decisions" in review


def test_refine_derives_coherent_routes_from_certified_problem() -> None:
    for root in (MAIN, CODEX):
        text = skill(root, "research-refine")
        assert "Certified Problem Contract" in text
        assert "method-design-contract.md" in text
        assert "Scientific Mainline" in text
        assert "dominant-only closure" in text
        assert "closure" in text.lower()
        assert "scientific delta" in text.lower()
        assert "Frontier Leverage" not in text
        assert "The smallest adequate mechanism wins" not in text
        assert "method-refinement-protocol.md" in text
        assert "Controller-issued final independent review" in text
        assert "Do not read all `round-*.md` files" in text or "Do not read every" in text
        assert "score" in text.lower() and "acceptance" in text.lower()


def test_problem_contract_and_method_proposal_are_separate() -> None:
    text = read(REPO_ROOT / "templates" / "RESEARCH_CONTRACT_TEMPLATE.md")
    capsule = read(REPO_ROOT / "templates" / "PROBLEM_EVIDENCE_CAPSULE_TEMPLATE.md")
    proposal = read(REPO_ROOT / "templates" / "METHOD_PROPOSAL_TEMPLATE.md")
    assert "## Certified Problem Contract" in text
    assert "Problem version" in text and "Contract SHA-256" in text
    assert "Value if yes / value if no" in text
    assert "Problem novelty verdict" in text
    assert "Acceptance status" in text
    assert "## Problem Evidence Capsule" not in text
    assert "PROBLEM_EVIDENCE_CAPSULE_TEMPLATE.md" in text
    assert "# Problem Evidence Capsule" in capsule
    assert "sole formal compact evidence handoff" in capsule
    assert "Linked Contract path" in capsule
    assert "Linked Contract SHA-256" in capsule
    assert "before the Controller records human acceptance" in " ".join(text.split())
    assert "before the Controller records" in " ".join(capsule.split())
    assert "Scientific Mainline" not in text and "Selected Method Route" not in text
    assert "Problem version" in proposal
    assert "Design-obligation set ID" in proposal
    assert "Scientific Mainline" in proposal
    assert "Design Obligations and Route" in proposal
    assert "Scientific Closure and Claim Validation" in proposal
    assert "## Experiment Design" not in text
    assert "experiment plan" in proposal.lower()


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


def test_cross_family_overlays_preserve_the_core_contract() -> None:
    for root in (CLAUDE_OVERLAY, GEMINI_OVERLAY):
        novelty = skill(root, "novelty-check")
        review = skill(root, "research-review")
        refine = skill(root, "research-refine")
        assert "mode: problem|method|combined" in novelty
        assert "Problem Novelty" in novelty and "Method Novelty" in novelty
        assert "stage: problem|method|project" in review
        assert "Certified Problem Contract" in refine
        assert "Scientific Closure" in refine
        assert "Hypothesis Quality" in refine
        assert "Controller-issued final independent Gate" in refine
        assert "Frontier Leverage" not in refine

    creator = skill(GEMINI_OVERLAY, "idea-creator")
    discovery = skill(GEMINI_OVERLAY, "idea-discovery")
    assert "certified problems and derived method routes" in creator.lower()
    assert "scientific mainline" in creator.lower()
    assert "dominant method" in creator.lower()
    assert "problem-certification" in discovery
    assert 'mode: problem|diagnosis|method' in creator
    assert 'mode: diagnosis' in creator
    assert "1a observed failure phenomena" in creator
    assert "2b explicit causal chains" in creator
    assert "root_cause_analysis" in discovery
    assert "root_cause_gate" in discovery
    assert discovery.index('mode: diagnosis') < discovery.index('mode: method')
    assert "METHOD_CONFIRMED_AWAITING_USER_VALIDATION" in discovery


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


def test_refinement_protocol_is_mirrored_and_preserves_gap_driven_search() -> None:
    for root in (MAIN, CODEX):
        text = read(root / "shared-references" / "method-refinement-protocol.md")
        compact = " ".join(text.split()).lower()
        assert "active-context capsule" in compact
        assert "do not read every historical round" in compact
        assert "controller-issued final independent review" in compact
        assert "previous scores" in compact
        assert "only independent review that decides whether this phase ends" in compact
        assert "method_ready" in compact and "rethink" in compact and "hold" in compact
        order = (
            "minimal sufficient dominant solution",
            "dominant-only closure -> residual must gap",
            "field map and same-field completion when that gap remains",
            "cross-field structural search only if same-field options cannot reasonably close it",
        )
        positions = [compact.index(item) for item in order]
        assert positions == sorted(positions)
        assert "combination is permitted only when a supporting mechanism closes a declared" in compact
        assert "neither the default search strategy nor the innovation verdict" in compact


def test_runtime_method_skills_use_residual_gap_and_field_first_order() -> None:
    base_skills = (
        "idea-creator",
        "research-refine",
        "research-refine-pipeline",
        "novelty-check",
        "research-review",
    )
    for root in (MAIN, CODEX):
        for name in base_skills:
            compact = " ".join(skill(root, name).split()).lower()
            assert "residual" in compact, name
            assert "same-field" in compact, name
            assert "combination is the default preferred" not in compact, name
            assert "preferred combination search" not in compact, name

    for root in (CLAUDE_OVERLAY, GEMINI_OVERLAY):
        for name in ("research-refine", "novelty-check", "research-review"):
            compact = " ".join(skill(root, name).split()).lower()
            assert "residual" in compact, name
            assert "same-field" in compact, name
            assert "preferred combination search" not in compact, name

    creator = " ".join(skill(GEMINI_OVERLAY, "idea-creator").split()).lower()
    assert "minimal sufficient dominant" in creator
    assert "residual `must` gap" in creator
    assert creator.index("field map and same-field") < creator.index("other field")


def test_generator_and_problem_jury_are_independent() -> None:
    for root in (MAIN, CODEX):
        text = skill(root, "idea-creator")
        compact = " ".join(text.split()).lower()
        assert "fresh" in compact
        assert "generator" in compact and "jury" in compact
        assert "do not reuse" in compact
        assert "same reviewer thread" not in compact


def test_refine_routing_requires_a_certified_problem() -> None:
    for root in (MAIN, CODEX):
        refine = skill(root, "research-refine")
        pipeline = skill(root, "research-refine-pipeline")
        assert "Do not use for a vague direction" in refine
        assert "For a vague direction" in pipeline
        assert "Certified Problem Contract" in refine


def test_default_discovery_cannot_cross_human_or_compute_gates() -> None:
    for root in (MAIN, CODEX):
        discovery = skill(root, "idea-discovery")
        creator = skill(root, "idea-creator")
        assert "If no response, I'll proceed" not in discovery
        assert "If no response, stop here" in discovery
        assert "AUTO_EXPERIMENT_PLAN = false" in discovery
        assert "CERTIFIED/accepted" in creator
        assert "CERTIFIED/provisional" in creator
        assert "explicit human confirmation" in creator
        assert "Parallel Pilot Experiments" not in creator
        assert "PILOT_MAX_HOURS" not in creator
        assert "single seed" not in creator.lower()
        assert "/experiment-plan" in creator


def test_refine_phase_mapping_matches_shared_protocol() -> None:
    for root in (MAIN, CODEX):
        text = skill(root, "research-refine")
        assert "R1 executes M0-M6" in text
        assert "R2 starts the independent iterative review" in text
        assert "R1 executes M0-M2" not in text


def test_core_codex_relative_reference_links_resolve() -> None:
    link_pattern = re.compile(r"\]\((\.\./[^)#]+\.md)\)")
    for name in (
        "research-lit",
        "idea-creator",
        "idea-discovery",
        "research-refine",
        "research-refine-pipeline",
    ):
        skill_path = CODEX / name / "SKILL.md"
        for relative in link_pattern.findall(read(skill_path)):
            target = (skill_path.parent / relative).resolve()
            assert target.is_file(), f"{skill_path}: unresolved {relative}"


def test_restored_idea_modules_are_mirrored_and_keep_stage_boundaries() -> None:
    module_names = (
        "idea-fanout-module.md",
        "idea-wiki-integration.md",
        "reference-paper-intake.md",
        "idea-output-composition.md",
    )
    for name in module_names:
        main = read(MAIN / "shared-references" / name)
        codex = read(CODEX / "shared-references" / name)
        assert main == codex, name
        assert len(main) < 12_000, name

    fanout = read(MAIN / "shared-references" / "idea-fanout-module.md")
    assert "working Leads" in fanout
    assert "not Lead artifacts" in fanout
    assert "certification" in fanout and "ranking" in fanout
    assert "never reused as a jury context" in fanout

    wiki = read(MAIN / "shared-references" / "idea-wiki-integration.md")
    assert "wiki-helper-resolution.md" in wiki
    assert "query_pack.md" in wiki
    assert 'python3 "$WIKI_SCRIPT" upsert_idea' in wiki
    assert "Wiki presence is memory" in wiki

    paper = read(MAIN / "shared-references" / "reference-paper-intake.md")
    assert "REF_PAPER" in paper
    assert "USER_SUPPLIED_READ" in paper
    assert "REF_PAPER_SUMMARY.md" in paper
    assert "cannot silently change scope" in paper
    assert "do not generate a method" in paper

    composition = read(MAIN / "shared-references" / "idea-output-composition.md")
    assert "if and only if" in composition
    assert "never activates it" in composition
    composition_compact = " ".join(composition.split())
    assert "only after the human has accepted the problem, the root-cause Gate is `DIAGNOSIS_READY`, and the human has selected a route" in composition_compact


def test_root_cause_contract_is_mirrored_and_precedes_method_design() -> None:
    main = read(MAIN / "shared-references" / "root-cause-analysis-contract.md")
    codex = read(CODEX / "shared-references" / "root-cause-analysis-contract.md")
    assert main == codex
    for marker in (
        "1a - Direct phenomenon evidence",
        "1b - Phenomenon grouping",
        "2a - Causal depth traces",
        "2b - Causal chains",
        "DIAGNOSIS_READY | REVISE_DIAGNOSIS | REOPEN_PROBLEM",
        "A failed experiment is not a mandatory prerequisite",
        "evidence_source_type: existing_experiment | literature | dataset | real_world | diagnostic_pilot",
        "reviewed_analysis_sha256",
        "primary_causal_chain_ids",
    ):
        assert marker in main
    method = read(MAIN / "shared-references" / "method-design-contract.md")
    assert "only after the independent Root-Cause Gate" in method
    assert "derived_from_causal_chain_id" in method


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
    expected = {
        "problem_quality_gate": {
            "HOLD": "problem_generation",
            "REJECT": "problem_generation",
            "BLOCKED": "problem_generation",
        },
        "problem_novelty_gate": {
            "BLOCKED": "problem_generation",
        },
        "final_method_novelty_gate": {
            "UNCERTAIN": "method_design",
            "NOT_NOVEL": "method_design",
            "BLOCKED": "method_design",
        },
        "method_refinement": {
            "REVISE": "method_refinement",
            "RETHINK": "method_design",
            "HOLD": "method_refinement",
        },
    }
    for root in (MAIN, CODEX):
        workflow = json.loads(read(root / "shared-references" / "idea-workflow.yaml"))
        phases = {item["phase"]: item for item in workflow["phases"]}
        ordered = [item["phase"] for item in workflow["phases"]]
        for phase_name, targets in expected.items():
            assert phases[phase_name]["return_targets"] == targets
            assert all(ordered.index(target) <= ordered.index(phase_name) for target in targets.values())
        assert phases["method_refinement"]["accepted_verdicts"] == ["METHOD_READY"]


def test_formal_experiment_chain_requires_mechanism_evidence_and_result_interpretation() -> None:
    for root in (MAIN, CODEX):
        plan = skill(root, "experiment-plan")
        assert "ROOT_CAUSE_ANALYSIS.json" in plan
        assert "ROOT_CAUSE_VERDICT.json" in plan
        assert "Mechanism Validation Map" in plan
        assert "Predicted mechanism or failure-phenomenon change" in plan
        assert "Mechanism observation" in plan
        assert "Performance evaluation" in plan
        assert "smallest necessary ablation or controlled comparison" in plan
        assert "not a new workflow stage or Gate" in plan

        result = skill(root, "result-to-claim")
        assert "mechanism evidence table" in result
        assert "mechanism_status" in result
        assert "EXPLANATION_SUPPORTED | PERFORMANCE_ONLY | DIAGNOSE_FAILURE" in result
        assert "mechanism_evidence_closure" in result
        assert '"explanation_status": "EXPLANATION_SUPPORTED"' in result
        assert '"mechanism_match": "MATCHES_PREDICTION"' in result
        assert "validation_review_request" in result
        assert "Main must not parse or normalize the judgment" in result
        assert "positive empirical result, but does NOT establish the original mechanism" in result
        assert "method mismatch, implementation/measurement fault, and an incomplete or wrong earlier analysis" in result
        assert "Preserve anomalous observations as new" in result

    discovery = skill(MAIN, "idea-discovery")
    assert "WebSearch" not in discovery
    assert "WebFetch" not in discovery

    template = read(REPO_ROOT / "templates" / "EXPERIMENT_PLAN_TEMPLATE.md")
    template_cn = read(REPO_ROOT / "templates" / "EXPERIMENT_PLAN_TEMPLATE_CN.md")
    for marker in ("Mechanism Validation Map", "Causal link / core change", "Use only when needed"):
        assert marker in template
    for marker in ("机制验证映射", "因果链 / 核心改动", "仅在必要时使用"):
        assert marker in template_cn


def test_experiment_skills_fail_closed_for_formal_inputs_and_isolate_ad_hoc_work() -> None:
    for root in (MAIN, CODEX):
        plan = skill(root, "experiment-plan")
        bridge = skill(root, "experiment-bridge")
        for text in (plan, bridge):
            assert "validation-handoff <run_id>" in text
            assert "NON_CANONICAL_AD_HOC" in text
            assert "not a new workflow stage or Gate" in text or "read-only preflight" in text

        assert "Do not derive `FINAL_PROPOSAL`" in plan
        assert "missing files are a stop condition" in plan
        assert "Do not create `FINAL_PROPOSAL`, `RESEARCH_CONTRACT`" in bridge
        assert "this fallback is forbidden" in bridge
        assert "idea-stage/docs/research_contract.md" in bridge


def test_research_pipeline_cannot_bypass_the_canonical_scientific_route() -> None:
    required = (
        "validation-handoff <run_id>",
        "METHOD_CONFIRMED_AWAITING_USER_VALIDATION",
        "sole formal entry to this\npipeline",
        "Do not recreate, infer, replace, or supplement",
        "Stop. Do not invoke `/idea-discovery`",
        "must not use `tools/run_state.py`",
        "There is no\ntimeout approval, automatic choice of a ranked idea",
        "`/research-pipeline` does not operate in `NON_CANONICAL_AD_HOC` mode",
        "`/experiment-plan`",
        "`/experiment-bridge`",
        "`/result-to-claim`",
    )
    forbidden = (
        "AUTO_PROCEED = true",
        "wait 10 seconds",
        "run_state.py start",
        "### Stage 1: Idea Discovery",
        "End-to-end autonomous research workflow",
    )

    for root in (MAIN, CODEX):
        pipeline = skill(root, "research-pipeline")
        for marker in required:
            assert marker in pipeline
        for marker in forbidden:
            assert marker not in pipeline


def test_public_routing_and_legacy_iteration_log_are_consistent() -> None:
    public_routes = {
        REPO_ROOT / "README.md": 'research-pipeline "<canonical-run-id>"',
        REPO_ROOT / "README_CN.md": 'research-pipeline "<canonical-run-id>"',
        REPO_ROOT / "AGENT_GUIDE.md": "canonical Controller workflow",
        REPO_ROOT / "docs" / "SKILLS_CATALOG.md": "input is a canonical run ID",
        REPO_ROOT / "SETUP_GUIDE.md": 'research-pipeline "<canonical-run-id>"',
        REPO_ROOT / "docs" / "COPILOT_CLI_ADAPTATION.md": 'research-pipeline "<canonical-run-id>"',
    }
    for path, marker in public_routes.items():
        assert marker in read(path), path

    assert 'research-pipeline "your topic"' not in read(REPO_ROOT / "README.md")
    assert 'research-pipeline "你的课题"' not in read(REPO_ROOT / "README_CN.md")
    assert "chains idea discovery → auto review → paper writing autonomously" not in read(
        REPO_ROOT / "README.md"
    )
    assert "三大工作流端到端贯通" not in read(REPO_ROOT / "README_CN.md")

    for path in (REPO_ROOT / "README.md", REPO_ROOT / "README_CN.md"):
        text = read(path)
        assert "METHOD_CONFIRMED_AWAITING_USER_VALIDATION" in text
        assert "SEARCH_LEDGER.jsonl" in text
    guide = read(REPO_ROOT / "AGENT_GUIDE.md")
    assert "IDEA_REPORT.md` | `/idea-discovery` | human reading only" in guide
    assert "refine-logs/EXPERIMENT_PLAN.md" in guide
    handoff = read(REPO_ROOT / "RESEARCH_HANDOFF_CN.md")
    assert "SEARCH_LEDGER.jsonl" in handoff
    assert "SEARCH_LOG.md" not in handoff
    assert "USER_SUPPLIED_READ" in handoff
    catalog = read(REPO_ROOT / "docs" / "SKILLS_CATALOG.md")
    assert "stops before validation" in catalog
    assert "not part of canonical `/idea-discovery`" in catalog

    iteration_log = read(REPO_ROOT / "tools" / "iteration_log.py")
    assert "LEGACY: iteration_log.py" in iteration_log
    for root in (MAIN, CODEX):
        cadence = read(root / "shared-references" / "external-cadence.md")
        integration = read(root / "shared-references" / "integration-contract.md")
        assert "no active shipped consumer" in cadence
        assert "Legacy; no active caller" in integration


def test_idea_workflow_references_restored_modules_without_inlining_them() -> None:
    creator = skill(MAIN, "idea-creator")
    discovery = skill(MAIN, "idea-discovery")
    for ref in (
        "idea-fanout-module.md",
        "idea-wiki-integration.md",
        "idea-output-composition.md",
    ):
        assert ref in creator
    for ref in ("reference-paper-intake.md", "idea-output-composition.md"):
        assert ref in discovery
    assert "REF_PAPER = false" in discovery
    assert "COMPACT = false" in discovery
    assert "human problem or route decision" in discovery
    assert "mode: method" in creator and "human_accepted" in creator
