# ADR-0007: Serve only versioned publications

Status: accepted. Date: 2026-10-17. Amends [ADR-0006](0006-versioned-publication.md) by withdrawing
support for publications stored directly under the Scene's Workspace root.

The user requested deletion of old Scene data and legacy code rather than continued compatibility.
The API therefore serves only publications identified by a Job UUID, with no synthetic `legacy`
version. A Scene without a publication has no asset or evidence URLs. Existing development Scene
data is cleared as part of this change; model weights, credentials and the migration ledger are
preserved. Historical migrations and ADRs remain as the record of schema and design evolution.

Keeping the compatibility branch or adding a data conversion was considered and rejected: this
single-user learning project no longer needs the old results. Any other installation must reset
its old Scene data before using this version; no automatic destructive migration runs at startup.
