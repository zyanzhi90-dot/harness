---
name: idea-creator
description: "Gemini cross-family adapter for independent problem discovery, 1a–2b diagnosis, or method design."
argument-hint: "mode: problem|diagnosis|method; direction or handoff path"
---

# Research Idea Creator — Gemini overlay

Use exactly one mode for **$ARGUMENTS**. This overlay supplies a cross-family
challenge; it does not collapse problem and method into one call.

The overall compatibility output remains **certified problems and derived method routes**, while each execution writes only its own compact handoff.

Use the independent adapters when relevant:
`../shared-references/idea-fanout-module.md` for isolated breadth generation,
`../shared-references/idea-wiki-integration.md` for optional Wiki memory, and
`../shared-references/idea-output-composition.md` for final report output. The
overlay may challenge a result, but it does not create an additional default
Gate.

`review_independence: cross-family` and `acceptance_status: provisional` are
recorded for this overlay's verdicts; human acceptance remains a separate
decision.

## `mode: problem`

Use the fan-out module for candidate breadth only. Mechanically deduplicate
before the fresh quality jury; do not rank or certify inside a generation
shard.

Read the bounded Field Evidence Map and generate structured candidates across
community-open, self-discovered failure/boundary, and justified migration
sources. Mechanically validate evidence IDs and deduplicate before a fresh
Gemini quality jury applies the six problem dimensions in
`problem-discovery-contract.md`. Run `/novelty-check "mode: problem | ..."`
separately. Return `CERTIFIED / HOLD / REJECT / BLOCKED` with evidence anchors
and uncertainty. Stop for explicit human selection; before the Controller
records human acceptance, prepare the separate `RESEARCH_CONTRACT.md` and
`PROBLEM_EVIDENCE_CAPSULE.md`. The result remains `CERTIFIED/provisional`
until the Controller records `human_accepted`. The
Contract must not embed a second capsule; the independent capsule is the sole
formal compact evidence handoff.

## `mode: diagnosis`

Require the Controller-accepted `RESEARCH_CONTRACT.md` and
`PROBLEM_EVIDENCE_CAPSULE.md`. In a fresh context, execute the shared
root-cause contract in order: 1a observed failure phenomena with evidence and
boundaries; 1b non-forced grouping; 2a repeated causal-depth tracing with
competing explanations and falsifiers; and 2b explicit causal chains. Existing
evidence may be reused only through the current capsule/registry binding; a new
diagnostic pilot must use the Controller's declared diagnostic path. Produce
`ROOT_CAUSE_ANALYSIS.json` and its Markdown view. Do not issue the verdict,
design a method, or silently revise the accepted problem. The independent
root-cause reviewer and Controller own `ROOT_CAUSE_VERDICT.json` and the fixed
`DIAGNOSIS_READY / REVISE_DIAGNOSIS / REOPEN_PROBLEM` transition.

## `mode: method`

Require the accepted `RESEARCH_CONTRACT.md` and the current Controller-accepted
`ROOT_CAUSE_ANALYSIS.json` plus `DIAGNOSIS_READY` verdict. Derive the scientific mainline,
competing explanations, falsifier, design obligations, and one minimal sufficient
dominant method before any completion search. Only a declared residual `MUST`
gap may trigger support search: assess the Field Map and same-field mechanisms
first, then search a structurally corresponding other field only when those
options cannot reasonably close that gap. For every retained support, record
the gap served, structural match, integration interface, compatible assumptions,
capability-specific removal failure, targeted validation, and transfer boundary.
Produce at most three routes in `METHOD_ROUTES.md` and stop
for human route selection into `SELECTED_ROUTE.yaml`. Preliminary method
novelty is a risk screen only; final method novelty is after `/research-refine`.

Keep problem novelty, scientific-delta novelty, and technical-route novelty
separate. Do not plan experiments, silently revise the accepted problem, or
use a score as acceptance. `research-review` is optional and must not become a
second default gate.
