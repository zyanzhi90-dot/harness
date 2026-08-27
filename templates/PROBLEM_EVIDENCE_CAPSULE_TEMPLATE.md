# Problem Evidence Capsule: [Certified Problem]

- **Capsule schema version**: 1
- **Problem ID**: [same stable selected problem ID as the Contract]
- **Linked Contract path**: `idea-stage/RESEARCH_CONTRACT.md`
- **Linked Contract SHA-256**: [registered hash]
- **Capsule SHA-256 (recorded in Controller state after human acceptance)**: [Controller-registered content hash]

> Prepare this Capsule after problem selection and before the Controller records human acceptance.
> Its authoritative hash is registered only when that Human Gate succeeds.

> This is the sole formal compact evidence handoff for the accepted problem.
> It is independent from `RESEARCH_CONTRACT.md`: keep evidence records here and
> do not embed a duplicate capsule in the Contract, a candidate list, or a
> report. It records evidence and its limits; scientific acceptance remains the
> Human Gate decision.

## Evidence Boundary

- **Included evidence IDs**: [unique comma-separated IDs; each resolves to an accepted Evidence Card or a current problem-bound artifact]
- **Excluded uncertainty / boundary IDs**: [stable IDs or none]
- **Snapshot source**: [Evidence Registry path/hash and relevant verdict artifacts]
- **Known gaps and contested evidence**: [what this capsule cannot establish]

## Evidence Records

For each included evidence ID, record:

- **Evidence ID / source locator**: [stable ID; accepted Evidence Card or registered artifact and exact locator]
- **Observed claim or phenomenon**: [evidence, not a causal inference]
- **Setting and boundary conditions**: [where it applies and does not apply]
- **Epistemic status**: [established / supported / preliminary / contested]
- **Role for the accepted problem**: [reality / importance / unresolvedness /
  scope / falsifier]

## Registered Non-Literature Artifacts

Use this optional machine-readable block only for pre-existing experiments,
datasets, or real-world observations. The Controller verifies and registers
these files when the problem Human Gate accepts the Capsule. Do not list a new
root-cause diagnostic pilot here.

```json
[
  {
    "artifact_id": "EXP-001",
    "path": "idea-stage/existing-experiment.json",
    "sha256": "<lowercase sha256>",
    "evidence_source_type": "existing_experiment"
  }
]
```

## Integrity Check

- [ ] Problem ID matches `RESEARCH_CONTRACT.md`
- [ ] Every listed evidence ID resolves to the cited formal source artifact
- [ ] Existing experiment, dataset, and real-world IDs are already registered
  from this block with the accepted problem version; a later root-cause
  diagnostic pilot is not retroactively presented as Capsule evidence
- [ ] No method route, root-cause conclusion, or human acceptance decision is
  stored in this capsule
