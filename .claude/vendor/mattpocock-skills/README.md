# mattpocock/skills (vendored)

Source: https://github.com/mattpocock/skills, MIT licence (see `LICENSE`).
Commit: `49dd158d1076134a641b33efb035946536778336` (2026-10-09).

The 27 skills listed in that repo's `.claude-plugin/plugin.json` are copied unchanged into
`.claude/skills/<name>/`. Every other folder in `.claude/skills/` (such as `done-check`) belongs to
this repo.

To update, clone the repo, then for each path in its `plugin.json` replace
`.claude/skills/<basename>` with the new copy, and update the commit above. Review the diff before
committing: skills are instructions Claude follows.
