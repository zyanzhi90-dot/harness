---
name: "novelty-check"
description: "Verify problem novelty, method novelty, or both against recent literature. Use for 查新, novelty checks, prior-art questions, and research problem or method verification."
---

> Override for Codex users who want **Claude Code**, not a second Codex agent, to act as the reviewer. Install this package **after** `skills/skills-codex/*`.
>
> This reviewer is a different model family from the Codex executor. Every overlay trace/audit records:
>
> ```yaml
> review_independence: cross-family
> acceptance_status: accepted
> ```

# Novelty Check Skill

Check whether a proposed problem framing and/or method has already been
established in the literature: **$ARGUMENTS**

## Constants

- **REVIEWER_MODEL = `claude-review`** — Claude reviewer invoked through the local `claude-review` MCP bridge. Set `CLAUDE_REVIEW_MODEL` if you need a specific Claude model override.
- **REVIEWER_BACKEND = `claude-review`** — reviews route through the claude-review MCP (Claude family; cross-family for a Codex executor).

## Instructions

Parse `mode: problem|method|combined`. Default to `combined` only when both are
present; otherwise infer and report the applicable mode. Follow
[`problem-discovery-contract.md`](../shared-references/problem-discovery-contract.md)
and keep problem novelty separate from method novelty.
`mode: method-final` is a final-method alias and may run only on the refined
`FINAL_PROPOSAL.md`, not on preliminary routes.

Apply
[`source-admission-policy.md`](../shared-references/source-admission-policy.md)
before reading or expanding any candidate paper.

### Phase A: Extract Key Claims
1. For `problem|combined`, extract problem claims: phenomenon, setting,
   failure/boundary, causal framing, importance, and research question.
2. For `method|combined`, extract the falsifiable hypothesis, intended
   scientific delta, dominant method, backbone, innovation carrier, supporting
   mechanisms, integration interfaces, targeted evidence, and technical delta.
3. Assign separate IDs (`P1...`, `M1...`).

### Phase B: Controller-Governed Literature Search
For each applicable claim:

1. In a formal run, use a pending phase's `submit_query_plan` Controller action,
   then only the existing query, admission, read and evidence actions. Never
   use hosted web search/fetch or a private corpus/ledger.
2. Use `problem_novelty_gate` or `final_method_novelty_gate` as appropriate and
   finish reading before starting the Gate; newly accepted Evidence Card hashes
   are bound by the Controller to its request.
3. Read only `ADMIT_DECISION_GRADE` or `USER_SUPPLIED_READ` content; discovery
   records remain metadata, never scientific evidence.

### Phase C: Fresh-Agent Verification (cross-family accepted by default)
Call REVIEWER_MODEL via `mcp__claude-review__review_start` with high-rigor review:
```
mcp__claude-review__review_start:
  prompt: |
    [Full novelty briefing + prior work list + specific novelty questions]
```

After this start call, immediately save the returned `jobId` and poll `mcp__claude-review__review_status` with a bounded `waitSeconds` until `done=true`. Treat the completed status payload's `response` as the reviewer output, and save the completed `threadId` for any follow-up round.
Prompt should include:
- mode and separate problem/method claim lists
- All papers found in Phase B
- Ask for independent problem and/or method verdicts, closest prior framing or
  route, residual delta, and confidence. In combined mode, one verdict cannot
  substitute for the other.

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
- Residual scientific delta and technical-route delta
- Scientific closure: actual interfaces, capability-specific removal failures,
  targeted evidence, and one causal chain
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
- "Applying X to Y" requires structural problem correspondence and a coherent
  new mechanism or understanding.
- In combined mode, report problem, scientific-delta, and technical-route
  novelty separately. A supporting mechanism is justified only for a declared
  residual `MUST` gap after Field-Map and same-field assessment; combination is
  not a novelty claim.
- If the method is not novel but the FINDING would be, say so explicitly
- Apply the Source Admission Gate without using recency as an eligibility gate.

## Review Tracing

After each `mcp__claude-review__review_start` or optional `oracle-pro` reviewer call, save the trace following `../shared-references/review-tracing.md`. Write files directly to `.aris/traces/novelty-check/<date>_run<NN>/` and record searched claims, closest papers, reviewer route, raw response, and final novelty decision. Respect the `--- trace:` parameter when present (default: `full`).
