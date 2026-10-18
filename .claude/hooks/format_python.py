"""PostToolUse hook: formats a Python file Claude just edited with Ruff, using the rules in pyproject.toml.

Only files Ruff owns in this repo (`backend/` and `main.py`, as in `main.py lint`) are touched.
A formatting failure never blocks the edit; Ruff's message goes to the transcript instead.
"""

import json
import os
import subprocess
import sys
from pathlib import Path


def main():
    payload = json.load(sys.stdin)
    file_path = payload.get("tool_input", {}).get("file_path")
    if not file_path or not file_path.endswith(".py"):
        return
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR", ".")).resolve()
    try:
        relative = Path(file_path).resolve().relative_to(root)
    except ValueError:
        return
    if relative.parts[0] != "backend" and relative != Path("main.py"):
        return
    result = subprocess.run(
        [sys.executable, "-m", "ruff", "format", str(relative)],
        cwd=root,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"ruff format failed for {relative}:\n{result.stderr}", file=sys.stderr)


if __name__ == "__main__":
    main()
