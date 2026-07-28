import { NextResponse } from "next/server";
import { getServiceClient } from "@/lib/supabase";

// Fresh data on every call (initial load + Refresh). Protected by middleware —
// the browser sends the session cookie automatically (same-origin).
export const dynamic = "force-dynamic";

export async function GET() {
  const sb = getServiceClient();
  const [{ data: transactions }, { data: categories }, { data: subcategories }] =
    await Promise.all([
      sb.from("transactions").select("*").order("ts", { ascending: false }).limit(5000),
      sb.from("categories").select("id,name").order("name"),
      sb.from("subcategories").select("id,category_id,name").order("name"),
    ]);
  return NextResponse.json(
    {
      transactions: transactions ?? [],
      categories: categories ?? [],
      subcategories: subcategories ?? [],
    },
    { headers: { "Cache-Control": "no-store" } },
  );
}
