import { create } from "zustand";
import type {
  Bounds,
  Layer,
  Layers,
  Point,
  ViewMode,
} from "../../components/viewer/view";
export type { Layer, Point } from "../../components/viewer/view";
/** Viewer state only; camera moves go through components/viewer/camera.ts. */
type ViewerState = {
  selectedId: string | null;
  highlightedIds: string[];
  measuring: boolean;
  points: Point[];
  /** The last camera pose, sent with questions so answers can say left or right. */
  camera: { position: Point; target: Point };
  layers: Layers;
  /** Bounds of each loaded room layer; visibleBounds picks the one framing the view. */
  loadedBounds: Partial<Record<ViewMode, Bounds>>;
  pointSize: number;
  select: (id: string) => void;
  deselect: () => void;
  highlight: (ids: string[]) => void;
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
};
const initial = {
  selectedId: null,
  highlightedIds: [],
  measuring: false,
  points: [],
  camera: { position: [6, -8, 5] as Point, target: [0, 0, 1] as Point },
  layers: { points: true, mesh: false, boxes: true },
  loadedBounds: {},
  pointSize: 0.012,
};
export const useViewer = create<ViewerState>((set) => ({
  ...initial,
  select: (id) => set({ selectedId: id, highlightedIds: [id] }),
  deselect: () => set({ selectedId: null }),
  highlight: (ids) => set({ highlightedIds: ids }),
  setMeasuring: (measuring) => set({ measuring, points: [] }),
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
}));
