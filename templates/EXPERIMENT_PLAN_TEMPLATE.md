# Experiment Plan

> **Template for Workflow 1.5 (`/experiment-bridge`).** Fill in, save as `refine-logs/EXPERIMENT_PLAN.md`, then run `/experiment-bridge`.

**Problem**: [What problem does your method solve?]
**Method Thesis**: [One-sentence description of your approach]
**Execution context**: [FORMAL_CANONICAL / NON_CANONICAL_AD_HOC]

> For `FORMAL_CANONICAL`, copy the current `python -m arisctl validation-handoff <run_id>`
> bindings below. A missing binding stops work; do not reconstruct it from a prompt or old report.

## Formal Upstream Handoff (formal only)

**Run ID**: [controller run ID]
**Workflow hash**: [workflow SHA-256]
**Validation handoff hash**: [handoff SHA-256]
| Accepted artifact | SHA-256 | Producer phase |
|-------------------|---------|----------------|
| [path] | [hash] | [phase] |

### Validation obligations

- **Selected Principle ID/version and intervention**: [...]
- **Causal-chain IDs**: [...]
- **Required Mechanism Change IDs**: [...]
- **Required Capability / Design Obligation IDs**: [...]
- **Core Method changes**: [...]
- **Final Scientific Delta Claim**: [validation target, not established fact]
- **Claim-validation obligations**: [...]
- **Failure conditions / applicability boundaries**: [...]

## Claim Map

| Claim | Why It Matters | Minimum Convincing Evidence | Linked Blocks |
|-------|----------------|----------------------------|---------------|
| C1: [Main claim] | [Why] | [Evidence needed] | B1, B2 |
| C2: [Supporting claim] | [Why] | [Evidence needed] | B3 |

## Mechanism Validation Map

| Principle / causal-chain / RMC / obligation / core change | Problem mechanism or failure addressed | Predicted observable change | Discriminating evidence | Performance consequence | Boundary / falsifier |
|-----------------------------------------------------------|-----------------------------------------|-----------------------------|-------------------------|-------------------------|----------------------|
| P1 / CC-1 / RMC-1 / OBL-1 / M1 | [What this change should fix] | [What should change] | [Measurement or controlled test] | [Primary outcome consequence] | [failure condition / limit] |

## Experiment Blocks

### Block 1: Main Result
- **Claim tested**: C1
- **Dataset / split / task**: [e.g., ImageNet val]
- **Compared systems**: [Your method vs. Baseline A vs. Baseline B]
- **Metrics**: [Primary: accuracy/PPL. Secondary: throughput]
- **Principle / causal link / RMC / obligation / core change**: [bound IDs and Method change]
- **Predicted mechanism or failure-phenomenon change**: [Expected direction/pattern]
- **Mechanism observation**: [Measurement, diagnostic, or controlled comparison]
- **Performance evaluation**: [Final outcome metric and baseline comparison]
- **Setup details**: [Backbone, optimizer, lr, epochs, seeds]
- **Success criterion**: [e.g., "> 2% accuracy over baseline"]
- **Failure interpretation**: [If negative, what does it mean?]
- **Priority**: MUST-RUN

### Block 2: Ablation Study
- **Claim tested**: C1 (novelty isolation)
- **Compared systems**: [Full method, -component A, -component B]
- **Use only when needed**: [Explain which independently claimable core changes this control distinguishes; otherwise omit this block]
- **Success criterion**: [Each component contributes > 0.5%]
- **Priority**: MUST-RUN

### Block 3: [Additional Experiment]
- **Priority**: NICE-TO-HAVE

## Run Order

| Milestone | Goal | Runs | Decision Gate | Cost |
|-----------|------|------|---------------|------|
| M0: Sanity | Pipeline works | 1 quick run | Loss decreases? | ~0.5h |
| M1: Baselines | Reproduce baselines | Block 3 | Numbers match? | ~4h |
| M2: Main | Full method | Block 1 | Meets criterion? | ~8h |
| M3: Ablation | Components | Block 2 | Each matters? | ~6h |

## Compute Budget
- **Total estimated GPU-hours**: ~18h
- **Hardware**: [e.g., 4x RTX 3090]
- **Biggest bottleneck**: [e.g., baseline reproduction]

## Risks
- **Risk**: [What could go wrong] → **Mitigation**: [How to handle it]

> Do not write `Established Scientific Delta` in this plan. That status exists
> only after a Controller-accepted `VALIDATED` result closes the mechanism and
> performance obligations.
