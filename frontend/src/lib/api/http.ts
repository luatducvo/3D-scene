import createClient from "openapi-fetch";
import type { paths } from "./schema";
import type { ProgressEvent, QueryEvent, Schemas } from "./types";
import { ApiError, toApiError } from "./errors";
import { consumeSSE } from "./sse";
import { decodeMembership } from "./membership";
import { shrinkAll } from "../upload/shrink";
export { ApiError } from "./errors";
export const apiOrigin =
  (typeof window === "undefined"
    ? process.env.API_INTERNAL_URL
    : process.env.NEXT_PUBLIC_API_URL) || "http://localhost:8000";
// fetch is looked up per request, so MSW can intercept it after this module loads.
export const typedClient = createClient<paths>({
  baseUrl: apiOrigin,
  fetch: (request) => globalThis.fetch(request),
});
/** The response data, or the API's error as an ApiError. */
async function data<T>(
  call: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  const { data, error, response } = await call;
  if (!response.ok) throw toApiError(error, response.status);
  return data as T;
}
const scene = (id: string) => ({ params: { path: { scene_id: id } } });
/** Reconnects a dropped progress stream after this delay while the Scene is processing. */
const RECONNECT_MS = 1000;
/** The browser's only way to the backend; MSW serves the same paths in mock mode. */
export const sceneApi = {
  listScenes: () => data(typedClient.GET("/api/v1/scenes")),
  createScene: (name: string) =>
    data(typedClient.POST("/api/v1/scenes", { body: { name } })),
  deleteScene: async (id: string) => {
    await data(typedClient.DELETE("/api/v1/scenes/{scene_id}", scene(id)));
  },
  getScene: (id: string) =>
    data(typedClient.GET("/api/v1/scenes/{scene_id}", scene(id))),
  startProcessing: async (id: string) => {
    await data(
      typedClient.POST("/api/v1/scenes/{scene_id}/process", scene(id)),
    );
  },
  listObjects: (id: string) =>
    data(typedClient.GET("/api/v1/scenes/{scene_id}/objects", scene(id))),
  searchObjects: (id: string, q: string) =>
    data(
      typedClient.GET("/api/v1/scenes/{scene_id}/search", {
        params: { path: { scene_id: id }, query: { q } },
      }),
    ),
  /** Object membership from `SceneAssets.membership_url`, decoded (api.md "Object membership"). */
  getMembership: async (url: string) => {
    const response = await fetch(url);
    if (!response.ok)
      throw toApiError(
        await response.json().catch(() => null),
        response.status,
      );
    return decodeMembership(await response.arrayBuffer());
  },
  getMessages: (id: string) =>
    data(typedClient.GET("/api/v1/scenes/{scene_id}/messages", scene(id))),
  /**
   * Shrinks photos to ingest's size first (the first half of progress), then sends them with
   * XMLHttpRequest, because fetch cannot report upload progress.
   */
  uploadFiles: async (
    id: string,
    files: File[],
    progress?: (ratio: number) => void,
  ) => {
    const prepared = await shrinkAll(files, (ratio) => progress?.(ratio / 2));
    return new Promise<void>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      const body = new FormData();
      prepared.forEach((file) => body.append("files", file));
      xhr.open("POST", `${apiOrigin}/api/v1/scenes/${id}/uploads`);
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable)
          progress?.(0.5 + event.loaded / event.total / 2);
      };
      xhr.onerror = () =>
        reject(new ApiError("NETWORK_ERROR", "Upload connection failed"));
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          progress?.(1);
          return resolve();
        }
        let body: unknown = null;
        try {
          body = JSON.parse(xhr.responseText);
        } catch {}
        reject(toApiError(body, xhr.status));
      };
      xhr.send(body);
    });
  },
  /**
   * Streams a Scene's progress: the replayed state first, then live events, until a terminal
   * status. A dropped connection reconnects and replays; the returned function stops.
   */
  subscribeProgress: (id: string, receive: (event: ProgressEvent) => void) => {
    const stop = new AbortController();
    let finished = false;
    void (async () => {
      while (!finished && !stop.signal.aborted) {
        try {
          const response = await fetch(
            `${apiOrigin}/api/v1/scenes/${id}/events`,
            { signal: stop.signal, headers: { Accept: "text/event-stream" } },
          );
          await consumeSSE<ProgressEvent>(response, (event) => {
            if (event.type === "status" && event.status !== "processing")
              finished = true;
            receive(event);
          });
        } catch (error) {
          // A refused stream (for example a deleted Scene) will not succeed on retry.
          if (error instanceof ApiError) return;
        }
        if (!finished && !stop.signal.aborted)
          await new Promise((wake) => setTimeout(wake, RECONNECT_MS));
      }
    })();
    return () => stop.abort();
  },
  askQuestion: async (
    id: string,
    body: Schemas["QueryRequest"],
    receive: (event: QueryEvent) => void,
    signal?: AbortSignal,
  ) =>
    consumeSSE(
      await fetch(`${apiOrigin}/api/v1/scenes/${id}/queries`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal,
      }),
      receive,
    ),
};
