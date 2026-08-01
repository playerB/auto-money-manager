"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { fmtBaht } from "@/lib/format";

type Anchor = {
  id: number;
  bank: string;
  card_masked: string;
  statement_date: string;
  closing_balance: number;
  previous_balance: number | null;
  min_payment: number | null;
  due_date: string | null;
};

type Evt = {
  id: number;
  source: string;
  payload: { filename?: string; bank?: string } | null;
  received_at: string;
  processed: boolean;
  error: string | null;
};

const BANKS = [
  { key: "uob", label: "UOB credit card" },
  { key: "kbank", label: "KBANK bank" },
  { key: "scb", label: "SCB bank" },
];

export function StatementsClient() {
  const [bank, setBank] = useState("uob");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [anchors, setAnchors] = useState<Anchor[]>([]);
  const [events, setEvents] = useState<Evt[]>([]);
  const fileRef = useRef<HTMLInputElement>(null);

  async function loadRecent() {
    const res = await fetch("/api/statements", { cache: "no-store" });
    if (res.ok) {
      const j = await res.json();
      setAnchors(j.anchors ?? []);
      setEvents(j.events ?? []);
    }
  }

  useEffect(() => {
    loadRecent();
  }, []);

  async function upload() {
    const file = fileRef.current?.files?.[0];
    if (!file) {
      setMsg({ ok: false, text: "Choose a PDF first." });
      return;
    }
    setBusy(true);
    setMsg(null);
    try {
      const fd = new FormData();
      fd.append("bank", bank);
      fd.append("file", file);
      const res = await fetch("/api/statements", { method: "POST", body: fd });
      const j = await res.json().catch(() => ({}));
      if (res.ok) {
        setMsg({
          ok: true,
          text: "Uploaded. Processing runs in the background — refresh in a minute to see results.",
        });
        if (fileRef.current) fileRef.current.value = "";
        setTimeout(loadRecent, 1500);
      } else {
        setMsg({ ok: false, text: j.error || "Upload failed" });
      }
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : "Upload failed" });
    } finally {
      setBusy(false);
    }
  }

  // Latest anchor per card (list is already newest-first).
  const latest = new Map<string, Anchor>();
  for (const a of anchors) {
    const k = `${a.bank} ••${a.card_masked}`;
    if (!latest.has(k)) latest.set(k, a);
  }

  return (
    <div className="container">
      <div className="topbar">
        <h1>📄 Statements</h1>
        <Link className="btn" href="/">
          ← Dashboard
        </Link>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <h2 className="section-title">Upload a statement PDF</h2>
        <div className="field">
          <label>Bank / source</label>
          <select value={bank} onChange={(e) => setBank(e.target.value)}>
            {BANKS.map((b) => (
              <option key={b.key} value={b.key}>
                {b.label}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>PDF file</label>
          <input ref={fileRef} type="file" accept="application/pdf" />
        </div>
        <div className="modal-actions">
          <button
            className="btn"
            onClick={upload}
            disabled={busy}
            style={{ background: "var(--series-1)", color: "#fff", borderColor: "var(--series-1)" }}
          >
            {busy ? "Uploading…" : "Upload"}
          </button>
          <button className="btn" onClick={loadRecent} disabled={busy}>
            ↻ Refresh
          </button>
        </div>
        {msg ? (
          <p style={{ color: msg.ok ? "var(--good)" : "var(--critical)", fontSize: 13 }}>
            {msg.text}
          </p>
        ) : (
          <p style={{ color: "var(--muted)", fontSize: 12 }}>
            One PDF per upload. UOB monthly statements cover all cards; KBANK/SCB
            are per-account. Encrypted PDFs are opened with the password stored in
            the processor&apos;s secrets.
          </p>
        )}
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <h2 className="section-title">Card balance anchors (from statements)</h2>
        {latest.size === 0 ? (
          <p style={{ color: "var(--muted)", fontSize: 13 }}>
            No statement anchors yet.
          </p>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table>
              <thead>
                <tr>
                  <th>Card</th>
                  <th>Statement date</th>
                  <th className="num">Closing balance</th>
                  <th className="num">Min payment</th>
                  <th>Due date</th>
                </tr>
              </thead>
              <tbody>
                {[...latest.values()].map((a) => (
                  <tr key={a.id}>
                    <td>
                      {a.bank} ••{a.card_masked}
                    </td>
                    <td>{a.statement_date}</td>
                    <td className="num">{fmtBaht(Number(a.closing_balance))}</td>
                    <td className="num">
                      {a.min_payment != null ? fmtBaht(Number(a.min_payment)) : "—"}
                    </td>
                    <td>{a.due_date ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="card">
        <h2 className="section-title">Recent uploads</h2>
        {events.length === 0 ? (
          <p style={{ color: "var(--muted)", fontSize: 13 }}>Nothing uploaded yet.</p>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table>
              <thead>
                <tr>
                  <th>When</th>
                  <th>Source</th>
                  <th>File</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {events.map((e) => (
                  <tr key={e.id}>
                    <td>{new Date(e.received_at).toLocaleString("en-GB")}</td>
                    <td>{e.source}</td>
                    <td>{e.payload?.filename ?? "—"}</td>
                    <td>
                      {e.error ? (
                        <span className="badge badge-review">{e.error.slice(0, 60)}</span>
                      ) : e.processed ? (
                        <span className="badge">done</span>
                      ) : (
                        <span className="badge">pending…</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
