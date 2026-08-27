# Idea output and composition module

This is the idea-discovery adapter for the general
[`output-composition.md`](output-composition.md),
[`output-versioning.md`](output-versioning.md),
[`output-manifest.md`](output-manifest.md), and
[`output-language.md`](output-language.md) protocols.

## Default and explicit mode

Standalone is the default. Composed mode is active if and only if the caller
passes an explicit `--composed: <canonical-report-path>` directive; an old
`IDEA_REPORT.md` on disk never activates it. `--standalone` or
`--composed: false` overrides composition. This makes one-module execution
safe and prevents hidden output loss.

In the current problem-first workflow, `/research-lit`, `/idea-creator`, and
reviewers first write their own stage-scoped machine handoffs and audit traces.
The orchestrator owns the final `idea-stage/IDEA_REPORT.md` only after the
human has accepted the problem, the root-cause Gate is `DIAGNOSIS_READY`, and
the human has selected a route. Composition folds unique
findings or links to their durable artifacts; it does not paste registries,
transcripts, or duplicate verdict tables into the report.

## Artifact policy

Use timestamped immutable files plus a fixed-name handoff copy as required by
`output-versioning.md`. Keep machine state in JSONL/YAML and human reading in
Markdown. `IDEA_REPORT.md` is a readable decision record, never a hidden state
database and never the handoff between problem and method modes.

An optional `COMPACT` output may create
`idea-stage/IDEA_CANDIDATES.md` after problem acceptance or route selection. It
is a short index (candidate/route IDs, status, one-line rationale, artifact
links), not a second report. Render HTML only after the canonical report is
complete; rendering is presentation, not a scientific gate.

Keep scratch launch logs and redundant summaries out of the stage directory
after their content is captured. Maintain a manifest only when the artifact
count crosses the threshold in `output-manifest.md`; otherwise the manifest is
more duplication. Always preserve verdict IDs, evidence IDs, input hashes,
reviewer provenance, and human decision paths.

## Composition safety checks

Before writing a composed report, verify: one canonical path; all included
sections have source artifact links; problem acceptance, the root-cause
analysis/verdict IDs and hashes, and route selection are present; no section
claims a method was accepted before its final gate; and no
intermediate report has been treated as active context. On failure, keep the
stage artifacts and return `BLOCKED_COMPOSITION` instead of silently producing
a persuasive but incomplete report.
