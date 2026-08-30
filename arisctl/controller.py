"""Single workflow authority for formal ARIS research-literature runs."""

from __future__ import annotations

import json
import hashlib
import os
import re
import shutil
import subprocess
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from tools import run_state
from tools.literature_coverage_audit import audit_landscape
from tools.provenance import model_family

from . import approvals, reviews
from .gateways import (
    FullTextPayload,
    HumanSearchRequired,
    MetadataVerifyCallable,
    ReadCallable,
    SearchCallable,
    SearchOutcome,
    append_jsonl,
    ledger_event,
    now,
    ProviderUnavailable,
    repair_embedded_record_hash_contamination,
)
from .state import _StateStore
from .project_setup import (
    ProjectRuntimeError,
    install_project_codex_layer,
    verify_formal_native_subagent_runtime,
)
from .validators import (
    ValidationError,
    validate_method_test_result,
    validate_principle_evidence_context,
    validate_selected_principle,
    render_field_map,
    render_method_design_view,
    render_principle_test_plan_view,
    sha256_file,
    validate_canonical_registry,
    validate_coverage_review,
    validate_evidence_card,
    validate_field_map,
    validate_problem_candidates_artifact,
    validate_query_plan,
    validate_problem_acceptance_handoff,
    validate_problem_capsule_nonliterature_artifacts,
    validate_source_admission_policy,
)
from .workflow import canonical_workflow_path, load_workflow


class ControllerError(RuntimeError):
    pass


READABLE_ADMISSION_STATUSES = {
    "ADMIT_FOR_READING",
    "ADMIT_DECISION_GRADE",
    "USER_SUPPLIED_READ",
}

SCREENING_BASES = {
    "TITLE_ONLY",
    "TITLE_ABSTRACT",
    "TITLE_ONLY_ABSTRACT_UNAVAILABLE",
    "FULL_TEXT",
}
SCREENING_FINAL_STATUSES = {"IN_SCOPE", "OUT_OF_SCOPE", "DUPLICATE"}
READING_PRIORITY_TIERS = {
    "RECENT_AUTHORITATIVE_REVIEWS",
    "HIGH_CITATION_BACKBONE",
    "RECENT_ELITE_FRONTIER",
    "TARGETED_GAP_FOLLOWUP",
}
MANDATORY_FULLTEXT_PRIORITIES = {
    "RECENT_AUTHORITATIVE_REVIEWS",
    "HIGH_CITATION_BACKBONE",
}

DECISION_GRADE_EXCEPTION_KINDS = {
    "decisive_closest_prior_or_concurrent",
    "negative_or_contradictory_result",
    "diagnostic_or_replication_evidence",
}


def _has_formal_source_identity(paper: dict[str, Any]) -> bool:
    """Accept gateway verification or Controller-registered local provenance."""
    return paper.get("identity_status") == "verified" or (
        paper.get("source_origin") == "user_supplied"
        and bool(str(paper.get("source_path") or "").strip())
        and bool(str(paper.get("source_sha256") or "").strip())
    )


def _merge_discovery_metadata(
    existing: dict[str, Any] | None,
    discovered: dict[str, Any],
) -> dict[str, Any]:
    """Merge a repeated discovery without rolling a paper back before its formal state."""
    if not existing:
        return dict(discovered)

    found_by = sorted(
        set(existing.get("found_by_query_ids") or [])
        | set(discovered.get("found_by_query_ids") or [])
    )
    has_formal_identity_or_decision = (
        existing.get("identity_status") == "verified"
        or existing.get("admission_status") != "DISCOVERY_METADATA_ONLY"
    )
    if not has_formal_identity_or_decision:
        merged = dict(discovered)
        merged["found_by_query_ids"] = found_by
        return merged

    # A new search result may refresh discovery-only counters/snippets, but it
    # cannot erase a verified identity, admission/withdrawal decision, user
    # full text, or any later paper-level provenance.
    merged = dict(existing)
    for key in (
        "citation_count",
        "cited_by_id",
        "cited_by_url",
        "snippet",
        "discovery_provider",
    ):
        if discovered.get(key) is not None:
            merged[key] = discovered[key]
    merged["found_by_query_ids"] = found_by
    return merged


# This is a Controller-issued validation handoff, not an additional workflow
# phase. The current canonical workflow ends with method confirmation and
# deliberately leaves experiment initiation to the user; a downstream skill
# must nevertheless prove that it is consuming that confirmed Principle/Method rather
# than reconstructing one from free text or historical files.
FORMAL_VALIDATION_HANDOFF_ARTIFACTS = {
    "idea-stage/RESEARCH_CONTRACT.md": ("problem_human_acceptance", "human_accepted"),
    "idea-stage/ROOT_CAUSE_ANALYSIS.json": ("root_cause_analysis", "done"),
    "idea-stage/ROOT_CAUSE_VERDICT.json": ("root_cause_gate", "accepted"),
    "idea-stage/SELECTED_PRINCIPLE.yaml": ("principle_evaluation", "accepted"),
    "refine-logs/FINAL_PROPOSAL.md": ("method_refinement", "accepted"),
    "idea-stage/FINAL_METHOD_NOVELTY_VERDICT.md": (
        "final_method_novelty_gate",
        "accepted",
    ),
    "idea-stage/IDEA_REPORT.md": ("final_method_human_acceptance", "human_accepted"),
}


# Validation remains outside the canonical phase sequence: it is started only
# when the user asks to validate an accepted method.  These are the only
# evidence-backed outcomes that can reopen that sequence, and each has one
# fixed target so a downstream result cannot choose an arbitrary rollback.
VALIDATION_RESULT_RETURN_TARGETS = {
    "METHOD_REFINEMENT_REQUIRED": "method_refinement",
    "SELECTED_PRINCIPLE_REJECTED": "method_design",
    "ROOT_CAUSE_REJECTED": "root_cause_analysis",
    "PROBLEM_PREMISE_REJECTED": "problem_generation",
}
VALIDATION_RESULT_DECISIONS = {"VALIDATED", *VALIDATION_RESULT_RETURN_TARGETS}
VALIDATION_REVIEWER_ROLE = "result_to_claim_reviewer"
VALIDATION_REVIEW_REQUEST_TYPE = "FORMAL_VALIDATION_JUDGMENT"


class ARISController:
    def __init__(
        self,
        root: str | Path,
        run_id: str,
        workflow_path: str | Path | None = None,
    ):
        self.root = Path(root).resolve()
        self.run_id = run_id
        canonical = canonical_workflow_path()
        requested = Path(workflow_path).resolve() if workflow_path is not None else canonical
        if requested != canonical:
            raise ControllerError(
                "formal runs must use the checked-in canonical idea-workflow.yaml"
            )
        self.workflow_path = canonical
        self.workflow = load_workflow(self.workflow_path)
        self.workflow_sha256 = sha256_file(self.workflow_path)
        self._store = _StateStore(
            self.root,
            run_id,
            self.workflow_sha256,
            self.workflow,
        )

    @classmethod
    def start(
        cls,
        root: str | Path,
        run_id: str,
        workflow_path: str | Path | None = None,
        *,
        executor: str,
    ) -> "ARISController":
        controller = cls(root, run_id, workflow_path)
        try:
            install_project_codex_layer(controller.root)
        except ValueError as exc:
            raise ControllerError(str(exc)) from exc
        state_path = run_state._run_path(str(controller.root), run_id)
        if state_path.exists():
            existing = run_state._load(str(controller.root), run_id)
            if not existing.get("controller_managed"):
                raise ControllerError(
                    "existing legacy run cannot be converted in place; start a new formal run_id"
                )
            controller._store._verify(existing)
            return controller
        state = run_state.start_run(
            str(controller.root),
            run_id,
            [],
            executor=executor,
            workflow_path=str(controller.workflow_path),
        )
        with run_state._lock(str(controller.root), run_id):
            state = run_state._load(str(controller.root), run_id)
            state["controller_managed"] = True
            state["controller_version"] = 2
            state["workflow_sha256"] = controller.workflow_sha256
            budget = controller.workflow["research_effort_budget"]
            initial_stage = "SOURCE_POLICY_DRAFTING"
            waiting_for = None
            approval_request = None
            pending_source_policy = None
            validator_results: list[dict[str, Any]] = []
            policy_path = controller._paths()["source_admission_policy"]
            if policy_path.is_file():
                try:
                    validate_source_admission_policy(controller._load_policy())
                except (ControllerError, ValidationError) as exc:
                    validator_results.append(
                        {
                            "timestamp": now(),
                            "artifact": "source_admission_policy",
                            "result": "FAIL",
                            "errors": [str(exc)],
                        }
                    )
                else:
                    policy_sha256 = sha256_file(policy_path)
                    initial_stage = "WAITING_FOR_HUMAN"
                    waiting_for = "source_policy_approval"
                    approval_request = {
                        "id": uuid.uuid4().hex,
                        "gate": "source_policy_approval",
                        "artifact_sha256": policy_sha256,
                        "artifact_bindings": {
                            str(policy_path.relative_to(controller.root)): policy_sha256
                        },
                        "issued_by": "ARISController",
                        "created_at": now(),
                    }
                    pending_source_policy = {
                        "path": str(policy_path.relative_to(controller.root)),
                        "validator_result": "PASS",
                        "sha256": policy_sha256,
                        "author_role": "preexisting_project_policy",
                        "validated_at": now(),
                    }
                    validator_results.append(
                        {
                            "timestamp": now(),
                            "artifact": "source_admission_policy",
                            "result": "PASS",
                            "errors": [],
                        }
                    )
            state["research_lit"] = {
                "current_stage": initial_stage,
                "waiting_for": waiting_for,
                "query_count": 0,
                "fulltext_count": 0,
                "max_queries": budget["max_queries"],
                "max_fulltext_papers": budget["max_fulltext_papers"],
                "max_search_cycles": budget["max_search_cycles"],
                "search_cycle_count": 0,
                "papers": {},
                "query_events": {},
                "read_events": {},
                "planned_queries": [],
                "accepted_artifacts": {},
                "validator_results": validator_results,
                "approvals": [],
                "approval_request": approval_request,
                "pending_source_policy": pending_source_policy,
                "coverage_review_request": None,
                # The current Field Map or Coverage Review may require a
                # controlled replenishment search.  This is one shared
                # gap-binding channel, not a second review mechanism.
                "required_coverage_gaps": [],
                "human_search_request": None,
                "human_fulltext_request": None,
                # Phase-scoped additions share the one corpus, ledger and
                # Evidence Registry.  They are not a second literature run.
                "incremental_literature_active": None,
                "incremental_evidence_by_phase": {},
                # One live reading authorization is enough for landscape work.
                # It is deliberately separate from the durable screening and
                # admission records on each candidate.
                "active_reading_session": None,
                "initial_screened_corpus_ids": None,
                "initial_field_map_binding": None,
                "formal_primary_selection": None,
                "field_map_history": [],
                # This is a small history for the one mutable Query Plan
                # handoff.  It is populated only when an accepted plan has
                # already entered formal query provenance.
                "query_plan_history": [],
                "landscape_evidence_ids": [],
            }
            state["scientific_core"] = {
                "status": "NOT_STARTED",
                "current_phase": None,
                "accepted_artifacts": {},
                "invalidated_artifacts": [],
                "return_history": [],
                "lessons": [],
                "landscape_handoff": None,
                "approval_request": None,
                "review_request": None,
                "approvals": [],
                "transition_log": [],
                # One accepted problem may be revised, but its accepted hash is
                # never a mutable method-workspace input.  Version records are
                # intentionally a small linear history, not an artifact graph.
                "problem_versions": [],
                "active_problem_version": None,
                "pending_problem_revision": None,
                "problem_revision_request": None,
                "selected_for_testing": None,
                "method_test_cycle": None,
                "validation_entry": {
                    "status": "BLOCKED_UNTIL_METHOD_CONFIRMATION",
                    "entry_policy": "human_initiated_only",
                },
            }
            landscape = run_state._find_phase(state, "landscape")
            landscape["status"] = "running"
            run_state._save(str(controller.root), run_id, state)
        return controller

    @classmethod
    def migrate_legacy(
        cls,
        root: str | Path,
        run_id: str,
        *,
        executor: str,
    ) -> "ARISController":
        """Archive unverifiable history and bootstrap a clean formal rerun."""

        project = Path(root).resolve()
        legacy_manifest = project / ".aris" / "LEGACY_MIGRATION.json"
        if not legacy_manifest.is_file():
            raise ControllerError("legacy migration requires .aris/LEGACY_MIGRATION.json")
        state_path = run_state._run_path(str(project), run_id)
        if state_path.exists():
            return cls.start(project, run_id, executor=executor)

        archive = project / ".aris" / "legacy" / run_id / "idea-stage"
        archived: list[dict[str, str]] = []
        idea_stage = project / "idea-stage"
        if idea_stage.is_dir():
            for source in sorted(path for path in idea_stage.rglob("*") if path.is_file()):
                relative = source.relative_to(idea_stage)
                target = archive / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                archived.append(
                    {
                        "path": str(source.relative_to(project)),
                        "archive_path": str(target.relative_to(project)),
                        "sha256": sha256_file(target),
                    }
                )

        # These are Controller-produced in a formal run. Keep their historical
        # copies in the archive, then start fresh rather than forging provenance.
        for name in (
            "SEARCH_LEDGER.jsonl",
            "LITERATURE_CORPUS.jsonl",
            "EVIDENCE_REGISTRY.jsonl",
            "ACTIVE_FIELD_MAP.md",
        ):
            active = idea_stage / name
            if active.is_file():
                active.unlink()

        controller = cls.start(project, run_id, executor=executor)
        migration_record = {
            "schema_version": 2,
            "formal_run_id": run_id,
            "status": "WAITING_FOR_HUMAN",
            "historical_artifacts_are_provenance_only": True,
            "historical_system_events_reconstructed": False,
            "archive_root": str(archive.parent.relative_to(project)),
            "archived_artifacts": archived,
            "created_at": now(),
        }
        record_path = project / ".aris" / "migrations" / f"{run_id}.json"
        record_path.parent.mkdir(parents=True, exist_ok=True)
        record_path.write_text(
            json.dumps(migration_record, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        with controller._store.mutate() as state:
            state["research_lit"]["legacy_migration_record"] = str(
                record_path.relative_to(project)
            )

        previous = json.loads(legacy_manifest.read_text(encoding="utf-8"))
        previous.update(
            {
                "schema_version": 2,
                "migration_status": "formal_rerun_bootstrapped",
                "historical_artifacts_formal_controller_compliance": False,
                "formal_run_id": run_id,
                "formal_run_status": "WAITING_FOR_HUMAN",
                "formal_run_controller_compliance": True,
                "migration_record": str(record_path.relative_to(project)),
                "next_action": (
                    "User reviews SOURCE_ADMISSION_POLICY.yaml and confirms the "
                    "source_policy_approval Gate in the Codex interface."
                ),
            }
        )
        legacy_manifest.write_text(
            json.dumps(previous, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return controller

    @staticmethod
    def _workflow_migration_report(
        state: dict[str, Any], current_workflow: dict[str, Any]
    ) -> dict[str, Any]:
        """Decide whether a stored workflow can adopt the canonical workflow.

        A migration is compatible only when the literature protocol and every
        phase already executed by the run (including its dependencies) retain
        the same specification.  Future scientific-core work may evolve.
        """

        stored = state.get("workflow")
        if not isinstance(stored, dict):
            raise ControllerError("formal run has no stored workflow to migrate")

        required_equal = (
            "schema_version",
            "research_effort_budget",
            "research_lit",
            "terminal_statuses",
        )
        incompatible = [
            key for key in required_equal if stored.get(key) != current_workflow.get(key)
        ]
        old_specs = {
            item.get("phase"): item
            for item in stored.get("phases", [])
            if isinstance(item, dict) and isinstance(item.get("phase"), str)
        }
        new_specs = {
            item.get("phase"): item
            for item in current_workflow.get("phases", [])
            if isinstance(item, dict) and isinstance(item.get("phase"), str)
        }
        phase_records = state.get("phases", [])
        executed: list[str] = []
        replaced_suffix: list[str] = []
        pending_suffix_started = False
        for item in phase_records:
            if not isinstance(item, dict) or not isinstance(item.get("phase"), str):
                incompatible.append("phases")
                continue
            if item.get("status") in {None, "pending"}:
                pending_suffix_started = True
                replaced_suffix.append(item["phase"])
            elif pending_suffix_started:
                incompatible.append(f"phases.{item['phase']}.non_contiguous_executed_prefix")
            else:
                executed.append(item["phase"])
        canonical_order = [
            item.get("phase")
            for item in current_workflow.get("phases", [])
            if isinstance(item, dict)
        ]
        if canonical_order[:len(executed)] != executed:
            incompatible.append("phases.executed_prefix_order")
        checked = set(executed)
        pending = list(executed)
        while pending:
            phase = pending.pop()
            spec = old_specs.get(phase)
            if spec is None:
                incompatible.append(f"phases.{phase}")
                continue
            for dependency in spec.get("depends_on", []):
                if dependency not in checked:
                    checked.add(dependency)
                    pending.append(dependency)
        for phase in sorted(checked):
            if old_specs.get(phase) != new_specs.get(phase):
                incompatible.append(f"phases.{phase}")

        def artifact_refs(value: Any) -> set[str]:
            if isinstance(value, str) and value.startswith("@artifact:"):
                return {value[len("@artifact:"):]}
            if isinstance(value, dict):
                return (
                    set().union(*(artifact_refs(item) for item in value.values()))
                    if value else set()
                )
            if isinstance(value, list):
                return (
                    set().union(*(artifact_refs(item) for item in value))
                    if value else set()
                )
            return set()

        old_manifest = stored.get("artifact_manifest") or {}
        new_manifest = current_workflow.get("artifact_manifest") or {}
        for phase in checked:
            for key in artifact_refs(old_specs.get(phase)) | artifact_refs(new_specs.get(phase)):
                if old_manifest.get(key) != new_manifest.get(key):
                    incompatible.append(f"artifact_manifest.{key}")

        return {
            "compatible": not incompatible,
            "executed_phases": executed,
            "checked_phase_semantics": sorted(checked),
            "incompatible_paths": sorted(set(incompatible)),
            "replaced_suffix": replaced_suffix,
        }

    def _paper_reading_structural_migration(
        self, state: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Map a pre-review-led reading checkpoint onto current control bindings.

        The old run already has an accepted Field Map and completed read events,
        but predates the current Initial-Map / formal-Primary lifecycle. This
        restores only the normal active reading subset and landscape Evidence
        list needed to continue; it never invents Initial-Map provenance.
        """

        research = state.get("research_lit")
        if not isinstance(research, dict):
            return None
        if research.get("current_stage") != "PAPER_READING":
            return None
        if any(
            research.get(field) is not None
            for field in (
                "initial_field_map_binding",
                "initial_screened_corpus_ids",
                "formal_primary_selection",
                "active_reading_session",
            )
        ):
            return None

        try:
            self._assert_artifact_current(research, "active_field_map")
        except ControllerError:
            return None

        accepted = research.get("accepted_artifacts") or {}
        landscape_evidence_ids: list[str] = []
        for key in accepted:
            if not isinstance(key, str) or not key.startswith("evidence:"):
                continue
            paper_id = key.split(":", 1)[1]
            if not paper_id:
                return None
            try:
                self._assert_artifact_current(research, key)
            except ControllerError:
                return None
            landscape_evidence_ids.append(paper_id)

        papers = research.get("papers") or {}
        read_events = research.get("read_events") or {}
        accepted_evidence = set(landscape_evidence_ids)
        replayable: list[tuple[str, str]] = []
        for read_event_id, event in read_events.items():
            if not isinstance(read_event_id, str) or not isinstance(event, dict):
                continue
            paper_id = event.get("paper_id")
            if (
                not isinstance(paper_id, str)
                or paper_id in accepted_evidence
                or event.get("status") != "complete"
            ):
                continue
            paper = papers.get(paper_id)
            registration = paper.get("user_fulltext") if isinstance(paper, dict) else None
            if not isinstance(registration, dict):
                continue
            source_path = registration.get("source_path")
            source_sha256 = registration.get("source_sha256")
            if (
                not isinstance(source_path, str)
                or not isinstance(source_sha256, str)
                or source_sha256 != event.get("content_sha256")
            ):
                continue
            source = (self.root / source_path).resolve()
            source_root = (self.root / "source-materials").resolve()
            try:
                source.relative_to(source_root)
            except ValueError:
                continue
            if not source.is_file() or sha256_file(source) != source_sha256:
                continue
            replayable.append((read_event_id, paper_id))
        if not replayable:
            return None

        paper_ids = [paper_id for _event_id, paper_id in replayable]
        replay_session = {"paper_ids": paper_ids}
        readable_context = {**research, "active_reading_session": replay_session}
        if any(
            not self._paper_readable_in_active_session(readable_context, paper_id)
            for paper_id in paper_ids
        ):
            return None
        return {
            "active_reading_session": {
                **replay_session,
                "rationale": "Continue verified completed read events without canonical Evidence.",
                "created_at": now(),
            },
            "landscape_evidence_ids": sorted(set(landscape_evidence_ids)),
        }

    def migrate_workflow_if_compatible(self) -> dict[str, Any]:
        """Controller-owned in-place migration for compatible or structural changes."""

        with run_state._lock(str(self.root), self.run_id):
            state = run_state._load(str(self.root), self.run_id)
            if not state.get("controller_managed") or state.get("controller_version") != 2:
                raise ControllerError("only current Controller-managed runs can migrate workflows")
            if (
                state.get("workflow_sha256") == self.workflow_sha256
                and state.get("workflow") == self.workflow
            ):
                raise ControllerError("formal run already uses the canonical workflow")
            report = self._workflow_migration_report(state, self.workflow)
            if not report["compatible"]:
                structural = self._paper_reading_structural_migration(state)
                if structural is None:
                    raise ControllerError(
                        "workflow migration would change executed-stage semantics: "
                        + ", ".join(report["incompatible_paths"])
                    )
                state["research_lit"].update(structural)
                migration_type = "STRUCTURAL_PAPER_READING_CONTINUATION"
            else:
                migration_type = "COMPATIBLE_WORKFLOW_MIGRATION"

            record = {
                "schema_version": 1,
                "migration_id": uuid.uuid4().hex,
                "migration_type": migration_type,
                "migrated_at": now(),
                "from_workflow_id": (state.get("workflow") or {}).get("workflow_id"),
                "to_workflow_id": self.workflow.get("workflow_id"),
                "from_workflow_sha256": state.get("workflow_sha256"),
                "to_workflow_sha256": self.workflow_sha256,
                "executed_phases": report["executed_phases"],
                "checked_phase_semantics": report["checked_phase_semantics"],
                "replaced_suffix": report["replaced_suffix"],
                "recorded_by": "ARISController",
            }
            preserved_prefix = state["phases"][:len(report["executed_phases"])]
            canonical_suffix = self.workflow["phases"][len(preserved_prefix):]
            state["phases"] = [
                *preserved_prefix,
                *[
                    {
                        "phase": spec["phase"],
                        "status": "pending",
                        "artifact": None,
                        "verdict_id": None,
                        "reviewer": None,
                        "reviewer_family": None,
                        "review_independence": None,
                        "acceptance_status": None,
                        "executor_model": state.get("executor_model"),
                        "executor_family": state.get("executor_family"),
                        "human_decision": None,
                        "updated": now(),
                    }
                    for spec in canonical_suffix
                ],
            ]
            state.setdefault("workflow_migrations", []).append(record)
            state["workflow"] = deepcopy(self.workflow)
            state["workflow_sha256"] = self.workflow_sha256
            core = state["scientific_core"]
            core.setdefault("selected_for_testing", None)
            if core.get("status") == "ACTIVE":
                core_phase_names = set(self.workflow["scientific_core"]["phases"])
                phase_specs = {
                    item["phase"]: item
                    for item in self.workflow["phases"]
                    if isinstance(item, dict) and isinstance(item.get("phase"), str)
                }
                terminal_statuses = set(self.workflow["terminal_statuses"])
                current = next(
                    (
                        item["phase"] for item in state["phases"]
                        if item["phase"] in core_phase_names
                        and item.get("status") not in terminal_statuses
                        and not (
                            item.get("status") == "done"
                            and not phase_specs[item["phase"]].get("formal_gate")
                        )
                    ),
                    None,
                )
                core["current_phase"] = current
            elif core.get("status") == "NOT_STARTED":
                core["current_phase"] = None
            run_state._save(str(self.root), self.run_id, state)
            return {
                "migration": record,
                "current_stage": (state.get("research_lit") or {}).get("current_stage"),
            }

    def status(self) -> dict[str, Any]:
        return self._store.load()

    def _build_validation_handoff(self, state: dict[str, Any]) -> dict[str, Any]:
        """Build the stable, current artifact binding for a user validation."""

        core = state.get("scientific_core") or {}
        if core.get("status") != "METHOD_CONFIRMED_AWAITING_USER_VALIDATION":
            raise ControllerError(
                "formal validation handoff requires METHOD_CONFIRMED_AWAITING_USER_VALIDATION"
            )
        entry = core.get("validation_entry")
        if (
            not isinstance(entry, dict)
            or entry.get("status") not in {
                "AWAITING_USER_INITIATION",
                "HANDOFF_ISSUED",
                "JUDGMENT_REQUESTED",
            }
            or entry.get("entry_policy") != "human_initiated_only"
        ):
            raise ControllerError("formal validation entry is missing or is not user-initiated")

        accepted = core.get("accepted_artifacts") or {}
        entry_artifacts = entry.get("accepted_method_artifacts") or {}
        active_problem = self._assert_active_problem_version_current(state)
        handoff: dict[str, dict[str, str]] = {}
        for raw_path, (producer_phase, required_status) in FORMAL_VALIDATION_HANDOFF_ARTIFACTS.items():
            record = accepted.get(raw_path)
            if not isinstance(record, dict):
                raise ControllerError(
                    f"formal validation handoff missing Controller-accepted artifact: {raw_path}"
                )
            if record.get("producer_phase") != producer_phase:
                raise ControllerError(
                    f"formal validation handoff has wrong producer for {raw_path}: "
                    f"expected {producer_phase}"
                )
            provenance = record.get("provenance") or {}
            if provenance.get("controller") != "ARISController" or provenance.get("run_id") != self.run_id:
                raise ControllerError(
                    f"formal validation handoff has unverifiable run provenance: {raw_path}"
                )
            phase = run_state._find_phase(state, producer_phase)
            if phase.get("status") != required_status:
                raise ControllerError(
                    f"formal validation handoff source phase is not accepted: {producer_phase}"
                )
            path = Path(str(record.get("path") or ""))
            if not path.is_absolute():
                path = self.root / path
            digest = record.get("sha256")
            if not path.is_file() or not isinstance(digest, str) or sha256_file(path) != digest:
                raise ControllerError(
                    f"formal validation handoff artifact is missing or changed: {raw_path}"
                )
            entry_record = entry_artifacts.get(raw_path)
            if producer_phase in {
                "method_refinement",
                "final_method_novelty_gate",
                "final_method_human_acceptance",
            } and (
                not isinstance(entry_record, dict)
                or entry_record.get("sha256") != digest
            ):
                raise ControllerError(
                    f"formal validation entry does not bind current method artifact: {raw_path}"
                )
            handoff[raw_path] = {"sha256": digest, "producer_phase": producer_phase}

        final_proposal = accepted.get("refine-logs/FINAL_PROPOSAL.md")
        expected_binding = {
            "problem_id": active_problem["problem_id"],
            "version": active_problem["version"],
            "contract_sha256": active_problem["contract_sha256"],
            "evidence_capsule_sha256": active_problem["evidence_capsule_sha256"],
        }
        if (
            not isinstance(final_proposal, dict)
            or final_proposal.get("problem_version_binding") != expected_binding
        ):
            raise ControllerError(
                "formal validation handoff final method is not bound to the active accepted problem version"
            )

        selected_path = self.root / str(
            self.workflow["artifact_manifest"]["selected_principle"]
        )
        proposal_path = self.root / str(
            self.workflow["artifact_manifest"]["final_proposal"]
        )
        try:
            selected = yaml.safe_load(selected_path.read_text(encoding="utf-8"))
            proposal_text = proposal_path.read_text(encoding="utf-8")
        except (OSError, yaml.YAMLError) as exc:
            raise ControllerError("formal validation obligations cannot be recovered") from exc
        if not isinstance(selected, dict):
            raise ControllerError("formal validation Selected Principle is invalid")
        required_sections = list(
            self.workflow["artifact_contracts"]["final_proposal"]["required_sections"]
        )
        section_matches = list(
            re.finditer(r"(?m)^#{1,6}\s+(.+?)\s*$", proposal_text)
        )
        canonical_sections = {title.casefold(): title for title in required_sections}
        sections: dict[str, str] = {}
        for index, match in enumerate(section_matches):
            title = match.group(1).strip()
            end = (
                section_matches[index + 1].start()
                if index + 1 < len(section_matches)
                else len(proposal_text)
            )
            body = proposal_text[match.end():end].strip()
            canonical_title = canonical_sections.get(title.casefold())
            if canonical_title is not None:
                if not body:
                    raise ControllerError(
                        f"formal validation proposal section is empty: {title}"
                    )
                sections[canonical_title] = body
        if set(sections) != set(required_sections):
            raise ControllerError("formal validation proposal sections are incomplete")
        validation_obligations = {
            "selected_principle": {
                key: deepcopy(selected.get(key))
                for key in (
                    "principle_id", "principle_version", "principle", "intervention",
                    "changed_structure", "activation_conditions", "failure_conditions",
                    "applicability_boundaries",
                )
            },
            "causal_chain_ids": list(selected.get("causal_chain_ids") or []),
            "mechanism_change_ids": list(selected.get("mechanism_change_ids") or []),
            "capability_ids": list(selected.get("capability_ids") or []),
            "obligation_ids": list(selected.get("obligation_ids") or []),
            "final_proposal_sections": sections,
        }

        handoff = {
            "handoff_type": "FORMAL_CANONICAL_VALIDATION",
            "run_id": self.run_id,
            "workflow_sha256": self.workflow_sha256,
            "problem_version": expected_binding,
            "artifacts": handoff,
            "validation_obligations": validation_obligations,
        }
        canonical = json.dumps(handoff, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        handoff["handoff_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return handoff

    def validation_handoff(self) -> dict[str, Any]:
        """Issue the current Controller-bound handoff for explicit user validation.

        Issuing this small, live record is the only Controller-recognized start
        of validation. It neither starts an experiment nor adds a workflow
        phase, but prevents a result fabricated without a formal handoff from
        changing the canonical research state.
        """

        # Returning an existing live request is still formal authorization for
        # a native reviewer, so this cannot be bypassed by reusing a request.
        self._require_formal_native_runtime(VALIDATION_REVIEWER_ROLE)
        with self._store.mutate() as state:
            handoff = self._build_validation_handoff(state)
            entry = state["scientific_core"]["validation_entry"]
            artifact_bindings = {
                path: str(record["sha256"])
                for path, record in handoff["artifacts"].items()
            }
            request = entry.get("validation_review_request")
            if not isinstance(request, dict) or (
                request.get("handoff_sha256") != handoff["handoff_sha256"]
                or request.get("artifact_bindings") != artifact_bindings
            ):
                request = {
                    "id": f"validation-judgment-{uuid.uuid4().hex}",
                    "request_type": VALIDATION_REVIEW_REQUEST_TYPE,
                    "run_id": self.run_id,
                    "handoff_sha256": handoff["handoff_sha256"],
                    "required_reviewer_role": VALIDATION_REVIEWER_ROLE,
                    "artifact_bindings": artifact_bindings,
                    "allowed_verdicts": sorted(VALIDATION_RESULT_DECISIONS),
                }
                entry["validation_review_request"] = request
            entry["status"] = "JUDGMENT_REQUESTED"
            entry["issued_handoff"] = dict(handoff)
            entry["issued_at"] = now()
            return {**handoff, "validation_review_request": dict(request)}

    def _attested_validation_verdict(
        self,
        state: dict[str, Any],
        handoff: dict[str, Any],
        submitted: dict[str, Any] | None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Require the existing result-to-claim judgment to own the verdict text.

        The request binds the accepted method handoff; the reviewer-owned payload
        separately binds every result artifact by hash.  Main may transport an
        exact copy for CLI compatibility, but cannot amend its scientific claim.
        """

        entry = state["scientific_core"].get("validation_entry") or {}
        request = entry.get("validation_review_request")
        if (
            entry.get("status") != "JUDGMENT_REQUESTED"
            or not isinstance(request, dict)
            or request.get("request_type") != VALIDATION_REVIEW_REQUEST_TYPE
            or request.get("required_reviewer_role") != VALIDATION_REVIEWER_ROLE
            or request.get("handoff_sha256") != handoff["handoff_sha256"]
            or not isinstance(request.get("id"), str)
            or not isinstance(request.get("artifact_bindings"), dict)
        ):
            raise ControllerError(
                "validation result requires a current Controller-issued validation judgment request"
            )
        try:
            attestation = reviews.load_review_attestation(
                self.root,
                self.run_id,
                role=VALIDATION_REVIEWER_ROLE,
                request_id=request["id"],
                artifact_bindings=dict(request["artifact_bindings"]),
            )
        except ValueError as exc:
            raise ControllerError(str(exc)) from exc
        payload = attestation.get("verdict_payload")
        if not isinstance(payload, dict):
            raise ControllerError("validation reviewer attestation lacks the canonical verdict payload")
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        if hashlib.sha256(canonical.encode("utf-8")).hexdigest() != attestation.get("payload_sha256"):
            raise ControllerError("validation reviewer verdict payload fails its attested hash")
        if (
            payload.get("run_id") != self.run_id
            or payload.get("review_request_id") != request["id"]
            or payload.get("reviewed_artifact_hashes") != request["artifact_bindings"]
            or payload.get("reviewer") != attestation.get("reviewer")
            or payload.get("verdict_id") != attestation.get("verdict_id")
            or payload.get("decision") != attestation.get("decision")
            or payload.get("handoff_sha256") != handoff["handoff_sha256"]
        ):
            raise ControllerError("validation reviewer verdict does not match its live attestation")
        if submitted is not None and submitted != payload:
            raise ControllerError(
                "Main may only submit the exact externally attested validation verdict payload"
            )
        consumed = self._consume_review_attestation(
            role=VALIDATION_REVIEWER_ROLE,
            request_id=request["id"],
            reviewer=str(payload["reviewer"]),
            verdict_id=str(payload["verdict_id"]),
            decision=str(payload["decision"]),
            artifact_bindings=dict(request["artifact_bindings"]),
        )
        return payload, consumed

    def _normalize_validation_result(
        self, result: dict[str, Any], handoff: dict[str, Any]
    ) -> dict[str, Any]:
        if not isinstance(result, dict):
            raise ControllerError("validation result must be a JSON object")
        required = (
            "schema_version",
            "validation_result_id",
            "run_id",
            "workflow_sha256",
            "handoff_sha256",
            "decision",
            "rationale",
            "evidence_artifacts",
            "evidence_refs",
            "findings",
            "return_guidance",
        )
        missing = [name for name in required if name not in result]
        if missing:
            raise ControllerError("validation result is missing required fields: " + ", ".join(missing))
        if result.get("schema_version") != 1:
            raise ControllerError("validation result schema_version must be 1")
        validation_result_id = result.get("validation_result_id")
        if not isinstance(validation_result_id, str) or not validation_result_id.strip():
            raise ControllerError("validation result validation_result_id must be a non-empty string")
        if result.get("run_id") != self.run_id:
            raise ControllerError("validation result run_id does not match this Controller run")
        if result.get("workflow_sha256") != self.workflow_sha256:
            raise ControllerError("validation result workflow_sha256 does not match this run")
        if result.get("handoff_sha256") != handoff["handoff_sha256"]:
            raise ControllerError("validation result does not bind the current validation handoff")
        decision = result.get("decision")
        if decision not in VALIDATION_RESULT_DECISIONS:
            raise ControllerError("validation result has an unsupported decision")
        rationale = result.get("rationale")
        if not isinstance(rationale, str) or not rationale.strip():
            raise ControllerError("validation result rationale must be a non-empty string")
        evidence = result.get("evidence_artifacts")
        if not isinstance(evidence, list) or not evidence:
            raise ControllerError("validation result evidence_artifacts must be a non-empty list")
        normalized_evidence: list[dict[str, str]] = []
        seen_paths: set[str] = set()
        for item in evidence:
            if not isinstance(item, dict):
                raise ControllerError("validation result evidence artifact must be an object")
            raw_path = item.get("path")
            digest = item.get("sha256")
            if not isinstance(raw_path, str) or not raw_path or Path(raw_path).is_absolute():
                raise ControllerError("validation result evidence path must be project-relative")
            if not isinstance(digest, str) or len(digest) != 64:
                raise ControllerError("validation result evidence artifact must include a SHA-256")
            path = (self.root / raw_path).resolve()
            try:
                path.relative_to(self.root.resolve())
            except ValueError as exc:
                raise ControllerError("validation result evidence path must stay inside the project") from exc
            stored_path = path.relative_to(self.root).as_posix()
            if stored_path in seen_paths or not path.is_file() or sha256_file(path) != digest:
                raise ControllerError("validation result evidence artifact is missing, changed, or duplicated")
            seen_paths.add(stored_path)
            normalized_evidence.append({"path": stored_path, "sha256": digest})
        normalized: dict[str, Any] = {
            "schema_version": 1,
            "validation_result_id": validation_result_id.strip(),
            "run_id": self.run_id,
            "workflow_sha256": self.workflow_sha256,
            "handoff_sha256": handoff["handoff_sha256"],
            "decision": decision,
            "rationale": rationale.strip(),
            "evidence_artifacts": normalized_evidence,
        }
        evidence_refs = result.get("evidence_refs")
        if (
            not isinstance(evidence_refs, list)
            or not evidence_refs
            or any(not isinstance(value, str) or not value.strip() for value in evidence_refs)
            or len(evidence_refs) != len(set(evidence_refs))
        ):
            raise ControllerError("validation result evidence_refs must be a non-empty unique string list")
        findings = result.get("findings")
        if not isinstance(findings, list) or not findings:
            raise ControllerError("validation result findings must be a non-empty list")
        return_guidance = result.get("return_guidance")
        if decision != "VALIDATED" and not isinstance(return_guidance, dict):
            raise ControllerError("validation return decisions require structured return_guidance")
        if decision == "VALIDATED" and return_guidance not in (None, {}):
            raise ControllerError("VALIDATED return_guidance must be empty")
        normalized["evidence_refs"] = [value.strip() for value in evidence_refs]
        normalized["findings"] = deepcopy(findings)
        normalized["return_guidance"] = deepcopy(return_guidance)
        if decision == "VALIDATED":
            closure = result.get("mechanism_evidence_closure")
            if not isinstance(closure, list) or not closure:
                raise ControllerError(
                    "VALIDATED requires non-empty mechanism_evidence_closure; performance alone is insufficient"
                )
            selected_path = self.root / str(
                self.workflow["artifact_manifest"]["selected_principle"]
            )
            try:
                selected = yaml.safe_load(selected_path.read_text(encoding="utf-8"))
            except (OSError, yaml.YAMLError) as exc:
                raise ControllerError("VALIDATED cannot resolve the Controller-accepted Selected Principle") from exc
            if not isinstance(selected, dict):
                raise ControllerError("VALIDATED Selected Principle is invalid")
            required_chains = set(selected.get("causal_chain_ids") or [])
            required_mechanisms = set(selected.get("mechanism_change_ids") or [])
            required_obligations = set(selected.get("obligation_ids") or [])
            closure_chains: set[str] = set()
            closure_mechanisms: set[str] = set()
            closure_obligations: set[str] = set()
            normalized_closure: list[dict[str, Any]] = []
            evidence_paths = {item["path"] for item in normalized_evidence}
            allowed_methods = {
                "controlled_intervention", "ablation", "counterfactual",
                "mechanism_measurement", "joint_mechanism_experiment", "theory",
            }
            for index, item in enumerate(closure, 1):
                if not isinstance(item, dict):
                    raise ControllerError("mechanism_evidence_closure entries must be objects")
                required_fields = (
                    "causal_chain_id", "mechanism_change_ids", "obligation_ids",
                    "predicted_mechanism_change",
                    "observed_mechanism_change", "explanation_status", "mechanism_match",
                    "discriminating_evidence", "performance_consequence",
                )
                if any(field not in item for field in required_fields):
                    raise ControllerError("mechanism_evidence_closure entry is missing a required causal link")
                chain_id = item["causal_chain_id"]
                if not isinstance(chain_id, str) or chain_id not in required_chains:
                    raise ControllerError("mechanism_evidence_closure references an unknown causal chain")
                mechanism_ids = item["mechanism_change_ids"]
                obligation_ids = item["obligation_ids"]
                if not isinstance(mechanism_ids, list) or any(
                    not isinstance(value, str) or value not in required_mechanisms
                    for value in mechanism_ids
                ):
                    raise ControllerError("mechanism_evidence_closure mechanism-change IDs are invalid")
                if not isinstance(obligation_ids, list) or any(
                    not isinstance(value, str) or value not in required_obligations
                    for value in obligation_ids
                ):
                    raise ControllerError("mechanism_evidence_closure obligation IDs are invalid")
                if len(mechanism_ids) != len(set(mechanism_ids)) or len(obligation_ids) != len(set(obligation_ids)):
                    raise ControllerError("mechanism_evidence_closure IDs must be unique")
                for field in ("predicted_mechanism_change", "observed_mechanism_change", "performance_consequence"):
                    if not isinstance(item[field], str) or not item[field].strip():
                        raise ControllerError(f"mechanism_evidence_closure.{field} must be non-empty")
                if item["explanation_status"] != "EXPLANATION_SUPPORTED":
                    raise ControllerError(
                        "VALIDATED requires EXPLANATION_SUPPORTED for every causal closure"
                    )
                if item["mechanism_match"] != "MATCHES_PREDICTION":
                    raise ControllerError(
                        "VALIDATED requires observed mechanism change to match its prediction"
                    )
                discriminating = item["discriminating_evidence"]
                if not isinstance(discriminating, dict):
                    raise ControllerError("mechanism_evidence_closure discriminating_evidence must be an object")
                method = discriminating.get("method")
                paths = discriminating.get("artifact_paths")
                if method not in allowed_methods or not isinstance(paths, list) or not paths:
                    raise ControllerError("discriminating evidence must name an allowed identifiable-mechanism method and artifact")
                if any(not isinstance(path, str) or path not in evidence_paths for path in paths):
                    raise ControllerError("discriminating evidence artifacts must be declared validation evidence")
                closure_chains.add(chain_id)
                closure_mechanisms.update(mechanism_ids)
                closure_obligations.update(obligation_ids)
                normalized_closure.append({
                    "causal_chain_id": chain_id,
                    "mechanism_change_ids": mechanism_ids,
                    "obligation_ids": obligation_ids,
                    "predicted_mechanism_change": item["predicted_mechanism_change"].strip(),
                    "observed_mechanism_change": item["observed_mechanism_change"].strip(),
                    "explanation_status": "EXPLANATION_SUPPORTED",
                    "mechanism_match": "MATCHES_PREDICTION",
                    "discriminating_evidence": {"method": method, "artifact_paths": paths},
                    "performance_consequence": item["performance_consequence"].strip(),
                })
            if (
                closure_chains != required_chains
                or closure_mechanisms != required_mechanisms
                or closure_obligations != required_obligations
            ):
                raise ControllerError(
                    "VALIDATED requires evidence closure for every Selected Principle causal chain, mechanism change, and obligation"
                )
            normalized["mechanism_evidence_closure"] = normalized_closure
            for field in (
                "supported_claim_elements", "applicability_boundaries",
                "established_scientific_delta",
            ):
                value = result.get(field)
                if value in (None, "", [], {}):
                    raise ControllerError(f"VALIDATED requires non-empty {field}")
                normalized[field] = deepcopy(value)
            for field in ("retained_limitations", "remaining_uncertainties"):
                if field not in result or result[field] is None:
                    raise ControllerError(f"VALIDATED requires {field}")
                normalized[field] = deepcopy(result[field])
        return normalized

    def submit_validation_result(self, result: dict[str, Any] | None = None) -> dict[str, Any]:
        """Materialize the externally attested result-to-claim verdict."""

        with self._store.mutate() as state:
            handoff = self._build_validation_handoff(state)
            entry = state["scientific_core"]["validation_entry"]
            if entry.get("issued_handoff") != handoff:
                raise ControllerError(
                    "validation result requires a current Controller-issued validation handoff"
                )
            verdict, attestation = self._attested_validation_verdict(state, handoff, result)
            normalized = self._normalize_validation_result(verdict, handoff)
            normalized["review_request_id"] = verdict["review_request_id"]
            normalized["reviewed_artifact_hashes"] = dict(verdict["reviewed_artifact_hashes"])
            normalized["reviewer"] = verdict["reviewer"]
            normalized["verdict_id"] = verdict["verdict_id"]
            normalized["reviewer_agent_id"] = attestation["agent_id"]
            normalized["verdict_payload_sha256"] = attestation["payload_sha256"]
            result_id = normalized["validation_result_id"]
            if any(item.get("id") == result_id for item in state["scientific_core"].get("validation_results") or []):
                raise ControllerError("validation result ID has already been registered")
            result_path = self._canonical_path(result_id)
            result_path.parent.mkdir(parents=True, exist_ok=True)
            result_path.write_text(
                json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            record = {
                "id": result_id,
                "path": str(result_path.relative_to(self.root)),
                "sha256": sha256_file(result_path),
                "registered_at": now(),
                **normalized,
            }
            core = state["scientific_core"]
            core.setdefault("validation_results", []).append(record)
            if normalized["decision"] == "VALIDATED":
                core["status"] = "VALIDATION_CONFIRMED"
                core["validation_entry"] = {
                    "status": "VALIDATED",
                    "entry_policy": "human_initiated_only",
                    "handoff_sha256": handoff["handoff_sha256"],
                    "validation_result_id": result_id,
                    "validated_at": record["registered_at"],
                }
                core["transition_log"].append(
                    {
                        "timestamp": record["registered_at"],
                        "from": "METHOD_CONFIRMED_AWAITING_USER_VALIDATION",
                        "to": "VALIDATION_CONFIRMED",
                        "reason": "validation_result_validated",
                        "validation_result_id": result_id,
                    }
                )
                return state
            target = VALIDATION_RESULT_RETURN_TARGETS[normalized["decision"]]
            if normalized["decision"] == "SELECTED_PRINCIPLE_REJECTED":
                selected_path = self.root / str(
                    self.workflow["artifact_manifest"]["selected_principle"]
                )
                try:
                    selected = yaml.safe_load(selected_path.read_text(encoding="utf-8"))
                except (OSError, yaml.YAMLError) as exc:
                    raise ControllerError("validation rejection cannot resolve Selected Principle") from exc
                self._append_method_history_event(
                    "method_principles",
                    {
                        "schema_version": 1,
                        "event_id": f"principle-{uuid.uuid4().hex}",
                        "event_type": "VALIDATION_REJECTED",
                        "cycle_id": str(
                            (core.get("method_test_cycle") or {}).get("cycle_id") or "validation"
                        ),
                        "principle_id": str(selected["principle_id"]),
                        "principle_version": str(selected["principle_version"]),
                        "parent_version": None,
                        "scientific_context_refs": [
                            *list(selected.get("mechanism_change_ids") or []),
                            *list(selected.get("obligation_ids") or []),
                            *list(selected.get("causal_chain_ids") or []),
                        ],
                        "evidence_refs": list(normalized["evidence_refs"]),
                        "reason": normalized["rationale"],
                        "recorded_at": record["registered_at"],
                        "record_refs": [{"path": record["path"], "sha256": record["sha256"]}],
                    },
                )
            final_phase = self.workflow["scientific_core"]["phases"][-1]
            self._return_to_phase(
                state,
                from_phase=final_phase,
                target=target,
                decision=normalized["decision"],
                reason="validation_result_return",
                provenance={
                    "validation_result_id": result_id,
                    "validation_result_sha256": record["sha256"],
                    "handoff_sha256": handoff["handoff_sha256"],
                    "return_guidance": deepcopy(normalized["return_guidance"]),
                    "evidence_refs": list(normalized["evidence_refs"]),
                    "findings": deepcopy(normalized["findings"]),
                },
            )
            return state

    def current_stage(self) -> str:
        state = self.status()
        core = state.get("scientific_core") or {}
        if core.get("status") == "ACTIVE" and core.get("current_phase"):
            return str(core["current_phase"]).upper()
        if core.get("status") in {
            "METHOD_CONFIRMED_AWAITING_USER_VALIDATION",
            "VALIDATION_CONFIRMED",
        }:
            return str(core["status"])
        return state["research_lit"]["current_stage"]

    def allowed_actions(self) -> list[str]:
        state = self.status()
        core = state.get("scientific_core") or {}
        if core.get("status") == "METHOD_CONFIRMED_AWAITING_USER_VALIDATION":
            entry = core.get("validation_entry") or {}
            if entry.get("status") == "JUDGMENT_REQUESTED":
                return ["validation_handoff", "submit_validation_result"]
            return ["validation_handoff"]
        if core.get("status") == "VALIDATION_CONFIRMED":
            return []
        if core.get("status") == "ACTIVE":
            research = state["research_lit"]
            # An approved, phase-scoped literature session temporarily reuses
            # the existing research-lit actions.  It must finish before the
            # core phase can start, so it cannot be a side channel around a
            # formal Gate.
            if research["current_stage"] != "LANDSCAPE_ACCEPTED":
                return self._research_lit_allowed_actions(research)
            phase = self._current_core_phase(state)
            spec = self._phase_spec(state, phase["phase"])
            revision_action = (
                ["revise_problem"]
                if core.get("active_problem_version") and phase["status"] != "running"
                else []
            )
            if spec.get("human_checkpoint"):
                return ["human_approve", *revision_action]
            if phase["status"] == "pending":
                if phase["phase"] == "principle_evaluation":
                    cycle = core.get("method_test_cycle") or {}
                    approved = set(cycle.get("approved_test_ids") or [])
                    terminal = set((cycle.get("terminal_outcomes") or {}).keys())
                    if not approved or terminal != approved or not cycle.get("evidence_context"):
                        return ["method_test_handoff", "submit_method_test_result", *revision_action]
                actions = ["start_phase", *revision_action]
                if self._incremental_literature_phase_allowed(state, phase):
                    actions.insert(0, "submit_query_plan")
                if self._evidence_re_adoption_available(state, phase):
                    actions.insert(0, "readopt_evidence")
                return actions
            if phase["status"] == "running":
                reviewed = self._resolved_phase_paths(
                    state, str(phase["phase"]), "reviewed_artifacts"
                )
                request = phase.get("review_request")
                actions = (
                    ["refresh_review_request"]
                    if reviewed
                    and isinstance(request, dict)
                    and request.get("reviewed_artifacts_pending")
                    else ["complete_phase", *( ["refresh_review_request"] if reviewed else [] )]
                )
                if phase["phase"] == "method_design":
                    actions.insert(0, "reopen_root_cause")
                if self._incremental_literature_phase_allowed(state, phase):
                    actions.insert(0, "submit_query_plan")
                if self._evidence_re_adoption_available(state, phase):
                    actions.insert(0, "readopt_evidence")
                return actions
            if phase["status"] == "done" and spec.get("formal_gate"):
                decision = phase.get("gate_verdict")
                if decision in set(spec.get("accepted_verdicts") or []):
                    return ["accept_phase", *revision_action]
                if decision in (spec.get("return_targets") or {}):
                    return ["return_phase", *revision_action]
                return []
            return []
        stage = state["research_lit"]["current_stage"]
        return self._research_lit_allowed_actions(state["research_lit"])

    def _research_lit_allowed_actions(self, research: dict[str, Any]) -> list[str]:
        """Return primary workflow actions plus live, non-advancing corrections."""

        stage = research["current_stage"]
        actions = list(self.workflow["research_lit"]["allowed_actions"][stage])
        if stage == "METADATA_RETRIEVAL" and self._reconcilable_query_plan_events(
            research
        ):
            actions.insert(0, "reconcile_query_plan_events")
        if stage == "COVERAGE_REVIEW" and isinstance(
            research.get("coverage_review_request"), dict
        ):
            actions.insert(0, "repair_literature_corpus_hash_chain")
        if stage == "PAPER_READING" or (
            stage == "HUMAN_SEARCH_REQUIRED"
            and isinstance(research.get("human_fulltext_request"), dict)
        ):
            insertion = len(actions) - 1 if stage == "PAPER_READING" else len(actions)
            actions.insert(insertion, "promote_user_source")
            insertion += 1
            actions.insert(insertion, "reverify_admission")
            actions.insert(insertion + 1, "withdraw_admission")
        return actions

    def allowed_agents(self) -> list[str]:
        state = self.status()
        core = state.get("scientific_core") or {}
        if core.get("status") == "ACTIVE":
            research = state["research_lit"]
            if research["current_stage"] != "LANDSCAPE_ACCEPTED":
                return list(self.workflow["research_lit"]["allowed_agents"][research["current_stage"]])
            phase = str(core["current_phase"])
            return list(self.workflow["scientific_core"]["allowed_agents"][phase])
        if core.get("status") in {
            "METHOD_CONFIRMED_AWAITING_USER_VALIDATION",
            "VALIDATION_CONFIRMED",
        }:
            entry = core.get("validation_entry") or {}
            if entry.get("status") == "JUDGMENT_REQUESTED":
                return [VALIDATION_REVIEWER_ROLE]
            return []
        stage = state["research_lit"]["current_stage"]
        return list(self.workflow["research_lit"]["allowed_agents"][stage])

    def preflight_native_subagent_dispatch(
        self,
        role: str,
        *,
        runtime_project_root: str | Path | None = None,
    ) -> dict[str, str]:
        """Verify Hook discovery before the current Codex turn creates a child.

        This is intentionally a non-transitioning Controller check: it binds a
        live, Controller-authorized reader/reviewer role to the runtime cwd
        which Codex children inherit, while leaving scientific work and the
        existing Stop/SubagentStop receipt path untouched.
        """
        if role not in self.allowed_agents():
            raise ControllerError(
                f"{role} is not Controller-authorized for the current formal stage"
            )
        result = self._require_formal_native_runtime(role, runtime_project_root=runtime_project_root)
        return {"run_id": self.run_id, **result}

    def _require_formal_native_runtime(
        self,
        role: str,
        *,
        runtime_project_root: str | Path | None = None,
    ) -> dict[str, str]:
        """Apply the one project-root verifier at a formal Hook-bound authorization."""
        try:
            result = verify_formal_native_subagent_runtime(
                self.root,
                role,
                runtime_project_root=runtime_project_root,
            )
        except ProjectRuntimeError as exc:
            raise ControllerError(str(exc)) from exc
        return result

    def _paths(self) -> dict[str, Path]:
        return {
            key: self.root / value
            for key, value in self.workflow["artifact_manifest"].items()
        }

    def _stage_path(self, artifact_name: str) -> Path:
        safe = "".join(c for c in artifact_name if c.isalnum() or c in "-_.")
        if not safe or safe != artifact_name:
            raise ControllerError("invalid staging artifact name")
        return self.root / ".aris" / "staging" / self.run_id / f"{safe}.json"

    def _canonical_path(self, artifact_name: str) -> Path:
        safe = "".join(c for c in artifact_name if c.isalnum() or c in "-_.")
        if not safe or safe != artifact_name:
            raise ControllerError("invalid canonical artifact name")
        return self.root / ".aris" / "canonical" / self.run_id / f"{safe}.json"

    @staticmethod
    def _evidence_artifact_name(paper_id: str) -> str:
        """Map an admitted external paper identifier to a safe artifact name."""

        candidate = f"evidence-{paper_id}"
        safe = "".join(c for c in candidate if c.isalnum() or c in "-_.")
        if safe == candidate:
            return candidate
        digest = hashlib.sha256(paper_id.encode("utf-8")).hexdigest()
        return f"evidence-external-{digest}"

    def _require_stage(self, state: dict, expected: str) -> dict:
        research = state["research_lit"]
        if research["current_stage"] != expected:
            raise ControllerError(
                f"action requires stage {expected}, current={research['current_stage']}"
            )
        return research

    def _incremental_literature_phase_allowed(
        self, state: dict[str, Any], phase: dict[str, Any]
    ) -> bool:
        """Whether a declared core phase may open the existing lit gateway."""

        allowed = (
            (self.workflow.get("scientific_core") or {})
            .get("incremental_literature", {})
            .get("permitted_phases", [])
        )
        phase_name = phase.get("phase")
        status = phase.get("status")
        return (
            phase_name in allowed
            and state["research_lit"].get("current_stage") == "LANDSCAPE_ACCEPTED"
            and (
                (
                    status == "pending"
                    and phase_name not in {
                        "problem_generation", "method_design", "method_refinement"
                    }
                )
                or (
                    phase_name in {
                        "problem_generation", "root_cause_analysis",
                        "method_design", "method_refinement",
                    }
                    and status == "running"
                )
            )
        )

    def _evidence_re_adoption_available(self, state: dict[str, Any], phase: dict[str, Any]) -> bool:
        """Expose the narrow re-adoption action only when history makes it useful."""

        research = state["research_lit"]
        if research.get("current_stage") != "LANDSCAPE_ACCEPTED" or self._incremental_literature_active(research):
            return False
        phase_name = str(phase.get("phase") or "")
        if phase_name == "problem_generation":
            records = (research.get("incremental_evidence_by_phase") or {}).get(phase_name)
            return bool(
                self._phase_lifecycle_return_id(state, phase_name)
                and isinstance(records, dict)
                and bool(records)
            )
        if phase_name in {"method_design", "method_refinement", "final_method_novelty_gate"}:
            if phase.get("status") not in {"pending", "running"}:
                return False
            try:
                anchor = self._phase_evidence_anchor(state, phase_name)
            except ControllerError:
                return False
            if not isinstance(anchor.get("design_obligation_binding"), dict):
                return False
            for evidence_key in self._historical_phase_evidence_keys(research):
                source_id = evidence_key.split(":", 1)[1]
                try:
                    self._registered_evidence_card(research, source_id)
                except ControllerError:
                    continue
                if self._method_re_adoption_mechanical_status(
                    research, phase_name, evidence_key, anchor
                ) == "eligible":
                    return True
            return False
        if phase_name != "root_cause_analysis" or not self._phase_lifecycle_return_id(state, phase_name):
            return False
        method_phases = {"method_design", "method_refinement", "final_method_novelty_gate"}
        return any(
            candidate_phase in method_phases and isinstance(records, dict) and bool(records)
            for candidate_phase, records in (research.get("incremental_evidence_by_phase") or {}).items()
        )

    def _method_design_query_context(self, state: dict[str, Any]) -> dict[str, Any]:
        """Return immutable anchors for a running method-design gap search."""

        research = state["research_lit"]
        field_map = self._assert_artifact_current(research, "active_field_map")
        analysis_path = self._paths()["root_cause_analysis"]
        if not analysis_path.is_file():
            raise ControllerError("method-design incremental search requires the accepted root-cause analysis")
        try:
            analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ControllerError("method-design incremental search cannot read root-cause analysis") from exc
        analysis_id = analysis.get("analysis_id") if isinstance(analysis, dict) else None
        chains = analysis.get("primary_causal_chain_ids") if isinstance(analysis, dict) else None
        if (
            not isinstance(analysis_id, str)
            or not analysis_id
            or not isinstance(chains, list)
            or not all(isinstance(chain, str) and chain for chain in chains)
        ):
            raise ControllerError("method-design incremental search has no valid primary causal-chain handoff")
        active = self._assert_active_problem_version_current(state)
        return {
            "root_cause_analysis_id": analysis_id,
            "root_cause_analysis_sha256": sha256_file(analysis_path),
            "active_field_map_sha256": str(field_map["sha256"]),
            "primary_causal_chain_ids": set(chains),
            "problem_version": {
                "problem_id": active["problem_id"],
                "version": active["version"],
                "contract_sha256": active["contract_sha256"],
                "evidence_capsule_sha256": active["evidence_capsule_sha256"],
            },
        }

    def _method_refinement_query_context(self, state: dict[str, Any]) -> dict[str, Any]:
        raw_path = str(self.workflow["artifact_manifest"]["selected_principle"])
        record = self._registered_artifact_by_path(state, raw_path)
        path = self.root / raw_path
        if (
            not isinstance(record, dict)
            or not path.is_file()
            or record.get("sha256") != sha256_file(path)
        ):
            raise ControllerError("adaptation-gap search requires the active Selected Principle")
        try:
            selected = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise ControllerError("Selected Principle is invalid") from exc
        if not isinstance(selected, dict):
            raise ControllerError("Selected Principle is invalid")
        return {
            "principle_id": str(selected.get("principle_id") or ""),
            "principle_version": str(selected.get("principle_version") or ""),
            "selected_principle_sha256": str(record["sha256"]),
        }

    def _incremental_literature_active(self, research: dict[str, Any]) -> dict[str, Any] | None:
        session = research.get("incremental_literature_active")
        return session if isinstance(session, dict) else None

    @staticmethod
    def _active_reading_session(research: dict[str, Any]) -> dict[str, Any] | None:
        session = research.get("active_reading_session")
        return session if isinstance(session, dict) else None

    def _paper_is_active_for_reading(
        self, research: dict[str, Any], paper_id: str
    ) -> bool:
        """Whether this live landscape pass, rather than past admission, authorizes a read."""

        if self._incremental_literature_active(research) is not None:
            session = self._incremental_literature_active(research)
            return paper_id in set(session.get("paper_ids") or [])
        session = self._active_reading_session(research)
        return bool(session and paper_id in set(session.get("paper_ids") or []))

    def _paper_readable_in_active_session(
        self, research: dict[str, Any], paper_id: str
    ) -> bool:
        """Require both the pass-local selection and a current readable admission."""

        paper = research.get("papers", {}).get(paper_id)
        if not isinstance(paper, dict) or not self._paper_is_active_for_reading(research, paper_id):
            return False
        if paper.get("screening_status") != "IN_SCOPE" or paper.get("duplicate"):
            return False
        return paper.get("admission_status") in READABLE_ADMISSION_STATUSES

    def _archive_active_field_map(self, research: dict[str, Any]) -> None:
        """Preserve any referenced immutable Field Map bytes before replacement."""

        current = research.get("accepted_artifacts", {}).get("active_field_map")
        if not isinstance(current, dict):
            return
        canonical = self._paths()["active_field_map"]
        digest = str(current.get("sha256") or "")
        if not digest or not canonical.is_file() or sha256_file(canonical) != digest:
            raise ControllerError("accepted artifact changed after validation: active_field_map")
        archive = self.root / ".aris" / "archive" / self.run_id / "field-map" / f"{digest}.md"
        archive.parent.mkdir(parents=True, exist_ok=True)
        if archive.exists():
            if sha256_file(archive) != digest:
                raise ControllerError("Field Map archive hash conflicts with accepted artifact")
        else:
            shutil.copy2(canonical, archive)
        history = research.setdefault("field_map_history", [])
        if not any(item.get("sha256") == digest for item in history if isinstance(item, dict)):
            history.append({
                "sha256": digest,
                "archive_path": str(archive.relative_to(self.root)),
                "accepted_at": current.get("accepted_at"),
            })

    def _archive_accepted_query_plan_if_referenced(
        self, research: dict[str, Any], artifact_name: str
    ) -> None:
        """Keep old accepted bytes only after query provenance has used them."""

        current = research.get("accepted_artifacts", {}).get(artifact_name)
        if not isinstance(current, dict):
            return
        digest = str(current.get("sha256") or "")
        if not digest or not any(
            isinstance(event, dict) and event.get("query_plan_sha256") == digest
            for event in (research.get("query_events") or {}).values()
        ):
            return
        canonical = self.root / str(current.get("path") or "")
        if not canonical.is_file() or sha256_file(canonical) != digest:
            raise ControllerError("accepted query plan changed after validation")
        archive = self.root / ".aris" / "archive" / self.run_id / "query-plan" / f"{digest}.json"
        archive.parent.mkdir(parents=True, exist_ok=True)
        if archive.exists():
            if sha256_file(archive) != digest:
                raise ControllerError("Query Plan archive hash conflicts with accepted artifact")
        else:
            shutil.copy2(canonical, archive)
        history = research.setdefault("query_plan_history", [])
        if not any(item.get("sha256") == digest for item in history if isinstance(item, dict)):
            history.append({
                "sha256": digest,
                "archive_path": str(archive.relative_to(self.root)),
                "accepted_at": current.get("accepted_at"),
            })

    def _problem_lead_query_context(
        self, research: dict[str, Any], planned: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Build the immutable per-query snapshot for a running problem Lead."""

        session = self._incremental_literature_active(research)
        if not isinstance(session, dict) or session.get("phase") != "problem_generation":
            return None
        plan_path = str(session.get("query_plan_path") or "")
        plan_sha256 = str(session.get("query_plan_sha256") or "")
        candidate = self.root / plan_path
        if not plan_path or not plan_sha256 or not candidate.is_file() or sha256_file(candidate) != plan_sha256:
            raise ControllerError("problem-lead query plan changed after Controller acceptance")
        fields = (
            "lead_id",
            "lead_statement",
            "active_field_map_sha256",
            "decision_dimension",
            "purpose",
            "expected_close_condition",
        )
        if any(not isinstance(planned.get(field), str) or not planned[field].strip() for field in fields):
            raise ControllerError("problem-lead query has incomplete accepted context")
        return {
            "phase": "problem_generation",
            "query_plan_sha256": plan_sha256,
            **{field: planned[field] for field in fields},
        }

    def _active_query_plan(self, research: dict[str, Any]) -> dict[str, Any]:
        session = self._incremental_literature_active(research)
        path = (
            session.get("query_plan_path")
            if session is not None
            else self._canonical_path("query_plan").relative_to(self.root).as_posix()
        )
        if not isinstance(path, str) or not path:
            raise ControllerError("active query plan has no canonical path")
        candidate = self.root / path
        if not candidate.is_file():
            raise ControllerError("active query plan is missing")
        return json.loads(candidate.read_text(encoding="utf-8"))

    @staticmethod
    def _required_coverage_gaps(research: dict[str, Any]) -> set[str]:
        """Return the live, Controller-bound gaps for the next search cycle."""

        gaps = research.get("required_coverage_gaps") or []
        if not isinstance(gaps, list) or any(
            not isinstance(gap, str) or not gap.strip() for gap in gaps
        ):
            raise ControllerError("required coverage gaps state is invalid")
        return set(gaps)

    def _incremental_evidence_bindings(
        self, state: dict[str, Any], phase_name: str
    ) -> dict[str, str]:
        """Return only phase Evidence whose binding-time context is still current.

        Evidence Cards remain immutable, run-wide provenance.  The small record
        in ``incremental_evidence_by_phase`` is instead a phase-current binding;
        it records the formal inputs that made a particular use current.  This
        deliberately leaves a historical binding in place after a return so it
        can be audited or explicitly re-adopted later.
        """

        sessions = state["research_lit"].get("incremental_evidence_by_phase") or {}
        records = sessions.get(phase_name) if isinstance(sessions, dict) else None
        if not isinstance(records, dict):
            return {}
        bindings: dict[str, str] = {}
        current_anchor: dict[str, Any] | None = None
        for record in records.values():
            if not isinstance(record, dict):
                raise ControllerError("incremental evidence record is invalid")
            path = str(record.get("path") or "")
            digest = str(record.get("sha256") or "")
            candidate = self.root / path
            if not path or not candidate.is_file() or sha256_file(candidate) != digest:
                raise ControllerError("incremental evidence changed after Controller acceptance")
            stored_anchor = record.get("phase_binding_anchor")
            # Runs created before phase-current anchors were introduced retain
            # their existing binding semantics.  New bindings always carry an
            # anchor and therefore never regain currentness after a return
            # merely because regenerated bytes happen to match.
            if stored_anchor is not None:
                if not isinstance(stored_anchor, dict):
                    raise ControllerError("incremental evidence binding anchor is invalid")
                if current_anchor is None:
                    current_anchor = self._phase_evidence_anchor(state, phase_name)
                comparison_anchor = current_anchor
                # A normal RCA revision keeps the accepted Problem and its
                # still-relevant diagnostic Evidence current.  Only the
                # exceptional method->reopened-RCA adoption is tied to that
                # specific return receipt.
                if phase_name == "root_cause_analysis" and "reopened_rca_return_event_id" in stored_anchor:
                    comparison_anchor = {
                        **current_anchor,
                        "reopened_rca_return_event_id": self._phase_lifecycle_return_id(
                            state, "root_cause_analysis"
                        ),
                    }
                if stored_anchor != comparison_anchor:
                    continue
            bindings[path] = digest
        return bindings

    def _current_phase_evidence_ids(
        self, state: dict[str, Any], phase_name: str
    ) -> set[str]:
        """Project the one Evidence Registry into a phase's current view.

        Landscape Cards remain generally usable.  A Card that has entered a
        phase-scoped incremental binding is usable only through a current
        binding for the requesting phase; this is the same Controller filter
        used for Gate artifact hashes, expressed as source IDs for validators.
        """

        all_paths = run_state._current_formal_evidence_paths(str(self.root), state)
        path_to_ids: dict[str, set[str]] = {}
        for evidence_id, path in all_paths.items():
            path_to_ids.setdefault(path, set()).add(evidence_id)
        scoped_ids: set[str] = set()
        by_phase = state["research_lit"].get("incremental_evidence_by_phase") or {}
        if not isinstance(by_phase, dict):
            raise ControllerError("incremental evidence records are invalid")
        for records in by_phase.values():
            if not isinstance(records, dict):
                raise ControllerError("incremental evidence records are invalid")
            for binding_key, record in records.items():
                if not isinstance(record, dict):
                    raise ControllerError("incremental evidence record is invalid")
                evidence_key = record.get("evidence_key") or binding_key
                if isinstance(evidence_key, str) and evidence_key.startswith("evidence:"):
                    scoped_ids.add(evidence_key.split(":", 1)[1])
        current_ids: set[str] = set()
        for path in self._incremental_evidence_bindings(state, phase_name):
            current_ids.update(path_to_ids.get(path, set()))
        landscape_ids = {
            evidence_id
            for evidence_id in state["research_lit"].get("landscape_evidence_ids") or []
            if isinstance(evidence_id, str)
        }
        return (set(all_paths) - scoped_ids) | current_ids | landscape_ids

    @staticmethod
    def _binding_artifact_identity(record: dict[str, Any]) -> dict[str, Any]:
        """Keep the existing registered artifact identity in a binding anchor."""

        identity: dict[str, Any] = {
            "path": str(record.get("path") or ""),
            "sha256": str(record.get("sha256") or ""),
        }
        for field in ("producer_phase", "registered_at", "accepted_at"):
            value = record.get(field)
            if isinstance(value, str) and value:
                identity[field] = value
        for field in ("problem_version_binding", "acceptance"):
            value = record.get(field)
            if isinstance(value, dict):
                identity[field] = deepcopy(value)
        return identity

    def _phase_lifecycle_return_id(self, state: dict[str, Any], phase_name: str) -> str | None:
        """Use the existing return history as the phase lifecycle boundary."""

        history = (state.get("scientific_core") or {}).get("return_history") or []
        for event in reversed(history):
            if not isinstance(event, dict):
                continue
            if phase_name in set(event.get("invalidated_phases") or []):
                event_id = event.get("id")
                return str(event_id) if isinstance(event_id, str) and event_id else None
        return None

    def _current_method_obligation_binding(
        self, state: dict[str, Any], phase_name: str
    ) -> dict[str, Any] | None:
        """Resolve the one current formal obligation context without a new registry."""

        research = state["research_lit"]
        if phase_name == "method_design":
            record = (research.get("accepted_artifacts") or {}).get(
                "incremental-query-plan-method_design"
            )
            if not isinstance(record, dict):
                return None
            path = self.root / str(record.get("path") or "")
            if not path.is_file() or sha256_file(path) != record.get("sha256"):
                raise ControllerError("accepted method-design query plan changed after validation")
            try:
                context = json.loads(path.read_text(encoding="utf-8")).get("method_design_context")
            except json.JSONDecodeError as exc:
                raise ControllerError("accepted method-design query plan is invalid") from exc
            if not isinstance(context, dict):
                return None
            mechanism_ids = [
                item.get("mechanism_change_id")
                for item in context.get("required_mechanism_changes") or []
                if isinstance(item, dict)
            ]
            capability_ids = [
                item.get("capability_id")
                for item in context.get("required_capabilities") or []
                if isinstance(item, dict)
            ]
            obligation_ids = [
                item.get("obligation_id")
                for item in context.get("design_obligations") or []
                if isinstance(item, dict)
            ]
            if any(
                not values or any(not isinstance(value, str) or not value for value in values)
                for values in (mechanism_ids, capability_ids, obligation_ids)
            ):
                raise ControllerError("accepted method-design Principle-search context is invalid")
            return {
                "source": "method_design_query_context",
                "mechanism_change_ids": sorted(mechanism_ids),
                "capability_ids": sorted(capability_ids),
                "obligation_ids": sorted(obligation_ids),
                "principle_search_context_sha256": hashlib.sha256(
                    json.dumps(context, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
                ).hexdigest(),
            }

        selected_path = str(self.workflow["artifact_manifest"]["selected_principle"])
        selected_record = self._registered_artifact_by_path(state, selected_path)
        if not isinstance(selected_record, dict):
            return None
        try:
            selected = yaml.safe_load((self.root / selected_path).read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError, AttributeError) as exc:
            raise ControllerError("current method obligation binding is invalid") from exc
        obligation_ids = selected.get("obligation_ids") if isinstance(selected, dict) else None
        if not obligation_ids or any(not isinstance(item, str) or not item for item in obligation_ids):
            raise ControllerError("Selected Principle has invalid obligation IDs")
        return {
            "source": "selected_principle",
            "obligation_ids": sorted(obligation_ids),
            "principle_id": selected.get("principle_id"),
            "principle_version": selected.get("principle_version"),
            "mechanism_change_ids": list(selected.get("mechanism_change_ids") or []),
            "selected_principle": self._binding_artifact_identity(selected_record),
        }

    def _registered_evidence_card(
        self, research: dict[str, Any], source_id: str
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Resolve one immutable, fully-provenanced Evidence Card."""

        evidence_key = f"evidence:{source_id}"
        record = (research.get("accepted_artifacts") or {}).get(evidence_key)
        if not isinstance(record, dict):
            raise ControllerError("Evidence Card is not registered in this run")
        path = str(record.get("path") or "")
        digest = str(record.get("sha256") or "")
        card_path = self.root / path
        read_event = research.get("read_events", {}).get(record.get("read_event_id"))
        if (
            not path
            or not digest
            or not card_path.is_file()
            or sha256_file(card_path) != digest
            or not isinstance(read_event, dict)
            or read_event.get("status") != "complete"
        ):
            raise ControllerError("Evidence Card lacks complete current-run read provenance")
        try:
            card = json.loads(card_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ControllerError("registered Evidence Card is invalid") from exc
        if card.get("source_id") != source_id or card.get("read_event_id") != record.get("read_event_id"):
            raise ControllerError("Evidence Card identity does not match its registered provenance")
        paper = research.get("papers", {}).get(source_id)
        query_ids = paper.get("found_by_query_ids") if isinstance(paper, dict) else None
        user_supplied = isinstance(paper, dict) and paper.get("source_origin") == "user_supplied"
        if not user_supplied and (
            not isinstance(query_ids, list)
            or not query_ids
            or any(
                not isinstance(research.get("query_events", {}).get(query_id), dict)
                or research["query_events"][query_id].get("status") not in {"complete", "complete_human"}
                for query_id in query_ids
            )
        ):
            raise ControllerError("Evidence Card lacks complete query/search provenance")
        registry_path = self._paths()["evidence_registry"]
        try:
            registry_has_card = any(
                isinstance(row, dict)
                and row.get("source_id") == source_id
                and row.get("read_event_id") == record.get("read_event_id")
                for row in (
                    json.loads(line)
                    for line in registry_path.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                )
            )
        except (OSError, json.JSONDecodeError) as exc:
            raise ControllerError("Evidence Registry provenance is unavailable") from exc
        if not registry_has_card:
            raise ControllerError("Evidence Card is absent from the Evidence Registry")
        return record, card

    def _historical_phase_evidence_keys(self, research: dict[str, Any]) -> set[str]:
        """Return Evidence keys with a binding under a declared literature phase."""

        permitted_phases = set(
            (self.workflow.get("scientific_core") or {})
            .get("incremental_literature", {})
            .get("permitted_phases", [])
        )
        by_phase = research.get("incremental_evidence_by_phase") or {}
        if not isinstance(by_phase, dict):
            return set()
        return {
            evidence_key
            for phase_name, records in by_phase.items()
            if phase_name in permitted_phases and isinstance(records, dict)
            for binding_key, binding in records.items()
            if isinstance(binding, dict)
            for evidence_key in [binding.get("evidence_key") or binding_key]
            if isinstance(evidence_key, str) and evidence_key.startswith("evidence:")
        }

    def _method_re_adoption_mechanical_status(
        self,
        research: dict[str, Any],
        phase_name: str,
        evidence_key: str,
        anchor: dict[str, Any],
    ) -> str:
        """Classify only the mechanics shared by Method discovery and execution."""

        if not isinstance(anchor.get("design_obligation_binding"), dict):
            return "missing_obligation_context"
        if evidence_key not in self._historical_phase_evidence_keys(research):
            return "not_historical_phase_evidence"
        records = (research.get("incremental_evidence_by_phase") or {}).get(phase_name)
        if isinstance(records, dict) and any(
            isinstance(binding, dict)
            and (binding.get("evidence_key") or binding_key) == evidence_key
            and binding.get("phase_binding_anchor") == anchor
            for binding_key, binding in records.items()
        ):
            return "already_current"
        return "eligible"

    @staticmethod
    def _evidence_has_method_context(
        research: dict[str, Any], evidence_key: str, card: dict[str, Any]
    ) -> bool:
        if "method_design_search_context" in card or "method_refinement_search_context" in card:
            return True
        method_phases = {"method_design", "method_refinement", "final_method_novelty_gate"}
        return any(
            isinstance(binding, dict) and binding.get("evidence_key") == evidence_key
            for phase_name, phase_records in (research.get("incremental_evidence_by_phase") or {}).items()
            if phase_name in method_phases and isinstance(phase_records, dict)
            for binding in phase_records.values()
        )

    def reopen_root_cause(
        self,
        reason: str,
        *,
        evidence_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Return a running method-design phase to RCA through the one normal path."""

        scientific_reason = reason.strip()
        if not scientific_reason:
            raise ControllerError("root-cause reopen requires a non-empty scientific reason")
        normalized_ids = [str(item).strip() for item in (evidence_ids or [])]
        if any(not item for item in normalized_ids) or len(normalized_ids) != len(set(normalized_ids)):
            raise ControllerError("root-cause reopen Evidence IDs must be non-empty and unique")
        with self._store.mutate() as state:
            research = state["research_lit"]
            if (
                research.get("current_stage") != "LANDSCAPE_ACCEPTED"
                or self._incremental_literature_active(research) is not None
            ):
                raise ControllerError(
                    "finish the active method literature session before reopening root-cause analysis"
                )
            phase = self._current_core_phase(state)
            if phase.get("phase") != "method_design" or phase.get("status") != "running":
                raise ControllerError("root-cause reopen requires method_design to be running")
            self._assert_phase_inputs_current(state, "method_design")
            for source_id in normalized_ids:
                _record, card = self._registered_evidence_card(research, source_id)
                if not self._evidence_has_method_context(research, f"evidence:{source_id}", card):
                    raise ControllerError(
                        "root-cause reopen Evidence must previously have been used in a method context"
                    )
            self._return_to_phase(
                state,
                from_phase="method_design",
                target="root_cause_analysis",
                decision="METHOD_TO_RCA_REOPEN",
                reason=scientific_reason,
                provenance={"trigger_evidence_ids": normalized_ids},
            )
            return state

    def _phase_evidence_anchor(self, state: dict[str, Any], phase_name: str) -> dict[str, Any]:
        """Build the minimal formal context that makes a phase Evidence use current."""

        supported = {
            "problem_generation", "problem_novelty_gate", "root_cause_analysis",
            "method_design", "method_refinement", "final_method_novelty_gate",
        }
        if phase_name not in supported:
            raise ControllerError(f"incremental evidence has no declared phase context: {phase_name}")
        required_inputs: dict[str, dict[str, Any]] = {}
        for raw_path in self._resolved_phase_paths(state, phase_name, "required_inputs"):
            record = self._registered_artifact_by_path(state, raw_path)
            if not isinstance(record, dict) or not record.get("sha256"):
                raise ControllerError(f"phase evidence anchor has no registered input: {raw_path}")
            required_inputs[str(raw_path)] = self._binding_artifact_identity(record)
        anchor: dict[str, Any] = {
            "phase": phase_name,
            "required_inputs": required_inputs,
        }
        if phase_name != "root_cause_analysis":
            anchor["lifecycle_return_event_id"] = self._phase_lifecycle_return_id(
                state, phase_name
            )
        core = state["scientific_core"]
        if phase_name == "problem_generation":
            # There is deliberately no active accepted Problem at initial
            # discovery.  A reopened draft is identified by the existing
            # pending-revision and return records instead.
            pending = core.get("pending_problem_revision")
            if isinstance(pending, dict):
                anchor["pending_problem_revision"] = deepcopy(pending)
                return_id = pending.get("return_event_id")
                if isinstance(return_id, str) and return_id:
                    anchor["problem_return_event_id"] = return_id
        elif phase_name in {"root_cause_analysis", "method_design", "method_refinement", "final_method_novelty_gate"}:
            active = self._assert_active_problem_version_current(state)
            anchor["active_problem_binding"] = {
                key: active[key]
                for key in ("problem_id", "version", "contract_sha256", "evidence_capsule_sha256")
            }
        if phase_name in {"method_design", "method_refinement", "final_method_novelty_gate"}:
            root_phase = run_state._find_phase(state, "root_cause_analysis")
            anchor["accepted_rca_binding"] = {
                "analysis_id": root_phase.get("analysis_id"),
                "lifecycle_return_event_id": self._phase_lifecycle_return_id(
                    state, "root_cause_analysis"
                ),
            }
            obligations = self._current_method_obligation_binding(state, phase_name)
            if obligations is not None:
                anchor["design_obligation_binding"] = obligations
        return anchor

    def _backfill_current_evidence_anchors(
        self, state: dict[str, Any], phase_names: list[str]
    ) -> None:
        """Close the upgrade boundary before an existing return invalidates it.

        Pre-anchor runs have durable phase bindings but no record of their
        original context.  At the next formal return we still have that live
        context, so retain it on the existing binding rather than deleting
        Evidence or inventing a parallel derivation history.
        """

        by_phase = state["research_lit"].get("incremental_evidence_by_phase") or {}
        if not isinstance(by_phase, dict):
            return
        for phase_name in phase_names:
            records = by_phase.get(phase_name)
            if not isinstance(records, dict) or not any(
                isinstance(record, dict) and "phase_binding_anchor" not in record
                for record in records.values()
            ):
                continue
            try:
                anchor = self._phase_evidence_anchor(state, phase_name)
            except ControllerError:
                # Only legacy hand-built fixtures can lack the Controller's
                # required formal inputs at this point.  Normal runs reached
                # this return through those checks and are always anchored.
                continue
            for evidence_key, record in records.items():
                if isinstance(record, dict) and "phase_binding_anchor" not in record:
                    record["evidence_key"] = str(record.get("evidence_key") or evidence_key)
                    record["phase_binding_anchor"] = deepcopy(anchor)

    def _record_validation(
        self, research: dict, artifact: str, result: str, errors: list[str] | None = None
    ) -> None:
        research["validator_results"].append(
            {
                "timestamp": now(),
                "artifact": artifact,
                "result": result,
                "errors": errors or [],
            }
        )

    def _assert_artifact_current(self, research: dict, name: str) -> dict[str, Any]:
        record = (research.get("accepted_artifacts") or {}).get(name)
        if not isinstance(record, dict) or record.get("validator_result") != "PASS":
            raise ControllerError(f"{name} is not a Controller-accepted artifact")
        path = self.root / str(record.get("path") or "")
        expected = record.get("sha256")
        if not path.is_file() or not expected or sha256_file(path) != expected:
            raise ControllerError(f"accepted artifact changed after validation: {name}")
        return record

    def _assert_pending_source_policy_current(
        self, research: dict[str, Any]
    ) -> dict[str, Any]:
        record = research.get("pending_source_policy")
        if not isinstance(record, dict) or record.get("validator_result") != "PASS":
            raise ControllerError("source policy candidate has not passed validation")
        path = self.root / str(record.get("path") or "")
        expected = record.get("sha256")
        if not path.is_file() or not expected or sha256_file(path) != expected:
            raise ControllerError("validated source policy candidate changed before approval")
        return record

    @staticmethod
    def _fallback_level_three_active(research: dict[str, Any]) -> bool:
        """Return whether a *recorded query* reached the level-three route.

        Provider failures are query-scoped incidents.  They must never become a
        run-wide source blacklist because a browser block and ordinary network
        failures are often transient.
        """

        for event in research.get("query_events", {}).values():
            attempts = event.get("provider_attempts") or []
            statuses = {
                str(item.get("provider")): str(item.get("status"))
                for item in attempts
                if isinstance(item, dict)
            }
            if (
                statuses.get("serpapi_google_scholar") in {"unavailable", "blocked"}
                and statuses.get("scholar_google_hk") in {"unavailable", "blocked"}
                and any(
                    statuses.get(name) == "complete"
                    for name in ("arxiv", "ieee_xplore")
                )
            ):
                return True
        return False

    def _route_planned_queries_to_human_search(
        self,
        research: dict[str, Any],
        *,
        evidence_gaps: list[Any],
        reason: str,
        include_completed: bool = False,
    ) -> None:
        eligible_statuses = {"planned", "started"}
        if include_completed:
            eligible_statuses.add("complete")
        candidates = [
            item
            for item in research["planned_queries"]
            if item.get("status") in eligible_statuses
        ]
        if not candidates:
            raise ControllerError("no planned query is available for required human search")
        unallocated = sum(1 for item in candidates if not item.get("query_id"))
        if research["query_count"] + unallocated > research["max_queries"]:
            raise ControllerError(
                "human-search batch would exceed the declared query budget: "
                f"{research['query_count']}+{unallocated}/{research['max_queries']}"
            )
        session = self._incremental_literature_active(research)
        active_plan_record = (
            session if session is not None else self._assert_artifact_current(research, "query_plan")
        )
        query_plan_sha256 = str(
            active_plan_record.get("query_plan_sha256") or active_plan_record.get("sha256") or ""
        )
        if not query_plan_sha256:
            raise ControllerError("accepted query plan has no sha256")
        request_queries: list[dict[str, Any]] = []
        all_attempts: list[dict[str, Any]] = []
        for item in candidates:
            query_context = self._problem_lead_query_context(research, item)
            query_id = item.get("query_id")
            if not query_id:
                before = research["query_count"]
                research["query_count"] = before + 1
                query_id = f"Q{research['query_count']:04d}"
                budget_before = {
                    "queries": before,
                    "fulltext": research["fulltext_count"],
                }
                budget_after = {
                    "queries": research["query_count"],
                    "fulltext": research["fulltext_count"],
                }
                research["query_events"][query_id] = {
                    "event_id": uuid.uuid4().hex,
                    "query": item["query"],
                    "coverage_gaps": list(item.get("coverage_gaps") or []),
                    "query_plan_sha256": query_plan_sha256,
                    "query_context": query_context,
                    "tool": "human_google_scholar",
                    "status": "planned",
                    "budget_before": budget_before,
                    "budget_after": budget_after,
                }
            item["query_id"] = query_id
            item["status"] = "human_search_required"
            event = research["query_events"].setdefault(
                query_id,
                {
                    "event_id": query_id,
                    "query": item["query"],
                    "coverage_gaps": list(item.get("coverage_gaps") or []),
                    "tool": "human_google_scholar",
                    "status": item["status"],
                    "budget_before": None,
                    "budget_after": None,
                },
            )
            event["status"] = item["status"]
            event["tool"] = "human_google_scholar"
            event["query_plan_sha256"] = query_plan_sha256
            if query_context is not None:
                event["query_plan_sha256"] = query_context["query_plan_sha256"]
                event["query_context"] = query_context
            attempts = [
                dict(attempt)
                for attempt in event.get("provider_attempts") or []
                if isinstance(attempt, dict)
            ]
            all_attempts.extend(attempts)
            request_queries.append(
                {
                    "query_id": query_id,
                    "plan_item_id": item.get("plan_item_id"),
                    "query": item["query"],
                    "purpose": item["purpose"],
                    "coverage_gaps": list(item.get("coverage_gaps") or []),
                    "priority_tier": item.get("priority_tier"),
                    "target_venues": list(item.get("target_venues") or []),
                    "constraints": dict(item.get("constraints") or {}),
                    "query_context": query_context,
                    "provider_attempts": attempts,
                }
            )
        current = request_queries[0]
        research["human_search_request"] = {
            "status": "HUMAN_SEARCH_REQUIRED",
            "kind": "metadata_search_batch",
            "query": current["query"],
            "purpose": current["purpose"],
            "evidence_gaps": list(evidence_gaps),
            "preferred_sources": ["Google Scholar", "arXiv", "IEEE Xplore"],
            "provider_attempts": all_attempts,
            "reason": reason,
            "queries": request_queries,
            "remaining_queries": request_queries[1:],
            "stop": True,
        }
        research["current_stage"] = "HUMAN_SEARCH_REQUIRED"
        research["waiting_for"] = "human_search_results"

    def _consume_agent_attestation(
        self,
        role: str,
        correlation_id: str,
        payload: dict[str, Any],
        *,
        allow_missing: bool = False,
    ) -> dict[str, Any] | None:
        path = (
            self.root
            / ".aris"
            / "agent-attestations"
            / role
            / f"{correlation_id}.json"
        )
        try:
            attestation = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            if allow_missing:
                return None
            raise ControllerError(
                f"no SubagentStop attestation from required role {role}"
            ) from exc
        canonical = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        expected_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        if (
            attestation.get("agent_type") != role
            or attestation.get("correlation_id") != correlation_id
            or attestation.get("payload_sha256") != expected_hash
            or not attestation.get("agent_id")
        ):
            raise ControllerError(f"invalid or mismatched {role} attestation")
        try:
            path.replace(path.with_suffix(".consumed.json"))
        except OSError as exc:
            raise ControllerError(f"could not consume {role} attestation") from exc
        return attestation

    def _consume_ui_approval_receipt(
        self,
        gate: str,
        request_id: str,
        decision: str,
        *,
        selected_id: str | None = None,
        human_feedback: str | None = None,
        artifact_bindings: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Consume a UI receipt, restoring it if the enclosing state write fails."""

        try:
            receipt = approvals.consume_ui_approval_receipt(
                self.root,
                self.run_id,
                gate,
                request_id,
                decision,
                selected_id=selected_id,
                human_feedback=human_feedback,
                artifact_bindings=artifact_bindings,
            )
        except ValueError as exc:
            raise ControllerError(str(exc)) from exc
        try:
            self._store.recover_on_mutation_failure(
                lambda: approvals.restore_ui_approval_receipt(
                    self.root, self.run_id, request_id
                )
            )
        except BaseException:
            approvals.restore_ui_approval_receipt(self.root, self.run_id, request_id)
            raise
        return receipt

    def _consume_review_attestation(
        self,
        *,
        role: str,
        request_id: str,
        reviewer: str,
        verdict_id: str,
        decision: str,
        artifact_bindings: dict[str, str],
    ) -> dict[str, Any]:
        """Consume a reviewer proof, restoring it if the enclosing state write fails."""

        try:
            attestation = reviews.consume_review_attestation(
                self.root,
                self.run_id,
                role=role,
                request_id=request_id,
                reviewer=reviewer,
                verdict_id=verdict_id,
                decision=decision,
                artifact_bindings=artifact_bindings,
            )
        except ValueError as exc:
            raise ControllerError(str(exc)) from exc
        try:
            self._store.recover_on_mutation_failure(
                lambda: reviews.restore_review_attestation(
                    self.root,
                    self.run_id,
                    role=role,
                    request_id=request_id,
                )
            )
        except BaseException:
            reviews.restore_review_attestation(
                self.root, self.run_id, role=role, request_id=request_id
            )
            raise
        return attestation

    def _attested_reviewer_payload(
        self,
        *,
        role: str,
        request_id: str,
        reviewer: str,
        verdict_id: str,
        decision: str,
        artifact_bindings: dict[str, str],
    ) -> dict[str, Any]:
        """Return the complete reviewer-owned payload after verifying its receipt."""

        try:
            attestation = reviews.load_review_attestation(
                self.root, self.run_id, role=role, request_id=request_id,
                artifact_bindings=artifact_bindings,
            )
        except ValueError as exc:
            raise ControllerError(str(exc)) from exc
        payload = attestation.get("verdict_payload")
        if not isinstance(payload, dict):
            raise ControllerError("reviewer attestation lacks the complete canonical payload")
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        if hashlib.sha256(canonical.encode("utf-8")).hexdigest() != attestation.get("payload_sha256"):
            raise ControllerError("reviewer canonical payload fails its attested hash")
        expected = {
            "run_id": self.run_id, "review_request_id": request_id,
            "reviewer": reviewer, "verdict_id": verdict_id,
            "decision": decision, "reviewed_artifact_hashes": artifact_bindings,
        }
        if any(payload.get(key) != value for key, value in expected.items()):
            raise ControllerError("reviewer canonical payload does not match the live attestation")
        return payload

    def _assert_candidate_verdict_attested(
        self, state: dict[str, Any], phase: dict[str, Any], request: dict[str, Any], result: dict[str, Any]
    ) -> None:
        """Ensure the candidate judgments which drive the next phase are reviewer-owned."""

        role = str(request["required_reviewer_role"])
        phase_name = str(phase["phase"])
        if phase_name not in {"problem_quality_gate", "problem_novelty_gate"}:
            return
        payload = self._attested_reviewer_payload(
            role=role, request_id=str(request["id"]), reviewer=str(result["reviewer"]),
            verdict_id=str(result["verdict_id"]), decision=str(result["gate_verdict"]),
            artifact_bindings=dict(request["artifact_bindings"]),
        )
        records = payload.get("verdict_records")
        if not isinstance(records, list):
            raise ControllerError("candidate reviewer payload lacks verdict_records")
        paths = self._resolved_phase_paths(state, str(phase["phase"]), "produced_artifacts")
        if len(paths) != 1:
            raise ControllerError("candidate Gate must declare exactly one verdict artifact")
        try:
            actual = [json.loads(line) for line in (self.root / paths[0]).read_text(encoding="utf-8").splitlines() if line.strip()]
        except json.JSONDecodeError as exc:
            raise ControllerError("candidate verdict artifact is not valid JSONL") from exc
        if actual != records:
            raise ControllerError("candidate verdict artifact differs from the attested reviewer payload")

    def _phase_spec(self, state: dict, phase_name: str) -> dict[str, Any]:
        spec = run_state._workflow_phase(state, phase_name)
        if not isinstance(spec, dict):
            raise ControllerError(f"workflow phase is not declared: {phase_name}")
        return spec

    def _current_core_phase(self, state: dict) -> dict[str, Any]:
        core = state.get("scientific_core") or {}
        if core.get("status") != "ACTIVE" or not core.get("current_phase"):
            raise ControllerError("scientific core is not active")
        return run_state._find_phase(state, str(core["current_phase"]))

    def _resolved_phase_paths(
        self, state: dict, phase_name: str, field: str
    ) -> list[str]:
        spec = self._phase_spec(state, phase_name)
        return run_state._resolve_artifact_refs(
            state.get("workflow") or {}, list(spec.get(field) or []), phase_name
        )

    def _artifact_record(
        self,
        raw_path: str,
        *,
        producer_phase: str,
        provenance: dict[str, Any],
        upstream_snapshot: dict[str, str],
    ) -> dict[str, Any]:
        path = Path(raw_path)
        if not path.is_absolute():
            path = self.root / path
        if not path.is_file():
            raise ControllerError(f"formal handoff artifact is missing: {raw_path}")
        try:
            stored_path = str(path.resolve().relative_to(self.root))
        except ValueError:
            stored_path = str(path.resolve())
        return {
            "path": stored_path,
            "sha256": sha256_file(path),
            "size_bytes": path.stat().st_size,
            "status": "active",
            "producer_phase": producer_phase,
            "registered_at": now(),
            "provenance": dict(provenance),
            "upstream_snapshot": dict(upstream_snapshot),
        }

    def _registered_artifact_by_path(
        self, state: dict, raw_path: str
    ) -> dict[str, Any] | None:
        path = Path(raw_path)
        if not path.is_absolute():
            path = self.root / path
        resolved = path.resolve()
        core = state.get("scientific_core") or {}
        records: list[dict[str, Any]] = []
        landscape = core.get("landscape_handoff") or {}
        records.extend(
            item for item in (landscape.get("artifacts") or {}).values()
            if isinstance(item, dict)
        )
        records.extend(
            item for item in (core.get("accepted_artifacts") or {}).values()
            if isinstance(item, dict)
        )
        for record in records:
            candidate = Path(str(record.get("path") or ""))
            if not candidate.is_absolute():
                candidate = self.root / candidate
            if candidate.resolve() == resolved:
                return record
        return None

    def _assert_phase_inputs_current(self, state: dict, phase_name: str) -> None:
        spec = self._phase_spec(state, phase_name)
        try:
            run_state._assert_dependencies(str(self.root), state, spec, phase_name)
        except ValueError as exc:
            raise ControllerError(str(exc)) from exc
        for raw_path in self._resolved_phase_paths(state, phase_name, "required_inputs"):
            record = self._registered_artifact_by_path(state, raw_path)
            if not isinstance(record, dict):
                raise ControllerError(
                    f"required input is not a Controller-registered handoff: {raw_path}"
                )
            path = Path(str(record["path"]))
            if not path.is_absolute():
                path = self.root / path
            if not path.is_file() or sha256_file(path) != record.get("sha256"):
                raise ControllerError(f"registered handoff changed after acceptance: {raw_path}")
        if phase_name == "root_cause_gate":
            analysis_phase = run_state._find_phase(state, "root_cause_analysis")
            for source in analysis_phase.get("diagnostic_pilot_artifacts") or []:
                if not isinstance(source, dict):
                    raise ControllerError("root-cause diagnostic-pilot registry record is invalid")
                raw_path = source.get("path")
                if not isinstance(raw_path, str):
                    raise ControllerError("root-cause diagnostic-pilot registry record has no path")
                record = self._registered_artifact_by_path(state, raw_path)
                if not isinstance(record, dict):
                    raise ControllerError(
                        f"root-cause diagnostic pilot is not Controller-registered: {raw_path}"
                    )
                path = Path(str(record["path"]))
                if not path.is_absolute():
                    path = self.root / path
                if not path.is_file() or sha256_file(path) != record.get("sha256"):
                    raise ControllerError(
                        f"root-cause diagnostic pilot changed after diagnosis acceptance: {raw_path}"
                    )
        if phase_name in {
            "method_design",
            "principle_human_selection",
            "principle_test_design",
            "principle_test_human_approval",
            "principle_evaluation",
            "method_refinement",
            "final_method_novelty_gate",
            "final_method_human_acceptance",
        }:
            self._assert_active_problem_version_current(state)
        if phase_name in {
            "principle_test_design",
            "principle_test_human_approval",
            "principle_evaluation",
        }:
            self._selected_for_testing_candidate(state)

    def _assert_active_problem_version_current(self, state: dict) -> dict[str, Any]:
        """Verify that downstream method work consumes the accepted problem version."""

        core = state["scientific_core"]
        active = core.get("active_problem_version")
        if not isinstance(active, dict):
            raise ControllerError("method work requires a current human-accepted problem version")
        contract_path = str(active.get("contract_path") or "")
        contract_hash = str(active.get("contract_sha256") or "")
        evidence_path = str(active.get("evidence_capsule_path") or "")
        evidence_hash = str(active.get("evidence_capsule_sha256") or "")
        record = self._registered_artifact_by_path(state, contract_path)
        evidence_record = self._registered_artifact_by_path(state, evidence_path)
        if (
            not contract_path
            or not contract_hash
            or not isinstance(record, dict)
            or record.get("sha256") != contract_hash
            or not evidence_path
            or not evidence_hash
            or not isinstance(evidence_record, dict)
            or evidence_record.get("sha256") != evidence_hash
        ):
            raise ControllerError("active problem version is not registered to its accepted contract and evidence capsule")
        path = self.root / contract_path
        evidence = self.root / evidence_path
        if (
            not path.is_file()
            or sha256_file(path) != contract_hash
            or not evidence.is_file()
            or sha256_file(evidence) != evidence_hash
        ):
            raise ControllerError("accepted problem version changed after human acceptance")
        return dict(active)

    def _selected_problem_novelty_record(
        self, state: dict, selected_id: str
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Return one selected candidate's current, accepted novelty audit."""

        quality = run_state._find_phase(state, "problem_quality_gate")
        if selected_id not in (quality.get("survivor_ids") or []):
            raise ControllerError(
                "selected_id must be quality-certified and covered by the completed novelty audit"
            )
        novelty_path = "idea-stage/PROBLEM_NOVELTY_VERDICTS.jsonl"
        novelty_record = self._registered_artifact_by_path(state, novelty_path)
        if not isinstance(novelty_record, dict) or not novelty_record.get("sha256"):
            raise ControllerError("problem acceptance is missing a registered novelty verdict artifact")
        novelty_file = self.root / novelty_path
        if not novelty_file.is_file() or sha256_file(novelty_file) != novelty_record["sha256"]:
            raise ControllerError("problem novelty verdict artifact changed after acceptance")
        try:
            novelty_rows = [
                json.loads(line)
                for line in novelty_file.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        except json.JSONDecodeError as exc:
            raise ControllerError("problem novelty verdict artifact is not valid JSONL") from exc
        selected_records = [
            row for row in novelty_rows
            if row.get("record_type") == "candidate_verdict"
            and row.get("candidate_id") == selected_id
        ]
        if len(selected_records) != 1:
            raise ControllerError("selected_id must have exactly one completed novelty audit record")
        selected = selected_records[0]
        if selected.get("decision") not in {"NOVEL", "NOT_NOVEL", "UNCERTAIN"}:
            raise ControllerError(
                "selected_id novelty audit must be NOVEL, NOT_NOVEL, or UNCERTAIN"
            )
        return dict(selected), dict(novelty_record)

    def _accept_problem_version(
        self,
        state: dict,
        *,
        selected_id: str,
        registered: dict[str, dict[str, Any]],
        acceptance: dict[str, Any],
    ) -> dict[str, Any]:
        """Lock the selected problem's current version at the Human Gate."""

        core = state["scientific_core"]
        contract_path = "idea-stage/RESEARCH_CONTRACT.md"
        evidence_path = "idea-stage/PROBLEM_EVIDENCE_CAPSULE.md"
        contract = registered.get(contract_path)
        evidence = registered.get(evidence_path)
        if not isinstance(contract, dict) or not isinstance(evidence, dict):
            raise ControllerError("problem acceptance did not register the problem contract and evidence capsule")
        quality = run_state._find_phase(state, "problem_quality_gate")
        novelty = run_state._find_phase(state, "problem_novelty_gate")
        selected_novelty_record, novelty_record = self._selected_problem_novelty_record(
            state, selected_id
        )
        candidate_path = "idea-stage/PROBLEM_CANDIDATES.jsonl"
        quality_path = "idea-stage/PROBLEM_QUALITY_VERDICTS.jsonl"
        novelty_path = "idea-stage/PROBLEM_NOVELTY_VERDICTS.jsonl"
        candidate = self._registered_artifact_by_path(state, candidate_path)
        quality_record = self._registered_artifact_by_path(state, quality_path)
        if not all(isinstance(item, dict) and item.get("sha256") for item in (candidate, quality_record, novelty_record)):
            raise ControllerError("problem acceptance is missing a registered candidate or verdict artifact")
        selected_novelty_decision = selected_novelty_record["decision"]
        try:
            capsule_artifacts = validate_problem_capsule_nonliterature_artifacts(
                (self.root / evidence_path).read_text(encoding="utf-8")
            )
            allowed_capsule_evidence_ids = set(
                run_state._current_formal_evidence_paths(str(self.root), state)
            ) | {source["artifact_id"] for source in capsule_artifacts}
            validate_problem_acceptance_handoff(
                (self.root / contract_path).read_text(encoding="utf-8"),
                (self.root / evidence_path).read_text(encoding="utf-8"),
                selected_id=selected_id,
                candidate_path=candidate_path,
                candidate_sha256=str(candidate["sha256"]),
                quality_path=quality_path,
                quality_sha256=str(quality_record["sha256"]),
                quality_verdict_id=str(quality.get("verdict_id") or ""),
                novelty_path=novelty_path,
                novelty_sha256=str(novelty_record["sha256"]),
                novelty_verdict_id=str(novelty.get("verdict_id") or ""),
                novelty_candidate_decision=str(selected_novelty_decision),
                contract_path=contract_path,
                contract_sha256=str(contract["sha256"]),
                allowed_capsule_evidence_ids=allowed_capsule_evidence_ids,
            )
        except ValidationError as exc:
            raise ControllerError(str(exc)) from exc
        pending = core.get("pending_problem_revision")
        if isinstance(pending, dict):
            if (
                selected_id != pending.get("problem_id")
                and not pending.get("allow_problem_replacement")
            ):
                raise ControllerError(
                    "a problem revision must re-confirm the same problem ID; use a new problem discovery run for a different problem"
                )
            if selected_id == pending.get("problem_id"):
                version = int(pending["version"])
                parent_version = int(pending["parent_version"])
            else:
                prior_versions = [
                    int(item.get("version", 0))
                    for item in core.get("problem_versions", [])
                    if item.get("problem_id") == selected_id
                ]
                version = max(prior_versions, default=0) + 1
                parent_version = None
        else:
            prior_versions = [
                int(item.get("version", 0))
                for item in core.get("problem_versions", [])
                if item.get("problem_id") == selected_id
            ]
            version = max(prior_versions, default=0) + 1
            parent_version = version - 1 if version > 1 else None
        record = {
            "problem_id": selected_id,
            "version": version,
            "status": "accepted",
            "parent_version": parent_version,
            "contract_path": contract_path,
            "contract_sha256": contract["sha256"],
            "evidence_capsule_path": evidence_path,
            "evidence_capsule_sha256": evidence["sha256"],
            "accepted_at": now(),
            "acceptance": dict(acceptance),
        }
        core.setdefault("problem_versions", []).append(record)
        core["active_problem_version"] = dict(record)
        core["pending_problem_revision"] = None
        binding = {
            "problem_id": selected_id,
            "version": version,
            "contract_sha256": contract["sha256"],
            "evidence_capsule_sha256": evidence["sha256"],
        }
        contract["problem_version"] = dict(binding)
        evidence["problem_version"] = dict(binding)
        for source in capsule_artifacts:
            raw_path = source["path"]
            if Path(raw_path).is_absolute():
                raise ControllerError(
                    f"problem Capsule non-literature artifact {source['artifact_id']!r} must use a project-relative path"
                )
            path = (self.root / raw_path).resolve()
            try:
                path.relative_to(self.root.resolve())
            except ValueError as exc:
                raise ControllerError(
                    f"problem Capsule non-literature artifact {source['artifact_id']!r} must be inside the project"
                ) from exc
            if not path.is_file() or sha256_file(path) != source["sha256"]:
                raise ControllerError(
                    f"problem Capsule non-literature artifact {source['artifact_id']!r} does not match its declared file hash"
                )
            if self._registered_artifact_by_path(state, raw_path) is not None:
                raise ControllerError(
                    f"problem Capsule non-literature artifact is already registered: {raw_path}"
                )
            artifact_record = self._artifact_record(
                raw_path,
                producer_phase="problem_human_acceptance",
                provenance={
                    "controller": "ARISController",
                    "run_id": self.run_id,
                    "problem_capsule_artifact_id": source["artifact_id"],
                },
                upstream_snapshot={
                    contract_path: str(contract["sha256"]),
                    evidence_path: str(evidence["sha256"]),
                },
            )
            artifact_record["artifact_id"] = source["artifact_id"]
            artifact_record["evidence_source_type"] = source["evidence_source_type"]
            artifact_record["problem_version_binding"] = dict(binding)
            core["accepted_artifacts"][raw_path] = artifact_record
        return binding

    def _begin_problem_revision(
        self,
        state: dict,
        *,
        reason: str,
        source: str,
        return_event_id: str,
        allow_problem_replacement: bool = False,
    ) -> dict[str, Any]:
        """Make a new draft version explicit before reopening problem discovery."""

        core = state["scientific_core"]
        active = self._assert_active_problem_version_current(state)
        for item in reversed(core.get("problem_versions", [])):
            if (
                item.get("problem_id") == active["problem_id"]
                and item.get("version") == active["version"]
                and item.get("status") == "accepted"
            ):
                item["status"] = "superseded"
                item["superseded_at"] = now()
                item["superseded_by"] = int(active["version"]) + 1
                break
        revision = {
            "problem_id": active["problem_id"],
            "version": int(active["version"]) + 1,
            "parent_version": int(active["version"]),
            "status": "draft",
            "reason": reason,
            "source": source,
            "allow_problem_replacement": allow_problem_replacement,
            "return_event_id": return_event_id,
            "created_at": now(),
        }
        core["active_problem_version"] = None
        core["pending_problem_revision"] = revision
        return revision

    def _phase_input_bindings(self, state: dict, phase_name: str) -> dict[str, str]:
        """Return the current Controller-registered inputs a Gate must bind."""

        self._assert_phase_inputs_current(state, phase_name)
        bindings: dict[str, str] = {}
        for raw_path in self._resolved_phase_paths(state, phase_name, "required_inputs"):
            record = self._registered_artifact_by_path(state, raw_path)
            if not isinstance(record, dict) or not isinstance(record.get("sha256"), str):
                raise ControllerError(f"Gate input has no registered hash: {raw_path}")
            bindings[str(raw_path)] = str(record["sha256"])
        if phase_name == "root_cause_gate":
            analysis_phase = run_state._find_phase(state, "root_cause_analysis")
            for source in analysis_phase.get("diagnostic_pilot_artifacts") or []:
                if not isinstance(source, dict) or not isinstance(source.get("path"), str):
                    raise ControllerError("root-cause diagnostic-pilot registry record is invalid")
                record = self._registered_artifact_by_path(state, source["path"])
                if not isinstance(record, dict) or not isinstance(record.get("sha256"), str):
                    raise ControllerError(
                        f"root-cause diagnostic pilot has no registered hash: {source['path']}"
                    )
                bindings[source["path"]] = str(record["sha256"])
            # Diagnostic literature collected while 1a–2b was running is part
            # of the reviewed diagnosis, even though it intentionally never
            # mutates the accepted problem Capsule.
            bindings.update(self._incremental_evidence_bindings(state, "root_cause_analysis"))
        if phase_name in {"problem_quality_gate", "problem_novelty_gate"}:
            survivor_ids = None
            if phase_name == "problem_novelty_gate":
                survivor_ids = set(
                    run_state._find_phase(state, "problem_quality_gate").get("survivor_ids") or []
                )
            bindings.update(self._problem_candidate_evidence_bindings(state, survivor_ids=survivor_ids))
        if phase_name == "problem_novelty_gate":
            bindings.update(self._novelty_coverage_bindings())
        bindings.update(self._incremental_evidence_bindings(state, phase_name))
        if not bindings:
            raise ControllerError(f"formal Gate {phase_name!r} has no bindable reviewed artifact")
        return bindings

    def _problem_candidate_evidence_bindings(
        self, state: dict, *, survivor_ids: set[str] | None
    ) -> dict[str, str]:
        """Bind the formal Evidence Cards actually cited by reviewed candidates."""

        candidate_path = "idea-stage/PROBLEM_CANDIDATES.jsonl"
        candidate_record = self._registered_artifact_by_path(state, candidate_path)
        if not isinstance(candidate_record, dict) or not isinstance(candidate_record.get("sha256"), str):
            raise ControllerError("problem candidate registry has no registered hash")
        path = self.root / candidate_path
        if not path.is_file() or sha256_file(path) != candidate_record["sha256"]:
            raise ControllerError("problem candidate registry changed after acceptance")
        evidence_paths = run_state._current_formal_evidence_paths(str(self.root), state)
        try:
            validate_problem_candidates_artifact(
                path.read_text(encoding="utf-8"),
                label="problem candidates",
                formal_evidence_ids=set(evidence_paths),
            )
        except ValidationError as exc:
            raise ControllerError(str(exc)) from exc
        bindings: dict[str, str] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            candidate = json.loads(line)
            candidate_id = candidate["problem_id"]
            if survivor_ids is not None and candidate_id not in survivor_ids:
                continue
            for evidence_id in candidate["evidence_refs"]:
                evidence_path = evidence_paths[evidence_id]
                evidence_file = self.root / evidence_path
                bindings[evidence_path] = sha256_file(evidence_file)
        if not bindings:
            scope = "quality survivors" if survivor_ids is not None else "candidates"
            raise ControllerError(f"reviewed {scope} have no bindable formal evidence")
        return bindings

    def _novelty_coverage_bindings(self) -> dict[str, str]:
        """Bind existing corpus and search-ledger records without a new registry."""

        bindings: dict[str, str] = {}
        for name in ("literature_corpus", "search_log"):
            path = self._paths()[name]
            if not path.is_file():
                raise ControllerError(f"problem novelty coverage artifact is missing: {path}")
            bindings[str(path.relative_to(self.root))] = sha256_file(path)
        return bindings

    def _human_approval_bindings(
        self, state: dict, phase_name: str, spec: dict[str, Any]
    ) -> dict[str, str]:
        """Bind the accepted problem handoffs into its one-time UI receipt."""

        bindings = self._phase_input_bindings(state, phase_name)
        if phase_name != "problem_human_acceptance":
            return bindings
        try:
            run_state._assert_outputs(str(self.root), state, spec, phase_name)
        except ValueError as exc:
            raise ControllerError(str(exc)) from exc
        for raw_path in self._resolved_phase_paths(state, phase_name, "produced_artifacts"):
            path = Path(raw_path)
            if not path.is_absolute():
                path = self.root / path
            if not path.is_file():
                raise ControllerError(f"Human Gate artifact is missing: {raw_path}")
            bindings[str(raw_path)] = sha256_file(path)
        return bindings

    def _phase_review_bindings(self, state: dict, phase_name: str) -> dict[str, str]:
        """Return the exact artifact versions a completed Gate review covers."""

        bindings = self._phase_input_bindings(state, phase_name)
        for raw_path in self._resolved_phase_paths(state, phase_name, "reviewed_artifacts"):
            path = Path(raw_path)
            if not path.is_absolute():
                path = self.root / path
            if not path.is_file():
                raise ControllerError(
                    f"formal Gate review artifact is missing: {raw_path}"
                )
            bindings[str(raw_path)] = sha256_file(path)
        return bindings

    @staticmethod
    def _current_return_feedback(
        state: dict[str, Any], phase_name: str
    ) -> dict[str, Any] | None:
        for event in reversed((state.get("scientific_core") or {}).get("return_history") or []):
            if isinstance(event, dict) and event.get("return_target") == phase_name:
                return {
                    key: deepcopy(value)
                    for key, value in event.items()
                    if key in {
                        "id", "at", "from_phase", "return_target", "decision",
                        "reason", "return_guidance", "human_feedback",
                        "validation_result_id", "trigger_evidence_ids",
                        "evidence_refs", "findings",
                    }
                }
        return None

    def _new_core_review_request(self, state: dict, phase: dict, spec: dict) -> dict[str, Any]:
        role = spec.get("reviewer_role")
        allowed = spec.get("accepted_verdicts")
        if not isinstance(role, str) or not role or not isinstance(allowed, list) or not allowed:
            raise ControllerError("formal reviewer Gate lacks a declared reviewer role or verdict enum")
        self._require_formal_native_runtime(role)
        allowed_review_verdicts = [*allowed, *list((spec.get("return_targets") or {}).keys())]
        request = {
            "id": uuid.uuid4().hex,
            "run_id": self.run_id,
            "phase": phase["phase"],
            "gate": spec["gate_id"],
            "required_reviewer_role": role,
            "accepted_verdicts": list(allowed),
            "allowed_review_verdicts": allowed_review_verdicts,
            "artifact_bindings": self._phase_input_bindings(state, phase["phase"]),
            "issued_by": "ARISController",
            "created_at": now(),
        }
        feedback = self._current_return_feedback(state, str(phase["phase"]))
        if feedback is not None:
            request["return_feedback"] = feedback
        reviewed_artifacts = self._resolved_phase_paths(state, phase["phase"], "reviewed_artifacts")
        if reviewed_artifacts:
            # Method refinement creates the proposal before it can be reviewed.
            # Retain one live request ID, then bind its final proposal version
            # immediately after completion and before any attestation is accepted.
            request["reviewed_artifacts_pending"] = reviewed_artifacts
        return request

    def _method_packet(self, state: dict[str, Any], *, accepted: bool) -> dict[str, Any]:
        raw_path = str(self.workflow["artifact_manifest"]["method_design_packet"])
        path = self.root / raw_path
        if accepted:
            record = (state["scientific_core"].get("accepted_artifacts") or {}).get(raw_path)
            if (
                not isinstance(record, dict)
                or not path.is_file()
                or record.get("sha256") != sha256_file(path)
            ):
                raise ControllerError("current method design packet is not Controller-accepted")
        try:
            packet = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ControllerError("method design packet is not valid JSON") from exc
        if not isinstance(packet, dict):
            raise ControllerError("method design packet must be a JSON object")
        return packet

    def _principle_test_plan(self, state: dict[str, Any], *, accepted: bool) -> dict[str, Any]:
        raw_path = str(self.workflow["artifact_manifest"]["principle_test_plan"])
        path = self.root / raw_path
        if accepted:
            record = (state["scientific_core"].get("accepted_artifacts") or {}).get(raw_path)
            if (
                not isinstance(record, dict)
                or not path.is_file()
                or record.get("sha256") != sha256_file(path)
            ):
                raise ControllerError("current Principle test plan is not Controller-accepted")
        try:
            plan = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ControllerError("Principle test plan is not valid JSON") from exc
        if not isinstance(plan, dict):
            raise ControllerError("Principle test plan must be a JSON object")
        return plan

    def _selected_for_testing_candidate(
        self, state: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        core = state["scientific_core"]
        selection = core.get("selected_for_testing")
        if not isinstance(selection, dict) or selection.get("status") != "ACTIVE":
            raise ControllerError("Principle test work requires an active Human-selected Candidate")
        packet_path = str(self.workflow["artifact_manifest"]["method_design_packet"])
        review_path = str(self.workflow["artifact_manifest"]["method_design_review"])
        accepted = core.get("accepted_artifacts") or {}
        for field, raw_path in (
            ("method_design_packet", packet_path),
            ("method_design_review", review_path),
        ):
            record = accepted.get(raw_path)
            expected = selection.get(field)
            path = self.root / raw_path
            if (
                not isinstance(expected, dict)
                or expected != {"path": raw_path, "sha256": (record or {}).get("sha256")}
                or not isinstance(record, dict)
                or not path.is_file()
                or sha256_file(path) != record.get("sha256")
            ):
                raise ControllerError("Human-selected Candidate binding is stale")
        packet = self._method_packet(state, accepted=True)
        candidate = next(
            (
                item
                for item in packet["candidate_principles"]
                if str(item["principle_id"]) == str(selection.get("principle_id"))
                and str(item["principle_version"]) == str(selection.get("principle_version"))
                and item["status"] in {"ACTIVE", "REVISED", "WEAKENED"}
            ),
            None,
        )
        if candidate is None:
            raise ControllerError("Human-selected Candidate no longer resolves to the reviewed packet")
        return selection, candidate

    def _resolve_candidate_selection(
        self, state: dict[str, Any], selected_id: str | None
    ) -> dict[str, Any]:
        if not isinstance(selected_id, str) or not selected_id.strip():
            raise ControllerError("principle_selection requires one explicit Candidate ID/version")
        token = selected_id.strip()
        packet = self._method_packet(state, accepted=True)
        eligible = [
            item for item in packet["candidate_principles"]
            if item["status"] in {"ACTIVE", "REVISED", "WEAKENED"}
        ]
        matches = [
            item for item in eligible
            if token in {
                str(item["principle_id"]),
                f"{item['principle_id']}@{item['principle_version']}",
            }
        ]
        if len(matches) != 1:
            raise ControllerError(
                "principle_selection selected_id must resolve exactly one active Candidate; use principle_id@principle_version when needed"
            )
        return matches[0]

    def _resolve_combine_source_candidates(
        self, state: dict[str, Any], selected_id: str | None
    ) -> list[dict[str, str]]:
        if not isinstance(selected_id, str) or not selected_id.strip():
            raise ControllerError(
                "principle_selection combine requires comma-separated Candidate ID@version sources"
            )
        tokens = [item.strip() for item in selected_id.split(",") if item.strip()]
        if len(tokens) < 2 or len(tokens) != len(set(tokens)):
            raise ControllerError(
                "principle_selection combine requires at least two unique Candidate ID@version sources"
            )
        packet = self._method_packet(state, accepted=True)
        eligible = {
            f"{item['principle_id']}@{item['principle_version']}": item
            for item in packet["candidate_principles"]
            if item["status"] in {"ACTIVE", "REVISED", "WEAKENED"}
        }
        sources: list[dict[str, str]] = []
        for token in tokens:
            if "@" not in token or token not in eligible:
                raise ControllerError(
                    "principle_selection combine sources must be current reviewed Candidate ID@version values"
                )
            item = eligible[token]
            sources.append(
                {
                    "principle_id": str(item["principle_id"]),
                    "principle_version": str(item["principle_version"]),
                }
            )
        return sources

    def _establish_selected_for_testing(
        self,
        state: dict[str, Any],
        *,
        candidate: dict[str, Any],
        request: dict[str, Any],
        receipt: dict[str, Any],
    ) -> dict[str, Any]:
        core = state["scientific_core"]
        packet_path = str(self.workflow["artifact_manifest"]["method_design_packet"])
        review_path = str(self.workflow["artifact_manifest"]["method_design_review"])
        accepted = core["accepted_artifacts"]
        binding = {
            "status": "ACTIVE",
            "binding_type": "selected_for_testing",
            "selection_request_id": request["id"],
            "principle_id": str(candidate["principle_id"]),
            "principle_version": str(candidate["principle_version"]),
            "method_design_packet": {
                "path": packet_path,
                "sha256": accepted[packet_path]["sha256"],
            },
            "method_design_review": {
                "path": review_path,
                "sha256": accepted[review_path]["sha256"],
            },
            "confirmed_in": receipt["confirmed_in"],
            "selected_at": now(),
        }
        core["selected_for_testing"] = binding
        return binding

    def _append_method_history_event(self, manifest_name: str, event: dict[str, Any]) -> None:
        path = self.root / str(self.workflow["artifact_manifest"][manifest_name])
        append_jsonl(path, event)

    @staticmethod
    def _candidate_scientific_context_refs(candidate: dict[str, Any]) -> list[str]:
        refs: set[str] = set()
        for field in (
            "mechanism_change_ids", "capability_ids", "obligation_ids", "causal_chain_ids",
        ):
            refs.update(str(value) for value in candidate.get(field) or [])
        for item in candidate.get("fatal_assumptions") or []:
            if isinstance(item, dict) and isinstance(item.get("assumption_id"), str):
                refs.add(item["assumption_id"])
        for item in candidate.get("predictions") or []:
            if isinstance(item, dict) and isinstance(item.get("prediction_id"), str):
                refs.add(item["prediction_id"])
        return sorted(refs)

    def _record_reviewed_artifact_history(
        self, state: dict[str, Any], phase: dict[str, Any]
    ) -> None:
        phase_name = str(phase["phase"])
        reviewed = self._resolved_phase_paths(state, phase_name, "reviewed_artifacts")
        if len(reviewed) != 1:
            return
        path = self.root / reviewed[0]
        digest = sha256_file(path)
        if phase.get("history_recorded_for_reviewed_sha256") == digest:
            return
        recorded_at = now()
        if phase_name == "method_design":
            packet = self._method_packet(state, accepted=False)
            cycle_id = str(packet["design_cycle_id"])
            for candidate in packet["candidate_principles"]:
                event = {
                    "schema_version": 1,
                    "event_id": f"principle-{uuid.uuid4().hex}",
                    "event_type": "REVISED" if candidate.get("parent_version") is not None else "PROPOSED",
                    "cycle_id": cycle_id,
                    "principle_id": str(candidate["principle_id"]),
                    "principle_version": str(candidate["principle_version"]),
                    "parent_version": candidate.get("parent_version"),
                    "scientific_context_refs": self._candidate_scientific_context_refs(candidate),
                    "evidence_refs": list(candidate.get("evidence_refs") or []),
                    "reason": str(candidate["status_rationale"]),
                    "recorded_at": recorded_at,
                    "record_refs": [{"path": reviewed[0], "sha256": digest}],
                }
                self._append_method_history_event("method_principles", event)
        elif phase_name == "principle_test_design":
            plan = self._principle_test_plan(state, accepted=False)
            for test in plan["discriminating_tests"]:
                self._append_method_history_event(
                    "method_test_evidence",
                    {
                        "schema_version": 1,
                        "event_id": f"method-test-{uuid.uuid4().hex}",
                        "event_type": "PROPOSED",
                        "cycle_id": str(plan["cycle_id"]),
                        "execution_set_id": str(plan["execution_set_id"]),
                        "test_id": str(test["test_id"]),
                        "targets": deepcopy(test["targets"]),
                        "record_refs": [{"path": reviewed[0], "sha256": digest}],
                        "reason": "minimum selected-Candidate test proposed in reviewed plan",
                        "recorded_at": recorded_at,
                    },
                )
        elif phase_name == "principle_evaluation":
            packet = self._method_packet(state, accepted=True)
            evaluation = json.loads(path.read_text(encoding="utf-8"))
            updates_by_principle = {
                (str(update["principle_id"]), str(update["principle_version"])): update
                for update in evaluation["principle_updates"]
            }
            for update in evaluation["principle_updates"]:
                candidate = next(
                    item
                    for item in packet["candidate_principles"]
                    if str(item["principle_id"]) == str(update["principle_id"])
                    and str(item["principle_version"]) == str(update["principle_version"])
                )
                self._append_method_history_event(
                    "method_principles",
                    {
                        "schema_version": 1,
                        "event_id": f"principle-{uuid.uuid4().hex}",
                        "event_type": "EVIDENCE_UPDATED",
                        "cycle_id": str(evaluation["cycle_id"]),
                        "principle_id": str(update["principle_id"]),
                        "principle_version": str(update["principle_version"]),
                        "parent_version": candidate.get("parent_version"),
                        "scientific_context_refs": self._candidate_scientific_context_refs(candidate),
                        "evidence_refs": list(update.get("evidence_refs") or []),
                        "reason": str(update["rationale"]),
                        "decision": str(update["decision"]),
                        "recorded_at": recorded_at,
                        "record_refs": [{"path": reviewed[0], "sha256": digest}],
                    },
                )
            cycle = state["scientific_core"].get("method_test_cycle") or {}
            for test_id, outcome in (cycle.get("terminal_outcomes") or {}).items():
                test = cycle["tests"][test_id]
                record_refs = [
                    *deepcopy(outcome.get("result_refs") or []),
                    {"path": reviewed[0], "sha256": digest},
                ]
                self._append_method_history_event(
                    "method_test_evidence",
                    {
                        "schema_version": 1,
                        "event_id": f"method-test-{uuid.uuid4().hex}",
                        "event_type": "EVIDENCE_UPDATED",
                        "cycle_id": str(cycle["cycle_id"]),
                        "execution_set_id": str(cycle["execution_set_id"]),
                        "test_id": test_id,
                        "targets": deepcopy(test["targets"]),
                        "record_refs": deepcopy(record_refs),
                        "reason": "Principle evaluation consumed the terminal test outcome",
                        "recorded_at": recorded_at,
                    },
                )
                principle_keys = {
                    (str(target["principle_id"]), str(target["principle_version"]))
                    for target in test["targets"]
                }
                for principle_key in sorted(principle_keys & updates_by_principle.keys()):
                    update = updates_by_principle[principle_key]
                    self._append_method_history_event(
                        "method_test_evidence",
                        {
                            "schema_version": 1,
                            "event_id": f"method-test-{uuid.uuid4().hex}",
                            "event_type": "PRINCIPLE_DECISION_RECORDED",
                            "cycle_id": str(cycle["cycle_id"]),
                            "execution_set_id": str(cycle["execution_set_id"]),
                            "test_id": test_id,
                            "targets": deepcopy(test["targets"]),
                            "principle_id": principle_key[0],
                            "principle_version": principle_key[1],
                            "decision": str(update["decision"]),
                            "evidence_refs": deepcopy(update.get("evidence_refs") or []),
                            "updated_boundary_or_assumption_refs": deepcopy(
                                update.get("updated_boundary_or_assumption_refs") or []
                            ),
                            "record_refs": deepcopy(record_refs),
                            "reason": str(update["rationale"]),
                            "recorded_at": recorded_at,
                        },
                    )
        phase["history_recorded_for_reviewed_sha256"] = digest

    def refresh_current_review_request(self) -> dict[str, Any]:
        """Finalize the live formal request after Main's reviewed artifact is current."""

        with self._store.mutate() as state:
            if state["research_lit"]["current_stage"] != "LANDSCAPE_ACCEPTED":
                raise ControllerError("complete the active incremental literature session before review finalization")
            phase = self._current_core_phase(state)
            spec = self._phase_spec(state, str(phase["phase"]))
            reviewed = self._resolved_phase_paths(state, str(phase["phase"]), "reviewed_artifacts")
            if phase.get("status") != "running" or not spec.get("formal_gate") or not reviewed:
                raise ControllerError("current phase has no running Main artifact review to finalize")
            try:
                main_artifact = run_state._validate_method_main_artifact(
                    str(self.root),
                    state,
                    spec,
                    str(phase["phase"]),
                    current_phase_evidence_ids=self._current_phase_evidence_ids(
                        state, str(phase["phase"])
                    ),
                )
            except ValueError as exc:
                raise ControllerError(str(exc)) from exc
            if phase["phase"] == "method_design":
                view_path = self.root / str(
                    self.workflow["artifact_manifest"]["method_design_view"]
                )
                view_path.parent.mkdir(parents=True, exist_ok=True)
                view_path.write_text(
                    render_method_design_view(main_artifact["packet"]), encoding="utf-8"
                )
            elif phase["phase"] == "principle_test_design":
                view_path = self.root / str(
                    self.workflow["artifact_manifest"]["principle_test_plan_view"]
                )
                view_path.parent.mkdir(parents=True, exist_ok=True)
                view_path.write_text(
                    render_principle_test_plan_view(main_artifact["plan"]), encoding="utf-8"
                )
            self._record_reviewed_artifact_history(state, phase)
            expected = self._phase_review_bindings(state, str(phase["phase"]))
            request = phase.get("review_request")
            static_valid = (
                isinstance(request, dict)
                and request.get("run_id") == self.run_id
                and request.get("phase") == phase["phase"]
                and request.get("gate") == spec.get("gate_id")
                and request.get("required_reviewer_role") == spec.get("reviewer_role")
            )
            if not static_valid:
                raise ControllerError("formal Gate has no current Controller-issued review request")
            if not request.get("reviewed_artifacts_pending") and request.get("artifact_bindings") == expected:
                return dict(request)
            if not request.get("reviewed_artifacts_pending"):
                request = self._new_core_review_request(state, phase, spec)
                phase["review_request"] = request
            if request.get("reviewed_artifacts_pending") != reviewed:
                raise ControllerError("formal review request has invalid pending reviewed artifacts")
            request["artifact_bindings"] = expected
            request.pop("reviewed_artifacts_pending", None)
            request["finalized_at"] = now()
            return dict(request)

    def _initialize_method_test_cycle(self, state: dict[str, Any]) -> dict[str, Any]:
        self._selected_for_testing_candidate(state)
        plan = self._principle_test_plan(state, accepted=True)
        execution = plan["recommended_execution_set"]
        previous_cycle_id = state["scientific_core"].get("last_method_test_cycle_id")
        if previous_cycle_id is not None and str(plan["cycle_id"]) == str(previous_cycle_id):
            raise ControllerError("a new Principle test design round must establish a new test cycle")
        approved_ids = list(execution["test_ids"])
        tests = {
            str(item["test_id"]): deepcopy(item)
            for item in plan["discriminating_tests"]
            if item["test_id"] in set(approved_ids)
        }
        if set(tests) != set(approved_ids):
            raise ControllerError("approved execution set cannot resolve every test from the plan")
        cycle = {
            "cycle_id": str(plan["cycle_id"]),
            "execution_set_id": str(plan["execution_set_id"]),
            "approved_test_ids": approved_ids,
            "estimated_total_cost": plan["estimated_total_cost"],
            "tests": tests,
            "terminal_outcomes": {},
            "handoff_issued": False,
            "evidence_context": None,
            "status": "APPROVED",
            "approved_at": now(),
        }
        state["scientific_core"]["method_test_cycle"] = cycle
        plan_path = str(self.workflow["artifact_manifest"]["principle_test_plan"])
        plan_record = state["scientific_core"]["accepted_artifacts"][plan_path]
        for test_id in approved_ids:
            self._append_method_history_event(
                "method_test_evidence",
                {
                    "schema_version": 1,
                    "event_id": f"method-test-{uuid.uuid4().hex}",
                    "event_type": "EXECUTION_SET_APPROVED",
                    "cycle_id": cycle["cycle_id"],
                    "execution_set_id": cycle["execution_set_id"],
                    "test_id": test_id,
                    "targets": deepcopy(tests[test_id]["targets"]),
                    "record_refs": [{"path": plan_path, "sha256": plan_record["sha256"]}],
                    "reason": "Human approved the complete atomic execution set",
                    "recorded_at": cycle["approved_at"],
                },
            )
        return cycle

    def _require_method_test_window(self, state: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        phase = self._current_core_phase(state)
        if phase["phase"] != "principle_evaluation" or phase["status"] != "pending":
            raise ControllerError("method-test actions require pending principle_evaluation")
        cycle = state["scientific_core"].get("method_test_cycle")
        if not isinstance(cycle, dict) or cycle.get("status") not in {"APPROVED", "EXECUTING", "TERMINAL"}:
            raise ControllerError("no Human-approved method test cycle is active")
        return phase, cycle

    def method_test_handoff(self) -> dict[str, Any]:
        with self._store.mutate() as state:
            _, cycle = self._require_method_test_window(state)
            handoff = {
                "handoff_type": "APPROVED_METHOD_TEST_EXECUTION_SET",
                "run_id": self.run_id,
                "cycle_id": cycle["cycle_id"],
                "execution_set_id": cycle["execution_set_id"],
                "approved_test_ids": list(cycle["approved_test_ids"]),
                "estimated_total_cost": cycle["estimated_total_cost"],
                "tests": [deepcopy(cycle["tests"][test_id]) for test_id in cycle["approved_test_ids"]],
            }
            canonical = json.dumps(handoff, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            handoff["handoff_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            if not cycle.get("handoff_issued"):
                for test_id in cycle["approved_test_ids"]:
                    self._append_method_history_event(
                        "method_test_evidence",
                        {
                            "schema_version": 1,
                            "event_id": f"method-test-{uuid.uuid4().hex}",
                            "event_type": "EXECUTION_HANDED_OFF",
                            "cycle_id": cycle["cycle_id"],
                            "execution_set_id": cycle["execution_set_id"],
                            "test_id": test_id,
                            "targets": deepcopy(cycle["tests"][test_id]["targets"]),
                            "record_refs": [],
                            "reason": "Controller issued the approved execution handoff",
                            "recorded_at": now(),
                        },
                    )
                cycle["handoff_issued"] = True
                cycle["handoff_sha256"] = handoff["handoff_sha256"]
                cycle["status"] = "EXECUTING"
            return handoff

    def _materialize_principle_evidence_context(
        self, state: dict[str, Any]
    ) -> dict[str, Any]:
        core = state["scientific_core"]
        cycle = core.get("method_test_cycle")
        if not isinstance(cycle, dict):
            raise ControllerError("cannot form Evidence Context without an approved test cycle")
        approved = set(cycle["approved_test_ids"])
        terminal = cycle.get("terminal_outcomes") or {}
        if set(terminal) != approved:
            raise ControllerError("cannot form Evidence Context before every approved test is terminal")
        packet = self._method_packet(state, accepted=True)
        selection, selected_candidate = self._selected_for_testing_candidate(state)
        active_principles = [
            {
                "principle_id": str(selection["principle_id"]),
                "principle_version": str(selection["principle_version"]),
            }
        ]
        targets = [
            {"test_id": test_id, **deepcopy(target)}
            for test_id in cycle["approved_test_ids"]
            for target in cycle["tests"][test_id]["targets"]
        ]
        history_evidence: set[str] = set()
        for event in run_state._relevant_scientific_history_events(
            str(self.root), state, packet
        ):
            history_evidence.update(
                value for value in event.get("evidence_refs") or [] if isinstance(value, str)
            )
        result_refs = [
            deepcopy(ref)
            for test_id in cycle["approved_test_ids"]
            for ref in terminal[test_id].get("result_refs") or []
        ]
        current_evidence = set(self._current_phase_evidence_ids(state, "principle_evaluation"))
        current_evidence.update(
            ref["path"] for ref in result_refs if isinstance(ref, dict) and isinstance(ref.get("path"), str)
        )
        unresolved = sorted(
            {
                assumption["assumption_id"]
                for assumption in selected_candidate["fatal_assumptions"]
            }
        )
        context = {
            "schema_version": 1,
            "cycle_id": cycle["cycle_id"],
            "execution_set_id": cycle["execution_set_id"],
            "active_principles": active_principles,
            "test_targets": targets,
            "approved_test_ids": list(cycle["approved_test_ids"]),
            "terminal_outcomes": [
                {
                    "test_id": test_id,
                    "outcome": terminal[test_id]["outcome"],
                    "reason": terminal[test_id].get("reason"),
                }
                for test_id in cycle["approved_test_ids"]
            ],
            "result_refs": result_refs,
            "historical_evidence_refs": sorted(history_evidence),
            "current_evidence_refs": sorted(current_evidence),
            "unresolved_assumption_ids": unresolved,
            "execution_metadata": {
                test_id: deepcopy(terminal[test_id].get("execution_metadata") or {})
                for test_id in cycle["approved_test_ids"]
            },
        }
        return self._register_principle_evidence_context(state, cycle, context)

    def _register_principle_evidence_context(
        self,
        state: dict[str, Any],
        cycle: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        approved = set(cycle["approved_test_ids"])
        terminal = cycle.get("terminal_outcomes") or {}
        self._method_packet(state, accepted=True)
        selection, _ = self._selected_for_testing_candidate(state)
        expected_active_principles = {
            (str(selection["principle_id"]), str(selection["principle_version"]))
        }
        expected_test_targets = [
            {"test_id": test_id, **deepcopy(target)}
            for test_id in cycle["approved_test_ids"]
            for target in cycle["tests"][test_id]["targets"]
        ]
        try:
            validate_principle_evidence_context(
                context,
                contract=self.workflow["artifact_contracts"]["principle_evidence_context"],
                cycle_id=cycle["cycle_id"],
                execution_set_id=cycle["execution_set_id"],
                approved_test_ids=approved,
                terminal_outcomes=terminal,
                expected_active_principles=expected_active_principles,
                expected_test_targets=expected_test_targets,
            )
        except ValidationError as exc:
            raise ControllerError(str(exc)) from exc
        raw_path = str(self.workflow["artifact_manifest"]["principle_evidence_context"])
        path = self.root / raw_path
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            temporary.write_text(json.dumps(context, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            os.replace(temporary, path)
        finally:
            if temporary.exists():
                temporary.unlink()
        record = self._artifact_record(
            raw_path,
            producer_phase="principle_evaluation",
            provenance={
                "controller": "ARISController",
                "run_id": self.run_id,
                "cycle_id": cycle["cycle_id"],
                "execution_set_id": cycle["execution_set_id"],
            },
            upstream_snapshot=self._upstream_snapshot(state, "principle_evaluation"),
        )
        active = self._assert_active_problem_version_current(state)
        record["problem_version_binding"] = {
            "problem_id": active["problem_id"],
            "version": active["version"],
            "contract_sha256": active["contract_sha256"],
            "evidence_capsule_sha256": active["evidence_capsule_sha256"],
        }
        state["scientific_core"]["accepted_artifacts"][raw_path] = record
        cycle["evidence_context"] = {"path": raw_path, "sha256": record["sha256"]}
        cycle["status"] = "TERMINAL"
        return record

    def _assert_principle_evaluation_ready(self, state: dict[str, Any]) -> None:
        _, cycle = self._require_method_test_window(state)
        approved = set(cycle["approved_test_ids"])
        terminal = cycle.get("terminal_outcomes") or {}
        if set(terminal) != approved:
            raise ControllerError("all approved tests must be terminal before principle_evaluation starts")
        context_ref = cycle.get("evidence_context")
        if not isinstance(context_ref, dict):
            raise ControllerError("principle_evaluation requires an active Evidence Context")
        raw_path = str(self.workflow["artifact_manifest"]["principle_evidence_context"])
        record = state["scientific_core"]["accepted_artifacts"].get(raw_path)
        path = self.root / raw_path
        if (
            not isinstance(record, dict)
            or context_ref != {"path": raw_path, "sha256": record.get("sha256")}
            or not path.is_file()
            or sha256_file(path) != record.get("sha256")
        ):
            raise ControllerError("active Evidence Context is missing or stale")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            self._method_packet(state, accepted=True)
            selection, _ = self._selected_for_testing_candidate(state)
            validate_principle_evidence_context(
                payload,
                contract=self.workflow["artifact_contracts"]["principle_evidence_context"],
                cycle_id=cycle["cycle_id"],
                execution_set_id=cycle["execution_set_id"],
                approved_test_ids=approved,
                terminal_outcomes=terminal,
                expected_active_principles={
                    (str(selection["principle_id"]), str(selection["principle_version"]))
                },
                expected_test_targets=[
                    {"test_id": test_id, **deepcopy(target)}
                    for test_id in cycle["approved_test_ids"]
                    for target in cycle["tests"][test_id]["targets"]
                ],
            )
        except (OSError, json.JSONDecodeError, ValidationError) as exc:
            raise ControllerError(f"active Evidence Context is invalid: {exc}") from exc

    def _deactivate_principle_evidence_context(
        self, state: dict[str, Any], *, reason: str
    ) -> None:
        core = state["scientific_core"]
        raw_path = str(self.workflow["artifact_manifest"]["principle_evidence_context"])
        record = (core.get("accepted_artifacts") or {}).pop(raw_path, None)
        path = self.root / raw_path
        if not isinstance(record, dict) and not path.is_file():
            return
        event_id = f"context-{uuid.uuid4().hex}"
        target = self.root / ".aris" / "archive" / self.run_id / event_id / "artifacts" / raw_path
        archive_path: str | None = None
        if path.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(target))
            archive_path = str(target.relative_to(self.root))
        invalidated = deepcopy(record or {})
        invalidated.update(
            {
                "path": raw_path,
                "status": "invalidated",
                "invalidated_at": now(),
                "invalidation": {"reason": reason, "context_event_id": event_id},
                "archive_path": archive_path,
                "archive_status": "archived" if archive_path else "missing_at_invalidation",
            }
        )
        core.setdefault("invalidated_artifacts", []).append(invalidated)
        cycle = core.get("method_test_cycle")
        if isinstance(cycle, dict):
            cycle["evidence_context"] = None
            if reason == "PRINCIPLE_CONVERGED":
                cycle["status"] = "CONVERGED"

    def submit_method_test_result(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._store.mutate() as state:
            _, cycle = self._require_method_test_window(state)
            if not cycle.get("handoff_issued"):
                raise ControllerError("method test result requires the Controller-issued approved execution handoff")
            try:
                result = validate_method_test_result(
                    payload,
                    cycle_id=str(cycle["cycle_id"]),
                    execution_set_id=str(cycle["execution_set_id"]),
                    approved_test_ids=set(cycle["approved_test_ids"]),
                    no_result_reasons=set(
                        self.workflow["artifact_contracts"]["method_test_evidence"]["no_result_reasons"]
                    ),
                    root=self.root,
                )
            except ValidationError as exc:
                raise ControllerError(str(exc)) from exc
            test_id = result["test_id"]
            if test_id in cycle["terminal_outcomes"]:
                raise ControllerError("approved method test already has a terminal outcome")
            recorded = {**deepcopy(result), "recorded_at": now()}
            cycle["terminal_outcomes"][test_id] = recorded
            cycle["status"] = "EXECUTING"
            self._append_method_history_event(
                "method_test_evidence",
                {
                    "schema_version": 1,
                    "event_id": f"method-test-{uuid.uuid4().hex}",
                    "event_type": result["outcome"],
                    "cycle_id": cycle["cycle_id"],
                    "execution_set_id": cycle["execution_set_id"],
                    "test_id": test_id,
                    "targets": deepcopy(cycle["tests"][test_id]["targets"]),
                    "record_refs": deepcopy(result["result_refs"]),
                    "reason": result.get("reason") or "result available",
                    "recorded_at": recorded["recorded_at"],
                },
            )
            if set(cycle["terminal_outcomes"]) == set(cycle["approved_test_ids"]):
                self._materialize_principle_evidence_context(state)
            return deepcopy(cycle)

    def _materialize_selected_principle(
        self,
        state: dict[str, Any],
        phase: dict[str, Any],
        acceptance: dict[str, Any],
    ) -> dict[str, Any]:
        principle_id = str(phase.get("selected_principle_id") or "")
        principle_version = str(phase.get("selected_principle_version") or "")
        if not principle_id or not principle_version:
            raise ControllerError("accepted convergence has no unique selected Principle ID/version")
        selection, _ = self._selected_for_testing_candidate(state)
        if (
            principle_id != str(selection["principle_id"])
            or principle_version != str(selection["principle_version"])
        ):
            raise ControllerError("accepted convergence must name the Human-selected Candidate version")
        packet = self._method_packet(state, accepted=True)
        candidate = next(
            (
                item
                for item in packet["candidate_principles"]
                if str(item["principle_id"]) == principle_id
                and str(item["principle_version"]) == principle_version
                and item["status"] in {"ACTIVE", "REVISED", "WEAKENED"}
            ),
            None,
        )
        if candidate is None:
            raise ControllerError("accepted convergence selected an unreviewed Principle version")
        evaluation_path = str(self.workflow["artifact_manifest"]["principle_evaluation"])
        verdict_path = str(self.workflow["artifact_manifest"]["principle_evaluation_verdict"])
        try:
            evaluation = json.loads((self.root / evaluation_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ControllerError("cannot materialize Selected Principle from the accepted evaluation") from exc
        update = next(
            (
                item
                for item in evaluation["principle_updates"]
                if str(item["principle_id"]) == principle_id
                and str(item["principle_version"]) == principle_version
            ),
            None,
        )
        if update is None:
            raise ControllerError("selected Principle has no reviewed Evidence Update")
        if update["decision"] in {"MERGED", "RETIRED", "REJECTED"}:
            raise ControllerError("accepted convergence selected a non-surviving Principle update")
        selected = {
            "schema_version": 1,
            "principle_id": principle_id,
            "principle_version": principle_version,
            "principle": deepcopy(candidate["principle"]),
            "intervention": deepcopy(candidate["intervention"]),
            "changed_structure": deepcopy(candidate["changed_structure"]),
            "problem_binding": deepcopy(packet["problem_binding"]),
            "root_cause_binding": deepcopy(packet["root_cause_binding"]),
            "causal_chain_ids": deepcopy(candidate["causal_chain_ids"]),
            "mechanism_change_ids": deepcopy(candidate["mechanism_change_ids"]),
            "capability_ids": deepcopy(candidate["capability_ids"]),
            "obligation_ids": deepcopy(candidate["obligation_ids"]),
            "evidence_closure": {
                "evidence_refs": deepcopy(update.get("evidence_refs") or []),
                "evaluation": {
                    "path": evaluation_path,
                    "sha256": sha256_file(self.root / evaluation_path),
                },
                "convergence_verdict": {
                    "path": verdict_path,
                    "sha256": sha256_file(self.root / verdict_path),
                },
            },
            "activation_conditions": deepcopy(candidate["activation_conditions"]),
            "failure_conditions": deepcopy(candidate["failure_conditions"]),
            "applicability_boundaries": {
                "activation_conditions": deepcopy(candidate["activation_conditions"]),
                "failure_conditions": deepcopy(candidate["failure_conditions"]),
                "updated_boundary_or_assumption_refs": deepcopy(
                    update.get("updated_boundary_or_assumption_refs") or []
                ),
            },
            "remaining_uncertainty": deepcopy(evaluation.get("remaining_uncertainties") or []),
        }
        try:
            validate_selected_principle(
                selected,
                contract=self.workflow["artifact_contracts"]["selected_principle"],
                expected_principle_id=principle_id,
                expected_principle_version=principle_version,
                packet=packet,
            )
        except ValidationError as exc:
            raise ControllerError(str(exc)) from exc
        raw_path = str(self.workflow["artifact_manifest"]["selected_principle"])
        path = self.root / raw_path
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            temporary.write_text(
                yaml.safe_dump(selected, sort_keys=False, allow_unicode=True),
                encoding="utf-8",
            )
            os.replace(temporary, path)
        finally:
            if temporary.exists():
                temporary.unlink()
        record = self._artifact_record(
            raw_path,
            producer_phase="principle_evaluation",
            provenance={
                "controller": "ARISController",
                "run_id": self.run_id,
                "accepted_convergence_verdict_id": phase["verdict_id"],
            },
            upstream_snapshot=self._upstream_snapshot(state, "principle_evaluation"),
        )
        active = self._assert_active_problem_version_current(state)
        record["problem_version_binding"] = {
            "problem_id": active["problem_id"],
            "version": active["version"],
            "contract_sha256": active["contract_sha256"],
            "evidence_capsule_sha256": active["evidence_capsule_sha256"],
        }
        record["acceptance"] = deepcopy(acceptance)
        state["scientific_core"]["accepted_artifacts"][raw_path] = record
        if phase.get("acceptance_artifacts") is None:
            phase["acceptance_artifacts"] = {}
        phase["acceptance_artifacts"][raw_path] = record
        for event_type in ("CONVERGED", "SELECTED"):
            self._append_method_history_event(
                "method_principles",
                {
                    "schema_version": 1,
                    "event_id": f"principle-{uuid.uuid4().hex}",
                    "event_type": event_type,
                    "cycle_id": str(evaluation["cycle_id"]),
                    "principle_id": principle_id,
                    "principle_version": principle_version,
                    "parent_version": candidate.get("parent_version"),
                    "scientific_context_refs": self._candidate_scientific_context_refs(candidate),
                    "evidence_refs": deepcopy(update.get("evidence_refs") or []),
                    "reason": "independent convergence verdict accepted by the Controller",
                    "recorded_at": acceptance["accepted_at"],
                    "record_refs": [{"path": raw_path, "sha256": record["sha256"]}],
                },
            )
        return record

    def _materialize_root_cause_verdict(self, state: dict, phase: dict, spec: dict) -> None:
        """Persist the reviewer-owned root-cause verdict through the Controller.

        The independent reviewer attests one complete payload outside the project.
        Main has no write path for its semantic content; this Controller-only
        materialization validates the live request/bindings and atomically writes
        the canonical artifact before normal output registration.
        """

        request = self._assert_core_review_request_current(
            state, phase, spec, allow_pending_reviewed_artifacts=True
        )
        try:
            attestation = reviews.load_review_attestation(
                self.root,
                self.run_id,
                role=str(request["required_reviewer_role"]),
                request_id=str(request["id"]),
                artifact_bindings=dict(request["artifact_bindings"]),
            )
        except ValueError as exc:
            raise ControllerError(str(exc)) from exc
        payload = attestation.get("verdict_payload")
        if not isinstance(payload, dict):
            raise ControllerError("root-cause reviewer attestation lacks the canonical verdict payload")
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        if hashlib.sha256(canonical.encode("utf-8")).hexdigest() != attestation.get("payload_sha256"):
            raise ControllerError("root-cause reviewer verdict payload fails its attested hash")
        if (
            payload.get("review_request_id") != request["id"]
            or payload.get("reviewed_artifact_hashes") != request["artifact_bindings"]
            or payload.get("run_id") != self.run_id
            or payload.get("reviewer") != attestation.get("reviewer")
            or payload.get("verdict_id") != attestation.get("verdict_id")
            or payload.get("decision") != attestation.get("decision")
        ):
            raise ControllerError("root-cause reviewer verdict does not match its live attestation")
        output_paths = self._resolved_phase_paths(state, phase["phase"], "produced_artifacts")
        if len(output_paths) != 1:
            raise ControllerError("root-cause Gate must declare exactly one canonical verdict artifact")
        target = self.root / output_paths[0]
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
        try:
            temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            os.replace(temporary, target)
        finally:
            if temporary.exists():
                temporary.unlink()

    def _assert_core_review_request_current(
        self,
        state: dict,
        phase: dict,
        spec: dict,
        *,
        allow_pending_reviewed_artifacts: bool = False,
    ) -> dict[str, Any]:
        request = phase.get("review_request")
        if (
            not isinstance(request, dict)
            or request.get("run_id") != self.run_id
            or request.get("phase") != phase["phase"]
            or request.get("gate") != spec.get("gate_id")
            or request.get("required_reviewer_role") != spec.get("reviewer_role")
            or request.get("accepted_verdicts") != spec.get("accepted_verdicts")
            or request.get("allowed_review_verdicts")
            != [*list(spec.get("accepted_verdicts") or []), *list((spec.get("return_targets") or {}).keys())]
            or request.get("issued_by") != "ARISController"
        ):
            raise ControllerError("formal Gate has no current Controller-issued review request")
        pending = self._resolved_phase_paths(state, phase["phase"], "reviewed_artifacts")
        if pending and request.get("reviewed_artifacts_pending") == pending:
            if not allow_pending_reviewed_artifacts:
                raise ControllerError("formal review request is not yet bound to its reviewed artifact")
            expected_bindings = self._phase_input_bindings(state, phase["phase"])
        else:
            if request.get("reviewed_artifacts_pending"):
                raise ControllerError("formal review request has invalid pending reviewed artifacts")
            expected_bindings = self._phase_review_bindings(state, phase["phase"])
        if request.get("artifact_bindings") != expected_bindings:
            raise ControllerError("formal review request is stale or its reviewed artifact changed")
        return request

    def _upstream_snapshot(self, state: dict, phase_name: str) -> dict[str, str]:
        snapshot: dict[str, str] = {}
        for raw_path in self._resolved_phase_paths(state, phase_name, "required_inputs"):
            record = self._registered_artifact_by_path(state, raw_path)
            if isinstance(record, dict) and record.get("sha256"):
                snapshot[str(raw_path)] = str(record["sha256"])
        snapshot.update(self._incremental_evidence_bindings(state, phase_name))
        return snapshot

    def _register_phase_outputs(
        self,
        state: dict,
        phase_name: str,
        *,
        provenance: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        spec = self._phase_spec(state, phase_name)
        try:
            validation_result = run_state._assert_outputs(
                str(self.root),
                state,
                spec,
                phase_name,
                current_phase_evidence_ids=(
                    self._current_phase_evidence_ids(state, phase_name)
                    if phase_name in {
                        "problem_generation", "root_cause_analysis",
                        "method_design", "principle_evaluation",
                    }
                    else None
                ),
            )
        except ValueError as exc:
            raise ControllerError(str(exc)) from exc
        if validation_result is not None:
            phase = run_state._find_phase(state, phase_name)
            for key in (
                "coverage_status", "validated_artifacts", "analysis_id",
                "problem_contract_sha256", "evidence_capsule_sha256",
                "gate_verdict", "verdict_id", "reviewer",
                "reviewed_analysis_sha256", "review_request_id",
                "reviewed_artifact_hashes",
                "candidate_ids", "survivor_ids",
                "diagnostic_pilot_artifacts",
                "cycle_id", "execution_set_id", "test_ids",
                "selected_principle_id", "selected_principle_version",
            ):
                if key in validation_result:
                    phase[key] = validation_result[key]
        core = state["scientific_core"]
        upstream = self._upstream_snapshot(state, phase_name)
        registered: dict[str, dict[str, Any]] = {}
        for raw_path in self._resolved_phase_paths(state, phase_name, "produced_artifacts"):
            record = self._artifact_record(
                raw_path,
                producer_phase=phase_name,
                provenance=provenance,
                upstream_snapshot=upstream,
            )
            if phase_name in {
                "method_design",
                "principle_test_human_approval",
                "principle_evaluation",
                "method_refinement",
                "final_method_novelty_gate",
                "final_method_human_acceptance",
            }:
                active = self._assert_active_problem_version_current(state)
                record["problem_version_binding"] = {
                    "problem_id": active["problem_id"],
                    "version": active["version"],
                    "contract_sha256": active["contract_sha256"],
                    "evidence_capsule_sha256": active["evidence_capsule_sha256"],
                }
            core["accepted_artifacts"][str(raw_path)] = record
            registered[str(raw_path)] = record
        if phase_name == "root_cause_analysis":
            active = self._assert_active_problem_version_current(state)
            for source in (validation_result or {}).get("diagnostic_pilot_artifacts") or []:
                if not isinstance(source, dict):
                    raise ControllerError("root-cause diagnostic-pilot validation result is invalid")
                raw_path = str(source["path"])
                if self._registered_artifact_by_path(state, raw_path) is not None:
                    raise ControllerError(
                        f"root-cause diagnostic pilot is already registered: {raw_path}"
                    )
                record = self._artifact_record(
                    raw_path,
                    producer_phase=phase_name,
                    provenance={**provenance, "diagnostic_pilot_artifact_id": source["artifact_id"]},
                    upstream_snapshot=upstream,
                )
                record["artifact_id"] = source["artifact_id"]
                record["evidence_source_type"] = source["evidence_source_type"]
                record["problem_version_binding"] = {
                    "problem_id": active["problem_id"],
                    "version": active["version"],
                    "contract_sha256": active["contract_sha256"],
                    "evidence_capsule_sha256": active["evidence_capsule_sha256"],
                }
                core["accepted_artifacts"][raw_path] = record
                registered[raw_path] = record
        return registered

    def _normalize_return_lesson(self, lesson: dict[str, Any] | None) -> dict[str, Any] | None:
        """Validate the optional, reusable lesson extracted from a return.

        Lessons are deliberately a small index of reusable checks, not a second
        archive or a substitute for the invalidated artifacts themselves.
        """

        if lesson is None:
            return None
        if not isinstance(lesson, dict):
            raise ControllerError("return lesson must be a JSON object")
        required = (
            "failure_phenomenon",
            "wrong_assumption_or_reason",
            "evidence_refs",
            "future_check",
        )
        missing = [name for name in required if name not in lesson]
        if missing:
            raise ControllerError(
                "return lesson is missing required fields: " + ", ".join(missing)
            )
        normalized: dict[str, Any] = {}
        for name in ("failure_phenomenon", "wrong_assumption_or_reason", "future_check"):
            value = lesson.get(name)
            if not isinstance(value, str) or not value.strip():
                raise ControllerError(f"return lesson {name} must be a non-empty string")
            normalized[name] = value.strip()
        evidence_refs = lesson.get("evidence_refs")
        if (
            not isinstance(evidence_refs, list)
            or not evidence_refs
            or any(not isinstance(value, str) or not value.strip() for value in evidence_refs)
        ):
            raise ControllerError("return lesson evidence_refs must be a non-empty string list")
        normalized["evidence_refs"] = [value.strip() for value in evidence_refs]
        return normalized

    def _archive_invalidated_outputs(
        self,
        state: dict,
        phase_names: list[str],
        *,
        return_event_id: str,
        invalidated_at: str,
        invalidation: dict[str, Any],
    ) -> tuple[str, list[dict[str, Any]]]:
        """Move controller-owned outputs out of active paths for a phase range.

        This is intentionally an ordered-phase rule rather than a dependency
        graph: a declared return target invalidates that target and every
        completed controller phase through the returning Gate.
        """

        core = state["scientific_core"]
        reset_names = set(phase_names)
        archive_root = self.root / ".aris" / "archive" / self.run_id / return_event_id
        archive_artifacts = archive_root / "artifacts"
        records_by_path: dict[str, dict[str, Any]] = {
            raw_path: record
            for raw_path, record in (core.get("accepted_artifacts") or {}).items()
            if isinstance(record, dict) and record.get("producer_phase") in reset_names
        }
        for phase_name in phase_names:
            phase = run_state._find_phase(state, phase_name)
            for field in ("handoff_artifacts", "acceptance_artifacts"):
                for raw_path, record in (phase.get(field) or {}).items():
                    if isinstance(record, dict):
                        records_by_path.setdefault(str(raw_path), record)

        output_paths: list[str] = []
        for phase_name in phase_names:
            for raw_path in self._resolved_phase_paths(state, phase_name, "produced_artifacts"):
                if raw_path not in output_paths:
                    output_paths.append(raw_path)
            for raw_path in self._resolved_phase_paths(state, phase_name, "acceptance_artifacts"):
                if raw_path not in output_paths:
                    output_paths.append(raw_path)
        if "principle_evaluation" in reset_names:
            context_path = str(
                self.workflow.get("artifact_manifest", {}).get("principle_evidence_context") or ""
            )
            context_file = self.root / context_path if context_path else None
            if (
                context_path
                and context_path not in output_paths
                and (
                    context_path in (core.get("accepted_artifacts") or {})
                    or (context_file is not None and context_file.is_file())
                )
            ):
                output_paths.append(context_path)

        moves: list[tuple[Path, Path, str]] = []
        for raw_path in output_paths:
            source = Path(raw_path)
            if not source.is_absolute():
                source = self.root / source
            source = source.resolve()
            try:
                relative = source.relative_to(self.root)
            except ValueError as exc:
                raise ControllerError(
                    f"cannot archive controller artifact outside project root: {raw_path}"
                ) from exc
            if source.exists() and not source.is_file():
                raise ControllerError(f"controller artifact is not a file: {raw_path}")
            if source.is_file():
                target = archive_artifacts / relative
                if target.exists():
                    raise ControllerError(f"archive target already exists: {target}")
                moves.append((source, target, str(relative)))

        moved: list[tuple[Path, Path]] = []
        try:
            for source, target, _ in moves:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(source), str(target))
                moved.append((source, target))
        except OSError as exc:
            for source, target in reversed(moved):
                source.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(target), str(source))
            raise ControllerError("could not archive invalidated artifacts") from exc

        archive_paths = {relative: target for _, target, relative in moves}
        invalidated: list[dict[str, Any]] = []
        for raw_path in output_paths:
            source = Path(raw_path)
            if not source.is_absolute():
                source = self.root / source
            source = source.resolve()
            relative = str(source.relative_to(self.root))
            record = deepcopy(records_by_path.get(raw_path) or {})
            record.update(
                {
                    "path": relative,
                    "status": "invalidated",
                    "invalidated_at": invalidated_at,
                    "invalidation": dict(invalidation),
                    "archive_path": (
                        str(archive_paths[relative].relative_to(self.root))
                        if relative in archive_paths
                        else None
                    ),
                    "archive_status": (
                        "archived" if relative in archive_paths else "missing_at_invalidation"
                    ),
                }
            )
            invalidated.append(record)
        return str(archive_root.relative_to(self.root)), invalidated

    def _append_return_lesson(
        self,
        lesson: dict[str, Any],
        *,
        return_event_id: str,
        invalidated_at: str,
        invalidation: dict[str, Any],
    ) -> dict[str, Any]:
        lesson_id = f"LESSON-{uuid.uuid4().hex[:12]}"
        path = self.root / "LESSONS_LEARNED.md"
        if not path.exists():
            path.write_text(
                "# Lessons learned\n\n"
                "Reusable return-path checks recorded by ARIS. These are planning "
                "constraints, not formal evidence or workflow handoffs.\n",
                encoding="utf-8",
            )
        entry = (
            f"\n## {lesson_id}\n\n"
            f"- Recorded: {invalidated_at}\n"
            f"- Return event: `{return_event_id}`\n"
            f"- Failure phenomenon: {lesson['failure_phenomenon']}\n"
            f"- Wrong assumption / reason: {lesson['wrong_assumption_or_reason']}\n"
            "- Evidence references:\n"
            + "".join(f"  - {reference}\n" for reference in lesson["evidence_refs"])
            + f"- Future avoidance / check: {lesson['future_check']}\n"
        )
        with path.open("a", encoding="utf-8") as handle:
            handle.write(entry)
        return {
            "lesson_id": lesson_id,
            "path": str(path.relative_to(self.root)),
            "sha256": sha256_file(path),
            "recorded_at": invalidated_at,
            "return_event_id": return_event_id,
            "invalidation": dict(invalidation),
            **lesson,
        }

    def _build_landscape_handoff(
        self, state: dict, approval_receipt: dict[str, Any]
    ) -> dict[str, Any]:
        research = state["research_lit"]
        artifacts: dict[str, dict[str, Any]] = {}
        landscape_paths = self._resolved_phase_paths(
            state, "landscape", "produced_artifacts"
        )
        manifest_names = {
            str(raw_path): name
            for name, raw_path in self.workflow["artifact_manifest"].items()
        }
        for raw_path in landscape_paths:
            name = manifest_names.get(str(raw_path), str(raw_path))
            record = self._artifact_record(
                str(raw_path),
                producer_phase="landscape",
                provenance={
                    "controller": "ARISController",
                    "run_id": self.run_id,
                    "scope_approval_request_id": approval_receipt.get("request_id"),
                    "accepted_registry_record": dict(
                        (research.get("accepted_artifacts") or {}).get(name) or {}
                    ),
                },
                upstream_snapshot={},
            )
            artifacts[str(raw_path)] = record
        return {
            "run_id": self.run_id,
            "created_at": now(),
            "scope_approval": dict(approval_receipt),
            "coverage_status": run_state._find_phase(state, "landscape").get(
                "coverage_status"
            ),
            "artifacts": artifacts,
        }

    def _activate_scientific_core(
        self, state: dict, approval_receipt: dict[str, Any]
    ) -> None:
        core = state["scientific_core"]
        first = self.workflow["scientific_core"]["phases"][0]
        core["status"] = "ACTIVE"
        core["current_phase"] = first
        core["landscape_handoff"] = self._build_landscape_handoff(
            state, approval_receipt
        )
        core["approval_request"] = None
        core["transition_log"].append(
            {
                "timestamp": now(),
                "from": "scope_human_approval",
                "to": first,
                "reason": "scope_human_accepted",
            }
        )

    def _advance_scientific_core(self, state: dict, *, reason: str) -> None:
        core = state["scientific_core"]
        current = str(core["current_phase"])
        phases = list(self.workflow["scientific_core"]["phases"])
        index = phases.index(current)
        if index + 1 == len(phases):
            final_phase = run_state._find_phase(state, current)
            core["status"] = "METHOD_CONFIRMED_AWAITING_USER_VALIDATION"
            core["current_phase"] = None
            core["approval_request"] = None
            core["validation_entry"] = {
                "status": "AWAITING_USER_INITIATION",
                "entry_policy": "human_initiated_only",
                "method_confirmation": dict(final_phase.get("human_decision") or {}),
                "accepted_method_artifacts": {
                    path: dict(record)
                    for path, record in core["accepted_artifacts"].items()
                    if record.get("producer_phase")
                    in {"method_refinement", "final_method_novelty_gate", current}
                },
                "created_at": now(),
            }
            core["transition_log"].append(
                {
                    "timestamp": now(),
                    "from": current,
                    "to": "METHOD_CONFIRMED_AWAITING_USER_VALIDATION",
                    "reason": reason,
                }
            )
            return
        next_phase = phases[index + 1]
        core["current_phase"] = next_phase
        core["transition_log"].append(
            {"timestamp": now(), "from": current, "to": next_phase, "reason": reason}
        )
        spec = self._phase_spec(state, next_phase)
        if spec.get("human_checkpoint"):
            core["approval_request"] = {
                "id": uuid.uuid4().hex,
                "gate": spec["gate_id"],
                "phase": next_phase,
                "requires_selection": bool(spec.get("requires_selection")),
                "artifact_bindings": self._phase_input_bindings(state, next_phase),
                "issued_by": "ARISController",
                "created_at": now(),
            }
        else:
            core["approval_request"] = None

    def start_current_phase(self) -> dict:
        with self._store.mutate() as state:
            if state["research_lit"]["current_stage"] != "LANDSCAPE_ACCEPTED":
                raise ControllerError("complete the active incremental literature session before starting a core phase")
            phase = self._current_core_phase(state)
            spec = self._phase_spec(state, phase["phase"])
            if spec.get("human_checkpoint"):
                raise ControllerError("human checkpoint cannot be started by an agent")
            if phase["status"] != "pending":
                raise ControllerError(
                    f"phase {phase['phase']} must be pending before start; current={phase['status']}"
                )
            self._assert_phase_inputs_current(state, phase["phase"])
            if phase["phase"] == "principle_evaluation":
                self._assert_principle_evaluation_ready(state)
            if spec.get("formal_gate"):
                phase["review_request"] = self._new_core_review_request(state, phase, spec)
            phase["status"] = "running"
            phase["updated"] = now()
            return state

    def complete_current_phase(self) -> dict:
        with self._store.mutate() as state:
            phase = self._current_core_phase(state)
            spec = self._phase_spec(state, phase["phase"])
            if spec.get("human_checkpoint"):
                raise ControllerError("human checkpoint completes only through human approval")
            if phase["status"] != "running":
                raise ControllerError(
                    f"phase {phase['phase']} must be running before completion; current={phase['status']}"
                )
            self._assert_phase_inputs_current(state, phase["phase"])
            if spec.get("formal_gate"):
                self._assert_core_review_request_current(
                    state,
                    phase,
                    spec,
                )
                if phase["phase"] == "root_cause_gate":
                    self._materialize_root_cause_verdict(state, phase, spec)
            registered = self._register_phase_outputs(
                state,
                phase["phase"],
                provenance={
                    "controller": "ARISController",
                    "run_id": self.run_id,
                    "executor_model": state.get("executor_model"),
                },
            )
            phase["status"] = "done"
            phase["artifact"] = next(iter(registered), None)
            phase["handoff_artifacts"] = registered
            if spec.get("formal_gate"):
                try:
                    validation_result = run_state._assert_outputs(
                        str(self.root), state, spec, phase["phase"]
                    )
                except ValueError as exc:
                    raise ControllerError(str(exc)) from exc
                phase["return_guidance"] = (
                    validation_result.get("return_guidance")
                    if validation_result is not None
                    else None
                )
                if validation_result is not None:
                    for key in (
                        "coverage_status", "validated_artifacts", "analysis_id",
                        "problem_contract_sha256", "evidence_capsule_sha256",
                        "gate_verdict", "verdict_id", "reviewer",
                        "reviewed_analysis_sha256", "review_request_id",
                        "reviewed_artifact_hashes",
                        "candidate_ids", "survivor_ids", "return_guidance",
                        "design_cycle_id", "cycle_id", "execution_set_id", "test_ids",
                        "selected_principle_id", "selected_principle_version",
                    ):
                        if key in validation_result:
                            phase[key] = validation_result[key]
            phase["updated"] = now()
            if not spec.get("formal_gate"):
                self._advance_scientific_core(state, reason="non_gate_phase_completed")
            return state

    def accept_current_phase(self, verdict_id: str, reviewer: str) -> dict:
        if not verdict_id or not reviewer:
            raise ControllerError("formal phase acceptance requires verdict_id and reviewer")
        with self._store.mutate() as state:
            phase = self._current_core_phase(state)
            spec = self._phase_spec(state, phase["phase"])
            if not spec.get("formal_gate") or spec.get("human_checkpoint"):
                raise ControllerError("current phase is not a reviewer-owned formal Gate")
            if phase["status"] != "done":
                raise ControllerError(
                    f"phase {phase['phase']} must be done before acceptance; current={phase['status']}"
                )
            self._assert_phase_inputs_current(state, phase["phase"])
            request = self._assert_core_review_request_current(state, phase, spec)
            try:
                run_state._assert_acceptance_matches_gate(
                    str(self.root), state, spec, phase["phase"], verdict_id, reviewer
                )
            except ValueError as exc:
                raise ControllerError(str(exc)) from exc
            decision = str((run_state._assert_outputs(
                str(self.root), state, spec, phase["phase"]
            ) or {}).get("gate_verdict") or "")
            if not decision:
                raise ControllerError("formal Gate has no validated verdict artifact")
            if decision not in request["accepted_verdicts"]:
                raise ControllerError("review verdict is not allowed for this formal Gate")
            result = run_state._assert_outputs(str(self.root), state, spec, phase["phase"]) or {}
            self._assert_candidate_verdict_attested(state, phase, request, result)
            review_attestation = self._consume_review_attestation(
                role=str(request["required_reviewer_role"]),
                request_id=str(request["id"]),
                reviewer=reviewer,
                verdict_id=verdict_id,
                decision=decision,
                artifact_bindings=dict(request["artifact_bindings"]),
            )
            for record in (phase.get("handoff_artifacts") or {}).values():
                path = Path(str(record.get("path") or ""))
                if not path.is_absolute():
                    path = self.root / path
                if not path.is_file() or sha256_file(path) != record.get("sha256"):
                    raise ControllerError("formal Gate output changed after completion")
            reviewer_family = model_family(reviewer)
            executor_family = str(state.get("executor_family") or "")
            review_independence = (
                "deterministic"
                if reviewer_family == "deterministic"
                else "independent-context"
                if reviewer_family == executor_family
                else "cross-family"
            )
            accepted_at = now()
            acceptance = {
                "status": "accepted",
                "verdict_id": verdict_id,
                "reviewer": reviewer,
                "reviewer_family": reviewer_family,
                "review_independence": review_independence,
                "accepted_at": accepted_at,
                "review_request_id": request["id"],
                "reviewer_agent_id": review_attestation["agent_id"],
                "reviewed_artifact_bindings": dict(request["artifact_bindings"]),
            }
            core = state["scientific_core"]
            for raw_path, record in (phase.get("handoff_artifacts") or {}).items():
                record["acceptance"] = dict(acceptance)
                accepted_record = core["accepted_artifacts"].get(raw_path)
                if not isinstance(accepted_record, dict):
                    raise ControllerError(
                        f"formal Gate output is not registered: {raw_path}"
                    )
                accepted_record["acceptance"] = dict(acceptance)
            if phase["phase"] == "principle_evaluation":
                self._materialize_selected_principle(state, phase, acceptance)
                selection = core.get("selected_for_testing")
                if isinstance(selection, dict):
                    selection["status"] = "CONVERGED"
                    selection["converged_at"] = accepted_at
                self._deactivate_principle_evidence_context(
                    state, reason="PRINCIPLE_CONVERGED"
                )
            phase.update(
                {
                    "status": "accepted",
                    "verdict_id": verdict_id,
                    "reviewer": reviewer,
                    "reviewer_family": reviewer_family,
                    "review_independence": review_independence,
                    "acceptance_status": "accepted",
                    "review_request": None,
                    "updated": accepted_at,
                }
            )
            self._advance_scientific_core(state, reason="formal_gate_accepted")
            return state

    def _return_to_phase(
        self,
        state: dict[str, Any],
        *,
        from_phase: str,
        target: str,
        decision: str,
        reason: str,
        provenance: dict[str, Any],
        lesson: dict[str, Any] | None = None,
    ) -> None:
        """Reuse the canonical archive/invalidation return path for a fixed target."""

        core = state["scientific_core"]
        phases = list(self.workflow["scientific_core"]["phases"])
        if from_phase not in phases or target not in phases:
            raise ControllerError("return source and target must be declared canonical phases")
        target_index = phases.index(target)
        from_index = phases.index(from_phase)
        if target_index > from_index:
            raise ControllerError("return target cannot be downstream of its source phase")
        reset_phases = phases[target_index : from_index + 1]
        reset_names = set(reset_phases)
        rebuild_evidence_context = (
            decision == "REVISE_EVALUATION"
            and from_phase == "principle_evaluation"
            and target == "principle_evaluation"
            and isinstance(core.get("method_test_cycle"), dict)
        )
        rebuilt_context_payload: dict[str, Any] | None = None
        if rebuild_evidence_context:
            context_path = self.root / str(
                self.workflow["artifact_manifest"]["principle_evidence_context"]
            )
            try:
                rebuilt_context_payload = json.loads(context_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ControllerError("REVISE_EVALUATION requires the current Evidence Context") from exc
        invalidated_at = now()
        return_event_id = f"return-{uuid.uuid4().hex}"
        invalidation = {
            "return_event_id": return_event_id,
            "from_phase": from_phase,
            "return_target": target,
            "decision": decision,
            **provenance,
        }
        self._backfill_current_evidence_anchors(state, reset_phases)
        if target == "problem_generation" and core.get("active_problem_version") is not None:
            self._begin_problem_revision(
                state,
                reason=f"{decision}: {provenance.get('verdict_id') or provenance.get('validation_result_id')}",
                source=reason,
                return_event_id=return_event_id,
                allow_problem_replacement=True,
            )
        archive_root, invalidated_artifacts = self._archive_invalidated_outputs(
            state,
            reset_phases,
            return_event_id=return_event_id,
            invalidated_at=invalidated_at,
            invalidation=invalidation,
        )
        core["accepted_artifacts"] = {
            path: record
            for path, record in core["accepted_artifacts"].items()
            if record.get("producer_phase") not in reset_names
        }
        core.setdefault("invalidated_artifacts", []).extend(invalidated_artifacts)
        return_record = {
            "id": return_event_id,
            "at": invalidated_at,
            "reason": reason,
            "archive_root": archive_root,
            "invalidated_phases": list(reset_phases),
            "invalidated_artifact_paths": [record["path"] for record in invalidated_artifacts],
            **invalidation,
        }
        if lesson is not None:
            lesson_record = self._append_return_lesson(
                lesson,
                return_event_id=return_event_id,
                invalidated_at=invalidated_at,
                invalidation=invalidation,
            )
            core.setdefault("lessons", []).append(lesson_record)
            return_record["lesson_id"] = lesson_record["lesson_id"]
        core.setdefault("return_history", []).append(return_record)
        clear_fields = (
            "artifact", "verdict_id", "reviewer", "reviewer_family",
            "review_independence", "acceptance_status", "human_decision",
            "handoff_artifacts", "acceptance_artifacts", "validated_artifacts", "analysis_id",
            "problem_contract_sha256", "evidence_capsule_sha256",
            "gate_verdict", "reviewed_analysis_sha256", "review_request",
            "return_guidance", "history_recorded_for_reviewed_sha256",
        )
        for name in reset_names:
            item = run_state._find_phase(state, name)
            item["status"] = "pending"
            for field in clear_fields:
                item[field] = None
            item["updated"] = now()
        returning_from_validation = core.get("status") == "METHOD_CONFIRMED_AWAITING_USER_VALIDATION"
        core["status"] = "ACTIVE"
        core["current_phase"] = target
        core["approval_request"] = None
        core["problem_revision_request"] = None
        if "method_design" in reset_names:
            prior_cycle = core.get("method_test_cycle")
            if isinstance(prior_cycle, dict) and prior_cycle.get("cycle_id"):
                core["last_method_test_cycle_id"] = prior_cycle["cycle_id"]
            core["method_test_cycle"] = None
            core["selected_for_testing"] = None
        elif target == "principle_test_design":
            prior_cycle = core.get("method_test_cycle")
            if isinstance(prior_cycle, dict) and prior_cycle.get("cycle_id"):
                core["last_method_test_cycle_id"] = prior_cycle["cycle_id"]
            core["method_test_cycle"] = None
        elif "principle_evaluation" in reset_names:
            cycle = core.get("method_test_cycle")
            if isinstance(cycle, dict):
                cycle["evidence_context"] = None
        if returning_from_validation:
            core["validation_entry"] = None
        if rebuild_evidence_context:
            assert rebuilt_context_payload is not None
            cycle = core.get("method_test_cycle")
            assert isinstance(cycle, dict)
            self._register_principle_evidence_context(
                state, cycle, rebuilt_context_payload
            )
        target_spec = self._phase_spec(state, target)
        if target_spec.get("human_checkpoint"):
            core["approval_request"] = {
                "id": uuid.uuid4().hex,
                "gate": target_spec["gate_id"],
                "phase": target,
                "requires_selection": bool(target_spec.get("requires_selection")),
                "artifact_bindings": self._phase_input_bindings(state, target),
                "issued_by": "ARISController",
                "created_at": now(),
            }
        core["transition_log"].append(
            {
                "timestamp": invalidated_at,
                "from": from_phase,
                "to": target,
                "reason": reason,
                "return_event_id": return_event_id,
                "archive_root": archive_root,
                **provenance,
                "decision": decision,
            }
        )

    def return_current_phase(
        self,
        verdict_id: str,
        reviewer: str,
        *,
        lesson: dict[str, Any] | None = None,
    ) -> dict:
        """Apply a declared non-accepting Gate verdict and reopen its return target."""
        if not verdict_id or not reviewer:
            raise ControllerError("phase return requires verdict_id and reviewer")
        normalized_lesson = self._normalize_return_lesson(lesson)
        with self._store.mutate() as state:
            phase = self._current_core_phase(state)
            spec = self._phase_spec(state, phase["phase"])
            targets = spec.get("return_targets") or {}
            if not spec.get("formal_gate") or not targets:
                raise ControllerError("current phase has no declared verdict return path")
            if phase["status"] != "done":
                raise ControllerError(
                    f"phase {phase['phase']} must be done before return; current={phase['status']}"
                )
            self._assert_phase_inputs_current(state, phase["phase"])
            try:
                result = run_state._assert_outputs(
                    str(self.root), state, spec, phase["phase"]
                ) or {}
            except ValueError as exc:
                raise ControllerError(str(exc)) from exc
            decision = result.get("gate_verdict")
            target = targets.get(decision)
            if not target:
                raise ControllerError(
                    f"verdict {decision!r} has no declared return target for phase {phase['phase']!r}"
                )
            if result.get("verdict_id") != verdict_id or result.get("reviewer") != reviewer:
                raise ControllerError(
                    "phase return provenance must match the validated verdict artifact"
                )
            request = self._assert_core_review_request_current(state, phase, spec)
            if decision not in request.get("allowed_review_verdicts", []):
                raise ControllerError("review verdict is not allowed for this formal Gate")
            self._assert_candidate_verdict_attested(state, phase, request, result)
            self._consume_review_attestation(
                role=str(request["required_reviewer_role"]),
                request_id=str(request["id"]),
                reviewer=reviewer,
                verdict_id=verdict_id,
                decision=str(decision),
                artifact_bindings=dict(request["artifact_bindings"]),
            )
            verdict_records = phase.get("handoff_artifacts") or {}
            verdict_hashes = {
                path: record.get("sha256")
                for path, record in verdict_records.items()
                if isinstance(record, dict)
            }
            if decision == "CANDIDATE_REJECTED" and phase["phase"] == "principle_evaluation":
                selection, candidate = self._selected_for_testing_candidate(state)
                evaluation_path = str(self.workflow["artifact_manifest"]["principle_evaluation"])
                evaluation = json.loads((self.root / evaluation_path).read_text(encoding="utf-8"))
                update = next(
                    item for item in evaluation["principle_updates"]
                    if str(item["principle_id"]) == str(selection["principle_id"])
                    and str(item["principle_version"]) == str(selection["principle_version"])
                )
                if update["decision"] != "REJECTED":
                    raise ControllerError(
                        "CANDIDATE_REJECTED requires the reviewed evaluation to reject the Human-selected Candidate"
                    )
                self._append_method_history_event(
                    "method_principles",
                    {
                        "schema_version": 1,
                        "event_id": f"principle-{uuid.uuid4().hex}",
                        "event_type": "REJECTED",
                        "cycle_id": str(evaluation["cycle_id"]),
                        "principle_id": str(selection["principle_id"]),
                        "principle_version": str(selection["principle_version"]),
                        "parent_version": candidate.get("parent_version"),
                        "scientific_context_refs": self._candidate_scientific_context_refs(candidate),
                        "evidence_refs": list(update.get("evidence_refs") or []),
                        "reason": str(update["rationale"]),
                        "recorded_at": now(),
                        "record_refs": [{"path": evaluation_path, "sha256": sha256_file(self.root / evaluation_path)}],
                    },
                )
            self._return_to_phase(
                state,
                from_phase=str(phase["phase"]),
                target=str(target),
                decision=str(decision),
                reason="formal_gate_return",
                provenance={
                    "verdict_id": verdict_id,
                    "reviewer": reviewer,
                    "verdict_artifact_sha256": verdict_hashes,
                    **(
                        {"return_guidance": result["return_guidance"]}
                        if "return_guidance" in result
                        else {}
                    ),
                },
                lesson=normalized_lesson,
            )
            return state

    def request_problem_revision(self, reason: str) -> dict[str, Any]:
        """Issue the receipt-bound human request for an explicit problem revision."""

        reason = reason.strip()
        if not reason:
            raise ControllerError("problem revision requires a non-empty scientific reason")
        with self._store.mutate() as state:
            phase = self._current_core_phase(state)
            if phase.get("status") == "running":
                raise ControllerError(
                    "cannot revise a problem while a phase is running; stop at a Controller boundary first"
                )
            phases = list(self.workflow["scientific_core"]["phases"])
            if phases.index(str(phase["phase"])) <= phases.index("problem_human_acceptance"):
                raise ControllerError("problem revision is available only after problem acceptance")
            active = self._assert_active_problem_version_current(state)
            bindings = {
                active["contract_path"]: active["contract_sha256"],
                active["evidence_capsule_path"]: active["evidence_capsule_sha256"],
            }
            core = state["scientific_core"]
            existing = core.get("problem_revision_request")
            if isinstance(existing, dict):
                if (
                    existing.get("phase") == phase["phase"]
                    and existing.get("reason") == reason
                    and existing.get("artifact_bindings") == bindings
                ):
                    return dict(existing)
                raise ControllerError("a different problem revision request is already pending")
            request = {
                "id": uuid.uuid4().hex,
                "gate": "problem_revision",
                "phase": phase["phase"],
                "reason": reason,
                "artifact_bindings": bindings,
                "issued_by": "ARISController",
                "created_at": now(),
            }
            core["problem_revision_request"] = request
            return dict(request)

    def revise_problem(self, reason: str) -> dict:
        """Apply one UI-confirmed problem revision at a Controller boundary."""

        reason = reason.strip()
        if not reason:
            raise ControllerError("problem revision requires a non-empty scientific reason")
        request = self.request_problem_revision(reason)
        with self._store.mutate() as state:
            phase = self._current_core_phase(state)
            if phase.get("status") == "running":
                raise ControllerError(
                    "cannot revise a problem while a phase is running; stop at a Controller boundary first"
                )
            core = state["scientific_core"]
            live_request = core.get("problem_revision_request")
            if (
                not isinstance(live_request, dict)
                or live_request.get("id") != request["id"]
                or live_request.get("phase") != phase["phase"]
                or live_request.get("reason") != reason
                or live_request.get("artifact_bindings") != request["artifact_bindings"]
                or live_request.get("issued_by") != "ARISController"
            ):
                raise ControllerError("problem revision request changed before approval was recorded")
            self._assert_active_problem_version_current(state)
            phases = list(self.workflow["scientific_core"]["phases"])
            target = "problem_generation"
            target_index = phases.index(target)
            current_index = phases.index(str(phase["phase"]))
            if current_index <= phases.index("problem_human_acceptance"):
                raise ControllerError("problem revision is available only after problem acceptance")
            receipt = self._consume_ui_approval_receipt(
                "problem_revision",
                str(request["id"]),
                "approve",
                artifact_bindings=dict(request["artifact_bindings"]),
            )
            reset_phases = phases[target_index : current_index + 1]
            reset_names = set(reset_phases)
            invalidated_at = now()
            return_event_id = f"revision-{uuid.uuid4().hex}"
            invalidation = {
                "return_event_id": return_event_id,
                "from_phase": phase["phase"],
                "return_target": target,
                "decision": "EXPLICIT_PROBLEM_REVISION",
                "reason": reason,
            }
            self._backfill_current_evidence_anchors(state, reset_phases)
            revision = self._begin_problem_revision(
                state,
                reason=reason,
                source="explicit_user_revision",
                return_event_id=return_event_id,
            )
            archive_root, invalidated_artifacts = self._archive_invalidated_outputs(
                state,
                reset_phases,
                return_event_id=return_event_id,
                invalidated_at=invalidated_at,
                invalidation=invalidation,
            )
            core["accepted_artifacts"] = {
                path: record
                for path, record in core["accepted_artifacts"].items()
                if record.get("producer_phase") not in reset_names
            }
            core.setdefault("invalidated_artifacts", []).extend(invalidated_artifacts)
            clear_fields = (
                "artifact", "verdict_id", "reviewer", "reviewer_family",
                "review_independence", "acceptance_status", "human_decision",
                "handoff_artifacts", "acceptance_artifacts", "validated_artifacts", "analysis_id",
                "problem_contract_sha256", "evidence_capsule_sha256",
                "gate_verdict", "reviewed_analysis_sha256", "review_request",
                "return_guidance", "history_recorded_for_reviewed_sha256",
            )
            for name in reset_names:
                item = run_state._find_phase(state, name)
                item["status"] = "pending"
                for field in clear_fields:
                    item[field] = None
                item["updated"] = invalidated_at
            core["current_phase"] = target
            core["approval_request"] = None
            core["problem_revision_request"] = None
            prior_cycle = core.get("method_test_cycle")
            if isinstance(prior_cycle, dict) and prior_cycle.get("cycle_id"):
                core["last_method_test_cycle_id"] = prior_cycle["cycle_id"]
            core["method_test_cycle"] = None
            core["selected_for_testing"] = None
            core["approvals"].append(
                {
                    "gate": "problem_revision",
                    "phase": phase["phase"],
                    "decision": "approve",
                    "approval_request_id": request["id"],
                    "artifact_bindings": request["artifact_bindings"],
                    "confirmed_in": receipt["confirmed_in"],
                    "at": invalidated_at,
                }
            )
            core.setdefault("return_history", []).append(
                {
                    "id": return_event_id,
                    "at": invalidated_at,
                    "archive_root": archive_root,
                    "invalidated_phases": list(reset_phases),
                    "invalidated_artifact_paths": [
                        record["path"] for record in invalidated_artifacts
                    ],
                    "problem_revision": dict(revision),
                    "approval_request_id": request["id"],
                    "confirmed_in": receipt["confirmed_in"],
                    **invalidation,
                }
            )
            core["transition_log"].append(
                {
                    "timestamp": invalidated_at,
                    "from": phase["phase"],
                    "to": target,
                    "reason": "explicit_problem_revision",
                    "return_event_id": return_event_id,
                }
            )
            return state

    def pending_human_approval(self) -> dict[str, Any]:
        state = self.status()
        core = state.get("scientific_core") or {}
        if core.get("status") == "ACTIVE":
            phase = self._current_core_phase(state)
            spec = self._phase_spec(state, phase["phase"])
            if not spec.get("human_checkpoint"):
                raise ControllerError("current scientific phase is not a Human Gate")
            request = core.get("approval_request")
            if (
                not isinstance(request, dict)
                or request.get("gate") != spec.get("gate_id")
                or request.get("phase") != phase["phase"]
                or request.get("issued_by") != "ARISController"
            ):
                raise ControllerError("Human Gate has no valid approval request")
            return dict(request)
        research = self._require_stage(state, "WAITING_FOR_HUMAN")
        request = research.get("approval_request")
        if not isinstance(request, dict) or request.get("gate") != research.get("waiting_for"):
            raise ControllerError("Human Gate has no valid approval request")
        return dict(request)

    @staticmethod
    def _human_gate_decision_target(spec: dict[str, Any], decision: str) -> str | None:
        accepted = set(spec.get("accepted_decisions") or [])
        if decision in accepted:
            return None
        target = (spec.get("return_targets") or {}).get(decision)
        if isinstance(target, str) and target:
            return target
        raise ControllerError(
            f"decision {decision!r} is not declared for Human Gate {spec.get('gate_id')!r}"
        )

    def _return_human_phase(
        self,
        state: dict,
        phase: dict[str, Any],
        spec: dict[str, Any],
        request: dict[str, Any],
        receipt: dict[str, Any],
        decision: str,
        target: str,
        selected_id: str | None,
        human_feedback: str | None,
    ) -> dict:
        """Archive one declined Human Gate and reopen its declared earlier phase."""

        core = state["scientific_core"]
        novelty_audit: dict[str, Any] | None = None
        candidate_baseline: dict[str, Any] | None = None
        combine_source_candidates: list[dict[str, str]] | None = None
        combine_source_packet: dict[str, str] | None = None
        if phase["phase"] == "principle_human_selection" and decision == "combine":
            combine_source_candidates = self._resolve_combine_source_candidates(
                state, selected_id
            )
            packet_path = str(self.workflow["artifact_manifest"]["method_design_packet"])
            packet_hash = request["artifact_bindings"].get(packet_path)
            if not isinstance(packet_hash, str) or not packet_hash:
                raise ControllerError("Human combine request is missing its reviewed Candidate packet binding")
            combine_source_packet = {"path": packet_path, "sha256": packet_hash}
        if phase["phase"] == "problem_human_acceptance":
            if not selected_id:
                raise ControllerError("Human Gate problem_acceptance requires an explicit selected_id for a non-approval decision")
            if decision == "request_revision":
                candidate_path = "idea-stage/PROBLEM_CANDIDATES.jsonl"
                candidate_record = self._registered_artifact_by_path(state, candidate_path)
                candidate_file = self.root / candidate_path
                if (
                    not isinstance(candidate_record, dict)
                    or not isinstance(candidate_record.get("sha256"), str)
                    or not candidate_file.is_file()
                    or sha256_file(candidate_file) != candidate_record["sha256"]
                ):
                    raise ControllerError("problem acceptance is missing the selected Candidate baseline artifact")
                candidate_baseline = {
                    "selected_id": selected_id,
                    "candidate_artifact": {
                        "path": candidate_path,
                        "sha256": candidate_record["sha256"],
                    },
                }
            selected_novelty, novelty_record = self._selected_problem_novelty_record(
                state, selected_id
            )
            novelty_audit = {
                "phase": "problem_novelty_gate",
                "candidate_id": selected_id,
                "candidate_verdict": selected_novelty["decision"],
                "verdict_id": selected_novelty["verdict_id"],
                "reviewer": selected_novelty["reviewer"],
                "review_request_id": selected_novelty["review_request_id"],
                "artifact": {
                    "path": "idea-stage/PROBLEM_NOVELTY_VERDICTS.jsonl",
                    "sha256": novelty_record["sha256"],
                },
                "novelty_assessment": dict(selected_novelty["novelty_assessment"]),
            }
        phases = list(self.workflow["scientific_core"]["phases"])
        target_index = phases.index(target)
        current_index = phases.index(str(phase["phase"]))
        reset_phases = phases[target_index : current_index + 1]
        reset_names = set(reset_phases)
        invalidated_at = now()
        return_event_id = f"human-return-{uuid.uuid4().hex}"
        invalidation = {
            "return_event_id": return_event_id,
            "from_phase": phase["phase"],
            "return_target": target,
            "decision": decision,
            "approval_request_id": request["id"],
            "human_feedback": human_feedback,
        }
        if candidate_baseline is not None:
            candidate_baseline["candidate_artifact"]["archive_path"] = (
                Path(".aris")
                / "archive"
                / self.run_id
                / return_event_id
                / "artifacts"
                / candidate_baseline["candidate_artifact"]["path"]
            ).as_posix()
        self._backfill_current_evidence_anchors(state, reset_phases)
        archive_root, invalidated_artifacts = self._archive_invalidated_outputs(
            state,
            reset_phases,
            return_event_id=return_event_id,
            invalidated_at=invalidated_at,
            invalidation=invalidation,
        )
        core["accepted_artifacts"] = {
            path: record
            for path, record in core["accepted_artifacts"].items()
            if record.get("producer_phase") not in reset_names
        }
        core.setdefault("invalidated_artifacts", []).extend(invalidated_artifacts)
        clear_fields = (
            "artifact", "verdict_id", "reviewer", "reviewer_family",
            "review_independence", "acceptance_status", "human_decision",
            "handoff_artifacts", "acceptance_artifacts", "validated_artifacts", "analysis_id",
            "problem_contract_sha256", "evidence_capsule_sha256",
            "gate_verdict", "reviewed_analysis_sha256", "review_request",
            "return_guidance", "history_recorded_for_reviewed_sha256",
        )
        for name in reset_names:
            item = run_state._find_phase(state, name)
            item["status"] = "pending"
            for field in clear_fields:
                item[field] = None
            item["updated"] = invalidated_at
        core["current_phase"] = target
        core["approval_request"] = None
        core["problem_revision_request"] = None
        if "method_design" in reset_names:
            prior_cycle = core.get("method_test_cycle")
            if isinstance(prior_cycle, dict) and prior_cycle.get("cycle_id"):
                core["last_method_test_cycle_id"] = prior_cycle["cycle_id"]
            core["method_test_cycle"] = None
            core["selected_for_testing"] = None
        core["approvals"].append(
            {
                "gate": request["gate"],
                "phase": phase["phase"],
                "decision": decision,
                "selected_id": selected_id,
                "human_feedback": human_feedback,
                "approval_request_id": request["id"],
                "artifact_bindings": dict(request["artifact_bindings"]),
                "confirmed_in": receipt["confirmed_in"],
                "at": invalidated_at,
            }
        )
        core.setdefault("return_history", []).append(
            {
                "id": return_event_id,
                "at": invalidated_at,
                "archive_root": archive_root,
                "invalidated_phases": list(reset_phases),
                "invalidated_artifact_paths": [
                    record["path"] for record in invalidated_artifacts
                ],
                "confirmed_in": receipt["confirmed_in"],
                "selected_id": selected_id,
                "human_feedback": human_feedback,
                **(
                    {"combine_source_candidates": combine_source_candidates}
                    if combine_source_candidates is not None
                    else {}
                ),
                **(
                    {"combine_source_packet": combine_source_packet}
                    if combine_source_packet is not None
                    else {}
                ),
                **({"candidate_baseline": candidate_baseline} if candidate_baseline is not None else {}),
                **({"novelty_audit": novelty_audit} if novelty_audit is not None else {}),
                **invalidation,
            }
        )
        target_spec = self._phase_spec(state, target)
        if target_spec.get("human_checkpoint"):
            core["approval_request"] = {
                "id": uuid.uuid4().hex,
                "gate": target_spec["gate_id"],
                "phase": target,
                "requires_selection": bool(target_spec.get("requires_selection")),
                "artifact_bindings": self._phase_input_bindings(state, target),
                "issued_by": "ARISController",
                "created_at": now(),
            }
        core["transition_log"].append(
            {
                "timestamp": invalidated_at,
                "from": phase["phase"],
                "to": target,
                "reason": "human_gate_return",
                "decision": decision,
                "selected_id": selected_id,
                "human_feedback": human_feedback,
                "approval_request_id": request["id"],
                "return_event_id": return_event_id,
                "archive_root": archive_root,
            }
        )
        return state

    def submit_source_admission_policy(self, payload: dict[str, Any]) -> dict:
        staged = self._stage_path("source_admission_policy")
        staged.parent.mkdir(parents=True, exist_ok=True)
        staged.write_text(
            yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        with self._store.mutate() as state:
            research = self._require_stage(state, "SOURCE_POLICY_DRAFTING")
            try:
                policy = validate_source_admission_policy(payload)
            except ValidationError as exc:
                self._record_validation(
                    research, "source_admission_policy", "FAIL", [str(exc)]
                )
                raise ControllerError(str(exc)) from exc
            policy_path = self._paths()["source_admission_policy"]
            policy_path.parent.mkdir(parents=True, exist_ok=True)
            policy_path.write_text(
                yaml.safe_dump(policy, sort_keys=False, allow_unicode=True),
                encoding="utf-8",
            )
            policy_sha256 = sha256_file(policy_path)
            self._record_validation(research, "source_admission_policy", "PASS")
            research["pending_source_policy"] = {
                "path": str(policy_path.relative_to(self.root)),
                "validator_result": "PASS",
                "sha256": policy_sha256,
                "author_role": "main_research_agent",
                "validated_at": now(),
            }
            research["current_stage"] = "WAITING_FOR_HUMAN"
            research["waiting_for"] = "source_policy_approval"
            research["approval_request"] = {
                "id": uuid.uuid4().hex,
                "gate": "source_policy_approval",
                "artifact_sha256": policy_sha256,
                "artifact_bindings": {
                    str(policy_path.relative_to(self.root)): policy_sha256
                },
                "issued_by": "ARISController",
                "created_at": now(),
            }
            return state

    def validate_human_gate_request(
        self,
        gate: str,
        *,
        require_outputs: bool = True,
        selected_id: str | None = None,
    ) -> dict[str, Any]:
        state = self.status()
        core = state.get("scientific_core") or {}
        if core.get("status") == "ACTIVE":
            phase = self._current_core_phase(state)
            spec = self._phase_spec(state, phase["phase"])
            if not spec.get("human_checkpoint") or gate != spec.get("gate_id"):
                raise ControllerError(
                    f"run is waiting for {spec.get('gate_id')}, not {gate}"
                )
            request = core.get("approval_request")
            if (
                not isinstance(request, dict)
                or request.get("gate") != gate
                or request.get("phase") != phase["phase"]
            ):
                raise ControllerError("Human Gate has no valid approval request")
            if phase.get("status") != "pending":
                raise ControllerError(
                    f"Human Gate phase must be pending; current={phase.get('status')}"
                )
            self._assert_phase_inputs_current(state, phase["phase"])
            if request.get("artifact_bindings") != self._phase_input_bindings(state, phase["phase"]):
                raise ControllerError("Human Gate request is stale or its reviewed artifact changed")
            if require_outputs:
                try:
                    output_result = run_state._assert_outputs(
                        str(self.root), state, spec, phase["phase"]
                    )
                except ValueError as exc:
                    raise ControllerError(str(exc)) from exc
            result = dict(request)
            if require_outputs:
                result["artifact_bindings"] = self._human_approval_bindings(
                    state, phase["phase"], spec
                )
            return result
        research = self._require_stage(state, "WAITING_FOR_HUMAN")
        if gate != research.get("waiting_for"):
            raise ControllerError(f"run is waiting for {research.get('waiting_for')}, not {gate}")
        request = research.get("approval_request")
        if (
            not isinstance(request, dict)
            or request.get("gate") != gate
            or request.get("issued_by") != "ARISController"
        ):
            raise ControllerError("Human Gate has no valid approval request")
        if gate == "source_policy_approval":
            candidate = self._assert_pending_source_policy_current(research)
            if request.get("artifact_sha256") != candidate["sha256"]:
                raise ControllerError("Human Gate does not match the validated source policy")
            if request.get("artifact_bindings") != {candidate["path"]: candidate["sha256"]}:
                raise ControllerError("Human Gate source-policy binding is stale or invalid")
        elif gate == "scope_human_approval":
            for name in ("source_admission_policy", "active_field_map", "coverage_review"):
                self._assert_artifact_current(research, name)
            if require_outputs:
                result = audit_landscape(self.root, state["workflow"], state=state)
                if not result["ok"] or result["coverage_status"] != "SUFFICIENT":
                    raise ControllerError(
                        "scope Human Gate prerequisites failed: " + "; ".join(result["errors"])
                    )
            expected = {
                str((research["accepted_artifacts"][name])["path"]): str(
                    research["accepted_artifacts"][name]["sha256"]
                )
                for name in ("source_admission_policy", "active_field_map", "coverage_review")
            }
            if request.get("artifact_bindings") != expected:
                raise ControllerError("scope Human Gate request is stale or its reviewed artifact changed")
        else:
            raise ControllerError(f"unsupported human gate {gate!r}")
        return dict(request)

    def validate_human_gate_decision(
        self,
        gate: str,
        decision: str,
        *,
        selected_id: str | None = None,
        human_feedback: str | None = None,
    ) -> dict[str, Any]:
        """Check a declared Human Gate decision before a UI receipt is issued."""

        decision = decision.strip().casefold()
        if not decision:
            raise ControllerError("human approval decision must be non-empty")
        state = self.status()
        core = state.get("scientific_core") or {}
        if core.get("status") == "ACTIVE":
            phase = self._current_core_phase(state)
            spec = self._phase_spec(state, phase["phase"])
            target = self._human_gate_decision_target(spec, decision)
            if phase["phase"] == "principle_human_selection":
                if target is None:
                    self._resolve_candidate_selection(state, selected_id)
                else:
                    if not isinstance(human_feedback, str) or not human_feedback.strip():
                        raise ControllerError(
                            "Human Gate principle_selection revisions, combinations, and rejection require non-empty human_feedback"
                        )
                    if decision == "combine":
                        self._resolve_combine_source_candidates(state, selected_id)
            if (
                target is not None
                and phase["phase"] == "principle_test_human_approval"
                and (not isinstance(human_feedback, str) or not human_feedback.strip())
            ):
                raise ControllerError(
                    "Human Gate principle_test_approval revision requires non-empty human_feedback"
                )
            if (
                target is not None
                and phase["phase"] == "problem_human_acceptance"
            ):
                if not selected_id:
                    raise ControllerError(
                        "Human Gate problem_acceptance requires an explicit selected_id for a non-approval decision"
                    )
                if not isinstance(human_feedback, str) or not human_feedback.strip():
                    raise ControllerError(
                        "Human Gate problem_acceptance requires non-empty human_feedback for a non-approval decision"
                    )
            if target is not None and phase["phase"] == "problem_human_acceptance":
                self._selected_problem_novelty_record(state, selected_id)
            return self.validate_human_gate_request(
                gate, require_outputs=target is None, selected_id=selected_id
            )
        elif gate == "scope_human_approval":
            spec = run_state._workflow_phase(state, "scope_human_approval")
            assert spec is not None
            target = self._human_gate_decision_target(spec, decision)
            return self.validate_human_gate_request(
                gate, require_outputs=target is None, selected_id=selected_id
            )
        elif gate == "source_policy_approval" and decision != "approve":
            raise ControllerError("source-policy revisions use request-source-policy-revision")
        return self.validate_human_gate_request(gate, selected_id=selected_id)

    def human_approve(
        self,
        gate: str,
        decision: str,
        *,
        selected_id: str | None = None,
        human_feedback: str | None = None,
    ) -> dict:
        decision = decision.strip().casefold()
        if not decision:
            raise ControllerError("human approval decision must be non-empty")
        request = self.validate_human_gate_decision(
            gate, decision, selected_id=selected_id, human_feedback=human_feedback
        )
        with self._store.mutate() as state:
            core = state.get("scientific_core") or {}
            if core.get("status") == "ACTIVE":
                phase = self._current_core_phase(state)
                spec = self._phase_spec(state, phase["phase"])
                live_request = core.get("approval_request")
                if (
                    not spec.get("human_checkpoint")
                    or gate != spec.get("gate_id")
                    or not isinstance(live_request, dict)
                    or live_request.get("id") != request.get("id")
                ):
                    raise ControllerError("Human Gate changed before approval was recorded")
                if phase.get("status") != "pending":
                    raise ControllerError(
                        f"Human Gate phase must be pending; current={phase.get('status')}"
                    )
                self._assert_phase_inputs_current(state, phase["phase"])
                if live_request.get("artifact_bindings") != self._phase_input_bindings(state, phase["phase"]):
                    raise ControllerError("Human Gate request is stale or its reviewed artifact changed")
                target = self._human_gate_decision_target(spec, decision)
                approval_bindings = (
                    self._human_approval_bindings(state, phase["phase"], spec)
                    if target is None
                    else dict(request.get("artifact_bindings") or {})
                )
                if request.get("artifact_bindings") != approval_bindings:
                    raise ControllerError("Human Gate approval artifacts changed before receipt consumption")
                if target is not None:
                    receipt = self._consume_ui_approval_receipt(
                        gate,
                        str(request["id"]),
                        decision,
                        selected_id=selected_id,
                        human_feedback=human_feedback,
                        artifact_bindings=approval_bindings,
                    )
                    return self._return_human_phase(
                        state,
                        phase,
                        spec,
                        request,
                        receipt,
                        decision,
                        target,
                        selected_id,
                        human_feedback,
                    )
                if spec.get("requires_selection") and not selected_id:
                    raise ControllerError(
                        f"Human Gate {gate} requires an explicit selected_id"
                    )
                receipt = self._consume_ui_approval_receipt(
                    gate,
                    str(request["id"]),
                    decision,
                    selected_id=selected_id,
                    human_feedback=human_feedback,
                    artifact_bindings=approval_bindings,
                )
                registered = self._register_phase_outputs(
                    state,
                    phase["phase"],
                    provenance={
                        "controller": "ARISController",
                        "run_id": self.run_id,
                        "human_gate": gate,
                        "approval_request_id": request["id"],
                        "approved_by": "codex_ui_user",
                        "selected_id": selected_id,
                        "confirmed_in": receipt["confirmed_in"],
                    },
                )
                phase["status"] = "human_accepted"
                phase["acceptance_status"] = "human_accepted"
                phase["human_decision"] = {
                    "decision": decision,
                    "selected_id": selected_id,
                    "approval_request_id": request["id"],
                    "artifact_bindings": approval_bindings,
                    "confirmed_in": receipt["confirmed_in"],
                    "recorded_at": now(),
                }
                if phase["phase"] == "problem_human_acceptance":
                    self._accept_problem_version(
                        state,
                        selected_id=str(selected_id),
                        registered=registered,
                        acceptance=phase["human_decision"],
                    )
                elif phase["phase"] == "principle_human_selection":
                    candidate = self._resolve_candidate_selection(state, selected_id)
                    binding = self._establish_selected_for_testing(
                        state,
                        candidate=candidate,
                        request=request,
                        receipt=receipt,
                    )
                    phase["selected_for_testing"] = deepcopy(binding)
                elif phase["phase"] == "principle_test_human_approval":
                    self._initialize_method_test_cycle(state)
                phase["artifact"] = next(iter(registered), None)
                phase["handoff_artifacts"] = registered
                phase["updated"] = now()
                core["approvals"].append(
                    {
                        "gate": gate,
                        "phase": phase["phase"],
                        "decision": decision,
                        "selected_id": selected_id,
                        "approval_request_id": request["id"],
                        "confirmed_in": receipt["confirmed_in"],
                        "at": now(),
                    }
                )
                core["approval_request"] = None
                self._advance_scientific_core(state, reason="human_gate_accepted")
                return state
            research = self._require_stage(state, "WAITING_FOR_HUMAN")
            waiting_for = research.get("waiting_for")
            if gate != waiting_for:
                raise ControllerError(f"run is waiting for {waiting_for}, not {gate}")
            live_request = research.get("approval_request")
            if (
                not isinstance(live_request, dict)
                or live_request.get("id") != request.get("id")
                or live_request.get("gate") != gate
                or live_request.get("issued_by") != "ARISController"
                or live_request.get("artifact_bindings") != request.get("artifact_bindings")
            ):
                raise ControllerError("Human Gate changed before approval was recorded")
            if gate == "source_policy_approval":
                if decision != "approve":
                    raise ControllerError("source-policy revisions use request-source-policy-revision")
                candidate = self._assert_pending_source_policy_current(research)
                if request.get("artifact_sha256") != candidate["sha256"]:
                    raise ControllerError(
                        "Human Gate does not match the validated source policy"
                    )
                research["accepted_artifacts"]["source_admission_policy"] = {
                    "path": candidate["path"],
                    "validator_result": "PASS",
                    "sha256": candidate["sha256"],
                    "author_role": candidate["author_role"],
                    "approved_by": "codex_ui_user",
                    "approval_request_id": request["id"],
                    "artifact_bindings": dict(request["artifact_bindings"]),
                    "approved_at": now(),
                }
                research["current_stage"] = "QUERY_PLANNING"
                research["waiting_for"] = None
                research["pending_source_policy"] = None
                research["human_fulltext_request"] = None
            elif gate == "scope_human_approval":
                phase = run_state._find_phase(state, "scope_human_approval")
                spec = run_state._workflow_phase(state, "scope_human_approval")
                assert spec is not None
                run_state._assert_dependencies(str(self.root), state, spec, "scope_human_approval")
                target = self._human_gate_decision_target(spec, decision)
                if target is not None:
                    receipt = self._consume_ui_approval_receipt(
                        gate,
                        str(request["id"]),
                        decision,
                        selected_id=selected_id,
                        artifact_bindings=dict(request.get("artifact_bindings") or {}),
                    )
                    phase.update(
                        {
                            "status": "pending",
                            "acceptance_status": None,
                            "human_decision": None,
                            "updated": now(),
                        }
                    )
                    research["approvals"].append({
                        "gate": gate,
                        "phase": "scope_human_approval",
                        "decision": decision,
                        "approval_request_id": request["id"],
                        "artifact_bindings": dict(request["artifact_bindings"]),
                        "confirmed_in": receipt["confirmed_in"],
                        "at": now(),
                    })
                    research["current_stage"] = "QUERY_PLANNING"
                    research["waiting_for"] = None
                    research["approval_request"] = None
                    return state
                phase["status"] = "human_accepted"
                phase["acceptance_status"] = "human_accepted"
                phase["human_decision"] = {
                    "decision": decision,
                    "selected_id": selected_id,
                    "recorded_at": now(),
                }
                research["current_stage"] = "LANDSCAPE_ACCEPTED"
                research["waiting_for"] = None
            else:
                raise ControllerError(f"unsupported human gate {gate!r}")
            receipt = self._consume_ui_approval_receipt(
                gate,
                str(request["id"]),
                decision,
                selected_id=selected_id,
                artifact_bindings=dict(request.get("artifact_bindings") or {}),
            )
            research["approvals"].append({
                "gate": gate,
                "decision": decision,
                "selected_id": selected_id,
                "approval_request_id": request["id"],
                "confirmed_in": receipt["confirmed_in"],
                "at": now(),
            })
            research["approval_request"] = None
            if gate == "scope_human_approval":
                self._activate_scientific_core(state, receipt)
            return state

    def request_source_policy_revision(self) -> dict:
        """Return a validated policy candidate to Main for human-requested revision."""
        gate = "source_policy_approval"
        request = self.validate_human_gate_request(gate)
        with self._store.mutate() as state:
            research = self._require_stage(state, "WAITING_FOR_HUMAN")
            if research.get("waiting_for") != gate:
                raise ControllerError(f"run is waiting for {research.get('waiting_for')}, not {gate}")
            candidate = self._assert_pending_source_policy_current(research)
            if research.get("approval_request", {}).get("id") != request["id"]:
                raise ControllerError("Human Gate changed before source policy revision")
            if request.get("artifact_sha256") != candidate["sha256"]:
                raise ControllerError("Human Gate does not match the validated source policy")
            receipt = self._consume_ui_approval_receipt(
                gate,
                str(request["id"]),
                "request_revision",
                artifact_bindings=dict(request.get("artifact_bindings") or {}),
            )
            research["approvals"].append({
                "gate": gate,
                "decision": "request_revision",
                "approval_request_id": request["id"],
                "artifact_sha256": candidate["sha256"],
                "artifact_bindings": dict(request["artifact_bindings"]),
                "confirmed_in": receipt["confirmed_in"],
                "at": now(),
            })
            research["current_stage"] = "SOURCE_POLICY_DRAFTING"
            research["waiting_for"] = None
            research["approval_request"] = None
            research["pending_source_policy"] = None
            research["human_fulltext_request"] = None
            return state

    def submit_query_plan(self, payload: dict[str, Any]) -> dict:
        staged = self._stage_path("query_plan")
        staged.parent.mkdir(parents=True, exist_ok=True)
        staged.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        with self._store.mutate() as state:
            research = state["research_lit"]
            incremental_phase: str | None = None
            if research["current_stage"] == "QUERY_PLANNING":
                pass
            elif research["current_stage"] == "LANDSCAPE_ACCEPTED":
                phase = self._current_core_phase(state)
                if not self._incremental_literature_phase_allowed(state, phase):
                    raise ControllerError(
                        "incremental literature is allowed only before an eligible phase, "
                        "or while an iterative Problem/RCA/Method phase is running"
                    )
                incremental_phase = str(phase["phase"])
            else:
                raise ControllerError(
                    f"action requires stage QUERY_PLANNING or an eligible core phase, current={research['current_stage']}"
                )
            self._assert_artifact_current(research, "source_admission_policy")
            fallback_insufficient = self._fallback_level_three_active(research) and (
                research.get("last_coverage_status") in {"PARTIAL", "INSUFFICIENT"}
                or research.get("last_coverage_review_decision") == "CONTINUE"
            )
            if (
                not fallback_insufficient
                and research["search_cycle_count"] >= research["max_search_cycles"]
            ):
                raise ControllerError("search-cycle budget exhausted before accepting a new plan")
            try:
                method_context = (
                    self._method_design_query_context(state)
                    if incremental_phase == "method_design"
                    and phase.get("status") == "running"
                    else None
                )
                refinement_context = (
                    self._method_refinement_query_context(state)
                    if incremental_phase == "method_refinement"
                    and phase.get("status") == "running"
                    else None
                )
                problem_lead_context = (
                    {
                        "active_field_map_sha256": str(
                            self._assert_artifact_current(research, "active_field_map")["sha256"]
                        )
                    }
                    if incremental_phase == "problem_generation"
                    else None
                )
                # Keep the historical review-gap check below for its explicit
                # error/reporting path, then validate the same unified gaps at
                # per-query granularity.
                plan = validate_query_plan(
                    payload,
                    method_design_context=method_context,
                    method_refinement_context=refinement_context,
                    problem_lead_context=problem_lead_context,
                )
            except ValidationError as exc:
                self._record_validation(research, "query_plan", "FAIL", [str(exc)])
                raise ControllerError(str(exc)) from exc
            required_gaps = self._required_coverage_gaps(research)
            planned_gaps = set(plan.get("coverage_gaps") or [])
            if not required_gaps.issubset(planned_gaps):
                if research.get("last_coverage_review_decision") == "CONTINUE":
                    raise ControllerError(
                        "controlled coverage replenishment query plan must retain every "
                        "concrete CONTINUE gap"
                    )
                raise ControllerError(
                    "gap-driven query plan must retain every required coverage gap from "
                    "the current Active Field Map"
                )
            try:
                validate_query_plan(
                    plan,
                    method_design_context=method_context,
                    method_refinement_context=refinement_context,
                    problem_lead_context=problem_lead_context,
                    required_coverage_gaps=required_gaps,
                )
            except ValidationError as exc:
                self._record_validation(research, "query_plan", "FAIL", [str(exc)])
                raise ControllerError(str(exc)) from exc
            self._record_validation(research, "query_plan", "PASS")
            artifact_name = (
                f"incremental-query-plan-{incremental_phase}"
                if incremental_phase is not None
                else "query_plan"
            )
            serialized_plan = json.dumps(plan, ensure_ascii=False, indent=2)
            # A method-design Evidence Card carries its accepted Query Plan path
            # as discovery provenance.  Unlike the ordinary current-plan slot,
            # this plan can be followed by another running-phase search, so its
            # accepted bytes need a stable path from the first acceptance.
            if artifact_name in {
                "incremental-query-plan-method_design",
                "incremental-query-plan-method_refinement",
            }:
                plan_sha256 = hashlib.sha256(serialized_plan.encode("utf-8")).hexdigest()
                canonical = (
                    self.root
                    / ".aris"
                    / "canonical"
                    / self.run_id
                    / "query-plan"
                    / f"{artifact_name}-{plan_sha256}.json"
                )
            else:
                canonical = self._canonical_path(artifact_name)
            canonical.parent.mkdir(parents=True, exist_ok=True)
            self._archive_accepted_query_plan_if_referenced(research, artifact_name)
            canonical.write_text(serialized_plan, encoding="utf-8")
            research["accepted_artifacts"][artifact_name] = {
                "path": str(canonical.relative_to(self.root)),
                "validator_result": "PASS",
                "sha256": sha256_file(canonical),
                "accepted_at": now(),
                "author_role": "main_research_agent",
            }
            if incremental_phase is not None:
                try:
                    binding_anchor = self._phase_evidence_anchor(state, incremental_phase)
                except ControllerError:
                    # Controller-started phases have already passed their input
                    # checks.  Keep compatibility with old in-memory harness
                    # fixtures that construct a gateway session directly; they
                    # predate phase-current bindings and remain legacy records.
                    binding_anchor = None
                research["incremental_literature_active"] = {
                    "phase": incremental_phase,
                    "query_plan_path": str(canonical.relative_to(self.root)),
                    "query_plan_sha256": sha256_file(canonical),
                    # The query plan is provenance, not a derivation epoch.
                    # Freeze only the phase's formal upstream context here,
                    # before the gateway starts accepting Evidence Cards.
                    "evidence_artifacts": {},
                    "started_at": now(),
                }
                if binding_anchor is not None:
                    research["incremental_literature_active"]["phase_binding_anchor"] = binding_anchor
            if not fallback_insufficient:
                research["search_cycle_count"] += 1
            research["planned_queries"] = []
            for item in plan["queries"]:
                planned = dict(item)
                planned["query"] = item["query"].strip()
                planned["status"] = "planned"
                if plan.get("schema_version", 1) == 2:
                    planned["constraints"] = {
                        "year_from": item["year_from"],
                        "year_to": item["year_to"],
                        "exact_title": item["exact_title"],
                        "page": item["page"],
                    }
                research["planned_queries"].append(planned)
            if fallback_insufficient:
                self._route_planned_queries_to_human_search(
                    research,
                    evidence_gaps=list(plan["coverage_gaps"]),
                    reason="existing research-lit coverage judgment remains insufficient after level-3 fallback",
                )
            else:
                research["current_stage"] = "METADATA_RETRIEVAL"
            return state

    def execute_query(
        self,
        query: str,
        tool: str,
        search: SearchCallable,
        *,
        plan_item_id: str | None = None,
        query_options: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        query = query.strip()
        if not query:
            raise ControllerError("query must be non-empty")
        ledger = self._paths()["search_log"]
        with self._store.mutate() as state:
            research = self._require_stage(state, "METADATA_RETRIEVAL")
            self._assert_artifact_current(research, "source_admission_policy")
            session = self._incremental_literature_active(research)
            if session is None:
                active_plan_record = self._assert_artifact_current(research, "query_plan")
            else:
                self._active_query_plan(research)
                active_plan_record = session
            active_plan = self._active_query_plan(research)
            schema_version = active_plan.get("schema_version", 1)
            if schema_version == 2:
                if not isinstance(plan_item_id, str) or not plan_item_id.strip():
                    raise ControllerError("schema_version 2 queries require plan_item_id")
                planned = next(
                    (
                        item
                        for item in research["planned_queries"]
                        if item.get("plan_item_id") == plan_item_id and item["query"] == query
                    ),
                    None,
                )
                if planned is None:
                    raise ControllerError("query and plan_item_id do not match the accepted query plan")
                if not isinstance(query_options, dict):
                    raise ControllerError("schema_version 2 queries require explicit query options")
                expected_options = dict(planned.get("constraints") or {})
                actual_options = {
                    key: query_options.get(key)
                    for key in ("year_from", "year_to", "exact_title", "page")
                }
                if actual_options != expected_options:
                    raise ControllerError(
                        "query options do not match the accepted query-plan item: "
                        f"expected={expected_options}, actual={actual_options}"
                    )
            else:
                planned = next(
                    (item for item in research["planned_queries"] if item["query"] == query),
                    None,
                )
            if planned is None:
                raise ControllerError("query was not accepted in the current query plan")
            if planned["status"] != "planned":
                raise ControllerError("query has already been attempted in this search cycle")
            query_context = self._problem_lead_query_context(research, planned)
            query_plan_sha256 = str(active_plan_record.get("sha256") or active_plan_record.get("query_plan_sha256") or "")
            if not query_plan_sha256:
                raise ControllerError("accepted query plan has no sha256")
            retry_query_id = str(planned.pop("retry_query_id", "") or "")
            before = research["query_count"]
            if retry_query_id:
                query_id = retry_query_id
            else:
                if before >= research["max_queries"]:
                    raise ControllerError(
                        f"query budget exhausted before tool call: {before}/{research['max_queries']}"
                    )
                research["query_count"] = before + 1
                query_id = f"Q{research['query_count']:04d}"
            event_id = uuid.uuid4().hex
            planned["status"] = "started"
            planned["query_id"] = query_id
            budget_before = {"queries": before, "fulltext": research["fulltext_count"]}
            budget_after = {
                "queries": research["query_count"],
                "fulltext": research["fulltext_count"],
            }
            append_jsonl(
                ledger,
                ledger_event(
                    run_id=self.run_id,
                    stage="METADATA_RETRIEVAL",
                    action="query",
                    query_id=query_id,
                    query=query,
                    tool=tool,
                    result_status="started",
                    event_id=event_id,
                    budget_before=budget_before,
                    budget_after=budget_after,
                    details={
                        "plan_item_id": planned.get("plan_item_id"),
                        "priority_tier": planned.get("priority_tier"),
                        "coverage_gaps": list(planned.get("coverage_gaps") or []),
                        "query_options": dict(query_options or {}),
                        "query_context": query_context,
                    },
                ),
            )
            research["query_events"][query_id] = {
                "event_id": event_id,
                "query": query,
                "plan_item_id": planned.get("plan_item_id"),
                "priority_tier": planned.get("priority_tier"),
                "coverage_gaps": list(planned.get("coverage_gaps") or []),
                "query_options": dict(query_options or {}),
                "query_plan_sha256": query_plan_sha256,
                "query_context": query_context,
                "tool": tool,
                "status": "started",
                "budget_before": budget_before,
                "budget_after": budget_after,
            }
        try:
            search_result = search(query)
            if isinstance(search_result, SearchOutcome):
                results = search_result.results
                tool_used = search_result.provider
                provider_attempts = search_result.attempts
                google_scholar_coverage = search_result.google_scholar_coverage
                query_constraints = search_result.query_options
            else:
                results = search_result
                tool_used = tool
                provider_attempts = []
                google_scholar_coverage = None
                query_constraints = {}
            if not isinstance(results, list):
                raise TypeError("search gateway adapter must return a list of metadata objects")
            metadata_rows: list[dict[str, Any]] = []
            for metadata in results:
                if not isinstance(metadata, dict):
                    raise ControllerError("search gateway metadata rows must be objects")
                paper_id = metadata.get("paper_id") or metadata.get("source_id")
                if not isinstance(paper_id, str) or not paper_id:
                    raise ControllerError("paper metadata requires paper_id or source_id")
                row = dict(metadata)
                row["source_id"] = paper_id
                row["source_origin"] = "gateway_discovery"
                row["found_by_query_ids"] = sorted(
                    set(list(row.get("found_by_query_ids") or []) + [query_id])
                )
                row["admission_status"] = "DISCOVERY_METADATA_ONLY"
                if isinstance(search_result, SearchOutcome):
                    row.setdefault("search_route", tool_used)
                    row.setdefault("google_scholar_coverage", google_scholar_coverage)
                metadata_rows.append(row)
        except HumanSearchRequired as exc:
            with self._store.mutate() as state:
                research = self._require_stage(state, "METADATA_RETRIEVAL")
                event = research["query_events"][query_id]
                event["status"] = "human_search_required"
                event["provider_attempts"] = exc.attempts
                planned_query = next(
                    item for item in research["planned_queries"] if item.get("query_id") == query_id
                )
                planned_query["constraints"] = dict(exc.query_options)
                plan = self._active_query_plan(research)
                self._route_planned_queries_to_human_search(
                    research,
                    evidence_gaps=list(plan.get("coverage_gaps") or []),
                    reason="all configured discovery routes failed for this query",
                )
                exc.request = dict(research["human_search_request"])
            append_jsonl(
                ledger,
                ledger_event(
                    run_id=self.run_id,
                    stage="METADATA_RETRIEVAL",
                    action="query",
                    query_id=query_id,
                    query=query,
                    tool=tool,
                    result_status="human_search_required",
                    event_id=event_id,
                    budget_before=budget_before,
                    budget_after=budget_after,
                    details={
                        "plan_item_id": planned.get("plan_item_id"),
                        "query_options": dict(query_options or {}),
                        "provider_attempts": exc.attempts,
                        "query_context": query_context,
                    },
                ),
            )
            for attempt in exc.attempts:
                append_jsonl(
                    ledger,
                    ledger_event(
                        run_id=self.run_id,
                        stage="METADATA_RETRIEVAL",
                        action="provider_attempt",
                        query_id=query_id,
                        query=query,
                        tool=attempt["provider"],
                        result_status=attempt["status"],
                        event_id=uuid.uuid4().hex,
                        details={"reason": attempt.get("reason", "")},
                    ),
                )
            raise
        except Exception:
            with self._store.mutate() as state:
                research = self._require_stage(state, "METADATA_RETRIEVAL")
                research["query_events"][query_id]["status"] = "failed"
                next(
                    item for item in research["planned_queries"] if item.get("query_id") == query_id
                )["status"] = "failed"
            append_jsonl(
                ledger,
                ledger_event(
                    run_id=self.run_id,
                    stage="METADATA_RETRIEVAL",
                    action="query",
                    query_id=query_id,
                    query=query,
                    tool=tool,
                    result_status="failed",
                    event_id=event_id,
                    budget_before=budget_before,
                    budget_after=budget_after,
                ),
            )
            raise
        with self._store.mutate() as state:
            research = self._require_stage(state, "METADATA_RETRIEVAL")
            session = self._incremental_literature_active(research)
            research["query_events"][query_id]["status"] = "complete"
            research["query_events"][query_id]["tool"] = tool_used
            research["query_events"][query_id]["provider_attempts"] = provider_attempts
            planned_query = next(
                item for item in research["planned_queries"] if item.get("query_id") == query_id
            )
            planned_query["status"] = "complete"
            planned_query["constraints"] = dict(query_constraints)
            for row in metadata_rows:
                paper_id = row["source_id"]
                merged = _merge_discovery_metadata(
                    research["papers"].get(paper_id), row
                )
                research["papers"][paper_id] = merged
                row.clear()
                row.update(merged)
                if session is not None:
                    session.setdefault("paper_ids", []).append(paper_id)
            provider_failure = any(
                attempt.get("status") in {"unavailable", "blocked"}
                for attempt in provider_attempts
            )
            if provider_failure:
                plan = self._active_query_plan(research)
                self._route_planned_queries_to_human_search(
                    research,
                    evidence_gaps=list(plan.get("coverage_gaps") or []),
                    reason=(
                        "automatic discovery reached a lower-priority route after one or more "
                        "configured sources failed; manual batch search is required to preserve coverage"
                    ),
                    include_completed=True,
                )
                human_request = dict(research["human_search_request"])
            else:
                human_request = None
        append_jsonl(
            ledger,
            ledger_event(
                run_id=self.run_id,
                stage="METADATA_RETRIEVAL",
                action="query",
                query_id=query_id,
                query=query,
                tool=tool_used,
                result_status=("complete_with_human_followup" if human_request else "complete"),
                event_id=event_id,
                budget_before=budget_before,
                budget_after=budget_after,
                details={
                    "plan_item_id": planned.get("plan_item_id"),
                    "priority_tier": planned.get("priority_tier"),
                    "coverage_gaps": list(planned.get("coverage_gaps") or []),
                    "query_options": dict(query_constraints or query_options or {}),
                    "query_context": query_context,
                },
            ),
        )
        for attempt in provider_attempts:
            append_jsonl(
                ledger,
                ledger_event(
                    run_id=self.run_id,
                    stage="METADATA_RETRIEVAL",
                    action="provider_attempt",
                    query_id=query_id,
                    query=query,
                    tool=attempt["provider"],
                    result_status=attempt["status"],
                    event_id=uuid.uuid4().hex,
                    details={"reason": attempt.get("reason", "")},
                ),
            )
        for row in metadata_rows:
            append_jsonl(self._paths()["literature_corpus"], row)
            append_jsonl(
                ledger,
                ledger_event(
                    run_id=self.run_id,
                    stage="METADATA_RETRIEVAL",
                    action="metadata",
                    query_id=query_id,
                    paper_id=row["source_id"],
                    tool=tool_used,
                    result_status="recorded",
                    admission_decision=row.get("admission_status", "DISCOVERY_METADATA_ONLY"),
                    event_id=uuid.uuid4().hex,
                ),
            )
        if human_request is not None:
            required = HumanSearchRequired(provider_attempts, query_options=query_constraints)
            required.request = human_request
            raise required
        return results

    def submit_human_search_results(
        self, payload: dict[str, Any]
    ) -> list[dict[str, Any]] | dict[str, Any]:
        query = str(payload.get("query") or "").strip()
        retry_provider = str(payload.get("retry_provider") or "").strip()
        if retry_provider:
            return self._resume_after_provider_recovery(query, retry_provider)
        submitted = payload.get("queries")
        if submitted is None:
            results = payload.get("results")
            if not query or not isinstance(results, list):
                raise ControllerError("human search results require query results or a batch queries list")
            submitted = [{"query": query, "results": results, "source": payload.get("source")}]
        if not isinstance(submitted, list) or not submitted:
            raise ControllerError("human search batch requires a non-empty queries list")
        metadata_rows: list[dict[str, Any]] = []
        ledger_rows: list[tuple[dict[str, Any], str, str, str]] = []
        query_completion_rows: list[dict[str, Any]] = []
        with self._store.mutate() as state:
            research = self._require_stage(state, "HUMAN_SEARCH_REQUIRED")
            request = research.get("human_search_request")
            requested = request.get("queries") if isinstance(request, dict) else None
            if not isinstance(requested, list) or not requested:
                raise ControllerError("no batch human-search request is pending")
            expected_by_id = {
                str(item.get("query_id")): item
                for item in requested
                if isinstance(item, dict) and item.get("query_id")
            }
            submitted_by_id: dict[str, dict[str, Any]] = {}
            for item in submitted:
                if not isinstance(item, dict):
                    raise ControllerError("each human search batch item must be an object")
                item_query = str(item.get("query") or "").strip()
                item_id = str(item.get("query_id") or "").strip()
                if not item_id:
                    matches = [
                        candidate_id
                        for candidate_id, candidate in expected_by_id.items()
                        if candidate.get("query") == item_query
                    ]
                    if len(matches) != 1:
                        raise ControllerError("human search batch item does not match a requested query")
                    item_id = matches[0]
                if item_id not in expected_by_id or item_id in submitted_by_id:
                    raise ControllerError("human search batch items must match each requested query once")
                if not isinstance(item.get("results"), list):
                    raise ControllerError("human search batch results must be a list")
                submitted_by_id[item_id] = item
            if set(submitted_by_id) != set(expected_by_id):
                raise ControllerError("human search batch must cover every requested query")
            for query_id, requested_item in expected_by_id.items():
                item = submitted_by_id[query_id]
                source = str(
                    item.get("source") or payload.get("source") or "human_google_scholar"
                ).strip()
                planned = next(
                    (candidate for candidate in research["planned_queries"] if candidate.get("query_id") == query_id),
                    None,
                )
                if planned is None or planned.get("status") != "human_search_required":
                    raise ControllerError("pending human search query is not resumable")
                for metadata in item["results"]:
                    if not isinstance(metadata, dict):
                        raise ControllerError("human search metadata rows must be objects")
                    paper_id = metadata.get("paper_id") or metadata.get("source_id")
                    if not isinstance(paper_id, str) or not paper_id:
                        raise ControllerError("human search metadata requires paper_id or source_id")
                    row = dict(metadata)
                    row["source_id"] = paper_id
                    row["source_origin"] = "human_search"
                    row["found_by_query_ids"] = sorted(
                        set(list(row.get("found_by_query_ids") or []) + [query_id])
                    )
                    row["admission_status"] = "DISCOVERY_METADATA_ONLY"
                    row["search_route"] = source
                    row["google_scholar_coverage"] = source == "human_google_scholar"
                    metadata_rows.append(row)
                    ledger_rows.append((row, query_id, str(requested_item["query"]), source))
                    merged = _merge_discovery_metadata(
                        research["papers"].get(paper_id), row
                    )
                    research["papers"][paper_id] = merged
                    row.clear()
                    row.update(merged)
                    session = self._incremental_literature_active(research)
                    if session is not None:
                        session.setdefault("paper_ids", []).append(paper_id)
                planned["status"] = "complete"
                query_event = research["query_events"][query_id]
                query_event["status"] = "complete_human"
                query_event["tool"] = source
                query_completion_rows.append(
                    {
                        "query_id": query_id,
                        "query": str(requested_item["query"]),
                        "source": source,
                        "result_count": len(item["results"]),
                        "budget_before": query_event.get("budget_before"),
                        "budget_after": query_event.get("budget_after"),
                        "supersedes_event_id": query_event.get("event_id"),
                        "query_context": query_event.get("query_context"),
                    }
                )
            research["current_stage"] = "METADATA_RETRIEVAL"
            research["waiting_for"] = None
            research["human_search_request"] = None
        for completion in query_completion_rows:
            append_jsonl(
                self._paths()["search_log"],
                ledger_event(
                    run_id=self.run_id,
                    stage="HUMAN_SEARCH_REQUIRED",
                    action="query",
                    query_id=completion["query_id"],
                    query=completion["query"],
                    tool=completion["source"],
                    result_status="complete_human",
                    event_id=uuid.uuid4().hex,
                    budget_before=completion["budget_before"],
                    budget_after=completion["budget_after"],
                    details={
                        "result_count": completion["result_count"],
                        "supersedes_event_id": completion["supersedes_event_id"],
                        "query_context": completion["query_context"],
                    },
                ),
            )
        for row, query_id, item_query, source in ledger_rows:
            append_jsonl(self._paths()["literature_corpus"], row)
            append_jsonl(
                self._paths()["search_log"],
                ledger_event(
                    run_id=self.run_id,
                    stage="HUMAN_SEARCH_REQUIRED",
                    action="human_search_metadata",
                    query_id=query_id,
                    query=item_query,
                    paper_id=row["source_id"],
                    tool=source,
                    result_status="recorded",
                    admission_decision=row.get("admission_status", "DISCOVERY_METADATA_ONLY"),
                    event_id=uuid.uuid4().hex,
                ),
            )
        return metadata_rows

    def recover_interrupted_query(self, plan_item_id: str, *, reason: str) -> dict[str, str]:
        """Return an orphaned started query to the plan without refunding its budget."""

        item_id = str(plan_item_id or "").strip()
        scientific_reason = str(reason or "").strip()
        if not item_id or not scientific_reason:
            raise ControllerError(
                "interrupted-query recovery requires a plan_item_id and reason"
            )
        with self._store.mutate() as state:
            research = self._require_stage(state, "METADATA_RETRIEVAL")
            planned = next(
                (
                    item
                    for item in research.get("planned_queries") or []
                    if item.get("plan_item_id") == item_id
                ),
                None,
            )
            if planned is None:
                raise ControllerError("unknown query-plan item")
            if planned.get("status") != "started":
                raise ControllerError("only an interrupted started query can be recovered")
            query_id = str(planned.get("query_id") or "")
            event = research.get("query_events", {}).get(query_id)
            if not query_id or not isinstance(event, dict) or event.get("status") != "started":
                raise ControllerError("query-plan item has no matching started gateway event")
            event["status"] = "interrupted_recovered"
            event["recovery_reason"] = scientific_reason
            planned["status"] = "planned"
            planned["retry_query_id"] = query_id
            planned.pop("query_id", None)
            query = str(planned.get("query") or "")
        append_jsonl(
            self._paths()["search_log"],
            ledger_event(
                run_id=self.run_id,
                stage="METADATA_RETRIEVAL",
                action="query_recovery",
                query_id=query_id,
                query=query,
                tool="arisctl.recover-interrupted-query",
                result_status="returned_to_plan",
                event_id=uuid.uuid4().hex,
                details={"plan_item_id": item_id, "reason": scientific_reason},
            ),
        )
        return {"plan_item_id": item_id, "query_id": query_id, "status": "planned"}

    @staticmethod
    def _reconcilable_query_plan_events(
        research: dict[str, Any],
    ) -> list[tuple[dict[str, Any], str, dict[str, Any]]]:
        """Find reset plan items that have one exact, terminal gateway event."""

        terminal_statuses = {"complete", "complete_human", "failed"}
        query_events = research.get("query_events") or {}
        matches: list[tuple[dict[str, Any], str, dict[str, Any]]] = []
        for planned in research.get("planned_queries") or []:
            if planned.get("status") != "planned" or not planned.get("plan_item_id"):
                continue
            expected_options = dict(planned.get("constraints") or {})
            candidates = [
                (str(query_id), event)
                for query_id, event in query_events.items()
                if isinstance(event, dict)
                and event.get("plan_item_id") == planned.get("plan_item_id")
                and event.get("query") == planned.get("query")
                and event.get("status") in terminal_statuses
                and all(
                    (event.get("query_options") or {}).get(key)
                    == expected_options.get(key)
                    for key in ("year_from", "year_to", "exact_title", "page")
                )
            ]
            if len(candidates) == 1:
                query_id, event = candidates[0]
                matches.append((planned, query_id, event))
        return matches

    def reconcile_query_plan_events(self, *, reason: str) -> dict[str, Any]:
        """Restore reset plan-item statuses from exact existing terminal events."""

        scientific_reason = str(reason or "").strip()
        if not scientific_reason:
            raise ControllerError("query-plan event reconciliation requires a reason")
        with self._store.mutate() as state:
            research = self._require_stage(state, "METADATA_RETRIEVAL")
            self._assert_artifact_current(research, "query_plan")
            matches = self._reconcilable_query_plan_events(research)
            if not matches:
                raise ControllerError(
                    "no reset query-plan item has one exact terminal gateway event"
                )
            reconciled: list[dict[str, str]] = []
            for planned, query_id, event in matches:
                event_status = str(event["status"])
                planned_status = "failed" if event_status == "failed" else "complete"
                planned["status"] = planned_status
                planned["query_id"] = query_id
                planned.pop("retry_query_id", None)
                reconciled.append(
                    {
                        "plan_item_id": str(planned["plan_item_id"]),
                        "query_id": query_id,
                        "event_status": event_status,
                        "plan_status": planned_status,
                    }
                )
            query_count = int(research["query_count"])
            paper_count = len(research.get("papers") or {})
        append_jsonl(
            self._paths()["search_log"],
            ledger_event(
                run_id=self.run_id,
                stage="METADATA_RETRIEVAL",
                action="query_plan_event_reconciliation",
                tool="arisctl.reconcile-query-plan-events",
                result_status="restored_from_terminal_gateway_events",
                event_id=uuid.uuid4().hex,
                details={
                    "reason": scientific_reason,
                    "reconciled": reconciled,
                    "query_count_unchanged": query_count,
                    "paper_count_unchanged": paper_count,
                },
            ),
        )
        return {
            "reconciled": reconciled,
            "query_count": query_count,
            "paper_count": paper_count,
        }

    def extend_literature_budget(
        self,
        *,
        max_fulltext_papers: int | None = None,
        max_queries: int | None = None,
        max_search_cycles: int | None = None,
        reason: str,
    ) -> dict[str, Any]:
        """Record an explicit, monotonic resource extension for an active literature run."""

        scientific_reason = str(reason or "").strip()
        if not scientific_reason:
            raise ControllerError("literature budget extension requires a reason")
        if max_fulltext_papers is None and max_queries is None and max_search_cycles is None:
            raise ControllerError("literature budget extension requires at least one new limit")
        with self._store.mutate() as state:
            research = state["research_lit"]
            stage = research.get("current_stage")
            active_cycle = stage in {
                "QUERY_PLANNING",
                "METADATA_RETRIEVAL",
                "HUMAN_SEARCH_REQUIRED",
                "PAPER_READING",
            }
            incremental_cycle_boundary = False
            if max_search_cycles is not None and stage == "LANDSCAPE_ACCEPTED":
                phase = self._current_core_phase(state)
                incremental_cycle_boundary = (
                    self._incremental_literature_active(research) is None
                    and self._incremental_literature_phase_allowed(state, phase)
                    and int(research["search_cycle_count"]) >= int(research["max_search_cycles"])
                )
            if not active_cycle and not incremental_cycle_boundary:
                raise ControllerError("literature budget can only be extended during an active literature cycle")
            if max_search_cycles is not None and not incremental_cycle_boundary:
                raise ControllerError(
                    "search-cycle budget extension requires a legal idle incremental retrieval boundary"
                )
            before = {
                "max_queries": int(research["max_queries"]),
                "max_fulltext_papers": int(research["max_fulltext_papers"]),
                "max_search_cycles": int(research["max_search_cycles"]),
            }
            if max_fulltext_papers is not None:
                if max_fulltext_papers <= before["max_fulltext_papers"]:
                    raise ControllerError("max_fulltext_papers extension must strictly increase the limit")
                research["max_fulltext_papers"] = int(max_fulltext_papers)
            if max_queries is not None:
                if max_queries <= before["max_queries"]:
                    raise ControllerError("max_queries extension must strictly increase the limit")
                research["max_queries"] = int(max_queries)
            if max_search_cycles is not None:
                if max_search_cycles <= before["max_search_cycles"]:
                    raise ControllerError("max_search_cycles extension must strictly increase the limit")
                research["max_search_cycles"] = int(max_search_cycles)
            after = {
                "max_queries": int(research["max_queries"]),
                "max_fulltext_papers": int(research["max_fulltext_papers"]),
                "max_search_cycles": int(research["max_search_cycles"]),
            }
        append_jsonl(
            self._paths()["search_log"],
            ledger_event(
                run_id=self.run_id,
                stage="METADATA_RETRIEVAL",
                action="budget_extension",
                tool="arisctl.extend-literature-budget",
                result_status="extended",
                event_id=uuid.uuid4().hex,
                budget_before=before,
                budget_after=after,
                details={"reason": scientific_reason},
            ),
        )
        return {"before": before, "after": after, "reason": scientific_reason}

    def _resume_after_provider_recovery(
        self, query: str, provider: str
    ) -> dict[str, Any]:
        credential_names = {
            "serpapi_google_scholar": "SERPAPI_KEY",
        }
        if not query:
            raise ControllerError("provider recovery requires the pending query")
        credential_name = credential_names.get(provider)
        if credential_name is None:
            raise ControllerError("provider cannot be re-enabled by credential recovery")
        if not os.getenv(credential_name, "").strip():
            raise ControllerError(f"{credential_name} is still missing")
        old_query_id: str
        with self._store.mutate() as state:
            research = self._require_stage(state, "HUMAN_SEARCH_REQUIRED")
            request = research.get("human_search_request")
            if not isinstance(request, dict) or request.get("query") != query:
                raise ControllerError("provider recovery does not match the pending query")
            attempted = {
                str(item.get("provider"))
                for item in request.get("provider_attempts") or []
                if isinstance(item, dict)
            }
            if provider not in attempted:
                raise ControllerError("provider was not unavailable for the pending query")
            planned = next(
                (item for item in research["planned_queries"] if item.get("query") == query),
                None,
            )
            if planned is None or planned.get("status") != "human_search_required":
                raise ControllerError("pending provider query is not resumable")
            old_query_id = str(planned.get("query_id") or "")
            for candidate in research["planned_queries"]:
                if candidate.get("status") == "human_search_required":
                    candidate["status"] = "planned"
                    candidate_id = str(candidate.get("query_id") or "")
                    candidate["retry_query_id"] = candidate_id
                    if candidate_id in research["query_events"]:
                        research["query_events"][candidate_id]["status"] = "planned"
            research["current_stage"] = "METADATA_RETRIEVAL"
            research["waiting_for"] = None
            research["human_search_request"] = None
        append_jsonl(
            self._paths()["search_log"],
            ledger_event(
                run_id=self.run_id,
                stage="HUMAN_SEARCH_REQUIRED",
                action="provider_reenabled",
                query_id=old_query_id,
                query=query,
                tool=provider,
                result_status="credential_available",
                event_id=uuid.uuid4().hex,
                details={"credential_name": credential_name},
            ),
        )
        return {
            "status": "PROVIDER_REENABLED",
            "provider": provider,
            "query": query,
            "next_stage": "METADATA_RETRIEVAL",
        }

    def register_user_source(self, metadata: dict[str, Any]) -> dict[str, Any]:
        paper_id = metadata.get("paper_id") or metadata.get("source_id")
        if not isinstance(paper_id, str) or not paper_id:
            raise ControllerError("user source metadata requires paper_id or source_id")
        source_path = metadata.get("source_path")
        if not isinstance(source_path, str) or not source_path:
            raise ControllerError("user source metadata requires source_path")
        source_root = (self.root / "source-materials").resolve()
        source = (self.root / source_path).resolve()
        try:
            source.relative_to(source_root)
        except ValueError as exc:
            raise ControllerError("user source must be inside source-materials/") from exc
        if not source.is_file():
            raise ControllerError("user source file does not exist")
        supplied_query_ids = metadata.get("found_by_query_ids") or []
        if (
            not isinstance(supplied_query_ids, list)
            or any(not isinstance(item, str) or not item.strip() for item in supplied_query_ids)
            or len(supplied_query_ids) != len(set(supplied_query_ids))
        ):
            raise ControllerError("user source found_by_query_ids must be unique non-empty query IDs")
        row = dict(metadata)
        row["source_id"] = paper_id
        row["source_origin"] = "user_supplied"
        row["found_by_query_ids"] = []
        row["admission_status"] = "USER_SUPPLIED_READ"
        row["screening_in_scope"] = True
        row["screening_status"] = "IN_SCOPE"
        row["screening_basis"] = "FULL_TEXT"
        row["screening_reason"] = str(
            metadata.get("screening_reason")
            or "user supplied this source for formal full-text reading"
        ).strip()
        row["reading_priority"] = str(
            metadata.get("reading_priority") or "TARGETED_GAP_FOLLOWUP"
        )
        if row["reading_priority"] not in READING_PRIORITY_TIERS:
            raise ControllerError("user source reading_priority is invalid")
        row["fulltext_selected"] = True
        row["fulltext_selection_reason"] = "user-supplied full text"
        row["screened_at"] = now()
        row["source_sha256"] = sha256_file(source)
        with self._store.mutate() as state:
            research = self._require_stage(state, "METADATA_RETRIEVAL")
            if paper_id in research["papers"]:
                raise ControllerError("paper_id is already registered")
            research["papers"][paper_id] = row
            session = self._incremental_literature_active(research)
            if session is not None:
                if session.get("phase") == "method_design":
                    plan = self._active_query_plan(research)
                    context = plan.get("method_design_context")
                    if isinstance(context, dict) and context.get("search_mode") == "PRINCIPLE_SEARCH":
                        plan_sha256 = str(session.get("query_plan_sha256") or "")
                        current_query_ids = {
                            query_id
                            for query_id, event in research.get("query_events", {}).items()
                            if isinstance(event, dict)
                            and event.get("query_plan_sha256") == plan_sha256
                            and event.get("status") in {"complete", "complete_human"}
                        }
                        if not supplied_query_ids or not set(supplied_query_ids) <= current_query_ids:
                            raise ControllerError(
                                "Principle-search user source requires explicit current completed query associations"
                            )
                        row["found_by_query_ids"] = sorted(supplied_query_ids)
                session.setdefault("paper_ids", []).append(paper_id)
        append_jsonl(self._paths()["literature_corpus"], row)
        append_jsonl(
            self._paths()["search_log"],
            ledger_event(
                run_id=self.run_id,
                stage="METADATA_RETRIEVAL",
                action="user_source",
                paper_id=paper_id,
                tool="arisctl.user_source",
                result_status="recorded",
                admission_decision="USER_SUPPLIED_READ",
                event_id=uuid.uuid4().hex,
            ),
        )
        return row

    def submit_human_fulltext_batch(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        """Register a single user-supplied local-file batch and resume reading.

        This does not manufacture evidence or mark the papers read.  It merely
        binds the requested papers to local files so the normal PAPER_READING and
        paper-reader evidence path can continue.
        """

        supplied = payload.get("papers")
        if not isinstance(supplied, list) or not supplied:
            raise ControllerError("human full-text batch requires a non-empty papers list")
        registered: list[dict[str, Any]] = []
        with self._store.mutate() as state:
            research = self._require_stage(state, "HUMAN_SEARCH_REQUIRED")
            request = research.get("human_fulltext_request")
            if not isinstance(request, dict):
                raise ControllerError("no human full-text batch is pending")
            expected = {
                str(item.get("paper_id"))
                for item in request.get("papers") or []
                if isinstance(item, dict) and item.get("paper_id")
            }
            supplied_by_id: dict[str, dict[str, Any]] = {}
            source_root = (self.root / "source-materials").resolve()
            for item in supplied:
                if not isinstance(item, dict):
                    raise ControllerError("each human full-text batch item must be an object")
                paper_id = str(item.get("paper_id") or "").strip()
                source_path = item.get("source_path")
                if not paper_id or not isinstance(source_path, str) or not source_path:
                    raise ControllerError("each human full-text batch item needs paper_id and source_path")
                if paper_id not in expected or paper_id in supplied_by_id:
                    raise ControllerError("human full-text batch must match each requested paper once")
                source = (self.root / source_path).resolve()
                try:
                    source.relative_to(source_root)
                except ValueError as exc:
                    raise ControllerError("user full-text files must be inside source-materials/") from exc
                if not source.is_file() or source.stat().st_size == 0:
                    raise ControllerError(f"user full-text file does not exist for {paper_id}")
                supplied_by_id[paper_id] = {
                    "paper_id": paper_id,
                    "source_path": str(source.relative_to(self.root)),
                    "source_sha256": sha256_file(source),
                    "media_type": item.get("media_type"),
                }
            if set(supplied_by_id) != expected:
                raise ControllerError("human full-text batch must cover every requested paper")
            for paper_id, item in supplied_by_id.items():
                paper = research["papers"].get(paper_id)
                if not paper:
                    raise ControllerError(f"human full-text request references an unknown paper: {paper_id}")
                paper["user_fulltext"] = item
                paper.pop("fulltext_failure", None)
                registered.append(dict(item))
            research["human_fulltext_request"] = None
            research["current_stage"] = "PAPER_READING"
            research["waiting_for"] = None
        for item in registered:
            append_jsonl(
                self._paths()["search_log"],
                ledger_event(
                    run_id=self.run_id,
                    stage="HUMAN_SEARCH_REQUIRED",
                    action="human_fulltext_source",
                    paper_id=item["paper_id"],
                    tool="arisctl.human_fulltext_batch",
                    result_status="registered",
                    event_id=uuid.uuid4().hex,
                    artifact_sha256=item["source_sha256"],
                    details={
                        "source_path": item["source_path"],
                        "media_type": item.get("media_type"),
                    },
                ),
            )
        return registered

    def promote_user_source(
        self,
        paper_id: str,
        *,
        source_path: str,
        reason: str,
        media_type: str | None = None,
        identity_verifier: MetadataVerifyCallable | None = None,
        identity_tool: str = "crossref_metadata",
    ) -> dict[str, Any]:
        """Bind later user-supplied full text to a known discovery-only paper.

        This is a non-advancing correction for material that the user supplies
        after metadata discovery.  It preserves discovery provenance while
        moving the paper onto the policy's explicit user-supplied reading track.
        """

        scientific_reason = str(reason or "").strip()
        if not scientific_reason:
            raise ControllerError("user-source promotion requires a reason")
        if not isinstance(source_path, str) or not source_path.strip():
            raise ControllerError("user-source promotion requires source_path")
        source_root = (self.root / "source-materials").resolve()
        source = (self.root / source_path).resolve()
        try:
            source.relative_to(source_root)
        except ValueError as exc:
            raise ControllerError("user full-text files must be inside source-materials/") from exc
        if not source.is_file() or source.stat().st_size == 0:
            raise ControllerError("user full-text file does not exist")

        with self._store.mutate() as state:
            research = state["research_lit"]
            stage = research["current_stage"]
            if stage not in {"PAPER_READING", "HUMAN_SEARCH_REQUIRED"}:
                raise ControllerError(
                    "user-source promotion requires PAPER_READING or a pending human full-text batch"
                )
            if stage == "HUMAN_SEARCH_REQUIRED" and not isinstance(
                research.get("human_fulltext_request"), dict
            ):
                raise ControllerError(
                    "user-source promotion during HUMAN_SEARCH_REQUIRED requires a pending full-text batch"
                )
            try:
                paper = research["papers"][paper_id]
            except KeyError as exc:
                raise ControllerError(f"unknown paper_id {paper_id!r}") from exc
            if paper.get("screening_status") != "IN_SCOPE" or paper.get("duplicate"):
                raise ControllerError("user-source promotion requires a current in-scope discovery paper")
            if f"evidence:{paper_id}" in research["accepted_artifacts"]:
                raise ControllerError("cannot promote a paper with an accepted Evidence Card")
            if paper.get("admission_status") in READABLE_ADMISSION_STATUSES:
                raise ControllerError("paper is already on a readable admission track")
            if paper.get("admission_status") not in {
                "DISCOVERY_METADATA_ONLY",
                "ADMIT_DISCOVERY_ONLY",
                "HOLD_IDENTITY",
            }:
                raise ControllerError("only a discovery-only paper can be promoted by user supply")
            snapshot = dict(paper)

        identity_result: dict[str, Any] | None = None
        if snapshot.get("identity_status") != "verified":
            if identity_verifier is None:
                raise ControllerError("user-source promotion requires verified paper identity")
            candidate = identity_verifier(snapshot)
            if not isinstance(candidate, dict) or candidate.get("identity_status") != "verified":
                raise ControllerError("user-source promotion did not produce a verified identity")
            identity_result = candidate

        registration = {
            "paper_id": paper_id,
            "source_path": str(source.relative_to(self.root)),
            "source_sha256": sha256_file(source),
            "media_type": media_type,
        }
        identity_fields = {
            "identity_status",
            "identity_provider",
            "identity_reason",
            "title",
            "authors",
            "year",
            "venue",
            "doi",
            "doi_or_stable_url",
            "publication_type",
            "abstract",
            "abstract_source",
        }
        with self._store.mutate() as state:
            research = state["research_lit"]
            paper = research["papers"].get(paper_id)
            if not isinstance(paper, dict) or paper.get("admission_status") not in {
                "DISCOVERY_METADATA_ONLY",
                "ADMIT_DISCOVERY_ONLY",
                "HOLD_IDENTITY",
            }:
                raise ControllerError("paper changed during user-source promotion")
            if f"evidence:{paper_id}" in research["accepted_artifacts"]:
                raise ControllerError("cannot promote a paper with an accepted Evidence Card")
            if identity_result is not None:
                paper.update(
                    {key: value for key, value in identity_result.items() if key in identity_fields}
                )
                paper["identity_verification_status"] = "complete"
            paper["admission_status"] = "USER_SUPPLIED_READ"
            paper["user_fulltext"] = registration
            paper["user_supply_transition"] = {
                "reason": scientific_reason,
                "recorded_at": now(),
                "prior_source_origin": paper.get("source_origin"),
            }
            paper.pop("fulltext_failure", None)
            corpus_row = dict(paper)
            ledger_stage = research["current_stage"]
        append_jsonl(self._paths()["literature_corpus"], corpus_row)
        append_jsonl(
            self._paths()["search_log"],
            ledger_event(
                run_id=self.run_id,
                stage=ledger_stage,
                action="user_source_promotion",
                paper_id=paper_id,
                tool="arisctl.promote-user-source",
                result_status="registered",
                admission_decision="USER_SUPPLIED_READ",
                event_id=uuid.uuid4().hex,
                artifact_sha256=registration["source_sha256"],
                details={
                    "reason": scientific_reason,
                    "source_path": registration["source_path"],
                    "media_type": media_type,
                    "identity_tool": identity_tool if identity_result is not None else None,
                    "prior_source_origin": corpus_row["user_supply_transition"][
                        "prior_source_origin"
                    ],
                },
            ),
        )
        return corpus_row

    def repair_literature_corpus_hash_chain(self, *, reason: str) -> dict[str, Any]:
        """Repair the recognized legacy embedded-receipt writer defect only."""

        repair_reason = str(reason or "").strip()
        if not repair_reason:
            raise ControllerError("registry hash-chain repair requires a reason")
        with self._store.mutate() as state:
            research = self._require_stage(state, "COVERAGE_REVIEW")
            if not isinstance(research.get("coverage_review_request"), dict):
                raise ControllerError("registry repair requires a live coverage review request")
        corpus = self._paths()["literature_corpus"]
        before_sha256 = sha256_file(corpus)
        archive = (
            self.root
            / ".aris"
            / "repair-history"
            / self.run_id
            / f"literature-corpus-before-{before_sha256}.jsonl"
        )
        archive.parent.mkdir(parents=True, exist_ok=True)
        if not archive.exists():
            shutil.copy2(corpus, archive)
        try:
            result = repair_embedded_record_hash_contamination(corpus)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise ControllerError(str(exc)) from exc
        after_sha256 = sha256_file(corpus)
        with self._store.mutate() as state:
            for paper in state["research_lit"]["papers"].values():
                if isinstance(paper, dict):
                    paper.pop("previous_record_sha256", None)
                    paper.pop("record_sha256", None)
        append_jsonl(
            self._paths()["search_log"],
            ledger_event(
                run_id=self.run_id,
                stage="COVERAGE_REVIEW",
                action="literature_corpus_hash_chain_repair",
                tool="arisctl.repair-literature-corpus-hash-chain",
                result_status="repaired_recognized_writer_defect",
                event_id=uuid.uuid4().hex,
                details={
                    "reason": repair_reason,
                    "before_sha256": before_sha256,
                    "after_sha256": after_sha256,
                    "archive_path": str(archive.relative_to(self.root)),
                    **result,
                },
            ),
        )
        return {
            **result,
            "before_sha256": before_sha256,
            "after_sha256": after_sha256,
            "archive_path": str(archive.relative_to(self.root)),
        }

    def read_registered_user_fulltext(self, paper_id: str) -> dict[str, Any]:
        """Read a batch-registered local file through the normal evidence gate."""

        with self._store.mutate() as state:
            research = self._require_stage(state, "PAPER_READING")
            paper = research["papers"].get(paper_id)
            if not self._paper_readable_in_active_session(research, paper_id):
                raise ControllerError("user full-text read is outside the active readable subset")
            registration = paper.get("user_fulltext") if isinstance(paper, dict) else None
            if not isinstance(registration, dict):
                raise ControllerError("paper has no registered user-supplied full text")
            source_path = registration.get("source_path")
            expected_hash = registration.get("source_sha256")
            if not isinstance(source_path, str) or not isinstance(expected_hash, str):
                raise ControllerError("registered user full-text provenance is invalid")
            source = (self.root / source_path).resolve()
            source_root = (self.root / "source-materials").resolve()
            try:
                source.relative_to(source_root)
            except ValueError as exc:
                raise ControllerError("registered user full-text file is outside source-materials/") from exc
            if not source.is_file() or sha256_file(source) != expected_hash:
                raise ControllerError("registered user full-text file changed or is unavailable")
            media_type = str(registration.get("media_type") or "application/octet-stream")

        return self.read_full_text(
            paper_id,
            "arisctl.read-user-fulltext",
            lambda _: FullTextPayload(
                source.read_bytes(),
                source.as_uri(),
                media_type,
                "user_supplied_local",
            ),
        )

    def materialize_completed_read_event(
        self, paper_id: str, read_event_id: str
    ) -> dict[str, Any]:
        """Return verified existing full text for one already-completed read event.

        This is a non-transitioning handoff for a native paper_reader continuing
        a historical checkpoint.  It preserves the original event identity and
        never allocates a replacement read event or touches the full-text budget.
        """

        self._require_formal_native_runtime("paper_reader")
        state = self._store.load()
        research = self._require_stage(state, "PAPER_READING")
        paper = research["papers"].get(paper_id)
        if not isinstance(paper, dict) or not self._paper_readable_in_active_session(
            research, paper_id
        ):
            raise ControllerError("completed read-event handoff is outside the active readable subset")
        event = research.get("read_events", {}).get(read_event_id)
        if (
            not isinstance(event, dict)
            or event.get("paper_id") != paper_id
            or event.get("status") != "complete"
        ):
            raise ControllerError("completed read-event handoff requires the original completed event")
        registration = paper.get("user_fulltext")
        if not isinstance(registration, dict):
            raise ControllerError("completed read-event handoff requires registered user full text")
        source_path = registration.get("source_path")
        source_sha256 = registration.get("source_sha256")
        if (
            not isinstance(source_path, str)
            or not isinstance(source_sha256, str)
            or source_sha256 != event.get("content_sha256")
        ):
            raise ControllerError("completed read-event source binding is invalid")
        source = (self.root / source_path).resolve()
        source_root = (self.root / "source-materials").resolve()
        try:
            source.relative_to(source_root)
        except ValueError as exc:
            raise ControllerError("completed read-event source is outside source-materials/") from exc
        if not source.is_file():
            raise ControllerError("completed read-event source is unavailable")
        source_content = source.read_bytes()
        if hashlib.sha256(source_content).hexdigest() != source_sha256:
            raise ControllerError("completed read-event source changed")
        media_type = str(registration.get("media_type") or "").casefold()
        if media_type == "application/pdf" or source.suffix.casefold() == ".pdf":
            executable = shutil.which("pdftotext")
            if executable is None:
                raise ControllerError("completed read-event PDF handoff requires pdftotext")
            extracted = subprocess.run(
                [executable, "-layout", "-", "-"],
                input=source_content,
                capture_output=True,
                timeout=120,
            )
            if extracted.returncode != 0 or not extracted.stdout.strip():
                detail = extracted.stderr.decode("utf-8", errors="replace").strip()
                raise ControllerError(
                    "completed read-event PDF text extraction failed"
                    + (f": {detail[:200]}" if detail else "")
                )
            content = extracted.stdout.decode("utf-8", errors="replace")
        else:
            try:
                content = source_content.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ControllerError(
                    "completed read-event content is not reader-deliverable text"
                ) from exc
        return {
            "paper_id": paper_id,
            "read_event_id": read_event_id,
            "content_sha256": source_sha256,
            "content": content,
        }

    def _load_policy(self) -> dict[str, Any]:
        policy_path = self._paths()["source_admission_policy"]
        try:
            policy = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise ControllerError(f"source admission policy is invalid YAML: {exc}") from exc
        if not isinstance(policy, dict):
            raise ControllerError("source admission policy must be a YAML object")
        return policy

    @staticmethod
    def _elite_venues(policy: dict[str, Any]) -> set[str]:
        groups: list[Any] = []
        top_level = policy.get("approved_elite_venues") or []
        if isinstance(top_level, dict):
            for entries in top_level.values():
                if isinstance(entries, list):
                    groups.extend(entries)
        elif isinstance(top_level, list):
            groups.extend(top_level)
        for field in policy.get("fields") or []:
            groups.extend((field or {}).get("approved_elite_venues") or [])
        venues: set[str] = set()
        for item in groups:
            if isinstance(item, dict):
                names = [item.get("canonical_name"), *(item.get("aliases") or [])]
                venues.update(str(name).casefold() for name in names if name)
        return venues

    @classmethod
    def _venue_eligible(cls, policy: dict[str, Any], raw_venue: Any) -> bool:
        venue = " ".join(
            re.sub(r"[^a-z0-9]+", " ", str(raw_venue or "").casefold()).split()
        )
        if not venue:
            return False
        groups: list[Any] = []
        top_level = policy.get("approved_elite_venues") or []
        if isinstance(top_level, dict):
            for entries in top_level.values():
                if isinstance(entries, list):
                    groups.extend(entries)
        elif isinstance(top_level, list):
            groups.extend(top_level)
        for field in policy.get("fields") or []:
            groups.extend((field or {}).get("approved_elite_venues") or [])

        def normalize(value: Any) -> str:
            return " ".join(
                re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).split()
            )

        venue_without_year = re.sub(r"^\d{4}\s+", "", venue)
        for item in groups:
            if not isinstance(item, dict):
                continue
            canonical = normalize(item.get("canonical_name"))
            if canonical and (
                venue == canonical
                or venue_without_year == canonical
                or venue.startswith(canonical + " ")
                or venue_without_year.startswith(canonical + " ")
            ):
                return True
            for alias in item.get("aliases") or []:
                normalized_alias = normalize(alias)
                if normalized_alias and re.search(
                    rf"(?<![a-z0-9]){re.escape(normalized_alias)}(?![a-z0-9])",
                    venue,
                ):
                    return True
        return False

    @staticmethod
    def _citation_eligible(policy: dict[str, Any], paper: dict[str, Any]) -> bool:
        count = paper.get("citation_count")
        year = paper.get("year")
        if not isinstance(count, (int, float)):
            return False
        rule = policy.get("high_citation_rule") or {}
        for threshold in rule.get("thresholds") or []:
            minimum = threshold.get("publication_year_min", -10**9)
            maximum = threshold.get("publication_year_max", 10**9)
            if isinstance(year, int) and minimum <= year <= maximum:
                return count > threshold["citation_count_strictly_greater_than"]
        fixed = policy.get("non_elite_citation_threshold_exclusive")
        return isinstance(fixed, (int, float)) and count > fixed

    def decide_admission(
        self,
        paper_id: str,
        *,
        screening_in_scope: bool,
        duplicate: bool = False,
        screening_basis: str | None = None,
        screening_reason: str | None = None,
        reading_priority: str | None = None,
        fulltext_selected: bool = True,
        fulltext_selection_reason: str | None = None,
        decision_grade_exception: str | None = None,
        exception_reason: str | None = None,
        decision_targets: list[str] | None = None,
        identity_verifier: MetadataVerifyCallable | None = None,
        identity_tool: str = "crossref_metadata",
    ) -> str:
        explicit_screening = any(
            value is not None
            for value in (screening_basis, screening_reason, reading_priority)
        )
        if explicit_screening:
            if screening_basis not in SCREENING_BASES:
                raise ControllerError("screening_basis must identify title, abstract, or full-text review")
            if not str(screening_reason or "").strip():
                raise ControllerError("candidate screening requires a scientific inclusion/exclusion reason")
            if reading_priority not in READING_PRIORITY_TIERS:
                raise ControllerError("candidate screening requires a canonical reading priority")
            if screening_in_scope and not duplicate and screening_basis == "TITLE_ONLY":
                raise ControllerError("in-scope candidates require title-and-abstract screening")
            if (
                screening_in_scope
                and not duplicate
                and not fulltext_selected
                and not str(fulltext_selection_reason or "").strip()
            ):
                raise ControllerError(
                    "abstract-only retention requires a reason for not selecting full text"
                )
        exception: dict[str, Any] | None = None
        if decision_grade_exception is not None:
            if decision_grade_exception not in DECISION_GRADE_EXCEPTION_KINDS:
                raise ControllerError("unknown decision-grade admission exception")
            reason = str(exception_reason or "").strip()
            targets = sorted(
                {
                    str(target).strip()
                    for target in decision_targets or []
                    if str(target).strip()
                }
            )
            if not reason or not targets:
                raise ControllerError(
                    "decision-grade admission exception requires a scientific reason "
                    "and at least one explicit decision target"
                )
            exception = {
                "kind": decision_grade_exception,
                "reason": reason,
                "decision_targets": targets,
            }
        # Obvious scope exclusions and duplicates do not consume an identity
        # verification call. Every in-scope candidate still passes the formal
        # identity gate before it can be selected for reading.
        accepted_evidence_reuse = (
            screening_basis == "FULL_TEXT"
            and f"evidence:{paper_id}"
            in self.status().get("research_lit", {}).get("accepted_artifacts", {})
        )
        abstract_unavailable_reuse = (
            screening_basis == "TITLE_ONLY_ABSTRACT_UNAVAILABLE"
            and self.status()
            .get("research_lit", {})
            .get("papers", {})
            .get(paper_id, {})
            .get("identity_verification_status")
            == "complete"
        )
        if (
            identity_verifier is not None
            and screening_in_scope
            and not duplicate
            and not accepted_evidence_reuse
            and not abstract_unavailable_reuse
        ):
            self._verify_metadata_identity(paper_id, identity_tool, identity_verifier)
        policy = self._load_policy()
        with self._store.mutate() as state:
            research = self._require_stage(state, "METADATA_RETRIEVAL")
            self._assert_artifact_current(research, "source_admission_policy")
            try:
                paper = research["papers"][paper_id]
            except KeyError as exc:
                raise ControllerError(f"unknown paper_id {paper_id!r}") from exc
            if explicit_screening and screening_basis == "TITLE_ABSTRACT":
                if not str(paper.get("abstract") or "").strip():
                    raise ControllerError(
                        "TITLE_ABSTRACT screening requires a retrieved abstract, not only a search snippet"
                    )
            if explicit_screening and screening_basis == "TITLE_ONLY_ABSTRACT_UNAVAILABLE":
                if paper.get("identity_status") != "verified":
                    raise ControllerError(
                        "abstract-unavailable screening requires verified identity"
                    )
                if paper.get("identity_verification_status") != "complete":
                    raise ControllerError(
                        "abstract-unavailable screening requires a completed metadata enrichment attempt"
                    )
                if str(paper.get("abstract") or "").strip():
                    raise ControllerError(
                        "use TITLE_ABSTRACT when an abstract is available"
                    )
            if explicit_screening and screening_basis == "FULL_TEXT":
                accepted_evidence = (
                    f"evidence:{paper_id}" in research.get("accepted_artifacts", {})
                )
                if (
                    not paper.get("user_fulltext")
                    and not paper.get("fulltext_screened")
                    and not accepted_evidence
                ):
                    raise ControllerError("FULL_TEXT screening requires a registered local full text")

            citation_eligible = self._citation_eligible(policy, paper)
            source_eligible = self._venue_eligible(policy, paper.get("venue")) or citation_eligible

            if paper.get("source_origin") == "user_supplied":
                decision = "USER_SUPPLIED_READ"
            elif duplicate:
                decision = "EXCLUDE_DUPLICATE"
            elif not screening_in_scope:
                decision = "EXCLUDE_IRRELEVANT"
            elif f"evidence:{paper_id}" in research.get("accepted_artifacts", {}):
                # A prior accepted Evidence Card is already the formal output of
                # a completed full-text read.  Re-screen it without scheduling a
                # duplicate read, while still allowing an explicit new-scope
                # exclusion in the branch above.
                decision = "ADMIT_DECISION_GRADE"
            elif paper.get("identity_status") != "verified":
                decision = "HOLD_IDENTITY"
            else:
                if (
                    explicit_screening
                    and reading_priority == "HIGH_CITATION_BACKBONE"
                    and not citation_eligible
                ):
                    raise ControllerError(
                        "HIGH_CITATION_BACKBONE requires the source-policy high-citation threshold"
                    )
                if (
                    explicit_screening
                    and fulltext_selected
                    and not source_eligible
                    and exception is None
                ):
                    raise ControllerError(
                        "selected full-text reading requires source-policy eligibility or a declared exception"
                    )
                if source_eligible and fulltext_selected:
                    decision = "ADMIT_FOR_READING"
                    paper.pop("admission_exception", None)
                elif exception is not None and fulltext_selected:
                    decision = "ADMIT_FOR_READING"
                    paper["admission_exception"] = {
                        **exception,
                        "recorded_at": now(),
                    }
                else:
                    decision = "ADMIT_DISCOVERY_ONLY"
                    paper.pop("admission_exception", None)
            paper["admission_status"] = decision
            paper["screening_in_scope"] = screening_in_scope
            if explicit_screening:
                paper["screening_status"] = (
                    "DUPLICATE"
                    if duplicate
                    else "IN_SCOPE"
                    if screening_in_scope
                    else "OUT_OF_SCOPE"
                )
                paper["screening_basis"] = screening_basis
                paper["screening_reason"] = str(screening_reason).strip()
                paper["reading_priority"] = reading_priority
                paper["fulltext_selected"] = bool(
                    fulltext_selected and screening_in_scope and not duplicate
                )
                paper["fulltext_selection_reason"] = (
                    str(fulltext_selection_reason).strip()
                    if fulltext_selection_reason
                    else None
                )
                paper["screened_at"] = now()
            else:
                # Preserve programmatic backward compatibility, but do not let
                # an unrecorded legacy decision close retrieval or coverage.
                paper["screening_status"] = "UNRESOLVED"
        corpus_row = dict(paper)
        append_jsonl(self._paths()["literature_corpus"], corpus_row)
        append_jsonl(
            self._paths()["search_log"],
            ledger_event(
                run_id=self.run_id,
                stage="METADATA_RETRIEVAL",
                action="admission",
                paper_id=paper_id,
                tool="arisctl.admission",
                result_status="decided",
                admission_decision=decision,
                event_id=uuid.uuid4().hex,
                details={
                    "admission_exception": paper.get("admission_exception"),
                    "screening_status": paper.get("screening_status"),
                    "screening_basis": paper.get("screening_basis"),
                    "reading_priority": paper.get("reading_priority"),
                    "fulltext_selected": paper.get("fulltext_selected"),
                },
            ),
        )
        return decision

    def withdraw_admission(self, paper_id: str, *, reason: str) -> str:
        """Withdraw an admitted paper before its Evidence Card is accepted."""

        scientific_reason = str(reason or "").strip()
        if not scientific_reason:
            raise ControllerError("admission withdrawal requires a reason")
        with self._store.mutate() as state:
            research = state["research_lit"]
            stage = research["current_stage"]
            if stage not in {"PAPER_READING", "HUMAN_SEARCH_REQUIRED"}:
                raise ControllerError(
                    "admission withdrawal requires PAPER_READING or a pending human full-text batch"
                )
            if stage == "HUMAN_SEARCH_REQUIRED" and not isinstance(
                research.get("human_fulltext_request"), dict
            ):
                raise ControllerError(
                    "admission withdrawal during HUMAN_SEARCH_REQUIRED requires a pending full-text batch"
                )
            try:
                paper = research["papers"][paper_id]
            except KeyError as exc:
                raise ControllerError(f"unknown paper_id {paper_id!r}") from exc
            if paper.get("admission_status") not in READABLE_ADMISSION_STATUSES:
                raise ControllerError("only an admitted paper can be withdrawn")
            if f"evidence:{paper_id}" in research["accepted_artifacts"]:
                raise ControllerError("cannot withdraw a paper with an accepted Evidence Card")

            paper["admission_status"] = "EXCLUDE_USER_WITHDRAWN"
            paper["admission_withdrawal"] = {
                "reason": scientific_reason,
                "recorded_at": now(),
            }
            request = research.get("human_fulltext_request")
            if isinstance(request, dict):
                request["papers"] = [
                    item
                    for item in request.get("papers") or []
                    if isinstance(item, dict) and item.get("paper_id") != paper_id
                ]
                if not request["papers"]:
                    research["human_fulltext_request"] = None
                    research["current_stage"] = "PAPER_READING"
                    research["waiting_for"] = None
            corpus_row = dict(paper)
            ledger_stage = stage
        append_jsonl(self._paths()["literature_corpus"], corpus_row)
        append_jsonl(
            self._paths()["search_log"],
            ledger_event(
                run_id=self.run_id,
                stage=ledger_stage,
                action="admission_withdrawal",
                paper_id=paper_id,
                tool="arisctl.withdraw-admission",
                result_status="decided",
                admission_decision="EXCLUDE_USER_WITHDRAWN",
                event_id=uuid.uuid4().hex,
                details={"reason": scientific_reason},
            ),
        )
        return "EXCLUDE_USER_WITHDRAWN"

    def reverify_admission(
        self,
        paper_id: str,
        *,
        reason: str,
        identity_verifier: MetadataVerifyCallable,
        identity_tool: str = "crossref_metadata",
    ) -> dict[str, Any]:
        """Correct a verified admitted identity before evidence acceptance."""

        correction_reason = str(reason or "").strip()
        if not correction_reason:
            raise ControllerError("admission identity correction requires a reason")
        with self._store.mutate() as state:
            research = state["research_lit"]
            stage = research["current_stage"]
            if stage not in {"PAPER_READING", "HUMAN_SEARCH_REQUIRED"}:
                raise ControllerError(
                    "admission identity correction requires PAPER_READING or a pending human full-text batch"
                )
            if stage == "HUMAN_SEARCH_REQUIRED" and not isinstance(
                research.get("human_fulltext_request"), dict
            ):
                raise ControllerError(
                    "identity correction during HUMAN_SEARCH_REQUIRED requires a pending full-text batch"
                )
            try:
                paper = research["papers"][paper_id]
            except KeyError as exc:
                raise ControllerError(f"unknown paper_id {paper_id!r}") from exc
            if paper.get("admission_status") not in READABLE_ADMISSION_STATUSES:
                raise ControllerError("only an admitted paper can be reverified")
            if f"evidence:{paper_id}" in research["accepted_artifacts"]:
                raise ControllerError("cannot correct a paper with an accepted Evidence Card")
            snapshot = dict(paper)
        result = identity_verifier(snapshot)
        if not isinstance(result, dict) or result.get("identity_status") != "verified":
            raise ControllerError("admission identity correction did not produce a verified identity")
        allowed = {
            "identity_status",
            "identity_provider",
            "identity_reason",
            "title",
            "authors",
            "year",
            "venue",
            "doi",
            "doi_or_stable_url",
            "publication_type",
        }
        previous = {key: snapshot.get(key) for key in allowed if key in snapshot}
        with self._store.mutate() as state:
            research = state["research_lit"]
            paper = research["papers"].get(paper_id)
            if not isinstance(paper, dict) or paper.get("admission_status") not in READABLE_ADMISSION_STATUSES:
                raise ControllerError("admitted paper changed during identity correction")
            if f"evidence:{paper_id}" in research["accepted_artifacts"]:
                raise ControllerError("cannot correct a paper with an accepted Evidence Card")
            paper.update({key: value for key, value in result.items() if key in allowed})
            paper["identity_verification_status"] = "complete"
            paper["identity_correction"] = {
                "reason": correction_reason,
                "previous": previous,
                "corrected": {key: paper.get(key) for key in allowed if key in paper},
                "recorded_at": now(),
            }
            corpus_row = dict(paper)
            ledger_stage = research["current_stage"]
        append_jsonl(self._paths()["literature_corpus"], corpus_row)
        append_jsonl(
            self._paths()["search_log"],
            ledger_event(
                run_id=self.run_id,
                stage=ledger_stage,
                action="admission_identity_correction",
                paper_id=paper_id,
                tool=identity_tool,
                result_status="verified",
                admission_decision=str(corpus_row["admission_status"]),
                event_id=uuid.uuid4().hex,
                details={
                    "reason": correction_reason,
                    "previous_doi": previous.get("doi"),
                    "corrected_doi": corpus_row.get("doi"),
                },
            ),
        )
        return corpus_row["identity_correction"]

    def _verify_metadata_identity(
        self,
        paper_id: str,
        tool: str,
        verify: MetadataVerifyCallable,
    ) -> None:
        with self._store.mutate() as state:
            research = self._require_stage(state, "METADATA_RETRIEVAL")
            try:
                paper = research["papers"][paper_id]
            except KeyError as exc:
                raise ControllerError(f"unknown paper_id {paper_id!r}") from exc
            if paper.get("source_origin") == "user_supplied":
                return
            verified_and_complete = (
                paper.get("identity_status") == "verified"
                and isinstance(paper.get("year"), int)
                and bool(str(paper.get("abstract") or "").strip())
            )
            if verified_and_complete:
                return
            if (
                paper.get("identity_verification_event_id")
                and paper.get("identity_verification_status") == "complete"
                and paper.get("identity_status") != "verified"
            ):
                return
            snapshot = dict(paper)
            event_id = uuid.uuid4().hex
            paper["identity_verification_event_id"] = event_id
            paper["identity_verification_status"] = "started"
        append_jsonl(
            self._paths()["search_log"],
            ledger_event(
                run_id=self.run_id,
                stage="METADATA_RETRIEVAL",
                action="metadata_identity_verification",
                paper_id=paper_id,
                tool=tool,
                result_status="started",
                event_id=event_id,
            ),
        )

        try:
            result = verify(snapshot)
            if not isinstance(result, dict) or result.get("identity_status") not in {
                "verified",
                "verify_failed",
            }:
                raise ControllerError("metadata verifier returned an invalid identity result")
        except Exception as exc:
            with self._store.mutate() as state:
                paper = state["research_lit"]["papers"][paper_id]
                paper["identity_verification_status"] = "failed"
                paper["identity_verification_error"] = type(exc).__name__
            append_jsonl(
                self._paths()["search_log"],
                ledger_event(
                    run_id=self.run_id,
                    stage="METADATA_RETRIEVAL",
                    action="metadata_identity_verification",
                    paper_id=paper_id,
                    tool=tool,
                    result_status="failed",
                    event_id=event_id,
                    details={"error_type": type(exc).__name__},
                ),
            )
            raise
        allowed = {
            "identity_status",
            "identity_provider",
            "identity_reason",
            "title",
            "authors",
            "year",
            "venue",
            "doi",
            "doi_or_stable_url",
            "publication_type",
            "abstract",
            "abstract_source",
        }
        with self._store.mutate() as state:
            paper = state["research_lit"]["papers"][paper_id]
            paper.update({key: value for key, value in result.items() if key in allowed})
            paper["identity_verification_status"] = "complete"
            corpus_row = dict(paper)
        append_jsonl(self._paths()["literature_corpus"], corpus_row)
        append_jsonl(
            self._paths()["search_log"],
            ledger_event(
                run_id=self.run_id,
                stage="METADATA_RETRIEVAL",
                action="metadata_identity_verification",
                paper_id=paper_id,
                tool=tool,
                result_status=str(result["identity_status"]),
                event_id=event_id,
                details={"identity_provider": result.get("identity_provider")},
            ),
        )

    def enrich_candidate_metadata(
        self,
        paper_id: str,
        *,
        identity_verifier: MetadataVerifyCallable,
        identity_tool: str = "crossref_openalex_metadata",
    ) -> dict[str, Any]:
        """Retrieve decision inputs before title/abstract screening is recorded."""

        state = self.status()
        research = self._require_stage(state, "METADATA_RETRIEVAL")
        if paper_id not in research.get("papers", {}):
            raise ControllerError(f"unknown paper_id {paper_id!r}")
        self._verify_metadata_identity(paper_id, identity_tool, identity_verifier)
        paper = self.status()["research_lit"]["papers"][paper_id]
        return {
            key: paper.get(key)
            for key in (
                "source_id",
                "title",
                "authors",
                "year",
                "venue",
                "doi",
                "doi_or_stable_url",
                "citation_count",
                "abstract",
                "abstract_source",
                "identity_status",
            )
        }

    def retry_candidate_metadata_enrichment(
        self,
        paper_id: str,
        *,
        reason: str,
        identity_verifier: MetadataVerifyCallable,
        identity_tool: str = "crossref_openalex_arxiv_metadata",
    ) -> dict[str, Any]:
        retry_reason = str(reason or "").strip()
        if not retry_reason:
            raise ControllerError("metadata enrichment retry requires a reason")
        with self._store.mutate() as state:
            research = self._require_stage(state, "METADATA_RETRIEVAL")
            try:
                paper = research["papers"][paper_id]
            except KeyError as exc:
                raise ControllerError(f"unknown paper_id {paper_id!r}") from exc
            retryable = paper.get("identity_status") == "verify_failed" or (
                paper.get("identity_verification_status") == "complete"
                and not str(paper.get("abstract") or "").strip()
            )
            if not retryable:
                raise ControllerError(
                    "metadata enrichment retry requires a prior failed identity or missing abstract"
                )
            prior_event_id = paper.get("identity_verification_event_id")
            paper.pop("identity_verification_event_id", None)
            paper.pop("identity_verification_status", None)
            paper.pop("identity_verification_error", None)
        append_jsonl(
            self._paths()["search_log"],
            ledger_event(
                run_id=self.run_id,
                stage="METADATA_RETRIEVAL",
                action="metadata_enrichment_retry",
                paper_id=paper_id,
                tool="arisctl.retry-candidate-enrichment",
                result_status="retry_authorized",
                event_id=uuid.uuid4().hex,
                details={"reason": retry_reason, "prior_event_id": prior_event_id},
            ),
        )
        return self.enrich_candidate_metadata(
            paper_id,
            identity_verifier=identity_verifier,
            identity_tool=identity_tool,
        )

    def _reconcile_accepted_evidence_papers(self, research: dict[str, Any]) -> list[str]:
        """Recover a paper record only when its accepted Evidence proves a later rollback."""
        evidence_ids = {
            key.split(":", 1)[1]
            for key in research.get("accepted_artifacts", {})
            if key.startswith("evidence:")
        }
        inconsistent = {
            paper_id
            for paper_id in evidence_ids
            if (
                not _has_formal_source_identity(
                    research.get("papers", {}).get(paper_id, {})
                )
                or (
                    research.get("papers", {}).get(paper_id, {}).get("admission_status")
                    != "ADMIT_DECISION_GRADE"
                    and research.get("papers", {}).get(paper_id, {}).get("screening_status")
                    not in {"OUT_OF_SCOPE", "DUPLICATE"}
                )
            )
        }
        if not inconsistent:
            return []

        snapshots: dict[str, dict[str, Any]] = {}
        corpus = self._paths()["literature_corpus"]
        if corpus.is_file():
            for line in corpus.read_text(encoding="utf-8").splitlines():
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                paper_id = row.get("source_id") or row.get("paper_id")
                if (
                    paper_id in inconsistent
                    and _has_formal_source_identity(row)
                    and row.get("admission_status") == "ADMIT_DECISION_GRADE"
                ):
                    snapshots[str(paper_id)] = row

        missing = sorted(inconsistent - snapshots.keys())
        if missing:
            raise ControllerError(
                "accepted Evidence paper records are inconsistent and have no formal corpus snapshot: "
                + ", ".join(missing)
            )

        for paper_id in sorted(inconsistent):
            current = research["papers"].get(paper_id, {})
            restored = dict(snapshots[paper_id])
            restored.pop("previous_record_sha256", None)
            restored.pop("record_sha256", None)
            restored["found_by_query_ids"] = sorted(
                set(restored.get("found_by_query_ids") or [])
                | set(current.get("found_by_query_ids") or [])
            )
            for key in ("citation_count", "cited_by_id", "cited_by_url", "snippet"):
                if current.get(key) is not None:
                    restored[key] = current[key]
            if current.get("user_fulltext"):
                restored["user_fulltext"] = current["user_fulltext"]
            research["papers"][paper_id] = restored
            append_jsonl(corpus, restored)
            append_jsonl(
                self._paths()["search_log"],
                ledger_event(
                    run_id=self.run_id,
                    stage="METADATA_RETRIEVAL",
                    action="rediscovery_reconciliation",
                    paper_id=paper_id,
                    tool="controller_formal_corpus_reconciliation",
                    result_status="restored_formal_paper_state",
                    admission_decision="ADMIT_DECISION_GRADE",
                    event_id=uuid.uuid4().hex,
                ),
            )
        return sorted(inconsistent)

    def finish_retrieval(self) -> dict:
        with self._store.mutate() as state:
            research = self._require_stage(state, "METADATA_RETRIEVAL")
            reconciled = self._reconcile_accepted_evidence_papers(research)
            session = self._incremental_literature_active(research)
            candidate_papers = (
                [research["papers"][paper_id] for paper_id in session.get("paper_ids", []) if paper_id in research["papers"]]
                if session is not None
                else list(research["papers"].values())
            )
            unfinished_queries = [
                item.get("plan_item_id") or item.get("query")
                for item in research.get("planned_queries") or []
                if item.get("status") not in {"complete", "failed", "complete_human"}
            ]
            if unfinished_queries:
                raise ControllerError(
                    "cannot finish retrieval while accepted query-plan items remain unfinished: "
                    + ", ".join(str(item) for item in unfinished_queries[:10])
                )
            required_gaps = self._required_coverage_gaps(research)
            completed_gap_bindings = {
                gap
                for item in research.get("planned_queries") or []
                if item.get("status") == "complete"
                for gap in item.get("coverage_gaps") or []
            }
            missing_executed_gap_queries = sorted(required_gaps - completed_gap_bindings)
            if missing_executed_gap_queries:
                raise ControllerError(
                    "cannot finish retrieval before every required coverage gap has a completed "
                    "bound query: "
                    + ", ".join(missing_executed_gap_queries)
                )
            unresolved = [
                str(paper.get("source_id") or "<unknown>")
                for paper in candidate_papers
                if paper.get("screening_status") not in SCREENING_FINAL_STATUSES
            ]
            if unresolved:
                raise ControllerError(
                    "cannot finish retrieval until every deduplicated candidate has a recorded "
                    "title/abstract screening decision; unresolved="
                    + ", ".join(unresolved[:20])
                )
            abstract_gaps = [
                str(paper.get("source_id") or "<unknown>")
                for paper in candidate_papers
                if paper.get("screening_status") == "IN_SCOPE"
                and paper.get("screening_basis") == "TITLE_ABSTRACT"
                and not str(paper.get("abstract") or "").strip()
            ]
            if abstract_gaps:
                raise ControllerError(
                    "in-scope abstract-screened candidates are missing actual abstracts: "
                    + ", ".join(abstract_gaps[:20])
                )
            active = self._active_reading_session(research)
            if session is None and active is None:
                readable_papers = [
                    str(paper.get("source_id") or "")
                    for paper in candidate_papers
                    if paper.get("screening_status") == "IN_SCOPE"
                    and paper.get("admission_status") in READABLE_ADMISSION_STATUSES
                ]
                if not readable_papers:
                    self._route_planned_queries_to_human_search(
                        research,
                        evidence_gaps=list(required_gaps),
                        reason="no screened in-scope source is readable under the accepted source policy",
                        include_completed=True,
                    )
                    return state
                # A pre-selection rollback can leave accepted Evidence with a
                # stale paper record.  Persist its formal reconciliation first,
                # then let Main choose the existing non-empty subset on the
                # next action; Controller must not choose that subset itself.
                if reconciled:
                    return state
                raise ControllerError(
                    "all screening is complete; main_research_agent must select a non-empty "
                    "current reading subset before PAPER_READING"
                )
            if session is None and not any(
                self._paper_readable_in_active_session(research, paper_id)
                for paper_id in active.get("paper_ids", [])
            ):
                raise ControllerError("the selected reading subset contains no source-policy-readable paper")
            research["current_stage"] = "PAPER_READING"
            return state

    def select_reading_subset(
        self,
        paper_ids: list[str],
        *,
        rationale: str,
        initial: bool = False,
    ) -> dict:
        """Bind one non-empty, screened landscape cohort to the live reading pass.

        The Controller deliberately does not classify a paper as a Review,
        foundation, representative, or branch.  It only verifies identity,
        source-policy eligibility, corpus membership and lifecycle.
        """

        reason = str(rationale or "").strip()
        ids = list(dict.fromkeys(str(paper_id).strip() for paper_id in paper_ids if str(paper_id).strip()))
        if not ids or not reason:
            raise ControllerError("reading-subset selection requires non-empty paper_ids and rationale")
        with self._store.mutate() as state:
            research = state["research_lit"]
            stage = research["current_stage"]
            if stage not in {"METADATA_RETRIEVAL", "PAPER_READING"}:
                raise ControllerError("reading-subset selection requires METADATA_RETRIEVAL or PAPER_READING")
            if self._incremental_literature_active(research) is not None:
                raise ControllerError("incremental literature uses its existing phase-scoped reading session")
            existing = self._active_reading_session(research)
            if stage == "PAPER_READING":
                if not existing or existing.get("purpose") != "initial_cognition":
                    raise ControllerError("only the live initial-cognition pass may receive fallback additions")
                new_ids = list(dict.fromkeys([*existing.get("paper_ids", []), *ids]))
                if new_ids == existing.get("paper_ids", []):
                    raise ControllerError("fallback selection adds no new paper")
                ids = new_ids
                purpose = "initial_cognition"
            else:
                if existing is not None:
                    raise ControllerError("finish or replace the current reading session before selecting another")
                if research.get("initial_field_map_binding") is None and not initial:
                    raise ControllerError("the first reading subset must be declared as initial cognition")
                if research.get("initial_field_map_binding") is not None and initial:
                    raise ControllerError("initial cognition cannot restart after an Initial Field Map")
                purpose = "initial_cognition" if initial else "coverage"
                if purpose == "initial_cognition":
                    unresolved = [
                        paper_id for paper_id, paper in research["papers"].items()
                        if paper.get("screening_status") not in SCREENING_FINAL_STATUSES
                    ]
                    if unresolved:
                        raise ControllerError(
                            "initial reading selection requires screening every current initial candidate; unresolved="
                            + ", ".join(sorted(unresolved)[:20])
                        )
                    corpus_ids = sorted(
                        paper_id for paper_id, paper in research["papers"].items()
                        if paper.get("screening_status") in SCREENING_FINAL_STATUSES
                    )
                    if not corpus_ids:
                        raise ControllerError("initial reading selection requires the screened initial corpus")
                    research["initial_screened_corpus_ids"] = corpus_ids
            allowed_corpus = (
                set(research.get("initial_screened_corpus_ids") or [])
                if purpose == "initial_cognition"
                else set(research["papers"])
            )
            for paper_id in ids:
                paper = research["papers"].get(paper_id)
                if not isinstance(paper, dict) or paper_id not in allowed_corpus:
                    raise ControllerError(f"selected paper is outside the bound screened corpus: {paper_id}")
                if paper.get("screening_status") != "IN_SCOPE" or paper.get("duplicate"):
                    raise ControllerError(f"selected paper is excluded, duplicate, or out of scope: {paper_id}")
                if paper.get("identity_status") != "verified":
                    raise ControllerError(f"selected paper identity is not verified: {paper_id}")
                if not self._paper_readable_in_active_session(
                    {**research, "active_reading_session": {"paper_ids": ids}}, paper_id
                ):
                    raise ControllerError(f"selected paper is not eligible under the existing source policy: {paper_id}")
            research["active_reading_session"] = {
                "purpose": purpose,
                "paper_ids": ids,
                "rationale": reason,
                "created_at": now(),
            }
            if stage == "METADATA_RETRIEVAL":
                return state
            return state

    def _request_human_fulltext_batch(
        self,
        research: dict[str, Any],
        *,
        failed_paper_id: str,
        reason: str,
    ) -> dict[str, Any]:
        """Stop once and collect every admitted paper still lacking local full text."""

        missing: list[dict[str, Any]] = []
        session = self._incremental_literature_active(research)
        active = self._active_reading_session(research)
        paper_ids = (
            session.get("paper_ids", []) if session is not None
            else active.get("paper_ids", []) if active is not None
            else []
        )
        for paper_id in paper_ids:
            paper = research["papers"].get(paper_id)
            if not isinstance(paper, dict):
                continue
            if not self._paper_readable_in_active_session(research, paper_id):
                continue
            if f"evidence:{paper_id}" in research["accepted_artifacts"]:
                continue
            if paper.get("user_fulltext"):
                continue
            if any(
                event.get("paper_id") == paper_id and event.get("status") == "complete"
                for event in research.get("read_events", {}).values()
            ):
                continue
            missing.append(
                {
                    "paper_id": paper_id,
                    "title": paper.get("title"),
                    "authors": paper.get("authors"),
                    "year": paper.get("year"),
                    "venue": paper.get("venue"),
                    "doi": paper.get("doi"),
                    "doi_or_stable_url": paper.get("doi_or_stable_url"),
                }
            )
        if not missing:
            raise ControllerError("no admitted paper needs a user-supplied full-text batch")
        request = {
            "status": "HUMAN_FULLTEXT_REQUIRED",
            "kind": "fulltext_download_batch",
            "failed_paper_id": failed_paper_id,
            "reason": reason,
            "papers": missing,
            "target_directory": "source-materials/",
            "required_action": (
                "Download one local full-text file for every listed paper, place the files "
                "under source-materials/, then submit one batch manifest."
            ),
            "stop": True,
        }
        research["human_fulltext_request"] = request
        research["human_search_request"] = None
        research["current_stage"] = "HUMAN_SEARCH_REQUIRED"
        research["waiting_for"] = "human_fulltext_batch"
        return request

    def defer_fulltext_to_human_batch(
        self,
        paper_ids: list[str],
        *,
        reason: str,
    ) -> dict[str, Any]:
        """Record known access constraints without making futile provider calls."""

        defer_reason = str(reason or "").strip()
        if not defer_reason or not paper_ids:
            raise ControllerError("full-text deferral requires paper IDs and a reason")
        deferred: list[str] = []
        with self._store.mutate() as state:
            research = self._require_stage(state, "PAPER_READING")
            for paper_id in paper_ids:
                paper = research.get("papers", {}).get(paper_id)
                if not isinstance(paper, dict) or not self._paper_readable_in_active_session(research, paper_id):
                    raise ControllerError(f"cannot defer paper outside the active readable subset {paper_id!r}")
                if f"evidence:{paper_id}" in research.get("accepted_artifacts", {}):
                    continue
                if any(
                    event.get("paper_id") == paper_id and event.get("status") == "complete"
                    for event in research.get("read_events", {}).values()
                ):
                    continue
                paper["fulltext_failure"] = {
                    "read_event_id": None,
                    "reason": defer_reason,
                    "deferred_without_provider_call": True,
                }
                deferred.append(paper_id)
        for paper_id in deferred:
            append_jsonl(
                self._paths()["search_log"],
                ledger_event(
                    run_id=self.run_id,
                    stage="PAPER_READING",
                    action="fulltext_deferred_to_human_batch",
                    paper_id=paper_id,
                    tool="arisctl.defer-fulltext-batch",
                    result_status="deferred",
                    admission_decision="ADMIT_FOR_READING",
                    event_id=uuid.uuid4().hex,
                    details={"reason": defer_reason},
                ),
            )
        return {"deferred_paper_ids": deferred, "reason": defer_reason}

    def read_full_text(self, paper_id: str, tool: str, read: ReadCallable) -> Any:
        # A read event is the only formal paper_reader binding. Verify before
        # allocating its ID, budget, ledger record, or state entry.
        self._require_formal_native_runtime("paper_reader")
        ledger = self._paths()["search_log"]
        read_event_id = uuid.uuid4().hex
        content_sha256: str | None = None
        provenance_details: dict[str, str] | None = None
        with self._store.mutate() as state:
            research = self._require_stage(state, "PAPER_READING")
            paper = research["papers"].get(paper_id)
            if not paper or not self._paper_readable_in_active_session(research, paper_id):
                raise ControllerError(
                    f"full-text access denied before tool call: {paper_id} is outside the active readable subset"
                )
            if f"evidence:{paper_id}" in research.get("accepted_artifacts", {}):
                raise ControllerError("paper already has canonical Evidence; reuse it instead of rereading")
            before = research["fulltext_count"]
            if before >= research["max_fulltext_papers"]:
                raise ControllerError("full-text budget exhausted before tool call")
            research["fulltext_count"] = before + 1
            budget_before = {"queries": research["query_count"], "fulltext": before}
            budget_after = {
                "queries": research["query_count"],
                "fulltext": research["fulltext_count"],
            }
            append_jsonl(
                ledger,
                ledger_event(
                    run_id=self.run_id,
                    stage="PAPER_READING",
                    action="fulltext",
                    paper_id=paper_id,
                    tool=tool,
                    result_status="started",
                    event_id=read_event_id,
                    admission_decision=paper["admission_status"],
                    budget_before=budget_before,
                    budget_after=budget_after,
                ),
            )
            research["read_events"][read_event_id] = {
                "paper_id": paper_id,
                "tool": tool,
                "status": "started",
                "admission_decision": paper["admission_status"],
                "budget_before": budget_before,
                "budget_after": budget_after,
            }
        try:
            result = read(dict(paper))
        except Exception as exc:
            status = "failed"
            provider_failure_deferred = False
            with self._store.mutate() as state:
                research = state["research_lit"]
                research["read_events"][read_event_id]["status"] = status
                if isinstance(exc, ProviderUnavailable):
                    paper = research["papers"][paper_id]
                    paper["fulltext_failure"] = {
                        "read_event_id": read_event_id,
                        "reason": str(exc),
                    }
                    provider_failure_deferred = True
            if provider_failure_deferred:
                return {
                    "status": "FULLTEXT_PROVIDER_UNAVAILABLE",
                    "paper_id": paper_id,
                    "reason": str(exc),
                    "continue": True,
                }
            raise
        else:
            status = "complete"
            if isinstance(result, FullTextPayload):
                content_bytes = result.content
                returned_content: Any = result.content
                provenance_details = {
                    "source_url": result.source_url,
                    "media_type": result.media_type,
                    "provider": result.provider,
                }
            elif isinstance(result, bytes):
                content_bytes = result
                returned_content = result
            elif isinstance(result, str):
                content_bytes = result.encode("utf-8")
                returned_content = result
            else:
                content_bytes = json.dumps(
                    result, ensure_ascii=False, sort_keys=True
                ).encode("utf-8")
                returned_content = result
            content_sha256 = hashlib.sha256(content_bytes).hexdigest()
            with self._store.mutate() as state:
                research = state["research_lit"]
                event = research["read_events"][read_event_id]
                event["status"] = status
                event["content_sha256"] = content_sha256
                if provenance_details:
                    event["provenance"] = provenance_details
                research["papers"][paper_id].pop("fulltext_failure", None)
            return {
                "read_event_id": read_event_id,
                "paper_id": paper_id,
                "content_sha256": content_sha256,
                "content": returned_content,
                "provenance": provenance_details,
            }
        finally:
            append_jsonl(
                ledger,
                ledger_event(
                    run_id=self.run_id,
                    stage="PAPER_READING",
                    action="fulltext",
                    paper_id=paper_id,
                    tool=tool,
                    result_status=status,
                    event_id=read_event_id,
                    admission_decision=paper["admission_status"],
                    budget_before=budget_before,
                    budget_after=budget_after,
                    artifact_sha256=(content_sha256 if status == "complete" else None),
                    details=provenance_details,
                ),
            )

    def submit_evidence_card(self, paper_id: str, payload: dict[str, Any]) -> dict:
        artifact_name = self._evidence_artifact_name(paper_id)
        staged = self._stage_path(artifact_name)
        staged.parent.mkdir(parents=True, exist_ok=True)
        staged.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        with self._store.mutate() as state:
            research = self._require_stage(state, "PAPER_READING")
            paper = research["papers"].get(paper_id)
            if not paper or not self._paper_readable_in_active_session(research, paper_id):
                raise ControllerError("Evidence Card is not linked to the active readable subset")
            read_event_id = payload.get("read_event_id")
            read_event = research["read_events"].get(read_event_id)
            if (
                not isinstance(read_event, dict)
                or read_event.get("paper_id") != paper_id
                or read_event.get("status") != "complete"
                or payload.get("content_sha256") != read_event.get("content_sha256")
            ):
                raise ControllerError(
                    "Evidence Card must reference a completed full-text gateway event"
                )
            try:
                card = validate_evidence_card(
                    payload,
                    paper_id,
                    existing_evidence_ids={
                        key.split(":", 1)[1]
                        for key in research["accepted_artifacts"]
                        if key.startswith("evidence:")
                    },
                )
            except ValidationError as exc:
                self._record_validation(research, f"evidence:{paper_id}", "FAIL", [str(exc)])
                raise ControllerError(str(exc)) from exc
            attestation = self._consume_agent_attestation(
                "paper_reader", str(read_event_id), card, allow_missing=True
            )
            session = self._incremental_literature_active(research)
            if session is not None and session.get("phase") == "problem_generation":
                contexts = []
                for query_id in paper.get("found_by_query_ids") or []:
                    event = research.get("query_events", {}).get(query_id)
                    context = event.get("query_context") if isinstance(event, dict) else None
                    if isinstance(context, dict):
                        contexts.append(dict(context))
                if contexts:
                    # Preserve the query snapshots that actually discovered this
                    # source.  They are provenance, not a Controller-owned Lead.
                    card = {**card, "problem_lead_search_contexts": contexts}
            if session is not None and session.get("phase") == "method_design":
                plan = self._active_query_plan(research)
                plan_path = str(session.get("query_plan_path") or "")
                plan_sha256 = str(session.get("query_plan_sha256") or "")
                candidate = self.root / plan_path
                if not plan_path or not plan_sha256 or not candidate.is_file() or sha256_file(candidate) != plan_sha256:
                    raise ControllerError("method-design incremental query plan changed after Controller acceptance")
                context = plan.get("method_design_context")
                if not isinstance(context, dict):
                    raise ControllerError("method-design incremental query plan lost its search context")
                mode = context.get("search_mode")
                common_context = {
                    "query_plan_path": plan_path,
                    "query_plan_sha256": plan_sha256,
                    "root_cause_analysis_id": context["root_cause_analysis_id"],
                    "root_cause_analysis_sha256": context["root_cause_analysis_sha256"],
                    "active_field_map_sha256": context["active_field_map_sha256"],
                    "search_mode": mode,
                }
                if mode == "PRINCIPLE_SEARCH":
                    current_query_ids = {
                        query_id
                        for query_id, event in research.get("query_events", {}).items()
                        if isinstance(event, dict)
                        and event.get("query_plan_sha256") == plan_sha256
                        and event.get("status") in {"complete", "complete_human"}
                    }
                    actual_query_ids = sorted(
                        current_query_ids & set(paper.get("found_by_query_ids") or [])
                    )
                    if not actual_query_ids:
                        raise ControllerError(
                            "Principle-search Evidence requires an explicit hit from the current session"
                        )
                    actual_bindings = {
                        "mechanism_change_ids": set(),
                        "capability_ids": set(),
                        "obligation_ids": set(),
                        "causal_chain_ids": set(),
                        "search_dimensions": set(),
                    }
                    for query_id in actual_query_ids:
                        event = research["query_events"][query_id]
                        planned = next(
                            (
                                item
                                for item in plan.get("queries", [])
                                if (
                                    item.get("plan_item_id") == event.get("plan_item_id")
                                    if event.get("plan_item_id") is not None
                                    else item.get("query") == event.get("query")
                                )
                            ),
                            None,
                        )
                        if not isinstance(planned, dict):
                            raise ControllerError("Principle-search Evidence cannot resolve its accepted query-plan item")
                        for field in (
                            "mechanism_change_ids", "capability_ids",
                            "obligation_ids", "causal_chain_ids",
                        ):
                            actual_bindings[field].update(planned.get(field) or [])
                        actual_bindings["search_dimensions"].add(planned["search_dimension"])
                    card = {
                        **card,
                        "method_design_search_context": {
                            **common_context,
                            "actual_hit_query_ids": actual_query_ids,
                            **{
                                field: sorted(values)
                                for field, values in actual_bindings.items()
                            },
                        },
                    }
                else:
                    raise ControllerError("method-design incremental query plan has an invalid search mode")
            if session is not None and session.get("phase") == "method_refinement":
                plan = self._active_query_plan(research)
                plan_path = str(session.get("query_plan_path") or "")
                plan_sha256 = str(session.get("query_plan_sha256") or "")
                candidate = self.root / plan_path
                if not plan_path or not plan_sha256 or not candidate.is_file() or sha256_file(candidate) != plan_sha256:
                    raise ControllerError("adaptation-gap query plan changed after Controller acceptance")
                context = plan.get("method_refinement_context")
                if not isinstance(context, dict) or context.get("search_mode") != "ADAPTATION_GAP_SEARCH":
                    raise ControllerError("adaptation-gap query plan lost its search context")
                current_query_ids = {
                    query_id
                    for query_id, event in research.get("query_events", {}).items()
                    if isinstance(event, dict)
                    and event.get("query_plan_sha256") == plan_sha256
                    and event.get("status") in {"complete", "complete_human"}
                }
                actual_query_ids = sorted(current_query_ids & set(paper.get("found_by_query_ids") or []))
                if not actual_query_ids:
                    raise ControllerError("adaptation-gap Evidence requires an explicit current-session query hit")
                gap_ids: set[str] = set()
                for query_id in actual_query_ids:
                    event = research["query_events"][query_id]
                    planned = next(
                        (
                            item
                            for item in plan.get("queries", [])
                            if (
                                item.get("plan_item_id") == event.get("plan_item_id")
                                if event.get("plan_item_id") is not None
                                else item.get("query") == event.get("query")
                            )
                        ),
                        None,
                    )
                    if not isinstance(planned, dict):
                        raise ControllerError("adaptation-gap Evidence cannot resolve its query-plan item")
                    gap_ids.update(planned.get("residual_adaptation_gap_ids") or [])
                card = {
                    **card,
                    "method_refinement_search_context": {
                        "query_plan_path": plan_path,
                        "query_plan_sha256": plan_sha256,
                        "search_mode": "ADAPTATION_GAP_SEARCH",
                        "principle_id": context["principle_id"],
                        "principle_version": context["principle_version"],
                        "selected_principle_sha256": context["selected_principle_sha256"],
                        "actual_hit_query_ids": actual_query_ids,
                        "residual_adaptation_gap_ids": sorted(gap_ids),
                    },
                }
            canonical = self._canonical_path(artifact_name)
            canonical.parent.mkdir(parents=True, exist_ok=True)
            canonical.write_text(
                json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            append_jsonl(self._paths()["evidence_registry"], card)
            self._record_validation(research, f"evidence:{paper_id}", "PASS")
            research["accepted_artifacts"][f"evidence:{paper_id}"] = {
                "path": str(canonical.relative_to(self.root)),
                "validator_result": "PASS",
                "sha256": sha256_file(canonical),
                "read_event_id": read_event_id,
                "accepted_at": now(),
            }
            if attestation is not None:
                research["accepted_artifacts"][f"evidence:{paper_id}"][
                    "paper_reader_agent_id"
                ] = attestation["agent_id"]
            if session is not None:
                session.setdefault("evidence_artifacts", {})[f"evidence:{paper_id}"] = dict(
                    research["accepted_artifacts"][f"evidence:{paper_id}"]
                )
            else:
                landscape_evidence = research.setdefault("landscape_evidence_ids", [])
                if paper_id not in landscape_evidence:
                    landscape_evidence.append(paper_id)
            paper["admission_status"] = "ADMIT_DECISION_GRADE"
            corpus_row = dict(paper)
        append_jsonl(self._paths()["literature_corpus"], corpus_row)
        return self.status()

    def readopt_incremental_evidence(
        self,
        evidence_id: str,
        *,
        obligation_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create one new, current phase binding for an existing Evidence Card.

        The three legitimate uses are returned Problem Generation reusing
        existing Problem-phase Evidence; Method phases re-adopting historical
        phase-scoped Evidence under the current Design Obligation context; and
        formally reopened RCA re-adopting Evidence that previously entered a
        Method context.  This never rewrites the Card, query/read provenance,
        or an older binding.
        """

        source_id = str(evidence_id or "").strip()
        if not source_id:
            raise ControllerError("evidence re-adoption requires an Evidence ID")
        if obligation_ids is not None and (
            not isinstance(obligation_ids, list)
            or not obligation_ids
            or any(not isinstance(item, str) or not item.strip() for item in obligation_ids)
            or len(obligation_ids) != len(set(obligation_ids))
        ):
            raise ControllerError("re-adopted method evidence requires unique current obligation IDs")
        with self._store.mutate() as state:
            research = state["research_lit"]
            if research.get("current_stage") != "LANDSCAPE_ACCEPTED" or self._incremental_literature_active(research):
                raise ControllerError("evidence re-adoption requires an idle incremental literature boundary")
            phase = self._current_core_phase(state)
            phase_name = str(phase.get("phase") or "")
            if phase_name not in {
                "problem_generation", "method_design", "method_refinement", "final_method_novelty_gate", "root_cause_analysis",
            } or phase.get("status") not in {"pending", "running"}:
                raise ControllerError("evidence re-adoption is allowed only in returned problem generation, the current method phase, or reopened RCA")
            evidence_key = f"evidence:{source_id}"
            record, card = self._registered_evidence_card(research, source_id)
            self._assert_phase_inputs_current(state, phase_name)
            anchor = self._phase_evidence_anchor(state, phase_name)
            if phase_name == "problem_generation":
                return_id = self._phase_lifecycle_return_id(state, phase_name)
                prior_records = (research.get("incremental_evidence_by_phase") or {}).get(phase_name)
                if not isinstance(return_id, str) or not return_id:
                    raise ControllerError("problem-generation evidence re-adoption requires a formal Human-return binding")
                if not isinstance(prior_records, dict) or not any(
                    isinstance(binding, dict) and binding.get("evidence_key") == evidence_key
                    for binding in prior_records.values()
                ):
                    raise ControllerError("problem-generation evidence re-adoption requires a prior binding in problem_generation")
            elif phase_name == "root_cause_analysis":
                return_id = self._phase_lifecycle_return_id(state, "root_cause_analysis")
                if not isinstance(return_id, str) or not return_id:
                    raise ControllerError("RCA evidence re-adoption requires a formal reopened-RCA return binding")
                if obligation_ids is not None:
                    raise ControllerError("RCA evidence re-adoption does not bind method obligation IDs")
                if not self._evidence_has_method_context(research, evidence_key, card):
                    raise ControllerError("RCA re-adoption requires Evidence previously used in a method context")
                # A diagnostic binding that is already current for this
                # accepted Problem needs no second RCA binding merely because
                # the Evidence also originated in a method search.
                if any(
                    isinstance(binding, dict)
                    and binding.get("evidence_key") == evidence_key
                    and binding.get("phase_binding_anchor") == anchor
                    for binding in (research.get("incremental_evidence_by_phase", {}).get(phase_name) or {}).values()
                ):
                    return {"status": "ALREADY_CURRENT", "evidence_id": source_id, "phase": phase_name}
                anchor["reopened_rca_return_event_id"] = return_id
            else:
                mechanical_status = self._method_re_adoption_mechanical_status(
                    research, phase_name, evidence_key, anchor
                )
                context = anchor.get("design_obligation_binding")
                if mechanical_status == "missing_obligation_context":
                    raise ControllerError("method evidence re-adoption requires a current Design Obligation binding")
                if mechanical_status == "not_historical_phase_evidence":
                    raise ControllerError(
                        "method evidence re-adoption requires a prior formal phase-scoped binding"
                    )
                legal_ids = set(context.get("obligation_ids") or [])
                requested_ids = set(obligation_ids or [])
                if not requested_ids or not requested_ids.issubset(legal_ids):
                    raise ControllerError("re-adopted obligation IDs are not in the current Design Obligation context")
                if mechanical_status == "already_current":
                    return {"status": "ALREADY_CURRENT", "evidence_id": source_id, "phase": phase_name}
            phase_evidence = research.setdefault("incremental_evidence_by_phase", {}).setdefault(phase_name, {})
            if not isinstance(phase_evidence, dict):
                raise ControllerError("incremental evidence records are invalid")
            for binding in phase_evidence.values():
                if (
                    isinstance(binding, dict)
                    and binding.get("evidence_key") == evidence_key
                    and binding.get("phase_binding_anchor") == anchor
                ):
                    return {"status": "ALREADY_CURRENT", "evidence_id": source_id, "phase": phase_name}
            binding_key = f"{evidence_key}@readopt-{uuid.uuid4().hex}"
            binding = {
                **dict(record),
                "evidence_key": evidence_key,
                "phase_binding_anchor": anchor,
                "re_adopted_at": now(),
            }
            if obligation_ids is not None:
                binding["obligation_ids"] = sorted(obligation_ids)
            phase_evidence[binding_key] = binding
            return {"status": "RE_ADOPTED", "evidence_id": source_id, "phase": phase_name}

    def finish_reading(self) -> dict:
        with self._store.mutate() as state:
            research = self._require_stage(state, "PAPER_READING")
            session = self._incremental_literature_active(research)
            if session is not None:
                missing = [
                    paper_id
                    for paper_id in session.get("paper_ids", [])
                    if research["papers"].get(paper_id, {}).get("admission_status") in READABLE_ADMISSION_STATUSES
                    and f"evidence:{paper_id}" not in research["accepted_artifacts"]
                ]
                if missing:
                    if all(
                        research["papers"][paper_id].get("fulltext_failure")
                        for paper_id in missing
                    ):
                        first = research["papers"][missing[0]]["fulltext_failure"]
                        self._request_human_fulltext_batch(
                            research,
                            failed_paper_id=missing[0],
                            reason=str(first.get("reason") or "automatic full-text routes failed"),
                        )
                        return state
                    raise ControllerError(
                        "cannot finish incremental literature; admitted papers lack accepted Evidence Cards: "
                        f"{sorted(set(missing))}"
                    )
                phase_name = str(session.get("phase") or "")
                if not phase_name:
                    raise ControllerError("incremental literature session has no core phase")
                evidence = session.get("evidence_artifacts") or {}
                # Root-cause diagnosis can return to the gateway more than once
                # while running. Preserve every accepted phase-scoped Evidence
                # Card so the analysis snapshot and its Gate reviewer see the
                # complete diagnostic evidence set.
                phase_evidence = research.setdefault("incremental_evidence_by_phase", {}).setdefault(
                    phase_name, {}
                )
                if not isinstance(phase_evidence, dict):
                    raise ControllerError("incremental evidence records are invalid")
                anchor = session.get("phase_binding_anchor")
                if anchor is not None and not isinstance(anchor, dict):
                    raise ControllerError("incremental literature session has an invalid phase binding anchor")
                for evidence_key, record in evidence.items():
                    if not isinstance(record, dict):
                        raise ControllerError("incremental evidence artifact record is invalid")
                    binding = {
                        **dict(record),
                        "evidence_key": str(evidence_key),
                    }
                    if anchor is not None:
                        binding["phase_binding_anchor"] = anchor
                    phase_evidence[str(evidence_key)] = binding
                research["incremental_literature_active"] = None
                research["current_stage"] = "LANDSCAPE_ACCEPTED"
                research["waiting_for"] = None
                return state
            active = self._active_reading_session(research)
            if active is None:
                raise ControllerError("PAPER_READING has no active reading subset")
            missing = [
                paper_id
                for paper_id in active.get("paper_ids", [])
                if self._paper_readable_in_active_session(research, paper_id)
                and f"evidence:{paper_id}" not in research["accepted_artifacts"]
            ]
            if missing:
                if all(
                    research["papers"][paper_id].get("fulltext_failure")
                    for paper_id in missing
                ):
                    first = research["papers"][missing[0]]["fulltext_failure"]
                    self._request_human_fulltext_batch(
                        research,
                        failed_paper_id=missing[0],
                        reason=str(first.get("reason") or "automatic full-text routes failed"),
                    )
                    return state
                raise ControllerError(
                    f"cannot enter FIELD_SYNTHESIS; admitted papers lack accepted Evidence Cards: {missing}"
                )
            if not any(
                f"evidence:{paper_id}" in research["accepted_artifacts"]
                for paper_id in active.get("paper_ids", [])
            ):
                raise ControllerError(
                    "cannot enter FIELD_SYNTHESIS without an accepted Evidence Card for the active subset"
                )
            research["active_reading_session"] = None
            research["current_stage"] = "FIELD_SYNTHESIS"
            return state

    def submit_field_map(
        self,
        payload: dict[str, Any],
        *,
        review_trigger: str | None = None,
    ) -> dict:
        requested_review = review_trigger
        # The first map is a provisional cognition handoff, not a coverage
        # judgment.  The existing FIELD_SYNTHESIS stage carries both cases.
        state_before = self.status()
        research_before = state_before.get("research_lit") or {}
        provisional = (
            research_before.get("initial_field_map_binding") is None
            and "active_field_map" not in (research_before.get("accepted_artifacts") or {})
        )
        if provisional and review_trigger is not None:
            raise ControllerError("provisional Initial Field Map cannot request coverage review")
        if provisional and "coverage_record" in payload:
            raise ControllerError("provisional Initial Field Map must not carry a coverage_record")
        coverage_record = payload.get("coverage_record")
        if (
            requested_review is None
            and isinstance(coverage_record, dict)
            and coverage_record.get("coverage_status") == "SUFFICIENT"
        ):
            requested_review = "candidate_sufficient"
        if requested_review is not None:
            allowed_triggers = set(self.workflow["research_lit"]["coverage_review_triggers"])
            if requested_review not in allowed_triggers:
                raise ControllerError(
                    "coverage reviewer may run only for candidate_sufficient, "
                    "major_taxonomy_change, or final_acceptance"
                )
            # The coverage request is the only formal coverage_reviewer
            # binding; reject before writing staging/canonical artifacts.
            self._require_formal_native_runtime("coverage_reviewer")
        review_trigger = requested_review
        staged = self._stage_path("active_field_map")
        staged.parent.mkdir(parents=True, exist_ok=True)
        staged.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        with self._store.mutate() as state:
            research = self._require_stage(state, "FIELD_SYNTHESIS")
            for paper_id in research.get("landscape_evidence_ids", []):
                self._assert_artifact_current(research, f"evidence:{paper_id}")
            try:
                provisional = (
                    research.get("initial_field_map_binding") is None
                    and "active_field_map" not in (research.get("accepted_artifacts") or {})
                )
                field_map = validate_field_map(
                    payload,
                    evidence_ids={
                        str(paper_id)
                        for paper_id in research.get("landscape_evidence_ids", [])
                        if f"evidence:{paper_id}" in research["accepted_artifacts"]
                    },
                    provisional=provisional,
                )
            except ValidationError as exc:
                self._record_validation(research, "active_field_map", "FAIL", [str(exc)])
                raise ControllerError(str(exc)) from exc
            canonical = self._paths()["active_field_map"]
            canonical.parent.mkdir(parents=True, exist_ok=True)
            self._archive_active_field_map(research)
            canonical.write_text(render_field_map(field_map), encoding="utf-8")
            self._record_validation(research, "active_field_map", "PASS")
            research["accepted_artifacts"]["active_field_map"] = {
                "path": str(canonical.relative_to(self.root)),
                "validator_result": "PASS",
                "sha256": sha256_file(canonical),
                "accepted_at": now(),
                "author_role": "main_research_agent",
            }
            if provisional:
                research["initial_field_map_binding"] = {
                    "path": str(canonical.relative_to(self.root)),
                    "sha256": research["accepted_artifacts"]["active_field_map"]["sha256"],
                    "initial_screened_corpus_ids": list(
                        research.get("initial_screened_corpus_ids") or []
                    ),
                }
                research["coverage_review_request"] = None
                research["required_coverage_gaps"] = []
                # Remain in FIELD_SYNTHESIS so the main agent can bind formal
                # Primary selection to this exact accepted Initial Map.
                return state
            coverage_status = field_map["coverage_record"]["coverage_status"]
            research["last_coverage_status"] = coverage_status
            research["last_coverage_review_decision"] = None
            map_gaps = list(field_map["coverage_record"].get("coverage_gaps") or [])
            research["required_coverage_gaps"] = (
                map_gaps if coverage_status in {"PARTIAL", "INSUFFICIENT"} else []
            )
            if coverage_status == "SUFFICIENT" and review_trigger is None:
                review_trigger = "candidate_sufficient"
            allowed_triggers = set(
                self.workflow["research_lit"]["coverage_review_triggers"]
            )
            if review_trigger is None:
                research["coverage_review_request"] = None
                research["current_stage"] = "QUERY_PLANNING"
                return state
            if review_trigger not in allowed_triggers:
                raise ControllerError(
                    "coverage reviewer may run only for candidate_sufficient, "
                    "major_taxonomy_change, or final_acceptance"
                )
            review_bindings: dict[str, str] = {}
            for artifact_name in (
                "source_admission_policy",
                "query_plan",
                "active_field_map",
            ):
                record = research["accepted_artifacts"].get(artifact_name)
                if isinstance(record, dict) and record.get("path"):
                    artifact_path = self.root / str(record["path"])
                    if artifact_path.is_file():
                        review_bindings[str(record["path"])] = sha256_file(artifact_path)
            for manifest_name in ("literature_corpus", "search_log", "evidence_registry"):
                artifact_path = self._paths()[manifest_name]
                if artifact_path.is_file():
                    review_bindings[str(artifact_path.relative_to(self.root))] = sha256_file(
                        artifact_path
                    )
            request = {
                "id": uuid.uuid4().hex,
                "run_id": self.run_id,
                "trigger": review_trigger,
                "development_trace_count": len(field_map["family_development_traces"]),
                "artifact_sha256": research["accepted_artifacts"]["active_field_map"]["sha256"],
                "required_agent": "coverage_reviewer",
                "accepted_verdicts": ["CONTINUE", "CANDIDATE_SUFFICIENT"],
                "artifact_bindings": review_bindings,
                "issued_by": "ARISController",
                "created_at": now(),
            }
            research["coverage_review_request"] = request
            research["current_stage"] = "COVERAGE_REVIEW"
            return state

    def select_formal_primary_subset(
        self, paper_ids: list[str], *, rationale: str
    ) -> dict:
        """Start the post-Initial, map-guided Primary reading pass.

        The supplied rationale is audit provenance only.  Controller checks
        identity, bound corpus membership, source policy and hashes, never the
        scientific classification asserted by the main agent.
        """

        reason = str(rationale or "").strip()
        ids = list(dict.fromkeys(str(paper_id).strip() for paper_id in paper_ids if str(paper_id).strip()))
        if not ids or not reason:
            raise ControllerError("formal Primary selection requires non-empty paper_ids and rationale")
        with self._store.mutate() as state:
            research = self._require_stage(state, "FIELD_SYNTHESIS")
            binding = research.get("initial_field_map_binding")
            if not isinstance(binding, dict):
                raise ControllerError("formal Primary selection requires an accepted Initial Field Map")
            current = self._assert_artifact_current(research, "active_field_map")
            if current.get("sha256") != binding.get("sha256"):
                raise ControllerError("Initial Field Map is no longer the active selection basis")
            initial_corpus = set(binding.get("initial_screened_corpus_ids") or [])
            if not initial_corpus:
                raise ControllerError("Initial Field Map lacks recoverable screened-corpus provenance")
            for paper_id in ids:
                paper = research["papers"].get(paper_id)
                if not isinstance(paper, dict) or paper_id not in initial_corpus:
                    raise ControllerError(f"formal Primary selection is outside the bound initial corpus: {paper_id}")
                if paper.get("screening_status") != "IN_SCOPE" or paper.get("duplicate"):
                    raise ControllerError(f"formal Primary selection cannot reactivate excluded paper: {paper_id}")
                if paper.get("identity_status") != "verified":
                    raise ControllerError(f"formal Primary selection requires verified identity: {paper_id}")
                if not self._paper_readable_in_active_session(
                    {**research, "active_reading_session": {"paper_ids": ids}}, paper_id
                ):
                    raise ControllerError(f"formal Primary selection violates the existing source policy: {paper_id}")
            selection = {
                "purpose": "formal_primary",
                "paper_ids": ids,
                "rationale": reason,
                "initial_field_map_path": binding["path"],
                "initial_field_map_sha256": binding["sha256"],
                "initial_screened_corpus_ids": sorted(initial_corpus),
                "created_at": now(),
            }
            research["formal_primary_selection"] = dict(selection)
            research["active_reading_session"] = selection
            research["current_stage"] = "PAPER_READING"
            return state

    def submit_coverage_review(self, payload: dict[str, Any]) -> dict:
        staged = self._stage_path("coverage_review")
        staged.parent.mkdir(parents=True, exist_ok=True)
        staged.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        with self._store.mutate() as state:
            research = self._require_stage(state, "COVERAGE_REVIEW")
            request = research.get("coverage_review_request")
            if (
                not isinstance(request, dict)
                or request.get("run_id") != self.run_id
                or request.get("required_agent") != "coverage_reviewer"
                or request.get("issued_by") != "ARISController"
            ):
                raise ControllerError("Controller has not issued a coverage review request")
            try:
                review = validate_coverage_review(
                    payload,
                    development_trace_count=request["development_trace_count"],
                )
                field_record = validate_canonical_registry(state, "active_field_map")
                self._assert_artifact_current(research, "active_field_map")
                if review["review_request_id"] != request["id"]:
                    raise ValidationError("coverage review request id is stale or unknown")
                if review["reviewed_artifact_sha256"] != field_record["sha256"]:
                    raise ValidationError("coverage review does not match the canonical Field Map")
                if review["run_id"] != self.run_id:
                    raise ValidationError("coverage review does not identify the active run")
                if review["reviewed_artifact_hashes"] != request["artifact_bindings"]:
                    raise ValidationError("coverage review does not match the current artifact bindings")
                if review["decision"] not in request["accepted_verdicts"]:
                    raise ValidationError("coverage review decision is not allowed for this request")
            except ValidationError as exc:
                self._record_validation(research, "coverage_review", "FAIL", [str(exc)])
                raise ControllerError(str(exc)) from exc
            attested_payload = self._attested_reviewer_payload(
                role="coverage_reviewer",
                request_id=str(request["id"]),
                reviewer=str(review["reviewer"]),
                verdict_id=str(review["verdict_id"]),
                decision=str(review["decision"]),
                artifact_bindings=dict(request["artifact_bindings"]),
            )
            if review != attested_payload:
                self._record_validation(
                    research, "coverage_review", "FAIL",
                    ["coverage review differs from the attested reviewer payload"],
                )
                raise ControllerError("coverage review differs from the attested reviewer payload")
            attestation = self._consume_review_attestation(
                role="coverage_reviewer",
                request_id=str(request["id"]),
                reviewer=str(review["reviewer"]),
                verdict_id=str(review["verdict_id"]),
                decision=str(review["decision"]),
                artifact_bindings=dict(request["artifact_bindings"]),
            )
            self._record_validation(research, "coverage_review", "PASS")
            canonical = self._canonical_path("coverage_review")
            canonical.parent.mkdir(parents=True, exist_ok=True)
            canonical.write_text(
                json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            research["accepted_artifacts"]["coverage_review"] = {
                "path": str(canonical.relative_to(self.root)),
                "validator_result": "PASS",
                "decision": review["decision"],
                "sha256": sha256_file(canonical),
                "accepted_at": now(),
                "review_request_id": request["id"],
                "review_trigger": request["trigger"],
                "reviewer_role": "coverage_reviewer",
                "coverage_reviewer_agent_id": attestation["agent_id"],
                "verdict_id": review["verdict_id"],
                "reviewer": review["reviewer"],
                "reviewed_artifact_bindings": dict(request["artifact_bindings"]),
            }
            if review["decision"] == "CONTINUE":
                research["last_coverage_review_decision"] = "CONTINUE"
                prior_required_gaps = list(research.get("required_coverage_gaps") or [])
                research["required_coverage_gaps"] = list(
                    dict.fromkeys([*prior_required_gaps, *review["gaps"]])
                )
                research["coverage_review_request"] = None
                research["current_stage"] = "QUERY_PLANNING"
                return state
            result = audit_landscape(self.root, state["workflow"], state=state)
            if not result["ok"]:
                self._record_validation(research, "landscape", "FAIL", result["errors"])
                raise ControllerError("coverage validator FAIL: " + "; ".join(result["errors"]))
            if result["coverage_status"] != "SUFFICIENT":
                raise ControllerError(
                    "CANDIDATE_SUFFICIENT requires canonical coverage_status SUFFICIENT"
                )
            landscape = run_state._find_phase(state, "landscape")
            landscape.update(
                {
                    "status": "accepted",
                    "coverage_status": result["coverage_status"],
                    "verdict_id": f"coverage:{review['reviewer_run_id']}",
                    "reviewer": "coverage_reviewer",
                    "reviewer_family": "independent-context",
                    "review_independence": "independent-context",
                    "acceptance_status": "accepted",
                    "updated": now(),
                }
            )
            research["current_stage"] = "WAITING_FOR_HUMAN"
            research["waiting_for"] = "scope_human_approval"
            research["coverage_review_request"] = None
            research["approval_request"] = {
                "id": uuid.uuid4().hex,
                "gate": "scope_human_approval",
                "artifact_bindings": {
                    str(research["accepted_artifacts"][name]["path"]): str(
                        research["accepted_artifacts"][name]["sha256"]
                    )
                    for name in ("source_admission_policy", "active_field_map", "coverage_review")
                },
                "issued_by": "ARISController",
                "created_at": now(),
            }
            self._record_validation(research, "landscape", "PASS")
            return state
