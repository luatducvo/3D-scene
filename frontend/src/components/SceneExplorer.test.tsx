import { afterAll, afterEach, beforeAll, expect, test } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { setupServer } from "msw/node";
import { http, HttpResponse } from "msw";
import { NextIntlClientProvider } from "next-intl";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { PLYLoader } from "three/examples/jsm/loaders/PLYLoader.js";
import { sceneApi } from "../lib/api";
import { apiOrigin } from "../lib/api/http";
import { handlers } from "../lib/api/mock/handlers";
import { useViewer } from "../lib/store/viewerStore";
import {
  DIM,
  normalizeSimilarities,
  objectIndices,
  Painter,
} from "./viewer/highlight";
import { PipelineInspector } from "./PipelineInspector";
import { SceneExplorer } from "./SceneExplorer";
import { Header } from "./Header";
import { SearchStatus } from "./SearchStatus";
import en from "../../messages/en.json";

// The mock SceneApi that mock mode serves in the browser.
const server = setupServer(...handlers);
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  useViewer.getState().reset();
});
afterAll(() => server.close());

const render = (node: React.ReactNode) =>
  renderToStaticMarkup(
    <NextIntlClientProvider locale="en" timeZone="UTC" messages={en}>
      <QueryClientProvider client={new QueryClient()}>
        {node}
      </QueryClientProvider>
    </NextIntlClientProvider>,
  );

test("search paints raw semantic similarity on matched geometry and dims the rest of the room", async () => {
  const scene = await sceneApi.getScene("demo");
  const membership = await sceneApi.getMembership(
    scene.assets!.membership_url!,
  );
  const ply = await (await fetch(scene.assets!.points_url!)).text();
  const geometry = new PLYLoader().parse(ply);
  expect(membership.pointCount).toBe(geometry.getAttribute("position").count);

  const hits = await sceneApi.searchObjects("demo", "sofa");
  // Exercise the real transport, normalization and painter used by the explorer.
  const similarities = normalizeSimilarities(
    Object.fromEntries(hits.map((hit) => [hit.object.id, hit.raw_similarity])),
  );
  useViewer.getState().showResult(
    useViewer.getState().beginResult(),
    "search",
    hits.map((hit) => hit.object.id),
    similarities,
  );
  expect(useViewer.getState().highlightedIds).toEqual(["sofa-1"]);

  const base = geometry.getAttribute("color").array as Float32Array;
  const colors = new Float32Array(base);
  new Painter(colors, base, membership.points, membership.ids.length).highlight(
    objectIndices(membership, useViewer.getState().highlightedIds),
    [similarities["sofa-1"]],
  );
  const hot = [0.9325, 0.1675, 0.1675].map(Math.fround);
  const sofa = membership.points(membership.ids.indexOf("sofa-1"));
  expect(sofa.length).toBeGreaterThan(100);
  for (const i of sofa)
    expect([...colors.subarray(3 * i, 3 * i + 3)]).toEqual(hot);
  // Point 0 is on the floor, which belongs to no Object.
  for (let c = 0; c < 3; c++) expect(colors[c]).toBeCloseTo(base[c] * DIM);
});

test("an unavailable GPU Target shows a localized search message", async () => {
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
    <SearchStatus fetching={false} error={error} count={0} onClear={() => {}} />,
  );
  expect(markup).toContain(en.searchErrors.COMPUTE_UNAVAILABLE);
  expect(markup).not.toContain("Target gpu has no URL");
});

test("navigation is English-only and offers no language switch", () => {
  const markup = render(<Header />);
  expect(markup).not.toContain("language-switch");
});

test("the explorer offers Search and inspection but no way to ask the Scene", async () => {
  const scene = await sceneApi.getScene("demo");
  const markup = render(<SceneExplorer scene={scene} />);
  expect(markup).toContain('type="search"');
  expect(markup).not.toMatch(/\bask\b|question/i);
});

test("Inspector explains Stage inputs and missing execution facts without a Target", async () => {
  const scene = await sceneApi.getScene("demo");
  const markup = render(
    <PipelineInspector scene={{ ...scene, stage_runs: [] }} />,
  );
  expect(markup).toContain("Input Frames");
  expect(markup).toContain("Reconstruction");
  expect(markup).toContain("Not available");
  expect(markup).not.toContain("<pre");
});
