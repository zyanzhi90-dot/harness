"""Type-A validators. Scientific truth and taxonomy remain reviewer judgments."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

class ValidationError(ValueError):
    pass


EVIDENCE_CARD_FIELDS = (
    "source_id",
    "read_event_id",
    "content_sha256",
    "claim",
    "claim_locator",
    "access_level",
    "decision_grade",
    "epistemic_status",
    "problem_and_setting",
    "method_or_mechanism",
    "content_summary",
    "synthesis_role",
    "development_link",
    "evidence",
    "evidence_kind",
    "boundary_conditions",
    "assumptions",
    "reported_or_inferred_failures",
    "conflicts_with",
    "verification_status",
)

FIELD_MAP_FIELDS = (
    "field_core_purposes",
    "typical_tasks_and_scenarios",
    "core_bottlenecks",
    "method_families",
    "family_development_traces",
    "problem_method_matrix",
    "assumption_effectiveness_failure_matrix",
    "consensus",
    "unresolved_contradictions",
    "coverage_record",
    "unresolved_problem_leads",
)

DEVELOPMENT_TRACE_FIELDS = (
    "transition_id",
    "previous_problem_or_bottleneck",
    "progress_and_conditions",
    "residual_or_new_bottleneck",
    "research_question_shift",
    "subsequent_direction",
    "transition_problem_status",
    "evidence_ids",
)

TRANSITION_PROBLEM_STATUSES = {
    "still_open",
    "partially_addressed",
    "mature_under_specific_conditions",
    "reframed",
}

EVOLUTION_ASSESSMENT_FIELDS = (
    "foundation_to_frontier",
    "key_nodes_and_branches",
    "transition_causality",
    "explanatory_coherence",
)

TRANSITION_CAUSALITY_BASES = {
    "DECLARED_TRACES_REVIEWED",
    "NO_MATERIAL_TRANSITION_SUPPORTED",
    "MATERIAL_TRANSITION_MISSING",
}

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_OBSERVATION_STATUSES = {"established", "supported", "preliminary", "contested"}
_EXPLANATION_STATUSES = {"supported", "preliminary", "speculative", "contested"}
_CHAIN_STATUSES = {"supported", "preliminary", "contested"}
_ROOT_CAUSE_DECISIONS = {
    "DIAGNOSIS_READY",
    "REVISE_DIAGNOSIS",
    "REOPEN_PROBLEM",
}
_NECESSITY_DECISIONS = {
    "FULLY_COVERED",
    "RESIDUAL_SAME_PROBLEM",
    "RESIDUAL_REDEFINES_PROBLEM",
    "UNRESOLVED",
}
_PHENOMENON_EVIDENCE_SOURCE_TYPES = {
    "existing_experiment",
    "literature",
    "dataset",
    "real_world",
    "diagnostic_pilot",
}
_PROBLEM_SOURCE_CLASSES = {
    "community_open_problem",
    "self_discovered",
    "problem_migration",
}
_PROBLEM_CANDIDATE_TEXT_FIELDS = (
    "research_question",
    "observed_phenomenon",
    "scope_and_conditions",
    "why_it_matters",
    "value_if_yes",
    "value_if_no",
    "measurement_validity",
    "phenomenon_prevalence_or_effect_scale",
    "decision_owner_and_threshold",
    "falsifier",
    "feasible_discriminating_probe",
    "closest_prior_answer",
    "dedup_key",
)
_PROBLEM_CANDIDATE_LIST_FIELDS = (
    "evidence_refs",
    "artifact_or_confound_alternatives",
    "independent_support",
    "uncertainties",
)
_PROBLEM_MIGRATION_TEXT_FIELDS = (
    "source_problem_and_evidence",
    "source_problem_formation_mechanism",
    "target_mechanism_mapping",
    "target_structural_isomorphism",
    "target_problem_evidence",
    "stakes_and_scope",
    "disanalogy_and_transfer_limit",
    "target_negative_control_analogue",
    "transfer_failure_criterion",
)
_PROBLEM_MIGRATION_LIST_FIELDS = (
    "expected_invariants",
    "non_invariants_that_may_break_transfer",
)
_PROBLEM_MIGRATION_TRANSFER_STATUSES = {
    "forbidden_until_target_confirmed",
    "eligible_for_method_search",
}
_QUALITY_DIMENSIONS = (
    "Reality",
    "Importance",
    "Unresolvedness",
    "Precision",
    "Falsifiability",
    "Answerability",
)
_QUALITY_EVIDENCE_DIMENSIONS = {
    "Reality",
    "Importance",
    "Unresolvedness",
}
_QUALITY_JUDGMENTS = {
    "PASS",
    "INSUFFICIENT_EVIDENCE",
    "FAIL",
}


def validate_problem_candidates_artifact(
    text: str,
    *,
    label: str,
    formal_evidence_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Validate the machine-readable candidate index used by later Gates.

    This is the machine-readable P2 contract. It validates complete candidate
    structure and formal-evidence references, while leaving the scientific
    adequacy of every field to the independent reviewer.
    """

    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"{label} line {line_number} must be JSON") from exc
        records.append(_require_mapping(record, f"{label} candidate {line_number}"))
    if not records:
        raise ValidationError(f"{label} must contain at least one candidate")
    candidate_ids: set[str] = set()
    for index, record in enumerate(records, 1):
        candidate_label = f"{label} candidate {index}"
        _require_fields(
            record,
            (
                "problem_id",
                "source_class",
                *_PROBLEM_CANDIDATE_TEXT_FIELDS,
                *_PROBLEM_CANDIDATE_LIST_FIELDS,
                "plausible_explanations",
                "provenance",
            ),
            candidate_label,
        )
        problem_id = record["problem_id"]
        if not isinstance(problem_id, str) or not problem_id.strip() or problem_id in candidate_ids:
            raise ValidationError(f"{label} problem_id values must be non-empty and unique")
        if record["source_class"] not in _PROBLEM_SOURCE_CLASSES:
            raise ValidationError(
                f"{label} source_class must be one of {sorted(_PROBLEM_SOURCE_CLASSES)}"
            )
        for field in _PROBLEM_CANDIDATE_TEXT_FIELDS:
            if not isinstance(record[field], str) or not record[field].strip():
                raise ValidationError(f"{candidate_label}.{field} must be a non-empty string")
        for field in _PROBLEM_CANDIDATE_LIST_FIELDS:
            values = _require_string_list(record[field], f"{candidate_label}.{field}", non_empty=True)
            if len(values) != len(set(values)):
                raise ValidationError(f"{candidate_label}.{field} must not contain duplicate values")
        _validate_plausible_explanations(record["plausible_explanations"], candidate_label)
        if not isinstance(record["provenance"], dict) or not record["provenance"]:
            raise ValidationError(f"{candidate_label}.provenance must be a non-empty object")
        evidence_refs = set(record["evidence_refs"])
        if formal_evidence_ids is not None:
            unresolved = sorted(evidence_refs - formal_evidence_ids)
            if unresolved:
                raise ValidationError(
                    f"{candidate_label}.evidence_refs contain unregistered formal evidence IDs: {unresolved}"
                )
        if record["source_class"] == "problem_migration":
            _require_fields(
                record,
                (
                    *_PROBLEM_MIGRATION_TEXT_FIELDS,
                    "unit_and_variable_mapping",
                    *_PROBLEM_MIGRATION_LIST_FIELDS,
                    "solution_transfer_status",
                ),
                candidate_label,
            )
            for field in _PROBLEM_MIGRATION_TEXT_FIELDS:
                if not isinstance(record[field], str) or not record[field].strip():
                    raise ValidationError(f"{candidate_label}.{field} must be a non-empty string")
            if not isinstance(record["unit_and_variable_mapping"], dict) or not record["unit_and_variable_mapping"]:
                raise ValidationError(
                    f"{candidate_label}.unit_and_variable_mapping must be a non-empty object"
                )
            for field in _PROBLEM_MIGRATION_LIST_FIELDS:
                _require_string_list(record[field], f"{candidate_label}.{field}", non_empty=True)
            if record["solution_transfer_status"] not in _PROBLEM_MIGRATION_TRANSFER_STATUSES:
                raise ValidationError(
                    f"{candidate_label}.solution_transfer_status must be one of "
                    f"{sorted(_PROBLEM_MIGRATION_TRANSFER_STATUSES)}"
                )
        candidate_ids.add(problem_id)
    return {"candidate_ids": sorted(candidate_ids)}


def _validate_plausible_explanations(value: Any, candidate_label: str) -> None:
    if not isinstance(value, list) or not value:
        raise ValidationError(f"{candidate_label}.plausible_explanations must be a non-empty list")
    for index, raw in enumerate(value, 1):
        item = _require_mapping(raw, f"{candidate_label}.plausible_explanations[{index}]")
        _require_fields(
            item,
            ("explanation", "epistemic_status"),
            f"{candidate_label}.plausible_explanations[{index}]",
        )
        if not isinstance(item["explanation"], str) or not item["explanation"].strip():
            raise ValidationError(
                f"{candidate_label}.plausible_explanations[{index}].explanation must be a non-empty string"
            )
        if item["epistemic_status"] not in _EXPLANATION_STATUSES:
            raise ValidationError(
                f"{candidate_label}.plausible_explanations[{index}].epistemic_status is invalid"
            )


def _validate_review_binding(
    payload: Any,
    *,
    label: str,
    request_id: str,
    reviewer: str | None,
    verdict_id: str | None,
    decision: str | None,
    artifact_bindings: dict[str, str],
) -> dict[str, Any]:
    """Validate the mechanical identity shared by a verdict artifact and attestation."""

    record = _require_mapping(payload, label)
    _require_fields(
        record,
        (
            "schema_version",
            "review_request_id",
            "reviewer",
            "verdict_id",
            "decision",
            "reviewed_artifact_hashes",
        ),
        label,
    )
    if record["schema_version"] != 1:
        raise ValidationError(f"{label} schema_version must be 1")
    if record["review_request_id"] != request_id:
        raise ValidationError(f"{label} review_request_id does not match the live review request")
    if not isinstance(record["reviewer"], str) or not record["reviewer"]:
        raise ValidationError(f"{label} reviewer must be a non-empty string")
    if not isinstance(record["verdict_id"], str) or not record["verdict_id"]:
        raise ValidationError(f"{label} verdict_id must be a non-empty string")
    if not isinstance(record["decision"], str) or not record["decision"]:
        raise ValidationError(f"{label} decision must be a non-empty string")
    bindings = record["reviewed_artifact_hashes"]
    if (
        not isinstance(bindings, dict)
        or any(
            not isinstance(path, str)
            or not path
            or _SHA256_RE.fullmatch(digest) is None
            for path, digest in bindings.items()
        )
    ):
        raise ValidationError(f"{label} reviewed_artifact_hashes must be a SHA-256 map")
    if bindings != artifact_bindings:
        raise ValidationError(f"{label} reviewed_artifact_hashes do not match the live review request")
    for field, expected in (("reviewer", reviewer), ("verdict_id", verdict_id), ("decision", decision)):
        if expected is not None and record[field] != expected:
            raise ValidationError(f"{label} {field} does not match the phase verdict")
    return record


def validate_candidate_verdict_artifact(
    text: str,
    *,
    label: str,
    request_id: str,
    artifact_bindings: dict[str, str],
    phase_decisions: set[str],
    candidate_decisions: set[str],
    expected_candidate_ids: set[str] | None = None,
    review_kind: str,
    formal_evidence_paths: dict[str, str],
    formal_evidence_source_ids: dict[str, str],
) -> dict[str, Any]:
    """Validate a JSONL candidate review plus its one phase-level decision.

    Candidate rows retain the Type-B assessment for each proposed problem. The
    phase row is the only value that can authorize the Controller transition.
    This validator checks that the declared assessment has the contract-required
    structure and binds every declared evidence anchor; it does not decide the
    assessment's scientific truth.
    """

    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValidationError(f"{label} line {line_number} must be JSON") from exc
    if not records:
        raise ValidationError(f"{label} must contain candidate verdicts and one phase verdict")
    summaries = [item for item in records if isinstance(item, dict) and item.get("record_type") == "phase_verdict"]
    candidates = [item for item in records if isinstance(item, dict) and item.get("record_type") == "candidate_verdict"]
    if len(summaries) != 1 or len(candidates) != len(records) - 1 or not candidates:
        raise ValidationError(f"{label} must contain one phase_verdict and one candidate_verdict per row")
    summary = _validate_review_binding(
        summaries[0],
        label=f"{label} phase verdict",
        request_id=request_id,
        reviewer=None,
        verdict_id=None,
        decision=None,
        artifact_bindings=artifact_bindings,
    )
    if summary["decision"] not in phase_decisions:
        raise ValidationError(f"{label} phase decision is not allowed by the Gate")
    candidate_ids: set[str] = set()
    candidate_outcomes: list[str] = []
    for index, item in enumerate(candidates, 1):
        candidate = _validate_review_binding(
            item,
            label=f"{label} candidate verdict {index}",
            request_id=request_id,
            reviewer=summary["reviewer"],
            verdict_id=summary["verdict_id"],
            decision=None,
            artifact_bindings=artifact_bindings,
        )
        candidate_id = candidate.get("candidate_id")
        if not isinstance(candidate_id, str) or not candidate_id or candidate_id in candidate_ids:
            raise ValidationError(f"{label} candidate_id values must be non-empty and unique")
        candidate_ids.add(candidate_id)
        if candidate["decision"] not in candidate_decisions:
            raise ValidationError(f"{label} candidate decision is invalid")
        if review_kind == "quality":
            _validate_quality_assessment(
                candidate,
                label=f"{label} candidate verdict {index}",
                formal_evidence_paths=formal_evidence_paths,
                artifact_bindings=artifact_bindings,
            )
        elif review_kind == "novelty":
            _validate_novelty_assessment(
                candidate,
                label=f"{label} candidate verdict {index}",
                formal_evidence_paths=formal_evidence_paths,
                formal_evidence_source_ids=formal_evidence_source_ids,
                artifact_bindings=artifact_bindings,
            )
        else:
            raise ValidationError(f"{label} review kind is invalid")
        candidate_outcomes.append(candidate["decision"])
    if expected_candidate_ids is not None and candidate_ids != expected_candidate_ids:
        raise ValidationError(f"{label} candidate verdicts do not cover the expected candidate set")
    if summary["decision"] not in candidate_outcomes:
        raise ValidationError(
            f"{label} phase decision must be supported by at least one candidate verdict"
        )
    if review_kind == "novelty":
        consumable = {"NOVEL", "NOT_NOVEL", "UNCERTAIN"}
        has_consumable = any(decision in consumable for decision in candidate_outcomes)
        has_uncertain = "UNCERTAIN" in candidate_outcomes
        if summary["decision"] == "BLOCKED" and has_consumable:
            raise ValidationError(
                f"{label} may be BLOCKED only when every candidate novelty audit is BLOCKED"
            )
        if summary["decision"] != "BLOCKED" and not has_consumable:
            raise ValidationError(
                f"{label} must be BLOCKED when no candidate novelty audit is consumable"
            )
        if has_uncertain and summary["decision"] != "UNCERTAIN":
            raise ValidationError(
                f"{label} phase decision must be UNCERTAIN when any candidate novelty audit is UNCERTAIN"
            )
    survivors = sorted(
        candidate_id
        for candidate_id, decision in zip(
            (item["candidate_id"] for item in candidates), candidate_outcomes
        )
        if decision == summary["decision"]
    )
    declared_survivors = summary.get("survivor_ids")
    if (
        not isinstance(declared_survivors, list)
        or any(not isinstance(item, str) or not item for item in declared_survivors)
        or len(declared_survivors) != len(set(declared_survivors))
        or sorted(declared_survivors) != survivors
    ):
        raise ValidationError(
            f"{label} phase verdict survivor_ids must exactly identify candidates with its decision"
        )
    return_guidance = _validate_return_guidance(
        summary,
        label=f"{label} phase verdict",
        required=(
            (review_kind == "quality" and summary["decision"] == "HOLD")
            or (review_kind == "novelty" and summary["decision"] == "UNCERTAIN")
        ),
    )
    return {
        **summary,
        "candidate_ids": sorted(candidate_ids),
        "survivor_ids": survivors,
        **({"return_guidance": return_guidance} if return_guidance is not None else {}),
    }


def _validate_anchored_evidence_ids(
    value: Any,
    *,
    label: str,
    formal_evidence_paths: dict[str, str],
    artifact_bindings: dict[str, str],
    non_empty: bool = True,
) -> list[str]:
    evidence_ids = _require_string_list(value, label, non_empty=non_empty)
    if len(evidence_ids) != len(set(evidence_ids)):
        raise ValidationError(f"{label} must not contain duplicate evidence IDs")
    unresolved = sorted(set(evidence_ids) - set(formal_evidence_paths))
    if unresolved:
        raise ValidationError(f"{label} contains unregistered formal evidence IDs: {unresolved}")
    unbound = sorted(
        evidence_id
        for evidence_id in evidence_ids
        if formal_evidence_paths[evidence_id] not in artifact_bindings
    )
    if unbound:
        raise ValidationError(f"{label} contains evidence not bound into this review: {unbound}")
    return evidence_ids


def _validate_quality_assessment(
    candidate: dict[str, Any],
    *,
    label: str,
    formal_evidence_paths: dict[str, str],
    artifact_bindings: dict[str, str],
) -> None:
    assessment = _require_mapping(candidate.get("quality_assessment"), f"{label}.quality_assessment")
    if set(assessment) != set(_QUALITY_DIMENSIONS):
        raise ValidationError(
            f"{label}.quality_assessment must contain exactly {list(_QUALITY_DIMENSIONS)}"
        )
    for dimension in _QUALITY_DIMENSIONS:
        item = _require_mapping(assessment[dimension], f"{label}.quality_assessment.{dimension}")
        _require_fields(
            item,
            ("judgment", "rationale", "evidence_ids", "issue_ids"),
            f"{label}.quality_assessment.{dimension}",
        )
        if item["judgment"] not in _QUALITY_JUDGMENTS:
            raise ValidationError(
                f"{label}.quality_assessment.{dimension}.judgment is invalid"
            )
        if not isinstance(item["rationale"], str) or not item["rationale"].strip():
            raise ValidationError(f"{label}.quality_assessment.{dimension}.rationale must be a non-empty string")
        _validate_anchored_evidence_ids(
            item["evidence_ids"],
            label=f"{label}.quality_assessment.{dimension}.evidence_ids",
            formal_evidence_paths=formal_evidence_paths,
            artifact_bindings=artifact_bindings,
            non_empty=dimension in _QUALITY_EVIDENCE_DIMENSIONS,
        )
        _require_string_list(
            item["issue_ids"],
            f"{label}.quality_assessment.{dimension}.issue_ids",
        )


def _validate_novelty_assessment(
    candidate: dict[str, Any],
    *,
    label: str,
    formal_evidence_paths: dict[str, str],
    formal_evidence_source_ids: dict[str, str],
    artifact_bindings: dict[str, str],
) -> None:
    assessment = _require_mapping(candidate.get("novelty_assessment"), f"{label}.novelty_assessment")
    _require_fields(
        assessment,
        ("closest_priors", "search_coverage", "residual_unresolved_delta", "evidence_ids", "issue_ids"),
        f"{label}.novelty_assessment",
    )
    if not isinstance(assessment["residual_unresolved_delta"], str) or not assessment["residual_unresolved_delta"].strip():
        raise ValidationError(f"{label}.novelty_assessment.residual_unresolved_delta must be a non-empty string")
    _validate_anchored_evidence_ids(
        assessment["evidence_ids"],
        label=f"{label}.novelty_assessment.evidence_ids",
        formal_evidence_paths=formal_evidence_paths,
        artifact_bindings=artifact_bindings,
    )
    _require_string_list(assessment["issue_ids"], f"{label}.novelty_assessment.issue_ids")
    coverage = _require_mapping(assessment["search_coverage"], f"{label}.novelty_assessment.search_coverage")
    _require_fields(coverage, ("summary", "artifact_paths"), f"{label}.novelty_assessment.search_coverage")
    if not isinstance(coverage["summary"], str) or not coverage["summary"].strip():
        raise ValidationError(f"{label}.novelty_assessment.search_coverage.summary must be a non-empty string")
    coverage_paths = _require_string_list(
        coverage["artifact_paths"],
        f"{label}.novelty_assessment.search_coverage.artifact_paths",
        non_empty=True,
    )
    if len(coverage_paths) != len(set(coverage_paths)) or any(path not in artifact_bindings for path in coverage_paths):
        raise ValidationError(
            f"{label}.novelty_assessment.search_coverage.artifact_paths must name bound coverage artifacts"
        )
    priors = assessment["closest_priors"]
    if not isinstance(priors, list) or not priors:
        raise ValidationError(f"{label}.novelty_assessment.closest_priors must be a non-empty list")
    for index, raw_prior in enumerate(priors, 1):
        prior = _require_mapping(raw_prior, f"{label}.novelty_assessment.closest_priors[{index}]")
        _require_fields(
            prior,
            ("paper_id", "verification_status", "potentially_decisive", "overlap", "residual_delta"),
            f"{label}.novelty_assessment.closest_priors[{index}]",
        )
        if not all(isinstance(prior[field], str) and prior[field].strip() for field in ("paper_id", "overlap", "residual_delta")):
            raise ValidationError(f"{label}.novelty_assessment.closest_priors[{index}] text fields must be non-empty strings")
        if not isinstance(prior["potentially_decisive"], bool):
            raise ValidationError(
                f"{label}.novelty_assessment.closest_priors[{index}].potentially_decisive must be boolean"
            )
        status = prior["verification_status"]
        evidence_id = prior.get("evidence_id")
        if status == "decision_grade":
            if not isinstance(evidence_id, str) or not evidence_id.strip():
                raise ValidationError(
                    f"{label}.novelty_assessment.closest_priors[{index}] decision-grade prior requires evidence_id"
                )
            _validate_anchored_evidence_ids(
                [evidence_id],
                label=f"{label}.novelty_assessment.closest_priors[{index}].evidence_id",
                formal_evidence_paths=formal_evidence_paths,
                artifact_bindings=artifact_bindings,
            )
            if formal_evidence_source_ids.get(evidence_id) != prior["paper_id"]:
                raise ValidationError(
                    f"{label}.novelty_assessment.closest_priors[{index}] paper_id must match "
                    "the source_id of its decision-grade Evidence Card"
                )
        elif status == "unverified_or_unavailable":
            if evidence_id not in (None, ""):
                raise ValidationError(
                    f"{label}.novelty_assessment.closest_priors[{index}] unverified prior must not claim an evidence_id"
                )
            if prior["potentially_decisive"] and candidate["decision"] == "NOVEL":
                raise ValidationError(
                    f"{label} cannot return NOVEL while a potentially decisive closest/concurrent prior is unverified"
                )
        else:
            raise ValidationError(
                f"{label}.novelty_assessment.closest_priors[{index}].verification_status is invalid"
            )
def _validate_return_guidance(
    summary: dict[str, Any], *, label: str, required: bool
) -> dict[str, Any] | None:
    guidance = summary.get("return_guidance")
    if guidance is None and not required:
        return None
    if guidance is None:
        raise ValidationError(f"{label} requires return_guidance for its evidence-return decision")
    guidance = _require_mapping(guidance, f"{label}.return_guidance")
    _require_fields(guidance, ("missing_evidence", "decision_target", "required_check"), f"{label}.return_guidance")
    if not isinstance(guidance["decision_target"], str) or not guidance["decision_target"].strip():
        raise ValidationError(f"{label}.return_guidance.decision_target must be a non-empty string")
    _require_string_list(guidance["missing_evidence"], f"{label}.return_guidance.missing_evidence", non_empty=True)
    _require_string_list(guidance["required_check"], f"{label}.return_guidance.required_check", non_empty=True)
    return guidance


def _markdown_field(text: str, label: str, artifact: str) -> str:
    matches = re.findall(
        rf"(?mi)^\s*-\s*\*\*{re.escape(label)}\*\*:\s*(.+?)\s*$", text
    )
    if len(matches) != 1:
        raise ValidationError(f"{artifact} must contain exactly one {label!r} field")
    value = matches[0].strip().strip("`")
    if not value:
        raise ValidationError(f"{artifact} {label!r} must be non-empty")
    return value


def root_cause_capsule_evidence_ids(capsule_text: str) -> set[str]:
    """Read the formal evidence identifiers frozen in a problem Capsule."""

    raw = _markdown_field(
        capsule_text,
        "Included evidence IDs",
        "problem evidence capsule",
    )
    identifiers = [item.strip().strip("`") for item in raw.split(",")]
    if (
        not identifiers
        or any(not identifier for identifier in identifiers)
        or len(identifiers) != len(set(identifiers))
    ):
        raise ValidationError(
            "problem evidence capsule Included evidence IDs must be a unique comma-separated list"
        )
    return set(identifiers)


def root_cause_problem_handoff(
    contract_text: str, capsule_text: str
) -> tuple[str, set[str]]:
    """Read the problem identity and frozen evidence set used for diagnosis."""

    contract_problem_id = _markdown_field(contract_text, "Problem ID", "problem contract")
    capsule_problem_id = _markdown_field(capsule_text, "Problem ID", "problem evidence capsule")
    if contract_problem_id != capsule_problem_id:
        raise ValidationError(
            "problem contract and problem evidence capsule identify different problems"
        )
    return contract_problem_id, root_cause_capsule_evidence_ids(capsule_text)


def validate_root_cause_diagnostic_pilots(provenance: dict[str, Any]) -> list[dict[str, str]]:
    """Validate only new, root-cause-stage diagnostic-pilot evidence.

    Existing experiments, datasets, and real-world observations must already be
    registered and frozen in the accepted problem Capsule. A pilot is the one
    1a exception: it may be collected after problem acceptance when necessary
    to characterize the phenomenon for diagnosis.
    """

    raw_artifacts = provenance.get("new_diagnostic_pilot_artifacts", [])
    if not isinstance(raw_artifacts, list):
        raise ValidationError("analysis_provenance.new_diagnostic_pilot_artifacts must be a list")
    artifacts: list[dict[str, str]] = []
    ids: set[str] = set()
    for index, raw in enumerate(raw_artifacts, 1):
        artifact = _require_mapping(raw, f"root-cause diagnostic pilot {index}")
        _require_fields(
            artifact,
            ("artifact_id", "path", "sha256", "evidence_source_type"),
            f"root-cause diagnostic pilot {index}",
        )
        artifact_id = artifact["artifact_id"]
        path = artifact["path"]
        source_type = artifact["evidence_source_type"]
        if not isinstance(artifact_id, str) or not artifact_id.strip() or artifact_id in ids:
            raise ValidationError("root-cause diagnostic pilot IDs must be non-empty and unique")
        if not isinstance(path, str) or not path.strip():
            raise ValidationError(f"root-cause diagnostic pilot {index}.path must be a non-empty string")
        if source_type != "diagnostic_pilot":
            raise ValidationError(
                f"root-cause diagnostic pilot {index}.evidence_source_type must be diagnostic_pilot"
            )
        artifacts.append(
            {
                "artifact_id": artifact_id,
                "path": path,
                "sha256": _require_sha256(artifact["sha256"], f"root-cause diagnostic pilot {index}.sha256"),
                "evidence_source_type": source_type,
            }
        )
        ids.add(artifact_id)
    return artifacts


def validate_problem_capsule_nonliterature_artifacts(capsule_text: str) -> list[dict[str, str]]:
    """Read optional pre-existing non-literature evidence from a Capsule.

    The Capsule is prepared before problem acceptance, so this is the one
    available registration surface for existing experiment, dataset, and
    real-world evidence. Empty Capsules remain valid.
    """

    blocks = re.findall(
        r"(?ms)^## Registered Non-Literature Artifacts\s*\n\s*```json\s*\n(.*?)\n```",
        capsule_text,
    )
    if not blocks:
        return []
    if len(blocks) != 1:
        raise ValidationError(
            "problem evidence capsule may contain only one Registered Non-Literature Artifacts JSON block"
        )
    try:
        raw_artifacts = json.loads(blocks[0])
    except json.JSONDecodeError as exc:
        raise ValidationError(
            "problem evidence capsule Registered Non-Literature Artifacts block must be JSON"
        ) from exc
    if not isinstance(raw_artifacts, list):
        raise ValidationError(
            "problem evidence capsule Registered Non-Literature Artifacts must be a list"
        )
    artifacts: list[dict[str, str]] = []
    ids: set[str] = set()
    for index, raw in enumerate(raw_artifacts, 1):
        artifact = _require_mapping(raw, f"problem capsule non-literature artifact {index}")
        _require_fields(
            artifact,
            ("artifact_id", "path", "sha256", "evidence_source_type"),
            f"problem capsule non-literature artifact {index}",
        )
        artifact_id = artifact["artifact_id"]
        path = artifact["path"]
        source_type = artifact["evidence_source_type"]
        if not isinstance(artifact_id, str) or not artifact_id.strip() or artifact_id in ids:
            raise ValidationError(
                "problem capsule non-literature artifact IDs must be non-empty and unique"
            )
        if not isinstance(path, str) or not path.strip():
            raise ValidationError(
                f"problem capsule non-literature artifact {index}.path must be a non-empty string"
            )
        if source_type not in {"existing_experiment", "dataset", "real_world"}:
            raise ValidationError(
                f"problem capsule non-literature artifact {index}.evidence_source_type is invalid"
            )
        artifacts.append(
            {
                "artifact_id": artifact_id,
                "path": path,
                "sha256": _require_sha256(
                    artifact["sha256"], f"problem capsule non-literature artifact {index}.sha256"
                ),
                "evidence_source_type": source_type,
            }
        )
        ids.add(artifact_id)
    return artifacts


def validate_problem_acceptance_handoff(
    contract_text: str,
    capsule_text: str,
    *,
    selected_id: str,
    candidate_path: str,
    candidate_sha256: str,
    quality_path: str,
    quality_sha256: str,
    quality_verdict_id: str,
    novelty_path: str,
    novelty_sha256: str,
    novelty_verdict_id: str,
    novelty_candidate_decision: str,
    contract_path: str,
    contract_sha256: str,
    allowed_capsule_evidence_ids: set[str],
) -> None:
    """Close the selected candidate through both verdicts and formal handoffs."""

    contract = "problem contract"
    capsule = "problem evidence capsule"
    expected_contract = {
        "Problem ID": selected_id,
        "Candidate registry path": candidate_path,
        "Candidate registry SHA-256": candidate_sha256,
        "Quality verdict path": quality_path,
        "Quality verdict SHA-256": quality_sha256,
        "Quality verdict ID": quality_verdict_id,
        "Novelty verdict path": novelty_path,
        "Novelty verdict SHA-256": novelty_sha256,
        "Novelty verdict ID": novelty_verdict_id,
        "Problem novelty verdict": novelty_candidate_decision,
    }
    for label, expected in expected_contract.items():
        if _markdown_field(contract_text, label, contract) != expected:
            raise ValidationError(f"{contract} {label!r} does not match the accepted problem chain")
    required_contract_fields = (
        "Problem ID / source class",
        "Research question",
        "Observed phenomenon",
        "Evidence-backed phenomenon",
        "Evidence status",
        "Decisive evidence tier",
        "Measurement validity",
        "Artifact/confound alternatives",
        "Independent support",
        "Prevalence/effect scale",
        "Scope and boundary",
        "Why it matters",
        "Value if yes / value if no",
        "Decision owner / threshold",
        "Plausible explanations",
        "Decisive probe or falsifier",
        "Feasible discriminating probe",
        "Closest prior / residual delta",
        "Uncertainties",
        "Problem quality verdict",
        "Acceptance status",
        "Verdict ID / acceptance authority",
        "Evidence snapshot / novelty cutoff date",
        "Source",
    )
    for label in required_contract_fields:
        _markdown_field(contract_text, label, contract)
    if _markdown_field(capsule_text, "Problem ID", capsule) != selected_id:
        raise ValidationError(f"{capsule} Problem ID does not match the selected problem")
    if _markdown_field(capsule_text, "Linked Contract path", capsule) != contract_path:
        raise ValidationError(f"{capsule} Linked Contract path does not match the formal contract")
    if _markdown_field(capsule_text, "Linked Contract SHA-256", capsule) != contract_sha256:
        raise ValidationError(f"{capsule} Linked Contract SHA-256 does not match the formal contract")
    for label in (
        "Excluded uncertainty / boundary IDs",
        "Snapshot source",
        "Known gaps and contested evidence",
    ):
        _markdown_field(capsule_text, label, capsule)
    included_evidence_ids = root_cause_capsule_evidence_ids(capsule_text)
    unresolved = sorted(included_evidence_ids - allowed_capsule_evidence_ids)
    if unresolved:
        raise ValidationError(
            f"{capsule} Included evidence IDs do not resolve to accepted or atomically registered evidence: {unresolved}"
        )


def validate_markdown_review_verdict_artifact(
    text: str,
    *,
    label: str,
    request_id: str,
    artifact_bindings: dict[str, str],
    decisions: set[str],
    return_targets: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Read the single JSON metadata block embedded in a human-readable verdict."""

    blocks = re.findall(r"```json\s*\n(\{.*?\})\s*\n```", text, flags=re.DOTALL)
    if len(blocks) != 1:
        raise ValidationError(f"{label} must contain exactly one JSON review metadata block")
    try:
        payload = json.loads(blocks[0])
    except json.JSONDecodeError as exc:
        raise ValidationError(f"{label} review metadata must be JSON") from exc
    verdict = _validate_review_binding(
        payload,
        label=label,
        request_id=request_id,
        reviewer=None,
        verdict_id=None,
        decision=None,
        artifact_bindings=artifact_bindings,
    )
    if verdict["decision"] not in decisions:
        raise ValidationError(f"{label} decision is not allowed by the Gate")
    if return_targets and verdict["decision"] in return_targets:
        guidance = _validate_return_guidance(verdict, label=label, required=True)
        if guidance["decision_target"] != return_targets[verdict["decision"]]:
            raise ValidationError(
                f"{label}.return_guidance.decision_target does not match the canonical return target"
            )
    return verdict


def validate_source_admission_policy(payload: Any) -> dict[str, Any]:
    policy = _require_mapping(payload, "source admission policy")
    if "research_effort_budget" in policy:
        raise ValidationError(
            "research_effort_budget belongs only in the canonical workflow"
        )
    _require_fields(
        policy,
        ("schema_version", "source_tracks"),
        "source admission policy",
    )
    venues = policy.get("approved_elite_venues")
    fields = policy.get("fields")
    if not isinstance(venues, (list, dict)) and not isinstance(fields, list):
        raise ValidationError(
            "source admission policy requires approved_elite_venues or fields"
        )
    rule = policy.get("high_citation_rule")
    fixed = policy.get("non_elite_citation_threshold_exclusive")
    if rule is None and not isinstance(fixed, (int, float)):
        raise ValidationError(
            "source admission policy requires an age-calibrated or fixed citation threshold"
        )
    if rule is not None:
        rule = _require_mapping(rule, "high_citation_rule")
        thresholds = rule.get("thresholds")
        if not isinstance(thresholds, list) or not thresholds:
            raise ValidationError("high_citation_rule.thresholds must be a non-empty list")
        year_ranges: list[tuple[int, int]] = []
        for index, threshold in enumerate(thresholds, 1):
            item = _require_mapping(threshold, f"citation threshold {index}")
            _require_fields(
                item,
                ("publication_year_max", "citation_count_strictly_greater_than"),
                f"citation threshold {index}",
            )
            minimum = item.get("publication_year_min", -10**9)
            maximum = item["publication_year_max"]
            citation_threshold = item["citation_count_strictly_greater_than"]
            if not isinstance(minimum, int) or not isinstance(maximum, int) or minimum > maximum:
                raise ValidationError(
                    f"citation threshold {index} must have an integer publication-year range"
                )
            if not isinstance(citation_threshold, (int, float)) or citation_threshold < 0:
                raise ValidationError(
                    f"citation threshold {index} must have a non-negative numeric citation threshold"
                )
            year_ranges.append((minimum, maximum))
        for index, (minimum, maximum) in enumerate(year_ranges, 1):
            for other_index, (other_minimum, other_maximum) in enumerate(year_ranges[: index - 1], 1):
                if minimum <= other_maximum and other_minimum <= maximum:
                    raise ValidationError(
                        f"citation threshold {index} overlaps citation threshold {other_index}"
                    )
    if not isinstance(policy["source_tracks"], dict):
        raise ValidationError("source_tracks must be an object")
    return policy


def _require_mapping(payload: Any, label: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValidationError(f"{label} must be a JSON object")
    return payload


def _require_fields(payload: dict[str, Any], fields: tuple[str, ...], label: str) -> None:
    missing = [field for field in fields if field not in payload or payload[field] in (None, "")]
    if missing:
        raise ValidationError(f"{label} is missing required fields: {missing}")


def _require_list(payload: dict[str, Any], field: str, label: str, *, non_empty: bool = False) -> list[Any]:
    value = payload.get(field)
    if not isinstance(value, list) or (non_empty and not value):
        qualifier = "non-empty " if non_empty else ""
        raise ValidationError(f"{label}.{field} must be a {qualifier}list")
    return value


def _require_string_list(value: Any, label: str, *, non_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or (non_empty and not value):
        qualifier = "non-empty " if non_empty else ""
        raise ValidationError(f"{label} must be a {qualifier}list")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValidationError(f"{label} must contain only non-empty strings")
    return value


def _require_sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise ValidationError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _unique_ids(items: list[Any], field: str, label: str) -> set[str]:
    identifiers: list[str] = []
    for index, raw in enumerate(items, 1):
        item = _require_mapping(raw, f"{label} item {index}")
        _require_fields(item, (field,), f"{label} item {index}")
        identifier = item[field]
        if not isinstance(identifier, str) or not identifier.strip():
            raise ValidationError(f"{label} item {index}.{field} must be a non-empty string")
        identifiers.append(identifier)
    if len(identifiers) != len(set(identifiers)):
        raise ValidationError(f"{label}.{field} values must be unique")
    return set(identifiers)


def _method_identifier_list(value: Any, label: str, *, non_empty: bool = True) -> list[str]:
    """Normalize stable IDs used to close Principle-first method artifacts to diagnosis."""

    values = _require_string_list(value, label, non_empty=non_empty)
    if len(values) != len(set(values)):
        raise ValidationError(f"{label} must contain unique identifiers")
    return values


def _required_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{label} must be a non-empty string")
    return value.strip()


def _unique_string_values(value: Any, label: str, *, non_empty: bool = True) -> list[str]:
    values = _require_string_list(value, label, non_empty=non_empty)
    if len(values) != len(set(values)):
        raise ValidationError(f"{label} must contain unique identifiers")
    return values


def validate_method_design_packet(
    payload: Any,
    *,
    contract: dict[str, Any],
    problem_version: dict[str, Any],
    root_cause_analysis_id: str,
    root_cause_analysis_sha256: str,
    primary_causal_chain_ids: set[str],
    rival_rca_ids: set[str] | None = None,
    current_evidence_ids: set[str] | None = None,
    required_history_refs: set[str] | None = None,
    required_return_ref: str | None = None,
    required_combine_sources: set[tuple[str, str]] | None = None,
    query_plan_provenance: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Validate the machine-resolvable Candidate Principle packet without judging quality."""

    packet = _require_mapping(payload, "method design packet")
    _require_fields(packet, tuple(contract["required_fields"]), "method design packet")
    forbidden = set(contract.get("forbidden_fields") or []) & set(packet)
    if forbidden:
        raise ValidationError(
            "method design packet must not contain test design fields: "
            + ", ".join(sorted(forbidden))
        )
    if packet["schema_version"] != contract.get("schema_version", 1):
        raise ValidationError("method design packet schema_version is invalid")
    design_cycle_id = _required_text(
        packet["design_cycle_id"], "method design packet.design_cycle_id"
    )

    problem = _require_mapping(packet["problem_binding"], "method design packet.problem_binding")
    expected_problem = {
        "problem_id": problem_version["problem_id"],
        "problem_version": problem_version["version"],
        "problem_contract_sha256": problem_version["contract_sha256"],
        "evidence_capsule_sha256": problem_version["evidence_capsule_sha256"],
    }
    if problem != expected_problem:
        raise ValidationError("method design packet problem_binding does not match the active Problem")

    root_cause = _require_mapping(
        packet["root_cause_binding"], "method design packet.root_cause_binding"
    )
    _require_fields(
        root_cause,
        ("analysis_id", "analysis_sha256", "causal_chain_ids"),
        "method design packet.root_cause_binding",
    )
    if (
        root_cause["analysis_id"] != root_cause_analysis_id
        or root_cause["analysis_sha256"] != root_cause_analysis_sha256
    ):
        raise ValidationError("method design packet root_cause_binding is stale")
    bound_chains = set(
        _unique_string_values(
            root_cause["causal_chain_ids"],
            "method design packet.root_cause_binding.causal_chain_ids",
        )
    )
    if bound_chains != primary_causal_chain_ids:
        raise ValidationError("method design packet must bind every accepted primary causal chain")

    dispositions = _require_list(
        packet, "primary_chain_dispositions", "method design packet", non_empty=True
    )
    disposition_chain_ids = _unique_ids(
        dispositions,
        "causal_chain_id",
        "method design packet.primary_chain_dispositions",
    )
    if disposition_chain_ids != primary_causal_chain_ids:
        raise ValidationError("every accepted primary causal chain must have exactly one disposition")
    disposition_by_chain: dict[str, dict[str, Any]] = {}
    disposition_enum = set(contract["primary_chain_disposition_enum"])
    for index, raw in enumerate(dispositions, 1):
        item = _require_mapping(raw, f"primary chain disposition {index}")
        _require_fields(
            item,
            tuple(contract["primary_chain_disposition_fields"]),
            f"primary chain disposition {index}",
        )
        if item["disposition"] not in disposition_enum:
            raise ValidationError(f"primary chain disposition {index}.disposition is invalid")
        mechanism_refs = _unique_string_values(
            item["mechanism_change_ids"],
            f"primary chain disposition {index}.mechanism_change_ids",
            non_empty=item["disposition"] == "RMC",
        )
        evidence_refs = _unique_string_values(
            item["evidence_refs"],
            f"primary chain disposition {index}.evidence_refs",
            non_empty=item["disposition"] != "RMC",
        )
        if item["disposition"] == "RMC" and evidence_refs:
            # RMC support is judged through the bound RCA and rationale; this
            # field is reserved for claim-boundary dispositions.
            raise ValidationError("RMC primary-chain dispositions must not masquerade as claim-boundary evidence")
        if item["disposition"] != "RMC" and mechanism_refs:
            raise ValidationError("claim-boundary dispositions must not also consume the chain as an RMC")
        _required_text(item["rationale"], f"primary chain disposition {index}.rationale")
        if current_evidence_ids is not None and not set(evidence_refs) <= current_evidence_ids:
            raise ValidationError(
                f"primary chain disposition {index} cites Evidence outside the current formal context"
            )
        disposition_by_chain[item["causal_chain_id"]] = item

    mechanism_changes = _require_list(
        packet, "required_mechanism_changes", "method design packet", non_empty=True
    )
    mechanism_ids = _unique_ids(
        mechanism_changes, "mechanism_change_id", "method design packet.required_mechanism_changes"
    )
    mechanism_by_id: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(mechanism_changes, 1):
        item = _require_mapping(raw, f"required mechanism change {index}")
        _require_fields(
            item,
            tuple(contract["required_mechanism_change_fields"]),
            f"required mechanism change {index}",
        )
        chains = set(_unique_string_values(item["causal_chain_ids"], f"required mechanism change {index}.causal_chain_ids"))
        if not chains <= primary_causal_chain_ids:
            raise ValidationError(f"required mechanism change {index} references an unknown causal chain")
        for field in (
            "failed_relation_state_or_information_structure",
            "required_mechanism_change",
            "change_direction",
            "causal_position",
            "activation_condition",
            "root_cause_resolution_rationale",
        ):
            _required_text(item[field], f"required mechanism change {index}.{field}")
        _unique_string_values(item["capability_ids"], f"required mechanism change {index}.capability_ids")
        _unique_string_values(item["obligation_ids"], f"required mechanism change {index}.obligation_ids")
        mechanism_by_id[item["mechanism_change_id"]] = item

    for chain_id, disposition in disposition_by_chain.items():
        if disposition["disposition"] == "RMC":
            refs = set(disposition["mechanism_change_ids"])
            if not refs <= mechanism_ids or any(
                chain_id not in mechanism_by_id[mechanism_id]["causal_chain_ids"]
                for mechanism_id in refs
            ):
                raise ValidationError(
                    f"primary chain disposition {chain_id} has an unresolved or inconsistent RMC binding"
                )
        elif any(chain_id in item["causal_chain_ids"] for item in mechanism_changes):
            raise ValidationError(
                f"claim-boundary primary chain {chain_id} must not also be consumed by an RMC"
            )

    capabilities = _require_list(packet, "required_capabilities", "method design packet", non_empty=True)
    capability_ids = _unique_ids(capabilities, "capability_id", "method design packet.required_capabilities")
    capability_by_id: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(capabilities, 1):
        item = _require_mapping(raw, f"required capability {index}")
        _require_fields(item, tuple(contract["required_capability_fields"]), f"required capability {index}")
        refs = set(_unique_string_values(item["mechanism_change_ids"], f"required capability {index}.mechanism_change_ids"))
        if not refs <= mechanism_ids:
            raise ValidationError(f"required capability {index} references an unknown mechanism change")
        _required_text(item["required_capability"], f"required capability {index}.required_capability")
        _require_list(item, "acceptance_conditions", f"required capability {index}", non_empty=True)
        capability_by_id[item["capability_id"]] = item

    obligations = _require_list(packet, "design_obligations", "method design packet", non_empty=True)
    obligation_ids = _unique_ids(obligations, "obligation_id", "method design packet.design_obligations")
    obligation_by_id: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(obligations, 1):
        item = _require_mapping(raw, f"design obligation {index}")
        _require_fields(item, tuple(contract["design_obligation_fields"]), f"design obligation {index}")
        if not set(_unique_string_values(item["mechanism_change_ids"], f"design obligation {index}.mechanism_change_ids")) <= mechanism_ids:
            raise ValidationError(f"design obligation {index} references an unknown mechanism change")
        if not set(_unique_string_values(item["capability_ids"], f"design obligation {index}.capability_ids")) <= capability_ids:
            raise ValidationError(f"design obligation {index} references an unknown capability")
        _required_text(item["design_obligation"], f"design obligation {index}.design_obligation")
        _require_list(item, "acceptance_conditions", f"design obligation {index}", non_empty=True)
        obligation_by_id[item["obligation_id"]] = item

    for mechanism_id, item in mechanism_by_id.items():
        if not set(item["capability_ids"]) <= capability_ids or not set(item["obligation_ids"]) <= obligation_ids:
            raise ValidationError(f"required mechanism change {mechanism_id} has an unresolved capability or obligation link")
        if any(
            mechanism_id not in capability_by_id[capability_id]["mechanism_change_ids"]
            for capability_id in item["capability_ids"]
        ):
            raise ValidationError(f"required mechanism change {mechanism_id} has an inconsistent capability link")
        if any(
            mechanism_id not in obligation_by_id[obligation_id]["mechanism_change_ids"]
            for obligation_id in item["obligation_ids"]
        ):
            raise ValidationError(f"required mechanism change {mechanism_id} has an inconsistent obligation link")
    for capability_id, item in capability_by_id.items():
        if any(
            capability_id not in mechanism_by_id[mechanism_id]["capability_ids"]
            for mechanism_id in item["mechanism_change_ids"]
        ):
            raise ValidationError(f"required capability {capability_id} has an inconsistent mechanism-change link")
    for obligation_id, item in obligation_by_id.items():
        if any(
            obligation_id not in mechanism_by_id[mechanism_id]["obligation_ids"]
            for mechanism_id in item["mechanism_change_ids"]
        ):
            raise ValidationError(f"design obligation {obligation_id} has an inconsistent mechanism-change link")
        if any(
            not set(capability_by_id[capability_id]["mechanism_change_ids"])
            & set(item["mechanism_change_ids"])
            for capability_id in item["capability_ids"]
        ):
            raise ValidationError(f"design obligation {obligation_id} has an inconsistent capability link")

    search = _require_mapping(packet["principle_search_record"], "method design packet.principle_search_record")
    _require_fields(search, tuple(contract["principle_search_record_fields"]), "method design packet.principle_search_record")
    signatures = _require_list(
        search, "target_mechanism_signatures", "method design packet.principle_search_record", non_empty=True
    )
    signature_ids = _unique_ids(
        signatures, "target_mechanism_signature_id", "target mechanism signatures"
    )
    signature_by_id: dict[str, dict[str, Any]] = {}
    signature_rmc_ids: set[str] = set()
    for index, raw in enumerate(signatures, 1):
        item = _require_mapping(raw, f"target mechanism signature {index}")
        _require_fields(
            item, tuple(contract["target_mechanism_signature_fields"]),
            f"target mechanism signature {index}",
        )
        if item["rmc_id"] not in mechanism_ids:
            raise ValidationError(f"target mechanism signature {index} references an unknown RMC")
        if item["rmc_id"] in signature_rmc_ids:
            raise ValidationError("each RMC must have exactly one current Target Mechanism Signature")
        signature_rmc_ids.add(item["rmc_id"])
        for field in contract["target_mechanism_signature_fields"]:
            _required_text(item[field], f"target mechanism signature {index}.{field}")
        rmc = mechanism_by_id[item["rmc_id"]]
        for field in ("change_direction", "causal_position", "activation_condition"):
            if item[field] != rmc[field]:
                raise ValidationError(
                    f"target mechanism signature {index}.{field} is inconsistent with its RMC"
                )
        signature_by_id[item["target_mechanism_signature_id"]] = item
    if signature_rmc_ids != mechanism_ids:
        raise ValidationError("every RMC must have a Target Mechanism Signature before transfer search")

    first_principles = _require_list(
        search, "first_principles", "method design packet.principle_search_record", non_empty=True
    )
    first_origin_ids = _unique_ids(first_principles, "origin_record_id", "first-principles derivations")
    first_rmc_ids: set[str] = set()
    for index, raw in enumerate(first_principles, 1):
        item = _require_mapping(raw, f"first-principles derivation {index}")
        _require_fields(
            item, tuple(contract["first_principles_derivation_fields"]),
            f"first-principles derivation {index}",
        )
        if item["rmc_id"] not in mechanism_ids:
            raise ValidationError(f"first-principles derivation {index} references an unknown RMC")
        first_rmc_ids.add(item["rmc_id"])
        for field in ("premises", "derivation_steps", "formal_or_evidence_basis", "assumptions", "boundaries"):
            if not isinstance(item[field], (str, list, dict)) or item[field] in ("", [], {}):
                raise ValidationError(f"first-principles derivation {index}.{field} must be non-empty")
        for field in ("derived_intervention", "rmc_resolution_rationale"):
            _required_text(item[field], f"first-principles derivation {index}.{field}")
    if first_rmc_ids != mechanism_ids:
        raise ValidationError("FIRST_PRINCIPLES requires a reviewable derivation record for every RMC")

    transformations = _require_list(
        search, "representation_transformations", "method design packet.principle_search_record", non_empty=True
    )
    representation_origin_ids = _unique_ids(
        transformations, "origin_record_id", "representation transformations"
    )
    representation_rmc_ids: set[str] = set()
    for index, raw in enumerate(transformations, 1):
        item = _require_mapping(raw, f"representation transformation {index}")
        _require_fields(
            item, tuple(contract["representation_transformation_fields"]),
            f"representation transformation {index}",
        )
        if item["rmc_id"] not in mechanism_ids:
            raise ValidationError(f"representation transformation {index} references an unknown RMC")
        representation_rmc_ids.add(item["rmc_id"])
        for field in (
            "old_representation", "new_representation", "failure_mechanism_resolution",
            "information_preserved", "formal_or_evidence_basis", "assumptions", "boundaries",
        ):
            if not isinstance(item[field], (str, list, dict)) or item[field] in ("", [], {}):
                raise ValidationError(f"representation transformation {index}.{field} must be non-empty")
        if not isinstance(item["information_lost"], (str, list, dict)):
            raise ValidationError(f"representation transformation {index}.information_lost is invalid")
    if representation_rmc_ids != mechanism_ids:
        raise ValidationError(
            "REPRESENTATION_TRANSFORMATION requires a reviewable derivation record for every RMC"
        )

    hypotheses = _require_list(
        search, "domain_hypotheses", "method design packet.principle_search_record", non_empty=True
    )
    hypothesis_ids = _unique_ids(hypotheses, "domain_hypothesis_id", "domain hypotheses")
    hypothesis_by_id: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(hypotheses, 1):
        item = _require_mapping(raw, f"domain hypothesis {index}")
        _require_fields(item, tuple(contract["domain_hypothesis_fields"]), f"domain hypothesis {index}")
        if item["rmc_id"] not in mechanism_ids:
            raise ValidationError(f"domain hypothesis {index} references an unknown RMC")
        signature = signature_by_id.get(item["target_mechanism_signature_ref"])
        if not signature or signature["rmc_id"] != item["rmc_id"]:
            raise ValidationError(f"domain hypothesis {index} has a stale Target Mechanism Signature binding")
        channel = item["source_channel"]
        if channel not in set(contract["domain_hypothesis_source_enum"]):
            raise ValidationError(f"domain hypothesis {index}.source_channel is invalid")
        for field in (
            "domain_or_research_community_or_paradigm", "structural_rationale",
            "expected_problem_structure", "expected_intervention_family",
            "introduced_query_plan_sha256",
        ):
            _required_text(item[field], f"domain hypothesis {index}.{field}")
        if query_plan_provenance is not None:
            plan_record = query_plan_provenance.get(item["introduced_query_plan_sha256"])
            if not isinstance(plan_record, dict) or item["domain_hypothesis_id"] not in set(
                plan_record.get("domain_hypothesis_ids") or []
            ):
                raise ValidationError(
                    f"domain hypothesis {index} was not registered in its claimed immutable Query Plan"
                )
        provenance = _unique_string_values(
            item["provenance_refs"], f"domain hypothesis {index}.provenance_refs",
            non_empty=channel == "ACADEMIC_BRIDGE",
        )
        if channel == "PRACTITIONER_SIGNAL" and not provenance:
            raise ValidationError("PRACTITIONER_SIGNAL hypotheses require traceable discovery provenance")
        if item["disposition"] not in set(contract["domain_hypothesis_disposition_enum"]):
            raise ValidationError(f"domain hypothesis {index}.disposition is invalid")
        if item["disposition"] != "CLOSED":
            raise ValidationError("Method Design cannot close while a domain hypothesis remains EXPLORE")
        _required_text(item["closure_rationale"], f"domain hypothesis {index}.closure_rationale")
        _unique_string_values(
            item["closure_provenance_refs"],
            f"domain hypothesis {index}.closure_provenance_refs",
        )
        hypothesis_by_id[item["domain_hypothesis_id"]] = item

    discovery_executions = _require_list(
        search,
        "discovery_executions",
        "method design packet.principle_search_record",
        non_empty=True,
    )
    _unique_ids(discovery_executions, "discovery_execution_id", "domain discovery executions")
    discovery_channels_by_rmc = {rmc_id: set() for rmc_id in mechanism_ids}
    discovery_outcomes = set(contract["discovery_execution_outcome_enum"])
    for index, raw in enumerate(discovery_executions, 1):
        item = _require_mapping(raw, f"domain discovery execution {index}")
        _require_fields(
            item,
            tuple(
                field
                for field in contract["discovery_execution_fields"]
                if field != "query_plan_sha256"
            ),
            f"domain discovery execution {index}",
        )
        if "query_plan_sha256" not in item:
            raise ValidationError(
                f"domain discovery execution {index} is missing query_plan_sha256"
            )
        rmc_id = item["rmc_id"]
        signature = signature_by_id.get(item["target_mechanism_signature_ref"])
        if rmc_id not in mechanism_ids or signature is None or signature["rmc_id"] != rmc_id:
            raise ValidationError(
                f"domain discovery execution {index} has a stale RMC/signature binding"
            )
        channel = item["source_channel"]
        if channel not in {"MODEL_PRIOR", "ACADEMIC_BRIDGE"}:
            raise ValidationError(
                f"domain discovery execution {index}.source_channel must be MODEL_PRIOR or ACADEMIC_BRIDGE"
            )
        discovery_channels_by_rmc[rmc_id].add(channel)
        outcome = item["outcome"]
        if outcome not in discovery_outcomes:
            raise ValidationError(f"domain discovery execution {index}.outcome is invalid")
        registered_ids = set(
            _unique_string_values(
                item["registered_domain_hypothesis_ids"],
                f"domain discovery execution {index}.registered_domain_hypothesis_ids",
                non_empty=outcome == "HYPOTHESES_REGISTERED",
            )
        )
        if outcome == "NO_ADDITIONAL_DOMAIN_HYPOTHESIS" and registered_ids:
            raise ValidationError(
                "NO_ADDITIONAL_DOMAIN_HYPOTHESIS must not fabricate a Domain Hypothesis"
            )
        for hypothesis_id in registered_ids:
            hypothesis = hypothesis_by_id.get(hypothesis_id)
            if (
                hypothesis is None
                or hypothesis["rmc_id"] != rmc_id
                or hypothesis["target_mechanism_signature_ref"]
                != item["target_mechanism_signature_ref"]
                or hypothesis["source_channel"] != channel
            ):
                raise ValidationError(
                    f"domain discovery execution {index} has an invalid registered hypothesis binding"
                )
        _required_text(
            item["closure_rationale"],
            f"domain discovery execution {index}.closure_rationale",
        )
        plan_item_ids = _unique_string_values(
            item["plan_item_ids"],
            f"domain discovery execution {index}.plan_item_ids",
            non_empty=channel == "ACADEMIC_BRIDGE",
        )
        evidence_refs = set(
            _unique_string_values(
                item["evidence_refs"],
                f"domain discovery execution {index}.evidence_refs",
                non_empty=channel == "ACADEMIC_BRIDGE",
            )
        )
        if current_evidence_ids is not None and not evidence_refs <= current_evidence_ids:
            raise ValidationError(
                f"domain discovery execution {index} cites Evidence outside the current formal context"
            )
        if channel == "MODEL_PRIOR":
            if outcome != "HYPOTHESES_REGISTERED" or not registered_ids:
                raise ValidationError("MODEL_PRIOR must register at least one Search Hypothesis")
            if item["query_plan_sha256"] not in (None, "") or plan_item_ids or evidence_refs:
                raise ValidationError(
                    "MODEL_PRIOR is hypothesis-only and must not masquerade as scholarly provenance"
                )
        else:
            plan_sha256 = _required_text(
                item["query_plan_sha256"],
                f"domain discovery execution {index}.query_plan_sha256",
            )
            if query_plan_provenance is not None:
                plan_record = query_plan_provenance.get(plan_sha256)
                steps = (
                    plan_record.get("search_step_by_plan_item")
                    if isinstance(plan_record, dict)
                    else None
                )
                if not isinstance(steps, dict) or any(
                    steps.get(plan_item_id) != "DOMAIN_DISCOVERY"
                    for plan_item_id in plan_item_ids
                ):
                    raise ValidationError(
                        f"domain discovery execution {index} lacks accepted DOMAIN_DISCOVERY Query Plan provenance"
                    )
                evidence_by_item = plan_record.get("evidence_ids_by_plan_item") or {}
                provenance_evidence = {
                    evidence_id
                    for plan_item_id in plan_item_ids
                    for evidence_id in evidence_by_item.get(plan_item_id, [])
                }
                if not evidence_refs <= provenance_evidence:
                    raise ValidationError(
                        f"domain discovery execution {index} lacks scholarly read provenance"
                    )
    for rmc_id, channels in discovery_channels_by_rmc.items():
        if not {"MODEL_PRIOR", "ACADEMIC_BRIDGE"} <= channels:
            raise ValidationError(
                f"RMC {rmc_id} requires both MODEL_PRIOR and ACADEMIC_BRIDGE Domain Discovery execution"
            )

    terminology_maps = _require_list(
        search, "terminology_maps", "method design packet.principle_search_record"
    )
    terminology_map_ids = _unique_ids(terminology_maps, "terminology_map_id", "terminology maps")
    terminology_by_id: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(terminology_maps, 1):
        item = _require_mapping(raw, f"terminology map {index}")
        _require_fields(item, tuple(contract["terminology_map_fields"]), f"terminology map {index}")
        if item["domain_hypothesis_id"] not in hypothesis_ids:
            raise ValidationError(f"terminology map {index} references an unknown Domain Hypothesis")
        for field in (
            "canonical_problem_terms", "canonical_variable_state_relation_terms",
            "canonical_intervention_terms", "canonical_method_families",
            "search_read_provenance",
        ):
            _unique_string_values(item[field], f"terminology map {index}.{field}")
        evidence_refs = set(_unique_string_values(item["evidence_refs"], f"terminology map {index}.evidence_refs"))
        if current_evidence_ids is not None and not evidence_refs <= current_evidence_ids:
            raise ValidationError(f"terminology map {index} cites Evidence outside the current formal context")
        _required_text(item["query_plan_sha256"], f"terminology map {index}.query_plan_sha256")
        if query_plan_provenance is not None:
            plan_record = query_plan_provenance.get(item["query_plan_sha256"])
            if not isinstance(plan_record, dict) or "TERMINOLOGY_GROUNDING" not in set(
                (plan_record.get("search_step_by_plan_item") or {}).values()
            ):
                raise ValidationError(
                    f"terminology map {index} lacks its claimed evidence-grounding Query Plan provenance"
                )
        terminology_by_id[item["terminology_map_id"]] = item

    same_field = _require_list(
        search, "same_field_mechanisms", "method design packet.principle_search_record"
    )
    cross_domain = _require_list(
        search, "cross_domain_structural_isomorphisms", "method design packet.principle_search_record"
    )
    source_records = [("same-field", item) for item in same_field] + [
        ("cross-domain", item) for item in cross_domain
    ]
    source_ids: set[str] = set()
    alignment_by_id: dict[str, dict[str, Any]] = {}
    source_by_id: dict[str, dict[str, Any]] = {}
    source_kind_by_id: dict[str, str] = {}
    for index, (kind, raw) in enumerate(source_records, 1):
        source = _require_mapping(raw, f"{kind} Source Mechanism {index}")
        _require_fields(source, tuple(contract["source_mechanism_fields"]), f"{kind} Source Mechanism {index}")
        source_id = _required_text(source["source_mechanism_id"], f"{kind} Source Mechanism {index}.source_mechanism_id")
        if source_id in source_ids:
            raise ValidationError("source_mechanism_id must be unique across same-field and cross-domain Sources")
        source_ids.add(source_id)
        source_by_id[source_id] = source
        source_kind_by_id[source_id] = kind
        served_rmc_ids = set(_unique_string_values(source["served_rmc_ids"], f"{kind} Source Mechanism {index}.served_rmc_ids"))
        served_capability_ids = set(_unique_string_values(source["served_capability_ids"], f"{kind} Source Mechanism {index}.served_capability_ids"))
        served_obligation_ids = set(_unique_string_values(source["served_obligation_ids"], f"{kind} Source Mechanism {index}.served_obligation_ids"))
        if not served_rmc_ids <= mechanism_ids or not served_capability_ids <= capability_ids or not served_obligation_ids <= obligation_ids:
            raise ValidationError(f"{kind} Source Mechanism {index} has an unresolved served binding")
        for field in (
            "source_problem", "source_intervention", "changed_variable_relation_or_structure",
            "causal_or_computational_effect", "outcome", "mechanism_origin_or_stop_rationale",
        ):
            _required_text(source[field], f"{kind} Source Mechanism {index}.{field}")
        if "source_root_cause" in source and source["source_root_cause"] is not None:
            _required_text(source["source_root_cause"], f"{kind} Source Mechanism {index}.source_root_cause")
        for field in ("assumptions", "activation_conditions", "boundaries"):
            if not isinstance(source[field], (str, list, dict)) or source[field] in ("", [], {}):
                raise ValidationError(f"{kind} Source Mechanism {index}.{field} must be non-empty")
        evidence_refs = set(_unique_string_values(source["evidence_refs"], f"{kind} Source Mechanism {index}.evidence_refs"))
        if current_evidence_ids is not None and not evidence_refs <= current_evidence_ids:
            raise ValidationError(f"{kind} Source Mechanism {index} cites Evidence outside the current formal context")
        for field in ("discovery_provenance", "search_provenance"):
            provenance = _require_mapping(source[field], f"{kind} Source Mechanism {index}.{field}")
            _require_fields(provenance, ("query_plan_sha256", "plan_item_id"), f"{kind} Source Mechanism {index}.{field}")
            _required_text(provenance["query_plan_sha256"], f"{kind} Source Mechanism {index}.{field}.query_plan_sha256")
            _required_text(provenance["plan_item_id"], f"{kind} Source Mechanism {index}.{field}.plan_item_id")
            if query_plan_provenance is not None:
                plan_record = query_plan_provenance.get(provenance["query_plan_sha256"])
                step_by_item = plan_record.get("search_step_by_plan_item") if isinstance(plan_record, dict) else None
                if not isinstance(step_by_item, dict) or provenance["plan_item_id"] not in step_by_item:
                    raise ValidationError(
                        f"{kind} Source Mechanism {index}.{field} does not resolve to an accepted Query Plan item"
                    )
        if kind == "cross-domain":
            discovery = source["discovery_provenance"]
            _require_fields(
                discovery,
                ("target_mechanism_signature_ref", "domain_hypothesis_id", "terminology_map_id"),
                f"cross-domain Source Mechanism {index}.discovery_provenance",
            )
            hypothesis = hypothesis_by_id.get(discovery["domain_hypothesis_id"])
            terminology = terminology_by_id.get(discovery["terminology_map_id"])
            if (
                discovery["target_mechanism_signature_ref"] not in signature_ids
                or hypothesis is None
                or terminology is None
                or terminology["domain_hypothesis_id"] != hypothesis["domain_hypothesis_id"]
                or hypothesis["target_mechanism_signature_ref"] != discovery["target_mechanism_signature_ref"]
            ):
                raise ValidationError(f"cross-domain Source Mechanism {index} has a stale discovery/terminology binding")
            if query_plan_provenance is not None:
                discovery_plan = query_plan_provenance[source["discovery_provenance"]["query_plan_sha256"]]
                search_plan = query_plan_provenance[source["search_provenance"]["query_plan_sha256"]]
                terminology_plan = query_plan_provenance[terminology["query_plan_sha256"]]
                if discovery_plan["search_step_by_plan_item"][source["discovery_provenance"]["plan_item_id"]] != "DOMAIN_DISCOVERY":
                    raise ValidationError("cross-domain Source discovery provenance is post-hoc or not DOMAIN_DISCOVERY")
                if search_plan["search_step_by_plan_item"][source["search_provenance"]["plan_item_id"]] != "SOURCE_SEARCH":
                    raise ValidationError("cross-domain Source search provenance is not SOURCE_SEARCH")
                if discovery["terminology_map_id"] not in set(search_plan.get("terminology_map_ids") or []):
                    raise ValidationError("cross-domain Source search did not bind its evidence-grounded Terminology Map")
                if not (
                    discovery_plan["order"]
                    < terminology_plan["order"]
                    < search_plan["order"]
                ):
                    raise ValidationError(
                        "cross-domain Source requires pre-Source discovery and terminology Query Plan contexts"
                    )
        genealogy = _require_mapping(source["genealogy"], f"{kind} Source Mechanism {index}.genealogy")
        _require_fields(genealogy, ("nodes", "relations"), f"{kind} Source Mechanism {index}.genealogy")
        nodes = _require_list(genealogy, "nodes", f"{kind} Source Mechanism {index}.genealogy", non_empty=True)
        node_ids = _unique_ids(nodes, "node_id", f"{kind} Source Mechanism {index}.genealogy.nodes")
        for number, raw_node in enumerate(nodes, 1):
            node = _require_mapping(raw_node, f"{kind} Source Mechanism {index} genealogy node {number}")
            _require_fields(node, tuple(contract["genealogy_node_fields"]), f"{kind} Source Mechanism {index} genealogy node {number}")
            _required_text(node["paper_id"], f"{kind} Source Mechanism {index} genealogy node {number}.paper_id")
            _required_text(node["mechanism_role"], f"{kind} Source Mechanism {index} genealogy node {number}.mechanism_role")
            _unique_string_values(node["evidence_refs"], f"{kind} Source Mechanism {index} genealogy node {number}.evidence_refs")
        relations = _require_list(genealogy, "relations", f"{kind} Source Mechanism {index}.genealogy")
        for number, raw_relation in enumerate(relations, 1):
            relation = _require_mapping(raw_relation, f"{kind} Source Mechanism {index} genealogy relation {number}")
            _require_fields(relation, tuple(contract["genealogy_relation_fields"]), f"{kind} Source Mechanism {index} genealogy relation {number}")
            if relation["from_node_id"] not in node_ids or relation["to_node_id"] not in node_ids:
                raise ValidationError(f"{kind} Source Mechanism {index} genealogy relation {number} has an unresolved node")
            _required_text(relation["relation"], f"{kind} Source Mechanism {index} genealogy relation {number}.relation")
        alignment = _require_mapping(source["intervention_level_alignment"], f"{kind} Source Mechanism {index}.intervention_level_alignment")
        nullable_alignment_fields = {"solution_principle_abstraction", "failure_disposition"}
        _require_fields(
            alignment,
            tuple(
                field
                for field in contract["intervention_alignment_fields"]
                if field not in nullable_alignment_fields
            ),
            f"{kind} Source Mechanism {index}.intervention_level_alignment",
        )
        if any(field not in alignment for field in nullable_alignment_fields):
            raise ValidationError(
                f"{kind} Source Mechanism {index}.intervention_level_alignment is missing nullable decision fields"
            )
        alignment_id = _required_text(alignment["alignment_id"], f"{kind} Source Mechanism {index}.alignment_id")
        if alignment_id in alignment_by_id or alignment["source_mechanism_id"] != source_id or alignment["rmc_id"] not in served_rmc_ids:
            raise ValidationError(f"{kind} Source Mechanism {index} has an invalid alignment binding")
        if alignment["decision"] not in set(contract["intervention_alignment_decision_enum"]):
            raise ValidationError(f"{kind} Source Mechanism {index} alignment decision is invalid")
        for field in (
            "variable_or_relation_role_mapping", "change_direction_alignment",
            "intervention_position_alignment", "activation_condition_alignment",
            "source_actual_effect", "assumption_boundary_mismatches",
        ):
            if not isinstance(alignment[field], (str, list, dict)) or alignment[field] in ("", [], {}):
                raise ValidationError(f"{kind} Source Mechanism {index} alignment.{field} must be non-empty")
        alignment_refs = set(_unique_string_values(alignment["evidence_refs"], f"{kind} Source Mechanism {index} alignment.evidence_refs"))
        if not alignment_refs <= evidence_refs:
            raise ValidationError(f"{kind} Source Mechanism {index} alignment cites Evidence outside its Source record")
        if alignment["decision"] == "PASS":
            _required_text(alignment["solution_principle_abstraction"], f"{kind} Source Mechanism {index} alignment.solution_principle_abstraction")
            if alignment["failure_disposition"] not in (None, ""):
                raise ValidationError("PASS alignment must not carry a failure disposition")
        else:
            _required_text(alignment["failure_disposition"], f"{kind} Source Mechanism {index} alignment.failure_disposition")
            if alignment["solution_principle_abstraction"] not in (None, ""):
                raise ValidationError("FAIL alignment must not abstract a Solution Principle")
        alignment_by_id[alignment_id] = alignment

    closures = _require_list(
        search, "search_space_closures", "method design packet.principle_search_record", non_empty=True
    )
    closure_rmc_ids = _unique_ids(closures, "rmc_id", "search-space closures")
    if closure_rmc_ids != mechanism_ids:
        raise ValidationError("each RMC must have exactly one same-field/cross-domain search closure")
    allowed_outcomes = set(contract["source_search_outcome_enum"])
    for index, raw in enumerate(closures, 1):
        item = _require_mapping(raw, f"search-space closure {index}")
        _require_fields(item, tuple(contract["search_space_closure_fields"]), f"search-space closure {index}")
        for field in ("same_field_search_provenance", "cross_domain_search_provenance"):
            _unique_string_values(item[field], f"search-space closure {index}.{field}")
        for field in ("same_field_outcome", "cross_domain_outcome"):
            if item[field] not in allowed_outcomes:
                raise ValidationError(f"search-space closure {index}.{field} is invalid")
        if item["model_prior_executed"] is not True or item["academic_bridge_executed"] is not True:
            raise ValidationError(f"search-space closure {index} must execute MODEL_PRIOR and ACADEMIC_BRIDGE")
        unresolved = _unique_string_values(
            item["unresolved_high_value_branches"],
            f"search-space closure {index}.unresolved_high_value_branches",
            non_empty=False,
        )
        if unresolved:
            raise ValidationError("fixed search budget cannot close an unresolved high-value branch")
        _required_text(item["literature_budget_disposition"], f"search-space closure {index}.literature_budget_disposition")
        _required_text(item["closure_rationale"], f"search-space closure {index}.closure_rationale")
        rmc_id = item["rmc_id"]
        retained_same = any(rmc_id in source["served_rmc_ids"] for source in same_field)
        retained_cross = any(rmc_id in source["served_rmc_ids"] for source in cross_domain)
        if (item["same_field_outcome"] == "CREDIBLE_SOURCE_RETAINED") != retained_same:
            raise ValidationError(f"search-space closure {index} same-field outcome does not match retained Sources")
        if (item["cross_domain_outcome"] == "CREDIBLE_SOURCE_RETAINED") != retained_cross:
            raise ValidationError(f"search-space closure {index} cross-domain outcome does not match retained Sources")
    _required_text(search["closure_rationale"], "method design packet.principle_search_record.closure_rationale")

    constraint_assessment = _require_mapping(
        packet["solution_space_constraint_assessment"],
        "method design packet.solution_space_constraint_assessment",
    )
    _require_fields(
        constraint_assessment,
        tuple(contract["solution_space_constraint_assessment_fields"]),
        "method design packet.solution_space_constraint_assessment",
    )
    if constraint_assessment["disposition"] not in set(
        contract["solution_space_constraint_disposition_enum"]
    ):
        raise ValidationError("method design packet has an invalid solution-space constraint disposition")
    if not isinstance(constraint_assessment["constraint_basis"], (str, list, dict)) or (
        constraint_assessment["constraint_basis"] in ("", [], {})
    ):
        raise ValidationError("method design packet.solution_space_constraint_assessment.constraint_basis must be non-empty")

    principles = _require_list(packet, "candidate_principles", "method design packet", non_empty=True)
    principle_keys: set[tuple[str, str]] = set()
    principle_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    assumption_ids: dict[tuple[str, str], set[str]] = {}
    prediction_ids: dict[tuple[str, str], set[str]] = {}
    prediction_assumptions: dict[tuple[str, str], dict[str, set[str]]] = {}
    derived_sources_by_candidate: dict[tuple[str, str], set[tuple[str, str]]] = {}
    pending_rival_principle_refs: list[tuple[str, str, str]] = []
    statuses = set(contract["candidate_status_enum"])
    for index, raw in enumerate(principles, 1):
        item = _require_mapping(raw, f"candidate principle {index}")
        nullable_candidate_fields = {"parent_version", "alignment_ref_id"}
        candidate_fields = tuple(
            field
            for field in contract["candidate_principle_fields"]
            if field not in nullable_candidate_fields
        )
        _require_fields(item, candidate_fields, f"candidate principle {index}")
        candidate_forbidden = set(contract.get("candidate_forbidden_fields") or []) & set(item)
        if candidate_forbidden:
            raise ValidationError(
                f"candidate principle {index} must not contain test design fields: "
                + ", ".join(sorted(candidate_forbidden))
            )
        if any(field not in item for field in nullable_candidate_fields):
            raise ValidationError(
                f"candidate principle {index} is missing parent_version or alignment_ref_id"
            )
        principle_id = _required_text(item["principle_id"], f"candidate principle {index}.principle_id")
        version = _required_text(str(item["principle_version"]), f"candidate principle {index}.principle_version")
        key = (principle_id, version)
        if key in principle_keys:
            raise ValidationError("candidate Principle ID/version pairs must be unique")
        principle_keys.add(key)
        principle_by_key[key] = item
        if item["parent_version"] is not None and not isinstance(item["parent_version"], (str, int)):
            raise ValidationError(f"candidate principle {index}.parent_version is invalid")
        if item["parent_version"] is not None and str(item["parent_version"]) == version:
            raise ValidationError(f"candidate principle {index}.parent_version must identify an earlier version")
        raw_derived_sources = item.get("derived_from_principles")
        if raw_derived_sources is not None:
            if not isinstance(raw_derived_sources, list):
                raise ValidationError(
                    f"candidate principle {index}.derived_from_principles must be a list"
                )
            derived_sources: set[tuple[str, str]] = set()
            for number, raw_source in enumerate(raw_derived_sources, 1):
                source = _require_mapping(
                    raw_source,
                    f"candidate principle {index} derived source {number}",
                )
                _require_fields(
                    source,
                    tuple(contract["candidate_derived_from_principle_fields"]),
                    f"candidate principle {index} derived source {number}",
                )
                source_key = (
                    _required_text(
                        source["principle_id"],
                        f"candidate principle {index} derived source {number}.principle_id",
                    ),
                    _required_text(
                        str(source["principle_version"]),
                        f"candidate principle {index} derived source {number}.principle_version",
                    ),
                )
                if source_key in derived_sources:
                    raise ValidationError(
                        f"candidate principle {index}.derived_from_principles contains duplicates"
                    )
                derived_sources.add(source_key)
            if derived_sources and len(derived_sources) < 2:
                raise ValidationError(
                    f"candidate principle {index}.derived_from_principles requires at least two sources"
                )
            derived_sources_by_candidate[key] = derived_sources
        for field in (
            "principle", "origin_type", "origin_ref_id", "intervention", "changed_structure",
            "root_cause_resolution_rationale", "provisional_scientific_delta",
            "substantive_difference", "status_rationale",
        ):
            _required_text(item[field], f"candidate principle {index}.{field}")
        origin_type = item["origin_type"]
        if origin_type not in set(contract["candidate_origin_type_enum"]):
            raise ValidationError(f"candidate principle {index}.origin_type is invalid")
        for field, allowed_ids in (
            ("mechanism_change_ids", mechanism_ids),
            ("capability_ids", capability_ids),
            ("obligation_ids", obligation_ids),
            ("causal_chain_ids", primary_causal_chain_ids),
        ):
            refs = set(_unique_string_values(item[field], f"candidate principle {index}.{field}"))
            if not refs <= allowed_ids:
                raise ValidationError(f"candidate principle {index}.{field} contains an unresolved ID")
        candidate_rmc_ids = set(item["mechanism_change_ids"])
        origin_ref_id = item["origin_ref_id"]
        if origin_type == "FIRST_PRINCIPLES":
            origin = next(
                (record for record in first_principles if record["origin_record_id"] == origin_ref_id),
                None,
            )
            if origin is None or origin["rmc_id"] not in candidate_rmc_ids:
                raise ValidationError(f"candidate principle {index} has a stale first-principles origin binding")
            if item["alignment_ref_id"] is not None:
                raise ValidationError(f"candidate principle {index} derivation origin must not fabricate Source alignment")
        elif origin_type == "REPRESENTATION_TRANSFORMATION":
            origin = next(
                (record for record in transformations if record["origin_record_id"] == origin_ref_id),
                None,
            )
            if origin is None or origin["rmc_id"] not in candidate_rmc_ids:
                raise ValidationError(f"candidate principle {index} has a stale representation origin binding")
            if item["alignment_ref_id"] is not None:
                raise ValidationError(f"candidate principle {index} derivation origin must not fabricate Source alignment")
        else:
            source = source_by_id.get(origin_ref_id)
            expected_kind = "same-field" if origin_type == "SAME_FIELD_SOURCE" else "cross-domain"
            if source is None or source_kind_by_id.get(origin_ref_id) != expected_kind:
                raise ValidationError(f"candidate principle {index} has a stale Source Mechanism origin binding")
            alignment = alignment_by_id.get(str(item["alignment_ref_id"] or ""))
            if (
                alignment is None
                or alignment["source_mechanism_id"] != origin_ref_id
                or alignment["decision"] != "PASS"
                or alignment["rmc_id"] not in candidate_rmc_ids
            ):
                raise ValidationError(
                    f"candidate principle {index} requires an accepted intervention-level alignment"
                )
            if not candidate_rmc_ids <= set(source["served_rmc_ids"]):
                raise ValidationError(f"candidate principle {index} exceeds its Source Mechanism RMC binding")
            if item["principle"] != alignment["solution_principle_abstraction"]:
                raise ValidationError(
                    f"candidate principle {index} must use the accepted algorithm-independent Solution Principle abstraction"
                )
        for field in ("activation_conditions", "failure_conditions", "target_domain_operationalization"):
            if not isinstance(item[field], (str, list, dict)) or item[field] in ("", [], {}):
                raise ValidationError(f"candidate principle {index}.{field} must be non-empty")
        assumptions = _require_list(item, "fatal_assumptions", f"candidate principle {index}", non_empty=True)
        assumption_ids[key] = _unique_ids(assumptions, "assumption_id", f"candidate principle {index}.fatal_assumptions")
        for number, assumption in enumerate(assumptions, 1):
            assumption = _require_mapping(assumption, f"candidate principle {index} fatal assumption {number}")
            _require_fields(assumption, tuple(contract["fatal_assumption_fields"]), f"candidate principle {index} fatal assumption {number}")
            _required_text(
                assumption["assumption"],
                f"candidate principle {index} fatal assumption {number}.assumption",
            )
            _required_text(
                assumption["failure_consequence"],
                f"candidate principle {index} fatal assumption {number}.failure_consequence",
            )
        predictions = _require_list(item, "predictions", f"candidate principle {index}", non_empty=True)
        prediction_ids[key] = _unique_ids(predictions, "prediction_id", f"candidate principle {index}.predictions")
        prediction_assumptions[key] = {}
        for number, prediction in enumerate(predictions, 1):
            prediction = _require_mapping(prediction, f"candidate principle {index} prediction {number}")
            _require_fields(prediction, tuple(contract["prediction_fields"]), f"candidate principle {index} prediction {number}")
            bound_assumptions = set(_unique_string_values(prediction["assumption_ids"], f"candidate principle {index} prediction {number}.assumption_ids"))
            if not bound_assumptions <= assumption_ids[key]:
                raise ValidationError(f"candidate principle {index} prediction {number} references an unknown assumption")
            prediction_assumptions[key][prediction["prediction_id"]] = bound_assumptions
            for field in (
                "observable", "pattern_a", "rival_id", "pattern_b", "killer_criterion",
                "cheapest_informative_rationale",
            ):
                _required_text(
                    prediction[field],
                    f"candidate principle {index} prediction {number}.{field}",
                )
            if prediction["rival_type"] not in set(contract["prediction_rival_type_enum"]):
                raise ValidationError(
                    f"candidate principle {index} prediction {number}.rival_type is invalid"
                )
            if not isinstance(prediction["activation_condition"], (str, list, dict)) or prediction["activation_condition"] in ("", [], {}):
                raise ValidationError(
                    f"candidate principle {index} prediction {number}.activation_condition must be non-empty"
                )
            if prediction["rival_type"] == "PRINCIPLE":
                pending_rival_principle_refs.append(
                    (
                        f"candidate principle {index} prediction {number}",
                        principle_id,
                        str(prediction["rival_id"]),
                    )
                )
            elif rival_rca_ids is not None and str(prediction["rival_id"]) not in rival_rca_ids:
                raise ValidationError(
                    f"candidate principle {index} prediction {number} references an unknown Rival RCA"
                )
        evidence_refs = _unique_string_values(item["evidence_refs"], f"candidate principle {index}.evidence_refs", non_empty=False)
        if current_evidence_ids is not None and not set(evidence_refs) <= current_evidence_ids:
            raise ValidationError(f"candidate principle {index} cites Evidence outside the current formal context")
        novelty = _require_mapping(
            item["target_intervention_novelty"],
            f"candidate principle {index}.target_intervention_novelty",
        )
        _require_fields(
            novelty,
            tuple(contract["target_intervention_novelty_fields"]),
            f"candidate principle {index}.target_intervention_novelty",
        )
        _required_text(
            novelty["novelty_closure_id"],
            f"candidate principle {index}.target_intervention_novelty.novelty_closure_id",
        )
        novelty_refs = set(
            _unique_string_values(
                novelty["nearest_target_prior_evidence_refs"],
                f"candidate principle {index}.target_intervention_novelty.nearest_target_prior_evidence_refs",
            )
        )
        novelty_provenance = _require_list(
            novelty,
            "evidence_search_provenance",
            f"candidate principle {index}.target_intervention_novelty",
            non_empty=True,
        )
        if query_plan_provenance is None:
            raise ValidationError(
                f"candidate principle {index} target novelty requires current Method Design query provenance"
            )
        seen_novelty_provenance: set[tuple[str, str, str]] = set()
        for number, raw_provenance in enumerate(novelty_provenance, 1):
            provenance = _require_mapping(
                raw_provenance,
                f"candidate principle {index} target novelty search provenance {number}",
            )
            _require_fields(
                provenance,
                ("query_plan_sha256", "plan_item_id", "query_id"),
                f"candidate principle {index} target novelty search provenance {number}",
            )
            plan_sha256 = _required_text(
                provenance["query_plan_sha256"],
                f"candidate principle {index} target novelty search provenance {number}.query_plan_sha256",
            )
            plan_item_id = _required_text(
                provenance["plan_item_id"],
                f"candidate principle {index} target novelty search provenance {number}.plan_item_id",
            )
            query_id = _required_text(
                provenance["query_id"],
                f"candidate principle {index} target novelty search provenance {number}.query_id",
            )
            provenance_key = (plan_sha256, plan_item_id, query_id)
            if provenance_key in seen_novelty_provenance:
                raise ValidationError(
                    f"candidate principle {index} target novelty search provenance contains duplicates"
                )
            seen_novelty_provenance.add(provenance_key)
            plan_record = query_plan_provenance.get(plan_sha256)
            if not isinstance(plan_record, dict):
                raise ValidationError(
                    f"candidate principle {index} target novelty cites an unknown accepted Method Design Query Plan"
                )
            if plan_record.get("is_current") is not True:
                raise ValidationError(
                    f"candidate principle {index} target novelty cites a stale Method Design Query Plan"
                )
            if plan_item_id not in (plan_record.get("search_step_by_plan_item") or {}):
                raise ValidationError(
                    f"candidate principle {index} target novelty cites an unknown Method Design plan item"
                )
            completed_by_item = plan_record.get("completed_query_ids_by_plan_item") or {}
            if query_id not in set(completed_by_item.get(plan_item_id) or []):
                raise ValidationError(
                    f"candidate principle {index} target novelty does not resolve to a completed current Method Design query event"
                )
        for field in ("uncovered_residual_delta", "mechanism_delta", "scientific_delta"):
            _required_text(
                novelty[field],
                f"candidate principle {index}.target_intervention_novelty.{field}",
            )
        if novelty["causal_equivalent_intervention_check"] not in set(
            contract["target_intervention_novelty_check_enum"]
        ):
            raise ValidationError(f"candidate principle {index} has an invalid causal-equivalence check")
        if novelty["disposition"] not in set(
            contract["target_intervention_novelty_disposition_enum"]
        ):
            raise ValidationError(f"candidate principle {index} has an invalid target-novelty disposition")
        if current_evidence_ids is not None and not novelty_refs <= current_evidence_ids:
            raise ValidationError(f"candidate principle {index} target novelty cites Evidence outside the current formal context")
        if item["status"] in {"ACTIVE", "REVISED", "WEAKENED"} and (
            novelty["causal_equivalent_intervention_check"] == "COVERED"
            or novelty["disposition"] == "REJECTED_AS_COVERED"
        ):
            raise ValidationError(
                f"candidate principle {index} cannot remain active when the Target already has a causal-equivalent intervention"
            )
        if item["status"] not in statuses:
            raise ValidationError(f"candidate principle {index}.status is invalid")

    known_principle_ids = {principle_id for principle_id, _ in principle_keys}
    for label, principle_id, rival_id in pending_rival_principle_refs:
        if rival_id not in known_principle_ids or rival_id == principle_id:
            raise ValidationError(f"{label} references an unknown or self Rival Principle")

    active_keys = {key for key, item in principle_by_key.items() if item["status"] in {"ACTIVE", "REVISED", "WEAKENED"}}
    if not active_keys:
        raise ValidationError("method design packet must retain at least one active Candidate Principle")
    active_candidates = [principle_by_key[key] for key in active_keys]
    if (
        constraint_assessment["disposition"] == "UNDERCONSTRAINED"
        and len(active_candidates) < 2
    ):
        raise ValidationError(
            "UNDERCONSTRAINED solution space requires multiple active Candidate Principles"
        )
    for field, required_ids in (
        ("mechanism_change_ids", mechanism_ids),
        ("capability_ids", capability_ids),
        ("obligation_ids", obligation_ids),
    ):
        consumed = {
            reference
            for candidate in active_candidates
            for reference in candidate[field]
        }
        if consumed != required_ids:
            raise ValidationError(
                f"active Candidate Principles must consume every current {field}: {sorted(required_ids - consumed)}"
            )

    if required_combine_sources is not None:
        if len(required_combine_sources) < 2:
            raise ValidationError("Human combine source Candidate lineage requires at least two sources")
        if not derived_sources_by_candidate:
            raise ValidationError(
                "Human combine return requires a synthesis Candidate derived_from_principles"
            )
        if not any(
            sources == required_combine_sources
            for sources in derived_sources_by_candidate.values()
        ):
            raise ValidationError(
                "Human combine return has no synthesis Candidate whose derived_from_principles match current reviewed Human combine sources"
            )

    history_refs = set(_unique_string_values(packet["relevant_history_refs"], "method design packet.relevant_history_refs", non_empty=False))
    if not set(required_history_refs or set()) <= history_refs:
        raise ValidationError("method design packet omits relevant cross-cycle Principle/Test history")
    return_refs = set(_unique_string_values(packet["return_feedback_refs"], "method design packet.return_feedback_refs", non_empty=False))
    if required_return_ref is not None and required_return_ref not in return_refs:
        raise ValidationError("method design packet omits the current return feedback")
    return {
        "packet": packet,
        "design_cycle_id": design_cycle_id,
        "principle_keys": sorted(principle_keys),
        "mechanism_change_ids": sorted(mechanism_ids),
        "capability_ids": sorted(capability_ids),
        "obligation_ids": sorted(obligation_ids),
    }


def render_method_design_view(packet: dict[str, Any]) -> str:
    lines = [
        "# Method Design — Candidate Principles",
        "",
        f"Design cycle: `{packet['design_cycle_id']}`",
        "",
        "This packet presents Candidate Principles for Human discussion and selection. It does not contain a test plan, execution set, or cost approval.",
        "",
        "**Solution-space constraint.** "
        f"{packet['solution_space_constraint_assessment']['disposition']}: "
        f"{packet['solution_space_constraint_assessment']['constraint_basis']}",
    ]
    for candidate in packet["candidate_principles"]:
        lines.extend(
            [
                "",
                f"## {candidate['principle_id']} · version {candidate['principle_version']}",
                "",
                f"**Principle.** {candidate['principle']}",
                "",
                f"**Mechanism.** {candidate['intervention']} This changes {candidate['changed_structure']}. {candidate['root_cause_resolution_rationale']}",
                "",
                f"**Provisional Scientific Delta.** {candidate['provisional_scientific_delta']}",
                "",
                "**Primary risks.** " + "; ".join(
                    f"{item['assumption']} → {item['failure_consequence']}"
                    for item in candidate["fatal_assumptions"]
                ),
                "",
                f"**Substantive difference.** {candidate['substantive_difference']}",
                "",
                "**Killer-test concepts.** " + "; ".join(
                    f"{item['observable']}: Pattern A={item['pattern_a']} vs "
                    f"{item['rival_type']} {item['rival_id']} Pattern B={item['pattern_b']} "
                    f"under {item['activation_condition']}"
                    for item in candidate["predictions"]
                ),
                "",
                f"**Status.** {candidate['status']}: {candidate['status_rationale']}",
            ]
        )
    return "\n".join(lines) + "\n"


def validate_method_design_view(text: Any, packet: dict[str, Any]) -> str:
    expected = render_method_design_view(packet)
    if text != expected:
        raise ValidationError(
            "method design view must exactly match the deterministic packet rendering"
        )
    return text


def validate_principle_test_plan(
    payload: Any,
    *,
    contract: dict[str, Any],
    selected_for_testing: dict[str, Any],
    candidate: dict[str, Any],
    required_history_refs: set[str] | None = None,
    required_return_ref: str | None = None,
) -> dict[str, Any]:
    """Validate one selected-Candidate, minimum-set test plan mechanically."""

    plan = _require_mapping(payload, "Principle test plan")
    _require_fields(plan, tuple(contract["required_fields"]), "Principle test plan")
    if plan["schema_version"] != contract.get("schema_version", 1):
        raise ValidationError("Principle test plan schema_version is invalid")
    cycle_id = _required_text(plan["cycle_id"], "Principle test plan.cycle_id")
    execution_set_id = _required_text(
        plan["execution_set_id"], "Principle test plan.execution_set_id"
    )
    binding = _require_mapping(
        plan["selected_for_testing_binding"],
        "Principle test plan.selected_for_testing_binding",
    )
    _require_fields(
        binding,
        tuple(contract["selected_for_testing_binding_fields"]),
        "Principle test plan.selected_for_testing_binding",
    )
    expected_binding = {
        field: selected_for_testing[field]
        for field in contract["selected_for_testing_binding_fields"]
    }
    if binding != expected_binding:
        raise ValidationError("Principle test plan does not bind the active Human-selected Candidate")

    strategy = _require_mapping(plan["test_strategy"], "Principle test plan.test_strategy")
    _require_fields(
        strategy,
        tuple(contract["test_strategy_fields"]),
        "Principle test plan.test_strategy",
    )
    for field in contract["test_strategy_fields"]:
        if not isinstance(strategy[field], (str, list, dict)) or strategy[field] in ("", [], {}):
            raise ValidationError(f"Principle test plan.test_strategy.{field} must be non-empty")

    principle_key = (str(candidate["principle_id"]), str(candidate["principle_version"]))
    assumption_ids = {
        str(item["assumption_id"]): item for item in candidate["fatal_assumptions"]
    }
    prediction_by_id = {
        str(item["prediction_id"]): item for item in candidate["predictions"]
    }
    tests = _require_list(plan, "discriminating_tests", "Principle test plan", non_empty=True)
    test_ids = _unique_ids(tests, "test_id", "Principle test plan.discriminating_tests")
    targeted_assumptions: set[str] = set()
    tiers = set(contract["evidence_tier_enum"])
    for index, raw in enumerate(tests, 1):
        item = _require_mapping(raw, f"Principle test {index}")
        _require_fields(
            item,
            tuple(contract["discriminating_test_required_fields"]),
            f"Principle test {index}",
        )
        killer_ref = _required_text(
            item["killer_test_concept_ref"],
            f"Principle test {index}.killer_test_concept_ref",
        )
        if killer_ref not in prediction_by_id:
            raise ValidationError(f"Principle test {index} cites an unknown killer-test concept")
        concept = prediction_by_id[killer_ref]
        for field in ("test_type", "operationalization", "information_gain", "falsification_criterion"):
            _required_text(item[field], f"Principle test {index}.{field}")
        if item["evidence_tier"] not in tiers:
            raise ValidationError(f"Principle test {index}.evidence_tier is invalid")
        if not isinstance(item["execution_requirements"], (str, list, dict)) or item["execution_requirements"] in ("", [], {}):
            raise ValidationError(f"Principle test {index}.execution_requirements must be non-empty")
        if item.get("test_only_concrete_realization") is not None and (
            not isinstance(item["test_only_concrete_realization"], (str, dict))
            or item["test_only_concrete_realization"] in ("", {})
        ):
            raise ValidationError(f"Principle test {index}.test_only_concrete_realization is invalid")
        observation = _require_mapping(
            item["observation_contract"], f"Principle test {index}.observation_contract"
        )
        _require_fields(
            observation,
            tuple(contract["observation_contract_fields"]),
            f"Principle test {index}.observation_contract",
        )
        expected_observation = {
            "observable": concept["observable"],
            "pattern_a": concept["pattern_a"],
            "rival_type": concept["rival_type"],
            "rival_id": concept["rival_id"],
            "pattern_b": concept["pattern_b"],
            "activation_condition": concept["activation_condition"],
        }
        if observation != expected_observation:
            raise ValidationError(
                f"Principle test {index} does not preserve its Candidate/Rival Pattern A/B concept"
            )
        terminal_criteria = _require_mapping(
            item["terminal_criteria"], f"Principle test {index}.terminal_criteria"
        )
        _require_fields(
            terminal_criteria,
            tuple(contract["terminal_criteria_fields"]),
            f"Principle test {index}.terminal_criteria",
        )
        for field in contract["terminal_criteria_fields"]:
            _required_text(
                terminal_criteria[field], f"Principle test {index}.terminal_criteria.{field}"
            )
        targets = _require_list(item, "targets", f"Principle test {index}", non_empty=True)
        seen_targets: set[tuple[str, ...]] = set()
        for number, raw_target in enumerate(targets, 1):
            target = _require_mapping(raw_target, f"Principle test {index} target {number}")
            _require_fields(
                target,
                tuple(contract["test_target_fields"]),
                f"Principle test {index} target {number}",
            )
            if (str(target["principle_id"]), str(target["principle_version"])) != principle_key:
                raise ValidationError(f"Principle test {index} targets a non-selected Candidate")
            assumption_id = str(target["assumption_id"])
            prediction_id = str(target["prediction_id"])
            if assumption_id not in assumption_ids or prediction_id not in prediction_by_id:
                raise ValidationError(f"Principle test {index} targets an unknown assumption or prediction")
            if prediction_id != killer_ref:
                raise ValidationError(
                    f"Principle test {index} target does not match its killer-test concept"
                )
            if assumption_id not in {
                str(value) for value in prediction_by_id[prediction_id]["assumption_ids"]
            }:
                raise ValidationError(f"Principle test {index} target does not bind its prediction to its assumption")
            if (
                target["mechanism_change_id"] not in candidate["mechanism_change_ids"]
                or target["causal_chain_id"] not in candidate["causal_chain_ids"]
            ):
                raise ValidationError(f"Principle test {index} target is not bound through the selected Candidate to RCA")
            identity = tuple(str(target[field]) for field in contract["test_target_fields"])
            if identity in seen_targets:
                raise ValidationError(f"Principle test {index} contains a duplicate target")
            seen_targets.add(identity)
            targeted_assumptions.add(assumption_id)

    priority_ids = set(
        _unique_string_values(
            strategy["fatal_assumption_priority"],
            "Principle test plan.test_strategy.fatal_assumption_priority",
        )
    )
    if not priority_ids <= set(assumption_ids) or not priority_ids <= targeted_assumptions:
        raise ValidationError("Principle test plan does not test every prioritized fatal assumption")
    recommended = _require_mapping(
        plan["recommended_execution_set"], "Principle test plan.recommended_execution_set"
    )
    _require_fields(
        recommended,
        tuple(contract["recommended_execution_set_fields"]),
        "Principle test plan.recommended_execution_set",
    )
    if recommended["execution_set_id"] != execution_set_id:
        raise ValidationError("Principle test plan execution-set ID is inconsistent")
    approved_ids = _unique_string_values(
        recommended["test_ids"], "Principle test plan.recommended_execution_set.test_ids"
    )
    if set(approved_ids) != test_ids:
        raise ValidationError("Principle test plan may contain only tests in the current execution set")
    if recommended["estimated_total_cost"] != plan["estimated_total_cost"]:
        raise ValidationError("Principle test plan execution-set cost is inconsistent")
    history_refs = set(
        _unique_string_values(
            plan["relevant_history_refs"],
            "Principle test plan.relevant_history_refs",
            non_empty=False,
        )
    )
    if not set(required_history_refs or set()) <= history_refs:
        raise ValidationError("Principle test plan omits relevant cross-cycle Principle/Test history")
    return_refs = set(
        _unique_string_values(
            plan["return_feedback_refs"],
            "Principle test plan.return_feedback_refs",
            non_empty=False,
        )
    )
    if required_return_ref is not None and required_return_ref not in return_refs:
        raise ValidationError("Principle test plan omits the current return feedback")
    return {
        "plan": plan,
        "cycle_id": cycle_id,
        "execution_set_id": execution_set_id,
        "test_ids": sorted(test_ids),
        "approved_test_ids": approved_ids,
    }


def render_principle_test_plan_view(plan: dict[str, Any]) -> str:
    binding = plan["selected_for_testing_binding"]
    lines = [
        "# Principle Test Plan",
        "",
        f"Selected Candidate: `{binding['principle_id']}` version `{binding['principle_version']}`",
        "",
        f"Test cycle: `{plan['cycle_id']}` · execution set: `{plan['execution_set_id']}`",
        "",
        f"**Minimum sufficiency.** {plan['test_strategy']['minimum_sufficiency_rationale']}",
        "",
        f"**Highest information gain.** {plan['test_strategy']['highest_information_gain_rationale']}",
        "",
        f"**Lower-cost evidence first.** {plan['test_strategy']['lower_cost_evidence_assessment']}",
        "",
        f"**Physical-experiment escalation.** {plan['test_strategy']['physical_experiment_escalation_justification']}",
    ]
    for test in plan["discriminating_tests"]:
        lines.extend(
            [
                "",
                f"## {test['test_id']} · {test['evidence_tier']}",
                "",
                f"**Operationalization.** {test['operationalization']}",
                "",
                f"**Pattern A.** {test['observation_contract']['pattern_a']}",
                "",
                f"**Pattern B ({test['observation_contract']['rival_type']} {test['observation_contract']['rival_id']}).** {test['observation_contract']['pattern_b']}",
                "",
                f"**Information gain.** {test['information_gain']}",
                "",
                f"**Fatal falsification criterion.** {test['falsification_criterion']}",
                "",
                f"**Estimated cost.** {test['estimated_cost']}",
            ]
        )
    lines.extend(["", f"**Total current execution-set cost.** {plan['estimated_total_cost']}"])
    return "\n".join(lines) + "\n"


def validate_principle_test_plan_view(text: Any, plan: dict[str, Any]) -> str:
    expected = render_principle_test_plan_view(plan)
    if text != expected:
        raise ValidationError(
            "Principle test plan view must exactly match the deterministic plan rendering"
        )
    return text


def validate_json_review_verdict_artifact(
    payload: Any,
    *,
    label: str,
    request_id: str,
    artifact_bindings: dict[str, str],
    decisions: set[str],
    reviewed_artifact_path: str,
) -> dict[str, Any]:
    verdict = _validate_review_binding(
        payload,
        label=label,
        request_id=request_id,
        reviewer=None,
        verdict_id=None,
        decision=None,
        artifact_bindings=artifact_bindings,
    )
    _require_fields(
        verdict,
        ("reviewed_artifact", "findings"),
        label,
    )
    if "return_guidance" not in verdict:
        raise ValidationError(f"{label} is missing return_guidance")
    if verdict["decision"] not in decisions:
        raise ValidationError(f"{label} decision is not allowed by the Gate")
    reviewed = _require_mapping(verdict["reviewed_artifact"], f"{label}.reviewed_artifact")
    _require_fields(reviewed, ("path", "sha256"), f"{label}.reviewed_artifact")
    if reviewed != {
        "path": reviewed_artifact_path,
        "sha256": artifact_bindings.get(reviewed_artifact_path),
    }:
        raise ValidationError(f"{label}.reviewed_artifact does not identify the declared Main artifact")
    _require_list(verdict, "findings", label)
    if verdict["decision"] not in {"PRINCIPLE_PACKET_READY", "TEST_PLAN_READY", "PRINCIPLE_CONVERGED"}:
        _validate_return_guidance(verdict, label=label, required=True)
    elif verdict["return_guidance"] not in (None, {}):
        _validate_return_guidance(verdict, label=label, required=False)
    return verdict


def validate_method_test_result(
    payload: Any,
    *,
    cycle_id: str,
    execution_set_id: str,
    approved_test_ids: set[str],
    no_result_reasons: set[str],
    root: Path | None = None,
) -> dict[str, Any]:
    result = _require_mapping(payload, "method test result")
    _require_fields(
        result,
        ("schema_version", "cycle_id", "execution_set_id", "test_id", "outcome", "result_refs", "execution_metadata"),
        "method test result",
    )
    if result["schema_version"] != 1 or result["cycle_id"] != cycle_id or result["execution_set_id"] != execution_set_id:
        raise ValidationError("method test result does not match the approved execution set")
    test_id = _required_text(result["test_id"], "method test result.test_id")
    if test_id not in approved_test_ids:
        raise ValidationError("method test result test_id is not in the approved execution set")
    if result["outcome"] not in {"RESULT_AVAILABLE", "NO_RESULT"}:
        raise ValidationError("method test result outcome is invalid")
    refs = _require_list(result, "result_refs", "method test result", non_empty=result["outcome"] == "RESULT_AVAILABLE")
    normalized_refs: list[dict[str, str]] = []
    for index, raw in enumerate(refs, 1):
        ref = _require_mapping(raw, f"method test result reference {index}")
        _require_fields(ref, ("path", "sha256"), f"method test result reference {index}")
        path = _required_text(ref["path"], f"method test result reference {index}.path")
        digest = _require_sha256(ref["sha256"], f"method test result reference {index}.sha256")
        if Path(path).is_absolute():
            raise ValidationError("method test result reference paths must be project-relative")
        if root is not None:
            candidate = (root / path).resolve()
            try:
                candidate.relative_to(root.resolve())
            except ValueError as exc:
                raise ValidationError("method test result reference must stay inside the project") from exc
            if not candidate.is_file() or sha256_file(candidate) != digest:
                raise ValidationError("method test result reference is missing or changed")
        normalized_refs.append({"path": path, "sha256": digest})
    if result["outcome"] == "NO_RESULT":
        if result.get("reason") not in no_result_reasons:
            raise ValidationError("NO_RESULT requires a declared terminal reason")
    elif result.get("reason") not in (None, ""):
        raise ValidationError("RESULT_AVAILABLE must not carry a NO_RESULT reason")
    if not isinstance(result["execution_metadata"], dict):
        raise ValidationError("method test result.execution_metadata must be an object")
    return {
        **result,
        "test_id": test_id,
        "result_refs": normalized_refs,
        "reason": result.get("reason"),
    }


def validate_principle_evidence_context(
    payload: Any,
    *,
    contract: dict[str, Any],
    cycle_id: str,
    execution_set_id: str,
    approved_test_ids: set[str],
    terminal_outcomes: dict[str, Any],
    expected_active_principles: set[tuple[str, str]],
    expected_test_targets: list[dict[str, Any]],
) -> dict[str, Any]:
    context = _require_mapping(payload, "Principle Evidence Context")
    _require_fields(context, tuple(contract["required_fields"]), "Principle Evidence Context")
    if (
        context["schema_version"] != contract.get("schema_version", 1)
        or context["cycle_id"] != cycle_id
        or context["execution_set_id"] != execution_set_id
    ):
        raise ValidationError("Principle Evidence Context does not match the approved cycle")
    if set(_unique_string_values(context["approved_test_ids"], "Principle Evidence Context.approved_test_ids")) != approved_test_ids:
        raise ValidationError("Principle Evidence Context does not bind the exact approved tests")
    outcomes = _require_list(context, "terminal_outcomes", "Principle Evidence Context")
    by_test: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(outcomes, 1):
        outcome = _require_mapping(raw, f"Principle Evidence Context terminal outcome {index}")
        _require_fields(outcome, ("test_id", "outcome"), f"Principle Evidence Context terminal outcome {index}")
        test_id = _required_text(outcome["test_id"], f"Principle Evidence Context terminal outcome {index}.test_id")
        if test_id in by_test or outcome["outcome"] not in {"RESULT_AVAILABLE", "NO_RESULT"}:
            raise ValidationError("Principle Evidence Context has a duplicate or invalid terminal outcome")
        by_test[test_id] = outcome
    if set(by_test) != approved_test_ids or any(
        by_test[test_id]["outcome"] != terminal_outcomes[test_id]["outcome"]
        for test_id in approved_test_ids
    ):
        raise ValidationError("Principle Evidence Context terminal outcomes are incomplete or stale")
    targets = _require_list(context, "test_targets", "Principle Evidence Context", non_empty=True)
    target_fields = tuple(contract["test_target_fields"])
    actual_targets: list[tuple[str, ...]] = []
    for index, raw in enumerate(targets, 1):
        target = _require_mapping(raw, f"Principle Evidence Context target {index}")
        _require_fields(target, target_fields, f"Principle Evidence Context target {index}")
        if target["test_id"] not in approved_test_ids:
            raise ValidationError("Principle Evidence Context target is outside the approved set")
        actual_targets.append(tuple(str(target[field]) for field in target_fields))
    expected_targets = [
        tuple(str(target[field]) for field in target_fields)
        for target in expected_test_targets
    ]
    if sorted(actual_targets) != sorted(expected_targets):
        raise ValidationError("Principle Evidence Context does not preserve the approved test-target mapping")
    principles = _require_list(context, "active_principles", "Principle Evidence Context", non_empty=True)
    actual_principles: set[tuple[str, str]] = set()
    for index, raw in enumerate(principles, 1):
        principle = _require_mapping(raw, f"Principle Evidence Context active Principle {index}")
        _require_fields(
            principle,
            ("principle_id", "principle_version"),
            f"Principle Evidence Context active Principle {index}",
        )
        key = (str(principle["principle_id"]), str(principle["principle_version"]))
        if key in actual_principles:
            raise ValidationError("Principle Evidence Context contains a duplicate active Principle")
        actual_principles.add(key)
    if actual_principles != expected_active_principles:
        raise ValidationError("Principle Evidence Context does not bind the exact active Candidate set")
    _require_list(context, "result_refs", "Principle Evidence Context")
    _require_list(context, "historical_evidence_refs", "Principle Evidence Context")
    _require_list(context, "current_evidence_refs", "Principle Evidence Context")
    _require_list(context, "unresolved_assumption_ids", "Principle Evidence Context")
    if not isinstance(context["execution_metadata"], dict):
        raise ValidationError("Principle Evidence Context.execution_metadata must be an object")
    return context


def validate_principle_evaluation(
    payload: Any,
    *,
    contract: dict[str, Any],
    cycle_id: str,
    execution_set_id: str,
    evidence_context_ref: dict[str, str],
    test_plan: dict[str, Any],
    candidate: dict[str, Any],
    root_cause_analysis_id: str,
    necessity_residual_ids: set[str],
    current_evidence_refs: set[str],
    required_history_refs: set[str] | None = None,
    required_return_ref: str | None = None,
) -> dict[str, Any]:
    evaluation = _require_mapping(payload, "Principle evaluation")
    _require_fields(evaluation, tuple(contract["required_fields"]), "Principle evaluation")
    if (
        evaluation["schema_version"] != contract.get("schema_version", 1)
        or evaluation["cycle_id"] != cycle_id
        or evaluation["execution_set_id"] != execution_set_id
    ):
        raise ValidationError("Principle evaluation does not match the active cycle")
    if evaluation["evidence_context_ref"] != evidence_context_ref:
        raise ValidationError("Principle evaluation does not bind the active Evidence Context")
    tests = {
        str(item["test_id"]): item for item in test_plan["discriminating_tests"]
    }
    if set(tests) != set(test_plan["recommended_execution_set"]["test_ids"]):
        raise ValidationError("Principle evaluation Test Plan does not resolve the approved execution set")
    predictions = {
        str(item["prediction_id"]): item for item in candidate["predictions"]
    }

    def validate_test_assessment_list(
        field: str,
        fields_contract: str,
        status_field: str,
        status_contract: str,
    ) -> None:
        items = _require_list(evaluation, field, "Principle evaluation", non_empty=True)
        covered = _unique_ids(items, "test_id", f"Principle evaluation.{field}")
        if covered != set(tests):
            raise ValidationError(f"Principle evaluation.{field} must cover every approved test")
        allowed = set(contract[status_contract])
        for index, raw in enumerate(items, 1):
            item = _require_mapping(raw, f"Principle evaluation.{field} item {index}")
            _require_fields(
                item,
                tuple(contract[fields_contract]),
                f"Principle evaluation.{field} item {index}",
            )
            if item[status_field] not in allowed:
                raise ValidationError(
                    f"Principle evaluation.{field} item {index}.{status_field} is invalid"
                )
            refs = set(
                _unique_string_values(
                    item["evidence_refs"],
                    f"Principle evaluation.{field} item {index}.evidence_refs",
                    non_empty=False,
                )
            )
            if not refs <= current_evidence_refs:
                raise ValidationError(
                    f"Principle evaluation.{field} item {index} cites Evidence outside the active Context"
                )
            _required_text(item["rationale"], f"Principle evaluation.{field} item {index}.rationale")

    validate_test_assessment_list(
        "operationalization_assessments",
        "operationalization_assessment_fields",
        "status",
        "operationalization_status_enum",
    )
    validate_test_assessment_list(
        "test_validity_assessments",
        "test_validity_assessment_fields",
        "status",
        "test_validity_status_enum",
    )
    for index, item in enumerate(evaluation["test_validity_assessments"], 1):
        if item["discriminativeness"] not in set(contract["test_discriminativeness_enum"]):
            raise ValidationError(
                f"Principle evaluation.test_validity_assessments item {index}.discriminativeness is invalid"
            )
    validate_test_assessment_list(
        "activation_condition_assessments",
        "activation_condition_assessment_fields",
        "status",
        "activation_status_enum",
    )
    for index, item in enumerate(evaluation["activation_condition_assessments"], 1):
        test = tests[str(item["test_id"])]
        if str(item["prediction_id"]) != str(test["killer_test_concept_ref"]):
            raise ValidationError(
                f"Principle evaluation.activation_condition_assessments item {index} has a stale prediction binding"
            )

    comparisons = _require_list(
        evaluation, "prediction_comparisons", "Principle evaluation", non_empty=True
    )
    comparison_tests = _unique_ids(
        comparisons, "test_id", "Principle evaluation.prediction_comparisons"
    )
    if comparison_tests != set(tests):
        raise ValidationError("Principle evaluation.prediction_comparisons must cover every approved test")
    for index, raw in enumerate(comparisons, 1):
        item = _require_mapping(raw, f"Principle evaluation prediction comparison {index}")
        _require_fields(
            item,
            tuple(contract["prediction_comparison_fields"]),
            f"Principle evaluation prediction comparison {index}",
        )
        test = tests[str(item["test_id"])]
        prediction_id = str(item["prediction_id"])
        if prediction_id != str(test["killer_test_concept_ref"]) or prediction_id not in predictions:
            raise ValidationError(
                f"Principle evaluation prediction comparison {index} has a stale prediction binding"
            )
        concept = predictions[prediction_id]
        for field in ("observable", "rival_type", "rival_id"):
            if item[field] != concept[field]:
                raise ValidationError(
                    f"Principle evaluation prediction comparison {index}.{field} does not match the reviewed killer-test concept"
                )
        if item["rival_discrimination"] not in set(contract["rival_discrimination_enum"]):
            raise ValidationError(
                f"Principle evaluation prediction comparison {index}.rival_discrimination is invalid"
            )
        refs = set(
            _unique_string_values(
                item["evidence_refs"],
                f"Principle evaluation prediction comparison {index}.evidence_refs",
                non_empty=False,
            )
        )
        if not refs <= current_evidence_refs:
            raise ValidationError(
                f"Principle evaluation prediction comparison {index} cites Evidence outside the active Context"
            )
        _required_text(item["observed_pattern"], f"Principle evaluation prediction comparison {index}.observed_pattern")
        _required_text(item["rationale"], f"Principle evaluation prediction comparison {index}.rationale")

    principle_key = f"{candidate['principle_id']}@{candidate['principle_version']}"
    assumption_ids = {
        str(item["assumption_id"]) for item in candidate["fatal_assumptions"]
    }
    rival_principle_ids = {
        str(item["rival_id"])
        for item in candidate["predictions"]
        if item["rival_type"] == "PRINCIPLE"
    }
    rival_rca_ids = {
        str(item["rival_id"])
        for item in candidate["predictions"]
        if item["rival_type"] == "RIVAL_RCA"
    }
    valid_targets = {
        "PRINCIPLE": {principle_key},
        "ASSUMPTION": assumption_ids,
        "SOURCE_TARGET_MAPPING": ({str(candidate["alignment_ref_id"])} if candidate.get("alignment_ref_id") else set()),
        "TARGET_OPERATIONALIZATION": {principle_key},
        "APPLICABILITY_BOUNDARY": {principle_key},
        "RIVAL_PRINCIPLE": rival_principle_ids,
        "RIVAL_RCA": rival_rca_ids,
        "ROOT_CAUSE": {root_cause_analysis_id},
        "NECESSITY_RESIDUAL_ENVELOPE": set(necessity_residual_ids),
    }
    updates = _require_list(
        evaluation, "scientific_updates", "Principle evaluation", non_empty=True
    )
    _unique_ids(updates, "update_id", "Principle evaluation.scientific_updates")
    target_types = set(contract["scientific_update_target_type_enum"])
    consequences = set(contract["scientific_update_consequence_enum"])
    for index, raw in enumerate(updates, 1):
        update = _require_mapping(raw, f"Scientific update {index}")
        _require_fields(
            update, tuple(contract["scientific_update_fields"]), f"Scientific update {index}"
        )
        target_type = update["target_type"]
        target_id = _required_text(update["target_id"], f"Scientific update {index}.target_id")
        if target_type not in target_types:
            raise ValidationError(f"Scientific update {index}.target_type is invalid")
        if target_id not in valid_targets[target_type]:
            raise ValidationError(f"Scientific update {index} has a stale or unknown target binding")
        if update["consequence"] not in consequences:
            raise ValidationError(f"Scientific update {index}.consequence is invalid")
        if update["before"] is None or update["proposed_after"] is None:
            raise ValidationError(f"Scientific update {index} requires before and proposed_after")
        refs = set(
            _unique_string_values(
                update["evidence_refs"], f"Scientific update {index}.evidence_refs", non_empty=False
            )
        )
        if not refs <= current_evidence_refs:
            raise ValidationError(f"Scientific update {index} cites Evidence outside the active Context")
        _required_text(update["rationale"], f"Scientific update {index}.rationale")
    _require_list(evaluation, "remaining_uncertainties", "Principle evaluation")
    history_refs = set(_unique_string_values(evaluation["relevant_history_refs"], "Principle evaluation.relevant_history_refs", non_empty=False))
    if not set(required_history_refs or set()) <= history_refs:
        raise ValidationError("Principle evaluation omits relevant cross-cycle Principle/Test history")
    return_refs = set(_unique_string_values(evaluation["return_feedback_refs"], "Principle evaluation.return_feedback_refs", non_empty=False))
    if required_return_ref is not None and required_return_ref not in return_refs:
        raise ValidationError("Principle evaluation omits the current return feedback")
    return evaluation


def validate_selected_principle(
    payload: Any,
    *,
    contract: dict[str, Any],
    expected_principle_id: str,
    expected_principle_version: str,
    packet: dict[str, Any],
    evaluation: dict[str, Any],
    accepted_boundary_update_ids: set[str],
) -> dict[str, Any]:
    selected = _require_mapping(payload, "Selected Principle")
    selected_fields = tuple(
        field for field in contract["required_fields"] if field != "intervention_alignment"
    )
    _require_fields(selected, selected_fields, "Selected Principle")
    if "intervention_alignment" not in selected:
        raise ValidationError("Selected Principle is missing intervention_alignment")
    if selected["schema_version"] != contract.get("schema_version", 1):
        raise ValidationError("Selected Principle schema_version is invalid")
    if (
        str(selected["principle_id"]) != expected_principle_id
        or str(selected["principle_version"]) != expected_principle_version
    ):
        raise ValidationError("Selected Principle does not match the accepted convergence verdict")
    candidate = next(
        (
            item
            for item in packet["candidate_principles"]
            if str(item["principle_id"]) == expected_principle_id
            and str(item["principle_version"]) == expected_principle_version
        ),
        None,
    )
    if candidate is None:
        raise ValidationError("Selected Principle is not a reviewed Candidate version")
    origin_binding = {
        "origin_type": candidate["origin_type"],
        "origin_ref_id": candidate["origin_ref_id"],
        "alignment_ref_id": candidate["alignment_ref_id"],
    }
    if selected["origin_binding"] != origin_binding:
        raise ValidationError("Selected Principle.origin_binding does not match the reviewed Candidate")
    search = packet["principle_search_record"]
    if candidate["origin_type"] == "FIRST_PRINCIPLES":
        origin_records = search["first_principles"]
    elif candidate["origin_type"] == "REPRESENTATION_TRANSFORMATION":
        origin_records = search["representation_transformations"]
    elif candidate["origin_type"] == "SAME_FIELD_SOURCE":
        origin_records = search["same_field_mechanisms"]
    else:
        origin_records = search["cross_domain_structural_isomorphisms"]
    origin = next(
        (
            item
            for item in origin_records
            if str(item.get("origin_record_id") or item.get("source_mechanism_id"))
            == str(candidate["origin_ref_id"])
        ),
        None,
    )
    if origin is None or selected["origin_closure"] != origin:
        raise ValidationError("Selected Principle.origin_closure does not match its reviewed origin")
    expected_alignment = (
        origin.get("intervention_level_alignment")
        if candidate["origin_type"] in {"SAME_FIELD_SOURCE", "CROSS_DOMAIN_SOURCE"}
        else None
    )
    if selected["intervention_alignment"] != expected_alignment:
        raise ValidationError("Selected Principle.intervention_alignment does not match its reviewed origin")
    expected_fields = {
        "principle": candidate["principle"],
        "intervention": candidate["intervention"],
        "changed_structure": candidate["changed_structure"],
        "problem_binding": packet["problem_binding"],
        "root_cause_binding": packet["root_cause_binding"],
        "causal_chain_ids": candidate["causal_chain_ids"],
        "mechanism_change_ids": candidate["mechanism_change_ids"],
        "capability_ids": candidate["capability_ids"],
        "obligation_ids": candidate["obligation_ids"],
        "target_intervention_novelty": candidate["target_intervention_novelty"],
        "accepted_assumptions": candidate["fatal_assumptions"],
        "accepted_predictions": candidate["predictions"],
        "provisional_scientific_delta": candidate["provisional_scientific_delta"],
        "activation_conditions": candidate["activation_conditions"],
        "failure_conditions": candidate["failure_conditions"],
    }
    for field, expected in expected_fields.items():
        if selected[field] != expected:
            raise ValidationError(f"Selected Principle.{field} does not match the reviewed Candidate")
    if not isinstance(selected["evidence_closure"], (dict, list)) or not selected["evidence_closure"]:
        raise ValidationError("Selected Principle.evidence_closure must be non-empty")
    updates_by_id = {
        str(item["update_id"]): item for item in evaluation["scientific_updates"]
    }
    if not accepted_boundary_update_ids <= set(updates_by_id):
        raise ValidationError("Selected Principle cites an unknown accepted boundary update")
    if any(
        updates_by_id[update_id]["consequence"] != "UPDATE_BOUNDARY"
        for update_id in accepted_boundary_update_ids
    ):
        raise ValidationError("Selected Principle boundary acceptance may contain only UPDATE_BOUNDARY records")
    expected_boundaries = {
        "activation_conditions": candidate["activation_conditions"],
        "failure_conditions": candidate["failure_conditions"],
        "accepted_boundary_updates": [
            item
            for item in evaluation["scientific_updates"]
            if str(item["update_id"]) in accepted_boundary_update_ids
        ],
    }
    if selected["applicability_boundaries"] != expected_boundaries:
        raise ValidationError("Selected Principle.applicability_boundaries does not match accepted boundary updates")
    if not isinstance(selected["applicability_boundaries"], (dict, list, str)) or selected["applicability_boundaries"] in ({}, [], ""):
        raise ValidationError("Selected Principle.applicability_boundaries must be non-empty")
    if not isinstance(selected["remaining_uncertainty"], (dict, list, str)):
        raise ValidationError("Selected Principle.remaining_uncertainty is invalid")
    return selected


def render_final_method_view(packet: dict[str, Any]) -> str:
    """Render the sole deterministic human view of the Final Method packet."""

    def section(title: str, value: Any) -> list[str]:
        return [
            f"## {title}",
            "",
            "```json",
            json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True),
            "```",
            "",
        ]

    lines = [
        "# Final Method",
        "",
        f"Final Method ID: `{packet['final_method_id']}`",
        "",
        "This document is a deterministic human view of "
        "`refine-logs/FINAL_METHOD_PACKET.json`; the JSON packet is the only "
        "canonical machine authority. The Final Scientific Delta Claim remains "
        "pending Full Validation.",
        "",
    ]
    for title, field in (
        ("Selected Principle binding", None),
        ("Target-domain adaptation", "target_constraints"),
        ("Minimal faithful realization", "minimal_faithful_realization"),
        ("Principle-only closure attempt", "principle_only_closure"),
        ("Residual mechanism and adaptation gaps", "residual_musts"),
        ("Minimal necessary composition", "minimal_necessary_composition"),
        ("Core method changes", "core_method_changes"),
        ("Predicted mechanism changes", "mechanism_delta"),
        ("Failure conditions and applicability boundaries", "failure_and_applicability_boundaries"),
        ("Final Scientific Delta Claim", "final_scientific_delta_claim"),
        ("Claim-validation obligations", "claim_validation_obligations"),
        ("Assumption-constraint collisions", "assumption_constraint_collisions"),
        ("Causal repair DAG", "causal_repair_dag"),
        ("Target RMC and final intervention alignment", "intervention_alignment"),
        ("Target-only natural derivation", "target_only_natural_derivation"),
        ("Feasibility closure", "feasibility_closure"),
        ("Counterfactual necessity obligations", "counterfactual_necessity_obligations"),
    ):
        value = (
            {
                "problem_binding": packet["problem_binding"],
                "necessity_binding": packet["necessity_binding"],
                "root_cause_binding": packet["root_cause_binding"],
                "selected_principle_binding": packet["selected_principle_binding"],
            }
            if field is None
            else packet[field]
        )
        lines.extend(section(title, value))
    return "\n".join(lines).rstrip() + "\n"


def validate_final_method_view(text: Any, packet: dict[str, Any]) -> str:
    expected = render_final_method_view(packet)
    if text != expected:
        raise ValidationError(
            "final proposal must exactly match the deterministic Final Method packet rendering"
        )
    return text


def validate_final_method_packet(
    payload: Any,
    *,
    contract: dict[str, Any],
    problem_binding: dict[str, Any],
    necessity_binding: dict[str, Any],
    root_cause_binding: dict[str, Any],
    selected_principle: dict[str, Any],
    selected_principle_sha256: str,
    current_evidence_ids: set[str] | None = None,
    final_proposal_text: str | None = None,
) -> dict[str, Any]:
    """Validate Final Method identity, closure, references, and graph facts.

    Necessity, minimality, causal truth, and novelty strength remain reviewer
    judgments. This function checks only mechanically decidable structure and
    current bindings.
    """

    packet = _require_mapping(payload, "Final Method packet")
    _require_fields(packet, tuple(contract["required_fields"]), "Final Method packet")
    if packet["schema_version"] != contract.get("schema_version", 1):
        raise ValidationError("Final Method packet schema_version is invalid")
    _required_text(packet["final_method_id"], "Final Method packet.final_method_id")

    def exact_binding(field: str, fields_key: str, expected: dict[str, Any]) -> None:
        binding = _require_mapping(packet[field], f"Final Method packet.{field}")
        _require_fields(binding, tuple(contract[fields_key]), f"Final Method packet.{field}")
        if binding != expected:
            raise ValidationError(f"Final Method packet.{field} is stale or does not match accepted upstream state")

    exact_binding("problem_binding", "problem_binding_fields", problem_binding)
    exact_binding("necessity_binding", "necessity_binding_fields", necessity_binding)
    exact_binding("root_cause_binding", "root_cause_binding_fields", root_cause_binding)
    exact_binding(
        "selected_principle_binding",
        "selected_principle_binding_fields",
        {
            "principle_id": selected_principle["principle_id"],
            "principle_version": selected_principle["principle_version"],
            "selected_principle_sha256": selected_principle_sha256,
        },
    )

    causal_ids = set(_unique_string_values(selected_principle["causal_chain_ids"], "Selected Principle.causal_chain_ids"))
    rmc_ids = set(_unique_string_values(selected_principle["mechanism_change_ids"], "Selected Principle.mechanism_change_ids"))
    capability_ids = set(_unique_string_values(selected_principle["capability_ids"], "Selected Principle.capability_ids"))
    obligation_ids = set(_unique_string_values(selected_principle["obligation_ids"], "Selected Principle.obligation_ids"))
    activation_conditions = set(_unique_string_values(selected_principle["activation_conditions"], "Selected Principle.activation_conditions"))
    failure_conditions = set(_unique_string_values(selected_principle["failure_conditions"], "Selected Principle.failure_conditions"))
    assumption_ids = {
        str(item["assumption_id"])
        for item in _require_list(selected_principle, "accepted_assumptions", "Selected Principle", non_empty=False)
        if isinstance(item, dict) and isinstance(item.get("assumption_id"), str) and item["assumption_id"]
    }

    def items(field: str, fields_key: str, id_field: str, *, non_empty: bool) -> tuple[list[dict[str, Any]], set[str]]:
        raw_items = _require_list(packet, field, "Final Method packet", non_empty=non_empty)
        ids = _unique_ids(raw_items, id_field, f"Final Method packet.{field}")
        mapped: list[dict[str, Any]] = []
        for index, raw in enumerate(raw_items, 1):
            item = _require_mapping(raw, f"Final Method packet.{field} item {index}")
            _require_fields(item, tuple(contract[fields_key]), f"Final Method packet.{field} item {index}")
            mapped.append(item)
        return mapped, ids

    def refs(value: Any, label: str, known: set[str], *, non_empty: bool = True) -> set[str]:
        values = set(_unique_string_values(value, label, non_empty=non_empty))
        if not values <= known:
            raise ValidationError(f"{label} contains unknown references: {sorted(values - known)}")
        return values

    def evidence_refs(value: Any, label: str, *, non_empty: bool = True) -> set[str]:
        values = set(_unique_string_values(value, label, non_empty=non_empty))
        if current_evidence_ids is not None and not values <= current_evidence_ids:
            raise ValidationError(f"{label} cites Evidence outside the current formal context")
        return values

    constraints, constraint_ids = items(
        "target_constraints", "target_constraint_fields", "constraint_id", non_empty=True
    )
    target_source_ids = (
        {str(value) for value in necessity_binding["residual_failure_ids"]}
        | causal_ids | rmc_ids | capability_ids | obligation_ids
        | activation_conditions | failure_conditions
    )
    for index, constraint in enumerate(constraints, 1):
        _required_text(constraint["constraint"], f"target constraint {index}.constraint")
        refs(
            constraint["source_ref_ids"],
            f"target constraint {index}.source_ref_ids",
            target_source_ids,
        )
        evidence_refs(constraint["evidence_refs"], f"target constraint {index}.evidence_refs", non_empty=False)

    boundaries, boundary_ids = items(
        "failure_and_applicability_boundaries", "boundary_fields", "boundary_id", non_empty=True
    )
    boundary_by_id = {str(item["boundary_id"]): item for item in boundaries}
    for index, boundary in enumerate(boundaries, 1):
        if boundary["boundary_type"] not in set(contract["boundary_type_enum"]):
            raise ValidationError(f"boundary {index}.boundary_type is invalid")
        _required_text(boundary["boundary"], f"boundary {index}.boundary")
        _unique_string_values(boundary["source_refs"], f"boundary {index}.source_refs")

    claim = _require_mapping(packet["final_scientific_delta_claim"], "Final Scientific Delta Claim")
    _require_fields(claim, tuple(contract["final_scientific_delta_claim_fields"]), "Final Scientific Delta Claim")
    if claim["claim_status"] not in set(contract["final_scientific_delta_claim_status_enum"]):
        raise ValidationError("Final Scientific Delta Claim must remain pending Full Validation")
    claim_elements = _require_list(claim, "claim_elements", "Final Scientific Delta Claim", non_empty=True)
    claim_element_ids = _unique_ids(claim_elements, "claim_element_id", "Final Scientific Delta Claim.claim_elements")
    for index, raw in enumerate(claim_elements, 1):
        element = _require_mapping(raw, f"claim element {index}")
        _require_fields(element, tuple(contract["claim_element_fields"]), f"claim element {index}")
        _required_text(element["claim"], f"claim element {index}.claim")
        refs(element["causal_chain_ids"], f"claim element {index}.causal_chain_ids", causal_ids)
        refs(element["mechanism_change_ids"], f"claim element {index}.mechanism_change_ids", rmc_ids)
        refs(element["capability_ids"], f"claim element {index}.capability_ids", capability_ids)
        refs(element["obligation_ids"], f"claim element {index}.obligation_ids", obligation_ids)
        refs(element["boundary_refs"], f"claim element {index}.boundary_refs", boundary_ids)

    changes, change_ids = items(
        "core_method_changes", "core_method_change_fields", "core_method_change_id", non_empty=True
    )
    change_by_id = {str(item["core_method_change_id"]): item for item in changes}
    change_types = set(contract["core_method_change_type_enum"])
    for index, change in enumerate(changes, 1):
        _required_text(change["change"], f"core method change {index}.change")
        if change["change_type"] not in change_types:
            raise ValidationError(f"core method change {index}.change_type is invalid")
        _unique_string_values(change["causal_parent_refs"], f"core method change {index}.causal_parent_refs")
        refs(change["served_rmc_ids"], f"core method change {index}.served_rmc_ids", rmc_ids)
        refs(change["served_capability_ids"], f"core method change {index}.served_capability_ids", capability_ids)
        refs(change["served_obligation_ids"], f"core method change {index}.served_obligation_ids", obligation_ids)
    for index, element in enumerate(claim_elements, 1):
        refs(element["core_method_change_ids"], f"claim element {index}.core_method_change_ids", change_ids)

    for field, known in (
        ("causal_chain_ids", causal_ids),
        ("mechanism_change_ids", rmc_ids),
        ("capability_ids", capability_ids),
        ("obligation_ids", obligation_ids),
        ("core_method_change_ids", change_ids),
    ):
        covered = {
            str(value)
            for element in claim_elements
            for value in element[field]
        }
        if covered != known:
            raise ValidationError(
                f"Final Scientific Delta Claim does not exactly cover current {field}"
            )

    realization = _require_mapping(packet["minimal_faithful_realization"], "minimal faithful realization")
    _require_fields(realization, tuple(contract["minimal_faithful_realization_fields"]), "minimal faithful realization")
    if realization["selected_intervention"] != selected_principle["intervention"]:
        raise ValidationError("minimal faithful realization drifts from the Selected Principle intervention")
    for field in ("target_realization", "fidelity_rationale"):
        _required_text(realization[field], f"minimal faithful realization.{field}")
    _unique_string_values(realization["reused_implementation_machinery"], "minimal faithful realization.reused_implementation_machinery", non_empty=False)
    realization_change_ids = refs(realization["core_method_change_ids"], "minimal faithful realization.core_method_change_ids", change_ids)
    expected_realization_changes = {
        change_id for change_id, change in change_by_id.items()
        if change["change_type"] == "PRINCIPLE_REALIZATION"
    }
    if realization_change_ids != expected_realization_changes or not realization_change_ids:
        raise ValidationError("minimal faithful realization must identify every and only Principle-realization core change")

    closures, closure_ids = items(
        "principle_only_closure", "principle_only_closure_fields", "closure_id", non_empty=True
    )
    expected_subjects = {
        *(('CAUSAL_CHAIN', value) for value in causal_ids),
        *(('RMC', value) for value in rmc_ids),
        *(('CAPABILITY', value) for value in capability_ids),
        *(('OBLIGATION', value) for value in obligation_ids),
        *(('ACTIVATION_CONDITION', value) for value in activation_conditions),
        *(('FAILURE_CONDITION', value) for value in failure_conditions),
        *(
            ('APPLICABILITY_BOUNDARY', boundary_id)
            for boundary_id, boundary in boundary_by_id.items()
            if boundary["boundary_type"] == "APPLICABILITY_BOUNDARY"
        ),
    }
    actual_subjects: set[tuple[str, str]] = set()
    closure_by_id: dict[str, dict[str, Any]] = {}
    for index, closure in enumerate(closures, 1):
        subject_type = closure["subject_type"]
        subject_id = _required_text(closure["subject_id"], f"closure {index}.subject_id")
        if subject_type not in set(contract["principle_only_closure_subject_enum"]):
            raise ValidationError(f"closure {index}.subject_type is invalid")
        if closure["status"] not in set(contract["principle_only_closure_status_enum"]):
            raise ValidationError(f"closure {index}.status is invalid")
        _required_text(closure["predicted_mechanism_change"], f"closure {index}.predicted_mechanism_change")
        _required_text(closure["rationale"], f"closure {index}.rationale")
        residual_refs = set(_unique_string_values(closure["residual_must_ids"], f"closure {index}.residual_must_ids", non_empty=False))
        if (closure["status"] == "RESIDUAL_GAP") != bool(residual_refs):
            raise ValidationError("closure residual status and Residual MUST references are inconsistent")
        key = (str(subject_type), subject_id)
        if key in actual_subjects:
            raise ValidationError("principle-only closure contains duplicate subject coverage")
        actual_subjects.add(key)
        closure_by_id[str(closure["closure_id"])] = closure
    if actual_subjects != expected_subjects:
        raise ValidationError("principle-only closure does not exactly cover the current causal/RMC/capability/obligation/condition/boundary set")

    residual_musts, residual_must_ids = items(
        "residual_musts", "residual_must_fields", "residual_must_id", non_empty=False
    )
    residual_by_id = {str(item["residual_must_id"]): item for item in residual_musts}
    for index, must in enumerate(residual_musts, 1):
        closure_id = str(must["closure_id"])
        if closure_id not in closure_by_id or closure_by_id[closure_id]["status"] != "RESIDUAL_GAP":
            raise ValidationError(f"Residual MUST {index} does not originate from a RESIDUAL_GAP closure")
        _required_text(must["gap"], f"Residual MUST {index}.gap")
        _required_text(must["acceptance_condition"], f"Residual MUST {index}.acceptance_condition")
    for closure in closures:
        refs(closure["residual_must_ids"], f"closure {closure['closure_id']}.residual_must_ids", residual_must_ids, non_empty=False)
        for must_id in closure["residual_must_ids"]:
            if str(residual_by_id[str(must_id)]["closure_id"]) != str(closure["closure_id"]):
                raise ValidationError("Residual MUST and closure references are not reciprocal")

    collisions, _ = items(
        "assumption_constraint_collisions", "collision_fields", "collision_id", non_empty=False
    )
    for index, collision in enumerate(collisions, 1):
        if str(collision["assumption_id"]) not in assumption_ids:
            raise ValidationError(f"collision {index} references an unknown Selected Principle assumption")
        if str(collision["target_constraint_id"]) not in constraint_ids:
            raise ValidationError(f"collision {index} references an unknown Target Constraint")
        if collision["disposition"] not in set(contract["collision_disposition_enum"]):
            raise ValidationError(f"collision {index} has no valid disposition")
        _required_text(collision["rationale"], f"collision {index}.rationale")
        collision_musts = refs(collision["residual_must_ids"], f"collision {index}.residual_must_ids", residual_must_ids, non_empty=False)
        if (collision["disposition"] == "RESIDUAL_GAP") != bool(collision_musts):
            raise ValidationError("collision disposition and Residual MUST references are inconsistent")

    composition, support_ids = items(
        "minimal_necessary_composition", "composition_fields", "support_id", non_empty=False
    )
    support_change_ids: set[str] = set()
    served_residual_must_ids: set[str] = set()
    support_by_id: dict[str, dict[str, Any]] = {}
    for index, support in enumerate(composition, 1):
        served_residual_must_ids.update(
            refs(
                support["residual_must_ids"],
                f"support {index}.residual_must_ids",
                residual_must_ids,
            )
        )
        for field in ("mechanism", "integration_interface", "assumption_compatibility"):
            _required_text(support[field], f"support {index}.{field}")
        _unique_string_values(support["activation_conditions"], f"support {index}.activation_conditions")
        linked_changes = refs(support["core_method_change_ids"], f"support {index}.core_method_change_ids", change_ids)
        if any(change_by_id[change_id]["change_type"] != "RESIDUAL_SUPPORT" for change_id in linked_changes):
            raise ValidationError("support composition may reference only RESIDUAL_SUPPORT core changes")
        support_change_ids.update(linked_changes)
        support_by_id[str(support["support_id"])] = support
    expected_support_changes = {
        change_id for change_id, change in change_by_id.items()
        if change["change_type"] == "RESIDUAL_SUPPORT"
    }
    if support_change_ids != expected_support_changes:
        raise ValidationError("every Residual-support core change must belong to minimal necessary composition")
    if served_residual_must_ids != residual_must_ids:
        raise ValidationError("minimal necessary composition must cover every Residual MUST")
    if not residual_must_ids and (composition or expected_support_changes):
        raise ValidationError("zero Residual MUST closure requires empty composition and no support changes")

    validation_obligations, validation_obligation_ids = items(
        "claim_validation_obligations", "claim_validation_obligation_fields", "validation_obligation_id", non_empty=True
    )
    obligation_claim_ids: list[str] = []
    for index, obligation in enumerate(validation_obligations, 1):
        claim_id = str(obligation["claim_element_id"])
        if claim_id not in claim_element_ids:
            raise ValidationError(f"claim-validation obligation {index} references an unknown claim element")
        obligation_claim_ids.append(claim_id)
        for field in (
            "predicted_mechanism_change", "observed_mechanism_change_required",
            "discriminating_evidence_required", "performance_consequence_required",
            "falsifying_pattern",
        ):
            _required_text(obligation[field], f"claim-validation obligation {index}.{field}")
    if set(obligation_claim_ids) != claim_element_ids:
        raise ValidationError("every Final Scientific Delta claim element requires a claim-validation obligation")

    dag = _require_mapping(packet["causal_repair_dag"], "causal repair DAG")
    _require_fields(dag, ("nodes", "edges"), "causal repair DAG")
    nodes = _require_list(dag, "nodes", "causal repair DAG", non_empty=True)
    node_ids = _unique_ids(nodes, "node_id", "causal repair DAG.nodes")
    node_by_id: dict[str, dict[str, Any]] = {}
    core_node_by_change: dict[str, str] = {}
    for index, raw in enumerate(nodes, 1):
        node = _require_mapping(raw, f"DAG node {index}")
        _require_fields(node, tuple(contract["causal_dag_node_fields"]), f"DAG node {index}")
        node_type = node["node_type"]
        ref_id = _required_text(node["ref_id"], f"DAG node {index}.ref_id")
        if node_type not in set(contract["causal_dag_node_type_enum"]):
            raise ValidationError(f"DAG node {index}.node_type is invalid")
        if node_type == "PRIMARY_ROOT_CAUSE" and ref_id not in causal_ids:
            raise ValidationError("DAG Primary Root Cause node references an unknown accepted primary chain")
        if node_type == "TARGET_CONSTRAINT" and ref_id not in constraint_ids:
            raise ValidationError("DAG Target Constraint node references an unknown constraint")
        if node_type == "CORE_METHOD_CHANGE":
            if ref_id not in change_ids or ref_id in core_node_by_change:
                raise ValidationError("DAG core node does not uniquely resolve a core method change")
            core_node_by_change[ref_id] = str(node["node_id"])
        if node_type == "INCOMPATIBILITY":
            _require_fields(node, ("introduced_by_core_method_change_id", "original_causal_requirement_ref"), f"DAG incompatibility node {index}")
            if str(node["introduced_by_core_method_change_id"]) not in change_ids:
                raise ValidationError("DAG incompatibility has an unknown earlier retained design")
            if str(node["original_causal_requirement_ref"]) not in causal_ids | constraint_ids | rmc_ids:
                raise ValidationError("DAG incompatibility has an unknown original causal requirement")
        node_by_id[str(node["node_id"])] = node
    if set(core_node_by_change) != change_ids:
        raise ValidationError("causal repair DAG must contain exactly one node for every core method change")

    edges = _require_list(dag, "edges", "causal repair DAG", non_empty=True)
    _unique_ids(edges, "edge_id", "causal repair DAG.edges")
    outgoing: dict[str, set[str]] = {node_id: set() for node_id in node_ids}
    incoming: dict[str, set[str]] = {node_id: set() for node_id in node_ids}
    for index, raw in enumerate(edges, 1):
        edge = _require_mapping(raw, f"DAG edge {index}")
        _require_fields(edge, tuple(contract["causal_dag_edge_fields"]), f"DAG edge {index}")
        source = str(edge["from_node_id"])
        target = str(edge["to_node_id"])
        if source not in node_ids or target not in node_ids or source == target:
            raise ValidationError("DAG edge references a missing node or self-loop")
        if str(edge["validation_obligation_id"]) not in validation_obligation_ids:
            raise ValidationError("every scientific DAG edge requires a claim-validation obligation")
        outgoing[source].add(target)
        incoming[target].add(source)
    indegree = {node_id: len(parents) for node_id, parents in incoming.items()}
    queue = [node_id for node_id, degree in indegree.items() if degree == 0]
    visited: list[str] = []
    while queue:
        node_id = queue.pop()
        visited.append(node_id)
        for child in outgoing[node_id]:
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    if len(visited) != len(node_ids):
        raise ValidationError("causal repair DAG must be acyclic")
    if any(not incoming[node_id] and not outgoing[node_id] for node_id in node_ids):
        raise ValidationError("causal repair DAG contains a structural orphan")
    for change_id, node_id in core_node_by_change.items():
        parent_nodes = [node_by_id[parent_id] for parent_id in incoming[node_id]]
        if not parent_nodes or any(parent["node_type"] not in {"PRIMARY_ROOT_CAUSE", "TARGET_CONSTRAINT", "INCOMPATIBILITY"} for parent in parent_nodes):
            raise ValidationError("every core method node requires only legal causal parents")
        parent_refs = {str(parent["ref_id"]) for parent in parent_nodes}
        if parent_refs != set(change_by_id[change_id]["causal_parent_refs"]):
            raise ValidationError("core method change causal_parent_refs do not match the DAG")
    for node_id, node in node_by_id.items():
        if node["node_type"] != "INCOMPATIBILITY":
            continue
        earlier_change = str(node["introduced_by_core_method_change_id"])
        if core_node_by_change[earlier_change] not in incoming[node_id]:
            raise ValidationError("DAG incompatibility is not caused by its declared earlier retained design")

    delta = _require_mapping(packet["mechanism_delta"], "mechanism delta")
    _require_fields(delta, tuple(contract["mechanism_delta_fields"]), "mechanism delta")
    for field in ("existing_causal_or_computational_relation", "new_causal_or_computational_relation", "intervention_change"):
        _required_text(delta[field], f"mechanism delta.{field}")
    if (
        delta["existing_causal_or_computational_relation"].strip()
        == delta["new_causal_or_computational_relation"].strip()
    ):
        raise ValidationError("mechanism delta Existing and New relations must differ")
    priors = _require_list(delta, "nearest_prior_separation", "mechanism delta", non_empty=True)
    _unique_ids(priors, "prior_id", "mechanism delta.nearest_prior_separation")
    for index, raw in enumerate(priors, 1):
        prior = _require_mapping(raw, f"nearest prior {index}")
        _require_fields(prior, tuple(contract["nearest_prior_separation_fields"]), f"nearest prior {index}")
        evidence_refs(prior["evidence_refs"], f"nearest prior {index}.evidence_refs")
        for field in ("existing_intervention", "existing_mechanism_or_relation", "final_separation"):
            _required_text(prior[field], f"nearest prior {index}.{field}")

    alignments, _ = items(
        "intervention_alignment", "intervention_alignment_fields", "alignment_id", non_empty=True
    )
    aligned_rmcs: set[str] = set()
    aligned_change_ids: set[str] = set()
    for index, alignment in enumerate(alignments, 1):
        rmc_id = str(alignment["rmc_id"])
        if rmc_id not in rmc_ids or rmc_id in aligned_rmcs:
            raise ValidationError("Final intervention alignment has an unknown or duplicate RMC")
        aligned_rmcs.add(rmc_id)
        if alignment["selected_intervention"] != selected_principle["intervention"]:
            raise ValidationError("Final intervention alignment drifts from the Selected Principle")
        if alignment.get("source_intervention") is not None and not isinstance(alignment["source_intervention"], str):
            raise ValidationError("Final intervention alignment source_intervention is invalid")
        aligned_change_ids.update(
            refs(
                alignment["final_computational_change_ids"],
                f"alignment {index}.final_computational_change_ids",
                change_ids,
            )
        )
        _required_text(alignment["rationale"], f"alignment {index}.rationale")
    if aligned_rmcs != rmc_ids:
        raise ValidationError("Final intervention alignment must cover every Selected Principle RMC")
    if aligned_change_ids != change_ids:
        raise ValidationError("Final intervention alignment must cover every core method change")

    derivation = _require_mapping(packet["target_only_natural_derivation"], "target-only natural derivation")
    _require_fields(derivation, tuple(contract["natural_derivation_fields"]), "target-only natural derivation")
    if derivation["source_story_removed"] is not True:
        raise ValidationError("target-only natural derivation must explicitly remove the Source story")
    if set(_unique_string_values(derivation["residual_failure_ids"], "natural derivation.residual_failure_ids")) != set(necessity_binding["residual_failure_ids"]):
        raise ValidationError("target-only natural derivation has stale Residual Failure bindings")
    if refs(derivation["root_cause_refs"], "natural derivation.root_cause_refs", causal_ids) != causal_ids:
        raise ValidationError("target-only natural derivation must cover every primary Root Cause")
    if refs(derivation["rmc_ids"], "natural derivation.rmc_ids", rmc_ids) != rmc_ids:
        raise ValidationError("target-only natural derivation must cover every RMC")
    if refs(derivation["target_constraint_ids"], "natural derivation.target_constraint_ids", constraint_ids) != constraint_ids:
        raise ValidationError("target-only natural derivation must cover every Target Constraint")
    if refs(derivation["core_method_change_ids"], "natural derivation.core_method_change_ids", change_ids) != change_ids:
        raise ValidationError("target-only natural derivation must cover every core method change")
    _required_text(derivation["derivation"], "target-only natural derivation.derivation")

    feasibility = _require_mapping(packet["feasibility_closure"], "feasibility closure")
    _require_fields(feasibility, tuple(contract["feasibility_closure_fields"]), "feasibility closure")
    _unique_string_values(feasibility["supported_conditions"], "feasibility closure.supported_conditions")
    debts = _require_list(feasibility, "unresolved_feasibility_debts", "feasibility closure", non_empty=False)
    debt_ids = _unique_ids(debts, "debt_id", "feasibility closure.unresolved_feasibility_debts")
    restrictions = _require_list(feasibility, "claim_restrictions", "feasibility closure", non_empty=False)
    restriction_ids = _unique_ids(restrictions, "restriction_id", "feasibility closure.claim_restrictions")
    restriction_by_id: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(restrictions, 1):
        restriction = _require_mapping(raw, f"claim restriction {index}")
        _require_fields(restriction, tuple(contract["claim_restriction_fields"]), f"claim restriction {index}")
        unsupported_fields = set(restriction) - set(contract["claim_restriction_fields"])
        if unsupported_fields:
            raise ValidationError(f"claim restriction {index} contains unsupported fields: {sorted(unsupported_fields)}")
        restricted_claim_ids = refs(
            restriction["claim_element_ids"],
            f"claim restriction {index}.claim_element_ids",
            claim_element_ids,
        )
        boundary_id = _required_text(restriction["boundary_id"], f"claim restriction {index}.boundary_id")
        if boundary_id not in boundary_by_id:
            raise ValidationError(f"claim restriction {index}.boundary_id references an unknown boundary")
        if boundary_by_id[boundary_id]["boundary_type"] != "CLAIM_RESTRICTION":
            raise ValidationError(f"claim restriction {index}.boundary_id must reference a CLAIM_RESTRICTION boundary")
        for claim_element in claim_elements:
            if str(claim_element["claim_element_id"]) in restricted_claim_ids and boundary_id not in {
                str(value) for value in claim_element["boundary_refs"]
            }:
                raise ValidationError("claim restriction boundary must be referenced by every restricted claim element")
        restriction_by_id[str(restriction["restriction_id"])] = restriction
    restriction_boundary_ids = {
        str(restriction["boundary_id"]) for restriction in restriction_by_id.values()
    }
    for claim_element in claim_elements:
        for boundary_id in claim_element["boundary_refs"]:
            if boundary_by_id[str(boundary_id)]["boundary_type"] == "CLAIM_RESTRICTION" and str(boundary_id) not in restriction_boundary_ids:
                raise ValidationError("Claim element references a CLAIM_RESTRICTION boundary without a formal claim restriction")
    orphan_claim_restriction_boundaries = {
        boundary_id
        for boundary_id, boundary in boundary_by_id.items()
        if boundary["boundary_type"] == "CLAIM_RESTRICTION"
    } - restriction_boundary_ids
    if orphan_claim_restriction_boundaries:
        raise ValidationError("CLAIM_RESTRICTION boundary is not referenced by a formal claim restriction")
    fatal_debt_ids: set[str] = set()
    for index, raw in enumerate(debts, 1):
        debt = _require_mapping(raw, f"feasibility debt {index}")
        _require_fields(debt, tuple(contract["feasibility_debt_fields"]), f"feasibility debt {index}")
        for field in ("dimension", "debt", "repair_disposition", "claim_restriction_disposition"):
            _required_text(debt[field], f"feasibility debt {index}.{field}")
        if not isinstance(debt["fatal"], bool):
            raise ValidationError(f"feasibility debt {index}.fatal must be boolean")
        evidence_refs(debt["evidence_refs"], f"feasibility debt {index}.evidence_refs")
        restriction_refs = refs(debt["restriction_ids"], f"feasibility debt {index}.restriction_ids", restriction_ids, non_empty=False)
        evidence_refs(debt["excluded_recovery_evidence_refs"], f"feasibility debt {index}.excluded_recovery_evidence_refs", non_empty=False)
        if not debt["fatal"] and not restriction_refs:
            raise ValidationError("every nonfatal unresolved feasibility debt requires an explicit claim restriction")
        if debt["fatal"]:
            fatal_debt_ids.add(str(debt["debt_id"]))
        for restriction_id in restriction_refs:
            if str(debt["debt_id"]) not in {
                str(value) for value in restriction_by_id[restriction_id]["debt_ids"]
            }:
                raise ValidationError(
                    "feasibility debt and claim restriction references are not reciprocal"
                )
    for restriction_id, restriction in restriction_by_id.items():
        linked_debts = refs(restriction["debt_ids"], f"claim restriction {restriction_id}.debt_ids", debt_ids)
        if any(restriction_id not in set(debt["restriction_ids"]) for debt in debts if str(debt["debt_id"]) in linked_debts):
            raise ValidationError("feasibility debt and claim restriction references are not reciprocal")
    fatality = feasibility["fatality_disposition"]
    if fatality not in set(contract["feasibility_fatality_enum"]):
        raise ValidationError("feasibility closure.fatality_disposition is invalid")
    if (fatality == "NO_FATAL_DEBT") != (not fatal_debt_ids):
        raise ValidationError("feasibility fatality disposition conflicts with unresolved fatal debts")
    if fatality == "FATAL_UNRECOVERABLE":
        for debt in debts:
            if not debt["fatal"]:
                continue
            if (
                debt["repair_disposition"] != "EVIDENCE_EXCLUDED"
                or debt["claim_restriction_disposition"] != "CANNOT_PRESERVE_CORE_SEED"
                or not debt["excluded_recovery_evidence_refs"]
            ):
                raise ValidationError("fatal-unrecoverable debt lacks Evidence-excluded repair/restriction closure")

    counterfactuals, _ = items(
        "counterfactual_necessity_obligations", "counterfactual_obligation_fields", "counterfactual_obligation_id", non_empty=bool(composition)
    )
    counterfactual_support_ids: set[str] = set()
    for index, obligation in enumerate(counterfactuals, 1):
        support_id = str(obligation["support_id"])
        if support_id not in support_ids or support_id in counterfactual_support_ids:
            raise ValidationError("counterfactual obligation has an unknown or duplicate support")
        counterfactual_support_ids.add(support_id)
        _required_text(obligation["removal_condition"], f"counterfactual obligation {index}.removal_condition")
        failed_closure_ids = refs(
            obligation["expected_failed_closure_ids"],
            f"counterfactual obligation {index}.expected_failed_closure_ids",
            closure_ids,
        )
        expected_failed_closure_ids = {
            str(residual_by_id[str(must_id)]["closure_id"])
            for must_id in support_by_id[support_id]["residual_must_ids"]
        }
        if failed_closure_ids != expected_failed_closure_ids:
            raise ValidationError(
                "counterfactual obligation must target the closure served by its support"
            )
        _required_text(obligation["discriminating_consequence"], f"counterfactual obligation {index}.discriminating_consequence")
        if obligation["evidence_status"] not in set(contract["counterfactual_evidence_status_enum"]):
            raise ValidationError("unexecuted counterfactual must remain a future obligation, not Evidence")
    if counterfactual_support_ids != support_ids:
        raise ValidationError("every retained support requires exactly one counterfactual necessity obligation")

    if final_proposal_text is not None:
        validate_final_method_view(final_proposal_text, packet)
    return {
        "packet": packet,
        "final_method_id": str(packet["final_method_id"]),
        "fatality_disposition": str(fatality),
        "fatal_debt_ids": sorted(fatal_debt_ids),
        "current_evidence_ids": sorted(current_evidence_ids or set()),
    }


def validate_necessity_closure(
    payload: Any,
    *,
    contract: dict[str, Any],
    run_id: str,
    problem_version: dict[str, Any],
    current_evidence_ids: set[str],
) -> dict[str, Any]:
    """Validate the pre-RCA Necessity artifact mechanically.

    Scientific judgments about whether a repair is genuinely simple, applicable,
    or sufficient remain the independent problem reviewer's responsibility.
    """

    closure = _require_mapping(payload, "Necessity Closure")
    _require_fields(closure, tuple(contract["required_fields"]), "Necessity Closure")
    if closure["schema_version"] != contract.get("schema_version", 1):
        raise ValidationError("Necessity Closure schema_version is invalid")
    if closure["run_id"] != run_id:
        raise ValidationError("Necessity Closure run_id does not match the active run")
    _required_text(closure["necessity_id"], "Necessity Closure.necessity_id")

    binding = _require_mapping(closure["problem_binding"], "Necessity Closure.problem_binding")
    _require_fields(
        binding,
        tuple(contract["problem_binding_fields"]),
        "Necessity Closure.problem_binding",
    )
    expected_binding = {
        "problem_id": problem_version["problem_id"],
        "problem_version": problem_version["version"],
        "problem_contract_sha256": problem_version["contract_sha256"],
        "evidence_capsule_sha256": problem_version["evidence_capsule_sha256"],
    }
    if binding != expected_binding:
        raise ValidationError("Necessity Closure problem_binding does not match the active accepted Problem")

    def evidence_refs(value: Any, label: str) -> list[str]:
        refs = _unique_string_values(value, label)
        unknown = set(refs) - current_evidence_ids
        if unknown:
            raise ValidationError(f"{label} contains Evidence outside the current formal context: {sorted(unknown)}")
        return refs

    failures = _require_list(closure, "active_failures", "Necessity Closure", non_empty=True)
    failure_ids = _unique_ids(failures, "failure_id", "Necessity Closure.active_failures")
    for index, raw in enumerate(failures, 1):
        failure = _require_mapping(raw, f"Necessity active failure {index}")
        _require_fields(
            failure,
            tuple(contract["active_failure_fields"]),
            f"Necessity active failure {index}",
        )
        for field in ("condition", "observable_failure", "consequence"):
            _required_text(failure[field], f"Necessity active failure {index}.{field}")
        evidence_refs(failure["evidence_refs"], f"Necessity active failure {index}.evidence_refs")

    if not isinstance(closure["operating_envelope"], (str, list, dict)) or closure[
        "operating_envelope"
    ] in ("", [], {}):
        raise ValidationError("Necessity Closure.operating_envelope must be non-empty")

    residuals = _require_list(
        closure, "residual_failure_envelope", "Necessity Closure", non_empty=False
    )
    residual_ids = _unique_ids(
        residuals, "residual_failure_id", "Necessity Closure.residual_failure_envelope"
    )
    residual_by_id: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(residuals, 1):
        residual = _require_mapping(raw, f"Necessity residual failure {index}")
        _require_fields(
            residual,
            tuple(contract["residual_failure_fields"]),
            f"Necessity residual failure {index}",
        )
        source_failures = set(
            _unique_string_values(
                residual["source_failure_ids"],
                f"Necessity residual failure {index}.source_failure_ids",
            )
        )
        if not source_failures <= failure_ids:
            raise ValidationError(f"Necessity residual failure {index} references an unknown active failure")
        for field in ("condition", "observable_failure", "consequence"):
            _required_text(residual[field], f"Necessity residual failure {index}.{field}")
        evidence_refs(
            residual["evidence_refs"], f"Necessity residual failure {index}.evidence_refs"
        )
        residual_by_id[str(residual["residual_failure_id"])] = residual

    repairs = _require_list(
        closure, "simple_repair_assessments", "Necessity Closure", non_empty=True
    )
    repair_ids = _unique_ids(
        repairs, "assessment_id", "Necessity Closure.simple_repair_assessments"
    )
    conclusions = set(contract["coverage_conclusion_enum"])
    covered_failure_ids: set[str] = set()
    residual_requiring_assessments: set[str] = set()
    for index, raw in enumerate(repairs, 1):
        repair = _require_mapping(raw, f"Simple Repair assessment {index}")
        _require_fields(
            repair,
            tuple(contract["simple_repair_assessment_fields"]),
            f"Simple Repair assessment {index}",
        )
        _required_text(repair["repair"], f"Simple Repair assessment {index}.repair")
        applicable = set(
            _unique_string_values(
                repair["applicable_failure_ids"],
                f"Simple Repair assessment {index}.applicable_failure_ids",
            )
        )
        if not applicable <= failure_ids:
            raise ValidationError(f"Simple Repair assessment {index} references an unknown active failure")
        if repair["preserves_core_causal_or_computational_relation"] is not True:
            raise ValidationError(
                f"Simple Repair assessment {index} is not a Simple Repair because it changes the core relation"
            )
        evidence_refs(
            repair["evidence_refs"], f"Simple Repair assessment {index}.evidence_refs"
        )
        if not isinstance(repair["coverage_boundary"], (str, list, dict)) or repair[
            "coverage_boundary"
        ] in ("", [], {}):
            raise ValidationError(f"Simple Repair assessment {index}.coverage_boundary must be non-empty")
        conclusion = repair["coverage_conclusion"]
        if conclusion not in conclusions:
            raise ValidationError(f"Simple Repair assessment {index}.coverage_conclusion is invalid")
        referenced_residuals = set(
            _unique_string_values(
                repair["residual_failure_ids"],
                f"Simple Repair assessment {index}.residual_failure_ids",
                non_empty=False,
            )
        )
        if not referenced_residuals <= residual_ids:
            raise ValidationError(f"Simple Repair assessment {index} references an unknown residual failure")
        if conclusion == "FULL_COVERAGE":
            if referenced_residuals:
                raise ValidationError("FULL_COVERAGE cannot retain residual failure references")
            covered_failure_ids.update(applicable)
        elif conclusion in {"PARTIAL_COVERAGE", "NO_COVERAGE"}:
            if not referenced_residuals:
                raise ValidationError(
                    f"{conclusion} requires an explicit Residual Failure Envelope reference"
                )
            residual_requiring_assessments.add(str(repair["assessment_id"]))

    for residual_id, residual in residual_by_id.items():
        assessment_refs = set(
            _unique_string_values(
                residual["uncovered_by_repair_assessment_ids"],
                f"Necessity residual failure {residual_id}.uncovered_by_repair_assessment_ids",
            )
        )
        if not assessment_refs <= repair_ids:
            raise ValidationError(f"Necessity residual failure {residual_id} references an unknown repair assessment")
    if residual_requiring_assessments and not residuals:
        raise ValidationError("partial or uncovered repair coverage requires a Residual Failure Envelope")

    disposition = closure["problem_identity_disposition"]
    if disposition not in set(contract["problem_identity_disposition_enum"]):
        raise ValidationError("Necessity Closure.problem_identity_disposition is invalid")
    if disposition in {"SAME_ACCEPTED_PROBLEM", "REDEFINES_PROBLEM"} and not residuals:
        raise ValidationError(f"{disposition} requires an explicit Residual Failure Envelope")
    if disposition == "NO_RESIDUAL_FAILURE":
        if residuals or covered_failure_ids != failure_ids:
            raise ValidationError(
                "NO_RESIDUAL_FAILURE requires every active failure to be fully covered and no residual envelope"
            )

    provenance = _require_mapping(closure["analysis_provenance"], "Necessity Closure.analysis_provenance")
    _require_fields(
        provenance,
        ("author_role", "created_at", "analysis_modes", "source_artifact_ids"),
        "Necessity Closure.analysis_provenance",
    )
    modes = set(
        _unique_string_values(
            provenance["analysis_modes"], "Necessity Closure.analysis_provenance.analysis_modes"
        )
    )
    if not modes <= {"EXISTING_FORMAL_EVIDENCE", "FORMAL_ANALYSIS", "READ_ONLY_EXISTING_DATA_ANALYSIS"}:
        raise ValidationError("Necessity Closure declares an analysis mode outside the pre-RCA Evidence boundary")
    evidence_refs(
        provenance["source_artifact_ids"],
        "Necessity Closure.analysis_provenance.source_artifact_ids",
    )
    return closure


def validate_necessity_verdict(
    payload: Any,
    *,
    contract: dict[str, Any],
    run_id: str,
    request_id: str,
    artifact_bindings: dict[str, str],
    closure: dict[str, Any],
    reviewed_closure_sha256: str,
    problem_contract_sha256: str,
    evidence_capsule_sha256: str,
) -> dict[str, Any]:
    """Validate reviewer identity/bindings and the fixed Necessity decision contract."""

    verdict = _require_mapping(payload, "Necessity Verdict")
    _require_fields(verdict, tuple(contract["required_fields"]), "Necessity Verdict")
    if verdict["schema_version"] != contract.get("schema_version", 1):
        raise ValidationError("Necessity Verdict schema_version is invalid")
    _validate_review_binding(
        verdict,
        label="Necessity Verdict",
        request_id=request_id,
        reviewer=None,
        verdict_id=None,
        decision=None,
        artifact_bindings=artifact_bindings,
    )
    if verdict["run_id"] != run_id or verdict["necessity_id"] != closure["necessity_id"]:
        raise ValidationError("Necessity Verdict does not identify the active run and closure")
    expected_hashes = {
        "reviewed_closure_sha256": reviewed_closure_sha256,
        "problem_contract_sha256": problem_contract_sha256,
        "evidence_capsule_sha256": evidence_capsule_sha256,
    }
    for field, expected in expected_hashes.items():
        _require_sha256(verdict[field], f"Necessity Verdict.{field}")
        if verdict[field] != expected:
            raise ValidationError(f"Necessity Verdict.{field} does not match the live artifact")
    decision = verdict["decision"]
    if decision not in _NECESSITY_DECISIONS or decision not in set(contract["decision_enum"]):
        raise ValidationError("Necessity Verdict decision is invalid")
    expected_disposition = {
        "FULLY_COVERED": "NO_RESIDUAL_FAILURE",
        "RESIDUAL_SAME_PROBLEM": "SAME_ACCEPTED_PROBLEM",
        "RESIDUAL_REDEFINES_PROBLEM": "REDEFINES_PROBLEM",
        "UNRESOLVED": "UNRESOLVED",
    }[decision]
    if closure["problem_identity_disposition"] != expected_disposition:
        raise ValidationError("Necessity Verdict conflicts with the reviewed problem-identity disposition")
    _require_string_list(verdict["reasons"], "Necessity Verdict.reasons", non_empty=True)
    issues = _require_list(verdict, "issues", "Necessity Verdict", non_empty=False)
    blocking = False
    for index, raw in enumerate(issues, 1):
        issue = _require_mapping(raw, f"Necessity Verdict issue {index}")
        _require_fields(issue, ("issue_id", "severity", "message"), f"Necessity Verdict issue {index}")
        if issue["severity"] not in {"BLOCKING", "NON_BLOCKING"}:
            raise ValidationError(f"Necessity Verdict issue {index}.severity is invalid")
        blocking = blocking or issue["severity"] == "BLOCKING"
    rubrics = (
        "failure_reality",
        "operating_envelope_fidelity",
        "simple_repair_coverage",
        "residual_failure_fidelity",
        "problem_identity_fidelity",
        "evidence_sufficiency",
    )
    for field in rubrics:
        if verdict[field] not in {"PASS", "FAIL", "UNCERTAIN"}:
            raise ValidationError(f"Necessity Verdict.{field} must be PASS, FAIL, or UNCERTAIN")
    if decision != "UNRESOLVED" and (blocking or any(verdict[field] != "PASS" for field in rubrics)):
        raise ValidationError(f"{decision} requires all Necessity rubrics PASS and no BLOCKING issue")
    if decision == "UNRESOLVED" and verdict["evidence_sufficiency"] == "PASS":
        raise ValidationError("UNRESOLVED requires insufficient or uncertain Evidence")
    return verdict


def validate_root_cause_analysis(
    payload: Any,
    *,
    run_id: str,
    problem_contract_sha256: str,
    evidence_capsule_sha256: str,
    active_problem_id: str | None = None,
    formal_evidence_sources: dict[str, str] | None = None,
    necessity_binding: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate the executable 1a-2b diagnosis handoff.

    This is deliberately a Type-A validator: it checks structure, bindings and
    referential integrity. Whether a proposed causal chain is scientifically
    adequate remains the independent Root-Cause Gate's judgment.
    """
    analysis = _require_mapping(payload, "root-cause analysis")
    _require_fields(
        analysis,
        (
            "schema_version",
            "run_id",
            "analysis_id",
            "problem_id",
            "problem_contract_sha256",
            "evidence_capsule_sha256",
            "necessity_binding",
            "failure_observations",
            "phenomenon_clusters",
            "causal_depth_traces",
            "causal_chains",
            "primary_causal_chain_ids",
            "unresolved_questions",
            "analysis_provenance",
        ),
        "root-cause analysis",
    )
    if analysis["schema_version"] != 1:
        raise ValidationError("root-cause analysis schema_version must be 1")
    if analysis["run_id"] != run_id:
        raise ValidationError("root-cause analysis run_id does not match the active run")
    if analysis["problem_contract_sha256"] != problem_contract_sha256:
        raise ValidationError("root-cause analysis is not bound to the current problem contract")
    if analysis["evidence_capsule_sha256"] != evidence_capsule_sha256:
        raise ValidationError("root-cause analysis is not bound to the current evidence capsule")
    _require_sha256(analysis["problem_contract_sha256"], "problem_contract_sha256")
    _require_sha256(analysis["evidence_capsule_sha256"], "evidence_capsule_sha256")
    if active_problem_id is not None and analysis["problem_id"] != active_problem_id:
        raise ValidationError("root-cause analysis problem_id does not match the active accepted problem")
    if necessity_binding is not None:
        actual_necessity = _require_mapping(
            analysis["necessity_binding"], "root-cause analysis.necessity_binding"
        )
        if actual_necessity != necessity_binding:
            raise ValidationError("root-cause analysis necessity_binding is stale or mismatched")
    if formal_evidence_sources is not None:
        if not formal_evidence_sources:
            raise ValidationError("root-cause analysis has no formal evidence bound to the active problem")
        if any(
            not isinstance(reference, str) or not reference.strip()
            or source_type not in _PHENOMENON_EVIDENCE_SOURCE_TYPES
            for reference, source_type in formal_evidence_sources.items()
        ):
            raise ValidationError("formal root-cause evidence sources are invalid")

    def require_formal_evidence_references(references: list[str], label: str) -> None:
        if formal_evidence_sources is None:
            return
        unknown = set(references) - set(formal_evidence_sources)
        if unknown:
            raise ValidationError(f"{label} references evidence outside the active problem: {sorted(unknown)}")

    observations = _require_list(analysis, "failure_observations", "root-cause analysis", non_empty=True)
    observation_ids = _unique_ids(observations, "observation_id", "failure_observations")
    for index, raw in enumerate(observations, 1):
        item = _require_mapping(raw, f"phenomenon evidence item {index}")
        _require_fields(
            item,
            (
                "observation_id", "phenomenon", "conditions", "abnormal_variables",
                "evidence_source_type", "evidence_refs", "epistemic_status",
            ),
            f"phenomenon evidence item {index}",
        )
        _require_string_list(item["abnormal_variables"], f"phenomenon evidence item {index}.abnormal_variables", non_empty=True)
        evidence_refs = _require_string_list(item["evidence_refs"], f"phenomenon evidence item {index}.evidence_refs", non_empty=True)
        if item["evidence_source_type"] not in _PHENOMENON_EVIDENCE_SOURCE_TYPES:
            raise ValidationError(
                f"phenomenon evidence item {index}.evidence_source_type is invalid"
            )
        if item["epistemic_status"] not in _OBSERVATION_STATUSES:
            raise ValidationError(f"phenomenon evidence item {index}.epistemic_status is invalid")
        require_formal_evidence_references(
            evidence_refs, f"phenomenon evidence item {index}.evidence_refs"
        )
        if formal_evidence_sources is not None and not any(
            formal_evidence_sources[reference] == item["evidence_source_type"]
            for reference in evidence_refs
        ):
            raise ValidationError(
                f"phenomenon evidence item {index}.evidence_refs do not include its declared evidence source type"
            )

    clusters = _require_list(analysis, "phenomenon_clusters", "root-cause analysis", non_empty=True)
    cluster_ids = _unique_ids(clusters, "cluster_id", "phenomenon_clusters")
    grouped_observations: set[str] = set()
    for index, raw in enumerate(clusters, 1):
        item = _require_mapping(raw, f"phenomenon cluster {index}")
        _require_fields(item, ("cluster_id", "observation_ids", "grouping_rationale"), f"phenomenon cluster {index}")
        references = _require_string_list(item["observation_ids"], f"phenomenon cluster {index}.observation_ids", non_empty=True)
        unknown = set(references) - observation_ids
        if unknown:
            raise ValidationError(f"phenomenon cluster {index} references unknown observations: {sorted(unknown)}")
        grouped_observations.update(references)
    if grouped_observations != observation_ids:
        raise ValidationError("every phenomenon evidence item must appear in at least one phenomenon cluster")

    traces = _require_list(analysis, "causal_depth_traces", "root-cause analysis", non_empty=True)
    _unique_ids(traces, "trace_id", "causal_depth_traces")
    traced_clusters: set[str] = set()
    for index, raw in enumerate(traces, 1):
        item = _require_mapping(raw, f"causal depth trace {index}")
        _require_fields(item, ("trace_id", "cluster_id", "why_steps"), f"causal depth trace {index}")
        if item["cluster_id"] not in cluster_ids:
            raise ValidationError(f"causal depth trace {index} references an unknown cluster")
        traced_clusters.add(item["cluster_id"])
        steps = _require_list(item, "why_steps", f"causal depth trace {index}", non_empty=True)
        _unique_ids(steps, "step_id", f"causal depth trace {index}.why_steps")
        for step_index, raw_step in enumerate(steps, 1):
            step = _require_mapping(raw_step, f"causal depth trace {index} step {step_index}")
            _require_fields(
                step,
                ("step_id", "effect", "candidate_cause", "evidence_refs", "epistemic_status", "discriminating_observation"),
                f"causal depth trace {index} step {step_index}",
            )
            evidence_refs = _require_string_list(step["evidence_refs"], f"causal depth trace {index} step {step_index}.evidence_refs", non_empty=True)
            require_formal_evidence_references(
                evidence_refs, f"causal depth trace {index} step {step_index}.evidence_refs"
            )
            if step["epistemic_status"] not in _EXPLANATION_STATUSES:
                raise ValidationError(f"causal depth trace {index} step {step_index}.epistemic_status is invalid")
    if traced_clusters != cluster_ids:
        raise ValidationError("every phenomenon cluster must have at least one causal depth trace")

    chains = _require_list(analysis, "causal_chains", "root-cause analysis", non_empty=True)
    chain_ids = _unique_ids(chains, "chain_id", "causal_chains")
    for index, raw in enumerate(chains, 1):
        item = _require_mapping(raw, f"causal chain {index}")
        _require_fields(
            item,
            (
                "chain_id", "cluster_ids", "conditions_or_input_change", "mechanism_failure",
                "intermediate_state_abnormality", "final_failure_phenomenon", "evidence_refs",
                "alternative_explanations", "intervention_target", "falsifier", "epistemic_status",
            ),
            f"causal chain {index}",
        )
        references = _require_string_list(item["cluster_ids"], f"causal chain {index}.cluster_ids", non_empty=True)
        unknown = set(references) - cluster_ids
        if unknown:
            raise ValidationError(f"causal chain {index} references unknown clusters: {sorted(unknown)}")
        evidence_refs = _require_string_list(item["evidence_refs"], f"causal chain {index}.evidence_refs", non_empty=True)
        require_formal_evidence_references(
            evidence_refs, f"causal chain {index}.evidence_refs"
        )
        alternatives = _require_list(item, "alternative_explanations", f"causal chain {index}", non_empty=True)
        _unique_ids(alternatives, "explanation_id", f"causal chain {index}.alternative_explanations")
        for alternative_index, raw_alternative in enumerate(alternatives, 1):
            alternative = _require_mapping(raw_alternative, f"causal chain {index} alternative {alternative_index}")
            _require_fields(
                alternative,
                ("explanation_id", "mechanism", "epistemic_status", "discriminating_evidence"),
                f"causal chain {index} alternative {alternative_index}",
            )
            if alternative["epistemic_status"] not in _EXPLANATION_STATUSES:
                raise ValidationError(f"causal chain {index} alternative {alternative_index}.epistemic_status is invalid")
        if item["epistemic_status"] not in _CHAIN_STATUSES:
            raise ValidationError(f"causal chain {index}.epistemic_status is invalid")

    primary_ids = _require_string_list(analysis["primary_causal_chain_ids"], "primary_causal_chain_ids", non_empty=True)
    if len(primary_ids) != len(set(primary_ids)):
        raise ValidationError("primary_causal_chain_ids must be unique")
    unknown_primary = set(primary_ids) - chain_ids
    if unknown_primary:
        raise ValidationError(f"primary_causal_chain_ids reference unknown chains: {sorted(unknown_primary)}")
    _require_string_list(analysis["unresolved_questions"], "unresolved_questions")

    provenance = _require_mapping(analysis["analysis_provenance"], "analysis_provenance")
    _require_fields(provenance, ("author_role", "created_at", "source_artifact_ids"), "analysis_provenance")
    source_artifact_ids = _require_string_list(
        provenance["source_artifact_ids"], "analysis_provenance.source_artifact_ids", non_empty=True
    )
    validate_root_cause_diagnostic_pilots(provenance)
    require_formal_evidence_references(
        source_artifact_ids, "analysis_provenance.source_artifact_ids"
    )
    return analysis


def validate_root_cause_verdict(
    payload: Any,
    *,
    run_id: str,
    analysis_id: str,
    reviewed_analysis_sha256: str,
    problem_contract_sha256: str,
    evidence_capsule_sha256: str,
    necessity_closure_sha256: str,
    necessity_verdict_sha256: str,
) -> dict[str, Any]:
    """Validate an independent Root-Cause Gate verdict and its artifact bindings."""
    verdict = _require_mapping(payload, "root-cause verdict")
    _require_fields(
        verdict,
        (
            "schema_version", "run_id", "verdict_id", "reviewer", "analysis_id",
            "reviewed_analysis_sha256", "problem_contract_sha256", "evidence_capsule_sha256",
            "necessity_closure_sha256", "necessity_verdict_sha256",
            "decision", "reasons", "issues", "observation_fidelity", "grouping_adequacy",
            "causal_depth", "explanatory_coverage", "evidence_calibration",
            "intervention_relevance", "falsifiability", "residual_failure_alignment",
        ),
        "root-cause verdict",
    )
    if verdict["schema_version"] != 1:
        raise ValidationError("root-cause verdict schema_version must be 1")
    if verdict["run_id"] != run_id or verdict["analysis_id"] != analysis_id:
        raise ValidationError("root-cause verdict does not identify the active run and analysis")
    bindings = {
        "reviewed_analysis_sha256": reviewed_analysis_sha256,
        "problem_contract_sha256": problem_contract_sha256,
        "evidence_capsule_sha256": evidence_capsule_sha256,
        "necessity_closure_sha256": necessity_closure_sha256,
        "necessity_verdict_sha256": necessity_verdict_sha256,
    }
    for field, expected in bindings.items():
        _require_sha256(verdict[field], field)
        if verdict[field] != expected:
            raise ValidationError(f"root-cause verdict {field} does not match the reviewed artifact")
    if verdict["decision"] not in _ROOT_CAUSE_DECISIONS:
        raise ValidationError("root-cause verdict decision is invalid")
    _require_string_list(verdict["reasons"], "root-cause verdict reasons", non_empty=True)
    issues = _require_list(verdict, "issues", "root-cause verdict")
    blocking = False
    for index, raw in enumerate(issues, 1):
        issue = _require_mapping(raw, f"root-cause verdict issue {index}")
        _require_fields(issue, ("issue_id", "severity", "message"), f"root-cause verdict issue {index}")
        if issue["severity"] not in {"BLOCKING", "NON_BLOCKING"}:
            raise ValidationError(f"root-cause verdict issue {index}.severity is invalid")
        blocking = blocking or issue["severity"] == "BLOCKING"
    if verdict["decision"] == "DIAGNOSIS_READY" and blocking:
        raise ValidationError("DIAGNOSIS_READY cannot contain a BLOCKING issue")
    for field in (
        "observation_fidelity", "grouping_adequacy", "causal_depth", "explanatory_coverage",
        "evidence_calibration", "intervention_relevance", "falsifiability",
        "residual_failure_alignment",
    ):
        if verdict[field] not in {"PASS", "FAIL", "UNCERTAIN"}:
            raise ValidationError(f"root-cause verdict {field} must be PASS, FAIL, or UNCERTAIN")
    if verdict["decision"] == "DIAGNOSIS_READY" and any(
        verdict[field] != "PASS"
        for field in (
            "observation_fidelity", "grouping_adequacy", "causal_depth", "explanatory_coverage",
            "evidence_calibration", "intervention_relevance", "falsifiability",
            "residual_failure_alignment",
        )
    ):
        raise ValidationError(
            "DIAGNOSIS_READY requires PASS on all root-cause scientific rubrics"
        )
    return verdict


def validate_root_cause_view(text: Any, analysis: dict[str, Any]) -> str:
    """Ensure the human view exposes the canonical handoff identifiers.

    Semantic equivalence remains reviewable, but a view that omits the bound
    analysis, upstream hashes, or primary chains is not an acceptable handoff.
    """
    if not isinstance(text, str) or not text.strip():
        raise ValidationError("root-cause Markdown view must be non-empty")
    required_tokens = [
        analysis["analysis_id"],
        analysis["problem_id"],
        analysis["problem_contract_sha256"],
        analysis["evidence_capsule_sha256"],
        analysis["necessity_binding"]["necessity_id"],
        analysis["necessity_binding"]["closure_sha256"],
        analysis["necessity_binding"]["verdict_id"],
        analysis["necessity_binding"]["verdict_sha256"],
        *analysis["necessity_binding"]["residual_failure_ids"],
        *analysis["primary_causal_chain_ids"],
    ]
    missing = [token for token in required_tokens if token not in text]
    if missing:
        raise ValidationError(
            f"root-cause Markdown view omits canonical identifiers or hashes: {missing}"
        )
    return text


def validate_query_plan(
    payload: Any,
    *,
    method_design_context: dict[str, Any] | None = None,
    method_refinement_context: dict[str, Any] | None = None,
    problem_lead_context: dict[str, Any] | None = None,
    problem_necessity_context: dict[str, Any] | None = None,
    required_coverage_gaps: set[str] | None = None,
) -> dict[str, Any]:
    plan = _require_mapping(payload, "query plan")
    _require_fields(plan, ("queries", "coverage_gaps"), "query plan")
    if not isinstance(plan["queries"], list) or not plan["queries"]:
        raise ValidationError("query plan queries must be a non-empty list")
    declared_coverage_gaps = _require_string_list(
        plan["coverage_gaps"], "query plan coverage_gaps", non_empty=False
    )
    if len(declared_coverage_gaps) != len(set(declared_coverage_gaps)):
        raise ValidationError("query plan coverage_gaps must contain unique entries")
    required_gaps = set(required_coverage_gaps or set())
    if required_gaps - set(declared_coverage_gaps):
        raise ValidationError(
            "query plan must retain every required coverage gap from the current Field Map or Coverage Review"
        )
    schema_version = plan.get("schema_version", 1)
    if schema_version not in {1, 2}:
        raise ValidationError("query plan schema_version must be 1 or 2")
    if schema_version == 2:
        strategy = _require_mapping(plan.get("search_strategy"), "query plan search_strategy")
        _require_fields(
            strategy,
            (
                "priority_order",
                "discovery_sources",
                "time_range",
                "screening_requirement",
                "saturation_criteria",
            ),
            "query plan search_strategy",
        )
        expected_priority = [
            "RECENT_AUTHORITATIVE_REVIEWS",
            "HIGH_CITATION_BACKBONE",
            "RECENT_ELITE_FRONTIER",
            "TARGETED_GAP_FOLLOWUP",
        ]
        if strategy["priority_order"] != expected_priority:
            raise ValidationError(
                "query plan search_strategy.priority_order must preserve the canonical evidence priority"
            )
        _require_string_list(
            strategy["discovery_sources"],
            "query plan search_strategy.discovery_sources",
            non_empty=True,
        )
        time_range = _require_mapping(strategy["time_range"], "query plan search_strategy.time_range")
        _require_fields(time_range, ("year_from", "year_to"), "query plan search_strategy.time_range")
        if (
            not isinstance(time_range["year_from"], int)
            or not isinstance(time_range["year_to"], int)
            or time_range["year_from"] > time_range["year_to"]
        ):
            raise ValidationError("query plan search_strategy.time_range must be an ordered integer range")
        if strategy["screening_requirement"] != "TITLE_ABSTRACT_FOR_ALL_RETRIEVED_CANDIDATES":
            raise ValidationError(
                "query plan must require title/abstract screening for all retrieved candidates"
            )
        _require_string_list(
            strategy["saturation_criteria"],
            "query plan search_strategy.saturation_criteria",
            non_empty=True,
        )
    method_search_mode: str | None = None
    method_context_ids: dict[str, set[str]] = {}
    method_context_links: dict[str, dict[str, set[str]]] = {}
    target_signature_by_id: dict[str, dict[str, Any]] = {}
    domain_hypothesis_by_id: dict[str, dict[str, Any]] = {}
    terminology_map_by_id: dict[str, dict[str, Any]] = {}
    method_decision_targets: set[str] = set()
    principle_query_dimensions_by_rmc: dict[str, set[str]] = {}
    cross_domain_steps_by_rmc: dict[str, set[str]] = {}
    declared_adaptation_gap_ids: set[str] | None = None
    necessity_decision_target_ids: set[str] | None = None
    covered_necessity_target_ids: set[str] = set()
    if problem_necessity_context is not None:
        context = _require_mapping(
            plan.get("problem_necessity_context"),
            "query plan problem_necessity_context",
        )
        _require_fields(
            context,
            (
                "search_mode",
                "problem_id",
                "problem_version",
                "problem_contract_sha256",
                "evidence_capsule_sha256",
                "decision_targets",
            ),
            "query plan problem_necessity_context",
        )
        if context["search_mode"] != "NECESSITY_EVIDENCE_RECOVERY":
            raise ValidationError(
                "query plan problem_necessity_context.search_mode must be NECESSITY_EVIDENCE_RECOVERY"
            )
        for field in (
            "problem_id",
            "problem_version",
            "problem_contract_sha256",
            "evidence_capsule_sha256",
        ):
            if str(context[field]) != str(problem_necessity_context[field]):
                raise ValidationError(
                    f"query plan problem_necessity_context.{field} is stale"
                )
        targets = _require_list(
            context,
            "decision_targets",
            "query plan problem_necessity_context",
            non_empty=True,
        )
        necessity_decision_target_ids = _unique_ids(
            targets,
            "decision_target_id",
            "query plan problem_necessity_context.decision_targets",
        )
        for index, raw in enumerate(targets, 1):
            target = _require_mapping(raw, f"Necessity decision target {index}")
            _require_fields(
                target,
                ("decision_target_id", "failure_id", "simple_repair_decision_target"),
                f"Necessity decision target {index}",
            )
            _required_text(target["failure_id"], f"Necessity decision target {index}.failure_id")
            _required_text(
                target["simple_repair_decision_target"],
                f"Necessity decision target {index}.simple_repair_decision_target",
            )
    if method_design_context is not None:
        context = _require_mapping(
            plan.get("method_design_context"), "query plan method_design_context"
        )
        _require_fields(
            context,
            (
                "root_cause_analysis_id", "root_cause_analysis_sha256",
                "active_field_map_sha256", "search_mode",
                "problem_id", "problem_version", "problem_contract_sha256",
                "evidence_capsule_sha256", "causal_chain_ids",
                "required_mechanism_changes", "required_capabilities", "design_obligations",
                "principle_search_context",
            ),
            "query plan method_design_context",
        )
        for field in (
            "root_cause_analysis_id", "root_cause_analysis_sha256", "active_field_map_sha256"
        ):
            if context[field] != method_design_context[field]:
                raise ValidationError(
                    f"query plan method_design_context.{field} does not match the active method-design handoff"
                )
        method_search_mode = context["search_mode"]
        if method_search_mode != "PRINCIPLE_SEARCH":
            raise ValidationError("query plan method_design_context.search_mode must be PRINCIPLE_SEARCH")
        expected_problem = method_design_context["problem_version"]
        for field, expected in (
            ("problem_id", expected_problem["problem_id"]),
            ("problem_version", expected_problem["version"]),
            ("problem_contract_sha256", expected_problem["contract_sha256"]),
            ("evidence_capsule_sha256", expected_problem["evidence_capsule_sha256"]),
        ):
            if context[field] != expected:
                raise ValidationError(f"query plan method_design_context.{field} is stale")
        chains = set(_unique_string_values(context["causal_chain_ids"], "query plan method_design_context.causal_chain_ids"))
        if chains != set(method_design_context["primary_causal_chain_ids"]):
            raise ValidationError("query plan method_design_context must bind every primary causal chain")
        mechanism_records = _require_list(context, "required_mechanism_changes", "query plan method_design_context", non_empty=True)
        capability_records = _require_list(context, "required_capabilities", "query plan method_design_context", non_empty=True)
        obligation_records = _require_list(context, "design_obligations", "query plan method_design_context", non_empty=True)
        mechanism_ids = _unique_ids(mechanism_records, "mechanism_change_id", "query plan method_design_context.required_mechanism_changes")
        capability_ids = _unique_ids(capability_records, "capability_id", "query plan method_design_context.required_capabilities")
        obligation_ids = _unique_ids(obligation_records, "obligation_id", "query plan method_design_context.design_obligations")
        if not mechanism_ids or not capability_ids or not obligation_ids:
            raise ValidationError("PRINCIPLE_SEARCH requires non-empty RMC, Capability, and Obligation bindings")
        mechanism_links: dict[str, set[str]] = {}
        mechanism_capability_links: dict[str, set[str]] = {}
        mechanism_obligation_links: dict[str, set[str]] = {}
        capability_links: dict[str, set[str]] = {}
        obligation_links: dict[str, set[str]] = {}
        for index, raw in enumerate(mechanism_records, 1):
            item = _require_mapping(raw, f"query plan Required Mechanism Change {index}")
            _require_fields(
                item,
                (
                    "mechanism_change_id", "causal_chain_ids",
                    "failed_relation_state_or_information_structure", "required_mechanism_change",
                    "change_direction", "causal_position", "activation_condition",
                    "root_cause_resolution_rationale", "capability_ids", "obligation_ids",
                ),
                f"query plan Required Mechanism Change {index}",
            )
            linked_chains = set(_unique_string_values(item["causal_chain_ids"], f"query plan Required Mechanism Change {index}.causal_chain_ids"))
            linked_capabilities = set(_unique_string_values(item["capability_ids"], f"query plan Required Mechanism Change {index}.capability_ids"))
            linked_obligations = set(_unique_string_values(item["obligation_ids"], f"query plan Required Mechanism Change {index}.obligation_ids"))
            if not linked_chains <= chains or not linked_capabilities <= capability_ids or not linked_obligations <= obligation_ids:
                raise ValidationError("query plan Required Mechanism Change has an unresolved binding")
            for field in (
                "failed_relation_state_or_information_structure", "required_mechanism_change",
                "change_direction", "causal_position", "activation_condition",
                "root_cause_resolution_rationale",
            ):
                _required_text(item[field], f"query plan Required Mechanism Change {index}.{field}")
            mechanism_links[item["mechanism_change_id"]] = linked_chains
            mechanism_capability_links[item["mechanism_change_id"]] = linked_capabilities
            mechanism_obligation_links[item["mechanism_change_id"]] = linked_obligations
        for index, raw in enumerate(capability_records, 1):
            item = _require_mapping(raw, f"query plan Required Capability {index}")
            _require_fields(item, ("capability_id", "mechanism_change_ids"), f"query plan Required Capability {index}")
            linked = set(_unique_string_values(item["mechanism_change_ids"], f"query plan Required Capability {index}.mechanism_change_ids"))
            if not linked <= mechanism_ids:
                raise ValidationError("query plan Required Capability has an unresolved mechanism-change binding")
            capability_links[item["capability_id"]] = linked
        for index, raw in enumerate(obligation_records, 1):
            item = _require_mapping(raw, f"query plan Design Obligation {index}")
            _require_fields(item, ("obligation_id", "mechanism_change_ids", "capability_ids"), f"query plan Design Obligation {index}")
            linked_mechanisms = set(_unique_string_values(item["mechanism_change_ids"], f"query plan Design Obligation {index}.mechanism_change_ids"))
            linked_capabilities = set(_unique_string_values(item["capability_ids"], f"query plan Design Obligation {index}.capability_ids"))
            if not linked_mechanisms <= mechanism_ids or not linked_capabilities <= capability_ids:
                raise ValidationError("query plan Design Obligation has an unresolved binding")
            obligation_links[item["obligation_id"]] = linked_mechanisms
        if any(
            mechanism_id not in capability_links[capability_id]
            for mechanism_id, linked in mechanism_capability_links.items()
            for capability_id in linked
        ) or any(
            capability_id not in mechanism_capability_links[mechanism_id]
            for capability_id, linked in capability_links.items()
            for mechanism_id in linked
        ):
            raise ValidationError("query plan RMC/Capability bindings are inconsistent")
        if any(
            mechanism_id not in obligation_links[obligation_id]
            for mechanism_id, linked in mechanism_obligation_links.items()
            for obligation_id in linked
        ) or any(
            obligation_id not in mechanism_obligation_links[mechanism_id]
            for obligation_id, linked in obligation_links.items()
            for mechanism_id in linked
        ):
            raise ValidationError("query plan RMC/Obligation bindings are inconsistent")
        method_context_ids = {
            "mechanism_change_ids": mechanism_ids,
            "capability_ids": capability_ids,
            "obligation_ids": obligation_ids,
            "causal_chain_ids": chains,
        }
        method_context_links = {
            "mechanism_chain_ids": mechanism_links,
            "capability_mechanism_ids": capability_links,
            "obligation_mechanism_ids": obligation_links,
        }
        principle_query_dimensions_by_rmc = {
            mechanism_id: set() for mechanism_id in mechanism_ids
        }
        cross_domain_steps_by_rmc = {
            mechanism_id: set() for mechanism_id in mechanism_ids
        }
        principle_context = _require_mapping(
            context["principle_search_context"],
            "query plan method_design_context.principle_search_context",
        )
        _require_fields(
            principle_context,
            ("target_mechanism_signatures", "domain_hypotheses", "terminology_maps", "decision_targets"),
            "query plan method_design_context.principle_search_context",
        )
        signatures = _require_list(
            principle_context,
            "target_mechanism_signatures",
            "query plan method_design_context.principle_search_context",
            non_empty=True,
        )
        signature_ids = _unique_ids(signatures, "target_mechanism_signature_id", "query plan Target Mechanism Signatures")
        signature_rmc_ids: set[str] = set()
        for index, raw in enumerate(signatures, 1):
            item = _require_mapping(raw, f"query plan Target Mechanism Signature {index}")
            _require_fields(
                item,
                (
                    "target_mechanism_signature_id", "rmc_id", "domain_neutral_failure_structure",
                    "causal_or_computational_variable_or_relation", "current_relation_or_state",
                    "required_intervention", "change_direction", "causal_position", "activation_condition",
                ),
                f"query plan Target Mechanism Signature {index}",
            )
            rmc_id = item["rmc_id"]
            if rmc_id not in mechanism_ids or rmc_id in signature_rmc_ids:
                raise ValidationError("query plan must bind exactly one Target Mechanism Signature per RMC")
            signature_rmc_ids.add(rmc_id)
            for field in (
                "domain_neutral_failure_structure", "causal_or_computational_variable_or_relation",
                "current_relation_or_state", "required_intervention", "change_direction",
                "causal_position", "activation_condition",
            ):
                _required_text(item[field], f"query plan Target Mechanism Signature {index}.{field}")
            rmc = next(record for record in mechanism_records if record["mechanism_change_id"] == rmc_id)
            for field in ("change_direction", "causal_position", "activation_condition"):
                if item[field] != rmc[field]:
                    raise ValidationError(
                        f"query plan Target Mechanism Signature {index}.{field} is inconsistent with its RMC"
                    )
            target_signature_by_id[item["target_mechanism_signature_id"]] = item
        if signature_rmc_ids != mechanism_ids:
            raise ValidationError("query plan must derive a Target Mechanism Signature for every RMC")

        hypotheses = _require_list(
            principle_context,
            "domain_hypotheses",
            "query plan method_design_context.principle_search_context",
        )
        hypothesis_ids = _unique_ids(hypotheses, "domain_hypothesis_id", "query plan Domain Hypotheses") if hypotheses else set()
        for index, raw in enumerate(hypotheses, 1):
            item = _require_mapping(raw, f"query plan Domain Hypothesis {index}")
            _require_fields(
                item,
                (
                    "domain_hypothesis_id", "rmc_id", "target_mechanism_signature_ref",
                    "source_channel", "domain_or_research_community_or_paradigm",
                    "structural_rationale", "expected_problem_structure", "expected_intervention_family",
                    "provenance_refs", "disposition",
                ),
                f"query plan Domain Hypothesis {index}",
            )
            signature = target_signature_by_id.get(item["target_mechanism_signature_ref"])
            if signature is None or signature["rmc_id"] != item["rmc_id"]:
                raise ValidationError(f"query plan Domain Hypothesis {index} has a stale RMC/signature binding")
            if item["source_channel"] not in {"MODEL_PRIOR", "ACADEMIC_BRIDGE", "PRACTITIONER_SIGNAL"}:
                raise ValidationError(f"query plan Domain Hypothesis {index}.source_channel is invalid")
            for field in (
                "domain_or_research_community_or_paradigm", "structural_rationale",
                "expected_problem_structure", "expected_intervention_family",
            ):
                _required_text(item[field], f"query plan Domain Hypothesis {index}.{field}")
            _unique_string_values(
                item["provenance_refs"], f"query plan Domain Hypothesis {index}.provenance_refs",
                non_empty=item["source_channel"] != "MODEL_PRIOR",
            )
            if item["disposition"] not in {"EXPLORE", "CLOSED"}:
                raise ValidationError(f"query plan Domain Hypothesis {index}.disposition is invalid")
            domain_hypothesis_by_id[item["domain_hypothesis_id"]] = item

        terminology_maps = _require_list(
            principle_context,
            "terminology_maps",
            "query plan method_design_context.principle_search_context",
        )
        terminology_ids = _unique_ids(terminology_maps, "terminology_map_id", "query plan Terminology Maps") if terminology_maps else set()
        for index, raw in enumerate(terminology_maps, 1):
            item = _require_mapping(raw, f"query plan Terminology Map {index}")
            _require_fields(
                item,
                (
                    "terminology_map_id", "domain_hypothesis_id", "canonical_problem_terms",
                    "canonical_variable_state_relation_terms", "canonical_intervention_terms",
                    "canonical_method_families", "evidence_refs", "search_read_provenance",
                    "query_plan_sha256",
                ),
                f"query plan Terminology Map {index}",
            )
            if item["domain_hypothesis_id"] not in hypothesis_ids:
                raise ValidationError(f"query plan Terminology Map {index} references an unknown Domain Hypothesis")
            for field in (
                "canonical_problem_terms", "canonical_variable_state_relation_terms",
                "canonical_intervention_terms", "canonical_method_families", "evidence_refs",
                "search_read_provenance",
            ):
                _unique_string_values(item[field], f"query plan Terminology Map {index}.{field}")
            _required_text(item["query_plan_sha256"], f"query plan Terminology Map {index}.query_plan_sha256")
            terminology_map_by_id[item["terminology_map_id"]] = item
        method_decision_targets = set(
            _unique_string_values(
                principle_context["decision_targets"],
                "query plan method_design_context.principle_search_context.decision_targets",
            )
        )
    if method_refinement_context is not None:
        context = _require_mapping(
            plan.get("method_refinement_context"), "query plan method_refinement_context"
        )
        _require_fields(
            context,
            (
                "search_mode", "principle_id", "principle_version",
                "selected_principle_sha256", "residual_adaptation_gaps",
            ),
            "query plan method_refinement_context",
        )
        if context["search_mode"] != "ADAPTATION_GAP_SEARCH":
            raise ValidationError("method refinement search_mode must be ADAPTATION_GAP_SEARCH")
        for field in ("principle_id", "principle_version", "selected_principle_sha256"):
            if str(context[field]) != str(method_refinement_context[field]):
                raise ValidationError(f"query plan method_refinement_context.{field} is stale")
        gaps = _require_list(context, "residual_adaptation_gaps", "query plan method_refinement_context", non_empty=True)
        declared_adaptation_gap_ids = _unique_ids(
            gaps, "gap_id", "query plan method_refinement_context.residual_adaptation_gaps"
        )

    plan_item_ids: list[str] = []
    for index, query in enumerate(plan["queries"], 1):
        item = _require_mapping(query, f"query plan item {index}")
        _require_fields(item, ("query", "purpose"), f"query plan item {index}")
        if not isinstance(item["purpose"], str) or not item["purpose"].strip():
            raise ValidationError(f"query plan item {index}.purpose must be non-empty")
        if problem_lead_context is not None:
            _require_fields(
                item,
                (
                    "lead_id",
                    "lead_statement",
                    "active_field_map_sha256",
                    "decision_dimension",
                    "expected_close_condition",
                ),
                f"problem-lead query plan item {index}",
            )
            for field in ("lead_id", "lead_statement", "expected_close_condition"):
                if not isinstance(item[field], str) or not item[field].strip():
                    raise ValidationError(
                        f"problem-lead query plan item {index}.{field} must be non-empty"
                    )
            if item["active_field_map_sha256"] != problem_lead_context["active_field_map_sha256"]:
                raise ValidationError(
                    f"problem-lead query plan item {index}.active_field_map_sha256 "
                    "does not match the current accepted Field Map"
                )
            if item["decision_dimension"] not in {
                "Reality",
                "Importance",
                "Unresolvedness",
                "Precision",
                "Falsifiability",
                "Answerability",
            }:
                raise ValidationError(
                    f"problem-lead query plan item {index}.decision_dimension must be one "
                    "of Reality, Importance, Unresolvedness, Precision, Falsifiability, or Answerability"
                )
        if necessity_decision_target_ids is not None:
            _require_fields(
                item,
                ("decision_target_ids",),
                f"Necessity query plan item {index}",
            )
            target_ids = set(
                _unique_string_values(
                    item["decision_target_ids"],
                    f"Necessity query plan item {index}.decision_target_ids",
                )
            )
            if not target_ids <= necessity_decision_target_ids:
                raise ValidationError(
                    f"Necessity query plan item {index} references an unknown Failure/Simple-Repair decision target"
                )
            covered_necessity_target_ids.update(target_ids)
        if required_gaps:
            _require_fields(item, ("coverage_gaps",), f"query plan item {index}")
            item_gaps = _require_string_list(
                item["coverage_gaps"],
                f"query plan item {index}.coverage_gaps",
                non_empty=False,
            )
            if len(item_gaps) != len(set(item_gaps)):
                raise ValidationError(
                    f"query plan item {index}.coverage_gaps must contain unique entries"
                )
            undeclared = set(item_gaps) - set(declared_coverage_gaps)
            if undeclared:
                raise ValidationError(
                    f"query plan item {index}.coverage_gaps contains gaps not declared by the query plan: "
                    f"{sorted(undeclared)}"
                )
        if method_search_mode == "PRINCIPLE_SEARCH":
            _require_fields(
                item,
                (
                    "search_dimension", "mechanism_change_ids", "capability_ids",
                    "obligation_ids", "causal_chain_ids", "search_step",
                    "target_mechanism_signature_refs", "domain_hypothesis_ids",
                    "terminology_map_ids", "decision_target",
                ),
                f"query plan Principle-search item {index}",
            )
            if item["search_dimension"] not in {
                "SAME_FIELD_MECHANISM", "CROSS_DOMAIN_STRUCTURAL_ISOMORPHISM",
            }:
                raise ValidationError(
                    f"query plan Principle-search item {index} must be a literature search; "
                    "FIRST_PRINCIPLES and REPRESENTATION_TRANSFORMATION belong in derivation records"
                )
            item_ids: dict[str, set[str]] = {}
            for field, known_ids in method_context_ids.items():
                target_ids = set(_unique_string_values(item[field], f"query plan Principle-search item {index}.{field}"))
                if not target_ids <= known_ids:
                    raise ValidationError(f"query plan Principle-search item {index}.{field} contains an unresolved ID")
                item_ids[field] = target_ids
            linked_chains = set().union(
                *(method_context_links["mechanism_chain_ids"][mechanism_id] for mechanism_id in item_ids["mechanism_change_ids"])
            )
            if not item_ids["causal_chain_ids"] <= linked_chains:
                raise ValidationError(f"query plan Principle-search item {index} has a causal-chain binding outside its RMC targets")
            for field, link_name in (
                ("capability_ids", "capability_mechanism_ids"),
                ("obligation_ids", "obligation_mechanism_ids"),
            ):
                if any(
                    not method_context_links[link_name][target_id] & item_ids["mechanism_change_ids"]
                    for target_id in item_ids[field]
                ):
                    raise ValidationError(f"query plan Principle-search item {index}.{field} is not linked to its RMC targets")
            signature_refs = set(
                _unique_string_values(
                    item["target_mechanism_signature_refs"],
                    f"query plan Principle-search item {index}.target_mechanism_signature_refs",
                )
            )
            if not signature_refs <= set(target_signature_by_id) or {
                target_signature_by_id[signature_id]["rmc_id"] for signature_id in signature_refs
            } != item_ids["mechanism_change_ids"]:
                raise ValidationError(
                    f"query plan Principle-search item {index} must bind the current Target Mechanism Signature for every target RMC"
                )
            domain_ids = set(
                _unique_string_values(
                    item["domain_hypothesis_ids"],
                    f"query plan Principle-search item {index}.domain_hypothesis_ids",
                    non_empty=False,
                )
            )
            terminology_ids = set(
                _unique_string_values(
                    item["terminology_map_ids"],
                    f"query plan Principle-search item {index}.terminology_map_ids",
                    non_empty=False,
                )
            )
            decision_target = _required_text(
                item["decision_target"],
                f"query plan Principle-search item {index}.decision_target",
            )
            if decision_target not in method_decision_targets:
                raise ValidationError(
                    f"query plan Principle-search item {index}.decision_target is not declared in the current Principle Search context"
                )
            if item["search_dimension"] == "SAME_FIELD_MECHANISM":
                if item["search_step"] != "SOURCE_SEARCH" or domain_ids or terminology_ids:
                    raise ValidationError(
                        f"query plan same-field item {index} uses SOURCE_SEARCH without a fabricated cross-domain discovery story"
                    )
            else:
                if item["search_step"] not in {
                    "DOMAIN_DISCOVERY", "TERMINOLOGY_GROUNDING", "SOURCE_SEARCH"
                }:
                    raise ValidationError(f"query plan cross-domain item {index}.search_step is invalid")
                if item["search_step"] == "DOMAIN_DISCOVERY":
                    if domain_ids or terminology_ids:
                        raise ValidationError(
                            "DOMAIN_DISCOVERY must bind the current RMC/signature and must not require a pre-existing Domain Hypothesis"
                        )
                elif item["search_step"] == "TERMINOLOGY_GROUNDING":
                    if not domain_ids or terminology_ids:
                        raise ValidationError(
                            "TERMINOLOGY_GROUNDING requires a registered Domain Hypothesis and precedes a Terminology Map"
                        )
                else:
                    if not domain_ids or not terminology_ids:
                        raise ValidationError(
                            "SOURCE_SEARCH requires a Domain Hypothesis, evidence-grounded Terminology Map, and explicit decision target"
                        )
                if not domain_ids <= set(domain_hypothesis_by_id):
                    raise ValidationError(f"query plan Principle-search item {index} references an unknown Domain Hypothesis")
                if not terminology_ids <= set(terminology_map_by_id):
                    raise ValidationError(f"query plan Principle-search item {index} references an unknown Terminology Map")
                for domain_id in domain_ids:
                    hypothesis = domain_hypothesis_by_id[domain_id]
                    if hypothesis["rmc_id"] not in item_ids["mechanism_change_ids"]:
                        raise ValidationError(f"query plan Principle-search item {index} has a Domain Hypothesis outside its RMC targets")
                for terminology_id in terminology_ids:
                    terminology = terminology_map_by_id[terminology_id]
                    if terminology["domain_hypothesis_id"] not in domain_ids:
                        raise ValidationError(f"query plan Principle-search item {index} has a Terminology Map outside its Domain Hypotheses")
            for mechanism_id in item_ids["mechanism_change_ids"]:
                principle_query_dimensions_by_rmc[mechanism_id].add(item["search_dimension"])
                if item["search_dimension"] == "CROSS_DOMAIN_STRUCTURAL_ISOMORPHISM":
                    cross_domain_steps_by_rmc[mechanism_id].add(item["search_step"])
        if declared_adaptation_gap_ids is not None:
            _require_fields(
                item, ("decision_target", "residual_adaptation_gap_ids"),
                f"query plan adaptation-gap item {index}",
            )
            if not isinstance(item["decision_target"], str) or not item["decision_target"].strip():
                raise ValidationError(
                    f"query plan method-design item {index}.decision_target must be non-empty"
                )
            target_ids = set(_method_identifier_list(
                item["residual_adaptation_gap_ids"],
                f"query plan adaptation-gap item {index}.residual_adaptation_gap_ids",
            ))
            if not target_ids <= declared_adaptation_gap_ids:
                raise ValidationError(
                    f"query plan adaptation-gap item {index} targets no declared residual gap"
                )
        if schema_version == 2:
            _require_fields(
                item,
                (
                    "plan_item_id",
                    "priority_tier",
                    "year_from",
                    "year_to",
                    "page",
                    "exact_title",
                    "target_venues",
                    "expected_close_condition",
                ),
                f"query plan item {index}",
            )
            plan_item_id = item["plan_item_id"]
            if not isinstance(plan_item_id, str) or not plan_item_id.strip():
                raise ValidationError(f"query plan item {index}.plan_item_id must be non-empty")
            plan_item_ids.append(plan_item_id)
            if item["priority_tier"] not in {
                "RECENT_AUTHORITATIVE_REVIEWS",
                "HIGH_CITATION_BACKBONE",
                "RECENT_ELITE_FRONTIER",
                "TARGETED_GAP_FOLLOWUP",
            }:
                raise ValidationError(f"query plan item {index}.priority_tier is invalid")
            if (
                not isinstance(item["year_from"], int)
                or not isinstance(item["year_to"], int)
                or item["year_from"] > item["year_to"]
            ):
                raise ValidationError(f"query plan item {index} requires an ordered year range")
            if not isinstance(item["page"], int) or item["page"] < 1:
                raise ValidationError(f"query plan item {index}.page must be at least 1")
            if not isinstance(item["exact_title"], bool):
                raise ValidationError(f"query plan item {index}.exact_title must be boolean")
            _require_string_list(item["target_venues"], f"query plan item {index}.target_venues")
            if (
                not isinstance(item["expected_close_condition"], str)
                or not item["expected_close_condition"].strip()
            ):
                raise ValidationError(
                    f"query plan item {index}.expected_close_condition must be non-empty"
                )
    query_texts = [str(item["query"]).strip() for item in plan["queries"]]
    if any(not query for query in query_texts):
        raise ValidationError("query plan queries must be non-empty")
    if schema_version == 1 and len(set(query_texts)) != len(query_texts):
        raise ValidationError("query plan schema_version 1 queries must be unique")
    if schema_version == 2 and len(set(plan_item_ids)) != len(plan_item_ids):
        raise ValidationError("query plan plan_item_id values must be unique")
    if required_gaps:
        query_bound_gaps = {
            gap
            for item in plan["queries"]
            for gap in item.get("coverage_gaps", [])
        }
        missing_query_bindings = sorted(required_gaps - query_bound_gaps)
        if missing_query_bindings:
            raise ValidationError(
                "each required coverage gap must be bound to at least one executable query: "
                f"{missing_query_bindings}"
            )
    if (
        necessity_decision_target_ids is not None
        and covered_necessity_target_ids != necessity_decision_target_ids
    ):
        raise ValidationError(
            "Necessity Evidence recovery must bind every declared Failure/Simple-Repair decision target"
        )
    if method_search_mode == "PRINCIPLE_SEARCH":
        for rmc_id, dimensions in principle_query_dimensions_by_rmc.items():
            if "SAME_FIELD_MECHANISM" not in dimensions:
                raise ValidationError(
                    f"RMC {rmc_id} requires formal SAME_FIELD_MECHANISM search provenance"
                )
            if "DOMAIN_DISCOVERY" not in cross_domain_steps_by_rmc[rmc_id]:
                raise ValidationError(
                    f"RMC {rmc_id} requires an actual ACADEMIC_BRIDGE DOMAIN_DISCOVERY query"
                )
    return plan


def validate_evidence_card(
    payload: Any,
    admitted_paper_id: str,
    *,
    existing_evidence_ids: set[str] | None = None,
) -> dict[str, Any]:
    card = _require_mapping(payload, "Evidence Card")
    _require_fields(card, EVIDENCE_CARD_FIELDS, "Evidence Card")
    if not isinstance(card["source_id"], str) or not card["source_id"].strip():
        raise ValidationError("Evidence Card source_id must be a non-empty evidence identifier")
    if card["source_id"] != admitted_paper_id:
        raise ValidationError("Evidence Card source_id does not match the admitted paper")
    if existing_evidence_ids is not None and card["source_id"] in existing_evidence_ids:
        raise ValidationError("Evidence Card source_id must be unique among accepted Evidence Cards")
    if card["decision_grade"] != "decision_grade":
        raise ValidationError("accepted Evidence Cards must be decision_grade")
    if card["access_level"] not in {"partial_text", "full_text"}:
        raise ValidationError("accepted Evidence Cards require partial_text or full_text access")
    return card


def validate_field_map(
    payload: Any,
    *,
    evidence_ids: set[str] | None = None,
    provisional: bool = False,
) -> dict[str, Any]:
    field_map = _require_mapping(payload, "Active Field Map")
    required_fields = (
        tuple(field for field in FIELD_MAP_FIELDS if field != "coverage_record")
        if provisional
        else FIELD_MAP_FIELDS
    )
    _require_fields(field_map, required_fields, "Active Field Map")
    if provisional and "coverage_record" in field_map:
        raise ValidationError("provisional Initial Field Map must not carry a coverage_record")
    bottleneck_ids = _unique_ids(
        _require_list(field_map, "core_bottlenecks", "Active Field Map"),
        "id",
        "Active Field Map core_bottlenecks",
    )
    method_ids = _unique_ids(
        _require_list(field_map, "method_families", "Active Field Map"),
        "id",
        "Active Field Map method_families",
    )

    def require_references(
        rows: Any,
        *,
        label: str,
        reference_field: str,
        allowed_ids: set[str],
    ) -> None:
        for index, raw in enumerate(_require_list(field_map, rows, "Active Field Map"), 1):
            row = _require_mapping(raw, f"Active Field Map {label} row {index}")
            _require_fields(row, (reference_field,), f"Active Field Map {label} row {index}")
            reference = row[reference_field]
            if not isinstance(reference, str) or not reference.strip():
                raise ValidationError(
                    f"Active Field Map {label} row {index}.{reference_field} must be a non-empty identifier"
                )
            if reference not in allowed_ids:
                raise ValidationError(
                    f"Active Field Map {label} row {index}.{reference_field} does not resolve"
                )

    transition_ids: list[str] = []
    for index, raw in enumerate(
        _require_list(field_map, "family_development_traces", "Active Field Map"), 1
    ):
        trace = _require_mapping(raw, f"Active Field Map family_development_traces row {index}")
        label = f"Active Field Map family_development_traces row {index}"
        _require_fields(trace, DEVELOPMENT_TRACE_FIELDS, label)
        transition_id = trace["transition_id"]
        if not isinstance(transition_id, str) or not transition_id.strip():
            raise ValidationError(f"{label}.transition_id must be a non-empty string")
        transition_ids.append(transition_id)
        for field in (
            "previous_problem_or_bottleneck",
            "progress_and_conditions",
            "residual_or_new_bottleneck",
            "research_question_shift",
            "subsequent_direction",
        ):
            value = trace[field]
            if not isinstance(value, str) or not value.strip():
                raise ValidationError(f"{label}.{field} must be a non-empty string")
        if (
            not isinstance(trace["transition_problem_status"], str)
            or trace["transition_problem_status"] not in TRANSITION_PROBLEM_STATUSES
        ):
            raise ValidationError(f"{label}.transition_problem_status is invalid")
        references = _require_string_list(
            trace["evidence_ids"], f"{label}.evidence_ids", non_empty=True
        )
        if len(references) != len(set(references)):
            raise ValidationError(f"{label}.evidence_ids must contain unique identifiers")
        if evidence_ids is not None:
            unresolved = sorted(set(references) - evidence_ids)
            if unresolved:
                raise ValidationError(
                    f"{label}.evidence_ids contains unresolved evidence IDs: {unresolved}"
                )
        # Some valid traces describe a cross-family question shift and therefore
        # have no single family. When a trace does name one, it must resolve.
        if "family" in trace:
            family = trace["family"]
            if not isinstance(family, str) or not family.strip():
                raise ValidationError(
                    f"Active Field Map family_development_traces row {index}.family must be a non-empty identifier"
                )
            if family not in method_ids:
                raise ValidationError(
                    f"Active Field Map family_development_traces row {index}.family does not resolve"
                )
    if len(transition_ids) != len(set(transition_ids)):
        raise ValidationError(
            "Active Field Map family_development_traces.transition_id values must be unique"
        )
    require_references(
        "problem_method_matrix",
        label="problem_method_matrix",
        reference_field="problem",
        allowed_ids=bottleneck_ids,
    )
    require_references(
        "problem_method_matrix",
        label="problem_method_matrix",
        reference_field="method",
        allowed_ids=method_ids,
    )
    require_references(
        "assumption_effectiveness_failure_matrix",
        label="assumption_effectiveness_failure_matrix",
        reference_field="family",
        allowed_ids=method_ids,
    )

    if evidence_ids is not None:
        for field, label in (
            ("assumption_effectiveness_failure_matrix", "assumption_effectiveness_failure_matrix"),
        ):
            evidence_field = "source_ids"
            for index, raw in enumerate(_require_list(field_map, field, "Active Field Map"), 1):
                row = _require_mapping(raw, f"Active Field Map {label} row {index}")
                references = _require_string_list(
                    row.get(evidence_field),
                    f"Active Field Map {label} row {index}.{evidence_field}",
                    non_empty=True,
                )
                if len(references) != len(set(references)):
                    raise ValidationError(
                        f"Active Field Map {label} row {index}.{evidence_field} must contain unique identifiers"
                    )
                unresolved = sorted(set(references) - evidence_ids)
                if unresolved:
                    raise ValidationError(
                        f"Active Field Map {label} row {index}.{evidence_field} contains unresolved evidence IDs: {unresolved}"
                    )
    if provisional:
        return field_map
    coverage = _require_mapping(field_map["coverage_record"], "coverage_record")
    _require_fields(
        coverage,
        ("coverage_status", "research_effort_budget", "stopping_reason"),
        "coverage_record",
    )
    if coverage["coverage_status"] not in {"SUFFICIENT", "PARTIAL", "INSUFFICIENT"}:
        raise ValidationError("coverage_record.coverage_status is invalid")
    if coverage["coverage_status"] in {"PARTIAL", "INSUFFICIENT"}:
        coverage_gaps = _require_string_list(
            coverage.get("coverage_gaps"),
            "coverage_record.coverage_gaps",
            non_empty=True,
        )
        if len(coverage_gaps) != len(set(coverage_gaps)):
            raise ValidationError("coverage_record.coverage_gaps must contain unique entries")
    elif "coverage_gaps" in coverage:
        coverage_gaps = _require_string_list(
            coverage["coverage_gaps"],
            "coverage_record.coverage_gaps",
            non_empty=False,
        )
        if len(coverage_gaps) != len(set(coverage_gaps)):
            raise ValidationError("coverage_record.coverage_gaps must contain unique entries")
        if coverage_gaps:
            raise ValidationError(
                "coverage_record.coverage_status SUFFICIENT requires coverage_gaps to be empty"
            )
    return field_map


def validate_coverage_review(
    payload: Any,
    *,
    development_trace_count: int | None = None,
) -> dict[str, Any]:
    review = _require_mapping(payload, "coverage review")
    _require_fields(
        review,
        (
            "decision",
            "reasons",
            "gaps",
            "reviewer_run_id",
            "review_request_id",
            "reviewed_artifact_sha256",
            "run_id",
            "reviewer",
            "verdict_id",
            "reviewed_artifact_hashes",
            "evolution_assessment",
        ),
        "coverage review",
    )
    if review["decision"] not in {"CONTINUE", "CANDIDATE_SUFFICIENT"}:
        raise ValidationError("coverage review decision must be CONTINUE or CANDIDATE_SUFFICIENT")
    for field in ("reasons", "gaps"):
        if not isinstance(review[field], list) or any(
            not isinstance(item, str) or not item.strip() for item in review[field]
        ):
            raise ValidationError(f"coverage review {field} must be a list of non-empty strings")
    if review["decision"] == "CONTINUE" and not review["gaps"]:
        raise ValidationError("CONTINUE coverage review requires at least one concrete gap")
    if not review["reasons"]:
        raise ValidationError("coverage review requires at least one concrete reason")
    if not isinstance(review["reviewed_artifact_hashes"], dict):
        raise ValidationError("coverage review reviewed_artifact_hashes must be an object")

    assessment = _require_mapping(
        review["evolution_assessment"], "coverage review evolution_assessment"
    )
    _require_fields(
        assessment,
        EVOLUTION_ASSESSMENT_FIELDS + ("material_evolution_gaps",),
        "coverage review evolution_assessment",
    )
    has_gap = False
    for field in EVOLUTION_ASSESSMENT_FIELDS:
        dimension = _require_mapping(
            assessment[field], f"coverage review evolution_assessment.{field}"
        )
        required = ("status", "rationale", "basis") if field == "transition_causality" else (
            "status",
            "rationale",
        )
        _require_fields(
            dimension,
            required,
            f"coverage review evolution_assessment.{field}",
        )
        if (
            not isinstance(dimension["status"], str)
            or dimension["status"] not in {"PASS", "GAP"}
        ):
            raise ValidationError(
                f"coverage review evolution_assessment.{field}.status must be PASS or GAP"
            )
        if not isinstance(dimension["rationale"], str) or not dimension["rationale"].strip():
            raise ValidationError(
                f"coverage review evolution_assessment.{field}.rationale must be non-empty"
            )
        has_gap = has_gap or dimension["status"] == "GAP"

    transition = assessment["transition_causality"]
    basis = transition["basis"]
    if not isinstance(basis, str) or basis not in TRANSITION_CAUSALITY_BASES:
        raise ValidationError(
            "coverage review evolution_assessment.transition_causality.basis is invalid"
        )
    if development_trace_count is not None:
        if not isinstance(development_trace_count, int) or development_trace_count < 0:
            raise ValidationError("development_trace_count must be a non-negative integer")
        if development_trace_count > 0 and basis != "DECLARED_TRACES_REVIEWED":
            raise ValidationError(
                "non-empty development traces require DECLARED_TRACES_REVIEWED"
            )
        if development_trace_count == 0:
            if transition["status"] == "PASS" and basis != "NO_MATERIAL_TRANSITION_SUPPORTED":
                raise ValidationError(
                    "empty development traces with PASS require NO_MATERIAL_TRANSITION_SUPPORTED"
                )
            if transition["status"] == "GAP" and basis != "MATERIAL_TRANSITION_MISSING":
                raise ValidationError(
                    "empty development traces with GAP require MATERIAL_TRANSITION_MISSING"
                )
    if basis == "NO_MATERIAL_TRANSITION_SUPPORTED" and transition["status"] != "PASS":
        raise ValidationError("NO_MATERIAL_TRANSITION_SUPPORTED requires transition_causality PASS")
    if basis == "MATERIAL_TRANSITION_MISSING" and transition["status"] != "GAP":
        raise ValidationError("MATERIAL_TRANSITION_MISSING requires transition_causality GAP")

    material_gaps = _require_string_list(
        assessment["material_evolution_gaps"],
        "coverage review evolution_assessment.material_evolution_gaps",
    )
    if len(material_gaps) != len(set(material_gaps)):
        raise ValidationError(
            "coverage review evolution_assessment.material_evolution_gaps must contain unique entries"
        )
    if has_gap != bool(material_gaps):
        raise ValidationError(
            "evolution assessment GAP status and material_evolution_gaps must be mutually consistent"
        )
    missing_top_level = [gap for gap in material_gaps if gap not in review["gaps"]]
    if missing_top_level:
        raise ValidationError(
            "material evolution gaps must also appear verbatim in coverage review gaps"
        )
    if review["decision"] == "CANDIDATE_SUFFICIENT" and has_gap:
        raise ValidationError(
            "CANDIDATE_SUFFICIENT requires all evolution assessments to PASS; "
            "an evolution assessment GAP requires CONTINUE"
        )
    return review


def render_field_map(field_map: dict[str, Any]) -> str:
    coverage = field_map.get("coverage_record")
    lines = [
        "# Active Field Map",
        "",
        *( [
            f"coverage_status: {coverage['coverage_status']}",
            "coverage_record:",
            f"research_effort_budget: {json.dumps(coverage['research_effort_budget'], ensure_ascii=False)}",
            f"stopping_reason: {coverage['stopping_reason']}",
            "",
        ] if isinstance(coverage, dict) else ["map_lifecycle: INITIAL_PROVISIONAL", ""] ),
    ]
    for field in FIELD_MAP_FIELDS:
        if field not in field_map:
            continue
        title = field.replace("_", " ").title()
        lines.extend(
            [f"## {title}", "", "```json", json.dumps(field_map[field], ensure_ascii=False, indent=2), "```", ""]
        )
    return "\n".join(lines)


def validate_canonical_registry(state: dict, artifact_name: str) -> dict[str, Any]:
    record = (state.get("research_lit") or {}).get("accepted_artifacts", {}).get(artifact_name)
    if not isinstance(record, dict) or record.get("validator_result") != "PASS":
        raise ValidationError(
            f"{artifact_name} is not a Controller-accepted canonical artifact"
        )
    return record


def sha256_file(path: str | Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))
