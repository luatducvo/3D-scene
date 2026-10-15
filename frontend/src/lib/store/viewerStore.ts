import { create } from "zustand";
export type Point = [number, number, number];
export type Layer = "points" | "mesh" | "boxes";
type ViewerState = {
  selectedId: string | null;
  highlightedIds: string[];
  measuring: boolean;
  points: Point[];
  camera: { position: Point; target: Point };
  layers: Record<Layer, boolean>;
  bounds: { min: Point; max: Point } | null;
  select: (id: string) => void;
  highlight: (ids: string[]) => void;
  setMeasuring: (active: boolean) => void;
  pick: (point: Point) => void;
  clear: () => void;
  setCamera: (position: Point, target: Point) => void;
  toggleLayer: (layer: Layer) => void;
  setBounds: (bounds: { min: Point; max: Point } | null) => void;
};
export const useViewer = create<ViewerState>((set) => ({
  selectedId: null,
  highlightedIds: [],
  measuring: false,
  points: [],
  camera: { position: [6, -8, 5], target: [0, 0, 1] },
  layers: { points: true, mesh: false, boxes: true },
  bounds: null,
  select: (id) => set({ selectedId: id, highlightedIds: [id] }),
  highlight: (ids) => set({ highlightedIds: ids }),
  setMeasuring: (measuring) => set({ measuring, points: [] }),
  pick: (point) =>
    set((s) => ({
      points: s.points.length === 2 ? [point] : [...s.points, point],
    })),
  clear: () =>
    set({ points: [], measuring: false, selectedId: null, highlightedIds: [] }),
  setCamera: (position, target) => set({ camera: { position, target } }),
  toggleLayer: (layer) =>
    set((s) => ({ layers: { ...s.layers, [layer]: !s.layers[layer] } })),
  setBounds: (bounds) => set({ bounds }),
}));
