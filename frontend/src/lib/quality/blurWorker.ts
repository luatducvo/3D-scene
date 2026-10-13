import { scoreImage } from "./score";
self.onmessage = async ({ data }: MessageEvent<{ id: string; file: File }>) => {
  try {
    const bitmap = await createImageBitmap(data.file);
    const scale = Math.min(1, 800 / Math.max(bitmap.width, bitmap.height));
    const canvas = new OffscreenCanvas(
      Math.max(3, Math.round(bitmap.width * scale)),
      Math.max(3, Math.round(bitmap.height * scale)),
    );
    const ctx = canvas.getContext("2d")!;
    ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    bitmap.close();
    const pixels = ctx.getImageData(0, 0, canvas.width, canvas.height);
    self.postMessage({
      id: data.id,
      quality: scoreImage(pixels.data, canvas.width, canvas.height),
    });
  } catch {
    self.postMessage({ id: data.id, error: true });
  }
};
