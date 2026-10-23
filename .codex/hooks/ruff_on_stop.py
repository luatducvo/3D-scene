"""Run the repository's Ruff commands when Codex finishes a turn."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    payload = json.load(sys.stdin)
    failures = []
    for task in ("format", "lint"):
        command = ["uv", "run", "main.py", task]
        try:
            result = subprocess.run(
                command,
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            failures.append(f"{' '.join(command)} failed: {error}")
            continue
        if result.returncode:
            failures.append(
                f"{' '.join(command)} exited {result.returncode}:\n{result.stdout}\n{result.stderr}"
            )

    response = {}
    if failures:
        reason = "Ruff completion checks failed:\n" + "\n".join(failures)
        if payload.get("stop_hook_active"):
            # Surface unresolved failures without starting another continuation.
            response = {"systemMessage": reason}
        else:
            response = {
                "decision": "block",
                "reason": reason + "\nFix these findings and rerun the failed commands.",
            }
    print(json.dumps(response))


if __name__ == "__main__":
    main()
