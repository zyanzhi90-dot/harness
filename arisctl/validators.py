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
    """Normalize the stable IDs used to close a method route to diagnosis."""

    values = _require_string_list(value, label, non_empty=non_empty)
    if len(values) != len(set(values)):
        raise ValidationError(f"{label} must contain unique identifiers")
    return values


def _validate_method_binding(
    payload: dict[str, Any],
    *,
    label: str,
    problem_version: dict[str, Any],
    root_cause_analysis_id: str,
    root_cause_analysis_sha256: str,
) -> None:
    """Check a route artifact's immutable upstream identity, not its quality."""

    _require_fields(
        payload,
        (
            "problem_id", "problem_version", "problem_contract_sha256",
            "evidence_capsule_sha256", "root_cause_analysis_id",
            "root_cause_analysis_sha256",
        ),
        label,
    )
    expected = {
        "problem_id": problem_version["problem_id"],
        "problem_version": problem_version["version"],
        "problem_contract_sha256": problem_version["contract_sha256"],
        "evidence_capsule_sha256": problem_version["evidence_capsule_sha256"],
        "root_cause_analysis_id": root_cause_analysis_id,
        "root_cause_analysis_sha256": root_cause_analysis_sha256,
    }
    for field, expected_value in expected.items():
        if payload[field] != expected_value:
            raise ValidationError(f"{label} {field} does not match the active handoff")
    if not isinstance(payload["problem_version"], int) or payload["problem_version"] < 1:
        raise ValidationError(f"{label} problem_version must be a positive integer")
    _require_sha256(payload["problem_contract_sha256"], f"{label}.problem_contract_sha256")
    _require_sha256(payload["evidence_capsule_sha256"], f"{label}.evidence_capsule_sha256")
    _require_sha256(payload["root_cause_analysis_sha256"], f"{label}.root_cause_analysis_sha256")


def validate_design_obligation_set(
    payload: Any,
    *,
    label: str,
    problem_version: dict[str, Any],
    root_cause_analysis_id: str,
    root_cause_analysis_sha256: str,
    primary_causal_chain_ids: set[str],
) -> dict[str, Any]:
    """Validate and normalize one diagnosis-derived Design Obligation set.

    The same set is carried either by complete method routes or a live
    method-search Query Plan. This remains a structural/provenance check only.
    """

    record = _require_mapping(payload, label)
    _require_fields(
        record,
        ("design_obligation_set_id", "causal_chain_ids", "design_obligations"),
        label,
    )
    set_id = record["design_obligation_set_id"]
    if not isinstance(set_id, str) or not set_id.strip():
        raise ValidationError(f"{label} ID must be a non-empty string")
    _validate_method_binding(
        record,
        label=label,
        problem_version=problem_version,
        root_cause_analysis_id=root_cause_analysis_id,
        root_cause_analysis_sha256=root_cause_analysis_sha256,
    )
    chain_ids = _method_identifier_list(record["causal_chain_ids"], f"{label}.causal_chain_ids")
    unknown_chains = set(chain_ids) - primary_causal_chain_ids
    if unknown_chains:
        raise ValidationError(
            f"{label} references unknown primary causal chains: {sorted(unknown_chains)}"
        )
    obligations = _require_list(record, "design_obligations", label, non_empty=True)
    normalized_obligations: list[dict[str, Any]] = []
    obligation_ids: list[str] = []
    must_ids: list[str] = []
    should_ids: list[str] = []
    for index, raw_obligation in enumerate(obligations, 1):
        obligation = _require_mapping(raw_obligation, f"{label} obligation {index}")
        _require_fields(
            obligation,
            (
                "obligation_id", "derived_from_causal_chain_ids", "required_capability",
                "why_current_methods_fail", "measurable_acceptance_condition", "priority",
            ),
            f"{label} obligation {index}",
        )
        obligation_id = obligation["obligation_id"]
        if (
            not isinstance(obligation_id, str) or not obligation_id.strip()
            or obligation_id in obligation_ids
        ):
            raise ValidationError(f"{label} obligation IDs must be non-empty and unique")
        derived_chains = _method_identifier_list(
            obligation["derived_from_causal_chain_ids"],
            f"{label} obligation {obligation_id}.derived_from_causal_chain_ids",
        )
        unknown_derived = set(derived_chains) - set(chain_ids)
        if unknown_derived:
            raise ValidationError(
                f"{label} obligation {obligation_id} references chains outside its set: "
                f"{sorted(unknown_derived)}"
            )
        for field in (
            "required_capability", "why_current_methods_fail", "measurable_acceptance_condition"
        ):
            if not isinstance(obligation[field], str) or not obligation[field].strip():
                raise ValidationError(
                    f"{label} obligation {obligation_id}.{field} must be a non-empty string"
                )
        if obligation["priority"] not in {"MUST", "SHOULD"}:
            raise ValidationError(f"{label} obligation {obligation_id}.priority must be MUST or SHOULD")
        normalized_obligations.append(
            {
                "obligation_id": obligation_id,
                "derived_from_causal_chain_ids": sorted(derived_chains),
                "required_capability": obligation["required_capability"],
                "why_current_methods_fail": obligation["why_current_methods_fail"],
                "measurable_acceptance_condition": obligation["measurable_acceptance_condition"],
                "priority": obligation["priority"],
            }
        )
        obligation_ids.append(obligation_id)
        (must_ids if obligation["priority"] == "MUST" else should_ids).append(obligation_id)
    return {
        "design_obligation_set_id": set_id,
        "causal_chain_ids": sorted(chain_ids),
        "design_obligations": sorted(normalized_obligations, key=lambda item: item["obligation_id"]),
        "obligation_ids": sorted(obligation_ids),
        "must_obligation_ids": sorted(must_ids),
        "should_obligation_ids": sorted(should_ids),
    }


def validate_method_routes(
    text: str,
    *,
    problem_version: dict[str, Any],
    root_cause_analysis_id: str,
    root_cause_analysis_sha256: str,
    primary_causal_chain_ids: set[str],
) -> dict[str, dict[str, Any]]:
    """Validate one diagnosis-derived obligation set and the routes that reference it."""

    canonical: dict[str, Any] | None = None
    route_records: list[tuple[int, dict[str, Any]]] = []
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"method routes line {line_number} must be JSON") from exc
        record = _require_mapping(raw, f"method routes line {line_number}")
        record_type = record.get("record_type")
        if record_type == "design_obligation_set":
            if canonical is not None or route_records:
                raise ValidationError("method routes must declare exactly one design-obligation set before routes")
            _require_fields(
                record,
                (
                    "schema_version", "record_type", "design_obligation_set_id",
                    "causal_chain_ids", "design_obligations",
                ),
                "design-obligation set",
            )
            if record["schema_version"] != 2:
                raise ValidationError("design-obligation set schema_version must be 2")
            canonical = validate_design_obligation_set(
                record,
                label="design-obligation set",
                problem_version=problem_version,
                root_cause_analysis_id=root_cause_analysis_id,
                root_cause_analysis_sha256=root_cause_analysis_sha256,
                primary_causal_chain_ids=primary_causal_chain_ids,
            )
        elif record_type == "method_route":
            route_records.append((line_number, record))
        else:
            raise ValidationError(
                "method routes records must be design_obligation_set or method_route"
            )

    if canonical is None:
        raise ValidationError("method routes must begin with one canonical design-obligation set")
    if not route_records:
        raise ValidationError("method routes must contain at least one route")

    routes: dict[str, dict[str, Any]] = {}
    for line_number, route in route_records:
        _require_fields(
            route,
            (
                "schema_version", "record_type", "route_id", "design_obligation_set_id",
                "causal_chain_ids", "obligation_coverage",
                "dominant_solution", "dominant_solution_origin", "dominant_only_closure",
                "supporting_mechanisms",
            ),
            f"method route {line_number}",
        )
        if route["schema_version"] != 2:
            raise ValidationError(f"method route {line_number} schema_version must be 2")
        route_id = route["route_id"]
        if not isinstance(route_id, str) or not route_id.strip() or route_id in routes:
            raise ValidationError("method route IDs must be non-empty and unique")
        _validate_method_binding(
            route, label=f"method route {route_id}", problem_version=problem_version,
            root_cause_analysis_id=root_cause_analysis_id,
            root_cause_analysis_sha256=root_cause_analysis_sha256,
        )
        chain_ids = _method_identifier_list(
            route["causal_chain_ids"], f"method route {route_id}.causal_chain_ids"
        )
        if set(chain_ids) != set(canonical["causal_chain_ids"]):
            raise ValidationError(
                f"method route {route_id} causal_chain_ids must match the canonical design-obligation set"
            )
        if route["design_obligation_set_id"] != canonical["design_obligation_set_id"]:
            raise ValidationError(
                f"method route {route_id} must reference the canonical design-obligation set"
            )
        if "design_obligations" in route:
            raise ValidationError(
                f"method route {route_id} must not redefine canonical design obligations"
            )
        for field in ("dominant_solution", "dominant_solution_origin"):
            if not isinstance(route[field], str) or not route[field].strip():
                raise ValidationError(f"method route {route_id}.{field} must be a non-empty string")
        if route["dominant_solution_origin"] not in {
            "first_principles", "same_field", "cross_field", "hybrid"
        }:
            raise ValidationError(
                f"method route {route_id}.dominant_solution_origin must state whether the dominant solution is first-principles, same-field, cross-field, or hybrid"
            )
        coverage = _require_mapping(
            route["obligation_coverage"], f"method route {route_id}.obligation_coverage"
        )
        _require_fields(
            coverage, ("covered_obligation_ids", "residual_obligation_ids"),
            f"method route {route_id}.obligation_coverage",
        )
        covered_ids = _method_identifier_list(
            coverage["covered_obligation_ids"],
            f"method route {route_id}.obligation_coverage.covered_obligation_ids", non_empty=False,
        )
        residual_ids = _method_identifier_list(
            coverage["residual_obligation_ids"],
            f"method route {route_id}.obligation_coverage.residual_obligation_ids", non_empty=False,
        )
        if (
            set(covered_ids) & set(residual_ids)
            or set(covered_ids) | set(residual_ids) != set(canonical["obligation_ids"])
        ):
            raise ValidationError(
                f"method route {route_id} obligation_coverage must classify every canonical obligation exactly once"
            )
        obligation_ids = canonical["obligation_ids"]
        must_ids = canonical["must_obligation_ids"]
        should_ids = canonical["should_obligation_ids"]
        closure = _require_mapping(
            route["dominant_only_closure"], f"method route {route_id}.dominant_only_closure"
        )
        _require_fields(
            closure, ("satisfied_obligation_ids", "residual_must_obligation_ids"),
            f"method route {route_id}.dominant_only_closure",
        )
        satisfied_ids = _method_identifier_list(
            closure["satisfied_obligation_ids"],
            f"method route {route_id}.dominant_only_closure.satisfied_obligation_ids",
        )
        residual_must_ids = _method_identifier_list(
            closure["residual_must_obligation_ids"],
            f"method route {route_id}.dominant_only_closure.residual_must_obligation_ids",
            non_empty=False,
        )
        if set(satisfied_ids) - set(obligation_ids) or set(residual_must_ids) - set(must_ids):
            raise ValidationError(
                f"method route {route_id} dominant-only closure must only name route obligations and residual MUST obligations"
            )
        if set(satisfied_ids) & set(residual_must_ids) or set(must_ids) != set(satisfied_ids) & set(must_ids) | set(residual_must_ids):
            raise ValidationError(
                f"method route {route_id} dominant-only closure must classify every MUST obligation exactly once"
            )
        supporting = _require_list(route, "supporting_mechanisms", f"method route {route_id}", non_empty=False)
        covered_residuals: set[str] = set()
        for index, raw_support in enumerate(supporting, 1):
            support = _require_mapping(raw_support, f"method route {route_id} supporting mechanism {index}")
            _require_fields(
                support,
                (
                    "mechanism_id", "residual_must_obligation_ids", "mechanism_match",
                    "activation_condition", "integration_interface", "removal_failure_prediction",
                ),
                f"method route {route_id} supporting mechanism {index}",
            )
            if not isinstance(support["mechanism_id"], str) or not support["mechanism_id"].strip():
                raise ValidationError(f"method route {route_id} supporting mechanism IDs must be non-empty")
            support_ids = _method_identifier_list(
                support["residual_must_obligation_ids"],
                f"method route {route_id} supporting mechanism {support['mechanism_id']}.residual_must_obligation_ids",
            )
            if set(support_ids) - set(residual_must_ids):
                raise ValidationError(
                    f"method route {route_id} supporting mechanism {support['mechanism_id']} serves no declared residual MUST gap"
                )
            for field in ("mechanism_match", "activation_condition", "integration_interface", "removal_failure_prediction"):
                if not isinstance(support[field], str) or not support[field].strip():
                    raise ValidationError(
                        f"method route {route_id} supporting mechanism {support['mechanism_id']}.{field} must be a non-empty string"
                    )
            covered_residuals.update(support_ids)
        if covered_residuals != set(residual_must_ids):
            raise ValidationError(
                f"method route {route_id} must bind every residual MUST gap to a necessary supporting mechanism"
            )
        routes[route_id] = {
            "route_id": route_id,
            "design_obligation_set_id": canonical["design_obligation_set_id"],
            "causal_chain_ids": chain_ids,
            "obligation_ids": obligation_ids,
            "must_obligation_ids": must_ids,
            "should_obligation_ids": should_ids,
        }
    return routes


def validate_method_routes_view(
    text: str,
    *,
    routes: dict[str, dict[str, Any]],
    problem_version: dict[str, Any],
    root_cause_analysis_id: str,
    root_cause_analysis_sha256: str,
) -> None:
    """Ensure the human route packet exposes the machine index's closure IDs."""

    if not isinstance(text, str) or not text.strip():
        raise ValidationError("method routes Markdown view must be non-empty")
    required_tokens = [
        str(problem_version["problem_id"]), str(problem_version["version"]),
        str(problem_version["contract_sha256"]), str(problem_version["evidence_capsule_sha256"]),
        root_cause_analysis_id, root_cause_analysis_sha256,
    ]
    for route in routes.values():
        required_tokens.extend(route["causal_chain_ids"])
        required_tokens.append(route["route_id"])
        required_tokens.append(route["design_obligation_set_id"])
        required_tokens.extend(route["obligation_ids"])
    missing = [token for token in required_tokens if token not in text]
    if missing:
        raise ValidationError(
            f"method routes Markdown view omits canonical route references: {sorted(set(missing))}"
        )


def validate_selected_route(
    payload: Any,
    *,
    routes: dict[str, dict[str, Any]],
    problem_version: dict[str, Any],
    root_cause_analysis_id: str,
    root_cause_analysis_sha256: str,
    expected_selected_id: str | None = None,
) -> dict[str, Any]:
    """Validate the selected route as an exact reference to one route index row."""

    selection = _require_mapping(payload, "selected route")
    _require_fields(
        selection,
        ("schema_version", "route_id", "design_obligation_set_id", "causal_chain_ids", "obligation_ids"),
        "selected route",
    )
    if selection["schema_version"] != 1:
        raise ValidationError("selected route schema_version must be 1")
    route_id = selection["route_id"]
    if not isinstance(route_id, str) or route_id not in routes:
        raise ValidationError("selected route route_id does not identify a current method route")
    if expected_selected_id is not None and route_id != expected_selected_id:
        raise ValidationError("selected route route_id does not match the Human selected_id")
    _validate_method_binding(
        selection, label="selected route", problem_version=problem_version,
        root_cause_analysis_id=root_cause_analysis_id,
        root_cause_analysis_sha256=root_cause_analysis_sha256,
    )
    route = routes[route_id]
    if selection["design_obligation_set_id"] != route["design_obligation_set_id"]:
        raise ValidationError("selected route design_obligation_set_id does not match the selected method route")
    chain_ids = _method_identifier_list(selection["causal_chain_ids"], "selected route.causal_chain_ids")
    obligation_ids = _method_identifier_list(selection["obligation_ids"], "selected route.obligation_ids")
    if set(chain_ids) != set(route["causal_chain_ids"]):
        raise ValidationError("selected route causal_chain_ids do not match the selected method route")
    if set(obligation_ids) != set(route["obligation_ids"]):
        raise ValidationError("selected route obligation_ids do not match the selected method route")
    return {
        "route_id": route_id,
        "design_obligation_set_id": route["design_obligation_set_id"],
        "causal_chain_ids": chain_ids,
        "obligation_ids": obligation_ids,
        "must_obligation_ids": route["must_obligation_ids"],
        "should_obligation_ids": route["should_obligation_ids"],
    }


def validate_final_proposal(
    text: str,
    *,
    selected_route: dict[str, Any],
    problem_version: dict[str, Any],
    root_cause_analysis_id: str,
    root_cause_analysis_sha256: str,
) -> None:
    """Validate FINAL_PROPOSAL's typed Markdown binding to the selected route."""

    proposal = {
        "problem_id": _markdown_field(text, "Problem ID", "final proposal"),
        "problem_version": _markdown_field(text, "Problem version", "final proposal"),
        "problem_contract_sha256": _markdown_field(text, "Problem-contract SHA-256", "final proposal"),
        "evidence_capsule_sha256": _markdown_field(text, "Problem-evidence-capsule SHA-256", "final proposal"),
        "root_cause_analysis_id": _markdown_field(text, "Root-cause analysis ID", "final proposal"),
        "root_cause_analysis_sha256": _markdown_field(text, "Root-cause analysis SHA-256", "final proposal"),
    }
    try:
        proposal["problem_version"] = int(proposal["problem_version"])
    except ValueError as exc:
        raise ValidationError("final proposal Problem version must be an integer") from exc
    _validate_method_binding(
        proposal, label="final proposal", problem_version=problem_version,
        root_cause_analysis_id=root_cause_analysis_id,
        root_cause_analysis_sha256=root_cause_analysis_sha256,
    )
    route_id = _markdown_field(text, "Selected route ID", "final proposal")
    if route_id != selected_route["route_id"]:
        raise ValidationError("final proposal Selected route ID does not match the selected route")
    obligation_set_id = _markdown_field(text, "Design-obligation set ID", "final proposal")
    if obligation_set_id != selected_route["design_obligation_set_id"]:
        raise ValidationError("final proposal Design-obligation set ID does not match the selected route")
    chain_ids = _method_identifier_list(
        [item.strip().strip("`") for item in _markdown_field(text, "Causal-chain IDs", "final proposal").split(",")],
        "final proposal Causal-chain IDs",
    )
    must_ids = _method_identifier_list(
        [item.strip().strip("`") for item in _markdown_field(text, "MUST design-obligation IDs", "final proposal").split(",")],
        "final proposal MUST design-obligation IDs",
    )
    obligation_ids = _method_identifier_list(
        [item.strip().strip("`") for item in _markdown_field(text, "Design-obligation IDs", "final proposal").split(",")],
        "final proposal Design-obligation IDs",
    )
    if set(chain_ids) != set(selected_route["causal_chain_ids"]):
        raise ValidationError("final proposal must preserve every selected-route causal chain")
    if set(must_ids) != set(selected_route["must_obligation_ids"]):
        raise ValidationError("final proposal must preserve every selected-route MUST obligation")
    dispositions_raw = _markdown_field(text, "SHOULD obligation dispositions", "final proposal")
    should_ids = set(selected_route["should_obligation_ids"])
    if not should_ids:
        if dispositions_raw.lower() != "none":
            raise ValidationError("final proposal has no SHOULD obligations, so its disposition must be 'none'")
        dispositions: dict[str, str] = {}
    else:
        dispositions = {}
        for token in dispositions_raw.split(","):
            parts = token.strip().strip("`").split("=", 1)
            if len(parts) != 2 or parts[1].strip().split(":", 1)[0] not in {"retained", "waived", "superseded"}:
                raise ValidationError("SHOULD obligation dispositions must use ID=retained|waived:reason|superseded:reason")
            obligation_id, decision = parts[0].strip(), parts[1].strip()
            status = decision.split(":", 1)[0]
            if not obligation_id or obligation_id in dispositions or (status != "retained" and not decision.partition(":")[2].strip()):
                raise ValidationError("each waived or superseded SHOULD obligation requires an explicit reason")
            dispositions[obligation_id] = status
        if set(dispositions) != should_ids:
            raise ValidationError("final proposal must explicitly retain, waive, or supersede every selected-route SHOULD obligation")
    retained_should = {key for key, value in dispositions.items() if value == "retained"}
    if set(obligation_ids) != set(must_ids) | retained_should:
        raise ValidationError("final proposal Design-obligation IDs must contain all MUST and only retained SHOULD obligations")


def validate_root_cause_analysis(
    payload: Any,
    *,
    run_id: str,
    problem_contract_sha256: str,
    evidence_capsule_sha256: str,
    active_problem_id: str | None = None,
    formal_evidence_sources: dict[str, str] | None = None,
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
) -> dict[str, Any]:
    """Validate an independent Root-Cause Gate verdict and its artifact bindings."""
    verdict = _require_mapping(payload, "root-cause verdict")
    _require_fields(
        verdict,
        (
            "schema_version", "run_id", "verdict_id", "reviewer", "analysis_id",
            "reviewed_analysis_sha256", "problem_contract_sha256", "evidence_capsule_sha256",
            "decision", "reasons", "issues", "observation_fidelity", "grouping_adequacy",
            "causal_depth", "explanatory_coverage", "evidence_calibration",
            "intervention_relevance", "falsifiability",
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
    ):
        if verdict[field] not in {"PASS", "FAIL", "UNCERTAIN"}:
            raise ValidationError(f"root-cause verdict {field} must be PASS, FAIL, or UNCERTAIN")
    if verdict["decision"] == "DIAGNOSIS_READY" and any(
        verdict[field] != "PASS"
        for field in (
            "observation_fidelity", "grouping_adequacy", "causal_depth", "explanatory_coverage",
            "evidence_calibration", "intervention_relevance", "falsifiability",
        )
    ):
        raise ValidationError(
            "DIAGNOSIS_READY requires PASS on all seven root-cause scientific rubrics"
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
    problem_lead_context: dict[str, Any] | None = None,
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
    canonical_method_obligations: dict[str, Any] | None = None
    declared_residual_must_ids: set[str] | None = None
    if method_design_context is not None:
        context = _require_mapping(
            plan.get("method_design_context"), "query plan method_design_context"
        )
        _require_fields(
            context,
            (
                "root_cause_analysis_id", "root_cause_analysis_sha256",
                "active_field_map_sha256", "search_mode", "design_obligation_set_id",
                "problem_id", "problem_version", "problem_contract_sha256",
                "evidence_capsule_sha256", "causal_chain_ids", "design_obligations",
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
        if method_search_mode not in {
            "DOMINANT_SOLUTION_SEARCH", "RESIDUAL_MUST_GAP_SEARCH"
        }:
            raise ValidationError("query plan method_design_context.search_mode is invalid")
        canonical_method_obligations = validate_design_obligation_set(
            context,
            label="query plan method_design_context",
            problem_version=method_design_context["problem_version"],
            root_cause_analysis_id=method_design_context["root_cause_analysis_id"],
            root_cause_analysis_sha256=method_design_context["root_cause_analysis_sha256"],
            primary_causal_chain_ids=set(method_design_context["primary_causal_chain_ids"]),
        )
        if method_search_mode == "RESIDUAL_MUST_GAP_SEARCH":
            _require_fields(
                context,
                ("dominant_solution", "dominant_only_closure"),
                "query plan method_design_context",
            )
            if not isinstance(context["dominant_solution"], str) or not context["dominant_solution"].strip():
                raise ValidationError("query plan method_design_context.dominant_solution must be non-empty")
            closure = _require_mapping(
                context["dominant_only_closure"], "query plan method_design_context dominant_only_closure"
            )
            _require_fields(
                closure, ("satisfied_obligation_ids", "residual_must_obligation_ids"),
                "query plan method_design_context dominant_only_closure",
            )
            obligation_ids = set(canonical_method_obligations["obligation_ids"])
            must_ids = set(canonical_method_obligations["must_obligation_ids"])
            satisfied = set(_method_identifier_list(
                closure["satisfied_obligation_ids"],
                "query plan method-design dominant-only satisfied_obligation_ids",
            ))
            residual = set(_method_identifier_list(
                closure["residual_must_obligation_ids"],
                "query plan method-design dominant-only residual_must_obligation_ids",
                non_empty=False,
            ))
            if not residual:
                raise ValidationError(
                    "method-design residual search requires a declared residual MUST gap"
                )
            if satisfied - obligation_ids or residual - must_ids or satisfied & residual:
                raise ValidationError("query plan method-design dominant-only closure has invalid obligation IDs")
            if must_ids != (satisfied & must_ids) | residual:
                raise ValidationError(
                    "query plan method-design dominant-only closure must classify every MUST obligation exactly once"
                )
            declared_residual_must_ids = residual

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
        if method_search_mode == "DOMINANT_SOLUTION_SEARCH":
            assert canonical_method_obligations is not None
            _require_fields(
                item, ("design_obligation_ids", "causal_chain_ids"),
                f"query plan dominant-solution item {index}",
            )
            target_ids = set(_method_identifier_list(
                item["design_obligation_ids"],
                f"query plan dominant-solution item {index}.design_obligation_ids",
            ))
            known_ids = set(canonical_method_obligations["obligation_ids"])
            if not target_ids <= known_ids:
                raise ValidationError(
                    f"query plan dominant-solution item {index} targets obligations outside the current set"
                )
            expected_chains = {
                chain_id
                for obligation in canonical_method_obligations["design_obligations"]
                if obligation["obligation_id"] in target_ids
                for chain_id in obligation["derived_from_causal_chain_ids"]
            }
            item_chains = set(_method_identifier_list(
                item["causal_chain_ids"],
                f"query plan dominant-solution item {index}.causal_chain_ids",
            ))
            if item_chains != expected_chains:
                raise ValidationError(
                    f"query plan dominant-solution item {index} causal chains do not match its obligations"
                )
        if declared_residual_must_ids is not None:
            _require_fields(
                item, ("decision_target", "residual_must_obligation_ids"),
                f"query plan method-design item {index}",
            )
            if not isinstance(item["decision_target"], str) or not item["decision_target"].strip():
                raise ValidationError(
                    f"query plan method-design item {index}.decision_target must be non-empty"
                )
            target_ids = set(_method_identifier_list(
                item["residual_must_obligation_ids"],
                f"query plan method-design item {index}.residual_must_obligation_ids",
            ))
            if not target_ids <= declared_residual_must_ids:
                raise ValidationError(
                    f"query plan method-design item {index} targets no declared residual MUST gap"
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
