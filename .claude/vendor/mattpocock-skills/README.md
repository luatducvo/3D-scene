# mattpocock/skills (vendored)

Source: https://github.com/mattpocock/skills, MIT licence (see `LICENSE`).

The skills listed in that repo's `.claude-plugin/plugin.json` are copied unchanged into
`.claude/skills/<name>/`. [vendor.json](vendor.json) records the upstream commit and which skill
folders are vendored; every other folder in `.claude/skills/` (such as `done-check`) belongs to
this repo.

## Updating

From the repository root:

```
python .claude/vendor/mattpocock-skills/update.py          # latest main
python .claude/vendor/mattpocock-skills/update.py <ref>    # a tag, branch or commit
```

The script replaces the vendored skills, removes ones upstream dropped, and stops without changing
anything if upstream adds a skill whose name a repo-owned skill already uses. Review
`git diff .claude/skills` before committing: skills are instructions Claude follows. Local edits to
a vendored skill are overwritten, so make them again after an update.
