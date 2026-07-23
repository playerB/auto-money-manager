# MacroDroid — upload transfer slips to Supabase Storage

Goal: when a bank app saves a slip image into its folder (e.g. `K PLUS` for
KBANK), MacroDroid uploads that image to Supabase Storage and inserts a
`raw_events` row. The processor then OCRs it and records the transfer.

Build one macro per slip folder so the bank is known from the folder.

## One-time setup (Supabase)

Run `db/migrations/003_slips_storage.sql` in the SQL editor. It creates a private
`slips` bucket and lets the anon key upload (but not read) it.

## The macro

**Trigger** → **File Changed** (the trigger you found):
- Folder: your bank's slip folder, e.g. `.../Pictures/K PLUS` (KBANK).
- Operation: **Created**.
- This exposes the new file's path/name as a magic-text variable — note its
  exact name in your MacroDroid (often something like `{file_path}` /
  `{file_name}`); use the magic-text picker rather than typing it.

**Action 1 — HTTP Request (upload the image):**
- Method: **POST**
- URL (use the file *name* magic text as the object path):
  ```
  https://YOUR-PROJECT.supabase.co/storage/v1/object/slips/{file_name}
  ```
- Headers:
  ```
  apikey: YOUR_SUPABASE_ANON_KEY
  Authorization: Bearer YOUR_SUPABASE_ANON_KEY
  Content-Type: image/jpeg
  ```
- Body: choose **File / Upload file** and point it at the changed file
  (the trigger's file-path magic text). This sends the raw image bytes.

**Action 2 — HTTP Request (register the event):**
- Method: **POST**
- URL: `https://YOUR-PROJECT.supabase.co/rest/v1/raw_events`
- Headers:
  ```
  apikey: YOUR_SUPABASE_ANON_KEY
  Authorization: Bearer YOUR_SUPABASE_ANON_KEY
  Content-Type: application/json
  Prefer: return=minimal
  ```
- Body (set `bank` to this folder's bank; `path` = the same file name you
  uploaded to):
  ```json
  {"source":"slip","payload":{"path":"{file_name}","bank":"KBANK"}}
  ```

**Constraint (recommended):** only fire for image files — add a constraint that
the file name ends with `.jpg`/`.png`, so non-image files in the folder are
ignored.

## Owner name (for internal-transfer detection)

Add a GitHub Actions secret `OWNER_NAMES` = your full name(s) as printed on
slips, comma-separated, Thai and/or English. Give the fullest form you have —
the matcher tolerates redaction/abbreviation (`ก` / `ก.` / `ก***` / `KANO`):

```
OWNER_NAMES=นาย ศุภวิชญ์ กนกพงศกร,SUPAWISH KANOKPONGSAKORN
```

A transfer is marked internal only when **both** sender and recipient match you
(so a transfer to a friend with a similar first name is not misread). When it's
internal, it's excluded from spending/income and the matching recipient-side
credit alert is flagged internal too. If both names are heavily redacted, it's
still marked internal but flagged `needs_review` so you can confirm.

## Test

1. Save a slip in the bank app (or copy an image into the watched folder).
2. Supabase → Storage → `slips`: confirm the image appears.
3. Supabase → Table editor → `raw_events`: confirm a `source='slip'` row.
4. Run the processor (Actions → Run workflow) and check `transactions` for the
   recorded transfer (internal transfers show `is_internal = true`).

## Notes

- The processor uses Tesseract (Thai+English), which reads amount/fee/names/
  banks/account last-4 reliably. Reference numbers and occasionally dates are
  unreliable, so dedup uses amount+time and the date falls back to upload time.
- A slip for an own→own transfer produces a debit on the sender bank and marks
  the matching credit internal — both are excluded from spending/income.
