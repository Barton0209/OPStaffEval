@echo off
chcp 65001 >nul
echo Stopping Kingisepp processes...
taskkill /FI "WINDOWTITLE eq Kingisepp API*" /T /F >nul 2>&1
taskkill /IM uvicorn.exe /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Kingisepp Tunnel*" /T /F >nul 2>&1
echo Done.
