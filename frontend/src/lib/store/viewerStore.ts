import { create } from "zustand";
import type {
  Bounds,
  Layer,
  Layers,
  Point,
  ViewMode,
} from "../../components/viewer/view";
export type { Layer, Point } from "../../components/viewer/view";
/** The Object under the pointer and where the pointer is, in client pixels. */
export type Hover = { id: string; x: number; y: number };
/** Viewer state only; camera moves go through components/viewer/camera.ts. */
type ViewerState = {
  appearance: "original" | "instances";
  setAppearance: (appearance: "original" | "instances") => void;
  resultSource: "search" | null;
  similarities: Record<string, number> | null;
  resultVersion: number;
  beginResult: () => number;
  showResult: (
    version: number,
    source: "search",
    ids: string[],
    similarities?: Record<string, number>,
  ) => boolean;
  clearResult: () => void;
  selectedId: string | null;
  highlightedIds: string[];
  hovered: Hover | null;
  measuring: boolean;
  points: Point[];
  layers: Layers;
  /** Bounds of each loaded room layer; visibleBounds picks the one framing the view. */
  loadedBounds: Partial<Record<ViewMode, Bounds>>;
  /** Room layers whose loaded geometry does not match the Scene's Object membership. */
  membershipMismatch: Partial<Record<ViewMode, boolean>>;
  pointSize: number;
  select: (id: string) => void;
  /** Drop the selection, and its highlight when nothing else is highlighted. */
  deselect: () => void;
  hover: (hovered: Hover | null) => void;
  setMeasuring: (active: boolean) => void;
  pick: (point: Point) => void;
  /** Drop selection, highlights and measurement. */
  clear: () => void;
  /** Forget everything about the current Scene, for leaving it. */
  reset: () => void;
  toggleLayer: (layer: Layer) => void;
  setLayers: (layers: Layers) => void;
  setPointSize: (size: number) => void;
  setLoadedBounds: (mode: ViewMode, bounds: Bounds) => void;
  setMembershipMismatch: (mode: ViewMode, mismatch: boolean) => void;
};
const initial = {
  appearance: "original" as const,
  resultSource: null,
  similarities: null,
  resultVersion: 0,
  selectedId: null,
  highlightedIds: [],
  hovered: null,
  measuring: false,
  points: [],
  layers: { points: true, mesh: false },
  loadedBounds: {},
  membershipMismatch: {},
  pointSize: 0.012,
};
export const useViewer = create<ViewerState>((set, get) => ({
  ...initial,
  setAppearance: (appearance) => set({ appearance }),
  select: (id) => set({ selectedId: id }),
  deselect: () => set({ selectedId: null }),
  beginResult: () => {
    const version = get().resultVersion + 1;
    set({ resultVersion: version });
    return version;
  },
  showResult: (version, source, ids, similarities) => {
    if (version !== get().resultVersion) return false;
    set({
      resultSource: source,
      highlightedIds: ids,
      similarities: similarities ?? null,
      selectedId: null,
    });
    return true;
  },
  clearResult: () =>
    set((s) => ({
      resultVersion: s.resultVersion + 1,
      resultSource: null,
      similarities: null,
      highlightedIds: [],
      selectedId: null,
    })),
  hover: (hovered) =>
    set((s) =>
      s.hovered?.id === hovered?.id &&
      s.hovered?.x === hovered?.x &&
      s.hovered?.y === hovered?.y
        ? s
        : { hovered },
    ),
  setMeasuring: (measuring) => set({ measuring, points: [], hovered: null }),
  pick: (point) =>
    set((s) => ({
      points: s.points.length === 2 ? [point] : [...s.points, point],
    })),
  clear: () =>
    set((s) => ({
      points: [],
      measuring: false,
      selectedId: null,
      highlightedIds: [],
      resultSource: null,
      similarities: null,
      resultVersion: s.resultVersion + 1,
    })),
  reset: () => set((s) => ({ ...initial, resultVersion: s.resultVersion + 1 })),
  toggleLayer: (layer) =>
    set((s) => ({ layers: { ...s.layers, [layer]: !s.layers[layer] } })),
  setLayers: (layers) => set({ layers }),
  setPointSize: (pointSize) => set({ pointSize }),
  setLoadedBounds: (mode, bounds) =>
    set((s) => ({ loadedBounds: { ...s.loadedBounds, [mode]: bounds } })),
  setMembershipMismatch: (mode, mismatch) =>
    set((s) =>
      Boolean(s.membershipMismatch[mode]) === mismatch
        ? s
        : { membershipMismatch: { ...s.membershipMismatch, [mode]: mismatch } },
    ),
}));
