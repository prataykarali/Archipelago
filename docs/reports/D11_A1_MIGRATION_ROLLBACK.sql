-- Tested rollback for D11-A.1 (20261127000000_d11_a1_session_reason_and_eval_quota.sql)
-- Restores the prior D10-S6 session RPC and fixed 10/hour quota RPC without dropping historical session/quota events.

drop table if exists public.archipelago_runtime_quota_overrides;

alter table public.archipelago_runtime_sessions
    drop column if exists revoked_reason;

-- Re-apply functions from:
--   supabase/migrations/20261124000000_d10_s4_durable_sessions.sql
--   supabase/migrations/20261114030000_student_rolling_hour_quota.sql
