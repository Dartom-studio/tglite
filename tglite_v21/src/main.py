"""
TG Lite v2.1 — Десктоп клиент (Windows/Linux/macOS)
• Вход по QR-коду / номеру+паролю
• Системные уведомления
• Иконка в трее
• OTA обновления
• Бета-канал
"""

import sys
import os
import asyncio
import threading
import json
import base64
import io
import webbrowser
import urllib.request
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from telethon import TelegramClient, events
from telethon.tl.types import User, Chat, Channel
from telethon.tl.functions.auth import ExportLoginTokenRequest
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError
import socks

try:
    from plyer import notification as plyer_notify
    HAS_PLYER = True
except ImportError:
    HAS_PLYER = False

try:
    import pystray
    from PIL import Image, ImageDraw, ImageTk
    HAS_TRAY = True
except ImportError:
    HAS_TRAY = False

try:
    import qrcode
    from PIL import Image as PILImage, ImageTk as PILImageTk
    HAS_QR = True
except ImportError:
    HAS_QR = False

APP_NAME     = "TG Lite"
APP_VERSION  = "2.1.0"
CONFIG_FILE  = Path.home() / ".tglite" / "config.json"
SESSION_DIR  = Path.home() / ".tglite"
SESSION_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_CONFIG = {
    "api_id": "", "api_hash": "", "phone": "",
    "proxy":  {"enabled": False, "type": "SOCKS5",
               "host": "127.0.0.1", "port": 1080,
               "username": "", "password": ""},
    "theme":          "dark",
    "notifications":  True,
    "tray_on_close":  True,
    "github_repo":    "YOUR_USER/tglite",
    "beta_channel":   False,
}

def load_config():
    if CONFIG_FILE.exists():
        try:
            cfg = json.loads(CONFIG_FILE.read_text())
            for k, v in DEFAULT_CONFIG.items():
                cfg.setdefault(k, v)
            return cfg
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()

def save_config(cfg):
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))

THEMES = {
    "dark": {
        "bg": "#17212b", "sidebar_bg": "#0d1117", "chat_bg": "#0f1923",
        "bubble_me": "#2b5278", "bubble_them": "#182533",
        "text": "#e8eaed", "text_dim": "#7a8f9e",
        "accent": "#5a9fd4", "input_bg": "#1c2a38",
        "border": "#2a3b4c", "online": "#4caf50",
        "unread_bg": "#5a9fd4", "hover": "#1e2f3e",
        "danger": "#e53935", "warning": "#ff9800", "success": "#4caf50",
    },
    "light": {
        "bg": "#f5f5f5", "sidebar_bg": "#ffffff", "chat_bg": "#f0f2f5",
        "bubble_me": "#dcf8c6", "bubble_them": "#ffffff",
        "text": "#111111", "text_dim": "#777777",
        "accent": "#0088cc", "input_bg": "#ffffff",
        "border": "#dddddd", "online": "#4caf50",
        "unread_bg": "#0088cc", "hover": "#e8e8e8",
        "danger": "#e53935", "warning": "#ff9800", "success": "#4caf50",
    }
}

def get_proxy(cfg):
    p = cfg.get("proxy", {})
    if not p.get("enabled"):
        return None
    pt = {"SOCKS5": socks.SOCKS5, "SOCKS4": socks.SOCKS4,
          "HTTP": socks.HTTP}.get(p.get("type", "SOCKS5"), socks.SOCKS5)
    return (pt, p["host"], int(p["port"]), True,
            p.get("username") or None, p.get("password") or None)

def peer_display(entity):
    if isinstance(entity, User):
        name = (entity.first_name or "") + (" " + entity.last_name if entity.last_name else "")
        return name.strip() or entity.username or str(entity.id)
    if hasattr(entity, "title"):
        return entity.title
    return str(entity.id)

def peer_initials(name):
    parts = name.split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    return name[:2].upper() if name else "??"

def format_time(dt):
    if not dt:
        return ""
    now = datetime.now()
    if dt.date() == now.date():
        return dt.strftime("%H:%M")
    return dt.strftime("%d.%m")

def make_pil_icon(size=64, has_dot=False):
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([2, 2, size-2, size-2], fill=(90, 159, 212, 255))
    cx, cy, s = size//2, size//2, size//4
    d.polygon([
        (cx, cy-s), (cx+s*2, cy+s//2),
        (cx, cy+s//3), (cx-s*2, cy+s//2),
    ], fill=(255, 255, 255, 230))
    if has_dot:
        r = size // 6
        d.ellipse([size-r*2-2, 2, size-2, r*2+2], fill=(229, 57, 53, 255))
    return img

def ver_tuple(v):
    try:
        return tuple(int(x) for x in str(v).lstrip("v").split("."))
    except Exception:
        return (0,)

# ─── Диалог входа ────────────────────────────────────────────────────────────
class LoginDialog(tk.Toplevel):
    def __init__(self, parent, theme, on_done):
        super().__init__(parent)
        self.title(f"{APP_NAME} — Вход")
        self.resizable(False, False)
        self.configure(bg=theme["bg"])
        self._t = theme
        self._on_done = on_done
        self._build()
        self.transient(parent)
        self.grab_set()

    def _build(self):
        t = self._t
        tk.Label(self, text="✈  TG Lite", font=("Segoe UI", 22, "bold"),
                 bg=t["bg"], fg=t["accent"]).pack(pady=(20, 2))
        tk.Label(self, text=f"v{APP_VERSION}  —  Выберите способ входа",
                 font=("Segoe UI", 10), bg=t["bg"], fg=t["text_dim"]).pack(pady=(0, 14))

        nb = ttk.Notebook(self)
        nb.pack(fill="both", padx=20, pady=(0, 12))
        style = ttk.Style()
        style.configure("TNotebook", background=t["bg"], borderwidth=0)
        style.configure("TNotebook.Tab", background=t["input_bg"],
                        foreground=t["text"], padding=[16, 8])
        style.map("TNotebook.Tab",
                  background=[("selected", t["accent"])],
                  foreground=[("selected", "white")])

        self._tab_qr    = tk.Frame(nb, bg=t["bg"])
        self._tab_phone = tk.Frame(nb, bg=t["bg"])
        nb.add(self._tab_qr,    text="📱 QR-код")
        nb.add(self._tab_phone, text="📞 Телефон")
        self._build_qr_tab()
        self._build_phone_tab()

        # API ключи
        af = tk.LabelFrame(self, text="  Telegram API  ",
                           bg=t["bg"], fg=t["text_dim"],
                           font=("Segoe UI", 9), relief="flat",
                           highlightbackground=t["border"], highlightthickness=1)
        af.pack(fill="x", padx=20, pady=(0, 16))

        self.v_api_id   = tk.StringVar()
        self.v_api_hash = tk.StringVar()
        self._api_row(af, "API ID:",   self.v_api_id,   0)
        self._api_row(af, "API Hash:", self.v_api_hash, 1)
        tk.Label(af, text="Получить: my.telegram.org → API Development Tools",
                 font=("Segoe UI", 8), bg=t["bg"], fg=t["text_dim"]).grid(
            row=2, column=0, columnspan=2, pady=(0, 6))

    def _api_row(self, f, lbl, var, row):
        t = self._t
        tk.Label(f, text=lbl, bg=t["bg"], fg=t["text"],
                 font=("Segoe UI", 10), width=10, anchor="w").grid(
            row=row, column=0, padx=8, pady=5, sticky="w")
        tk.Entry(f, textvariable=var, bg=t["input_bg"], fg=t["text"],
                 insertbackground=t["text"], relief="flat",
                 font=("Segoe UI", 11), width=30).grid(
            row=row, column=1, padx=8, pady=5, sticky="ew")

    def _build_qr_tab(self):
        t = self._t
        f = self._tab_qr
        tk.Label(f, text="Откройте Telegram → Настройки\n→ Устройства → Подключить устройство",
                 font=("Segoe UI", 10), bg=t["bg"], fg=t["text"],
                 justify="center").pack(pady=(16, 8))
        self.qr_label = tk.Label(f, bg=t["bg"],
                                  text="QR появится после ввода API ключей",
                                  fg=t["text_dim"], font=("Segoe UI", 10))
        self.qr_label.pack(pady=8)
        self.qr_status = tk.Label(f, text="", font=("Segoe UI", 10),
                                   bg=t["bg"], fg=t["text_dim"])
        self.qr_status.pack(pady=2)
        tk.Button(f, text="Показать QR-код",
                  bg=t["accent"], fg="white", relief="flat",
                  font=("Segoe UI", 10), padx=16, pady=6,
                  command=self._start_qr).pack(pady=(8, 16))

    def _build_phone_tab(self):
        t = self._t
        f = self._tab_phone
        tk.Label(f, text="", bg=t["bg"]).pack(pady=6)
        self.v_phone = tk.StringVar()
        self.v_pass  = tk.StringVar()

        def row(lbl, var, show=""):
            fr = tk.Frame(f, bg=t["bg"])
            fr.pack(fill="x", padx=20, pady=5)
            tk.Label(fr, text=lbl, bg=t["bg"], fg=t["text"],
                     font=("Segoe UI", 10), width=16, anchor="w").pack(side="left")
            tk.Entry(fr, textvariable=var, show=show,
                     bg=t["input_bg"], fg=t["text"],
                     insertbackground=t["text"], relief="flat",
                     font=("Segoe UI", 11), width=22).pack(side="left", ipady=4)

        row("Телефон:", self.v_phone)
        row("Пароль 2FA (если есть):", self.v_pass, show="•")
        tk.Label(f, text="Формат: +79991234567",
                 font=("Segoe UI", 8), bg=t["bg"], fg=t["text_dim"]).pack()
        tk.Button(f, text="Войти →",
                  bg=t["accent"], fg="white", relief="flat",
                  font=("Segoe UI", 11, "bold"), padx=24, pady=8,
                  command=self._phone_login).pack(pady=(14, 20))

    def _start_qr(self):
        if not self.v_api_id.get() or not self.v_api_hash.get():
            messagebox.showwarning("Ошибка", "Введите API ID и API Hash", parent=self)
            return
        self._on_done({"mode": "qr",
                       "api_id":   self.v_api_id.get().strip(),
                       "api_hash": self.v_api_hash.get().strip()}, self)

    def _phone_login(self):
        if not self.v_api_id.get() or not self.v_api_hash.get():
            messagebox.showwarning("Ошибка", "Введите API ID и API Hash", parent=self)
            return
        if not self.v_phone.get():
            messagebox.showwarning("Ошибка", "Введите номер телефона", parent=self)
            return
        self._on_done({"mode":     "phone",
                       "api_id":   self.v_api_id.get().strip(),
                       "api_hash": self.v_api_hash.get().strip(),
                       "phone":    self.v_phone.get().strip(),
                       "password": self.v_pass.get().strip()}, self)

    def show_qr(self, token_bytes):
        if not HAS_QR:
            self.qr_status.config(
                text="pip install qrcode pillow", fg=self._t["danger"])
            return
        try:
            token_b64 = base64.urlsafe_b64encode(token_bytes).decode().rstrip("=")
            url = f"tg://login?token={token_b64}"
            qr  = qrcode.QRCode(version=1, box_size=6, border=2)
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="white", back_color="#17212b")
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            photo = PILImageTk.PhotoImage(PILImage.open(buf))
            self.qr_label.config(image=photo, text="")
            self.qr_label.image = photo
            self.qr_status.config(text="📱 Сканируйте камерой Telegram",
                                   fg=self._t["success"])
        except Exception as e:
            self.qr_status.config(text=f"Ошибка QR: {e}", fg=self._t["danger"])

    def set_qr_status(self, text, color):
        self.qr_status.config(text=text, fg=color)

# ─── Диалог обновления ───────────────────────────────────────────────────────
class UpdateDialog(tk.Toplevel):
    def __init__(self, parent, theme, version, url, dl_url, body):
        super().__init__(parent)
        self.title("Новая версия!")
        self.resizable(False, False)
        self.configure(bg=theme["bg"])
        t = theme
        self.transient(parent)

        tk.Label(self, text="🎉 Новая версия TG Lite!",
                 font=("Segoe UI", 16, "bold"),
                 bg=t["bg"], fg=t["accent"]).pack(pady=(20, 4))
        tk.Label(self, text=f"Версия {APP_VERSION}  →  {version}",
                 font=("Segoe UI", 12), bg=t["bg"], fg=t["text"]).pack(pady=(0, 12))

        if body:
            fr = tk.Frame(self, bg=t["input_bg"], padx=14, pady=10)
            fr.pack(fill="x", padx=24, pady=(0, 12))
            tk.Label(fr, text="Что нового:", font=("Segoe UI", 9, "bold"),
                     bg=t["input_bg"], fg=t["text_dim"]).pack(anchor="w")
            tk.Label(fr, text=body[:400], font=("Segoe UI", 9),
                     bg=t["input_bg"], fg=t["text"],
                     wraplength=340, justify="left").pack(anchor="w", pady=(4, 0))

        self.prog_var = tk.DoubleVar()
        self.prog_bar = ttk.Progressbar(self, variable=self.prog_var, maximum=100)
        self.lbl_prog = tk.Label(self, text="", font=("Segoe UI", 9),
                                  bg=t["bg"], fg=t["text_dim"])

        bf = tk.Frame(self, bg=t["bg"])
        bf.pack(pady=(0, 20))
        if dl_url:
            tk.Button(bf, text="⬇ Скачать",
                      bg=t["accent"], fg="white", relief="flat",
                      font=("Segoe UI", 11, "bold"), padx=20, pady=7,
                      command=lambda: self._download(dl_url)).pack(side="left", padx=6)
        tk.Button(bf, text="🌐 Страница релиза",
                  bg=t["input_bg"], fg=t["text"], relief="flat",
                  font=("Segoe UI", 10), padx=16, pady=7,
                  command=lambda: webbrowser.open(url)).pack(side="left", padx=6)
        tk.Button(bf, text="Позже",
                  bg=t["input_bg"], fg=t["text_dim"], relief="flat",
                  font=("Segoe UI", 10), padx=16, pady=7,
                  command=self.destroy).pack(side="left", padx=6)

    def _download(self, dl_url):
        self.prog_bar.pack(fill="x", padx=24, pady=(0, 4))
        self.lbl_prog.pack()
        threading.Thread(target=self._do_dl, args=(dl_url,), daemon=True).start()

    def _do_dl(self, dl_url):
        try:
            tmp = tempfile.mktemp(suffix=".exe")
            def hook(c, bs, ts):
                if ts > 0:
                    pct = min(100, c * bs * 100 / ts)
                    self.prog_var.set(pct)
                    self.lbl_prog.config(text=f"Скачивание... {pct:.0f}%")
            urllib.request.urlretrieve(dl_url, tmp, hook)
            self.lbl_prog.config(text="✅ Запускаю установщик...")
            import time; time.sleep(1)
            subprocess.Popen([tmp], shell=True)
            self.after(0, self.destroy)
        except Exception as e:
            self.lbl_prog.config(text=f"Ошибка: {e}")

# ─── Диалог прокси ───────────────────────────────────────────────────────────
class ProxyDialog(tk.Toplevel):
    def __init__(self, parent, cfg, theme):
        super().__init__(parent)
        self.title("Настройки прокси")
        self.resizable(False, False)
        self.configure(bg=theme["bg"])
        self._t = theme
        self._cfg = cfg
        self._build()
        self.transient(parent)
        self.grab_set()

    def _build(self):
        t = self._t
        p = self._cfg.get("proxy", {})
        f = tk.Frame(self, bg=t["bg"], padx=18, pady=14)
        f.pack(fill="both", expand=True)

        self.v_en   = tk.BooleanVar(value=p.get("enabled", False))
        self.v_type = tk.StringVar(value=p.get("type", "SOCKS5"))
        self.v_host = tk.StringVar(value=p.get("host", "127.0.0.1"))
        self.v_port = tk.StringVar(value=str(p.get("port", 1080)))
        self.v_user = tk.StringVar(value=p.get("username", ""))
        self.v_pass = tk.StringVar(value=p.get("password", ""))

        tk.Checkbutton(f, text="Включить прокси", variable=self.v_en,
                       bg=t["bg"], fg=t["text"], selectcolor=t["input_bg"],
                       activebackground=t["bg"],
                       font=("Segoe UI", 10, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        rows = [("Тип:", None), ("Хост:", self.v_host),
                ("Порт:", self.v_port), ("Логин:", self.v_user),
                ("Пароль:", self.v_pass)]
        for i, (lbl, var) in enumerate(rows, 1):
            tk.Label(f, text=lbl, bg=t["bg"], fg=t["text"],
                     font=("Segoe UI", 10)).grid(
                row=i, column=0, sticky="w", pady=5, padx=(0, 8))
            if var is None:
                ttk.Combobox(f, textvariable=self.v_type,
                             values=["SOCKS5", "SOCKS4", "HTTP"],
                             state="readonly", width=10).grid(
                    row=i, column=1, pady=5, sticky="w")
            else:
                show = "•" if lbl == "Пароль:" else ""
                tk.Entry(f, textvariable=var, show=show,
                         bg=t["input_bg"], fg=t["text"],
                         insertbackground=t["text"], relief="flat",
                         font=("Segoe UI", 10), width=22).grid(
                    row=i, column=1, pady=5, sticky="ew")

        bf = tk.Frame(f, bg=t["bg"])
        bf.grid(row=6, column=0, columnspan=2, pady=(12, 0))
        tk.Button(bf, text="Сохранить", command=self._save,
                  bg=t["accent"], fg="white", relief="flat",
                  font=("Segoe UI", 10), padx=16, pady=6).pack(side="left", padx=4)
        tk.Button(bf, text="Отмена", command=self.destroy,
                  bg=t["input_bg"], fg=t["text"], relief="flat",
                  font=("Segoe UI", 10), padx=16, pady=6).pack(side="left", padx=4)

    def _save(self):
        self._cfg["proxy"] = {
            "enabled":  self.v_en.get(),
            "type":     self.v_type.get(),
            "host":     self.v_host.get(),
            "port":     int(self.v_port.get() or 1080),
            "username": self.v_user.get(),
            "password": self.v_pass.get(),
        }
        save_config(self._cfg)
        self.destroy()
        messagebox.showinfo("Прокси", "Сохранено. Перезапустите приложение.")

# ─── Основное приложение ─────────────────────────────────────────────────────
class TGLiteApp:
    def __init__(self):
        self.cfg        = load_config()
        self.theme      = THEMES[self.cfg.get("theme", "dark")]
        self.client     = None
        self.loop       = None
        self.dialogs    = []
        self.messages   = {}
        self.unread     = {}
        self.active_peer = None
        self._tray      = None
        self._login_dlg = None

        self._build_window()
        self._start_loop()
        if HAS_TRAY:
            self._start_tray()
        self.root.after(400, self._init_session)

    # ── Окно ─────────────────────────────────────────────────────────────
    def _build_window(self):
        t = self.theme
        self.root = tk.Tk()
        self.root.title(f"{APP_NAME} v{APP_VERSION}")
        self.root.geometry("1040x700")
        self.root.minsize(820, 520)
        self.root.configure(bg=t["bg"])
        self._set_tk_icon()

        # Меню
        mb = tk.Menu(self.root, bg=t["sidebar_bg"], fg=t["text"],
                     activebackground=t["accent"], activeforeground="white",
                     relief="flat")
        self.root.config(menu=mb)

        def menu(label, parent=mb):
            m = tk.Menu(parent, tearoff=0, bg=t["sidebar_bg"], fg=t["text"],
                        activebackground=t["accent"])
            parent.add_cascade(label=label, menu=m)
            return m

        m_app = menu("TG Lite")
        m_app.add_command(label="⬆  Проверить обновления", command=self._check_update)
        m_app.add_command(label="⚙  Прокси",               command=self._proxy_dialog)
        m_app.add_command(label="🎨 Сменить тему",          command=self._toggle_theme)
        m_app.add_separator()
        m_app.add_command(label="Выход",                    command=self._quit)

        m_acc = menu("Аккаунт")
        m_acc.add_command(label="Войти / Сменить аккаунт", command=self._show_login)
        m_acc.add_command(label="Выйти из аккаунта",       command=self._logout)

        m_notif = menu("Уведомления")
        self._notif_var = tk.BooleanVar(value=self.cfg.get("notifications", True))
        m_notif.add_checkbutton(label="Включить уведомления",
                                variable=self._notif_var,
                                command=self._toggle_notif)

        m_beta = menu("Бета")
        self._beta_var = tk.BooleanVar(value=self.cfg.get("beta_channel", False))
        m_beta.add_checkbutton(label="Бета-канал обновлений",
                               variable=self._beta_var,
                               command=self._toggle_beta)
        m_beta.add_command(label="ℹ  О бета-канале", command=self._beta_info)

        # Layout
        paned = tk.PanedWindow(self.root, orient="horizontal",
                               bg=t["border"], sashwidth=2, sashrelief="flat")
        paned.pack(fill="both", expand=True)

        # ── Сайдбар ──────────────────────────────────────────────────────
        sidebar = tk.Frame(paned, bg=t["sidebar_bg"], width=290)
        paned.add(sidebar, minsize=220)

        head = tk.Frame(sidebar, bg=t["sidebar_bg"], pady=10)
        head.pack(fill="x", padx=12)
        self.lbl_me = tk.Label(head, text=APP_NAME,
                               font=("Segoe UI", 14, "bold"),
                               bg=t["sidebar_bg"], fg=t["accent"])
        self.lbl_me.pack(side="left")
        tk.Label(head, text=f"v{APP_VERSION}",
                 font=("Segoe UI", 8),
                 bg=t["sidebar_bg"], fg=t["text_dim"]).pack(side="left", padx=4)
        self.lbl_status = tk.Label(head, text="●",
                                   font=("Segoe UI", 14),
                                   bg=t["sidebar_bg"], fg=t["text_dim"])
        self.lbl_status.pack(side="right")

        sf = tk.Frame(sidebar, bg=t["sidebar_bg"], padx=10, pady=4)
        sf.pack(fill="x")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._render_chat_list())
        tk.Entry(sf, textvariable=self.search_var,
                 bg=t["input_bg"], fg=t["text"],
                 insertbackground=t["text"], relief="flat",
                 font=("Segoe UI", 10),
                 ).pack(fill="x", ipady=5)

        self.chat_canvas = tk.Canvas(sidebar, bg=t["sidebar_bg"], highlightthickness=0)
        self.chat_canvas.pack(fill="both", expand=True, side="left")
        sb = ttk.Scrollbar(sidebar, orient="vertical", command=self.chat_canvas.yview)
        sb.pack(side="right", fill="y")
        self.chat_canvas.configure(yscrollcommand=sb.set)
        self.chat_frame = tk.Frame(self.chat_canvas, bg=t["sidebar_bg"])
        self.chat_canvas.create_window((0, 0), window=self.chat_frame, anchor="nw")
        self.chat_frame.bind("<Configure>",
            lambda e: self.chat_canvas.configure(
                scrollregion=self.chat_canvas.bbox("all")))

        # ── Панель чата ───────────────────────────────────────────────────
        chat_panel = tk.Frame(paned, bg=t["chat_bg"])
        paned.add(chat_panel, minsize=420)

        self.chat_header = tk.Frame(chat_panel, bg=t["sidebar_bg"], pady=10)
        self.chat_header.pack(fill="x")
        self.lbl_chat_name = tk.Label(self.chat_header, text="Выберите чат",
                                      font=("Segoe UI", 13, "bold"),
                                      bg=t["sidebar_bg"], fg=t["text"])
        self.lbl_chat_name.pack(side="left", padx=14)
        self.lbl_chat_info = tk.Label(self.chat_header, text="",
                                      font=("Segoe UI", 9),
                                      bg=t["sidebar_bg"], fg=t["text_dim"])
        self.lbl_chat_info.pack(side="left")

        msg_outer = tk.Frame(chat_panel, bg=t["chat_bg"])
        msg_outer.pack(fill="both", expand=True)
        self.msg_canvas = tk.Canvas(msg_outer, bg=t["chat_bg"], highlightthickness=0)
        self.msg_canvas.pack(fill="both", expand=True, side="left")
        msg_sb = ttk.Scrollbar(msg_outer, orient="vertical",
                               command=self.msg_canvas.yview)
        msg_sb.pack(side="right", fill="y")
        self.msg_canvas.configure(yscrollcommand=msg_sb.set)
        self.msg_frame = tk.Frame(self.msg_canvas, bg=t["chat_bg"])
        self.msg_canvas.create_window((0, 0), window=self.msg_frame, anchor="nw")
        self.msg_frame.bind("<Configure>",
            lambda e: self.msg_canvas.configure(
                scrollregion=self.msg_canvas.bbox("all")))
        self.msg_canvas.bind("<Configure>", self._on_canvas_resize)

        inp = tk.Frame(chat_panel, bg=t["input_bg"], pady=8)
        inp.pack(fill="x")
        self.msg_input = tk.Text(inp, height=3,
                                  bg=t["input_bg"], fg=t["text"],
                                  insertbackground=t["text"],
                                  relief="flat", font=("Segoe UI", 11),
                                  wrap="word", padx=10, pady=6)
        self.msg_input.pack(side="left", fill="both", expand=True, padx=(10, 4))
        self.msg_input.bind("<Return>", self._on_enter)
        tk.Button(inp, text="▶", font=("Segoe UI", 16),
                  bg=t["accent"], fg="white", relief="flat",
                  activebackground=t["accent"],
                  command=self._send_message,
                  width=3, height=2).pack(side="right", padx=(0, 10))

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _set_tk_icon(self):
        try:
            if HAS_TRAY:
                img = make_pil_icon(32)
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                photo = tk.PhotoImage(data=base64.b64encode(buf.getvalue()))
                self.root.iconphoto(True, photo)
        except Exception:
            pass

    # ── Asyncio ───────────────────────────────────────────────────────────
    def _start_loop(self):
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self.loop.run_forever, daemon=True).start()

    def run_async(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    # ── Трей ─────────────────────────────────────────────────────────────
    def _start_tray(self):
        try:
            img  = make_pil_icon(64)
            menu = pystray.Menu(
                pystray.MenuItem("Открыть TG Lite", self._tray_show, default=True),
                pystray.MenuItem("Проверить обновления",
                                 lambda *_: self.root.after(0, self._check_update)),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Выход", self._quit),
            )
            self._tray = pystray.Icon("tglite", img, APP_NAME, menu)
            threading.Thread(target=self._tray.run, daemon=True).start()
        except Exception as e:
            print(f"Трей: {e}")

    def _tray_show(self, *_):
        self.root.after(0, lambda: (self.root.deiconify(), self.root.lift()))

    def _on_close(self):
        if self.cfg.get("tray_on_close") and HAS_TRAY and self._tray:
            self.root.withdraw()
        else:
            self._quit()

    # ── Уведомления ───────────────────────────────────────────────────────
    def _notify(self, title, message):
        if not self._notif_var.get():
            return
        if HAS_PLYER:
            try:
                plyer_notify.notify(title=title, message=message[:100],
                                    app_name=APP_NAME, timeout=5)
            except Exception:
                pass

    def _toggle_notif(self):
        self.cfg["notifications"] = self._notif_var.get()
        save_config(self.cfg)

    def _toggle_beta(self):
        self.cfg["beta_channel"] = self._beta_var.get()
        save_config(self.cfg)
        state = "включён" if self._beta_var.get() else "выключен"
        messagebox.showinfo("Бета-канал", f"Бета-канал {state}.")

    def _beta_info(self):
        messagebox.showinfo("Бета-канал",
            "Бета-канал позволяет получать обновления раньше всех.\n\n"
            "Бета-версии могут содержать ошибки.\n"
            "Используйте на свой риск.")

    # ── Сессия ───────────────────────────────────────────────────────────
    def _init_session(self):
        if not self.cfg.get("api_id") or not self.cfg.get("api_hash"):
            self._show_login()
        else:
            self.run_async(self._async_connect())

    async def _async_connect(self):
        try:
            self.client = TelegramClient(
                str(SESSION_DIR / "tglite"),
                int(self.cfg["api_id"]),
                self.cfg["api_hash"],
                proxy=get_proxy(self.cfg),
                loop=self.loop
            )
            await self.client.connect()
            if not await self.client.is_user_authorized():
                self.root.after(0, self._show_login)
                return
            await self._post_auth()
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Ошибка", str(e)))

    async def _post_auth(self):
        me   = await self.client.get_me()
        name = peer_display(me)
        self.root.after(0, lambda: (
            self.lbl_me.config(text=name),
            self.lbl_status.config(fg=self.theme["online"])
        ))
        self.client.add_event_handler(self._on_new_message, events.NewMessage)
        await self._load_dialogs()
        self.root.after(5000, lambda: self.run_async(self._check_update_silent()))

    # ── Вход ─────────────────────────────────────────────────────────────
    def _show_login(self):
        if self._login_dlg and self._login_dlg.winfo_exists():
            self._login_dlg.lift()
            return
        self._login_dlg = LoginDialog(self.root, self.theme, self._on_login_submit)

    def _on_login_submit(self, result, dlg):
        self.cfg["api_id"]   = result["api_id"]
        self.cfg["api_hash"] = result["api_hash"]
        if result.get("phone"):
            self.cfg["phone"] = result["phone"]
        save_config(self.cfg)
        if result["mode"] == "qr":
            self.run_async(self._qr_login(dlg))
        else:
            self.run_async(self._phone_login(result, dlg))

    async def _qr_login(self, dlg):
        try:
            self.client = TelegramClient(
                str(SESSION_DIR / "tglite"),
                int(self.cfg["api_id"]), self.cfg["api_hash"],
                proxy=get_proxy(self.cfg), loop=self.loop)
            await self.client.connect()
            qr = await self.client(ExportLoginTokenRequest(
                api_id=int(self.cfg["api_id"]),
                api_hash=self.cfg["api_hash"], except_ids=[]))
            self.root.after(0, lambda: dlg.show_qr(qr.token))
            for _ in range(24):
                await asyncio.sleep(5)
                if await self.client.is_user_authorized():
                    self.root.after(0, lambda: dlg.set_qr_status("✅ Успешно!", self.theme["success"]))
                    await asyncio.sleep(1)
                    self.root.after(0, dlg.destroy)
                    await self._post_auth()
                    return
                try:
                    qr = await self.client(ExportLoginTokenRequest(
                        api_id=int(self.cfg["api_id"]),
                        api_hash=self.cfg["api_hash"], except_ids=[]))
                    self.root.after(0, lambda t=qr.token: dlg.show_qr(t))
                except Exception:
                    pass
            self.root.after(0, lambda: dlg.set_qr_status(
                "⏰ Время истекло", self.theme["danger"]))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("QR ошибка", str(e)))

    async def _phone_login(self, result, dlg):
        try:
            self.client = TelegramClient(
                str(SESSION_DIR / "tglite"),
                int(self.cfg["api_id"]), self.cfg["api_hash"],
                proxy=get_proxy(self.cfg), loop=self.loop)
            await self.client.connect()
            await self.client.send_code_request(result["phone"])
            self.root.after(0, lambda: self._ask_code(result, dlg))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Ошибка", str(e)))

    def _ask_code(self, result, dlg):
        code = simpledialog.askstring("Код", "Введите код из Telegram:",
                                      parent=dlg or self.root)
        if code:
            self.run_async(self._sign_in(result, code, dlg))

    async def _sign_in(self, result, code, dlg):
        try:
            await self.client.sign_in(result["phone"], code)
            self.root.after(0, dlg.destroy)
            await self._post_auth()
        except SessionPasswordNeededError:
            pwd = result.get("password") or ""
            if not pwd:
                self.root.after(0, lambda: self._ask_2fa(dlg))
            else:
                await self._do_2fa(pwd, dlg)
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Ошибка", str(e)))

    def _ask_2fa(self, dlg):
        pwd = simpledialog.askstring("2FA", "Введите пароль:",
                                     show="•", parent=dlg or self.root)
        if pwd:
            self.run_async(self._do_2fa(pwd, dlg))

    async def _do_2fa(self, pwd, dlg):
        try:
            await self.client.sign_in(password=pwd)
            self.root.after(0, dlg.destroy)
            await self._post_auth()
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("2FA ошибка", str(e)))

    # ── Чаты ─────────────────────────────────────────────────────────────
    async def _load_dialogs(self):
        try:
            raw = await self.client.get_dialogs(limit=50)
            self.dialogs = []
            for d in raw:
                self.dialogs.append({
                    "id": d.id, "entity": d.entity,
                    "name": peer_display(d.entity),
                    "last_msg": (d.message.message or "[медиа]")[:50] if d.message else "",
                    "last_time": d.message.date if d.message else None,
                    "unread": d.unread_count or 0,
                })
                self.unread[d.id] = d.unread_count or 0
            self.root.after(0, self._render_chat_list)
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Ошибка", str(e)))

    def _render_chat_list(self):
        t  = self.theme
        ft = self.search_var.get().lower()
        for w in self.chat_frame.winfo_children():
            w.destroy()
        items = [d for d in self.dialogs if ft in d["name"].lower()] if ft else self.dialogs
        for d in items:
            self._chat_item(d, t)

    def _chat_item(self, d, t):
        is_act = (self.active_peer and
                  getattr(self.active_peer, "id", None) == d["id"])
        bg  = t["hover"] if is_act else t["sidebar_bg"]
        row = tk.Frame(self.chat_frame, bg=bg, cursor="hand2")
        row.pack(fill="x", pady=1)

        av = tk.Label(row, text=peer_initials(d["name"]),
                      font=("Segoe UI", 11, "bold"),
                      bg=t["accent"], fg="white", width=3)
        av.pack(side="left", padx=(8, 8), pady=6)

        info = tk.Frame(row, bg=bg)
        info.pack(side="left", fill="both", expand=True)
        tk.Label(info, text=d["name"], font=("Segoe UI", 11, "bold"),
                 bg=bg, fg=t["text"], anchor="w").pack(fill="x")
        tk.Label(info, text=d["last_msg"], font=("Segoe UI", 9),
                 bg=bg, fg=t["text_dim"], anchor="w").pack(fill="x")

        right = tk.Frame(row, bg=bg)
        right.pack(side="right", padx=(0, 8), pady=6)
        tk.Label(right, text=format_time(d.get("last_time")),
                 font=("Segoe UI", 8), bg=bg, fg=t["text_dim"]).pack()
        uc = self.unread.get(d["id"], 0)
        if uc > 0:
            tk.Label(right, text=str(uc),
                     bg=t["unread_bg"], fg="white",
                     font=("Segoe UI", 8, "bold"),
                     padx=5, pady=1).pack()

        entity = d["entity"]
        for w in (row, av, info, right):
            w.bind("<Button-1>", lambda e, en=entity: self._open_chat(en))
        for child in list(info.winfo_children()) + list(right.winfo_children()):
            child.bind("<Button-1>", lambda e, en=entity: self._open_chat(en))

    def _open_chat(self, entity):
        self.active_peer = entity
        self.lbl_chat_name.config(text=peer_display(entity))
        self.lbl_chat_info.config(
            text="канал" if isinstance(entity, Channel) else
                 "группа" if isinstance(entity, Chat) else "")
        self.unread[entity.id] = 0
        self._render_chat_list()
        self.run_async(self._load_messages(entity))

    async def _load_messages(self, entity):
        try:
            raw  = await self.client.get_messages(entity, limit=50)
            msgs = []
            for m in reversed(raw):
                msgs.append({
                    "id": m.id, "text": m.message or "[медиа]",
                    "sender": peer_display(m.sender) if m.sender else "",
                    "date": m.date, "out": m.out,
                })
            self.messages[entity.id] = msgs
            self.root.after(0, lambda: self._render_messages(entity.id))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Ошибка", str(e)))

    def _render_messages(self, pid):
        t = self.theme
        for w in self.msg_frame.winfo_children():
            w.destroy()
        for m in self.messages.get(pid, []):
            self._bubble(m, t)
        self.msg_frame.update_idletasks()
        self.msg_canvas.yview_moveto(1.0)

    def _bubble(self, m, t):
        is_out = m.get("out", False)
        color  = t["bubble_me"] if is_out else t["bubble_them"]
        row = tk.Frame(self.msg_frame, bg=t["chat_bg"])
        row.pack(fill="x", pady=2, padx=10)
        inner = tk.Frame(row, bg=t["chat_bg"])
        inner.pack(side="right" if is_out else "left")
        if not is_out and m.get("sender"):
            tk.Label(inner, text=m["sender"],
                     font=("Segoe UI", 8, "bold"),
                     bg=t["chat_bg"], fg=t["accent"]).pack(anchor="w")
        bbl = tk.Frame(inner, bg=color, padx=10, pady=6)
        bbl.pack(anchor="e" if is_out else "w")
        w = max(200, int((self.msg_canvas.winfo_width() or 600) * 0.65))
        tk.Label(bbl, text=m["text"], bg=color, fg=t["text"],
                 font=("Segoe UI", 11), wraplength=w,
                 justify="left", anchor="w").pack(anchor="w")
        tk.Label(bbl, text=format_time(m.get("date")),
                 bg=color, fg=t["text_dim"],
                 font=("Segoe UI", 8)).pack(anchor="e")

    def _on_canvas_resize(self, event):
        if self.active_peer:
            pid = getattr(self.active_peer, "id", None)
            if pid and pid in self.messages:
                self._render_messages(pid)

    # ── Отправка ─────────────────────────────────────────────────────────
    def _on_enter(self, event):
        if event.state & 0x1:
            return
        self._send_message()
        return "break"

    def _send_message(self):
        if not self.active_peer:
            return
        text = self.msg_input.get("1.0", "end").strip()
        if not text:
            return
        self.msg_input.delete("1.0", "end")
        self.run_async(self._async_send(self.active_peer, text))

    async def _async_send(self, entity, text):
        try:
            msg = await self.client.send_message(entity, text)
            m   = {"id": msg.id, "text": text, "sender": "Вы",
                   "date": msg.date, "out": True}
            self.messages.setdefault(entity.id, []).append(m)
            self.root.after(0, lambda: self._render_messages(entity.id))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Ошибка", str(e)))

    # ── Входящие ─────────────────────────────────────────────────────────
    async def _on_new_message(self, event):
        msg    = event.message
        pid    = event.chat_id
        sender = ""
        try:
            se = await msg.get_sender()
            if se:
                sender = peer_display(se)
        except Exception:
            pass
        m = {"id": msg.id, "text": msg.message or "[медиа]",
             "sender": sender, "date": msg.date, "out": msg.out}
        self.messages.setdefault(pid, []).append(m)
        if self.active_peer and getattr(self.active_peer, "id", None) == pid:
            self.root.after(0, lambda: self._render_messages(pid))
        else:
            self.unread[pid] = self.unread.get(pid, 0) + 1
            self.root.after(0, self._render_chat_list)
            if sender and msg.message:
                self._notify(sender, msg.message[:80])
        for d in self.dialogs:
            if d["id"] == pid:
                d["last_msg"]  = (msg.message or "[медиа]")[:50]
                d["last_time"] = msg.date
                break

    # ── Обновления ────────────────────────────────────────────────────────
    def _check_update(self):
        self.run_async(self._async_check_update(silent=False))

    async def _check_update_silent(self):
        await self._async_check_update(silent=True)

    async def _async_check_update(self, silent=False):
        try:
            repo     = self.cfg.get("github_repo", "YOUR_USER/tglite")
            beta     = self.cfg.get("beta_channel", False)
            endpoint = (f"https://api.github.com/repos/{repo}/releases"
                        if beta else
                        f"https://api.github.com/repos/{repo}/releases/latest")
            req  = urllib.request.Request(
                endpoint, headers={"User-Agent": "TGLite"})
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read())
            release  = data[0] if isinstance(data, list) and data else data
            latest   = release.get("tag_name", "").lstrip("v")
            page_url = release.get("html_url", "")
            body     = release.get("body", "")
            dl_url   = next(
                (a["browser_download_url"] for a in release.get("assets", [])
                 if a["name"].lower().endswith(".exe")), "")
            if ver_tuple(latest) > ver_tuple(APP_VERSION):
                self.root.after(0, lambda: UpdateDialog(
                    self.root, self.theme, latest, page_url, dl_url, body))
                if HAS_TRAY and self._tray:
                    self._tray.icon = make_pil_icon(64, has_dot=True)
            elif not silent:
                self.root.after(0, lambda: messagebox.showinfo(
                    "Обновления", f"Актуальная версия {APP_VERSION} ✅"))
        except Exception as e:
            if not silent:
                self.root.after(0, lambda: messagebox.showwarning(
                    "Обновления", f"Не удалось проверить:\n{e}"))

    # ── Прочее ───────────────────────────────────────────────────────────
    def _proxy_dialog(self):
        ProxyDialog(self.root, self.cfg, self.theme)

    def _toggle_theme(self):
        new = "light" if self.cfg.get("theme") == "dark" else "dark"
        self.cfg["theme"] = new
        save_config(self.cfg)
        messagebox.showinfo("Тема", f"Тема: {new}.\nПерезапустите приложение.")

    def _logout(self):
        if messagebox.askyesno("Выход", "Выйти из аккаунта?"):
            self.run_async(self._async_logout())

    async def _async_logout(self):
        try:
            if self.client:
                await self.client.log_out()
            s = SESSION_DIR / "tglite.session"
            if s.exists():
                s.unlink()
        except Exception:
            pass
        self.root.after(0, lambda: self.lbl_status.config(fg=self.theme["text_dim"]))

    def _quit(self, *_):
        try:
            if self._tray:
                self._tray.stop()
            if self.client:
                self.run_async(self.client.disconnect())
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass
        sys.exit(0)

    def run(self):
        self.root.mainloop()


def main():
    app = TGLiteApp()
    app.run()


if __name__ == "__main__":
    main()
