@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo  KingiseppApp — первая установка
echo ============================================
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo [!] Нужен Python 3.11+  https://www.python.org/downloads/
  echo     При установке отметьте "Add python.exe to PATH"
  pause
  exit /b 1
)

where npm >nul 2>&1
if errorlevel 1 (
  echo [!] Нужен Node.js LTS  https://nodejs.org/
  pause
  exit /b 1
)

if not exist ".env" (
  copy /Y ".env.example" ".env" >nul
  echo [+] Создан .env из .env.example
)

if not exist "..\Files" mkdir "..\Files"
if not exist "data" mkdir data
if not exist "logs" mkdir logs
if not exist "backups" mkdir backups

echo [1/4] Python venv...
if not exist "backend\.venv\Scripts\python.exe" (
  python -m venv backend\.venv
  if errorlevel 1 (
    echo Ошибка создания venv
    pause
    exit /b 1
  )
)

echo [2/4] pip install...
"backend\.venv\Scripts\python.exe" -m pip install --upgrade pip
"backend\.venv\Scripts\python.exe" -m pip install -r backend\requirements.txt
if errorlevel 1 (
  echo Ошибка pip install
  pause
  exit /b 1
)

echo [3/4] npm install + сборка фронта...
pushd frontend
call npm install
if errorlevel 1 (
  popd
  echo Ошибка npm install
  pause
  exit /b 1
)
call npm run build
if errorlevel 1 (
  popd
  echo Ошибка npm run build
  pause
  exit /b 1
)
popd

echo [4/4] Готово.
echo.
echo Дальше:
echo   1. Положите Excel в папку Files рядом с KingiseppApp:
echo        01_База_1С.xlsx
echo        02_Пользователи.xlsx
echo        03_Реестр_закрепления.xlsx
echo        05_Анкеты.xlsx  (по желанию)
echo   2. Запустите start.bat
echo   3. Откройте http://127.0.0.1:8000
echo.
echo Для телефона в той же Wi-Fi: caddy-lan.bat
echo Для доступа из другой сети: tunnel-lt.bat  (или VPN + tunnel.bat)
echo.
pause
