import { httpSceneApi } from "../http";
export const mockSceneApi = httpSceneApi;
export async function startMockWorker() {
  const { setupWorker } = await import("msw/browser");
  const { handlers } = await import("./handlers");
  await setupWorker(...handlers).start({ onUnhandledRequest: "bypass" });
}
