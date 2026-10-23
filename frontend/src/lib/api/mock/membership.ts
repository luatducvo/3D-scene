import {
  MEMBERSHIP_FIELD,
  MEMBERSHIP_HEADER_SIZE,
  MEMBERSHIP_MAGIC,
  MEMBERSHIP_VERSION,
} from "../membership";

/** Writes the `objects/membership.bin` format (api.md "Object membership") for the mock room. */
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
  const buffer = new ArrayBuffer(
    MEMBERSHIP_HEADER_SIZE + idsLength + 4 * words,
  );
  const bytes = new Uint8Array(buffer),
    head = new DataView(buffer);
  bytes.set(new TextEncoder().encode(MEMBERSHIP_MAGIC), 0);
  const header: Record<keyof typeof MEMBERSHIP_FIELD, number> = {
    version: MEMBERSHIP_VERSION,
    objectCount: ids.length,
    pointCount,
    vertexCount,
    idsLength,
  };
  for (const [name, value] of Object.entries(header))
    head.setUint32(
      MEMBERSHIP_FIELD[name as keyof typeof MEMBERSHIP_FIELD],
      value,
      true,
    );
  bytes.fill(0x20, MEMBERSHIP_HEADER_SIZE, MEMBERSHIP_HEADER_SIZE + idsLength);
  bytes.set(json, MEMBERSHIP_HEADER_SIZE);
  let offset = MEMBERSHIP_HEADER_SIZE + idsLength;
  for (const section of sections)
    for (const value of section) {
      head.setUint32(offset, value, true);
      offset += 4;
    }
  return buffer;
}
