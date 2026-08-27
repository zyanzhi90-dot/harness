---
name: idea-discovery
description: "Codex-compatible thin orchestrator for independent problem discovery, method design, refinement, and human decisions."
argument-hint: "[research-direction]"
---

# Idea Discovery — Codex adapter

Orchestrate **$ARGUMENTS** using the checked-in
`../shared-references/idea-workflow.yaml`. Keep every module in a fresh
context and pass only compact, versioned handoff artifacts:

```text
/research-lit -> human scope approval -> /idea-creator "mode: problem"
-> problem quality -> /novelty-check "mode: problem" -> human problem acceptance
-> /idea-creator "mode: diagnosis" -> independent root-cause Gate
-> /idea-creator "mode: method" -> human route selection
-> /research-refine -> /novelty-check "mode: method-final"
-> human final method acceptance -> METHOD_CONFIRMED_AWAITING_USER_VALIDATION
```

Read the independent adapters when relevant:
`reference-paper-intake.md` for explicit `REF_PAPER`,
`idea-fanout-module.md` for breadth generation, and
`idea-output-composition.md` for explicit standalone/composed output. Do not
inline their full protocols in this orchestrator.

## Constants and boundaries

`AUTO_COMMIT = false`; `AUTO_EXPERIMENT_PLAN = false`; `REF_PAPER = false`;
`COMPACT = false`; `RENDER_HTML = true`; `ARXIV_DOWNLOAD = false`.
If no response, stop here at a human checkpoint and preserve artifacts. Do not
infer acceptance from silence, a score, or a same-family review. No diagnosis
module may run until `RESEARCH_CONTRACT.md` records `CERTIFIED/accepted` and
`human_accepted`. No method module may run until `ROOT_CAUSE_VERDICT.json` is
validated as `DIAGNOSIS_READY` against the current problem/evidence/analysis
hashes. No final method novelty gate may run
until `FINAL_PROPOSAL.md` exists.
Final method acceptance does not start validation; only the user may initiate
validation after understanding and confirming the method.
Main may prepare a checkpoint's declared handoff artifact, but cannot approve
the checkpoint or advance it without the Controller's UI-confirmed Human Gate.

## Phase 0: Load Research Brief

Read `RESEARCH_BRIEF.md` when present; compile only constraints, non-goals,
prior attempts, and existing results into the active scope packet.

When `REF_PAPER` is explicit, run `reference-paper-intake.md` before the field
map and present its bounded summary at scope approval. Pass only
`REF_PAPER_SUMMARY.md` and selected evidence IDs downstream.

## Phase 1: Field Evidence Map

Run `/research-lit` independently. Require field purpose, tasks, bottlenecks,
method families and mechanisms, assumptions, effective/failure conditions,
contradictions, negative evidence, coverage status, evidence registry,
literature corpus, source-admission policy, and search log. Retain compact
compact causal development traces for each major family. Apply
`source-admission-policy.md` before reading. For a proactively retrieved
reference, admit it only after the default hard high-citation-or-approved-
elite-venue gate and relevance checks, or the narrow Controller-recorded
exception for decisive closest/concurrent, negative/contradictory, or
diagnostic/replication evidence tied to an explicit decision target; user material is
`USER_SUPPLIED_READ` and is never discarded before content inspection.
`INSUFFICIENT` blocks final problem generation; `PARTIAL` permits exploratory
candidates only and cannot authorize problem certification or human problem
acceptance. That checkpoint requires `SUFFICIENT`.

For a proactively retrieved reference, the admission decision precedes any
abstract or full-text reading. Research-lit may use isolated extraction
fan-out, but it must consolidate the map before any problem Gate. Do not fan
out overlapping verdicts.

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

Present the existing compact scope checkpoint. State that the formal review
object remains `ACTIVE_FIELD_MAP.md`; the user may also consult sibling
`ACTIVE_FIELD_MAP_AUDIT.md` for its supporting papers and Evidence, but it is
auxiliary only and requires no approval. Persist the decision only through the
Controller's UI-confirmed `human-approve` action.

## Phase 2: Problem module and gates

Run `/idea-creator "mode: problem | map: idea-stage/ACTIVE_FIELD_MAP.md"`.
It first discovers and triages internal Leads from horizontal Field Map
comparison and key-paper inspiration. A limitation or future-work sentence is
only a Lead, never a direct Candidate. Use targeted deep dive to seek
counterevidence and check reality, importance, closest prior, alternatives,
engineering-only resolution, and the residual unresolved gap; then strengthen,
narrow, reframe, reject, or mature it. Only mature Leads become existing
Candidates, after which a fresh problem jury assesses the six dimensions. Run
`/novelty-check "mode: problem | ..."` as a separate owner. Record model
verdicts as `CERTIFIED/provisional`; stop for explicit human confirmation and,
after selection but before the Controller records human acceptance, write the
separate `RESEARCH_CONTRACT.md` and `PROBLEM_EVIDENCE_CAPSULE.md`. The Contract must not embed a second capsule;
the independent capsule is the sole formal compact evidence handoff.

## Phase 3: Root-cause analysis and Gate

Run `/idea-creator "mode: diagnosis | contract: idea-stage/RESEARCH_CONTRACT.md
| evidence: idea-stage/PROBLEM_EVIDENCE_CAPSULE.md"` in a fresh context.
Execute 1a direct phenomenon-evidence collection/description, 1b grouping, 2a
causal-depth tracing, and 2b causal chains under
`root-cause-analysis-contract.md`. Existing experiments, literature, datasets,
real-world scenarios, or a necessary diagnostic pilot may support 1a; failed
experiments are not required. Require
`ROOT_CAUSE_ANALYSIS.{json,md}` and an independent
`ROOT_CAUSE_VERDICT.json`. Apply only the fixed verdict mapping:
`DIAGNOSIS_READY -> method_design`,
`REVISE_DIAGNOSIS -> root_cause_analysis`, and
`REOPEN_PROBLEM -> problem_generation`, which repeats problem quality review,
novelty review, and human acceptance before diagnosis can resume.

## Phase 4: Method module and route selection

Run `/idea-creator "mode: method | contract: idea-stage/RESEARCH_CONTRACT.md |
diagnosis: idea-stage/ROOT_CAUSE_ANALYSIS.json | verdict:
idea-stage/ROOT_CAUSE_VERDICT.json"`
 in a fresh context. It derives the Scientific mainline, Design obligations,
 minimal sufficient dominant method, dominant-only closure, and a
 residual-MUST-gap-driven supporting-mechanism ledger. It checks the Field Map
 and same-field mechanisms before any cross-field structural search. Stop for
 human route selection into `SELECTED_ROUTE.yaml`; combination is not itself
 novelty.

## Phase 5: Refinement and final decision

Run `/research-refine` with the accepted contract and selected route. Its
Controller-issued `independent_method_reviewer` is the sole fresh final
independent Gate; require `FINAL_PROPOSAL.md`, `FINAL_BLIND_REVIEW.md`, and
separate reviewer provenance.
Then run final `/novelty-check` against the final proposal and present the
human decision. Compose `IDEA_REPORT.md` only after that decision using
`idea-output-composition.md`; optional `COMPACT` output is a short index, not a
second report. The composition signal is explicit:
`--composed: idea-stage/IDEA_REPORT.md`; earlier module runs remain standalone.
`/research-review` is optional, not a duplicate core gate.

## State and output

Use `python -m arisctl` for every formal transition in the Controller-managed
run. `start-phase -> complete-phase` records execution; `accept-phase` records
a deterministic/independent verdict; `human-approve` records a human decision.
The Controller registers every handoff path, SHA-256, provenance, and upstream
snapshot before advancing. `tools/run_state.py` is not an alternate transition
path. After method acceptance, no automatic validation action is exposed.
`IDEA_REPORT.md` is a final report only, never the machine state store. Invoke
`/render-html` only after it is complete.

Use the workflow starting context budget: active packet ≤24,000 characters,
review bundle ≤32,000 characters, at most 12 evidence cards and 8 unresolved
issue IDs. Use paths and stable IDs for history.

## Compatibility contract

The final **Problem-First Ranked Idea Report** retains **Certified Problems and
Derived Routes**, and route fields for **Scientific-delta novelty**. Keep
generators and juries fresh and do not reuse the generator context for the jury.
