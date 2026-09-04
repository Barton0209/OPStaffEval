@echo off
chcp 65001 >nul
echo Stopping Kingisepp processes...
taskkill /FI "WINDOWTITLE eq Kingisepp API*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Kingisepp Tunnel*" /T /F >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do taskkill /PID %%a /F >nul 2>&1
echo Done.
