"use client";

import { useLayoutEffect, useRef, useState } from "react";
import { fmtBaht } from "@/lib/format";
import { squarify } from "@/lib/treemap";

export type TreeItem = {
  name: string;
  amount: number;
  color: string;
  changePct: number | null;
};

// Wide-rectangle treemap of expense categories. Each tile: name, value, and the
// category's own % change vs the previous period (▲ red / ▼ green — for spending,
// down is good).
export function Treemap({ items, height = 210 }: { items: TreeItem[]; height?: number }) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [width, setWidth] = useState(0);

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const measure = () => setWidth(el.clientWidth);
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const tiles =
    width > 0
      ? squarify(
          items.map((i) => ({ ...i, value: i.amount })),
          width,
          height,
        )
      : [];

  return (
    <div className="treemap" ref={ref} style={{ height }}>
      {tiles.map((t) => {
        const showVal = t.h >= 42 && t.w >= 56;
        const showChg = t.changePct !== null && t.h >= 58 && t.w >= 72;
        const good = (t.changePct ?? 0) < 0; // spending down = good
        return (
          <div
            key={t.name}
            className="tm-tile"
            style={{ left: t.x, top: t.y, width: t.w, height: t.h, background: t.color }}
            title={`${t.name}: ${fmtBaht(t.amount)}${
              t.changePct !== null ? ` (${t.changePct >= 0 ? "+" : ""}${t.changePct.toFixed(1)}%)` : ""
            }`}
          >
            <div className="tm-name">{t.name}</div>
            {showVal ? <div className="tm-val">{fmtBaht(t.amount)}</div> : null}
            {showChg ? (
              <div className={`tm-chg ${good ? "pos" : "neg"}`}>
                {(t.changePct as number) >= 0 ? "▲" : "▼"}{" "}
                {Math.abs(t.changePct as number).toFixed(1)}%
              </div>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}
