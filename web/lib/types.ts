export type Txn = {
  id: number;
  ts: string;
  amount: number;
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
