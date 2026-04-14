-- Add human-readable descriptions for API settings
alter table public.api_settings
add column if not exists description text not null default '';
