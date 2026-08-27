---
name: novelty-check
description: Verify problem novelty, method novelty, or both against recent literature. Use when user says "查新", "novelty check", "有没有人做过", "check novelty", or wants to verify a research problem or method before committing.
argument-hint: "[mode: problem|method|combined] [problem-or-method-description]"
allowed-tools: Grep, Read, Glob, mcp__codex__codex
---

# Novelty Check Skill

Check whether a proposed problem framing and/or method has already been
established in the literature: **$ARGUMENTS**

## Constants

- REVIEWER_MODEL = `gpt-5.6-sol` — Model used via Codex MCP. Must be an OpenAI model (e.g., `gpt-5.6-sol`, `o3`, `gpt-4o`)

## Instructions

Parse `mode: problem|method|combined` from the arguments. Default to `combined`
when both a problem and method are present; otherwise infer the only applicable
mode and state that inference. Follow
[`problem-discovery-contract.md`](../shared-references/problem-discovery-contract.md)
for problem mode and
[`method-design-contract.md`](../shared-references/method-design-contract.md)
for method mode. Never collapse problem novelty, scientific-delta novelty, and
technical-route novelty.

`mode: method-final` is an explicit final-method alias. It accepts only
`refine-logs/FINAL_PROPOSAL.md`, runs after refinement, and must not be treated
as the preliminary method-risk screen.

For the formal final-method Gate, `idea-stage/FINAL_METHOD_NOVELTY_VERDICT.md`
must contain exactly one fenced JSON metadata block with `schema_version: 1`,
the live `review_request_id`, `reviewer`, `verdict_id`, `decision: NOVEL`, and
the exact `reviewed_artifact_hashes` map for `FINAL_PROPOSAL.md`.

Apply
[`source-admission-policy.md`](../shared-references/source-admission-policy.md)
before reading or expanding any candidate paper.

### Phase A: Extract Key Claims
1. Extract **problem claims** when mode is `problem` or `combined`:
   phenomenon, setting/population, boundary or failure, causal framing,
   importance, and the precise research question.
2. Extract **method claims** when mode is `method` or `combined`: falsifiable
   hypothesis, intended scientific delta, dominant method, reused backbone,
   innovation carrier, supporting mechanisms, integration interfaces, targeted
   evidence, and claimed technical-route delta.
3. Keep separate claim IDs (`P1...` and `M1...`).

### Phase B: Controller-Governed Literature Search
For each applicable claim:

1. For a formal run, ask `arisctl allowed-actions`. If the pending phase exposes
   `submit_query_plan`, submit the claim-specific formulations there, then use
   only the existing Controller `query`, `admit`, `read-*`, and
   `submit-evidence` actions. Do not use WebSearch, WebFetch, hosted pages, or
   a private corpus/ledger.
2. Problem novelty uses its pending `problem_novelty_gate`; final method novelty
   uses its pending `final_method_novelty_gate`. Finish the existing reading
   flow before starting that Gate. The Controller binds newly accepted Evidence
   Card hashes to the live Gate request.
3. Retrieve admission metadata only through that gateway. Read only
   `ADMIT_DECISION_GRADE` or `USER_SUPPLIED_READ` content; retain discovery-only
   and blocked records as metadata with uncertainty, never scientific evidence.
4. For non-formal/ad-hoc work, state that web findings are provisional and
   cannot be promoted into a formal ARIS artifact.

### Phase C: Cross-Model Verification
Call REVIEWER_MODEL via Codex MCP (`mcp__codex__codex`) with xhigh reasoning.
When the method description plus the Phase-B paper list is more than a short
note, avoid pasting it inline into the MCP prompt. Write a dossier file such as
`NOVELTY_DOSSIER.md` (or a project-local equivalent) containing the method
description, core claims, candidate papers, and the exact questions below, then
send only the file path:
```
mcp__codex__codex:
  model: gpt-5.6-sol
  config: {"model_reasoning_effort": "xhigh"}
  prompt: |
    Read the novelty dossier at <absolute path to NOVELTY_DOSSIER.md> and
    follow all instructions in it.
```
Dossier contents should include:
- mode and the separate problem/method claim lists
- all papers found in Phase B, with verified identifiers or `[UNVERIFIED]`
- for problem mode: ask whether the phenomenon and research-question framing
  are already established, and what unresolved delta remains
- for method mode: ask separately whether the scientific delta and technical
  route are established; assess any combination only as necessary support for a
  declared residual `MUST` gap, never as evidence of novelty
- for combined mode: require two independent verdicts; a novel method cannot
  rescue a non-novel problem framing, and vice versa

### Phase D: Novelty Report
Output a structured report:

```markdown
## Novelty Check Report

### Mode
problem / method / combined

### Problem Novelty
- **Problem statement**: [...]
- **Problem claims**: [P1...]
- **Closest existing framing**: [...]
- **Residual unresolved delta**: [...]
- **Verdict**: HIGH / MEDIUM / LOW / BLOCKED
- **Confidence and evidence gaps**: [...]

### Method Novelty
- **Scientific hypothesis and intended delta**: [...]
- **Method embodiment**: [dominant method + backbone + innovation carrier]
- **Supporting-mechanism integration (if any)**: [residual MUST gap served,
  Field-Map/same-field assessment, and for any cross-field support: structural
  match, actual interface, targeted responsibility]
- **Method claims**: [M1...]
- **Closest existing route**: [...]
- **Residual scientific delta**: [...]
- **Residual technical-route delta**: [...]
- **Scientific closure**: [single causal chain, capability-specific removal
  failures, targeted evidence]
- **Verdict**: HIGH / MEDIUM / LOW / BLOCKED
- **Confidence and evidence gaps**: [...]

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
[Accurate positioning without inflating either novelty dimension]
```

### Important Rules
- Be BRUTALLY honest — false novelty claims waste months of research time
- A supporting mechanism is justified only when it closes a declared residual
  `MUST` gap after Field-Map and same-field options have been assessed;
  combination itself is not a novelty claim.
- "Applying X to Y" is novel only when structures match, integration is real,
  and the route creates a scientific delta.
- In combined mode, report problem and method novelty separately.
- If the method is not novel but the FINDING would be, say so explicitly
- Apply the Source Admission Gate without using recency as an eligibility gate.
- If a low-citation, non-elite, or just-published paper is a potentially
  decisive closest/concurrent prior, invoke the existing
  `decisive_closest_prior_or_concurrent` admission exception and obtain its
  decision-grade Evidence Card whose source ID is that same prior. If that verification cannot be completed, the
  problem verdict is `UNCERTAIN`, never `NOVEL`.
- **Anti-hallucination for Closest Prior Work.** The Source Admission Gate takes
  precedence: if admission metadata cannot be verified, keep the paper
  discovery-only or blocked. For an admitted paper, run `verify_papers.py` (canonical name resolved
  per [`shared-references/integration-contract.md`](../shared-references/integration-contract.md)
  §2). If only this identifier helper fails, tag the citation `[UNVERIFIED]` and
  surface the uncertainty. Never fabricate arXiv IDs, DOIs, or titles. Full
  protocol:
  [`citation-discipline.md`](../shared-references/citation-discipline.md).

## Review Tracing

After each `mcp__codex__codex` or `mcp__codex__codex-reply` reviewer call, save the trace following `shared-references/review-tracing.md` (Policy C — forensic; never silently skip). Use `save_trace.sh` (resolved per the chain in `shared-references/integration-contract.md` §2) or write files directly to `.aris/traces/<skill>/<date>_run<NN>/`. Respect the `--- trace:` parameter (default: `full`).
