import { fmtBaht } from "@/lib/format";
import { StatTile } from "@/components/StatTile";

export function CreditCards({
  total,
  cards,
  anchored,
}: {
  total: number;
  cards: { label: string; net: number }[];
  anchored?: boolean;
}) {
  return (
    <section style={{ marginBottom: 16 }}>
      <h2 className="section-title">
        Credit cards — {anchored ? "outstanding balance" : "balance (since tracking)"}
      </h2>
      <div className="grid-tiles">
        <StatTile label="Total balance" value={fmtBaht(total)} />
        {cards.map((c) => (
          <StatTile key={c.label} label={c.label} value={fmtBaht(c.net)} />
        ))}
      </div>
      <p style={{ color: "var(--muted)", fontSize: 12, marginTop: 8 }}>
        {anchored
          ? "Anchored to each card’s latest statement closing balance, plus charges minus refunds and bill payments since that statement — i.e. the true outstanding. Upload newer statements to re-anchor."
          : "Charges minus refunds and bill payments, all-time. Not anchored to a starting balance yet, so it reflects movement since tracking began — upload a statement to anchor it to the true outstanding."}
      </p>
    </section>
  );
}
