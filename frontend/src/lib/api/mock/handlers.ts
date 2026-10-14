import { http, HttpResponse } from "msw";
import {
  progressEvent,
  type Scene,
  type SceneObject,
  type ProgressEvent,
  type QueryEvent,
  type Schemas,
} from "../port";
import { apiOrigin } from "../http";
const base = `${apiOrigin}/api/v1/scenes`;
const objects: SceneObject[] = [
  {
    id: "chair-1",
    label: "chair",
    box: { center: [1, 1, 0.5], size: [0.6, 0.6, 1], yaw: 0 },
    attributes: { color: ["blue"] },
    best_views: [],
  },
  {
    id: "table-1",
    label: "table",
    box: { center: [0, 0, 0.4], size: [1.5, 1, 0.8], yaw: 0 },
    attributes: { material: ["wood"] },
    best_views: [],
  },
];
const scenes = new Map<string, Scene>([
  [
    "demo",
    {
      id: "demo",
      name: "Demo room",
      status: "ready",
      created_at: new Date().toISOString(),
      assets: {},
      stage_runs: [],
    },
  ],
]);
const messages = new Map<string, Schemas["Message"][]>();
const stages = [
  "ingest",
  "recon",
  "align",
  "mesh",
  "segment",
  "lift",
  "embed",
  "attributes",
  "graph",
];
const missing = () =>
  HttpResponse.json(
    { error: { code: "NOT_FOUND", message: "Scene not found" } },
    { status: 404 },
  );
const stream = (events: (ProgressEvent | QueryEvent)[]) =>
  new HttpResponse(
    new ReadableStream({
      async start(controller) {
        for (const event of events) {
          controller.enqueue(
            new TextEncoder().encode(
              `event: ${event.type}\ndata: ${JSON.stringify(event)}\n\n`,
            ),
          );
          await new Promise((r) => setTimeout(r, 60));
        }
        controller.close();
      },
    }),
    { headers: { "Content-Type": "text/event-stream" } },
  );
export const handlers = [
  http.get(base, () => HttpResponse.json([...scenes.values()])),
  http.post(base, async ({ request }) => {
    const { name } = (await request.json()) as { name: string };
    const id = crypto.randomUUID();
    scenes.set(id, {
      id,
      name,
      status: "created",
      created_at: new Date().toISOString(),
      assets: {},
      stage_runs: [],
    });
    return HttpResponse.json({ id });
  }),
  http.get(`${base}/:id`, ({ params }) =>
    scenes.has(String(params.id))
      ? HttpResponse.json(scenes.get(String(params.id)))
      : missing(),
  ),
  http.delete(`${base}/:id`, ({ params }) => {
    const scene = scenes.get(String(params.id));
    if (scene?.status === "processing")
      return HttpResponse.json(
        { error: { code: "SCENE_BUSY", message: "Processing" } },
        { status: 409 },
      );
    scenes.delete(String(params.id));
    return new HttpResponse(null, { status: 204 });
  }),
  http.post(`${base}/:id/uploads`, ({ params }) => {
    const scene = scenes.get(String(params.id));
    if (!scene) return missing();
    if (!["created", "uploaded"].includes(scene.status))
      return HttpResponse.json(
        { error: { code: "SCENE_LOCKED", message: "Create a new scene" } },
        { status: 409 },
      );
    scene.status = "uploaded";
    return HttpResponse.json({ filenames: [] });
  }),
  http.post(`${base}/:id/process`, ({ params }) => {
    const scene = scenes.get(String(params.id));
    if (!scene) return missing();
    scene.status = "processing";
    scene.stage_runs = [];
    return HttpResponse.json({ job_id: "mock-job" });
  }),
  http.get(`${base}/:id/events`, ({ params }) => {
    const scene = scenes.get(String(params.id));
    if (!scene) return missing();
    if (scene.status !== "processing")
      return stream([
        progressEvent({
          type: "status",
          status: scene.status,
          stage: null,
          algorithm: null,
          manifest: null,
        }),
      ]);
    const events: ProgressEvent[] = stages.flatMap((stage) => [
      progressEvent({
        type: "stage",
        stage,
        status: "running",
        started_at: new Date().toISOString(),
      }),
      ...[1, 2, 3].map((done) =>
        progressEvent({ type: "progress", stage, done, total: 3, unit: "step" }),
      ),
      progressEvent({
        type: "stage",
        stage,
        status: "done",
        algorithm: null,
        manifest: null,
      }),
    ]);
    scene.status = "ready";
    scene.stage_runs = stages.map((stage) => ({
      stage,
      status: "done",
      algorithm: `${stage}.fake`,
      config_hash: "mock",
    }));
    return stream([
      ...events,
      progressEvent({
        type: "status",
        status: "ready",
        stage: null,
        algorithm: null,
        manifest: null,
      }),
    ]);
  }),
  http.get(`${base}/:id/objects`, () => HttpResponse.json(objects)),
  http.get(`${base}/:id/search`, ({ request }) => {
    const q = new URL(request.url).searchParams.get("q")?.trim().toLowerCase();
    return HttpResponse.json(
      q
        ? objects
            .filter((o) => o.label.includes(q))
            .map((object) => ({ object, score: 1 }))
        : [],
    );
  }),
  http.get(`${base}/:id/messages`, ({ params }) =>
    HttpResponse.json(messages.get(String(params.id)) || []),
  ),
  http.post(`${base}/:id/queries`, async ({ params, request }) => {
    const body = (await request.json()) as Schemas["QueryRequest"];
    const answer = "1 chair";
    const history = messages.get(String(params.id)) || [];
    history.push(
      {
        id: history.length + 1,
        role: "user",
        content: { question: body.question },
        created_at: new Date().toISOString(),
      },
      {
        id: history.length + 2,
        role: "assistant",
        content: { answer, object_ids: ["chair-1"], evidence: [] },
        created_at: new Date().toISOString(),
      },
    );
    messages.set(String(params.id), history);
    return stream([
      {
        type: "tool",
        tool: "count_objects",
        delta: null,
        answer: null,
        object_ids: [],
        evidence: [],
      },
      {
        type: "delta",
        delta: answer,
        tool: null,
        answer: null,
        object_ids: [],
        evidence: [],
      },
      {
        type: "final",
        answer,
        tool: null,
        delta: null,
        object_ids: ["chair-1"],
        evidence: [],
      },
    ]);
  }),
];
