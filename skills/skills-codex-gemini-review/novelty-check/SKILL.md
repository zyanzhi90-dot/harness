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

Parse `mode: problem|method|method-final|combined`. Follow
[`problem-discovery-contract.md`](../shared-references/problem-discovery-contract.md)
for problem mode and
[`method-design-contract.md`](../shared-references/method-design-contract.md)
for method mode. Never collapse problem novelty, Principle/Scientific-Delta
novelty, and concrete Method embodiment novelty. `mode: method-final` is the
formal final-method alias and accepts only the Controller-bound Selected
Principle, `FINAL_PROPOSAL.md`, and final independent review. Non-final
`mode: method` is only an advisory risk screen.

For the formal final-method Gate,
`idea-stage/FINAL_METHOD_NOVELTY_VERDICT.md` contains exactly one fenced JSON
metadata block with `schema_version: 1`, the live `review_request_id`,
`reviewer`, `verdict_id`, a Controller-declared `decision: NOVEL |
REVISE_METHOD_DELTA | RETHINK_PRINCIPLE_DELTA | HOLD`, and the exact
`reviewed_artifact_hashes` map for `FINAL_PROPOSAL.md`.

Apply
[`source-admission-policy.md`](../shared-references/source-admission-policy.md)
before reading or expanding any candidate paper.

### Phase A: Extract Key Claims
1. For `problem|combined`, extract phenomenon, setting, failure/boundary,
   causal framing, importance, and research question as `P1...`.
2. For non-final `method`, extract Candidate Principle/version, RMC/Capability/
   Obligation bindings, Provisional Scientific Delta, activation/failure
   conditions, fatal assumptions, predictions/tests, and Evidence scope.
3. For `method-final`, extract the Selected Principle, target adaptation,
   minimal faithful realization, Principle-only closure, residual gaps, minimal
   necessary composition, failure/applicability boundaries, Final Scientific
   Delta Claim, claim-validation obligations, and embodiment delta as `M1...`.

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
- Ask for independent problem/method verdicts, closest framing/Principle or
  embodiment, residual delta, and confidence. For final method mode, identify
  whether failure is at the Principle/Scientific-Delta layer or only at target
  adaptation, embodiment, Claim formulation, or boundaries. Composition is
  support for a demonstrated residual gap, never novelty by itself. One verdict
  cannot substitute for the other.
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
- Candidate/Selected Principle and Evidence-supported scope
- Target adaptation and minimal faithful realization
- Principle-only closure and residual gaps
- Minimal necessary composition, with gap served, actual interface, activation
  conditions, and removal/counterfactual responsibility
- Final Scientific Delta Claim and M-claims
- Closest existing Principle/embodiment, residual scientific delta, and
  residual embodiment delta
- Failure layer: none / Principle-Scientific-Delta /
  adaptation-embodiment-Claim / novelty-Evidence-only
- Validation obligations and boundaries
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
[Accurate positioning without inflating either novelty dimension]
```

### Important Rules
- Be BRUTALLY honest — false novelty claims waste months of research time
- A supporting mechanism is justified only when it closes a demonstrated
  residual adaptation/mechanism gap after the Principle-only closure attempt;
  composition itself is not a novelty claim.
- "Applying X to Y" is novel only when the selected Principle's structural
  mapping and target adaptation create a real scientific or embodiment delta.
- In combined mode, report problem and method novelty separately.
- For the formal final Gate, map adaptation/embodiment/Claim/boundary failure
  to `REVISE_METHOD_DELTA`, Principle/Scientific-Delta failure to
  `RETHINK_PRINCIPLE_DELTA`, and missing novelty Evidence or interpretation to
  `HOLD`. Do not reject a Principle merely because its concrete realization is
  insufficiently novel.
- If the method is not novel but the FINDING would be, say so explicitly
- Apply the Source Admission Gate without using recency as an eligibility gate.
