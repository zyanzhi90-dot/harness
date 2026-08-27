---
name: "novelty-check"
description: "Gemini cross-family verification of problem novelty, method novelty, or both against recent literature."
---

> Override for Codex users who want **Gemini**, not a second Codex agent, to act as the reviewer. Install this package **after** `skills/skills-codex/*`.

# Novelty Check Skill

> **Gemini overlay assurance:** `review_independence: cross-family` and `acceptance_status: accepted`.

Check whether a proposed problem framing and/or method is already established:
**$ARGUMENTS**

## Constants

- **REVIEWER_MODEL = `gemini-review`** — Gemini reviewer invoked through the local `gemini-review` MCP bridge. Set `GEMINI_REVIEW_MODEL` if you need a specific Gemini model override.

## Instructions

Parse `mode: problem|method|combined`. Follow
[`problem-discovery-contract.md`](../shared-references/problem-discovery-contract.md)
for problem mode and
[`method-design-contract.md`](../shared-references/method-design-contract.md)
for method mode. Keep problem, scientific-delta, and technical-route novelty
distinct.

Apply
[`source-admission-policy.md`](../shared-references/source-admission-policy.md)
before reading or expanding any candidate paper.

### Phase A: Extract Key Claims
1. For `problem|combined`, extract phenomenon, setting, failure/boundary,
   causal framing, importance, and research question as `P1...`.
2. For `method|combined`, extract falsifiable hypothesis, intended scientific
   delta, dominant method, backbone, innovation carrier, supporting mechanisms,
   integration interfaces, targeted evidence, and technical delta as `M1...`.

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

### Phase C: Cross-Model Verification
Call REVIEWER_MODEL via `mcp__gemini-review__review_start` with high-rigor review:
```
mcp__gemini-review__review_start:
  prompt: |
    [Full novelty briefing + prior work list + specific novelty questions]
```

After this start call, immediately save the returned `jobId` and poll `mcp__gemini-review__review_status` with a bounded `waitSeconds` until `done=true`. Treat the completed status payload's `response` as the reviewer output, and save the completed `threadId` for any follow-up round.
Prompt should include:
- mode and separate problem/method claim lists
- All papers found in Phase B
- Ask for independent problem/method verdicts, closest framing/route, residual
  delta, and confidence. One verdict cannot substitute for the other.
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
- Problem statement and P-claims
- Closest framing and residual unresolved delta
- Verdict: HIGH / MEDIUM / LOW / BLOCKED
- Confidence and evidence gaps

### Method Novelty
- Scientific hypothesis and intended delta
- Dominant method + backbone + innovation carrier and M-claims
- Supporting mechanisms, integration interfaces, and targeted responsibilities
- Closest route, residual scientific delta, and technical-route delta
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
- Key differentiator(s): [problem and method separately]
- Risk: [what a reviewer would cite as prior work]

### Suggested Positioning
[How to frame the contribution to maximize novelty perception]
```

### Important Rules
- Be BRUTALLY honest — false novelty claims waste months of research time
- A supporting mechanism is justified only when it closes a declared residual
  `MUST` gap after Field-Map and same-field options have been assessed;
  combination itself is not a novelty claim.
- "Applying X to Y" needs structural correspondence, real integration, and a
  scientific delta.
- In combined mode, report problem, scientific-delta, and technical-route
  novelty separately.
`mode: method-final` is a final-method alias and may run only on the refined
`FINAL_PROPOSAL.md`, not on preliminary routes.
- If the method is not novel but the FINDING would be, say so explicitly
- Apply the Source Admission Gate without using recency as an eligibility gate.
