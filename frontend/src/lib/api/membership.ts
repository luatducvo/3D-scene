/**
 * Object membership (`SceneAssets.membership_url`, `graph/membership.bin`): which points of
 * `points.ply` and which vertices of `mesh.glb` belong to each Object. The format is documented in
 * docs/architecture/api.md ("Object membership"); every array is a zero-copy view of the buffer.
 */
export type Membership = {
  /** Object ids in the Scene Graph's order; an Object's index is its position here. */
  ids: string[];
  /** Vertices of `points.ply` when the file was written. */
  pointCount: number;
  /** POSITION entries of `mesh.glb` when the file was written. */
  vertexCount: number;
  /** Sorted point indices of Object `i`. */
  points: (i: number) => Uint32Array;
  /** Sorted mesh vertex indices of Object `i`. */
  vertices: (i: number) => Uint32Array;
};

export const MEMBERSHIP_MAGIC = "SCMB";
export const MEMBERSHIP_VERSION = 1;

export function decodeMembership(buffer: ArrayBuffer): Membership {
  if (buffer.byteLength < 24) throw new Error("Membership file is truncated");
  const head = new DataView(buffer);
  const magic = String.fromCharCode(...new Uint8Array(buffer, 0, 4));
  if (
    magic !== MEMBERSHIP_MAGIC ||
    head.getUint32(4, true) !== MEMBERSHIP_VERSION
  )
    throw new Error("Unsupported membership file");
  const count = head.getUint32(8, true),
    idsLength = head.getUint32(20, true);
  const ids: string[] = JSON.parse(
    new TextDecoder().decode(new Uint8Array(buffer, 24, idsLength)),
  );
  if (ids.length !== count) throw new Error("Membership ids do not match");
  let offset = 24 + idsLength;
  const take = (length: number) => {
    if (offset + 4 * length > buffer.byteLength)
      throw new Error("Membership file is truncated");
    const view = new Uint32Array(buffer, offset, length);
    offset += 4 * length;
    return view;
  };
  const pointOffsets = take(count + 1),
    pointIndices = take(pointOffsets[count]);
  const vertexOffsets = take(count + 1),
    vertexIndices = take(vertexOffsets[count]);
  return {
    ids,
    pointCount: head.getUint32(12, true),
    vertexCount: head.getUint32(16, true),
    points: (i) => pointIndices.subarray(pointOffsets[i], pointOffsets[i + 1]),
    vertices: (i) =>
      vertexIndices.subarray(vertexOffsets[i], vertexOffsets[i + 1]),
  };
}
