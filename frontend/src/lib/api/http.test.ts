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
test("questions preserve tool, split UTF-8 deltas and final citations", async () => {
  server.use(
    http.post(
      "http://localhost:8000/api/v1/scenes/room/queries",
      () =>
        new HttpResponse(
          new ReadableStream({
            start(controller) {
              const bytes = new TextEncoder().encode(
                'event: tool\ndata: {"type":"tool","tool":"count_objects"}\n\nevent: delta\ndata: {"type":"delta","delta":"café"}\n\nevent: final\ndata: {"type":"final","answer":"one chair","object_ids":["chair-1"],"evidence":[]}\n\n',
              );
              for (let i = 0; i < bytes.length; i += 3)
                controller.enqueue(bytes.slice(i, i + 3));
              controller.close();
            },
          }),
          { headers: { "Content-Type": "text/event-stream" } },
        ),
    ),
  );
  const events: unknown[] = [];
  await sceneApi.askQuestion("room", { question: "Count chairs" }, (event) =>
    events.push(event),
  );
  expect(events).toEqual([
    { type: "tool", tool: "count_objects" },
    { type: "delta", delta: "café" },
    {
      type: "final",
      answer: "one chair",
      object_ids: ["chair-1"],
      evidence: [],
    },
  ]);
});
test("question stream supports CRLF boundaries split between network packets", async () => {
  server.use(
    http.post(
      "http://localhost:8000/api/v1/scenes/room/queries",
      () =>
        new HttpResponse(
          new ReadableStream({
            start(controller) {
              for (const part of [
                'data: {"type":"delta","delta":"hello"}\r',
                "\n\r",
                "\n",
              ])
                controller.enqueue(new TextEncoder().encode(part));
              controller.close();
            },
          }),
        ),
    ),
  );
  const events: unknown[] = [];
  await sceneApi.askQuestion("room", { question: "Hello" }, (event) =>
    events.push(event),
  );
  expect(events).toEqual([{ type: "delta", delta: "hello" }]);
});
test("a question reports refused and mid-stream errors with their codes", async () => {
  server.use(
    http.post("http://localhost:8000/api/v1/scenes/room/queries", () =>
      HttpResponse.json(
        { error: { code: "SCENE_NOT_READY", message: "Process first" } },
        { status: 409 },
      ),
    ),
  );
  await expect(
    sceneApi.askQuestion("room", { question: "?" }, () => {}),
  ).rejects.toMatchObject({ code: "SCENE_NOT_READY" });
  server.use(
    http.post(
      "http://localhost:8000/api/v1/scenes/room/queries",
      () =>
        new HttpResponse(
          'event: tool\ndata: {"type":"tool","tool":"count_objects"}\n\n' +
            'event: error\ndata: {"error":{"code":"QA_STEP_LIMIT","message":"No answer"}}\n\n',
          { headers: { "Content-Type": "text/event-stream" } },
        ),
    ),
  );
  const seen: string[] = [];
  await expect(
    sceneApi.askQuestion("room", { question: "?" }, (e) => seen.push(e.type)),
  ).rejects.toMatchObject({ code: "QA_STEP_LIMIT" });
  expect(seen).toEqual(["tool"]);
});
