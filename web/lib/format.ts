const baht = new Intl.NumberFormat("en-US", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export function fmtBaht(n: number): string {
  return `฿${baht.format(n ?? 0)}`;
}

// Currency-aware: THB shows ฿, others show "1,234.00 USD".
export function fmtMoney(n: number, currency?: string | null): string {
  const cur = currency || "THB";
  if (cur === "THB") return `฿${baht.format(n ?? 0)}`;
  return `${baht.format(n ?? 0)} ${cur}`;
}

export function fmtDateTime(iso: string): string {
  const d = new Date(iso);
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Bangkok",
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(d);
}

export function monthKey(iso: string): string {
  const d = new Date(iso);
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Bangkok",
    year: "numeric",
    month: "short",
  }).format(d);
}

// Bangkok month key (YYYY-MM) and a display label, for the monthly chart.
export function bkkMonthKey(iso: string): string {
  const d = new Date(new Date(iso).getTime() + 7 * 3600 * 1000);
  return d.toISOString().slice(0, 7);
}

export function monthLabel(key: string): string {
  const [y, m] = key.split("-").map(Number);
  return new Intl.DateTimeFormat("en-GB", { month: "short", year: "numeric" }).format(
    new Date(Date.UTC(y, m - 1, 1)),
  );
}

export type RangeKey = "7d" | "30d" | "90d" | "mtd" | "all";

export function sinceForRange(range: RangeKey): Date | null {
  const now = new Date();
  switch (range) {
    case "7d":
      return new Date(now.getTime() - 7 * 864e5);
    case "30d":
      return new Date(now.getTime() - 30 * 864e5);
    case "90d":
      return new Date(now.getTime() - 90 * 864e5);
    case "mtd":
      return new Date(now.getFullYear(), now.getMonth(), 1);
    case "all":
    default:
      return null;
  }
}
