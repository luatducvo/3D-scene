import { expect, test } from "vitest";
import { Color } from "three";
import {
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

test("the membership file decodes to each Object's points in Scene Graph order", () => {
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
