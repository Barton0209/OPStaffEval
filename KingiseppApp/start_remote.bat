@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================================
echo  Внешний доступ ТОЛЬКО через туннель с аутентификацией.
echo ============================================================
echo  Публичные Quick Tunnel (trycloudflare) и localtunnel ЗАПРЕЩЕНЫ:
echo  они открывают персональные данные (152-ФЗ) всему интернету.
echo.
echo  Правильный вариант - Cloudflare Tunnel + Cloudflare Access:
echo   1. Создайте Named Tunnel и добавьте маршрут на http://127.0.0.1:8000
echo   2. Настройте политику доступа (email/SSO) в Cloudflare Zero Trust
echo   3. Запустите: cloudflared.exe tunnel run ^<TUNNEL_NAME^>
echo.
echo  Либо используйте VPN (Tailscale) для сервера и устройств мастеров.
echo ============================================================
pause