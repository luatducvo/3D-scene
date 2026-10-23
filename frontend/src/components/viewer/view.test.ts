import { expect, test } from "vitest";
import {
  defaultLayers,
  focusBounds,
  highlightState,
  homePose,
  showMode,
  viewMode,
  visibleBounds,
  type Bounds,
} from "./view";
import type { SceneObject } from "../../lib/api/types";
const points: Bounds = { min: [0, 0, 0], max: [4, 3, 2.5] },
  mesh: Bounds = { min: [-1, -1, 0], max: [5, 4, 3] };

test("a Scene shows its point cloud when it has one, else its mesh, and never boxes", () => {
  expect(defaultLayers({ points_url: "p.ply", mesh_url: "m.glb" })).toEqual({
    points: true,
    mesh: false,
  });
  expect(defaultLayers({ mesh_url: "m.glb" })).toEqual({
    points: false,
    mesh: true,
  });
  expect(viewMode(defaultLayers({}))).toBeNull();
});

test("switching the view mode shows exactly one room layer", () => {
  const layers = showMode({ points: true, mesh: false }, "mesh");
  expect(layers).toEqual({ points: false, mesh: true });
  expect(viewMode(layers)).toBe("mesh");
});

test("highlighting fails without membership, or with membership that does not fit the shown geometry", () => {
  const assets = { points_url: "p.ply", membership_url: "m.bin" };
  expect(highlightState(assets, "success", {}, "points")).toBe("available");
  expect(highlightState(assets, "pending", {}, "points")).toBe("available");
  expect(highlightState(assets, "error", {}, "points")).toBe("failed");
  expect(
    highlightState(
      { ...assets, membership_url: null },
      "pending",
      {},
      "points",
    ),
  ).toBe("failed");
  // Only the shown layer's fit matters.
  expect(highlightState(assets, "success", { mesh: true }, "points")).toBe(
    "available",
  );
  expect(highlightState(assets, "success", { points: true }, "points")).toBe(
    "failed",
  );
  // Without geometry the viewer already says there is nothing to show.
  expect(highlightState({}, "pending", {}, "points")).toBe("available");
});

test("the room is framed by the visible layer, whichever layer loaded first", () => {
  const shown = { points: false, mesh: true };
  // The point cloud loaded first, but the mesh is what is shown once its bounds are known.
  expect(visibleBounds(shown, { points })).toBe(points);
  expect(visibleBounds(shown, { points, mesh })).toBe(mesh);
  expect(visibleBounds(showMode(shown, "points"), { points, mesh })).toBe(
    points,
  );
  expect(visibleBounds(shown, {})).toBeNull();
});

test("home looks at the room's center from far enough to see all of it", () => {
  const { position, target } = homePose(points);
  expect(target).toEqual([2, 1.5, 1.25]);
  const distance = 4 * 1.35;
  expect(position).toEqual([
    2 + distance * 0.6,
    1.5 - distance * 0.8,
    1.25 + distance * 0.7,
  ]);
  expect(homePose(null).target).toEqual([0, 0, 1.5]);
});

test("focus encloses rotated Object boxes and ignores unknown ids", () => {
  const box = (id: string, center: number[], size: number[], yaw = 0) =>
    ({ id, label: id, box: { center, size, yaw } }) as unknown as SceneObject;
  const objects = [
    box("table", [0, 0, 0.4], [2, 1, 0.8], Math.PI / 2),
    box("chair", [3, 0, 0.5], [0.5, 0.5, 1]),
  ];
  const turned = focusBounds(objects, ["table"])!;
  // A quarter turn swaps the footprint's width and depth.
  turned.min.forEach((v, i) => expect(v).toBeCloseTo([-0.5, -1, 0][i]));
  turned.max.forEach((v, i) => expect(v).toBeCloseTo([0.5, 1, 0.8][i]));
  const both = focusBounds(objects, ["table", "chair", "missing"])!;
  expect(both.max[0]).toBeCloseTo(3.25);
  expect(focusBounds(objects, ["missing"])).toBeNull();
});
