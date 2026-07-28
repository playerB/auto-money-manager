import { fmtBaht } from "@/lib/format";
import { StatTile } from "@/components/StatTile";

export function CreditCards({
  total,
  cards,
}: {
  total: number;
  cards: { label: string; net: number }[];
}) {
  return (
    <section style={{ marginBottom: 16 }}>
      <h2 className="section-title">Credit cards — balance (since tracking)</h2>
      <div className="grid-tiles">
        <StatTile label="Total balance" value={fmtBaht(total)} />
        {cards.map((c) => (
          <StatTile key={c.label} label={c.label} value={fmtBaht(c.net)} />
        ))}
      </div>
      <p style={{ color: "var(--muted)", fontSize: 12, marginTop: 8 }}>
        Charges minus refunds and bill payments, all-time. Not anchored to a
        starting balance yet, so it reflects movement since tracking began — it
        becomes the true outstanding once each card&rsquo;s opening balance is set.
      </p>
    </section>
  );
}
