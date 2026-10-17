import type { SceneObject } from "../types";

// Small deterministic geometry for UI development; it never represents a user's capture.
export const demoObjects: SceneObject[] = [
  {
    id: "sofa-1",
    label: "sofa",
    label_vi: "Sofa",
    box: { center: [2.3, 3.35, 0.55], size: [2.6, 0.85, 1.1], yaw: 0 },
    attributes: { color: ["green"], material: ["fabric"] },
    best_views: [],
  },
  {
    id: "table-1",
    label: "coffee table",
    label_vi: "Bàn cà phê",
    box: { center: [2.55, 1.975, 0.29], size: [1.3, 0.75, 0.58], yaw: 0 },
    attributes: { material: ["wood"] },
    best_views: [],
  },
  {
    id: "plant-1",
    label: "plant",
    label_vi: "Chậu cây",
    box: { center: [4.45, 3.55, 0.65], size: [0.7, 0.7, 1.3], yaw: 0 },
    attributes: { color: ["green"] },
    best_views: [],
  },
];

export function roomPointCloud() {
  let seed = 8;
  const random = () => {
    seed = (seed * 1664525 + 1013904223) >>> 0;
    return seed / 4294967296;
  };
  const points: string[] = [];
  const add = (x: number, y: number, z: number, c: number[]) =>
    points.push([x.toFixed(3), y.toFixed(3), z.toFixed(3), ...c].join(" "));
  function plane(
    x: number,
    y: number,
    z: number,
    w: number,
    d: number,
    h: number,
    color: number[],
    n: number,
  ) {
    for (let i = 0; i < n; i++)
      add(x + random() * w, y + random() * d, z + random() * h, color);
  }
  function box(
    x: number,
    y: number,
    z: number,
    w: number,
    d: number,
    h: number,
    color: number[],
  ) {
    plane(x, y, z + h, w, d, 0, color, 350);
    plane(x, y, z, w, 0, h, color, 240);
    plane(x + w, y, z, 0, d, h, color, 180);
  }
  plane(0, 0, 0, 5, 4, 0, [110, 133, 120], 2400);
  plane(0, 4, 0, 5, 0, 2.8, [137, 154, 139], 1500);
  plane(0, 0, 0, 0, 4, 2.8, [159, 178, 154], 1500);
  plane(0.01, 1, 0.85, 0, 1.8, 1.5, [218, 229, 201], 500);
  box(1, 3, 0, 2.6, 0.8, 0.5, [78, 171, 141]);
  box(1, 3.65, 0.5, 2.6, 0.2, 0.6, [130, 201, 166]);
  box(1, 3, 0.5, 0.2, 0.8, 0.3, [140, 202, 169]);
  box(3.4, 3, 0.5, 0.2, 0.8, 0.3, [140, 202, 169]);
  plane(1.35, 1, 0.015, 2.45, 1.7, 0, [154, 163, 139], 500);
  box(1.9, 1.6, 0.48, 1.3, 0.75, 0.1, [214, 199, 166]);
  for (const x of [2, 3.1])
    for (const y of [1.68, 2.23])
      plane(x, y, 0, 0.05, 0.05, 0.48, [138, 146, 133], 40);
  box(4.3, 3.4, 0, 0.36, 0.36, 0.4, [189, 152, 122]);
  for (let i = 0; i < 500; i++) {
    const angle = random() * Math.PI * 2,
      r = random() * 0.4;
    add(
      4.48 + Math.cos(angle) * r,
      3.6 + Math.sin(angle) * r,
      0.4 + random() * 0.95,
      [168, 187, 115],
    );
  }
  return [
    "ply",
    "format ascii 1.0",
    "element vertex " + points.length,
    "property float x",
    "property float y",
    "property float z",
    "property uchar red",
    "property uchar green",
    "property uchar blue",
    "end_header",
    ...points,
  ].join("\n");
}
