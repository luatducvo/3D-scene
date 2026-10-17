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
 * Objects in green and the rest dimmed, or real colours when nothing is highlighted, plus a light
 * tint on the hovered Object. A hover change repaints only the two Objects involved.
 */
export class Painter {
  private readonly count: number;
  private readonly marked: Uint8Array;
  private readonly green: number[];
  private dimmed = false;
  private hovered: number | null = null;
  constructor(
    readonly colors: Float32Array,
    private readonly base: Float32Array,
    private readonly members: Members,
    private readonly objectCount: number,
  ) {
    this.count = Math.floor(base.length / 3);
    this.marked = new Uint8Array(this.count);
    this.green = new Color(HIGHLIGHT_COLOR).toArray();
  }
  /** Highlight these Objects and dim the rest; an empty list returns real colours. */
  highlight(objects: number[]) {
    this.marked.fill(0);
    for (const object of objects)
      for (const index of this.list(object))
        if (index < this.count) this.marked[index] = 1;
    this.dimmed = objects.length > 0;
    for (let i = 0; i < this.count; i++) this.plain(i);
    const hovered = this.hovered;
    this.hovered = null;
    this.hover(hovered);
  }
  hover(object: number | null) {
    if (object === this.hovered) return;
    if (this.hovered !== null)
      for (const index of this.list(this.hovered))
        if (index < this.count) this.plain(index);
    this.hovered = object;
    if (object === null) return;
    for (const index of this.list(object))
      if (index < this.count)
        // Lighten towards white, which stands out from real colours and from the highlight green.
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
      this.colors[k] = this.marked[index]
        ? this.green[c]
        : this.dimmed
          ? this.base[k] * DIM
          : this.base[k];
    }
  }
}
