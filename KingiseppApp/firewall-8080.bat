@echo off
:: Открыть порт 8080 в брандмауэре (нужны права администратора)
chcp 65001 >nul
net session >nul 2>&1
if errorlevel 1 (
  echo Запросите права администратора...
  powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)

netsh advfirewall firewall delete rule name="Kingisepp Caddy 8080" >nul 2>&1
netsh advfirewall firewall add rule name="Kingisepp Caddy 8080" dir=in action=allow protocol=TCP localport=8080 profile=private
echo.
echo Правило добавлено: входящий TCP 8080 разрешён ТОЛЬКО в частной сети (LAN).
echo На телефоне в той же Wi-Fi откройте: http://IP-ПК:8080
echo.
pause
