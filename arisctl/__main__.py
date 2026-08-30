"""Controller CLI whose Human Gates are confirmed in the Codex approval UI."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import yaml

from . import approvals
from . import reviews
from .controller import ARISController, ControllerError
from .recovery import save_recovery_snapshot
from .transcript_attestation import attest_review_transcript
from .gateways import (
    HumanSearchRequired,
    ProviderUnavailable,
    ScholarQueryOptions,
    crossref_openalex_verify_metadata,
    research_literature_search,
    open_access_fulltext,
)


def _emit(text: str) -> None:
    """Write UTF-8 CLI output without depending on the host text encoding."""

    output = text + "\n"
    stream = sys.stdout
    buffer = getattr(stream, "buffer", None)
    if buffer is None:
        stream.write(output)
        stream.flush()
        return
    stream.flush()
    buffer.write(output.encode("utf-8"))
    buffer.flush()


def _emit_json(value: object) -> None:
    _emit(json.dumps(value, ensure_ascii=False, indent=2))


def _json_file(path: str) -> dict:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON artifact must be an object")
    return value


def _yaml_mapping_file(path: str) -> dict:
    try:
        value = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"YAML artifact is invalid: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("YAML artifact must be an object")
    return value


def _controller(args: argparse.Namespace) -> ARISController:
    return ARISController(args.root, args.run_id)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="arisctl")
    parser.add_argument("--root", default=".")
    sub = parser.add_subparsers(dest="command", required=True)

    start = sub.add_parser("start")
    start.add_argument("run_id")
    start.add_argument("--executor", required=True)

    save_recovery = sub.add_parser("save-recovery")
    save_recovery.add_argument("run_id")
    save_recovery.add_argument("destination")

    migrate = sub.add_parser("migrate-legacy")
    migrate.add_argument("run_id")
    migrate.add_argument("--executor", required=True)

    migrate_workflow = sub.add_parser("migrate-workflow")
    migrate_workflow.add_argument("run_id")

    for name in (
        "status",
        "allowed-actions",
        "allowed-agents",
        "validation-handoff",
        "finish-retrieval",
        "finish-reading",
        "start-phase",
        "complete-phase",
        "refresh-review-request",
        "method-test-handoff",
    ):
        command = sub.add_parser(name)
        command.add_argument("run_id")

    approve = sub.add_parser("human-approve")
    approve.add_argument("run_id")
    approve.add_argument(
        "gate",
        choices=(
            "source_policy_approval",
            "scope_human_approval",
            "problem_acceptance",
            "principle_selection",
            "principle_test_approval",
            "method_acceptance",
        ),
    )
    approve.add_argument(
        "--decision",
        choices=("approve", "select", "request_revision", "combine", "reject"),
        required=True,
    )
    approve.add_argument("--selected-id")
    approve.add_argument("--human-feedback")

    revise_policy = sub.add_parser("request-source-policy-revision")
    revise_policy.add_argument("run_id")


    revise_problem = sub.add_parser("revise-problem")
    revise_problem.add_argument("run_id")
    revise_problem.add_argument(
        "--reason",
        required=True,
        help="scientific evidence or reasoning that requires an explicit problem revision",
    )

    accept_phase = sub.add_parser("accept-phase")
    accept_phase.add_argument("run_id")
    accept_phase.add_argument("--verdict-id", required=True)
    accept_phase.add_argument("--reviewer", required=True)

    terminate_core = sub.add_parser("terminate-scientific-core")
    terminate_core.add_argument("run_id")
    terminate_core.add_argument("--verdict-id", required=True)
    terminate_core.add_argument("--reviewer", required=True)

    return_phase = sub.add_parser("return-phase")
    return_phase.add_argument("run_id")
    return_phase.add_argument("--verdict-id", required=True)
    return_phase.add_argument("--reviewer", required=True)
    return_phase.add_argument(
        "--lesson-file",
        help=(
            "optional JSON with failure_phenomenon, wrong_assumption_or_reason, "
            "evidence_refs, and future_check; use only for reusable lessons"
        ),
    )

    method_test_result = sub.add_parser("submit-method-test-result")
    method_test_result.add_argument("run_id")
    method_test_result.add_argument("json_file")

    policy = sub.add_parser("submit-source-policy")
    policy.add_argument("run_id")
    policy.add_argument("yaml_file")

    plan = sub.add_parser("submit-query-plan")
    plan.add_argument("run_id")
    plan.add_argument("json_file")

    query = sub.add_parser("query")
    query.add_argument("run_id")
    query.add_argument("query")
    query.add_argument("--plan-item-id")
    query.add_argument("--year-from", type=int)
    query.add_argument("--year-to", type=int)
    query.add_argument("--exact-title", action="store_true")
    query.add_argument("--page", type=int, default=1)
    query.add_argument("--cited-by")

    enrich_candidate = sub.add_parser("enrich-candidate")
    enrich_candidate.add_argument("run_id")
    enrich_candidate.add_argument("paper_id")

    enrich_candidates = sub.add_parser("enrich-candidates")
    enrich_candidates.add_argument("run_id")
    enrich_candidates.add_argument("paper_ids", nargs="+")

    retry_enrichment = sub.add_parser("retry-candidate-enrichment")
    retry_enrichment.add_argument("run_id")
    retry_enrichment.add_argument("paper_id")
    retry_enrichment.add_argument("--reason", required=True)

    recover_query = sub.add_parser("recover-interrupted-query")
    recover_query.add_argument("run_id")
    recover_query.add_argument("plan_item_id")
    recover_query.add_argument("--reason", required=True)

    reconcile_query_plan = sub.add_parser("reconcile-query-plan-events")
    reconcile_query_plan.add_argument("run_id")
    reconcile_query_plan.add_argument("--reason", required=True)

    extend_budget = sub.add_parser("extend-literature-budget")
    extend_budget.add_argument("run_id")
    extend_budget.add_argument("--max-fulltext-papers", type=int)
    extend_budget.add_argument("--max-queries", type=int)
    extend_budget.add_argument("--max-search-cycles", type=int)
    extend_budget.add_argument("--reason", required=True)

    readopt_evidence = sub.add_parser("readopt-evidence")
    readopt_evidence.add_argument("run_id")
    readopt_evidence.add_argument("evidence_id")
    readopt_evidence.add_argument("--obligation-id", dest="obligation_ids", action="append")

    reopen_root_cause = sub.add_parser("reopen-root-cause")
    reopen_root_cause.add_argument("run_id")
    reopen_root_cause.add_argument("--reason", required=True)
    reopen_root_cause.add_argument("--evidence-id", dest="evidence_ids", action="append")

    human_results = sub.add_parser("submit-human-search-results")
    human_results.add_argument("run_id")
    human_results.add_argument("json_file")

    human_fulltext = sub.add_parser("submit-human-fulltext-batch")
    human_fulltext.add_argument("run_id")
    human_fulltext.add_argument("json_file")

    defer_fulltext = sub.add_parser("defer-fulltext-batch")
    defer_fulltext.add_argument("run_id")
    defer_fulltext.add_argument("paper_ids", nargs="+")
    defer_fulltext.add_argument("--reason", required=True)

    promote_user = sub.add_parser("promote-user-source")
    promote_user.add_argument("run_id")
    promote_user.add_argument("paper_id")
    promote_user.add_argument("source_path")
    promote_user.add_argument("--reason", required=True)
    promote_user.add_argument("--media-type")

    repair_corpus = sub.add_parser("repair-literature-corpus-hash-chain")
    repair_corpus.add_argument("run_id")
    repair_corpus.add_argument("--reason", required=True)

    admit = sub.add_parser("admit")
    admit.add_argument("run_id")
    admit.add_argument("paper_id")
    admit.add_argument("--out-of-scope", action="store_true")
    admit.add_argument("--duplicate", action="store_true")
    admit.add_argument(
        "--screening-basis",
        choices=(
            "TITLE_ONLY",
            "TITLE_ABSTRACT",
            "TITLE_ONLY_ABSTRACT_UNAVAILABLE",
            "FULL_TEXT",
        ),
        required=True,
    )
    admit.add_argument("--screening-reason", required=True)
    admit.add_argument(
        "--reading-priority",
        choices=(
            "RECENT_AUTHORITATIVE_REVIEWS",
            "HIGH_CITATION_BACKBONE",
            "RECENT_ELITE_FRONTIER",
            "TARGETED_GAP_FOLLOWUP",
        ),
        required=True,
    )
    admit.add_argument(
        "--abstract-only",
        action="store_true",
        help="retain an in-scope frontier/gap paper at abstract level instead of selecting full text",
    )
    admit.add_argument("--fulltext-selection-reason")
    admit.add_argument(
        "--decision-grade-exception",
        choices=(
            "decisive_closest_prior_or_concurrent",
            "negative_or_contradictory_result",
            "diagnostic_or_replication_evidence",
            "rmc_bound_source_mechanism_or_genealogy",
        ),
    )
    admit.add_argument("--exception-reason")
    admit.add_argument("--decision-target", action="append", default=[])

    admit_batch = sub.add_parser("admit-batch")
    admit_batch.add_argument("run_id")
    admit_batch.add_argument("paper_ids", nargs="+")
    admit_batch.add_argument("--out-of-scope", action="store_true")
    admit_batch.add_argument("--duplicate", action="store_true")
    admit_batch.add_argument(
        "--screening-basis",
        choices=(
            "TITLE_ONLY",
            "TITLE_ABSTRACT",
            "TITLE_ONLY_ABSTRACT_UNAVAILABLE",
            "FULL_TEXT",
        ),
        required=True,
    )
    admit_batch.add_argument("--screening-reason", required=True)
    admit_batch.add_argument(
        "--reading-priority",
        choices=(
            "RECENT_AUTHORITATIVE_REVIEWS",
            "HIGH_CITATION_BACKBONE",
            "RECENT_ELITE_FRONTIER",
            "TARGETED_GAP_FOLLOWUP",
        ),
        required=True,
    )
    admit_batch.add_argument("--abstract-only", action="store_true")
    admit_batch.add_argument("--fulltext-selection-reason")

    select_subset = sub.add_parser("select-reading-subset")
    select_subset.add_argument("run_id")
    select_subset.add_argument("paper_ids", nargs="+")
    select_subset.add_argument("--rationale", required=True)
    select_subset.add_argument(
        "--initial",
        action="store_true",
        help="bind the first Review-led or minimal-Primary initial-cognition cohort",
    )

    select_primary = sub.add_parser("select-formal-primary-subset")
    select_primary.add_argument("run_id")
    select_primary.add_argument("paper_ids", nargs="+")
    select_primary.add_argument("--rationale", required=True)

    withdraw = sub.add_parser("withdraw-admission")
    withdraw.add_argument("run_id")
    withdraw.add_argument("paper_id")
    withdraw.add_argument("--reason", required=True)

    reverify = sub.add_parser("reverify-admission")
    reverify.add_argument("run_id")
    reverify.add_argument("paper_id")
    reverify.add_argument("--reason", required=True)

    user_source = sub.add_parser("register-user-source")
    user_source.add_argument("run_id")
    user_source.add_argument("json_file")

    read_text = sub.add_parser("read-text")
    read_text.add_argument("run_id")
    read_text.add_argument("paper_id")
    read_text.add_argument("text_file")

    fetch_fulltext = sub.add_parser("fetch-fulltext")
    fetch_fulltext.add_argument("run_id")
    fetch_fulltext.add_argument("paper_id")
    fetch_fulltext.add_argument("output_file")

    read_user_fulltext = sub.add_parser("read-user-fulltext")
    read_user_fulltext.add_argument("run_id")
    read_user_fulltext.add_argument("paper_id")

    materialize_read_event = sub.add_parser("materialize-completed-read-event")
    materialize_read_event.add_argument("run_id")
    materialize_read_event.add_argument("paper_id")
    materialize_read_event.add_argument("read_event_id")

    evidence = sub.add_parser("submit-evidence")
    evidence.add_argument("run_id")
    evidence.add_argument("paper_id")
    evidence.add_argument("json_file")

    native_preflight = sub.add_parser("preflight-native-subagent")
    native_preflight.add_argument("run_id")
    native_preflight.add_argument("role", choices=("paper_reader", "coverage_reviewer"))

    field_map = sub.add_parser("submit-field-map")
    field_map.add_argument("run_id")
    field_map.add_argument("json_file")
    field_map.add_argument(
        "--review-trigger",
        choices=("candidate_sufficient", "major_taxonomy_change", "final_acceptance"),
    )

    review = sub.add_parser("submit-coverage-review")
    review.add_argument("run_id")
    review.add_argument("json_file")

    transcript_review = sub.add_parser("attest-review-transcript")
    transcript_review.add_argument("run_id")
    transcript_review.add_argument("role")
    transcript_review.add_argument("transcript_path")

    transcript_submit = sub.add_parser("submit-coverage-review-transcript")
    transcript_submit.add_argument("run_id")
    transcript_submit.add_argument("transcript_path")

    validation_result = sub.add_parser("submit-validation-result")
    validation_result.add_argument("run_id")
    validation_result.add_argument("json_file")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "start":
            controller = ARISController.start(
                args.root,
                args.run_id,
                executor=args.executor,
            )
            result = controller.status()
        elif args.command == "save-recovery":
            result = save_recovery_snapshot(args.root, args.run_id, args.destination)
        elif args.command == "migrate-legacy":
            controller = ARISController.migrate_legacy(
                args.root,
                args.run_id,
                executor=args.executor,
            )
            result = controller.status()
        else:
            controller = _controller(args)
            if args.command == "migrate-workflow":
                result = controller.migrate_workflow_if_compatible()
            elif args.command == "status":
                result = controller.status()
            elif args.command == "validation-handoff":
                result = controller.validation_handoff()
            elif args.command == "submit-validation-result":
                result = controller.submit_validation_result(_json_file(args.json_file))
            elif args.command == "allowed-actions":
                result = {"stage": controller.current_stage(), "actions": controller.allowed_actions()}
            elif args.command == "allowed-agents":
                result = {"stage": controller.current_stage(), "agents": controller.allowed_agents()}
            elif args.command == "start-phase":
                result = controller.start_current_phase()
            elif args.command == "complete-phase":
                result = controller.complete_current_phase()
            elif args.command == "refresh-review-request":
                result = controller.refresh_current_review_request()
            elif args.command == "method-test-handoff":
                result = controller.method_test_handoff()
            elif args.command == "submit-method-test-result":
                result = controller.submit_method_test_result(_json_file(args.json_file))
            elif args.command == "accept-phase":
                result = controller.accept_current_phase(
                    args.verdict_id,
                    args.reviewer,
                )
            elif args.command == "terminate-scientific-core":
                result = controller.terminate_scientific_core(
                    args.verdict_id,
                    args.reviewer,
                )
            elif args.command == "return-phase":
                result = controller.return_current_phase(
                    args.verdict_id,
                    args.reviewer,
                    lesson=(
                        _json_file(args.lesson_file)
                        if args.lesson_file is not None
                        else None
                    ),
                )
            elif args.command == "human-approve":
                request = controller.validate_human_gate_decision(
                    args.gate,
                    args.decision,
                    selected_id=args.selected_id,
                    human_feedback=args.human_feedback,
                )
                approvals.issue_ui_approval_receipt(
                    controller.root,
                    controller.run_id,
                    args.gate,
                    str(request["id"]),
                    args.decision,
                    selected_id=args.selected_id,
                    human_feedback=args.human_feedback,
                    artifact_bindings=request["artifact_bindings"],
                )
                result = controller.human_approve(
                    args.gate,
                    args.decision,
                    selected_id=args.selected_id,
                    human_feedback=args.human_feedback,
                )
            elif args.command == "request-source-policy-revision":
                request = controller.validate_human_gate_request("source_policy_approval")
                approvals.issue_ui_approval_receipt(
                    controller.root,
                    controller.run_id,
                    "source_policy_approval",
                    str(request["id"]),
                    "request_revision",
                    artifact_bindings=request["artifact_bindings"],
                )
                result = controller.request_source_policy_revision()
            elif args.command == "revise-problem":
                request = controller.request_problem_revision(args.reason)
                approvals.issue_ui_approval_receipt(
                    controller.root,
                    controller.run_id,
                    "problem_revision",
                    str(request["id"]),
                    "approve",
                    artifact_bindings=request["artifact_bindings"],
                )
                result = controller.revise_problem(args.reason)
            elif args.command == "submit-source-policy":
                result = controller.submit_source_admission_policy(
                    _yaml_mapping_file(args.yaml_file)
                )
            elif args.command == "submit-query-plan":
                result = controller.submit_query_plan(_json_file(args.json_file))
            elif args.command == "query":
                if args.page < 1:
                    raise ValueError("--page must be at least 1")
                if (
                    args.year_from is not None
                    and args.year_to is not None
                    and args.year_from > args.year_to
                ):
                    raise ValueError("--year-from cannot exceed --year-to")
                options = ScholarQueryOptions(
                    year_from=args.year_from,
                    year_to=args.year_to,
                    exact_title=args.exact_title,
                    page=args.page,
                    cited_by=args.cited_by,
                )
                result = controller.execute_query(
                    args.query,
                    "research-lit-provider-cascade",
                    lambda value: research_literature_search(value, options),
                    plan_item_id=args.plan_item_id,
                    query_options={
                        "year_from": args.year_from,
                        "year_to": args.year_to,
                        "exact_title": args.exact_title,
                        "page": args.page,
                        "cited_by": args.cited_by,
                    },
                )
            elif args.command == "enrich-candidate":
                result = controller.enrich_candidate_metadata(
                    args.paper_id,
                    identity_verifier=crossref_openalex_verify_metadata,
                )
            elif args.command == "enrich-candidates":
                candidates = []
                errors = []
                for paper_id in args.paper_ids:
                    try:
                        candidates.append(
                            controller.enrich_candidate_metadata(
                                paper_id,
                                identity_verifier=crossref_openalex_verify_metadata,
                            )
                        )
                    except Exception as exc:
                        errors.append(
                            {
                                "paper_id": paper_id,
                                "error_type": type(exc).__name__,
                                "error": str(exc),
                            }
                        )
                result = {"candidates": candidates, "errors": errors}
            elif args.command == "retry-candidate-enrichment":
                result = controller.retry_candidate_metadata_enrichment(
                    args.paper_id,
                    reason=args.reason,
                    identity_verifier=crossref_openalex_verify_metadata,
                )
            elif args.command == "recover-interrupted-query":
                result = controller.recover_interrupted_query(
                    args.plan_item_id,
                    reason=args.reason,
                )
            elif args.command == "reconcile-query-plan-events":
                result = controller.reconcile_query_plan_events(reason=args.reason)
            elif args.command == "extend-literature-budget":
                result = controller.extend_literature_budget(
                    max_fulltext_papers=args.max_fulltext_papers,
                    max_queries=args.max_queries,
                    max_search_cycles=args.max_search_cycles,
                    reason=args.reason,
                )
            elif args.command == "readopt-evidence":
                result = controller.readopt_incremental_evidence(
                    args.evidence_id,
                    obligation_ids=args.obligation_ids,
                )
            elif args.command == "reopen-root-cause":
                result = controller.reopen_root_cause(
                    args.reason,
                    evidence_ids=args.evidence_ids,
                )
            elif args.command == "submit-human-search-results":
                result = controller.submit_human_search_results(_json_file(args.json_file))
            elif args.command == "submit-human-fulltext-batch":
                result = controller.submit_human_fulltext_batch(_json_file(args.json_file))
            elif args.command == "defer-fulltext-batch":
                result = controller.defer_fulltext_to_human_batch(
                    args.paper_ids,
                    reason=args.reason,
                )
            elif args.command == "promote-user-source":
                result = controller.promote_user_source(
                    args.paper_id,
                    source_path=args.source_path,
                    reason=args.reason,
                    media_type=args.media_type,
                    identity_verifier=crossref_openalex_verify_metadata,
                )
            elif args.command == "repair-literature-corpus-hash-chain":
                result = controller.repair_literature_corpus_hash_chain(reason=args.reason)
            elif args.command == "admit":
                result = {
                    "decision": controller.decide_admission(
                        args.paper_id,
                        screening_in_scope=not args.out_of_scope,
                        duplicate=args.duplicate,
                        screening_basis=args.screening_basis,
                        screening_reason=args.screening_reason,
                        reading_priority=args.reading_priority,
                        fulltext_selected=not args.abstract_only,
                        fulltext_selection_reason=args.fulltext_selection_reason,
                        decision_grade_exception=args.decision_grade_exception,
                        exception_reason=args.exception_reason,
                        decision_targets=args.decision_target,
                        identity_verifier=crossref_openalex_verify_metadata,
                        identity_tool="crossref_openalex_metadata",
                    )
                }
            elif args.command == "admit-batch":
                result = {
                    "decisions": [
                        {
                            "paper_id": paper_id,
                            "decision": controller.decide_admission(
                                paper_id,
                                screening_in_scope=not args.out_of_scope,
                                duplicate=args.duplicate,
                                screening_basis=args.screening_basis,
                                screening_reason=args.screening_reason,
                                reading_priority=args.reading_priority,
                                fulltext_selected=not args.abstract_only,
                                fulltext_selection_reason=args.fulltext_selection_reason,
                                identity_verifier=crossref_openalex_verify_metadata,
                                identity_tool="crossref_openalex_metadata",
                            ),
                        }
                        for paper_id in args.paper_ids
                    ]
                }
            elif args.command == "withdraw-admission":
                result = {
                    "decision": controller.withdraw_admission(
                        args.paper_id,
                        reason=args.reason,
                    )
                }
            elif args.command == "reverify-admission":
                result = controller.reverify_admission(
                    args.paper_id,
                    reason=args.reason,
                    identity_verifier=crossref_openalex_verify_metadata,
                )
            elif args.command == "select-reading-subset":
                result = controller.select_reading_subset(
                    args.paper_ids,
                    rationale=args.rationale,
                    initial=args.initial,
                )
            elif args.command == "select-formal-primary-subset":
                result = controller.select_formal_primary_subset(
                    args.paper_ids,
                    rationale=args.rationale,
                )
            elif args.command == "register-user-source":
                result = controller.register_user_source(_json_file(args.json_file))
            elif args.command == "finish-retrieval":
                result = controller.finish_retrieval()
            elif args.command == "read-text":
                path = Path(args.text_file).resolve()
                result = controller.read_full_text(
                    args.paper_id,
                    "arisctl.read-text",
                    lambda _: path.read_text(encoding="utf-8"),
                )
            elif args.command == "fetch-fulltext":
                path = Path(args.output_file).resolve()

                def fetch_and_save(paper: dict) -> object:
                    payload = open_access_fulltext(paper)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(payload.content)
                    return payload

                result = controller.read_full_text(
                    args.paper_id,
                    "arisctl.fetch-fulltext.arxiv",
                    fetch_and_save,
                )
                result.pop("content", None)
                result["content_path"] = str(path)
            elif args.command == "read-user-fulltext":
                result = controller.read_registered_user_fulltext(args.paper_id)
                result.pop("content", None)
            elif args.command == "materialize-completed-read-event":
                result = controller.materialize_completed_read_event(
                    args.paper_id, args.read_event_id
                )
            elif args.command == "submit-evidence":
                result = controller.submit_evidence_card(
                    args.paper_id, _json_file(args.json_file)
                )
            elif args.command == "preflight-native-subagent":
                result = controller.preflight_native_subagent_dispatch(args.role)
            elif args.command == "finish-reading":
                result = controller.finish_reading()
            elif args.command == "submit-field-map":
                result = controller.submit_field_map(
                    _json_file(args.json_file),
                    review_trigger=args.review_trigger,
                )
            elif args.command == "submit-coverage-review":
                result = controller.submit_coverage_review(_json_file(args.json_file))
            elif args.command == "attest-review-transcript":
                result = attest_review_transcript(
                    controller.root, controller.run_id, args.role, args.transcript_path
                )
            elif args.command == "submit-coverage-review-transcript":
                request = controller.status()["research_lit"]["coverage_review_request"]
                if not isinstance(request, dict):
                    raise ControllerError("no live coverage review request")
                receipt = reviews.load_review_attestation(
                    controller.root, controller.run_id,
                    role="coverage_reviewer", request_id=str(request["id"]),
                    artifact_bindings=dict(request["artifact_bindings"]),
                )
                result = controller.submit_coverage_review(receipt["verdict_payload"])
            else:  # pragma: no cover
                raise AssertionError(args.command)
    except HumanSearchRequired as exc:
        _emit_json(exc.request)
        return 2
    except (ControllerError, FileNotFoundError, ProviderUnavailable, ValueError) as exc:
        _emit(f"error: {exc}")
        return 1
    _emit_json(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
