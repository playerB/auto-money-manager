"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { fmtBaht, fmtMoney, fmtTime, fmtDateHeader } from "@/lib/format";
import { colorFor } from "@/lib/palette";
import type { Txn } from "@/lib/types";

const PAGE = 20; // rows revealed per "load more"
const LOAD_MS = 500; // brief load animation even though data is prefetched

function PencilIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 20h9" />
      <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4Z" />
    </svg>
  );
}
function TrashIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 6h18" />
      <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
      <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
    </svg>
  );
}

function amountText(t: Txn): string {
  const sign = t.direction === "credit" ? "+" : "−";
  if (t.thb_amount != null) return `${sign}${fmtBaht(Number(t.thb_amount))}`;
  if ((t.currency ?? "THB") === "THB") return `${sign}${fmtBaht(Number(t.amount))}`;
  return `${sign}${fmtMoney(Number(t.amount), t.currency)}`;
}

// Count of transactions within the last 3 days (from now); at least a few so the
// list never starts empty.
function initialCount(rows: Txn[]): number {
  const cutoff = Date.now() - 3 * 864e5;
  let n = 0;
  for (const t of rows) if (new Date(t.ts).getTime() >= cutoff) n++;
  if (n === 0) return Math.min(rows.length, 8);
  return n;
}

export function RecentTransactions({
  rows,
  categories,
  search,
  onSearch,
  onEdit,
  onDelete,
}: {
  rows: Txn[];
  categories: Record<number, string>;
  search: string;
  onSearch: (v: string) => void;
  onEdit: (t: Txn) => void;
  onDelete: (t: Txn) => void;
}) {
  const [visible, setVisible] = useState(() => initialCount(rows));
  const [loading, setLoading] = useState(false);
  const sentinelRef = useRef<HTMLDivElement | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Reset when the underlying list changes (filters / search / refresh).
  useEffect(() => {
    setVisible(initialCount(rows));
    setLoading(false);
  }, [rows]);

  const hasMore = visible < rows.length;

  // Reveal the next page (with a short spinner) when the sentinel scrolls in.
  useEffect(() => {
    if (!hasMore) return;
    const el = sentinelRef.current;
    if (!el) return;
    const io = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && !timer.current) {
          setLoading(true);
          timer.current = setTimeout(() => {
            setVisible((v) => Math.min(rows.length, v + PAGE));
            setLoading(false);
            timer.current = null;
          }, LOAD_MS);
        }
      },
      { rootMargin: "120px" },
    );
    io.observe(el);
    return () => {
      io.disconnect();
      if (timer.current) {
        clearTimeout(timer.current);
        timer.current = null;
      }
    };
  }, [hasMore, rows.length, visible]);

  // Group the visible slice by Bangkok day (rows arrive newest-first).
  const groups = useMemo(() => {
    const out: { key: string; label: string; items: Txn[] }[] = [];
    const idx = new Map<string, number>();
    for (const t of rows.slice(0, visible)) {
      const key = new Date(new Date(t.ts).getTime() + 7 * 3600 * 1000)
        .toISOString()
        .slice(0, 10);
      let gi = idx.get(key);
      if (gi === undefined) {
        gi = out.length;
        idx.set(key, gi);
        out.push({ key, label: fmtDateHeader(t.ts), items: [] });
      }
      out[gi].items.push(t);
    }
    return out;
  }, [rows, visible]);

  return (
    <section className="panel rise" style={{ animationDelay: "0.08s" }}>
      <div className="panel-head" style={{ alignItems: "center" }}>
        <h2 className="panel-title" style={{ whiteSpace: "nowrap" }}>
          Transaction
        </h2>
        <div className="txn-search">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="7" />
            <path d="m21 21-4.3-4.3" />
          </svg>
          <input
            placeholder="Search transactions"
            value={search}
            onChange={(e) => onSearch(e.target.value)}
          />
        </div>
      </div>

      {rows.length === 0 ? (
        <p className="empty">No transactions match.</p>
      ) : (
        <>
          {groups.map((g) => (
            <div key={g.key}>
              <div className="txn-date">{g.label}</div>
              {g.items.map((t) => {
                const cat = t.category_id ? categories[t.category_id] : null;
                const colorKey = cat || t.counterparty_name || "?";
                const name =
                  t.counterparty_name || (t.is_internal ? "Internal transfer" : "—");
                return (
                  <div className="txn-row" key={t.id}>
                    <div className="txn-ico" style={{ background: colorFor(colorKey) }}>
                      {(name[0] || "?").toUpperCase()}
                    </div>
                    <div className="txn-main">
                      <div className="txn-name">
                        {name}
                        {t.is_internal ? <span className="tag">internal</span> : null}
                        {t.needs_review ? <span className="tag review">review</span> : null}
                      </div>
                      <div className="txn-time">{fmtTime(t.ts)}</div>
                    </div>
                    <div className="txn-cat">
                      {cat ? (
                        <>
                          <span className="dot" style={{ background: colorFor(cat) }} />
                          <span>{cat}</span>
                        </>
                      ) : (
                        <>
                          <span className="dot" style={{ background: "var(--baseline)" }} />
                          <span style={{ color: "var(--muted)" }}>Uncategorized</span>
                        </>
                      )}
                    </div>
                    <div className={`txn-amt ${t.direction === "credit" ? "pos" : ""}`}>
                      {amountText(t)}
                    </div>
                    <div className="txn-actions">
                      <button className="icon-btn" aria-label="Edit" onClick={() => onEdit(t)}>
                        <PencilIcon />
                      </button>
                      <button
                        className="icon-btn danger"
                        aria-label="Delete"
                        onClick={() => onDelete(t)}
                      >
                        <TrashIcon />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          ))}

          {hasMore ? (
            <div className="txn-loader" ref={sentinelRef}>
              <span className="spinner" />
              <span>Loading more…</span>
            </div>
          ) : rows.length > initialCount(rows) ? (
            <div className="txn-end">That’s everything.</div>
          ) : null}
        </>
      )}
    </section>
  );
}
