export type Category = { id: number; name: string };
export type Subcategory = { id: number; category_id: number; name: string };

export type Account = {
  key: string;
  label: string;
  method: "cash" | "bank" | "credit_card";
  bank: string | null;
  account_masked: string | null;
};

// A row from the `accounts` table (the real configured accounts).
export type DbAccount = {
  id: number;
  type: "bank" | "credit_card" | "cash";
  bank_name: string | null;
  masked_number: string | null;
  full_number: string | null;
  display_name: string | null;
  is_own: boolean;
};

export type CardStatement = {
  id: number;
  bank: string;
  card_masked: string;
  statement_date: string;
  closing_balance: number;
  previous_balance: number | null;
  min_payment: number | null;
  due_date: string | null;
};

export type Txn = {
  id: number;
  ts: string;
  amount: number;
  currency: string | null;
  thb_amount: number | null;
  direction: "debit" | "credit";
  method: string;
  bank: string | null;
  account_masked: string | null;
  counterparty_name: string | null;
  category_id: number | null;
  subcategory_id: number | null;
  source: string;
  is_internal: boolean;
  needs_review: boolean;
  notes: string | null;
};
