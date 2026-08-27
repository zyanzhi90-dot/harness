#!/usr/bin/env python3
"""Deterministic checks for the literature landscape handoff.

This is intentionally a small contract verifier, not a scientific judge. It
checks that the artifacts needed for a landscape decision exist, are not
placeholders, and retain the minimum source-to-evidence lineage required by
the shared problem-discovery contract.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from arisctl.validators import FIELD_MAP_FIELDS, ValidationError, validate_field_map


REQUIRED_MANIFEST_KEYS = (
    "active_field_map",
    "evidence_registry",
    "literature_corpus",
    "source_admission_policy",
    "search_log",
)
VALID_COVERAGE_STATUSES = {"SUFFICIENT", "PARTIAL", "INSUFFICIENT"}
DECISION_GRADE_STATUSES = {"ADMIT_DECISION_GRADE", "USER_SUPPLIED_READ"}
FINAL_SCREENING_STATUSES = {"IN_SCOPE", "OUT_OF_SCOPE", "DUPLICATE"}
MANDATORY_FULLTEXT_PRIORITIES = {
    "RECENT_AUTHORITATIVE_REVIEWS",
    "HIGH_CITATION_BACKBONE",
}
REQUIRED_LEDGER_FIELDS = {
    "timestamp",
    "run_id",
    "stage",
    "action",
    "query_id",
    "query",
    "paper_id",
    "tool",
    "result_status",
    "admission_decision",
    "budget_before",
    "budget_after",
}
FORMAL_LEDGER_FIELDS = {
    "event_id",
    "artifact_sha256",
    "previous_record_sha256",
    "record_sha256",
}

REQUIRED_EVIDENCE_FIELDS = {
    "source_id",
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
}
FORMAL_EVIDENCE_FIELDS = {"read_event_id", "content_sha256"}


def _path(root: str | Path, relative: str) -> Path:
    candidate = Path(relative)
    return candidate if candidate.is_absolute() else Path(root) / candidate


def _read_jsonl(path: Path, label: str, errors: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        errors.append(f"{label} cannot be read: {exc}")
        return rows
    if not any(line.strip() for line in lines):
        errors.append(f"{label} is empty")
        return rows
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"{label} line {line_number} is not valid JSON: {exc.msg}")
            continue
        if not isinstance(value, dict):
            errors.append(f"{label} line {line_number} must be an object")
            continue
        rows.append(value)
    return rows


def _check_hash_chain(rows: list[dict[str, Any]], label: str, errors: list[str]) -> None:
    previous: str | None = None
    for index, row in enumerate(rows, 1):
        if row.get("previous_record_sha256") != previous:
            errors.append(f"{label} row {index} breaks the append-only hash chain")
            return
        recorded = row.get("record_sha256")
        unhashed = dict(row)
        unhashed.pop("record_sha256", None)
        canonical = json.dumps(
            unhashed, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        calculated = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        if recorded != calculated:
            errors.append(f"{label} row {index} has an invalid record hash")
            return
        previous = recorded


def _read_rendered_field_map(text: str, errors: list[str]) -> dict[str, Any] | None:
    """Recover the canonical JSON sections emitted by render_field_map()."""

    payload: dict[str, Any] = {}
    for field in FIELD_MAP_FIELDS:
        title = field.replace("_", " ").title()
        match = re.search(
            rf"(?ms)^## {re.escape(title)}\s*\n\s*```json\s*\n(.*?)\n```",
            text,
        )
        if match is None:
            errors.append(f"active_field_map is missing JSON section: {field}")
            continue
        try:
            payload[field] = json.loads(match.group(1))
        except json.JSONDecodeError as exc:
            errors.append(
                f"active_field_map {field} JSON section is invalid: {exc.msg}"
            )
    return payload if len(payload) == len(FIELD_MAP_FIELDS) else None


def audit_landscape(
    root: str | Path,
    workflow: dict[str, Any],
    *,
    state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a machine-readable landscape handoff verdict."""

    errors: list[str] = []
    manifest = workflow.get("artifact_manifest")
    if not isinstance(manifest, dict):
        return {"ok": False, "coverage_status": None, "errors": ["artifact_manifest is missing"]}
    missing_keys = [key for key in REQUIRED_MANIFEST_KEYS if not isinstance(manifest.get(key), str)]
    if missing_keys:
        errors.append(f"artifact_manifest is missing keys: {missing_keys}")
        return {"ok": False, "coverage_status": None, "errors": errors}

    paths = {key: _path(root, manifest[key]) for key in REQUIRED_MANIFEST_KEYS}
    for key, path in paths.items():
        if not path.is_file():
            errors.append(f"{key} artifact is missing: {manifest[key]}")

    coverage_status: str | None = None
    field_map_payload: dict[str, Any] | None = None
    field_map = paths["active_field_map"]
    if field_map.is_file():
        try:
            field_map_text = field_map.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            errors.append(f"active_field_map cannot be read: {exc}")
        else:
            if not field_map_text.strip():
                errors.append("active_field_map is empty")
            match = re.search(r"(?im)^\s*coverage_status\s*:\s*([A-Z_]+)\s*$", field_map_text)
            if not match or match.group(1) not in VALID_COVERAGE_STATUSES:
                errors.append("active_field_map must declare coverage_status")
            else:
                coverage_status = match.group(1)
            if not re.search(r"(?im)^\s*coverage_record\s*:", field_map_text):
                errors.append("active_field_map must include coverage_record")
            for field in ("research_effort_budget", "stopping_reason"):
                if not re.search(rf"(?im)^\s*{field}\s*:", field_map_text):
                    errors.append(f"active_field_map coverage_record must record {field}")
            # Controller-generated maps carry the JSON sections rendered by
            # render_field_map(). Keep the audit backward-compatible with the
            # legacy compact handoff used by unstructured runs.
            if re.search(r"(?m)^## Method Families\s*\n\s*```json", field_map_text):
                field_map_payload = _read_rendered_field_map(field_map_text, errors)

    evidence_rows: list[dict[str, Any]] = []
    corpus_rows: list[dict[str, Any]] = []
    formal = bool(state and state.get("controller_managed"))
    if paths["evidence_registry"].is_file():
        evidence_rows = _read_jsonl(paths["evidence_registry"], "evidence_registry", errors)
        if formal:
            _check_hash_chain(evidence_rows, "evidence_registry", errors)
    if paths["literature_corpus"].is_file():
        corpus_rows = _read_jsonl(paths["literature_corpus"], "literature_corpus", errors)
        if formal:
            _check_hash_chain(corpus_rows, "literature_corpus", errors)

    evidence_ids: set[str] = set()
    for index, row in enumerate(evidence_rows, 1):
        source_id = row.get("source_id")
        if not isinstance(source_id, str) or not source_id.strip():
            errors.append(f"evidence_registry row {index} has no source_id")
        else:
            if source_id in evidence_ids:
                errors.append(
                    f"evidence_registry row {index} duplicates Evidence Card source_id: {source_id}"
                )
            evidence_ids.add(source_id)
        required_evidence = REQUIRED_EVIDENCE_FIELDS | (FORMAL_EVIDENCE_FIELDS if formal else set())
        missing = sorted(required_evidence - set(row))
        if missing:
            errors.append(f"evidence_registry row {index} is missing fields: {missing}")

    if field_map_payload is not None:
        try:
            validate_field_map(field_map_payload, evidence_ids=evidence_ids)
        except ValidationError as exc:
            errors.append(f"active_field_map cross-reference validation failed: {exc}")

    latest_corpus: dict[str, dict[str, Any]] = {}
    for row in corpus_rows:
        if isinstance(row.get("source_id"), str) and row["source_id"].strip():
            latest_corpus[row["source_id"]] = row

    for index, row in enumerate(latest_corpus.values(), 1):
        source_id = row.get("source_id")
        if not isinstance(source_id, str) or not source_id.strip():
            errors.append(f"literature_corpus row {index} has no source_id")
            continue
        admission_status = row.get("admission_status")
        if not isinstance(admission_status, str) or not admission_status.strip():
            errors.append(f"literature_corpus row {index} has no admission_status")
            continue
        if admission_status in DECISION_GRADE_STATUSES and source_id not in evidence_ids:
            errors.append(
                f"literature_corpus row {index} ({source_id}) is decision-grade without an evidence card"
            )

    if formal and coverage_status == "SUFFICIENT":
        unresolved_screening: list[str] = []
        for source_id, row in latest_corpus.items():
            screening_status = row.get("screening_status")
            if screening_status not in FINAL_SCREENING_STATUSES:
                unresolved_screening.append(source_id)
                continue
            if not str(row.get("screening_reason") or "").strip():
                errors.append(f"literature candidate {source_id} lacks a screening reason")
            if screening_status != "IN_SCOPE":
                continue
            basis = row.get("screening_basis")
            abstract_unavailable = (
                basis == "TITLE_ONLY_ABSTRACT_UNAVAILABLE"
                and row.get("identity_status") == "verified"
                and row.get("identity_verification_status") == "complete"
                and not str(row.get("abstract") or "").strip()
            )
            if basis not in {"TITLE_ABSTRACT", "FULL_TEXT"} and not abstract_unavailable:
                errors.append(
                    f"in-scope candidate {source_id} was not screened from an abstract or full text"
                )
            if basis == "TITLE_ABSTRACT" and not str(row.get("abstract") or "").strip():
                errors.append(f"in-scope candidate {source_id} has no actual abstract")
            priority = row.get("reading_priority")
            if priority in MANDATORY_FULLTEXT_PRIORITIES and source_id not in evidence_ids:
                errors.append(
                    f"mandatory review/high-citation backbone paper {source_id} has no full-text Evidence Card"
                )
            if not row.get("fulltext_selected"):
                if not str(row.get("fulltext_selection_reason") or "").strip():
                    errors.append(
                        f"abstract-only candidate {source_id} lacks a representative-selection reason"
                    )
            elif (
                source_id not in evidence_ids
                and row.get("admission_status") != "ADMIT_DISCOVERY_ONLY"
            ):
                errors.append(
                    f"full-text-selected candidate {source_id} has no accepted Evidence Card"
                )
        if unresolved_screening:
            sample = ", ".join(unresolved_screening[:20])
            suffix = "" if len(unresolved_screening) <= 20 else ", ..."
            errors.append(
                "literature corpus has candidates without a final title/abstract screening "
                f"decision: count={len(unresolved_screening)}, sample={sample}{suffix}"
            )

    policy = paths["source_admission_policy"]
    if policy.is_file():
        try:
            policy_text = policy.read_text(encoding="utf-8")
            if not policy_text.strip():
                errors.append("source_admission_policy is empty")
            policy_compact = " ".join(policy_text.lower().split())
            if "citation" not in policy_compact or "elite" not in policy_compact:
                errors.append("source_admission_policy must state the citation/elite-venue gate")
            if "user" not in policy_compact or "supplied" not in policy_compact:
                errors.append("source_admission_policy must define the user-supplied track")
        except (OSError, UnicodeError) as exc:
            errors.append(f"source_admission_policy cannot be read: {exc}")

    ledger_rows: list[dict[str, Any]] = []
    search_log = paths["search_log"]
    if search_log.is_file():
        ledger_rows = _read_jsonl(search_log, "search_log", errors)
        if formal:
            _check_hash_chain(ledger_rows, "search_log", errors)
        for index, row in enumerate(ledger_rows, 1):
            required_ledger = REQUIRED_LEDGER_FIELDS | (FORMAL_LEDGER_FIELDS if formal else set())
            missing = sorted(required_ledger - set(row))
            if missing:
                errors.append(f"search_log row {index} is missing fields: {missing}")
        completed_queries = {
            row.get("query_id")
            for row in ledger_rows
            if row.get("action") == "query"
            and row.get("result_status") in {"complete", "complete_human", "failed"}
        }
        if not completed_queries:
            errors.append("search_log has no terminal real query action")
        if formal:
            completed_reads = {
                row.get("event_id"): row
                for row in ledger_rows
                if row.get("action") == "fulltext" and row.get("result_status") == "complete"
            }
            for index, evidence in enumerate(evidence_rows, 1):
                event = completed_reads.get(evidence.get("read_event_id"))
                if (
                    event is None
                    or event.get("paper_id") != evidence.get("source_id")
                    or event.get("artifact_sha256") != evidence.get("content_sha256")
                ):
                    errors.append(
                        f"evidence_registry row {index} is not linked to a completed full-text event"
                    )

    if state is not None:
        research = state.get("research_lit") or {}
        accepted = research.get("accepted_artifacts") or {}
        for name in ("active_field_map", "coverage_review", "source_admission_policy"):
            record = accepted.get(name)
            if not isinstance(record, dict) or record.get("validator_result") != "PASS":
                errors.append(f"{name} is not registered as Controller-accepted")
        accepted_evidence = {
            key.split(":", 1)[1]
            for key, record in accepted.items()
            if key.startswith("evidence:")
            and isinstance(record, dict)
            and record.get("validator_result") == "PASS"
        }
        missing_acceptance = sorted(evidence_ids - accepted_evidence)
        if missing_acceptance:
            errors.append(
                "evidence cards exist without Controller acceptance: "
                + ", ".join(missing_acceptance)
            )
        if coverage_status == "SUFFICIENT":
            unfinished = [
                item.get("plan_item_id") or item.get("query")
                for item in research.get("planned_queries") or []
                if item.get("status") not in {"complete", "complete_human", "failed"}
            ]
            if unfinished:
                errors.append(
                    "coverage SUFFICIENT has unfinished query-plan items: "
                    + ", ".join(str(item) for item in unfinished[:10])
                )
        if research.get("query_count") != len(completed_queries):
            errors.append(
                "query counter does not match real completed/failed gateway actions"
            )
        if research.get("fulltext_count") != len(research.get("read_events") or {}):
            errors.append("full-text counter does not match Controller read events")
        for name, record in accepted.items():
            if not isinstance(record, dict) or not record.get("sha256"):
                continue
            artifact = _path(root, str(record.get("path") or ""))
            if not artifact.is_file():
                errors.append(f"accepted artifact is missing: {name}")
                continue
            digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
            if digest != record["sha256"]:
                errors.append(f"accepted artifact changed after validation: {name}")

    return {"ok": not errors, "coverage_status": coverage_status, "errors": errors}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", help="run root containing idea-stage artifacts")
    parser.add_argument("--workflow", required=True, help="JSON-compatible YAML workflow manifest")
    args = parser.parse_args()
    workflow = json.loads(Path(args.workflow).read_text(encoding="utf-8"))
    result = audit_landscape(args.root, workflow)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
