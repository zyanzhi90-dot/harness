---
name: "experiment-plan"
description: "Turn a refined research proposal or method idea into a detailed, claim-driven experiment roadmap. Use after `research-refine`, or when the user asks for a detailed experiment plan, ablation matrix, evaluation protocol, run order, compute budget, or paper-ready validation that supports the core problem, novelty, simplicity, and any LLM / VLM / Diffusion / RL-based contribution."
---

# Experiment Plan: Claim-Driven, Mechanism-Aware Validation

Refine and concretize: **$ARGUMENTS**

## Overview

Use this skill after the method is stable enough that the next question becomes: **what exact experiments should we run, in what order, to defend the paper?** If the user wants the full chain in one request, prefer `/research-refine-pipeline`.

The goal is not to generate a giant benchmark wishlist. The goal is to turn a proposal into a **claim -> evidence -> run order** roadmap that supports four things:

1. the method actually solves the anchored problem
2. the primary claimed contribution is real and focused
3. the method is elegant enough that extra complexity is unnecessary
4. any frontier-model-era component is genuinely useful, not decorative

For a formal ARIS final Method, performance is necessary but not enough: the
plan must also test the predicted mechanism or failure-phenomenon change that
links the Selected Principle, each Required Mechanism Change and Design
Obligation, and each core Method change to the validated RCA. This is Full
Validation planning, not the pre-convergence Principle-discrimination cycle and
not a new workflow phase or Gate.

## Execution Boundary

### Formal / canonical run — fail closed

If this invocation belongs to a Controller-managed run, first obtain the
current formal handoff and use **only** the paths and hashes it returns:

```bash
python -m arisctl --root . validation-handoff <run_id>
```

The command verifies the current run and directly binds the accepted Necessity,
RCA, Method Design requirements, Principle Evidence/convergence closure,
Controller-materialized Selected Principle, canonical
`FINAL_METHOD_PACKET.json`, Final Method review, Final Novelty verdict,
Top-Venue verdict, and Final Human acceptance. Consume its
`validation_obligations`, including the exact coverage set for assumptions,
conditions, predictions, feasibility debt, causal chains, RMCs,
Capabilities/Design Obligations, core Method changes, Mechanism Delta, DAG
edges, counterfactuals, claim elements, and boundaries/restrictions. If
it fails, stop and
report its missing or invalid formal artifact. Do not derive `FINAL_PROPOSAL`,
create a research contract, or substitute a prompt, old report, compatibility
path, or other free text. This check is read-only and does not add a stage or
Gate.

For a successful formal handoff, record its run ID, workflow hash, handoff hash,
artifact hash map, and validation obligations in `EXPERIMENT_PLAN.md`; a later
`/experiment-bridge` must re-check the same handoff before implementation.

### Legacy / ad-hoc request — isolated

Only when no Controller-managed run is being invoked may a user-supplied method
or historical report be used directly. Label the resulting plan
`execution_context: NON_CANONICAL_AD_HOC`, retain its source paths, and state
that it has no canonical acceptance or upstream certification. Never write or
register a canonical artifact, mutate `.aris` state, or present this plan as a
completed `problem → root cause → method` route.

## Constants

- **OUTPUT_DIR = `refine-logs/`** — Default destination for experiment planning artifacts.
- **MAX_PRIMARY_CLAIMS = 2** — Prefer one dominant claim plus one supporting claim.
- **MAX_CORE_BLOCKS = 5** — Keep the must-run experimental story compact.
- **MAX_BASELINE_FAMILIES = 3** — Prefer a few strong baselines over many weak ones.
- **DEFAULT_SEEDS = 3** — Use 3 seeds when stochastic variance matters and budget allows.

## Workflow

### Phase 0: Load the Proposal Context

For a successful formal handoff, read the structured Final Method only from
its bound `refine-logs/FINAL_METHOD_PACKET.json`; `FINAL_PROPOSAL.md` is a Human
view and is not a formal planning input. Otherwise,
for a non-canonical ad-hoc request, read the most relevant existing files first
if they exist:

- `refine-logs/FINAL_PROPOSAL.md`
- `refine-logs/REVIEW_SUMMARY.md`
- `refine-logs/REFINEMENT_REPORT.md`
- `idea-stage/ROOT_CAUSE_ANALYSIS.json`
- `idea-stage/ROOT_CAUSE_VERDICT.json`

Extract:

- **Problem Anchor**
- **Selected Principle and Evidence-supported conditions**
- **Target-domain adaptation and minimal faithful realization**
- **Residual gaps and minimal necessary composition**
- **Final Scientific Delta Claim and claim-validation obligations**
- **Critical reviewer concerns**
- **Data / compute / timeline constraints**
- **Which frontier primitive is central, if any**
- **Primary causal-chain IDs, intervention targets, and expected observables**
- **Each RMC, Capability/Design Obligation, core Method change, and its
  claim-validation obligation**

If these files do not exist, derive the same information from the user's prompt
**only for an explicitly non-canonical ad-hoc request**. In a formal run,
missing files are a stop condition handled by `validation-handoff`, never a
fallback.

In a formal Controller route, do not invent a new mechanism here: a missing
root-cause artifact must already have stopped at `validation-handoff`. Only a
non-canonical ad-hoc plan may mark an unavailable mechanism link as
`UNRESOLVED`, while clearly retaining that non-canonical limitation.

### Phase 1: Freeze the Paper Claims

Before proposing experiments, write down the claims that must be defended.

Use this structure. These are validation targets, not established facts:

- **Primary claim**: the main mechanism-level contribution
- **Supporting claim**: optional, only if it directly strengthens the main paper story
- **Anti-claim to rule out**: e.g. "the gain only comes from more parameters," "the gain only comes from a larger search space," or "the modern component is just decoration"
- **Minimum convincing evidence**: what would make each claim believable to a strong reviewer?

Do not exceed `MAX_PRIMARY_CLAIMS` unless the paper truly has multiple inseparable claims.

### Phase 2: Build the Experimental Storyline

Before choosing blocks, write a compact **Mechanism Validation Map**. For every
Selected Principle causal chain, RMC, Design Obligation, and core Method change,
record the claim-validation obligation it traces to; the problem mechanism or
failure it is intended to change; the predicted observable direction or
failure-pattern change; the discriminating measurement/control that can test
it; the performance consequence; and the failure/applicability boundary.

If multiple core changes need their individual roles distinguished, add the
smallest necessary ablation or controlled comparison. Do not force a component
ablation merely because there are multiple changes; a joint mechanism test is
enough when the changes are not independently claimable.

Design the paper around a compact set of experiment blocks. Default to the following blocks and delete any that are not needed:

1. **Main anchor result** — does the method solve the actual bottleneck?
2. **Novelty isolation** — does the primary claimed contribution itself matter?
3. **Simplicity / elegance check** — can a bigger or more fragmented version be avoided?
4. **Frontier necessity check** — if an LLM / VLM / Diffusion / RL-era component is central, is it actually the right tool?
5. **Failure analysis or qualitative diagnosis** — what does the method still miss?

For each block, decide whether it belongs in:

- **Main paper** — essential to defend the core claims
- **Appendix** — useful but non-blocking
- **Cut** — interesting, but not worth the paper budget

Prefer one strong baseline family over many weak baselines. If a stronger modern baseline exists, use it instead of padding the list.

### Phase 3: Specify Each Experiment Block

For every kept block, fully specify:

- **Claim tested**
- **Why this block exists**
- **Dataset / split / task**
- **Compared systems**: strongest baselines, ablations, and variants only
- **Metrics**: decisive metrics first, secondary metrics second
- **Principle / causal link / RMC / obligation / core change**: which accepted
  binding is targeted
- **Predicted mechanism or failure-phenomenon change**: what should change, in which direction
- **Mechanism observation**: measurement, diagnostic, controlled comparison, or falsifier
- **Performance evaluation**: final outcome metric and comparison that establishes utility
- **Setup details**: backbone, frozen vs trainable parts, key hyperparameters, training budget, seeds
- **Success criterion**: what outcome would count as convincing evidence?
- **Failure interpretation**: if the result is negative, what does it mean?
- **Table / figure target**: where this result should appear in the paper

Special rules:

- A core block cannot be complete with a performance metric alone. It must name
  the mechanism/failure observation expected if the explanation is correct.
- Preserve unexpected mechanism observations. They are new research evidence,
  not noise to be omitted: use them to distinguish method mismatch,
  implementation/measurement error, and a wrong or incomplete prior analysis.

- A **simplicity check** should usually compare the final method against either an overbuilt variant or a tempting extra component that the paper intentionally rejects.
- A **frontier necessity check** should usually compare the chosen modern primitive against the strongest plausible simpler or older alternative.
- If the proposal is intentionally non-frontier, say so explicitly and skip the frontier block instead of forcing one.

### Phase 4: Turn the Plan Into an Execution Order

Build a realistic run order so the user knows what to do first.

Use this milestone structure:

1. **Sanity stage** — data pipeline, metric correctness, one quick overfit or toy split
2. **Baseline stage** — reproduce the strongest baseline(s)
3. **Main method stage** — run the final method on the primary setting
4. **Decision stage** — run the decisive ablations for novelty, simplicity, and frontier necessity
5. **Polish stage** — robustness, qualitative figures, appendix extras

For each milestone, estimate:

- compute cost
- expected turnaround time
- stop / go decision gate
- risk and mitigation

Separate **must-run** from **nice-to-have** experiments.

### Phase 5: Write the Outputs

#### Step 5.1: Write `refine-logs/EXPERIMENT_PLAN.md`

Use this structure:

```markdown
# Experiment Plan

**Problem**: [problem]
**Method Thesis**: [one-sentence thesis]
**Date**: [today]
**Execution context**: FORMAL_CANONICAL / NON_CANONICAL_AD_HOC

## Formal Upstream Handoff (formal only)
**Run ID**: [controller run ID]
**Workflow hash**: [controller workflow SHA-256]
**Validation handoff hash**: [controller handoff SHA-256]
| Accepted artifact | SHA-256 | Producer phase |
|-------------------|---------|----------------|
| ...               | ...     | ...            |

### Validation Obligations
- Selected Principle ID/version and intervention:
- Causal-chain / RMC / Capability / Design Obligation IDs:
- Core Method changes and predicted mechanism changes:
- Final Scientific Delta Claim:
- Claim-validation obligations:
- Failure conditions and applicability boundaries:

## Claim Map
| Claim | Why It Matters | Minimum Convincing Evidence | Linked Blocks |
|-------|-----------------|-----------------------------|---------------|
| C1    | ...             | ...                         | B1, B2        |

## Mechanism Validation Map
| Principle / causal-chain / RMC / obligation / core change | Problem mechanism or failure addressed | Predicted observable change | Discriminating evidence | Performance consequence | Boundary / falsifier |
|-----------------------------------------------------------|-----------------------------------------|-----------------------------|-------------------------|-------------------------|----------------------|
| P1 / CC-1 / RMC-1 / OBL-1 / M1                            | ...                                     | ...                         | ...                     | ...                     | ...                  |

## Paper Storyline
- Main paper must prove:
- Appendix can support:
- Experiments intentionally cut:

## Experiment Blocks

### Block 1: [Name]
- Claim tested:
- Why this block exists:
- Dataset / split / task:
- Compared systems:
- Metrics:
- Principle / causal link / RMC / obligation / core change:
- Predicted mechanism or failure-phenomenon change:
- Mechanism observation:
- Performance evaluation:
- Setup details:
- Success criterion:
- Failure interpretation:
- Table / figure target:
- Priority: MUST-RUN / NICE-TO-HAVE

### Block 2: [Name]
...

## Run Order and Milestones
| Milestone | Goal | Runs | Decision Gate | Cost | Risk |
|-----------|------|------|---------------|------|------|
| M0        | ...  | ...  | ...           | ...  | ...  |

## Compute and Data Budget
- Total estimated GPU-hours:
- Data preparation needs:
- Human evaluation needs:
- Biggest bottleneck:

## Risks and Mitigations
- [Risk]:
- [Mitigation]:

## Final Checklist
- [ ] Main paper tables are covered
- [ ] Novelty is isolated
- [ ] Simplicity is defended
- [ ] Frontier contribution is justified or explicitly not claimed
- [ ] Nice-to-have runs are separated from must-run runs
- [ ] Every Selected Principle causal chain, RMC, and Design Obligation has a
      discriminating mechanism-closure path and performance consequence
```

#### Step 5.2: Write `refine-logs/EXPERIMENT_TRACKER.md`

Use this structure:

```markdown
# Experiment Tracker

| Run ID | Milestone | Purpose | System / Variant | Split | Performance metric | Mechanism signal / causal-chain ID | Priority | Status | Notes |
|--------|-----------|---------|------------------|-------|--------------------|------------------------------------|----------|--------|-------|
| R001   | M0        | sanity  | ...              | ...   | ...                | ...                                | MUST     | TODO   | ...   |
```

Keep the tracker compact and execution-oriented.

#### Step 5.3: Present a Brief Summary to the User

```
Experiment plan ready.

Must-run blocks:
- [Block 1]
- [Block 2]

Highest-risk assumption:
- [risk]

First three runs to launch:
1. [run]
2. [run]
3. [run]

Plan file: refine-logs/EXPERIMENT_PLAN.md
Tracker file: refine-logs/EXPERIMENT_TRACKER.md
```

## Output Protocols

> Follow these shared protocols for all output files:
> - **[Output Versioning Protocol](../../shared-references/output-versioning.md)** — write timestamped file first, then copy to fixed name
> - **[Output Manifest Protocol](../../shared-references/output-manifest.md)** — log every output to MANIFEST.md
> - **[Output Language Protocol](../../shared-references/output-language.md)** — respect the project's language setting

## Key Rules

- **Large file handling**: If the Write tool fails due to file size, immediately retry using Bash (`cat << 'EOF' > file`) to write in chunks. Do NOT ask the user for permission — just do it silently.

- **Every experiment must defend a claim.** If it does not change a reviewer belief, cut it.
- **Formal inputs are consume-only.** A failed or missing `validation-handoff`
  stops formal planning; no prompt, report, legacy contract, or template may
  reconstruct the missing upstream artifact.
- **Keep ad-hoc work isolated.** It may plan experiments from user material,
  but it must remain `NON_CANONICAL_AD_HOC` and never claim formal acceptance.
- **Prefer a compact paper story.** Design the main table first, then add only the ablations that defend it.
- **Defend simplicity explicitly.** If complexity is a concern, include a deletion study or a stronger-but-bloated variant comparison.
- **Defend frontier choices explicitly.** If a modern primitive is central, prove why it is better than the strongest simpler alternative.
- **Prefer strong baselines over long baseline lists.** A short, credible comparison set is better than a padded one.
- **Separate must-run from nice-to-have.** Do not let appendix ideas delay the core paper evidence.
- **Reuse proposal constraints.** Do not invent unrealistic budgets or data assumptions.
- **Do not fabricate results.** Plan evidence; do not claim evidence.
- **Do not establish the delta in planning.** `Final Scientific Delta Claim`
  remains a validation target; `Established Scientific Delta` exists only
  after a Controller-accepted `VALIDATED` result.

## Composing with Other Skills

```
/research-refine-pipeline -> one-shot method + experiment planning
/research-refine   -> method and claim refinement
/experiment-plan   -> detailed experiment roadmap
/run-experiment    -> execute the runs
/auto-review-loop  -> react to results and iterate on the paper
```
