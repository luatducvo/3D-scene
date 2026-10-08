export const HIGHLIGHT_COLORS = [
  [255, 202, 40], [38, 198, 218], [239, 83, 80], [171, 71, 188],
  [102, 187, 106], [255, 167, 38], [66, 165, 245], [236, 64, 122],
];

export function highlightColor(index: number): string {
  return `rgb(${HIGHLIGHT_COLORS[index % HIGHLIGHT_COLORS.length].join(",")})`;
}
