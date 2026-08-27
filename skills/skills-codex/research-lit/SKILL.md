---
name: research-lit
description: Build an evidence-grounded Active Field Map for a bounded research field. Use for literature landscapes, method-family taxonomies, bottleneck analysis, causal development traces, failure-boundary analysis, and unresolved problem leads. Formal runs are controlled by arisctl; this Skill contains scientific reasoning only.
allowed-tools: Read, Agent
---

# Research Literature Cognition

Research topic: $ARGUMENTS

## Execution boundary

For a formal run, first read the Controller status and perform only the action
allowed for its current stage. Return structured cognition to the Controller;
never search, fetch full text, admit a paper, write canonical artifacts, change
state, approve a Gate, count a budget, or declare the stage complete yourself.

When the Controller reports `SOURCE_POLICY_DRAFTING`, Main Research Agent must
draft a project-specific candidate using `source-admission-policy.md` and submit
it through `arisctl submit-source-policy`. Do not write the canonical policy
path directly and do not approve the candidate. The Controller validates the
candidate before it opens `source_policy_approval`; retrieval remains forbidden
until the user approves that exact validated candidate.

The mechanical contract is `shared-references/idea-workflow.yaml`, enforced by
`arisctl`. This Skill intentionally does not duplicate stage order, budgets,
artifact-existence rules, admission permission, human approval, transition
conditions, or schema validation.

Query planning and Field Map synthesis are Main Research Agent responsibilities.
Spawn only `paper_reader` to isolate admitted-paper context and
`coverage_reviewer` for a Controller-issued candidate-sufficiency, major-taxonomy,
or final-acceptance review. Do not create role-named agents for the Main tasks.

## Native reader/reviewer dispatch

Reader and coverage-review work stays inside the current active Codex turn.
Prefer the configured native `paper_reader` or `coverage_reviewer` role. If this
runtime cannot select that custom role, use a current-turn native generic child
only for these two roles; never emulate a configured role through nested
`codex exec`, a new Codex CLI session, or a new top-level turn.

The generic child must use `fork_turns = none`. Its Controller-bound user task
must contain exactly one one-line `ARIS_NATIVE_GENERIC_COMPAT:` JSON binding
with `dispatch_mode: native_generic_compat`, `formal_role`, the SHA-256 of the
configured role's exact `developer_instructions`, and that verbatim contract.
For `paper_reader`, bind `paper_id`, `read_event_id`, and `content_sha256` and
include only the Controller-supplied paper content. For `coverage_reviewer`,
bind the live `run_id`, `review_request_id`, and exact
`reviewed_artifact_hashes`. The native lifecycle hook recognizes this only from
the real child transcript and records `dispatch_mode = native_generic_compat`;
it rejects incomplete bindings, non-native/root children, reader tool use, and
reviewer capabilities beyond the configured contract. Submit no formal output
unless that attestation exists.

Scientific source policy and the downstream problem boundary remain defined by:

- [`source-admission-policy.md`](../shared-references/source-admission-policy.md)
- [`problem-discovery-contract.md`](../shared-references/problem-discovery-contract.md)
- [`fan-out-pattern.md`](../shared-references/fan-out-pattern.md)

If an explicitly requested private source is unavailable, stop and ask the user to configure
it; do not silently downgrade to public search. Provider routing is a
Controller/gateway concern and not an agent action. The discovery order is fixed:

1. SerpApi Google Scholar (`engine=google_scholar`, key from `SERPAPI_KEY`);
2. only when SerpApi is unavailable and the current environment exposes real
   browser/computer interaction, normal serial page interaction with
   `https://scholar.google.hk/`, conservative spacing, and immediate exit on
   CAPTCHA, unusual-traffic, `We're sorry`, or HTTP 429/403 signals; without
   that capability this route is unavailable, and no HTTP/HTML scraper is used;
3. only when both Scholar routes are unavailable or blocked, the parallel,
   deduplicated union of arXiv and IEEE Xplore (or whichever one remains
   available), recorded explicitly as non-Google-Scholar fallback coverage;
4. when a configured provider fails, do not permanently suppress it for later
   queries. Record the query-scoped incident. If a lower-priority route produced
   metadata after any such failure, or no route can run, enter
   `HUMAN_SEARCH_REQUIRED` and STOP so coverage is not silently downgraded.

A successful Scholar-provider response with few, low-relevance, or zero results
is not provider failure. Keep that provider and use the existing targeted query
refinement and citation-expansion cycle. At the final arXiv + IEEE Xplore level,
use the existing admission and Field Map coverage decisions—never a new coverage
rule—to determine whether the automated fallback completed the search. A human-search request is
one batch: it includes every affected planned query, purpose, requested filters, and provider
attempts; the user returns one matching batch of metadata before retrieval resumes. Ordinary Web Search and
`site:scholar.google.*` queries never count as Google Scholar retrieval. Never
add another automatic discovery source, bypass CAPTCHA, rotate proxies/IPs, or
use anti-detection measures.

Automatic full-text acquisition is arXiv-only. Partition the unread admitted
papers before retrieval: call `fetch-fulltext` only when the admitted identity
declares an `arxiv_id` or `arxiv.org` stable URL; pass every other unread ID to one
`defer-fulltext-batch` call without probing publisher pages, Crossref, OpenAlex,
Semantic Scholar, or general Web Search for a PDF. After the arXiv attempts and
their Evidence Cards are complete, call `finish-reading` once; it must stop in
`HUMAN_SEARCH_REQUIRED` with one download batch containing every deferred paper
and any arXiv paper whose direct download failed. The user places one local file
per listed paper under `source-materials/` and submits a single manifest; only
then does normal paper reading and evidence extraction resume. Never ask for one
download at a time or omit an admitted paper because its full text is unavailable.

## Scientific objective

Construct a compact, revisable model of the field in this causal order:

```text
field core purposes -> typical tasks and scenarios -> core bottlenecks
  -> evidence-validated major method families
  -> bottleneck addressed and mechanism
  -> assumptions -> effective conditions -> failure conditions
  -> unresolved contradictions -> unresolved problem leads
```

Do not start from a fashionable method and search backward for a problem. A
paper list, a chronology, or a survey author's taxonomy is not a Field Map.

## Role: query planner

### Evidence-acquisition ladder

Do not equate a short full-text list with a complete search. Build the corpus in
decreasing evidence priority while screening the whole retrieved set:

1. find multiple complementary, recent authoritative reviews from elite venues
   or with strong citation influence; read them in full to construct and
   cross-check the initial map rather than inheriting one survey taxonomy;
2. identify high-citation candidates regardless of venue; after title/abstract
   screening, label and read in full only the task's foundational or
   turning-point mechanism papers as `HIGH_CITATION_BACKBONE`, to recover
   mechanisms, causal transitions, and persistent bottlenecks;
3. search recent elite journals/conferences systematically for current methods
   and hotspots; when the set is large, select representative papers for full
   text using explicit mechanism, branch, recency, and contradiction coverage,
   while retaining the remainder at abstract level;
4. run targeted gap, citation-chain, negative-result, and saturation follow-up.

Every deduplicated candidate must receive a title-and-abstract inclusion or
exclusion decision before retrieval closes. A title-only decision is permitted
only for an obvious duplicate or clear scope mismatch. Search-result snippets
are not abstracts. An in-scope abstract-only record must preserve the abstract
and the reason full text was not selected. If normal enrichment has verified
identity but cannot obtain an actual abstract, use
`TITLE_ONLY_ABSTRACT_UNAVAILABLE`; this completes screening but is never
scientific Evidence. Priority/admission metadata never authorizes a read by
itself: after all current initial candidates are screened, explicitly select a
non-empty initial-cognition subset. Prefer complementary authoritative Reviews;
if none are usable, select the minimal foundational/representative Primary
fallback. If Review Evidence is insufficient, add only the necessary screened
Primary fallback to the still-live pass. Venue and citation influence reading
priority; they never prove a scientific claim.

Submit the provisional Initial Map through the same `ACTIVE_FIELD_MAP.md`
path, without a coverage record or coverage review. It is a reliable cognition
handoff, not a coverage verdict. Then choose the formal Primary subset from the
same bound initial corpus, recording the scientific selection rationale for
foundational anchors, representative branches, transitions, contradictions or
gaps as applicable. `ACTIVE_FIELD_MAP.md` remains the sole Field Map:
`INITIAL_PROVISIONAL` labels this current initial-cognition use, not a Map type,
file, or independent lifecycle. Retain the existing `initial_field_map_binding`,
`formal_primary_selection`, and map-lifecycle expression. During formal Primary
selection, a paper with lawful canonical Evidence satisfies its reading
requirement through the existing Evidence lifecycle; do not create duplicate
Evidence. The subsequent revised map and later coverage updates use normal
coverage semantics and the same canonical map path.

For formal runs, submit Query Plan schema version 2. Each executable item has a
unique `plan_item_id`, priority tier, year range, page, exact-title flag, target
venues, purpose, and close condition. Repeated query text is allowed for real
pagination. The Controller checks these fields before the provider call, so
year/venue/page stratification must exist as executable plan items, not prose.

When the current Active Field Map is `PARTIAL` or `INSUFFICIENT`, its
`coverage_record.coverage_gaps` are equally controlled correction requests.
When an independent coverage review returns `CONTINUE`, combine its concrete
gaps with any still-live Field Map gaps. Carry every required gap into the
smallest gap-resolving Query Plan and bind each one to at least one executable
query item's `coverage_gaps`; the Controller rejects both an omitted required
gap and a required gap with no bound query. A planned query is not enough:
complete the bound search before retrieval can close. Re-enter through the
same retrieval, screening, admission, reading, Evidence, Field Map, and review
path. Never repair a prior classification by editing an archived corpus record
or accepted Evidence directly.

Receive only the current Field Map, coverage record, and named evidence gaps.
Propose the smallest next batch of queries that can discriminate among:

- an uncovered or unstable family boundary;
- a missing foundational, turning-point, or current representative anchor;
- a contradiction or suspected failure regime;
- a missing backward/forward citation link;
- a negative-result, reproduction, benchmark, or diagnostic blind spot;
- an unresolved identity or nearest-prior uncertainty.

For each query, state its purpose and the observation that would close or
reopen the gap. Do not execute it and do not infer saturation from the plan.

Design the query from the unresolved field cognition, not by mechanically
extracting keywords. The current Map and Evidence may supply discriminating
professional terminology—method and mechanism names, alternative labels,
assumptions, failure regimes, benchmark or diagnostic terms, cited-paper
identities, and backward/forward citation anchors. Use them when they help
separate competing explanations or recover a missing branch; they are inputs
to judgment, not a mandatory keyword-extraction pipeline.

## Role: paper reader

Read only the admitted paper content supplied by the Controller. Extract an
Evidence Card that distinguishes bibliographic identity from scientific claim
validity and author reports from executor inference.

For each paper, determine:

- the actual problem and setting;
- the method or mechanism, not only its name;
- the claimed contribution and inspected evidence;
- assumptions and boundary conditions;
- effective and failure conditions;
- conflicts with other admitted evidence;
- its synthesis role and supported development link;
- an exact claim locator and epistemic status.

Metadata, snippets, abstracts, and unlocated notes are discovery-only. Claims
about failure causes, negative results, assumptions, novelty, or closest-prior
capability require inspected source content with enough local context. Preserve
uncertainty when access or evidence is inadequate.

## Role: field synthesizer

Update one working Active Field Map from accepted Evidence Cards. Do not replace
it with disconnected batch summaries.

For an Initial Map, synthesize only the selected initial Review/fallback
Evidence and omit `coverage_record`; it must not request coverage review or
ordinary gap queries. After map-guided formal Primary reading, revise the same
map with landscape Evidence only—never mix Problem, RCA, Method, or other
phase-scoped incremental Evidence. The Controller archives each accepted
version before the canonical map is overwritten, so an SHA used by formal
provenance remains recoverable.

For `PARTIAL` or `INSUFFICIENT`, `coverage_record.coverage_gaps` must name the
specific missing cognition that could change a family boundary, anchor,
bottleneck, mechanism, condition, failure regime, causal transition, or
frontier judgment. When new Evidence arrives, revise the same canonical
`ACTIVE_FIELD_MAP.md`: correct a mistaken classification, add an omission,
merge or split families, or reorganize the evidence-supported development
trace as warranted. It is neither append-only nor a new map per search round;
historical Evidence Cards remain intact even when the working taxonomy changes.

The synthesis target is an evidence-shaped account of `research problem ->
method -> evidence -> bottleneck -> transition -> subsequent evolution`, from
foundational work to the current frontier. This frame is fixed, but the
literature determines stage count, duration, and branch topology. Allow
parallel branches, forks, merges, long-term coexistence, and paradigm shifts;
never create a stage from year boundaries alone.

### Purposes, tasks, and bottlenecks

State what the field is trying to achieve, for whom, under which constraints,
and which trade-offs cannot be optimized simultaneously. Separate application
scenarios from the control, inference, representation, measurement, or system
bottlenecks that cause difficulty.

### Method families

Derive a small number of field-recognized broad families by triangulating
high-quality reviews, representative-paper introductions, and the papers'
actual mechanisms. Treat every source taxonomy as a perspective rather than
authority. Keep a one- or two-paper direction as a branch unless evidence
supports a distinct mechanism and boundary.

Taxonomy is an evidence-conditioned working model. Split families when their
mechanisms, assumptions, or failure regimes are materially different; merge
labels that describe the same causal strategy. Preserve competing plausible
groupings when the evidence does not settle the boundary.

### Problem × method relation

For every family, identify the bottleneck it addresses and the mechanism by
which it does so. Do not infer effectiveness from popularity, venue, or citation
count. A family that targets a bottleneck may still fail outside its assumptions.

### Assumption × effective-condition × failure-condition relation

Connect, in the same row, the family's required assumptions, conditions where
evidence supports it, failure or degradation conditions, and source IDs.
Distinguish author-reported limitations, direct negative evidence, conflicts,
and executor-inferred boundaries that remain hypotheses.

### Causal development trace

Development is not chronology. A transition is supported only when evidence
shows the previous bottleneck, progress and conditions, residual bottleneck,
research-question shift, subsequent direction, transition status, and source
IDs. Record a unique `transition_id`; `progress_and_conditions` must identify
the method or mechanism, evidence-supported progress, and its conditions.
Explain why the question migrated. Chronology and citation order alone do not
establish the explanatory lineage. Create a trace only for a supported research-
problem or method-paradigm change. Several papers may jointly support it; no
single landmark paper is required. Empty traces are valid only when evidence
supports no material transition. Keep paper-level links only for foundational,
turning-point, and current representative work in the Evidence Registry, and
keep the main trace at family level; cross-family traces may omit `family`.

### Contradictions and unresolved leads

Preserve conflicting credible evidence rather than forcing consensus. Generate
unresolved leads from observed failures, boundary shifts, contradictions,
untested assumptions, measurement blind spots, or unknown mechanisms. Search
absence and author-written future work are leads, never proof. Do not design a
method in this Skill.

## Role: coverage reviewer

Review the Controller-bound Query Plan, Source Policy, latest candidate Corpus,
Search Ledger, Evidence Registry, and canonical Field Map in a fresh context,
independently of the synthesizer's reasoning history. Look for unexecuted
pagination/year/venue searches, candidates lacking title/abstract screening,
unexplained abstract-only retention, reviews or high-citation backbone papers
lacking full-text evidence, missing branches, unsupported family boundaries,
discovery-only decisive claims, flattened contradictions, missing negative or
diagnostic evidence, unresolved identities, and unsupported saturation.

Return an `evolution_assessment` covering `foundation_to_frontier`,
`key_nodes_and_branches`, `transition_causality`, and
`explanatory_coherence`, each with `status: PASS | GAP` and a non-empty
`rationale`. The last asks whether the map explains why the field developed
into its current form and where the present frontier sits.

For `transition_causality`, bind the review path to the Controller's
`development_trace_count`: use `DECLARED_TRACES_REVIEWED` when traces exist;
with no traces, use `NO_MATERIAL_TRANSITION_SUPPORTED` only when evidence
supports no material transition, or `MATERIAL_TRANSITION_MISSING` for an
important omitted transition. Put each `material_evolution_gaps` entry verbatim
in top-level `gaps`; any such gap requires `CONTINUE`. Do not treat an untidy
timeline, irregular stage count, parallel coexistence, or lack of one landmark
paper as a gap.

Return `CONTINUE` or `CANDIDATE_SUFFICIENT` with concrete reasons and gaps. The
decision is advisory; only the Controller's deterministic validator may accept
the landscape or change workflow state.

Use external search only for a small number of targeted omission-falsification
queries when the bound record creates a concrete doubt; do not browse publisher
pages one by one. Any hit is only a lead. Return `CONTINUE` with the exact gap so
it re-enters through formal retrieval, screening, reading, and Evidence.

## Scientific saturation judgment

`CANDIDATE_SUFFICIENT` means working saturation for the declared scope, never
exhaustive coverage. It requires evidenced families and anchors, decision-grade
critical claims, an unchanged follow-up cycle with targeted query refinement
plus backward/forward citation expansion, and explicit blind spots. If a
missing route, inaccessible full text, unresolved identity, or open branch
could materially change the map, recommend `CONTINUE`. “Not found” never means
nobody has done it.

It also requires all four evolution judgments to pass. Do not require a fixed
stage count or a non-empty development trace; an empty trace requires explicit
evidence-based support from the reviewer.

## Non-negotiable scientific discipline

- Cite decisive claims to exact source locations.
- Distinguish peer-reviewed work from preprints.
- Separate evidence strength from venue prestige and admission eligibility.
- Keep full registry detail out of active context; retrieve cards by source ID.
- Preserve uncertainty, disconfirming evidence, and competing explanations.
- Do not turn a cross-field terminology match into target-field evidence.
- Do not certify a problem, judge novelty, or recommend a method here.
