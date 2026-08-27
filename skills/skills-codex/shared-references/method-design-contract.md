# Scientific Method Design Contract

Load this contract only after the independent Root-Cause Gate in
[`root-cause-analysis-contract.md`](root-cause-analysis-contract.md) returns
`DIAGNOSIS_READY`. It is the single source of truth for turning a Certified
Problem Contract plus validated causal chains into a top-journal-level method
route. Skills must reference this contract instead of copying its doctrine or
inventing parallel schemas.

Apply
[`source-admission-policy.md`](source-admission-policy.md) before using any
paper for explanations, same-field or cross-field completion, closest prior
work, method transfer, or novelty. Proactively retrieved papers require
`ADMIT`; explicitly user-supplied materials require `USER_SUPPLIED_READ` plus a
post-read content assessment. Neither track grants automatic scientific truth.

`ACTIVE_FIELD_MAP.md` is a Controller-accepted formal upstream input to this
phase. Before seeking new literature, use its problem--method--mechanism,
effective-condition, and failure-condition records together with the existing
Evidence Registry to test candidate dominant mechanisms. Cite the Field Map
hash in the Controller-bound method-design handoff; do not repeat its coverage
search merely to rediscover mechanisms already mapped there.

## Contents

- M0: validate the certified problem, root-cause handoff, and contribution type.
- M1: consume validated explanations and state the scientific mainline.
- M2: derive problem-traceable design obligations.
- M3-M4: choose the dominant carrier and integrate only necessary support.
- M5-M6: close the scientific logic, specify decisive validation obligations,
  and judge the route.

## Core doctrine

Center method design on a **falsifiable scientific hypothesis and a
non-redundant complete scientific closure**.

The primary optimization objective is **problem-method fit**: select the
smallest scientifically adequate route whose mechanism directly resolves the
certified problem. Assess novelty after that route is coherent. Never add a
component, learning objective, model, or theoretical wrapper merely to increase
the apparent novelty of the proposal.

For method-oriented research, use this high-efficiency decision order:

> Derive the required capabilities from the causal chain, then choose the
> smallest sufficient dominant solution. Only after its dominant-only closure
> exposes a residual `MUST` gap, first check the accepted Field Map and
> same-field mechanisms. Search a structurally corresponding cross-field
> mechanism only when those same-field options cannot reasonably close that
> declared gap.

Transfer and combination are permitted mechanisms of problem solving, not a
default design goal or innovation target. The dominant solution may be an
existing method or a first-principles design. Accept supporting mechanisms only
when they close a declared residual `MUST` gap through a real interface and
create a scientific delta beyond ordinary engineering integration. Do not force
a combination when one method already closes the hypothesis with sufficient
scientific novelty.

Use this causal order:

```text
Certified Problem Contract
  -> validated primary causal chains and competing explanations
  -> mechanism failures and intervention targets
  -> falsifiable scientific hypothesis
  -> design obligations
  -> organizing principle
  -> minimal sufficient dominant solution
  -> dominant-only closure and residual MUST gaps
  -> if a gap remains: accepted Field Map and same-field completion search
  -> only if same-field options cannot reasonably close that gap: cross-field structural search
  -> implementation backbone, innovation carrier, and necessary integration through shared interfaces
  -> claim-level falsifiers and decisive evidence
  -> scientific closure
  -> scientific- and technical-novelty verdicts
```

## M0 - Input gate

Proceed only when the input contains a `CERTIFIED` problem with:

- an evidence-backed phenomenon;
- a precise research question and scope;
- a decisive falsifier;
- a problem-quality verdict;
- a separate problem-novelty verdict.
- `acceptance_status: accepted` plus its verdict ID and human or cross-family
  acceptance authority.
- one Controller-recorded problem ID/version and matching accepted
  problem-contract and evidence-capsule SHA-256 values.

Also require `ROOT_CAUSE_ANALYSIS.json` and `ROOT_CAUSE_VERDICT.json` with:

- `decision: DIAGNOSIS_READY`;
- the same run ID and analysis ID;
- matching SHA-256 values for the problem contract, evidence capsule, and
  reviewed analysis;
- one or more `primary_causal_chain_ids` that resolve to causal chains with
  evidence anchors, alternatives, intervention targets, and falsifiers.

In the default half-autonomous workflow, require `acceptance_authority: human`.
Treat cross-family review as advisory unless the user explicitly enabled an
autonomous acceptance mode.

If a problem item is absent or invalid, return to problem discovery. If the
diagnosis is absent or changed, do not enter method design. A non-ready
root-cause verdict follows only its fixed Controller mapping:
`REVISE_DIAGNOSIS -> root_cause_analysis` or
`REOPEN_PROBLEM -> problem_generation`. Never manufacture a method to
compensate for an uncertified problem or unaccepted diagnosis.

Method artifacts are separate from the problem contract. They may refine a
route, but any material problem change must use explicit `arisctl revise-problem`;
that creates a draft next version and repeats the existing problem Gates.

## Canonical route handoff identity

`METHOD_ROUTES.jsonl` is one machine handoff, not one requirement set per
route. Its first record is the `schema_version: 2`,
`record_type: design_obligation_set` record: one named, diagnosis-bound
`design_obligation_set_id`, the active problem/diagnosis hashes, full causal
chain basis, and the complete obligations. Each following
`record_type: method_route` record uses the same bindings and set ID, and may
only reference its obligation IDs through `obligation_coverage` and
`dominant_only_closure`. The validator rejects a route before that set, a second
set, a different set ID, or a different causal-chain basis. Each obligation has
a unique `obligation_id` and non-empty `derived_from_causal_chain_ids`; all
chain references must resolve to the accepted diagnosis's primary causal
chains.

`METHOD_ROUTES.md` is the human decision packet and exposes those same IDs and
hashes. After the user chooses, `SELECTED_ROUTE.yaml` repeats the route's
problem/diagnosis binding together with its `route_id`,
`design_obligation_set_id`, full causal-chain ID set, and full obligation-ID
set. The Human Gate's `selected_id` must be that existing route ID. Refinement
carries the same fields in `FINAL_PROPOSAL.md`; it may refine the route but
cannot silently switch its problem, diagnosis, obligation set, or selected
route. These are mechanical provenance requirements, not a method quality
score.

Classify the intended contribution before route generation:

```yaml
contribution_type: method | problem_reformulation | measurement |
  theory | dataset_or_benchmark | system_or_workflow
```

The dominant solution is not required to be borrowed; it may be designed from
first principles. For other
types, name one dominant scientific carrier and adapt removal tests to that
carrier rather than forcing an artificial algorithmic component.

## M1 - Scientific mainline

Write the scientific mainline before naming components:

```yaml
critical_contradiction:
candidate_explanations:
  - explanation_id:
    source_chain_id:
    mechanism:
    supporting_evidence:
    counterevidence:
    epistemic_status: supported | preliminary | speculative | contested
    discriminating_prediction:
selected_explanation_or_open_set:
claim_type: causal | mechanistic | functional | descriptive
falsifiable_hypothesis:
decisive_falsifier:
intended_scientific_delta:
operationalization:
  input_intervention_or_explanatory_variable:
  claimed_mechanism_or_state_change:
  observable_outcome:
  expected_direction_or_distinguishing_pattern:
  scope_and_boundary:
```

Import the primary chains, their alternatives, epistemic status, and
discriminating evidence from the validated diagnosis. Do not silently replace
or deepen that diagnosis inside method design. If method reasoning exposes a
contradiction, finish any active method literature session, then use the
Controller's `reopen-root-cause` action while `method_design` is running. Pass
a specific scientific reason and, when applicable, the formal method-stage
Evidence IDs that triggered reconsideration. The reopened RCA and its existing
Gate decide the scientific outcome; the Agent does not rewrite the diagnosis in
place. Use a causal hypothesis only when
the design can support causal identification or intervention; otherwise use
mechanistic, functional, or descriptive language.

When `claim_type: causal`, add:

```yaml
causal_identification:
  intervention_or_change:
  expected_mechanism:
  strongest_alternative_mechanism:
  confound_or_artifact_risk:
  discriminating_observation_or_control:
  claim_limit_if_not_identified:
```

Keep this block at the level needed to prevent causal overclaiming. Detailed
estimands, sampling, statistics, controls, and analysis procedures belong in
the downstream experiment plan. An ablation establishes functional dependence,
not automatically causation. If the causal logic cannot be defended, downgrade
the claim type or return `REVISE/HOLD`.

The scientific mainline states what the work would demonstrate and why the
selected mechanism should resolve the contradiction. It may be a scientific
principle, problem reformulation, unifying mechanism, or workflow-level
hypothesis. It is not required to be the name of an existing algorithm.

`intended_scientific_delta` must identify at least one of:

- a new mechanism or causal explanation;
- a new problem representation or observable;
- a new unifying principle;
- a new boundary, limitation, or reliability result;
- a new capability demonstrated under conditions not previously closed.

## M2 - Design obligations

Derive one canonical obligation set from the Certified Problem Contract,
validated primary causal chains, and scientific hypothesis before any route is
generated. Its runtime fields are:

```yaml
design_obligation_set_id:              # set-level identity
obligation_id:
derived_from_causal_chain_ids:
required_capability:
why_current_methods_fail:
measurable_acceptance_condition:
priority: MUST | SHOULD
```

When routes are ready, emit this set as the first `METHOD_ROUTES.jsonl`
record; candidate routes must not restate or edit it. When dominant-mechanism
knowledge is still insufficient, the running method phase instead carries the
same complete set in its Controller-registered Mode-A Query Plan. That plan is
the existing pre-route binding, not a new artifact or lifecycle.

Every `MUST` obligation must trace to the problem or to a causal link required
by the hypothesis. Do not add obligations solely to make a preferred technique
appear necessary.

`MUST`/`SHOULD`, capability, and acceptance-condition changes are a new
upstream method-design derivation, not a route-local edit. If that derivation
changes the diagnosis or hypothesis premise, use the existing root-cause return
path and its formal verdict; otherwise re-enter the existing `method_design`
phase and regenerate its one handoff before route selection.

Do not reuse a `design_obligation_set_id` with changed definitions. A formally
re-derived set receives a new ID; earlier Evidence and its provenance remain
historical, and become current for the new set only through existing explicit
Evidence re-adoption.

Separate scientific obligations from operational prerequisites. Add an
operational prerequisite only when the proposed route cannot run or cannot
support its claim without it. Check, as applicable rather than as a generic
domain checklist:

- whether required states or variables are measured, estimated, or unavailable;
- whether learned or fitted quantities are identifiable under the intended data;
- whether model error or uncertainty can invalidate decisions or constraints;
- whether online adaptation preserves the stability, feasibility, or physical
  consistency required by the task.

These checks protect correctness. Do not present standard sensing, uncertainty,
stability, or safety machinery as a scientific contribution unless the
certified problem specifically makes it the innovation carrier.

## M3 - Minimal route generation and necessary completion search

First ask whether the accepted Field Map and Evidence Registry already support
a credible dominant mechanism. If not, while `method_design` is running, use
`DOMINANT_SOLUTION_SEARCH`: bind every query to one or more current Design
Obligations and their derived causal chains, then search same-field mechanisms,
causally isomorphic mechanisms, and only where necessary cross-field mechanisms.
This search does not assume a dominant solution, closure, or residual gap; the
Agent stops when the evidence can support a dominant choice.

Then construct a **minimal sufficient dominant solution** and its
**dominant-only closure attempt**: the simplest credible realization of the
hypothesis using the dominant method without borrowed support. Mark exactly
which `MUST` obligations it satisfies and which remain open.

Treat the accepted Field Map and its registered Evidence Cards as the first
completion search space. If a mapped mechanism closes a residual obligation
under compatible conditions, reuse that knowledge directly. Only if the
dominant-only closure leaves a specific `MUST` obligation unresolved by this
existing cognition may running `method_design` re-enter the existing
literature gateway.

That `RESIDUAL_MUST_GAP_SEARCH` re-entry is a targeted decision action, not a
generic refresh. Its Query Plan carries the same canonical obligation-set ID,
the accepted RCA and Field Map hashes, the dominant solution and its
dominant-only satisfied/residual `MUST` IDs; every query names a non-empty
decision target and residual `MUST` IDs it can resolve. The Controller reuses
only query -> admission -> full-text reading -> Evidence Card -> Registry.
A closure with no residual `MUST` ID has no Mode-B search path.

Only after recording the residual `MUST` gaps, generate two or three credible routes, including that dominant-only route
when it is viable, and select one. For every route:

1. Choose the **dominant method** that best carries the hypothesis.
2. Identify the reused **implementation backbone**.
3. Identify the **innovation carrier** that creates the technical or scientific
   change.
4. Map obligations the dominant method already satisfies.
5. For a declared residual `MUST` gap not closed by the Field Map, use the
   running method-design gateway re-entry to seek same-field mechanisms.
6. Search other fields for that same gap only after recording why the accepted
   Field Map and a reasonable same-field search cannot close it; use causal and
   structural correspondence, not shared vocabulary.
7. Keep only the non-redundant set of supporting mechanisms required to
   complete the scientific chain.

For a cross-field route, preserve the migration order established during
problem discovery:

```text
source-field problem
  -> source problem-formation mechanism
  -> structurally isomorphic target mechanism
  -> target-field data confirming the problem
  -> residual target design obligation
  -> source solution mechanism
  -> transferred method or idea
```

Never transfer a solution merely because its source task resembles the target
task. Target-problem confirmation must precede solution borrowing.

Prefer a combined route over the dominant-only route only when the latter
fails at least one evidenced `MUST` obligation and the added mechanism closes
that obligation through a real interface. Expected performance improvement
alone is not enough.

Record:

```yaml
organizing_principle:
dominant_method:
implementation_backbone:
innovation_carrier:
dominant_method_obligation_coverage:
supporting_mechanisms:
single_scientific_chain: causal only when claim_type is causal
closest_prior_route:
failure_modes:
```

The machine `METHOD_ROUTES.jsonl` contract records the causal chain → required
capability → why current methods fail → measurable acceptance condition →
`MUST|SHOULD` once in its canonical set. For every route it records that shared
set ID, its own covered/residual obligation IDs, dominant solution and origin,
dominant-only satisfied/residual `MUST` IDs, and any supporting mechanism's
residual gap, mechanism match, activation condition, integration interface, and
removal-failure prediction.

`FINAL_PROPOSAL.md` preserves every selected causal chain and `MUST` obligation.
Every selected `SHOULD` obligation is explicitly `retained`, `waived`, or
`superseded` (with a reason for the latter two); none may disappear silently.

For method-oriented work, keep the dominant method visibly primary. For other
contribution types, keep the dominant scientific carrier primary. Reuse the
backbone without claiming it as novel. The innovation carrier may be the
dominant method itself, a new coupling mechanism, a problem reformulation, a
measurement principle, a training principle, or a system-level closure.

Compare the selected route against the dominant-only attempt and strongest
remaining challenger:

```yaml
route_comparison:
  route:
  obligation_coverage:
  distinguishing_prediction:
  weakest_assumption:
  closest_prior:
  data_compute_and_tuning_cost:
  likely_failure:
  cheapest_killer_test:
  condition_under_which_it_beats_the_selected_route:
```

Do not select a route merely because it is the most elaborate or easiest to
narrate.

Before accepting a route, apply a **minimum-sufficient-method audit**:

1. For each component, name the evidenced failure or unmet `MUST` obligation it
   resolves.
2. Confirm that its inputs are available and its assumptions are compatible
   with the intended operating regime.
3. Confirm a real integration interface with the dominant method.
4. Remove it if the same obligation is already closed without it.
5. If removing it exposes an operational gap rather than a scientific gap,
   retain it as a prerequisite or implementation constraint, not as novelty.

Novelty pressure must never reverse this order.

## M4 - Supporting-mechanism ledger

For every same-field or cross-field method or idea, record:

```yaml
method_or_idea:
source_field:
obligation_served:
why_dominant_method_is_insufficient:
source_problem_and_solution_mechanism:
target_problem_evidence_and_mechanism:
source_target_structural_match:
disanalogy_and_transfer_limit:
integration_interface:
assumption_and_learning_signal_compatibility:
removal_failure_prediction:
targeted_validation:
```

`integration_interface` must name the actual coupling mechanism, such as a
shared variable, representation, objective, control signal, optimization
constraint, hierarchy, or workflow stage. A topical analogy is not an
integration interface.

Reject or remove a supporting mechanism when:

- it satisfies no unique obligation;
- the dominant method already provides the capability adequately;
- its assumptions or learning signals conflict with the route;
- its source mechanism is not isomorphic to the evidenced target mechanism;
- it creates a second disconnected contribution;
- its removal predicts no specific capability loss.

Allow necessary sophistication. Parsimony removes redundancy, not causal or
inferential links required to close the hypothesis.

## M5 - Scientific closure and minimum validation logic

Build a closure ledger:

```yaml
causal_link:
mechanism_or_component:
claim_supported:
evidence_type:
decisive_test:
expected_failure_or_boundary:
```

For every central claim, state only the minimum validation obligation needed to
show that the proposed technical route is discriminating and falsifiable:

```yaml
claim_validation_obligation:
  claim:
  mechanism_or_link_at_risk:
  decisive_evidence_type:
  supporting_result_pattern:
  falsifying_result_pattern:
  expected_failure_or_boundary:
```

Adapt the evidence type to the contribution. For theoretical work, use proof
obligations, assumption checks, boundary counterexamples, and known-special-case
consistency. Do not design sample sizes, power, confidence intervals,
multiplicity controls, random seeds, dataset splits, or execution schedules in
this contract. After the user accepts the method route, pass these claim
obligations to `/experiment-plan`, which owns detailed experimental validity
and execution planning.

Choose evidence by claim. Valid evidence types include:

- a targeted ablation or intervention;
- a theoretical stability, convergence, or safety argument;
- an identifiability, sensitivity, uncertainty, or credibility analysis;
- a controlled mechanism experiment;
- a transfer, generalization, or boundary test;
- an end-to-end system or real-world validation.

Do not judge a supporting mechanism only by average performance. Test its
removal on the specific capability, failure regime, or causal link it is
responsible for. Also include one overall test of the full scientific
hypothesis. When literal component deletion is meaningless, use a
counterfactual intervention, alternative realization, or measurement-removal
test that challenges the same claimed link.

For 3a–4b closure, `VALIDATED` requires for every core causal chain and every
`MUST` obligation: predicted mechanism change → observed mechanism change →
appropriate discriminating evidence → performance consequence. Core effects
must be identifiable, but this does not require a mechanically separate
ablation for each module: controlled interventions, ablation, counterfactuals,
mechanism measurements, theory, or a necessary joint-mechanism experiment are
acceptable when they discriminate the claimed link. Performance improvement
alone never closes this chain.

## M6 - Novelty and decision gate

Keep these verdicts separate:

```yaml
problem_novelty:
scientific_delta_novelty:
technical_route_novelty:
```

Bind each verdict to a closest-prior × claim-element matrix covering problem
definition, hypothesis, mechanism, integration interface, evidence regime, and
applicability boundary. For each cell record the source/locator, overlap,
residual delta, confidence, search date, and concurrent-work risk. An
unresolved high-overlap cell cannot be converted into novelty by better prose.

Keep internal design provenance separate from manuscript exposition. The
internal ledger should preserve which prior methods or ideas were reused. A
paper-facing abstract, introduction, or method section should normally present
`problem -> mechanism -> method -> boundary`, not a construction diary such as
"A + B", "not a simple combination", or rebuttal-style deletion rhetoric.
State assumptions and boundaries directly and neutrally. Do not obscure genuine
reuse, but do not make source assembly the scientific storyline.

Ask:

1. Is the hypothesis new and scientifically consequential?
2. Is the dominant method the right carrier?
3. Do supporting mechanisms precisely close residual obligations?
4. Is the integration natural at the level of variables, representations,
   objectives, or workflow?
5. Does each critical claimed link have a decisive and falsifiable validation
   obligation?
6. Does the completed route create new understanding or capability rather than
   an additive engineering improvement?
7. Is the planned claim strength no greater than the causal/mechanistic logic
   and proposed decisive evidence can support?

Allowed route verdicts:

```text
READY | REVISE | RETHINK | HOLD
```

- `READY`: the hypothesis, method, integration, novelty, and claim-level
  validation logic form one coherent proposed scientific closure. It means the
  method route is ready for human acceptance and downstream experiment
  planning; it does not claim that experiments are complete.
- `REVISE`: the mainline is promising but a mechanism, interface, or proof is
  incomplete.
- `RETHINK`: the dominant method or causal hypothesis is fundamentally
  mismatched.
- `HOLD`: missing evidence prevents a responsible decision.

At the Controller-owned `method_refinement` Gate, this existing vocabulary has
fixed execution semantics: `READY` is emitted as `METHOD_READY`; `REVISE` and
`HOLD` return to `method_refinement`; and `RETHINK` returns to `method_design`
for a new route and the existing human route-selection step. That Gate does not
use a method verdict to reopen the root-cause analysis or problem premise.

## Canonical output

Expose these sections in order:

1. Certified Problem Contract
2. Root-Cause Analysis Handoff
3. Scientific Mainline
4. Design Obligations
5. Organizing Principle and Dominant Method
6. Implementation Backbone and Innovation Carrier
7. Supporting-Mechanism Ledger
8. Integration and Single Scientific Chain
9. Scientific Closure and Minimum Validation Logic
10. Problem, Scientific-Delta, and Technical-Route Novelty
11. Verdict, Risks, and Next Decision

## Failure paths

| Code | Trigger | Required response |
|---|---|---|
| `SCIENTIFIC_HYPOTHESIS_MISSING` | route starts from techniques without a falsifiable claim | return to M1 |
| `OBLIGATION_UNGROUNDED` | requirement lacks problem or hypothesis trace | delete or re-derive it |
| `DOMINANT_METHOD_UNCLEAR` | no primary technical carrier | regenerate the route |
| `TRANSFER_ANALOGY_WEAK` | cross-field lead lacks causal/structural correspondence | reject the borrowing |
| `INTEGRATION_INTERFACE_MISSING` | components only coexist | redesign the coupling or remove the component |
| `METHOD_ASSEMBLY_BLOAT` | component has no unique obligation | remove it |
| `METHOD_INCOHERENT` | assumptions, objectives, or learning signals conflict | reject the route |
| `NOVELTY_DRIVEN_BLOAT` | a component exists mainly to make the route look more novel | remove it and reassess the smallest adequate route |
| `OPERATIONAL_FEASIBILITY_GAP` | required state, parameter, uncertainty bound, or closed-loop condition is unavailable or undefined | specify the minimal prerequisite or return `REVISE/HOLD` |
| `TARGETED_EVIDENCE_MISSING` | a claimed link lacks a decisive, capability-specific validation obligation | specify the minimum supporting and falsifying evidence |
| `CAUSAL_IDENTIFICATION_MISSING` | causal language lacks a defensible intervention/change, alternative mechanism, or discriminating observation | downgrade the claim or redesign identification |
| `CLAIM_VALIDATION_MISSING` | a must-prove claim lacks decisive evidence and a falsifying pattern | return `REVISE/HOLD`; never issue `READY` |
| `SCIENTIFIC_DELTA_WEAK` | route adds no new mechanism, understanding, boundary, or capability | reposition or rethink |
