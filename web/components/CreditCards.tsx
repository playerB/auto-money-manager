"use client";

import { useState } from "react";
import { fmtBaht } from "@/lib/format";
import { paletteAt } from "@/lib/palette";

// Card-like stack: first face = total outstanding across all cards, then one
// face per card (bank ••last4 + amount used). Tap to swap to the next card;
// dots show progress (Instagram-style). Each card gets a palette color.
export function CreditCards({
  total,
  cards,
  anchored,
}: {
  total: number;
  cards: { label: string; net: number }[];
  anchored?: boolean;
}) {
  const faces = [
    { label: "Total outstanding balance", amount: total, color: "var(--brand)" },
    ...cards.map((c, i) => ({ label: c.label, amount: c.net, color: paletteAt(i) })),
  ];
  const n = faces.length;
  const [idx, setIdx] = useState(0);

  return (
    <section className="panel rise" style={{ animationDelay: "0.14s" }}>
      <div className="panel-head">
        <div>
          <h2 className="panel-title">Credit cards</h2>
        </div>
      </div>

      <div
        className="cc-stack"
        role="button"
        tabIndex={0}
        aria-label="Next card"
        onClick={() => setIdx((i) => (i + 1) % n)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") setIdx((i) => (i + 1) % n);
        }}
      >
        {faces.map((f, i) => {
          const pos = (i - idx + n) % n;
          return (
            <div
              key={i}
              className="cc-card"
              data-pos={pos <= 2 ? pos : "hidden"}
              style={{
                background: `linear-gradient(135deg, rgba(255,255,255,.16), rgba(0,0,0,.18)), ${f.color}`,
              }}
            >
              <div className="cc-top">
                <span className="cc-chip" />
                <span className="cc-mc">
                  <span className="cc-mc-a" />
                  <span className="cc-mc-b" />
                </span>
              </div>
              <div className="cc-amount">{fmtBaht(f.amount)}</div>
              <div className="cc-label">{f.label}</div>
            </div>
          );
        })}
      </div>

      <div className="cc-dots">
        {faces.map((_, i) => (
          <button
            key={i}
            className="cc-dot"
            data-active={i === idx}
            aria-label={`Card ${i + 1}`}
            onClick={() => setIdx(i)}
          />
        ))}
      </div>

      <p className="panel-sub" style={{ marginTop: 12, textAlign: "center" }}>
        {anchored ? "Outstanding — anchored to latest statements" : "Balance since tracking"}
      </p>
    </section>
  );
}
