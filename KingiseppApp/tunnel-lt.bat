@echo off
chcp 65001 >nul
cd /d "%~dp0"

where npm >nul 2>&1
if errorlevel 1 (
  echo [!] Нужен Node.js / npm. Установите с https://nodejs.org
  pause
  exit /b 1
)

echo Запасной туннель (localtunnel) к http://127.0.0.1:8000
echo Убедитесь, что API уже запущен (start.bat / порт 8000).
echo.
echo После старта появится ссылка вида:
echo   https://something.loca.lt
echo.
echo На телефоне:
echo   1^) Откройте ссылку
echo   2^) Если спросит пароль — это ваш внешний IP
echo      (посмотрите на https://ifconfig.me или ipinfo.io)
echo   3^) Дальше вход как обычно (табельный / пароль)
echo.
echo Окно не закрывайте.
echo.

npx --yes localtunnel --port 8000
pause
