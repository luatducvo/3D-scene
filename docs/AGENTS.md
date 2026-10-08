# Documentation guidance

Read [root AGENTS.md](../AGENTS.md) and [current status](project-status.md) first.

## Sources and updates

- `project-status.md`: single entry point for changing delivery state, remaining
  work, verification summary and last-known deployment. Update it at completion
  when those facts change; name the revision/date and link detailed evidence.
- `s3dpkg-spec.md`, `mesh-bin.md`: current serialized contracts. Synchronize
  contract changes with both producers and consumers.
- `adr/`: confirmed architectural decisions and their reasons. Preserve the
  decision history; record a new decision when behavior supersedes an old one
  and clearly identify what it supersedes.
- `../GLOSSARY.md`: core input domain terms; `../CONTEXT.md`: wider graph/query
  terminology. Read these before introducing or renaming domain concepts.
- `implement_plan.md` and `../.scratch/s3d-v3/issues/`: intended behavior and
  acceptance criteria. Annotate superseded requirements so they cannot override
  the current contract accidentally.
- `verification.md`, `spikes/`, `code-review*.md`: dated evidence and review
  results. Preserve historical measurements with their original version/date.

## Evidence quality

Distinguish implementation complete, tests passed, real GPU verified, deployment
checked and remote CI passed. A check applies to its recorded revision and
environment; label older evidence explicitly. A completed test/build is required
before claiming it passed. Mark untested paths and remaining work directly.

Keep live machine state as a dated snapshot that future agents verify before
operating on it. Link ignored local assets as local-only artifacts and say they
are absent from a fresh clone. Maintain repository-relative links within docs;
use absolute local paths in user-facing responses.

After doc-only changes, check link targets, referenced paths and consistency with
the affected source/contracts. Application suites are needed when behavior or a
contract also changes, not to validate prose alone.
