import createClient from "openapi-fetch";
import type { paths } from "./schema";
import type { SceneApi } from "./port";
import { consumeSSE } from "./sse";
export const apiOrigin =
  (typeof window === "undefined"
    ? process.env.API_INTERNAL_URL
    : process.env.NEXT_PUBLIC_API_URL) || "http://localhost:8000";
export const typedClient = createClient<paths>({ baseUrl: apiOrigin });
export { ApiError } from "./errors";
import { ApiError } from "./errors";
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiOrigin}/api/v1${path}`, init);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new ApiError(
      body.error?.code || "REQUEST_FAILED",
      body.error?.message || `${response.status}`,
    );
  }
  return response.status === 204 ? (undefined as T) : response.json();
}
const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});
export const httpSceneApi: SceneApi = {
  listScenes: () => request("/scenes"),
  createScene: (name) => request("/scenes", json({ name })),
  deleteScene: (id) => request(`/scenes/${id}`, { method: "DELETE" }),
  getScene: (id) => request(`/scenes/${id}`),
  startProcessing: async (id, stage) => {
    await request(`/scenes/${id}/process`, json({ from_stage: stage }));
  },
  listObjects: (id) => request(`/scenes/${id}/objects`),
  searchObjects: (id, query) =>
    request(`/scenes/${id}/search?q=${encodeURIComponent(query)}`),
  getMessages: (id) => request(`/scenes/${id}/messages`),
  uploadFiles: (id, files, progress) =>
    new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      const body = new FormData();
      files.forEach((file) => body.append("files", file));
      xhr.open("POST", `${apiOrigin}/api/v1/scenes/${id}/uploads`);
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable) progress?.(event.loaded / event.total);
      };
      xhr.onerror = () =>
        reject(new ApiError("NETWORK_ERROR", "Upload connection failed"));
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          progress?.(1);
          resolve();
        } else {
          let error;
          try {
            error = JSON.parse(xhr.responseText).error;
          } catch {}
          reject(
            new ApiError(
              error?.code || "UPLOAD_FAILED",
              error?.message || `${xhr.status}`,
            ),
          );
        }
      };
      xhr.send(body);
    }),
  subscribeProgress: (id, receive) => {
    const source = new EventSource(`${apiOrigin}/api/v1/scenes/${id}/events`);
    const handler = (event: MessageEvent) => receive(JSON.parse(event.data));
    source.addEventListener("stage", handler);
    source.addEventListener("status", handler);
    source.onmessage = handler;
    return () => source.close();
  },
  askQuestion: async (id, body, receive, signal) =>
    consumeSSE(
      await fetch(`${apiOrigin}/api/v1/scenes/${id}/queries`, {
        ...json(body),
        signal,
      }),
      receive,
    ),
};
