# Method Proposal: [Proposal Name]

- **Proposal status**: [refining / final]
- **Problem ID**: [active accepted problem ID]
- **Problem version**: [active accepted problem version]
- **Problem-contract SHA-256**: [Controller-registered hash]
- **Problem-evidence-capsule SHA-256**: [Controller-registered hash]
- **Root-cause analysis ID**: [accepted analysis ID]
- **Root-cause analysis SHA-256**: [Controller-registered hash]

> This is a post-convergence Method artifact. It adapts the active
> Controller-materialized Selected Principle and must not redefine the accepted
> Problem, RCA, Principle version, or their bindings. A test-only concrete
> realization from Principle evaluation is not a Method commitment.

## Selected Principle binding

- **Selected Principle ID**: [exact `SELECTED_PRINCIPLE.yaml` value]
- **Selected Principle version**: [exact value]
- **Selected Principle statement**: [algorithm-independent intervention]
- **Causal-chain IDs**: [all bound IDs]
- **Required Mechanism Change IDs**: [all bound IDs]
- **Required Capability IDs**: [all bound IDs]
- **Design Obligation IDs**: [all bound IDs]
- **Evidence closure**: [accepted convergence Evidence]
- **Activation conditions**: [...]
- **Remaining uncertainty**: [...]

## Target-domain adaptation

Map the selected intervention to the target entities, relations, states or
information structures, operating conditions, and every bound RMC/Capability/
Obligation. Distinguish Evidence, inference, and proposed adaptation.

## Minimal faithful realization

Specify the smallest concrete realization that faithfully instantiates the
Selected Principle. Identify reused implementation machinery separately from
core Method changes. Do not inherit a pre-convergence test realization without
independent post-convergence justification.

## Principle-only closure attempt

For every bound causal chain, RMC, Capability, Obligation, activation condition,
failure condition, and boundary, record the selected intervention, concrete
realization, predicted mechanism change, and `CLOSED` or `RESIDUAL_GAP` status.

## Residual mechanism and adaptation gaps

Give each real residual gap a stable ID, failed closure link, target condition,
consequence, and acceptance condition. Use `none` when Principle-only closure is
complete; do not invent gaps to justify composition.

## Minimal necessary composition

For each retained support, bind residual gap IDs, mechanism, activation
conditions, actual integration interface, assumption compatibility, and the
removal/counterfactual failure prediction. Use `none` when no support is needed.

## Core method changes

List the concrete changes that implement the Selected Principle or close a
declared residual gap. For each, identify its binding IDs and distinguish core
scientific change from ordinary implementation prerequisites.

## Predicted mechanism changes

For each causal chain/RMC/core change, state the predicted observable mechanism
or failure-pattern change, activation conditions, discriminating observation,
and expected performance consequence.

## Failure conditions and applicability boundaries

Carry forward the Selected Principle's failure conditions and boundaries, then
state any target-adaptation-specific limits. Do not broaden scope beyond current
Evidence.

## Final Scientific Delta Claim

State the bounded Claim that Full Validation will test. It is not an established
fact. Identify its new mechanism, representation, boundary, or important
capability and distinguish it from concrete embodiment novelty.

## Claim-validation obligations

For every Claim element record: claim-element ID; causal-chain, RMC, Capability,
Obligation, and core-change IDs; predicted mechanism change; discriminating
Evidence required; performance consequence required; falsifying pattern;
failure conditions; and applicability boundary.

Full causal closure requires:

```text
predicted mechanism change -> observed mechanism change
  -> discriminating evidence -> performance consequence
```

Performance improvement alone cannot establish the Final Scientific Delta
Claim. `Established Scientific Delta` is reserved for a Controller-accepted
`VALIDATED` result.
