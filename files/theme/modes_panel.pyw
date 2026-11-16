"""Панель выбора режима Garasu: повседневный, рабочий, игровой. Открывается кнопкой режима на панели.
Клик по карточке включает режим. Закрыть: Esc, клик мимо или повторный клик по кнопке."""
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
import ui, mode as M

C = ui.colors()
BG, FG, MUTED, ACC, TROUGH = C["BG"], C["FG"], C["MUTED"], C["ACC"], C["TROUGH"]
FONT, ICONS = ui.FONT, ui.ICONS
GLYPH = {"daily": "", "work": "", "game": ""}
current = M.options().get("mode", "daily")

win = tk.Tk()
win.title(TITLE)
win.overrideredirect(True)
win.attributes("-topmost", True)
win.attributes("-alpha", 0.94)
win.configure(bg=BG)
SW = win.winfo_screenwidth()
WIDTH = 420
body = tk.Frame(win, bg=BG, padx=16, pady=10)
body.pack(fill="both", expand=True)
head = tk.Frame(body, bg=BG)
head.pack(fill="x", pady=(0, 8))
tk.Label(head, text="硝", font=(FONT, 15, "bold"), bg=BG, fg=ACC).pack(side="left")
tk.Label(head, text="  РЕЖИМ", font=(FONT, 10, "bold"), bg=BG, fg=FG).pack(side="left")
status = tk.Label(head, text="", font=(FONT, 9), bg=BG, fg=MUTED)
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

auto = tk.Label(body, font=(FONT, 9), bg=BG, fg=MUTED, cursor="hand2", anchor="w")
auto.pack(fill="x", pady=(8, 0))


def auto_text():
    on = M.options().get("auto_game", True)
    auto.configure(text="Игровой режим сам при запуске игры из Steam:  " + ("вкл" if on else "выкл"),
                   fg=FG if on else MUTED)


def auto_toggle(e):
    o = M.options()
    o["auto_game"] = not o.get("auto_game", True)
    M.save_options(o)
    auto_text()


auto.bind("<Button-1>", auto_toggle)
auto_text()

win.update_idletasks()
win.geometry("%dx%d+%d+%d" % (WIDTH, body.winfo_reqheight(), SW - WIDTH - 12, 50))
try:
    hwnd = wintypes.HWND(u.GetParent(win.winfo_id()) or win.winfo_id())
    ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(ctypes.c_int(2)), 4)
except Exception:
    pass
win.bind("<Escape>", lambda e: win.destroy())
win.bind("<FocusOut>", lambda e: win.after(150, lambda: win.focus_displayof() is None and win.destroy()))
win.after(80, lambda: (win.lift(), win.focus_force()))
win.mainloop()
