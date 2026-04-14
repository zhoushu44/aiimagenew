-- User points balances and atomic award helpers
create table if not exists public.user_points_balances (
  user_id uuid primary key references auth.users (id) on delete cascade,
  balance integer not null default 0,
  total_earned integer not null default 0,
  total_spent integer not null default 0,
  signup_bonus_awarded_at timestamptz,
  last_daily_claim_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint user_points_balances_balance_nonnegative check (balance >= 0),
  constraint user_points_balances_total_earned_nonnegative check (total_earned >= 0),
  constraint user_points_balances_total_spent_nonnegative check (total_spent >= 0)
);

create index if not exists user_points_balances_created_at_idx on public.user_points_balances (created_at);

create or replace function public.set_user_points_balances_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists user_points_balances_updated_at on public.user_points_balances;
create trigger user_points_balances_updated_at
before update on public.user_points_balances
for each row
execute function public.set_user_points_balances_updated_at();

alter table public.user_points_balances enable row level security;

drop policy if exists "user_points_balances service role full access" on public.user_points_balances;
create policy "user_points_balances service role full access"
on public.user_points_balances
for all
to service_role
using (true)
with check (true);

create or replace function public.ensure_user_points_balance(p_user_id uuid)
returns public.user_points_balances
language plpgsql
security definer
set search_path = public
as $$
declare
  v_row public.user_points_balances;
begin
  if p_user_id is null then
    raise exception 'user_id 不能为空';
  end if;

  insert into public.user_points_balances (user_id)
  values (p_user_id)
  on conflict (user_id) do nothing;

  select * into v_row
  from public.user_points_balances
  where user_id = p_user_id;

  return v_row;
end;
$$;

create or replace function public.award_signup_bonus_points(p_user_id uuid, p_amount integer)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_row public.user_points_balances;
begin
  if p_user_id is null then
    raise exception 'user_id 不能为空';
  end if;
  if p_amount is null or p_amount < 0 then
    raise exception 'amount 不能为空';
  end if;

  perform public.ensure_user_points_balance(p_user_id);

  update public.user_points_balances
  set balance = balance + p_amount,
      total_earned = total_earned + p_amount,
      signup_bonus_awarded_at = coalesce(signup_bonus_awarded_at, now())
  where user_id = p_user_id
    and signup_bonus_awarded_at is null
  returning * into v_row;

  if found then
    return jsonb_build_object(
      'success', true,
      'awarded', true,
      'balance_row', to_jsonb(v_row)
    );
  end if;

  select * into v_row
  from public.user_points_balances
  where user_id = p_user_id;

  return jsonb_build_object(
    'success', true,
    'awarded', false,
    'balance_row', to_jsonb(v_row)
  );
end;
$$;

create or replace function public.claim_daily_free_points(p_user_id uuid, p_amount integer)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_row public.user_points_balances;
begin
  if p_user_id is null then
    raise exception 'user_id 不能为空';
  end if;
  if p_amount is null or p_amount < 0 then
    raise exception 'amount 不能为空';
  end if;

  perform public.ensure_user_points_balance(p_user_id);

  update public.user_points_balances
  set balance = balance + p_amount,
      total_earned = total_earned + p_amount,
      last_daily_claim_at = now()
  where user_id = p_user_id
    and (
      last_daily_claim_at is null
      or timezone('UTC', last_daily_claim_at)::date < timezone('UTC', now())::date
    )
  returning * into v_row;

  if found then
    return jsonb_build_object(
      'success', true,
      'claimed', true,
      'balance_row', to_jsonb(v_row)
    );
  end if;

  select * into v_row
  from public.user_points_balances
  where user_id = p_user_id;

  return jsonb_build_object(
    'success', true,
    'claimed', false,
    'reason', 'already_claimed_today',
    'balance_row', to_jsonb(v_row)
  );
end;
$$;

create or replace function public.spend_user_points(p_user_id uuid, p_amount integer)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_row public.user_points_balances;
begin
  if p_user_id is null then
    raise exception 'user_id 不能为空';
  end if;
  if p_amount is null or p_amount < 0 then
    raise exception 'amount 不能为空';
  end if;

  perform public.ensure_user_points_balance(p_user_id);

  update public.user_points_balances
  set balance = balance - p_amount,
      total_spent = total_spent + p_amount
  where user_id = p_user_id
    and balance >= p_amount
  returning * into v_row;

  if found then
    return jsonb_build_object(
      'success', true,
      'spent', true,
      'balance_row', to_jsonb(v_row)
    );
  end if;

  raise exception '积分余额不足';
end;
$$;
