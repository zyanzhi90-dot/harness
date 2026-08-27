"""Workflow loading shared by the ARIS controller and legacy run state."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tools.run_state import _load_workflow


CANONICAL_WORKFLOW_PATH = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "shared-references"
    / "idea-workflow.yaml"
)


def canonical_workflow_path() -> Path:
    return CANONICAL_WORKFLOW_PATH.resolve()


REQUIRED_RESEARCH_STAGES = (
    "SOURCE_POLICY_DRAFTING",
    "WAITING_FOR_HUMAN",
    "QUERY_PLANNING",
    "METADATA_RETRIEVAL",
    "HUMAN_SEARCH_REQUIRED",
    "PAPER_READING",
    "FIELD_SYNTHESIS",
    "COVERAGE_REVIEW",
    "LANDSCAPE_ACCEPTED",
)

def load_workflow(path: str | Path) -> dict[str, Any]:
    workflow = _load_workflow(str(path))
    assert workflow is not None
    research = workflow.get("research_lit")
    if not isinstance(research, dict):
        raise ValueError("workflow requires a research_lit controller declaration")
    stages = research.get("stages")
    if not isinstance(stages, list) or tuple(stages) != REQUIRED_RESEARCH_STAGES:
        raise ValueError(
            "research_lit.stages must declare the canonical controller stage order"
        )
    actions = research.get("allowed_actions")
    if not isinstance(actions, dict) or any(stage not in actions for stage in stages):
        raise ValueError("research_lit.allowed_actions must cover every controller stage")
    agents = research.get("allowed_agents")
    if not isinstance(agents, dict) or any(stage not in agents for stage in stages):
        raise ValueError("research_lit.allowed_agents must cover every controller stage")
    if any(not isinstance(agents[stage], list) for stage in stages):
        raise ValueError("research_lit.allowed_agents values must be lists")
    scientific_core = workflow.get("scientific_core")
    if not isinstance(scientific_core, dict):
        raise ValueError("workflow requires a scientific_core controller declaration")
    core_phases = scientific_core.get("phases")
    if (
        not isinstance(core_phases, list)
        or not core_phases
        or any(not isinstance(phase, str) or not phase for phase in core_phases)
        or len(core_phases) != len(set(core_phases))
    ):
        raise ValueError("scientific_core.phases must be a non-empty list of unique names")
    declared_specs = {
        item["phase"]: item
        for item in workflow.get("phases", [])
        if isinstance(item, dict) and isinstance(item.get("phase"), str)
    }
    if any(phase not in declared_specs for phase in core_phases):
        raise ValueError("scientific_core.phases must reference declared workflow phases")
    core_positions = {phase: index for index, phase in enumerate(core_phases)}
    for phase, index in core_positions.items():
        for dependency in declared_specs[phase].get("depends_on", []):
            dependency_index = core_positions.get(dependency)
            if dependency_index is not None and dependency_index >= index:
                raise ValueError(
                    "scientific_core.phases must be topologically compatible with "
                    f"declared dependencies: {phase!r} depends on {dependency!r}"
                )
    core_agents = scientific_core.get("allowed_agents")
    if not isinstance(core_agents, dict) or any(
        phase not in core_agents or not isinstance(core_agents[phase], list)
        for phase in core_phases
    ):
        raise ValueError("scientific_core.allowed_agents must cover every core phase")
    for phase in core_phases:
        spec = declared_specs[phase]
        if spec.get("formal_gate") and not spec.get("human_checkpoint"):
            role = spec.get("reviewer_role")
            verdicts = spec.get("accepted_verdicts")
            if (
                not isinstance(role, str)
                or role not in core_agents[phase]
                or not isinstance(verdicts, list)
                or not verdicts
            ):
                raise ValueError(
                    f"formal reviewer Gate {phase!r} must declare an allowed reviewer_role and verdict enum"
                )
    incremental = scientific_core.get("incremental_literature")
    if not isinstance(incremental, dict):
        raise ValueError("scientific_core requires an incremental_literature declaration")
    incremental_phases = incremental.get("permitted_phases")
    if (
        not isinstance(incremental_phases, list)
        or not incremental_phases
        or any(phase not in core_phases for phase in incremental_phases)
        or len(incremental_phases) != len(set(incremental_phases))
    ):
        raise ValueError("incremental_literature.permitted_phases must be unique declared core phases")
    if incremental.get("completion") != "return_to_landscape_accepted_without_coverage_review":
        raise ValueError("incremental literature must not add a second coverage Gate")
    final_spec = declared_specs[core_phases[-1]]
    if not final_spec.get("formal_gate") or not final_spec.get("human_checkpoint"):
        raise ValueError(
            "scientific_core must end at a formal Human Gate before validation"
        )
    if scientific_core.get("completion_state") != "METHOD_CONFIRMED_AWAITING_USER_VALIDATION":
        raise ValueError("scientific_core must stop at human-initiated validation entry")
    if (
        scientific_core.get("validation_entry_policy")
        != "human_initiated_only_after_method_confirmation"
    ):
        raise ValueError("scientific_core validation entry must remain human-initiated")
    if (
        scientific_core.get("artifact_hook_policy")
        != "registered_path_sha256_provenance_and_upstream_snapshot"
    ):
        raise ValueError("scientific_core must declare the registered artifact hook")
    budget = workflow.get("research_effort_budget")
    if not isinstance(budget, dict) or not isinstance(budget.get("max_queries"), int):
        raise ValueError("workflow requires an integer research_effort_budget.max_queries")
    if not isinstance(budget.get("max_fulltext_papers"), int):
        raise ValueError(
            "workflow requires an integer research_effort_budget.max_fulltext_papers"
        )
    return workflow
