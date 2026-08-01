"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  fmtBaht,
  sinceForRange,
  bkkMonthKey,
  monthLabel,
  type RangeKey,
} from "@/lib/format";
import type {
  Account,
  CardStatement,
  Category,
  DbAccount,
  Subcategory,
  Txn,
} from "@/lib/types";

// THB value of a transaction: the reconciled THB amount when set (foreign
// charge resolved from a statement), else the amount when already THB, else
// null (foreign, not yet reconciled -> excluded from ฿ totals).
function thbValue(t: Txn): number | null {
  if (t.thb_amount != null) return Number(t.thb_amount);
  if ((t.currency ?? "THB") === "THB") return Number(t.amount);
  return null;
}
import { StatTile } from "@/components/StatTile";
import { CreditCards } from "@/components/CreditCards";
import { CategoryBars } from "@/components/CategoryBars";
import { MonthlyBars } from "@/components/MonthlyBars";
import { TransactionsTable } from "@/components/TransactionsTable";
import { TransactionModal } from "@/components/NewTransactionModal";

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
  const [dbAccounts, setDbAccounts] = useState<DbAccount[]>([]);
  const [cardStatements, setCardStatements] = useState<CardStatement[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [range, setRange] = useState<RangeKey>("30d");
  const [bank, setBank] = useState("all");
  const [modal, setModal] = useState<{ mode: "add" } | { mode: "edit"; txn: Txn } | null>(
    null,
  );

  async function del(t: Txn) {
    if (!window.confirm(`Delete this ${t.direction} of ${t.amount} ${t.currency ?? "THB"}?`)) {
      return;
    }
    const res = await fetch(`/api/transactions?id=${t.id}`, { method: "DELETE" });
    if (res.ok) {
      load();
    } else {
      const j = await res.json().catch(() => ({}));
      setError(j.error || "Delete failed");
    }
  }

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
      setDbAccounts(j.accounts ?? []);
      setCardStatements(j.cardStatements ?? []);
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

  // Account options for the manual form. Prefer the real `accounts` table (so
  // every configured account shows, incl. ones with no transactions yet); fall
  // back to accounts seen in transactions only if the table is empty.
  const accounts = useMemo<Account[]>(() => {
    const list: Account[] = [
      { key: "cash", label: "Cash", method: "cash", bank: null, account_masked: null },
    ];
    const own = dbAccounts.filter((a) => a.is_own !== false);
    if (own.length > 0) {
      for (const a of own) {
        if (a.type === "cash") continue; // "Cash" is already the first option
        const masked = a.masked_number ?? null;
        const label =
          a.display_name ||
          `${a.bank_name ?? "Account"}${masked ? " ••" + masked : ""}` +
            (a.type === "credit_card" ? " (card)" : "");
        list.push({
          key: `acct-${a.id}`,
          label,
          method: a.type as Account["method"],
          bank: a.bank_name,
          account_masked: masked,
        });
      }
      return list;
    }
    // Fallback: derive from transactions.
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
  }, [dbAccounts, txns]);

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
    // THB value per row: reconciled THB (incl. resolved foreign) counts; foreign
    // charges without a THB yet are excluded from ฿ totals.
    const external = filtered.filter((t) => !t.is_internal && thbValue(t) != null);
    const cashFlow = external.filter((t) => t.method !== "credit_card");
    const spend = cashFlow
      .filter((t) => t.direction === "debit")
      .reduce((s, t) => s + (thbValue(t) ?? 0), 0);
    const income = cashFlow
      .filter((t) => t.direction === "credit")
      .reduce((s, t) => s + (thbValue(t) ?? 0), 0);
    const reviewCount = filtered.filter((t) => t.needs_review).length;

    const catTotals = new Map<string, number>();
    for (const t of external) {
      if (t.direction !== "debit") continue;
      const name = t.category_id ? categories[t.category_id] ?? "Uncategorized" : "Uncategorized";
      catTotals.set(name, (catTotals.get(name) || 0) + (thbValue(t) ?? 0));
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
      monthTotals.set(k, (monthTotals.get(k) || 0) + (thbValue(t) ?? 0));
    }
    const monthly = [...monthTotals.entries()]
      .sort((a, b) => a[0].localeCompare(b[0]))
      .slice(-6)
      .map(([k, amount]) => ({ month: monthLabel(k), amount }));

    return { spend, income, reviewCount, byCategory, monthly };
  }, [filtered, categories]);

  // Per-card unpaid balance. When a statement anchor exists for a card, the true
  // balance = that statement's closing balance + card movement AFTER the
  // statement date (statement-sourced rows are all on/before it, so no double
  // count). Without an anchor, fall back to all-time net (charges − payments).
  const { cards, cardTotal, anchored } = useMemo(() => {
    // latest anchor per card (list is newest-first from the API)
    const latestAnchor = new Map<string, CardStatement>();
    for (const a of cardStatements) {
      const k = `${a.bank}|${a.card_masked}`;
      if (!latestAnchor.has(k)) latestAnchor.set(k, a);
    }

    const map = new Map<
      string,
      { label: string; net: number; anchor?: CardStatement }
    >();
    for (const t of txns) {
      if (t.method !== "credit_card" || t.is_internal) continue;
      const v = thbValue(t);
      if (v == null) continue; // foreign, not yet reconciled
      const masked = t.account_masked ?? "";
      const label = `${t.bank ?? "Card"}${masked ? " ••" + masked : ""}`;
      const anchor = latestAnchor.get(`${t.bank}|${masked}`);
      const cur = map.get(label) ?? { label, net: 0, anchor };
      if (anchor) {
        // Only count movement strictly after the statement date.
        const afterAnchor =
          new Date(t.ts) > new Date(anchor.statement_date + "T23:59:59+07:00");
        if (afterAnchor) cur.net += (t.direction === "debit" ? 1 : -1) * v;
      } else {
        cur.net += (t.direction === "debit" ? 1 : -1) * v;
      }
      map.set(label, cur);
    }
    // Seed the anchor base for cards that have an anchor.
    let anyAnchor = false;
    for (const [k, a] of latestAnchor) {
      const [b, m] = k.split("|");
      const label = `${b}${m ? " ••" + m : ""}`;
      anyAnchor = true;
      const cur = map.get(label) ?? { label, net: 0, anchor: a };
      cur.net += Number(a.closing_balance);
      cur.anchor = a;
      map.set(label, cur);
    }
    const list = [...map.values()]
      .map((c) => ({ label: c.label, net: c.net }))
      .sort((a, b) => b.net - a.net);
    return {
      cards: list,
      cardTotal: list.reduce((s, c) => s + c.net, 0),
      anchored: anyAnchor,
    };
  }, [txns, cardStatements]);

  return (
    <div className="container">
      <div className="topbar">
        <h1>💸 Money Manager</h1>
        <div style={{ display: "flex", gap: 8 }}>
          <button
            className="btn"
            onClick={() => setModal({ mode: "add" })}
            style={{ background: "var(--series-1)", color: "#fff", borderColor: "var(--series-1)" }}
          >
            ＋ Add
          </button>
          <button className="btn" onClick={load} disabled={loading}>
            {loading ? "Refreshing…" : "↻ Refresh"}
          </button>
          <Link className="btn" href="/statements">
            📄 Statements
          </Link>
          <form method="post" action="/api/logout">
            <button className="btn" type="submit">
              Sign out
            </button>
          </form>
        </div>
      </div>

      {modal ? (
        <TransactionModal
          accounts={accounts}
          categories={cats}
          subcategories={subs}
          editing={modal.mode === "edit" ? modal.txn : null}
          onClose={() => setModal(null)}
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

          {cards.length > 0 ? (
            <CreditCards total={cardTotal} cards={cards} anchored={anchored} />
          ) : null}

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
            <TransactionsTable
              rows={filtered.slice(0, 500)}
              categories={categories}
              onEdit={(t) => setModal({ mode: "edit", txn: t })}
              onDelete={del}
            />
          </div>
        </>
      )}
    </div>
  );
}
