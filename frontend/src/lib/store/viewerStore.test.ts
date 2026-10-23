import { afterEach, expect, test } from "vitest";
import { clickable, interaction, useViewer } from "./viewerStore";

const viewer = () => useViewer.getState();
const at = { x: 10, y: 20 };
/** A finished Search for `text` whose hits are `ids`. */
function searched(text: string, ids: string[]) {
  viewer().setSearch(text);
  viewer().showResult(
    viewer().beginResult(),
    ids,
    Object.fromEntries(ids.map((id) => [id, 1])),
  );
}
afterEach(() => viewer().reset());

test("idle hovers Objects, and a click on one selects it", () => {
  expect(interaction(viewer())).toBe("idle");
  viewer().hover({ id: "chair", ...at });
  expect(viewer().hovered?.id).toBe("chair");
  viewer().click(null);
  expect(interaction(viewer())).toBe("idle");
  viewer().click("chair");
  expect(interaction(viewer())).toBe("selection");
  expect(viewer().selectedId).toBe("chair");
});

test("a Search turns hover off and only its hits can be clicked", () => {
  viewer().hover({ id: "chair", ...at });
  searched("sofa", ["sofa-1"]);
  expect(interaction(viewer())).toBe("search");
  expect(viewer().hovered).toBeNull();
  viewer().hover({ id: "sofa-1", ...at });
  expect(viewer().hovered).toBeNull();
  expect(clickable(viewer(), "sofa-1")).toBe(true);
  expect(clickable(viewer(), "chair")).toBe(false);
  viewer().click("chair");
  viewer().click(null);
  expect(interaction(viewer())).toBe("search");
  expect(viewer().highlightedIds).toEqual(["sofa-1"]);
});

test("a Search counts while its text is there, before any hit arrives", () => {
  viewer().setSearch("lamp");
  expect(interaction(viewer())).toBe("search");
  expect(clickable(viewer(), "chair")).toBe(false);
  viewer().setSearch("  ");
  expect(interaction(viewer())).toBe("idle");
});

test("clicking a hit selects it, empties the Search box and drops the Highlight", () => {
  searched("sofa", ["sofa-1"]);
  viewer().click("sofa-1");
  expect(interaction(viewer())).toBe("selection");
  expect(viewer().selectedId).toBe("sofa-1");
  expect(viewer().search).toBe("");
  expect(viewer().highlightedIds).toEqual([]);
  expect(viewer().similarities).toBeNull();
});

test("a Search response that arrives after a Selection is dropped", () => {
  viewer().setSearch("sofa");
  const version = viewer().beginResult();
  viewer().showResult(version, ["sofa-1", "chair"], { "sofa-1": 1, chair: 0 });
  viewer().click("chair");
  expect(viewer().showResult(version, ["sofa-1"], { "sofa-1": 1 })).toBe(false);
  expect(viewer().highlightedIds).toEqual([]);
});

test("a Selection turns hover off, and another click switches or drops it", () => {
  viewer().click("chair");
  viewer().hover({ id: "sofa-1", ...at });
  expect(viewer().hovered).toBeNull();
  expect(clickable(viewer(), "sofa-1")).toBe(true);
  viewer().click("sofa-1");
  expect(viewer().selectedId).toBe("sofa-1");
  viewer().click(null);
  expect(interaction(viewer())).toBe("idle");
  viewer().hover({ id: "chair", ...at });
  expect(viewer().hovered?.id).toBe("chair");
});

test("Esc drops the Selection without bringing back the Search, then ends a Search", () => {
  searched("sofa", ["sofa-1"]);
  viewer().click("sofa-1");
  viewer().escape();
  expect(interaction(viewer())).toBe("idle");
  expect(viewer().search).toBe("");
  searched("sofa", ["sofa-1"]);
  viewer().escape();
  expect(interaction(viewer())).toBe("idle");
  expect(viewer().search).toBe("");
  expect(viewer().highlightedIds).toEqual([]);
});

test("typing a Search drops the Selection", () => {
  viewer().click("chair");
  viewer().setSearch("s");
  expect(viewer().selectedId).toBeNull();
  expect(interaction(viewer())).toBe("search");
});

test("going home clears the Search text with the Selection and Highlight", () => {
  searched("sofa", ["sofa-1"]);
  viewer().clear();
  expect(interaction(viewer())).toBe("idle");
  expect(viewer().search).toBe("");
});
