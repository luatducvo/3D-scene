import { expect, test } from "vitest";
import { Color } from "three";
import {
  normalizeSimilarities,
  DIM,
  HIGHLIGHT_COLOR,
  objectIndices,
  owners,
  Painter,
  pickColors,
  pickedObject,
} from "./highlight";
import { decodeMembership } from "../../lib/api/membership";
import { encodeMembership } from "../../lib/api/mock/membership";

// Six points: a wardrobe owns 0-3, its handle owns 2, a chair owns 5; point 4 is a bare wall.
const membership = decodeMembership(
  encodeMembership(
    ["wardrobe", "handle", "chair"],
    6,
    0,
    [[0, 1, 2, 3], [2], [5]],
    [[], [], []],
  ),
);

test("the membership file decodes to each Object's points in Object order", () => {
  expect(membership.ids).toEqual(["wardrobe", "handle", "chair"]);
  expect(membership.pointCount).toBe(6);
  expect([...membership.points(0)]).toEqual([0, 1, 2, 3]);
  expect([...membership.vertices(1)]).toEqual([]);
  expect(objectIndices(membership, ["chair", "missing", "chair"])).toEqual([2]);
  expect(() => decodeMembership(new ArrayBuffer(24))).toThrow();
});

test("picking names the smallest Object where Objects overlap, and nothing on bare geometry", () => {
  const owner = owners(6, 3, membership.points);
  expect([...owner]).toEqual([1, 1, 2, 1, 0, 3]);
  const bytes = pickColors(owner);
  const at = (i: number) =>
    pickedObject(bytes[3 * i], bytes[3 * i + 1], bytes[3 * i + 2]);
  expect(at(2)).toBe(1); // the handle, not the wardrobe around it
  expect(at(0)).toBe(0);
  expect(at(4)).toBeNull();
  // Ids above one byte survive the RGB encoding.
  const many = pickColors(Uint32Array.of(70_000));
  expect(pickedObject(many[0], many[1], many[2])).toBe(69_999);
});

test("highlighting paints Objects green and dims the rest; clearing returns real colours", () => {
  const base = Float32Array.from({ length: 18 }, (_, i) => (i + 1) / 20);
  const colors = new Float32Array(base);
  const painter = new Painter(colors, base, membership.points, 3);
  const green = new Color(HIGHLIGHT_COLOR).toArray();
  const color = (i: number) => [...colors.subarray(3 * i, 3 * i + 3)];
  painter.highlight([2]);
  expect(color(5)).toEqual(green.map((v) => Math.fround(v)));
  color(4).forEach((v, c) => expect(v).toBeCloseTo(base[12 + c] * DIM));
  painter.highlight([]);
  expect(colors).toEqual(base);
});

test("hover tints only the hovered Object and restores it when the pointer moves on", () => {
  const base = new Float32Array(18).fill(0.5);
  const colors = new Float32Array(base);
  const painter = new Painter(colors, base, membership.points, 3);
  painter.highlight([]);
  painter.hover(1);
  expect(colors[6]).not.toBeCloseTo(0.5);
  expect(colors[3]).toBe(0.5); // the rest of the wardrobe keeps its colour
  painter.hover(2);
  expect(colors[6]).toBe(0.5);
  expect(colors[15]).not.toBeCloseTo(0.5);
  painter.hover(null);
  expect(colors).toEqual(base);
  // A hovered, highlighted Object stays distinct from the highlight and returns to it.
  painter.highlight([2]);
  const highlighted = colors[15];
  painter.hover(2);
  expect(colors[15]).not.toBe(highlighted);
  painter.hover(null);
  expect(colors[15]).toBe(highlighted);
});

test("instance appearance survives selection, result highlights and clearing", () => {
  const base = new Float32Array(18).fill(0.2);
  const colors = new Float32Array(base);
  const painter = new Painter(colors, base, membership.points, 3);
  painter.appearance("instances", membership.ids);
  const instances = new Float32Array(colors);
  expect([...colors.slice(0, 3)]).not.toEqual([...colors.slice(6, 9)]);
  expect([...colors.slice(0, 3)]).not.toEqual([...colors.slice(15, 18)]);
  expect([...colors.slice(12, 15)]).toEqual([...base.slice(12, 15)]);
  painter.highlight([2]);
  painter.selection(1);
  expect([...colors.slice(6, 9)]).not.toEqual([...instances.slice(6, 9)]);
  painter.selection(null);
  painter.highlight([]);
  expect(colors).toEqual(instances);
  painter.appearance("original", membership.ids);
  expect(colors).toEqual(base);
  painter.appearance("instances", membership.ids);
  expect(colors).toEqual(instances);
});

test("heatmaps normalize raw cosine per query, with one hot level for ties", () => {
  expect(
    normalizeSimilarities({ first: 0.25, middle: 0.5, last: 0.75 }),
  ).toEqual({ first: 0, middle: 0.5, last: 1 });
  expect(normalizeSimilarities({ first: 0.2, last: 0.2 })).toEqual({
    first: 1,
    last: 1,
  });
  expect(normalizeSimilarities({ only: 0.1 })).toEqual({ only: 1 });
  expect(normalizeSimilarities({})).toEqual({});
});

test("overlapping search results retain the smaller Object's similarity color", () => {
  const base = new Float32Array(18).fill(0.2),
    colors = new Float32Array(base);
  const painter = new Painter(colors, base, membership.points, 3);
  painter.highlight([1, 0], [1, 0]);
  expect([...colors.slice(6, 9)]).toEqual(
    [0.9325, 0.1675, 0.1675].map(Math.fround),
  );
  expect([...colors.slice(0, 3)]).not.toEqual([...colors.slice(6, 9)]);
});

test("similar Object IDs have distinguishable rendered instance colors", () => {
  const base = new Float32Array(18).fill(0.2),
    colors = new Float32Array(base);
  const painter = new Painter(colors, base, membership.points, 3);
  painter.appearance("instances", [
    "obj-0123456789abcde1",
    "obj-0123456789abcde2",
    "chair",
  ]);
  const first = new Color().fromArray(colors, 0).getHexString();
  const second = new Color().fromArray(colors, 6).getHexString();
  expect(first).not.toBe(second);
});
