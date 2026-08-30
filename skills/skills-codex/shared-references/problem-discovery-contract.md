# Research Problem Discovery Contract

Use this contract when a workflow moves from literature understanding to
problem discovery and certification. It is the single source of truth for that
handoff. Use `root-cause-analysis-contract.md` only after certification;
method design additionally requires an accepted root-cause verdict.

Before P1, apply
[`source-admission-policy.md`](source-admission-policy.md). Proactively retrieved
papers must be `ADMIT`; explicitly user-supplied materials must be
`USER_SUPPLIED_READ` and content-assessed before they shape the Field Evidence
Map, candidate problems, migration evidence, or problem-novelty judgment.

## Contents

- P0: define field purpose, scope, constraints, and success criteria.
- P1: build a problem-centered Field Evidence Map in a fixed scientific order.
- P2: discover and mature Leads from community, self-discovery, and migration.
- P3: certify problem quality independently.
- Handoff: pass one unchanged Certified Problem Contract to root-cause analysis.

## Core doctrine

The required causal order is:

```text
field purpose and constraints
  -> typical tasks and scenarios
  -> core bottlenecks
  -> evidence-validated major method families
  -> family origins, turning points, interactions, and current frontiers
  -> bottlenecks each family addresses
  -> assumptions and conditions of success
  -> failure conditions and boundaries
  -> unresolved contradictions
  -> Lead discovery and triage
  <-> targeted deep dive, evidence, and reframing
  -> mature problem candidates
  -> independent problem-quality gate
  -> problem-novelty check
  -> Certified Problem Contract
  -> root-cause-analysis-contract.md
```

Do not start from a fashionable method and search backward for a problem. Do
not treat an unsearched area, a paper count, or an author-written future-work
sentence as proof that a valuable research problem exists.

### Root-cause-analysis handoff

This contract ends when a problem is `CERTIFIED`. Then load
[`root-cause-analysis-contract.md`](root-cause-analysis-contract.md), which
defines 1a-2b and the independent diagnosis Gate. Only a validated
`DIAGNOSIS_READY` verdict may then load
[`method-design-contract.md`](method-design-contract.md). Do not duplicate
either downstream contract here.

When Full Validation returns `PROBLEM_PREMISE_REJECTED`, reopened problem
generation must consume the Controller-linked validation-result ID, Evidence
references/result paths, findings, and structured return guidance. Reassess the
rejected premise and only its directly affected framing/evidence fields; do not
silently preserve the rejected premise or inherit the former Method's
interpretation of the Evidence.

## Phase contracts

### P0 — Research Frame

Required fields:

```yaml
field_or_domain:
core_purposes:
task_and_scenario_scope:
constraints:
non_goals:
success_criteria:
```

If the field has competing purposes, record the trade-off instead of forcing
one artificial objective.

### P1 — Evidence Map

The map is problem-centered, not a chronological paper list.

Use two layers:

1. **Active Field Map** — a compact decision view containing the field purpose,
   core problem/method families, family-level development traces,
   contradictions, failure boundaries, leading problem signals, coverage
   status, and source IDs. Keep this in active context.
2. **Evidence Registry** — full source cards and retrieval traces. Store it as
   an artifact, including supported paper-level development links for key work,
   and retrieve cards by `source_id` only when a decision needs them.

Do not pass the full registry through every downstream stage. The compact map
must preserve uncertainty and source IDs; it must not replace the evidence.

Build the landscape in this order. Do not jump from papers directly to gaps:

```text
field core purposes
  -> typical tasks and scenarios
  -> core bottlenecks
  -> evidence-validated major method families
  -> origins, turning points, interactions, and current frontier of each family
  -> which bottleneck each family addresses and by what mechanism
  -> assumptions each family requires
  -> conditions where each family is effective
  -> conditions where each family fails
  -> unresolved contradictions
```

Required sections:

```yaml
field_core_purposes:
typical_tasks_and_scenarios:
core_bottlenecks:
method_families:
family_development_traces:
problem_method_matrix:
assumption_effectiveness_failure_matrix:
evidence_cards:
consensus:
unresolved_contradictions:
coverage_record:
unresolved_problem_leads:
```

The `problem_method_matrix` must name the mechanism by which each method family
addresses each bottleneck. The `assumption_effectiveness_failure_matrix` must
connect, in one row, the method family, required assumptions, effective
conditions, failure conditions, and source IDs. A taxonomy without these
relations is not a field map.

Derive the major-family taxonomy by triangulating high-quality reviews,
representative-paper introductions, and the papers' actual methods. Treat each
author's taxonomy as a perspective rather than authority. Prefer a small number
of field-recognized broad families while preserving genuine mechanistic
differences; keep a sparse direction as a branch or emerging line unless it
clearly constitutes a distinct family.

Treat the taxonomy as an evidence-conditioned working model. Differences among
sources may reflect author perspective, scope, or the field's historical stage.
Reassess family boundaries and paper assignments as new literature is read;
revise them when the combined evidence is sufficiently clear, and preserve
competing views when it is not. Consensus is useful but neither mandatory nor
permanent.

`family_development_traces` must reconstruct the evidence-supported explanatory
lineage from research problem through method, evidence, residual bottleneck,
transition, and subsequent evolution. The frame is fixed, but its shape is
determined by the literature: do not prescribe stage counts, time spans, branch
counts, or a single linear history, and do not create a stage from calendar
boundaries alone. Parallel branches, forks, merges, long-term coexistence, and
paradigm shifts are valid when the evidence supports them. Keep the main map at
family level. Store paper-level links only for foundational, turning-point, and
current representative work in the Evidence Registry; a transition may be
supported by several papers and need not have one landmark paper.

Each key transition must also be a causal research-question transition, not
only a method-ordering statement. Record one compact row per transition:

```yaml
transition_id:
previous_problem_or_bottleneck:
progress_and_conditions:       # method/mechanism, evidence-supported progress, and conditions
residual_or_new_bottleneck:
research_question_shift:       # why the question migrated, expanded, or reframed
subsequent_direction:
transition_problem_status: still_open | partially_addressed | mature_under_specific_conditions | reframed
evidence_ids:                  # Evidence Registry IDs supporting the row
```

Do not infer a transition from chronology, citation order, or publication date
alone. Here, a causal development trace is an evidence-supported explanatory
lineage: the row must make clear what method or mechanism produced which
progress under what conditions, what remained open or newly became visible,
and why the next direction followed. Create a row only for a real research-
problem or method-paradigm change supported by evidence; an empty trace is
valid when the literature supports no material transition. Use
`transition_problem_status` only for the state of the
problem at that transition; its human-facing labels are “still open”,
“partially addressed”, “mature under specific conditions”, and “reframed”. Do
not turn it into a method-quality score.

Each `evidence_card` must contain:

```yaml
source_id:
claim:
claim_locator: page | section | figure | table | theorem | paragraph
access_level: metadata | abstract | partial_text | full_text
decision_grade: discovery_only | decision_grade
epistemic_status: established | supported | preliminary | speculative | contested
problem_and_setting:
method_or_mechanism:
content_summary:
synthesis_role:
development_link:
evidence:
evidence_kind:
boundary_conditions:
assumptions:
reported_or_inferred_failures:
conflicts_with:
verification_status:
```

`reported_or_inferred_failures` must distinguish author-reported evidence from
executor inference. A verified paper identity does not verify every scientific
claim inside the paper.

Use a two-tier evidence policy with weighted reading depth:

- Every eligible relevant source must be inspected deeply enough to summarize
  its actual problem, method or mechanism, claimed contribution, evidence, and
  boundary. If only metadata or an abstract is accessible, keep it
  `discovery_only` and do not count it as content-read.
- `discovery_only` evidence may seed taxonomies, queries, contradictions, and
  candidate problems. Metadata, snippets, abstracts, and unlocated notes remain
  at this tier.
- `decision_grade` evidence must come from inspected source content with an
  exact locator and enough surrounding context to verify the claim, setting,
  comparison, and stated boundary. Full text is normally required for claims
  about failure causes, negative results, assumptions, novelty, or closest
  prior capability.

Before P3, escalate every claim that could change Reality, Importance,
Unresolvedness, scope, or the closest-prior judgment to `decision_grade`.
Allocate close reading to foundational, influential, turning-point, current
representative, contradictory, decisive, and nearest-prior work. Other admitted
papers still receive a basic content summary and support branches, consensus,
or boundaries. Do not load the whole corpus into active context.

If an ineligible proactively retrieved paper appears downstream, remove it from
the Evidence Map and active scientific context but retain its metadata,
discovery provenance, and exclusion reason in the literature corpus. Do not
apply that evidence-removal rule to explicitly user-supplied material; instead
retain its post-read assessment and boundary. If a decision-critical claim then
loses support, return `HOLD`; never replace source eligibility with a weaker
evidence label.

The `coverage_record` must state:

- databases and retrieval routes actually attempted;
- exact executed queries, query families, naming variants, screened/relevant
  counts, and failed or low-precision routes;
- foundational and recent time bands;
- venues or source classes covered and candidate admission/exclusion counts;
- major branches plus their foundational, influential, turning-point, and
  current representative anchors;
- backward/forward citation expansion actually executed for decisive sources;
- taxonomy sources, family-boundary checks, and key development transitions;
- negative-result, reproduction, benchmark, or diagnostic searches attempted;
- unresolved paper identities, known blind spots, and unavailable sources.

#### Landscape stopping rule

The deterministic completion gate (Type-A) checks that the search log and
complete candidate corpus exist, every admitted retained paper has an evidence
card, and every claimed query or citation action has an audit record. Landscape
sufficiency is a Type-B judgment. Mark it `SUFFICIENT`, `PARTIAL`, or
`INSUFFICIENT`; never claim exhaustive coverage.

`SUFFICIENT` requires all of:

1. all major purpose/problem/method families and branches found so far have
   evidence;
2. every major family covers its foundational, influential or turning-point,
   and current representative anchors when the literature supports them;
3. after the initial map, one complete cycle containing both targeted query
   refinement and backward/forward citation expansion adds no major branch and
   changes no family anchor or leading nearest-prior set, and further reading
   reveals no uncovered important branch or development lineage requiring a new
   query; otherwise repeat the affected branch before testing saturation again;
   and
4. every cited paper identity is verified, with no unresolved or mismatched
   identity supporting a decisive claim.

The major-family taxonomy and its key development transitions must also be
triangulated well enough that an alternative plausible grouping would not
materially change the unresolved contradictions or leading problem candidates.

It also requires, when the field supports them:

- Google Scholar broad, high-citation, recent, exact-title, and `Cited by`
  discovery views through the fixed SerpApi -> `scholar.google.hk` route, or an
  explicitly recorded arXiv + IEEE Xplore fallback when both Scholar paths are
  unavailable;
- targeted negative-result, reproduction, benchmark, and diagnostic queries;
- decision-grade evidence for each core family and leading nearest prior.

If unavailable Google Scholar access, a paywall, missing full text, unresolved
identity, or an unclosed branch prevents these checks, use `PARTIAL` and name
the blind spot. A `PARTIAL` landscape may be persisted as progress, but it must
not be presented as a complete research-state survey or authorize a Certified
Problem Contract or human problem acceptance. Only `SUFFICIENT` authorizes
that checkpoint.

Interpret `SUFFICIENT` as **working saturation for the declared scope**, not as
proof that no unknown literature exists. Always retain known blind spots.

### P2 — Lead discovery, triage, and maturation

The three routes `community_open_problem`, `self_discovered`, and
`problem_migration` are discovery routes, never quotas. A Lead is internal
cognition, not a Stage, State, Artifact, Registry, Gate, Reviewer, version, or
epoch. Fan-out may discover and triage Leads, but must not materialize a formal
Candidate directly.

Discover Leads from both complementary sources. First, compare the Field Map
horizontally across papers and families: shared assumptions, recurring failure
patterns, applicability boundaries, inconsistent results, and unresolved
contradictions can expose a potential bottleneck. Second, a key paper may
inspire a Lead through a discussion/conclusion limitation, an exposed method
bottleneck, or a promising underdeveloped direction. In either case, the
observation is only a Lead. A paper limitation or future-work sentence must not
be converted directly into a Problem Candidate; compare it with the wider field
and run the targeted deep dive first.

For every Lead, record in the active working context: the starting observation,
why it is worth tracking, largest uncertainty, current basis, and the kind of
evidence that could directly weaken or overturn it. Only a promising Lead may
enter targeted deep dive. Treat that deep dive as an attempted disconfirmation,
not a search for support. After each Evidence round, the Agent may strengthen,
narrow, reframe, reject, or mature it. Check the closest/strongest prior and
its residual unresolved delta, strongest counterevidence, alternative
explanation, whether it is truly unresolved, and whether simple application or
tuning already solves it. Do not prescribe paper, search, or route counts.

Maturation judges Reality, Importance, Unresolvedness, Precision,
Falsifiability, and Answerability. Scope/boundary is part of Precision; closest
prior plus residual unresolved delta is central to Unresolvedness. A rejected
Lead creates no formal Candidate and continues ordinary Lead cognition. Only a
mature Lead is expanded into the existing formal Candidate below, then enters
the existing Candidate Validator, Quality Gate, Novelty Gate, and Human
Acceptance path.

While `problem_generation` is running, a promising Lead may use the existing
incremental literature gateway. Each query item must bind one immutable working
snapshot: non-empty `lead_id`, `lead_statement`, `purpose`, and
`expected_close_condition`; the current accepted `active_field_map_sha256`; and
exactly one `decision_dimension` from `Reality | Importance | Unresolvedness |
Precision | Falsifiability | Answerability`. Strengthening, narrowing, or
reframing a Lead, and replacing its Query Plan within the same derivation, does
not create a formal derivation or stale that derivation's Evidence.

### Mature Problem Candidate

Each candidate must contain:

```yaml
problem_id:
source_class:
research_question:
observed_phenomenon:
scope_and_conditions:
evidence_refs:
why_it_matters:
value_if_yes:
value_if_no:
plausible_explanations:
measurement_validity:
artifact_or_confound_alternatives:
independent_support:
phenomenon_prevalence_or_effect_scale:
decision_owner_and_threshold:
falsifier:
feasible_discriminating_probe:
closest_prior_answer:
uncertainties:
```

`PROBLEM_CANDIDATES.jsonl` is the Controller-consumed index. Each line uses
the same `problem_id` and a `source_class` from
`community_open_problem | self_discovered | problem_migration`; IDs are unique
within the generated set. It carries every required P2 field above, plus a
non-empty `dedup_key` and `provenance` object. Narrative fields are non-empty
strings; `evidence_refs`, `artifact_or_confound_alternatives`,
`independent_support`, and `uncertainties` are non-empty string lists.
`plausible_explanations` is a non-empty list of
`{explanation, epistemic_status}` records, where status is `supported`,
`preliminary`, `speculative`, or `contested`. Every `evidence_refs` ID must
resolve to current formal evidence. This Type-A schema check prevents an
incomplete scientific question from reaching review; it does not turn Reality,
Importance, Unresolvedness, or novelty into scores.

At this phase, method analogies may be retained as search leads, but do not
design or rank full methods before the problem gate.

For a phenomenon supported by only one source or one benchmark construction,
require an independent re-analysis, reproduction, triangulating source, or
feasible replication probe. Otherwise keep Reality at `HOLD`.

Keep at least two plausible explanations when the evidence permits. Label each
as `supported`, `preliminary`, `speculative`, or `contested`; do not promote a
plausible story to a causal diagnosis before discriminating evidence.

#### Problem-migration check

Enforce this order for both problem migration and any later method migration:

```text
observe problem P in a source field
  -> extract the mechanism that produces P
  -> test whether the target field contains a structurally isomorphic mechanism
  -> confirm with target-field data that P actually occurs
  -> only then consider transferring a solution principle or method
```

A migrated problem must pass the structural mapping and boundary check:

```yaml
source_problem_and_evidence:
source_problem_formation_mechanism:
target_mechanism_mapping:
target_structural_isomorphism:
target_problem_evidence:
stakes_and_scope:
disanalogy_and_transfer_limit:
unit_and_variable_mapping:
expected_invariants:
non_invariants_that_may_break_transfer:
target_negative_control_analogue:
transfer_failure_criterion:
solution_transfer_status: forbidden_until_target_confirmed | eligible_for_method_search
```

In the machine candidate record, all migration narrative fields are non-empty
strings; `unit_and_variable_mapping` is a non-empty object; and the two
invariant fields are non-empty string lists. The Controller validates this
conditional structure, not whether the claimed isomorphism is scientifically
sound.

Reject a migration based only on shared vocabulary such as “long tail,”
“sparsity,” or “long sequence.” Similar outcomes without a matched formation
mechanism are also insufficient. If the target phenomenon has not been
independently observed or probed, keep the migration at `HOLD` and set
`solution_transfer_status: forbidden_until_target_confirmed`. Do not let a
source-field solution influence target diagnosis before this gate passes.

### P3 — Problem Quality Gate

Problem quality is a Type-B judgment. The executor may generate and annotate
candidates, but an independent reviewer owns the final verdict. Start this
verdict in a fresh review context that receives the candidate set and primary
evidence, not the generator's reasoning history. Follow
[`reviewer-independence.md`](reviewer-independence.md).

Assess six dimensions:

| Dimension | Required question |
|---|---|
| Reality | Is the phenomenon supported rather than merely asserted? |
| Importance | What scientific or practical decision changes, and does the answer yield a reusable explanation, boundary, or capability rather than an isolated benchmark gain? |
| Unresolvedness | What exactly remains unanswered by the closest work? |
| Precision | Are scope, conditions, variables, and boundary explicit? |
| Falsifiability | What result would overturn the proposed problem framing? |
| Answerability | Can available evidence discriminate among explanations? |

Hard gates do not average away:

- no supporting evidence -> `HOLD`;
- any decisive claim remains `discovery_only` -> `HOLD` pending targeted
  full-text verification;
- no meaningful consequence under either answer -> `REJECT`;
- already answered in the stated scope -> `REJECT` or narrow the scope;
- no feasible discriminating probe -> `HOLD`;
- critical safety, ethics, or compliance conflict -> `BLOCKED`;
- material search-coverage blind spot -> `HOLD` pending targeted search.

Allowed verdicts:

```text
CERTIFIED | HOLD | REJECT | BLOCKED
```

## Formal verdict record

`PROBLEM_QUALITY_VERDICTS.jsonl` and `PROBLEM_NOVELTY_VERDICTS.jsonl` each
contain one `candidate_verdict` JSON record per reviewed candidate plus exactly
one `phase_verdict` record. Every record carries the same
`schema_version: 1`, `review_request_id`, `reviewer`, `verdict_id`, and
`reviewed_artifact_hashes`; candidate records additionally carry `candidate_id`.
The phase decision is the only Controller transition decision and must appear
among the candidate decisions. Use `CERTIFIED | HOLD | REJECT | BLOCKED` for
quality candidates and `NOVEL | UNCERTAIN | NOT_NOVEL | BLOCKED` for novelty
candidates; do not substitute `CONFIRMED` for `NOVEL`.
The phase record additionally carries `survivor_ids`, exactly the candidate
IDs whose candidate decision equals the phase decision. Quality reviews cover
the complete registered candidate set; novelty reviews cover exactly the
quality survivors. For Human problem selection, eligibility is instead the
intersection of quality `survivor_ids` and candidate-level novelty decisions
`NOVEL`, `NOT_NOVEL`, or `UNCERTAIN`: every quality-certified candidate must
receive a complete novelty audit, while `BLOCKED` candidates are not selectable.
The Contract names the candidate registry and both verdict artifacts by path,
SHA-256, and verdict ID, and its `Problem novelty verdict` exactly equals the
selected candidate's audited decision. The Evidence Capsule names the same
selected `Problem ID` and the exact Contract path/SHA-256. The Human receipt
binds that selection and both resulting handoffs.

Quality candidate records additionally contain a `quality_assessment` object
with exactly `Reality`, `Importance`, `Unresolvedness`, `Precision`,
`Falsifiability`, and `Answerability`. Each dimension records a `PASS`,
`INSUFFICIENT_EVIDENCE`, or `FAIL` judgment, rationale, evidence IDs, and issue
IDs. `Reality`, `Importance`, and `Unresolvedness` require non-empty bound
formal evidence IDs. `Precision`, `Falsifiability`, and `Answerability` may
leave evidence IDs empty when the judgment follows from the already bound
candidate and Field Map; do not add irrelevant literature anchors. Novelty
candidate records additionally contain `novelty_assessment` with closest priors, search coverage, residual
unresolved delta, formal evidence IDs, and issue IDs. Each closest-prior row
records `paper_id`, overlap, residual delta, `potentially_decisive`, and either
a decision-grade `evidence_id` whose formal Evidence Card `source_id` equals
`paper_id`, or `unverified_or_unavailable` status. A
potentially decisive closest/concurrent prior that is not decision-grade makes
`NOVEL` invalid: return `UNCERTAIN` and use the existing targeted literature
route. These are Type-A completeness and evidence-binding checks; the
reviewer's scientific assessment remains Type-B.

For a quality `HOLD` or novelty `UNCERTAIN`, the phase record must include
`return_guidance` with `missing_evidence`, `decision_target`, and
`required_check`. A novelty phase is `BLOCKED` only when every candidate audit
is `BLOCKED`; otherwise its complete consumable audits reach the Human Gate. If
any candidate is `UNCERTAIN`, the phase verdict is `UNCERTAIN` and its guidance
aggregates the outstanding checks for those candidates. A novelty `BLOCKED`
result returns automatically. Each `NOT_NOVEL` candidate's
`novelty_assessment.revision_guidance` identifies its closest prior, key overlap,
residual delta, and recommended reframing or re-check; each `UNCERTAIN`
candidate's guidance identifies missing evidence, required checks, and search
targets. At the Human problem Gate, `approve` accepts the selected candidate;
`request_revision` and `reject` each require its `selected_id` and non-empty
human feedback in the one-time receipt and `return_history`. A
`request_revision` return records only the selected candidate's novelty audit,
reviewer guidance, and preserved Candidate registry baseline: its original
artifact path, hash, and archive path. Reopened problem generation reads that
record, keeps the same `problem_id`, and makes
only the directed correction and directly affected content changes. A `reject`
return records the human reason for a new analysis of the active Field Map and
Evidence; it may form a different Candidate without inheriting the rejected
Candidate's structure or ID. Both paths invalidate the old Candidate through
Human Gate outputs and repeat Quality, Novelty, and Human Acceptance. Use the
configured incremental-literature route only for a real evidence gap. This is
not a reusable Lesson unless it separately satisfies the Lesson contract.

P3 certifies problem quality; it does not by itself establish novelty. The
accepted artifact is a **Certified Problem Contract**, not a method idea. Create
it only after a separate problem-novelty check and the configured independent
or human acceptance boundary. Until then, record the P3 result as provisional.

Always record these fields separately:

```yaml
problem_verdict: CERTIFIED | HOLD | REJECT | BLOCKED
problem_novelty_verdict:
acceptance_status: provisional | accepted
verdict_id:
acceptance_authority: same_family_reviewer | cross_family_reviewer | human
```

`CERTIFIED/provisional` may support further analysis but cannot authorize a
Principle/Test Human Gate, test execution, Principle convergence, or a
`METHOD_READY` final Method. In the default
half-autonomous workflow, an independent review remains advisory and explicit
human confirmation is the sufficient and final acceptance authority. A
cross-family reviewer may accept only when the user explicitly enabled an
autonomous acceptance mode.

## Diagnosis handoff

The accepted artifact from this contract is the Certified Problem Contract.
Pass it unchanged with its evidence capsule to
`problem-necessity-contract.md`. Only an independently accepted
`RESIDUAL_SAME_PROBLEM` Necessity Closure/Verdict may then pass the residual
Failure Envelope to `root-cause-analysis-contract.md`. Keep problem novelty separate from the later
root-cause verdict, Provisional Scientific Delta, Final Scientific Delta Claim,
final Method novelty, and any Established Scientific Delta recorded only after
`VALIDATED`.

## Failure paths

| Code | Trigger | Required response |
|---|---|---|
| `FRAME_INCOMPLETE` | P0 required field missing | infer visibly or request the missing constraint |
| `LANDSCAPE_INSUFFICIENT` | core family or source class uncovered | run targeted retrieval; do not generate final problems |
| `EVIDENCE_CONFLICT` | credible sources disagree materially | preserve both positions and mine a contradiction candidate |
| `GAP_UNVERIFIED` | “not studied” rests on search absence | mark `HOLD`; broaden aliases/citations/databases |
| `MIGRATION_ANALOGY_WEAK` | no causal/structural correspondence | reject the migration lead |
| `NO_CERTIFIED_PROBLEM` | all candidates fail P3 | return to P1/P2; do not force a method |
| `PROBLEM_NOT_ANSWERABLE` | valuable but no feasible probe | keep as `HOLD`, state enabling conditions |

## Output and trace discipline

- Fold human-facing P0-P3 content into the orchestrator's one canonical report.
- Use the focused research contract for the selected problem; do not create
  parallel `GAP_REPORT` or `PROBLEM_REPORT` files.
- Keep search records, reviewer verdicts, and raw traces in their designated
  audit locations.
- Required-field presence is Type-A. Problem quality and problem novelty are
  Type-B and require the configured independent reviewer route.
