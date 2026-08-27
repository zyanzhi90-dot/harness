# Literature Coverage and Reading-Priority Fix Changelog

Date: 2026-08-13

Scope: minimal changes to the existing `research-lit` flow. No new workflow
stage, Human Gate, Reviewer role, or parallel artifact family was added.

## Confirmed failure

The impedance-control run had 171 deduplicated candidates, but 151 remained
metadata-only and 85 high-citation-eligible candidates had no full-text
Evidence Card. The previous Query Plan could describe coverage intentions but
did not encode executable year/page/venue strata; repeated query text for real
pagination was rejected. Retrieval could close after one admitted paper and
did not require a final screening decision for every candidate. The Coverage
Reviewer was bound only to the Active Field Map, so it could not audit the
actual search and screening flow.

## Changes

### Executable search coverage

- Added Query Plan schema version 2 with the fixed evidence-acquisition order:
  recent complementary authoritative reviews, high-citation backbone,
  recent elite frontier, and targeted gap follow-up.
- Added plan-item IDs, year bounds, page, exact-title flag, target venues, and
  explicit close conditions. Repeated query text is permitted when plan-item
  IDs differ.
- The Controller now preserves these fields and checks the plan-item ID and
  search options before calling a gateway. Human-search batch requests retain
  the same plan item, tier, venue, and filter context.
- Query ledger events now record the executed plan item, evidence tier, and
  search options.

### Candidate screening and reading priority

- Added one screening record to the existing Literature Corpus; no new
  screening artifact was introduced.
- Every schema-v2 candidate must close as in-scope, out-of-scope, or duplicate.
  In-scope candidates require an actual abstract or full text; snippets do not
  count. Obvious duplicates and clear scope exclusions may be title-only.
- Admission eligibility is now distinct from reading priority.
- In-scope recent authoritative reviews and high-citation backbone papers must
  be selected for full-text reading. In-scope high-citation papers cannot be
  downgraded to abstract-only.
- Recent elite/frontier candidates may remain abstract-only when the set is
  large, but the Corpus must retain the abstract and an explicit full-text
  selection reason.
- Crossref identity enrichment now retains a cleaned Crossref abstract when
  available; when it is absent, a fixed DOI-based OpenAlex metadata lookup
  reconstructs the abstract without creating another discovery query or
  visiting publisher pages.
- `finish_retrieval` checks completion of all planned queries and, for schema
  version 2, the full candidate-screening closure before paper reading begins.

### Coverage acceptance

- The existing deterministic coverage audit now evaluates the latest record
  for each candidate rather than treating historical Corpus rows as separate
  papers.
- A formal `SUFFICIENT` result now requires final candidate screening,
  full-text Evidence for selected papers and mandatory review/backbone papers,
  and explicit reasons for abstract-only frontier retention.
- The existing Coverage Reviewer is now bound to the Query Plan, Source Policy,
  Literature Corpus, Search Ledger, Evidence Registry, and Active Field Map.
- Its optional web access is limited to targeted omission falsification. An
  externally found paper is only a lead and forces `CONTINUE`; it cannot bypass
  formal retrieval, screening, reading, or Evidence.

### Semi-autonomous execution

- The existing Controller actions let the Main Research Agent execute and
  screen the planned corpus without repeated user prompting; no workflow-stage
  migration was introduced for existing formal runs.
- No additional Human Gate was added. Human involvement remains limited to the
  existing source-policy approval, batched unavailable-provider/full-text
  assistance, and later scientific decision gates.
- Formal runs no longer stop merely because an otherwise identical workflow
  file was reformatted. A hash mismatch is tolerated only when the stored
  structured workflow is semantically identical to the current canonical
  workflow; actual workflow changes remain rejected.
- A scope `request_revision` no longer runs the sufficiency audit that protects
  `approve`. Artifact/request bindings are still checked, but a newly detected
  coverage gap can now use the declared formal return path instead of being
  trapped behind the very prerequisite it is trying to repair.

### Documentation and tests

- Updated both canonical and Codex mirrors of `research-lit`, the shared source
  admission policy, the workflow agent assignment, and the installed
  impedance-control Coverage Reviewer.
- Added tests for pre-gateway plan-option enforcement and mandatory full-text
  treatment of high-citation backbone papers; updated the E2E fixture to carry
  explicit screening evidence and multi-artifact review bindings.

## Compatibility

Legacy Query Plan schema version 1 remains readable for existing runs and
tests. It does not gain silent synthetic screening data. Any legacy run that
claims formal `SUFFICIENT` coverage still fails the final audit if candidates
lack explicit screening records. New or revised research should use schema
version 2.

## Current impedance-control run

The current run remains at its existing `WAITING_FOR_HUMAN` scope-approval Gate;
this change does not approve, reject, or rewrite that decision. A read-only
audit against the strengthened contract reports 171/171 candidate records
without the new explicit screening fields (151 are still
`DISCOVERY_METADATA_ONLY`). Therefore its previously synthesized
`coverage_status: SUFFICIENT` must not be reused as evidence of adequate
coverage. If scope revision is requested, the next research cycle must use a
schema-v2 Query Plan and close the candidate-screening backlog before returning
to full-text reading and Field Map synthesis.
# 2026-08-13 — accepted-Evidence migration semantics

- Accepted Evidence Cards now satisfy the revised workflow's `FULL_TEXT` screening basis, so a rollback does not schedule an already completed full-text read again.
- An explicitly recorded revised-scope exclusion or duplicate decision is no longer undone by legacy Evidence reconciliation. In-scope accepted Evidence remains `ADMIT_DECISION_GRADE`.
- Added regression tests for both reuse and deliberate exclusion of old accepted Evidence.
- A `FULL_TEXT` re-screen backed by accepted Evidence now skips redundant online abstract enrichment; the already verified identity remains required.

# 2026-08-13 — interrupted query recovery

- Added `recover-interrupted-query` for the narrow case where a process terminates after the formal `started` event but before completion/failure recording.
- Recovery requires an explicit reason, accepts only a matching orphaned `started` event, reuses the original query ID, does not refund or re-consume query budget, and appends a formal Ledger event.

# 2026-08-13 — screening process batching

- Added the thin `admit-batch` CLI wrapper for candidate groups sharing one scientific screening rationale.
- It introduces no new state or transition: every paper still passes the existing admission validator and receives its own Corpus and Ledger record.

# 2026-08-13 — genuine title/abstract decision order

- Added `enrich-candidate` and `enrich-candidates` so identity and abstract are retrieved before the Agent records a screening decision.
- The commands do not admit, exclude, or advance state; they expose the actual decision input while retaining the existing metadata gateway and Ledger provenance.

# 2026-08-13 — monotonic literature budget extension

- Added `extend-literature-budget` for an explicitly authorized evidence expansion when the accepted priority rules identify more required papers than the original cap permits.
- Limits may only increase during an active literature cycle; consumed budget is never reset, and before/after limits plus reason are written to the Ledger.

# 2026-08-13 — abstract-unavailable full-text route

- Added `TITLE_ONLY_ABSTRACT_UNAVAILABLE` only for identity-verified candidates whose formal metadata enrichment completed without an abstract and whose full text is mandatory-selected.
- It resolves the otherwise circular dependency between admission and full-text access; ordinary in-scope title-only admission remains forbidden.

# 2026-08-13 — venue alias normalization

- Elite-venue admission now recognizes a canonical name or standalone approved alias inside provider-style bibliographic venue strings such as `2022 ... (ICRA)`.
- Matching remains boundary based; it is not fuzzy title similarity and does not admit partial-word collisions.
- Canonical venue names no longer match arbitrary interior substrings; this prevents false positives such as an `Industrial Robot` venue containing IJRR-like descriptive text.

# 2026-08-13 — arXiv identity fallback

- Crossref/OpenAlex verification now falls back to the existing arXiv gateway when discovery metadata explicitly identifies an arXiv work.
- The fallback requires an exact normalized-title match and records arXiv identity plus abstract provenance; it does not broaden general discovery.
- Added an explicit, reasoned retry command for prior `verify_failed` or completed-without-abstract records; the prior verification event remains in the Ledger.

# 2026-08-13 — access-aware full-text routing

- Added a direct arXiv PDF gateway for already admitted, identity-verified arXiv records.
- Added `defer-fulltext-batch` to formally route known publisher-restricted papers to one human download batch without wasting provider calls or full-text budget; every deferred paper receives a Ledger event.
