import { http, HttpResponse } from "msw";
import {
  STAGES,
  progressEvent,
  type Scene,
  type ProgressEvent,
} from "../types";
import { apiOrigin } from "../http";
import { demoObjects, roomMembership, roomPointCloud, roomMesh } from "./room";
const base = `${apiOrigin}/api/v1/scenes`;
const objects = demoObjects;
const demoAssets = {
  mesh_url: `${apiOrigin}/api/v1/mock/room.glb`,
  points_url: `${apiOrigin}/api/v1/mock/room.ply`,
  membership_url: `${apiOrigin}/api/v1/mock/room-membership.bin`,
};
const scenes = new Map<string, Scene>([
  [
    "demo",
    {
      id: "demo",
      name: "Living room - Demo",
      status: "ready",
      created_at: new Date().toISOString(),
      assets: demoAssets,
      stage_runs: STAGES.map((stage) => ({
        stage,
        algorithm: `${stage}.fake`,
        status: "done",
        started_at: "2026-10-18T00:00:00Z",
        updated_at: "2026-10-18T00:00:02Z",
        manifest: {
          num_inputs: 24,
          num_keyframes: 20,
          num_objects: 4,
          num_points: 12000,
        },
      })),
    },
  ],
]);
const stages = STAGES;
const missing = () =>
  HttpResponse.json(
    { error: { code: "NOT_FOUND", message: "Scene not found" } },
    { status: 404 },
  );
const stream = (events: ProgressEvent[]) =>
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
    `${apiOrigin}/api/v1/mock/room.glb`,
    () =>
      new HttpResponse(roomMesh(), {
        headers: { "Content-Type": "model/gltf-binary" },
      }),
  ),
  http.get(
    `${apiOrigin}/api/v1/mock/room.ply`,
    () =>
      new HttpResponse(roomPointCloud(), {
        headers: { "Content-Type": "application/octet-stream" },
      }),
  ),
  http.get(
    `${apiOrigin}/api/v1/mock/room-membership.bin`,
    () =>
      new HttpResponse(roomMembership(), {
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
            .filter((o) => o.label.toLowerCase().includes(q))
            .map((object, index) => ({
              object,
              score: 1,
              raw_similarity: 0.8 - index * 0.1,
            }))
        : [],
    );
  }),
];
