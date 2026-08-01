"use client";

import { useEffect, useMemo, useState } from "react";
import { fmtBaht, sinceForRange, type RangeKey } from "@/lib/format";
import { colorFor } from "@/lib/palette";
import type {
  Account,
  CardStatement,
  Category,
  DbAccount,
  Subcategory,
  Txn,
} from "@/lib/types";
import { AppShell } from "@/components/AppShell";
import { ExpensesPanel } from "@/components/ExpensesPanel";
import { IncomePanel } from "@/components/IncomePanel";
import { IncomeBreakdown } from "@/components/IncomeBreakdown";
import { RecentTransactions } from "@/components/RecentTransactions";
import { CreditCards } from "@/components/CreditCards";
import { ThemeToggle } from "@/components/ThemeToggle";
import { TransactionModal } from "@/components/NewTransactionModal";

const RANGES: { key: RangeKey; label: string }[] = [
  { key: "7d", label: "7 days" },
  { key: "30d", label: "30 days" },
  { key: "90d", label: "90 days" },
  { key: "mtd", label: "This month" },
  { key: "all", label: "All" },
];

// THB value of a row: reconciled THB when set, else amount when THB, else null.
function thbValue(t: Txn): number | null {
  if (t.thb_amount != null) return Number(t.thb_amount);
  if ((t.currency ?? "THB") === "THB") return Number(t.amount);
  return null;
}

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
  const [search, setSearch] = useState("");
  const [updatedAt, setUpdatedAt] = useState<string>("");
  const [modal, setModal] = useState<{ mode: "add" } | { mode: "edit"; txn: Txn } | null>(
    null,
  );

  async function del(t: Txn) {
    if (!window.confirm(`Delete this ${t.direction} of ${t.amount} ${t.currency ?? "THB"}?`)) {
      return;
    }
    const res = await fetch(`/api/transactions?id=${t.id}`, { method: "DELETE" });
    if (res.ok) load();
    else {
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
      setUpdatedAt(
        new Intl.DateTimeFormat("en-GB", {
          timeZone: "Asia/Bangkok",
          hour: "2-digit",
          minute: "2-digit",
          hour12: false,
        }).format(new Date()),
      );
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

  const banks = useMemo(
    () => Array.from(new Set(txns.map((t) => t.bank).filter(Boolean))).sort() as string[],
    [txns],
  );

  // Modal account options: prefer the real accounts table.
  const accounts = useMemo<Account[]>(() => {
    const list: Account[] = [
      { key: "cash", label: "Cash", method: "cash", bank: null, account_masked: null },
    ];
    const own = dbAccounts.filter((a) => a.is_own !== false);
    if (own.length > 0) {
      for (const a of own) {
        if (a.type === "cash") continue;
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

  // --- Expense/Income recap — respects the range + bank + search filters ----
  // Current window from the range chip; the previous equal-length window drives
  // the % change and its wording (vs last week / month / quarter).
  const recap = useMemo(() => {
    const DAY = 864e5;
    const now = Date.now();
    const d = new Date();
    let curLo = 0;
    let curHi = now;
    let prevLo: number | null = null;
    let prevHi: number | null = null;
    let label: string | null = null;
    if (range === "7d") {
      curLo = now - 7 * DAY; prevLo = now - 14 * DAY; prevHi = now - 7 * DAY; label = "vs last week";
    } else if (range === "30d") {
      curLo = now - 30 * DAY; prevLo = now - 60 * DAY; prevHi = now - 30 * DAY; label = "vs last month";
    } else if (range === "90d") {
      curLo = now - 90 * DAY; prevLo = now - 180 * DAY; prevHi = now - 90 * DAY; label = "vs last quarter";
    } else if (range === "mtd") {
      curLo = new Date(d.getFullYear(), d.getMonth(), 1).getTime();
      prevLo = new Date(d.getFullYear(), d.getMonth() - 1, 1).getTime();
      prevHi = new Date(
        d.getFullYear(), d.getMonth() - 1, d.getDate(), d.getHours(), d.getMinutes(), d.getSeconds(),
      ).getTime();
      label = "vs last month";
    } // "all": curLo=0, no previous window, no label

    const q = search.trim().toLowerCase();
    const base = txns.filter((t) => {
      if (bank !== "all" && t.bank !== bank) return false;
      if (q) {
        const cat = t.category_id ? categories[t.category_id] ?? "" : "";
        const hay = `${t.counterparty_name ?? ""} ${cat} ${t.bank ?? ""}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
    const ext = base.filter((t) => !t.is_internal && thbValue(t) != null);
    const inWin = (t: Txn, lo: number, hi: number) => {
      const ts = new Date(t.ts).getTime();
      return ts >= lo && ts <= hi;
    };
    const sumExp = (lo: number, hi: number) =>
      ext.filter((t) => t.direction === "debit" && inWin(t, lo, hi)).reduce((s, t) => s + (thbValue(t) ?? 0), 0);
    const sumInc = (lo: number, hi: number) =>
      ext
        .filter((t) => t.direction === "credit" && t.method !== "credit_card" && inWin(t, lo, hi))
        .reduce((s, t) => s + (thbValue(t) ?? 0), 0);

    const expenseTotal = sumExp(curLo, curHi);
    const incomeTotal = sumInc(curLo, curHi);
    const expPrev = prevLo !== null && prevHi !== null ? sumExp(prevLo, prevHi) : null;
    const incPrev = prevLo !== null && prevHi !== null ? sumInc(prevLo, prevHi) : null;
    const expenseChangePct = expPrev && expPrev > 0 ? ((expenseTotal - expPrev) / expPrev) * 100 : null;
    const incomeChangePct = incPrev && incPrev > 0 ? ((incomeTotal - incPrev) / incPrev) * 100 : null;

    // expense-by-category for the current window + previous window (for per-tile %)
    const catMap = new Map<string, number>();
    const prevCatMap = new Map<string, number>();
    for (const t of ext) {
      if (t.direction !== "debit") continue;
      const name = t.category_id ? categories[t.category_id] ?? "Uncategorized" : "Uncategorized";
      if (inWin(t, curLo, curHi)) catMap.set(name, (catMap.get(name) ?? 0) + (thbValue(t) ?? 0));
      else if (prevLo !== null && prevHi !== null && inWin(t, prevLo, prevHi))
        prevCatMap.set(name, (prevCatMap.get(name) ?? 0) + (thbValue(t) ?? 0));
    }
    const havePrev = prevLo !== null;
    const fullCats = [...catMap.entries()]
      .map(([name, amount]) => ({ name, amount, prev: prevCatMap.get(name) ?? 0 }))
      .sort((a, b) => b.amount - a.amount);
    let catItems = fullCats;
    if (fullCats.length > 6) {
      const top = fullCats.slice(0, 6);
      const rest = fullCats.slice(6);
      catItems = [
        ...top,
        {
          name: "Other",
          amount: rest.reduce((s, x) => s + x.amount, 0),
          prev: rest.reduce((s, x) => s + x.prev, 0),
        },
      ];
    }
    const breakdown = catItems.map((x) => ({
      name: x.name,
      amount: x.amount,
      color: colorFor(x.name),
      changePct: havePrev && x.prev > 0 ? ((x.amount - x.prev) / x.prev) * 100 : null,
    }));

    const curInc = ext.filter(
      (t) => t.direction === "credit" && t.method !== "credit_card" && inWin(t, curLo, curHi),
    );
    const srcMap = new Map<string, number>();
    for (const t of curInc) {
      const name =
        t.counterparty_name || (t.category_id ? categories[t.category_id] : null) || "Other income";
      srcMap.set(name, (srcMap.get(name) ?? 0) + (thbValue(t) ?? 0));
    }
    let sources = [...srcMap.entries()]
      .map(([name, amount]) => ({ name, amount, color: colorFor(name) }))
      .sort((a, b) => b.amount - a.amount);
    if (sources.length > 6) {
      const top = sources.slice(0, 6);
      const other = sources.slice(6).reduce((s, x) => s + x.amount, 0);
      sources = [...top, { name: "Other", amount: other, color: colorFor("Other") }];
    }

    const barPct = incPrev && incPrev > 0 ? (incomeTotal / Math.max(incomeTotal, incPrev)) * 100 : 100;

    return {
      expenseTotal,
      incomeTotal,
      expenseChangePct,
      incomeChangePct,
      breakdown,
      sources,
      periodLabel: label,
      barPct,
    };
  }, [txns, categories, range, bank, search]);

  // --- Recent transactions list (range + bank + search) --------------------
  const filtered = useMemo(() => {
    const since = sinceForRange(range);
    const q = search.trim().toLowerCase();
    return txns.filter((t) => {
      if (bank !== "all" && t.bank !== bank) return false;
      if (since && new Date(t.ts) < since) return false;
      if (q) {
        const cat = t.category_id ? categories[t.category_id] ?? "" : "";
        const hay = `${t.counterparty_name ?? ""} ${cat} ${t.bank ?? ""}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [txns, range, bank, search, categories]);

  // --- credit-card outstanding (anchored) ----------------------------------
  const { cards, cardTotal, anchored } = useMemo(() => {
    const latestAnchor = new Map<string, CardStatement>();
    for (const a of cardStatements) {
      const k = `${a.bank}|${a.card_masked}`;
      if (!latestAnchor.has(k)) latestAnchor.set(k, a);
    }
    const map = new Map<string, { label: string; net: number }>();
    for (const t of txns) {
      if (t.method !== "credit_card" || t.is_internal) continue;
      const v = thbValue(t);
      if (v == null) continue;
      const masked = t.account_masked ?? "";
      const label = `${t.bank ?? "Card"}${masked ? " ••" + masked : ""}`;
      const anchor = latestAnchor.get(`${t.bank}|${masked}`);
      const cur = map.get(label) ?? { label, net: 0 };
      if (anchor) {
        if (new Date(t.ts) > new Date(anchor.statement_date + "T23:59:59+07:00")) {
          cur.net += (t.direction === "debit" ? 1 : -1) * v;
        }
      } else {
        cur.net += (t.direction === "debit" ? 1 : -1) * v;
      }
      map.set(label, cur);
    }
    let anyAnchor = false;
    for (const [k, a] of latestAnchor) {
      const [b, m] = k.split("|");
      const label = `${b}${m ? " ••" + m : ""}`;
      anyAnchor = true;
      const cur = map.get(label) ?? { label, net: 0 };
      cur.net += Number(a.closing_balance);
      map.set(label, cur);
    }
    const list = [...map.values()].sort((a, b) => b.net - a.net);
    return { cards: list, cardTotal: list.reduce((s, c) => s + c.net, 0), anchored: anyAnchor };
  }, [txns, cardStatements]);

  return (
    <AppShell
      active="home"
      headerLeft={updatedAt ? <span className="synced">Synced at {updatedAt}</span> : null}
      headerRight={
        <>
          <ThemeToggle />
          <button className="btn" onClick={load} disabled={loading}>
            {loading ? "Refreshing…" : "↻ Refresh"}
          </button>
          <form method="post" action="/api/logout">
            <button className="btn" type="submit">
              Sign out
            </button>
          </form>
        </>
      }
    >
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

      {error ? (
        <div className="panel" style={{ color: "var(--negative)" }}>
          {error} —{" "}
          <button className="btn" onClick={load}>
            retry
          </button>
        </div>
      ) : loading && txns.length === 0 ? (
        <div className="panel" style={{ color: "var(--muted)" }}>
          Loading…
        </div>
      ) : (
        <div className="dash-grid">
          <div className="col">
            <div className="gi gi-expenses">
              <ExpensesPanel
                total={recap.expenseTotal}
                changePct={recap.expenseChangePct}
                periodLabel={recap.periodLabel}
                breakdown={recap.breakdown}
              />
            </div>

            <div className="gi gi-filters">
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
                <span style={{ width: 8 }} />
                <button
                  className="chip"
                  data-active={bank === "all"}
                  onClick={() => setBank("all")}
                >
                  All banks
                </button>
                {banks.map((b) => (
                  <button
                    key={b}
                    className="chip"
                    data-active={bank === b}
                    onClick={() => setBank(b)}
                  >
                    {b}
                  </button>
                ))}
              </div>
            </div>

            <div className="gi gi-txns">
              <RecentTransactions
                rows={filtered}
                categories={categories}
                search={search}
                onSearch={setSearch}
                onEdit={(t) => setModal({ mode: "edit", txn: t })}
                onDelete={del}
              />
            </div>
          </div>

          <div className="col">
            <div className="gi gi-income">
              <IncomePanel
                total={recap.incomeTotal}
                changePct={recap.incomeChangePct}
                periodLabel={recap.periodLabel}
                barPct={recap.barPct}
              />
            </div>
            <div className="gi gi-incbd">
              <IncomeBreakdown sources={recap.sources} />
            </div>
            {cards.length > 0 ? (
              <div className="gi gi-cards">
                <CreditCards total={cardTotal} cards={cards} anchored={anchored} />
              </div>
            ) : null}
          </div>
        </div>
      )}

      {/* Floating add button — sticky bottom-right, expands on hover. */}
      <button
        className="fab"
        onClick={() => setModal({ mode: "add" })}
        aria-label="Add transaction"
      >
        <span className="fab-plus" aria-hidden="true">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round">
            <path d="M12 5v14M5 12h14" />
          </svg>
        </span>
        <span className="fab-label">Add transaction</span>
      </button>
    </AppShell>
  );
}
