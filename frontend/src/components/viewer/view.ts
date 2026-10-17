/** The viewer's rules, free of WebGL: which layers show, which bounds frame the room, where the camera goes. */
import type { SceneObject, Schemas } from "../../lib/api/types";
export type Point = [number, number, number];
export type Bounds = { min: Point; max: Point };
export type Layer = "points" | "mesh";
export type Layers = Record<Layer, boolean>;
/** The room's appearance: exactly one of the point cloud or the mesh. */
export type ViewMode = "points" | "mesh";
type Assets = Schemas["SceneAssets"];
/** The point cloud when the Scene has one, else the mesh. */
export function defaultLayers(assets: Assets): Layers {
  const points = Boolean(assets.points_url);
  return { points, mesh: !points && Boolean(assets.mesh_url) };
}
export function showMode(layers: Layers, mode: ViewMode): Layers {
  return { ...layers, points: mode === "points", mesh: mode === "mesh" };
}
/**
 * Whether Objects can be hovered and highlighted in the shown view. A Scene published before
 * membership existed, or whose membership does not match the shown geometry, needs reprocessing.
 */
export function highlightState(
  assets: Assets,
  membership: "pending" | "error" | "success",
  mismatch: Partial<Record<ViewMode, boolean>>,
  mode: ViewMode | null,
): "available" | "reprocess" | "failed" {
  // Without geometry there is nothing to highlight, and the viewer says so already.
  if (!mode || !(assets.points_url || assets.mesh_url)) return "available";
  if (!assets.membership_url || mismatch[mode]) return "reprocess";
  return membership === "error" ? "failed" : "available";
}
export function viewMode(layers: Layers): ViewMode | null {
  return layers.points ? "points" : layers.mesh ? "mesh" : null;
}
/** Bounds of the room as shown: the visible layer's, else whichever layer has loaded. */
export function visibleBounds(
  layers: Layers,
  loaded: Partial<Record<ViewMode, Bounds>>,
): Bounds | null {
  const mode = viewMode(layers);
  return (mode && loaded[mode]) || loaded.points || loaded.mesh || null;
}
const ROOM_FALLBACK: Bounds = { min: [-2.5, -2.5, 0], max: [2.5, 2.5, 3] };
/** An oblique view from the front-right, far enough to see the whole room. */
export function homePose(bounds: Bounds | null): {
  position: Point;
  target: Point;
} {
  const { min, max } = bounds ?? ROOM_FALLBACK;
  const target = min.map((value, i) => (value + max[i]) / 2) as Point;
  const distance =
    Math.max(max[0] - min[0], max[1] - min[1], max[2] - min[2]) * 1.35;
  return {
    position: [
      target[0] + distance * 0.6,
      target[1] - distance * 0.8,
      target[2] + distance * 0.7,
    ],
    target,
  };
}
/** The axis-aligned box enclosing the given Objects' rotated boxes; null when none match. */
export function focusBounds(
  objects: SceneObject[],
  ids: string[],
): Bounds | null {
  const chosen = objects.filter((o) => ids.includes(o.id));
  if (!chosen.length) return null;
  const min: Point = [Infinity, Infinity, Infinity],
    max: Point = [-Infinity, -Infinity, -Infinity];
  for (const { box } of chosen) {
    const [hx, hy, hz] = box.size.map((s) => s / 2),
      yaw = box.yaw || 0;
    // Enclose rotated boxes rather than clipping their corners on camera flight.
    const extent = [
      Math.abs(Math.cos(yaw)) * hx + Math.abs(Math.sin(yaw)) * hy,
      Math.abs(Math.sin(yaw)) * hx + Math.abs(Math.cos(yaw)) * hy,
      hz,
    ];
    for (let i = 0; i < 3; i++) {
      min[i] = Math.min(min[i], box.center[i] - extent[i]);
      max[i] = Math.max(max[i], box.center[i] + extent[i]);
    }
  }
  return { min, max };
}
