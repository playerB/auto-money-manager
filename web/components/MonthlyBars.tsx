import { fmtBaht } from "@/lib/format";

export function MonthlyBars({
  data,
}: {
  data: { month: string; amount: number }[];
}) {
  const max = Math.max(1, ...data.map((d) => d.amount));
  if (data.length === 0) {
    return <p style={{ color: "var(--muted)", fontSize: 13 }}>No spending in range.</p>;
  }
  return (
    <div className="vbars">
      {data.map((d) => (
        <div className="vbar-col" key={d.month} title={`${d.month}: ${fmtBaht(d.amount)}`}>
          <div
            className="vbar-fill"
            style={{ height: `${Math.round((d.amount / max) * 100)}%` }}
          />
          <div className="vbar-label">{d.month}</div>
        </div>
      ))}
    </div>
  );
}
