// @vitest-environment jsdom
import { afterAll, afterEach, beforeAll, expect, test, vi } from "vitest";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import { setupServer } from "msw/node";
import { NextIntlClientProvider } from "next-intl";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { sceneApi } from "../lib/api";
import type { Scene } from "../lib/api/types";
import { handlers } from "../lib/api/mock/handlers";
import { useViewer } from "../lib/store/viewerStore";
import { viewMode } from "./viewer/view";
import { SceneExplorer } from "./SceneExplorer";
import en from "../../messages/en.json";

// The WebGL canvas is the only dynamic import; canvas hovers and clicks go through the store.
vi.mock("next/dynamic", () => ({ default: () => () => null }));

const server = setupServer(...handlers);
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  cleanup();
  server.resetHandlers();
  useViewer.getState().reset();
});
afterAll(() => server.close());

async function explore(change: (scene: Scene) => Scene = (scene) => scene) {
  const scene = change(await sceneApi.getScene("demo"));
  render(
    <NextIntlClientProvider locale="en" timeZone="UTC" messages={en}>
      <QueryClientProvider client={new QueryClient()}>
        <SceneExplorer scene={scene} />
      </QueryClientProvider>
    </NextIntlClientProvider>,
  );
  return scene;
}

test("the explorer opens on the point cloud and switches to the mesh", async () => {
  await explore();
  expect(viewMode(useViewer.getState().layers)).toBe("points");
  fireEvent.click(screen.getByRole("button", { name: en.layers.mesh }));
  expect(viewMode(useViewer.getState().layers)).toBe("mesh");
});

test("one Points/Mesh switch changes the geometry, with point size only for points", async () => {
  await explore();
  expect(screen.getAllByRole("button", { name: en.layers.points })).toHaveLength(1);
  expect(screen.getAllByRole("button", { name: en.layers.mesh })).toHaveLength(1);
  expect(screen.getByRole("slider", { name: en.ui.pointSize })).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: en.layers.mesh }));
  expect(screen.queryByRole("slider", { name: en.ui.pointSize })).toBeNull();
  expect(screen.queryByRole("switch", { name: en.layers.mesh })).toBeNull();
});

test("there is no Display layers panel and no topbar Clear button", async () => {
  await explore();
  expect(screen.queryByRole("button", { name: "Display layers" })).toBeNull();
  expect(screen.queryByRole("button", { name: "Clear" })).toBeNull();
});

test("one Instance Colors switch paints each Object in its own colour, in either geometry", async () => {
  await explore();
  const instances = screen.getByRole("switch", { name: en.appearance.instances });
  expect(screen.queryByRole("button", { name: "Original" })).toBeNull();
  fireEvent.click(instances);
  expect(useViewer.getState().appearance).toBe("instances");
  fireEvent.click(screen.getByRole("button", { name: en.layers.mesh }));
  expect(useViewer.getState().appearance).toBe("instances");
  fireEvent.click(instances);
  expect(useViewer.getState().appearance).toBe("original");
});

test("Instance Colors is disabled, with the notice, when the Scene has no Object Membership", async () => {
  await explore((scene) => ({
    ...scene,
    assets: { ...scene.assets, membership_url: null },
  }));
  expect(
    screen
      .getByRole("switch", { name: en.appearance.instances })
      .hasAttribute("disabled"),
  ).toBe(true);
  expect(screen.getByText(en.ui.highlightFailed)).toBeTruthy();
});
