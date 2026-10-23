/** Mock mode (VITE_API_MODE=mock): MSW serves the API's paths in the browser. */
export async function startMockWorker() {
  const { setupWorker } = await import("msw/browser");
  const { handlers } = await import("./handlers");
  await setupWorker(...handlers).start({ onUnhandledRequest: "bypass" });
}
