---
name: research-review
description: Get a deep critical review of research from GPT using a secondary Codex agent. Use when user says "review my research", "help me review", "get external review", or wants critical feedback on research ideas, papers, or experimental results.
argument-hint: "[topic-or-scope]"
---

# Research Review via a secondary Codex agent (ultra reasoning)

> **Codex assurance:** the fresh base reviewer is same-family. Record
> `review_independence: same-family` and `acceptance_status: provisional` in
> traces and deliverables. A Claude/Gemini overlay may record cross-family
> accepted; an unavailable reviewer is BLOCKED, never a fabricated PASS.

> 🔒 **Do not wrap this skill in `/loop`, `/schedule`, or `CronCreate`.** It is
> verdict-bearing — it produces a cross-model review verdict, multi-round with
> reviewer thread continuity. An external timer re-fires the verdict on
> wall-clock time and breaks the reviewer's round-to-round memory: zero new
> signal, full token cost. Schedule the *external wait that precedes it* (work
> ready → then review once), not the verdict. See
> [`shared-references/external-cadence.md`](../shared-references/external-cadence.md).

Get a multi-round critical review of research work from a fresh secondary Codex
agent with maximum reasoning depth.

## Constants

- REVIEWER_MODEL = `gpt-5.6-sol` — Model used via a secondary Codex agent, reasoning effort `ultra` (deep-audit tier). Must be an OpenAI model (e.g., `gpt-5.6-sol`, `gpt-5.5`, `o3`).
- **REVIEWER_BACKEND = `codex`** — Default: Codex ultra reviewer. Use `--reviewer: oracle-pro` only when explicitly requested; if Oracle is unavailable, warn and fall back to Codex at this skill's declared tier (`ultra`). **Same-family note:** this default reviewer is a second Codex/GPT agent — valid for Type-A completeness/drive review, but not a cross-family Type-B verdict; install a `skills-codex-claude-review` / `skills-codex-gemini-review` overlay for a cross-family acquittal (see `shared-references/reviewer-routing.md`).

## Reviewer Calling Convention

Start a fresh review with `spawn_agent` and continue the same review with
`send_input` using the returned agent ID. Keep full briefs in project-local
files and pass their absolute paths so the reviewer can verify artifacts.

## Context: $ARGUMENTS

Parse `stage: problem|principle|method|project` from the arguments. Default to `project`
for an existing complete work. When an orchestrator passes an explicit stage,
review only that stage's decision; do not ask a method to compensate for a weak
problem, collapse Principle truth into Method novelty, or reject a certified
problem merely because one Candidate Principle or Method adaptation is weak.
Use the stage contracts in
[`problem-discovery-contract.md`](../shared-references/problem-discovery-contract.md).
For `stage: principle` or `stage: method`, also load
[`method-design-contract.md`](../shared-references/method-design-contract.md).

## Prerequisites

- Use `spawn_agent` and `send_input` when delegation or subagents are allowed.

## Workflow

### Step 1: Gather Research Context
Before calling the external reviewer, compile a comprehensive briefing:
1. Read project narrative documents (e.g., STORY.md, README.md, paper drafts)
2. Read any memory/notes files for key findings and experiment history
3. For `stage: problem`, include the Evidence Map, exact research question,
   source class, scope, value if yes/no, decisive falsifier, and P3 gate record.
4. For `stage: principle`, include the accepted RCA, RMC/Capability/Obligation
   bindings, Principle Search record, Candidate versions, fatal assumptions,
   Provisional Scientific Delta, multi-target predictions/tests, current
   Evidence Context or Evidence Update when applicable, and return feedback.
5. For `stage: method`, include the Controller-materialized Selected Principle,
   target-domain adaptation, minimal faithful realization, Principle-only
   closure, residual gaps, minimal necessary composition, Final Scientific
   Delta Claim, boundaries, and claim-validation obligations.
6. For `stage: project`, identify core claims, methodology, key results, and
   known weaknesses as before.

### Step 2: Initial Review (Round 1)
Send a detailed prompt with ultra reasoning. Keep the tool payload short: write
the full briefing to `RESEARCH_REVIEW_REQUEST.md`, then point the fresh Codex
agent at that file.

```
spawn_agent:
  model: gpt-5.6-sol
  reasoning_effort: ultra
  message: |
    Read the review brief at <absolute path to RESEARCH_REVIEW_REQUEST.md>.
    Executor notes are not evidence beyond the files they cite, so verify the
    referenced artifacts before judging.
    Please act as a senior top-venue reviewer. Respect the stage declared in
    the brief. Start from the
    assumption that the work is broken somewhere — your job is to find where.
    Be adversarial. Trust nothing the author tells you — verify everything
    yourself.
    For stage=problem, score Reality, Importance, Unresolvedness, Precision,
    Falsifiability, and Answerability; return CERTIFIED / HOLD / REJECT /
    BLOCKED plus the decisive missing evidence.
     For stage=principle, judge the RCA-to-RMC-to-Capability/Obligation-to-
     Principle closure, algorithm independence, four-dimension search,
     cross-domain structural mappings, premature closure, fatal assumptions,
     multi-target discriminating predictions/tests, Evidence currentness, and
     whether an Evidence Update changes scientific understanding rather than
     only performance ranking. Do not interpret NO_RESULT as support/rejection.
     For stage=method, verify fidelity to the Controller-materialized Selected
     Principle, target adaptation, minimal faithful realization,
     Principle-only closure, named residual gaps, minimal necessary composition,
     bounded Final Scientific Delta Claim, and mechanism-linked validation
     obligations. Do not call the Claim established before VALIDATED.
    For stage=project, identify logical gaps, missing evidence, narrative
    weaknesses, and top-venue sufficiency as usual.
    Please be brutally honest.
```

The review brief should contain the full research context, the specific
questions, and the primary artifact / raw-result paths the reviewer should
inspect. Save the returned agent ID.

### Step 3: Iterative Dialogue (Rounds 2-N)
Use `send_input` with the returned agent ID to continue the conversation. For
follow-up rounds, write an updated brief such as
`RESEARCH_REVIEW_ROUND_2.md` and send only the path:

```text
send_input:
  id: [saved reviewer agent ID from Step 2]
  message: |
    Read the updated review brief at <absolute path to
    RESEARCH_REVIEW_ROUND_2.md>.
    Focus on unresolved weaknesses and whether the revision actually fixed them.
```

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
- `stage: problem`: a stable P3 verdict and the evidence required to change it
  are explicit.
- `stage: principle`: Candidate status, unresolved assumptions, Evidence
  interpretation, and the next discriminating decision are explicit.
- `stage: method`: Selected-Principle fidelity, residual gaps, concrete Method
  verdict, Claim boundaries, and decisive validation obligations are explicit.
- `stage: project`: core claims, evidence requirements, experiment plan, and
  narrative structure are settled.

### Step 5: Document Everything
Save the full interaction and conclusions to a review document in the project root:
- Round-by-round summary of criticisms and responses
- Declared stage and stage-specific verdict
- Separate problem-quality/problem-novelty and method-quality/method-novelty
  conclusions when both appear
- Final consensus on claims, narrative, and experiments where applicable
- Claims matrix (what claims are allowed under each possible outcome)
- Prioritized TODO list with estimated compute costs
- Paper outline if discussed

Update project memory/notes with key review conclusions.

> **Composed mode** — if invoked with `— composed: <canonical-report-path>` (an
> orchestrator like `/idea-discovery` passes this), do **not** write a standalone review
> `.md` in the project root. The raw conversation is already persisted to `.aris/traces/…`
> (see *Review Tracing* below — that audit copy is kept in every mode); fold the review
> *conclusions* (consensus, claims matrix, prioritized TODOs) into the orchestrator's
> canonical report and cite the trace path there. **Default (no `— composed:` directive):
> behave exactly as above — write the standalone review document.** Never infer composed
> mode from a report file merely existing. Full rules:
> [`shared-references/output-composition.md`](../shared-references/output-composition.md).

## Key Rules

- ALWAYS use `model: gpt-5.6-sol` + `reasoning_effort: ultra` for reviews (deep-audit tier; capability fallback per `reviewer-routing.md`, never below `xhigh`)
- Put comprehensive context in the review brief. Codex can read local files
  when you pass an absolute path; manual reviewers usually cannot, so attach or
  paste the same brief there.
- Be honest about weaknesses — hiding them leads to worse feedback
- Push back on criticisms you disagree with, but accept valid ones
- Focus on ACTIONABLE feedback — "what experiment would fix this?"
- Preserve stage separation: a problem verdict and a method verdict are
  different decisions.
- Document the reviewer agent ID for potential future resumption
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

## Review Tracing

After each `spawn_agent`, `send_input`, or optional `oracle-pro` review call, save the trace following `../shared-references/review-tracing.md` (Policy C — forensic; never silently skip). Use `save_trace.sh` (resolved per the chain in `../shared-references/integration-contract.md` §2) or write files directly to `.aris/traces/research-review/<date>_run<NN>/`. Respect the `--- trace:` parameter (default: `full`).
