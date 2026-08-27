from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from arisctl.__main__ import main
from arisctl.controller import ARISController
from arisctl.recovery import RECOVERY_MANIFEST, save_recovery_snapshot


def _formal_project(root: Path) -> ARISController:
    controller = ARISController.start(root, "resume-run", executor="codex-gpt-5.6-sol")
    (root / "CURRENT_CONTINUATION.md").write_text("# Resume here\n", encoding="utf-8")
    (root / "idea-stage").mkdir(exist_ok=True)
    (root / "idea-stage" / "ACTIVE_FIELD_MAP.md").write_text("# Field Map\n", encoding="utf-8")
    (root / "source-materials").mkdir(exist_ok=True)
    (root / "source-materials" / "paper.txt").write_text("full text", encoding="utf-8")
    canonical = root / ".aris" / "canonical" / "resume-run"
    canonical.mkdir(parents=True, exist_ok=True)
    (canonical / "evidence-P1.json").write_text('{"source_id":"P1"}\n', encoding="utf-8")
    return controller


def test_recovery_snapshot_copies_project_and_resumes_existing_run(tmp_path: Path) -> None:
    source = tmp_path / "source-project"
    original = _formal_project(source).status()
    snapshot = tmp_path / "saved-project"

    result = save_recovery_snapshot(source, "resume-run", snapshot)

    assert result["run_id"] == "resume-run"
    assert (snapshot / RECOVERY_MANIFEST).is_file()
    assert (snapshot / "CURRENT_CONTINUATION.md").read_text(encoding="utf-8") == "# Resume here\n"
    assert (snapshot / "idea-stage" / "ACTIVE_FIELD_MAP.md").is_file()
    assert (snapshot / "source-materials" / "paper.txt").read_text(encoding="utf-8") == "full text"
    assert (snapshot / ".aris" / "canonical" / "resume-run" / "evidence-P1.json").is_file()

    manifest = json.loads((snapshot / RECOVERY_MANIFEST).read_text(encoding="utf-8"))
    assert manifest["run_id"] == "resume-run"
    assert manifest["saved_research_stage"] == original["research_lit"]["current_stage"]
    assert manifest["resume"]["status_command"] == "python -m arisctl status resume-run"

    restored = tmp_path / "restored-project"
    shutil.copytree(snapshot, restored)
    resumed = ARISController.start(restored, "resume-run", executor="another-executor").status()
    assert resumed["run_id"] == original["run_id"]
    assert resumed["created"] == original["created"]
    assert resumed["research_lit"]["current_stage"] == original["research_lit"]["current_stage"]


def test_save_recovery_cli_uses_existing_state_without_controller_transition(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    source = tmp_path / "source-project"
    _formal_project(source)
    snapshot = tmp_path / "saved-project"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "arisctl",
            "--root",
            str(source),
            "save-recovery",
            "resume-run",
            str(snapshot),
        ],
    )

    assert main() == 0

    output = json.loads(capsys.readouterr().out)
    assert output["snapshot_directory"] == str(snapshot.resolve())
    assert (snapshot / ".aris" / "runs" / "resume-run.json").is_file()
