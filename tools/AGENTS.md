# Tools guidance

Read [root AGENTS.md](../AGENTS.md) and [current status](../docs/project-status.md)
first. Paths below are relative to `tools/`.

## Preprocessing boundary

`scannet_prep.py` is a standalone CPU utility with PEP 723 dependencies. Run it
without the backend environment, API, Docker, GPU or models. The serialized
[Package contract](../docs/s3dpkg-spec.md) connects it to Import; keep prep free of
backend imports.

- Default workflow examples read `dataset/scans/<scan>` and explicitly pass
  `--out dataset/preprocessing` from the repository root.
- Require a valid source `axisAlignment`, including explicit identity when valid.
  Apply it to mesh positions and camera poses, and its rotation to normals.
  Preserve source files, vertex/face order, RGB and superpoint correspondence.
- Emit aligned `s3dpkg/2` with coordinate-frame metadata and source-transform
  provenance. Missing/invalid alignment fails with a named error and produces no
  new complete Package. Preserve verify-before-atomic-rename and batch skip/report
  behavior. V1 requires rerunning prep from raw data.
- Keep ground-truth semantic labels outside generated Packages. Store real outputs
  in the ignored output directory; use synthetic data for committed fixtures.

## Verification and utilities

From the repository root:

```powershell
uv run tools/test_scannet_prep.py
uv run tools/scannet_prep.py --help
```

For Package format or alignment changes, also run relevant backend import tests
to check the independent reader and ensure S1 preserves prepared coordinates.
Use an isolated output/data directory for real-data checks and record evidence
without committing licensed scans or Packages.

`query_eval.py` requires running services/models and a processed Scene; read its
arguments and debug-mode requirements before use. `llm_spike.py` records model
experiments. Store dated results under `docs/spikes/` and distinguish hand-authored
Program comparisons from ground-truth benchmarks.
