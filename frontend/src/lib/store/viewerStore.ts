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
  selectedId: string | null;
  highlightedIds: string[];
  hovered: Hover | null;
  measuring: boolean;
  points: Point[];
  /** The last camera pose, sent with questions so answers can say left or right. */
  camera: { position: Point; target: Point };
  layers: Layers;
  /** Bounds of each loaded room layer; visibleBounds picks the one framing the view. */
  loadedBounds: Partial<Record<ViewMode, Bounds>>;
  /** Room layers whose loaded geometry does not match the Scene's Object membership. */
  membershipMismatch: Partial<Record<ViewMode, boolean>>;
  pointSize: number;
  select: (id: string) => void;
  /** Drop the selection, and its highlight when nothing else is highlighted. */
  deselect: () => void;
  highlight: (ids: string[]) => void;
  hover: (hovered: Hover | null) => void;
  setMeasuring: (active: boolean) => void;
  pick: (point: Point) => void;
  /** Drop selection, highlights and measurement. */
  clear: () => void;
  /** Forget everything about the current Scene, for leaving it. */
  reset: () => void;
  setCamera: (position: Point, target: Point) => void;
  toggleLayer: (layer: Layer) => void;
  setLayers: (layers: Layers) => void;
  setPointSize: (size: number) => void;
  setLoadedBounds: (mode: ViewMode, bounds: Bounds) => void;
  setMembershipMismatch: (mode: ViewMode, mismatch: boolean) => void;
};
const initial = {
  selectedId: null,
  highlightedIds: [],
  hovered: null,
  measuring: false,
  points: [],
  camera: { position: [6, -8, 5] as Point, target: [0, 0, 1] as Point },
  layers: { points: true, mesh: false },
  loadedBounds: {},
  membershipMismatch: {},
  pointSize: 0.012,
};
export const useViewer = create<ViewerState>((set) => ({
  ...initial,
  select: (id) => set({ selectedId: id, highlightedIds: [id] }),
  deselect: () =>
    set((s) => ({
      selectedId: null,
      highlightedIds:
        s.highlightedIds.length === 1 && s.highlightedIds[0] === s.selectedId
          ? []
          : s.highlightedIds,
    })),
  highlight: (ids) => set({ highlightedIds: ids }),
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
    set({ points: [], measuring: false, selectedId: null, highlightedIds: [] }),
  reset: () => set(initial),
  setCamera: (position, target) => set({ camera: { position, target } }),
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
