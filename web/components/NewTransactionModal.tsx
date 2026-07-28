"use client";

import { useMemo, useState } from "react";
import type { Account, Category, Subcategory, Txn } from "@/lib/types";

const CURRENCIES = ["THB", "USD", "EUR", "CHF", "JPY", "CNY"];

function nowDateInput(): string {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}
function nowTimeInput(): string {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, "0");
  return `${p(d.getHours())}:${p(d.getMinutes())}`;
}

// Split a stored UTC ISO timestamp into Bangkok wall-clock date + time.
function bkkParts(iso: string): { date: string; time: string } {
  const s = new Date(new Date(iso).getTime() + 7 * 3600 * 1000).toISOString();
  return { date: s.slice(0, 10), time: s.slice(11, 16) };
}

function accountKeyFor(t: Txn, accounts: Account[]): string {
  if (t.method === "cash") return "cash";
  const key = `${t.method}|${t.bank ?? ""}|${t.account_masked ?? ""}`;
  return accounts.some((a) => a.key === key) ? key : accounts[0]?.key ?? "cash";
}

export function TransactionModal({
  accounts,
  categories,
  subcategories,
  editing,
  onClose,
  onSaved,
}: {
  accounts: Account[];
  categories: Category[];
  subcategories: Subcategory[];
  editing?: Txn | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const init = editing ? bkkParts(editing.ts) : null;

  const [dateVal, setDateVal] = useState(init?.date ?? nowDateInput());
  const [timeVal, setTimeVal] = useState(init?.time ?? nowTimeInput());
  const [accountKey, setAccountKey] = useState(
    editing ? accountKeyFor(editing, accounts) : accounts[0]?.key ?? "cash",
  );
  const [amount, setAmount] = useState(editing ? String(editing.amount) : "");
  const [currency, setCurrency] = useState(editing?.currency ?? "THB");
  const [direction, setDirection] = useState<"debit" | "credit">(
    editing?.direction ?? "debit",
  );
  const [counterparty, setCounterparty] = useState(editing?.counterparty_name ?? "");
  const [categoryId, setCategoryId] = useState(
    editing?.category_id ? String(editing.category_id) : "",
  );
  const [subcategoryId, setSubcategoryId] = useState(
    editing?.subcategory_id ? String(editing.subcategory_id) : "",
  );
  const [note, setNote] = useState(editing?.notes ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const subOptions = useMemo(
    () => subcategories.filter((s) => String(s.category_id) === categoryId),
    [subcategories, categoryId],
  );

  async function save() {
    setError(null);
    const amt = Number(amount);
    if (!Number.isFinite(amt) || amt <= 0) {
      setError("Enter a valid amount.");
      return;
    }
    if (!dateVal || !timeVal) {
      setError("Enter a valid date and time.");
      return;
    }
    const acct = accounts.find((a) => a.key === accountKey);
    const ts = `${dateVal}T${timeVal}:00+07:00`; // entered time is Bangkok

    setSaving(true);
    try {
      const res = await fetch("/api/transactions", {
        method: editing ? "PATCH" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...(editing ? { id: editing.id } : {}),
          ts,
          amount: amt,
          currency,
          direction,
          method: acct?.method ?? "cash",
          bank: acct?.bank ?? null,
          account_masked: acct?.account_masked ?? null,
          counterparty_name: counterparty.trim() || null,
          category_id: categoryId || null,
          subcategory_id: subcategoryId || null,
          note: note.trim() || null,
        }),
      });
      const j = await res.json();
      if (!res.ok) throw new Error(j.error || `Save failed (${res.status})`);
      onSaved();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2 style={{ marginTop: 0, fontSize: 18 }}>
          {editing ? "Edit transaction" : "Add transaction"}
        </h2>

        <div className="row2-eq">
          <div className="field">
            <label>Date</label>
            <input
              type="date"
              lang="en-GB"
              value={dateVal}
              onChange={(e) => setDateVal(e.target.value)}
              min="2000-01-01"
              max="2100-12-31"
            />
          </div>
          <div className="field">
            <label>Time (24h)</label>
            <input
              type="time"
              lang="en-GB"
              step={60}
              value={timeVal}
              onChange={(e) => setTimeVal(e.target.value)}
            />
          </div>
        </div>

        <div className="field">
          <label>Account</label>
          <select value={accountKey} onChange={(e) => setAccountKey(e.target.value)}>
            {accounts.map((a) => (
              <option key={a.key} value={a.key}>
                {a.label}
              </option>
            ))}
          </select>
        </div>

        <div className="field">
          <label>Amount</label>
          <div className="row2">
            <input
              type="number"
              inputMode="decimal"
              step="0.01"
              min="0"
              placeholder="0.00"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
            />
            <select value={currency} onChange={(e) => setCurrency(e.target.value)}>
              {CURRENCIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="field">
          <label>Direction</label>
          <div className="toggle">
            <button
              type="button"
              data-active={direction === "debit"}
              onClick={() => setDirection("debit")}
            >
              Debit (out)
            </button>
            <button
              type="button"
              data-active={direction === "credit"}
              onClick={() => setDirection("credit")}
            >
              Credit (in)
            </button>
          </div>
        </div>

        <div className="field">
          <label>Counterparty</label>
          <input
            type="text"
            placeholder="Who / where"
            value={counterparty}
            onChange={(e) => setCounterparty(e.target.value)}
          />
        </div>

        <div className="field">
          <label>Category</label>
          <select
            value={categoryId}
            onChange={(e) => {
              setCategoryId(e.target.value);
              setSubcategoryId("");
            }}
          >
            <option value="">— none —</option>
            {categories.map((c) => (
              <option key={c.id} value={String(c.id)}>
                {c.name}
              </option>
            ))}
          </select>
        </div>

        {subOptions.length > 0 ? (
          <div className="field">
            <label>Subcategory</label>
            <select value={subcategoryId} onChange={(e) => setSubcategoryId(e.target.value)}>
              <option value="">— none —</option>
              {subOptions.map((s) => (
                <option key={s.id} value={String(s.id)}>
                  {s.name}
                </option>
              ))}
            </select>
          </div>
        ) : null}

        <div className="field">
          <label>Note</label>
          <input
            type="text"
            placeholder="Optional short note"
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
        </div>

        {error ? (
          <div className="error" style={{ marginBottom: 8 }}>
            {error}
          </div>
        ) : null}

        <div className="modal-actions">
          <button className="btn" onClick={onClose} disabled={saving}>
            Cancel
          </button>
          <button
            className="btn"
            onClick={save}
            disabled={saving}
            style={{ background: "var(--series-1)", color: "#fff", borderColor: "var(--series-1)" }}
          >
            {saving ? "Saving…" : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}
