# Idea fan-out execution module

This module is the execution adapter for breadth generation in
`/idea-creator`. The general safety rules live in
[`fan-out-pattern.md`](fan-out-pattern.md); this file binds them to the
problem-first research workflow.

## Decision boundary

Use fan-out only for `mode: problem`, step P1, where independent lenses produce
working Leads for discovery and triage. It may also be used by `/research-lit` for parallel
extraction of papers or claims. It must not be used to decide novelty, quality,
human acceptance, method readiness, or the final route. Those are formal gates
with one owner and one durable verdict. In `mode: method`, route synthesis is
normally sequential; if breadth is genuinely needed, fan out route hypotheses
only and collect them before any ranking or gate. Shards do not perform ranking
or certification.

## Dispatch and isolation

Select the smallest tier that the runtime supports:

1. parallel workers for independent lenses;
2. static-agent fan-out when the runtime exposes safe isolated workers;
3. sequential fresh invocations when it does not.

The default fallback is tier 3. Every shard receives only the compact evidence
packet, scope constraints, and its lens. It does not receive another shard's
draft, the full registry, a previous report, or a verdict. Shards do not write
shared files, update the Wiki, or call a formal reviewer. They return structured
data to the parent, which owns consolidation.

Recommended problem lenses are: community-open gaps, failure/boundary cases,
contradictions or negative evidence, and structurally justified migration.
Use at most five lenses and ask each for one to three Leads. Fewer lenses
are preferable when the evidence map is narrow.

## Shard contract

Each returned line must validate as an object with:

```json
{
  "shard_id": "problem-boundary-01",
  "lens": "failure-boundary",
  "candidates": [
    {
      "lead_id": "lead-boundary-01",
      "statement": "...",
      "discovery_route": "self_discovered",
      "starting_observation": "...",
      "why_track": "...",
      "largest_uncertainty": "...",
      "current_basis": "...",
      "possible_disconfirming_evidence": "..."
    }
  ]
}
```

These are in-context cognition returns, not Lead artifacts. The parent triages
them and may discard, deepen, narrow, or reframe them. It creates
`PROBLEM_CANDIDATES.jsonl` only after it judges one Lead mature and expands it
to the existing Candidate schema. A rejected Lead is not a Candidate and never
reaches the Candidate Validator or either existing problem Gate.

## Budget and recovery

Keep the shard packet below 24,000 characters, with at most 12 evidence cards.
If a worker fails, retry only that shard once with the same input hash, then
record a bounded missing-shard event; never silently substitute a new scope. If
the packet is insufficient, stop with `BLOCKED_EVIDENCE`, not more fan-out.

The parent records input hash, shard IDs, worker family, and completion status
in the run trace. It passes only mature formal Candidates to the independent
quality and novelty reviewers. A generator context is never reused as a jury context.
