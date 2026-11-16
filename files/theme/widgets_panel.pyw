"""Панель настройки виджетов Garasu. Сверху вкладки с виджетами, ниже настройки выбранного.
Открывается шестерёнкой на рамке выделенного виджета (сразу на его вкладке) или ссылкой
«Виджеты» в панели тем:   pythonw widgets_panel.pyw [имя виджета]
Галочки и прозрачность меняются сразу, положение, размер и включение - через секунду после
того, как отпустил ползунок (Zebar перезапускается). Закрыть: Esc или крестик."""
import os, sys, json, copy, ctypes, subprocess
from ctypes import wintypes

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import widgets as W
import ui

TITLE = "Ryoku Widgets"
u = ctypes.windll.user32
u.FindWindowW.restype = wintypes.HWND
old = u.FindWindowW(None, TITLE)
if old:
    u.PostMessageW(old, 0x0010, 0, 0)        # уже открыта: закрываем старую и открываем заново на нужной вкладке
    import time
    time.sleep(0.25)
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

import tkinter as tk
from tkinter import filedialog

FONT, ICONS = "Segoe UI Variable Text", "Segoe Fluent Icons"
c = {"pill": "#0c080a", "fg": "#f7e8ed", "muted": "#8d7e84", "accent": "#eeb7d0"}
try:
    c.update(json.load(open(os.path.join(W.zdir, "theme.json"), encoding="utf-8")))
except Exception:
    pass
BG, FG, MUTED, ACC = c["pill"], c["fg"], c["muted"], c["accent"]


def mix(a, b, t):
    A = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    B = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(round(A[i] + (B[i] - A[i]) * t) for i in range(3))


TROUGH = mix(BG, "#ffffff", 0.14)
cfg = W.load()
applied = W.geometry(cfg)
job = None
current = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in W.ORDER else W.ORDER[0]
controls = []

win = tk.Tk()
win.title(TITLE)
win.overrideredirect(True)
win.attributes("-topmost", True)
win.attributes("-alpha", 0.93)
win.configure(bg=BG)
SW, SH = win.winfo_screenwidth(), win.winfo_screenheight()
WIDTH = 460
body = tk.Frame(win, bg=BG, padx=16, pady=10)
body.pack(fill="both", expand=True)


def changed(geo=False):
    """Сохранить настройки; если менялось положение - отложенно перезапустить Zebar."""
    global job
    W.save(cfg)
    if geo:
        if job:
            win.after_cancel(job)
        status.configure(text="применяю…")
        job = win.after(900, apply_geo)


def apply_geo():
    global job, applied
    job = None
    if W.geometry(cfg) != applied:
        W.apply(cfg, restart=True)
        applied = W.geometry(cfg)
    status.configure(text="готово")
    win.after(1500, lambda: status.configure(text=""))
    win.after(2500, lambda: (win.lift(), win.attributes("-topmost", True)))


def toggle(parent, key, name, text, geo=False, big=False):
    f = tk.Frame(parent, bg=BG, cursor="hand2")
    box = tk.Label(f, font=(ICONS, 12 if big else 10), bg=BG)
    lab = tk.Label(f, text=text, font=(FONT, 11 if big else 9, "bold" if big else "normal"), bg=BG)
    box.pack(side="left")
    lab.pack(side="left", padx=(5, 0))

    def draw():
        on = cfg[key][name]
        box.configure(text="" if on else "", fg=ACC if on else MUTED)
        lab.configure(fg=(ACC if big else FG) if on else MUTED)

    def click(e):
        cfg[key][name] = not cfg[key][name]
        draw()
        changed(geo)
        if name == "on":
            draw_tabs()

    for w in (f, box, lab):
        w.bind("<Button-1>", click)
    draw()
    f.redraw = draw
    return f


def slider(parent, key, name, text, lo, hi, geo, suffix=""):
    row = tk.Frame(parent, bg=BG)
    tk.Label(row, text=text, font=(FONT, 9), bg=BG, fg=MUTED, width=15, anchor="w").pack(side="left")
    val = tk.Label(row, font=(FONT, 9), bg=BG, fg=FG, width=6, anchor="e")
    val.pack(side="right")
    def move(v):
        cfg[key][name] = int(v)
        val.configure(text=str(cfg[key][name]) + suffix)
        changed(geo)

    s = ui.Slider(row, lo, hi, cfg[key][name], move, bg=BG, track=TROUGH, accent=ACC, knob=FG)
    s.pack(side="left", fill="x", expand=True, padx=4)
    val.configure(text=str(cfg[key][name]) + suffix)
    row.pack(fill="x", pady=2)
    row.redraw = lambda: (s.set(cfg[key][name]), val.configure(text=str(cfg[key][name]) + suffix))
    return row


def choice(parent, key, name, text, variants):
    """Переключатель из нескольких вариантов (например, вид часов). Меняет размер окна, поэтому как положение."""
    row = tk.Frame(parent, bg=BG)
    tk.Label(row, text=text, font=(FONT, 9), bg=BG, fg=MUTED, width=15, anchor="w").pack(side="left")
    labs = {}

    def draw():
        for v, lab in labs.items():
            on = cfg[key][name] == v
            lab.configure(bg=ACC if on else TROUGH, fg=BG if on else FG)

    def pick(v):
        cfg[key][name] = v
        draw()
        changed(True)

    for v, title in variants:
        lab = tk.Label(row, text=title, font=(FONT, 9, "bold"), cursor="hand2", padx=10, pady=4)
        lab.pack(side="left", padx=(4, 0))
        lab.bind("<Button-1>", lambda e, v=v: pick(v))
        labs[v] = lab
    draw()
    row.pack(fill="x", pady=(2, 6))
    row.redraw = draw
    return row


def dates_editor(parent, key, name):
    """Список дат для счётчиков: название, дата в виде ГГГГ-ММ-ДД, крестик удаляет строку."""
    box = tk.Frame(parent, bg=BG)
    box.pack(fill="x", pady=(8, 0))
    rows = []

    def commit(e=None):
        items = [{"title": t.get().strip(), "date": d.get().strip()} for t, d in rows]
        if items != cfg[key][name]:
            cfg[key][name] = items
            changed(True)

    def remove(i):
        commit()
        del cfg[key][name][i]
        build()
        changed(True)

    def add():
        commit()
        cfg[key][name].append({"title": "", "date": ""})
        build()

    def build():
        for w in box.winfo_children():
            w.destroy()
        rows.clear()
        tk.Label(box, text="Название                                        Дата (ГГГГ-ММ-ДД)", font=(FONT, 8),
                 bg=BG, fg=MUTED, anchor="w").pack(fill="x")
        for i, it in enumerate(cfg[key][name]):
            line = tk.Frame(box, bg=BG)
            line.pack(fill="x", pady=2)
            style = dict(font=(FONT, 9), bg=TROUGH, fg=FG, insertbackground=FG, relief="flat",
                         highlightthickness=1, highlightbackground=TROUGH, highlightcolor=ACC)
            t = tk.Entry(line, width=30, **style)
            t.insert(0, it.get("title", ""))
            t.pack(side="left", ipady=3)
            d = tk.Entry(line, width=12, **style)
            d.insert(0, it.get("date", ""))
            d.pack(side="left", padx=6, ipady=3)
            x = tk.Label(line, text="\ue711", font=(ICONS, 8), bg=BG, fg=MUTED, cursor="hand2", padx=6)
            x.pack(side="left")
            x.bind("<Button-1>", lambda e, i=i: remove(i))
            for en in (t, d):
                en.bind("<FocusOut>", commit)
                en.bind("<Return>", commit)
            rows.append((t, d))
        button(box, "+ Добавить дату", add).pack(anchor="w", pady=(6, 0))
        resize() if "resize" in globals() else None

    build()
    box.redraw = build
    return box


def button(parent, text, action):
    b = tk.Label(parent, text=text, font=(FONT, 9, "bold"), bg=TROUGH, fg=FG, cursor="hand2", padx=12, pady=5)
    b.bind("<Button-1>", lambda e: action())
    return b


def file_row(parent, key, name, text):
    row = tk.Frame(parent, bg=BG)
    tk.Label(row, text=text, font=(FONT, 9), bg=BG, fg=MUTED, anchor="w").pack(anchor="w")
    line = tk.Frame(row, bg=BG)
    line.pack(fill="x", pady=(3, 0))
    lab = tk.Label(line, font=(FONT, 9), bg=BG, fg=FG, anchor="w")

    def draw():
        p = cfg[key][name]
        lab.configure(text=os.path.basename(p) if os.path.exists(p) else "не найдена: " + os.path.basename(p),
                      fg=FG if os.path.exists(p) else "#ff8a8a")

    def choose():
        start = os.path.dirname(cfg[key][name])
        win.attributes("-topmost", False)
        p = filedialog.askopenfilename(parent=win, title=text, initialdir=start if os.path.isdir(start) else None,
                                       filetypes=[("Заметки Markdown", "*.md"), ("Все файлы", "*.*")])
        win.attributes("-topmost", True)
        if p:
            cfg[key][name] = os.path.normpath(p)
            draw()
            changed(False)

    button(line, "Выбрать…", choose).pack(side="right")
    lab.pack(side="left", fill="x", expand=True)
    draw()
    row.pack(fill="x", pady=(6, 2))
    row.redraw = draw
    return row


# ---------------------------------------------------------------- шапка и вкладки
head = tk.Frame(body, bg=BG)
head.pack(fill="x", pady=(0, 6))
tk.Label(head, text="硝", font=(FONT, 15, "bold"), bg=BG, fg=ACC).pack(side="left")
tk.Label(head, text="  ВИДЖЕТЫ", font=(FONT, 10, "bold"), bg=BG, fg=FG).pack(side="left")
status = tk.Label(head, text="", font=(FONT, 9), bg=BG, fg=MUTED)
status.pack(side="left", padx=12)
x = tk.Label(head, text="", font=(ICONS, 10), bg=BG, fg=MUTED, cursor="hand2", padx=8, pady=4)
x.pack(side="right")
x.bind("<Button-1>", lambda e: win.destroy())

tabs = tk.Frame(body, bg=BG)
tabs.pack(fill="x")
tab_labels = {}
for i, k in enumerate(W.ORDER):
    t = tk.Label(tabs, text=W.NAMES[k], font=(FONT, 9, "bold"), cursor="hand2", padx=6, pady=5)
    t.grid(row=i // 4, column=i % 4, sticky="ew", padx=2, pady=2)
    tabs.grid_columnconfigure(i % 4, weight=1, uniform="tab")
    t.bind("<Button-1>", lambda e, k=k: show(k))
    tab_labels[k] = t


def draw_tabs():
    for k, t in tab_labels.items():
        if k == current:
            t.configure(bg=ACC, fg=BG)
        else:
            t.configure(bg=TROUGH, fg=FG if cfg[k]["on"] else MUTED)


content = tk.Frame(body, bg=BG)
content.pack(fill="x", pady=(10, 0))


def show(key):
    """Показать настройки одного виджета."""
    global current
    current = key
    draw_tabs()
    for w in content.winfo_children():
        w.destroy()
    controls.clear()
    t = toggle(content, key, "on", "Показывать «%s»" % W.NAMES[key], geo=True, big=True)
    t.pack(anchor="w", pady=(0, 6))
    controls.append(t)
    for o in W.OPTIONS[key]:
        if o[2] == "choice":
            controls.append(choice(content, key, o[0], o[1], o[3]))
    controls.append(slider(content, key, "x", "Слева, px", 0, SW - 100, True))
    controls.append(slider(content, key, "y", "Сверху, px", 0, SH - 60, True))
    controls.append(slider(content, key, "scale", "Размер", 40, 200, True, "%"))
    controls.append(slider(content, key, "opacity", "Непрозрачность", 20, 100, False, "%"))
    bools = [o for o in W.OPTIONS[key] if o[2] == "bool"]
    for o in W.OPTIONS[key]:
        if o[2] == "range":
            controls.append(slider(content, key, o[0], o[1], o[3], o[4], False))
        elif o[2] == "file":
            controls.append(file_row(content, key, o[0], o[1]))
        elif o[2] == "dates":
            controls.append(dates_editor(content, key, o[0]))
    if bools:
        grid = tk.Frame(content, bg=BG)
        grid.pack(fill="x", pady=(8, 0))
        for i, o in enumerate(bools):
            t = toggle(grid, key, o[0], o[1])
            t.grid(row=i // 3, column=i % 3, sticky="w", padx=(0, 14), pady=2)
            controls.append(t)
    for o in W.OPTIONS[key]:
        if o[2] == "folder":
            os.makedirs(W.PHOTOS, exist_ok=True)
            button(content, o[1], lambda: subprocess.Popen(["explorer.exe", W.PHOTOS])).pack(anchor="w", pady=(10, 0))
    if key == "visual":
        tk.Label(content, text="Полоски двигаются под звук компьютера. Нужен фоновый помощник\n"
                               "и библиотека pyaudiowpatch.", font=(FONT, 9), bg=BG, fg=MUTED,
                 justify="left").pack(anchor="w", pady=(10, 0))
    resize()


def redraw_controls():
    for ctl in controls:
        ctl.redraw()


tk.Frame(body, bg=TROUGH, height=1).pack(fill="x", pady=10)
foot = tk.Frame(body, bg=BG)
foot.pack(fill="x")
toggle(foot, "all", "snap", "Привязка (ровно)").pack(side="left", padx=(0, 16))
toggle(foot, "all", "lock", "Закрепить").pack(side="left")


def reset(e):
    cfg[current] = copy.deepcopy(W.DEFAULTS[current])
    redraw_controls()
    draw_tabs()
    changed(True)


r = tk.Label(foot, text="Сбросить этот виджет", font=(FONT, 9), bg=BG, fg=MUTED, cursor="hand2")
r.pack(side="right")
r.bind("<Button-1>", reset)


def watch():
    """Если виджет перетащили или растянули мышкой, пока панель открыта, - подтянуть значения в ползунки."""
    global applied
    if job is None:
        disk = W.load()
        moved = False
        for k in W.ORDER:
            now = tuple(disk[k][g] for g in ("x", "y", "scale"))   # вид часов мышкой не меняется
            if now != tuple(cfg[k][g] for g in ("x", "y", "scale")):
                cfg[k]["x"], cfg[k]["y"], cfg[k]["scale"] = now
                moved = True
        if moved:
            applied = W.geometry(cfg)
            redraw_controls()
    win.after(1000, watch)


def resize():
    win.update_idletasks()
    win.geometry("%dx%d+%d+%d" % (WIDTH, body.winfo_reqheight(), SW - WIDTH - 12, 50))


show(current)
win.after(1000, watch)
try:
    hwnd = wintypes.HWND(u.GetParent(win.winfo_id()) or win.winfo_id())
    ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(ctypes.c_int(2)), 4)
except Exception:
    pass
win.bind("<Escape>", lambda e: win.destroy())
win.after(80, lambda: (win.lift(), win.focus_force()))
win.mainloop()
