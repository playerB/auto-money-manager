"use client";

import { useEffect, useMemo, useState } from "react";
import {
  fmtBaht,
  sinceForRange,
  bkkMonthKey,
  monthLabel,
  type RangeKey,
} from "@/lib/format";
import type { Account, Category, Subcategory, Txn } from "@/lib/types";
import { StatTile } from "@/components/StatTile";
import { CreditCards } from "@/components/CreditCards";
import { CategoryBars } from "@/components/CategoryBars";
import { MonthlyBars } from "@/components/MonthlyBars";
import { TransactionsTable } from "@/components/TransactionsTable";
import { NewTransactionModal } from "@/components/NewTransactionModal";

const RANGES: { key: RangeKey; label: string }[] = [
  { key: "7d", label: "7 days" },
  { key: "30d", label: "30 days" },
  { key: "90d", label: "90 days" },
  { key: "mtd", label: "This month" },
  { key: "all", label: "All" },
];

export function DashboardClient() {
  const [txns, setTxns] = useState<Txn[]>([]);
  const [cats, setCats] = useState<Category[]>([]);
  const [subs, setSubs] = useState<Subcategory[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [range, setRange] = useState<RangeKey>("30d");
  const [bank, setBank] = useState("all");
  const [showAdd, setShowAdd] = useState(false);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/data", { cache: "no-store" });
      if (!res.ok) throw new Error(`Failed to load data (${res.status})`);
      const j = await res.json();
      setTxns(j.transactions ?? []);
      setCats(j.categories ?? []);
      setSubs(j.subcategories ?? []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  const categories = useMemo(() => {
    const m: Record<number, string> = {};
    for (const c of cats) m[c.id] = c.name;
    return m;
  }, [cats]);

  // Fetched once; the bank list is derived here, not re-queried per click.
  const banks = useMemo(
    () => Array.from(new Set(txns.map((t) => t.bank).filter(Boolean))).sort() as string[],
    [txns],
  );

  // Account options for the manual form: "Cash" + each bank account / card seen.
  const accounts = useMemo<Account[]>(() => {
    const list: Account[] = [
      { key: "cash", label: "Cash", method: "cash", bank: null, account_masked: null },
    ];
    const seen = new Set<string>();
    for (const t of txns) {
      if (t.method === "cash" || !t.bank) continue;
      const key = `${t.method}|${t.bank}|${t.account_masked ?? ""}`;
      if (seen.has(key)) continue;
      seen.add(key);
      const label =
        `${t.bank}${t.account_masked ? " ••" + t.account_masked : ""}` +
        (t.method === "credit_card" ? " (card)" : "");
      list.push({
        key,
        label,
        method: t.method as Account["method"],
        bank: t.bank,
        account_masked: t.account_masked,
      });
    }
    return list;
  }, [txns]);

  // All filtering is in-memory -> instant.
  const filtered = useMemo(() => {
    const since = sinceForRange(range);
    return txns.filter((t) => {
      if (bank !== "all" && t.bank !== bank) return false;
      if (since && new Date(t.ts) < since) return false;
      return true;
    });
  }, [txns, range, bank]);

  const metrics = useMemo(() => {
    // THB-only for ฿ totals (foreign amounts show in the table but aren't summed).
    const external = filtered.filter(
      (t) => !t.is_internal && (t.currency ?? "THB") === "THB",
    );
    const cashFlow = external.filter((t) => t.method !== "credit_card");
    const spend = cashFlow
      .filter((t) => t.direction === "debit")
      .reduce((s, t) => s + Number(t.amount), 0);
    const income = cashFlow
      .filter((t) => t.direction === "credit")
      .reduce((s, t) => s + Number(t.amount), 0);
    const reviewCount = filtered.filter((t) => t.needs_review).length;

    const catTotals = new Map<string, number>();
    for (const t of external) {
      if (t.direction !== "debit") continue;
      const name = t.category_id ? categories[t.category_id] ?? "Uncategorized" : "Uncategorized";
      catTotals.set(name, (catTotals.get(name) || 0) + Number(t.amount));
    }
    let byCategory = [...catTotals.entries()]
      .map(([name, amount]) => ({ name, amount }))
      .sort((a, b) => b.amount - a.amount);
    if (byCategory.length > 8) {
      const top = byCategory.slice(0, 7);
      const other = byCategory.slice(7).reduce((s, d) => s + d.amount, 0);
      byCategory = [...top, { name: "Other", amount: other }];
    }

    const monthTotals = new Map<string, number>();
    for (const t of external) {
      if (t.direction !== "debit") continue;
      const k = bkkMonthKey(t.ts);
      monthTotals.set(k, (monthTotals.get(k) || 0) + Number(t.amount));
    }
    const monthly = [...monthTotals.entries()]
      .sort((a, b) => a[0].localeCompare(b[0]))
      .slice(-6)
      .map(([k, amount]) => ({ month: monthLabel(k), amount }));

    return { spend, income, reviewCount, byCategory, monthly };
  }, [filtered, categories]);

  // Card balance is cumulative: all card transactions (unfiltered), not internal.
  const { cards, cardTotal } = useMemo(() => {
    const map = new Map<string, { label: string; net: number }>();
    for (const t of txns) {
      if (t.method !== "credit_card" || t.is_internal) continue;
      if ((t.currency ?? "THB") !== "THB") continue;
      const key = `${t.bank ?? "Card"}${t.account_masked ? " ••" + t.account_masked : ""}`;
      const cur = map.get(key) ?? { label: key, net: 0 };
      cur.net += (t.direction === "debit" ? 1 : -1) * Number(t.amount);
      map.set(key, cur);
    }
    const list = [...map.values()].sort((a, b) => b.net - a.net);
    return { cards: list, cardTotal: list.reduce((s, c) => s + c.net, 0) };
  }, [txns]);

  return (
    <div className="container">
      <div className="topbar">
        <h1>💸 Money Manager</h1>
        <div style={{ display: "flex", gap: 8 }}>
          <button
            className="btn"
            onClick={() => setShowAdd(true)}
            style={{ background: "var(--series-1)", color: "#fff", borderColor: "var(--series-1)" }}
          >
            ＋ Add
          </button>
          <button className="btn" onClick={load} disabled={loading}>
            {loading ? "Refreshing…" : "↻ Refresh"}
          </button>
          <form method="post" action="/api/logout">
            <button className="btn" type="submit">
              Sign out
            </button>
          </form>
        </div>
      </div>

      {showAdd ? (
        <NewTransactionModal
          accounts={accounts}
          categories={cats}
          subcategories={subs}
          onClose={() => setShowAdd(false)}
          onSaved={load}
        />
      ) : null}

      {/* Filters — plain buttons, no navigation */}
      <div className="filters">
        {RANGES.map((r) => (
          <button
            key={r.key}
            className="chip"
            data-active={range === r.key}
            onClick={() => setRange(r.key)}
          >
            {r.label}
          </button>
        ))}
        <span style={{ width: 12 }} />
        <button className="chip" data-active={bank === "all"} onClick={() => setBank("all")}>
          All banks
        </button>
        {banks.map((b) => (
          <button key={b} className="chip" data-active={bank === b} onClick={() => setBank(b)}>
            {b}
          </button>
        ))}
      </div>

      {error ? (
        <div className="card" style={{ color: "var(--critical)" }}>
          {error} — <button className="btn" onClick={load}>retry</button>
        </div>
      ) : loading && txns.length === 0 ? (
        <div className="card" style={{ color: "var(--muted)" }}>Loading…</div>
      ) : (
        <>
          <div className="grid-tiles">
            <StatTile label="Spending (cash/bank)" value={fmtBaht(metrics.spend)} />
            <StatTile label="Income (cash/bank)" value={fmtBaht(metrics.income)} />
            <StatTile label="Transactions" value={String(filtered.length)} />
            <StatTile label="Needs review" value={String(metrics.reviewCount)} />
          </div>

          {cards.length > 0 ? <CreditCards total={cardTotal} cards={cards} /> : null}

          <div className="grid-two">
            <div className="card">
              <h2 className="section-title">Spending by category</h2>
              <CategoryBars data={metrics.byCategory} />
            </div>
            <div className="card">
              <h2 className="section-title">Monthly spending</h2>
              <MonthlyBars data={metrics.monthly} />
            </div>
          </div>

          <div className="card">
            <h2 className="section-title">
              Transactions{filtered.length > 500 ? ` (showing 500 of ${filtered.length})` : ""}
            </h2>
            <TransactionsTable rows={filtered.slice(0, 500)} categories={categories} />
          </div>
        </>
      )}
    </div>
  );
}
