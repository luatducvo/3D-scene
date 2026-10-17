/**
 * Must equal ingest's `long_side` in backend/config/pipeline.yaml. Ingest keeps an upright, metadata-free
 * JPEG within it byte for byte, so a photo shrunk here is compressed exactly once.
 */
export const UPLOAD_LONG_SIDE = 1600;
/** The JPEG quality ingest uses when it re-encodes. */
const QUALITY = 0.95;
/**
 * JPEG encoding takes about a second per photo off the main thread, so photos shrink several at
 * once; 8 took 24 photos from 26 s to 4 s in Chromium.
 */
export const SHRINK_CONCURRENCY = 8;
const SHRINKABLE = ["image/jpeg", "image/png", "image/webp"];

type Decoded = { width: number; height: number; close(): void };
export type Codec<Drawn = unknown> = {
  decode(file: File): Promise<Decoded>;
  draw(image: Decoded, width: number, height: number): Drawn;
  encode(drawn: Drawn): Promise<Blob>;
};

/** Decodes upright (EXIF orientation applied) and re-encodes without metadata through a canvas. */
export const browserCodec: Codec<OffscreenCanvas> = {
  decode: (file) => createImageBitmap(file, { imageOrientation: "from-image" }),
  draw(image, width, height) {
    const canvas = new OffscreenCanvas(width, height);
    const context = canvas.getContext("2d")!;
    context.imageSmoothingQuality = "high";
    context.drawImage(image as ImageBitmap, 0, 0, width, height);
    return canvas;
  },
  encode: (canvas) =>
    canvas.convertToBlob({ type: "image/jpeg", quality: QUALITY }),
};

/**
 * A photo larger than longSide becomes a JPEG at most longSide on its long side. Videos, HEIC, photos
 * already small enough and files the browser cannot decode are sent as they are; ingest prepares them.
 */
export async function shrinkForUpload<Drawn>(
  file: File,
  longSide = UPLOAD_LONG_SIDE,
  codec: Codec<Drawn> = browserCodec as Codec<Drawn>,
): Promise<File> {
  if (!SHRINKABLE.includes(file.type)) return file;
  let drawn: Drawn;
  try {
    const image = await codec.decode(file);
    try {
      const scale = longSide / Math.max(image.width, image.height);
      if (scale >= 1) return file;
      drawn = codec.draw(
        image,
        Math.max(1, Math.round(image.width * scale)),
        Math.max(1, Math.round(image.height * scale)),
      );
    } finally {
      // A decoded full-resolution photo takes ~50 MB; it is released before the slow encode.
      image.close();
    }
    const blob = await codec.encode(drawn);
    // The stem stays, so ingest keeps the capture order.
    const name = file.name.replace(/\.[^.]*$/, "") + ".jpg";
    return new File([blob], name, {
      type: "image/jpeg",
      lastModified: file.lastModified,
    });
  } catch {
    return file;
  }
}

/**
 * Shrinks the files, at most `concurrency` at once, keeping their order. progress receives the
 * ratio of files done.
 */
export async function shrinkAll(
  files: File[],
  progress?: (ratio: number) => void,
  shrink: (file: File) => Promise<File> = shrinkForUpload,
  concurrency = SHRINK_CONCURRENCY,
): Promise<File[]> {
  const result: File[] = new Array(files.length);
  let next = 0;
  let done = 0;
  const lane = async () => {
    while (next < files.length) {
      const index = next++;
      result[index] = await shrink(files[index]);
      progress?.(++done / files.length);
    }
  };
  await Promise.all(
    Array.from({ length: Math.min(concurrency, files.length) }, lane),
  );
  return result;
}
