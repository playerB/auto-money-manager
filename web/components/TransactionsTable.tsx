import { fmtMoney, fmtDateTime } from "@/lib/format";
import type { Txn } from "@/lib/types";

function PencilIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 20h9" />
      <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4Z" />
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 6h18" />
      <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
      <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
    </svg>
  );
}

export function TransactionsTable({
  rows,
  categories,
  onEdit,
  onDelete,
}: {
  rows: Txn[];
  categories: Record<number, string>;
  onEdit?: (t: Txn) => void;
  onDelete?: (t: Txn) => void;
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
                <td>
                  <div className="actions-cell">
                    <button
                      className="icon-btn"
                      title="Edit"
                      aria-label="Edit"
                      onClick={() => onEdit?.(t)}
                    >
                      <PencilIcon />
                    </button>
                    <button
                      className="icon-btn danger"
                      title="Delete"
                      aria-label="Delete"
                      onClick={() => onDelete?.(t)}
                    >
                      <TrashIcon />
                    </button>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
