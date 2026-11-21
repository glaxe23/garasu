"""Окошко «Новая задача» для виджета «Задачи». Открывается кнопкой + на виджете:   pythonw task_add.pyw
Enter - дописать задачу в заметку (окно остаётся, можно вводить следующую), Esc или клик мимо - закрыть."""
import os, sys, ctypes
from ctypes import wintypes

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tasks
import ui

TITLE = "Ryoku Task"
u = ctypes.windll.user32
u.FindWindowW.restype = wintypes.HWND
if u.FindWindowW(None, TITLE):               # уже открыто
    sys.exit()
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass
import tkinter as tk

import fonts                              # на Windows 10 шрифты Windows 11 подменяются
FONT = fonts.UI
c = ui.colors()
BG, FG, MUTED, ACC = c["BG"], c["FG"], c["MUTED"], c["ACC"]
FIELD = ui.mix(BG, "#ffffff", 0.12)

win = tk.Tk()
win.title(TITLE)
win.overrideredirect(True)
win.attributes("-topmost", True)
ui.hidden(win, 0.96)
win.configure(bg=BG)
box = tk.Frame(win, bg=BG, padx=14, pady=12)
box.pack()
head = tk.Frame(box, bg=BG)
head.pack(fill="x")
tk.Label(head, text="НОВАЯ ЗАДАЧА", font=(FONT, 8, "bold"), bg=BG, fg=ACC).pack(side="left")
info = tk.Label(head, text="Enter — добавить · Esc — закрыть", font=(FONT, 8), bg=BG, fg=MUTED)
info.pack(side="right")
entry = tk.Entry(box, width=38, font=(FONT, 11), bg=FIELD, fg=FG, insertbackground=FG, relief="flat",
                 highlightthickness=1, highlightbackground=FIELD, highlightcolor=ACC)
entry.pack(pady=(8, 0), ipady=6)
added = [0]


def add(e=None):
    text = entry.get().strip()
    if not text:
        return
    try:
        tasks.add(text)
        added[0] += 1
        entry.delete(0, "end")
        info.configure(text="добавлено: %d" % added[0], fg=ACC)
    except Exception as err:
        info.configure(text="не записалось: %s" % err, fg="#ff8a8a")


def close(e=None):
    win.destroy()


entry.bind("<Return>", add)
win.bind("<Escape>", close)
win.bind("<FocusOut>", lambda e: win.after(150, lambda: close() if win.focus_displayof() is None else None))

win.update_idletasks()
pt = wintypes.POINT()
u.GetCursorPos(ctypes.byref(pt))
w, h = win.winfo_reqwidth(), win.winfo_reqheight()
x = max(8, min(pt.x - w + 20, win.winfo_screenwidth() - w - 8))
y = max(8, min(pt.y + 18, win.winfo_screenheight() - h - 60))
win.geometry("+%d+%d" % (x, y))
try:
    hwnd = wintypes.HWND(u.GetParent(win.winfo_id()) or win.winfo_id())
    ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(ctypes.c_int(2)), 4)
except Exception:
    pass
win.after(60, lambda: (win.lift(), win.focus_force(), entry.focus_set()))
ui.live(win)                      # плавная подсветка кнопок и ссылок при наведении
win.mainloop()
