create table if not exists public.generation_tasks (
  id text primary key,
  user_id uuid not null references auth.users (id) on delete cascade,
  mode text not null default 'suite',
  request_id text,
  status text not null default 'pending' check (status in ('pending', 'running', 'succeeded', 'failed')),
  result jsonb,
  error text,
  details text,
  spend_record jsonb,
  refunded boolean not null default false,
  refund_error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists generation_tasks_user_id_created_at_idx
on public.generation_tasks (user_id, created_at desc);

create index if not exists generation_tasks_status_updated_at_idx
on public.generation_tasks (status, updated_at desc);

create index if not exists generation_tasks_request_id_idx
on public.generation_tasks (request_id);

create or replace function public.set_generation_tasks_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists generation_tasks_updated_at on public.generation_tasks;
create trigger generation_tasks_updated_at
before update on public.generation_tasks
for each row
execute function public.set_generation_tasks_updated_at();

alter table public.generation_tasks enable row level security;

drop policy if exists "generation_tasks service role full access" on public.generation_tasks;
create policy "generation_tasks service role full access"
on public.generation_tasks
for all
to service_role
using (true)
with check (true);
