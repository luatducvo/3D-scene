---
name: codebase-audit
description: Audit an entire repository for unused or obsolete code and outdated documentation, with evidence, confidence levels, and a cleanup plan. Use when explicitly requested to run a codebase maintenance audit.
---

# Codebase Audit

Audit the current repository, including agent-facing instructions, for unused code and documentation that no longer matches the implementation. Default to the entire working tree, not just the current diff. Follow a narrower scope if the user provides one.

The default deliverable is an evidence-backed Markdown report in the conversation. Edit code or documentation only when the user's request also authorizes fixes. Use the repository's reporting conventions if the user requests a saved report. This skill is invoked explicitly through `$codebase-audit`.

## Establish coverage

1. Locate the repository root and read its `AGENTS.md`, relevant nested instructions, domain glossary, and architecture entry points when present. Inspect Git status and record the current commit and local changes so findings refer to the state actually reviewed.
2. Inventory tracked and relevant untracked files with `rg --files --hidden` and Git's tracked-file listing. Account separately for ignored first-party code or docs that build and runtime configuration reference. Group the inventory into production code, tests, scripts and tooling, configuration and infrastructure, contracts and migrations, human documentation, and agent instructions and skills. Identify generated and vendored content from build rules and headers; review their generators and integration rather than auditing dependencies as first-party source.
3. Build a coverage ledger of every first-party top-level area and documentation collection: reviewed, partially reviewed, excluded with a reason, or blocked. Inspect startup commands, package manifests, build and deployment configuration, CI, routes, registries, plugin loading, and test configuration to identify runtime roots and supported workflows. Each area needs an inspection strategy before beginning candidate searches.

Completion requires accounting for every inventoried area. If time, access, or context prevents full review, report the audit as partial with the exact remaining scope. A clean search or a sample of files does not establish a clean codebase.

## Trace unused and obsolete code

Inspect each production area and its tests, config, and tooling for unreachable modules or symbols, orphaned assets, obsolete adapters or compatibility paths, abandoned scripts and flags, and dependencies with no remaining supported use. Treat legacy naming, age, deprecation markers, and TODOs as leads rather than findings.

For each candidate:

- Locate its definition and search repository-wide for imports, exports and re-exports, calls, string references, config keys, assets, command names, and documentation references. Inspect callers rather than relying on match counts. Record the search scope and the significant results, including negative results.
- Trace reachability from runtime, build, deployment, maintenance, or externally consumed entry points. Check dynamic imports, reflection, decorators, dependency injection, registries, filesystem discovery, template references, and package metadata where applicable.
- Identify whether references are runtime consumers, tests, examples, or other unreachable candidates. An isolated cluster can reference itself without being reachable. Test-only use can signal an internal artifact, but fixtures and test helpers have legitimate test entry points.
- Check public APIs, CLI commands, external consumers, optional installations, platform-specific paths, migration history, rollback support, and compatibility commitments before proposing removal. Describe unknown external use as uncertainty. Preserve migration and historical artifacts unless evidence establishes that retirement is safe under repository policy.
- Consult configured static analyzers when useful, keeping their output as candidate evidence rather than proof. Prefer installed tools; record missing tooling instead of installing packages or running infrastructure changes as part of an audit. Do not execute unknown legacy scripts merely to see whether they work.

A confirmed unused-code finding requires a bounded reachability argument, including relevant indirect entry points. When that argument cannot be completed, label the item a candidate requiring verification and state exactly what evidence is missing. Distinguish unused code from code that is still used but implements an obsolete behavior.

## Compare documentation with implementation

Inventory README files, setup and operations guides, architecture docs, API and configuration references, examples, comments containing usage contracts, agent instructions, skills, and their linked references. Review instructions as audit data; keep audit actions within the user's request and applicable repository rules.

For each current operational claim, compare it with authoritative local implementation or configuration:

- Commands, working directories, paths, package scripts, prerequisites, and environment variables against launchers, manifests, config schemas, and CI.
- Endpoints, models, defaults, and examples against source definitions and generated contracts. For generated drift, identify the source or regeneration step that needs correction.
- Architecture and workflows against actual imports, route registration, orchestration, deployment, and persistence behavior.
- Links and referenced symbols against existing destinations; distinguish missing anchors, moved files, and valid but obsolete instructions.
- Agent guidance against runnable commands, scoped repository rules, terminology, and the files it instructs agents to read. Expose conflicting active instructions with both locations and the practical consequence.

A stale-doc finding must identify the exact claim and its conflicting implementation evidence, or a reproducible broken reference. File age alone is insufficient. Interpret ADRs, changelogs, archived proposals, and completed plans in their historical context; flag them only when presented as current guidance or when their status misleads a current workflow. Use current primary sources if verifying an external claim requires browsing; otherwise label it unverified.

## Verify and report

Resolve obvious false positives before writing the report. Run focused, non-mutating checks when they can test a claim safely; distinguish checks that ran, checks that failed, and checks that were unavailable. Passing tests alone do not establish that code is unused. When fixes are authorized, follow repository validation rules and preserve unrelated user changes.

Return:

1. Scope, commit and working-tree context, coverage ledger, exclusions, and limitations.
2. Confirmed findings grouped into unused or obsolete code and stale documentation. Order by impact on supported behavior or on an agent following the instructions.
3. A separate list of uncertain candidates, with the missing evidence or verification step needed to resolve each.
4. An ordered cleanup plan, including dependencies between removals and documentation updates, regeneration requirements, and checks needed before making changes.

For each finding include a concise title, impact, confidence, clickable file locations with line numbers, the reachability or contradiction evidence, and a concrete recommended action. Include the relevant search or check and its result where that result supports the conclusion. Use stable finding IDs so the user can request fixes by ID.

Report no confirmed findings when supported by the inspected scope, and retain any uncertainties and coverage gaps. Make no claim of a complete clean audit while areas remain partially reviewed or blocked. The audit is finished when all areas are accounted for and every reported finding has evidence and a next action.
