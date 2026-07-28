import { NextResponse } from "next/server";
import { getServiceClient } from "@/lib/supabase";

export const dynamic = "force-dynamic";

const METHODS = new Set(["bank", "cash", "credit_card"]);
const CURRENCIES = new Set(["THB", "USD", "EUR", "CHF", "JPY", "CNY"]);

type ParseResult =
  | { row: Record<string, unknown>; error?: undefined }
  | { row?: undefined; error: string };

// Validate + normalize the shared transaction fields (used by create + update).
function parseTxnBody(body: Record<string, unknown>): ParseResult {
  const amount = Number(body.amount);
  if (!Number.isFinite(amount) || amount <= 0) {
    return { error: "amount must be a positive number" };
  }
  const ts = typeof body.ts === "string" && body.ts ? body.ts : null;
  if (!ts || Number.isNaN(Date.parse(ts))) {
    return { error: "invalid date/time" };
  }
  return {
    row: {
      ts,
      amount: Math.round(amount * 100) / 100,
      currency: CURRENCIES.has(String(body.currency)) ? String(body.currency) : "THB",
      direction: body.direction === "credit" ? "credit" : "debit",
      method: METHODS.has(String(body.method)) ? String(body.method) : "cash",
      bank: body.bank ? String(body.bank) : null,
      account_masked: body.account_masked ? String(body.account_masked) : null,
      counterparty_name: body.counterparty_name ? String(body.counterparty_name) : null,
      category_id: body.category_id ? Number(body.category_id) : null,
      subcategory_id: body.subcategory_id ? Number(body.subcategory_id) : null,
      notes: body.note ? String(body.note) : null,
    },
  };
}

// Create a manual transaction (source='manual').
export async function POST(req: Request) {
  let body: Record<string, unknown>;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid JSON" }, { status: 400 });
  }
  const parsed = parseTxnBody(body);
  if (parsed.error) return NextResponse.json({ error: parsed.error }, { status: 400 });

  const sb = getServiceClient();
  const { error } = await sb.from("transactions").insert({
    ...parsed.row,
    source: "manual",
    is_internal: false,
    needs_review: false,
  });
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ ok: true });
}

// Edit any existing transaction. Preserves source/is_internal/dedup_key; editing
// clears the needs_review flag (you've handled it).
export async function PATCH(req: Request) {
  let body: Record<string, unknown>;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid JSON" }, { status: 400 });
  }
  const id = Number(body.id);
  if (!id) return NextResponse.json({ error: "missing id" }, { status: 400 });
  const parsed = parseTxnBody(body);
  if (parsed.error) return NextResponse.json({ error: parsed.error }, { status: 400 });

  const sb = getServiceClient();
  const { error } = await sb
    .from("transactions")
    .update({ ...parsed.row, needs_review: false })
    .eq("id", id);
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ ok: true });
}

// Delete a transaction by id (?id=123).
export async function DELETE(req: Request) {
  const id = Number(new URL(req.url).searchParams.get("id"));
  if (!id) return NextResponse.json({ error: "missing id" }, { status: 400 });

  const sb = getServiceClient();
  const { error } = await sb.from("transactions").delete().eq("id", id);
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ ok: true });
}
