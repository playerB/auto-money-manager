# Auto Money Manager — Web (Next.js)

Custom dashboard for supawishkanok.com, replacing the Streamlit app. Reads the
same Supabase database server-side (service key never reaches the browser),
behind a password.

Nothing about the data pipeline changes — the GitHub Actions processor and
Supabase DB are untouched.

## Local dev

```bash
cd web
npm install
cp .env.local.example .env.local   # fill in the values
npm run dev                         # http://localhost:3000
```

## Environment variables

Set these in `.env.local` (local) and in Vercel → Project → Settings →
Environment Variables:

| Var | What |
|-----|------|
| `SUPABASE_URL` | your Supabase project URL |
| `SUPABASE_SERVICE_KEY` | service_role key (server-side only; never public) |
| `APP_PASSWORD` | the dashboard login password |
| `AUTH_SECRET` | random string to sign the session cookie |

Generate `AUTH_SECRET`:

```bash
node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"
```

## Deploy to Vercel

1. Push the repo to GitHub (the app lives in the `web/` subfolder).
2. On vercel.com → **Add New → Project** → import the repo.
3. **Root Directory: `web`** (important — the Next app isn't at the repo root).
   Framework preset auto-detects as Next.js.
4. Add the four environment variables above.
5. Deploy.

### Custom domain (supawishkanok.com)

In Vercel → Project → **Settings → Domains**, add `supawishkanok.com` (and/or
`app.supawishkanok.com`). Vercel shows the DNS records to set at your registrar:

- Apex `supawishkanok.com` → an **A record** to Vercel's IP (Vercel shows it),
  or use Vercel's nameservers.
- Subdomain `app.supawishkanok.com` → a **CNAME** to `cname.vercel-dns.com`.

HTTPS is provisioned automatically once DNS resolves.

## Security notes

- The service_role key is only used in server components / route handlers; it is
  never sent to the client.
- All routes except `/login` and `/api/login` are gated by `middleware.ts`, which
  checks a signed, HTTP-only session cookie.
- Because reads use the service key, the RLS lockdown (migration 002) stays in
  place — the anon key still can't read your data.

## What's here

- `app/page.tsx` — dashboard (metrics, filters, category + monthly charts, table)
- `app/login` + `app/api/login|logout` — password auth
- `middleware.ts` — route protection
- `lib/` — supabase client, auth, formatting, types
- `components/` — tiles, filters, charts (plain HTML/CSS bars), table

Charts use single-hue bars from the validated data-viz palette (light + dark via
CSS variables), so they stay colorblind-safe and theme automatically.
