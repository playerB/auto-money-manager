import { getServiceClient } from "@/lib/supabase";
import { fmtBaht, sinceForRange, type RangeKey } from "@/lib/format";
import type { Txn } from "@/lib/types";
import { StatTile } from "@/components/StatTile";
import { Filters } from "@/components/Filters";
import { CategoryBars } from "@/components/CategoryBars";
import { MonthlyBars } from "@/components/MonthlyBars";
import { TransactionsTable } from "@/components/TransactionsTable";

export const dynamic = "force-dynamic";

function bkkMonthKey(iso: string): string {
  // Shift to Bangkok (+7h) then take YYYY-MM.
  const d = new Date(new Date(iso).getTime() + 7 * 3600 * 1000);
  return d.toISOString().slice(0, 7);
}

function monthLabel(key: string): string {
  const [y, m] = key.split("-").map(Number);
  return new Intl.DateTimeFormat("en-GB", { month: "short", year: "numeric" }).format(
    new Date(Date.UTC(y, m - 1, 1)),
  );
}

export default async function Dashboard({
  searchParams,
}: {
  searchParams: { range?: string; bank?: string };
}) {
  const range = (searchParams.range as RangeKey) || "30d";
  const bank = searchParams.bank || "all";
  const since = sinceForRange(range);

  const sb = getServiceClient();

  let q = sb
    .from("transactions")
    .select("*")
    .order("ts", { ascending: false })
    .limit(3000);
  if (since) q = q.gte("ts", since.toISOString());
  if (bank !== "all") q = q.eq("bank", bank);

  const [{ data: txnData }, { data: catData }, { data: bankData }] = await Promise.all([
    q,
    sb.from("categories").select("id,name"),
    sb.from("transactions").select("bank"),
  ]);

  const txns = (txnData || []) as Txn[];
  const categories: Record<number, string> = {};
  for (const c of catData || []) categories[c.id] = c.name;
  const banks = Array.from(
    new Set((bankData || []).map((r: { bank: string | null }) => r.bank).filter(Boolean)),
  ).sort() as string[];

  // Spending/income exclude internal transfers.
  const external = txns.filter((t) => !t.is_internal);
  const spend = external
    .filter((t) => t.direction === "debit")
    .reduce((s, t) => s + Number(t.amount), 0);
  const income = external
    .filter((t) => t.direction === "credit")
    .reduce((s, t) => s + Number(t.amount), 0);
  const reviewCount = txns.filter((t) => t.needs_review).length;

  // Spending by category (debits, external).
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

  // Monthly spending (debits, external), chronological.
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

  return (
    <div className="container">
      <div className="topbar">
        <h1>💸 Money Manager</h1>
        <form method="post" action="/api/logout">
          <button className="btn" type="submit">
            Sign out
          </button>
        </form>
      </div>

      <Filters range={range} bank={bank} banks={banks} />

      <div className="grid-tiles">
        <StatTile label="Spending" value={fmtBaht(spend)} />
        <StatTile label="Income" value={fmtBaht(income)} />
        <StatTile label="Transactions" value={String(txns.length)} />
        <StatTile label="Needs review" value={String(reviewCount)} />
      </div>

      <div className="grid-two">
        <div className="card">
          <h2 className="section-title">Spending by category</h2>
          <CategoryBars data={byCategory} />
        </div>
        <div className="card">
          <h2 className="section-title">Monthly spending</h2>
          <MonthlyBars data={monthly} />
        </div>
      </div>

      <div className="card">
        <h2 className="section-title">Transactions</h2>
        <TransactionsTable rows={txns} categories={categories} />
      </div>
    </div>
  );
}
