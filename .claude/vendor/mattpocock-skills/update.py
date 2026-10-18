"""Updates the vendored mattpocock/skills copies in .claude/skills/ to the latest upstream commit.

Usage, from the repository root:  python .claude/vendor/mattpocock-skills/update.py [ref]

`ref` is a branch, tag or commit (default: main). The script replaces every skill listed in the
upstream `.claude-plugin/plugin.json`, removes skills upstream dropped, refuses to overwrite a
repo-owned skill with the same name, and records the commit in vendor.json. Review `git diff`
before committing: skills are instructions Claude follows.
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = "https://github.com/mattpocock/skills"
VENDOR = Path(__file__).resolve().parent
SKILLS = VENDOR.parent.parent / "skills"
MANIFEST = VENDOR / "vendor.json"


def git(*args, cwd=None):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def main():
    ref = sys.argv[1] if len(sys.argv) > 1 else "main"
    manifest = json.loads(MANIFEST.read_text())
    old = set(manifest["skills"])

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        clone = Path(tmp) / "skills"
        git("clone", "--quiet", REPO, str(clone))
        git("checkout", "--quiet", ref, cwd=clone)
        commit = git("rev-parse", "HEAD", cwd=clone)
        if commit == manifest["commit"]:
            print(f"Already at {commit[:7]}; nothing to do.")
            return

        paths = json.loads((clone / ".claude-plugin" / "plugin.json").read_text())["skills"]
        new = {Path(p).name: clone / p for p in paths}

        clashes = sorted(name for name in new if name not in old and (SKILLS / name).exists())
        if clashes:
            sys.exit(f"Upstream adds skills that clash with repo-owned ones: {', '.join(clashes)}. Nothing changed.")

        for name in sorted(old - new.keys()):
            shutil.rmtree(SKILLS / name, ignore_errors=True)
        for name, source in new.items():
            shutil.rmtree(SKILLS / name, ignore_errors=True)
            shutil.copytree(source, SKILLS / name)
        shutil.copy2(clone / "LICENSE", VENDOR / "LICENSE")

    MANIFEST.write_text(json.dumps({"repo": REPO, "commit": commit, "skills": sorted(new)}, indent=2) + "\n")
    print(f"Updated {manifest['commit'][:7]} -> {commit[:7]}")
    print(f"  added:   {', '.join(sorted(new.keys() - old)) or '-'}")
    print(f"  removed: {', '.join(sorted(old - new.keys())) or '-'}")
    print("Review with: git diff --stat .claude/skills")


if __name__ == "__main__":
    main()
