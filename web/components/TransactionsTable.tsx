import { fmtMoney, fmtDateTime } from "@/lib/format";
import type { Txn } from "@/lib/types";

export function TransactionsTable({
  rows,
  categories,
}: {
  rows: Txn[];
  categories: Record<number, string>;
}) {
  if (rows.length === 0) {
    return <p style={{ color: "var(--muted)", fontSize: 13 }}>No transactions in range.</p>;
  }
  return (
    <div style={{ overflowX: "auto" }}>
      <table>
        <thead>
          <tr>
            <th>When</th>
            <th>Bank</th>
            <th>Counterparty</th>
            <th>Category</th>
            <th className="num">Amount</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((t) => {
            const isCredit = t.direction === "credit";
            const sign = isCredit ? "+" : "−";
            return (
              <tr key={t.id}>
                <td>{fmtDateTime(t.ts)}</td>
                <td>{t.bank ?? "—"}</td>
                <td>{t.counterparty_name ?? "—"}</td>
                <td>{t.category_id ? categories[t.category_id] ?? "—" : "—"}</td>
                <td className={`num ${isCredit ? "amt-credit" : "amt-debit"}`}>
                  {sign}
                  {fmtMoney(t.amount, t.currency)}
                </td>
                <td>
                  {t.is_internal ? <span className="badge">internal</span> : null}{" "}
                  {t.needs_review ? (
                    <span className="badge badge-review">review</span>
                  ) : null}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
