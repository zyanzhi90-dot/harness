---
name: idea-creator
description: "Codex-compatible independent problem-discovery, root-cause diagnosis, or method-design module."
argument-hint: "mode: problem|diagnosis|method; direction or handoff path"
---

# Research Idea Creator (Codex adapter)

Run one explicit mode for **$ARGUMENTS**. The adapter preserves the mainline
scientific contract while using the local Codex runner and fresh contexts.

## Mode boundary

`mode: problem` reads the Field Evidence Map, matures internal Leads into
evidence-grounded problem Candidates only when ready, and produces quality/novelty packets. It must stop before method
design and wait for a Controller-recorded `human_accepted` problem version in
`RESEARCH_CONTRACT.md`.

`mode: diagnosis` reads only the accepted problem and evidence capsule. It
executes 1a collection and description of phenomenon evidence directly
representing the problem/failure, 1b phenomenon grouping, 2a causal-depth
tracing, and 2b causal-chain construction under
`root-cause-analysis-contract.md`. It writes `ROOT_CAUSE_ANALYSIS.{json,md}`;
a fresh reviewer writes `ROOT_CAUSE_VERDICT.json`. 1a may use existing
experiments, literature, datasets, real-world scenarios, or a necessary
diagnostic pilot; a failed experiment is not required. It must not design
methods. For a Method-triggered reopen, read the matching existing Controller
return record (`method_design` → `root_cause_analysis`) and use its reason and
trigger Evidence IDs; formally cite a method-stage Card only by running the
existing `readopt-evidence` action.

`mode: method` reads the accepted problem plus a validated
`DIAGNOSIS_READY` root-cause analysis/verdict with matching IDs, problem
version, and hashes. It
derives the scientific mainline and design obligations from
`primary_causal_chain_ids`, then derives capabilities, chooses a minimal
sufficient dominant solution, records dominant-only closure, and adds completion
mechanisms only for residual MUST gaps. It
must stop at human route selection and write `SELECTED_ROUTE.yaml` only after
that decision. If this reasoning shows the accepted diagnosis needs
re-analysis, finish any active method literature session and invoke the unique
Controller `reopen-root-cause` action with a specific reason and any triggering
formal method Evidence IDs; do not continue route design or rewrite RCA.

`IDEA_REPORT.md` is a final human-facing report, not a machine handoff. Do not
paste the full registry, raw search history, or previous reviewer transcript
into a new context.

If `LESSONS_LEARNED.md` exists, use only relevant entries as anti-repetition
checks. They are not evidence or Controller handoffs and cannot authorize a
transition. Never use `.aris/archive/` as an active input: `return-phase`
moves invalidated outputs there so their former conclusion cannot be consumed.

Starting context budget: active packet ≤24,000 characters, review bundle
≤32,000 characters, at most 12 evidence cards and 8 unresolved issue IDs.
Retrieve larger artifacts by stable path and ID; tune these defaults using
task success, latency, and token-cost measurements.

Read only the active module references:

- [`idea-fanout-module.md`](../shared-references/idea-fanout-module.md) for
  problem-mode breadth generation;
- [`root-cause-analysis-contract.md`](../shared-references/root-cause-analysis-contract.md)
  for diagnosis mode and its independent Gate;
- [`idea-wiki-integration.md`](../shared-references/idea-wiki-integration.md)
  when `research-wiki/` is present;
- [`idea-output-composition.md`](../shared-references/idea-output-composition.md)
  when exporting the final report.

## Problem mode

Follow `idea-fanout-module.md`: use isolated lens packets and structured Lead
returns for discovery/triage only. Do not rank, certify, create Candidates,
write Lead artifacts, or invoke a formal Gate from a shard.

Follow `problem-discovery-contract.md`: map field purpose/tasks/bottlenecks,
method families, assumptions, boundaries, failures, contradictions, and
negative evidence; discover community-open, self-discovered, and structurally
justified migration Leads (routes, not quotas). Discover self-discovered Leads
from horizontal comparison of shared assumptions, recurring failures,
boundaries, inconsistent results, and unresolved contradictions, or from a key
paper's discussion/conclusion, exposed bottleneck, or underdeveloped direction.
A limitation is only a Lead, never a direct Candidate: compare it with the
wider Field Map and run targeted deep dive first; triage each by starting
observation, why track, largest uncertainty, current basis, and falsifier. Only
a promising Lead in running `problem_generation` may use the existing targeted
gateway, with one six-dimension primary `decision_dimension` plus immutable
Lead/Field-Map/purpose/close-condition query context. The deep dive seeks
disconfirmation, not only support. Evidence may strengthen,
narrow, reframe, reject, or mature it. Only mature Leads become the existing
formal Candidate schema; rejected Leads do not reach a validator or Gate. Then
use a fresh jury for Reality, Importance, Unresolvedness, Precision,
Falsifiability, and Answerability. Each dimension records `PASS`,
`INSUFFICIENT_EVIDENCE`, or `FAIL`; only Reality, Importance, and
Unresolvedness require formal evidence anchors, while the other dimensions may
rely on the bound candidate and Field Map. Keep problem novelty separate from method
novelty. Write `PROBLEM_CANDIDATES.jsonl`, `PROBLEM_CANDIDATES.md`, and verdict
packets under `idea-stage/`. Human consideration includes every Quality-certified
candidate with a completed consumable novelty audit (`NOVEL`, `NOT_NOVEL`, or
`UNCERTAIN`), never novelty `survivor_ids` alone. After a Human
`request_revision`, read the selected Candidate baseline, human feedback,
novelty audit, and reviewer guidance from the latest Controller `return_history`
entry; keep the same `problem_id` and make only the directed correction and
directly affected content changes. After `reject`, use its human feedback to
reassess the active Field Map and Evidence and form a different Candidate when
warranted. Use the Controller return record as the active input. A model
verdict is provisional; after human selection and before the Controller records
human acceptance, prepare the versioned `RESEARCH_CONTRACT.md` and the separate
`PROBLEM_EVIDENCE_CAPSULE.md`. The Contract must not embed the capsule: that
independent artifact is the sole formal compact evidence handoff, and the
Controller registers both hashes. A directed correction uses the live
`problem_acceptance` Human Gate with `request_revision`, selected Candidate ID,
and human feedback; a rejected Candidate uses `reject` with its selected ID and
rejection reason. Both returns repeat Quality, Novelty, and Human Acceptance;
the incremental literature gateway is used only for a real evidence gap.

### Phase 0: Load Research Wiki (if active)

If `research-wiki/` exists, follow `idea-wiki-integration.md`. This preserves
the existing **Load Research Wiki** and **Write Ideas to Research Wiki**
behavior, but Wiki presence never means human acceptance. The module owns
threat scanning, helper resolution, deterministic `upsert_idea`, and warn-only
failure handling.

## Method mode

Require `problem_status: CERTIFIED` and
`acceptance_status: human_accepted`, plus `DIAGNOSIS_READY` and matching
problem-version/evidence/analysis hashes. Import the validated causal chains,
alternatives, discriminating evidence, falsifier, claim type, and obligations before
searching techniques. Use the Controller-accepted `ACTIVE_FIELD_MAP.md` and
its Evidence Registry as the formal method-mode input before technique search.
While `method_design` is running, derive one canonical Design Obligation set
from the accepted chains and intervention targets. If current knowledge cannot
support a credible dominant mechanism, use `DOMINANT_SOLUTION_SEARCH` through
the existing `arisctl` gateway: its Query Plan is the formal pre-route binding
and every query names current obligation IDs and their derived chains, without
requiring a dominant solution, closure, or residual gap. Search same-field,
then causally isomorphic, then necessary cross-field mechanisms. Once a
dominant carrier is credible, derive its minimal dominant-only closure. Only a
declared residual `MUST` gap may use `RESIDUAL_MUST_GAP_SEARCH`; its queries
bind decision targets and residual IDs. Reuse only the existing
query/admission/read/evidence flow, never hosted web search/fetch. For each
retained support, record the gap served, structural match, integration
interface, compatible assumptions, removal failure, targeted validation, and
transfer boundary.
Preliminary `/novelty-check` is only a risk screen; final method novelty occurs
after `/research-refine`.
First seek a same-field mechanism for each declared residual `MUST` gap. Search
another field only after recording why the accepted Field Map and a reasonable
same-field search cannot close it. Combination is permitted only as the
necessary support for that gap, never as a default or novelty verdict.
Method artifacts are separate from the problem contract and may revise only
their route/proposal content. Use explicit `arisctl revise-problem` for a
material problem change; it creates a draft next version and repeats problem
quality, novelty, and human acceptance.
At route selection, `request_revision` returns only to `method_design`; final
method acceptance uses the same decision to return only to `method_refinement`.

## Wiki compatibility

When active, preserve the existing **Write Ideas to Research Wiki** behavior
through `upsert_idea`; retain `query_pack.md` and `review-tracing.md` paths for
session compatibility. The compact handoffs are the authoritative state.

## Downstream order

```text
/research-lit -> /idea-creator "mode: problem" -> independent problem-quality Gate
-> /novelty-check "mode: problem" -> human problem acceptance
-> /idea-creator "mode: diagnosis" -> root-cause Gate
-> /idea-creator "mode: method" -> human route selection
-> /research-refine -> final /novelty-check
```

`research-review` remains an optional challenge, not a duplicate core gate.

## Compatibility report fields

The final **Problem-First Ranked Idea Report** retains **Certified Problems and
Derived Routes**, including **Design obligations**, **Scientific mainline**,
**dominant-only closure/residual MUST gaps**, **necessary supporting-mechanism ledger**,
**Scientific-delta novelty**, and the **minimal sufficient dominant solution**. Keep generator and
jury in fresh contexts; **do not reuse** the generator for the jury. Verdicts
remain `CERTIFIED/provisional` until **explicit human confirmation** records
`CERTIFIED/accepted`. `/experiment-plan` is an optional downstream handoff.

Compatibility label: Certified Problems and Derived Routes are the report's
problem-first decision fields.
