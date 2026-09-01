# Root-Cause Analysis Contract

Use this contract after one problem has been human-accepted under
[`problem-discovery-contract.md`](problem-discovery-contract.md) and its
Residual Failure Envelope has been accepted under
[`problem-necessity-contract.md`](problem-necessity-contract.md), and before any
Candidate Principle is formed under
[`method-design-contract.md`](method-design-contract.md). It is the single
source of truth for the diagnosis handoff.

The stage owns **1a-2b**. These labels are reasoning operations inside one
revisable diagnosis stage, not four workflow phases and not four independent
skills:

```text
1a collect and describe phenomenon evidence that directly represents the problem or failure
  -> 1b group phenomena without forcing one cause
  -> 2a trace progressively deeper causes and alternatives
  -> 2b form evidence-calibrated, intervention-relevant causal chains
  -> independent Root-Cause Gate
```

Do not name, search, rank, or combine solution methods in this stage. A possible
intervention target states what mechanism would have to change; it is not a
method proposal.

## Input Gate

Require exactly one human-accepted Certified Problem Contract plus its compact
evidence capsule and one current accepted `RESIDUAL_SAME_PROBLEM` Necessity
Closure/Verdict. Record their current IDs and SHA-256 values in the analysis.
The diagnosis explains only the accepted Residual Failure Envelope. It must not
reframe a portion of the original Failure already covered by a Simple Repair as
a root cause requiring a new Method. If the
question, scope, falsifier, or evidence snapshot has changed, stop and return to
problem acceptance rather than diagnosing a moving target.

### Downstream-triggered reopen

When this phase is reopened by `RCA_CONFLICT` or `ROOT_CAUSE_REJECTED`, read the
latest matching Controller return record directed to `root_cause_analysis`.
Consume its scientific reason, return guidance, validation-result ID, linked
Evidence IDs/result paths, and findings as applicable. Reassess the identified
causal premise without turning a Candidate Principle, Method proposal, or
performance result into a diagnosis.

An identified downstream Evidence Card may be formally cited only through
the existing `readopt-evidence` action. This creates a current RCA binding
without copying the Card or changing its historical query/read provenance. If a
later `REVISE_DIAGNOSIS` return starts another RCA lifecycle and the same Card
is still needed, re-adopt it again.

## 1a - Direct phenomenon evidence

Collect and describe evidence that directly represents the accepted problem or
failure before explaining it. Evidence may come from existing experiments,
literature, datasets, real-world scenarios, or a necessary diagnostic pilot.
A failed experiment is not a mandatory prerequisite. Run a diagnostic pilot
only when the accepted evidence cannot adequately characterize the phenomenon
needed for diagnosis; the pilot is evidence collection, not method validation.

The canonical field remains `failure_observations` for schema compatibility,
but each entry is a phenomenon-evidence record and requires:

```yaml
observation_id:
phenomenon:
conditions:
abnormal_variables:
evidence_source_type: existing_experiment | literature | dataset | real_world | diagnostic_pilot
evidence_refs:
epistemic_status: established | supported | preliminary | contested
```

Every `evidence_refs` value must resolve to the current accepted problem's
formal evidence set. Literature normally uses an ID listed in the accepted Problem
Evidence Capsule and an accepted card with the same `source_id` in the Evidence
Registry. An existing experiment, dataset, or real-world observation must
already be listed in that Capsule's `Registered Non-Literature Artifacts` block;
the problem Human Gate verifies and registers it with the active
problem-version binding, and root-cause analysis only reuses it. A necessary diagnostic pilot is different: it may be newly collected
in 1a, but must be declared explicitly as
`analysis_provenance.new_diagnostic_pilot_artifacts`, never as pre-existing
problem evidence. The Controller verifies and registers that pilot in the
existing artifact registry when it accepts the analysis. Do not cite an
unregistered path, a paper from a different Capsule, or a free-text source
label.

Before `root_cause_analysis` starts, and again while its 1a–2b work is running
when a causal alternative exposes a focused gap, the existing literature gateway
may add Controller-registered Evidence Cards for diagnostic deepening. Those
cards are phase-scoped diagnostic evidence: their hashes enter this phase's
input/output snapshot and the following Root-Cause Gate request, but they do
not modify the accepted Contract or Capsule.
Use `REOPEN_PROBLEM` only when this evidence invalidates the accepted problem or
its evidence handoff; incomplete causal support remains `REVISE_DIAGNOSIS`.

Do not convert an inferred cause into an observation. Preserve null, negative,
contradictory, and boundary evidence when it bears on the accepted problem.

## 1b - Phenomenon grouping

Group observations only when a shared mechanism is plausible. Every group must
name its observation IDs and grouping rationale. Every observation must appear
in at least one group; one-observation groups are allowed when evidence does not
support aggregation. Do not force all failures into one root cause.

## 2a - Causal depth traces

For each group, trace one or more progressively deeper candidate causes. A
trace contains ordered `why_steps`; each step names the effect being explained,
the candidate cause, evidence references, epistemic status, and the next
discriminating observation. Stop at a mechanism deep enough to explain the
failure and admit intervention, not at an arbitrary number of “why” questions.

Keep competing explanations alive until evidence discriminates among them.
Plausibility alone cannot promote an explanation to the primary diagnosis.

## 2b - Causal chains

Every proposed chain must expose this structure:

```text
conditions or input change
  -> mechanism failure
  -> intermediate-state abnormality
  -> final failure phenomenon
```

The machine artifact uses:

```yaml
chain_id:
cluster_ids:
conditions_or_input_change:
mechanism_failure:
intermediate_state_abnormality:
final_failure_phenomenon:
evidence_refs:
alternative_explanations:
  - explanation_id:
    mechanism:
    epistemic_status: supported | preliminary | speculative | contested
    discriminating_evidence:
intervention_target:
falsifier:
epistemic_status: supported | preliminary | contested
```

`primary_causal_chain_ids` may contain more than one chain when the evidence
supports multiple material mechanisms. A primary chain must explain at least
one accepted failure group, have evidence anchors, state a falsifier, and expose
an intervention target. “The model is weak,” “the data are hard,” or a method
name is not a causal mechanism.

## Canonical artifacts

Write:

- `idea-stage/ROOT_CAUSE_ANALYSIS.json` — canonical machine handoff;
- `idea-stage/ROOT_CAUSE_ANALYSIS.md` — faithful human-readable view;
- `idea-stage/ROOT_CAUSE_VERDICT.json` — independent Gate verdict.

The JSON analysis requires:

```yaml
schema_version: 1
run_id:
analysis_id:
problem_id:
problem_contract_sha256:
evidence_capsule_sha256:
necessity_binding:
  necessity_id:
  closure_sha256:
  verdict_id:
  verdict_sha256:
  residual_failure_ids:
failure_observations:
phenomenon_clusters:
causal_depth_traces:
causal_chains:
primary_causal_chain_ids:
unresolved_questions:
analysis_provenance:
  author_role:
  created_at:
  source_artifact_ids:
  new_diagnostic_pilot_artifacts: # optional 1a evidence newly collected for diagnosis
    - artifact_id:
      path:
      sha256:
      evidence_source_type: diagnostic_pilot
```

`problem_id` must equal the active accepted Contract/Capsule problem. Every
`evidence_refs` and `source_artifact_ids` entry must resolve either to the
Capsule-bound Evidence Registry card, an already problem-bound artifact, or an
explicitly new diagnostic pilot. The validator checks identity, hash, and
reference closure only; the independent Gate remains responsible for the
pilot's necessity and causal adequacy.

The Markdown view must render the same IDs, chains, uncertainty, and upstream
hashes. It may improve readability but cannot add a diagnosis absent from the
JSON artifact.

## Independent Root-Cause Gate

Review in a fresh context containing the accepted problem, evidence capsule,
accepted Necessity Closure/Verdict, analysis artifacts, and named evidence
cards only. The reviewer must judge:

1. phenomenon-evidence fidelity — 1a directly characterizes the accepted
   problem/failure, identifies its evidence source, and contains observations
   rather than disguised causes; a failed experiment is not required;
2. grouping adequacy — 1b neither conflates distinct failures nor fragments a
   coherent mechanism without reason;
3. causal depth — 2a goes beyond surface symptoms and preserves alternatives;
4. explanatory coverage — 2b explains the material accepted phenomena;
5. evidence calibration — causal strength does not exceed the evidence;
6. intervention relevance — the mechanism can be changed without naming a
   preferred solution;
7. falsifiability — each primary chain has a discriminating falsifier.
8. residual-failure fidelity — the diagnosis explains the complete accepted
   residual and does not explain away or resurrect Failure already covered by
   a Simple Repair.

Allowed decisions:

```text
DIAGNOSIS_READY | REVISE_DIAGNOSIS | REOPEN_PROBLEM
```

- `DIAGNOSIS_READY`: all eight scientific rubrics are `PASS` and there is no
  `BLOCKING` issue, so the diagnosis is sufficient to derive method
  requirements. It does not claim that a chain is finally proven.
- `REVISE_DIAGNOSIS`: the accepted problem remains valid, but phenomenon
  evidence, grouping, causal depth, alternatives, or chain construction must be
  revised inside `root_cause_analysis`.
- `REOPEN_PROBLEM`: the accepted problem or its evidence handoff is no longer
  adequate for diagnosis and must return to `problem_generation`, then repeat
  problem quality review, novelty review, and human acceptance.

All eight scientific rubrics must be `PASS`. The workflow declares the unique executable mapping:

```text
DIAGNOSIS_READY   -> method_design
REVISE_DIAGNOSIS -> root_cause_analysis
REOPEN_PROBLEM    -> problem_generation
```

The Controller applies these only through `return-phase` with verdict ID,
reviewer identity, and the validated verdict artifact. It invalidates the
declared return target through the returning Gate, moves their controller-owned
outputs from active paths to `.aris/archive/<run-id>/<return-event>/`, and
removes them from the active artifact registry. The archive remains provenance
only; default resolvers and downstream hooks must not consume it. A reusable
failure pattern may be supplied as the small structured `--lesson-file` and is
then appended to `LESSONS_LEARNED.md`; ordinary returns create no lesson.

Only `DIAGNOSIS_READY` authorizes method design. The verdict must bind the
analysis ID and the SHA-256 values of the analysis, problem contract, and
evidence capsule. Any later hash change invalidates the handoff.

The canonical verdict schema is:

```yaml
schema_version: 1
run_id:
verdict_id:
reviewer:
analysis_id:
reviewed_analysis_sha256:
problem_contract_sha256:
evidence_capsule_sha256:
necessity_closure_sha256:
necessity_verdict_sha256:
decision: DIAGNOSIS_READY | REVISE_DIAGNOSIS | REOPEN_PROBLEM
reasons:
issues:
  - issue_id:
    severity: BLOCKING | NON_BLOCKING
    message:
observation_fidelity: PASS | FAIL | UNCERTAIN
grouping_adequacy: PASS | FAIL | UNCERTAIN
causal_depth: PASS | FAIL | UNCERTAIN
explanatory_coverage: PASS | FAIL | UNCERTAIN
evidence_calibration: PASS | FAIL | UNCERTAIN
intervention_relevance: PASS | FAIL | UNCERTAIN
falsifiability: PASS | FAIL | UNCERTAIN
residual_failure_alignment: PASS | FAIL | UNCERTAIN
```

`DIAGNOSIS_READY` cannot carry a `BLOCKING` issue and requires `PASS` on every
one of the eight rubrics. Schema validity and hash/ID
bindings are Type-A checks; the eight scientific judgments remain the fresh
reviewer's Type-B responsibility.

Each rubric field is a machine-readable scalar, not a `{status, rationale}`
object. Preserve the scientific basis for the decision in `reasons`, and record
actionable caveats in `issues`; the attested receipt carries the complete
verdict payload and must never reduce the reviewer judgment to rubric statuses
alone. Downstream Method Design reads the accepted analysis and this complete
verdict, so the reasons must retain every material qualification needed to use
the diagnosis without re-performing the review.

## Method-design handoff

Pass the accepted problem unchanged plus the validated analysis and verdict.
Method design consumes every `primary_causal_chain_id` and first derives
machine-resolvable Required Mechanism Changes, Required Capabilities, and Design
Obligations from its mechanism failures and intervention targets. Candidate
Principles and tests must remain traceable through that chain. They may not
replace the diagnosis with a more convenient story to justify a preferred
technique. If Principle formation, Evidence Update, Method adaptation, or Full
Validation exposes a contradiction, return the linked Evidence and feedback to
this stage rather than silently rewriting it downstream.

## Failure paths

| Code | Trigger | Required response |
|---|---|---|
| `OBSERVATION_CAUSE_LEAK` | 1a records an inferred cause as fact | rewrite the observation from inspected evidence |
| `PHENOMENA_FORCED_TO_ONE_CAUSE` | materially different failures are collapsed | split the groups and retain multiple chains |
| `CAUSE_TOO_SHALLOW` | diagnosis restates the symptom | continue 2a or return `REVISE_DIAGNOSIS` |
| `ALTERNATIVE_NOT_DISCRIMINATED` | primary explanation wins by plausibility | retain alternatives and specify discriminating evidence |
| `CHAIN_EVIDENCE_GAP` | a causal link lacks an evidence anchor | revise the chain or return `REOPEN_PROBLEM` when the accepted evidence handoff is inadequate |
| `CHAIN_NOT_INTERVENTION_RELEVANT` | no mechanism can be changed or tested | return `REVISE_DIAGNOSIS`; use `REOPEN_PROBLEM` only when the accepted problem itself must be reopened |
| `SOLUTION_LEAKAGE` | a method name or favored module determines the diagnosis | remove it and reconstruct from the accepted evidence |
