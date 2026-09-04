@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "CADDY="
if exist "C:\caddy\caddy.exe" set "CADDY=C:\caddy\caddy.exe"
if exist "%~dp0caddy.exe" set "CADDY=%~dp0caddy.exe"
if "%CADDY%"=="" (
  where caddy >nul 2>&1 && set "CADDY=caddy"
)
if "%CADDY%"=="" (
  echo [!] Не найден caddy.exe. Положите в C:\caddy\ или в эту папку.
  pause
  exit /b 1
)

echo Останавливаю старый Caddy (если был)...
taskkill /IM caddy.exe /F >nul 2>&1
timeout /t 1 /nobreak >nul

echo.
echo Caddy → http://127.0.0.1:8000
echo.
echo 1^) Сначала start.bat (API на порту 8000^)
echo 2^) С телефона В ТОЙ ЖЕ Wi-Fi откройте HTTP ^(без s^):
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4"') do (
  for /f "tokens=1" %%b in ("%%a") do echo   http://%%b:8080
)
echo.
echo Окно Caddy не закрывайте.
echo.

"%CADDY%" run --config "%~dp0Caddyfile"
pause
