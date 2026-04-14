-- Seed human-readable descriptions for existing API settings
update public.api_settings
set description = case setting_key
  when 'HOST' then '服务启动地址'
  when 'PORT' then '服务启动端口'
  when 'FLASK_DEBUG' then '是否开启调试模式'
  when 'OPENAI_MODEL' then 'OpenAI 聊天模型'
  when 'POINTS_SIGNUP_BONUS' then '新用户注册赠送积分'
  when 'POINTS_DAILY_FREE' then '每日免费领取积分'
  else description end
where setting_key in ('HOST','PORT','FLASK_DEBUG','OPENAI_MODEL','POINTS_SIGNUP_BONUS','POINTS_DAILY_FREE');
