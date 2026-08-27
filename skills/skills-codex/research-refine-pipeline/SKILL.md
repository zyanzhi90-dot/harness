---
name: "research-refine-pipeline"
description: "Chain `research-refine` and `experiment-plan` for an already Certified Problem Contract. Use when the user wants a problem-grounded method proposal plus a detailed experiment roadmap. For a vague direction, run `idea-discovery` first."
---

# Research Refine Pipeline: End-to-End Method and Experiment Planning

Refine and concretize: **$ARGUMENTS**

## Overview

Use this skill when the user does not want to stop at a refined method. The goal is to produce a coherent package that includes:

- a Certified-Problem-Contract-grounded, coherent final proposal
- the review history explaining why the method is focused
- a detailed experiment roadmap tied to the paper's claims
- a compact pipeline summary that says what to run next

This skill composes two existing workflows:

1. `research-refine` for method refinement
2. `experiment-plan` for claim-driven validation planning

For stage-specific detail, read these sibling skills only when needed:

- `../research-refine/SKILL.md`
- `../experiment-plan/SKILL.md`

## Core Rule

Require a CERTIFIED problem and a hash-matched `DIAGNOSIS_READY` root-cause
handoff before method refinement. Do not plan a large experiment suite on an
unstable route; preserve separate problem/diagnosis/method verdicts.

## Default Outputs

- `refine-logs/FINAL_PROPOSAL.md`
- `refine-logs/REVIEW_SUMMARY.md`
- `refine-logs/REFINEMENT_REPORT.md`
- `refine-logs/EXPERIMENT_PLAN.md`
- `refine-logs/EXPERIMENT_TRACKER.md`
- `refine-logs/PIPELINE_SUMMARY.md`

## Workflow

### Phase 0: Triage the Starting Point

- Extract the Certified Problem Contract, validated root-cause analysis/verdict,
  primary causal-chain IDs, any provisional design obligations, rough route,
  constraints, resources, and target venue.
- If the problem is not `CERTIFIED/accepted`, or is
  absent/HOLD/REJECT/BLOCKED, return to `/idea-discovery`.
- If the root-cause verdict is not `DIAGNOSIS_READY` or any bound hash changed,
  do not enter refinement. Let the Controller apply only
  `REVISE_DIAGNOSIS -> root_cause_analysis` or
  `REOPEN_PROBLEM -> problem_generation`.
- Reuse an existing proposal only when `REFINE_STATE.json` records matching
  schema version, Certified Problem Contract and root-cause handoff hashes,
  primary causal-chain IDs, scope/constraint hash,
  proposal hash, blind-verdict ID, and acceptance status.
- If the proposal is missing, stale, or materially different from the current request, run the full `research-refine` stage.
- If the proposal is already strong and aligned, reuse it and jump to experiment planning.
- If in doubt, prefer re-running `research-refine` rather than planning experiments for the wrong method.

### Phase 1: Method Refinement Stage

Run `research-refine` with its current problem-discovery contract:

- preserve the Certified Problem Contract;
- re-derive or verify Design Obligations after the Scientific Mainline;
- state one falsifiable scientific hypothesis and intended scientific delta;
- keep one dominant method and distinguish its reused backbone from its
  innovation carrier;
- after dominant-only closure leaves a residual `MUST` gap, check the Field Map
  and same-field mechanisms first; use cross-field structural search only if
  they cannot reasonably close that gap, then require actual integration
  interfaces, targeted evidence, and one scientific closure.

Exit this stage only when these are explicit:

- the scientific mainline, dominant method, backbone, and innovation carrier
- the supporting-mechanism and scientific-closure ledgers
- the key claims and targeted mechanism tests
- the remaining risks, if any

Use this transition table:

- `READY/accepted` with no blocker -> full experiment planning;
- `REVISE` -> only a minimal diagnostic plan tied to named blocking issue IDs;
- `RETHINK` or `HOLD` -> stop and return to method or problem refinement.

### Phase 2: Planning Gate

Before the experiment stage, write a short gate check:

- What is the falsifiable hypothesis and intended scientific delta?
- What is the dominant method, reused backbone, and innovation carrier?
- What causal link does each support close, through what interface?
- What capability-specific removal failure and targeted test isolate each support?
- Which reviewer concerns still matter for validation?
- Are transfer structure, interfaces, assumptions, and causal story coherent?
- Are causal-identification and validity contracts complete for the intended
  claim strength?

If these answers are not crisp, tighten the final proposal first.

### Phase 3: Experiment Planning Stage

Run the `experiment-plan` workflow grounded in:

- `refine-logs/FINAL_PROPOSAL.md`
- `refine-logs/REVIEW_SUMMARY.md`
- `refine-logs/REFINEMENT_REPORT.md`

Ensure the experiment plan covers:

- the main anchor result
- novelty isolation
- a capability-specific removal or counterfactual test
- a scientific-delta and claim-necessity test
- run order, budget, and decision gates

### Phase 4: Integration Summary

Write `refine-logs/PIPELINE_SUMMARY.md`:

```markdown
# Pipeline Summary

**Certified Problem**: [question, scope, verdict]
**Final Method Thesis**: [one sentence]
**Final Verdict**: [READY / REVISE / RETHINK]
**Date**: [today]

## Final Deliverables
- Proposal: `refine-logs/FINAL_PROPOSAL.md`
- Review summary: `refine-logs/REVIEW_SUMMARY.md`
- Experiment plan: `refine-logs/EXPERIMENT_PLAN.md`
- Experiment tracker: `refine-logs/EXPERIMENT_TRACKER.md`

## Contribution Snapshot
- Scientific mainline and intended delta:
- Dominant method / backbone / innovation carrier:
- Natural combination and supporting-mechanism ledger:
- Scientific closure and targeted evidence:
- Explicitly rejected redundancy:

## Must-Prove Claims
- [Claim 1]
- [Claim 2]

## First Runs to Launch
1. [Run]
2. [Run]
3. [Run]

## Main Risks
- [Risk]:
- [Mitigation]:

## Next Action
- [READY/accepted: request execution approval | REVISE: resolve issue IDs |
  RETHINK/HOLD: stop]
```

### Phase 5: Present a Brief Summary to the User

```
Pipeline complete.

Method output:
- refine-logs/FINAL_PROPOSAL.md

Experiment output:
- refine-logs/EXPERIMENT_PLAN.md
- refine-logs/EXPERIMENT_TRACKER.md

Pipeline summary:
- refine-logs/PIPELINE_SUMMARY.md

Best next step:
- [conditional on the transition table; never assume execution approval]
```

## Output Protocols

> Follow these shared protocols for all output files:
> - **[Output Versioning Protocol](../shared-references/output-versioning.md)** — write timestamped file first, then copy to fixed name
> - **[Output Manifest Protocol](../shared-references/output-manifest.md)** —
>   create `MANIFEST.md` only when the run exceeds 15 artifacts
> - **[Output Language Protocol](../shared-references/output-language.md)** — respect the project's language setting

## Key Rules

- **Large file handling**: If the Write tool fails due to file size, immediately retry using Bash (`cat << 'EOF' > file`) to write in chunks. Do NOT ask the user for permission — just do it silently.

- Do not let the experiment plan override the Certified Problem Contract or
  merge problem and method verdicts.
- Do not widen the paper story after method refinement unless a missing validation block is truly necessary.
- Reuse the same claims across `FINAL_PROPOSAL.md`, `EXPERIMENT_PLAN.md`, and `PIPELINE_SUMMARY.md`.
- Keep one falsifiable scientific mainline and one dominant method.
- Use combination only when it is necessary to close a declared residual `MUST`
  gap; do not count it as innovation. Require structural match, actual
  integration interfaces, targeted evidence, and scientific delta.
- Prefer the staged skills when the user only needs one stage; use this skill for the integrated flow.

## Composing with Other Skills

```
/research-refine-pipeline -> one-shot method + experiment planning
/research-refine   -> method refinement only
/experiment-plan   -> experiment planning only
/run-experiment    -> execution
```
