"""
TG Lite — мобильная версия (Kivy) для Android APK
"""

import asyncio
import threading
import json
from pathlib import Path
from datetime import datetime

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.recycleview import RecycleView
from kivy.uix.recycleview.views import RecycleDataViewBehavior
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.popup import Popup
from kivy.uix.widget import Widget
from kivy.clock import Clock
from kivy.metrics import dp, sp
from kivy.graphics import Color, RoundedRectangle, Rectangle

from telethon import TelegramClient, events
from telethon.tl.types import User, Chat, Channel
from telethon.errors import SessionPasswordNeededError
import socks

# ─── Config ──────────────────────────────────────────────────────────────────
CONFIG_FILE = Path.home() / ".tglite" / "config.json"
SESSION_DIR = Path.home() / ".tglite"
SESSION_DIR.mkdir(parents=True, exist_ok=True)

ACCENT   = (0.353, 0.620, 0.831, 1)
BG_DARK  = (0.090, 0.129, 0.169, 1)
BG_MSG   = (0.059, 0.098, 0.137, 1)
BUBBLE_OUT = (0.169, 0.322, 0.471, 1)
BUBBLE_IN  = (0.094, 0.145, 0.200, 1)
TEXT     = (0.910, 0.918, 0.929, 1)
TEXT_DIM = (0.478, 0.560, 0.620, 1)

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

def get_proxy(cfg):
    p = cfg.get("proxy", {})
    if not p.get("enabled"):
        return None
    pt = {"SOCKS5": socks.SOCKS5, "SOCKS4": socks.SOCKS4, "HTTP": socks.HTTP}.get(p.get("type","SOCKS5"), socks.SOCKS5)
    return (pt, p["host"], int(p["port"]), True,
            p.get("username") or None, p.get("password") or None)

# ─── Screens ─────────────────────────────────────────────────────────────────

class LoginScreen(Screen):
    def __init__(self, app_ref, **kw):
        super().__init__(**kw)
        self.app_ref = app_ref
        self._build()

    def _build(self):
        layout = BoxLayout(orientation="vertical", padding=dp(24), spacing=dp(12))
        with layout.canvas.before:
            Color(*BG_DARK)
            self._bg = Rectangle(pos=layout.pos, size=layout.size)
        layout.bind(pos=lambda *a: setattr(self._bg, "pos", layout.pos),
                    size=lambda *a: setattr(self._bg, "size", layout.size))

        lbl = Label(text="✈  TG Lite", font_size=sp(28), bold=True,
                    color=ACCENT, size_hint_y=None, height=dp(60))
        layout.add_widget(lbl)
        layout.add_widget(Label(text="Войдите через Telegram API",
                                 color=TEXT_DIM, font_size=sp(14),
                                 size_hint_y=None, height=dp(30)))

        self.api_id_in   = self._inp("API ID")
        self.api_hash_in = self._inp("API Hash")
        self.phone_in    = self._inp("Телефон (+79991234567)")
        for w in (self.api_id_in, self.api_hash_in, self.phone_in):
            layout.add_widget(w)

        btn = Button(text="Войти", size_hint_y=None, height=dp(48),
                     background_color=ACCENT, color=(1,1,1,1),
                     font_size=sp(16), bold=True)
        btn.bind(on_press=self._login)
        layout.add_widget(btn)

        # Прокси
        proxy_btn = Button(text="⚙ Прокси", size_hint_y=None, height=dp(40),
                           background_color=(0.2,0.3,0.4,1), color=(1,1,1,1),
                           font_size=sp(14))
        proxy_btn.bind(on_press=self._open_proxy)
        layout.add_widget(proxy_btn)

        layout.add_widget(Widget())
        self.add_widget(layout)

    def _inp(self, hint):
        return TextInput(hint_text=hint, multiline=False,
                         size_hint_y=None, height=dp(44),
                         background_color=(0.11,0.17,0.23,1),
                         foreground_color=(1,1,1,1),
                         hint_text_color=list(TEXT_DIM),
                         font_size=sp(15), padding=[dp(12), dp(10)])

    def _login(self, *_):
        cfg = self.app_ref.cfg
        cfg["api_id"]   = self.api_id_in.text.strip()
        cfg["api_hash"] = self.api_hash_in.text.strip()
        cfg["phone"]    = self.phone_in.text.strip()
        save_config(cfg)
        self.app_ref.connect()

    def _open_proxy(self, *_):
        self.app_ref.show_proxy_popup()


class ChatListScreen(Screen):
    def __init__(self, app_ref, **kw):
        super().__init__(**kw)
        self.app_ref = app_ref
        self._build()

    def _build(self):
        root = BoxLayout(orientation="vertical")
        with root.canvas.before:
            Color(*BG_DARK)
            self._bg = Rectangle(pos=root.pos, size=root.size)
        root.bind(pos=lambda *a: setattr(self._bg, "pos", root.pos),
                  size=lambda *a: setattr(self._bg, "size", root.size))

        # Header
        header = BoxLayout(size_hint_y=None, height=dp(56),
                           padding=[dp(16), 0])
        with header.canvas.before:
            Color(0.051, 0.067, 0.090, 1)
            self._hbg = Rectangle(pos=header.pos, size=header.size)
        header.bind(pos=lambda *a: setattr(self._hbg,"pos",header.pos),
                    size=lambda *a: setattr(self._hbg,"size",header.size))

        self.lbl_name = Label(text="TG Lite", font_size=sp(18), bold=True,
                              color=ACCENT, halign="left", valign="middle")
        self.lbl_name.bind(size=self.lbl_name.setter("text_size"))
        header.add_widget(self.lbl_name)

        self.status_dot = Label(text="●", font_size=sp(18),
                                color=TEXT_DIM, size_hint_x=None, width=dp(30))
        header.add_widget(self.status_dot)
        root.add_widget(header)

        # Search
        search_box = BoxLayout(size_hint_y=None, height=dp(44),
                               padding=[dp(10), dp(4)])
        with search_box.canvas.before:
            Color(*BG_DARK)
            Rectangle(pos=search_box.pos, size=search_box.size)
        self.search_inp = TextInput(hint_text="🔍 Поиск",
                                    multiline=False,
                                    background_color=(0.11,0.17,0.23,1),
                                    foreground_color=(1,1,1,1),
                                    hint_text_color=list(TEXT_DIM),
                                    font_size=sp(14), padding=[dp(10), dp(8)])
        self.search_inp.bind(text=self._on_search)
        search_box.add_widget(self.search_inp)
        root.add_widget(search_box)

        # Chat list
        self.scroll = ScrollView()
        self.chat_list = GridLayout(cols=1, size_hint_y=None, spacing=1)
        self.chat_list.bind(minimum_height=self.chat_list.setter("height"))
        self.scroll.add_widget(self.chat_list)
        root.add_widget(self.scroll)

        self.add_widget(root)

    def _on_search(self, instance, text):
        self.app_ref.render_chat_list(text)

    def render_dialogs(self, dialogs, filter_text=""):
        self.chat_list.clear_widgets()
        items = dialogs
        if filter_text:
            ft = filter_text.lower()
            items = [d for d in dialogs if ft in d["name"].lower()]
        for d in items:
            self._add_item(d)

    def _add_item(self, d):
        btn = Button(size_hint_y=None, height=dp(68),
                     background_color=(0.067,0.098,0.129,1),
                     border=(0,0,0,0))

        inner = BoxLayout(padding=[dp(12), dp(8)])

        # Avatar
        av_lbl = Label(text=peer_initials(d["name"]),
                       size_hint=(None, None), size=(dp(44), dp(44)),
                       bold=True, font_size=sp(16), color=(1,1,1,1))
        with av_lbl.canvas.before:
            Color(*ACCENT)
            RoundedRectangle(pos=av_lbl.pos, size=av_lbl.size, radius=[dp(22)])
        av_lbl.bind(pos=lambda w,p: w.canvas.before.clear() or
                    self._redraw_av(w, p, w.size))
        inner.add_widget(av_lbl)

        info = BoxLayout(orientation="vertical", padding=[dp(8),0])
        name_lbl = Label(text=d["name"], font_size=sp(15), bold=True,
                         color=TEXT, halign="left", valign="middle")
        name_lbl.bind(size=name_lbl.setter("text_size"))
        msg_lbl = Label(text=d["last_msg"], font_size=sp(12),
                        color=TEXT_DIM, halign="left", valign="middle")
        msg_lbl.bind(size=msg_lbl.setter("text_size"))
        info.add_widget(name_lbl)
        info.add_widget(msg_lbl)
        inner.add_widget(info)

        right = BoxLayout(orientation="vertical", size_hint_x=None, width=dp(50))
        time_lbl = Label(text=format_time(d.get("last_time")),
                         font_size=sp(11), color=TEXT_DIM)
        right.add_widget(time_lbl)
        if d.get("unread", 0) > 0:
            ub = Label(text=str(d["unread"]), font_size=sp(11),
                       color=(1,1,1,1), size_hint_y=None, height=dp(22))
            with ub.canvas.before:
                Color(*ACCENT)
                RoundedRectangle(pos=ub.pos, size=ub.size, radius=[dp(11)])
            right.add_widget(ub)
        inner.add_widget(right)

        btn.add_widget(inner)
        entity = d["entity"]
        btn.bind(on_press=lambda *_: self.app_ref.open_chat(entity))
        self.chat_list.add_widget(btn)

    def _redraw_av(self, w, pos, size):
        with w.canvas.before:
            Color(*ACCENT)
            RoundedRectangle(pos=pos, size=size, radius=[dp(22)])

    def set_status(self, online, name=""):
        self.status_dot.color = (0.298, 0.686, 0.314, 1) if online else TEXT_DIM
        if name:
            self.lbl_name.text = name


class ChatScreen(Screen):
    def __init__(self, app_ref, **kw):
        super().__init__(**kw)
        self.app_ref = app_ref
        self._build()

    def _build(self):
        root = BoxLayout(orientation="vertical")
        with root.canvas.before:
            Color(*BG_MSG)
            self._bg = Rectangle(pos=root.pos, size=root.size)
        root.bind(pos=lambda *a: setattr(self._bg,"pos",root.pos),
                  size=lambda *a: setattr(self._bg,"size",root.size))

        # Header
        header = BoxLayout(size_hint_y=None, height=dp(56),
                           padding=[dp(8), 0])
        with header.canvas.before:
            Color(0.051, 0.067, 0.090, 1)
            self._hbg = Rectangle(pos=header.pos, size=header.size)
        header.bind(pos=lambda *a: setattr(self._hbg,"pos",header.pos),
                    size=lambda *a: setattr(self._hbg,"size",header.size))

        back_btn = Button(text="←", size_hint=(None,None),
                          size=(dp(40),dp(40)),
                          background_color=(0,0,0,0),
                          color=ACCENT, font_size=sp(20), bold=True)
        back_btn.bind(on_press=lambda *_: self.app_ref.go_back())
        header.add_widget(back_btn)

        self.lbl_title = Label(text="Чат", font_size=sp(17), bold=True,
                               color=TEXT, halign="left", valign="middle")
        self.lbl_title.bind(size=self.lbl_title.setter("text_size"))
        header.add_widget(self.lbl_title)
        root.add_widget(header)

        # Messages
        self.scroll = ScrollView()
        self.msg_list = GridLayout(cols=1, size_hint_y=None,
                                   spacing=dp(4), padding=[dp(10), dp(8)])
        self.msg_list.bind(minimum_height=self.msg_list.setter("height"))
        self.scroll.add_widget(self.msg_list)
        root.add_widget(self.scroll)

        # Input row
        input_row = BoxLayout(size_hint_y=None, height=dp(60),
                              padding=[dp(8), dp(6)], spacing=dp(8))
        with input_row.canvas.before:
            Color(0.051, 0.067, 0.090, 1)
            self._ibg = Rectangle(pos=input_row.pos, size=input_row.size)
        input_row.bind(pos=lambda *a: setattr(self._ibg,"pos",input_row.pos),
                       size=lambda *a: setattr(self._ibg,"size",input_row.size))

        self.msg_input = TextInput(hint_text="Сообщение...",
                                   multiline=False,
                                   background_color=(0.11,0.17,0.23,1),
                                   foreground_color=(1,1,1,1),
                                   hint_text_color=list(TEXT_DIM),
                                   font_size=sp(15), padding=[dp(12), dp(10)])
        send_btn = Button(text="▶", size_hint=(None,None),
                          size=(dp(46),dp(46)),
                          background_color=ACCENT,
                          color=(1,1,1,1), font_size=sp(18), bold=True)
        send_btn.bind(on_press=self._send)
        input_row.add_widget(self.msg_input)
        input_row.add_widget(send_btn)
        root.add_widget(input_row)
        self.add_widget(root)

    def _send(self, *_):
        text = self.msg_input.text.strip()
        if text:
            self.msg_input.text = ""
            self.app_ref.send_message(text)

    def render_messages(self, messages):
        self.msg_list.clear_widgets()
        for m in messages:
            self._add_bubble(m)
        Clock.schedule_once(lambda dt: self._scroll_bottom(), 0.1)

    def _scroll_bottom(self):
        self.scroll.scroll_y = 0

    def _add_bubble(self, m):
        is_out = m.get("out", False)
        color = BUBBLE_OUT if is_out else BUBBLE_IN
        align = "right" if is_out else "left"

        row = BoxLayout(size_hint_y=None, height=dp(0))

        bbl = Label(
            text=m["text"],
            font_size=sp(14),
            color=TEXT,
            halign=align,
            valign="top",
            padding=(dp(10), dp(8)),
            size_hint=(0.75, None),
        )
        bbl.bind(texture_size=lambda w, ts: setattr(w, "height", max(dp(36), ts[1]+dp(16))))
        bbl.bind(width=lambda w, wd: setattr(w, "text_size", (wd - dp(20), None)))

        with bbl.canvas.before:
            Color(*color)
            RoundedRectangle(pos=bbl.pos, size=bbl.size, radius=[dp(10)])
        bbl.bind(pos=lambda w,p: self._rebg(w,p,w.size,color),
                 size=lambda w,s: self._rebg(w,w.pos,s,color))
        bbl.bind(texture_size=lambda w,ts: setattr(row,"height", max(dp(36), ts[1]+dp(24))))

        if is_out:
            row.add_widget(Widget())
            row.add_widget(bbl)
        else:
            row.add_widget(bbl)
            row.add_widget(Widget())

        self.msg_list.add_widget(row)

    def _rebg(self, w, pos, size, color):
        w.canvas.before.clear()
        with w.canvas.before:
            Color(*color)
            RoundedRectangle(pos=pos, size=size, radius=[dp(10)])


# ─── Основное приложение Kivy ────────────────────────────────────────────────
class TGLiteKivyApp(App):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.title = "TG Lite"
        self.cfg = load_config()
        self.client = None
        self.loop = None
        self.dialogs = []
        self.messages = {}
        self.active_peer = None

    def build(self):
        self._start_loop()
        self.sm = ScreenManager(transition=SlideTransition())
        self.login_screen = LoginScreen(self, name="login")
        self.chatlist_screen = ChatListScreen(self, name="chatlist")
        self.chat_screen = ChatScreen(self, name="chat")
        self.sm.add_widget(self.login_screen)
        self.sm.add_widget(self.chatlist_screen)
        self.sm.add_widget(self.chat_screen)

        if self.cfg.get("api_id") and self.cfg.get("api_hash"):
            Clock.schedule_once(lambda dt: self.connect(), 0.5)
        return self.sm

    def _start_loop(self):
        self.loop = asyncio.new_event_loop()
        t = threading.Thread(target=self.loop.run_forever, daemon=True)
        t.start()

    def run_async(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    def connect(self):
        self.run_async(self._async_connect())

    async def _async_connect(self):
        try:
            proxy = get_proxy(self.cfg)
            self.client = TelegramClient(
                str(SESSION_DIR / "tglite"),
                int(self.cfg["api_id"]),
                self.cfg["api_hash"],
                proxy=proxy,
                loop=self.loop
            )
            await self.client.connect()
            if not await self.client.is_user_authorized():
                await self.client.send_code_request(self.cfg["phone"])
                Clock.schedule_once(lambda dt: self._ask_code(), 0)
                return
            await self._post_auth()
        except Exception as e:
            Clock.schedule_once(lambda dt, err=e: self._show_popup("Ошибка", str(err)), 0)

    async def _post_auth(self):
        me = await self.client.get_me()
        name = peer_display(me)
        Clock.schedule_once(lambda dt: self.chatlist_screen.set_status(True, name), 0)
        Clock.schedule_once(lambda dt: setattr(self.sm, "current", "chatlist"), 0)
        self.client.add_event_handler(self._on_new_msg, events.NewMessage)
        await self._load_dialogs()

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
        self.chatlist_screen.render_dialogs(self.dialogs, text)

    def open_chat(self, entity):
        self.active_peer = entity
        self.chat_screen.lbl_title.text = peer_display(entity)
        self.sm.current = "chat"
        self.run_async(self._load_messages(entity))

    async def _load_messages(self, entity):
        msgs_raw = await self.client.get_messages(entity, limit=40)
        msgs = []
        for m in reversed(msgs_raw):
            msgs.append({
                "id": m.id, "text": m.message or "[медиа]",
                "sender": peer_display(m.sender) if m.sender else "",
                "date": m.date, "out": m.out,
            })
        self.messages[entity.id] = msgs
        Clock.schedule_once(lambda dt: self.chat_screen.render_messages(msgs), 0)

    def send_message(self, text):
        if self.active_peer:
            self.run_async(self._async_send(self.active_peer, text))

    async def _async_send(self, entity, text):
        msg = await self.client.send_message(entity, text)
        m = {"id": msg.id, "text": text, "sender": "Вы", "date": msg.date, "out": True}
        self.messages.setdefault(entity.id, []).append(m)
        Clock.schedule_once(
            lambda dt: self.chat_screen.render_messages(self.messages[entity.id]), 0)

    async def _on_new_msg(self, event):
        pid = event.chat_id
        msg = event.message
        m = {"id": msg.id, "text": msg.message or "[медиа]",
             "sender": "", "date": msg.date, "out": msg.out}
        self.messages.setdefault(pid, []).append(m)
        if self.active_peer and self.active_peer.id == pid:
            Clock.schedule_once(
                lambda dt: self.chat_screen.render_messages(self.messages[pid]), 0)

    def go_back(self):
        self.sm.current = "chatlist"

    def show_proxy_popup(self):
        self._show_popup("Прокси", "Настройте прокси в config.json:\n~/.tglite/config.json")

    def _ask_code(self):
        popup = None
        content = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(10))
        content.add_widget(Label(text="Введите код из Telegram:", color=TEXT))
        code_inp = TextInput(multiline=False, size_hint_y=None, height=dp(44),
                             background_color=(0.11,0.17,0.23,1),
                             foreground_color=(1,1,1,1), font_size=sp(16))
        content.add_widget(code_inp)
        def confirm(*_):
            popup.dismiss()
            self.run_async(self._sign_in(code_inp.text.strip()))
        btn = Button(text="Подтвердить", size_hint_y=None, height=dp(44),
                     background_color=ACCENT, on_press=confirm)
        content.add_widget(btn)
        popup = Popup(title="Код подтверждения", content=content,
                      size_hint=(0.9, None), height=dp(220))
        popup.open()

    async def _sign_in(self, code):
        try:
            await self.client.sign_in(self.cfg["phone"], code)
            await self._post_auth()
        except SessionPasswordNeededError:
            Clock.schedule_once(lambda dt: self._ask_2fa(), 0)
        except Exception as e:
            Clock.schedule_once(lambda dt, err=e: self._show_popup("Ошибка", str(err)), 0)

    def _ask_2fa(self):
        popup = None
        content = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(10))
        content.add_widget(Label(text="Пароль 2FA:", color=TEXT))
        pwd_inp = TextInput(multiline=False, size_hint_y=None, height=dp(44),
                            password=True,
                            background_color=(0.11,0.17,0.23,1),
                            foreground_color=(1,1,1,1), font_size=sp(16))
        content.add_widget(pwd_inp)
        def confirm(*_):
            popup.dismiss()
            self.run_async(self._2fa(pwd_inp.text))
        btn = Button(text="Войти", size_hint_y=None, height=dp(44),
                     background_color=ACCENT, on_press=confirm)
        content.add_widget(btn)
        popup = Popup(title="Двухфакторная аутентификация", content=content,
                      size_hint=(0.9, None), height=dp(220))
        popup.open()

    async def _2fa(self, pwd):
        try:
            await self.client.sign_in(password=pwd)
            await self._post_auth()
        except Exception as e:
            Clock.schedule_once(lambda dt, err=e: self._show_popup("Ошибка", str(err)), 0)

    def _show_popup(self, title, text):
        content = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(10))
        content.add_widget(Label(text=text, color=TEXT, text_size=(dp(260), None),
                                 halign="left", valign="top"))
        btn = Button(text="ОК", size_hint_y=None, height=dp(40),
                     background_color=ACCENT, color=(1,1,1,1))
        popup = Popup(title=title, content=content, size_hint=(0.85, None), height=dp(220))
        btn.bind(on_press=popup.dismiss)
        content.add_widget(btn)
        popup.open()


if __name__ == "__main__":
    TGLiteKivyApp().run()
