# Scientific Method Design Contract

Load this contract only after the independent Root-Cause Gate defined by
[`root-cause-analysis-contract.md`](root-cause-analysis-contract.md) has
accepted `DIAGNOSIS_READY`. It is the scientific source of truth for
Root-Cause-driven Principle formation and Evidence-driven Principle
convergence. Concrete Method adaptation begins only after the Controller has
accepted convergence and materialized `SELECTED_PRINCIPLE.yaml`.

Apply [`source-admission-policy.md`](source-admission-policy.md) before using
any paper. `ACTIVE_FIELD_MAP.md`, its Controller-accepted Evidence, and
formally current phase-scoped Evidence are the only scientific literature
inputs. A ledger reference preserves scientific history but does not make
historical Evidence current.

## Lifecycle and authority

The Controller's `scientific_core` is the only lifecycle authority. This
contract does not create an internal state machine. The scientific sequence is:

```text
accepted Problem and RCA
  -> Required Mechanism Changes
  -> Required Capabilities and Design Obligations
  -> Principle Search
  -> Candidate Principles
  -> fatal assumptions and discriminating predictions/tests
  -> Human-approved atomic execution set
  -> approved test execution
  -> Controller-formed Principle Evidence Context
  -> Evidence Update and convergence review
  -> Controller-materialized Selected Principle
```

The Human test Gate approves execution scope and total cost. It does not select
a Principle, interpret Evidence, or declare convergence. Before convergence,
any concrete realization is test-only operationalization; it is not a Candidate
Method, implementation backbone, final composition, or future Method
commitment.

## Input gate

For `method_design`, require:

- accepted `idea-stage/ACTIVE_FIELD_MAP.md`;
- active `idea-stage/RESEARCH_CONTRACT.md` and
  `idea-stage/PROBLEM_EVIDENCE_CAPSULE.md`;
- accepted `idea-stage/ROOT_CAUSE_ANALYSIS.json` and
  `idea-stage/ROOT_CAUSE_VERDICT.json` with `DIAGNOSIS_READY`, matching IDs and
  hashes, and non-empty primary causal-chain IDs;
- all records in `METHOD_PRINCIPLES.jsonl` and
  `METHOD_TEST_EVIDENCE.jsonl` that the Controller associates with the current
  RMC, Principle/version, assumption, test, Evidence Update, or return context;
- the latest Controller-exposed reviewer guidance, Human feedback, or Full
  Validation feedback directed to this phase.

If a return is active, consume its exact feedback before proposing new
scientific content. A phase return must change the reasoning it identifies; it
must not merely change the current phase and regenerate the same packet.

Directed feedback has these scientific meanings:

- `REVISE_PRINCIPLES`: repair the semantic reviewer's identified Principle,
  mapping, assumption, prediction, test, Evidence, or closure defect;
- Human `request_revision`: change the execution set/test operationalization or
  cost issue identified by the Human and issue the revised packet;
- `MORE_EVIDENCE`: consume the prior Evidence Update and convergence guidance
  when designing the next discriminating cycle;
- `RETHINK`, `RETHINK_PRINCIPLE_DELTA`, or
  `SELECTED_PRINCIPLE_REJECTED`: consume the failed scientific layer and linked
  Evidence before revising or replacing Candidate Principles;
- returned Full Validation: consume its validation-result ID, Evidence,
  findings, and required checks; do not repeat the rejected Principle version
  without resolving them.

If the accepted Problem or RCA binding is absent, changed, or internally
inconsistent, stop. A material problem change uses the existing explicit
problem-revision path. A conflict with the accepted diagnosis uses the declared
`RCA_CONFLICT` return with linked Evidence and guidance; do not rewrite the RCA
inside method design.

## D0 — Derive the machine-resolvable intervention chain

Start from every accepted primary causal chain. Derive the following relation
before naming algorithms, backbones, or modules:

```text
causal_chain_id
  -> mechanism_change_id
  -> capability_id / obligation_id
  -> candidate_principle_id + principle_version
  -> assumption_id / prediction_id / test_id
```

Each Required Mechanism Change contains:

```yaml
mechanism_change_id:
causal_chain_ids: []
failed_relation_state_or_information_structure:
required_mechanism_change:
root_cause_resolution_rationale:
capability_ids: []
obligation_ids: []
acceptance_conditions: []
```

Each Required Capability contains:

```yaml
capability_id:
mechanism_change_ids: []
required_capability:
acceptance_conditions: []
```

Each Design Obligation contains:

```yaml
obligation_id:
mechanism_change_ids: []
capability_ids: []
design_obligation:
acceptance_conditions: []
```

Links are bidirectionally consistent: every ID resolves, every accepted primary
causal chain is represented, and each Capability and Obligation serves at least
one linked Required Mechanism Change. These are not three parallel prose lists.
Their linked content must drive the search, Candidate Principles, tests,
evaluation, Selected Principle, and final validation obligations.

## D1 — Principle Search

For every Required Mechanism Change, actively inspect all four dimensions:

1. `FIRST_PRINCIPLES` — derive interventions from the failed relation, state,
   or information structure itself;
2. `REPRESENTATION_TRANSFORMATION` — ask whether changing the representation of
   the target problem removes the failure mechanism;
3. `SAME_FIELD_MECHANISM` — inspect accepted same-field mechanisms and their
   effective/failure conditions;
4. `CROSS_DOMAIN_STRUCTURAL_ISOMORPHISM` — search for problem–intervention pairs
   with the same causal structure in another domain.

The packet records those dimensions as:

```yaml
principle_search_record:
  first_principles: []
  representation_transformations: []
  same_field_mechanisms: []
  cross_domain_structural_isomorphisms: []
  closure_rationale:
```

When new literature is necessary, use the existing Controller-governed
incremental gateway with `search_mode: PRINCIPLE_SEARCH`. The query-plan context
must bind the current Problem and RCA hashes and the complete RMC/Capability/
Obligation/causal-chain relation. Every query names its search dimension and
the linked IDs it serves. Finish all acquisition or re-adoption before the Main
artifact is sealed for review.

Cross-domain search is mandatory; adopting a cross-domain Candidate is not. If
no credible isomorphism is found, record that bounded result and the search
basis. Never manufacture an analogy.

For every retained cross-domain structural isomorphism, record:

```yaml
source_problem:
source_root_cause:
source_intervention:
changed_relation_state_or_information_structure:
source_mechanism_evidence_refs: []
solution_principle:
target_source_structural_mapping:
causal_direction:
activation_transfer_conditions:
disanalogies:
transfer_boundaries:
```

The cited source Evidence must support the asserted source intervention →
mechanism change → outcome relation. Shared vocabulary or task resemblance is
not structural isomorphism.

## D2 — Candidate Principles

A Solution Principle is an algorithm-independent statement of what intervention
must change which relation, state, or information structure, under what
conditions, to resolve the Root Cause. A named architecture, optimizer,
component bundle, implementation backbone, or parameter choice is not a
Principle.

Each Candidate Principle contains:

```yaml
principle_id:
principle_version:
parent_version: null
principle:
origin:
mechanism_change_ids: []
capability_ids: []
obligation_ids: []
causal_chain_ids: []
activation_conditions:
intervention:
changed_structure:
root_cause_resolution_rationale:
failure_conditions:
fatal_assumptions:
  - assumption_id:
    assumption:
    failure_consequence:
target_domain_operationalization:
provisional_scientific_delta:
predictions:
  - prediction_id:
    assumption_ids: []
    predicted_observation:
    activation_conditions:
    discriminates_from_principle_ids: []
proposed_test_ids: []
evidence_refs: []
status: ACTIVE | REVISED | WEAKENED | MERGED | RETIRED | REJECTED
status_rationale:
```

`parent_version` identifies lineage without overwriting scientific history.
Revisions, weakening, merging, retirement, and rejection require a scientific
reason. Candidate differences must be differences in Principle, not parameters,
backbones, or module names.

For each active Candidate, state its critical unknowns and fatal assumptions,
the smallest faithful target-domain operationalization needed to test them, and
the observation that would distinguish it from substantive competitors. The
packet must explain why search did not close at the first feasible Candidate.
Candidate count is determined by substantive competition, not a quota.

### Provisional Scientific Delta

For each Candidate answer: if this Principle is true within its stated
conditions, what new scientific knowledge, mechanism, representation, boundary,
or important capability could it add? This is a `Provisional Scientific Delta`,
not an established fact. Principle truth/problem-solving ability and the
strength of its possible scientific delta are separate judgments; a weak
provisional delta does not mechanically falsify a real Principle.

## D3 — Discriminating predictions and tests

Tests challenge competing explanations. They are not a collection of
single-Candidate confirmation exercises. Each test contains:

```yaml
test_id:
test_type:
operationalization:
test_only_concrete_realization: {}  # optional; only what the test requires
targets:
  - principle_id:
    principle_version:
    assumption_id:
    prediction_id:
    mechanism_change_id:
    causal_chain_id:
execution_requirements:
estimated_cost:
terminal_outcome_contract:
```

Every active Candidate Principle/version is targeted. While more than one
substantive Candidate remains, the test set and the recommended set include at
least one shared test whose `targets[]` encode the Candidates' different
predictions. A killer test may target one Candidate against a null/baseline,
but the overall set must still discriminate the active competition.

Prefer the cheapest informative or killer tests. Operationalization must be
faithful enough that a result can bear on the targeted assumption and
prediction. State activation conditions, confounds, invalidity conditions, raw
outputs, execution needs, and resource cost. Do not interpret unrun tests.

## D4 — Atomic execution set and canonical packet

`idea-stage/METHOD_DESIGN_PACKET.json` is the machine handoff for one cycle. It
contains exactly one `cycle_id`, one `execution_set_id`, all linked scientific
objects above, a `recommended_execution_set`, and `estimated_total_cost`.

```yaml
recommended_execution_set:
  execution_set_id:
  test_ids: []
  estimated_total_cost:
```

The recommended set covers every active Candidate and preserves shared
discrimination while remaining the smallest informative set. Approval applies
to the complete set and total cost. Adding, removing, or changing a test
requires `request_revision -> method_design`; there is no partial approval.

Also write:

- `idea-stage/METHOD_DESIGN.md` as the deterministic human-readable rendering
  of the packet, with no independent scientific content;
- `idea-stage/METHOD_DESIGN_REVIEW.json` as the formal reviewer verdict;
- proposal/review history only through the existing Controller append actions
  for `METHOD_PRINCIPLES.jsonl` and `METHOD_TEST_EVIDENCE.jsonl`.

The packet must include every Controller-required `relevant_history_refs` and
the current `return_feedback_refs`. It is phase-scoped and contains no phase
status.

After Main finishes any legal Evidence acquisition/re-adoption and writes the
packet, invoke the Controller's `refresh-review-request`. Dispatch the reviewer
only after that action binds the current Controller-accepted inputs and the
final `METHOD_DESIGN_PACKET.json`. If an input or the packet changes after
dispatch, refresh and obtain a new current review; do not review stale inputs.

## D5 — Principle packet semantic review

The Controller-declared `independent_method_reviewer` judges whether:

- Candidates are algorithm-independent Principles rather than renamed Methods;
- RCA → RMC → Capability/Obligation → Principle is scientifically closed;
- active Principles are substantively different;
- every cross-domain mapping is structural and causally supported;
- assumptions, predictions, operationalizations, and tests are valid and
  discriminating;
- Provisional Scientific Delta is stated honestly;
- search avoided premature closure.

Structural validation does not replace this scientific judgment. The only
formal outcomes are:

```text
PRINCIPLE_PACKET_READY -> principle_test_human_approval
REVISE_PRINCIPLES      -> method_design
RCA_CONFLICT           -> root_cause_analysis
```

Every non-accepting verdict includes concrete return guidance. The next
execution consumes it.

## D6 — Approved test execution boundary

After Human approval and while `principle_evaluation` is pending, obtain the
Controller-issued handoff with `method-test-handoff`. Execute only its approved
tests through `/method-test`. Each approved test reaches exactly one terminal
outcome:

- `RESULT_AVAILABLE`, with project-relative raw-result references and execution
  metadata;
- `NO_RESULT`, with reason `execution_failed`, `unavailable`,
  `operationalization_failed`, or `user_stopped`.

Submit each result through `submit-method-test-result`. Completing every test,
not obtaining a positive result, closes the execution window. The Controller
then forms `PRINCIPLE_EVIDENCE_CONTEXT.json`; Main must not create or edit it.

## E0 — Principle Evidence Context and currentness

`PRINCIPLE_EVIDENCE_CONTEXT` is a Controller-formed, cycle-scoped pre-start
input. It binds active Candidate versions, approved tests and their multi-target
relations, terminal outcomes, raw result references, unresolved assumptions,
execution metadata, historical Evidence references, and current consumable
Evidence references.

Only these Evidence classes are current:

- accepted landscape Evidence;
- current-cycle results;
- historical phase-scoped Evidence formally re-adopted in the current
  RMC/Capability/Obligation context;
- Controller-returned Full Validation result/Evidence context.

Historical ledger records remain scientific history but do not restore Evidence
currentness. The Controller mechanically collects formal links; Main decides
their scientific relevance and interpretation.

## E1 — Evidence Update

Start `principle_evaluation` only after the Controller exposes `start_phase`.
Read the current Evidence Context, the accepted Candidate Principle/Test packet,
all Controller-associated cross-cycle history, and the latest return feedback.

For every active Candidate Principle/version, judge:

1. operationalization fidelity;
2. test validity and discriminativeness;
3. whether activation conditions held;
4. observations relative to every targeted competing prediction;
5. how Evidence changes assumptions, boundaries, the RCA interpretation, and
   the Candidate's scientific status;
6. whether a causal-premise conflict requires `RCA_CONFLICT`.

`NO_RESULT` does not support or refute a Principle. It may reveal an
operationalization, feasibility, or test-design failure. Do not convert missing
or invalid results into a scientific rejection.

Write `idea-stage/PRINCIPLE_EVALUATION.json` with the active cycle and execution
set, the exact Evidence Context reference, operationalization/test-validity/
activation assessments, prediction comparisons, an update for every active
Candidate, RCA conflicts, remaining uncertainties, relevant history references,
and current return-feedback references. Principle update decisions are:

```text
SUPPORTED | EXTENDED | REVISED | WEAKENED | MERGED | RETIRED | REJECTED | UNCHANGED
```

An Evidence-changing decision cites current Evidence. Update the persistent
ledgers only through Controller actions. Evidence Update must change scientific
understanding—Principle, assumption, boundary, prediction, test validity, or
RCA—not merely rank performance.

After writing the evaluation, refresh the formal review request so it binds the
current inputs and final `PRINCIPLE_EVALUATION.json`, then dispatch the declared
independent reviewer.

## E2 — Convergence review

`PRINCIPLE_CONVERGED` is allowed only when all are true:

1. the selected version remains an algorithm-independent Solution Principle;
2. valid discriminating Evidence addresses every fatal assumption that could
   overturn the bounded Claim;
3. operationalization fidelity, test validity, and activation conditions were
   checked;
4. all substantive competitors are rejected, weakened, merged, or shown not to
   affect the Claim, boundary, or future Method adaptation choice;
5. no unresolved RCA/causal-premise conflict remains;
6. Evidence is sufficient for Method adaptation without claiming universal
   proof.

The convergence reviewer returns exactly one formal outcome:

```text
PRINCIPLE_CONVERGED -> method_refinement
REVISE_EVALUATION   -> principle_evaluation
MORE_EVIDENCE       -> method_design
RCA_CONFLICT        -> root_cause_analysis
```

`PRINCIPLE_CONVERGED` names exactly one `selected_principle_id` and
`selected_principle_version`. Main must not write `SELECTED_PRINCIPLE.yaml`.
Only after the verdict is accepted does the Controller materialize that file
from the reviewed Candidate and register its Problem/RCA/causal-chain/RMC/
Capability/Obligation bindings, Evidence closure, activation/failure
conditions, applicability boundaries, and remaining uncertainty.

`REVISE_EVALUATION` preserves the same cycle, tests, and raw results and changes
only interpretation or attribution; no test is rerun. `MORE_EVIDENCE` ends the
current Evidence Context and creates a new design/test cycle that must pass the
Human test Gate again.

## Persistent scientific history

`METHOD_PRINCIPLES.jsonl` and `METHOD_TEST_EVIDENCE.jsonl` are append-only
cross-cycle scientific ledgers. They preserve proposals, versions, Evidence
updates, decisions, approvals, handoffs, terminal results, validation rejection,
and scientific reasons. They do not contain `pending/running/current_phase`, are
not normal phase outputs, and are not invalidated by an ordinary phase return.
The Controller remains the only lifecycle authority.

## Scientific Delta stage language

Use these terms exactly:

```text
method_design        -> Provisional Scientific Delta
method_refinement    -> Final Scientific Delta Claim
Full Validation only -> Established Scientific Delta, and only for VALIDATED
```

## Failure paths

| Code | Trigger | Required response |
|---|---|---|
| `RMC_CHAIN_BROKEN` | an RMC, Capability, or Obligation cannot resolve to the accepted RCA | re-derive it or return `RCA_CONFLICT` |
| `PRINCIPLE_IS_METHOD` | a Candidate is a concrete algorithm/backbone/module bundle | restate the algorithm-independent intervention or remove it |
| `PRINCIPLE_SEARCH_INCOMPLETE` | one RMC lacks a recorded search dimension | complete that search dimension |
| `TRANSFER_ANALOGY_WEAK` | cross-domain mapping lacks structural/causal support | reject the mapping |
| `PREMATURE_CLOSURE` | search stops at the first feasible Candidate | restore substantive alternatives and closure rationale |
| `TEST_CONFIRMATORY_ONLY` | tests cannot distinguish active competitors | derive shared discriminating predictions/tests |
| `OPERATIONALIZATION_UNFAITHFUL` | a test does not instantiate the targeted Principle assumption | revise the test packet and repeat Human approval |
| `EVIDENCE_NOT_CURRENT` | an update cites history without current formal eligibility | formally re-adopt or omit it |
| `NO_RESULT_OVERINTERPRETED` | a missing/invalid result is used to support or reject a Principle | restrict it to operationalization/test-feasibility implications |
| `CONVERGENCE_PREMATURE` | a fatal assumption or substantive competitor remains unresolved | return `MORE_EVIDENCE` or `REVISE_EVALUATION` as applicable |
