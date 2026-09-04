@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist "data" mkdir data
if not exist "logs" mkdir logs
if not exist "backups" mkdir backups

set PYTHONPATH=%~dp0backend
set "VENV_PY=%~dp0backend\.venv\Scripts\python.exe"

if not exist "%VENV_PY%" (
  echo [!] Нет venv. Создайте: python -m venv backend\.venv
  echo     затем: backend\.venv\Scripts\pip install -r backend\requirements.txt
  pause
  exit /b 1
)

echo [1/3] Инициализация БД / импорт Excel...
"%VENV_PY%" backend\scripts\init_db.py
if errorlevel 1 (
  echo Ошибка init_db
  pause
  exit /b 1
)

echo [2/3] Запуск API http://127.0.0.1:8000 ...
start "Kingisepp API" "%VENV_PY%" -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000

timeout /t 2 >nul

if exist "cloudflared.exe" (
  echo [3/3] Cloudflare Tunnel...
  echo     В окне туннеля появится https://....trycloudflare.com
  echo     Эту ссылку дайте мастерам в Кингисеппе и себе в Москве.
  start "Kingisepp Tunnel" "%~dp0cloudflared.exe" tunnel --url http://127.0.0.1:8000
) else (
  echo [3/3] cloudflared.exe не найден.
  echo     Локально: http://127.0.0.1:8000
  echo     Из интернета: положите cloudflared.exe сюда и запустите tunnel.bat
)

echo.
echo ============================================
echo  Локально:  http://127.0.0.1:8000
echo  Admin:     ADMIN-OP / AdminOP2026
echo  Docs API:  http://127.0.0.1:8000/docs
echo  База:      data\kingisepp.db
echo ============================================
pause
