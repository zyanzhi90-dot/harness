---
name: novelty-check
description: Verify problem novelty, method novelty, or both against recent literature. Use when user says "查新", "novelty check", "有没有人做过", "check novelty", or wants to verify a research problem or method before committing.
argument-hint: "[mode: problem|method|method-final|combined] [problem-or-method-description]"
allowed-tools: Grep, Read, Glob, mcp__codex__codex
---

# Novelty Check Skill

Check whether a proposed problem framing and/or method has already been
established in the literature: **$ARGUMENTS**

## Constants

- REVIEWER_MODEL = `gpt-5.6-sol` — Model used via Codex MCP. Must be an OpenAI model (e.g., `gpt-5.6-sol`, `o3`, `gpt-4o`)

## Instructions

Parse `mode: problem|method|method-final|combined` from the arguments. Default to `combined`
when both a problem and method are present; otherwise infer the only applicable
mode and state that inference. Follow
[`problem-discovery-contract.md`](../shared-references/problem-discovery-contract.md)
for problem mode and
[`method-design-contract.md`](../shared-references/method-design-contract.md)
for method mode. Never collapse problem novelty, Principle/Scientific-Delta
novelty, and concrete Method embodiment novelty.

`mode: method-final` is an explicit final-method alias. It accepts only
the active Controller-materialized `SELECTED_PRINCIPLE.yaml`, canonical
`refine-logs/FINAL_METHOD_PACKET.json`, accepted final method review, and the
current Gate's formal Evidence/context. `FINAL_PROPOSAL.md` is only a
deterministic Human view and is not a scientific input or compatibility
authority. This mode runs after refinement and must not be treated
as the preliminary method-risk screen. A non-final `mode: method` may assess a
Candidate Principle's Provisional Scientific Delta as an advisory risk screen;
it cannot emit the formal final-method verdict.

For the formal final-method Gate, `idea-stage/FINAL_METHOD_NOVELTY_VERDICT.md`
must contain exactly one fenced JSON metadata block with `schema_version: 1`,
the live `review_request_id`, `reviewer`, `verdict_id`, a Controller-declared
`decision: NOVEL | REVISE_METHOD_DELTA | RETHINK_PRINCIPLE_DELTA | HOLD`, and
the exact Controller-issued `reviewed_artifact_hashes` map containing the
canonical Final Method packet and its accepted scientific inputs.
Only `NOVEL` opens `top_venue_method_strength_gate`; this skill never opens the
final Human Gate directly.

Apply
[`source-admission-policy.md`](../shared-references/source-admission-policy.md)
before reading or expanding any candidate paper.

### Phase A: Extract Key Claims
1. Extract **problem claims** when mode is `problem` or `combined`:
   phenomenon, setting/population, boundary or failure, causal framing,
   importance, and the precise research question.
2. For non-final `mode: method`, extract Candidate Principle/version, RMC/
   Capability/Obligation bindings, activation/failure conditions, and
   Provisional Scientific Delta. Keep the result preliminary.
3. For `mode: method-final` (or combined input containing the accepted final
   artifacts), extract the Selected Principle and its Evidence-supported
   conditions; target-domain adaptation; minimal faithful realization;
   Principle-only closure; residual mechanism/adaptation gaps; minimal
   necessary composition; core and reused implementation elements;
   failure/applicability boundaries; Final Scientific Delta Claim;
   claim-validation obligations; and claimed embodiment delta.
   Make the core comparison explicit as Target intervention + Mechanism Delta
   + Scientific Delta + closest-prior causal equivalence. A mature or
   transferred Source primitive, small Target adaptation, or reused algorithm
   primitive is not by itself a failure; a new name, module, or architecture
   does not establish novelty over a causal-equivalent Target intervention.
4. Keep separate claim IDs (`P1...` and `M1...`).

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
- for preliminary method mode: assess the Candidate Principle's Provisional
  Scientific Delta without treating it as a final Claim; for final method mode:
  ask separately whether novelty failure is at the Principle/Scientific-Delta
  layer or only at the target adaptation, embodiment, Claim formulation, or
  boundary layer; assess composition only as support for a demonstrated
  residual adaptation/mechanism gap, never as novelty by itself
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
- **Candidate/Selected Principle and Evidence-supported scope**: [...]
- **Target adaptation and minimal faithful realization**: [...]
- **Principle-only closure and residual gaps**: [...]
- **Minimal necessary composition (if any)**: [gap served, actual interface,
  activation conditions, and removal/counterfactual responsibility]
- **Final Scientific Delta Claim**: [...]
- **Method claims**: [M1...]
- **Closest existing Principle / embodiment**: [...]
- **Residual scientific delta**: [...]
- **Residual embodiment delta**: [...]
- **Failure layer**: [none / Principle-Scientific-Delta / adaptation-embodiment-Claim / novelty-Evidence-only]
- **Validation obligations and boundaries**: [...]
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
- A supporting mechanism is justified only when it closes a demonstrated
  residual mechanism/adaptation gap after the Principle-only closure attempt;
  composition itself is not a novelty claim.
- "Applying X to Y" is novel only when the selected Principle's structural
  mapping and target adaptation create a real scientific or embodiment delta.
- In combined mode, report problem and method novelty separately.
- If the method is not novel but the FINDING would be, say so explicitly
- For the formal final Gate, map adaptation/embodiment/Claim/boundary failure to
  `REVISE_METHOD_DELTA`, Principle/Scientific-Delta failure to
  `RETHINK_PRINCIPLE_DELTA`, and missing novelty Evidence or interpretation to
  `HOLD`. Do not reject a Principle merely because its concrete realization is
  insufficiently novel.
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
