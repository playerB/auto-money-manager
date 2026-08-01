"use client";

import { fmtBaht } from "@/lib/format";

export type SourceItem = { name: string; amount: number; color: string };

// Income breakdown by source (no pie). Each source: a header line with the name
// (left) and value (right) aligned, then a full-width progress bar beneath it.
export function IncomeBreakdown({ sources }: { sources: SourceItem[] }) {
  const max = Math.max(1, ...sources.map((s) => s.amount));
  return (
    <section className="panel rise" style={{ animationDelay: "0.1s" }}>
      <div className="panel-head">
        <div>
          <h2 className="panel-title">Income breakdown</h2>
        </div>
      </div>

      {sources.length === 0 ? (
        <p className="empty">No income in this period.</p>
      ) : (
        <div>
          {sources.map((s) => (
            <div className="inc-row" key={s.name}>
              <div className="inc-head">
                <span className="inc-name">
                  <span className="dot" style={{ background: s.color }} />
                  {s.name}
                </span>
                <span className="inc-amount">{fmtBaht(s.amount)}</span>
              </div>
              <div className="inc-track">
                <div
                  className="inc-fill"
                  style={{ width: `${(s.amount / max) * 100}%`, background: s.color }}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
