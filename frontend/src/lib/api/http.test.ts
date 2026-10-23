import { beforeAll, afterAll, afterEach, expect, test } from "vitest";
import { setupServer } from "msw/node";
import { http, HttpResponse } from "msw";
import { sceneApi } from "./http";
const server = setupServer(
  http.get("http://localhost:8000/api/v1/scenes", () =>
    HttpResponse.json([{ id: "room", name: "Study", status: "created" }]),
  ),
  http.post("http://localhost:8000/api/v1/scenes", async ({ request }) =>
    HttpResponse.json({
      id: "new-room",
      ...((await request.json()) as object),
    }),
  ),
);
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
test("SceneApi lists captured rooms and creates a named room", async () => {
  expect(await sceneApi.listScenes()).toEqual([
    { id: "room", name: "Study", status: "created" },
  ]);
  expect(await sceneApi.createScene("Kitchen")).toEqual({
    id: "new-room",
    name: "Kitchen",
  });
});
test("a locked capture reports the server error code to the UI", async () => {
  server.use(
    http.delete("http://localhost:8000/api/v1/scenes/room", () =>
      HttpResponse.json(
        { error: { code: "SCENE_BUSY", message: "Processing is active" } },
        { status: 409 },
      ),
    ),
  );
  await expect(sceneApi.deleteScene("room")).rejects.toMatchObject({
    code: "SCENE_BUSY",
    message: "Processing is active",
  });
});
/** Serve `parts` as one SSE response on the Scene's events stream and collect what subscribeProgress receives. */
async function progressFrom(parts: Uint8Array[]) {
  server.use(
    http.get(
      "http://localhost:8000/api/v1/scenes/room/events",
      () =>
        new HttpResponse(
          new ReadableStream({
            start(controller) {
              for (const part of parts) controller.enqueue(part);
              controller.close();
            },
          }),
          { headers: { "Content-Type": "text/event-stream" } },
        ),
    ),
  );
  const events: { type: string }[] = [];
  await new Promise<void>((done) => {
    const stop = sceneApi.subscribeProgress("room", (event) => {
      events.push(event);
      if (event.type === "status") {
        stop();
        done();
      }
    });
  });
  return events;
}
test("progress events keep UTF-8 characters split between network packets", async () => {
  const bytes = new TextEncoder().encode(
    'event: progress\ndata: {"type":"progress","stage":"ingest","done":1,"total":2,"unit":"image"}\n\n' +
      'event: status\ndata: {"type":"status","status":"failed","error":{"message":"café"}}\n\n',
  );
  const parts = [];
  for (let i = 0; i < bytes.length; i += 3) parts.push(bytes.slice(i, i + 3));
  expect(await progressFrom(parts)).toEqual([
    { type: "progress", stage: "ingest", done: 1, total: 2, unit: "image" },
    { type: "status", status: "failed", error: { message: "café" } },
  ]);
});
test("progress events support CRLF boundaries split between network packets", async () => {
  const parts = ['data: {"type":"status","status":"ready"}\r', "\n\r", "\n"];
  expect(
    await progressFrom(parts.map((part) => new TextEncoder().encode(part))),
  ).toEqual([{ type: "status", status: "ready" }]);
});
