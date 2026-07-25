import Link from "next/link";
import type { RangeKey } from "@/lib/format";

const RANGES: { key: RangeKey; label: string }[] = [
  { key: "7d", label: "7 days" },
  { key: "30d", label: "30 days" },
  { key: "90d", label: "90 days" },
  { key: "mtd", label: "This month" },
  { key: "all", label: "All" },
];

function href(range: string, bank: string): string {
  const p = new URLSearchParams();
  p.set("range", range);
  if (bank && bank !== "all") p.set("bank", bank);
  return `/?${p.toString()}`;
}

export function Filters({
  range,
  bank,
  banks,
}: {
  range: string;
  bank: string;
  banks: string[];
}) {
  return (
    <div className="filters">
      {RANGES.map((r) => (
        <Link
          key={r.key}
          className="chip"
          data-active={range === r.key}
          href={href(r.key, bank)}
        >
          {r.label}
        </Link>
      ))}
      <span style={{ width: 12 }} />
      <Link className="chip" data-active={bank === "all"} href={href(range, "all")}>
        All banks
      </Link>
      {banks.map((b) => (
        <Link key={b} className="chip" data-active={bank === b} href={href(range, b)}>
          {b}
        </Link>
      ))}
    </div>
  );
}
