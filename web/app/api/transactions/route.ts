import { NextResponse } from "next/server";
import { getServiceClient } from "@/lib/supabase";

export const dynamic = "force-dynamic";

const METHODS = new Set(["bank", "cash", "credit_card"]);
const CURRENCIES = new Set(["THB", "USD", "EUR", "CHF", "JPY", "CNY"]);

// Create a manual transaction (source='manual'). Protected by middleware.
export async function POST(req: Request) {
  let body: Record<string, unknown>;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid JSON" }, { status: 400 });
  }

  const amount = Number(body.amount);
  if (!Number.isFinite(amount) || amount <= 0) {
    return NextResponse.json({ error: "amount must be a positive number" }, { status: 400 });
  }
  const ts = typeof body.ts === "string" && body.ts ? body.ts : null;
  if (!ts || Number.isNaN(Date.parse(ts))) {
    return NextResponse.json({ error: "invalid date/time" }, { status: 400 });
  }

  const direction = body.direction === "credit" ? "credit" : "debit";
  const method = METHODS.has(String(body.method)) ? String(body.method) : "cash";
  const currency = CURRENCIES.has(String(body.currency)) ? String(body.currency) : "THB";

  const row = {
    ts,
    amount: Math.round(amount * 100) / 100,
    currency,
    direction,
    method,
    bank: body.bank ? String(body.bank) : null,
    account_masked: body.account_masked ? String(body.account_masked) : null,
    counterparty_name: body.counterparty_name ? String(body.counterparty_name) : null,
    category_id: body.category_id ? Number(body.category_id) : null,
    subcategory_id: body.subcategory_id ? Number(body.subcategory_id) : null,
    source: "manual",
    is_internal: false,
    needs_review: false,
    notes: body.note ? String(body.note) : null,
  };

  const sb = getServiceClient();
  const { error } = await sb.from("transactions").insert(row);
  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
  return NextResponse.json({ ok: true });
}
