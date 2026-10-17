import { afterAll, afterEach, beforeAll, expect, test } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { setupServer } from "msw/node";
import { http, HttpResponse } from "msw";
import { NextIntlClientProvider } from "next-intl";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Color } from "three";
import { PLYLoader } from "three/examples/jsm/loaders/PLYLoader.js";
import { sceneApi } from "../lib/api";
import { apiOrigin } from "../lib/api/http";
import { handlers } from "../lib/api/mock/handlers";
import { useViewer } from "../lib/store/viewerStore";
import { focus } from "./viewer/camera";
import {
  DIM,
  HIGHLIGHT_COLOR,
  objectIndices,
  Painter,
} from "./viewer/highlight";
import { SceneExplorer } from "./SceneExplorer";
import { SearchStatus } from "./SearchStatus";
import en from "../../messages/en.json";
import vi from "../../messages/vi.json";

// The mock SceneApi that mock mode serves in the browser.
const server = setupServer(...handlers);
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  useViewer.getState().reset();
});
afterAll(() => server.close());

const render = (node: React.ReactNode, locale = "en", messages: object = en) =>
  renderToStaticMarkup(
    <NextIntlClientProvider locale={locale} timeZone="UTC" messages={messages}>
      <QueryClientProvider client={new QueryClient()}>
        {node}
      </QueryClientProvider>
    </NextIntlClientProvider>,
  );

test("search highlights its hits on their own points and dims the rest of the room", async () => {
  const scene = await sceneApi.getScene("demo");
  const membership = await sceneApi.getMembership(
    scene.assets!.membership_url!,
  );
  const ply = await (await fetch(scene.assets!.points_url!)).text();
  const geometry = new PLYLoader().parse(ply);
  expect(membership.pointCount).toBe(geometry.getAttribute("position").count);

  const hits = await sceneApi.searchObjects("demo", "sofa");
  // The explorer focuses search hits, which highlights them.
  focus(hits.map((hit) => hit.object.id));
  expect(useViewer.getState().highlightedIds).toEqual(["sofa-1"]);

  const base = geometry.getAttribute("color").array as Float32Array;
  const colors = new Float32Array(base);
  new Painter(colors, base, membership.points, membership.ids.length).highlight(
    objectIndices(membership, useViewer.getState().highlightedIds),
  );
  const green = new Color(HIGHLIGHT_COLOR).toArray().map(Math.fround);
  const sofa = membership.points(membership.ids.indexOf("sofa-1"));
  expect(sofa.length).toBeGreaterThan(100);
  for (const i of sofa)
    expect([...colors.subarray(3 * i, 3 * i + 3)]).toEqual(green);
  // Point 0 is on the floor, which belongs to no Object.
  for (let c = 0; c < 3; c++) expect(colors[c]).toBeCloseTo(base[c] * DIM);
});

test.each([
  ["en", en],
  ["vi", vi],
] as const)(
  "an unavailable GPU Target shows a localized search message in %s",
  async (locale, messages) => {
    server.use(
      http.get(`${apiOrigin}/api/v1/scenes/:id/search`, () =>
        HttpResponse.json(
          {
            error: {
              code: "COMPUTE_UNAVAILABLE",
              message: "Target gpu has no URL",
            },
          },
          { status: 503 },
        ),
      ),
    );
    const error = await sceneApi.searchObjects("demo", "chair").catch((e) => e);
    const markup = render(
      <SearchStatus
        fetching={false}
        error={error}
        count={0}
        onClear={() => {}}
      />,
      locale,
      messages,
    );
    expect(markup).toContain(messages.searchErrors.COMPUTE_UNAVAILABLE);
    expect(markup).not.toContain("Target gpu has no URL");
  },
);

test("a Scene published before membership shows its points and asks for a reprocess", async () => {
  const legacy = await sceneApi.getScene("legacy");
  expect(legacy.assets?.points_url).toBeTruthy();
  expect(render(<SceneExplorer scene={legacy} />)).toContain(
    en.ui.reprocessForHighlight,
  );
  const current = await sceneApi.getScene("demo");
  expect(render(<SceneExplorer scene={current} />)).not.toContain(
    en.ui.reprocessForHighlight,
  );
});
