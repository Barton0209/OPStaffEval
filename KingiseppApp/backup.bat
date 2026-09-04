@echo off
chcp 65001 >nul
set ROOT=%~dp0
set SRC=%ROOT%data\kingisepp.db
set DEST=%ROOT%backups
if not exist "%DEST%" mkdir "%DEST%"
if not exist "%SRC%" (
  echo Database not found: %SRC%
  exit /b 1
)
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set STAMP=%%i
copy /Y "%SRC%" "%DEST%\kingisepp_%STAMP%.db" >nul
echo Backup saved: %DEST%\kingisepp_%STAMP%.db
