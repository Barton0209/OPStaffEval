# KingiseppApp — Portable MVP (Вариант Г)

Пилот оценки персонала ОП **Кингисепп (ВСМ)**.

## Быстрый старт (ПК)

```bat
cd C:\My_Project\System_Ocenok\KingiseppApp
start.bat
```

Локально: http://127.0.0.1:8000

Из интернета (Москва ↔ Кингисепп): `tunnel.bat` → ссылка `https://….trycloudflare.com`

| Кто | Логин | Пароль |
|---|---|---|
| Админ ОП | `ADMIN-OP` | `AdminOP2026` |
| Нач. участка | `CHIEF-OP` | `ChiefOP2026` |
| Мастер/ПР | таб. из Excel | обычно `K` + цифры |

## Android-приложение

См. **[ANDROID.md](ANDROID.md)** — Capacitor APK, подключается к тому же серверу.

```bat
build-android.bat
```

или: `cd frontend` → `npm run android` (откроет Android Studio).

В приложении на экране входа вставьте ссылку туннеля → войдите табельным номером.

## Бэкап

`backup.bat` (также по расписанию в 02:00).
