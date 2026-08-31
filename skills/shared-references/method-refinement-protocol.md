# Method Refinement Protocol

Use this protocol only after the Controller has accepted
`PRINCIPLE_CONVERGED` and materialized an active
`idea-stage/SELECTED_PRINCIPLE.yaml`. It owns Selected-Principle-first target
adaptation, iterative issue resolution, and the final method review. Principle
formation and convergence remain owned by
[`method-design-contract.md`](method-design-contract.md).

## Scientific invariant

Preserve this order:

```text
Selected Principle
  -> target-domain adaptation
  -> minimal faithful realization
  -> Principle-only closure attempt
  -> residual mechanism/adaptation gaps
  -> minimal necessary supporting mechanisms
  -> Final Scientific Delta Claim
  -> claim-validation obligations
  -> independent final method review
```

Concrete Method commitments begin here, not in pre-convergence test
operationalization. Supporting mechanisms may be added only after a faithful
Principle-only realization exposes a named residual mechanism or adaptation
gap. Composition is minimal and gap-driven, not a novelty strategy.

## Input gate

Require:

- the active accepted Problem Contract and Evidence Capsule;
- accepted Root-Cause Analysis/verdict with current hashes;
- accepted `ACTIVE_FIELD_MAP.md` and currently usable Evidence;
- Controller-materialized `SELECTED_PRINCIPLE.yaml` with the selected
  Principle/intervention/changed structure; exact derivation or Source origin
  and accepted intervention alignment; Target novelty closure; causal-chain,
  RMC, Capability, and Obligation bindings; accepted assumptions, killer
  predictions, and Evidence closure; activation/failure conditions,
  Reviewer-accepted boundary updates, and remaining uncertainty;
- the latest Controller-exposed method-level reviewer guidance, Human feedback,
  novelty feedback, or Full Validation result directed to this phase;
- the previous proposal when a validation or method-level return preserves the
  same Selected Principle.

The Selected Principle remains active for `REVISE`, `HOLD`,
`REVISE_METHOD_DELTA`, final Human `request_revision`, and
`METHOD_REFINEMENT_REQUIRED`. A Principle-level rethink/rejection, RCA reopen,
or Problem-premise reopen invalidates it through the Controller; do not
reconstruct it from history.

If return feedback is active, consume the identified findings, Evidence, claim
elements, and required checks before revising. A return cannot be satisfied by
rewriting prose while preserving the rejected scientific state.

## Active context and artifacts

Keep only the active Problem/RCA/Selected-Principle bindings, current proposal,
unresolved issue IDs, current Evidence, and current return feedback in the
working context. Older rounds and ledger records remain retrievable audit
history.

Use the existing refinement artifacts:

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

`REFINE_STATE.json` records refinement/review progress only; it is not a second
scientific-core lifecycle. `ACTIVE_PROPOSAL.md` is the one mutable proposal.
Create `MANIFEST.md` only when the shared artifact threshold is crossed.

## R0 — Freeze accepted upstream bindings

Copy the active Problem, RCA, and Selected Principle identities unchanged. A
proposal may adapt the Principle but cannot silently switch its ID/version,
causal chains, RMCs, Capabilities, or Obligations. A contradiction in the
selected Principle returns `RETHINK`; a contradiction in the accepted RCA uses
`RCA_CONFLICT`; a material Problem change uses the existing Problem revision or
validation-return path.

## R1 — Target-domain adaptation

Translate the selected algorithm-independent intervention into the target
domain. Specify:

- target entities, relations, states, information structures, and operating
  conditions;
- how the selected intervention acts on them;
- how activation and failure conditions map to the target domain;
- which accepted RMCs, Capabilities, and Obligations the adaptation serves;
- which uncertainties remain assumptions rather than facts.

Do not introduce a preferred backbone or component before the adaptation logic
requires it.

## R2 — Minimal faithful realization and Principle-only closure

Construct the smallest concrete realization that faithfully embodies the
Selected Principle. Distinguish reused implementation machinery from core
method changes. Then attempt Principle-only closure against every selected RMC,
Capability, Obligation, failure condition, and applicability boundary.

For each closure entry record:

```yaml
binding_ids: []
principle_intervention:
concrete_realization:
predicted_mechanism_change:
closure_status: CLOSED | RESIDUAL_GAP
evidence_or_reason:
```

Do not use pre-convergence test-only realizations as an implicit backbone or
Method commitment. Reuse one only if the post-convergence adaptation reasoning
independently selects it as the minimal faithful realization.

## R3 — Residual gaps and minimal necessary composition

Only a genuine `RESIDUAL_GAP` may justify a supporting mechanism. Give each gap
a stable ID and record the failed closure link, target condition, consequence,
and acceptance condition.

First use the accepted Field Map and current Evidence. If a residual adaptation
gap still lacks a justified solution, the running `method_refinement` phase may
use the existing incremental literature gateway with
`search_mode: ADAPTATION_GAP_SEARCH`. Its query-plan context binds the active
Selected Principle ID/version/hash and non-empty
`residual_adaptation_gaps`; every query binds a decision target and one or more
gap IDs.

For each supporting mechanism retained after that check, record:

```yaml
residual_gap_ids: []
mechanism:
why_the_selected_principle_alone_cannot_close_the_gap:
activation_conditions:
integration_interface:
assumption_compatibility:
removal_or_counterfactual_failure_prediction:
```

Remove a support when it closes no declared gap, duplicates the faithful
realization, conflicts with the Selected Principle, lacks a real interface, or
has no discriminating removal/counterfactual consequence. Preserve operational
prerequisites as implementation constraints rather than scientific novelty.

If adaptation-gap search or Evidence re-adoption occurs while the phase is
running, finish that session before final review and refresh the review request
after the final proposal is written.

## R4 — Final Scientific Delta Claim and validation obligations

State the `Final Scientific Delta Claim` that Full Validation will test. It may
claim a new mechanism, representation, boundary, or important capability only
within the Selected Principle's Evidence-supported conditions and the final
Method's stated scope. It is not yet an established scientific fact.

For every claim element specify a claim-validation obligation:

```yaml
claim_element_id:
causal_chain_ids: []
mechanism_change_ids: []
capability_ids: []
obligation_ids: []
core_method_changes: []
predicted_mechanism_change:
discriminating_evidence_required:
performance_consequence_required:
falsifying_pattern:
failure_conditions_and_boundary:
```

Performance improvement alone cannot satisfy a mechanism-level claim. The
obligations must permit Full Validation to recover:

```text
predicted mechanism change
  -> observed mechanism change
  -> discriminating evidence
  -> performance consequence
```

## R5 — Write the final proposal

Use `templates/METHOD_PROPOSAL_TEMPLATE.md`. `FINAL_PROPOSAL.md` must contain
these exact non-empty sections and include every Selected Principle binding ID:

1. `Selected Principle binding`
2. `Target-domain adaptation`
3. `Minimal faithful realization`
4. `Principle-only closure attempt`
5. `Residual mechanism and adaptation gaps`
6. `Minimal necessary composition`
7. `Core method changes`
8. `Predicted mechanism changes`
9. `Failure conditions and applicability boundaries`
10. `Final Scientific Delta Claim`
11. `Claim-validation obligations`

Keep evidence, inference, proposal, and unvalidated Claim distinct.

## R6 — Review and revise

Iterative review may identify issue IDs for problem/RCA/Principle fidelity,
adaptation correctness, realization faithfulness, residual-gap necessity,
integration, feasibility, Claim calibration, and validation completeness.
Resolve issue IDs against Evidence and revise only the active proposal. Scores
are progress signals, never acceptance rules.

The Controller-issued `independent_method_reviewer` is the sole formal final
method reviewer. After all legal Evidence work is complete and
`FINAL_PROPOSAL.md` is final, invoke `refresh-review-request`; dispatch the
reviewer only against that current binding. Write its unchanged verdict to
`FINAL_BLIND_REVIEW.md` with the live request and reviewed-artifact hashes.

Formal outcomes are:

| Verdict | Controller effect |
|---|---|
| `METHOD_READY` | accept the phase and continue to final method novelty review |
| `REVISE` | revise adaptation, realization, composition, Claim, or validation obligations in `method_refinement` |
| `HOLD` | obtain or explain missing method-level Evidence in `method_refinement` |
| `RETHINK` | return to `method_design` because the selected Principle or its scientific delta must be reconsidered |
| `RCA_CONFLICT` | return linked Evidence and mechanism conflict to `root_cause_analysis` |

The formal reviewer does not select a new Principle or rewrite the RCA.

## Downstream boundaries

The final novelty Gate distinguishes failure layers:

- `REVISE_METHOD_DELTA` preserves the Selected Principle and returns concrete
  adaptation/embodiment/Claim work here;
- `RETHINK_PRINCIPLE_DELTA` returns to `method_design` and invalidates the
  Selected Principle through the Controller;
- `HOLD` remains in the novelty Gate for missing novelty Evidence or
  interpretation.

Final Human acceptance accepts or requests revision of the final Method; it is
not a Principle-selection Gate and does not start Full Validation. Only explicit
user initiation obtains the Controller validation handoff.

Use stage language exactly:

```text
method_design        -> Provisional Scientific Delta
method_refinement    -> Final Scientific Delta Claim
VALIDATED only       -> Established Scientific Delta
```

## Failure paths

| Code | Trigger | Response |
|---|---|---|
| `SELECTED_PRINCIPLE_MISSING` | no active Controller-materialized selection | stop; do not reconstruct it |
| `PRINCIPLE_DRIFT` | proposal silently changes the selected Principle or bindings | return `RETHINK` or `RCA_CONFLICT` as applicable |
| `ADAPTATION_UNFAITHFUL` | concrete Method does not instantiate the selected intervention | redesign the minimal realization |
| `COMPOSITION_PREMATURE` | support is added before a Principle-only closure attempt | remove it and run closure first |
| `SUPPORT_UNGROUNDED` | support closes no named residual gap | remove it |
| `INTEGRATION_MISSING` | support lacks a real interface | redesign or remove it |
| `CLAIM_OVERSTATED` | Final Scientific Delta Claim exceeds current Evidence or boundaries | narrow the Claim |
| `VALIDATION_OBLIGATION_INCOMPLETE` | a claim cannot be traced to mechanism and performance evidence | repair the obligation before `METHOD_READY` |
