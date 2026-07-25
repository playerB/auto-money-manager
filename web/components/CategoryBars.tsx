import { fmtBaht } from "@/lib/format";

export function CategoryBars({
  data,
}: {
  data: { name: string; amount: number }[];
}) {
  const max = Math.max(1, ...data.map((d) => d.amount));
  if (data.length === 0) {
    return <p style={{ color: "var(--muted)", fontSize: 13 }}>No spending in range.</p>;
  }
  return (
    <div>
      {data.map((d) => (
        <div className="hbar-row" key={d.name} title={`${d.name}: ${fmtBaht(d.amount)}`}>
          <div className="hbar-name">{d.name}</div>
          <div className="hbar-track">
            <div
              className="hbar-fill"
              style={{ width: `${Math.round((d.amount / max) * 100)}%` }}
            />
          </div>
          <div className="hbar-value">{fmtBaht(d.amount)}</div>
        </div>
      ))}
    </div>
  );
}
