import { afterAll, afterEach, beforeAll, expect, test } from "vitest";
import { setupServer } from "msw/node";
import { http, HttpResponse } from "msw";
import { watchSceneProgress, type SceneProgress } from "./sceneProgress";
import type { Scene, Schemas } from "./api/types";
const events = "http://localhost:8000/api/v1/scenes/room/events";
const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
const frame = (event: Record<string, unknown>) =>
  `event: ${event.type}\ndata: ${JSON.stringify(event)}\n\n`;
const sse = (frames: Record<string, unknown>[]) =>
  new HttpResponse(frames.map(frame).join(""), {
    headers: { "Content-Type": "text/event-stream" },
  });
const run = (stage: string, status: string): Schemas["StageRun"] =>
  ({
    stage,
    status,
    algorithm: `${stage}.fake`,
  }) as Schemas["StageRun"];
/** Watches until a terminal status, returning every reported state. */
function watched(runs: Scene["stage_runs"]) {
  return new Promise<SceneProgress[]>((resolve) => {
    const seen: SceneProgress[] = [];
    const stop = watchSceneProgress("room", runs, (progress) => {
      seen.push(progress);
      if (progress.status && progress.status !== "processing") {
        stop();
        resolve(seen);
      }
    });
  });
}

test("replay and live events fold into per-Stage state with progress", async () => {
  server.use(
    http.get(events, () =>
      sse([
        {
          type: "stage",
          stage: "ingest",
          status: "done",
          algorithm: "ingest.fake",
        },
        {
          type: "stage",
          stage: "recon",
          status: "running",
          algorithm: "recon.fake",
        },
        { type: "progress", stage: "recon", done: 2, total: 5, unit: "frame" },
        { type: "status", status: "processing" },
        // Live: progress that arrives before its Stage's first stage event still counts.
        { type: "progress", stage: "align", done: 1, total: 4, unit: "frame" },
        {
          type: "stage",
          stage: "recon",
          status: "done",
          algorithm: "recon.fake",
        },
        {
          type: "stage",
          stage: "align",
          status: "running",
          algorithm: "align.fake",
        },
        { type: "status", status: "ready" },
      ]),
    ),
  );
  const seen = await watched([run("ingest", "running")]);
  const last = seen.at(-1)!;
  expect(last.status).toBe("ready");
  expect(last.stages.ingest?.status).toBe("done");
  // A finished Stage keeps its last report; a Stage that starts clears it.
  expect(last.stages.recon).toMatchObject({
    status: "done",
    progress: { done: 2, total: 5, unit: "frame" },
  });
  expect(last.stages.align).toMatchObject({
    status: "running",
    progress: null,
  });
  const beforeAlignStarts = seen.find((state) => state.stages.align?.progress);
  expect(beforeAlignStarts?.stages.align).toMatchObject({
    status: null,
    progress: { done: 1, total: 4 },
  });
});

test("the first state comes from the Scene's Stage Runs", async () => {
  server.use(
    http.get(events, () => sse([{ type: "status", status: "failed" }])),
  );
  const [only] = await watched([run("ingest", "done"), run("recon", "failed")]);
  expect(only.stages.recon?.status).toBe("failed");
  expect(only.status).toBe("failed");
});

test("a dropped stream reconnects and resumes from the replay", async () => {
  let connections = 0;
  server.use(
    http.get(events, () => {
      connections += 1;
      return connections === 1
        ? sse([
            {
              type: "stage",
              stage: "ingest",
              status: "running",
              algorithm: "ingest.fake",
            },
          ])
        : sse([
            {
              type: "stage",
              stage: "ingest",
              status: "done",
              algorithm: "ingest.fake",
            },
            { type: "status", status: "ready" },
          ]);
    }),
  );
  const last = (await watched([])).at(-1)!;
  expect(connections).toBe(2);
  expect(last.stages.ingest?.status).toBe("done");
});
