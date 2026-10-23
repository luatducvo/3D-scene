// @vitest-environment jsdom
import { afterAll, afterEach, beforeAll, expect, test, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { setupServer } from "msw/node";
import { App } from "./App";
import { handlers } from "./lib/api/mock/handlers";

const server = setupServer(...handlers);
vi.mock("./components/viewer/SceneCanvas", () => ({ default: () => null }));
beforeAll(() => {
  server.listen({ onUnhandledRequest: "error" });
  // jsdom has no Worker; the quality module has its own tests.
  vi.stubGlobal(
    "Worker",
    class {
      terminate() {}
    },
  );
});
afterEach(() => {
  cleanup();
  server.resetHandlers();
});
afterAll(() => server.close());

function Location() {
  return <output data-testid="path">{useLocation().pathname}</output>;
}

test("root redirects to the library and capture navigation works without a page reload", async () => {
  render(
    <MemoryRouter initialEntries={["/"]}>
      <App />
      <Location />
    </MemoryRouter>,
  );
  await screen.findByRole("heading", { name: "Your Scenes" });
  expect(screen.getByTestId("path").textContent).toBe("/en");
  fireEvent.click(screen.getByRole("link", { name: "+ Create a scene" }));
  await screen.findByRole("heading", { name: "Bring your space into 3D." });
  expect(screen.getByTestId("path").textContent).toBe("/en/scenes/new");
  expect(screen.getByRole("textbox", { name: "Scene name" })).toBeTruthy();
});

test("direct Scene links load the identified Scene", async () => {
  render(
    <MemoryRouter initialEntries={["/en/scenes/demo"]}>
      <App />
      <Location />
    </MemoryRouter>,
  );
  // Scene data and WebGL failures have separate handling; routing must retain the Scene id.
  await waitFor(() =>
    expect(screen.getByRole("button", { name: "Options" })).toBeTruthy(),
  );
  expect(screen.getByTestId("path").textContent).toBe("/en/scenes/demo");
});

test("unknown paths show a route error with a library link", async () => {
  render(
    <MemoryRouter initialEntries={["/missing"]}>
      <App />
    </MemoryRouter>,
  );
  await screen.findByRole("heading", { name: "This page could not be found." });
  expect(
    screen.getByRole("link", { name: "Back to library" }).getAttribute("href"),
  ).toBe("/en");
});

test("Scene filters and Search can be cleared without leaving the library", async () => {
  render(
    <MemoryRouter initialEntries={["/en"]}>
      <App />
    </MemoryRouter>,
  );
  await screen.findByRole("link", { name: "Open scene" });
  fireEvent.click(screen.getByRole("button", { name: "Processing · 0" }));
  expect(
    screen.getByRole("heading", { name: "No matching scenes" }),
  ).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));
  expect(screen.getByRole("link", { name: "Open scene" })).toBeTruthy();
  fireEvent.change(screen.getByRole("searchbox", { name: "Find a scene…" }), {
    target: { value: "unmatched capture" },
  });
  expect(screen.queryByRole("link", { name: "Open scene" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));
  expect(screen.getByRole("link", { name: "Open scene" })).toBeTruthy();
});

test("shared navigation tracks the Scene and capture routes", async () => {
  render(
    <MemoryRouter initialEntries={["/en/scenes/demo"]}>
      <App />
      <Location />
    </MemoryRouter>,
  );
  await screen.findByRole("button", { name: "Options" });
  expect(
    screen.getByRole("link", { name: "Explore" }).getAttribute("aria-current"),
  ).toBe("page");
  fireEvent.click(screen.getByRole("link", { name: "Capture" }));
  await screen.findByRole("textbox", { name: "Scene name" });
  expect(
    screen
      .getByRole("link", { name: "Capture" })
      .getAttribute("aria-current"),
  ).toBe("page");
  expect(screen.getByRole("region", { name: "Capture form" }).tabIndex).toBe(0);
  expect(screen.getByTestId("path").textContent).toBe("/en/scenes/new");
});
