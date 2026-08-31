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
  -> Principle-only closure
  -> Residual MUSTs
  -> minimal necessary composition
  -> FINAL_METHOD_PACKET.json
  -> deterministic FINAL_PROPOSAL.md
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
  FINAL_METHOD_PACKET.json
  FINAL_BLIND_REVIEW.md
  FINAL_PROPOSAL.md
  REVIEW_SUMMARY.md
  REFINEMENT_REPORT.md
```

`FINAL_METHOD_PACKET.json` is the sole canonical Final Method machine
authority. `FINAL_PROPOSAL.md` is only its deterministic Controller-rendered
human view. `REFINE_STATE.json` records refinement/review progress only;
`ACTIVE_PROPOSAL.md` is optional working prose and neither may supply or recover
Final Method facts.
Create `MANIFEST.md` only when the shared artifact threshold is crossed.

## R0 — Freeze accepted upstream bindings

Copy the active Problem, RCA, and Selected Principle identities unchanged. A
proposal may adapt the Principle but cannot silently switch its ID/version,
causal chains, RMCs, Capabilities, or Obligations. A contradiction in the
selected Principle returns `RETHINK`; a contradiction in the accepted RCA uses
`RCA_CONFLICT`; a contradiction in the accepted Necessity premise or residual
failure envelope uses `NECESSITY_CONFLICT`; and a contradiction that invalidates
or materially changes the accepted Problem identity or premise uses
`PROBLEM_CONFLICT`. Never rewrite an accepted RCA, Necessity, or Problem in
place to avoid its canonical return.

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
method changes. Then attempt Principle-only closure against every accepted
primary causal chain, selected RMC, Capability, Obligation, activation/failure
condition, and pre-existing `APPLICABILITY_BOUNDARY`. Do not include the
`CLAIM_RESTRICTION` boundaries generated later by R4 feasibility.

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

## R3 — Residual MUSTs, minimal necessary composition, and causal repair DAG

Only a genuine `RESIDUAL_GAP` may create a `residual_must`. Give every MUST a
stable ID and record the failed closure link, gap, and acceptance condition.
Engineering preference, implementation convenience, and generic optimization
are not MUSTs. If every closure is `CLOSED`, both `residual_musts` and
`minimal_necessary_composition` are empty.

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
after the final Packet is written.

Persist an acyclic `causal_repair_dag`. A core Method node may have only an
accepted Primary Root Cause, a real Target Constraint, or an incompatibility
explicitly introduced by an earlier retained design as causal parent. For the
third case preserve `later repair <- incompatibility <- earlier design <-
original causal requirement`. Every edge names a claim-validation obligation;
every node participates; every core change is represented exactly once.

## R4 — Mechanism, natural derivation, feasibility, counterfactual, and Claim

Persist `mechanism_delta` as a specific Existing causal/computational relation
to New relation change. Record the nearest relevant prior or causal-equivalent
baseline, formal Evidence/provenance, and separation in the intervention,
mechanism, or computational relation. Algorithm names and module counts are not
mechanism separation.

Persist Target RMC ↔ Selected/Source Intervention ↔ Final Computational Change
alignment. Then write `target_only_natural_derivation`: after removing every
Source-domain story, `Target Failure -> RCA -> RMC -> Target Constraints ->
Final Method` must still explain the Method and every core structure.

Feasibility is claim-proportional. Record only dimensions relevant to the field
and Claim, supported conditions, unresolved debts, restrictions, and fatality.
For every claim restriction, write only `restriction_id`, `claim_element_ids`,
`debt_ids`, and `boundary_id`; `boundary_id` must resolve to the canonical
`failure_and_applicability_boundaries` entry with
`boundary_type: CLAIM_RESTRICTION`, and every listed claim element must include
that ID in `boundary_refs`. Put the restriction text only in that canonical
boundary; never generate `claim_restriction.boundary` or another copy of the
restriction. A nonfatal debt must restrict the Claim through this binding. A
fatal debt is `NO_GO`-eligible only when current Evidence excludes repair and
claim restriction cannot preserve the core seed.

Every retained supporting scientific mechanism gets one future
`counterfactual_necessity_obligation`: removal condition, closure expected to
fail, and discriminating consequence. An unexecuted removal/ablation is not
Evidence and remains `FUTURE_OBLIGATION`.

### Final Scientific Delta Claim and validation obligations

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

## R5 — Write the canonical Final Method Packet

Use `templates/METHOD_PROPOSAL_TEMPLATE.md` as the Packet/view authoring guide.
Main writes `refine-logs/FINAL_METHOD_PACKET.json` with exact current Problem,
Necessity, RCA, and Selected Principle hashes and every structure from R1–R4.
Keep evidence, inference, proposed method, and unvalidated Claim distinct.
Never write or parse `FINAL_PROPOSAL.md` as a second scientific authority.

## R6 — Deterministic human view

Invoke `refresh-review-request` after the Packet and legal Evidence work are
complete. The Controller validates the Packet, computes
`render_final_method_view(packet)`, and writes `FINAL_PROPOSAL.md`. Validation
requires byte equality with that render. Manual edits to the view are invalid.

## R7 — Review and revise

Iterative review may identify issue IDs for problem/RCA/Principle fidelity,
adaptation correctness, realization faithfulness, residual-gap necessity,
integration, feasibility, Claim calibration, and validation completeness.
Resolve issue IDs against Evidence and revise only the active proposal. Scores
are progress signals, never acceptance rules.

The Controller-issued `independent_method_reviewer` is the sole formal final
method reviewer. Dispatch it only against the current
`FINAL_METHOD_PACKET.json` binding. Write its unchanged verdict to
`FINAL_BLIND_REVIEW.md` with the live request and Packet hash.

Formal outcomes are:

| Verdict | Controller effect |
|---|---|
| `METHOD_READY` | accept the phase and continue to final method novelty review |
| `REVISE` | revise adaptation, realization, composition, Claim, or validation obligations in `method_refinement` |
| `HOLD` | obtain or explain missing method-level Evidence in `method_refinement` |
| `RETHINK` | return to `method_design` because the selected Principle or its scientific delta must be reconsidered |
| `RCA_CONFLICT` | return linked Evidence and mechanism conflict to `root_cause_analysis` |
| `NECESSITY_CONFLICT` | return Evidence that invalidates the accepted Necessity premise or residual failure envelope to `problem_necessity` |
| `PROBLEM_CONFLICT` | return Evidence that invalidates or materially changes the accepted Problem identity or premise to `problem_generation` |
| `NO_GO` | enter existing `SCIENTIFIC_NO_GO` only for a fatal feasibility debt after Evidence excludes repair, claim restriction, and every fixed return |

The canonical return lifecycle is reused without a refinement-specific
invalidation subsystem. `NECESSITY_CONFLICT` retains the accepted Problem but
invalidates the accepted Necessity and every downstream current scientific
artifact, including RCA, Method Design/Test/Convergence, `SELECTED_PRINCIPLE`,
and Final Method; downstream work resumes only after the existing Necessity
Producer, Reviewer, and Gate accept a new closure. `PROBLEM_CONFLICT` enters the
existing Problem revision/replacement lifecycle, invalidates the old Problem
and all downstream current scientific artifacts, and requires the new Problem
to pass the existing Quality, Novelty, and Human Acceptance lifecycle.

The formal reviewer does not select a new Principle or rewrite the RCA,
Necessity, or Problem. It returns the most upstream accepted scientific premise
that current formal Evidence actually invalidates: Problem before Necessity,
Necessity before RCA, RCA before Principle, and Principle before final Method.
Evidence that merely involves an upstream object does not justify escalation
when that accepted premise remains valid. Main findings, warnings, or proposed
consequences never authorize a transition.

Every non-accepting return uses structured `return_guidance` with non-empty
`missing_evidence`, `required_check`, and a `decision_target` equal to the
canonical return target above. `NO_GO` must include the Final Method/debt
subject, current Evidence, reason, and excluded `REVISE`, `HOLD`, `RETHINK`,
`RCA_CONFLICT`, `NECESSITY_CONFLICT`, and `PROBLEM_CONFLICT` recoveries. If
Necessity or Problem recovery remains reasonable, or a debt is repairable or
claim-restrictable, use the corresponding fixed return instead.

## Downstream boundaries

The final novelty Gate distinguishes failure layers:

- `REVISE_METHOD_DELTA` preserves the Selected Principle and returns concrete
  adaptation/embodiment/Claim work here;
- `RETHINK_PRINCIPLE_DELTA` returns to `method_design` and invalidates the
  Selected Principle through the Controller;
- `HOLD` remains in the novelty Gate for missing novelty Evidence or
  interpretation.

Final Novelty consumes `SELECTED_PRINCIPLE.yaml`, canonical
`FINAL_METHOD_PACKET.json`, the accepted final method review, and current
formal novelty Evidence/context. It never consumes `FINAL_PROPOSAL.md` as
scientific authority. After `NOVEL`, the existing `independent_method_reviewer`
owns the formal Top-Venue Method Strength Gate and judges the workflow's twelve
hard dimensions independently. Any FAIL blocks `TOP_VENUE_READY`; no aggregate
score or implementation complexity can compensate. Its recoveries are fixed at
`method_refinement`, `method_design`, `root_cause_analysis`,
`problem_necessity`, and `problem_generation`; only an Evidence-supported fatal
weakness with all five recoveries excluded may reuse `SCIENTIFIC_NO_GO`.

Final Human acceptance opens only after `NOVEL` and `TOP_VENUE_READY`, accepts
or requests revision of the final Method, and is
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
