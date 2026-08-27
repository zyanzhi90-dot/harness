from __future__ import annotations

import json
from pathlib import Path

import pytest

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 support
    import tomli as tomllib

from arisctl.project_setup import (
    ProjectRuntimeError,
    REQUIRED_PROJECT_HOOK_TRUST,
    install_project_codex_layer,
    verify_formal_native_subagent_runtime,
)


REVIEWER_ROLES = {
    "independent_problem_reviewer",
    "independent_novelty_reviewer",
    "independent_root_cause_reviewer",
    "independent_method_reviewer",
}


def test_project_layer_installs_every_declared_agent_without_gemini_bridge(
    tmp_path: Path,
) -> None:
    manifest_path = install_project_codex_layer(tmp_path)
    assert manifest_path is not None

    config = tomllib.loads(
        (tmp_path / ".codex" / "config.toml").read_text(encoding="utf-8")
    )
    declared = {
        role
        for role, definition in config["agents"].items()
        if isinstance(definition, dict)
    }
    assert REVIEWER_ROLES <= declared
    for role, definition in config["agents"].items():
        if not isinstance(definition, dict):
            continue
        assert (tmp_path / ".codex" / definition["config_file"]).is_file(), role

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    managed = {record["path"].replace("\\", "/") for record in manifest["managed_files"]}
    assert "gemini-review" not in str(config)
    assert not any("gemini-review" in path for path in managed)
    assert all(f".codex/agents/{role}.toml" in managed for role in REVIEWER_ROLES)

    agents_md = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert "reviewer role named by the live Controller request" in agents_md
    assert "Controller authorization automatically verifies" in agents_md
    assert "parent-workspace or other-project root is a hard stop" in agents_md
    assert "native generic compatibility path" in agents_md
    assert "nested `codex exec`" in agents_md
    assert "Every scientific-core reviewer" in agents_md
    assert "configured Codex CLI role" in agents_md
    assert "same-family verdicts are accepted" in agents_md
    assert "During project initialization, ask the user once" in agents_md
    assert "After confirmation, complete the corresponding `/hooks` trust action" in agents_md
    for event, status_message in REQUIRED_PROJECT_HOOK_TRUST:
        assert f"`{event}` — `{status_message}`" in agents_md
    rules = (tmp_path / ".codex" / "rules" / "aris.rules").read_text(encoding="utf-8")
    assert "Controller automatically verifies" in rules

    hook_config = json.loads((tmp_path / ".codex" / "hooks.json").read_text(encoding="utf-8"))
    installed_hooks = {
        (event, str(entry.get("statusMessage") or ""))
        for event, groups in hook_config["hooks"].items()
        for group in groups
        for entry in group.get("hooks", [])
        if isinstance(entry, dict) and entry.get("type") == "command"
    }
    assert installed_hooks == set(REQUIRED_PROJECT_HOOK_TRUST)

def test_formal_native_runtime_preflight_requires_exact_managed_project_root(
    tmp_path: Path,
) -> None:
    install_project_codex_layer(tmp_path)

    passed = verify_formal_native_subagent_runtime(
        tmp_path,
        "paper_reader",
        runtime_project_root=tmp_path,
    )
    assert passed == {
        "runtime_project_root": str(tmp_path.resolve()),
        "project_root": str(tmp_path.resolve()),
        "role": "paper_reader",
    }
    assert verify_formal_native_subagent_runtime(
        tmp_path,
        "independent_problem_reviewer",
        runtime_project_root=tmp_path,
    )["role"] == "independent_problem_reviewer"

    with pytest.raises(ProjectRuntimeError, match="runtime project root"):
        verify_formal_native_subagent_runtime(
            tmp_path,
            "paper_reader",
            runtime_project_root=tmp_path.parent,
        )


def test_every_scientific_core_reviewer_uses_direct_codex_cli() -> None:
    repo = Path(__file__).resolve().parents[1]
    for role in REVIEWER_ROLES:
        text = (repo / ".codex" / "agents" / f"{role}.toml").read_text(
            encoding="utf-8"
        )
        assert "directly in this Codex CLI session" in text
        assert "mcp__gemini-review__review_start" not in text
        assert "mcp__gemini-review__review_status" not in text
        assert "exact model identifier" in text


@pytest.mark.parametrize(
    "role",
    ("independent_problem_reviewer", "independent_novelty_reviewer"),
)
def test_candidate_reviewers_require_validator_binding_fields(role: str) -> None:
    repo = Path(__file__).resolve().parents[1]
    text = (repo / ".codex" / "agents" / f"{role}.toml").read_text(encoding="utf-8")
    assert "Every record must copy" in text
    for field in (
        "schema_version",
        "review_request_id",
        "reviewer",
        "verdict_id",
        "reviewed_artifact_hashes",
    ):
        assert field in text
    assert "one phase-level `verdict_id`" in text
    assert "candidate-specific verdict IDs are invalid" in text
