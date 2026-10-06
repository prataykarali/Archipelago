-- Physical reciprocal-library cards are entered and handled only by librarians.
-- No browser role can read card IDs or borrower details through the Data API.

create table public.external_membership_cards (
  id uuid primary key default gen_random_uuid(),
  provider text not null check (provider in ('british_council', 'american_library')),
  card_label text not null check (char_length(card_label) between 1 and 80),
  condition text not null default 'usable'
    check (condition in ('usable', 'lost', 'retired')),
  created_by uuid not null references auth.users(id),
  updated_by uuid not null references auth.users(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (provider, card_label)
);

create table public.external_membership_loans (
  id uuid primary key default gen_random_uuid(),
  card_id uuid not null references public.external_membership_cards(id),
  borrower_id uuid not null references auth.users(id),
  checked_out_at timestamptz not null default now(),
  due_at timestamptz not null,
  returned_at timestamptz,
  issued_by uuid not null references auth.users(id),
  returned_by uuid references auth.users(id),
  check (due_at > checked_out_at),
  check (returned_at is null or returned_at >= checked_out_at),
  check ((returned_at is null) = (returned_by is null))
);

-- Physical availability is derived: usable cards without an active loan.
-- This index is the concurrency guard against double checkout.
create unique index external_membership_one_active_loan_per_card
  on public.external_membership_loans (card_id)
  where returned_at is null;

create index external_membership_loans_due_idx
  on public.external_membership_loans (due_at)
  where returned_at is null;

create table public.external_membership_events (
  id bigint generated always as identity primary key,
  card_id uuid not null references public.external_membership_cards(id),
  loan_id uuid references public.external_membership_loans(id),
  event_type text not null
    check (event_type in ('card_added', 'card_condition_changed', 'checked_out', 'returned')),
  actor_id uuid not null references auth.users(id),
  occurred_at timestamptz not null default now(),
  detail jsonb not null default '{}'::jsonb
);

create index external_membership_events_card_time_idx
  on public.external_membership_events (card_id, occurred_at desc);

create function private.membership_card_audit()
returns trigger
language plpgsql
set search_path = public, pg_temp
as $$
begin
  if tg_table_name = 'external_membership_cards' then
    if tg_op = 'INSERT' then
      insert into public.external_membership_events
        (card_id, event_type, actor_id)
      values (new.id, 'card_added', new.created_by);
    elsif new.condition is distinct from old.condition then
      insert into public.external_membership_events
        (card_id, event_type, actor_id, detail)
      values (
        new.id, 'card_condition_changed', new.updated_by,
        jsonb_build_object('from', old.condition, 'to', new.condition)
      );
    end if;
  elsif tg_op = 'INSERT' then
    insert into public.external_membership_events
      (card_id, loan_id, event_type, actor_id)
    values (new.card_id, new.id, 'checked_out', new.issued_by);
  elsif old.returned_at is null and new.returned_at is not null then
    insert into public.external_membership_events
      (card_id, loan_id, event_type, actor_id)
    values (new.card_id, new.id, 'returned', new.returned_by);
  end if;
  return new;
end;
$$;

create function private.membership_loan_update_guard()
returns trigger
language plpgsql
set search_path = public, pg_temp
as $$
begin
  if old.returned_at is not null
     or new.card_id is distinct from old.card_id
     or new.borrower_id is distinct from old.borrower_id
     or new.issued_by is distinct from old.issued_by
     or new.checked_out_at is distinct from old.checked_out_at
     or new.due_at is distinct from old.due_at
     or new.returned_at is null then
    raise exception 'Only an active loan can be returned'
      using errcode = '23514';
  end if;
  return new;
end;
$$;

create function private.membership_card_checkout_guard()
returns trigger
language plpgsql
set search_path = public, pg_temp
as $$
declare
  card_condition text;
begin
  select condition into card_condition
    from public.external_membership_cards
    where id = new.card_id
    for update;
  if card_condition is distinct from 'usable' then
    raise exception 'Membership card is unavailable for checkout'
      using errcode = '23514';
  end if;
  return new;
end;
$$;

create trigger external_membership_card_added_or_changed
  after insert or update of condition on public.external_membership_cards
  for each row execute function private.membership_card_audit();

create trigger external_membership_loan_guard
  before insert on public.external_membership_loans
  for each row execute function private.membership_card_checkout_guard();

create trigger external_membership_loan_return_guard
  before update on public.external_membership_loans
  for each row execute function private.membership_loan_update_guard();

create trigger external_membership_loan_changed
  after insert or update of returned_at on public.external_membership_loans
  for each row execute function private.membership_card_audit();

alter table public.external_membership_cards enable row level security;
alter table public.external_membership_loans enable row level security;
alter table public.external_membership_events enable row level security;

revoke all on public.external_membership_cards from anon, authenticated;
revoke all on public.external_membership_loans from anon, authenticated;
revoke all on public.external_membership_events from anon, authenticated;
grant select, insert, update on public.external_membership_cards to service_role;
grant select, insert, update on public.external_membership_loans to service_role;
grant select, insert on public.external_membership_events to service_role;
grant usage, select on sequence public.external_membership_events_id_seq to service_role;

revoke all on function private.membership_card_audit() from public;
revoke all on function private.membership_card_checkout_guard() from public;
revoke all on function private.membership_loan_update_guard() from public;
