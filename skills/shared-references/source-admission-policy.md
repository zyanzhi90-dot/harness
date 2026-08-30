# Research Source Admission Policy

This policy separates retrieval triage from scientific evidence strength. For
proactively retrieved literature, high citation impact or approved elite-venue
status is the default hard active-reading gate: a paper must satisfy at least
one before its content enters decision-grade reading. This gate establishes
eligibility only; it does not itself require full-text reading or assign a
backbone label. A narrow Controller-
recorded exception is allowed only for identity-verified, in-scope work that is
decisive as the closest/concurrent prior work, negative or contradictory
evidence, or diagnostic/replication evidence for an explicit decision target.
Recency or relevance alone is not an exception. This gate does not apply to
papers explicitly supplied by the user.

## Project policy

Use `artifact_manifest.source_admission_policy` when the project supplies one.
It must define the field scope, the approved elite-venue list and/or the
field-calibrated high-citation rule, search routes, source types, and languages.
Venue or citation status is an active-reading eligibility
condition, not proof that a claim is correct; claim-level assessment remains
mandatory. Record policy version, approver, and timestamp in the search log.

### Default raw-citation baseline

Unless a project has a defensible field-calibrated alternative, use the following
age-calibrated *raw citation-count* baseline in its candidate policy.  The
comparison is always strict (`>`), and the count must record both provider and
retrieval date.  This is a triage gate, not a field-normalized impact metric or
a substitute for expert judgment.

| Publication year | High-citation gate |
| --- | --- |
| Before 2000 | >300 citations |
| 2000–2009 | >200 citations |
| 2010–2017 | >100 citations |
| 2018–2020 | >60 citations |
| 2021–2022 | >35 citations |
| 2023 | >20 citations |
| 2024 | >10 citations |
| 2025 | >3 citations |
| 2026 and later | >1 citation |

The later bands deliberately use lower thresholds because citation accumulation
is time-dependent.  Projects in fields with markedly different citation norms
must replace this baseline with an explicit field-calibrated rule and state the
rationale in the policy.  A paper that fails the citation gate may still be
actively read when it appears in an approved elite venue; otherwise it remains
`DISCOVERY_METADATA_ONLY`.

Threshold ranges must not overlap.  Configure every intended year range
explicitly: an uncovered year falls back to
`non_elite_citation_threshold_exclusive` when that value is supplied, and is
otherwise ineligible by citation count.

## Track A — proactively retrieved literature

Initially mark every search result `DISCOVERY_METADATA_ONLY`. Deduplicate it,
then screen every candidate from title and actual abstract before retrieval may
close; a search snippet is not an abstract. Title-only exclusion is permitted
only for an obvious duplicate or unmistakable scope mismatch.

Admission eligibility and reading priority are separate decisions. Use this
priority ladder for an in-scope corpus:

1. complementary recent authoritative reviews from elite venues or with high
   citation influence: after the current initial corpus is fully screened, the
   Agent selects the Reviews needed to establish and triangulate a provisional
   initial map;
2. high-citation candidates: after title/abstract screening, label only the
   task's in-scope foundational or turning-point mechanism papers as
   `HIGH_CITATION_BACKBONE`; this is priority metadata, not an automatic
   full-text cohort;
3. recent elite-venue frontier papers: search and abstract-screen the complete
   retrieved set, then select representative full texts when the set is large;
4. targeted gap, contradiction, negative-result, diagnostic, and saturation
   follow-up.

An abstract-only in-scope record must retain the abstract and an explicit,
task-specific reason why full text was not selected, such as a mechanism already
covered by identified evidence, a non-reusable application implementation, or
no unresolved decision target. An in-scope authoritative review or labelled
high-citation backbone paper may remain outside the current full-text pass. A citation
threshold makes a paper eligible for backbone assessment; it never labels every
high-citation or elite-venue paper as a backbone paper.

Use these decisions:

```text
ADMIT_DECISION_GRADE
  identity is sufficiently verified, the source is in scope, it satisfies the
  high-citation or approved-elite-venue gate (or has a recorded narrow exception),
  and content can be inspected at the depth required by the claim.

ADMIT_DISCOVERY_ONLY
  relevant search lead whose identity, active-reading eligibility, or content
  access is not yet sufficient for a scientific claim; it remains metadata-only
  and may guide query/citation expansion only.

HOLD_IDENTITY / EXCLUDE_IRRELEVANT / EXCLUDE_DUPLICATE
  do not use scientifically until the stated blocker is resolved.
```

For Track A, citation count or elite-venue status is required for active reading,
except for the narrow decision-grade exception above. The exception must record
one of `decisive_closest_prior_or_concurrent`,
`negative_or_contradictory_result`,
`diagnostic_or_replication_evidence`, or
`rmc_bound_source_mechanism_or_genealogy`, a scientific reason, and the explicit
problem/novelty/coverage/diagnostic/Source decision targets it may change. The
RMC-bound exception additionally requires a verified Source identity, the
current Method Design Query Plan/RMC decision context, and
`TARGETED_GAP_FOLLOWUP` priority; it only permits the full-text read needed to
judge Source intervention, causal efficacy, or genealogy. Neither the default
gate nor an exception establishes relevance, Source causal efficacy,
intervention-level alignment, novelty, strength, or evidence grade.
Deliberately search recent work, negative/null results, replications,
benchmarks, diagnostics, and contradictory findings; retain candidates that do
not pass the gate as metadata-only records rather than silently deleting them.

For every admitted source record identity status, admission reason, search
route, retrieval date, content access level, and the claim(s) it may support.
Do not use a discovery-only record as prior work, contradiction evidence,
problem evidence, transferred method, novelty evidence, or support for a
scientific claim. It may seed a query or citation expansion, and remains in the
auditable candidate corpus with its uncertainty.

Screening and admission are decisions in a scientific context, not global paper
properties. Keep paper identity, metadata, full text, and canonical Evidence
globally unique, while recording each decision under its immutable current
context. Incremental Method Design decisions bind at least `paper_id + phase +
query_plan_sha256 + phase_binding_anchor + decision_targets[]`; Landscape and
other phases use their own accepted context. A changed Query Plan, Problem/phase
binding, RMC, or Target Mechanism Signature makes an older decision non-current.
The reading session and Evidence lifecycle consume only the exact decision ID
selected for their current context, so Landscape and distinct RMC decisions for
the same paper remain separately auditable and cannot overwrite one another.

Decision-grade evidence requires inspected content, an exact locator, and
enough surrounding context to verify the claim, setting, comparison, and
boundary. A verified bibliographic identity does not verify the paper's
scientific claims.

## Track B — user-supplied papers and notes

When the user explicitly supplies a paper, local file, bibliography entry, or
design note and asks the Harness to analyze it, mark it `USER_SUPPLIED_READ` and
read it regardless of venue, citation count, or publication status. Never
discard user-supplied material before content inspection.

After reading, record relevance, internal correctness, evidence strength,
applicable boundary, and the role it may play. User provision is not evidence
that an author's claim is true or that novelty has been established.

## Audit requirements

The search log must preserve all decisions, including excluded and
discovery-only records. Evidence maps must state coverage blind spots and
search routes actually attempted. Follow PRISMA-style reporting for search,
screening, inclusion/exclusion, and flow counts where a systematic review is
claimed; do not present a convenience sample as exhaustive.

## Controlled correction and replenishment

When a screening decision may be wrong, a mechanism is missing, a contradiction
or failure boundary is uncovered, or a prior abstract-only record becomes
material to a named decision target, use the existing coverage-review return
route. The independent coverage reviewer returns `CONTINUE` with one or more
concrete gaps; the Controller then returns only to `QUERY_PLANNING`. The next
Query Plan must retain those gaps and define the smallest query batch that can
resolve them.
Every resulting candidate again passes the normal retrieval, title/abstract
screening, admission, explicit current-subset selection, full-text, Evidence Card, Field Map, and coverage-review
steps. Do not rewrite old corpus records, alter accepted Evidence, or create a
parallel correction workflow. During a declared scientific-core phase, use the
existing phase-scoped incremental-literature route under the same constraints.
