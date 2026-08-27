#!/usr/bin/env python3
"""PreToolUse defense-in-depth guard; Controller/gateway remain the boundary."""

from __future__ import annotations

import json
import re
import sys


PROTECTED = (
    "arisctl/",
    "tools/run_state.py",
    "tools/literature_coverage_audit.py",
    "skills/shared-references/idea-workflow.yaml",
    "skills/shared-references/source-admission-policy.md",
    "skills/shared-references/problem-discovery-contract.md",
    "skills/shared-references/root-cause-analysis-contract.md",
    "skills/shared-references/method-design-contract.md",
    "skills/shared-references/method-refinement-protocol.md",
    "skills/skills-codex/shared-references/idea-workflow.yaml",
    "skills/skills-codex/shared-references/source-admission-policy.md",
    "skills/skills-codex/shared-references/problem-discovery-contract.md",
    "skills/skills-codex/shared-references/root-cause-analysis-contract.md",
    "skills/skills-codex/shared-references/method-design-contract.md",
    "skills/skills-codex/shared-references/method-refinement-protocol.md",
    "templates/METHOD_PROPOSAL_TEMPLATE.md",
    ".aris/runs/",
    ".aris/canonical/",
    ".aris/approvals/",
    ".aris/agent-attestations/",
    "idea-stage/search_ledger.jsonl",
    "idea-stage/literature_corpus.jsonl",
    "idea-stage/evidence_registry.jsonl",
    "idea-stage/active_field_map.md",
    "idea-stage/source_admission_policy.yaml",
    "source-materials/",
    ".codex/config.toml",
    ".codex/agents/",
    ".codex/rules/",
    ".codex/hooks",
)

MUTATING_TOOLS = {"apply_patch", "edit", "write"}
SHELL_WRITE = re.compile(
    r"(?i)(?:\b(?:set-content|add-content|out-file|remove-item|move-item|copy-item|"
    r"new-item|apply_patch|rm|mv|cp|tee|touch|truncate|chmod|chown)\b|(?<![<>=])>{1,2}(?![=>]))"
)
PATCH_TARGET = re.compile(
    r"(?m)^\*\*\* (?:Add|Update|Delete) File: (.+?)\s*$|^\*\*\* Move to: (.+?)\s*$"
)

# This Hook deliberately does not decide which shell programs are useful for
# research.  The Controller, not command names, owns formal state and evidence.
# Keep only direct calls that expose the Controller's write primitives outside
# its public CLI/API boundary.  Protected-path writes below cover their files.
CONTROL_BYPASS = re.compile(
    r"(?i)(\bariscontroller\b|\barisctl\.controller\b|"
    r"run_state\.(?:set_status|accept|approve_human|mark_provisional)|"
    r"run_state\._save|_store\.mutate|"
    r"append_jsonl\s*\()"
)


def deny(reason: str) -> int:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )
    return 0


def protected_write_target(tool_name: str, tool_input: dict) -> bool:
    """Return whether a structured write tool targets a protected path."""
    if tool_name in {"write", "edit"}:
        targets = (str(tool_input.get("file_path") or ""),)
    elif tool_name == "apply_patch":
        patch = str(tool_input.get("patch") or "")
        targets = tuple(
            path
            for match in PATCH_TARGET.finditer(patch)
            for path in match.groups()
            if path
        )
    else:
        return False
    return any(
        protected.lower() in target.replace("\\", "/").lower()
        for target in targets
        for protected in PROTECTED
    )


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        return 2
    tool_input = event.get("tool_input") or {}
    tool_name = str(event.get("tool_name") or "").lower()
    command = str(tool_input.get("command") or tool_input.get("cmd") or "")
    serialized_input = json.dumps(tool_input, ensure_ascii=False)
    normalized = serialized_input.replace("\\", "/").lower()
    if re.search(
        r"(?i)\b(?:python(?:3)?|py)\s+-m\s+arisctl\b.*\b(human-approve|request-source-policy-revision|revise-problem)\b", command
    ):
        # The official execpolicy prompt rule owns the UI confirmation. Returning
        # permissionDecision="ask" here would fail open because Codex does not
        # support that PreToolUse value.
        return 0
    if any(name in normalized for name in (
        "human-approve", "human_approve", "approve_human",
        "request-source-policy-revision", "request_source_policy_revision",
        "revise-problem", "revise_problem",
        "request-problem-revision", "request_problem_revision",
    )):
        return deny("Human approval must use the exact UI-reviewed arisctl CLI route.")
    if CONTROL_BYPASS.search(serialized_input):
        return deny("Controller internals cannot be imported or scripted through agent tools.")
    if "run_state.py" in normalized and re.search(
        r"(?i)\b(set|accept|approve|mark-provisional)\b", serialized_input
    ):
        return deny("Controller-managed state cannot be mutated through legacy run_state commands.")
    protected_target = (
        protected_write_target(tool_name, tool_input)
        if tool_name in MUTATING_TOOLS
        else any(path.lower() in normalized for path in PROTECTED)
    )
    if protected_target and (tool_name in MUTATING_TOOLS or SHELL_WRITE.search(command)):
        return deny("Controller, state, contracts, agents, and hooks are protected from agent tool edits.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
