---
name: method-test
description: Execute only a Human-approved Principle discriminating-test set from the Controller method-test handoff, collect raw results and execution metadata, and submit terminal outcomes. It never interprets Principle support, changes Principle status, or declares convergence.
argument-hint: "<canonical-run-id>"
allowed-tools: Bash(*), Read, Write, Grep, Glob, Skill
---

# Method Test — thin approved-test orchestrator

Execute the approved Principle tests for: **$ARGUMENTS**.

## Entry gate

Require one canonical Controller run ID. Ask:

```text
python -m arisctl --root . allowed-actions <run_id>
```

Proceed only while `principle_evaluation` is pending and the Controller exposes
`method_test_handoff` and/or `submit_method_test_result`. Obtain the only
authorized execution contract:

```text
python -m arisctl --root . method-test-handoff <run_id>
```

Require `handoff_type: APPROVED_METHOD_TEST_EXECUTION_SET`, the run ID,
`cycle_id`, `execution_set_id`, `approved_test_ids`, estimated total cost,
complete test records, and `handoff_sha256`. Do not reconstruct or extend this
set from `METHOD_DESIGN_PACKET.json`, `PRINCIPLE_TEST_PLAN.json`, prose, an old
cycle, or a user message; only the Controller handoff reflects Human approval.

## Execution

For each approved test, read its:

- `targets[]` bindings to Principle/version, assumption, prediction, RMC, and
  causal chain;
- operationalization and optional `test_only_concrete_realization`;
- execution requirements, estimated cost, and terminal outcome contract.

Execute only what that test requires:

1. For a computational test, invoke the existing `/run-experiment`, queue,
   logging, and result-transport capabilities. Pass the approved test ID and
   execution requirements unchanged. Do not build another scheduler, GPU
   platform, logging system, or experiment lifecycle.
2. For a physical or human-run test, create the smallest handoff needed to run
   the approved procedure and identify the raw-result path expected in return.
   Do not perform scientific interpretation in that handoff.
3. Keep raw outputs and execution metadata separate from any hypothesis or
   Principle judgment. Record actual configurations, environment, timing,
   failures, deviations, and result locations.

The optional test-only concrete realization exists solely to operationalize the
approved discriminating test. It is not a Candidate Method, selected backbone,
Method adaptation, final implementation, or composition commitment.

## Terminal result submission

Every approved test must be submitted exactly once with one terminal outcome.
For an available raw result, write a JSON file with:

```json
{
  "schema_version": 1,
  "cycle_id": "<handoff cycle_id>",
  "execution_set_id": "<handoff execution_set_id>",
  "test_id": "<approved test_id>",
  "outcome": "RESULT_AVAILABLE",
  "result_refs": [
    {"path": "<project-relative raw-result path>", "sha256": "<file sha256>"}
  ],
  "execution_metadata": {}
}
```

For no usable result, write:

```json
{
  "schema_version": 1,
  "cycle_id": "<handoff cycle_id>",
  "execution_set_id": "<handoff execution_set_id>",
  "test_id": "<approved test_id>",
  "outcome": "NO_RESULT",
  "result_refs": [],
  "execution_metadata": {},
  "reason": "execution_failed | unavailable | operationalization_failed | user_stopped"
}
```

`RESULT_AVAILABLE` requires at least one existing project-relative file with
its current SHA-256 and carries no `NO_RESULT` reason. `NO_RESULT` carries one
declared reason and may retain failure metadata, but no result reference is
required.

Submit the unchanged record:

```text
python -m arisctl --root . submit-method-test-result <run_id> <result-json>
```

When all approved tests are terminal, stop. The Controller forms
`PRINCIPLE_EVIDENCE_CONTEXT.json` and exposes `start_phase`; this skill neither
creates that Context nor starts or evaluates the phase.

## Prohibited judgments and mutations

- Do not decide `SUPPORTED`, `REJECTED`, or any other Principle status.
- Do not compare results to choose a Principle or declare convergence.
- Do not edit Candidate Principles, ledgers, Controller State, the approved
  execution set, or `PRINCIPLE_EVIDENCE_CONTEXT.json`.
- Do not add tests, alter targets, expand cost, or silently retry with a changed
  operationalization. A scientific test change returns through Human
  `request_revision -> principle_test_design`.
- Do not turn `NO_RESULT` into Evidence for or against a Principle.
- Do not run Full Validation or write a Final Scientific Delta Claim.
