"use client";

import { fmtBaht } from "@/lib/format";
import { CountUp } from "@/components/CountUp";

// Income card: % change (on top) + total for the selected period + a slim bar.
export function IncomePanel({
  total,
  changePct,
  periodLabel,
  barPct,
}: {
  total: number;
  changePct: number | null;
  periodLabel: string | null;
  barPct: number;
}) {
  // For income, an increase is good (green).
  const good = changePct !== null && changePct >= 0;

  return (
    <section className="panel rise" style={{ animationDelay: "0.05s" }}>
      <div className="panel-head">
        <div>
          <h2 className="panel-title">Income</h2>
        </div>
      </div>

      {changePct === null ? (
        <div className="delta-note" style={{ marginBottom: 2 }}>
          {periodLabel ?? "all time"}
        </div>
      ) : (
        <div className={`delta ${good ? "pos" : "neg"}`} style={{ marginBottom: 2 }}>
          {changePct >= 0 ? "▲" : "▼"} {Math.abs(changePct).toFixed(1)}%
          <span className="delta-note"> {periodLabel}</span>
        </div>
      )}
      <div>
        <CountUp className="amount-xl" value={total} format={fmtBaht} />
      </div>

      <div className="slimbar">
        <div
          className="slimbar-fill"
          style={{ width: `${Math.max(4, Math.min(100, barPct))}%` }}
        />
      </div>
    </section>
  );
}
