@echo off
chcp 65001 >nul
cd /d "%~dp0frontend"

echo [1/3] Сборка веб-интерфейса...
call npm run build
if errorlevel 1 goto :err

echo [2/3] Синхронизация Capacitor Android...
call npx cap sync android
if errorlevel 1 goto :err

echo [3/3] Сборка debug APK...
cd android
call gradlew.bat assembleDebug
if errorlevel 1 (
  echo.
  echo Gradle не собрал APK. Откройте проект в Android Studio:
  echo   cd frontend ^&^& npx cap open android
  pause
  exit /b 1
)

echo.
echo ============================================
echo  APK готов:
echo  frontend\android\app\build\outputs\apk\debug\app-debug.apk
echo ============================================
explorer "app\build\outputs\apk\debug"
pause
exit /b 0

:err
echo Ошибка сборки.
pause
exit /b 1
