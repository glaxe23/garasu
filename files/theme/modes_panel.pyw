"""Панель выбора режима Garasu: повседневный, рабочий, игровой. Открывается кнопкой режима на панели.
Клик по карточке или клавиши 1-3 включают режим. Закрыть: Esc, клик мимо или повторный клик по кнопке."""
import os, sys, ctypes, subprocess
from ctypes import wintypes

TITLE = "Ryoku Modes"
u = ctypes.windll.user32
u.FindWindowW.restype = wintypes.HWND
old = u.FindWindowW(None, TITLE)
if old:
    u.PostMessageW(old, 0x0010, 0, 0)
    sys.exit()
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

import tkinter as tk
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, here)
import ui, glass, mode as M

C = ui.colors()
BG, FG, MUTED, ACC, TROUGH = C["BG"], C["FG"], C["MUTED"], C["ACC"], C["TROUGH"]
FONT, ICONS = ui.FONT, ui.ICONS
GLYPH = {"daily": "", "work": "", "game": ""}
current = M.options().get("mode", "daily")

win = tk.Tk()
win.title(TITLE)
win.overrideredirect(True)
win.attributes("-topmost", True)
ui.hidden(win, 0.94)
win.configure(bg=BG)
SW = win.winfo_screenwidth()
WIDTH = 420
body = tk.Frame(win, bg=BG, padx=16, pady=10)
body.pack(fill="both", expand=True)
head = tk.Frame(body, bg=BG)
head.pack(fill="x", pady=(0, 8))
tk.Label(head, text="硝", font=(FONT, 15, "bold"), bg=BG, fg=ACC).pack(side="left")
tk.Label(head, text="  РЕЖИМ", font=(FONT, 10, "bold"), bg=BG, fg=FG).pack(side="left")
status = tk.Label(head, text="1–%d — выбрать" % len(M.MODES), font=(FONT, 9), bg=BG, fg=MUTED)
status.pack(side="left", padx=12)


def choose(name):
    status.configure(text="переключаю…")
    win.update_idletasks()
    subprocess.Popen([sys.executable.replace("python.exe", "pythonw.exe"), os.path.join(here, "mode.py"), name],
                     creationflags=0x08000000)
    win.after(400, win.destroy)


for name, (title, text) in M.MODES.items():
    on = name == current
    card = tk.Frame(body, bg=ACC if on else TROUGH, cursor="hand2", padx=12, pady=10)
    card.pack(fill="x", pady=4)
    bg, fg, sub = (ACC, BG, BG) if on else (TROUGH, FG, MUTED)
    ico = tk.Label(card, text=GLYPH[name], font=(ICONS, 18), bg=bg, fg=fg, width=2)
    ico.pack(side="left", padx=(0, 10))
    col = tk.Frame(card, bg=bg)
    col.pack(side="left", fill="x", expand=True)
    t = tk.Label(col, text=title + ("   · сейчас" if on else ""), font=(FONT, 11, "bold"), bg=bg, fg=fg, anchor="w")
    t.pack(fill="x")
    d = tk.Label(col, text=text, font=(FONT, 9), bg=bg, fg=sub, anchor="w", justify="left", wraplength=WIDTH - 110)
    d.pack(fill="x")
    for w in (card, ico, col, t, d):
        w.bind("<Button-1>", lambda e, n=name: choose(n))

auto_row = tk.Frame(body, bg=BG, cursor="hand2")
auto_row.pack(fill="x", pady=(8, 0))
auto = tk.Label(auto_row, text="Игровой режим сам при запуске игры из Steam", font=(FONT, 9), bg=BG, fg=MUTED,
                cursor="hand2", anchor="w")


def auto_text():
    auto.configure(fg=FG if M.options().get("auto_game", True) else MUTED)


def auto_set(on):
    o = M.options()
    o["auto_game"] = bool(on)
    M.save_options(o)
    auto_text()


auto_sw = glass.Toggle(auto_row, M.options().get("auto_game", True), auto_set, bg=BG, fg=FG, accent=ACC,
                       muted=MUTED, scale=.9)
auto_sw.pack(side="left")
auto.pack(side="left", padx=(6, 0))
for w in (auto_row, auto):
    w.bind("<Button-1>", lambda e: auto_sw.set(not auto_sw.on, animate=True, notify=True))
auto_text()

win.update_idletasks()
win.geometry("%dx%d+%d+%d" % (WIDTH, body.winfo_reqheight(), SW - WIDTH - 12, 50))
try:
    hwnd = wintypes.HWND(u.GetParent(win.winfo_id()) or win.winfo_id())
    ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(ctypes.c_int(2)), 4)
except Exception:
    pass
win.bind("<Escape>", lambda e: win.destroy())
for i, name in enumerate(M.MODES, 1):          # 1, 2, 3 - режимы по порядку карточек
    win.bind(str(i), lambda e, n=name: choose(n))
    win.bind("<KP_%d>" % i, lambda e, n=name: choose(n))
win.bind("<FocusOut>", lambda e: win.after(150, lambda: win.focus_displayof() is None and win.destroy()))
win.after(80, lambda: (win.lift(), win.focus_force()))
ui.live(win)                      # плавная подсветка кнопок и ссылок при наведении
win.mainloop()
