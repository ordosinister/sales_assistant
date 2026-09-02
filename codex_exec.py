#!/usr/bin/env python3
"""Wrapper to launch codex exec with the report generation prompt."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

PROMPT = """
# Task
Generate a professional PDF report from the latest sales analysis text file produced by run.py.

# Source File
1. Look in `./data/` for files matching `Report_<YYYY>-<MM>-<DD>.txt`.
2. Select the most recent one by filename date.
3. Read its full contents.

# Skill Reference
Read and strictly follow the complete workflow defined in `skills/report_generation/SKILL.md`.
This skill covers parsing, dynamic chart-type inference, HTML/CSS styling with Blue Professional tokens,
inline Chart.js rendering, and Playwright PDF export.

# Execution Rules
- Do NOT use any external PNG files referenced in the .txt. Generate ALL visuals dynamically from the text content.
- Do NOT hard-code specific analyses or chart assumptions. Every visualization must be derived by parsing the actual .txt file content at runtime.
- Save the output PDF to `./data/` with the same filename as the source .txt, changing only the extension to `.pdf`.
- Delete temporary HTML files after successful PDF generation.
- Output language: match the source text.
"""


def find_codex() -> str:
    """Locate the codex executable in a cross-platform way."""
    found = shutil.which("codex")
    if found:
        found_path = Path(found)
        if os.name == "nt" and not found_path.suffix:
            cmd_path = found_path.with_suffix(".cmd")
            if cmd_path.exists():
                return str(cmd_path)
        return found

    if os.name == "nt":
        appdata = os.environ.get("APPDATA", "")
        candidates = [
            Path(appdata) / "npm" / "codex.cmd",
            Path(appdata) / "npm" / "codex.ps1",
            Path(os.environ.get("LOCALAPPDATA", "")) / "npm" / "codex.cmd",
        ]
        for cand in candidates:
            if cand.exists():
                return str(cand)

    unix_candidates = [
        Path.home() / ".local" / "bin" / "codex",
        "/usr/local/bin/codex",
        "/usr/bin/codex",
    ]
    for cand in unix_candidates:
        if cand.exists():
            return str(cand)

    raise FileNotFoundError("Could not locate 'codex' executable. " "Please ensure it is installed (e.g. via npm install -g codex) and on your PATH.")


def main():
    """Build and run the codex exec command."""
    codex_path = find_codex()
    print(f"Using codex: {codex_path}", file=sys.stderr)

    # cmd = [
    #     codex_path,
    #     "--ask-for-approval",
    #     "never",
    #     "exec",
    #     "--skip-git-repo-check",
    #     "--local-provider=ollama",
    #     "--oss",
    #     "-m",
    #     "kimi-k2.6:cloud",
    #     "--sandbox",
    #     "danger-full-access",
    #     "--ephemeral",
    # ]

    cmd = [
        codex_path,
        "exec",
        "--oss",
        "-m",
        "kimi-k2.6:cloud",
        "--sandbox",
        "danger-full-access",
    ]

    print("CMD:", repr(cmd), file=sys.stderr)

    for i, arg in enumerate(cmd):
        print(f"  [{i}] = {arg!r}", file=sys.stderr)

    print("Launching codex exec ...", file=sys.stderr)
    result = subprocess.run(cmd, cwd=".", encoding="utf-8", input=PROMPT)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
