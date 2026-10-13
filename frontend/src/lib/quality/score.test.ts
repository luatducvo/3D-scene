import { expect, test } from "vitest";
import { scoreImage } from "./score";
test("flat and overexposed captures are marked poor, textured balanced captures good", () => {
  const flat = new Uint8ClampedArray(8 * 8 * 4).fill(128);
  expect(scoreImage(flat, 8, 8).level).toBe("red");
  expect(
    scoreImage(new Uint8ClampedArray(8 * 8 * 4).fill(255), 8, 8).level,
  ).toBe("red");
  const sharp = new Uint8ClampedArray(8 * 8 * 4);
  for (let y = 0; y < 8; y++)
    for (let x = 0; x < 8; x++) {
      const i = (y * 8 + x) * 4;
      sharp.fill((x + y) % 2 ? 60 : 190, i, i + 3);
      sharp[i + 3] = 255;
    }
  expect(scoreImage(sharp, 8, 8).level).toBe("green");
});
