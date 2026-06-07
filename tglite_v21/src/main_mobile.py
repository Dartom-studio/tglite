"""
TG Lite v2.1 — Мобильная версия (Kivy / Android)
• Вход по номеру телефона + 2FA
• Список чатов, отправка/приём сообщений
• Прокси SOCKS5/4/HTTP
"""

import asyncio
import threading
import json
from pathlib import Path
from datetime import datetime

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.widget import Widget
from kivy.clock import Clock
from kivy.metrics import dp, sp
from kivy.graphics import Color, RoundedRectangle, Rectangle

from telethon import TelegramClient, events
from telethon.tl.types import User, Chat, Channel
from telethon.errors import SessionPasswordNeededError
import socks

APP_VERSION = "2.1.0"
CONFIG_FILE = Path.home() / ".tglite" / "config.json"
SESSION_DIR = Path.home() / ".tglite"
SESSION_DIR.mkdir(parents=True, exist_ok=True)

ACCENT     = (0.353, 0.620, 0.831, 1)
BG_DARK    = (0.090, 0.129, 0.169, 1)
BG_MSG     = (0.059, 0.098, 0.137, 1)
BUBBLE_OUT = (0.169, 0.322, 0.471, 1)
BUBBLE_IN  = (0.094, 0.145, 0.200, 1)
TEXT       = (0.910, 0.918, 0.929, 1)
TEXT_DIM   = (0.478, 0.560, 0.620, 1)
SUCCESS    = (0.298, 0.686, 0.314, 1)
DANGER     = (0.898, 0.224, 0.208, 1)

def load_config():
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except Exception:
            pass
    return {"api_id": "", "api_hash": "", "phone": "",
            "proxy": {"enabled": False, "type": "SOCKS5",
                      "host": "127.0.0.1", "port": 1080,
                      "username": "", "password": ""}}

def save_config(cfg):
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))

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

def with_bg(widget, color):
    with widget.canvas.before:
        Color(*color)
        rect = Rectangle(pos=widget.pos, size=widget.size)
    widget.bind(pos=lambda w, p: setattr(rect, "pos", p),
                size=lambda w, s: setattr(rect, "size", s))
    return widget

# ─── Экран входа ─────────────────────────────────────────────────────────────
class LoginScreen(Screen):
    def __init__(self, app_ref, **kw):
        super().__init__(**kw)
        self.app_ref = app_ref
        self._build()

    def _inp(self, hint, password=False):
        return TextInput(
            hint_text=hint, multiline=False,
            size_hint_y=None, height=dp(46),
            background_color=(0.11, 0.17, 0.23, 1),
            foreground_color=(1, 1, 1, 1),
            hint_text_color=list(TEXT_DIM),
            password=password,
            font_size=sp(15), padding=[dp(12), dp(10)])

    def _build(self):
        layout = BoxLayout(orientation="vertical", padding=dp(24), spacing=dp(10))
        with_bg(layout, BG_DARK)

        layout.add_widget(Label(
            text=f"✈  TG Lite  v{APP_VERSION}",
            font_size=sp(26), bold=True, color=ACCENT,
            size_hint_y=None, height=dp(56)))
        layout.add_widget(Label(
            text="Введите данные для входа",
            color=TEXT_DIM, font_size=sp(13),
            size_hint_y=None, height=dp(28)))

        self.api_id_inp   = self._inp("API ID")
        self.api_hash_inp = self._inp("API Hash")
        self.phone_inp    = self._inp("Телефон (+79991234567)")
        self.pass_inp     = self._inp("Пароль 2FA (если есть)", password=True)

        for w in (self.api_id_inp, self.api_hash_inp,
                  self.phone_inp, self.pass_inp):
            layout.add_widget(w)

        layout.add_widget(Label(
            text="API ID и Hash: my.telegram.org",
            color=TEXT_DIM, font_size=sp(11),
            size_hint_y=None, height=dp(24)))

        login_btn = Button(
            text="Войти →", size_hint_y=None, height=dp(50),
            background_color=ACCENT, color=(1, 1, 1, 1),
            font_size=sp(16), bold=True)
        login_btn.bind(on_press=self._login)
        layout.add_widget(login_btn)

        proxy_btn = Button(
            text="⚙  Прокси", size_hint_y=None, height=dp(40),
            background_color=(0.15, 0.22, 0.30, 1),
            color=(1, 1, 1, 1), font_size=sp(13))
        proxy_btn.bind(on_press=self._proxy)
        layout.add_widget(proxy_btn)

        layout.add_widget(Widget())
        self.add_widget(layout)

    def _login(self, *_):
        cfg = self.app_ref.cfg
        cfg["api_id"]   = self.api_id_inp.text.strip()
        cfg["api_hash"] = self.api_hash_inp.text.strip()
        cfg["phone"]    = self.phone_inp.text.strip()
        cfg["_password"] = self.pass_inp.text.strip()
        save_config(cfg)
        self.app_ref.connect()

    def _proxy(self, *_):
        self.app_ref.show_proxy_popup()


# ─── Экран списка чатов ──────────────────────────────────────────────────────
class ChatListScreen(Screen):
    def __init__(self, app_ref, **kw):
        super().__init__(**kw)
        self.app_ref = app_ref
        self._build()

    def _build(self):
        root = BoxLayout(orientation="vertical")
        with_bg(root, BG_DARK)

        # Шапка
        header = BoxLayout(size_hint_y=None, height=dp(56), padding=[dp(14), 0])
        with_bg(header, (0.051, 0.067, 0.090, 1))
        self.lbl_name = Label(
            text="TG Lite", font_size=sp(18), bold=True,
            color=ACCENT, halign="left", valign="middle")
        self.lbl_name.bind(size=self.lbl_name.setter("text_size"))
        header.add_widget(self.lbl_name)
        self.status_dot = Label(
            text="●", font_size=sp(18), color=TEXT_DIM,
            size_hint_x=None, width=dp(30))
        header.add_widget(self.status_dot)
        root.add_widget(header)

        # Поиск
        search_box = BoxLayout(size_hint_y=None, height=dp(46),
                               padding=[dp(10), dp(4)])
        with_bg(search_box, BG_DARK)
        self.search = TextInput(
            hint_text="🔍 Поиск", multiline=False,
            background_color=(0.11, 0.17, 0.23, 1),
            foreground_color=(1, 1, 1, 1),
            hint_text_color=list(TEXT_DIM),
            font_size=sp(14), padding=[dp(10), dp(8)])
        self.search.bind(text=lambda i, t: self.app_ref.render_chat_list(t))
        search_box.add_widget(self.search)
        root.add_widget(search_box)

        # Список
        self.scroll = ScrollView()
        self.list   = GridLayout(cols=1, size_hint_y=None, spacing=1)
        self.list.bind(minimum_height=self.list.setter("height"))
        self.scroll.add_widget(self.list)
        root.add_widget(self.scroll)
        self.add_widget(root)

    def render(self, dialogs, filter_text=""):
        self.list.clear_widgets()
        items = dialogs
        if filter_text:
            ft = filter_text.lower()
            items = [d for d in dialogs if ft in d["name"].lower()]
        for d in items:
            self._item(d)

    def _item(self, d):
        btn = Button(
            size_hint_y=None, height=dp(70),
            background_color=(0.067, 0.098, 0.129, 1),
            border=(0, 0, 0, 0))
        inner = BoxLayout(padding=[dp(12), dp(8)], spacing=dp(8))

        # Аватар
        av = Label(text=peer_initials(d["name"]),
                   size_hint=(None, None), size=(dp(46), dp(46)),
                   bold=True, font_size=sp(16), color=(1, 1, 1, 1))
        with av.canvas.before:
            Color(*ACCENT)
            RoundedRectangle(pos=av.pos, size=av.size, radius=[dp(23)])
        av.bind(pos=lambda w, p: self._redraw_av(w),
                size=lambda w, s: self._redraw_av(w))
        inner.add_widget(av)

        info = BoxLayout(orientation="vertical", spacing=dp(2))
        name_lbl = Label(text=d["name"], font_size=sp(15), bold=True,
                         color=TEXT, halign="left", valign="middle")
        name_lbl.bind(size=name_lbl.setter("text_size"))
        msg_lbl = Label(text=d["last_msg"], font_size=sp(12),
                        color=TEXT_DIM, halign="left", valign="middle")
        msg_lbl.bind(size=msg_lbl.setter("text_size"))
        info.add_widget(name_lbl)
        info.add_widget(msg_lbl)
        inner.add_widget(info)

        right = BoxLayout(orientation="vertical",
                          size_hint_x=None, width=dp(52))
        right.add_widget(Label(text=format_time(d.get("last_time")),
                               font_size=sp(11), color=TEXT_DIM))
        if d.get("unread", 0) > 0:
            ub = Label(text=str(d["unread"]), font_size=sp(11),
                       color=(1, 1, 1, 1), size_hint_y=None, height=dp(24))
            with ub.canvas.before:
                Color(*ACCENT)
                RoundedRectangle(pos=ub.pos, size=ub.size, radius=[dp(12)])
            ub.bind(pos=lambda w, p: self._redraw_badge(w),
                    size=lambda w, s: self._redraw_badge(w))
            right.add_widget(ub)
        inner.add_widget(right)

        btn.add_widget(inner)
        entity = d["entity"]
        btn.bind(on_press=lambda *_: self.app_ref.open_chat(entity))
        self.list.add_widget(btn)

    def _redraw_av(self, w):
        w.canvas.before.clear()
        with w.canvas.before:
            Color(*ACCENT)
            RoundedRectangle(pos=w.pos, size=w.size, radius=[dp(23)])

    def _redraw_badge(self, w):
        w.canvas.before.clear()
        with w.canvas.before:
            Color(*ACCENT)
            RoundedRectangle(pos=w.pos, size=w.size, radius=[dp(12)])

    def set_status(self, online, name=""):
        self.status_dot.color = SUCCESS if online else TEXT_DIM
        if name:
            self.lbl_name.text = name


# ─── Экран чата ──────────────────────────────────────────────────────────────
class ChatScreen(Screen):
    def __init__(self, app_ref, **kw):
        super().__init__(**kw)
        self.app_ref = app_ref
        self._build()

    def _build(self):
        root = BoxLayout(orientation="vertical")
        with_bg(root, BG_MSG)

        # Шапка
        header = BoxLayout(size_hint_y=None, height=dp(56),
                           padding=[dp(6), 0], spacing=dp(4))
        with_bg(header, (0.051, 0.067, 0.090, 1))
        back = Button(text="←", size_hint=(None, None),
                      size=(dp(44), dp(44)),
                      background_color=(0, 0, 0, 0),
                      color=ACCENT, font_size=sp(20), bold=True)
        back.bind(on_press=lambda *_: self.app_ref.go_back())
        header.add_widget(back)
        self.lbl_title = Label(
            text="Чат", font_size=sp(17), bold=True,
            color=TEXT, halign="left", valign="middle")
        self.lbl_title.bind(size=self.lbl_title.setter("text_size"))
        header.add_widget(self.lbl_title)
        root.add_widget(header)

        # Сообщения
        self.scroll = ScrollView()
        self.msgs   = GridLayout(cols=1, size_hint_y=None,
                                 spacing=dp(4), padding=[dp(10), dp(8)])
        self.msgs.bind(minimum_height=self.msgs.setter("height"))
        self.scroll.add_widget(self.msgs)
        root.add_widget(self.scroll)

        # Ввод
        inp_row = BoxLayout(size_hint_y=None, height=dp(62),
                            padding=[dp(8), dp(6)], spacing=dp(8))
        with_bg(inp_row, (0.051, 0.067, 0.090, 1))
        self.inp = TextInput(
            hint_text="Сообщение...", multiline=False,
            background_color=(0.11, 0.17, 0.23, 1),
            foreground_color=(1, 1, 1, 1),
            hint_text_color=list(TEXT_DIM),
            font_size=sp(15), padding=[dp(12), dp(10)])
        send = Button(text="▶", size_hint=(None, None),
                      size=(dp(48), dp(48)),
                      background_color=ACCENT,
                      color=(1, 1, 1, 1), font_size=sp(18), bold=True)
        send.bind(on_press=self._send)
        inp_row.add_widget(self.inp)
        inp_row.add_widget(send)
        root.add_widget(inp_row)
        self.add_widget(root)

    def _send(self, *_):
        text = self.inp.text.strip()
        if text:
            self.inp.text = ""
            self.app_ref.send_message(text)

    def render(self, messages):
        self.msgs.clear_widgets()
        for m in messages:
            self._bubble(m)
        Clock.schedule_once(lambda dt: setattr(self.scroll, "scroll_y", 0), 0.1)

    def _bubble(self, m):
        is_out = m.get("out", False)
        color  = BUBBLE_OUT if is_out else BUBBLE_IN
        align  = "right" if is_out else "left"

        row = BoxLayout(size_hint_y=None, height=dp(0))
        bbl = Label(
            text=m["text"], font_size=sp(14), color=TEXT,
            halign=align, valign="top",
            padding=(dp(10), dp(8)),
            size_hint=(0.78, None))
        bbl.bind(texture_size=lambda w, ts: (
            setattr(w, "height", max(dp(36), ts[1] + dp(16))),
            setattr(row, "height", max(dp(40), ts[1] + dp(24)))))
        bbl.bind(width=lambda w, wd: setattr(w, "text_size", (wd - dp(20), None)))

        with bbl.canvas.before:
            Color(*color)
            RoundedRectangle(pos=bbl.pos, size=bbl.size, radius=[dp(10)])

        def rebg(w, *_):
            w.canvas.before.clear()
            with w.canvas.before:
                Color(*color)
                RoundedRectangle(pos=w.pos, size=w.size, radius=[dp(10)])

        bbl.bind(pos=rebg, size=rebg)

        if is_out:
            row.add_widget(Widget())
            row.add_widget(bbl)
        else:
            row.add_widget(bbl)
            row.add_widget(Widget())

        self.msgs.add_widget(row)


# ─── Приложение ──────────────────────────────────────────────────────────────
class TGLiteKivyApp(App):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.title   = f"TG Lite v{APP_VERSION}"
        self.cfg     = load_config()
        self.client  = None
        self.loop    = None
        self.dialogs = []
        self.messages = {}
        self.active_peer = None

    def build(self):
        self._start_loop()
        self.sm = ScreenManager(transition=SlideTransition())
        self.login_screen    = LoginScreen(self,    name="login")
        self.chatlist_screen = ChatListScreen(self, name="chatlist")
        self.chat_screen     = ChatScreen(self,     name="chat")
        for s in (self.login_screen, self.chatlist_screen, self.chat_screen):
            self.sm.add_widget(s)
        if self.cfg.get("api_id") and self.cfg.get("api_hash"):
            Clock.schedule_once(lambda dt: self.connect(), 0.5)
        return self.sm

    def _start_loop(self):
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self.loop.run_forever, daemon=True).start()

    def run_async(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    # ── Подключение ──────────────────────────────────────────────────────
    def connect(self):
        self.run_async(self._async_connect())

    async def _async_connect(self):
        try:
            self.client = TelegramClient(
                str(SESSION_DIR / "tglite"),
                int(self.cfg["api_id"]), self.cfg["api_hash"],
                proxy=get_proxy(self.cfg), loop=self.loop)
            await self.client.connect()
            if not await self.client.is_user_authorized():
                await self.client.send_code_request(self.cfg["phone"])
                Clock.schedule_once(lambda dt: self._ask_code(), 0)
                return
            await self._post_auth()
        except Exception as e:
            Clock.schedule_once(
                lambda dt, err=e: self._popup("Ошибка", str(err)), 0)

    async def _post_auth(self):
        from telethon.tl.types import User
        me   = await self.client.get_me()
        name = peer_display(me)
        Clock.schedule_once(
            lambda dt: self.chatlist_screen.set_status(True, name), 0)
        Clock.schedule_once(
            lambda dt: setattr(self.sm, "current", "chatlist"), 0)
        self.client.add_event_handler(self._on_new_msg, events.NewMessage)
        await self._load_dialogs()

    # ── Авторизация ───────────────────────────────────────────────────────
    def _ask_code(self):
        popup = None
        content = BoxLayout(orientation="vertical",
                            padding=dp(16), spacing=dp(10))
        content.add_widget(Label(text="Код из Telegram:", color=TEXT))
        code_inp = TextInput(multiline=False, size_hint_y=None, height=dp(46),
                             background_color=(0.11, 0.17, 0.23, 1),
                             foreground_color=(1, 1, 1, 1), font_size=sp(16))
        content.add_widget(code_inp)
        def confirm(*_):
            popup.dismiss()
            self.run_async(self._sign_in(code_inp.text.strip()))
        btn = Button(text="Подтвердить", size_hint_y=None, height=dp(46),
                     background_color=ACCENT, on_press=confirm)
        content.add_widget(btn)
        popup = Popup(title="Код подтверждения", content=content,
                      size_hint=(0.9, None), height=dp(230))
        popup.open()

    async def _sign_in(self, code):
        try:
            await self.client.sign_in(self.cfg["phone"], code)
            await self._post_auth()
        except SessionPasswordNeededError:
            pwd = self.cfg.get("_password", "")
            if pwd:
                await self._do_2fa(pwd)
            else:
                Clock.schedule_once(lambda dt: self._ask_2fa(), 0)
        except Exception as e:
            Clock.schedule_once(
                lambda dt, err=e: self._popup("Ошибка", str(err)), 0)

    def _ask_2fa(self):
        popup = None
        content = BoxLayout(orientation="vertical",
                            padding=dp(16), spacing=dp(10))
        content.add_widget(Label(text="Пароль 2FA:", color=TEXT))
        pwd_inp = TextInput(multiline=False, size_hint_y=None, height=dp(46),
                            password=True,
                            background_color=(0.11, 0.17, 0.23, 1),
                            foreground_color=(1, 1, 1, 1), font_size=sp(16))
        content.add_widget(pwd_inp)
        def confirm(*_):
            popup.dismiss()
            self.run_async(self._do_2fa(pwd_inp.text))
        btn = Button(text="Войти", size_hint_y=None, height=dp(46),
                     background_color=ACCENT, on_press=confirm)
        content.add_widget(btn)
        popup = Popup(title="2FA", content=content,
                      size_hint=(0.9, None), height=dp(230))
        popup.open()

    async def _do_2fa(self, pwd):
        try:
            await self.client.sign_in(password=pwd)
            await self._post_auth()
        except Exception as e:
            Clock.schedule_once(
                lambda dt, err=e: self._popup("Ошибка 2FA", str(err)), 0)

    # ── Чаты ─────────────────────────────────────────────────────────────
    async def _load_dialogs(self):
        raw = await self.client.get_dialogs(limit=50)
        self.dialogs = []
        for d in raw:
            self.dialogs.append({
                "id": d.id, "entity": d.entity,
                "name": peer_display(d.entity),
                "last_msg": (d.message.message or "[медиа]")[:40] if d.message else "",
                "last_time": d.message.date if d.message else None,
                "unread": d.unread_count or 0,
            })
        Clock.schedule_once(lambda dt: self.render_chat_list(""), 0)

    def render_chat_list(self, text=""):
        self.chatlist_screen.render(self.dialogs, text)

    def open_chat(self, entity):
        self.active_peer = entity
        self.chat_screen.lbl_title.text = peer_display(entity)
        self.sm.current = "chat"
        self.run_async(self._load_messages(entity))

    async def _load_messages(self, entity):
        raw  = await self.client.get_messages(entity, limit=50)
        msgs = [{"id": m.id, "text": m.message or "[медиа]",
                 "sender": peer_display(m.sender) if m.sender else "",
                 "date": m.date, "out": m.out}
                for m in reversed(raw)]
        self.messages[entity.id] = msgs
        Clock.schedule_once(
            lambda dt: self.chat_screen.render(msgs), 0)

    def send_message(self, text):
        if self.active_peer:
            self.run_async(self._async_send(self.active_peer, text))

    async def _async_send(self, entity, text):
        msg = await self.client.send_message(entity, text)
        m   = {"id": msg.id, "text": text, "sender": "Вы",
               "date": msg.date, "out": True}
        self.messages.setdefault(entity.id, []).append(m)
        Clock.schedule_once(
            lambda dt: self.chat_screen.render(self.messages[entity.id]), 0)

    async def _on_new_msg(self, event):
        pid = event.chat_id
        msg = event.message
        m   = {"id": msg.id, "text": msg.message or "[медиа]",
               "sender": "", "date": msg.date, "out": msg.out}
        self.messages.setdefault(pid, []).append(m)
        if self.active_peer and self.active_peer.id == pid:
            Clock.schedule_once(
                lambda dt: self.chat_screen.render(self.messages[pid]), 0)
        else:
            for d in self.dialogs:
                if d["id"] == pid:
                    d["unread"] = d.get("unread", 0) + 1
                    d["last_msg"] = (msg.message or "[медиа]")[:40]
                    break
            Clock.schedule_once(lambda dt: self.render_chat_list(""), 0)

    def go_back(self):
        self.sm.current = "chatlist"

    def show_proxy_popup(self):
        cfg = self.cfg
        p   = cfg.get("proxy", {})
        content = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(8))
        content.add_widget(Label(text="Прокси настройки", color=TEXT,
                                 font_size=sp(15), bold=True,
                                 size_hint_y=None, height=dp(34)))
        fields = {}
        for key, hint, val in [
            ("host",     "Хост",   p.get("host", "127.0.0.1")),
            ("port",     "Порт",   str(p.get("port", 1080))),
            ("username", "Логин",  p.get("username", "")),
            ("password", "Пароль", p.get("password", "")),
        ]:
            inp = TextInput(hint_text=hint, text=val, multiline=False,
                            size_hint_y=None, height=dp(42),
                            background_color=(0.11, 0.17, 0.23, 1),
                            foreground_color=(1, 1, 1, 1),
                            hint_text_color=list(TEXT_DIM), font_size=sp(14),
                            password=(key == "password"))
            fields[key] = inp
            content.add_widget(inp)

        popup = None
        def save(*_):
            cfg["proxy"] = {
                "enabled":  True,
                "type":     "SOCKS5",
                "host":     fields["host"].text,
                "port":     int(fields["port"].text or 1080),
                "username": fields["username"].text,
                "password": fields["password"].text,
            }
            save_config(cfg)
            popup.dismiss()

        btn = Button(text="Сохранить", size_hint_y=None, height=dp(44),
                     background_color=ACCENT, on_press=save)
        content.add_widget(btn)
        popup = Popup(title="Прокси", content=content,
                      size_hint=(0.92, None), height=dp(360))
        popup.open()

    def _popup(self, title, text):
        content = BoxLayout(orientation="vertical", padding=dp(14))
        content.add_widget(Label(text=text, color=TEXT,
                                 text_size=(dp(260), None),
                                 halign="left", valign="top"))
        p = Popup(title=title, content=content,
                  size_hint=(0.88, None), height=dp(200))
        btn = Button(text="OK", size_hint_y=None, height=dp(40),
                     background_color=ACCENT, on_press=p.dismiss)
        content.add_widget(btn)
        p.open()


if __name__ == "__main__":
    TGLiteKivyApp().run()
