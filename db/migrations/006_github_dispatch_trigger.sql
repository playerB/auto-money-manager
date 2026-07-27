-- Migration 006 — fire a GitHub repository_dispatch on new raw_events.
-- Run once in the Supabase SQL editor. Replace <YOUR_GITHUB_TOKEN> with a
-- classic PAT that has the `repo` scope.
--
-- Why a trigger instead of the Database Webhook UI: that UI always sends
-- Supabase's own change payload as the body and can't be customized, but
-- GitHub's dispatches endpoint requires the body to be {"event_type": "..."}.
-- Calling pg_net ourselves lets us control the body exactly.
--
-- After running this, DELETE/disable the Database Webhook you made in the UI so
-- it stops sending the failing (422) requests.

-- pg_net is already enabled on Supabase (the webhook feature uses it). If not:
--   create extension if not exists pg_net with schema extensions;

create or replace function public.notify_github_dispatch()
returns trigger
language plpgsql
security definer
as $$
begin
  perform net.http_post(
    url := 'https://api.github.com/repos/playerB/auto-money-manager/dispatches',
    body := jsonb_build_object('event_type', 'raw_event'),
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'Accept', 'application/vnd.github+json',
      'User-Agent', 'supabase-webhook',
      'Authorization', 'Bearer <YOUR_GITHUB_TOKEN>'
    )
  );
  return new;
end;
$$;

drop trigger if exists trg_notify_github on raw_events;
create trigger trg_notify_github
  after insert on raw_events
  for each row
  execute function public.notify_github_dispatch();
