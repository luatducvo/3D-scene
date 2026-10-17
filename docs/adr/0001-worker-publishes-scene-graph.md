# ADR-0001: The worker publishes the Scene Graph

Status: accepted. Date: 2026-10-13.

## Context

Algorithms must execute on CPU or a remote GPU through the same Workspace contract. The local
database stores the published Scene understanding for API queries, while remote storage is disposable.

## Decision

Algorithms are pure Workspace transforms and never access a database. The graph Stage writes only
its graph folder. After every Stage succeeds, the worker reads the Scene Graph and object embeddings
and publishes Objects, Relations and embeddings through the Scene repository in one transaction.
The Scene becomes ready only after publication succeeds. Publication preserves Instance/Object ids.

## Alternative considered

The graph Algorithm could write directly to Postgres. That would couple Algorithms to database
credentials, network reachability and schema versions, prevent isolated Stage tests, and make a
remote Target responsible for local application state. It would also mix geometric work with
publication failure handling.

## Consequences

The worker owns publication and its failures. Workspace artifacts can be inspected or reused after
a database failure. Stage tests require only files, while publication is covered through the REST
API plus real worker/database seam. Both in-process and remote execution share the scene-core
Executor; neither needs database access to execute an Algorithm.
