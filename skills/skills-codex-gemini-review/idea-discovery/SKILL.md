---
name: idea-discovery
description: "Gemini cross-family overlay for the ARIS field map, problem-certification, independent method design, refinement, and human decisions."
argument-hint: "[research-direction]"
---

> `review_independence: cross-family`; default verdicts use
> `acceptance_status: provisional` until human acceptance.

# Idea Discovery — Gemini overlay

Run **$ARGUMENTS** as a problem-first pipeline. This overlay keeps the
problem-certification stage separate from method design and supplies an
independent cross-family challenge; it does not create a second default gate.

```text
/research-lit -> scope approval -> /idea-creator "mode: problem"
-> independent problem-quality Gate -> /novelty-check "mode: problem"
-> human problem acceptance -> /idea-creator "mode: diagnosis"
-> independent root-cause Gate -> /idea-creator "mode: method"
-> human route selection -> /research-refine
-> /novelty-check "mode: method-final" -> human final method acceptance
-> METHOD_CONFIRMED_AWAITING_USER_VALIDATION
```

Run each module in a fresh context. Pass compact packets and stable artifact
paths only: active map, the accepted `RESEARCH_CONTRACT.md` and separate
`PROBLEM_EVIDENCE_CAPSULE.md`, selected `SELECTED_ROUTE.yaml`, and final
proposal. The Contract must not embed a second capsule; the independent capsule
is the sole formal compact evidence handoff. Do not paste the full registry or
conversation history. `IDEA_REPORT.md` is the final human report only.

The shared workflow phase list is authoritative. In particular, neither this
overlay nor a cross-family review may skip `root_cause_analysis` or
`root_cause_gate`. Validation remains a separate user-initiated continuation
after final method acceptance.

After explicit problem selection and before the Controller records human
acceptance, prepare that separate Contract/Capsule pair. Downstream modules may
read it only after the Controller has registered the accepted version.

Use `reference-paper-intake.md` only when `REF_PAPER` is explicit,
`idea-fanout-module.md` for breadth generation, and
`idea-output-composition.md` for explicit final composition
(`--composed: idea-stage/IDEA_REPORT.md`). Keep these
protocols in their shared reference files rather than expanding this overlay.

Before reading proactively retrieved literature, apply the shared
source-admission policy. Citation count or approved venue is the default hard
active-reading gate. Use only the policy's narrow Controller-recorded exception
for identity-verified decisive closest/concurrent, negative/contradictory, or
diagnostic/replication evidence tied to an explicit decision target; recency or
relevance alone is insufficient. User material is `USER_SUPPLIED_READ` and
requires post-read assessment.

No method route may be generated before `human_accepted` appears in the problem
contract and the Controller has accepted a `DIAGNOSIS_READY` root-cause verdict
bound to the current contract, capsule, and 1a–2b analysis. Preliminary method
novelty is a risk screen; final method novelty requires `FINAL_PROPOSAL.md`.
`research-review` is optional. Do not plan or execute experiments in this
workflow.
