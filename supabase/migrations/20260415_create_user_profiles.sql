-- User admin flags for settings access
create table if not exists public.user_profiles (
  user_id uuid primary key references auth.users (id) on delete cascade,
  is_admin boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists user_profiles_is_admin_idx on public.user_profiles (is_admin);

create or replace function public.set_user_profiles_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists user_profiles_updated_at on public.user_profiles;
create trigger user_profiles_updated_at
before update on public.user_profiles
for each row
execute function public.set_user_profiles_updated_at();

alter table public.user_profiles enable row level security;

drop policy if exists "user_profiles service role full access" on public.user_profiles;
create policy "user_profiles service role full access"
on public.user_profiles
for all
to service_role
using (true)
with check (true);
