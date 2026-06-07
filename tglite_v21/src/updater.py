"""
TG Lite Updater — отдельная программа для уведомлений об обновлениях
• Живёт в трее
• Проверяет обновления каждые N минут
• Показывает уведомление когда выходит новая версия
• Может скачать и запустить установщик
"""

import sys
import os
import json
import threading
import time
import webbrowser
import urllib.request
import urllib.error
import base64
import io
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime

import tkinter as tk
from tkinter import ttk, messagebox

# Трей
try:
    import pystray
    from PIL import Image, ImageDraw, ImageFont
    HAS_TRAY = True
except ImportError:
    HAS_TRAY = False

# Уведомления
try:
    from plyer import notification as plyer_notify
    HAS_PLYER = True
except ImportError:
    HAS_PLYER = False

APP_NAME       = "TG Lite Updater"
CURRENT_VERSION = "2.1.0"
CONFIG_FILE    = Path.home() / ".tglite" / "updater_config.json"
LOG_FILE       = Path.home() / ".tglite" / "updater.log"
Path.home().joinpath(".tglite").mkdir(parents=True, exist_ok=True)

DEFAULT_CONFIG = {
    "github_repo":    "YOUR_USER/tglite",
    "check_interval": 30,        # минуты
    "notify_beta":    False,
    "auto_download":  False,
    "current_version": CURRENT_VERSION,
    "last_check":     "",
    "last_notified":  "",
}

# ─── Цвета ───────────────────────────────────────────────────────────────────
COLORS = {
    "bg":       "#17212b",
    "sidebar":  "#0d1117",
    "text":     "#e8eaed",
    "text_dim": "#7a8f9e",
    "accent":   "#5a9fd4",
    "input_bg": "#1c2a38",
    "border":   "#2a3b4c",
    "success":  "#4caf50",
    "warning":  "#ff9800",
    "danger":   "#e53935",
    "hover":    "#1e2f3e",
}

# ─── Утилиты ─────────────────────────────────────────────────────────────────
def load_config():
    if CONFIG_FILE.exists():
        try:
            cfg = json.loads(CONFIG_FILE.read_text())
            for k, v in DEFAULT_CONFIG.items():
                if k not in cfg:
                    cfg[k] = v
            return cfg
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()

def save_config(cfg):
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}\n"
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass
    print(line, end="")

def ver_tuple(v):
    try:
        return tuple(int(x) for x in str(v).lstrip("v").split("."))
    except Exception:
        return (0,)

def make_icon(size=64, color=(90, 159, 212), has_dot=False, dot_color=(76, 175, 80)):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # Круг фон
    d.ellipse([2, 2, size-2, size-2], fill=(*color, 255))
    # Самолётик
    cx, cy = size // 2, size // 2
    s = size // 4
    d.polygon([
        (cx, cy - s),
        (cx + s*2, cy + s//2),
        (cx, cy + s//3),
        (cx - s*2, cy + s//2),
    ], fill=(255, 255, 255, 230))
    # Точка уведомления
    if has_dot:
        r = size // 6
        d.ellipse([size-r*2-2, 2, size-2, r*2+2], fill=(*dot_color, 255))
    return img

# ─── Главное окно настроек ────────────────────────────────────────────────────
class UpdaterWindow:
    def __init__(self, updater_ref):
        self.app = updater_ref
        self.root = None

    def show(self):
        if self.root and self.root.winfo_exists():
            self.root.lift()
            self.root.focus_force()
            return

        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self.root.geometry("480x580")
        self.root.resizable(False, False)
        self.root.configure(bg=COLORS["bg"])
        self.root.protocol("WM_DELETE_WINDOW", self._hide)

        self._set_icon()
        self._build()
        self._refresh_status()

    def _set_icon(self):
        try:
            img = make_icon(32)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            photo = tk.PhotoImage(data=base64.b64encode(buf.read()))
            self.root.iconphoto(True, photo)
        except Exception:
            pass

    def _build(self):
        c = COLORS
        cfg = self.app.cfg

        # Заголовок
        header = tk.Frame(self.root, bg=c["sidebar"], pady=16)
        header.pack(fill="x")
        tk.Label(header, text="✈  TG Lite Updater",
                 font=("Segoe UI", 18, "bold"),
                 bg=c["sidebar"], fg=c["accent"]).pack()
        tk.Label(header, text="Автоматические уведомления об обновлениях",
                 font=("Segoe UI", 10), bg=c["sidebar"],
                 fg=c["text_dim"]).pack(pady=(2, 0))

        # Статус
        status_frame = tk.Frame(self.root, bg=c["input_bg"],
                                padx=16, pady=12)
        status_frame.pack(fill="x", padx=20, pady=(16, 0))

        tk.Label(status_frame, text="Статус",
                 font=("Segoe UI", 10, "bold"),
                 bg=c["input_bg"], fg=c["text_dim"]).pack(anchor="w")

        self.lbl_current = tk.Label(status_frame,
                                    text=f"Текущая версия: {CURRENT_VERSION}",
                                    font=("Segoe UI", 10),
                                    bg=c["input_bg"], fg=c["text"])
        self.lbl_current.pack(anchor="w", pady=2)

        self.lbl_latest = tk.Label(status_frame, text="Последняя версия: —",
                                   font=("Segoe UI", 10),
                                   bg=c["input_bg"], fg=c["text"])
        self.lbl_latest.pack(anchor="w", pady=2)

        self.lbl_last_check = tk.Label(status_frame, text="Последняя проверка: —",
                                       font=("Segoe UI", 9),
                                       bg=c["input_bg"], fg=c["text_dim"])
        self.lbl_last_check.pack(anchor="w", pady=2)

        self.lbl_status = tk.Label(status_frame, text="● Ожидание",
                                   font=("Segoe UI", 10, "bold"),
                                   bg=c["input_bg"], fg=c["text_dim"])
        self.lbl_status.pack(anchor="w", pady=(6, 0))

        # Кнопка проверить сейчас
        tk.Button(self.root, text="🔍 Проверить обновления сейчас",
                  bg=c["accent"], fg="white", relief="flat",
                  font=("Segoe UI", 11, "bold"),
                  padx=20, pady=8,
                  command=self._check_now).pack(pady=(14, 0))

        # Настройки
        settings_frame = tk.LabelFrame(self.root,
                                       text="  Настройки  ",
                                       bg=c["bg"], fg=c["text_dim"],
                                       font=("Segoe UI", 9),
                                       relief="flat",
                                       highlightbackground=c["border"],
                                       highlightthickness=1)
        settings_frame.pack(fill="x", padx=20, pady=16)

        # Репозиторий
        repo_row = tk.Frame(settings_frame, bg=c["bg"])
        repo_row.pack(fill="x", padx=12, pady=8)
        tk.Label(repo_row, text="GitHub репозиторий:",
                 font=("Segoe UI", 10), bg=c["bg"],
                 fg=c["text"]).pack(side="left")
        self.v_repo = tk.StringVar(value=cfg.get("github_repo", ""))
        tk.Entry(repo_row, textvariable=self.v_repo,
                 bg=c["input_bg"], fg=c["text"],
                 insertbackground=c["text"], relief="flat",
                 font=("Segoe UI", 10), width=24).pack(side="right")

        # Интервал
        interval_row = tk.Frame(settings_frame, bg=c["bg"])
        interval_row.pack(fill="x", padx=12, pady=4)
        tk.Label(interval_row, text="Проверять каждые (мин):",
                 font=("Segoe UI", 10), bg=c["bg"],
                 fg=c["text"]).pack(side="left")
        self.v_interval = tk.StringVar(value=str(cfg.get("check_interval", 30)))
        tk.Spinbox(interval_row, from_=5, to=1440,
                   textvariable=self.v_interval,
                   bg=c["input_bg"], fg=c["text"],
                   buttonbackground=c["input_bg"],
                   relief="flat", width=6,
                   font=("Segoe UI", 10)).pack(side="right")

        # Бета
        self.v_beta = tk.BooleanVar(value=cfg.get("notify_beta", False))
        tk.Checkbutton(settings_frame,
                       text="Уведомлять о бета-версиях",
                       variable=self.v_beta,
                       bg=c["bg"], fg=c["text"],
                       selectcolor=c["input_bg"],
                       activebackground=c["bg"],
                       font=("Segoe UI", 10)).pack(
            anchor="w", padx=12, pady=4)

        # Авто-скачивание
        self.v_auto = tk.BooleanVar(value=cfg.get("auto_download", False))
        tk.Checkbutton(settings_frame,
                       text="Автоматически скачивать обновления",
                       variable=self.v_auto,
                       bg=c["bg"], fg=c["text"],
                       selectcolor=c["input_bg"],
                       activebackground=c["bg"],
                       font=("Segoe UI", 10)).pack(
            anchor="w", padx=12, pady=(0, 8))

        # Кнопка сохранить
        tk.Button(settings_frame, text="Сохранить настройки",
                  bg=c["input_bg"], fg=c["text"], relief="flat",
                  font=("Segoe UI", 10), padx=14, pady=5,
                  command=self._save_settings).pack(pady=(0, 12))

        # Лог
        log_frame = tk.Frame(self.root, bg=c["bg"])
        log_frame.pack(fill="both", expand=True, padx=20, pady=(0, 16))
        tk.Label(log_frame, text="Журнал:",
                 font=("Segoe UI", 9, "bold"),
                 bg=c["bg"], fg=c["text_dim"]).pack(anchor="w")
        self.log_text = tk.Text(log_frame, height=5,
                                bg=c["input_bg"], fg=c["text_dim"],
                                insertbackground=c["text"],
                                relief="flat", font=("Consolas", 8),
                                state="disabled")
        self.log_text.pack(fill="both", expand=True)

        # Обновляем лог из файла
        self._load_log()

    def _load_log(self):
        try:
            if LOG_FILE.exists():
                lines = LOG_FILE.read_text(encoding="utf-8").splitlines()
                last = "\n".join(lines[-20:])
                self.log_text.config(state="normal")
                self.log_text.delete("1.0", "end")
                self.log_text.insert("end", last)
                self.log_text.config(state="disabled")
                self.log_text.yview_moveto(1.0)
        except Exception:
            pass

    def _refresh_status(self):
        cfg = self.app.cfg
        lc = cfg.get("last_check", "")
        self.lbl_last_check.config(
            text=f"Последняя проверка: {lc or 'никогда'}")

        latest = self.app.latest_version
        if latest:
            if ver_tuple(latest) > ver_tuple(CURRENT_VERSION):
                self.lbl_latest.config(
                    text=f"Последняя версия: {latest} 🆕",
                    fg=COLORS["warning"])
                self.lbl_status.config(
                    text="● Доступно обновление!",
                    fg=COLORS["warning"])
            else:
                self.lbl_latest.config(
                    text=f"Последняя версия: {latest} ✅",
                    fg=COLORS["success"])
                self.lbl_status.config(
                    text="● Актуальная версия",
                    fg=COLORS["success"])
        else:
            self.lbl_status.config(
                text="● Ожидание проверки...",
                fg=COLORS["text_dim"])

        if self.root and self.root.winfo_exists():
            self.root.after(10000, self._refresh_status)

    def _check_now(self):
        self.lbl_status.config(text="⏳ Проверяю...", fg=COLORS["text_dim"])
        threading.Thread(target=self.app.check_now, daemon=True).start()

    def _save_settings(self):
        self.app.cfg["github_repo"]    = self.v_repo.get().strip()
        self.app.cfg["check_interval"] = int(self.v_interval.get() or 30)
        self.app.cfg["notify_beta"]    = self.v_beta.get()
        self.app.cfg["auto_download"]  = self.v_auto.get()
        save_config(self.app.cfg)
        messagebox.showinfo("Сохранено", "Настройки сохранены ✅",
                            parent=self.root)
        log("Настройки сохранены")

    def _hide(self):
        if self.root:
            self.root.withdraw()

    def add_log_line(self, line):
        if self.root and self.root.winfo_exists():
            try:
                self.log_text.config(state="normal")
                self.log_text.insert("end", line + "\n")
                self.log_text.config(state="disabled")
                self.log_text.yview_moveto(1.0)
            except Exception:
                pass

# ─── Диалог нового обновления ─────────────────────────────────────────────────
class UpdateAvailableWindow:
    def __init__(self, version, url, changelog, download_url, auto_dl):
        self.version      = version
        self.url          = url
        self.changelog    = changelog
        self.download_url = download_url
        self.auto_dl      = auto_dl
        self._build()

    def _build(self):
        c = COLORS
        self.root = tk.Tk()
        self.root.title("Доступно обновление — TG Lite")
        self.root.geometry("440x420")
        self.root.resizable(False, False)
        self.root.configure(bg=c["bg"])
        self.root.attributes("-topmost", True)

        try:
            img = make_icon(32, has_dot=True)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            photo = tk.PhotoImage(data=base64.b64encode(buf.read()))
            self.root.iconphoto(True, photo)
        except Exception:
            pass

        # Шапка
        tk.Label(self.root, text="🎉 Новая версия TG Lite!",
                 font=("Segoe UI", 17, "bold"),
                 bg=c["bg"], fg=c["accent"]).pack(pady=(24, 4))
        tk.Label(self.root,
                 text=f"Версия  {CURRENT_VERSION}  →  {self.version}",
                 font=("Segoe UI", 12),
                 bg=c["bg"], fg=c["text"]).pack(pady=(0, 12))

        # Список изменений
        if self.changelog:
            frame = tk.Frame(self.root, bg=c["input_bg"], padx=14, pady=10)
            frame.pack(fill="x", padx=24, pady=(0, 12))
            tk.Label(frame, text="Что нового:",
                     font=("Segoe UI", 9, "bold"),
                     bg=c["input_bg"], fg=c["text_dim"]).pack(anchor="w")
            tk.Label(frame, text=self.changelog[:350],
                     font=("Segoe UI", 9),
                     bg=c["input_bg"], fg=c["text"],
                     wraplength=370, justify="left").pack(anchor="w", pady=(4, 0))

        # Прогресс (для авто-скачивания)
        self.progress_frame = tk.Frame(self.root, bg=c["bg"])
        self.progress_frame.pack(fill="x", padx=24)
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(self.progress_frame,
                                            variable=self.progress_var,
                                            maximum=100)
        self.lbl_progress = tk.Label(self.progress_frame, text="",
                                     font=("Segoe UI", 9),
                                     bg=c["bg"], fg=c["text_dim"])

        # Кнопки
        btn_frame = tk.Frame(self.root, bg=c["bg"])
        btn_frame.pack(pady=16)

        if self.download_url:
            tk.Button(btn_frame, text="⬇ Скачать и установить",
                      bg=c["accent"], fg="white", relief="flat",
                      font=("Segoe UI", 11, "bold"),
                      padx=20, pady=8,
                      command=self._download).pack(side="left", padx=6)

        tk.Button(btn_frame, text="🌐 Открыть страницу",
                  bg=c["input_bg"], fg=c["text"], relief="flat",
                  font=("Segoe UI", 10), padx=16, pady=8,
                  command=lambda: webbrowser.open(self.url)).pack(
            side="left", padx=6)

        tk.Button(btn_frame, text="Позже",
                  bg=c["input_bg"], fg=c["text_dim"], relief="flat",
                  font=("Segoe UI", 10), padx=16, pady=8,
                  command=self.root.destroy).pack(side="left", padx=6)

        if self.auto_dl and self.download_url:
            self.root.after(500, self._download)

        self.root.mainloop()

    def _download(self):
        if not self.download_url:
            webbrowser.open(self.url)
            return

        self.progress_bar.pack(fill="x", pady=(0, 4))
        self.lbl_progress.config(text="Скачивание...")
        self.lbl_progress.pack()

        threading.Thread(target=self._do_download, daemon=True).start()

    def _do_download(self):
        try:
            tmp = tempfile.mktemp(suffix=".exe")
            log(f"Скачивание {self.download_url} → {tmp}")

            def reporthook(count, block_size, total_size):
                if total_size > 0:
                    pct = min(100, count * block_size * 100 / total_size)
                    self.progress_var.set(pct)
                    self.lbl_progress.config(
                        text=f"Скачивание... {pct:.0f}%")

            urllib.request.urlretrieve(self.download_url, tmp, reporthook)
            self.progress_var.set(100)
            self.lbl_progress.config(
                text="✅ Скачано! Запускаю установщик...",
                fg=COLORS["success"])
            log("Скачивание завершено, запуск установщика")

            time.sleep(1)
            subprocess.Popen([tmp], shell=True)
            self.root.after(0, self.root.destroy)

        except Exception as e:
            log(f"Ошибка скачивания: {e}")
            self.lbl_progress.config(
                text=f"Ошибка: {e}", fg=COLORS["danger"])

# ─── Ядро Updater ─────────────────────────────────────────────────────────────
class TGLiteUpdater:
    def __init__(self):
        self.cfg            = load_config()
        self.latest_version = None
        self.latest_url     = ""
        self.latest_dl_url  = ""
        self.latest_body    = ""
        self._tray          = None
        self._window        = UpdaterWindow(self)
        self._stop_event    = threading.Event()

    def run(self):
        log(f"TG Lite Updater {CURRENT_VERSION} запущен")

        if not HAS_TRAY:
            # Без трея — показываем окно сразу
            self._window.show()
            self._start_checker()
            self._window.root.mainloop()
        else:
            self._start_tray()
            self._start_checker()
            # Первая проверка сразу
            threading.Thread(target=self.check_now, daemon=True).start()

    def _start_tray(self):
        icon_img = make_icon(64)
        menu = pystray.Menu(
            pystray.MenuItem("TG Lite Updater", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Открыть настройки",
                             lambda: self._open_window(), default=True),
            pystray.MenuItem("Проверить обновления",
                             lambda: threading.Thread(
                                 target=self.check_now, daemon=True).start()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Выход", self._quit),
        )
        self._tray = pystray.Icon("tglite_updater", icon_img, APP_NAME, menu)
        threading.Thread(target=self._tray.run, daemon=True).start()

    def _open_window(self):
        # Открываем окно из основного потока
        if self._window.root and self._window.root.winfo_exists():
            self._window.root.after(0, lambda: (
                self._window.root.deiconify(),
                self._window.root.lift()
            ))
        else:
            threading.Thread(target=self._window.show, daemon=False).start()

    def _start_checker(self):
        def loop():
            while not self._stop_event.is_set():
                interval = self.cfg.get("check_interval", 30) * 60
                self._stop_event.wait(interval)
                if not self._stop_event.is_set():
                    self.check_now()
        threading.Thread(target=loop, daemon=True).start()

    def check_now(self):
        log("Проверяю обновления...")
        try:
            repo = self.cfg.get("github_repo", "YOUR_USER/tglite")
            if "YOUR_USER" in repo:
                log("⚠ Укажите репозиторий в настройках!")
                return

            # Получаем все релизы (включая pre-release для бета)
            notify_beta = self.cfg.get("notify_beta", False)
            if notify_beta:
                url = f"https://api.github.com/repos/{repo}/releases"
            else:
                url = f"https://api.github.com/repos/{repo}/releases/latest"

            req = urllib.request.Request(
                url, headers={"User-Agent": "TGLiteUpdater"})
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read())

            if isinstance(data, list):
                # Берём первый (последний) релиз
                release = data[0] if data else {}
            else:
                release = data

            latest  = release.get("tag_name", "").lstrip("v")
            dl_url  = self._find_exe_asset(release)
            page_url = release.get("html_url", "")
            body    = release.get("body", "")
            is_pre  = release.get("prerelease", False)

            self.latest_version = latest
            self.latest_url     = page_url
            self.latest_dl_url  = dl_url
            self.latest_body    = body

            now = datetime.now().strftime("%d.%m.%Y %H:%M")
            self.cfg["last_check"] = now
            save_config(self.cfg)

            log(f"Текущая: {CURRENT_VERSION} | Последняя: {latest}")

            if ver_tuple(latest) > ver_tuple(CURRENT_VERSION):
                last_notified = self.cfg.get("last_notified", "")
                if last_notified != latest:
                    log(f"🆕 Найдено обновление: {latest}")
                    self.cfg["last_notified"] = latest
                    save_config(self.cfg)
                    self._notify_update(latest, page_url, dl_url, body)
                    self._update_tray_icon(has_dot=True)
                else:
                    log("Обновление уже было показано ранее")
            else:
                log("✅ Версия актуальна")
                self._update_tray_icon(has_dot=False)

            # Обновляем окно если открыто
            if self._window.root and self._window.root.winfo_exists():
                self._window.root.after(0, self._window._refresh_status)
                self._window.root.after(0, self._window._load_log)

        except urllib.error.URLError as e:
            log(f"Нет соединения: {e}")
        except Exception as e:
            log(f"Ошибка проверки: {e}")

    def _find_exe_asset(self, release):
        """Ищем .exe файл в assets релиза"""
        for asset in release.get("assets", []):
            name = asset.get("name", "").lower()
            if name.endswith(".exe") or "setup" in name:
                return asset.get("browser_download_url", "")
        return ""

    def _notify_update(self, version, url, dl_url, body):
        # Системное уведомление
        if HAS_PLYER:
            try:
                plyer_notify.notify(
                    title="TG Lite — Новая версия!",
                    message=f"Версия {version} доступна для загрузки. Нажмите чтобы открыть.",
                    app_name=APP_NAME,
                    timeout=10
                )
            except Exception as e:
                log(f"Ошибка уведомления: {e}")

        # Окно с деталями
        auto_dl = self.cfg.get("auto_download", False)
        threading.Thread(
            target=lambda: UpdateAvailableWindow(
                version, url, body, dl_url, auto_dl),
            daemon=False
        ).start()

    def _update_tray_icon(self, has_dot=False):
        if self._tray:
            try:
                new_img = make_icon(64, has_dot=has_dot)
                self._tray.icon = new_img
            except Exception:
                pass

    def _quit(self, *_):
        log("Updater остановлен")
        self._stop_event.set()
        if self._tray:
            self._tray.stop()
        sys.exit(0)


# ─── Точка входа ─────────────────────────────────────────────────────────────
def main():
    # Проверяем зависимости
    missing = []
    if not HAS_TRAY:
        missing.append("pystray  pillow")
    if not HAS_PLYER:
        missing.append("plyer")

    if missing:
        print("Для полной работы установите:")
        for m in missing:
            print(f"  pip install {m}")
        print()

    updater = TGLiteUpdater()
    updater.run()


if __name__ == "__main__":
    main()
