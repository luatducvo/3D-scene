/**
 * Object highlighting rules, free of WebGL: which Object owns a point for picking, how points are
 * coloured for highlight and hover. Points and mesh vertices work the same way: an element index
 * is a point of `points.ply` or a vertex of `mesh.glb`, and `members(i)` lists Object `i`'s ones.
 */
import { Color } from "three";
import type { Membership } from "../../lib/api/membership";

export type Members = (object: number) => Uint32Array;
/** The app's highlight green, for highlighted and selected Objects. */
export const HIGHLIGHT_COLOR = "#9ee8c4";
/** Share of an element's real (linear) colour kept while other Objects are highlighted. */
export const DIM = 0.15;
/** How far a hovered Object's colour moves towards white. */
export const HOVER_MIX = 0.5;
export type Appearance = "original" | "instances";
const EMPTY = new Uint32Array(0);

/**
 * For each of `count` elements, 1 + the index of the smallest Object (fewest members) that contains
 * it, or 0 for none: pointing at a door handle picks the handle, not the wardrobe around it.
 * Indices beyond `count` are ignored.
 */
export function owners(
  count: number,
  objectCount: number,
  members: Members,
): Uint32Array {
  const order = Array.from({ length: objectCount }, (_, i) => i).sort(
    (a, b) => members(b).length - members(a).length,
  );
  const owner = new Uint32Array(count);
  // Larger Objects first, so smaller ones overwrite the elements they share.
  for (const object of order)
    for (const index of members(object))
      if (index < count) owner[index] = object + 1;
  return owner;
}

/** Owners as RGB bytes (24-bit ids) for the pick pass; black is no Object. */
export function pickColors(owner: Uint32Array): Uint8Array {
  const bytes = new Uint8Array(owner.length * 3);
  owner.forEach((id, i) => {
    bytes[3 * i] = (id >> 16) & 255;
    bytes[3 * i + 1] = (id >> 8) & 255;
    bytes[3 * i + 2] = id & 255;
  });
  return bytes;
}

/** The Object index a pick pixel names, or null for none. */
export function pickedObject(r: number, g: number, b: number): number | null {
  const id = (r << 16) | (g << 8) | b;
  return id ? id - 1 : null;
}

const indexCache = new WeakMap<Membership, Map<string, number>>();
/** Object indices of the given ids in the membership, skipping unknown ids. */
export function objectIndices(membership: Membership, ids: string[]): number[] {
  let index = indexCache.get(membership);
  if (!index) {
    index = new Map(membership.ids.map((id, i) => [id, i]));
    indexCache.set(membership, index);
  }
  return [...new Set(ids)].flatMap((id) => {
    const i = index.get(id);
    return i === undefined ? [] : [i];
  });
}

/**
 * Paints an element colour array (linear RGB, 3 floats per element) from real colours: highlighted
 * Objects in `HIGHLIGHT_COLOR` and the rest dimmed, or real colours when nothing is highlighted,
 * plus a light tint on the hovered Object. A hover change repaints only the two Objects involved.
 */
export class Painter {
  private readonly count: number;
  private readonly marked: Uint8Array;
  private readonly owner: Uint32Array;
  private readonly highlightRgb: number[];
  private dimmed = false;
  private appearanceBase: Float32Array;
  private resultColors: Float32Array;
  private appearanceMode: Appearance | null = null;
  private appearanceIds: string[] | null = null;
  private selectedMembers = new Set<number>();
  private hovered: number | null = null;
  constructor(
    readonly colors: Float32Array,
    private readonly base: Float32Array,
    private readonly members: Members,
    private readonly objectCount: number,
  ) {
    this.count = Math.floor(base.length / 3);
    this.marked = new Uint8Array(this.count);
    this.owner = owners(this.count, this.objectCount, this.members);
    this.highlightRgb = new Color(HIGHLIGHT_COLOR).toArray();
    this.appearanceBase = new Float32Array(base);
    this.resultColors = new Float32Array(base.length);
  }
  /** Stable Object colors; shared elements use the same ownership as picking. */
  appearance(mode: Appearance, ids: string[]) {
    if (this.appearanceMode === mode && this.appearanceIds === ids) return;
    this.appearanceMode = mode;
    this.appearanceIds = ids;
    this.appearanceBase.set(this.base);
    if (mode === "instances") {
      const palette = new Map<string, number[]>();
      const used = new Set<string>();
      // Sorting identities and golden-angle spacing avoids near-identical colors for similar IDs.
      [...ids].sort().forEach((id, rank) => {
        let step = rank;
        let color: Color;
        do {
          color = new Color().setHSL(
            (step * 0.618033988749895) % 1,
            0.65,
            0.55,
          );
          step += 1;
        } while (used.has(color.getHexString()));
        used.add(color.getHexString());
        palette.set(id, color.toArray());
      });
      const owner = this.owner;
      owner.forEach((value, index) => {
        const rgb = value ? palette.get(ids[value - 1]) : undefined;
        if (rgb) this.appearanceBase.set(rgb, index * 3);
      });
    }
    this.repaint();
  }
  /** Selection is feedback on top of the current result, not a replacement result. */
  selection(object: number | null) {
    this.selectedMembers = new Set(
      object === null
        ? []
        : this.list(object).filter((index) => this.owner[index] === object + 1),
    );
    this.repaint();
  }
  private repaint() {
    for (let i = 0; i < this.count; i++) this.plain(i);
    const hovered = this.hovered;
    this.hovered = null;
    this.hover(hovered);
  }
  /** Highlight these Objects and dim the rest; an empty list returns real colours. */
  highlight(objects: number[], strengths?: number[]) {
    this.marked.fill(0);
    objects.forEach((object, position) => {
      const rgb = strengths
        ? heatmapColor(strengths[position]).toArray()
        : this.highlightRgb;
      for (const index of this.list(object))
        if (index < this.count && this.owner[index] === object + 1) {
          this.marked[index] = 1;
          this.resultColors.set(rgb, index * 3);
        }
    });
    this.dimmed = objects.length > 0;
    this.repaint();
  }
  hover(object: number | null) {
    if (object === this.hovered) return;
    if (this.hovered !== null)
      for (const index of this.list(this.hovered))
        if (index < this.count) this.plain(index);
    this.hovered = object;
    if (object === null) return;
    for (const index of this.list(object))
      if (index < this.count && this.owner[index] === object + 1)
        // Lighten towards white, which stands out from real colours and from the highlight colour.
        for (let c = 0; c < 3; c++) {
          const k = 3 * index + c;
          this.colors[k] += (1 - this.colors[k]) * HOVER_MIX;
        }
  }
  private list(object: number) {
    return object >= 0 && object < this.objectCount
      ? this.members(object)
      : EMPTY;
  }
  private plain(index: number) {
    for (let c = 0; c < 3; c++) {
      const k = 3 * index + c;
      this.colors[k] = this.selectedMembers.has(index)
        ? [1, 0.55, 0.12][c]
        : this.marked[index]
          ? this.resultColors[k]
          : this.dimmed
            ? this.appearanceBase[k] * DIM
            : this.appearanceBase[k];
    }
  }
}

/** Relative semantic similarity among this query's returned Objects, never confidence. */
export function normalizeSimilarities(
  values: Record<string, number>,
): Record<string, number> {
  const scores = Object.values(values);
  if (!scores.length) return {};
  const min = Math.min(...scores),
    max = Math.max(...scores);
  return Object.fromEntries(
    Object.entries(values).map(([id, score]) => [
      id,
      max === min ? 1 : (score - min) / (max - min),
    ]),
  );
}

/** One color scale shared by the linear-RGB painter and the displayed sRGB legend. */
export function heatmapColor(strength: number): Color {
  return new Color().setHSL(
    (1 - Math.max(0, Math.min(1, strength))) * 0.65,
    0.85,
    0.55,
  );
}
