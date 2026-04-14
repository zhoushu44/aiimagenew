-- Seed points settings for the protected API settings screen
insert into public.api_settings (scope, setting_key, setting_value, description)
values
  ('global', 'POINTS_SIGNUP_BONUS', '100', '新用户注册赠送积分'),
  ('global', 'POINTS_DAILY_FREE', '10', '每日免费领取积分')
on conflict (scope, setting_key) do update
set setting_value = excluded.setting_value,
    description = excluded.description;
