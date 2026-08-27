"""Cross-platform discovery for the repository's POSIX shell tests."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


POSIX_BASH_MODULES = {
    "test_codex_install_update.py",
    "test_copilot_install.py",
    "test_install_aris_replace_link.py",
    "test_install_aris_selective.py",
    "test_install_aris_tools_symlink.py",
    "test_research_wiki_helper_resolution.py",
    "test_verify_paper_audits.py",
}
WINDOWS_PORTABLE_BASH_TESTS = {
    "test_install_aris_codex_avoids_bash4_associative_arrays",
    "test_install_copilot_avoids_bash4_associative_arrays",
    "test_no_hardcoded_invocations",
}


def _find_posix_bash() -> Path | None:
    direct = shutil.which("bash")
    candidates = [Path(direct)] if direct else []
    if os.name == "nt":
        try:
            found = subprocess.run(
                ["where.exe", "git"],
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                check=False,
            ).stdout.splitlines()
        except OSError:
            found = []
        for git in found:
            git_path = Path(git.strip())
            if git_path.name.casefold() == "git.exe":
                candidates.extend(
                    (
                        git_path.parent.parent / "bin" / "bash.exe",
                        git_path.parent.parent / "usr" / "bin" / "bash.exe",
                    )
                )
    for candidate in candidates:
        if not candidate.is_file():
            continue
        try:
            result = subprocess.run(
                [str(candidate), "-lc", "exit 0"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
                check=False,
            )
        except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
            continue
        if result.returncode == 0:
            return candidate.resolve()
    return None


def pytest_configure(config: pytest.Config) -> None:
    bash = _find_posix_bash()
    config._aris_posix_bash = bash  # type: ignore[attr-defined]
    if bash is None:
        return
    shim_dir = Path(tempfile.mkdtemp(prefix="aris-test-bin-"))
    config._aris_shim_dir = shim_dir  # type: ignore[attr-defined]
    if os.name == "nt":
        python3 = shim_dir / "python3"
        executable = Path(sys.executable).as_posix()
        python3.write_text(
            f'#!/usr/bin/env bash\nexec "{executable}" "$@"\n', encoding="utf-8", newline="\n"
        )
    os.environ["PATH"] = os.pathsep.join(
        (str(shim_dir), str(bash.parent), os.environ.get("PATH", ""))
    )
    os.environ["PYTHONIOENCODING"] = "utf-8"
    os.environ["PYTHONUTF8"] = "1"
    os.environ["LANG"] = "C.UTF-8"
    os.environ["LC_ALL"] = "C.UTF-8"

    original_run = subprocess.run
    config._aris_original_subprocess_run = original_run  # type: ignore[attr-defined]

    def portable_run(*popenargs, **kwargs):
        if popenargs:
            command = popenargs[0]
            rest = popenargs[1:]
            if isinstance(command, (list, tuple)) and command and command[0] == "bash":
                command = [str(bash), *command[1:]]
            popenargs = (command, *rest)
        elif isinstance(kwargs.get("args"), (list, tuple)) and kwargs["args"]:
            command = kwargs["args"]
            if command[0] == "bash":
                kwargs["args"] = [str(bash), *command[1:]]
        if (kwargs.get("text") or kwargs.get("universal_newlines")) and "encoding" not in kwargs:
            kwargs["encoding"] = "utf-8"
            kwargs.setdefault("errors", "replace")
        return original_run(*popenargs, **kwargs)

    subprocess.run = portable_run

    symlink_ok = True
    if os.name == "nt":
        probe = Path(tempfile.mkdtemp(prefix="aris-symlink-probe-"))
        try:
            target = probe / "target"
            target.mkdir()
            os.symlink(target, probe / "link", target_is_directory=True)
        except OSError:
            symlink_ok = False
        finally:
            shutil.rmtree(probe, ignore_errors=True)
    config._aris_native_symlink_ok = symlink_ok  # type: ignore[attr-defined]


def pytest_unconfigure(config: pytest.Config) -> None:
    original_run = getattr(config, "_aris_original_subprocess_run", None)
    if original_run is not None:
        subprocess.run = original_run
    shim_dir = getattr(config, "_aris_shim_dir", None)
    if isinstance(shim_dir, Path) and shim_dir.is_dir():
        shutil.rmtree(shim_dir, ignore_errors=True)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    bash = getattr(config, "_aris_posix_bash", None)
    symlink_ok = getattr(config, "_aris_native_symlink_ok", False)
    if bash is not None and (os.name != "nt" or symlink_ok):
        return
    for item in items:
        module = Path(str(item.fspath)).name
        if module not in POSIX_BASH_MODULES:
            continue
        if bash is None:
            item.add_marker(pytest.mark.skip(reason="requires a POSIX Bash runtime"))
            continue
        if module == "test_verify_paper_audits.py" or item.name in WINDOWS_PORTABLE_BASH_TESTS:
            continue
        item.add_marker(
            pytest.mark.skip(
                reason="requires native POSIX symlink semantics unavailable to this Windows user"
            )
        )
