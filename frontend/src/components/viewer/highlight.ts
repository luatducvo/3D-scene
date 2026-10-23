/**
 * Object highlighting rules, free of WebGL: which Object owns a point for picking, how points are
 * coloured for a Search, a Selection and hover. Points and mesh vertices work the same way: an element index
 * is a point of `points.ply` or a vertex of `mesh.glb`, and `members(i)` lists Object `i`'s ones.
 */
import { Color } from "three";
import type { Membership } from "../../lib/api/membership";

export type Members = (object: number) => Uint32Array;
/** Share of an element's real (linear) colour kept while other Objects are highlighted. */
export const DIM = 0.15;
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
 * Paints an element colour array (linear RGB, 3 floats per element) from real colours, for one
 * interaction at a time: a Search's hits as an Object Heatmap with the rest dimmed, or the hovered
 * or selected Object in its Instance Color, or just the appearance. Under Instance Colors an
 * emphasised Object dims everything else; otherwise an emphasis change repaints only its Objects.
 */
export class Painter {
  private readonly count: number;
  private readonly marked: Uint8Array;
  private readonly owner: Uint32Array;
  private dimmed = false;
  private appearanceBase: Float32Array;
  /** Each element in its owner's Instance Color, or its real colour when it has no owner. */
  private instanceColors: Float32Array;
  private resultColors: Float32Array;
  private appearanceMode: Appearance | null = null;
  private appearanceIds: string[] | null = null;
  private selected: number | null = null;
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
    this.appearanceBase = base;
    this.instanceColors = new Float32Array(base);
    this.resultColors = new Float32Array(base.length);
  }
  /** Stable Object colors; shared elements use the same ownership as picking. */
  appearance(mode: Appearance, ids: string[]) {
    if (this.appearanceMode === mode && this.appearanceIds === ids) return;
    this.appearanceMode = mode;
    if (this.appearanceIds !== ids) {
      this.appearanceIds = ids;
      this.instanceColors.set(this.base);
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
      this.owner.forEach((value, index) => {
        const rgb = value ? palette.get(ids[value - 1]) : undefined;
        if (rgb) this.instanceColors.set(rgb, index * 3);
      });
    }
    this.appearanceBase =
      mode === "instances" ? this.instanceColors : this.base;
    this.repaint();
  }
  /** Paint the selected Object as hover paints it. */
  selection(object: number | null) {
    const previous = this.selected;
    this.selected = object;
    this.emphasisChanged(previous, object);
  }
  hover(object: number | null) {
    const previous = this.hovered;
    this.hovered = object;
    this.emphasisChanged(previous, object);
  }
  /** Paint these Objects by their heatmap strengths and dim the rest; an empty list returns real colours. */
  highlight(objects: number[], strengths: number[]) {
    this.marked.fill(0);
    objects.forEach((object, position) => {
      const rgb = heatmapColor(strengths[position]).toArray();
      for (const index of this.list(object))
        if (index < this.count && this.owner[index] === object + 1) {
          this.marked[index] = 1;
          this.resultColors.set(rgb, index * 3);
        }
    });
    this.dimmed = objects.length > 0;
    this.repaint();
  }
  private emphasisChanged(previous: number | null, next: number | null) {
    if (previous === next) return;
    // Under Instance Colors an emphasis dims or restores everything else.
    if (this.appearanceMode === "instances") return this.repaint();
    for (const changed of [previous, next])
      if (changed !== null)
        for (const index of this.list(changed))
          if (index < this.count) this.plain(index);
  }
  private repaint() {
    for (let i = 0; i < this.count; i++) this.plain(i);
  }
  private list(object: number) {
    return object >= 0 && object < this.objectCount
      ? this.members(object)
      : EMPTY;
  }
  private plain(index: number) {
    const object = this.owner[index] - 1;
    const emphasised =
      object >= 0 && (object === this.hovered || object === this.selected);
    const anyEmphasis = this.hovered !== null || this.selected !== null;
    const dimmed =
      this.dimmed || (anyEmphasis && this.appearanceMode === "instances");
    for (let c = 0; c < 3; c++) {
      const k = 3 * index + c;
      this.colors[k] = emphasised
        ? this.instanceColors[k]
        : this.marked[index]
          ? this.resultColors[k]
          : dimmed
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
