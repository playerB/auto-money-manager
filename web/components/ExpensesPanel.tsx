"use client";

import { fmtBaht } from "@/lib/format";
import { CountUp } from "@/components/CountUp";
import { Treemap, type TreeItem } from "@/components/Treemap";

// Expenses card: % change + total on the left, a wide category treemap on the right.
export function ExpensesPanel({
  total,
  changePct,
  periodLabel,
  breakdown,
}: {
  total: number;
  changePct: number | null;
  periodLabel: string | null;
  breakdown: TreeItem[];
}) {
  // For spending, a decrease is good (green); an increase is red.
  const good = changePct !== null && changePct < 0;

  return (
    <section className="panel rise">
      <div className="panel-head">
        <div>
          <h2 className="panel-title">Expenses</h2>
        </div>
      </div>

      <div className="exp-body">
        <div className="exp-left">
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
        </div>

        <div className="exp-right">
          {breakdown.length === 0 ? (
            <p className="empty">No spending in this period.</p>
          ) : (
            <Treemap items={breakdown} />
          )}
        </div>
      </div>
    </section>
  );
}
