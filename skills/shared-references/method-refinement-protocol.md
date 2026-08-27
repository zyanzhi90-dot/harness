# Method Refinement Protocol

Use this protocol to refine one Certified Problem Contract and its validated
root-cause handoff through iterative
review and an independent final decision. It owns context, state, review, and
recovery. Scientific method design is owned only by
[`method-design-contract.md`](method-design-contract.md).

## Contents

- Input gate and active-context capsule
- Canonical state and artifacts
- R0-R4: freeze, build, review, and revise
- R5: Controller-issued final independent review
- R6: finalization and failure paths

## Scientific invariant

Preserve:

```text
Field Evidence Map -> Certified Problem Contract
  -> DIAGNOSIS_READY primary causal chains
  -> competing explanations -> falsifiable Scientific Mainline
  -> Design Obligations -> minimal sufficient dominant solution
  -> dominant-only closure -> residual MUST gap
  -> Field Map and same-field completion when that gap remains
  -> cross-field structural search only if same-field options cannot reasonably close it
  -> necessary natural integration
  -> minimum claim-validation logic -> independent final decision
```

Combination is permitted only when a supporting mechanism closes a declared
residual `MUST` gap; it is neither the default search strategy nor the
innovation verdict. All detailed rules for the dominant method, supporting
mechanisms, transfer, integration, removal/counterfactual tests, and novelty
live in the method-design contract; do not copy them here or into platform
skills.

## Input gate

Require:

- one `CERTIFIED/accepted` problem version, acceptance record, and separate
  problem-novelty verdict;
- `ROOT_CAUSE_ANALYSIS.json` and `ROOT_CAUSE_VERDICT.json` with
  `DIAGNOSIS_READY`, matching IDs, and matching problem/evidence/analysis
  SHA-256 values;
- evidence-backed phenomenon, scope, value under either answer, and falsifier;
- compact Active Field Map plus retrievable evidence IDs;
- optional rough route, constraints, and reviewer feedback.

Return to problem discovery for `HOLD`, `REJECT`, `BLOCKED`, missing evidence,
or material scope ambiguity. Do not compensate with a more elaborate method.

## Active-context capsule

Keep only:

1. Certified Problem Contract and validated primary causal-chain IDs;
2. compact Active Field Map;
3. latest full proposal;
4. unresolved-issues ledger;
5. evidence cards referenced by the current decision.

Keep the full Evidence Registry and older rounds on disk. Retrieve them by
source or issue ID only when needed. On resume, read state, the focused
contract, latest proposal, and unresolved ledger; do not read every historical
round.

## Canonical state and artifacts

Use:

```text
refine-logs/
  REFINE_STATE.json
  ACTIVE_PROPOSAL.md
  UNRESOLVED_ISSUES.md
  round-N-review.md
  round-N-decision.md
  FINAL_BLIND_REVIEW.md
  FINAL_PROPOSAL.md
  REVIEW_SUMMARY.md
  REFINEMENT_REPORT.md
```

`REFINE_STATE.json` records schema version, phase, round, iterative reviewer
handle, latest verdict, unresolved blocking issue IDs, current proposal path,
Certified Problem Contract hash, root-cause analysis/verdict hashes,
primary causal-chain IDs, scope/constraint hash, proposal hash,
blind-verdict ID, acceptance status, and status. The Research Contract freezes
the accepted problem/evidence snapshot; `ACTIVE_PROPOSAL.md` is the only
mutable full method proposal and records the contract hash it implements.
Round decisions contain only accepted/rejected changes and issue transitions;
never duplicate the full proposal in every round.

`FINAL_PROPOSAL.md` keeps the selected route's `route_id`, complete
problem-version binding, root-cause analysis ID/SHA-256, and referenced
causal-chain and design-obligation IDs in the template's typed fields. The
references must resolve in `SELECTED_ROUTE.yaml`; a revised proposal is not a
route-switch mechanism.

Create `MANIFEST.md` only when the run exceeds the shared artifact threshold.

## Workflow

### R0 — Freeze the problem and diagnosis

Copy the Certified Problem Contract and validated root-cause handoff unchanged;
verify their problem ID/version, evidence IDs, causal-chain IDs, hashes, P3
verdict, and `DIAGNOSIS_READY` verdict. `ACTIVE_PROPOSAL.md` is a separate,
mutable method artifact and records that problem-version binding. A requested
change to the question, scope, or falsifier stops refinement: the user must use
explicit `arisctl revise-problem`, which creates a draft problem version and
requires the existing problem quality, novelty, and human-acceptance sequence.
Do not freeze Design Obligations before the hypothesis.

### R1 — Build the active proposal

Execute M0-M6 of `method-design-contract.md` in order. Use its canonical output
order and `templates/METHOD_PROPOSAL_TEMPLATE.md`. Keep evidence, inference,
hypothesis, and proposal distinct. Never claim unrun experiments or unverified
novelty.

### R2 — Start independent iterative review

Start from raw artifacts in a fresh review context. Judge:

1. problem fidelity;
2. competing-explanation discipline and hypothesis quality;
3. obligation traceability;
4. dominant-carrier fit;
5. integration and Scientific Closure;
6. feasibility and boundary awareness;
7. Scientific Delta and minimum claim-validation logic.

Require issue IDs, severity, evidence, a correction, and
`READY | REVISE | RETHINK | HOLD`. A numeric score tracks progress only.

### R3 — Revise against issue IDs

For each suggestion:

- accept it when evidence shows it repairs an issue without problem drift;
- reject it with evidence when it creates drift, redundancy, or unsupported
  claims;
- update the issue ledger;
- revise only `ACTIVE_PROPOSAL.md`.

Use the same reviewer thread only to check whether that reviewer's own issue
IDs were resolved. Never use continuity as independent acceptance.

### R4 — Exit the iterative loop

Stop when no blocking issue remains or the configured round limit is reached.
Do not optimize prose or component count merely to raise a score. A score
threshold or round limit cannot create `READY`.

### R5 — Controller-issued final independent review

The Controller-issued `independent_method_reviewer` is the one fresh final
independent Gate. Start it in a new reviewer context with:

- Certified Problem Contract;
- Active Field Map and cited evidence cards;
- current proposal;
- venue and resource constraints.

Do not pass generator history, previous scores, earlier feedback, or a change
summary. Require blocking claim/evidence failures, unresolved alternative
explanations, integration/redundancy failures, overclaiming, and missing
boundary tests. It returns exactly one Controller-declared verdict:

| Verdict | Formal Controller effect |
|---|---|
| `METHOD_READY` | accept this Gate and continue to final method novelty review |
| `REVISE` | selected route remains valid; return to `method_refinement` |
| `RETHINK` | the route's core method is unsound or inadequate; return to `method_design` and repeat the existing route-selection path |
| `HOLD` | missing method-level evidence prevents a responsible decision; return to `method_refinement` and use its existing evidence/refinement path |

`REVISE`, `RETHINK`, and `HOLD` are final formal Gate outcomes, not merely
notes for the iterative loop. This reviewer has no authority to reopen the
root-cause analysis or problem premise. Do not run a separate internal final
blind audit: R2-R4 are iterative issue-resolution feedback, while R5 is the
only independent review that decides whether this phase ends.

### R6 — Finalize

Write:

- `FINAL_PROPOSAL.md`: clean proposal;
- `FINAL_BLIND_REVIEW.md`: the raw verdict from that sole independent review.
  It includes exactly one
  fenced JSON metadata block with `schema_version: 1`, `review_request_id`,
  `reviewer`, `verdict_id`, one of `decision: METHOD_READY | REVISE | RETHINK |
  HOLD`, and
  `reviewed_artifact_hashes`; the Controller binds the completed
  `FINAL_PROPOSAL.md` SHA-256 to that same live request before attestation;
- `REVIEW_SUMMARY.md`: compact issue-resolution and remaining-risk handoff;
- `REFINEMENT_REPORT.md`: problem preservation, rejected suggestions,
  limitations, and final decision.

If R5 does not return `METHOD_READY`, preserve the best proposal and its
formal verdict; the Controller performs the fixed return above. Never
fabricate readiness.

## Failure paths

| Code | Trigger | Response |
|---|---|---|
| `PROBLEM_DRIFT` | question, scope, or falsifier changes | return to problem discovery |
| `EXPLANATION_COLLAPSE` | one plausible story becomes diagnosis without discrimination | restore competitors |
| `CAUSAL_OVERCLAIM` | claim exceeds identification | downgrade claim or strengthen design |
| `ROUTE_BLOAT` | mechanism has no unique obligation | remove it |
| `INTEGRATION_MISSING` | parts lack a shared interface | redesign or remove support |
| `REVIEWER_OVERFIT` | readiness depends on same-thread score | run the Controller-issued final independent review |
| `CONTEXT_BLOAT` | recovery loads all rounds/evidence | restore the active-context capsule |
| `NO_READY_ROUTE` | closure remains incomplete | retain explicit non-READY status |
