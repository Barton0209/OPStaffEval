@echo off
chcp 65001 >nul
cd /d "%~dp0frontend"

echo [1/3] Сборка веб-интерфейса...
call npm run build
if errorlevel 1 goto :err

echo [2/3] Синхронизация Capacitor Android...
call npx cap sync android
if errorlevel 1 goto :err

echo [3/3] Сборка release APK (minify + R8)...
cd android
call gradlew.bat assembleRelease
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
echo  frontend\android\app\build\outputs\apk\release\app-release.apk
echo ============================================
echo.
echo  ВНИМАНИЕ: если keystore.properties не настроен, APK подписан
echo  debug-ключом (только для теста). Для публикации в магазине:
echo   1) copy frontend\android\keystore.properties.example frontend\android\keystore.properties
echo   2) сгенерируйте release.keystore и заполните пароли в keystore.properties
echo   3) перезапустите этот скрипт
explorer "app\build\outputs\apk\release"
pause
exit /b 0

:err
echo Ошибка сборки.
pause
exit /b 1