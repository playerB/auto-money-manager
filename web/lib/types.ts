export type Category = { id: number; name: string };
export type Subcategory = { id: number; category_id: number; name: string };

export type Account = {
  key: string;
  label: string;
  method: "cash" | "bank" | "credit_card";
  bank: string | null;
  account_masked: string | null;
};

export type Txn = {
  id: number;
  ts: string;
  amount: number;
  currency: string | null;
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
