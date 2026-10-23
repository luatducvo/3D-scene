"""PostToolUse hook: format and lint the Python file Claude just wrote or edited.

Runs `ruff format`, then `ruff check --fix` (safe fixes only) on that one file with the
repository's pyproject.toml. Findings Ruff cannot fix go back to Claude on stderr with exit
code 2, so it fixes them before moving on. Files outside the repository, non-Python files and
paths excluded in pyproject.toml are skipped.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])


def ruff_command():
    """The workspace's own Ruff, so the hook uses the version uv.lock pins."""
    for name in ("Scripts/ruff.exe", "bin/ruff"):
        if (ROOT / ".venv" / name).is_file():
            return [str(ROOT / ".venv" / name)]
    if shutil.which("uv"):
        return ["uv", "run", "--frozen", "ruff"]
    return None


def main():
    payload = json.load(sys.stdin)
    raw = (payload.get("tool_input") or {}).get("file_path") or (
        payload.get("tool_response") or {}
    ).get("filePath")
    if not raw:
        return 0
    path = Path(raw).resolve()
    if path.suffix != ".py" or not path.is_file() or not path.is_relative_to(ROOT.resolve()):
        return 0
    ruff = ruff_command()
    if ruff is None:
        print("ruff hook: no .venv Ruff and no uv on PATH; run `uv sync`.", file=sys.stderr)
        return 1
    # --force-exclude applies pyproject's extend-exclude to a file named on the command line.
    common = ["--force-exclude", "--config", str(ROOT / "pyproject.toml"), str(path)]
    subprocess.run([*ruff, "format", "--quiet", *common], cwd=ROOT, capture_output=True)
    check = subprocess.run(
        [*ruff, "check", "--fix", "--output-format", "concise", "--quiet", *common],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if check.returncode != 0:
        print(f"Ruff found problems it cannot fix in {raw}:\n{check.stdout}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
