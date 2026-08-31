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
  -> independent Candidate packet review
  -> Human Candidate selection
  -> selected-Candidate minimum-sufficient test design
  -> independent test-plan review
  -> Human-approved atomic execution set
  -> approved test execution
  -> Controller-formed Principle Evidence Context
  -> Evidence Update and convergence review
  -> Controller-materialized Selected Principle
```

The first Human Gate selects, requests modification of, combines, or rejects
reviewed Candidates. Acceptance creates only a `selected_for_testing` binding;
it does not scientifically support or converge the Candidate and does not create
`SELECTED_PRINCIPLE.yaml`. The second Human Gate approves execution scope and
total cost. It does not select a Principle, interpret Evidence, or declare convergence. Before convergence,
any concrete realization is test-only operationalization; it is not a Candidate
Method, implementation backbone, final composition, or future Method
commitment.

## Input gate

For `method_design`, require:

- accepted `idea-stage/ACTIVE_FIELD_MAP.md`;
- active `idea-stage/RESEARCH_CONTRACT.md` and
  `idea-stage/PROBLEM_EVIDENCE_CAPSULE.md`;
- accepted `idea-stage/NECESSITY_CLOSURE.json` and
  `idea-stage/NECESSITY_VERDICT.json` with `RESIDUAL_SAME_PROBLEM`;
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
  mapping, assumption, prediction, Evidence, or closure defect;
- Human Candidate `request_revision`, `combine`, or `reject`: consume the exact
  feedback, preferentially reuse current Evidence/search/history, and modify,
  combine, replace, or redesign Candidates; conduct incremental literature only
  for a real knowledge gap;
- Human test-plan `request_revision`: change only the test set,
  operationalization, or cost issue identified by the Human;
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
change_direction:
causal_position:
activation_condition:
root_cause_resolution_rationale:
capability_ids: []
obligation_ids: []
```

The change states what causal/computational variable, relation, state, or
information structure must move from its failed condition toward the required
condition, where the intervention acts, and when it activates. It is derived
from the accepted residual RCA; it is not a desired metric or an algorithm.
Observable PASS/FAIL conditions belong to Capabilities and Design Obligations.

Record exactly one `primary_chain_disposition` per accepted primary causal
chain. `RMC` names the consuming RMC IDs. `CLAIM_BOUNDARY` or
`OUTSIDE_FINAL_CLAIM_ENVELOPE` requires current Evidence and a scientific
rationale and may not also bind an RMC. A boundary is not an empty escape hatch:
if it changes the residual Failure or Problem identity, return to Necessity or
Problem Generation. The independent reviewer, not the structural validator,
judges whether each RMC is actually entailed by the accepted RCA.

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
  target_mechanism_signatures: []
  first_principles: []
  representation_transformations: []
  same_field_mechanisms: []
  cross_domain_structural_isomorphisms: []
  discovery_executions: []
  domain_hypotheses: []
  terminology_maps: []
  search_space_closures: []
  closure_rationale:
```

`FIRST_PRINCIPLES` and `REPRESENTATION_TRANSFORMATION` are cognition operations,
not literature queries. Each has a reviewable derivation record. A
first-principles record binds an origin ID and RMC to explicit premises,
derivation steps, formal/Evidence basis, derived intervention, RMC-resolution
rationale, assumptions, and boundaries. A representation record binds an
origin ID and RMC to the old and new representation, how the Failure mechanism
is removed, information preserved/lost, formal/Evidence basis, assumptions, and
boundaries. Non-Source Candidates cite exactly one of these records through
`origin_type + origin_ref_id`.

Literature search is required only for `SAME_FIELD_MECHANISM` and
`CROSS_DOMAIN_STRUCTURAL_ISOMORPHISM`. Use the existing Controller-governed
incremental gateway with `search_mode: PRINCIPLE_SEARCH`. The immutable
`method_design_context.principle_search_context` carries Target Mechanism
Signatures, Domain/Paradigm Hypotheses, Terminology Maps, and explicit decision
targets in addition to the complete Problem/RCA/RMC/Capability/Obligation
binding. A query may serve multiple RMCs when every binding resolves.

For every RMC, derive one Target Mechanism Signature before transfer search. It
states the domain-neutral Failure structure, causal/computational variable or
relation, current state, required intervention and direction, causal position,
and activation condition. It constrains the mechanism being sought; it is not a
universal keyword template.

Cross-domain search uses three query steps inside the same literature gateway:

1. `DOMAIN_DISCOVERY` binds the current RMC and Target Mechanism Signature and
   deliberately does not require a pre-existing Domain Hypothesis;
2. `TERMINOLOGY_GROUNDING` additionally binds an already registered
   Domain/Paradigm Hypothesis;
3. `SOURCE_SEARCH` additionally binds an evidence-grounded Terminology Map and
   explicit Source decision target.

Discovery must execute both `MODEL_PRIOR` and `ACADEMIC_BRIDGE` for every RMC.
MODEL_PRIOR is a Search Hypothesis only and cannot support a Source claim.
ACADEMIC_BRIDGE uses formal scholarly search/read provenance to discover fields,
communities, paradigms, intervention families, terminology, and genealogy clues
that the initial model prior may have missed. Record the two channel executions
separately from Domain Hypotheses. ACADEMIC_BRIDGE may close as
`NO_ADDITIONAL_DOMAIN_HYPOTHESIS` when its accepted scholarly search/read
provenance yields no new high-value hypothesis; do not fabricate a hypothesis.
Every hypothesis it does discover must be registered and bound to that execution.
A traceable practitioner signal
may be used only as a discovery clue when the existing runtime or user supplies
it; it must return to scholarly Evidence before it can support a Source. Do not
add a provider for it.

An EXPLORE hypothesis that actually enters formal `SOURCE_SEARCH` must first
obtain an evidence-grounded Terminology Map containing the candidate domain's
canonical problem, variable/relation, intervention, and method-family terms.
Discovery or a justified CLOSED disposition alone does not require a Terminology
Map. SOURCE_SEARCH uses the local canonical terms to recover a real `Problem ->
Intervention -> Mechanism Change -> Outcome` with assumptions, activation
conditions, and boundaries. New terminology, mechanism, citation, or community
clues create a new/updated hypothesis in a later immutable Query Plan; never
backfill discovery reasoning after seeing a Source.

Search closure requires both discovery channels, CLOSED dispositions with
search/read provenance, all high-value branches explored or explicitly closed,
and no unresolved high-value branch. Fixed query counts, search-cycle limits,
or budget exhaustion cannot supply scientific closure. Use the existing
literature-budget extension when a high-value branch remains open.

Cross-domain exploration is mandatory; adopting a cross-domain Candidate is
not. If the branch closes with no credible Source and another origin is stronger,
continue without fabricating Source, genealogy, or alignment.

Retained same-field and cross-domain Sources remain in the existing
`same_field_mechanisms` and `cross_domain_structural_isomorphisms` collections.
They share one stable `source_mechanism_id` namespace and one causal-efficacy
structure:

```yaml
source_mechanism_id:
served_rmc_ids: []
served_capability_ids: []
served_obligation_ids: []
discovery_provenance:
search_provenance:
genealogy:
mechanism_origin_or_stop_rationale:
source_problem:
source_root_cause: null  # optional; only when Evidence reliably supports it
source_intervention:
changed_variable_relation_or_structure:
causal_or_computational_effect:
outcome:
assumptions:
activation_conditions:
boundaries:
evidence_refs: []
intervention_level_alignment:
```

Cross-domain Sources additionally bind the Target Mechanism Signature,
Domain/Paradigm Hypothesis, Terminology Map, and discovery/search provenance.
Same-field Sources must not fabricate a cross-domain discovery story. The
genealogy records ordered paper/mechanism nodes and lineage relations, or an
Evidence-based stop rationale. The Source RCA is optional; `Source Intervention
-> Mechanism Change -> Outcome` is mandatory and requires current formal
Evidence. Venue, popularity, primitive age, shared vocabulary, task resemblance,
algorithm name, or architecture resemblance cannot make a Strong Source.

For every retained Source, perform Intervention-Level Isomorphism against its
served RMC. Compare the causal/computational role, current-to-required direction,
intervention position, activation condition, Source actual effect, and
assumption/boundary mismatches. `PASS` requires that the Source Intervention
actually changes the very relation the accepted Target RCA/RMC requires, in the
right place, direction, and activation regime. Whole-problem and whole-root-
cause isomorphism are not required. `FAIL` forbids an active Candidate: follow a
new clue back through Discovery/Terminology/Search or, when it exposes an RMC
error, return to RCA. Only `PASS` may abstract an algorithm-independent Solution
Principle; never copy the Source implementation.

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
derived_from_principles: []  # optional; multi-Candidate synthesis only
principle:
origin_type: FIRST_PRINCIPLES | REPRESENTATION_TRANSFORMATION | SAME_FIELD_SOURCE | CROSS_DOMAIN_SOURCE
origin_ref_id:
alignment_ref_id: null  # required PASS alignment for Source origins
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
target_intervention_novelty:
  novelty_closure_id:
  nearest_target_prior_evidence_refs: []
  causal_equivalent_intervention_check: UNCOVERED | PARTIALLY_COVERED | COVERED
  evidence_search_provenance: []
  uncovered_residual_delta:
  mechanism_delta:
  scientific_delta:
  disposition: NOVEL_DELTA | RESTRUCTURED_DELTA | REJECTED_AS_COVERED
provisional_scientific_delta:
predictions:
  - prediction_id:
    assumption_ids: []
    observable:
    pattern_a:
    rival_type: PRINCIPLE | RIVAL_RCA
    rival_id:
    pattern_b:
    activation_condition:
    killer_criterion:
    cheapest_informative_rationale:
substantive_difference:
evidence_refs: []
status: ACTIVE | REVISED | WEAKENED | MERGED | RETIRED | REJECTED
status_rationale:
```

`parent_version` identifies single-Candidate revision lineage without overwriting
scientific history. `derived_from_principles` is optional and records a
multi-Candidate synthesis as exact `{principle_id, principle_version}` sources.
After a Human `combine` decision, its receipt must name at least two exact
`ID@version` sources from the reviewed packet; the resulting synthesis Candidate
must carry exactly those sources. The Controller rejects dangling, stale, or
unreviewed sources. The synthesis must combine mechanisms at the Principle
level, not concatenate concrete modules. Revisions, weakening, merging,
retirement, and rejection require a scientific reason. Candidate differences
must be differences in Principle, not parameters, backbones, or module names.

For each active Candidate, state its critical unknowns and fatal assumptions,
target-domain operational meaning, predicted observations, primary risks, and
substantive mechanism/Scientific-Delta differences from other Candidates. The
packet must explain why search did not close at the first feasible Candidate.
Candidate count is determined by substantive competition, not a quota.

The packet records one `solution_space_constraint_assessment`:

```yaml
solution_space_constraint_assessment:
  disposition: UNDERCONSTRAINED | CONSTRAINED
  constraint_basis:
```

`UNDERCONSTRAINED` requires multiple surviving Candidates whose intervention
mechanisms are scientifically distinct. `CONSTRAINED` permits one surviving
Candidate only when the declared constraints genuinely determine that solution
space. Backbone, optimizer, parameter, implementation, or module differences do
not create Principle competition. The Validator checks disposition and active
Candidate multiplicity; the reviewer judges whether the constraint basis and
mechanism differences are scientifically real.

Every Candidate prediction is a Human-selection-time killer-test concept: one
observable, this Candidate's Pattern A, a relevant Rival Principle or Rival RCA
and its Pattern B, the activation condition, a falsification/killer criterion,
and why it is the cheapest informative distinction. It is not a concrete test
and contains no operationalization, execution requirements, test-only
realization, execution set, or cost.

Every active Candidate binds one real origin. Source origins cite a stable
`source_mechanism_id` plus its accepted alignment; derivation origins cite their
structured cognition record and do not invent Source or Genealogy fields. Before
`PRINCIPLE_PACKET_READY`, each active Candidate also closes Early Target
Intervention Novelty against nearest Target-domain priors. If the Target already
contains a causal-equivalent intervention, a renamed algorithm or architecture
cannot remain a Strong active Candidate; reject, downgrade, or identify a real
residual delta. Conversely, transfer, an old Source primitive, or a small Target
adaptation is never a mechanical weakness. The questions are whether the Target
causal intervention was previously uncovered, relieves the RMC, and yields a
clear, meaningful, verifiable Mechanism and Scientific Delta.

### Provisional Scientific Delta

For each Candidate answer: if this Principle is true within its stated
conditions, what new scientific knowledge, mechanism, representation, boundary,
or important capability could it add? This is a `Provisional Scientific Delta`,
not an established fact. Principle truth/problem-solving ability and the
strength of its possible scientific delta are separate judgments; a weak
provisional delta does not mechanically falsify a real Principle.

## D3 — Candidate packet, human view, and semantic review

`idea-stage/METHOD_DESIGN_PACKET.json` is the machine handoff for one design
cycle. It contains the RCA → RMC → Capability/Obligation → Principle Search →
Candidate Principle chain, relevant history references, and current return
feedback references. It contains no concrete test, execution set, or cost.

`idea-stage/METHOD_DESIGN.md` is its deterministic human-readable view. For
every Candidate it states in plain language the mechanism, Provisional
Scientific Delta, primary risks, and substantive differences. It does not hide
those decisions inside a raw JSON dump.

The Controller-declared `independent_method_reviewer` judges whether accepted
residual RCA really entails each RMC and whether every primary-chain boundary is
scientifically legitimate; whether the four Principle spaces were genuinely
covered; whether cognition derivations are substantive; whether Domain Discovery
and local Terminology/Search closure are complete rather than budget-driven;
whether Sources have causal-efficacy Evidence and real genealogy; whether
Intervention-Level Isomorphism passes; whether Early Target Novelty excludes
causal-equivalent Target priors without penalizing mature transfer; and whether Candidates
are algorithm-independent, causally close the accepted RCA through the declared
RMCs/Capabilities/Obligations, are substantively distinct, use real structural
isomorphism rather than surface analogy, state fatal assumptions and predictions
honestly, consume active return feedback, and avoid premature closure. The
formal outcomes are:

```text
PRINCIPLE_PACKET_READY -> principle_human_selection
REVISE_PRINCIPLES      -> method_design
RCA_CONFLICT           -> root_cause_analysis
```

After review acceptance, the Human may `select` exactly one Candidate version,
`request_revision`, `combine`, or `reject`. Non-acceptance requires feedback and
returns to `method_design`; the next packet must cite and actually consume that
return event. Selection establishes the Controller's `selected_for_testing`
binding and advances to `principle_test_design`. It creates neither a test cycle
nor a formal Selected Principle.

## D4 — Selected-Candidate minimum-sufficient test plan

`principle_test_design` reads only the active Human-selected Candidate, its
fatal assumptions/predictions, current formal Evidence, relevant history, and
return feedback. It designs the current minimum sufficient, highest-information
execution set and prioritizes falsification of assumptions that could kill the
Candidate's core mechanism or Scientific Delta. If existing data, low-cost
analysis, or computation can decide the question, do not escalate to a large or
physical experiment.

Write `PRINCIPLE_TEST_PLAN.json`, its deterministic
`PRINCIPLE_TEST_PLAN.md` view, and `PRINCIPLE_TEST_PLAN_REVIEW.json`. Each test
contains:

```yaml
test_id:
test_type:
evidence_tier: EXISTING_DATA_ANALYSIS | COMPUTATIONAL | TARGETED_BENCH | PHYSICAL_EXPERIMENT
killer_test_concept_ref:
operationalization:
test_only_concrete_realization: {}  # optional; only what the test requires
observation_contract:
  observable:
  pattern_a:
  rival_type: PRINCIPLE | RIVAL_RCA
  rival_id:
  pattern_b:
  activation_condition:
terminal_criteria:
  pattern_a_criterion:
  pattern_b_criterion:
  inconclusive_criterion:
targets:
  - principle_id:
    principle_version:
    assumption_id:
    prediction_id:
    mechanism_change_id:
    causal_chain_id:
information_gain:
falsification_criterion:
execution_requirements:
estimated_cost:
terminal_outcome_contract:
```

The concrete plan preserves the reviewed killer-test concept's observable,
Candidate/Rival Pattern A/B, rival identity, and activation condition while
adding operationalization, execution requirements, test-only realization,
execution set, cost, and formal terminal criteria. A performance-only ablation
is not automatically discriminating; the reviewer rejects a schema-valid plan
that cannot distinguish the competing mechanisms.

The plan records fatal-assumption priority, minimum-sufficiency and information-
gain rationales, lower-cost Evidence assessment, and the reason any physical
experiment is unavoidable. It may contain only tests in the current recommended
execution set:

```yaml
recommended_execution_set:
  execution_set_id:
  test_ids: []
  estimated_total_cost:
```

The same `independent_method_reviewer` applies the separate test-plan rubric:

```text
TEST_PLAN_READY  -> principle_test_human_approval
REVISE_TEST_PLAN -> principle_test_design
RCA_CONFLICT     -> root_cause_analysis
```

Only an accepted test-plan review reaches the Human cost/execution Gate. Human
approval applies atomically to that plan's complete set and total cost. A
change returns to `principle_test_design` and preserves the selection binding.

## D5 — Approved test execution boundary

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
 input. It binds the one Human-selected Candidate version, approved tests and their target
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
Read the current Evidence Context, the accepted Candidate packet and accepted Test Plan,
all Controller-associated cross-cycle history, and the latest return feedback.

For the Human-selected Candidate Principle/version, judge:

1. operationalization fidelity;
2. test validity and discriminativeness;
3. whether activation conditions held;
4. observations relative to the targeted predictions and falsification criteria;
5. how Evidence changes assumptions, boundaries, the RCA interpretation, and
   the Candidate's scientific status;
6. whether a causal-premise conflict requires `RCA_CONFLICT`.

`NO_RESULT` does not support or refute a Principle. It may reveal an
operationalization, feasibility, or test-design failure. Do not convert missing
or invalid results into a scientific rejection.

Write `idea-stage/PRINCIPLE_EVALUATION.json` with the active cycle and execution
set, the exact Evidence Context reference, and structured per-test records for
operationalization fidelity, test validity/discriminativeness, activation
outcome, observed Pattern A/B/other, and Rival discrimination. Each record binds
the reviewed test and prediction IDs and cites only current Evidence.

Add `scientific_updates[]`; each update contains a stable `update_id`,
`target_type`, `target_id`, `before`, `proposed_after`, `evidence_refs`,
`consequence`, and rationale. Target types cover Principle, assumption,
Source–Target mapping, target operationalization, applicability boundary, Rival
Principle, Rival RCA, Root Cause, and Necessity/residual envelope. Consequence is
exactly one of:

```text
REVISE_EVALUATION | MORE_EVIDENCE | UPDATE_BOUNDARY | RETURN_METHOD_DESIGN
REOPEN_RCA | REOPEN_NECESSITY | REDEFINE_PROBLEM
```

These are Main's Evidence interpretation and proposed consequences, never
Controller transition authority. Main cannot edit an accepted RCA or Necessity
artifact in place. Update persistent ledgers only through Controller actions.
Evidence Update must change scientific understanding—not merely rank
performance.

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
4. no unresolved RCA/causal-premise conflict remains;
5. Evidence is sufficient for Method adaptation without claiming universal
   proof.

The convergence reviewer returns exactly one formal outcome:

```text
PRINCIPLE_CONVERGED -> method_refinement
REVISE_EVALUATION   -> principle_evaluation
MORE_EVIDENCE       -> principle_test_design
CANDIDATE_REJECTED  -> method_design
RCA_CONFLICT        -> root_cause_analysis
NECESSITY_CONFLICT  -> problem_necessity
PROBLEM_CONFLICT    -> problem_generation
```

`PRINCIPLE_CONVERGED` names exactly one `selected_principle_id` and
`selected_principle_version`, plus the IDs of any reviewed `UPDATE_BOUNDARY`
records the reviewer accepts. Main must not write `SELECTED_PRINCIPLE.yaml`.
Only after the verdict is accepted does the Controller materialize that file
from the reviewed Candidate, evaluation, Evidence Context, and verdict. It
preserves the Principle/intervention/changed structure; Problem/RCA/causal-chain/
RMC/Capability/Obligation bindings; exact derivation or Source origin and
alignment; Target novelty closure; accepted assumptions and killer predictions;
Provisional Scientific Delta; Evidence closure; Reviewer-accepted boundary
updates within the applicability boundaries; and remaining uncertainty. It
contains only the converged Candidate closure, not rejected-Candidate noise.

`REVISE_EVALUATION` preserves the same cycle, selection, tests, and raw results
and changes only interpretation or attribution; no test is rerun.
`MORE_EVIDENCE` preserves the selected Candidate, ends the current Evidence
Context, and returns to `principle_test_design` for a new minimum test round and
Human approval. `CANDIDATE_REJECTED` requires current Evidence rejecting the
core mechanism or fatal assumption, records the failed version as stopped,
invalidates the selection binding, and returns that failure Evidence to
`method_design`. `RCA_CONFLICT` invalidates the binding and reopens RCA.
`NECESSITY_CONFLICT` invalidates it and reopens `problem_necessity` when the
accepted residual envelope or Necessity premise conflicts with Evidence.
`PROBLEM_CONFLICT` invalidates it and returns to `problem_generation`, including
the complete Problem quality, novelty, and Human-acceptance chain. Only the
attested reviewer verdict selects these transitions; Main's consequence never
does.

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
