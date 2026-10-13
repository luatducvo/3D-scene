# 13: Run a Stage on the GPU server via the compute contract

**What to build:** scene-compute implements the compute contract (readiness ping, info, checksummed file listing, chunked upload, ranged download, Workspace delete, asynchronous Compute Runs, synchronous invoke, token auth, traversal guard). The worker gains the HTTP backend with checksum-based sync up/down and cold-start waiting, and builds backends per Target from compute configuration. Verified locally with a CPU-only compute service in non-shared-storage mode.

**Blocked by:** 06

**Status:** done

- [ ] With a pipeline config that sends some fake Stages to a local compute service, processing completes and outputs land in the local scene-data volume.
- [ ] Re-running sends no file already present on the Target (by checksum).
- [ ] The info endpoint reports image version, GPU (or none) and installed Algorithms.
- [ ] Contract tests (seam 2, in-process server, tiny chunks) cover chunked upload/download, checksum skip, a failed Compute Run surfacing as an error on the Scene, wrong token rejected, traversal rejected, and shared-storage mode skipping transfers.
- [ ] Every request in the contract stays under the 30 s and chunk-size limits.
