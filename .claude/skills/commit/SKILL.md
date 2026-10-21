---
name: commit
description: Stage all changes and create a git commit following the repo's commit conventions. Use only when the user invokes /commit.
disable-model-invocation: true
argument-hint: "[optional commit message]"
allowed-tools: Bash(git status:*), Bash(git diff:*), Bash(git add:*), Bash(git commit:*), Bash(git log:*), Bash(git show:*), Bash(git reset:*)
---

# Commit

Stage the working tree and commit it, following the conventions below.

## Steps

1. Run `git status --short` and `git diff HEAD --stat`. If there is nothing to commit, say so and stop.
2. Read `git diff HEAD` and any new untracked files to understand the change.
3. Check for files that must never be committed (see **Never commit**). If any are present, leave them unstaged, list them, and suggest adding them to `.gitignore`.
4. If the changes are several unrelated logical changes, say so and offer to split them into separate commits before going on.
5. Stage: `git add -A`, then `git reset -- <path>` for anything excluded in step 3.
6. Write the message (see **Message format**):
   - If the user passed arguments (`$ARGUMENTS`), use them as the subject's description. Add the `type(scope):` prefix if missing, but keep their wording.
   - Otherwise write it from the diff.
   - End the message with the attribution line from the current system reminder, if one is given.
7. Commit with a heredoc so multi-line messages survive:
   ```bash
   git commit -F - <<'EOF'
   <message>
   EOF
   ```
8. If a pre-commit hook fails, report the error, fix it if the fix is clearly mechanical, re-stage, and try again as a new commit. Never use `--no-verify` or `--amend`.
9. Show the result with `git log --oneline -1`.
10. List the files that were committed, from `git show --name-status --format= HEAD`, one per line with their status (`A` added, `M` modified, `D` deleted, `R` renamed). Also list anything left unstaged in step 3, so the user sees what was not committed.

Do not push.

## Message format

[Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>

<body — optional>

<footer — optional>
```

- **Subject**: English, imperative mood ("add", not "added"/"adds"), lowercase first word, no trailing period, ≤ 72 characters. Specific enough to find later — `fix(frontend): keep camera target when switching objects`, never `fix`, `update`, `123`, `wip`.
- **Body**: only when the subject is not enough. Explain *why* and anything non-obvious, wrapped at ~72 columns, separated from the subject by a blank line.
- **Footer**: `Refs: .scratch/<feature>/issues/NN-<slug>.md` when the commit works on a tracked issue; `BREAKING CHANGE: <what breaks>` for incompatible API, schema or config changes; co-author lines last.

### Types

| Type | Use for |
| --- | --- |
| `feat` | New user-visible behaviour |
| `fix` | Bug fix |
| `refactor` | Code change with no behaviour change |
| `perf` | Performance improvement |
| `test` | Adding or fixing tests only |
| `docs` | Docs, README, ADRs, glossary, diagrams |
| `build` | Dependencies, Dockerfiles, `compose.yaml`, `pyproject.toml`, `package.json` |
| `ci` | CI configuration |
| `chore` | Tooling, agent skills, `.gitignore`/`.gitattributes`, other housekeeping |

### Scopes

Optional but preferred. Use the area the change lives in: `backend`, `frontend`, `compute`, `api` (OpenAPI contracts), `db` (migrations), `docs`, `agents` (`.claude/`, skills, `docs/agents/`). Omit the scope when a change spans several areas evenly.

### Examples

```
feat(frontend): add heatmap toggle to scene explorer
fix(backend): return 404 when object id is unknown
refactor(compute): extract mesh loading into its own module
build: pin three.js to 0.169.0
docs: add Vietnamese README
chore(agents): add /commit skill
```

## What goes in one commit

- One logical change per commit. If the subject needs "and", it is probably two commits.
- Generated files (OpenAPI clients, lockfiles) go in the same commit as the change that produced them.
- Formatting-only or rename-only changes are kept apart from behaviour changes.

## Never commit

- Secrets: `.env`, keys, tokens, credentials.
- Build output and caches: `__pycache__/`, `node_modules/`, `.next/`, `*.tsbuildinfo`, tool working output.
- Large binary assets without asking first.
