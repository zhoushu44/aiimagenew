@echo off
echo === 停止现有服务 ===
taskkill /F /FI "WINDOWTITLE eq Celery Worker*" 2>nul
taskkill /F /FI "WINDOWTITLE eq Flask Server*" 2>nul
taskkill /F /FI "IMAGENAME eq python.exe" /FI "MEMUSAGE gt 100000" 2>nul
timeout /t 2 /nobreak > nul

echo.
echo === 启动生产环境 ===
echo.

echo [1/2] 启动 Celery Worker (gevent池, 并发100)...
start "Celery Worker" cmd /k "cd /d %~dp0 && python -m celery -A celery_tasks worker -Q generation_priority,generation_normal --pool=gevent --concurrency=100 --loglevel=info"
timeout /t 5 /nobreak > nul

echo [2/2] 启动 Flask 服务...
start "Flask Server" cmd /k "cd /d %~dp0 && python app.py"
timeout /t 3 /nobreak > nul

echo.
echo === 生产环境已启动 ===
echo Flask: http://127.0.0.1:5078
echo Worker: gevent池, 并发100
echo.
echo 提示: Worker已优化为gevent池，可处理高并发
echo.
pause
