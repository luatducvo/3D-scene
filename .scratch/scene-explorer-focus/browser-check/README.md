# Desktop acceptance checks

Run the mock frontend at localhost port 3001 with NEXT_PUBLIC_API_MODE=mock.
Install the isolated helper from the repository root:

    npm install --prefix .scratch/scene-explorer-focus/browser-check --no-save playwright

Run the two checks from the repository root:

    node .scratch/scene-explorer-focus/browser-check/acceptance.cjs
    node .scratch/scene-explorer-focus/browser-check/races.cjs

The checks use installed Microsoft Edge in headless mode at 1440 x 1000 with real WebGL
and software GPU rendering. The first exercises English locale redirects, rendered
Original/Instances changes, relative heatmap, Clear, Point Cloud and Mesh GPU picking,
manual measurement, independent latest-only questions, panel retention, Inspector metadata,
and empty chat after a Scene reload. The second delays search at the HTTP fetch boundary
to check that QA can take over and Clear invalidates a genuinely pending search.

PNG screenshots are generated locally beside these scripts and ignored by Git. These are
mock-data UI checks; they do not establish live GPU pipeline or reconstruction quality.
