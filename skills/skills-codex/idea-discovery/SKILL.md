---
name: idea-discovery
description: "Orchestrate the problem-first research workflow from a bounded field map through accepted RCA, Principle formation/testing/convergence, Method adaptation, and final method decision. Each scientific module runs independently with explicit handoff artifacts."
argument-hint: "[research-direction]"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, Skill, mcp__codex__codex, mcp__codex__codex-reply
---

# Idea Discovery — thin orchestrator

Orchestrate: **$ARGUMENTS**.

This skill coordinates modules; it does not duplicate their scientific
reasoning. The executable workflow is declared in
[`../shared-references/idea-workflow.yaml`](../shared-references/idea-workflow.yaml)
and formal state transitions are owned by `arisctl.controller.ARISController`.
The default run is:

```text
research-lit
  -> human scope approval
  -> idea-creator(mode: problem)
  -> problem-quality gate
  -> novelty-check(mode: problem)
  -> human problem acceptance
  -> idea-creator(mode: diagnosis)
  -> independent root-cause gate
  -> idea-creator(mode: method)
  -> independent Principle packet review
  -> human Candidate selection
  -> idea-creator(mode: principle-test-design)
  -> independent Principle test-plan review
  -> human approval of the atomic test execution set
  -> method-test
  -> idea-creator(mode: method) Principle Evidence Update
  -> independent Principle convergence review
  -> research-refine from the Controller-materialized Selected Principle
  -> novelty-check(mode: method-final)
  -> human final method acceptance
  -> METHOD_CONFIRMED_AWAITING_USER_VALIDATION
```

The problem and method modules use fresh contexts. The only machine handoff is
the compact artifact named in the workflow; `IDEA_REPORT.md` is a final human
report and must not be used as a context dump.

After problem acceptance, the Controller locks one problem version by its ID
and registered hashes. Method artifacts are separate and only bind to that
version. If later evidence changes the problem, the user must explicitly run
`arisctl revise-problem --reason "..."`; the Controller creates a draft next
version and repeats the existing problem quality, novelty, and human-acceptance
sequence before method work may resume.

## Non-negotiable boundaries

- No diagnosis before `RESEARCH_CONTRACT.md` has
  `acceptance_status: human_accepted`.
- No method design before `ROOT_CAUSE_VERDICT.json` is validated as
  `DIAGNOSIS_READY` against the current problem, evidence, and analysis hashes.
- No Principle test design before Human selection of one reviewed Candidate.
- No approved test execution before the Principle Test Human Gate, and no
  Principle interpretation inside `/method-test`.
- No Method adaptation or final implementation commitment before accepted
  Principle convergence and Controller materialization of
  `SELECTED_PRINCIPLE.yaml`.
- No final method novelty verdict before `refine-logs/FINAL_PROPOSAL.md`.
- Final method acceptance does not start validation. It creates a blocked
  validation entry that only the user may initiate after understanding and
  confirming the method.
- `research-review` is optional external challenge, not a mandatory duplicate
  gate. If used, its output is advisory unless the workflow explicitly assigns
  it a unique gate owner.
- A model score, same-family review, or silence never becomes human acceptance.
- Full registries, transcripts, and old reports remain audit history; active
  contexts receive only compiled evidence cards and unresolved issue IDs.

Use the workflow's starting context budget: active packet ≤24,000 characters,
review bundle ≤32,000 characters, at most 12 evidence cards and 8 unresolved
issue IDs. Tune these values with task-success/latency/token-cost measurements;
do not compensate for a poor packet by pasting the full registry.

Optional compatibility flags are explicit and default off unless stated:
`REF_PAPER = false`, `COMPACT = false`, `RENDER_HTML = true`, and
`ARXIV_DOWNLOAD = false`. The reference-paper, fan-out, Wiki, and output rules
are delegated to independent modules; this file only controls when they run.

Compatibility defaults remain explicit: `AUTO_EXPERIMENT_PLAN = false` and
`AUTO_COMMIT = false`. At every human checkpoint, **If no response, stop here**
and preserve the artifacts; silence is not consent.
Main may prepare the checkpoint's declared handoff artifact after the user has
stated a selection, but only the Controller's UI-confirmed `human-approve`
action may record acceptance or advance the phase.

## Phase 0 — Load Research Brief

Before invoking a module, check for `RESEARCH_BRIEF.md` in the project root or
the path supplied by the user. Load only its problem context, constraints,
prior attempts, non-goals, and existing results into the active scope packet.
If it is long, keep the source file on disk and compile a short
`idea-stage/ACTIVE_SCOPE.md`. A one-line argument sets direction; the brief
takes priority for details.

If the user supplies `REF_PAPER`, invoke
[`reference-paper-intake.md`](../shared-references/reference-paper-intake.md)
before the field map. Write `idea-stage/REF_PAPER_SUMMARY.md`, present its
bounded influence at the scope checkpoint, and pass only its path and selected
evidence IDs downstream. A reference paper informs the map; it cannot bypass
problem discovery or create a method before human problem acceptance.

## Phase 1 — Field Evidence Map

Invoke `/research-lit` as an independent run. It must produce the active field
map, evidence registry, literature corpus, source-admission policy, and search
log required by the workflow. Require
field-purpose/task/bottleneck structure, method families and mechanisms,
assumptions, effective/failure conditions, contradictions, evaluation blind
spots, negative evidence, and a coverage status. `INSUFFICIENT` blocks problem
generation; `PARTIAL` permits exploratory candidates only and is carried into
every verdict. It cannot authorize a Certified Problem Contract or human
problem acceptance; that checkpoint requires `SUFFICIENT`.

The literature module may use the shared fan-out protocol for independent
extraction shards. It must return a mechanically consolidated map before any
problem Gate; do not fan out overlapping verdicts. When
`REF_PAPER_SUMMARY.md` exists, pass its path rather than the source PDF or a
full paper transcript.

Apply `source-admission-policy.md` before scientific reading. For a proactively
retrieved reference, admit it only after the default hard high-citation-or-
approved-elite-venue gate and relevance checks, or the narrow Controller-
recorded exception for decisive closest/concurrent, negative/contradictory, or
diagnostic/replication evidence tied to an explicit decision target. User
material is `USER_SUPPLIED_READ` and is never discarded before content
inspection. The active map retains compact causal development traces for major method
families, not just a flat list of papers.

For a proactively retrieved reference, the admission decision precedes any
abstract or full-text reading.

After the existing Coverage Review has passed and the Controller reports
`WAITING_FOR_HUMAN` for `scope_human_approval`, but before presenting that
checkpoint, best-effort derive or overwrite the sibling
`idea-stage/ACTIVE_FIELD_MAP_AUDIT.md`. This is a **derived Human Audit View**,
not a research artifact: use only the current `ACTIVE_FIELD_MAP.md`, canonical
structured Evidence first, `EVIDENCE_REGISTRY.jsonl`, `LITERATURE_CORPUS.jsonl`, Map
`evidence_ids` / `source_ids`, and existing claim, locator, provenance,
method, assumption, boundary, failure, and contradiction information. For
each reviewable map item, show only reliably traceable source papers,
source/canonical Evidence, what the Evidence actually supports, existing
locators, and existing limits or contrary evidence; say when the current
information cannot determine a link. Select supporting literature/Evidence as
a **minimal sufficient** set: retain the Map's `evidence_ids` / `source_ids`
and check existing canonical Evidence for independently explanatory sources.
Do not omit an Evidence merely for brevity when it has an independent
foundational, pivotal-transition, branch, current-representative, or key
boundary/failure role. Compress only information that is substantively
redundant in mechanism, evolutionary role, and explanatory value. For each
Development Trace, the displayed support must cover every key evolution node
the Trace claims; do not retain only recent representative work while omitting
existing canonical Evidence for a material origin or transition.
Do not conduct new research or a paper
reading lifecycle, create Evidence/read events/attestations, alter the Field
Map, invent links, or add cognition. Never register this view in a manifest,
State, accepted artifacts, landscape handoff, Gate binding, required input, or
downstream context; it has no Controller/Validator, provenance, recovery,
branch, checkpoint, or lifecycle role. If derivation fails, tell the user that the auxiliary Audit
View was unavailable and continue the unchanged scope checkpoint. On every
`request_revision` return to this checkpoint, regenerate and overwrite this
same file from the then-current Map and existing evidence; do not retain an
older view.

Present a compact scope checkpoint to the user. Persist the decision with the
Controller's `human-approve` action; do not infer approval from a later message
or from a completed search. The accepted scope artifact IDs, hashes, provenance,
and approval receipt become the registered input hook for problem generation.
State that the formal review object remains `ACTIVE_FIELD_MAP.md`; the user may
also consult sibling `ACTIVE_FIELD_MAP_AUDIT.md` for its supporting papers and
Evidence, but it is auxiliary only and requires no approval.

## Phase 2 — Problem module and gates

Invoke the independent problem module:

```text
/idea-creator "mode: problem | direction: $ARGUMENTS | map: idea-stage/ACTIVE_FIELD_MAP.md"
```

It first discovers and triages internal Leads from horizontal Field Map
comparison and key-paper inspiration, then runs a targeted deep dive before
materializing any mature Lead as an existing Problem Candidate. A paper
limitation, discussion/conclusion remark, or future-work sentence is only a
Lead input: it must be checked against the wider field for reality, importance,
closest prior, counterevidence, alternative explanations, engineering-only
resolution, and a residual unresolved gap. The deep dive may strengthen,
narrow, reframe, reject, or mature the Lead. Only mature Candidates run the
existing problem-quality gate and prepare the novelty packet. Then invoke:

```text
/novelty-check "mode: problem | candidates: idea-stage/PROBLEM_QUALITY_VERDICTS.jsonl"
```

The novelty check is a separate gate with a separate owner. Present every
Quality-certified candidate with a completed consumable novelty audit (`NOVEL`,
`NOT_NOVEL`, or `UNCERTAIN`) and its evidence to the user; do not use novelty
`survivor_ids` as the Human consideration set. After the user selects a problem and
before the Controller records human acceptance, create the separate
`idea-stage/RESEARCH_CONTRACT.md` and `idea-stage/PROBLEM_EVIDENCE_CAPSULE.md`,
then record `human_accepted` only through the Controller. The Contract must not embed a second capsule; the
independent capsule is the formal evidence handoff. If all candidates are
rejected, revise the scope/search packet;
never jump directly to method design.

## Phase 3 — Root-cause analysis and Gate

Start a fresh module execution with the accepted problem handoff:

```text
/idea-creator "mode: diagnosis | contract: idea-stage/RESEARCH_CONTRACT.md | evidence: idea-stage/PROBLEM_EVIDENCE_CAPSULE.md"
```

The module executes 1a direct phenomenon-evidence collection and description,
1b phenomenon grouping, 2a causal-depth tracing, and 2b causal-chain
construction. 1a may use existing experiments, literature, datasets,
real-world scenarios, or a necessary diagnostic pilot; failed experiments are
not mandatory. Require canonical
`ROOT_CAUSE_ANALYSIS.json`, its faithful Markdown view, and a fresh independent
`ROOT_CAUSE_VERDICT.json`. The state helper validates their schema, IDs,
provenance, and SHA-256 bindings. The Controller applies the unique mapping:
`DIAGNOSIS_READY -> method_design`,
`REVISE_DIAGNOSIS -> root_cause_analysis`, and
`REOPEN_PROBLEM -> problem_generation`. The latter repeats the existing problem
generation, quality, novelty, and human-acceptance sequence. The Controller
executes non-accepting paths via `return-phase`; the Agent cannot select a
different target.

## Phase 4 — Principle formation, selection, test design, and convergence

Start a new module execution with the accepted contract:

```text
/idea-creator "mode: method | contract: idea-stage/RESEARCH_CONTRACT.md | evidence: idea-stage/PROBLEM_EVIDENCE_CAPSULE.md | diagnosis: idea-stage/ROOT_CAUSE_ANALYSIS.json | verdict: idea-stage/ROOT_CAUSE_VERDICT.json"
```

The module derives Required Mechanism Changes, Required Capabilities, and Design
Obligations from every accepted primary causal chain. It then executes all four
Principle Search dimensions, forms algorithm-independent Candidate Principles,
declares whether the solution space is constrained or underconstrained, and
states each Candidate's mechanism, fatal assumptions, Provisional Scientific
Delta, principal risks, substantive differences, and Candidate/Rival killer-test
concept in plain language. Method Design does not produce concrete tests, an
execution set, or cost. It consumes the latest directed Human/reviewer feedback and reuses current
Evidence/search/history; it acquires new Evidence only for a real knowledge gap.

Require `METHOD_DESIGN_PACKET.json`, its deterministic `METHOD_DESIGN.md` view,
and the formal `METHOD_DESIGN_REVIEW.json`. All legal Evidence acquisition or
re-adoption must finish before `refresh-review-request` binds the final packet
for independent review. `PRINCIPLE_PACKET_READY` advances to the Human
Candidate-selection Gate; `REVISE_PRINCIPLES` returns to this phase;
`RCA_CONFLICT` returns linked Evidence and guidance to RCA.

At `principle_human_selection`, the Human may select one Candidate, request a
Candidate revision, request a combination, or reject all Candidates with
redesign feedback. A selection creates only an active `selected_for_testing`
binding; it does not create a test cycle, establish scientific support, or
materialize `SELECTED_PRINCIPLE.yaml`. Every non-accepting decision returns to
Method Design, where the feedback must be consumed before fresh independent
review and another human Candidate selection.

After selection, invoke `idea-creator(mode: principle-test-design)`. It designs
only the current minimum sufficient, highest-information tests for the selected
Candidate by concretizing its reviewed killer-test concept and preserving the
Candidate/Rival Pattern A/B, prioritizing falsification of fatal assumptions. Existing data,
analysis, or computation must be preferred whenever sufficient; a large
physical experiment requires an explicit insufficiency justification. Require
`PRINCIPLE_TEST_PLAN.json`, its deterministic Markdown view, and an independent
Principle test-plan review from `independent_method_reviewer` under the test-plan
rubric. `TEST_PLAN_READY` advances to `principle_test_human_approval`;
`REVISE_TEST_PLAN` returns to Test Design; `RCA_CONFLICT` returns to RCA.

At `principle_test_human_approval`, present only the reviewed atomic execution
set and total cost for this round. A test or cost change uses
`request_revision -> principle_test_design`. No test may execute or submit a
result before this approval.

After approval, while `principle_evaluation` is pending, invoke `/method-test`.
It reads `method-test-handoff`, runs only approved tests through existing
execution capabilities or creates a physical-human handoff, and submits each
terminal `RESULT_AVAILABLE` or `NO_RESULT` record. It performs no scientific
interpretation. The Controller forms `PRINCIPLE_EVIDENCE_CONTEXT.json` only
after every approved test is terminal.

Then invoke `idea-creator(mode: method)` again for `principle_evaluation`. Main
must compare observations with Candidate/Rival Pattern A/B, assess per-test
operationalization fidelity/test validity/activation/rival discrimination, and
write Evidence-bound `scientific_updates` whose consequences are proposals, not
transition authority. Refresh the review request against the final
`PRINCIPLE_EVALUATION.json`. `PRINCIPLE_CONVERGED` names one Principle
ID/version and causes the Controller to materialize `SELECTED_PRINCIPLE.yaml`;
`REVISE_EVALUATION` preserves the same cycle/results, `MORE_EVIDENCE` preserves
the selected binding and returns to Test Design for the next minimum test,
`CANDIDATE_REJECTED` invalidates the binding and returns the failed Evidence to
Method Design, `RCA_CONFLICT` returns to RCA, `NECESSITY_CONFLICT` returns to
Problem Necessity, and `PROBLEM_CONFLICT` returns through the full Problem Gate
chain. Only the attested reviewer verdict drives that transition.

## Phase 5 — Refinement and final gates

Invoke `/research-refine` only with the accepted problem/RCA handoff and active
Controller-materialized `SELECTED_PRINCIPLE.yaml`. It performs target-domain
adaptation, a minimal faithful realization, Principle-only closure, and only
then minimal composition for demonstrated residual mechanism/adaptation gaps.
It owns iterative refinement; the Controller-issued
`independent_method_reviewer` performs the one fresh final independent Gate in
a new context. Its score is a progress signal, never a readiness rule. Require:

- `refine-logs/FINAL_PROPOSAL.md`;
- `refine-logs/FINAL_BLIND_REVIEW.md`;
- `refine-logs/REFINE_STATE.json`;
- separate reviewer provenance and unresolved-issue ledger.

Then invoke the final method novelty gate against the final proposal:

```text
/novelty-check "mode: method-final | proposal: refine-logs/FINAL_PROPOSAL.md"
```

Only after this gate present the final human decision. Compose
`idea-stage/IDEA_REPORT.md` from the compact accepted artifacts, Principle
convergence, Selected Principle, final proposal, and verdicts by following
[`idea-output-composition.md`](../shared-references/idea-output-composition.md).
Set the explicit signal `--composed: idea-stage/IDEA_REPORT.md` for this final
composition step; all earlier module runs remain standalone stage handoffs.
The report is a readable record, not a hidden state database. If `COMPACT` is
enabled, emit the short `idea-stage/IDEA_CANDIDATES.md` index only after the
human problem decision or accepted Principle convergence. If the user requests an HTML view, invoke
`/render-html` only after the report is complete; rendering is presentation,
not a scientific gate.

## State and recovery

Start one Controller-managed run from the checked-in workflow spec, for example:

```text
python -m arisctl --root . start idea-v4-001 --executor codex-gpt-5.6-sol
```

Use `start-phase -> complete-phase` for execution and `accept-phase` only for
deterministic or independent reviewer verdicts. Use `human-approve` for human
checkpoints. The Controller verifies dependencies and registered input hashes,
then registers each output path, SHA-256, provenance, and upstream snapshot.
`done` without reviewer acceptance remains visible and cannot advance a formal
Gate. After `method_acceptance`, the run stops at
`METHOD_CONFIRMED_AWAITING_USER_VALIDATION`; there is deliberately no automatic
validation transition or agent action.

## Optional challenge

`/research-review "stage: problem|method | artifact path"` may be invoked as an
independent challenge when a risk warrants it. Do not add it automatically to
both problem and method stages, and do not let the same reviewer thread act as
both generator and final acceptance authority.

## Final report skeleton

```markdown
# Idea Discovery Report
**Direction**: ...
**Scope status**: SUFFICIENT / PARTIAL / INSUFFICIENT
**Accepted problem**: link to `RESEARCH_CONTRACT.md`
**Principle packet and test cycle**: links to `METHOD_DESIGN_PACKET.json` and `PRINCIPLE_EVALUATION.json`
**Selected Principle**: link to `SELECTED_PRINCIPLE.yaml`
**Refined proposal**: link to `refine-logs/FINAL_PROPOSAL.md`
**Problem novelty**: verdict ID + uncertainty
**Final method novelty**: verdict ID + uncertainty
**Final independent method Gate**: verdict ID + unresolved issues
**Human decision**: accepted / revise / blocked
```

Follow the shared output composition, versioning, language, and review-tracing
protocols. Keep one canonical human report and stable machine handoffs.
