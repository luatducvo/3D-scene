import { scoreImage } from "./score";

type Job = { id: string; file: File };
// Decode one image at a time: a full-resolution photo takes ~50 MB once decoded, so
// decoding a 200-photo drop concurrently exhausts memory and can freeze the machine.
const queue: Job[] = [];
let running = false;

async function analyse({ id, file }: Job) {
  const bitmap = await createImageBitmap(file);
  const scale = Math.min(1, 800 / Math.max(bitmap.width, bitmap.height));
  const canvas = new OffscreenCanvas(
    Math.max(3, Math.round(bitmap.width * scale)),
    Math.max(3, Math.round(bitmap.height * scale)),
  );
  const ctx = canvas.getContext("2d")!;
  ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();
  const pixels = ctx.getImageData(0, 0, canvas.width, canvas.height);
  const quality = scoreImage(pixels.data, canvas.width, canvas.height);
  // A small preview keeps the file list from holding every photo decoded at full size.
  const thumbScale = Math.min(1, 240 / Math.max(canvas.width, canvas.height));
  const thumbCanvas = new OffscreenCanvas(
    Math.max(1, Math.round(canvas.width * thumbScale)),
    Math.max(1, Math.round(canvas.height * thumbScale)),
  );
  thumbCanvas
    .getContext("2d")!
    .drawImage(canvas, 0, 0, thumbCanvas.width, thumbCanvas.height);
  const thumb = await thumbCanvas.convertToBlob({
    type: "image/jpeg",
    quality: 0.75,
  });
  return { id, quality, thumb };
}

async function drain() {
  if (running) return;
  running = true;
  for (let job = queue.shift(); job; job = queue.shift()) {
    try {
      self.postMessage(await analyse(job));
    } catch {
      self.postMessage({ id: job.id, error: true });
    }
  }
  running = false;
}

self.onmessage = ({ data }: MessageEvent<Job>) => {
  queue.push(data);
  void drain();
};
