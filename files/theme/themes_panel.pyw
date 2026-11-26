"""Панель выбора темы Garasu. Открывается кнопкой с палитрой на панели.
Темы стоят каруселью: колёсико, стрелки или клик по боковой карточке крутят её,
клик по средней карточке (или Enter) - применить тему. Esc, крестик или клик мимо - закрыть.
Повторный запуск, когда панель уже открыта, закрывает её (кнопка работает как переключатель)."""
import os, sys, json, ctypes, subprocess, time
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
sys.path.insert(0, here)
import glass, ui, wallpaper_engine
from carousel import Carousel
root_dir = os.path.dirname(here)
thumbs = os.path.join(here, "thumbs")
os.makedirs(thumbs, exist_ok=True)
themes = json.load(open(os.path.join(here, "themes.json"), encoding="utf-8"))
themes = [t for t in themes if os.path.exists(t["wallpaper"] if os.path.isabs(t["wallpaper"]) else os.path.join(root_dir, "wallpapers", t["wallpaper"]))]
ZTHEME = os.path.join(os.path.expanduser("~"), ".glzr", "zebar", "ryoku", "theme.json")

COLS, TW, TH, GAP, PAD = 3, 208, 117, 12, 16
CW, CHH, CAR_H = 300, 169, 236          # карточка в карусели и высота карусели
import fonts                              # на Windows 10 шрифты Windows 11 подменяются
FONT = fonts.UI


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
    p = os.path.join(thumbs, t["id"] + "_c.png")             # крупнее прежних: карточка в карусели больше
    src = wall_path(t)
    if not os.path.exists(p) or os.path.getmtime(p) < os.path.getmtime(src):
        if src.lower().endswith((".mp4", ".m4v", ".webm", ".mkv", ".mov", ".avi", ".wmv")):
            frame = os.path.join(thumbs, t["id"] + "_frame.png")      # видеотема: первый кадр достаёт gifwall
            subprocess.run([sys.executable, os.path.join(here, "gifwall.pyw"), "--still", src, frame],
                           creationflags=0x08000000, timeout=40)
            src = frame
        im = ImageOps.fit(Image.open(src).convert("RGB"), (CW * 2, CHH * 2), Image.LANCZOS)
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
ui.hidden(win, 0.93)   # то же число в ALPHA ниже
W = PAD * 2 + COLS * TW + (COLS - 1) * GAP
H = PAD + 40 + CAR_H + 44 + PAD + 126        # шапка, карусель, подпись, три нижние строки
sw = win.winfo_screenwidth()
win.geometry("%dx%d+%d+%d" % (W, H, sw - W - 12, 50))

engine_notice = tk.Label(
    win, text="Чтобы увидеть обои Garasu, выйди из Wallpaper Engine через значок у часов.",
    font=(FONT, 9), anchor="w",
)


def refresh_engine_notice():
    running = wallpaper_engine.is_running()
    if running != bool(engine_notice.place_info()):
        win.geometry(f"{W}x{H + 32 if running else H}")
        if running:
            engine_notice.place(x=PAD, y=H, width=W - PAD * 2, height=24)
        else:
            engine_notice.place_forget()
    win.after(1500, refresh_engine_notice)

cells, imgs = [], {}
head = tk.Frame(win)
head.place(x=PAD, y=PAD - 4, width=W - PAD * 2, height=36)
kanji = tk.Label(head, text="硝", font=(FONT, 15, "bold"))
kanji.pack(side="left")
title = tk.Label(head, text="  ТЕМЫ", font=(FONT, 10, "bold"))
title.pack(side="left")
hint = tk.Label(head, text="", font=(FONT, 9))
hint.pack(side="left", padx=12)
close = tk.Label(head, text="", font=(fonts.ICONS, 10), cursor="hand2", padx=8, pady=4)
close.pack(side="right")
close.bind("<Button-1>", lambda e: win.destroy())
gear = tk.Label(head, text="Виджеты  ›", font=(FONT, 9, "bold"), cursor="hand2", padx=10, pady=4)
gear.pack(side="right")


def open_widgets(e):
    subprocess.Popen([sys.executable.replace("python.exe", "pythonw.exe"), os.path.join(here, "widgets_panel.pyw")],
                     creationflags=0x08000000)
    win.destroy()


gear.bind("<Button-1>", open_widgets)

def theme_index(tid):
    return next((i for i, t in enumerate(themes) if t["id"] == tid), 0)


_items = []
for t in themes:
    try:
        _items.append((t["id"], thumb(t)))
    except Exception:
        _items.append((t["id"], Image.new("RGB", (CW, CHH), "#222222")))
_c0 = colors()
car = Carousel(win, W - PAD * 2, CAR_H, _items, current=theme_index(_c0.get("id")),
               on_pick=lambda i: apply(themes[i]), on_focus=lambda i: show_name(i),
               bg=_c0["pill"], accent=_c0["accent"], card=(CW, CHH))
car.place(x=PAD, y=PAD + 40)
cap = tk.Frame(win)
cap.place(x=PAD, y=PAD + 40 + CAR_H - 6, width=W - PAD * 2, height=40)
cap_name = tk.Label(cap, font=(FONT, 12, "bold"))
cap_sub = tk.Label(cap, font=(FONT, 9))
cap_name.pack()
cap_sub.pack()


def show_name(i):
    """Подпись под каруселью: какая тема в центре и что будет по клику."""
    c = colors()
    t = themes[i]
    cur = t["id"] == c.get("id")
    cap_name.configure(text=t["name"].split(":")[0], fg=c["accent"] if cur else c["fg"])
    sub = t["name"].split(":", 1)[1].strip() if ":" in t["name"] else t["id"]
    cap_sub.configure(text=sub + ("  ·  клик по картинке — переприменить" if cur else "  ·  клик по картинке — применить"))


def spin(k):
    car.go(car.target + k)


win.bind("<Left>", lambda e: spin(-1))
win.bind("<Right>", lambda e: spin(1))
win.bind("<MouseWheel>", lambda e: spin(-1 if e.delta > 0 else 1))
win.bind("<Return>", lambda e: apply(themes[int(car.target)]))


SETTINGS = os.path.join(here, "settings.json")


def options():
    o = {"dock": "auto", "side_gap": 24}
    try:
        o.update(json.load(open(SETTINGS, encoding="utf-8")))
    except Exception:
        pass
    return o


_C0 = colors()
GKW = dict(bg=_C0["pill"], fg=_C0["fg"], accent=_C0["accent"], muted=_C0["muted"])
dock_row = tk.Frame(win, cursor="hand2")
dock_row.place(x=PAD, y=H - 122, width=W - PAD * 2, height=36)
dock_lab = tk.Label(dock_row, font=(FONT, 9, "bold"), cursor="hand2", anchor="w")


def dock_text():
    always = options()["dock"] == "always"
    dock_lab.configure(text="Док внизу:  " + ("всегда виден" if always else "прячется, выезжает от нижнего края"))


def dock_apply():
    win.update_idletasks()
    subprocess.run([sys.executable.replace("python.exe", "pythonw.exe"), os.path.join(here, "ryoku.py")],
                   creationflags=0x08000000)
    dock_text()
    win.after(150, grab_focus)


def dock_set(always):
    o = options()
    o["dock"] = "always" if always else "auto"
    json.dump(o, open(SETTINGS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    dock_lab.configure(text="применяю…")
    win.after(450, dock_apply)                  # сначала даём переключателю доехать, потом применяем


dock_sw = glass.Toggle(dock_row, options()["dock"] == "always", dock_set, scale=.8, **GKW)
dock_sw.pack(side="left")
dock_lab.pack(side="left", padx=(4, 0))
for _w in (dock_row, dock_lab):
    _w.bind("<Button-1>", lambda e: dock_sw.set(not dock_sw.on, animate=True, notify=True))

# тема по времени суток: сторож (watcher.pyw) сам включает дневную или ночную тему в нужный час
THEME_IDS = [t["id"] for t in themes]
AT_DEFAULT = {"on": False, "day": "sky", "night": "night", "day_from": 8, "night_from": 20}
at_row = tk.Frame(win)
at_row.place(x=PAD, y=H - 84, width=W - PAD * 2, height=36)
at_sw = glass.Toggle(at_row, False, lambda on: at_save(dict(at_get(), on=on)), scale=.8, **GKW)
at_on = tk.Label(at_row, text="Тема по времени", font=(FONT, 9, "bold"), cursor="hand2")
at_day = tk.Label(at_row, font=(FONT, 9), cursor="hand2")
at_night = tk.Label(at_row, font=(FONT, 9), cursor="hand2")
at_sw.pack(side="left")
at_on.pack(side="left", padx=(4, 16))
for _w in (at_day, at_night):
    _w.pack(side="left", padx=(0, 16))


# нижняя строка: своя картинка, шпаргалка по клавишам, версия и обновление
busy = [False]                                # пока открыто окно выбора файла, панель не закрывается сама
PYW_ = sys.executable.replace("python.exe", "pythonw.exe")
more = tk.Frame(win)
more.place(x=PAD, y=H - 46, width=W - PAD * 2, height=36)
own = tk.Label(more, text="Своя картинка…", font=(FONT, 9, "bold"), cursor="hand2")
keys = tk.Label(more, text="Клавиши", font=(FONT, 9, "bold"), cursor="hand2")
upd = tk.Label(more, text="", font=(FONT, 9), cursor="hand2")
dock_al = tk.Label(more, text="Док:", font=(FONT, 9, "bold"), cursor="hand2")
own.pack(side="left", padx=(0, 18))
keys.pack(side="left", padx=(0, 18))
dock_al.pack(side="left")


def dock_al_text():
    dock_seg.set("left" if options().get("dock_align") == "left" else "center")


def dock_al_apply():
    win.update_idletasks()
    subprocess.run([PYW_, os.path.join(here, "ryoku.py")], creationflags=0x08000000)
    paint()
    win.after(150, grab_focus)


def dock_al_set(v):
    o = options()
    o["dock_align"] = v
    json.dump(o, open(SETTINGS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    hint.configure(text="применяю…")
    win.after(450, dock_al_apply)               # сначала анимация, потом применяем


dock_seg = glass.Segment(more, [("left", "Слева"), ("center", "По центру")],
                         "left" if options().get("dock_align") == "left" else "center", dock_al_set,
                         font=(FONT, 8, "bold"), height=22, **GKW)
dock_seg.pack(side="left", padx=(2, 0))
upd.pack(side="right")


def own_pick(e):
    """Любая картинка становится обоями, цвета панели и виджетов подбираются под неё."""
    from tkinter import filedialog
    busy[0] = True
    win.attributes("-topmost", False)
    vids = "*.mp4 *.m4v *.webm *.mkv *.mov *.avi *.wmv"
    p = filedialog.askopenfilename(parent=win, title="Картинка, GIF или видео для обоев",
                                   filetypes=[("Картинки, GIF и видео",
                                               "*.jpg *.jpeg *.png *.bmp *.webp *.gif " + vids),
                                              ("Живые обои (GIF и видео)", "*.gif " + vids),
                                              ("Все файлы", "*.*")])
    win.attributes("-topmost", True)
    busy[0] = False
    if p:
        hint.configure(text="применяю…")
        win.update_idletasks()
        r = subprocess.run([PYW_, os.path.join(here, "ryoku.py"), os.path.normpath(p)], creationflags=0x08000000)
        paint()
        if r.returncode:
            hint.configure(text="не получилось открыть этот файл")
    win.after(150, grab_focus)


def keys_open(e):
    subprocess.Popen([PYW_, os.path.join(here, "help_panel.pyw")], creationflags=0x08000000)
    win.destroy()


new_ver = [""]
def upd_click(e):
    """Первый клик проверяет GitHub, второй (если есть новая версия) ставит её."""
    import update
    try:
        if new_ver[0]:
            upd.configure(text="обновляю…")
            win.update_idletasks()
            upd.configure(text=update.apply())
            new_ver[0] = ""
            return
        upd.configure(text="проверяю…")
        win.update_idletasks()
        ver, _url = update.latest()
        if update.num(ver) > update.num(update.local()):
            new_ver[0] = ver
            upd.configure(text="Есть версия %s — установить" % ver)
        else:
            upd.configure(text="v%s — последняя версия" % update.local())
    except Exception as err:
        upd.configure(text="не удалось проверить: нет связи с GitHub")


own.bind("<Button-1>", own_pick)
keys.bind("<Button-1>", keys_open)
try:
    import update as _u
    if _u.local():                              # в папке разработки версии нет: обновление скрыто
        upd.configure(text="v%s · проверить обновление" % _u.local())
        upd.bind("<Button-1>", upd_click)
except Exception:
    pass


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
    at_sw.set(a["on"])
    at_day.configure(text="с %d:00 - %s" % (a["day_from"], a["day"]))
    at_night.configure(text="с %d:00 - %s" % (a["night_from"], a["night"]))


def at_cycle(part):
    a = at_get()
    i = THEME_IDS.index(a[part]) if a[part] in THEME_IDS else -1
    a[part] = THEME_IDS[(i + 1) % len(THEME_IDS)]
    at_save(a)


at_on.bind("<Button-1>", lambda e: at_sw.set(not at_sw.on, animate=True, notify=True))
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
    engine_notice.configure(bg=bg, fg=c["accent"])
    close.configure(bg=bg, fg=c["muted"])
    gear.configure(bg=bg, fg=c["accent"])
    gk = dict(bg=bg, fg=c["fg"], accent=c["accent"], muted=c["muted"])
    for _g in (dock_sw, at_sw, dock_seg):
        _g.recolor(**gk)
    dock_row.configure(bg=bg)
    dock_lab.configure(bg=bg, fg=c["fg"])
    dock_text()
    at_row.configure(bg=bg)
    more.configure(bg=bg)
    own.configure(bg=bg, fg=c["accent"])
    keys.configure(bg=bg, fg=c["accent"])
    dock_al.configure(bg=bg, fg=c["fg"])
    dock_al_text()
    upd.configure(bg=bg, fg=c["muted"])
    at_on.configure(bg=bg, fg=c["fg"])
    at_day.configure(bg=bg, fg=c["accent"])
    at_night.configure(bg=bg, fg=c["accent"])
    at_text()
    car.recolor(bg, c["accent"], theme_index(c.get("id")))
    for _w in (cap, cap_name):
        _w.configure(bg=bg)
    cap_sub.configure(bg=bg, fg=c["muted"])
    show_name(int(car.target))


ALPHA = 0.93


def fade(a0, a1, ms, then=None):
    """Плавно меняет прозрачность окна (около 60 кадров в секунду), потом вызывает then."""
    t0 = time.perf_counter()

    def step():
        u = min(1.0, (time.perf_counter() - t0) * 1000 / ms)
        e = 1 - (1 - u) ** 3                      # быстро в начале, мягко в конце
        win.attributes("-alpha", a0 + (a1 - a0) * e)
        if u < 1:
            win.after(15, step)
        elif then:
            then()
    step()


def apply(t):
    """Тема меняется красиво: панель приглушается, пока ставятся обои и цвета, и проявляется уже в новых."""
    hint.configure(text="применяю…")

    def run():
        win.update_idletasks()
        subprocess.run([sys.executable.replace("python.exe", "pythonw.exe"), os.path.join(here, "ryoku.py"), t["id"]],
                       creationflags=0x08000000)
        paint()
        fade(0.42, ALPHA, 320, lambda: win.after(60, grab_focus))
    fade(ALPHA, 0.42, 140, run)


def grab_focus():
    win.lift()
    win.focus_force()


def on_focus_out(e):
    # закрываемся, только если фокус ушёл в другое окно, а не на наш же элемент
    win.after(120, lambda: not busy[0] and win.focus_displayof() is None and win.destroy())


paint()
refresh_engine_notice()
win.update_idletasks()
try:   # скруглённые углы и тёмная рамка окна (Windows 11)
    hwnd = wintypes.HWND(u.GetParent(win.winfo_id()) or win.winfo_id())
    ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(ctypes.c_int(2)), 4)
except Exception:
    pass
win.bind("<Escape>", lambda e: win.destroy())
win.bind("<FocusOut>", on_focus_out)
win.after(80, grab_focus)
ui.live(win)                      # плавная подсветка кнопок и ссылок при наведении
win.mainloop()
