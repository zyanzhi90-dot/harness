---
name: "research-review"
description: "Get a deep critical review of research from Gemini via gemini-review MCP. Use when user says \"review my research\", \"help me review\", \"get external review\", or wants critical feedback on research ideas, papers, or experimental results."
---

> Override for Codex users who want **Gemini**, not a second Codex agent, to act as the reviewer. Install this package **after** `skills/skills-codex/*`.

# Research Review via `gemini-review` MCP (high-rigor review)

> **Gemini overlay assurance:** `review_independence: cross-family` and `acceptance_status: accepted`.

Get a multi-round critical review of research work from an external LLM with maximum reasoning depth.

## Constants

- **REVIEWER_MODEL = `gemini-review`** — Gemini reviewer invoked through the local `gemini-review` MCP bridge. Set `GEMINI_REVIEW_MODEL` if you need a specific Gemini model override.

## Context: $ARGUMENTS

Parse `stage: problem|principle|method|project`. Default to `project`. When
explicit, review only that stage; do not ask a Method to compensate for a weak
problem, collapse Principle truth into Method novelty, or reject a certified
problem because one Principle/Method is weak. Load
[`problem-discovery-contract.md`](../shared-references/problem-discovery-contract.md)
and, for `principle|method`,
[`method-design-contract.md`](../shared-references/method-design-contract.md).

## Prerequisites

- Install the base Codex-native skills first: copy `skills/skills-codex/*` into `~/.codex/skills/`.
- Then install this overlay package: copy `skills/skills-codex-gemini-review/*` into `~/.codex/skills/` and allow it to overwrite the same skill names.
- Register the local reviewer bridge:
  ```bash
  codex mcp add gemini-review -- python3 ~/.codex/mcp-servers/gemini-review/server.py
  ```
- This gives Codex access to `mcp__gemini-review__review_start`, `mcp__gemini-review__review_reply_start`, and `mcp__gemini-review__review_status`.


## Workflow

### Step 1: Gather Research Context
Before calling the external reviewer, compile a comprehensive briefing:
1. Read project narrative documents (e.g., STORY.md, README.md, paper drafts)
2. Read any memory/notes files for key findings and experiment history
3. For `problem`, include Evidence Map, question, source class, scope, value if
   yes/no, falsifier, and P3 record.
4. For `principle`, include accepted RCA, RMC/Capability/Obligation bindings,
   Principle Search, Candidate lineage, fatal assumptions, Provisional
   Scientific Delta, multi-target predictions/tests, current Evidence Context
   or Evidence Update, and return feedback.
5. For `method`, include the Controller-materialized Selected Principle, target
   adaptation, minimal faithful realization, Principle-only closure, residual
   gaps, minimal necessary composition, Final Scientific Delta Claim,
   boundaries, and claim-validation obligations.
6. For `project`, include claims, methods, results, and weaknesses.

### Step 2: Initial Review (Round 1)
Send a detailed prompt with high-rigor review:

```
mcp__gemini-review__review_start:
  prompt: |
    [Full research context + specific questions]
    Please act as a senior top-venue reviewer and respect the declared stage.
    For problem stage, score Reality, Importance, Unresolvedness, Precision,
    Falsifiability, and Answerability; return CERTIFIED/HOLD/REJECT/BLOCKED.
    For principle stage, judge RCA-to-RMC-to-Capability/Obligation-to-Principle
    closure, algorithm independence, the four search dimensions, cross-domain
    structural mappings, fatal assumptions, multi-target discriminating tests,
    Evidence currentness, and whether Evidence Update changes scientific
    understanding rather than only performance ranking. NO_RESULT is not
    support or rejection.
    For method stage, verify fidelity to the Controller-materialized Selected
    Principle, target adaptation, minimal faithful realization, Principle-only
    closure, named residual gaps, minimal necessary composition, bounded Final
    Scientific Delta Claim, boundaries, and mechanism-linked validation
    obligations. Do not call the Claim established before VALIDATED.
    For project stage, review logic, evidence, narrative, and venue sufficiency.
    Please be brutally honest.
```

After this start call, immediately save the returned `jobId` and poll `mcp__gemini-review__review_status` with a bounded `waitSeconds` until `done=true`. Treat the completed status payload's `response` as the reviewer output, and save the completed `threadId` for any follow-up round.

### Step 3: Iterative Dialogue (Rounds 2-N)
Use `mcp__gemini-review__review_reply_start` with the saved completed `threadId`, then poll `mcp__gemini-review__review_status` with the returned `jobId` until `done=true` to continue the conversation:

For each round:
1. **Respond** to criticisms with evidence/counterarguments
2. **Ask targeted follow-ups** on the most actionable points
3. **Request specific deliverables**: experiment designs, paper outlines, claims matrices

Key follow-up patterns:
- "If we reframe X as Y, does that change your assessment?"
- "What's the minimum experiment to satisfy concern Z?"
- "Please design the minimal additional experiment package (highest acceptance lift per GPU week)"
- "Please write a mock NeurIPS/ICML review with scores"
- "Give me a results-to-claims matrix for possible experimental outcomes"

### Step 4: Convergence
Stop iterating when:
- problem stage: stable P3 verdict and decisive missing evidence are explicit
- principle stage: Candidate status, unresolved assumptions, Evidence
  interpretation, and the next discriminating decision are explicit
- method stage: Selected-Principle fidelity, residual gaps, concrete Method
  verdict, Claim boundaries, and decisive validation obligations are explicit
- project stage: claims, evidence, plan, and narrative are settled

### Step 5: Document Everything
Save the full interaction and conclusions to a review document in the project root:
- Round-by-round summary of criticisms and responses
- Declared stage and stage-specific verdict
- Separate problem and method conclusions whenever both appear
- Final consensus on claims, narrative, and experiments where applicable
- Claims matrix (what claims are allowed under each possible outcome)
- Prioritized TODO list with estimated compute costs
- Paper outline if discussed

Update project memory/notes with key review conclusions.

## Key Rules

- Always ask the Gemini reviewer for strict, high-rigor feedback.
- Send comprehensive context in Round 1 — the external model cannot read your files
- Be honest about weaknesses — hiding them leads to worse feedback
- Push back on criticisms you disagree with, but accept valid ones
- Focus on ACTIONABLE feedback — "what experiment would fix this?"
- Preserve stage separation: problem, Principle, and Method verdicts are
  distinct decisions.
- Document the completed `threadId` for potential future resumption
- The review document should be self-contained (readable without the conversation)

## Prompt Templates

### For initial review:
"I'm going to present a complete ML research project for your critical review. Please act as a senior ML reviewer (NeurIPS/ICML level)..."

### For experiment design:
"Please design the minimal additional experiment package that gives the highest acceptance lift per GPU week. Our compute: [describe]. Be very specific about configurations."

### For paper structure:
"Please turn this into a concrete paper outline with section-by-section claims and figure plan."

### For claims matrix:
"Please give me a results-to-claims matrix: what claim is allowed under each possible outcome of experiments X and Y?"

### For mock review:
"Please write a mock NeurIPS review with: Summary, Strengths, Weaknesses, Questions for Authors, Score, Confidence, and What Would Move Toward Accept."
