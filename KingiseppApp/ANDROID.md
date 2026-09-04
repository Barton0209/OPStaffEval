# Android-приложение «Оценка ОП»

Нативное Android-оболочка (Capacitor) над тем же интерфейсом. Подключается к вашему FastAPI через интернет (Cloudflare Tunnel или сервер).

## Схема

```text
Телефон (APK)  --https-->  cloudflared / сервер  -->  KingiseppApp на ПК
```

## Что нужно на компьютере сборки

1. [Android Studio](https://developer.android.com/studio) (JDK и Android SDK ставятся вместе с ним)
2. Node.js (уже есть)
3. Работающий backend + туннель (`start.bat` + `tunnel.bat`)

## Сборка APK

```bat
cd C:\My_Project\System_Ocenok\KingiseppApp\frontend
npm run build
npx cap sync android
npx cap open android
```

В Android Studio: **Build → Build Bundle(s) / APK(s) → Build APK(s)**.
Готовый файл: `android\app\build\outputs\apk\debug\app-debug.apk`

Или из командной строки (если SDK настроен):

```bat
cd android
gradlew.bat assembleDebug
```

Скрипт-помощник: `..\build-android.bat` из папки `KingiseppApp`.

## Как пользуется мастер в Кингисеппе

1. Установите `app-debug.apk` на телефон (файл / WhatsApp / USB)
2. На ПК в Москве: `start.bat`, затем `tunnel.bat`
3. Скопируйте ссылку `https://….trycloudflare.com` из окна туннеля
4. В приложении на экране входа вставьте эту ссылку → **Проверить и сохранить**
5. Войдите своим табельным номером и паролем
6. Оценивайте сотрудников как обычно

Если ссылка туннеля сменилась (перезапуск) — снова вставьте новый адрес на экране входа.

## Важно

- ПК с системой должен быть **включён**, пока мастера работают
- Для постоянной ссылки позже: именованный Cloudflare Tunnel или VPS
- Google Play не обязателен для пилота — достаточно установки APK
