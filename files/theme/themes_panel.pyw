"""Панель выбора темы Garasu. Открывается кнопкой с палитрой на панели.
Клик по картинке - применить тему. Esc, крестик или клик мимо - закрыть.
Повторный запуск, когда панель уже открыта, закрывает её (кнопка работает как переключатель)."""
import os, sys, json, ctypes, subprocess
from ctypes import wintypes

TITLE = "Ryoku Themes"
u = ctypes.windll.user32
u.FindWindowW.restype = wintypes.HWND
old = u.FindWindowW(None, TITLE)
if old:
    u.PostMessageW(old, 0x0010, 0, 0)   # WM_CLOSE
    sys.exit()

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

import tkinter as tk
from PIL import Image, ImageTk, ImageDraw, ImageOps

here = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(here)
thumbs = os.path.join(here, "thumbs")
os.makedirs(thumbs, exist_ok=True)
themes = json.load(open(os.path.join(here, "themes.json"), encoding="utf-8"))
themes = [t for t in themes if os.path.exists(t["wallpaper"] if os.path.isabs(t["wallpaper"]) else os.path.join(root_dir, "wallpapers", t["wallpaper"]))]
ZTHEME = os.path.join(os.path.expanduser("~"), ".glzr", "zebar", "ryoku", "theme.json")

COLS, TW, TH, GAP, PAD = 3, 208, 117, 12, 16
FONT = "Segoe UI Variable Text"


def colors():
    c = {"pill": "#0c080a", "fg": "#f7e8ed", "muted": "#8d7e84", "accent": "#eeb7d0", "id": ""}
    try:
        c.update(json.load(open(ZTHEME, encoding="utf-8")))
    except Exception:
        pass
    return c


def wall_path(t):
    w = t["wallpaper"]
    return w if os.path.isabs(w) else os.path.join(root_dir, "wallpapers", w)


def thumb(t):
    """Уменьшенная картинка темы (кэшируется в theme/thumbs)."""
    p = os.path.join(thumbs, t["id"] + ".png")
    src = wall_path(t)
    if not os.path.exists(p) or os.path.getmtime(p) < os.path.getmtime(src):
        im = ImageOps.fit(Image.open(src).convert("RGB"), (TW * 2, TH * 2), Image.LANCZOS)
        im.save(p)
    return Image.open(p).convert("RGB")


def rounded(im, bg, border=None):
    """Скруглённые углы поверх цвета фона панели (+ рамка у активной темы)."""
    S = 2
    im = im.resize((TW * S, TH * S), Image.LANCZOS)
    mask = Image.new("L", im.size, 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle((0, 0, im.size[0] - 1, im.size[1] - 1), radius=12 * S, fill=255)
    out = Image.new("RGB", im.size, bg)
    out.paste(im, (0, 0), mask)
    if border:
        ImageDraw.Draw(out).rounded_rectangle((2, 2, im.size[0] - 3, im.size[1] - 3), radius=11 * S,
                                              outline=border, width=3 * S)
    return out.resize((TW, TH), Image.LANCZOS)


win = tk.Tk()
win.title(TITLE)
win.overrideredirect(True)
win.attributes("-topmost", True)
win.attributes("-alpha", 0.93)
rows = (len(themes) + COLS - 1) // COLS
W = PAD * 2 + COLS * TW + (COLS - 1) * GAP
H = PAD + 40 + rows * (TH + 30 + GAP) + PAD - GAP + 72
sw = win.winfo_screenwidth()
win.geometry("%dx%d+%d+%d" % (W, H, sw - W - 12, 50))

cells, imgs = [], {}
head = tk.Frame(win)
head.place(x=PAD, y=PAD - 4, width=W - PAD * 2, height=36)
kanji = tk.Label(head, text="硝", font=(FONT, 15, "bold"))
kanji.pack(side="left")
title = tk.Label(head, text="  ТЕМЫ", font=(FONT, 10, "bold"))
title.pack(side="left")
hint = tk.Label(head, text="", font=(FONT, 9))
hint.pack(side="left", padx=12)
close = tk.Label(head, text="", font=("Segoe Fluent Icons", 10), cursor="hand2", padx=8, pady=4)
close.pack(side="right")
close.bind("<Button-1>", lambda e: win.destroy())
gear = tk.Label(head, text="Виджеты  ›", font=(FONT, 9, "bold"), cursor="hand2", padx=10, pady=4)
gear.pack(side="right")


def open_widgets(e):
    subprocess.Popen([sys.executable.replace("python.exe", "pythonw.exe"), os.path.join(here, "widgets_panel.pyw")],
                     creationflags=0x08000000)
    win.destroy()


gear.bind("<Button-1>", open_widgets)

for i, t in enumerate(themes):
    x = PAD + (i % COLS) * (TW + GAP)
    y = PAD + 40 + (i // COLS) * (TH + 30 + GAP)
    pic = tk.Label(win, bd=0, cursor="hand2")
    pic.place(x=x, y=y, width=TW, height=TH)
    name = tk.Label(win, text=t["name"].split(":")[0], font=(FONT, 10, "bold"), anchor="w")
    name.place(x=x + 2, y=y + TH + 4, width=TW - 60, height=22)
    tid = tk.Label(win, text=t["id"], font=(FONT, 9), anchor="e")
    tid.place(x=x + TW - 60, y=y + TH + 4, width=58, height=22)
    for wdg in (pic, name, tid):
        wdg.bind("<Button-1>", lambda e, t=t: apply(t))
    cells.append((t, pic, name, tid))


SETTINGS = os.path.join(here, "settings.json")


def options():
    o = {"dock": "auto", "side_gap": 24}
    try:
        o.update(json.load(open(SETTINGS, encoding="utf-8")))
    except Exception:
        pass
    return o


dock_lab = tk.Label(win, font=(FONT, 9, "bold"), cursor="hand2", anchor="w")
dock_lab.place(x=PAD, y=H - 72, width=W - PAD * 2, height=26)


def dock_text():
    always = options()["dock"] == "always"
    dock_lab.configure(text="Док внизу:  " + ("всегда виден" if always else "прячется, выезжает от нижнего края") +
                            "      (клик - переключить)")


def dock_toggle(e):
    o = options()
    o["dock"] = "auto" if o["dock"] == "always" else "always"
    json.dump(o, open(SETTINGS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    dock_lab.configure(text="применяю…")
    win.update_idletasks()
    subprocess.run([sys.executable.replace("python.exe", "pythonw.exe"), os.path.join(here, "ryoku.py")],
                   creationflags=0x08000000)
    dock_text()
    win.after(150, grab_focus)


dock_lab.bind("<Button-1>", dock_toggle)

# тема по времени суток: сторож (watcher.pyw) сам включает дневную или ночную тему в нужный час
THEME_IDS = [t["id"] for t in themes]
AT_DEFAULT = {"on": False, "day": "sky", "night": "night", "day_from": 8, "night_from": 20}
at_row = tk.Frame(win)
at_row.place(x=PAD, y=H - 40, width=W - PAD * 2, height=26)
at_on = tk.Label(at_row, font=(FONT, 9, "bold"), cursor="hand2")
at_day = tk.Label(at_row, font=(FONT, 9), cursor="hand2")
at_night = tk.Label(at_row, font=(FONT, 9), cursor="hand2")
for _w in (at_on, at_day, at_night):
    _w.pack(side="left", padx=(0, 16))


def at_get():
    a = dict(AT_DEFAULT)
    a.update(options().get("auto_theme") or {})
    return a


def at_save(a):
    o = options()
    o["auto_theme"] = a
    json.dump(o, open(SETTINGS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    at_text()


def at_text():
    a = at_get()
    at_on.configure(text="Тема по времени:  " + ("вкл" if a["on"] else "выкл"))
    at_day.configure(text="с %d:00 - %s" % (a["day_from"], a["day"]))
    at_night.configure(text="с %d:00 - %s" % (a["night_from"], a["night"]))


def at_cycle(part):
    a = at_get()
    i = THEME_IDS.index(a[part]) if a[part] in THEME_IDS else -1
    a[part] = THEME_IDS[(i + 1) % len(THEME_IDS)]
    at_save(a)


at_on.bind("<Button-1>", lambda e: at_save(dict(at_get(), on=not at_get()["on"])))
at_day.bind("<Button-1>", lambda e: at_cycle("day"))
at_night.bind("<Button-1>", lambda e: at_cycle("night"))


def paint():
    c = colors()
    bg = c["pill"]
    win.configure(bg=bg)
    head.configure(bg=bg)
    kanji.configure(bg=bg, fg=c["accent"])
    title.configure(bg=bg, fg=c["fg"])
    hint.configure(bg=bg, fg=c["muted"], text=c.get("name", ""))
    close.configure(bg=bg, fg=c["muted"])
    gear.configure(bg=bg, fg=c["accent"])
    dock_lab.configure(bg=bg, fg=c["fg"])
    dock_text()
    at_row.configure(bg=bg)
    at_on.configure(bg=bg, fg=c["fg"])
    at_day.configure(bg=bg, fg=c["accent"])
    at_night.configure(bg=bg, fg=c["accent"])
    at_text()
    for t, pic, name, tid in cells:
        active = t["id"] == c.get("id")
        try:
            imgs[t["id"]] = ImageTk.PhotoImage(rounded(thumb(t), bg, c["accent"] if active else None))
            pic.configure(image=imgs[t["id"]], bg=bg)
        except Exception:
            pic.configure(text="нет картинки", bg=bg, fg=c["muted"])
        name.configure(bg=bg, fg=c["accent"] if active else c["fg"])
        tid.configure(bg=bg, fg=c["muted"])


def apply(t):
    hint.configure(text="применяю…")
    win.update_idletasks()
    subprocess.run([sys.executable.replace("python.exe", "pythonw.exe"), os.path.join(here, "ryoku.py"), t["id"]],
                   creationflags=0x08000000)
    paint()
    win.after(150, grab_focus)


def grab_focus():
    win.lift()
    win.focus_force()


def on_focus_out(e):
    # закрываемся, только если фокус ушёл в другое окно, а не на наш же элемент
    win.after(120, lambda: win.focus_displayof() is None and win.destroy())


paint()
win.update_idletasks()
try:   # скруглённые углы и тёмная рамка окна (Windows 11)
    hwnd = wintypes.HWND(u.GetParent(win.winfo_id()) or win.winfo_id())
    ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(ctypes.c_int(2)), 4)
except Exception:
    pass
win.bind("<Escape>", lambda e: win.destroy())
win.bind("<FocusOut>", on_focus_out)
win.after(80, grab_focus)
win.mainloop()
