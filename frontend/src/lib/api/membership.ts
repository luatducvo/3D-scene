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
/** Byte offsets of the header's fields, each a little-endian uint32 after the 4-byte magic. */
export const MEMBERSHIP_FIELD = {
  version: 4,
  objectCount: 8,
  pointCount: 12,
  vertexCount: 16,
  idsLength: 20,
} as const;
/** Header bytes; the ids JSON starts here. */
export const MEMBERSHIP_HEADER_SIZE = 24;

export function decodeMembership(buffer: ArrayBuffer): Membership {
  if (buffer.byteLength < MEMBERSHIP_HEADER_SIZE)
    throw new Error("Membership file is truncated");
  const head = new DataView(buffer);
  const field = (name: keyof typeof MEMBERSHIP_FIELD) =>
    head.getUint32(MEMBERSHIP_FIELD[name], true);
  const magic = String.fromCharCode(
    ...new Uint8Array(buffer, 0, MEMBERSHIP_MAGIC.length),
  );
  if (magic !== MEMBERSHIP_MAGIC || field("version") !== MEMBERSHIP_VERSION)
    throw new Error("Unsupported membership file");
  const count = field("objectCount"),
    idsLength = field("idsLength");
  const ids: string[] = JSON.parse(
    new TextDecoder().decode(
      new Uint8Array(buffer, MEMBERSHIP_HEADER_SIZE, idsLength),
    ),
  );
  if (ids.length !== count) throw new Error("Membership ids do not match");
  let offset = MEMBERSHIP_HEADER_SIZE + idsLength;
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
    pointCount: field("pointCount"),
    vertexCount: field("vertexCount"),
    points: (i) => pointIndices.subarray(pointOffsets[i], pointOffsets[i + 1]),
    vertices: (i) =>
      vertexIndices.subarray(vertexOffsets[i], vertexOffsets[i + 1]),
  };
}
