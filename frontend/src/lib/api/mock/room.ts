import type { SceneObject } from "../types";
import { encodeMembership } from "./membership";

// Small deterministic geometry for UI development; it never represents a user's capture.
export const demoObjects: SceneObject[] = [
  {
    id: "sofa-1",
    label: "sofa",
    box: { center: [2.3, 3.35, 0.55], size: [2.6, 0.85, 1.1], yaw: 0 },
    best_views: [],
  },
  {
    id: "table-1",
    label: "coffee table",
    box: { center: [2.55, 1.975, 0.29], size: [1.3, 0.75, 0.58], yaw: 0 },
    best_views: [],
  },
  {
    id: "plant-1",
    label: "plant",
    box: { center: [4.45, 3.55, 0.65], size: [0.7, 0.7, 1.3], yaw: 0 },
    best_views: [],
  },
  // Inside the plant's box: its points belong to both, and picking prefers the smaller pot.
  {
    id: "pot-1",
    label: "flower pot",
    box: { center: [4.48, 3.58, 0.2], size: [0.36, 0.36, 0.4], yaw: 0 },
    best_views: [],
  },
];

type RoomPoint = { position: [number, number, number]; color: number[] };
let room: RoomPoint[] | null = null;
/** The room's points in PLY file order, positions rounded as the PLY writes them. */
export function roomPoints(): RoomPoint[] {
  if (room) return room;
  let seed = 8;
  const random = () => {
    seed = (seed * 1664525 + 1013904223) >>> 0;
    return seed / 4294967296;
  };
  const points: RoomPoint[] = [];
  const add = (x: number, y: number, z: number, color: number[]) =>
    points.push({
      position: [x, y, z].map((v) =>
        Number(v.toFixed(3)),
      ) as RoomPoint["position"],
      color,
    });
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
  room = points;
  return points;
}

export function roomPointCloud() {
  const points = roomPoints();
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
    ...points.map(({ position, color }) =>
      [...position.map((v) => v.toFixed(3)), ...color].join(" "),
    ),
  ].join("\n");
}

/** Points within 2 cm of an Object's box belong to it; the floor and the rug belong to nothing. */
export function roomMembership(): ArrayBuffer {
  const points = roomPoints();
  const members = demoObjects.map(({ box }) =>
    points.flatMap(({ position }, index) =>
      position[2] > 0.02 &&
      position.every(
        (v, axis) =>
          Math.abs(v - box.center[axis]) <= box.size[axis] / 2 + 0.02,
      )
        ? [index]
        : [],
    ),
  );
  return encodeMembership(
    demoObjects.map((o) => o.id),
    points.length,
    roomMeshData().positions.length / 3,
    members,
    roomMeshData().members,
  );
}

/** A small closed-box room fixture, in the same aligned frame as the mock point cloud. */
function roomMeshData() {
  const positions: number[] = [],
    colors: number[] = [];
  const members = demoObjects.map(() => [] as number[]);
  const addBox = (
    center: number[],
    size: number[],
    rgb: number[],
    objectIndex?: number,
  ) => {
    const corners = [
      [-1, -1, -1],
      [1, -1, -1],
      [1, 1, -1],
      [-1, 1, -1],
      [-1, -1, 1],
      [1, -1, 1],
      [1, 1, 1],
      [-1, 1, 1],
    ];
    const faces = [
      0, 2, 1, 0, 3, 2, 4, 5, 6, 4, 6, 7, 0, 1, 5, 0, 5, 4, 3, 7, 6, 3, 6, 2, 0,
      4, 7, 0, 7, 3, 1, 2, 6, 1, 6, 5,
    ];
    for (const corner of faces) {
      const index = positions.length / 3;
      positions.push(
        ...corners[corner].map(
          (v, axis) => center[axis] + (v * size[axis]) / 2,
        ),
      );
      colors.push(...rgb.map((v) => Math.pow(v / 255, 2.2)));
      if (objectIndex !== undefined) members[objectIndex].push(index);
    }
  };
  addBox([2.5, 2, -0.03], [5, 4, 0.06], [110, 133, 120]);
  addBox([-0.03, 2, 1.4], [0.06, 4, 2.8], [159, 178, 154]);
  addBox([2.5, 4.03, 1.4], [5, 0.06, 2.8], [137, 154, 139]);
  demoObjects.forEach((object, i) =>
    addBox(
      object.box.center,
      object.box.size,
      [
        [78, 171, 141],
        [214, 199, 166],
        [168, 187, 115],
        [189, 152, 122],
      ][i],
      i,
    ),
  );
  return { positions, colors, members };
}

/** Self-contained glTF binary for browser checks, with membership in accessor vertex order. */
export function roomMesh(): ArrayBuffer {
  const { positions, colors } = roomMeshData();
  const vertexCount = positions.length / 3,
    sectionBytes = positions.length * 4;
  const binary = new Float32Array([...positions, ...colors]);
  const gltf = {
    asset: { version: "2.0" },
    scene: 0,
    scenes: [{ nodes: [0] }],
    nodes: [{ mesh: 0 }],
    extensionsUsed: ["KHR_materials_unlit"],
    materials: [{ doubleSided: true, extensions: { KHR_materials_unlit: {} } }],
    meshes: [
      {
        primitives: [{ attributes: { POSITION: 0, COLOR_0: 1 }, material: 0 }],
      },
    ],
    buffers: [{ byteLength: binary.byteLength }],
    bufferViews: [
      { buffer: 0, byteOffset: 0, byteLength: sectionBytes },
      { buffer: 0, byteOffset: sectionBytes, byteLength: sectionBytes },
    ],
    accessors: [
      {
        bufferView: 0,
        componentType: 5126,
        count: vertexCount,
        type: "VEC3",
        min: [-0.06, 0, -0.06],
        max: [5, 4.06, 2.8],
      },
      { bufferView: 1, componentType: 5126, count: vertexCount, type: "VEC3" },
    ],
  };
  const json = new TextEncoder().encode(JSON.stringify(gltf));
  const jsonLength = Math.ceil(json.length / 4) * 4;
  const result = new ArrayBuffer(12 + 8 + jsonLength + 8 + binary.byteLength);
  const view = new DataView(result),
    bytes = new Uint8Array(result);
  view.setUint32(0, 0x46546c67, true);
  view.setUint32(4, 2, true);
  view.setUint32(8, result.byteLength, true);
  view.setUint32(12, jsonLength, true);
  view.setUint32(16, 0x4e4f534a, true);
  bytes.fill(0x20, 20, 20 + jsonLength);
  bytes.set(json, 20);
  view.setUint32(20 + jsonLength, binary.byteLength, true);
  view.setUint32(24 + jsonLength, 0x004e4942, true);
  bytes.set(new Uint8Array(binary.buffer), 28 + jsonLength);
  return result;
}
