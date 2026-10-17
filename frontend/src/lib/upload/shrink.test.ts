import { expect, test } from "vitest";
import { type Codec, shrinkAll, shrinkForUpload } from "./shrink";

/** Decodes every image at the given size and records what it drew and when it was released. */
function fakeCodec(width: number, height: number, failDecode = false) {
  const events: string[] = [];
  const codec: Codec<[number, number]> = {
    decode: async () => {
      if (failDecode) throw new Error("undecodable");
      return { width, height, close: () => events.push("close") };
    },
    draw: (_image, w, h) => {
      events.push(`draw ${w}x${h}`);
      return [w, h];
    },
    encode: async () => {
      events.push("encode");
      return new Blob(["small"], { type: "image/jpeg" });
    },
  };
  return { codec, events };
}

const file = (name: string, type: string) =>
  new File(["original bytes"], name, { type, lastModified: 42 });

test("a large photo becomes a JPEG at most the long side, released before encoding", async () => {
  const fake = fakeCodec(4000, 3000);
  const shrunk = await shrinkForUpload(
    file("IMG_0007.png", "image/png"),
    1600,
    fake.codec,
  );
  expect(fake.events).toEqual(["draw 1600x1200", "close", "encode"]);
  expect([shrunk.name, shrunk.type, shrunk.lastModified]).toEqual([
    "IMG_0007.jpg",
    "image/jpeg",
    42,
  ]);
  expect(await shrunk.text()).toBe("small");
});

test("small photos, videos, HEIC and undecodable files are sent unchanged", async () => {
  const small = fakeCodec(1600, 900);
  const photo = file("small.jpg", "image/jpeg");
  expect(await shrinkForUpload(photo, 1600, small.codec)).toBe(photo);
  expect(small.events).toEqual(["close"]);
  for (const other of [
    file("room.mp4", "video/mp4"),
    file("IMG_1.heic", "image/heic"),
  ])
    expect(
      await shrinkForUpload(other, 1600, fakeCodec(4000, 3000).codec),
    ).toBe(other);
  const broken = file("broken.jpg", "image/jpeg");
  expect(await shrinkForUpload(broken, 1600, fakeCodec(0, 0, true).codec)).toBe(
    broken,
  );
});

test("files shrink at most `concurrency` at once and keep their order", async () => {
  let running = 0;
  let most = 0;
  const reports: number[] = [];
  const files = ["a", "b", "c", "d", "e"].map((n) =>
    file(`${n}.jpg`, "image/jpeg"),
  );
  const result = await shrinkAll(
    files,
    (ratio) => reports.push(ratio),
    async (f) => {
      most = Math.max(most, ++running);
      // Earlier files finish later, so completion order differs from input order.
      await new Promise((wake) => setTimeout(wake, 10 - files.indexOf(f)));
      running--;
      return f;
    },
    2,
  );
  expect(result).toEqual(files);
  expect(most).toBe(2);
  expect(reports).toEqual([0.2, 0.4, 0.6, 0.8, 1]);
});
