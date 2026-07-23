# MacroDroid — forward bank LINE notifications to Supabase

Goal: whenever LINE shows a notification from your KBANK or UOB chat, POST its
text into the Supabase `raw_events` table. MacroDroid queues and retries when
offline, so your phone doesn't need to be always on.

## One-time permissions

1. Install **MacroDroid** from the Play Store.
2. Grant it **Notification access** (it will prompt; Settings → Notifications →
   Notification access → enable MacroDroid).
3. **Important on Samsung:** Settings → Apps → MacroDroid → Battery →
   **Unrestricted**, so Samsung doesn't kill it in the background. Also in
   MacroDroid: Settings → keep the persistent notification enabled.

## Create the macro

**Trigger**
- Add trigger → **Notification → Notification Received**.
- Application: **LINE**.
- (Optional but recommended) set **Text content contains** to a keyword that
  only your bank alerts have, or leave broad and filter by the chat title.

**Action** — add an **HTTP Request**:
- Method: **POST**
- URL:
  ```
  https://YOUR-PROJECT.supabase.co/rest/v1/raw_events
  ```
- Headers:
  ```
  apikey: YOUR_SUPABASE_ANON_KEY
  Authorization: Bearer YOUR_SUPABASE_ANON_KEY
  Content-Type: application/json
  Prefer: return=minimal
  ```
- Body (Content type application/json). MacroDroid magic-text variables in
  braces are filled in from the notification:
  ```json
  {
    "source": "line",
    "payload": {
      "title": "{notification_title}",
      "text": "{notification_text}",
      "app": "LINE",
      "timestamp": "{trigger_time_stamp}"
    }
  }
  ```
  > MacroDroid's variable names differ slightly by version — use its magic-text
  > picker (the `{}` button) to insert **Notification Title**, **Notification
  > Text**, and a **timestamp** rather than typing them by hand.

**Constraints (optional)**
- Add a constraint so it only fires for the bank chats (e.g. notification title
  contains "KBANK" or "UOB"), to avoid forwarding every LINE message.

## Test

1. Save the macro and enable it.
2. Make a tiny transfer (or ask someone to send you one).
3. In Supabase → **Table editor → raw_events**, confirm a new row appears with
   your notification text in `payload`.
4. Run the GitHub Action (**Actions → process-transactions → Run workflow**) and
   confirm a row appears in `transactions`.

## Privacy

The anon key can only *insert* into `raw_events` (see SETUP.md RLS policy); it
cannot read your transactions. Keep the service_role key off the phone entirely.

## Later

In Phase 6 a small native Android app (`NotificationListenerService` +
`WebView`) replaces this MacroDroid macro and folds capture + dashboard into one
sideloaded `.apk`.
