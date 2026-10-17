import { http, HttpResponse } from "msw";
import {
  STAGES,
  progressEvent,
  type Scene,
  type ProgressEvent,
  type QueryEvent,
  type Schemas,
} from "../types";
import { apiOrigin } from "../http";
import { demoObjects, roomPointCloud } from "./room";
const base = `${apiOrigin}/api/v1/scenes`;
const objects = demoObjects;
const demoAssets = { points_url: `${apiOrigin}/api/v1/mock/room.ply` };
const scenes = new Map<string, Scene>([
  [
    "demo",
    {
      id: "demo",
      name: "Phòng khách · Demo",
      status: "ready",
      created_at: new Date().toISOString(),
      assets: demoAssets,
      stage_runs: [],
    },
  ],
]);
const messages = new Map<string, Schemas["Message"][]>();
const stages = STAGES;
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
  http.get(
    `${apiOrigin}/api/v1/mock/room.ply`,
    () =>
      new HttpResponse(roomPointCloud(), {
        headers: { "Content-Type": "application/octet-stream" },
      }),
  ),
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
    if (scene.status === "processing")
      return HttpResponse.json(
        { error: { code: "SCENE_BUSY", message: "Processing is active" } },
        { status: 409 },
      );
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
        progressEvent({
          type: "progress",
          stage,
          done,
          total: 3,
          unit: "step",
        }),
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
    scene.assets = demoAssets;
    scene.stage_runs = stages.map((stage) => ({
      stage,
      status: "done",
      algorithm: `${stage}.fake`,
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
            .filter((o) =>
              [
                o.label,
                o.label_vi || "",
                ...Object.values(o.attributes || {}).flat(),
              ].some((value) => value.toLowerCase().includes(q)),
            )
            .map((object) => ({ object, score: 1 }))
        : [],
    );
  }),
  http.get(`${base}/:id/messages`, ({ params }) =>
    HttpResponse.json(messages.get(String(params.id)) || []),
  ),
  http.post(`${base}/:id/queries`, async ({ params, request }) => {
    const body = (await request.json()) as Schemas["QueryRequest"];
    const vietnamese = /[à-ỹ]|bao|phòng|sofa.*bàn/i.test(body.question);
    const answer = vietnamese
      ? "Đây là scene mẫu với một sofa, một bàn cà phê và một chậu cây. Vùng liên quan đã được tô sáng trong không gian 3D."
      : "This sample scene contains a sofa, a coffee table and a plant. The relevant region is highlighted in 3D.";
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
        content: { answer, object_ids: ["sofa-1"], evidence: [] },
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
        object_ids: ["sofa-1"],
        evidence: [],
      },
    ]);
  }),
];
