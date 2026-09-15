@echo off
chcp 65001 >nul
set ROOT=%~dp0
if not exist "%ROOT%backend\.venv\Scripts\python.exe" (
  echo [ERROR] venv не найден: %ROOT%backend\.venv
  exit /b 1
)
set PYTHONPATH=%ROOT%backend
"%ROOT%backend\.venv\Scripts\python.exe" -m app.backup_util
