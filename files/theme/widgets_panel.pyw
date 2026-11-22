"""Панель настройки виджетов Garasu. Сверху вкладки с виджетами, ниже настройки выбранного.
Открывается шестерёнкой на рамке выделенного виджета (сразу на его вкладке) или ссылкой
«Виджеты» в панели тем:   pythonw widgets_panel.pyw [имя виджета]
Пока панель открыта, включён режим редактирования: виджеты можно выделять, двигать и растягивать
мышкой (положение и размер задаются только так). Закрыл панель - виджеты снова закреплены.
Включение виджета и смена вида применяются сразу и только к этому виджету, остальные не перезапускаются.
Закрыть: «Готово», Esc или крестик."""
import os, sys, json, copy, ctypes, subprocess
from ctypes import wintypes

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import widgets as W
import ui
import glass

TITLE = W.PANEL_TITLE
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

import fonts as _fonts                     # на Windows 10 шрифты Windows 11 подменяются
FONT, ICONS = _fonts.UI, _fonts.ICONS
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
cfg["all"]["edit"] = True                    # панель открыта = режим редактирования
W.save(cfg)
applied = W.geometry(cfg)
job = None
current = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in W.ORDER else W.ORDER[0]
controls = []

win = tk.Tk()
win.title(TITLE)
win.overrideredirect(True)
win.attributes("-topmost", True)
ui.hidden(win, 0.93)
win.configure(bg=BG)
SW, SH = win.winfo_screenwidth(), win.winfo_screenheight()
WIDTH = 460
body = tk.Frame(win, bg=BG, padx=16, pady=10)
body.pack(fill="both", expand=True)


def pull_moves():
    """Положение и размер задаются мышкой (их пишет drag.pyw): перед сохранением берём их с диска,
    чтобы панель не затёрла свежий перенос старыми значениями."""
    disk = W.load()
    for k in W.ORDER:
        for g in ("x", "y", "scale", "cols", "rows"):      # cols, rows — ширина и высота ярлыков (края рамки)
            if g in disk[k]:
                cfg[k][g] = disk[k][g]


def changed(geo=False):
    """Сохранить настройки; если виджет включили, выключили или сменили его вид - применить только к нему."""
    global job
    pull_moves()
    W.save(cfg)
    if geo:
        if job:
            win.after_cancel(job)
        job = win.after(250, apply_geo)


def apply_geo():
    global job, applied
    job = None
    pull_moves()
    applied = W.live(cfg, applied)


def toggle(parent, key, name, text, geo=False, big=False):
    """Стеклянный переключатель (glass.Toggle) с подписью. Щелчок по подписи тоже переключает."""
    f = tk.Frame(parent, bg=BG, cursor="hand2")
    lab = tk.Label(f, text=text, font=(FONT, 11 if big else 9, "bold" if big else "normal"), bg=BG)

    def paint():
        on = cfg[key][name]
        lab.configure(fg=(ACC if big else FG) if on else MUTED)

    def flip(on):
        cfg[key][name] = bool(on)
        paint()
        changed(geo)
        if name == "on":
            draw_tabs()

    sw = glass.Toggle(f, cfg[key][name], flip, bg=BG, fg=FG, accent=ACC, muted=MUTED, scale=1.1 if big else .9)
    sw.pack(side="left")
    lab.pack(side="left", padx=(6, 0))
    for w in (f, lab):
        w.bind("<Button-1>", lambda e: sw.set(not sw.on, animate=True, notify=True))

    def draw():
        sw.set(cfg[key][name], animate=False, notify=False)
        paint()

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
    def pick(v):
        cfg[key][name] = v
        changed(True)

    seg = glass.Segment(row, variants, cfg[key][name], pick, bg=BG, fg=FG, accent=ACC, muted=MUTED)
    seg.pack(side="left", padx=(2, 0))

    def draw():
        seg.set(cfg[key][name], animate=False, notify=False)
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


def links_editor(parent, key, name):
    """Список ярлыков: название можно поправить, крестик удаляет. Кнопки добавляют программу (файл) или папку."""
    import icons
    box = tk.Frame(parent, bg=BG)
    box.pack(fill="x", pady=(8, 0))
    rows = []

    def commit(e=None):
        changed_ = False
        for (t,), it in zip(rows, cfg[key][name]):
            if t.get().strip() != it.get("title", ""):
                it["title"] = t.get().strip()
                changed_ = True
        if changed_:
            changed(False)

    def remove(i):
        commit()
        del cfg[key][name][i]
        build()
        changed(True)

    def add(folder):
        commit()
        win.attributes("-topmost", False)
        if folder:
            p = filedialog.askdirectory(parent=win, title="Папка для ярлыка")
        else:
            p = filedialog.askopenfilename(parent=win, title="Программа или файл для ярлыка",
                                           filetypes=[("Программы и ярлыки", "*.exe *.lnk *.url"), ("Все файлы", "*.*")])
        win.attributes("-topmost", True)
        if not p:
            return
        p = os.path.normpath(p)
        title = os.path.splitext(os.path.basename(p))[0] if not folder else (os.path.basename(p) or p)
        cfg[key][name].append({"title": title[:24], "path": p, "icon": icons.save_icon(p, W.ICONS)})
        build()
        changed(True)

    def build():
        for w in box.winfo_children():
            w.destroy()
        rows.clear()
        for i, it in enumerate(cfg[key][name]):
            line = tk.Frame(box, bg=BG)
            line.pack(fill="x", pady=2)
            t = tk.Entry(line, width=16, font=(FONT, 9), bg=TROUGH, fg=FG, insertbackground=FG, relief="flat",
                         highlightthickness=1, highlightbackground=TROUGH, highlightcolor=ACC)
            t.insert(0, it.get("title", ""))
            t.pack(side="left", ipady=3)
            xb = tk.Label(line, text="\ue711", font=(ICONS, 8), bg=BG, fg=MUTED, cursor="hand2", padx=6)
            xb.pack(side="right")
            xb.bind("<Button-1>", lambda e, i=i: remove(i))
            p = it.get("path", "")
            tk.Label(line, text=("…" + p[-30:]) if len(p) > 31 else p, font=(FONT, 8), bg=BG, fg=MUTED,
                     anchor="w").pack(side="left", padx=8, fill="x", expand=True)
            t.bind("<FocusOut>", commit)
            t.bind("<Return>", commit)
            rows.append((t,))
        if not cfg[key][name]:
            tk.Label(box, text="Пока пусто. Добавь программы и папки, которые открываешь чаще всего.",
                     font=(FONT, 9), bg=BG, fg=MUTED, anchor="w").pack(fill="x")
        btns = tk.Frame(box, bg=BG)
        btns.pack(anchor="w", pady=(6, 0))
        button(btns, "+ Программа", lambda: add(False)).pack(side="left")
        button(btns, "+ Папка", lambda: add(True)).pack(side="left", padx=8)
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
x.bind("<Button-1>", lambda e: finish())


def finish(e=None):
    """Закрыть панель и выйти из режима редактирования."""
    try:
        pull_moves()
        cfg["all"]["edit"] = False
        W.save(cfg)
    finally:
        win.destroy()


# панель можно перетащить за шапку, если она закрывает нужный виджет
# Место запоминается в panel_pos.json: панель остаётся там же при смене вкладки и при следующем открытии.
POS_FILE = os.path.join(W.here, "panel_pos.json")
pos = None                                   # None = по центру экрана
try:
    p_ = json.load(open(POS_FILE, encoding="utf-8"))
    pos = [int(p_[0]), int(p_[1])]
except Exception:
    pass
grab = [0, 0]
def drag_start(e):
    grab[0], grab[1] = e.x_root - win.winfo_x(), e.y_root - win.winfo_y()
def drag_move(e):
    global pos
    pos = [e.x_root - grab[0], e.y_root - grab[1]]
    win.geometry("+%d+%d" % tuple(pos))
def drag_end(e):
    if pos:
        try:
            json.dump(pos, open(POS_FILE, "w", encoding="utf-8"))
        except OSError:
            pass
for w_ in [head] + [w for w in head.winfo_children() if w is not x]:
    w_.bind("<Button-1>", drag_start)
    w_.bind("<B1-Motion>", drag_move)
    w_.bind("<ButtonRelease-1>", drag_end)

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
    controls.append(slider(content, key, "opacity", "Непрозрачность", 20, 100, False, "%"))
    bools = [o for o in W.OPTIONS[key] if o[2] == "bool"]
    for o in W.OPTIONS[key]:
        if o[2] == "range":
            controls.append(slider(content, key, o[0], o[1], o[3], o[4], False))
        elif o[2] == "file":
            controls.append(file_row(content, key, o[0], o[1]))
        elif o[2] == "dates":
            controls.append(dates_editor(content, key, o[0]))
        elif o[2] == "links":
            controls.append(links_editor(content, key, o[0]))
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


def use_layout(name):
    """Готовая расстановка: включает нужные виджеты и ставит их по местам (остальные выключает)."""
    pull_moves()
    W.layout(cfg, name)
    W.save(cfg)                       # места поменялись: пишем сразу, чтобы pull_moves не вернул старые
    redraw_controls()
    draw_tabs()
    show(current)
    changed(True)


lay = tk.Frame(body, bg=BG)
lay.pack(fill="x", pady=(0, 10))
tk.Label(lay, text="Расстановка", font=(FONT, 9), bg=BG, fg=MUTED).pack(side="left", padx=(0, 8))
for lk, (ltitle, _spec) in W.LAYOUTS.items():
    button(lay, ltitle, lambda lk=lk: use_layout(lk)).pack(side="left", padx=(0, 6))
gen = tk.Frame(body, bg=BG)                 # общие настройки вида для всех виджетов
gen.pack(fill="x", pady=(0, 8))
slider(gen, "all", "radius", "Скругление", 6, 44, False, "px")
gen2 = tk.Frame(body, bg=BG)
gen2.pack(fill="x", pady=(0, 10))
toggle(gen2, "all", "anim", "Анимации").pack(side="left", padx=(0, 16))
toggle(gen2, "all", "wallfade", "Плавные обои").pack(side="left", padx=(0, 16))
gen3 = tk.Frame(body, bg=BG)
gen3.pack(fill="x", pady=(0, 10))
toggle(gen3, "all", "adapt", "Тёмный текст на светлых обоях").pack(side="left")
foot = tk.Frame(body, bg=BG)
foot.pack(fill="x")
toggle(foot, "all", "snap", "Привязка (ровно)").pack(side="left", padx=(0, 16))


def engine_toggle(parent):
    """Лёгкие виджеты: рисовать их на Qt (Garasu Classic, ~100 МБ) вместо Zebar (~800 МБ). Флаг — файл classic.on."""
    f = tk.Frame(parent, bg=BG, cursor="hand2")
    lab = tk.Label(f, text="Лёгкие виджеты (Qt)", font=(FONT, 9), bg=BG)

    def paint(on, note=""):
        lab.configure(text="Лёгкие виджеты (Qt)" + note, fg=FG if on else MUTED)

    def flip(on):
        import subprocess, threading
        if on:
            ok = subprocess.run([sys.executable, W.CLASSIC, "--check"], creationflags=0x08000000,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
            if not ok:                                   # нет PyQt6: остаёмся на Zebar
                sw.set(False, animate=True, notify=False)
                paint(False, " — нет библиотек Qt")
                return
            open(W.CLASSIC_FLAG, "w").close()
            if os.path.exists(W.CLASSIC_OFF):
                os.remove(W.CLASSIC_OFF)
        else:
            if os.path.exists(W.CLASSIC_FLAG):
                os.remove(W.CLASSIC_FLAG)
            open(W.CLASSIC_OFF, "w").close()             # выбор человека: обновления не включат Qt сами
        paint(on)
        threading.Thread(target=W.restart_zebar, daemon=True).start()

    sw = glass.Toggle(f, W.classic_on(), flip, bg=BG, fg=FG, accent=ACC, muted=MUTED, scale=.9)
    sw.pack(side="left")
    lab.pack(side="left", padx=(6, 0))
    paint(W.classic_on())
    for w in (f, lab):
        w.bind("<Button-1>", lambda e: sw.set(not sw.on, animate=True, notify=True))
    return f


engine_toggle(foot).pack(side="left", padx=(0, 16))


def reset(e):
    cfg[current] = copy.deepcopy(W.DEFAULTS[current])
    W.save(cfg)                       # сброс возвращает и место с размером: пишем сразу, чтобы pull_moves их не вернул
    redraw_controls()
    draw_tabs()
    changed(True)


done = tk.Label(foot, text="Готово", font=(FONT, 9, "bold"), bg=ACC, fg=BG, cursor="hand2", padx=14, pady=5)
done.pack(side="right")
done.bind("<Button-1>", lambda e: finish())
r = tk.Label(foot, text="Сбросить этот виджет", font=(FONT, 9), bg=BG, fg=MUTED, cursor="hand2")
r.pack(side="right", padx=(0, 14))
r.bind("<Button-1>", reset)
tk.Label(body, text="Режим редактирования: кликни по виджету и тащи его, квадратик в углу меняет размер.",
         font=(FONT, 8), bg=BG, fg=MUTED, anchor="w").pack(fill="x", pady=(8, 0))


def watch():
    """Раз в секунду: подтянуть переносы мышкой и проверить, что режим редактирования всё ещё включён на диске."""
    global applied
    if job is None:
        disk = W.load()
        pull_moves()
        applied = W.geometry(cfg)
        if not disk["all"].get("edit"):
            W.save(cfg)
    win.after(1000, watch)


def resize():
    win.update_idletasks()
    h = body.winfo_reqheight()
    if pos:                                   # панель двигали: остаётся на своём месте (но не за краем экрана)
        px, py = max(0, min(pos[0], SW - WIDTH)), max(0, min(pos[1], SH - 80))
    else:
        px, py = (SW - WIDTH) // 2, max(40, (SH - h) // 2)
    win.geometry("%dx%d+%d+%d" % (WIDTH, h, px, py))


show(current)
win.after(1000, watch)
try:
    hwnd = wintypes.HWND(u.GetParent(win.winfo_id()) or win.winfo_id())
    ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(ctypes.c_int(2)), 4)
except Exception:
    pass
win.bind("<Escape>", finish)
win.protocol("WM_DELETE_WINDOW", finish)
win.after(80, lambda: (win.lift(), win.focus_force()))
ui.live(win)                      # плавная подсветка кнопок и ссылок при наведении
win.mainloop()
