# Focused Scene explorer completion report

Date: 2026-10-19 (Asia/Bangkok)
Status: done
Baseline: e2d1627d998d7f01108c5445fc2a76b3486a48ea

## Delivered

All five approved tickets are implemented: Original/Instances and direct Object interaction;
English open-vocabulary search with relative raw-cosine heatmap; independent English QA retaining
only the latest exchange; English-only UI and old-locale redirects; metadata-only Pipeline Inspector.
Manual measurement, camera navigation, Scene lifecycle controls, versioned geometry and membership
are preserved. Old conversations remain stored, but the explorer does not retrieve them and QA
neither reads previous context nor persists new exchanges.

Search, chat, selection and hover have separate lifetimes. Clear restores the base appearance and
invalidates pending results. Chat remains mounted at Scene lifetime, so panel switching retains the
latest answer while reopening the Scene resets it. Instance colors use sorted identities and spaced
colors with rendered-color collision checks. Shared geometry has consistent smaller-membership
ownership for colors and GPU picking. Renderer and legend use one heatmap color scale.

## Done check

| Step | Result | Evidence |
| --- | --- | --- |
| Backend lint | pass | Ruff reports All checks passed |
| Backend non-DB tests | pass | 97 passed, 30 deselected |
| Full backend tests with PostgreSQL | pass | 127 passed against the disposable Docker test database |
| API contract export and frontend sync | pass | Export and generation succeeded; copied contracts are byte-identical; raw_similarity is in the generated client |
| Frontend typecheck | pass | TypeScript noEmit succeeded after final contract generation |
| Frontend tests | pass | 38 passed across 10 files after review fixes |
| Frontend production build | pass | Next production compilation, type validation, static generation and tracing completed |
| Desktop browser verification | pass | Edge 1440 x 1000, real WebGL via software GPU; acceptance and delayed-response scripts succeeded |
| User-visible strings | pass | English is the only rendered language; message key parity retained in inactive translation data |
| Live documentation | pass | Product spec and frontend/API architecture updated; Object Heatmap and Pipeline Inspector defined in domain docs |
| Live GPU reconstruction | skipped | No pipeline Algorithm change; UI verification used deterministic MSW fixtures, not a live reconstruction run |

One existing Starlette/httpx deprecation warning appeared in backend tests; it did not fail tests.
API model changes required updating the committed contract and generated client; those outputs
have been regenerated and are synchronized.

Verdict: done for the approved five-ticket UI/API scope. These checks do not establish live
reconstruction quality, dense production-Scene performance, or live provider availability.

## Standards

Independent standards review found no hard documented-standard breaches. Two judgement findings
were corrected: the legend now shares the renderer's color scale, and the obsolete green-search
assertion now exercises raw similarity and the actual painter. Browser scripts additionally cover
the mounted explorer and request ordering. Recheck found no remaining substantive production issue.
The identified Clear verification gap was corrected by starting a fresh delayed search before Clear.

## Spec

Independent spec review found three issues, all reproduced and corrected: latest-answer loss on panel
switching, visually identical colors for similar Object IDs, and response-order-dependent heatmap
colors on overlapping Objects. Regression tests cover both color defects; browser acceptance now
covers answer retention and Point Cloud as well as Mesh GPU picking. Recheck reported no remaining
substantive Spec findings.

Review summary: Standards 0 remaining findings; Spec 0 remaining findings.

## Browser evidence

The checked-in acceptance scripts and their README describe reproduction. Screenshots are local
ignored artifacts. Checks covered:

- Old Vietnamese deep-link redirect with query preserved, English HTML/navigation, and no switch.
- Actual rendered Original/Instances changes and restoration through Clear.
- Query heatmap, legend, and Point Cloud/Mesh Object picking with real GPU pick passes.
- Two-point manual measurement on Mesh and displayed meter distance.
- Latest-only independent QA, no history fetch, retention across panel changes, reset on Scene reload.
- Stage selection, graph metadata, disabled attributes explanation and Inspector layout.
- Delayed search cannot replace newer QA, stay stuck searching, or repaint after Clear.

No live GPU check was performed or added to the live check log.
