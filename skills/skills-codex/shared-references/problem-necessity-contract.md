# Problem Necessity Contract

Use this contract after Human acceptance of one Problem and before root-cause
analysis. It is the only pre-RCA authority for deciding whether the accepted
Failure still requires a new Method after applicable Simple Repairs are
considered.

```text
accepted Problem + Contract + Evidence Capsule + current formal Evidence
  -> Failure and Operating Envelope
  -> applicable Simple Repair coverage
  -> Residual Failure Envelope and Problem identity disposition
  -> independent problem reviewer
  -> Controller accept or fixed return
```

This phase does not create a test plan or start an experiment. It may use only
current Controller-registered literature, dataset, experiment, real-world, or
user-provided Evidence, plus formal reasoning or read-only analysis of already
available data. If those sources are insufficient, use the existing
phase-scoped incremental literature gateway. Its query plan must bind the
current Problem ID/version, Contract hash, Capsule hash, and explicit
Failure/Simple-Repair decision targets. If the resulting Evidence is still
insufficient, the only valid decision is `UNRESOLVED`.

## Scientific operation

Describe every active Failure with a condition, observable failure,
consequence, and current formal Evidence references. State the Operating
Envelope in which those failures matter.

A Simple Repair is a conventional, low-complexity intervention that does not
change the core causal or computational relation under examination. Assess
only repair classes that are actually applicable to the current Problem. These
may include tuning, scheduling, standard preprocessing/filtering/estimation,
known constraints or certificates, more data/capacity/compute without changing
the core relation, local reparameterization, the strongest existing baseline,
or a nearest fair combination. The list is a search aid, not a requirement to
invent irrelevant checks.

For each assessed repair, state the applicable Failure IDs, Evidence, coverage
boundary, and one of:

```text
FULL_COVERAGE | PARTIAL_COVERAGE | NO_COVERAGE | UNRESOLVED
```

`PARTIAL_COVERAGE` and `NO_COVERAGE` must reference an explicit Residual
Failure Envelope. A residual records its source Failure IDs, remaining
condition/observable/consequence, repair assessments that do not cover it, and
formal Evidence. The closure must separately propose whether the residual is
the same accepted Problem, redefines the Problem, leaves no residual, or is
unresolved.

## Canonical artifacts

Main writes `idea-stage/NECESSITY_CLOSURE.json`. The independent problem
reviewer returns the complete canonical `idea-stage/NECESSITY_VERDICT.json`
payload through the live Controller request; the Controller materializes it.

The Closure follows the canonical `necessity_closure` artifact contract in
`idea-workflow.yaml`. Its `problem_binding` is exactly:

```yaml
problem_id:
problem_version:
problem_contract_sha256:
evidence_capsule_sha256:
```

Its analysis provenance may declare only `EXISTING_FORMAL_EVIDENCE`,
`FORMAL_ANALYSIS`, and `READ_ONLY_EXISTING_DATA_ANALYSIS`. Every Evidence ID
must resolve in the current phase context. There is no necessity-specific test
registry, execution approval, experiment handoff, result submission, Evidence
registry, CLI action, or equivalent active-experiment path.

## Independent review and fixed Controller decisions

The fresh-context `independent_problem_reviewer` judges Failure reality,
Operating Envelope fidelity, applicability and completeness of Simple Repair
coverage, residual-failure fidelity, Problem identity, and Evidence
sufficiency. The validator checks only schema, IDs, hashes, reference closure,
and consistency between the reviewer's declared disposition and decision.

Allowed verdicts and their only transitions are:

```text
FULLY_COVERED              -> problem_generation
RESIDUAL_SAME_PROBLEM      -> accept; root_cause_analysis
RESIDUAL_REDEFINES_PROBLEM -> problem_generation, then Quality, Novelty, Human acceptance
UNRESOLVED                 -> problem_necessity
```

`FULLY_COVERED` records `no_new_method_needed` for the current Failure. It is a
fixed return, not `SCIENTIFIC_NO_GO`. Only `RESIDUAL_SAME_PROBLEM` creates an
accepted Necessity handoff. RCA must bind the accepted Closure/Verdict IDs and
hashes and the complete Residual Failure Envelope; it may explain only that
residual, not portions of the original Failure already covered by a Simple
Repair.
