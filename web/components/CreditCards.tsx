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
      <h2 className="section-title">Credit cards — charges (net) this period</h2>
      <div className="grid-tiles">
        <StatTile label="Total charged" value={fmtBaht(total)} />
        {cards.map((c) => (
          <StatTile key={c.label} label={c.label} value={fmtBaht(c.net)} />
        ))}
      </div>
      <p style={{ color: "var(--muted)", fontSize: 12, marginTop: 8 }}>
        Charges minus refunds/cancellations. Not yet reduced by bill payments —
        becomes true &ldquo;unpaid&rdquo; once card-payment slips are wired in.
      </p>
    </section>
  );
}
