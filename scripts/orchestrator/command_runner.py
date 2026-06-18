from __future__ import annotations

import subprocess

from .errors import fail
from .pipeline_paths import REPO_ROOT


def run_command(command: list[str], *, stdin: str | None = None, show_output: bool = True) -> None:
    print("\n$ " + subprocess.list2cmdline(command))
    try:
        completed = subprocess.run(
            command,
            cwd=REPO_ROOT,
            input=stdin,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            stdout=None if show_output else subprocess.PIPE,
            stderr=None if show_output else subprocess.PIPE,
        )
    except FileNotFoundError:
        fail("Docker CLI was not found. Install Docker Desktop or add docker to PATH.")

    if completed.returncode == 0:
        return

    if not show_output:
        if completed.stdout:
            print(completed.stdout, end="")
        if completed.stderr:
            print(completed.stderr, end="")
    raise SystemExit(completed.returncode)
