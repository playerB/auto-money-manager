import { DashboardClient } from "@/components/DashboardClient";

// The page is a thin shell; data is fetched once client-side from /api/data and
// all filtering happens in memory (instant, no per-click server round-trips).
export default function Page() {
  return <DashboardClient />;
}
