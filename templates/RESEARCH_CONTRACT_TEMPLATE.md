# Research Contract: [Certified Problem]

- **Contract schema version**: 4
- **Problem ID**: [stable selected problem ID]
- **Problem version (recorded in Controller state after human acceptance)**: [Controller-assigned integer]
- **Contract SHA-256 (recorded in Controller state after human acceptance)**: [Controller-registered content hash]
- **Candidate registry path**: `idea-stage/PROBLEM_CANDIDATES.jsonl`
- **Candidate registry SHA-256**: [registered hash]
- **Quality verdict path**: `idea-stage/PROBLEM_QUALITY_VERDICTS.jsonl`
- **Quality verdict SHA-256**: [registered hash]
- **Quality verdict ID**: [accepted quality verdict ID]
- **Novelty verdict path**: `idea-stage/PROBLEM_NOVELTY_VERDICTS.jsonl`
- **Novelty verdict SHA-256**: [registered hash]
- **Novelty verdict ID**: [accepted novelty verdict ID]

> Prepare this Contract after problem selection and before the Controller records human acceptance.
> The Controller fills the authoritative version and hash registration only when that Human Gate succeeds.

> This file contains only the accepted problem and its evidence boundary. Once
> the Human Gate accepts it, the Controller records this exact version and hash
> as the active problem handoff. Method routes and refinement proposals belong
> in their own artifacts and may only reference this version. To alter the
> question, scope, falsifier, or evidence boundary, use explicit
> `arisctl revise-problem`; the resulting draft must pass problem generation,
> quality, novelty, and human acceptance again.

## Certified Problem Contract

- **Problem ID / source class**: [ID; community-open / self-discovered /
  problem-migration]
- **Research question**: [One precise, falsifiable question]
- **Observed phenomenon**: [Operational observation]
- **Evidence-backed phenomenon**: [What happens, where, and source anchors]
- **Evidence status**: [Established / supported / preliminary / contested]
- **Decisive evidence tier**: [decision_grade source IDs + exact locators]
- **Measurement validity**: [Why the observable measures the intended construct]
- **Artifact/confound alternatives**: [Strongest non-problem explanations]
- **Independent support**: [Replication, triangulation, or required probe]
- **Prevalence/effect scale**: [How large or frequent the phenomenon is]
- **Scope and boundary**: [Where the claim applies and does not apply]
- **Why it matters**: [Scientific and/or practical consequence]
- **Value if yes / value if no**: [How either answer changes knowledge or action]
- **Decision owner / threshold**: [Who changes what decision at which result]
- **Plausible explanations**: [At least two when evidence permits, with status]
- **Decisive probe or falsifier**: [Evidence that would overturn the framing]
- **Feasible discriminating probe**: [Probe separating the leading explanations]
- **Closest prior / residual delta**: [Nearest decision-grade framing and what remains unresolved]
- **Uncertainties**: [Known unresolved evidence or scope uncertainties]
- **Problem quality verdict**: [CERTIFIED + six-dimension rationale]
- **Problem novelty verdict**: [exact selected-candidate verdict: NOVEL / NOT_NOVEL / UNCERTAIN]
- **Acceptance status**: [provisional / accepted]
- **Verdict ID / acceptance authority**: [ID; same-family / cross-family / human]
- **Evidence snapshot / novelty cutoff date**: [registry hash + date]
- **Source**: [PROBLEM_CANDIDATES / problem-quality / novelty artifacts]

## Linked Formal Evidence Artifact

The formal compact evidence handoff is the separate
`idea-stage/PROBLEM_EVIDENCE_CAPSULE.md`, created from
`templates/PROBLEM_EVIDENCE_CAPSULE_TEMPLATE.md` and registered with this
Contract by the Controller. Do not reproduce its evidence records here.

## Status

- [ ] Problem is `CERTIFIED/accepted` through the Controller Human Gate
- [ ] Problem ID, version, contract hash, and evidence-capsule hash are recorded
- [ ] No method route, scientific mainline, design obligation, or method
  novelty decision is stored in this problem contract
- [ ] Any material problem change has used explicit reopen/revise and awaits a
  new problem acceptance
