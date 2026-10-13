# 07: Live progress over SSE

**What to build:** The Scene page shows each Stage's progress live. The worker publishes Stage and status events through Postgres notifications; the API fans them out over SSE, replaying current state on connect; the frontend StageStepper renders plain-language Stage names.

**Blocked by:** 06

**Status:** done

- [ ] After pressing Process I watch Stages move through running then done in order, ending in ready (or failed with the error).
- [ ] Refreshing the page mid-processing immediately shows completed Stages, then continues live.
- [ ] Event shapes match the spec and appear in the OpenAPI contract.
- [ ] API test: subscribing during a fake Job receives the replay, then live events through to the final status.
- [ ] Frontend test: StageStepper reacts correctly to a mocked event stream, including failure.
