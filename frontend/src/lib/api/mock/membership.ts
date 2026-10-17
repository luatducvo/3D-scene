import { MEMBERSHIP_MAGIC, MEMBERSHIP_VERSION } from "../membership";

/** Writes the `graph/membership.bin` format (api.md "Object membership") for the mock room. */
export function encodeMembership(
  ids: string[],
  pointCount: number,
  vertexCount: number,
  points: number[][],
  vertices: number[][],
): ArrayBuffer {
  const json = new TextEncoder().encode(JSON.stringify(ids));
  const idsLength = Math.ceil(json.length / 4) * 4;
  const sections = [points, vertices].flatMap((lists) => {
    const offsets = [0];
    for (const list of lists)
      offsets.push(offsets[offsets.length - 1] + list.length);
    return [offsets, lists.flatMap((list) => [...list].sort((a, b) => a - b))];
  });
  const words = sections.reduce((sum, section) => sum + section.length, 0);
  const buffer = new ArrayBuffer(24 + idsLength + 4 * words);
  const bytes = new Uint8Array(buffer),
    head = new DataView(buffer);
  bytes.set(new TextEncoder().encode(MEMBERSHIP_MAGIC), 0);
  head.setUint32(4, MEMBERSHIP_VERSION, true);
  head.setUint32(8, ids.length, true);
  head.setUint32(12, pointCount, true);
  head.setUint32(16, vertexCount, true);
  head.setUint32(20, idsLength, true);
  bytes.fill(0x20, 24, 24 + idsLength);
  bytes.set(json, 24);
  let offset = 24 + idsLength;
  for (const section of sections)
    for (const value of section) {
      head.setUint32(offset, value, true);
      offset += 4;
    }
  return buffer;
}
