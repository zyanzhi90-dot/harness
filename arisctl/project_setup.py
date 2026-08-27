"""Install the small project-local Codex layer required by a formal ARIS run."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path


MANAGED_FILES = (
    (".codex/config.toml", "config.toml"),
    (".codex/hooks.json", "hooks.json"),
    (".codex/agents/paper_reader.toml", "agents/paper_reader.toml"),
    (".codex/agents/coverage_reviewer.toml", "agents/coverage_reviewer.toml"),
    (
        ".codex/agents/independent_problem_reviewer.toml",
        "agents/independent_problem_reviewer.toml",
    ),
    (
        ".codex/agents/independent_novelty_reviewer.toml",
        "agents/independent_novelty_reviewer.toml",
    ),
    (
        ".codex/agents/independent_root_cause_reviewer.toml",
        "agents/independent_root_cause_reviewer.toml",
    ),
    (
        ".codex/agents/independent_method_reviewer.toml",
        "agents/independent_method_reviewer.toml",
    ),
    (
        ".codex/agents/result_to_claim_reviewer.toml",
        "agents/result_to_claim_reviewer.toml",
    ),
    (".codex/hooks/pre_tool_use_policy.py", "hooks/pre_tool_use_policy.py"),
    (".codex/hooks/subagent_attestation.py", "hooks/subagent_attestation.py"),
    (".codex/rules/aris.rules", "rules/aris.rules"),
)

# Every project-local command hook used by the formal lifecycle must be
# reviewed once when the project is initialized.  Keep this explicit rather
# than implying that the provenance hook is the only one: the PreToolUse guard
# protects the Controller boundary, while both natural child-completion paths
# need the attestation hook.
REQUIRED_PROJECT_HOOK_TRUST = (
    ("PreToolUse", "Checking ARIS Controller boundary"),
    ("SubagentStop", "Recording ARIS subagent provenance"),
    ("Stop", "Recording ARIS subagent provenance"),
)


def _hook_trust_instruction() -> str:
    hooks = "; ".join(
        f"`{event}` — `{status}`" for event, status in REQUIRED_PROJECT_HOOK_TRUST
    )
    return (
        "- During project initialization, ask the user once whether they trust every "
        "project-local ARIS command Hook: "
        f"{hooks}. After confirmation, complete the corresponding `/hooks` trust "
        "action before formal native work. Repeat the question only when a managed "
        "Hook definition changes. Do not dispatch a formal reader/reviewer or treat "
        "native preflight as proof of Hook trust until the user has confirmed it.\n"
    )


class ProjectRuntimeError(RuntimeError):
    """The active Codex task cannot discover this formal project's Hooks."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_formal_native_subagent_runtime(
    root: str | Path,
    role: str,
    *,
    runtime_project_root: str | Path | None = None,
) -> dict[str, str]:
    """Fail closed unless the active Codex task is this managed project.

    Codex discovers a project's ``.codex`` configuration from the task working
    directory and native children inherit that directory.  The Controller must
    therefore check the dispatching task's cwd *before* it creates a formal
    child, rather than trying to recover provenance after its Stop hook was
    missed.
    """
    project = Path(root).resolve()
    runtime = Path(runtime_project_root if runtime_project_root is not None else Path.cwd()).resolve()
    if runtime != project:
        raise ProjectRuntimeError(
            "formal native-subagent dispatch requires the active Codex runtime "
            f"project root to equal the formal ARIS project root; runtime is "
            f"{runtime}, formal project is {project}"
        )

    repo = Path(__file__).resolve().parents[1]
    layer = project / ".codex"
    manifest_path = layer / "ARIS_CONTROLLER_LAYER.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        records = manifest["managed_files"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ProjectRuntimeError(
            "formal native-subagent dispatch requires the formal project's "
            "managed .codex layer"
        ) from exc
    if not isinstance(records, list):
        raise ProjectRuntimeError("managed .codex manifest has invalid managed_files")
    recorded = {
        str(record.get("path", "")).replace("\\", "/"): record.get("sha256")
        for record in records
        if isinstance(record, dict)
    }
    for source_relative, target_relative in MANAGED_FILES:
        target_key = (Path(".codex") / target_relative).as_posix()
        target = project / target_key
        source = repo / source_relative
        if (
            recorded.get(target_key) != _sha256(source)
            or not target.is_file()
            or _sha256(target) != _sha256(source)
        ):
            raise ProjectRuntimeError(
                f"formal project managed .codex layer is missing or stale: {target_key}"
            )

    try:
        hooks = json.loads((layer / "hooks.json").read_text(encoding="utf-8"))
        config = (layer / "config.toml").read_text(encoding="utf-8")
        hook_groups = hooks["hooks"]
        hook_commands = [
            entry.get("commandWindows") or entry.get("command", "")
            for name in ("Stop", "SubagentStop")
            for group in hook_groups[name]
            for entry in group.get("hooks", [])
            if isinstance(entry, dict)
        ]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ProjectRuntimeError(
            "formal project .codex Hook or native role configuration is invalid"
        ) from exc
    role_config = re.search(
        rf"(?ms)^\[agents\.{re.escape(role)}\]\s*$.*?^config_file\s*=\s*\"([^\"]+)\"\s*$",
        config,
    )
    configured = role_config.group(1) if role_config is not None else ""
    if configured != f"agents/{role}.toml" or not (layer / configured).is_file():
        raise ProjectRuntimeError(f"formal project does not configure native role {role}")
    if not all(".codex/hooks/subagent_attestation.py" in str(command) for command in hook_commands) or len(hook_commands) < 2:
        raise ProjectRuntimeError(
            "formal project Stop/SubagentStop attestation Hooks are not registered"
        )
    return {
        "runtime_project_root": str(runtime),
        "project_root": str(project),
        "role": role,
    }


def install_project_codex_layer(root: str | Path) -> Path | None:
    project = Path(root).resolve()
    repo = Path(__file__).resolve().parents[1]
    source_layer = repo / ".codex"
    target_layer = project / ".codex"
    if target_layer.resolve() == source_layer.resolve():
        return None
    manifest = target_layer / "ARIS_CONTROLLER_LAYER.json"
    if (target_layer / "config.toml").exists() and not manifest.exists():
        raise ValueError(
            "project already has an unmanaged .codex/config.toml; merge the ARIS "
            "Controller layer explicitly instead of overwriting user configuration"
        )
    records = []
    for source_relative, target_relative in MANAGED_FILES:
        source = repo / source_relative
        target = target_layer / target_relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        digest = _sha256(target)
        records.append(
            {"path": str(Path(".codex") / target_relative), "sha256": digest}
        )
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source_repo": str(repo),
                "managed_files": records,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    agents = project / "AGENTS.md"
    if not agents.exists():
        agents.write_text(
        "# ARIS formal research project\n\n"
        "- Formal research-lit state changes only through `python -m arisctl`.\n"
        "- Follow the formal workflow implemented in `D:\\桌面\\科研Agent Harness设计\\ARIS`; Controller State and canonical Artifacts are the sole authority for stage transitions and research decisions.\n"
        + _hook_trust_instruction()
            +
            "- Main performs query planning and Field Map synthesis.\n"
            "- Spawn `paper_reader` and only the reviewer role named by the live Controller request. Controller authorization automatically verifies that this active Codex task is rooted at this formal project before issuing a reader event or reviewer request; a parent-workspace or other-project root is a hard stop. Do not start formal native work from an unverified root or treat the diagnostic `preflight-native-subagent` CLI as a substitute for Controller authorization. Keep reader/reviewer work in the current active Codex turn: prefer the configured native role; only when this runtime cannot select it, use the formally attested native generic compatibility path (`fork_turns = none`) for `paper_reader` or `coverage_reviewer`. Never use nested `codex exec`, a new CLI session, or a new top-level turn to simulate a configured role.\n"
            "- Every scientific-core reviewer performs its Controller-issued judgment directly in its configured Codex CLI role and reports that Codex session's actual model identifier. A reviewer remains independent through its configured role and fresh context; same-family verdicts are accepted by the Controller.\n"
            "- Human Gates require confirmation in the Codex interface.\n",
            encoding="utf-8",
        )
    return manifest
