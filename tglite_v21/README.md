# ✈ TG Lite v2.1

Лёгкий Telegram-клиент на Python с поддержкой прокси, QR-входа, уведомлений и автообновлений.

---

## 📦 Содержимое

```
tglite_v21/
├── src/
│   ├── main.py            ← Десктоп (Windows/Linux/macOS)
│   ├── main_mobile.py     ← Android (Kivy)
│   └── updater.py         ← Апдейтер (трей + уведомления)
├── installer/
│   └── setup.nsi          ← NSIS установщик
├── .github/workflows/
│   ├── build-exe.yml      ← GitHub Actions → EXE
│   └── build-apk.yml      ← GitHub Actions → APK (исправлен)
├── tglite.spec            ← PyInstaller (TGLite.exe)
├── updater.spec           ← PyInstaller (TGLiteUpdater.exe)
├── buildozer.spec         ← Buildozer (APK)
├── requirements.txt
└── README.md
```

---

## 🚀 Запуск без сборки

```bash
pip install telethon pysocks cryptg pillow pystray plyer qrcode
python src/main.py
```

---

## 🏗 Сборка через GitHub Actions

1. Загрузи все файлы в репозиторий GitHub
2. Вкладка **Actions**:
   - **Build EXE** → собирает `TGLite.exe` + `TGLiteUpdater.exe`
   - **Build APK** → собирает `tglite-debug.apk`
3. Запусти нужный workflow кнопкой **Run workflow**
4. Скачай из **Artifacts**

---

## 🔧 Настройка

При первом запуске введи:
- **API ID** и **API Hash** → получить на [my.telegram.org](https://my.telegram.org)
- **Номер телефона** или войди по **QR-коду**

Прокси: меню **TG Lite → Прокси**  
Бета-обновления: меню **Бета → Бета-канал**

---

## 🆕 Что нового в v2.1

- Вход по QR-коду
- Системные уведомления о новых сообщениях
- Иконка в трее (сворачивается вместо закрытия)
- Отдельная программа TGLiteUpdater
- Бета-канал обновлений
- Исправлена сборка APK
