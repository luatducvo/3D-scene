import { create } from "zustand";
import type {
  Bounds,
  Layers,
  Point,
  ViewMode,
} from "../../components/viewer/view";
import type { Appearance } from "../../components/viewer/highlight";
export type { Point } from "../../components/viewer/view";
/** The Object under the pointer and where the pointer is, in client pixels. */
export type Hover = { id: string; x: number; y: number };
/** What the viewer is doing; exactly one at a time, and only it paints Objects. */
export type Interaction = "idle" | "search" | "selection";
/** Viewer state only; camera moves go through components/viewer/camera.ts. */
type ViewerState = {
  /** The Search box's text; a Search is on while it is not blank. */
  search: string;
  /** Change the Search text; text that starts a Search drops the Selection. */
  setSearch: (search: string) => void;
  appearance: Appearance;
  setAppearance: (appearance: Appearance) => void;
  /** Each Highlighted Object's similarity relative to the Search's other hits; empty without a Search. */
  similarities: Record<string, number>;
  resultVersion: number;
  beginResult: () => number;
  showResult: (
    version: number,
    ids: string[],
    similarities: Record<string, number>,
  ) => boolean;
  /** Empty the Search text and drop its Highlight. */
  endSearch: () => void;
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
  /** Drop the Selection. */
  deselect: () => void;
  /** The Object under the pointer; ignored outside idle. */
  hover: (hovered: Hover | null) => void;
  /** A click on an Object, or on nothing, applied by the rules of the current interaction. */
  click: (id: string | null) => void;
  /** Drop the Selection, else end the Search; stop measuring either way. */
  escape: () => void;
  setMeasuring: (active: boolean) => void;
  pick: (point: Point) => void;
  /** Drop Selection, Search, highlights and measurement. */
  clear: () => void;
  /** Forget everything about the current Scene, for leaving it. */
  reset: () => void;
  setLayers: (layers: Layers) => void;
  setPointSize: (size: number) => void;
  setLoadedBounds: (mode: ViewMode, bounds: Bounds) => void;
  setMembershipMismatch: (mode: ViewMode, mismatch: boolean) => void;
};
const initial = {
  search: "",
  appearance: "original" as const,
  similarities: {},
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
/** No Search text and no Highlight; the version moves on so a late Search response is dropped. */
const searchEnded = (s: ViewerState) => ({
  search: "",
  highlightedIds: [],
  similarities: {},
  resultVersion: s.resultVersion + 1,
});
export const useViewer = create<ViewerState>((set, get) => ({
  ...initial,
  setAppearance: (appearance) => set({ appearance }),
  setSearch: (search) =>
    set((s) => ({
      search,
      selectedId: search.trim() ? null : s.selectedId,
      hovered: null,
    })),
  deselect: () => set({ selectedId: null }),
  click: (id) => {
    const state = get();
    if (id === null) {
      if (interaction(state) === "selection") set({ selectedId: null });
    } else if (clickable(state, id))
      set((s) => ({ ...searchEnded(s), selectedId: id, hovered: null }));
  },
  escape: () => {
    const state = get();
    if (interaction(state) === "selection") set({ selectedId: null });
    else if (interaction(state) === "search") set(searchEnded);
    get().setMeasuring(false);
  },
  beginResult: () => {
    const version = get().resultVersion + 1;
    set({ resultVersion: version });
    return version;
  },
  showResult: (version, ids, similarities) => {
    if (version !== get().resultVersion) return false;
    set({ highlightedIds: ids, similarities, selectedId: null });
    return true;
  },
  endSearch: () => set(searchEnded),
  hover: (next) =>
    set((s) => {
      const hovered = interaction(s) === "idle" ? next : null;
      return s.hovered?.id === hovered?.id &&
      s.hovered?.x === hovered?.x &&
      s.hovered?.y === hovered?.y
        ? s
        : { hovered };
    }),
  setMeasuring: (measuring) => set({ measuring, points: [], hovered: null }),
  pick: (point) =>
    set((s) => ({
      points: s.points.length === 2 ? [point] : [...s.points, point],
    })),
  clear: () =>
    set((s) => ({
      ...searchEnded(s),
      points: [],
      measuring: false,
      selectedId: null,
    })),
  reset: () => set((s) => ({ ...initial, resultVersion: s.resultVersion + 1 })),
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

export function interaction(
  state: Pick<ViewerState, "selectedId" | "search">,
): Interaction {
  return state.selectedId
    ? "selection"
    : state.search.trim()
      ? "search"
      : "idle";
}

/** Whether a click on this Object does anything now: during a Search only its hits count. */
export function clickable(
  state: Pick<ViewerState, "selectedId" | "search" | "highlightedIds">,
  id: string,
): boolean {
  return interaction(state) !== "search" || state.highlightedIds.includes(id);
}

/** The canvas cursor over this Object, or over nothing: a pointer only where a click does something. */
export function cursor(
  state: Pick<ViewerState, "selectedId" | "search" | "highlightedIds">,
  id: string | null,
): "pointer" | "" {
  return id && clickable(state, id) ? "pointer" : "";
}
