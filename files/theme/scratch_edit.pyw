"""Окно блокнота-черновика для виджета «Черновик». Открывается кликом по виджету:   pythonw scratch_edit.pyw
Текст сохраняется сам при каждом изменении в ~/.glzr/zebar/ryoku/scratch.txt. Esc или клик мимо - закрыть."""
import os, sys, ctypes
from ctypes import wintypes

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ui

TITLE = "Ryoku Scratch"
FILE = os.path.join(os.path.expanduser("~"), ".glzr", "zebar", "ryoku", "scratch.txt")
u = ctypes.windll.user32
u.FindWindowW.restype = wintypes.HWND
if u.FindWindowW(None, TITLE):
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
FIELD = ui.mix(BG, "#ffffff", 0.10)

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
tk.Label(head, text="ЧЕРНОВИК", font=(FONT, 8, "bold"), bg=BG, fg=ACC).pack(side="left")
info = tk.Label(head, text="сохраняется само · Esc — закрыть", font=(FONT, 8), bg=BG, fg=MUTED)
info.pack(side="right")
text = tk.Text(box, width=44, height=12, font=(FONT, 11), bg=FIELD, fg=FG, insertbackground=FG, relief="flat",
               wrap="word", undo=True, padx=8, pady=6, highlightthickness=1, highlightbackground=FIELD,
               highlightcolor=ACC)
text.pack(pady=(8, 0))
try:
    text.insert("1.0", open(FILE, encoding="utf-8").read())
except Exception:
    pass
pending = [None]


def save():
    pending[0] = None
    try:
        tmp = FILE + ".tmp"
        open(tmp, "w", encoding="utf-8").write(text.get("1.0", "end-1c"))
        os.replace(tmp, FILE)
        info.configure(text="сохранено · Esc — закрыть", fg=MUTED)
    except Exception as err:
        info.configure(text="не сохранилось: %s" % err, fg="#ff8a8a")


def changed(e=None):
    if text.edit_modified():
        text.edit_modified(False)
        if pending[0]:
            win.after_cancel(pending[0])
        pending[0] = win.after(400, save)


def close(e=None):
    if pending[0]:
        win.after_cancel(pending[0])
        save()
    win.destroy()


text.bind("<<Modified>>", changed)
win.bind("<Escape>", close)
win.bind("<FocusOut>", lambda e: win.after(150, lambda: close() if win.focus_displayof() is None else None))

win.update_idletasks()
pt = wintypes.POINT()
u.GetCursorPos(ctypes.byref(pt))
w, h = win.winfo_reqwidth(), win.winfo_reqheight()
x = max(8, min(pt.x - w // 2, win.winfo_screenwidth() - w - 8))
y = max(8, min(pt.y + 18, win.winfo_screenheight() - h - 60))
win.geometry("+%d+%d" % (x, y))
try:
    hwnd = wintypes.HWND(u.GetParent(win.winfo_id()) or win.winfo_id())
    ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(ctypes.c_int(2)), 4)
except Exception:
    pass
win.after(60, lambda: (win.lift(), win.focus_force(), text.focus_set(), text.mark_set("insert", "end")))
ui.live(win)                      # плавная подсветка кнопок и ссылок при наведении
win.mainloop()
