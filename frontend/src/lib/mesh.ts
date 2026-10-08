export type SceneMesh = {
  positions: Float32Array;
  colors: Uint8Array;
  indices: Uint32Array;
  instanceIds: Int32Array;
};

export function decodeMesh(buffer: ArrayBuffer): SceneMesh {
  const view = new DataView(buffer);
  if (view.byteLength < 16 || [0x53, 0x33, 0x44, 0x4d].some((byte, i) => view.getUint8(i) !== byte)) {
    throw new Error("Invalid mesh magic");
  }
  if (view.getUint32(4, true) !== 1) throw new Error("Unsupported mesh version");
  const vertices = view.getUint32(8, true);
  const indexCount = view.getUint32(12, true);
  const expected = 16 + vertices * 12 + vertices * 3 + indexCount * 4 + vertices * 4;
  if (view.byteLength !== expected) throw new Error("Invalid mesh length");
  let offset = 16;
  // Copy typed arrays: the packed RGB section leaves subsequent offsets unaligned.
  const positions = new Float32Array(vertices * 3);
  for (let i = 0; i < positions.length; i++) positions[i] = view.getFloat32(offset + i * 4, true);
  offset += vertices * 12;
  const colors = new Uint8Array(buffer.slice(offset, offset + vertices * 3));
  offset += vertices * 3;
  const indices = new Uint32Array(indexCount);
  for (let i = 0; i < indexCount; i++) indices[i] = view.getUint32(offset + i * 4, true);
  offset += indexCount * 4;
  const instanceIds = new Int32Array(vertices);
  for (let i = 0; i < vertices; i++) instanceIds[i] = view.getInt32(offset + i * 4, true);
  return { positions, colors, indices, instanceIds };
}
