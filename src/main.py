"""
TG Lite — лёгкий Telegram клиент с поддержкой прокси
Использует Telethon (MTProto API)
"""

import sys
import os
import asyncio
import threading
import json
import logging
from datetime import datetime
from pathlib import Path

# GUI
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog

# Telegram
from telethon import TelegramClient, events
from telethon.tl.types import User, Chat, Channel
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError

# Proxy
import socks

# ─── Константы ──────────────────────────────────────────────────────────────
APP_NAME    = "TG Lite"
APP_VERSION = "1.0.0"
CONFIG_FILE = Path.home() / ".tglite" / "config.json"
SESSION_DIR = Path.home() / ".tglite"
SESSION_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.WARNING)

# ─── Конфигурация ────────────────────────────────────────────────────────────
DEFAULT_CONFIG = {
    "api_id": "",
    "api_hash": "",
    "phone": "",
    "proxy": {
        "enabled": False,
        "type": "SOCKS5",
        "host": "127.0.0.1",
        "port": 1080,
        "username": "",
        "password": ""
    },
    "theme": "dark",
    "font_size": 13
}

def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                cfg = json.load(f)
            # merge defaults
            for k, v in DEFAULT_CONFIG.items():
                if k not in cfg:
                    cfg[k] = v
            return cfg
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()

def save_config(cfg: dict):
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

# ─── Цветовые схемы ──────────────────────────────────────────────────────────
THEMES = {
    "dark": {
        "bg":          "#17212b",
        "sidebar_bg":  "#0d1117",
        "chat_bg":     "#0f1923",
        "bubble_me":   "#2b5278",
        "bubble_them": "#182533",
        "text":        "#e8eaed",
        "text_dim":    "#7a8f9e",
        "accent":      "#5a9fd4",
        "input_bg":    "#1c2a38",
        "border":      "#2a3b4c",
        "online":      "#4caf50",
        "unread_bg":   "#5a9fd4",
        "hover":       "#1e2f3e",
    },
    "light": {
        "bg":          "#f5f5f5",
        "sidebar_bg":  "#ffffff",
        "chat_bg":     "#f0f2f5",
        "bubble_me":   "#dcf8c6",
        "bubble_them": "#ffffff",
        "text":        "#111111",
        "text_dim":    "#777777",
        "accent":      "#0088cc",
        "input_bg":    "#ffffff",
        "border":      "#dddddd",
        "online":      "#4caf50",
        "unread_bg":   "#0088cc",
        "hover":       "#e8e8e8",
    }
}

# ─── Вспомогательные функции ─────────────────────────────────────────────────
def get_proxy_settings(cfg: dict):
    p = cfg.get("proxy", {})
    if not p.get("enabled"):
        return None
    ptype = {"SOCKS5": socks.SOCKS5, "SOCKS4": socks.SOCKS4, "HTTP": socks.HTTP}.get(p["type"], socks.SOCKS5)
    return (ptype, p["host"], int(p["port"]),
            True,
            p.get("username") or None,
            p.get("password") or None)

def format_time(dt):
    if dt is None:
        return ""
    now = datetime.now()
    if dt.date() == now.date():
        return dt.strftime("%H:%M")
    return dt.strftime("%d.%m")

def peer_display(entity):
    if isinstance(entity, User):
        name = (entity.first_name or "") + (" " + entity.last_name if entity.last_name else "")
        return name.strip() or entity.username or str(entity.id)
    if hasattr(entity, "title"):
        return entity.title
    return str(entity.id)

def peer_initials(name: str) -> str:
    parts = name.split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    return name[:2].upper() if name else "??"

# ─── Диалог настроек прокси ──────────────────────────────────────────────────
class ProxyDialog(tk.Toplevel):
    def __init__(self, parent, cfg: dict, theme: dict):
        super().__init__(parent)
        self.title("Настройки прокси")
        self.resizable(False, False)
        self.configure(bg=theme["bg"])
        self.result = None
        self._cfg = cfg
        self._t = theme
        self._build()
        self.transient(parent)
        self.grab_set()

    def _lbl(self, frame, text, row, col=0):
        tk.Label(frame, text=text, bg=self._t["bg"], fg=self._t["text"],
                 font=("Segoe UI", 10)).grid(row=row, column=col, sticky="w", pady=4, padx=6)

    def _ent(self, frame, var, row, col=1, width=22):
        e = tk.Entry(frame, textvariable=var, bg=self._t["input_bg"], fg=self._t["text"],
                     insertbackground=self._t["text"], relief="flat",
                     font=("Segoe UI", 10), width=width)
        e.grid(row=row, column=col, pady=4, padx=6, sticky="ew")
        return e

    def _build(self):
        p = self._cfg.get("proxy", DEFAULT_CONFIG["proxy"])
        frame = tk.Frame(self, bg=self._t["bg"], padx=16, pady=12)
        frame.pack(fill="both", expand=True)

        self.v_enabled  = tk.BooleanVar(value=p.get("enabled", False))
        self.v_type     = tk.StringVar(value=p.get("type", "SOCKS5"))
        self.v_host     = tk.StringVar(value=p.get("host", "127.0.0.1"))
        self.v_port     = tk.StringVar(value=str(p.get("port", 1080)))
        self.v_user     = tk.StringVar(value=p.get("username", ""))
        self.v_pass     = tk.StringVar(value=p.get("password", ""))

        tk.Checkbutton(frame, text="Включить прокси",
                       variable=self.v_enabled,
                       bg=self._t["bg"], fg=self._t["text"],
                       selectcolor=self._t["input_bg"],
                       activebackground=self._t["bg"],
                       font=("Segoe UI", 10, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        self._lbl(frame, "Тип:", 1)
        cb = ttk.Combobox(frame, textvariable=self.v_type,
                          values=["SOCKS5", "SOCKS4", "HTTP"],
                          state="readonly", width=10)
        cb.grid(row=1, column=1, pady=4, padx=6, sticky="w")

        self._lbl(frame, "Хост:", 2)
        self._ent(frame, self.v_host, 2)
        self._lbl(frame, "Порт:", 3)
        self._ent(frame, self.v_port, 3, width=8)
        self._lbl(frame, "Логин (опц.):", 4)
        self._ent(frame, self.v_user, 4)
        self._lbl(frame, "Пароль (опц.):", 5)
        e = self._ent(frame, self.v_pass, 5)
        e.config(show="•")

        btn_frame = tk.Frame(frame, bg=self._t["bg"])
        btn_frame.grid(row=6, column=0, columnspan=2, pady=(12, 0))
        tk.Button(btn_frame, text="Сохранить", command=self._save,
                  bg=self._t["accent"], fg="white", relief="flat",
                  font=("Segoe UI", 10), padx=16).pack(side="left", padx=4)
        tk.Button(btn_frame, text="Отмена", command=self.destroy,
                  bg=self._t["bubble_them"], fg=self._t["text"], relief="flat",
                  font=("Segoe UI", 10), padx=16).pack(side="left", padx=4)

    def _save(self):
        self.result = {
            "enabled":  self.v_enabled.get(),
            "type":     self.v_type.get(),
            "host":     self.v_host.get(),
            "port":     int(self.v_port.get() or 1080),
            "username": self.v_user.get(),
            "password": self.v_pass.get(),
        }
        self.destroy()

# ─── Диалог авторизации ──────────────────────────────────────────────────────
class AuthDialog(tk.Toplevel):
    def __init__(self, parent, theme):
        super().__init__(parent)
        self.title(f"{APP_NAME} — Вход")
        self.resizable(False, False)
        self.configure(bg=theme["bg"])
        self._t = theme
        self.result = None
        self._build()
        self.transient(parent)
        self.grab_set()

    def _build(self):
        t = self._t
        frame = tk.Frame(self, bg=t["bg"], padx=24, pady=20)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text="✈ TG Lite", font=("Segoe UI", 20, "bold"),
                 bg=t["bg"], fg=t["accent"]).pack(pady=(0, 4))
        tk.Label(frame, text="Войдите через Telegram API",
                 font=("Segoe UI", 10), bg=t["bg"], fg=t["text_dim"]).pack(pady=(0, 16))

        def row(lbl, var, show=""):
            f = tk.Frame(frame, bg=t["bg"])
            f.pack(fill="x", pady=4)
            tk.Label(f, text=lbl, bg=t["bg"], fg=t["text"],
                     font=("Segoe UI", 10), width=12, anchor="w").pack(side="left")
            e = tk.Entry(f, textvariable=var, bg=t["input_bg"], fg=t["text"],
                         insertbackground=t["text"], relief="flat",
                         font=("Segoe UI", 11), width=28, show=show)
            e.pack(side="left", ipady=4, padx=(4, 0))
            return e

        self.v_api_id   = tk.StringVar()
        self.v_api_hash = tk.StringVar()
        self.v_phone    = tk.StringVar()

        row("API ID:", self.v_api_id)
        row("API Hash:", self.v_api_hash)
        row("Телефон:", self.v_phone)

        tk.Label(frame, text="Получите API ID и Hash на my.telegram.org",
                 font=("Segoe UI", 8), bg=t["bg"], fg=t["text_dim"]).pack(pady=(8, 0))

        tk.Button(frame, text="Далее →", command=self._ok,
                  bg=t["accent"], fg="white", relief="flat",
                  font=("Segoe UI", 11, "bold"), padx=24, pady=6).pack(pady=(16, 0))

    def _ok(self):
        self.result = {
            "api_id":   self.v_api_id.get().strip(),
            "api_hash": self.v_api_hash.get().strip(),
            "phone":    self.v_phone.get().strip()
        }
        self.destroy()

# ─── Основное приложение ─────────────────────────────────────────────────────
class TGLiteApp:
    def __init__(self):
        self.cfg    = load_config()
        self.theme  = THEMES[self.cfg.get("theme", "dark")]
        self.client = None
        self.loop   = None
        self.loop_thread = None

        self.dialogs      = []   # список чатов
        self.active_peer  = None
        self.messages     = {}   # peer_id -> list[dict]
        self.unread       = {}   # peer_id -> int

        self._build_window()
        self._start_event_loop()

        # Если нет credentials — показать диалог входа
        if not self.cfg.get("api_id") or not self.cfg.get("api_hash"):
            self.root.after(300, self._show_auth_dialog)
        else:
            self.root.after(300, self._connect)

    # ── Построение интерфейса ─────────────────────────────────────────────
    def _build_window(self):
        t = self.theme
        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self.root.geometry("1000x680")
        self.root.minsize(800, 500)
        self.root.configure(bg=t["bg"])

        # Меню
        menubar = tk.Menu(self.root, bg=t["sidebar_bg"], fg=t["text"],
                          activebackground=t["accent"], activeforeground="white",
                          relief="flat")
        self.root.config(menu=menubar)

        m_app = tk.Menu(menubar, tearoff=0, bg=t["sidebar_bg"], fg=t["text"],
                        activebackground=t["accent"])
        menubar.add_cascade(label="TG Lite", menu=m_app)
        m_app.add_command(label="Настройки прокси", command=self._open_proxy_settings)
        m_app.add_command(label="Сменить тему", command=self._toggle_theme)
        m_app.add_separator()
        m_app.add_command(label="Выход", command=self._quit)

        m_acc = tk.Menu(menubar, tearoff=0, bg=t["sidebar_bg"], fg=t["text"],
                        activebackground=t["accent"])
        menubar.add_cascade(label="Аккаунт", menu=m_acc)
        m_acc.add_command(label="Войти / Сменить аккаунт", command=self._show_auth_dialog)
        m_acc.add_command(label="Выйти из аккаунта", command=self._logout)

        # Главный layout
        paned = tk.PanedWindow(self.root, orient="horizontal",
                               bg=t["border"], sashwidth=2, sashrelief="flat")
        paned.pack(fill="both", expand=True)

        # ── Сайдбар ──
        sidebar = tk.Frame(paned, bg=t["sidebar_bg"], width=280)
        paned.add(sidebar, minsize=220)

        # Заголовок сайдбара
        sidebar_head = tk.Frame(sidebar, bg=t["sidebar_bg"], pady=10)
        sidebar_head.pack(fill="x", padx=10)

        self.lbl_me = tk.Label(sidebar_head, text=APP_NAME,
                               font=("Segoe UI", 14, "bold"),
                               bg=t["sidebar_bg"], fg=t["accent"])
        self.lbl_me.pack(side="left")

        # Статус подключения
        self.lbl_status = tk.Label(sidebar_head, text="●",
                                   font=("Segoe UI", 14),
                                   bg=t["sidebar_bg"], fg=t["text_dim"])
        self.lbl_status.pack(side="right")

        # Поиск
        search_frame = tk.Frame(sidebar, bg=t["sidebar_bg"], padx=10, pady=4)
        search_frame.pack(fill="x")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self._on_search)
        search_entry = tk.Entry(search_frame, textvariable=self.search_var,
                                bg=t["input_bg"], fg=t["text"],
                                insertbackground=t["text"], relief="flat",
                                font=("Segoe UI", 10), width=28)
        search_entry.pack(fill="x", ipady=5, padx=2)
        tk.Label(search_frame, text="🔍", bg=t["input_bg"], fg=t["text_dim"],
                 font=("Segoe UI", 10)).place(relx=1.0, rely=0.5, anchor="e", x=-8)

        # Список чатов
        self.chat_canvas = tk.Canvas(sidebar, bg=t["sidebar_bg"], highlightthickness=0)
        self.chat_canvas.pack(fill="both", expand=True)
        chat_scroll = ttk.Scrollbar(sidebar, orient="vertical",
                                    command=self.chat_canvas.yview)
        self.chat_canvas.configure(yscrollcommand=chat_scroll.set)
        chat_scroll.pack(side="right", fill="y")
        self.chat_frame = tk.Frame(self.chat_canvas, bg=t["sidebar_bg"])
        self.chat_canvas.create_window((0, 0), window=self.chat_frame, anchor="nw")
        self.chat_frame.bind("<Configure>",
            lambda e: self.chat_canvas.configure(
                scrollregion=self.chat_canvas.bbox("all")))

        # ── Панель чата ──
        chat_panel = tk.Frame(paned, bg=t["chat_bg"])
        paned.add(chat_panel, minsize=400)

        # Заголовок чата
        self.chat_header = tk.Frame(chat_panel, bg=t["sidebar_bg"], pady=10)
        self.chat_header.pack(fill="x")

        self.lbl_chat_name = tk.Label(self.chat_header, text="Выберите чат",
                                      font=("Segoe UI", 13, "bold"),
                                      bg=t["sidebar_bg"], fg=t["text"])
        self.lbl_chat_name.pack(side="left", padx=14)

        self.lbl_chat_info = tk.Label(self.chat_header, text="",
                                      font=("Segoe UI", 9),
                                      bg=t["sidebar_bg"], fg=t["text_dim"])
        self.lbl_chat_info.pack(side="left", padx=2)

        # Область сообщений
        self.msg_canvas = tk.Canvas(chat_panel, bg=t["chat_bg"], highlightthickness=0)
        self.msg_canvas.pack(fill="both", expand=True, side="left")
        msg_scroll = ttk.Scrollbar(chat_panel, orient="vertical",
                                   command=self.msg_canvas.yview)
        msg_scroll.pack(side="right", fill="y")
        self.msg_canvas.configure(yscrollcommand=msg_scroll.set)
        self.msg_frame = tk.Frame(self.msg_canvas, bg=t["chat_bg"])
        self.msg_canvas.create_window((0, 0), window=self.msg_frame, anchor="nw")
        self.msg_frame.bind("<Configure>",
            lambda e: self.msg_canvas.configure(
                scrollregion=self.msg_canvas.bbox("all")))
        self.msg_canvas.bind("<Configure>", self._on_canvas_resize)

        # Поле ввода
        input_frame = tk.Frame(chat_panel, bg=t["input_bg"], pady=8)
        input_frame.pack(fill="x", side="bottom", padx=0)

        self.msg_input = tk.Text(input_frame, height=3,
                                 bg=t["input_bg"], fg=t["text"],
                                 insertbackground=t["text"],
                                 relief="flat", font=("Segoe UI", 11),
                                 wrap="word", padx=10, pady=6)
        self.msg_input.pack(side="left", fill="both", expand=True, padx=(10, 4))
        self.msg_input.bind("<Return>", self._on_enter)
        self.msg_input.bind("<Shift-Return>", lambda e: None)

        send_btn = tk.Button(input_frame, text="▶",
                             font=("Segoe UI", 16),
                             bg=t["accent"], fg="white", relief="flat",
                             activebackground=t["accent"],
                             command=self._send_message,
                             width=3, height=2)
        send_btn.pack(side="right", padx=(0, 10))

        self.root.protocol("WM_DELETE_WINDOW", self._quit)

    # ── Цикл событий asyncio в отдельном потоке ───────────────────────────
    def _start_event_loop(self):
        self.loop = asyncio.new_event_loop()
        self.loop_thread = threading.Thread(target=self._run_loop, daemon=True)
        self.loop_thread.start()

    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def run_async(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    # ── Подключение ───────────────────────────────────────────────────────
    def _connect(self):
        self.run_async(self._async_connect())

    async def _async_connect(self):
        try:
            proxy = get_proxy_settings(self.cfg)
            session_path = str(SESSION_DIR / "tglite")
            self.client = TelegramClient(
                session_path,
                int(self.cfg["api_id"]),
                self.cfg["api_hash"],
                proxy=proxy,
                loop=self.loop
            )
            await self.client.connect()

            if not await self.client.is_user_authorized():
                self.root.after(0, self._request_code)
                return

            await self._post_auth()
        except Exception as e:
            self.root.after(0, lambda: self._show_error(f"Ошибка подключения:\n{e}"))

    async def _post_auth(self):
        me = await self.client.get_me()
        name = peer_display(me)
        self.root.after(0, lambda: self._set_status(True, name))
        self.root.after(0, lambda: self.lbl_me.config(text=name))

        # Регистрируем обработчик новых сообщений
        self.client.add_event_handler(self._on_new_message, events.NewMessage)

        await self._load_dialogs()

    def _request_code(self):
        self.run_async(self._async_request_code())

    async def _async_request_code(self):
        try:
            await self.client.send_code_request(self.cfg["phone"])
            self.root.after(0, self._ask_code)
        except Exception as e:
            self.root.after(0, lambda: self._show_error(f"Ошибка отправки кода:\n{e}"))

    def _ask_code(self):
        code = simpledialog.askstring("Код подтверждения",
            "Введите код из Telegram:", parent=self.root)
        if code:
            self.run_async(self._async_sign_in(code))

    async def _async_sign_in(self, code):
        try:
            await self.client.sign_in(self.cfg["phone"], code)
            await self._post_auth()
        except SessionPasswordNeededError:
            self.root.after(0, self._ask_2fa)
        except PhoneCodeInvalidError:
            self.root.after(0, lambda: self._show_error("Неверный код!"))
        except Exception as e:
            self.root.after(0, lambda: self._show_error(str(e)))

    def _ask_2fa(self):
        pwd = simpledialog.askstring("Двухфакторная аутентификация",
            "Введите пароль 2FA:", show="•", parent=self.root)
        if pwd:
            self.run_async(self._async_2fa(pwd))

    async def _async_2fa(self, pwd):
        try:
            await self.client.sign_in(password=pwd)
            await self._post_auth()
        except Exception as e:
            self.root.after(0, lambda: self._show_error(str(e)))

    # ── Загрузка диалогов ─────────────────────────────────────────────────
    async def _load_dialogs(self):
        try:
            dialogs_raw = await self.client.get_dialogs(limit=50)
            self.dialogs = []
            for d in dialogs_raw:
                name = peer_display(d.entity)
                last_msg = ""
                last_time = None
                if d.message:
                    last_msg = d.message.message or "[медиа]"
                    last_time = d.message.date
                self.dialogs.append({
                    "id":       d.id,
                    "entity":   d.entity,
                    "name":     name,
                    "last_msg": last_msg[:50],
                    "last_time": last_time,
                    "unread":   d.unread_count or 0,
                })
                self.unread[d.id] = d.unread_count or 0
            self.root.after(0, self._render_chat_list)
        except Exception as e:
            self.root.after(0, lambda: self._show_error(f"Ошибка загрузки чатов:\n{e}"))

    def _render_chat_list(self, filter_text=""):
        t = self.theme
        for w in self.chat_frame.winfo_children():
            w.destroy()

        items = self.dialogs
        if filter_text:
            ft = filter_text.lower()
            items = [d for d in items if ft in d["name"].lower()]

        for d in items:
            self._add_chat_item(d, t)

    def _add_chat_item(self, d, t):
        is_active = (self.active_peer and
                     getattr(self.active_peer, "id", None) == d["id"])
        bg = t["hover"] if is_active else t["sidebar_bg"]

        row = tk.Frame(self.chat_frame, bg=bg, cursor="hand2")
        row.pack(fill="x", pady=1)

        # Аватар
        initials = peer_initials(d["name"])
        av = tk.Label(row, text=initials, font=("Segoe UI", 11, "bold"),
                      bg=t["accent"], fg="white", width=3, height=1,
                      relief="flat")
        av.pack(side="left", padx=(8, 8), pady=6)

        # Имя + последнее сообщение
        info = tk.Frame(row, bg=bg)
        info.pack(side="left", fill="both", expand=True)
        tk.Label(info, text=d["name"],
                 font=("Segoe UI", 11, "bold"),
                 bg=bg, fg=t["text"], anchor="w").pack(fill="x")
        tk.Label(info, text=d["last_msg"],
                 font=("Segoe UI", 9),
                 bg=bg, fg=t["text_dim"], anchor="w").pack(fill="x")

        # Время + непрочитанные
        right = tk.Frame(row, bg=bg)
        right.pack(side="right", padx=(0, 8), pady=6)
        tk.Label(right, text=format_time(d["last_time"]),
                 font=("Segoe UI", 8),
                 bg=bg, fg=t["text_dim"]).pack()
        uc = self.unread.get(d["id"], 0)
        if uc > 0:
            tk.Label(right, text=str(uc),
                     bg=t["unread_bg"], fg="white",
                     font=("Segoe UI", 8, "bold"),
                     padx=5, pady=1, relief="flat").pack()

        # Клик по чату
        entity = d["entity"]
        for w in (row, av, info, right):
            w.bind("<Button-1>", lambda e, en=entity: self._open_chat(en))
        for child in info.winfo_children() + right.winfo_children():
            child.bind("<Button-1>", lambda e, en=entity: self._open_chat(en))

        # Ховер
        def on_enter(e, f=row, b=bg):
            if f["bg"] != t["hover"]:
                self._set_bg_recursive(f, t["hover"])
        def on_leave(e, f=row, b=bg):
            if self.active_peer and getattr(self.active_peer, "id", None) == d["id"]:
                self._set_bg_recursive(f, t["hover"])
            else:
                self._set_bg_recursive(f, t["sidebar_bg"])
        row.bind("<Enter>", on_enter)
        row.bind("<Leave>", on_leave)

    def _set_bg_recursive(self, widget, color):
        try:
            widget.configure(bg=color)
        except Exception:
            pass
        for child in widget.winfo_children():
            self._set_bg_recursive(child, color)

    # ── Открытие чата ────────────────────────────────────────────────────
    def _open_chat(self, entity):
        self.active_peer = entity
        name = peer_display(entity)
        self.lbl_chat_name.config(text=name)

        info = ""
        if isinstance(entity, Channel):
            info = "канал"
        elif isinstance(entity, Chat):
            info = "группа"
        self.lbl_chat_info.config(text=info)

        self.unread[entity.id] = 0
        self._render_chat_list(self.search_var.get())
        self.run_async(self._load_messages(entity))

    async def _load_messages(self, entity):
        try:
            msgs_raw = await self.client.get_messages(entity, limit=50)
            msgs = []
            for m in reversed(msgs_raw):
                sender = ""
                if m.sender:
                    sender = peer_display(m.sender)
                msgs.append({
                    "id":      m.id,
                    "text":    m.message or "[медиа]",
                    "sender":  sender,
                    "date":    m.date,
                    "out":     m.out,
                })
            self.messages[entity.id] = msgs
            self.root.after(0, lambda: self._render_messages(entity.id))
        except Exception as e:
            self.root.after(0, lambda: self._show_error(str(e)))

    def _render_messages(self, peer_id):
        t = self.theme
        for w in self.msg_frame.winfo_children():
            w.destroy()

        msgs = self.messages.get(peer_id, [])
        for m in msgs:
            self._add_message_bubble(m, t)

        self.msg_frame.update_idletasks()
        self.msg_canvas.yview_moveto(1.0)

    def _add_message_bubble(self, m, t):
        is_out = m.get("out", False)
        bubble_color = t["bubble_me"] if is_out else t["bubble_them"]
        align = "e" if is_out else "w"
        anchor = "e" if is_out else "w"

        row = tk.Frame(self.msg_frame, bg=t["chat_bg"])
        row.pack(fill="x", pady=2, padx=10)

        inner = tk.Frame(row, bg=t["chat_bg"])
        inner.pack(side="right" if is_out else "left")

        if not is_out and m.get("sender"):
            tk.Label(inner, text=m["sender"],
                     font=("Segoe UI", 8, "bold"),
                     bg=t["chat_bg"], fg=t["accent"]).pack(anchor="w")

        bubble = tk.Frame(inner, bg=bubble_color,
                          padx=10, pady=6)
        bubble.pack(anchor=anchor)

        canvas_width = self.msg_canvas.winfo_width() or 600
        max_w = max(200, int(canvas_width * 0.65))

        tk.Label(bubble, text=m["text"],
                 bg=bubble_color, fg=t["text"],
                 font=("Segoe UI", 11),
                 wraplength=max_w, justify="left",
                 anchor="w").pack(anchor="w")

        tk.Label(bubble, text=format_time(m.get("date")),
                 bg=bubble_color, fg=t["text_dim"],
                 font=("Segoe UI", 8)).pack(anchor="e")

    def _on_canvas_resize(self, event):
        if self.active_peer:
            pid = getattr(self.active_peer, "id", None)
            if pid and pid in self.messages:
                self._render_messages(pid)

    # ── Отправка сообщений ───────────────────────────────────────────────
    def _on_enter(self, event):
        if event.state & 0x1:   # Shift+Enter
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
            m = {
                "id":     msg.id,
                "text":   text,
                "sender": "Вы",
                "date":   msg.date,
                "out":    True,
            }
            pid = entity.id
            self.messages.setdefault(pid, []).append(m)
            self.root.after(0, lambda: self._render_messages(pid))
        except Exception as e:
            self.root.after(0, lambda: self._show_error(str(e)))

    # ── Входящие сообщения (real-time) ────────────────────────────────────
    async def _on_new_message(self, event):
        msg = event.message
        peer_id = event.chat_id

        sender = ""
        try:
            sender_entity = await msg.get_sender()
            if sender_entity:
                sender = peer_display(sender_entity)
        except Exception:
            pass

        m = {
            "id":     msg.id,
            "text":   msg.message or "[медиа]",
            "sender": sender,
            "date":   msg.date,
            "out":    msg.out,
        }

        self.messages.setdefault(peer_id, []).append(m)

        if self.active_peer and getattr(self.active_peer, "id", None) == peer_id:
            self.root.after(0, lambda: self._render_messages(peer_id))
        else:
            self.unread[peer_id] = self.unread.get(peer_id, 0) + 1
            self.root.after(0, lambda: self._render_chat_list(self.search_var.get()))

        # Обновляем превью в сайдбаре
        for d in self.dialogs:
            if d["id"] == peer_id:
                d["last_msg"] = (msg.message or "[медиа]")[:50]
                d["last_time"] = msg.date
                break

    # ── Прочие методы ─────────────────────────────────────────────────────
    def _on_search(self, *_):
        self._render_chat_list(self.search_var.get())

    def _set_status(self, connected: bool, name: str = ""):
        t = self.theme
        self.lbl_status.config(
            text="●",
            fg=t["online"] if connected else t["text_dim"]
        )

    def _show_error(self, msg: str):
        messagebox.showerror("Ошибка", msg, parent=self.root)

    def _open_proxy_settings(self):
        dlg = ProxyDialog(self.root, self.cfg, self.theme)
        self.root.wait_window(dlg)
        if dlg.result:
            self.cfg["proxy"] = dlg.result
            save_config(self.cfg)
            messagebox.showinfo("Прокси", "Настройки сохранены.\nПерезапустите приложение.", parent=self.root)

    def _toggle_theme(self):
        new_theme = "light" if self.cfg.get("theme", "dark") == "dark" else "dark"
        self.cfg["theme"] = new_theme
        save_config(self.cfg)
        messagebox.showinfo("Тема", f"Тема изменена на {new_theme}.\nПерезапустите приложение.", parent=self.root)

    def _show_auth_dialog(self):
        dlg = AuthDialog(self.root, self.theme)
        self.root.wait_window(dlg)
        if dlg.result:
            self.cfg.update(dlg.result)
            save_config(self.cfg)
            self._connect()

    def _logout(self):
        if messagebox.askyesno("Выход", "Выйти из аккаунта?", parent=self.root):
            self.run_async(self._async_logout())

    async def _async_logout(self):
        try:
            if self.client:
                await self.client.log_out()
            session = SESSION_DIR / "tglite.session"
            if session.exists():
                session.unlink()
        except Exception:
            pass
        self.root.after(0, lambda: self._set_status(False))

    def _quit(self):
        try:
            if self.client:
                self.run_async(self.client.disconnect())
        except Exception:
            pass
        self.root.destroy()
        sys.exit(0)

    def run(self):
        self.root.mainloop()

# ─── Точка входа ─────────────────────────────────────────────────────────────
def main():
    app = TGLiteApp()
    app.run()

if __name__ == "__main__":
    main()
