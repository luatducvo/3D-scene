// @vitest-environment jsdom
import { afterAll, afterEach, beforeAll, expect, test, vi } from "vitest";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { setupServer } from "msw/node";
import { IntlProvider } from "use-intl";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { sceneApi } from "../lib/api";
import type { Scene } from "../lib/api/types";
import { handlers } from "../lib/api/mock/handlers";
import { useViewer } from "../lib/store/viewerStore";
import { viewMode } from "./viewer/view";
import { SceneExplorer } from "./SceneExplorer";
import en from "../../messages/en.json";

// The WebGL canvas is the only dynamic import; canvas hovers and clicks go through the store.
vi.mock("./viewer/SceneCanvas", () => ({ default: () => null }));

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
    <IntlProvider locale="en" timeZone="UTC" messages={en}>
      <QueryClientProvider client={new QueryClient()}>
        <SceneExplorer scene={scene} />
      </QueryClientProvider>
    </IntlProvider>,
  );
  return scene;
}

test("the explorer opens on the point cloud and switches to the mesh", async () => {
  await explore();
  expect(viewMode(useViewer.getState().layers)).toBe("points");
  fireEvent.click(screen.getByRole("radio", { name: en.layers.mesh }));
  expect(viewMode(useViewer.getState().layers)).toBe("mesh");
});

test("one Points/Mesh switch changes the geometry, with point size only for points", async () => {
  await explore();
  expect(screen.getAllByRole("radio", { name: en.layers.points })).toHaveLength(1);
  expect(screen.getAllByRole("radio", { name: en.layers.mesh })).toHaveLength(1);
  expect(screen.getByRole("slider", { name: en.ui.pointSize })).toBeTruthy();
  fireEvent.click(screen.getByRole("radio", { name: en.layers.mesh }));
  expect(screen.queryByRole("slider", { name: en.ui.pointSize })).toBeNull();
});

test("one Instance Colors switch paints each Object in its own colour, in either geometry", async () => {
  await explore();
  const instances = screen.getByRole("switch", { name: en.appearance.instances });
  fireEvent.click(instances);
  expect(useViewer.getState().appearance).toBe("instances");
  fireEvent.click(screen.getByRole("radio", { name: en.layers.mesh }));
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

test("clicking a Search Hit selects it and empties the Search box", async () => {
  await explore();
  const box = screen.getByRole("searchbox", { name: en.search }) as HTMLInputElement;
  fireEvent.change(box, { target: { value: "sofa" } });
  await waitFor(() =>
    expect(useViewer.getState().highlightedIds).toEqual(["sofa-1"]),
  );
  useViewer.getState().click("sofa-1");
  await waitFor(() => expect(box.value).toBe(""));
  expect(useViewer.getState().selectedId).toBe("sofa-1");
  expect(useViewer.getState().highlightedIds).toEqual([]);
});

test("Object details opens only on request, follows the Selection and closes without one", async () => {
  await explore();
  const details = () =>
    screen.getByRole("button", { name: en.ui.objectDetails }) as HTMLButtonElement;
  const panel = () => screen.queryByRole("complementary", { name: en.ui.objectDetails });
  expect(details().disabled).toBe(true);
  act(() => useViewer.getState().click("sofa-1"));
  expect(panel()).toBeNull();
  expect(details().disabled).toBe(false);
  fireEvent.click(details());
  await waitFor(() => expect(panel()?.textContent).toContain("sofa"));
  act(() => useViewer.getState().click("table-1"));
  await waitFor(() => expect(panel()?.textContent).toContain("coffee table"));
  fireEvent.click(details());
  expect(panel()).toBeNull();
  expect(useViewer.getState().selectedId).toBe("table-1");
  fireEvent.click(details());
  act(() => useViewer.getState().click(null));
  expect(panel()).toBeNull();
  expect(details().disabled).toBe(true);
});
