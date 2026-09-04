@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist "cloudflared.exe" (
  echo [!] Нет cloudflared.exe
  echo Скачайте: https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe
  echo и положите файл в эту папку как cloudflared.exe
  pause
  exit /b 1
)

echo Запуск туннеля Cloudflare к http://127.0.0.1:8000
echo В логе появится строка вида:
echo   https://xxxx-xxxx.trycloudflare.com
echo Окно не закрывайте — пока оно открыто, сайт доступен из интернета.
echo.
echo Если будет timeout — запустите tunnel-lt.bat (запасной туннель)
echo или включите VPN и повторите.
echo.

set ATTEMPT=1
:retry
echo --- Попытка %ATTEMPT% ---
cloudflared.exe tunnel --url http://127.0.0.1:8000 --protocol http2
set ERR=%ERRORLEVEL%
if "%ERR%"=="0" goto end

echo.
echo [!] Cloudflare не ответил (код %ERR% / timeout).
if %ATTEMPT% GEQ 3 goto fail
set /a ATTEMPT+=1
echo Повтор через 5 сек...
timeout /t 5 /nobreak >nul
goto retry

:fail
echo.
echo ============================================
echo  Quick Tunnel Cloudflare сейчас недоступен
echo  с этой сети (часто без VPN / из РФ).
echo.
echo  Варианты:
echo   1^) Включить VPN и снова tunnel.bat
echo   2^) Запустить tunnel-lt.bat  (localtunnel)
echo ============================================
pause
exit /b 1

:end
pause
