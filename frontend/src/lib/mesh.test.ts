import { describe, expect, it } from "vitest";
import { decodeMesh } from "./mesh";

describe("mesh.bin decoder", () => {
  it("preserves vertex order and instance IDs", () => {
    const bytes = new ArrayBuffer(16 + 2 * 12 + 2 * 3 + 3 * 4 + 2 * 4);
    const view = new DataView(bytes);
    [0x53, 0x33, 0x44, 0x4d].forEach((value, i) => view.setUint8(i, value));
    view.setUint32(4, 1, true);
    view.setUint32(8, 2, true);
    view.setUint32(12, 3, true);
    [1, 2, 3, 4, 5, 6].forEach((value, i) => view.setFloat32(16 + i * 4, value, true));
    [255, 0, 0, 0, 255, 0].forEach((value, i) => view.setUint8(40 + i, value));
    [0, 1, 0].forEach((value, i) => view.setUint32(46 + i * 4, value, true));
    view.setInt32(58, -1, true);
    view.setInt32(62, 12, true);
    const mesh = decodeMesh(bytes);
    expect(Array.from(mesh.positions)).toEqual([1, 2, 3, 4, 5, 6]);
    expect(Array.from(mesh.colors)).toEqual([255, 0, 0, 0, 255, 0]);
    expect(Array.from(mesh.instanceIds)).toEqual([-1, 12]);
  });
});
