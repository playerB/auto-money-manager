// Squarified treemap layout (Bruls, Huizing & van Wijk). Lays a flat list of
// weighted items into a rectangle, keeping tiles close to square. Returns each
// item with pixel-space x/y/w/h inside the given box.
export type TreemapInput = { value: number; [k: string]: unknown };
export type TreemapTile<T> = T & { x: number; y: number; w: number; h: number };

export function squarify<T extends TreemapInput>(
  items: T[],
  width: number,
  height: number,
): TreemapTile<T>[] {
  const clean = items.filter((i) => i.value > 0);
  if (clean.length === 0 || width <= 0 || height <= 0) return [];

  const total = clean.reduce((s, i) => s + i.value, 0);
  const scale = (width * height) / total;
  const nodes = clean
    .map((it) => ({ it, area: it.value * scale }))
    .sort((a, b) => b.area - a.area);

  const out: TreemapTile<T>[] = [];
  const rect = { x: 0, y: 0, dx: width, dy: height };

  const worst = (start: number, end: number, side: number) => {
    let sum = 0;
    let mx = -Infinity;
    let mn = Infinity;
    for (let k = start; k <= end; k++) {
      const a = nodes[k].area;
      sum += a;
      if (a > mx) mx = a;
      if (a < mn) mn = a;
    }
    const s2 = sum * sum;
    return Math.max((side * side * mx) / s2, s2 / (side * side * mn));
  };

  let i0 = 0;
  while (i0 < nodes.length) {
    const side = Math.min(rect.dx, rect.dy);
    let i1 = i0;
    let cur = worst(i0, i1, side);
    while (i1 + 1 < nodes.length) {
      const next = worst(i0, i1 + 1, side);
      if (next > cur) break;
      i1++;
      cur = next;
    }

    let sum = 0;
    for (let k = i0; k <= i1; k++) sum += nodes[k].area;

    if (rect.dx >= rect.dy) {
      // carve a vertical column on the left; stack tiles top→bottom
      const colW = sum / rect.dy;
      let yy = rect.y;
      for (let k = i0; k <= i1; k++) {
        const hh = nodes[k].area / colW;
        out.push({ ...(nodes[k].it as T), x: rect.x, y: yy, w: colW, h: hh });
        yy += hh;
      }
      rect.x += colW;
      rect.dx -= colW;
    } else {
      // carve a horizontal row on top; place tiles left→right
      const rowH = sum / rect.dx;
      let xx = rect.x;
      for (let k = i0; k <= i1; k++) {
        const ww = nodes[k].area / rowH;
        out.push({ ...(nodes[k].it as T), x: xx, y: rect.y, w: ww, h: rowH });
        xx += ww;
      }
      rect.y += rowH;
      rect.dy -= rowH;
    }
    i0 = i1 + 1;
  }
  return out;
}
