# ✈ TG Lite

Лёгкий Telegram-клиент на Python с поддержкой прокси.  
Десктоп (Tkinter) + мобильная версия (Kivy/Android).

---

## 📦 Структура проекта

```
tglite/
├── src/
│   ├── main.py            ← Десктоп-клиент (Tkinter, Windows/Linux/macOS)
│   └── main_mobile.py     ← Мобильный клиент (Kivy, Android)
├── installer/
│   └── setup.nsi          ← NSIS-скрипт установщика для Windows
├── .github/
│   └── workflows/
│       └── ci.yml         ← GitHub Actions (авто-сборка EXE + APK)
├── tglite.spec            ← PyInstaller spec (для EXE)
├── buildozer.spec         ← Buildozer spec (для APK)
├── build.py               ← Мастер сборки
├── requirements.txt       ← Зависимости Python
└── README.md
```

---

## 🚀 Быстрый старт (запуск без сборки)

```bash
# 1. Установить зависимости
pip install telethon pysocks cryptg

# 2. Запустить десктоп-версию
python src/main.py
```

При первом запуске откроется окно входа — введите:
- **API ID** и **API Hash** (получить на [my.telegram.org](https://my.telegram.org))
- **Номер телефона** в формате `+79991234567`

---

## 🔧 Настройка прокси

### Через GUI
Меню **TG Lite → Настройки прокси**

### Через config.json
Файл: `~/.tglite/config.json`

```json
{
  "proxy": {
    "enabled": true,
    "type": "SOCKS5",
    "host": "127.0.0.1",
    "port": 1080,
    "username": "",
    "password": ""
  }
}
```

Поддерживаемые типы: `SOCKS5`, `SOCKS4`, `HTTP`

---

## 🏗 Сборка

### Автоматически (рекомендуется)

```bash
# Установить все зависимости
python build.py --install

# Собрать только EXE (Windows)
python build.py --exe

# Собрать только APK (Linux / macOS)
python build.py --apk

# Собрать всё
python build.py
```

---

### Windows EXE вручную

```bash
pip install pyinstaller telethon pysocks cryptg
pyinstaller --clean --noconfirm tglite.spec
# → dist/TGLite.exe
```

#### Установщик (NSIS)
1. Скачайте [NSIS 3.x](https://nsis.sourceforge.io)
2. После сборки EXE:
```bash
makensis installer/setup.nsi
# → installer/TGLite_Setup_1.0.0.exe
```

---

### Android APK вручную (Linux / WSL2)

```bash
pip install buildozer kivy cython
cp src/main_mobile.py main.py
buildozer android debug
# → bin/tglite-1.0.0-debug.apk
```

Установка на устройство:
```bash
adb install bin/tglite-*.apk
# или просто скопируйте APK и откройте на телефоне
```

#### На Windows через Docker
```bash
docker run -it --rm -v %CD%:/app kivy/buildozer android debug
```

---

### GitHub Actions (облачная сборка)

Пушните в репозиторий — Actions автоматически соберут:
- **TGLite-Windows** → `dist/TGLite.exe`  
- **TGLite-Android** → `bin/*.apk`

Артефакты доступны во вкладке **Actions → последний workflow**.

---

## 🎨 Возможности

| Функция | Десктоп | Android |
|---------|---------|---------|
| Список чатов (50 диалогов) | ✅ | ✅ |
| Отправка/получение сообщений | ✅ | ✅ |
| Real-time (входящие мгновенно) | ✅ | ✅ |
| Прокси SOCKS5/4/HTTP | ✅ | ✅ |
| Двухфакторная аутентификация | ✅ | ✅ |
| Тёмная / светлая тема | ✅ | — |
| Поиск по чатам | ✅ | ✅ |
| Счётчик непрочитанных | ✅ | ✅ |

---

## ⚠ Важно

- Получите `api_id` и `api_hash` на [my.telegram.org](https://my.telegram.org) → API Development Tools
- Сессия хранится в `~/.tglite/tglite.session` — не публикуйте этот файл
- Для разработки используйте тестовые серверы Telegram

---

## 📄 Лицензия

MIT — используйте свободно.
