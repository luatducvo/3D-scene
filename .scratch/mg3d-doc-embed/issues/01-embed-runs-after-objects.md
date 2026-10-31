# 01: Run the embed Stage after the objects Stage

**What to build:** Change the Pipeline order to ingest, recon, align, mesh, segment, lift, objects, embed. The embed Stage declares that it reads the objects Stage's output, and the objects Stage no longer depends on embed. `embed.metaclip2` and `embed.fake` keep working unchanged. Afterwards a fake Job publishes as before and its Stage Runs appear in the new order. This is the prefactor for the rest of the work in `../spec.md` (see ADR 0001).

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [x] The shared Stage list, each Stage's declared reads, and all three pipeline configs use the new order
- [x] A fake Job run through `create_app` publishes, and its Stage Runs are listed in the new order
- [x] Existing objects, results and target tests pass with no behaviour change other than the order
- [x] `uv run main.py lint` and `uv run main.py test` pass
