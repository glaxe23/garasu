"""Микшер громкости Garasu: общая громкость и отдельный ползунок для каждого приложения со звуком.
Открывается правым кликом по значку громкости на панели или кликом по динамику в плеере на обоях.
Клик по значку динамика в строке выключает или включает звук этого приложения.
Закрыть: Esc, крестик, клик мимо или повторное открытие."""
import os, sys, ctypes
from ctypes import wintypes, cast, POINTER

TITLE = "Ryoku Mixer"
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
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ui
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

C = ui.colors()
BG, FG, MUTED, ACC, TROUGH = C["BG"], C["FG"], C["MUTED"], C["ACC"], C["TROUGH"]
FONT, ICONS = ui.FONT, ui.ICONS
NICE = {"chrome": "Google Chrome", "msedge": "Microsoft Edge", "firefox": "Firefox", "discord": "Discord",
        "steam": "Steam", "spotify": "Spotify", "telegram": "Telegram", "obs64": "OBS", "browser": "Яндекс Браузер",
        "robloxplayerbeta": "Roblox", "vlc": "VLC", "steelseriessonar": "SteelSeries Sonar", "claude": "Claude"}
HIDE = {"audiodg", "pythonw", "python"}          # служебные процессы, в микшере не нужны


def exe_icon(path, size=22):
    """Значок программы из её exe-файла -> картинка для tkinter (None, если достать не удалось)."""
    try:
        from PIL import Image, ImageTk
        import ctypes.wintypes as wt
        shell32, user32, gdi32 = ctypes.windll.shell32, ctypes.windll.user32, ctypes.windll.gdi32

        class SHFILEINFO(ctypes.Structure):
            _fields_ = [("hIcon", ctypes.c_void_p), ("iIcon", ctypes.c_int), ("dwAttributes", wt.DWORD),
                        ("szDisplayName", ctypes.c_wchar * 260), ("szTypeName", ctypes.c_wchar * 80)]

        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [("biSize", wt.DWORD), ("biWidth", ctypes.c_long), ("biHeight", ctypes.c_long),
                        ("biPlanes", wt.WORD), ("biBitCount", wt.WORD), ("biCompression", wt.DWORD),
                        ("biSizeImage", wt.DWORD), ("biXPelsPerMeter", ctypes.c_long),
                        ("biYPelsPerMeter", ctypes.c_long), ("biClrUsed", wt.DWORD), ("biClrImportant", wt.DWORD)]

        shell32.SHGetFileInfoW.argtypes = [ctypes.c_wchar_p, wt.DWORD, ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint]
        shell32.SHGetFileInfoW.restype = ctypes.c_void_p
        for f in (user32.GetDC, gdi32.CreateCompatibleDC, gdi32.CreateDIBSection, gdi32.SelectObject):
            f.restype = ctypes.c_void_p
        user32.GetDC.argtypes = [ctypes.c_void_p]
        gdi32.CreateCompatibleDC.argtypes = [ctypes.c_void_p]
        gdi32.CreateDIBSection.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint,
                                           ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p, wt.DWORD]
        gdi32.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        gdi32.DeleteObject.argtypes = [ctypes.c_void_p]
        gdi32.DeleteDC.argtypes = [ctypes.c_void_p]
        user32.ReleaseDC.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        user32.DestroyIcon.argtypes = [ctypes.c_void_p]
        user32.DrawIconEx.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int,
                                      ctypes.c_int, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint]

        info = SHFILEINFO()
        if not shell32.SHGetFileInfoW(path, 0, ctypes.byref(info), ctypes.sizeof(info), 0x100) or not info.hIcon:
            return None
        N = 32
        bmi = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), N, -N, 1, 32, 0, 0, 0, 0, 0, 0)
        screen = user32.GetDC(None)
        dc = gdi32.CreateCompatibleDC(screen)
        bits = ctypes.c_void_p()
        bmp = gdi32.CreateDIBSection(dc, ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0)
        old = gdi32.SelectObject(dc, bmp)
        user32.DrawIconEx(dc, 0, 0, info.hIcon, N, N, 0, None, 3)
        img = Image.frombuffer("RGBA", (N, N), ctypes.string_at(bits, N * N * 4), "raw", "BGRA", 0, 1).copy()
        gdi32.SelectObject(dc, old)
        gdi32.DeleteObject(bmp)
        gdi32.DeleteDC(dc)
        user32.ReleaseDC(None, screen)
        user32.DestroyIcon(info.hIcon)
        if not img.getbbox():
            return None
        return img.resize((size, size), Image.LANCZOS)
    except Exception:
        return None


def master():
    dev = AudioUtilities.GetSpeakers()
    try:
        return dev.EndpointVolume
    except AttributeError:
        return cast(dev.Activate(IAudioEndpointVolume._iid_, 23, None), POINTER(IAudioEndpointVolume))


def exe_path(ss):
    for s in ss:
        try:
            return s.Process.exe()
        except Exception:
            pass
    return None


def apps():
    """{имя процесса: [звуковые сессии]} для всех приложений, у которых есть звук."""
    out = {}
    for s in AudioUtilities.GetAllSessions():
        if not s.Process:
            continue
        key = s.Process.name().lower().replace(".exe", "")
        if key not in HIDE:
            out.setdefault(key, []).append(s)
    return out


win = tk.Tk()
win.title(TITLE)
win.overrideredirect(True)
win.attributes("-topmost", True)
ui.hidden(win, 0.94)
win.configure(bg=BG)
SW = win.winfo_screenwidth()
WIDTH = 400
body = tk.Frame(win, bg=BG, padx=16, pady=10)
body.pack(fill="both", expand=True)

head = tk.Frame(body, bg=BG)
head.pack(fill="x", pady=(0, 6))
tk.Label(head, text="硝", font=(FONT, 15, "bold"), bg=BG, fg=ACC).pack(side="left")
tk.Label(head, text="  ГРОМКОСТЬ", font=(FONT, 10, "bold"), bg=BG, fg=FG).pack(side="left")
x = tk.Label(head, text="", font=(ICONS, 10), bg=BG, fg=MUTED, cursor="hand2", padx=8, pady=4)
x.pack(side="right")
x.bind("<Button-1>", lambda e: win.destroy())
rows_box = tk.Frame(body, bg=BG)
rows_box.pack(fill="x")
icons = {}                     # картинки значков (их нужно хранить, иначе tkinter их выбросит)
rows = {}                      # ключ -> (ползунок, подпись числа, значок, получить, поставить, mute-получить, mute-поставить)


def icon_for(v, muted):
    return "" if muted or v == 0 else "" if v < 34 else "" if v < 67 else ""


def add_row(key, title, get, put, get_mute, put_mute, big=False, exe=None):
    row = tk.Frame(rows_box, bg=BG)
    row.pack(fill="x", pady=(2, 8 if big else 4))
    top = tk.Frame(row, bg=BG)
    top.pack(fill="x")
    img = exe_icon(exe) if exe else None
    if img is not None:                               # значок самого приложения перед названием
        from PIL import ImageTk
        icons[key] = ImageTk.PhotoImage(img)
        tk.Label(top, image=icons[key], bg=BG).pack(side="left", padx=(2, 8))
    tk.Label(top, text=title, font=(FONT, 10 if big else 9, "bold"), bg=BG, fg=ACC if big else FG, anchor="w").pack(side="left")
    num = tk.Label(top, font=(FONT, 9), bg=BG, fg=MUTED)
    num.pack(side="right")
    line = tk.Frame(row, bg=BG)
    line.pack(fill="x")
    ico = tk.Label(line, font=(ICONS, 12), bg=BG, fg=FG, cursor="hand2", width=2)
    ico.pack(side="left")

    def change(v):
        try:
            put(v / 100)
        except Exception:
            pass
        paint(key)

    s = ui.Slider(line, 0, 100, 0, change, bg=BG, track=TROUGH, accent=ACC, knob=FG, step=4)
    s.pack(side="left", fill="x", expand=True, padx=(4, 0))

    def toggle_mute(e):
        try:
            put_mute(not get_mute())
        except Exception:
            pass
        paint(key)

    ico.bind("<Button-1>", toggle_mute)
    def all_of(w):                                   # колёсико над любой частью строки крутит её громкость
        yield w
        for c in w.winfo_children():
            yield from all_of(c)
    for w in all_of(row):
        if w is not s:
            w.bind("<MouseWheel>", s.wheel)
    rows[key] = (s, num, ico, get, get_mute, row)
    paint(key, sync=True)


def paint(key, sync=False):
    s, num, ico, get, get_mute, row = rows[key]
    try:
        v, m = round(get() * 100), bool(get_mute())
    except Exception:
        return
    if sync and not s.dragging:
        s.set(v)
    num.configure(text="выкл" if m else str(s.value))
    ico.configure(text=icon_for(s.value, m), fg=MUTED if m else FG)


def build():
    for w in rows_box.winfo_children():
        w.destroy()
    rows.clear()
    try:
        ev = master()
        add_row("*", "Общая громкость", ev.GetMasterVolumeLevelScalar, lambda v: ev.SetMasterVolumeLevelScalar(v, None),
                ev.GetMute, lambda m: ev.SetMute(m, None), big=True)
    except Exception as e:
        tk.Label(rows_box, text="Нет доступа к общей громкости: %s" % e, font=(FONT, 9), bg=BG, fg=MUTED).pack(anchor="w")
    found = apps()
    for key in sorted(found, key=lambda k: NICE.get(k, k).lower()):
        ss = found[key]
        add_row(key, NICE.get(key, key.capitalize()),
                lambda ss=ss: max(s.SimpleAudioVolume.GetMasterVolume() for s in ss),
                lambda v, ss=ss: [s.SimpleAudioVolume.SetMasterVolume(v, None) for s in ss],
                lambda ss=ss: all(s.SimpleAudioVolume.GetMute() for s in ss),
                lambda m, ss=ss: [s.SimpleAudioVolume.SetMute(m, None) for s in ss],
                exe=exe_path(ss))
    if not found:
        tk.Label(rows_box, text="Сейчас ни одно приложение не издаёт звук.", font=(FONT, 9), bg=BG, fg=MUTED).pack(anchor="w", pady=6)
    win.update_idletasks()
    win.geometry("%dx%d+%d+%d" % (WIDTH, body.winfo_reqheight(), SW - WIDTH - 12, 50))
    return set(found)


known = build()


def refresh():
    """Раз в секунду: подтянуть громкость, которую поменяли в другом месте; пересобрать список, если он изменился."""
    global known
    try:
        if set(apps()) != known and not any(r[0].dragging for r in rows.values()):
            known = build()
        else:
            for key in rows:
                paint(key, sync=True)
    except Exception:
        pass
    win.after(1000, refresh)


win.after(1000, refresh)
try:
    hwnd = wintypes.HWND(u.GetParent(win.winfo_id()) or win.winfo_id())
    ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(ctypes.c_int(2)), 4)
except Exception:
    pass
win.bind("<Escape>", lambda e: win.destroy())
win.bind("<FocusOut>", lambda e: win.after(150, lambda: win.focus_displayof() is None and win.destroy()))
win.after(80, lambda: (win.lift(), win.focus_force()))
ui.live(win)                      # плавная подсветка кнопок и ссылок при наведении
win.mainloop()
