import { NextResponse } from "next/server";
import { getServiceClient } from "@/lib/supabase";

export const dynamic = "force-dynamic";

const BANKS = new Set(["uob", "kbank", "scb"]);
const BUCKET = process.env.STATEMENT_BUCKET || "statements";
const MAX_BYTES = 15 * 1024 * 1024; // 15 MB

// Upload a statement PDF -> Supabase Storage + a raw_events row. The DB trigger
// then dispatches the processor, which parses, reconciles, and anchors balances.
export async function POST(req: Request) {
  let form: FormData;
  try {
    form = await req.formData();
  } catch {
    return NextResponse.json({ error: "expected multipart form" }, { status: 400 });
  }

  const bank = String(form.get("bank") || "").toLowerCase();
  if (!BANKS.has(bank)) {
    return NextResponse.json({ error: "unknown bank" }, { status: 400 });
  }
  const file = form.get("file");
  if (!(file instanceof File) || file.size === 0) {
    return NextResponse.json({ error: "no file uploaded" }, { status: 400 });
  }
  if (file.size > MAX_BYTES) {
    return NextResponse.json({ error: "file too large (max 15 MB)" }, { status: 400 });
  }
  const name = file.name || "statement.pdf";
  if (!name.toLowerCase().endsWith(".pdf")) {
    return NextResponse.json({ error: "must be a PDF" }, { status: 400 });
  }

  const sb = getServiceClient();
  const safe = name.replace(/[^a-zA-Z0-9._-]/g, "_");
  const path = `${bank}/${Date.now()}-${safe}`;
  const bytes = Buffer.from(await file.arrayBuffer());

  const up = await sb.storage
    .from(BUCKET)
    .upload(path, bytes, { contentType: "application/pdf", upsert: false });
  if (up.error) {
    return NextResponse.json(
      { error: `storage upload failed: ${up.error.message}` },
      { status: 500 },
    );
  }

  const { error } = await sb.from("raw_events").insert({
    source: `statement-${bank}`,
    payload: { path, bank, filename: name },
  });
  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
  return NextResponse.json({ ok: true, path });
}

// Recent imports: statement anchors + the last few statement raw_events (status).
export async function GET() {
  const sb = getServiceClient();
  const [{ data: anchors }, { data: events }] = await Promise.all([
    sb
      .from("card_statements")
      .select("*")
      .order("statement_date", { ascending: false })
      .limit(24),
    sb
      .from("raw_events")
      .select("id, source, payload, received_at, processed, error")
      .like("source", "statement-%")
      .order("received_at", { ascending: false })
      .limit(12),
  ]);
  return NextResponse.json({ anchors: anchors ?? [], events: events ?? [] });
}
