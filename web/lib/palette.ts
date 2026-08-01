// Warm→cool category palette (user-chosen). Used for category dots, the expense
// stacked bar, and income-source bars so a category reads the same color across
// the whole dashboard.
export const PALETTE = [
  "#f94144", // strawberry red
  "#f3722c", // atomic tangerine
  "#f8961e", // carrot orange
  "#f9844a", // coral glow
  "#f9c74f", // tuscan sun
  "#90be6d", // willow green
  "#43aa8b", // seagrass
  "#4d908e", // dark cyan
  "#577590", // blue slate
  "#277da1", // cerulean
];

// Stable color for a label: same name -> same swatch every render.
export function colorFor(key: string): string {
  const s = (key || "").trim().toLowerCase();
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  return PALETTE[h % PALETTE.length];
}

// A fixed ordered slice (used when we want visually distinct adjacent segments,
// e.g. the top expense categories in the stacked bar).
export function paletteAt(i: number): string {
  return PALETTE[i % PALETTE.length];
}
