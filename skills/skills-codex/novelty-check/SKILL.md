---
name: "novelty-check"
description: "Verify problem novelty, method novelty, or both against recent literature. Use for 查新, novelty checks, prior-art questions, and research problem or method verification."
---

# Novelty Check Skill

Check whether a proposed problem framing and/or method has already been
established in the literature: **$ARGUMENTS**

## Constants

- REVIEWER_MODEL = `gpt-5.6-sol` — Model used via a secondary Codex agent. Must be an OpenAI model (e.g., `gpt-5.6-sol`, `o3`, `gpt-4o`)
- **REVIEWER_BACKEND = `codex`** — Default: Codex xhigh reviewer. Use `--reviewer: oracle-pro` only when explicitly requested; if Oracle is unavailable, warn and fall back to Codex xhigh.

## Instructions

Parse `mode: problem|method|combined`. Default to `combined` only when both are
present; otherwise infer and report the applicable mode. Follow
[`problem-discovery-contract.md`](../shared-references/problem-discovery-contract.md)
for problem mode and
[`method-design-contract.md`](../shared-references/method-design-contract.md)
for method mode. Keep problem, scientific-delta, and technical-route novelty
separate.

`mode: method-final` is an explicit final-method alias. It accepts only
`refine-logs/FINAL_PROPOSAL.md` after refinement; preliminary route checks are
not final novelty gates.

For the formal final-method Gate, `idea-stage/FINAL_METHOD_NOVELTY_VERDICT.md`
must contain exactly one fenced JSON metadata block with `schema_version: 1`,
the live `review_request_id`, `reviewer`, `verdict_id`, `decision: NOVEL`, and
the exact `reviewed_artifact_hashes` map for `FINAL_PROPOSAL.md`.

Apply
[`source-admission-policy.md`](../shared-references/source-admission-policy.md)
before reading or expanding any candidate paper.

### Phase A: Extract Key Claims
1. For `problem|combined`, extract problem claims: phenomenon, setting,
   failure/boundary, causal framing, importance, and research question.
2. For `method|combined`, extract: falsifiable hypothesis, intended scientific
   delta, dominant method, reused backbone, innovation carrier, supporting
   mechanisms, integration interfaces, targeted evidence, and technical delta.
3. Assign separate IDs (`P1...`, `M1...`).

### Phase B: Controller-Governed Literature Search
For each applicable claim:

1. For a formal run, ask `arisctl allowed-actions`. If the pending phase exposes
   `submit_query_plan`, submit claim-specific formulations there, then use only
   the existing Controller query, admission, read and evidence actions. Never
   use hosted web search/fetch or a private corpus/ledger.
2. Use the pending `problem_novelty_gate` or `final_method_novelty_gate` as
   appropriate, and finish the existing reading flow before starting the Gate;
   the Controller binds newly accepted Evidence Card hashes to its request.
3. Read only `ADMIT_DECISION_GRADE` or `USER_SUPPLIED_READ` content. Keep
   discovery-only and blocked records as metadata, never scientific evidence.
4. Ad-hoc web findings are provisional and cannot become a formal ARIS artifact.

### Phase C: Fresh-Agent Verification (same-family provisional by default)
Call REVIEWER_MODEL via `spawn_agent` (`spawn_agent`) with xhigh reasoning:
```
reasoning_effort: xhigh
```
Prompt should include:
- mode and separate problem/method claim lists
- All papers found in Phase B
- Ask for independent problem and/or method verdicts, closest prior framing or
  route, residual delta, and confidence. In combined mode, one verdict cannot
  substitute for the other.
- A potentially decisive closest/concurrent prior must use the existing
  `decisive_closest_prior_or_concurrent` admission exception and resolve to a
  decision-grade Evidence Card whose source ID is that same prior. If it cannot be verified, return problem
  `UNCERTAIN`, not `NOVEL`.

### Phase D: Novelty Report
Output a structured report:

```markdown
## Novelty Check Report

### Mode
problem / method / combined

### Problem Novelty
- Problem statement and claims (P1...)
- Closest existing framing
- Residual unresolved delta
- Verdict: HIGH / MEDIUM / LOW / BLOCKED
- Confidence and evidence gaps

### Method Novelty
- Scientific hypothesis and intended delta
- Dominant method + backbone + innovation carrier and claims (M1...)
- Supporting mechanisms, integration interfaces, and targeted responsibilities
- Closest existing route
- Residual scientific delta and residual technical-route delta
- Scientific closure: structural match, actual interfaces,
  capability-specific removal failures, targeted evidence, and one causal chain
- Verdict: HIGH / MEDIUM / LOW / BLOCKED
- Confidence and evidence gaps

### Closest Prior Work
| Paper | Year | Venue | Overlap type | Claim IDs | Key difference |
|-------|------|-------|--------------|-----------|----------------|

### Overall Novelty Assessment
- Problem novelty: X/10 or N/A
- Method novelty: X/10 or N/A
- Recommendation: PROCEED / PROCEED WITH CAUTION / ABANDON
- Key differentiator(s): [problem and method stated separately]
- Risk: [what a reviewer would cite as prior work]

### Suggested Positioning
[How to frame the contribution to maximize novelty perception]
```

### Important Rules
- Be BRUTALLY honest — false novelty claims waste months of research time
- A supporting mechanism is justified only when it closes a declared residual
  `MUST` gap after Field-Map and same-field options have been assessed;
  combination itself is not a novelty claim.
- "Applying X to Y" requires structural correspondence, real integration, and a
  scientific delta.
- In combined mode, report problem and method novelty separately.
- If the method is not novel but the FINDING would be, say so explicitly
- Apply the Source Admission Gate without using recency as an eligibility gate.

## Review Tracing

After each `spawn_agent` or optional `oracle-pro` reviewer call, save the trace following `../shared-references/review-tracing.md`. Write files directly to `.aris/traces/novelty-check/<date>_run<NN>/` and record searched claims, closest papers, reviewer route, raw response, and final novelty decision. Respect the `--- trace:` parameter when present (default: `full`).
