export type Quality = {
  sharpness: number;
  exposure: number;
  level: "green" | "amber" | "red";
};
export function scoreImage(
  data: Uint8ClampedArray,
  width: number,
  height: number,
): Quality {
  const gray = new Float64Array(width * height);
  let sum = 0;
  for (let i = 0; i < gray.length; i++) {
    gray[i] =
      0.299 * data[i * 4] + 0.587 * data[i * 4 + 1] + 0.114 * data[i * 4 + 2];
    sum += gray[i];
  }
  let lap = 0,
    square = 0,
    count = 0;
  for (let y = 1; y < height - 1; y++)
    for (let x = 1; x < width - 1; x++) {
      const i = y * width + x;
      const v =
        gray[i - 1] +
        gray[i + 1] +
        gray[i - width] +
        gray[i + width] -
        4 * gray[i];
      lap += v;
      square += v * v;
      count++;
    }
  const sharpness = count ? square / count - (lap / count) ** 2 : 0;
  const exposure = sum / Math.max(1, gray.length);
  const level =
    sharpness < 40 || exposure < 25 || exposure > 235
      ? "red"
      : sharpness < 120 || exposure < 50 || exposure > 210
        ? "amber"
        : "green";
  return { sharpness, exposure, level };
}
