const baht = new Intl.NumberFormat("en-US", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export function fmtBaht(n: number): string {
  return `฿${baht.format(n ?? 0)}`;
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
