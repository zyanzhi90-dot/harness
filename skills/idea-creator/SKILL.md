---
name: idea-creator
description: "Run one independent problem-discovery, root-cause diagnosis, or method-design module. Use mode: problem to certify an evidence-grounded problem; mode: diagnosis to execute 1a-2b and obtain an independent root-cause verdict; mode: method only after DIAGNOSIS_READY."
argument-hint: "mode: problem|diagnosis|method; direction or handoff path"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, Skill, mcp__codex__codex, mcp__codex__codex-reply
---

# Research Idea Creator — three independent modes

Run exactly one mode for: **$ARGUMENTS**.

This skill is intentionally split at artifact boundaries. Fresh invocations in
`mode: diagnosis` and `mode: method` must not inherit the previous module's
reasoning history. Diagnosis reads the accepted problem handoff; method reads
the validated diagnosis handoff. The parent orchestrator may call the modes
sequentially, but it must not skip either boundary.

## Shared execution contract

Read only the references needed for the active mode:

- [`problem-discovery-contract.md`](../shared-references/problem-discovery-contract.md)
- [`root-cause-analysis-contract.md`](../shared-references/root-cause-analysis-contract.md)
- [`method-design-contract.md`](../shared-references/method-design-contract.md)
- [`source-admission-policy.md`](../shared-references/source-admission-policy.md)
- [`reviewer-independence.md`](../shared-references/reviewer-independence.md)
- [`idea-fanout-module.md`](../shared-references/idea-fanout-module.md) — read
  for problem-mode breadth generation only
- [`idea-wiki-integration.md`](../shared-references/idea-wiki-integration.md) —
  read when `research-wiki/` is present
- [`idea-output-composition.md`](../shared-references/idea-output-composition.md) —
  read when composing or exporting the final report

Use `idea-stage/` as the working directory. Keep the full literature registry
and raw search history out of the active prompt. Compile a compact packet with
stable evidence IDs, claim/boundary/failure fields, and unresolved questions.
Do not paste the complete `IDEA_REPORT.md` into downstream contexts.

When `LESSONS_LEARNED.md` exists, read only entries relevant to the active
problem, diagnosis, or method as anti-repetition checks. A lesson is neither
formal evidence nor a handoff and cannot authorize a transition. Never read
`.aris/archive/` as an active input: a Controller `return-phase` has moved
invalidated outputs there precisely because their former conclusion no longer
authorizes downstream work.

Every output must distinguish `evidence`, `inference`, `hypothesis`, and
`decision`. Never treat a model score as acceptance. Formal verdicts require a
verdict ID, reviewer identity/family, evidence anchors, and one status allowed
by the active contract: problem certification uses
`CERTIFIED/HOLD/REJECT/BLOCKED`; diagnosis uses
`DIAGNOSIS_READY/REVISE_DIAGNOSIS/REOPEN_PROBLEM`. Human acceptance remains separate from
machine or model review.

### Context budget (starting defaults)

Compile each active packet to at most 24,000 characters, with at most 12
evidence cards and 8 unresolved issue IDs. Keep review bundles below 32,000
characters; pass paths and stable IDs for larger artifacts. These are benchmark
starting points, not scientific limits: measure task success, retrieval
coverage, latency, and token cost before changing them. If a decision needs
more evidence, retrieve the specific card by ID rather than appending the full
registry or history.

For Codex-compatible path-only review transport, write the problem generator
bundle to `idea-stage/codex_brainstorm_bundle.md` and prompt
`Read the idea-generation bundle at <absolute path>`. Write the independent
jury packet to `idea-stage/codex_triage_bundle.md`; never paste the full bundle
into the reviewer context.

## Mode dispatch

Parse the first explicit `mode:` value. If absent, default to `problem` and
state that default in the output. Unknown modes are an error. The modes have
different inputs, outputs, and stopping conditions:

| Mode | Reads | Writes | Must stop at |
|---|---|---|---|
| `problem` | Field Evidence Map and source records | `PROBLEM_CANDIDATES.*`, `PROBLEM_QUALITY_VERDICTS.jsonl`, `PROBLEM_NOVELTY_VERDICTS.jsonl`, then the separate `RESEARCH_CONTRACT.md` and `PROBLEM_EVIDENCE_CAPSULE.md` after user selection and before the Controller records human acceptance | human problem selection |
| `diagnosis` | accepted `RESEARCH_CONTRACT.md` and `PROBLEM_EVIDENCE_CAPSULE.md` | `ROOT_CAUSE_ANALYSIS.json`, faithful `.md` view, independent `ROOT_CAUSE_VERDICT.json` | `DIAGNOSIS_READY` or return path |
| `method` | accepted problem plus validated root-cause analysis/verdict | `METHOD_ROUTES.*`, `SELECTED_ROUTE.yaml` only after selection | human route selection |

`IDEA_REPORT.md` is a final human-facing report only. It is never the machine
handoff between these modes.

---

## Mode: `problem` — discovery and certification

### P0. Validate the landscape

Require a `SUFFICIENT` or bounded `PARTIAL` Field Evidence Map from
`/research-lit`. The active map must cover field purpose, tasks, bottlenecks,
method families, assumptions, effective and failure conditions, contradictions,
evaluation blind spots, and negative evidence. If the map is `INSUFFICIENT`,
return a blocked handoff with the missing searches; do not generate ideas.

### P1. Discover and triage Leads in fresh lens contexts

Follow [`idea-fanout-module.md`](../shared-references/idea-fanout-module.md):
use isolated lens contexts and return structured Lead cognition only. Fan-out
is for discovery and triage, not ranking, certification, or materializing a
formal Candidate.

Use all three routes when they yield useful Leads, without treating them as
quotas:

1. community-open problems;
2. self-discovered failures, boundary conditions, and contradictions;
3. structurally justified problem migration.

Discover self-discovered Leads in two complementary ways: compare Field Map
families horizontally for shared assumptions, recurring failures, boundaries,
inconsistent results, and unresolved contradictions; and let a key paper's
discussion/conclusion, exposed bottleneck, or underdeveloped direction suggest
a Lead. In neither case does a paper limitation directly become a formal
Candidate: first compare it against the wider map and validate it by targeted
deep dive.

For each Lead, establish its starting observation, reason to track, largest
uncertainty, current basis, and possible disconfirming evidence. A promising
Lead alone may use the existing targeted literature gateway after
`problem_generation` has entered `running`. Each query has exactly one of
Reality, Importance, Unresolvedness, Precision, Falsifiability, or
Answerability as `decision_dimension`, with immutable non-empty Lead ID,
statement, purpose, close condition, and current Field Map hash. Generators do
not create formal Candidates, rank, certify, write Lead artifacts, or design
methods.

### P2. Evidence-led maturation

After each Evidence round, strengthen, narrow, reframe, reject, or mature the
Lead. Use the deep dive to seek disconfirmation, not merely support: check closest/strongest prior and residual unresolved delta, strongest
counterevidence, alternative explanations, true unresolvedness, and whether
simple application or tuning already resolves it. Judge Reality, Importance,
Unresolvedness, Precision, Falsifiability, and Answerability scientifically;
the Controller does not score these judgments.

Only when a Lead is mature, expand it into the existing Candidate schema,
resolve evidence IDs, and write:

- `idea-stage/PROBLEM_CANDIDATES.jsonl` — machine handoff, one candidate per line;
- `idea-stage/PROBLEM_CANDIDATES.md` — compact human-readable index.

Rejected Leads remain internal cognition: create no Candidate and continue
other Lead discovery/triage as needed. Do not send them to a validator, Gate,
or Human Acceptance.

### P3. Problem-quality gate

Use a fresh reviewer context and a path-only bundle. Assess Reality,
Importance, Unresolvedness, Precision, Falsifiability, and Answerability, plus
hard gates for evidence, scope, decisive test, feasibility, and calibrated
claim language. Record a `PASS`, `INSUFFICIENT_EVIDENCE`, or `FAIL` judgment
for each dimension. Reality, Importance, and Unresolvedness require formal
evidence anchors; Precision, Falsifiability, and Answerability may rely on the
bound candidate and Field Map without irrelevant literature anchors. Return one
verdict per candidate with issue IDs and applicable evidence anchors. This is a
provisional scientific gate, not human acceptance.

### P4. Problem novelty packet

Prepare the compact candidate/evidence packet for the orchestrator's unique
problem-novelty Gate. The parent workflow invokes
`/novelty-check "mode: problem | candidate IDs + compact evidence packet"` only
for quality-gate survivors. Keep problem novelty separate from method novelty;
record closest prior framing, search coverage, concurrent-work risk, and
`NOVEL / UNCERTAIN / NOT_NOVEL / BLOCKED` with a durable verdict ID in
`PROBLEM_NOVELTY_VERDICTS.jsonl`. This module must not invoke the same formal
Gate a second time.

When the Controller returns to `problem_generation`, read only its latest
`return_history` entry. For `request_revision`, use its selected Candidate
baseline, human feedback, novelty audit, and reviewer guidance; retain that
`problem_id` and make only the directed correction and directly affected
content changes. Use the Controller return record as the active input for its
feedback and reviewer guidance. For `reject`, use the human feedback as the re-analysis
reason, reassess the active Field Map and Evidence, and form a different
Candidate when warranted. Both paths repeat the existing Quality, Novelty, and
Human Gate sequence. Use the existing incremental-literature route only when a
real evidence gap is found; do not write an ordinary evidence gap into
`LESSONS_LEARNED.md`.

### P5. Human acceptance checkpoint

Present every Quality-certified candidate with a completed, consumable novelty
audit (`NOVEL`, `NOT_NOVEL`, or `UNCERTAIN`), including its evidence, weakest
assumption, novelty conclusion, and the cost of a decisive test. Do not use
novelty `survivor_ids` as the Human candidate set. Stop until the user selects
one problem or explicitly rejects/reframes it. After the user selects a problem
and before the Controller records human acceptance, create exactly these two
independent artifacts:

- `idea-stage/RESEARCH_CONTRACT.md` — the accepted Problem Contract;
- `idea-stage/PROBLEM_EVIDENCE_CAPSULE.md` — the sole formal compact evidence
  handoff for that Contract, using
  `templates/PROBLEM_EVIDENCE_CAPSULE_TEMPLATE.md`.

You must not embed a second capsule in the Contract or replace this artifact with a
report section. The Controller assigns and records the accepted problem version
with both artifact hashes. Do not create routes in this mode. A directed
correction uses the live `problem_acceptance` Human Gate with
`request_revision`, selected Candidate ID, and human feedback; a rejected
Candidate uses `reject` with its selected ID and rejection reason. The
Controller archives and invalidates the candidate-to-acceptance outputs before
returning only to `problem_generation`.

### Problem-mode forbidden actions

- Do not write a scientific method, method route, method novelty verdict, or
  method review.
- Do not turn a search gap into a novelty claim.
- Do not treat an LLM jury score as acceptance.
- Do not pass the full evidence registry or generator transcript downstream.

---

## Mode: `diagnosis` — independent 1a-2b root-cause analysis

Require a human-accepted `RESEARCH_CONTRACT.md` and its unchanged
`PROBLEM_EVIDENCE_CAPSULE.md`. Record both SHA-256 values, then follow
[`root-cause-analysis-contract.md`](../shared-references/root-cause-analysis-contract.md):

If this is a Method-triggered reopen, inspect the matching existing Controller
return record (`method_design` → `root_cause_analysis`) before analysis. Use
its scientific reason and any trigger Evidence IDs to reassess the diagnosis;
formally re-adopt a cited method-stage Evidence Card through
`readopt-evidence`, rather than copying or relabeling it.

1. 1a collects and describes phenomenon evidence that directly represents the
   accepted problem/failure, from existing experiments, literature, datasets,
   real-world scenarios, or a necessary diagnostic pilot; failed experiments
   are not a prerequisite;
2. 1b groups phenomena while allowing multiple material mechanisms;
3. 2a traces progressively deeper causes and competing explanations;
4. 2b constructs evidence-calibrated, falsifiable causal chains with explicit
   intervention targets.

Write `ROOT_CAUSE_ANALYSIS.json` as the canonical handoff and a faithful
`ROOT_CAUSE_ANALYSIS.md` view. Then a fresh independent reviewer writes
`ROOT_CAUSE_VERDICT.json`. Only `DIAGNOSIS_READY`, with matching analysis ID and
analysis/problem/evidence hashes, closes the Gate. `REVISE_DIAGNOSIS` returns
to `root_cause_analysis`; `REOPEN_PROBLEM` returns to
`problem_generation` so the problem is regenerated or revised and passes the
existing quality, novelty, and human-acceptance sequence again. The Agent
cannot choose another target. Do not
name, search, rank, or combine methods in diagnosis mode.

---

## Mode: `method` — initial route design after diagnosis acceptance

### M0. Preconditions

Require `idea-stage/RESEARCH_CONTRACT.md` with:

- `problem_status: CERTIFIED`;
- `acceptance_status: human_accepted`;
- selected problem ID and durable acceptance record;
- the Controller-recorded problem version and problem-contract hash;
- evidence IDs and scope boundaries.

Also require `ROOT_CAUSE_ANALYSIS.json` and `ROOT_CAUSE_VERDICT.json` with:

- verdict `DIAGNOSIS_READY`;
- matching run ID, analysis ID, problem-contract hash, evidence-capsule hash,
  and reviewed-analysis hash;
- non-empty `primary_causal_chain_ids`.

If any precondition is absent, return `BLOCKED_PRECONDITION` and do nothing.

### M1. Scientific closure before technique search

Using the accepted problem and validated primary causal chains, derive the
falsifiable scientific mainline, decisive falsifier, claim type, and design
obligations. Preserve each chain's competing explanations and discriminating
evidence; do not invent a replacement diagnosis to justify a preferred
technique. The method is a consequence of the problem contract, not a
free-standing list of fashionable components. If method reasoning reveals that
the accepted diagnosis itself needs re-analysis, first finish any active
method literature session, then invoke the Controller's unique
`reopen-root-cause` action with a specific reason and any triggering formal
method Evidence IDs. Do not silently rewrite the diagnosis or continue route
design after that request.

### M2. Necessary completion decision

Start the running `method_design` phase from the Controller-accepted
`ACTIVE_FIELD_MAP.md` and its Evidence Registry. First derive one canonical
Design Obligation set from the accepted primary chains and their intervention
targets. If current knowledge cannot support a credible dominant mechanism,
use `DOMINANT_SOLUTION_SEARCH` through the existing incremental gateway. Its
Query Plan is the formal pre-route binding: every query names current
obligation IDs and their derived chains, without requiring a dominant solution,
closure, or residual gap. Search same-field mechanisms first, then causally
isomorphic mechanisms, and cross-field mechanisms only when necessary.

After that evidence is sufficient to choose a dominant carrier, derive the
minimal dominant solution and its dominant-only closure. Only a specific
residual `MUST` obligation may use `RESIDUAL_MUST_GAP_SEARCH`; every query then
binds a non-empty decision target and declared residual `MUST` IDs. Do not
repeat mapped knowledge, use unregistered web evidence, or add support except
to close that recorded residual gap.

### M3. Route synthesis and preliminary risk

Produce at most three routes. Each route must specify dominant method,
backbone, innovation carrier, mechanism chain, integration, expected failure
mode, minimum validation logic, feasibility, and separate scientific-delta vs
technical-route novelty hypotheses. `/novelty-check "mode: method | preliminary
route"` may be used as a risk screen; it is not the final method novelty gate.

Write `METHOD_ROUTES.jsonl` and `METHOD_ROUTES.md`, each bound in Controller
state to the current problem ID/version/contract hash. The latter is a compact
decision packet, not the final proposal.

### M4. Human route selection

Present ranked routes with evidence, unresolved risks, and the cheapest
discriminating test. Stop for explicit selection or revision. On selection,
write `SELECTED_ROUTE.yaml` with route ID, problem ID/version, problem-contract
hash, selected dominant method, innovation carrier, unresolved risks, and user
decision. A requested revision uses the live `route_selection` Human Gate with
decision `request_revision`; the Controller returns only to `method_design`.
Do not call `/research-refine` until that file exists.

### Method-mode forbidden actions

- Do not revise the accepted problem silently. A material change must use
  explicit `arisctl revise-problem`, which creates a draft next version and
  restarts the existing problem quality, novelty, and human-acceptance sequence.
- Do not run the final method novelty gate before refinement.
- Do not plan or execute experiments; hand validation obligations downstream.
- Do not call `research-review` as a mandatory core stage. It remains an
  optional external challenge after the relevant artifact exists.

---

## Compatibility integrations

When `research-wiki/` exists, follow
[`idea-wiki-integration.md`](../shared-references/idea-wiki-integration.md).
This preserves the old **Load Research Wiki** and **Write Ideas to Research
Wiki** behavior without making Wiki state an acceptance gate. The module owns
helper resolution, threat scanning, deterministic `upsert_idea`, and warn-only
failure handling. Keep `review-tracing.md` records for generator and jury
calls, with generator and jury identities separated.

The module's deterministic write remains an actual helper invocation:

```text
python3 "$WIKI_SCRIPT" upsert_idea research-wiki/ --slug <stable-id> \
  --title <title> --stage proposed --outcome pending --thesis <problem-thesis>
```

The old single-report interface is retained for compatibility: after the human
accepts a route, the orchestrator may compose `IDEA_REPORT.md` from the compact
handoff artifacts. It must not use that report as a prompt-sized state store.
Follow [`idea-output-composition.md`](../shared-references/idea-output-composition.md)
for explicit standalone/composed mode, versioning, compact output, and render
timing.

## Optional downstream skills

```text
/research-lit -> /idea-creator "mode: problem" -> /novelty-check "mode: problem"
                 -> human acceptance
                 -> /idea-creator "mode: diagnosis" -> root-cause Gate
                 -> /idea-creator "mode: method" -> human route selection
                 -> /research-refine -> /novelty-check "mode: method-final"
```

`/research-review` is optional and may challenge a specific problem or route;
it is not a duplicate acceptance gate in the default pipeline.

## Compatibility fields retained in the handoff

The final human-facing **Problem-First Ranked Idea Report** contains
**Certified Problems and Derived Routes**. Its route entries retain the fields
**Design obligations**, **Scientific mainline**, **dominant-only closure and
residual MUST gaps**, **necessary supporting-mechanism ledger**,
**Scientific-delta novelty**, and **minimal sufficient dominant solution**. Problem juries and generators run in fresh contexts; **do
not reuse** a generator context for the jury. A problem is
`CERTIFIED/provisional` until explicit human confirmation creates
`CERTIFIED/accepted`. The route may then be handed to `/experiment-plan` only
as an optional downstream action.

Transfer/combination may appear only as the necessary support for a recorded
residual MUST gap; assess the Field Map and same-field options before any
cross-field search. It is neither an innovation verdict nor a default route.
