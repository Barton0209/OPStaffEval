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

echo [1/5] Бэкап базы (WAL-safe)...
"%VENV_PY%" -m app.backup_util

echo [2/5] Миграции БД (Alembic)...
pushd backend
"%VENV_PY%" -m alembic upgrade head
if errorlevel 1 (
  popd
  echo Ошибка миграций Alembic
  pause
  exit /b 1
)
popd

echo [3/5] Инициализация БД / импорт Excel...
"%VENV_PY%" backend\scripts\init_db.py
if errorlevel 1 (
  echo Ошибка init_db
  pause
  exit /b 1
)

echo [4/5] Запуск API http://127.0.0.1:8000 ...
start "Kingisepp API" "%VENV_PY%" -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000

echo [5/5] Готово.
echo.
echo ============================================
echo  Локально:  http://127.0.0.1:8000
echo  Swagger/docs в проде отключен.
echo  База:      data\kingisepp.db
echo  Внешний доступ: только VPN или start_remote.bat (Cloudflare Access).
echo  Публичные туннели (trycloudflare/localtunnel) запрещены - утечка ПДн.
echo ============================================
pause
