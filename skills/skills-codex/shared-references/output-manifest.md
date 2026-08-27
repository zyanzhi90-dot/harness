# Output Manifest Protocol

Maintain `MANIFEST.md` only when a run produces more than 15 durable artifacts.
Below that threshold, canonical paths and stage state are the index; do not
create a second bookkeeping artifact. Once the threshold is crossed, register
canonical, state, decision, review, and final artifacts, but not disposable
shards, transient logs, caches, or redundant latest-copy aliases.

## Format

If `MANIFEST.md` does not exist, create it with this header:

```markdown
# Research Output Manifest

> Auto-maintained by ARIS skills. Tracks all generated artifacts across the research lifecycle.

| Timestamp | Skill | File | Stage | Description |
|-----------|-------|------|-------|-------------|
```

Then append one row per durable output file:

```
| 2025-06-15 14:30 | /idea-creator | idea-stage/IDEA_REPORT_20250615_143022.md | idea-discovery | 12 ideas generated from "LLM reasoning" direction |
| 2025-06-15 14:30 | /idea-creator | idea-stage/IDEA_REPORT.md | idea-discovery | latest copy |
```

## Stage Values

| Stage | Skills |
|-------|--------|
| `idea-discovery` | /idea-creator, /idea-discovery, /novelty-check, /research-review |
| `implementation` | /research-refine, /research-refine-pipeline, /experiment-plan, /experiment-bridge, /run-experiment |
| `review` | /auto-review-loop |
| `paper` | /paper-writing, /paper-write, /paper-compile |

## Pre-flight Check

Before writing output, if the skill depends on a prerequisite file from a previous stage:
1. Check if the prerequisite file exists at its expected stage-scoped path (e.g., `idea-stage/IDEA_REPORT.md`, `review-stage/AUTO_REVIEW.md`)
2. If not found at the stage-scoped path, check the legacy root-level path (e.g., `./IDEA_REPORT.md`, `./AUTO_REVIEW.md`) — see [Path Fallback Rule](output-versioning.md#path-fallback-rule-backward-compatibility)
3. If not found at either path, warn: "⚠️ Expected {file} (from {skill}) but not found. Run {skill} first?"
4. Do not block — the user may have the file elsewhere or want to proceed anyway
