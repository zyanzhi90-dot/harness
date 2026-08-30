#!/usr/bin/env python3
"""Resumable run-state for ARIS multi-phase workflows.

A long ARIS workflow (research-pipeline, paper-writing, idea-discovery) can fail
mid-run, and today there is no record of *which phase* already finished — a
resume restarts from scratch. This helper models a run as an ordered list of
phases with status, so resume can pick up where it left off.

The ARIS increment over a naive "resume = reopen" (which is all Hermes does):
the phase status enum SPLITS execution from acceptance —

    done      executor (Claude) finished writing the artifact.
              EXECUTION-COMPLETENESS — a safe SAME-MODEL self-report.
    accepted  a CROSS-MODEL reviewer (codex/gemini) OR a deterministic verifier
              returned a positive verdict, recorded with a verdict id + reviewer.
    provisional a fresh SAME-FAMILY reviewer returned a positive verdict. This
              is terminal for resume so a Codex-only workflow can advance, but
              remains explicitly distinct from accepted.
    skipped   the phase does not apply to this run (e.g. paper-writing when
              AUTO_WRITE=false) — a deterministic config decision, terminal.

Resume resolves FORWARD to the first phase that is NOT terminal ({accepted,
provisional, skipped}) — never the first non-`done`. So a phase the executor self-considered
"done" but that crashed before its cross-model audit is RE-VALIDATED on resume,
never silently skipped. Acceptance-gate rule made operational: a loop can DRIVE
resume, it cannot ACQUIT a phase past itself.

Structurally enforced: `set` may only write pending/running/done/failed/skipped;
only `accept` writes `accepted`; `mark-provisional` writes `provisional`. Both
REQUIRE a verdict id + reviewer AND that
the phase already be `done` (use --force to override) — you cannot acquit a phase
that never ran, nor mark one accepted without recording who acquitted it.

State at ``<root>/.aris/runs/<run_id>.json`` (file-based, no DB). Single-writer
contract (one orchestrator per run); a best-effort flock guards against a
concurrent resumer. See shared-references/resumable-runs.md.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

import yaml

try:
    from provenance import model_family
except ImportError:  # package import: ``from tools import run_state``
    from tools.provenance import model_family

try:
    import fcntl  # POSIX
except ImportError:  # pragma: no cover - Windows
    fcntl = None  # type: ignore

EXECUTOR_STATUSES = {"pending", "running", "done", "failed", "skipped"}
# Statuses resume ALWAYS skips. `provisional` is deliberately NOT here: whether a
# same-family provisional verdict may advance a run is a PER-RUN POLICY
# (`policy.provisional_advances`, default False). The Codex-native mirror sets it
# true at start_run; mainline runs keep the historical guarantee that only a
# cross-family acceptance (or an explicit skip) closes a phase.
TERMINAL_STATUSES = {"accepted", "human_accepted", "skipped"}
ALL_STATUSES = EXECUTOR_STATUSES | {"accepted", "human_accepted", "provisional"}


def _assert_not_controller_managed(state: dict) -> None:
    """Keep legacy mutation APIs out of Controller-owned runs.

    The controller mutates those runs through its atomic StateStore.  This
    closes the old ``run_state.py set/accept/approve`` bypass while preserving
    backwards compatibility for non-controller workflows.
    """
    if state.get("controller_managed"):
        raise ValueError(
            "run is Controller-managed; use arisctl instead of run_state mutation APIs"
        )


def _terminal_statuses(state: dict) -> set:
    base = set(TERMINAL_STATUSES)
    if (state.get("policy") or {}).get("provisional_advances") is True:
        base.add("provisional")
    return base


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run_path(root: str, run_id: str) -> Path:
    safe = "".join(c for c in run_id if c.isalnum() or c in "-_.")
    if not safe or safe != run_id or run_id in (".", ".."):
        raise ValueError(f"invalid run_id {run_id!r} (use [A-Za-z0-9-_.])")
    return Path(root) / ".aris" / "runs" / f"{run_id}.json"


@contextmanager
def _lock(root: str, run_id: str) -> Iterator[None]:
    """Best-effort advisory lock for the load-modify-save of one run.

    Single-writer is the contract; this only guards against a stray concurrent
    resumer. No-op where fcntl is unavailable.
    """
    p = _run_path(root, run_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    if fcntl is None:
        yield
        return
    lock_path = p.with_suffix(".lock")
    fh = open(lock_path, "w")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(fh, fcntl.LOCK_UN)
        finally:
            fh.close()


def _load(root: str, run_id: str) -> dict:
    p = _run_path(root, run_id)
    if not p.exists():
        raise FileNotFoundError(f"no run state at {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def _save(root: str, run_id: str, state: dict) -> None:
    p = _run_path(root, run_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    state["updated"] = _now()
    # Unique temp in the same dir → atomic replace, no shared-tmp clobber.
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=f".{run_id}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        os.replace(tmp, p)
    except BaseException:
        try:
            os.unlink(tmp)
        finally:
            raise


def _load_workflow(path: Optional[str]) -> Optional[dict]:
    """Load the JSON-compatible YAML workflow declaration.

    The checked-in ``idea-workflow.yaml`` intentionally uses JSON syntax, which
    is valid YAML and keeps this state helper dependency-free. A workflow is
    metadata, not prompt text: it declares dependencies, handoff artifacts,
    gate ownership, and human checkpoints.
    """
    if not path:
        return None
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"workflow spec not found at {p}")
    try:
        workflow = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"workflow spec must be JSON-compatible YAML (stdlib parser): {p}: {exc}"
        ) from exc
    if not isinstance(workflow, dict) or not isinstance(workflow.get("phases"), list):
        raise ValueError("workflow spec requires an object with a phases list")
    manifest = workflow.get("artifact_manifest", {})
    if not isinstance(manifest, dict) or any(
        not isinstance(key, str) or not key or not isinstance(value, str) or not value
        for key, value in manifest.items()
    ):
        raise ValueError("artifact_manifest must map non-empty names to paths")
    names = [item.get("phase") for item in workflow["phases"] if isinstance(item, dict)]
    if len(names) != len(set(names)) or any(not name for name in names):
        raise ValueError("workflow phases must have unique non-empty phase names")
    formal_gate_ids = [
        item.get("gate_id") for item in workflow["phases"]
        if item.get("formal_gate")
    ]
    if len(formal_gate_ids) != len(set(formal_gate_ids)):
        raise ValueError("each formal Gate must have one unique gate_id")
    for item in workflow["phases"]:
        if item.get("formal_gate") and not item.get("gate_owner"):
            raise ValueError(f"formal Gate {item.get('gate_id')!r} has no gate_owner")
        for dependency in item.get("depends_on", []):
            if dependency not in names:
                raise ValueError(
                    f"phase {item.get('phase')!r} depends on unknown phase {dependency!r}"
                )
        for field in ("required_inputs", "produced_artifacts", "reviewed_artifacts"):
            for raw in item.get(field, []):
                if isinstance(raw, str) and raw.startswith("@artifact:"):
                    key = raw[len("@artifact:"):]
                    if key not in manifest:
                        raise ValueError(
                            f"phase {item.get('phase')!r} references unknown artifact {key!r}"
                        )
        reviewed_artifacts = item.get("reviewed_artifacts")
        if reviewed_artifacts is not None:
            if not isinstance(reviewed_artifacts, list) or not reviewed_artifacts:
                raise ValueError(
                    f"phase {item.get('phase')!r} reviewed_artifacts must be a non-empty list"
                )
            reviewed_paths = _resolve_artifact_refs(workflow, reviewed_artifacts, item.get("phase"))
            produced_paths = _resolve_artifact_refs(
                workflow, item.get("produced_artifacts", []), item.get("phase")
            )
            if any(path not in produced_paths for path in reviewed_paths):
                raise ValueError(
                    f"phase {item.get('phase')!r} reviewed_artifacts must be produced by the same phase"
                )
        coverage = item.get("requires_coverage")
        if coverage is not None:
            if not isinstance(coverage, dict) or not isinstance(coverage.get("phase"), str):
                raise ValueError(
                    f"phase {item.get('phase')!r} requires valid requires_coverage metadata"
                )
            if coverage["phase"] not in names or not isinstance(coverage.get("statuses"), list) \
                    or not coverage["statuses"]:
                raise ValueError(
                    f"phase {item.get('phase')!r} requires a known coverage phase and statuses"
                )
        validated = item.get("requires_validated_artifacts")
        if validated is not None:
            if not isinstance(validated, list) or not validated:
                raise ValueError(
                    f"phase {item.get('phase')!r} requires_validated_artifacts must be a non-empty list"
                )
            for requirement in validated:
                if not isinstance(requirement, dict) or requirement.get("phase") not in names:
                    raise ValueError(
                        f"phase {item.get('phase')!r} requires validated artifacts from a known phase"
                    )
                artifacts = requirement.get("artifacts")
                if not isinstance(artifacts, list) or not artifacts:
                    raise ValueError(
                        f"phase {item.get('phase')!r} has an empty validated artifact requirement"
                    )
                _resolve_artifact_refs(workflow, artifacts, item.get("phase"))
        accepted_verdicts = item.get("accepted_verdicts")
        if accepted_verdicts is not None and (
            not isinstance(accepted_verdicts, list)
            or not accepted_verdicts
            or any(not isinstance(value, str) or not value for value in accepted_verdicts)
        ):
            raise ValueError(
                f"phase {item.get('phase')!r} accepted_verdicts must be a non-empty string list"
            )
        if accepted_verdicts is not None and len(accepted_verdicts) != len(set(accepted_verdicts)):
            raise ValueError(
                f"phase {item.get('phase')!r} accepted_verdicts must be unique"
            )
        accepted_decisions = item.get("accepted_decisions")
        if item.get("human_checkpoint"):
            if (
                not isinstance(accepted_decisions, list)
                or not accepted_decisions
                or any(not isinstance(value, str) or not value for value in accepted_decisions)
            ):
                raise ValueError(
                    f"human checkpoint {item.get('phase')!r} accepted_decisions must be a non-empty string list"
                )
        elif accepted_decisions is not None:
            raise ValueError(
                f"non-human phase {item.get('phase')!r} cannot declare accepted_decisions"
            )
        return_targets = item.get("return_targets")
        if return_targets is not None:
            if not isinstance(return_targets, dict) or not return_targets:
                raise ValueError(
                    f"phase {item.get('phase')!r} return_targets must be a non-empty object"
                )
            current_index = names.index(item.get("phase"))
            for decision, target in return_targets.items():
                if (
                    not isinstance(decision, str) or not decision
                    or target not in names
                        or names.index(target) > current_index
                ):
                    raise ValueError(
                            f"phase {item.get('phase')!r} return_targets must map verdicts to its current or an earlier phase"
                    )
            if accepted_decisions is not None and set(accepted_decisions) & set(return_targets):
                raise ValueError(
                    f"phase {item.get('phase')!r} accepted_decisions and return_targets overlap"
                )
            if accepted_verdicts is not None and set(accepted_verdicts) & set(return_targets):
                raise ValueError(
                    f"phase {item.get('phase')!r} accepted_verdicts and return_targets overlap"
                )
        terminal_verdicts = item.get("terminal_verdicts")
        if terminal_verdicts is not None:
            if not isinstance(terminal_verdicts, dict) or not terminal_verdicts:
                raise ValueError(
                    f"phase {item.get('phase')!r} terminal_verdicts must be a non-empty object"
                )
            if not item.get("formal_gate") or item.get("human_checkpoint"):
                raise ValueError(
                    f"phase {item.get('phase')!r} terminal_verdicts require a reviewer-owned formal Gate"
                )
            for decision, terminal in terminal_verdicts.items():
                if not isinstance(decision, str) or not decision or not isinstance(terminal, dict):
                    raise ValueError(
                        f"phase {item.get('phase')!r} terminal_verdicts are invalid"
                    )
                if terminal != {
                    "action": "terminate_scientific_core",
                    "status": "SCIENTIFIC_NO_GO",
                }:
                    raise ValueError(
                        f"phase {item.get('phase')!r} terminal verdict {decision!r} must use the canonical scientific terminal"
                    )
            accepted = set(accepted_verdicts or [])
            returns = set((return_targets or {}).keys())
            terminals = set(terminal_verdicts)
            if accepted & terminals or returns & terminals:
                raise ValueError(
                    f"phase {item.get('phase')!r} accepted_verdicts, return_targets, and terminal_verdicts must be pairwise disjoint"
                )
    return workflow


def _workflow_phase(state: dict, phase: str) -> Optional[dict]:
    workflow = state.get("workflow") or {}
    for item in workflow.get("phases", []):
        if item.get("phase") == phase:
            return item
    return None


def _resolve_artifact_refs(workflow: dict, paths: list[str], phase: str) -> list[str]:
    manifest = workflow.get("artifact_manifest", {})
    resolved = []
    for raw in paths:
        if isinstance(raw, str) and raw.startswith("@artifact:"):
            key = raw[len("@artifact:"):]
            try:
                resolved.append(manifest[key])
            except KeyError as exc:  # validated on workflow load; keep state safe too
                raise ValueError(
                    f"phase {phase!r} references unknown artifact {key!r}"
                ) from exc
        else:
            resolved.append(raw)
    return resolved


def _is_terminal(state: dict, status: str, phase: Optional[str] = None) -> bool:
    if status in _terminal_statuses(state):
        return True
    # Non-gate modules only need execution completeness. Formal gates still
    # require an explicit accepted/provisional/human decision.
    if status == "done" and phase is not None:
        spec = _workflow_phase(state, phase)
        return bool(spec is not None and not spec.get("formal_gate", False))
    return False


def _check_paths(root: str, paths: list[str], kind: str, phase: str) -> None:
    missing = []
    for raw in paths:
        path = Path(raw)
        if not path.is_absolute():
            path = Path(root) / path
        if not path.exists():
            missing.append(raw)
    if missing:
        raise ValueError(
            f"phase {phase!r} cannot proceed: missing {kind} artifact(s): {missing}"
        )


def _artifact_path(root: str, raw: str) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else Path(root) / path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_hashes(root: str, paths: list[str]) -> dict[str, str]:
    return {raw: _sha256(_artifact_path(root, raw)) for raw in paths}


def _root_cause_formal_evidence_sources(
    root: str,
    state: dict,
    *,
    contract_path: str,
    capsule_path: str,
    analysis: dict,
    output_paths: list[str],
    current_incremental_evidence_ids: set[str] | None = None,
) -> tuple[str, dict[str, str], list[dict[str, str]]]:
    """Resolve diagnosis references against the current accepted problem.

    The accepted Capsule freezes the problem handoff. During the declared
    root-cause phase, the existing literature gateway may additionally bind
    Controller-registered Evidence Cards as *phase-scoped diagnostic evidence*;
    those cards supplement diagnosis only and never alter the accepted Capsule.
    Newly collected diagnostic pilots remain separately registered evidence.
    """

    from arisctl.validators import (
        ValidationError,
        root_cause_problem_handoff,
        validate_root_cause_diagnostic_pilots,
    )

    core = state.get("scientific_core") or {}
    active = core.get("active_problem_version")
    if not isinstance(active, dict) or not isinstance(active.get("problem_id"), str):
        raise ValueError("root-cause analysis requires an active accepted problem version")
    if (
        active.get("contract_path") != contract_path
        or active.get("evidence_capsule_path") != capsule_path
        or active.get("contract_sha256") != _sha256(_artifact_path(root, contract_path))
        or active.get("evidence_capsule_sha256") != _sha256(_artifact_path(root, capsule_path))
    ):
        raise ValueError("root-cause inputs no longer match the active accepted problem version")
    try:
        contract_problem_id, capsule_evidence_ids = root_cause_problem_handoff(
            _artifact_path(root, contract_path).read_text(encoding="utf-8"),
            _artifact_path(root, capsule_path).read_text(encoding="utf-8"),
        )
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc
    if contract_problem_id != active["problem_id"]:
        raise ValueError("root-cause inputs do not identify the active accepted problem")

    evidence_sources: dict[str, str] = {}
    research = state.get("research_lit") or {}
    accepted_evidence = research.get("accepted_artifacts") or {}
    registry_path = _artifact_path(root, "idea-stage/EVIDENCE_REGISTRY.jsonl")
    registry_ids: set[str] = set()
    if registry_path.is_file():
        try:
            registry_ids = {
                str(row["source_id"])
                for row in (
                    json.loads(line)
                    for line in registry_path.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                )
                if isinstance(row, dict) and isinstance(row.get("source_id"), str)
            }
        except json.JSONDecodeError as exc:
            raise ValueError("Evidence Registry must remain valid JSONL") from exc
    registered_nonliterature: dict[str, dict] = {}
    for record in (core.get("accepted_artifacts") or {}).values():
        if not isinstance(record, dict):
            continue
        artifact_id = record.get("artifact_id")
        binding = record.get("problem_version_binding")
        source_type = record.get("evidence_source_type")
        if (
            isinstance(artifact_id, str)
            and isinstance(binding, dict)
            and binding.get("problem_id") == active["problem_id"]
            and binding.get("version") == active.get("version")
            and binding.get("contract_sha256") == active.get("contract_sha256")
            and binding.get("evidence_capsule_sha256") == active.get("evidence_capsule_sha256")
            and source_type in {"existing_experiment", "dataset", "real_world"}
        ):
            registered_nonliterature[artifact_id] = record
    for evidence_id in capsule_evidence_ids:
        record = accepted_evidence.get(f"evidence:{evidence_id}")
        if isinstance(record, dict) and record.get("validator_result") == "PASS":
            path = record.get("path")
            digest = record.get("sha256")
            if not isinstance(path, str) or not isinstance(digest, str):
                raise ValueError(f"accepted Evidence Registry card {evidence_id!r} is incomplete")
            card_path = _artifact_path(root, path)
            if not card_path.is_file() or _sha256(card_path) != digest or evidence_id not in registry_ids:
                raise ValueError(
                    f"problem Capsule evidence {evidence_id!r} no longer matches the accepted Evidence Registry"
                )
            evidence_sources[evidence_id] = "literature"
            continue
        nonliterature = registered_nonliterature.get(evidence_id)
        if not isinstance(nonliterature, dict):
            raise ValueError(
                f"problem Capsule evidence {evidence_id!r} is not a current problem-bound Evidence Card or artifact"
            )
        path = nonliterature.get("path")
        digest = nonliterature.get("sha256")
        if not isinstance(path, str) or not isinstance(digest, str):
            raise ValueError(f"registered problem evidence {evidence_id!r} is incomplete")
        source_path = _artifact_path(root, path)
        if not source_path.is_file() or _sha256(source_path) != digest:
            raise ValueError(f"registered problem evidence {evidence_id!r} has changed")
        evidence_sources[evidence_id] = str(nonliterature["evidence_source_type"])

    # The gateway is the sole source of post-acceptance literature. These cards
    # are deliberately not merged into the accepted Capsule: they are valid only
    # for this root-cause analysis and are snapshotted in the phase handoff.
    incremental = (research.get("incremental_evidence_by_phase") or {}).get(
        "root_cause_analysis"
    )
    if incremental is not None:
        if not isinstance(incremental, dict):
            raise ValueError("root-cause phase-scoped evidence registry is invalid")
        for record in incremental.values():
            if not isinstance(record, dict):
                raise ValueError("root-cause phase-scoped evidence record is invalid")
            path, digest = record.get("path"), record.get("sha256")
            if not isinstance(path, str) or not isinstance(digest, str):
                raise ValueError("root-cause phase-scoped evidence record is incomplete")
            card_path = _artifact_path(root, path)
            if not card_path.is_file() or _sha256(card_path) != digest:
                raise ValueError("root-cause phase-scoped Evidence Card has changed")
            try:
                card = json.loads(card_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise ValueError("root-cause phase-scoped Evidence Card must be valid JSON") from exc
            evidence_id = card.get("source_id") if isinstance(card, dict) else None
            if not isinstance(evidence_id, str) or not evidence_id:
                raise ValueError("root-cause phase-scoped Evidence Card has no source_id")
            if (
                current_incremental_evidence_ids is not None
                and evidence_id not in current_incremental_evidence_ids
            ):
                continue
            if evidence_id in evidence_sources:
                # It is already part of the immutable problem handoff; it is not
                # a distinct diagnosis-only source.
                continue
            evidence_sources[evidence_id] = "literature"

    provenance = analysis.get("analysis_provenance")
    if not isinstance(provenance, dict):
        raise ValueError("root-cause analysis_provenance must be an object")
    try:
        diagnostic_pilots = validate_root_cause_diagnostic_pilots(provenance)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc
    output_files = {_artifact_path(root, path).resolve() for path in output_paths}
    root_path = Path(root).resolve()
    for artifact in diagnostic_pilots:
        if Path(artifact["path"]).is_absolute():
            raise ValueError(
                f"root-cause diagnostic pilot {artifact['artifact_id']!r} must use a project-relative path"
            )
        source_path = _artifact_path(root, artifact["path"]).resolve()
        try:
            source_path.relative_to(root_path)
        except ValueError as exc:
            raise ValueError(
                f"root-cause diagnostic pilot {artifact['artifact_id']!r} must be inside the project"
            ) from exc
        if source_path in output_files:
            raise ValueError("root-cause diagnostic pilots cannot be diagnosis output artifacts")
        if not source_path.is_file() or _sha256(source_path) != artifact["sha256"]:
            raise ValueError(
                f"root-cause diagnostic pilot {artifact['artifact_id']!r} does not match its declared file hash"
            )
        if artifact["artifact_id"] in evidence_sources:
            raise ValueError(
                f"root-cause diagnostic pilot ID duplicates formal evidence: {artifact['artifact_id']}"
            )
        evidence_sources[artifact["artifact_id"]] = artifact["evidence_source_type"]
    return str(active["problem_id"]), evidence_sources, diagnostic_pilots


def _assert_coverage_requirement(state: dict, spec: dict, phase: str) -> None:
    coverage = spec.get("requires_coverage")
    if not coverage:
        return
    required_phase = _find_phase(state, coverage["phase"])
    allowed = set(coverage["statuses"])
    actual = required_phase.get("coverage_status")
    if actual not in allowed:
        raise ValueError(
            f"phase {phase!r} requires coverage status in {sorted(allowed)}, "
            f"but {coverage['phase']!r} is {actual!r}"
        )


def _assert_validated_artifacts(root: str, state: dict, spec: dict, phase: str) -> None:
    workflow = state.get("workflow") or {}
    for requirement in spec.get("requires_validated_artifacts", []):
        source_phase = _find_phase(state, requirement["phase"])
        registered = source_phase.get("validated_artifacts")
        if not isinstance(registered, dict):
            raise ValueError(
                f"phase {phase!r} requires validated artifacts from {requirement['phase']!r}, "
                "but no validation snapshot is registered"
            )
        paths = _resolve_artifact_refs(workflow, requirement["artifacts"], phase)
        _check_paths(root, paths, "validated input", phase)
        for raw in paths:
            expected = registered.get(raw)
            actual = _sha256(_artifact_path(root, raw))
            if not expected or actual != expected:
                raise ValueError(
                    f"phase {phase!r} cannot proceed: validated artifact {raw!r} "
                    f"from {requirement['phase']!r} is missing its snapshot or has changed"
                )


def _assert_dependencies(root: str, state: dict, spec: dict, phase: str) -> None:
    dependencies = spec.get("depends_on", [])
    if not dependencies:
        return
    by_name = {item["phase"]: item for item in state["phases"]}
    not_ready = [
        dependency for dependency in dependencies
        if not _is_terminal(state, by_name[dependency]["status"], dependency)
    ]
    if not_ready:
        raise ValueError(
            f"phase {phase!r} is blocked by non-terminal dependencies: {not_ready}"
        )
    _check_paths(
        root,
        _resolve_artifact_refs(state.get("workflow") or {}, spec.get("required_inputs", []), phase),
        "required input",
        phase,
    )
    _assert_coverage_requirement(state, spec, phase)
    _assert_validated_artifacts(root, state, spec, phase)


def _method_principle_context(root: str, state: dict) -> dict:
    core = state.get("scientific_core") or {}
    active = core.get("active_problem_version")
    required = ("problem_id", "version", "contract_sha256", "evidence_capsule_sha256")
    if not isinstance(active, dict) or any(active.get(field) in (None, "") for field in required):
        raise ValueError("method work requires an active accepted Problem version")
    workflow = state.get("workflow") or {}
    try:
        raw_path = workflow["artifact_manifest"]["root_cause_analysis"]
        analysis_path = _artifact_path(root, raw_path)
        analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
    except (KeyError, OSError, json.JSONDecodeError) as exc:
        raise ValueError("method work cannot read the accepted root-cause analysis") from exc
    analysis_id = analysis.get("analysis_id") if isinstance(analysis, dict) else None
    chains = analysis.get("primary_causal_chain_ids") if isinstance(analysis, dict) else None
    if not isinstance(analysis_id, str) or not analysis_id or not isinstance(chains, list) or not chains:
        raise ValueError("method work has no machine-resolvable accepted RCA handoff")
    if any(not isinstance(item, str) or not item for item in chains):
        raise ValueError("accepted RCA primary causal-chain IDs are invalid")
    rival_rca_ids = {
        str(alternative["explanation_id"])
        for chain in analysis.get("causal_chains") or []
        if isinstance(chain, dict) and chain.get("chain_id") in set(chains)
        for alternative in chain.get("alternative_explanations") or []
        if isinstance(alternative, dict)
        and isinstance(alternative.get("explanation_id"), str)
        and alternative["explanation_id"]
    }
    return {
        "problem_version": dict(active),
        "root_cause_analysis_id": analysis_id,
        "root_cause_analysis_sha256": _sha256(analysis_path),
        "primary_causal_chain_ids": set(chains),
        "rival_rca_ids": rival_rca_ids,
    }


def _latest_return_feedback_ref(state: dict, phase: str) -> str | None:
    for event in reversed((state.get("scientific_core") or {}).get("return_history") or []):
        if isinstance(event, dict) and event.get("return_target") == phase:
            event_id = event.get("id")
            return event_id if isinstance(event_id, str) and event_id else None
    return None


def _combine_sources_for_method_design_return(
    state: dict,
) -> set[tuple[str, str]] | None:
    from arisctl.validators import ValidationError

    for event in reversed((state.get("scientific_core") or {}).get("return_history") or []):
        if not isinstance(event, dict) or event.get("return_target") != "method_design":
            continue
        if event.get("decision") != "combine":
            return None
        packet_path = str(
            ((state.get("workflow") or {}).get("artifact_manifest") or {}).get(
                "method_design_packet"
            )
            or ""
        )
        approval_request_id = event.get("approval_request_id")
        approval = next(
            (
                item
                for item in reversed((state.get("scientific_core") or {}).get("approvals") or [])
                if isinstance(item, dict)
                and item.get("approval_request_id") == approval_request_id
                and item.get("gate") == "principle_selection"
                and item.get("decision") == "combine"
            ),
            None,
        )
        approval_bindings = (approval or {}).get("artifact_bindings")
        expected_hash = (
            approval_bindings.get(packet_path)
            if isinstance(approval_bindings, dict)
            else None
        )
        if event.get("combine_source_packet") != {
            "path": packet_path,
            "sha256": expected_hash,
        }:
            raise ValidationError(
                "Human combine source Candidate lineage is not bound to the reviewed packet"
            )
        raw_sources = event.get("combine_source_candidates")
        if not isinstance(raw_sources, list) or len(raw_sources) < 2:
            raise ValidationError("Human combine return has no valid source Candidate lineage")
        sources: set[tuple[str, str]] = set()
        for item in raw_sources:
            if not isinstance(item, dict):
                raise ValidationError("Human combine source Candidate lineage is invalid")
            principle_id = item.get("principle_id")
            principle_version = item.get("principle_version")
            if (
                not isinstance(principle_id, str)
                or not principle_id
                or not isinstance(principle_version, str)
                or not principle_version
            ):
                raise ValidationError("Human combine source Candidate lineage is invalid")
            sources.add((principle_id, principle_version))
        if len(sources) != len(raw_sources):
            raise ValidationError("Human combine source Candidate lineage contains duplicates")
        return sources
    return None


def _load_scientific_history(root: str, state: dict) -> list[dict]:
    workflow = state.get("workflow") or {}
    manifest = workflow.get("artifact_manifest") or {}
    events: list[dict] = []
    for name in ("method_principles", "method_test_evidence"):
        raw_path = manifest.get(name)
        if not isinstance(raw_path, str):
            continue
        path = _artifact_path(root, raw_path)
        if not path.is_file():
            continue
        try:
            rows = [
                json.loads(line)
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        except json.JSONDecodeError as exc:
            raise ValueError(f"{name} must remain valid JSONL") from exc
        if any(not isinstance(row, dict) or not isinstance(row.get("event_id"), str) for row in rows):
            raise ValueError(f"{name} contains an invalid history event")
        events.extend(rows)
    return events


def _relevant_scientific_history_events(root: str, state: dict, packet: dict) -> list[dict]:
    context_ids: set[str] = set()
    for field, identifier in (
        ("required_mechanism_changes", "mechanism_change_id"),
        ("required_capabilities", "capability_id"),
        ("design_obligations", "obligation_id"),
        ("candidate_principles", "principle_id"),
        ("discriminating_tests", "test_id"),
    ):
        for item in packet.get(field) or []:
            if isinstance(item, dict) and isinstance(item.get(identifier), str):
                context_ids.add(item[identifier])
    for item in packet.get("candidate_principles") or []:
        if not isinstance(item, dict):
            continue
        principle_id = item.get("principle_id")
        principle_version = item.get("principle_version")
        if isinstance(principle_id, str) and isinstance(principle_version, (str, int)):
            context_ids.add(f"principle:{principle_id}@{principle_version}")
        for assumption in item.get("fatal_assumptions") or []:
            if isinstance(assumption, dict) and isinstance(assumption.get("assumption_id"), str):
                context_ids.add(assumption["assumption_id"])
        for prediction in item.get("predictions") or []:
            if isinstance(prediction, dict) and isinstance(prediction.get("prediction_id"), str):
                context_ids.add(prediction["prediction_id"])
    context_ids.update((packet.get("root_cause_binding") or {}).get("causal_chain_ids") or [])
    relevant: list[dict] = []
    for event in _load_scientific_history(root, state):
        if event.get("cycle_id") in {
            packet.get("cycle_id"), packet.get("design_cycle_id")
        }:
            continue
        event_ids: set[str] = set()
        for field in ("principle_id", "test_id", "cycle_id", "execution_set_id"):
            value = event.get(field)
            if isinstance(value, str):
                event_ids.add(value)
        if isinstance(event.get("principle_id"), str) and isinstance(
            event.get("principle_version"), (str, int)
        ):
            event_ids.add(
                f"principle:{event['principle_id']}@{event['principle_version']}"
            )
        event_ids.update(
            value
            for value in event.get("scientific_context_refs") or []
            if isinstance(value, str)
        )
        for target in event.get("targets") or []:
            if isinstance(target, dict):
                event_ids.update(str(value) for value in target.values() if isinstance(value, (str, int)))
        if event_ids & context_ids:
            relevant.append(event)
    return relevant


def _relevant_scientific_history_refs(root: str, state: dict, packet: dict) -> set[str]:
    return {
        event["event_id"]
        for event in _relevant_scientific_history_events(root, state, packet)
    }


def _accepted_json_artifact(root: str, state: dict, manifest_name: str) -> tuple[dict, str]:
    workflow = state.get("workflow") or {}
    raw_path = str(workflow["artifact_manifest"][manifest_name])
    record = ((state.get("scientific_core") or {}).get("accepted_artifacts") or {}).get(raw_path)
    path = _artifact_path(root, raw_path)
    if (
        not isinstance(record, dict)
        or not path.is_file()
        or record.get("sha256") != _sha256(path)
    ):
        raise ValueError(f"{manifest_name} is not a current Controller-accepted artifact")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{manifest_name} must be valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{manifest_name} must be a JSON object")
    return payload, raw_path


def _accepted_necessity_binding(root: str, state: dict) -> dict:
    """Return the exact accepted residual-failure handoff required by RCA."""

    workflow = state.get("workflow") or {}
    if state.get("controller_managed"):
        closure, closure_path = _accepted_json_artifact(root, state, "necessity_closure")
        verdict, verdict_path = _accepted_json_artifact(root, state, "necessity_verdict")
    else:
        closure_path = str(workflow["artifact_manifest"]["necessity_closure"])
        verdict_path = str(workflow["artifact_manifest"]["necessity_verdict"])
        try:
            closure = json.loads(_artifact_path(root, closure_path).read_text(encoding="utf-8"))
            verdict = json.loads(_artifact_path(root, verdict_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("root-cause analysis requires readable accepted Necessity artifacts") from exc
    phase = _find_phase(state, "problem_necessity")
    if phase.get("status") != "accepted" or verdict.get("decision") != "RESIDUAL_SAME_PROBLEM":
        raise ValueError("root-cause analysis requires accepted RESIDUAL_SAME_PROBLEM Necessity")
    if verdict.get("necessity_id") != closure.get("necessity_id"):
        raise ValueError("accepted Necessity Closure and Verdict identities do not match")
    closure_sha256 = _sha256(_artifact_path(root, closure_path))
    verdict_sha256 = _sha256(_artifact_path(root, verdict_path))
    if verdict.get("reviewed_closure_sha256") != closure_sha256:
        raise ValueError("accepted Necessity Verdict is stale for the current Closure")
    residuals = closure.get("residual_failure_envelope")
    if not isinstance(residuals, list) or not residuals:
        raise ValueError("accepted residual Necessity has no Residual Failure Envelope")
    residual_ids = [
        item.get("residual_failure_id") for item in residuals if isinstance(item, dict)
    ]
    if (
        len(residual_ids) != len(residuals)
        or any(not isinstance(item, str) or not item for item in residual_ids)
        or len(residual_ids) != len(set(residual_ids))
    ):
        raise ValueError("accepted Necessity has invalid residual failure identities")
    return {
        "necessity_id": closure["necessity_id"],
        "closure_sha256": closure_sha256,
        "verdict_id": verdict["verdict_id"],
        "verdict_sha256": verdict_sha256,
        "residual_failure_ids": residual_ids,
    }


def _method_design_query_plan_provenance(root: str, state: dict) -> dict[str, dict]:
    """Resolve immutable Method Design Query Plans in acceptance order."""

    research = state.get("research_lit") or {}
    records: list[dict] = [
        item for item in research.get("query_plan_history") or [] if isinstance(item, dict)
    ]
    current = (research.get("accepted_artifacts") or {}).get(
        "incremental-query-plan-method_design"
    )
    current_digest = str(current.get("sha256") or "") if isinstance(current, dict) else ""
    if isinstance(current, dict):
        records.append(current)
    ordered = sorted(
        records,
        key=lambda item: str(item.get("accepted_at") or ""),
    )
    resolved: dict[str, dict] = {}
    for order, record in enumerate(ordered):
        digest = str(record.get("sha256") or "")
        raw_path = record.get("archive_path") or record.get("path")
        path = _artifact_path(root, str(raw_path or ""))
        if not digest or not path.is_file() or _sha256(path) != digest:
            raise ValueError("Method Design Query Plan provenance is stale")
        try:
            plan = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("Method Design Query Plan provenance is invalid JSON") from exc
        context = plan.get("method_design_context") if isinstance(plan, dict) else None
        if not isinstance(context, dict):
            continue
        principle_context = context.get("principle_search_context") or {}
        resolved[digest] = {
            "order": order,
            "search_step_by_plan_item": {
                str(item.get("plan_item_id")): str(item.get("search_step"))
                for item in plan.get("queries") or []
                if isinstance(item, dict) and item.get("plan_item_id") and item.get("search_step")
            },
            "domain_hypothesis_ids": [
                item["domain_hypothesis_id"]
                for item in principle_context.get("domain_hypotheses") or []
                if isinstance(item, dict) and isinstance(item.get("domain_hypothesis_id"), str)
            ],
            "terminology_map_ids": [
                item["terminology_map_id"]
                for item in principle_context.get("terminology_maps") or []
                if isinstance(item, dict) and isinstance(item.get("terminology_map_id"), str)
            ],
            "evidence_ids_by_plan_item": {},
            "completed_query_ids_by_plan_item": {},
            "is_current": digest == current_digest,
        }
    if current_digest and current_digest not in resolved:
        raise ValueError("current Method Design Query Plan provenance is invalid")

    terminal_ledger_query_ids: set[str] = set()
    search_log_path = str(
        ((state.get("workflow") or {}).get("artifact_manifest") or {}).get("search_log")
        or ""
    )
    search_log = _artifact_path(root, search_log_path)
    if search_log.is_file():
        for line_number, line in enumerate(
            search_log.read_text(encoding="utf-8").splitlines(), 1
        ):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Search Ledger has invalid JSON at line {line_number}"
                ) from exc
            if (
                isinstance(row, dict)
                and row.get("run_id") == state.get("run_id")
                and row.get("action") == "query"
                and row.get("result_status")
                in {"complete", "complete_human", "complete_with_human_followup"}
                and isinstance(row.get("query_id"), str)
                and row["query_id"]
            ):
                terminal_ledger_query_ids.add(row["query_id"])

    query_events = research.get("query_events") or {}
    for query_id, event in query_events.items():
        if (
            not isinstance(query_id, str)
            or not isinstance(event, dict)
            or event.get("status") not in {"complete", "complete_human"}
            or query_id not in terminal_ledger_query_ids
        ):
            continue
        plan_sha256 = str(event.get("query_plan_sha256") or "")
        plan_record = resolved.get(plan_sha256)
        plan_item_id = event.get("plan_item_id")
        if (
            not isinstance(plan_record, dict)
            or not isinstance(plan_item_id, str)
            or plan_item_id not in plan_record["search_step_by_plan_item"]
        ):
            continue
        plan_record["completed_query_ids_by_plan_item"].setdefault(
            plan_item_id, []
        ).append(query_id)
    evidence_records: dict[str, dict] = {
        key: value
        for key, value in (research.get("accepted_artifacts") or {}).items()
        if key.startswith("evidence:") and isinstance(value, dict)
    }
    evidence_records.update({
        key: value
        for key, value in (
            ((research.get("incremental_evidence_by_phase") or {}).get("method_design") or {})
        ).items()
        if key.startswith("evidence:") and isinstance(value, dict)
    })
    for artifact_name, record in evidence_records.items():
        path = _artifact_path(root, str(record.get("path") or ""))
        digest = str(record.get("sha256") or "")
        if not digest or not path.is_file() or _sha256(path) != digest:
            raise ValueError("Method Design Evidence provenance is stale")
        try:
            card = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("Method Design Evidence provenance is invalid JSON") from exc
        context = card.get("method_design_search_context") if isinstance(card, dict) else None
        if not isinstance(context, dict):
            continue
        plan_sha256 = str(context.get("query_plan_sha256") or "")
        plan_record = resolved.get(plan_sha256)
        if not isinstance(plan_record, dict):
            raise ValueError("Method Design Evidence cites an unknown accepted Query Plan")
        evidence_id = str(card.get("source_id") or artifact_name.split(":", 1)[1])
        for query_id in context.get("actual_hit_query_ids") or []:
            event = query_events.get(query_id)
            plan_item_id = event.get("plan_item_id") if isinstance(event, dict) else None
            if (
                not isinstance(plan_item_id, str)
                or event.get("query_plan_sha256") != plan_sha256
                or event.get("status") not in {"complete", "complete_human"}
            ):
                raise ValueError("Method Design Evidence has stale query-event provenance")
            plan_record["evidence_ids_by_plan_item"].setdefault(plan_item_id, []).append(
                evidence_id
            )
    for plan_record in resolved.values():
        plan_record["evidence_ids_by_plan_item"] = {
            plan_item_id: sorted(set(evidence_ids))
            for plan_item_id, evidence_ids in plan_record["evidence_ids_by_plan_item"].items()
        }
        plan_record["completed_query_ids_by_plan_item"] = {
            plan_item_id: sorted(set(query_ids))
            for plan_item_id, query_ids in plan_record[
                "completed_query_ids_by_plan_item"
            ].items()
        }
    return resolved


def _validate_method_main_artifact(
    root: str,
    state: dict,
    spec: dict,
    phase: str,
    *,
    current_phase_evidence_ids: set[str] | None = None,
) -> dict:
    from arisctl.validators import (
        ValidationError,
        validate_final_proposal_for_principle,
        validate_method_design_packet,
        validate_principle_test_plan,
        validate_principle_evaluation,
        validate_necessity_closure,
    )

    workflow = state.get("workflow") or {}
    contracts = workflow.get("artifact_contracts") or {}
    output_paths = _resolve_artifact_refs(workflow, spec.get("produced_artifacts", []), phase)
    try:
        if phase == "problem_necessity":
            closure_path = str(workflow["artifact_manifest"]["necessity_closure"])
            closure = json.loads(_artifact_path(root, closure_path).read_text(encoding="utf-8"))
            problem_version = (state.get("scientific_core") or {}).get("active_problem_version")
            if not isinstance(problem_version, dict):
                raise ValidationError("Necessity requires an active accepted Problem")
            current_ids = (
                current_phase_evidence_ids
                if current_phase_evidence_ids is not None
                else set(_current_formal_evidence_paths(root, state))
            )
            validated = validate_necessity_closure(
                closure,
                contract=contracts["necessity_closure"],
                run_id=state["run_id"],
                problem_version=problem_version,
                current_evidence_ids=current_ids,
            )
            return {
                "closure": validated,
                "necessity_id": validated["necessity_id"],
                "residual_failure_ids": [
                    item["residual_failure_id"]
                    for item in validated["residual_failure_envelope"]
                ],
            }
        context = _method_principle_context(root, state)
        if phase == "method_design":
            packet_path = str(workflow["artifact_manifest"]["method_design_packet"])
            packet = json.loads(_artifact_path(root, packet_path).read_text(encoding="utf-8"))
            search_record = ((state.get("research_lit") or {}).get("accepted_artifacts") or {}).get(
                "incremental-query-plan-method_design"
            )
            if isinstance(search_record, dict):
                search_path = _artifact_path(root, str(search_record.get("path") or ""))
                if not search_path.is_file() or search_record.get("sha256") != _sha256(search_path):
                    raise ValidationError("current Principle-search Query Plan is not a registered artifact")
                search_context = json.loads(search_path.read_text(encoding="utf-8")).get(
                    "method_design_context"
                )
                if not isinstance(search_context, dict) or any(
                    packet.get(field) != search_context.get(field)
                    for field in (
                        "required_mechanism_changes", "required_capabilities", "design_obligations"
                    )
                ):
                    raise ValidationError(
                        "method design packet does not preserve the accepted Principle-search RMC binding"
                    )
            return validate_method_design_packet(
                packet,
                contract=contracts["method_design_packet"],
                problem_version=context["problem_version"],
                root_cause_analysis_id=context["root_cause_analysis_id"],
                root_cause_analysis_sha256=context["root_cause_analysis_sha256"],
                primary_causal_chain_ids=context["primary_causal_chain_ids"],
                rival_rca_ids=context["rival_rca_ids"],
                current_evidence_ids=current_phase_evidence_ids,
                required_history_refs=_relevant_scientific_history_refs(root, state, packet),
                required_return_ref=_latest_return_feedback_ref(state, phase),
                required_combine_sources=_combine_sources_for_method_design_return(state),
                query_plan_provenance=_method_design_query_plan_provenance(root, state),
            )
        if phase == "principle_test_design":
            packet, _ = _accepted_json_artifact(root, state, "method_design_packet")
            selection = (state.get("scientific_core") or {}).get("selected_for_testing")
            if not isinstance(selection, dict) or selection.get("status") != "ACTIVE":
                raise ValidationError("Principle test design requires an active Human selection")
            candidate = next(
                (
                    item for item in packet.get("candidate_principles") or []
                    if str(item.get("principle_id")) == str(selection.get("principle_id"))
                    and str(item.get("principle_version")) == str(selection.get("principle_version"))
                    and item.get("status") in {"ACTIVE", "REVISED", "WEAKENED"}
                ),
                None,
            )
            if candidate is None:
                raise ValidationError("active Human selection does not resolve to a reviewed Candidate")
            plan_path = str(workflow["artifact_manifest"]["principle_test_plan"])
            plan = json.loads(_artifact_path(root, plan_path).read_text(encoding="utf-8"))
            return validate_principle_test_plan(
                plan,
                contract=contracts["principle_test_plan"],
                selected_for_testing=selection,
                candidate=candidate,
                required_history_refs=_relevant_scientific_history_refs(
                    root, state, {**packet, "cycle_id": plan["cycle_id"]}
                ),
                required_return_ref=_latest_return_feedback_ref(state, phase),
            )
        if phase == "principle_evaluation":
            packet, _ = _accepted_json_artifact(root, state, "method_design_packet")
            test_plan, _ = _accepted_json_artifact(root, state, "principle_test_plan")
            necessity, _ = _accepted_json_artifact(root, state, "necessity_closure")
            evidence_context, evidence_path = _accepted_json_artifact(
                root, state, "principle_evidence_context"
            )
            evaluation_path = str(workflow["artifact_manifest"]["principle_evaluation"])
            evaluation = json.loads(
                _artifact_path(root, evaluation_path).read_text(encoding="utf-8")
            )
            cycle = (state.get("scientific_core") or {}).get("method_test_cycle") or {}
            evidence_record = ((state.get("scientific_core") or {}).get("accepted_artifacts") or {}).get(evidence_path)
            evidence_ref = {
                "path": evidence_path,
                "sha256": str((evidence_record or {}).get("sha256") or ""),
            }
            current_refs = set(evidence_context.get("current_evidence_refs") or [])
            for item in evidence_context.get("result_refs") or []:
                if isinstance(item, dict) and isinstance(item.get("path"), str):
                    current_refs.add(item["path"])
            selection = (state.get("scientific_core") or {}).get("selected_for_testing") or {}
            candidate = next(
                (
                    item
                    for item in packet.get("candidate_principles") or []
                    if str(item.get("principle_id")) == str(selection.get("principle_id"))
                    and str(item.get("principle_version")) == str(selection.get("principle_version"))
                ),
                None,
            )
            if candidate is None:
                raise ValidationError("Principle evaluation cannot resolve the Human-selected Candidate")
            return {
                "evaluation": validate_principle_evaluation(
                    evaluation,
                    contract=contracts["principle_evaluation"],
                    cycle_id=str(cycle.get("cycle_id") or ""),
                    execution_set_id=str(cycle.get("execution_set_id") or ""),
                    evidence_context_ref=evidence_ref,
                    test_plan=test_plan,
                    candidate=candidate,
                    root_cause_analysis_id=str(packet["root_cause_binding"]["analysis_id"]),
                    necessity_residual_ids={
                        str(item["residual_failure_id"])
                        for item in necessity["residual_failure_envelope"]
                    },
                    current_evidence_refs=current_refs,
                    required_history_refs=_relevant_scientific_history_refs(
                        root, state, {**packet, "cycle_id": cycle.get("cycle_id")}
                    ),
                    required_return_ref=_latest_return_feedback_ref(state, phase),
                )
            }
        if phase == "method_refinement":
            selected_path = str(workflow["artifact_manifest"]["selected_principle"])
            selected_record = ((state.get("scientific_core") or {}).get("accepted_artifacts") or {}).get(selected_path)
            path = _artifact_path(root, selected_path)
            if not isinstance(selected_record, dict) or not path.is_file() or selected_record.get("sha256") != _sha256(path):
                raise ValidationError("method refinement requires the active Controller-selected Principle")
            selected = yaml.safe_load(path.read_text(encoding="utf-8"))
            if not isinstance(selected, dict):
                raise ValidationError("Selected Principle must be a YAML object")
            proposal_path = str(workflow["artifact_manifest"]["final_proposal"])
            text = _artifact_path(root, proposal_path).read_text(encoding="utf-8")
            validate_final_proposal_for_principle(
                text,
                selected_principle=selected,
                required_sections=list(contracts["final_proposal"]["required_sections"]),
            )
            return {"selected_principle": selected}
    except (ValidationError, OSError, json.JSONDecodeError, yaml.YAMLError, KeyError) as exc:
        raise ValueError(f"phase {phase!r} has an invalid Principle-first method artifact: {exc}") from exc
    return {}


def _validate_principle_method_outputs(
    root: str,
    state: dict,
    spec: dict,
    phase: str,
    output_paths: list[str],
    *,
    current_phase_evidence_ids: set[str] | None = None,
) -> dict | None:
    if phase not in {"problem_necessity", "method_design", "principle_test_design", "principle_evaluation", "method_refinement"}:
        return None
    from arisctl.validators import (
        ValidationError,
        validate_json_review_verdict_artifact,
        validate_method_design_view,
        validate_principle_test_plan_view,
        validate_necessity_verdict,
    )

    main = _validate_method_main_artifact(
        root,
        state,
        spec,
        phase,
        current_phase_evidence_ids=current_phase_evidence_ids,
    )
    workflow = state.get("workflow") or {}
    request = _find_phase(state, phase).get("review_request")
    if not isinstance(request, dict) or request.get("reviewed_artifacts_pending"):
        return None
    result: dict = {"validated_artifacts": _artifact_hashes(root, output_paths)}
    try:
        if phase == "problem_necessity":
            closure = main["closure"]
            closure_path = str(workflow["artifact_manifest"]["necessity_closure"])
            verdict_path = str(workflow["artifact_manifest"]["necessity_verdict"])
            problem_version = (state.get("scientific_core") or {}).get("active_problem_version")
            if not isinstance(problem_version, dict):
                raise ValidationError("Necessity review requires an active accepted Problem")
            verdict = validate_necessity_verdict(
                json.loads(_artifact_path(root, verdict_path).read_text(encoding="utf-8")),
                contract=(workflow.get("artifact_contracts") or {})["necessity_verdict"],
                run_id=state["run_id"],
                request_id=request["id"],
                artifact_bindings=request["artifact_bindings"],
                closure=closure,
                reviewed_closure_sha256=_sha256(_artifact_path(root, closure_path)),
                problem_contract_sha256=problem_version["contract_sha256"],
                evidence_capsule_sha256=problem_version["evidence_capsule_sha256"],
            )
            result.update(
                necessity_id=closure["necessity_id"],
                residual_failure_ids=main["residual_failure_ids"],
            )
        elif phase == "method_design":
            packet = main["packet"]
            view_path = str(workflow["artifact_manifest"]["method_design_view"])
            validate_method_design_view(_artifact_path(root, view_path).read_text(encoding="utf-8"), packet)
            verdict_path = str(workflow["artifact_manifest"]["method_design_review"])
            verdict = validate_json_review_verdict_artifact(
                json.loads(_artifact_path(root, verdict_path).read_text(encoding="utf-8")),
                label="method design review",
                request_id=request["id"],
                artifact_bindings=request["artifact_bindings"],
                decisions=set(request["allowed_review_verdicts"]),
                reviewed_artifact_path=str(workflow["artifact_manifest"]["method_design_packet"]),
            )
            result.update(
                design_cycle_id=main["design_cycle_id"],
            )
        elif phase == "principle_test_design":
            plan = main["plan"]
            view_path = str(workflow["artifact_manifest"]["principle_test_plan_view"])
            validate_principle_test_plan_view(
                _artifact_path(root, view_path).read_text(encoding="utf-8"), plan
            )
            verdict_path = str(workflow["artifact_manifest"]["principle_test_plan_review"])
            verdict = validate_json_review_verdict_artifact(
                json.loads(_artifact_path(root, verdict_path).read_text(encoding="utf-8")),
                label="Principle test plan review",
                request_id=request["id"],
                artifact_bindings=request["artifact_bindings"],
                decisions=set(request["allowed_review_verdicts"]),
                reviewed_artifact_path=str(workflow["artifact_manifest"]["principle_test_plan"]),
            )
            result.update(
                cycle_id=main["cycle_id"],
                execution_set_id=main["execution_set_id"],
                test_ids=main["test_ids"],
            )
        elif phase == "principle_evaluation":
            verdict_path = str(workflow["artifact_manifest"]["principle_evaluation_verdict"])
            verdict = validate_json_review_verdict_artifact(
                json.loads(_artifact_path(root, verdict_path).read_text(encoding="utf-8")),
                label="Principle convergence review",
                request_id=request["id"],
                artifact_bindings=request["artifact_bindings"],
                decisions=set(request["allowed_review_verdicts"]),
                reviewed_artifact_path=str(workflow["artifact_manifest"]["principle_evaluation"]),
            )
            if verdict["decision"] == "PRINCIPLE_CONVERGED":
                if any(
                    not isinstance(verdict.get(field), (str, int))
                    or str(verdict[field]).strip() == ""
                    for field in ("selected_principle_id", "selected_principle_version")
                ):
                    raise ValidationError("PRINCIPLE_CONVERGED requires one selected Principle ID/version")
                if not isinstance(verdict.get("accepted_boundary_update_ids"), list):
                    raise ValidationError(
                        "PRINCIPLE_CONVERGED requires accepted boundary update IDs"
                    )
                result["selected_principle_id"] = str(verdict["selected_principle_id"])
                result["selected_principle_version"] = str(verdict["selected_principle_version"])
                boundary_ids = verdict["accepted_boundary_update_ids"]
                if not isinstance(boundary_ids, list) or any(
                    not isinstance(item, str) or not item for item in boundary_ids
                ) or len(boundary_ids) != len(set(boundary_ids)):
                    raise ValidationError(
                        "PRINCIPLE_CONVERGED accepted_boundary_update_ids must be unique string IDs"
                    )
                evaluation = main["evaluation"]
                updates = {
                    str(item["update_id"]): item
                    for item in evaluation["scientific_updates"]
                }
                if not set(boundary_ids) <= set(updates) or any(
                    updates[item]["consequence"] != "UPDATE_BOUNDARY"
                    for item in boundary_ids
                ):
                    raise ValidationError(
                        "PRINCIPLE_CONVERGED may accept only reviewed UPDATE_BOUNDARY records"
                    )
                result["accepted_boundary_update_ids"] = list(boundary_ids)
            elif any(
                field in verdict
                for field in (
                    "selected_principle_id",
                    "selected_principle_version",
                    "accepted_boundary_update_ids",
                )
            ):
                raise ValidationError(
                    "non-converged Principle verdict must not carry Selected Principle authority"
                )
        else:
            return None
    except (ValidationError, OSError, json.JSONDecodeError, KeyError) as exc:
        raise ValueError(f"phase {phase!r} has an invalid formal method review: {exc}") from exc
    result.update(
        gate_verdict=verdict["decision"],
        verdict_id=verdict["verdict_id"],
        reviewer=verdict["reviewer"],
        review_request_id=verdict["review_request_id"],
        reviewed_artifact_hashes=verdict["reviewed_artifact_hashes"],
        return_guidance=verdict.get("return_guidance"),
    )
    return result


def _assert_outputs(
    root: str,
    state: dict,
    spec: dict,
    phase: str,
    *,
    current_phase_evidence_ids: set[str] | None = None,
) -> Optional[dict]:
    workflow = state.get("workflow") or {}
    output_paths = _resolve_artifact_refs(workflow, spec.get("produced_artifacts", []), phase)
    _check_paths(
        root,
        output_paths,
        "required handoff",
        phase,
    )
    method_result = _validate_principle_method_outputs(
        root,
        state,
        spec,
        phase,
        output_paths,
        current_phase_evidence_ids=current_phase_evidence_ids,
    )
    if phase == "problem_generation":
        from arisctl.validators import validate_problem_candidates_artifact

        candidate_index = _artifact_path(root, output_paths[1])
        try:
            result = validate_problem_candidates_artifact(
                candidate_index.read_text(encoding="utf-8"),
                label="problem candidates",
                formal_evidence_ids=(
                    current_phase_evidence_ids
                    if current_phase_evidence_ids is not None
                    else set(_current_formal_evidence_paths(root, state))
                    if state.get("controller_managed")
                    else None
                ),
            )
        except ValueError as exc:
            raise ValueError(f"phase {phase!r} has invalid problem candidates: {exc}") from exc
        return {
            "validated_artifacts": _artifact_hashes(root, output_paths),
            **result,
        }
    if spec.get("gate_id") == "landscape_sufficiency":
        try:
            from literature_coverage_audit import audit_landscape
        except ImportError:  # package import: ``from tools import run_state``
            from tools.literature_coverage_audit import audit_landscape
        result = audit_landscape(root, state.get("workflow") or {})
        if not result["ok"]:
            raise ValueError(
                f"phase {phase!r} has invalid landscape handoff: "
                + "; ".join(result["errors"])
            )
        return result
    if spec.get("gate_id") == "root_cause_analysis_completeness":
        from arisctl.validators import (
            load_json,
            validate_root_cause_analysis,
            validate_root_cause_view,
        )

        input_paths = _resolve_artifact_refs(workflow, spec.get("required_inputs", []), phase)
        problem_contract, evidence_capsule, necessity_closure, necessity_verdict = input_paths
        analysis_path = output_paths[0]
        problem_hash = _sha256(_artifact_path(root, problem_contract))
        evidence_hash = _sha256(_artifact_path(root, evidence_capsule))
        raw_analysis = load_json(_artifact_path(root, analysis_path))
        accepted_necessity = _accepted_necessity_binding(root, state)
        active_problem_id: str | None = None
        formal_evidence_sources: dict[str, str] | None = None
        diagnostic_pilots: list[dict[str, str]] = []
        if state.get("controller_managed"):
            active_problem_id, formal_evidence_sources, diagnostic_pilots = (
                _root_cause_formal_evidence_sources(
                    root,
                    state,
                    contract_path=problem_contract,
                    capsule_path=evidence_capsule,
                    analysis=raw_analysis,
                    output_paths=output_paths,
                    current_incremental_evidence_ids=current_phase_evidence_ids,
                )
            )
        analysis = validate_root_cause_analysis(
            raw_analysis,
            run_id=state["run_id"],
            problem_contract_sha256=problem_hash,
            evidence_capsule_sha256=evidence_hash,
            active_problem_id=active_problem_id,
            formal_evidence_sources=formal_evidence_sources,
            necessity_binding=accepted_necessity,
        )
        validate_root_cause_view(
            _artifact_path(root, output_paths[1]).read_text(encoding="utf-8"),
            analysis,
        )
        return {
            "validated_artifacts": _artifact_hashes(
                root, [*input_paths, *output_paths]
            ),
            "analysis_id": analysis["analysis_id"],
            "problem_contract_sha256": problem_hash,
            "evidence_capsule_sha256": evidence_hash,
            "necessity_id": accepted_necessity["necessity_id"],
            "necessity_closure_sha256": accepted_necessity["closure_sha256"],
            "necessity_verdict_sha256": accepted_necessity["verdict_sha256"],
            "residual_failure_ids": list(accepted_necessity["residual_failure_ids"]),
            "diagnostic_pilot_artifacts": diagnostic_pilots,
        }
    if spec.get("gate_id") == "root_cause_quality":
        from arisctl.validators import load_json, validate_root_cause_verdict

        input_paths = _resolve_artifact_refs(workflow, spec.get("required_inputs", []), phase)
        (
            problem_contract,
            evidence_capsule,
            necessity_closure,
            necessity_verdict,
            analysis_path,
            _analysis_view,
        ) = input_paths
        verdict_path = output_paths[0]
        analysis = load_json(_artifact_path(root, analysis_path))
        verdict = validate_root_cause_verdict(
            load_json(_artifact_path(root, verdict_path)),
            run_id=state["run_id"],
            analysis_id=analysis["analysis_id"],
            reviewed_analysis_sha256=_sha256(_artifact_path(root, analysis_path)),
            problem_contract_sha256=_sha256(_artifact_path(root, problem_contract)),
            evidence_capsule_sha256=_sha256(_artifact_path(root, evidence_capsule)),
            necessity_closure_sha256=_sha256(_artifact_path(root, necessity_closure)),
            necessity_verdict_sha256=_sha256(_artifact_path(root, necessity_verdict)),
        )
        return {
            "validated_artifacts": _artifact_hashes(root, output_paths),
            "gate_verdict": verdict["decision"],
            "verdict_id": verdict["verdict_id"],
            "reviewer": verdict["reviewer"],
            "reviewed_analysis_sha256": verdict["reviewed_analysis_sha256"],
        }
    verdict_contracts = {
        "problem_quality": (
            "candidate",
            {"CERTIFIED", "HOLD", "REJECT", "BLOCKED"},
            {"CERTIFIED", "HOLD", "REJECT", "BLOCKED"},
            "problem quality verdicts",
        ),
        "problem_novelty": (
            "candidate",
            {"NOVEL", "UNCERTAIN", "NOT_NOVEL", "BLOCKED"},
            {"NOVEL", "UNCERTAIN", "NOT_NOVEL", "BLOCKED"},
            "problem novelty verdicts",
        ),
        "method_refinement": (
            "markdown",
            set(spec.get("accepted_verdicts") or [])
            | set((spec.get("return_targets") or {}).keys())
            | set((spec.get("terminal_verdicts") or {}).keys()),
            None,
            "final blind review",
        ),
        "method_novelty_final": (
            "markdown",
            set(spec.get("accepted_verdicts") or [])
            | set((spec.get("return_targets") or {}).keys())
            | set((spec.get("terminal_verdicts") or {}).keys()),
            None,
            "final method novelty verdict",
        ),
    }


    contract = verdict_contracts.get(spec.get("gate_id"))
    request = _find_phase(state, phase).get("review_request")
    # Legacy run-state runs do not issue Controller review requests.  Their
    # mutation API is intentionally not an alternate formal route; only a live
    # Controller request can establish the closure below.
    if contract and isinstance(request, dict):
        if request.get("reviewed_artifacts_pending"):
            return None
        request_id = request.get("id")
        bindings = request.get("artifact_bindings")
        if not isinstance(request_id, str) or not isinstance(bindings, dict):
            raise ValueError(f"phase {phase!r} has no valid live review request")
        from arisctl.validators import (
            validate_candidate_verdict_artifact,
            validate_markdown_review_verdict_artifact,
        )

        kind, phase_decisions, candidate_decisions, label = contract
        try:
            if kind == "candidate":
                expected_candidate_ids: set[str] | None = None
                if phase == "problem_quality_gate":
                    expected_candidate_ids = set(
                        (_find_phase(state, "problem_generation").get("candidate_ids") or [])
                    )
                elif phase == "problem_novelty_gate":
                    expected_candidate_ids = set(
                        (_find_phase(state, "problem_quality_gate").get("survivor_ids") or [])
                    )
                if not expected_candidate_ids:
                    raise ValueError(f"phase {phase!r} has no accepted candidate survivors to review")
                verdict = validate_candidate_verdict_artifact(
                    _artifact_path(root, output_paths[0]).read_text(encoding="utf-8"),
                    label=label,
                    request_id=request_id,
                    artifact_bindings=bindings,
                    phase_decisions=phase_decisions,
                    candidate_decisions=candidate_decisions or set(),
                    expected_candidate_ids=expected_candidate_ids,
                    review_kind=("quality" if phase == "problem_quality_gate" else "novelty"),
                    formal_evidence_paths=_current_formal_evidence_paths(root, state),
                    formal_evidence_source_ids=_current_decision_grade_evidence_card_source_ids(root, state),
                )
            else:
                verdict = validate_markdown_review_verdict_artifact(
                    _artifact_path(root, output_paths[1] if spec.get("gate_id") == "method_refinement" else output_paths[0]).read_text(encoding="utf-8"),
                    label=label,
                    request_id=request_id,
                    artifact_bindings=bindings,
                    decisions=phase_decisions,
                )
                if verdict["decision"] in (spec.get("return_targets") or {}):
                    return_guidance = verdict.get("return_guidance")
                    if not isinstance(return_guidance, dict) or not return_guidance:
                        raise ValueError(
                            f"{label} requires non-empty structured return_guidance for a return verdict"
                        )
        except ValueError as exc:
            raise ValueError(f"phase {phase!r} has invalid {label}: {exc}") from exc
        return {
            "validated_artifacts": _artifact_hashes(root, output_paths),
            "gate_verdict": verdict["decision"],
            "verdict_id": verdict["verdict_id"],
            "reviewer": verdict["reviewer"],
            "review_request_id": verdict["review_request_id"],
            "reviewed_artifact_hashes": verdict["reviewed_artifact_hashes"],
            **(
                {
                    "candidate_ids": verdict["candidate_ids"],
                    "survivor_ids": verdict["survivor_ids"],
                    **(
                        {"return_guidance": verdict["return_guidance"]}
                        if "return_guidance" in verdict
                        else {}
                    ),
                }
                if kind == "candidate"
                else (
                    {"return_guidance": verdict["return_guidance"]}
                    if verdict["decision"] in (spec.get("return_targets") or {})
                    else {}
                )
            ),
            **(method_result or {}),
        }
    return method_result


def _current_formal_evidence_paths(root: str, state: dict) -> dict[str, str]:
    """Return current, Controller-accepted evidence IDs and their artifact paths.

    Problem discovery can cite the existing literature Evidence Cards. Existing
    non-literature artifacts are included when they already have a Controller
    registration, preserving the same resolution rule used by the later problem
    Capsule handoff.
    """

    paths: dict[str, str] = {}
    research = state.get("research_lit") or {}
    for key, record in (research.get("accepted_artifacts") or {}).items():
        if not isinstance(key, str) or not key.startswith("evidence:") or not isinstance(record, dict):
            continue
        evidence_id = key.split(":", 1)[1]
        raw_path = record.get("path")
        digest = record.get("sha256")
        candidate = _artifact_path(root, str(raw_path or ""))
        if (
            record.get("validator_result") == "PASS"
            and isinstance(raw_path, str)
            and isinstance(digest, str)
            and candidate.is_file()
            and _sha256(candidate) == digest
        ):
            paths[evidence_id] = raw_path
    core = state.get("scientific_core") or {}
    for record in (core.get("accepted_artifacts") or {}).values():
        if not isinstance(record, dict):
            continue
        evidence_id = record.get("artifact_id")
        raw_path = record.get("path")
        digest = record.get("sha256")
        candidate = _artifact_path(root, str(raw_path or ""))
        if (
            isinstance(evidence_id, str)
            and evidence_id
            and isinstance(raw_path, str)
            and isinstance(digest, str)
            and candidate.is_file()
            and _sha256(candidate) == digest
        ):
            if evidence_id in paths and paths[evidence_id] != raw_path:
                raise ValueError(f"formal evidence ID {evidence_id!r} resolves to multiple artifacts")
            paths[evidence_id] = raw_path
    return paths


def _current_decision_grade_evidence_card_source_ids(root: str, state: dict) -> dict[str, str]:
    """Resolve existing admitted Evidence Card source IDs for novelty identity checks."""

    sources: dict[str, str] = {}
    research = state.get("research_lit") or {}
    for key, record in (research.get("accepted_artifacts") or {}).items():
        if not isinstance(key, str) or not key.startswith("evidence:") or not isinstance(record, dict):
            continue
        evidence_id = key.split(":", 1)[1]
        raw_path = record.get("path")
        digest = record.get("sha256")
        path = _artifact_path(root, str(raw_path or ""))
        if (
            record.get("validator_result") != "PASS"
            or not isinstance(raw_path, str)
            or not isinstance(digest, str)
            or not path.is_file()
            or _sha256(path) != digest
        ):
            continue
        try:
            card = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"accepted Evidence Card {evidence_id!r} is not valid JSON") from exc
        paper = (research.get("papers") or {}).get(evidence_id)
        source_id = card.get("source_id") if isinstance(card, dict) else None
        if (
            source_id != evidence_id
            or not isinstance(paper, dict)
        ):
            raise ValueError(
                f"accepted Evidence Card {evidence_id!r} no longer matches its global paper identity"
            )
        sources[evidence_id] = source_id
    return sources


def _assert_acceptance_matches_gate(
    root: str,
    state: dict,
    spec: Optional[dict],
    phase: str,
    verdict_id: str,
    reviewer: str,
) -> None:
    if spec is None or not spec.get("accepted_verdicts"):
        return
    _assert_dependencies(root, state, spec, phase)
    result = _assert_outputs(root, state, spec, phase) or {}
    if "gate_verdict" not in result:
        return
    allowed = set(spec["accepted_verdicts"])
    if result.get("gate_verdict") not in allowed:
        raise ValueError(
            f"phase {phase!r} verdict {result.get('gate_verdict')!r} does not authorize acceptance; "
            f"expected one of {sorted(allowed)}"
        )
    if result.get("verdict_id") != verdict_id or result.get("reviewer") != reviewer:
        raise ValueError(
            f"phase {phase!r} acceptance provenance must match the validated verdict artifact"
        )
    request = _find_phase(state, phase).get("review_request")
    if isinstance(request, dict) and "review_request_id" in result:
        if (
            result.get("review_request_id") != request.get("id")
            or result.get("reviewed_artifact_hashes") != request.get("artifact_bindings")
        ):
            raise ValueError(
                f"phase {phase!r} acceptance provenance must match the live review request"
            )


def start_run(root: str, run_id: str, phases: list[str], executor: Optional[str] = "claude",
              provisional_advances: bool = False, workflow_path: Optional[str] = None) -> dict:
    """Create a run with ordered phases, all `pending` (idempotent: won't clobber).

    ``claude`` is the historical mainline executor default. Codex-native callers
    must record ``--executor codex-gpt-5.6-sol`` (or their actual executor) so a
    same-family review cannot be misclassified as independent acceptance.
    ``provisional_advances`` is the per-run policy that lets a same-family
    provisional verdict close a phase for RESUME purposes (Codex-native mirror:
    true; mainline default: false — only cross-family acceptance advances).
    """
    workflow = _load_workflow(workflow_path)
    if workflow is not None:
        phases = [item["phase"] for item in workflow["phases"]]
    with _lock(root, run_id):
        if _run_path(root, run_id).exists():
            return _load(root, run_id)
        state = {
            "run_id": run_id,
            "executor_model": executor,
            "executor_family": model_family(executor) if executor else None,
            "policy": {"provisional_advances": bool(provisional_advances)},
            "workflow": workflow or {},
            "created": _now(),
            "updated": _now(),
            "phases": [{"phase": ph, "status": "pending", "artifact": None,
                        "verdict_id": None, "reviewer": None,
                        "reviewer_family": None, "review_independence": None,
                        "acceptance_status": None, "executor_model": executor,
                        "executor_family": model_family(executor) if executor else None,
                        "human_decision": None,
                        "updated": _now()} for ph in phases],
        }
        _save(root, run_id, state)
        return state


def _find_phase(state: dict, phase: str) -> dict:
    for ph in state["phases"]:
        if ph["phase"] == phase:
            return ph
    raise KeyError(f"phase {phase!r} not in run (have: {[p['phase'] for p in state['phases']]})")


def set_status(root: str, run_id: str, phase: str, status: str, artifact: Optional[str] = None) -> dict:
    """Executor-side status; acceptance statuses use their dedicated APIs."""
    if status not in EXECUTOR_STATUSES:
        raise ValueError(
            f"set_status may only write {sorted(EXECUTOR_STATUSES)}; "
            "'accepted' and 'provisional' require recorded review provenance.")
    with _lock(root, run_id):
        state = _load(root, run_id)
        _assert_not_controller_managed(state)
        ph = _find_phase(state, phase)
        spec = _workflow_phase(state, phase)
        if spec is not None:
            if status == "running":
                _assert_dependencies(root, state, spec, phase)
            elif status == "done":
                if ph["status"] not in ("running", "done"):
                    raise ValueError(
                        f"phase {phase!r} must be running before done; current={ph['status']!r}"
                    )
                _assert_dependencies(root, state, spec, phase)
                validation_result = _assert_outputs(root, state, spec, phase)
                if validation_result is not None:
                    if "coverage_status" in validation_result:
                        ph["coverage_status"] = validation_result["coverage_status"]
                    for key in (
                        "validated_artifacts", "analysis_id", "problem_contract_sha256",
                        "evidence_capsule_sha256", "gate_verdict", "verdict_id", "reviewer",
                        "reviewed_analysis_sha256",
                    ):
                        if key in validation_result:
                            ph[key] = validation_result[key]
        ph["status"] = status
        if artifact is not None:
            ph["artifact"] = artifact
        ph["updated"] = _now()
        _save(root, run_id, state)
        return state


def approve_human(root: str, run_id: str, phase: str, decision: str,
                  selected_id: Optional[str] = None, note: Optional[str] = None) -> dict:
    """Record an explicit human checkpoint without impersonating a reviewer.

    Human checkpoints may be approved while their phase is pending, provided
    dependencies and required inputs are satisfied. The decision is durable and
    separate from model acceptance provenance.
    """
    if not decision.strip():
        raise ValueError("human approval requires a non-empty decision")
    with _lock(root, run_id):
        state = _load(root, run_id)
        _assert_not_controller_managed(state)
        ph = _find_phase(state, phase)
        spec = _workflow_phase(state, phase)
        if spec is None or not spec.get("human_checkpoint"):
            raise ValueError(f"phase {phase!r} is not a declared human checkpoint")
        _assert_dependencies(root, state, spec, phase)
        if spec.get("requires_selection") and not selected_id:
            raise ValueError(f"phase {phase!r} requires selected_id")
        if ph["status"] not in ("pending", "running", "done", "human_accepted"):
            raise ValueError(
                f"phase {phase!r} cannot receive human approval from status {ph['status']!r}"
            )
        ph["status"] = "human_accepted"
        ph["acceptance_status"] = "human_accepted"
        ph["human_decision"] = {
            "decision": decision,
            "selected_id": selected_id,
            "note": note,
            "recorded_at": _now(),
        }
        ph["updated"] = _now()
        _save(root, run_id, state)
        return state


def accept(root: str, run_id: str, phase: str, verdict_id: str, reviewer: str, force: bool = False) -> dict:
    """Mark a phase `accepted` — REQUIRES a recorded verdict id + reviewer, and
    (unless force) that the phase already be `done`.

    Call ONLY from a cross-model reviewer verdict (codex/gemini) or a deterministic
    verifier (verify_papers.py, verify_paper_audits.sh, a passing test, exit 0).
    The executor (Claude) must never call this on its own self-report.

    `verdict_id` should be a durable handle: the reviewer thread/trace id, or the
    path/sha of the verifier's report — not just a label.
    """
    if not verdict_id or not reviewer:
        raise ValueError("accept requires a non-empty verdict_id AND reviewer — "
                         "a phase cannot be accepted without recording who acquitted it.")
    with _lock(root, run_id):
        state = _load(root, run_id)
        _assert_not_controller_managed(state)
        ph = _find_phase(state, phase)
        spec = _workflow_phase(state, phase)
        if spec is not None and spec.get("human_checkpoint"):
            raise ValueError(
                f"phase {phase!r} is a human checkpoint; use approve_human, not accept"
            )
        if force and state.get("workflow"):
            raise ValueError(
                "force is limited to unstructured legacy/development runs; it cannot bypass a declared workflow Gate"
            )
        if not force and ph["status"] not in ("done", "accepted", "provisional"):
            raise ValueError(
                f"phase {phase!r} is {ph['status']!r}, not 'done' — cannot accept a phase that "
                f"has not completed execution. Set it 'done' first, or pass force=True.")
        _assert_acceptance_matches_gate(root, state, spec, phase, verdict_id, reviewer)
        # (provisional -> accepted is the intended monotonic upgrade: a later
        # cross-family overlay acquits a phase a same-family review only drove.)
        reviewer_family = model_family(reviewer)
        # Older state files predate executor provenance. They belonged to the
        # Claude mainline, whose historical executor was Claude; retain that
        # compatibility default rather than letting an absent value bless an
        # arbitrary reviewer as cross-family.
        executor_model = ph.get("executor_model") or state.get("executor_model") or "claude"
        executor_family = model_family(executor_model)
        if reviewer_family != "deterministic":
            if executor_family == "unknown" or reviewer_family == "unknown":
                raise ValueError(
                    f"cannot classify acceptance families: executor={executor_model!r} "
                    f"({executor_family}), reviewer={reviewer!r} ({reviewer_family})")
            if executor_family == reviewer_family:
                raise ValueError(
                    "accept refuses known same-family review; use mark_provisional "
                    "so the phase can advance without claiming cross-family acceptance.")
        ph["status"] = "accepted"
        ph["verdict_id"] = verdict_id
        ph["reviewer"] = reviewer
        ph["reviewer_family"] = reviewer_family
        ph["review_independence"] = (
            "deterministic" if reviewer_family == "deterministic" else "cross-family"
        )
        ph["acceptance_status"] = "accepted"
        ph["executor_model"] = executor_model
        ph["executor_family"] = executor_family
        ph["updated"] = _now()
        _save(root, run_id, state)
        return state


def mark_provisional(root: str, run_id: str, phase: str, verdict_id: str,
                     reviewer: str, executor: Optional[str] = None) -> dict:
    """Record a same-family review as terminal-but-not-accepted progress.

    The executor defaults to the model recorded by :func:`start_run`. Both
    model names must resolve to the same non-deterministic family. This lets a
    Codex-only workflow resume past a reviewed phase while keeping the absence
    of cross-family acceptance machine-readable.
    """
    if not verdict_id or not reviewer:
        raise ValueError(
            "mark_provisional requires a non-empty verdict_id AND reviewer.")
    with _lock(root, run_id):
        state = _load(root, run_id)
        _assert_not_controller_managed(state)
        ph = _find_phase(state, phase)
        spec = _workflow_phase(state, phase)
        if spec is not None and spec.get("human_checkpoint"):
            raise ValueError(
                f"phase {phase!r} is a human checkpoint; use approve_human, not mark_provisional"
            )
        if ph["status"] not in ("done", "provisional"):
            raise ValueError(
                f"phase {phase!r} is {ph['status']!r}, not 'done' — cannot mark a "
                "phase provisional before execution completes.")
        _assert_acceptance_matches_gate(root, state, spec, phase, verdict_id, reviewer)
        executor_model = executor or ph.get("executor_model") or state.get("executor_model")
        if not executor_model:
            raise ValueError(
                "mark_provisional requires an executor model, either from start_run "
                "or the executor argument.")
        executor_family = model_family(executor_model)
        reviewer_family = model_family(reviewer)
        if executor_family == "unknown" or reviewer_family == "unknown":
            raise ValueError(
                f"cannot classify provisional executor/reviewer families: "
                f"{executor_model!r}={executor_family}, {reviewer!r}={reviewer_family}")
        if reviewer_family == "deterministic" or executor_family != reviewer_family:
            raise ValueError(
                "mark_provisional is only for same-family model review; use accept "
                "for cross-family or deterministic verdicts.")
        ph["status"] = "provisional"
        ph["verdict_id"] = verdict_id
        ph["reviewer"] = reviewer
        ph["reviewer_family"] = reviewer_family
        ph["review_independence"] = "same-family"
        ph["acceptance_status"] = "provisional"
        ph["executor_model"] = executor_model
        ph["executor_family"] = executor_family
        ph["updated"] = _now()
        _save(root, run_id, state)
        return state


def resume_point(root: str, run_id: str) -> Optional[dict]:
    """First phase whose status is NOT terminal — the resume
    target — or None if the run is complete.

    A `done`-but-not-`accepted` phase IS a resume target: its cross-model audit is
    still owed and must run before the next phase proceeds.
    """
    state = _load(root, run_id)
    for ph in state["phases"]:
        if not _is_terminal(state, ph["status"], ph["phase"]):
            return ph
    return None


def _print_status(state: dict) -> None:
    print(f"run {state['run_id']}  (updated {state.get('updated', '?')})")
    glyph = {"pending": "·", "running": "▶", "done": "✓(unaccepted)",
             "failed": "✗", "accepted": "✅", "provisional": "⚠ provisional",
             "skipped": "⊘(skipped)"}
    for ph in state["phases"]:
        line = f"  {glyph.get(ph['status'], '?'):>14}  {ph['phase']}  [{ph['status']}]"
        if ph["status"] in ("accepted", "provisional"):
            line += f"  ← {ph['reviewer']} / {ph['verdict_id']}"
        elif ph["status"] == "human_accepted":
            decision = ph.get("human_decision") or {}
            line += f"  decision={decision.get('selected_id') or decision.get('decision')}"
        elif ph["artifact"]:
            line += f"  → {ph['artifact']}"
        print(line)
    rp = next((p for p in state["phases"] if not _is_terminal(state, p["status"], p["phase"])), None)
    print(f"  resume → {rp['phase'] if rp else 'COMPLETE (all phases terminal; provisional is not accepted)'}")


def main() -> int:
    ap = argparse.ArgumentParser(description="ARIS resumable run-state (done vs accepted).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("start"); s.add_argument("root"); s.add_argument("run_id"); s.add_argument("--phases", default="", help="comma-separated phase names (optional when --workflow is supplied)"); s.add_argument("--workflow", help="JSON-compatible YAML workflow spec"); s.add_argument("--executor", default="claude"); s.add_argument("--provisional-advances", action="store_true", help="per-run policy: let a same-family provisional verdict close a phase for resume (Codex-native mirror only; mainline default keeps cross-family-only advance)")
    s = sub.add_parser("set"); s.add_argument("root"); s.add_argument("run_id"); s.add_argument("phase"); s.add_argument("status", choices=sorted(EXECUTOR_STATUSES)); s.add_argument("--artifact")
    s = sub.add_parser("accept"); s.add_argument("root"); s.add_argument("run_id"); s.add_argument("phase"); s.add_argument("--verdict-id", required=True); s.add_argument("--reviewer", required=True); s.add_argument("--force", action="store_true")
    s = sub.add_parser("mark-provisional"); s.add_argument("root"); s.add_argument("run_id"); s.add_argument("phase"); s.add_argument("--verdict-id", required=True); s.add_argument("--reviewer", required=True); s.add_argument("--executor")
    s = sub.add_parser("approve"); s.add_argument("root"); s.add_argument("run_id"); s.add_argument("phase"); s.add_argument("--decision", required=True); s.add_argument("--selected-id"); s.add_argument("--note")
    s = sub.add_parser("resume"); s.add_argument("root"); s.add_argument("run_id")
    s = sub.add_parser("status"); s.add_argument("root"); s.add_argument("run_id")
    s = sub.add_parser("list"); s.add_argument("root")
    a = ap.parse_args()

    try:
        if a.cmd == "start":
            phases = [p.strip() for p in a.phases.split(",") if p.strip()]
            if not phases and not a.workflow:
                raise ValueError("start requires --phases or --workflow")
            _print_status(start_run(a.root, a.run_id, phases, executor=a.executor, provisional_advances=a.provisional_advances, workflow_path=a.workflow))
        elif a.cmd == "set":
            _print_status(set_status(a.root, a.run_id, a.phase, a.status, a.artifact))
        elif a.cmd == "accept":
            _print_status(accept(a.root, a.run_id, a.phase, a.verdict_id, a.reviewer, force=a.force))
        elif a.cmd == "mark-provisional":
            _print_status(mark_provisional(a.root, a.run_id, a.phase, a.verdict_id, a.reviewer, executor=a.executor))
        elif a.cmd == "approve":
            _print_status(approve_human(a.root, a.run_id, a.phase, a.decision, selected_id=a.selected_id, note=a.note))
        elif a.cmd == "resume":
            rp = resume_point(a.root, a.run_id)
            if rp is None:
                print("COMPLETE"); return 0
            print(rp["phase"])  # machine-readable: the resume target phase name
            print(json.dumps(rp), file=sys.stderr)
        elif a.cmd == "status":
            _print_status(_load(a.root, a.run_id))
        elif a.cmd == "list":
            d = Path(a.root) / ".aris" / "runs"
            for f in sorted(d.glob("*.json")) if d.exists() else []:
                print(f.stem)
    except (FileNotFoundError, KeyError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr); return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
