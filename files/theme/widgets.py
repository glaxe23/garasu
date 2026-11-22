"""Настройки виджетов на обоях: часы, монитор, плеер, задачи, фоторамка, визуализатор.

Настройки лежат в ~/.glzr/zebar/ryoku/widgets.json. Мелочи (прозрачность, что показывать)
виджеты подхватывают сами за секунду. Положение, размер и включение одного виджета применяет
live(): двигает или открывает только его окно, остальные виджеты не трогает. Полный перезапуск
Zebar (apply) нужен только при смене режима.

  python widgets.py          - применить текущие настройки (с перезапуском Zebar)
  python widgets.py reset    - вернуть настройки по умолчанию
"""
import os, sys, json, copy, subprocess

home = os.path.expanduser("~")
here = os.path.dirname(os.path.abspath(__file__))
root = os.path.dirname(here)
zroot = os.path.join(home, ".glzr", "zebar")
zdir = os.path.join(zroot, "ryoku")
CFG = os.path.join(zdir, "widgets.json")
ZEBAR = os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "glzr.io", "Zebar", "zebar.exe")
PYW = os.path.join(os.path.dirname(sys.executable), "pythonw.exe").replace("\\", "/")
PHOTOS = os.path.join(root, "photos")                       # сюда кладут свои картинки для фоторамки
_vault = os.path.join(home, "Documents", "Obsidian Vault", "00 Входящие")   # свой путь выбирают в настройках виджета
VAULT_TASKS = os.path.join(_vault if os.path.isdir(_vault) else root, "Задачи.md")
_study = os.path.join(home, "Documents", "Obsidian Vault", "02 Учёба")
VAULT_SCHEDULE = os.path.join(_study if os.path.isdir(_study) else _vault if os.path.isdir(_vault) else root, "Расписание.md")
ICONS = os.path.join(zdir, "icons")                         # значки для виджета «Ярлыки»
# Доп. параметры встроенного браузера Zebar. --process-per-site: виджеты делят один процесс отрисовки
# вместо отдельного на каждый, это экономит память. Пустая строка - поведение по умолчанию.
ZEBAR_ARGS = "--process-per-site"
AUDIO_PORT = 47631                                          # по этому порту помощник отдаёт спектр звука

# Реестр виджетов. size - размер окна при масштабе 100%.
# options - что можно менять в панели: (ключ, подпись, тип[, мин, макс])
WIDGETS = {
    "clock": {
        "name": "Часы", "size": (1100, 170),
        # у каждого вида часов свой размер окна
        "sizes": {"line": (1100, 170), "stack": (430, 350), "analog": (300, 330)},
        "defaults": {"on": True, "x": 808, "y": 42, "scale": 70, "opacity": 86, "style": "stack",
                     "seconds": True, "date": True, "h12": False},
        "options": [("style", "Вид", "choice", [("line", "В строку"), ("stack", "Стопкой"), ("analog", "Стрелки")]),
                    ("seconds", "Секунды", "bool"), ("date", "Дата", "bool"), ("h12", "12-часовой формат", "bool")],
    },
    "sysmon": {
        "name": "Монитор", "size": (320, 560),
        "defaults": {"on": False, "x": 56, "y": 290, "scale": 100, "opacity": 100,
                     "cpu": True, "memory": True, "network": True, "disk": True, "graphs": True, "card": False},
        "options": [("cpu", "Процессор", "bool"), ("memory", "Память", "bool"), ("network", "Сеть", "bool"),
                    ("disk", "Диск", "bool"), ("graphs", "Графики", "bool"), ("card", "Стекло", "bool")],
    },
    "media": {
        "name": "Плеер", "size": (520, 372),
        "defaults": {"on": True, "x": 24, "y": 675, "scale": 90, "opacity": 96,
                     "art": True, "wave": True, "volume": True, "lyrics": True, "solid": False},
        # lyrics: название трека и исполнитель отправляются на lrclib.net, чтобы получить текст песни;
        # art: если Windows не даёт обложку, она ищется по названию в каталоге iTunes
        "options": [("art", "Обложка", "bool"), ("wave", "Визуализатор", "bool"), ("volume", "Громкость", "bool"),
                    ("lyrics", "Текст песни (lrclib.net)", "bool"), ("solid", "Сплошной фон вместо стекла", "bool")],
    },
    "tasks": {
        "name": "Задачи", "size": (340, 430),
        "defaults": {"on": True, "x": 1556, "y": 60, "scale": 100, "opacity": 100,
                     "note": VAULT_TASKS, "count": 8, "done": False, "card": False},
        "options": [("note", "Заметка с задачами", "file"), ("count", "Сколько задач", "range", 3, 14),
                    ("done", "Показывать выполненные", "bool"), ("card", "Стекло", "bool")],
    },
    "photo": {
        "name": "Фото", "size": (300, 400),
        "defaults": {"on": True, "x": 1616, "y": 618, "scale": 100, "opacity": 100,
                     "interval": 30, "border": True, "pack": "theme", "tint": "soft"},
        # pack: какие картинки показывать. theme - папка photos/<имя темы> (если она пуста, то свои),
        # mix - все папки вместе, own - только свои (картинки прямо в папке photos)
        # tint: насколько подкрашивать фото в цвет темы (чтобы чужая картинка не выбивалась из палитры)
        "options": [("pack", "Картинки", "choice", [("theme", "По теме"), ("mix", "Все вместе"), ("own", "Свои")]),
                    ("tint", "В цвет темы", "choice", [("off", "Нет"), ("soft", "Слегка"), ("strong", "Сильно")]),
                    ("interval", "Смена, сек", "range", 5, 600), ("border", "Рамка", "bool"),
                    ("photos", "Открыть папку с фото", "folder")],
    },
    "visual": {
        "name": "Музыка", "size": (560, 150),
        "defaults": {"on": False, "x": 680, "y": 860, "scale": 100, "opacity": 90,
                     "bars": 48, "mirror": False},
        "options": [("bars", "Полосок", "range", 16, 96), ("mirror", "Зеркально", "bool")],
    },
    "calendar": {
        "name": "Календарь", "size": (330, 400),
        "defaults": {"on": False, "x": 1540, "y": 530, "scale": 100, "opacity": 100, "card": False},
        "options": [("card", "Стекло", "bool")],
    },
    "weather": {
        "name": "Погода", "size": (300, 150),
        "defaults": {"on": False, "x": 56, "y": 290, "scale": 100, "opacity": 100, "card": False},
        "options": [("card", "Стекло", "bool")],
    },
    "counters": {
        "name": "Счётчики", "size": (300, 130),
        # items: список дат. Высота окна зависит от их числа (см. size ниже)
        "defaults": {"on": True, "x": 1596, "y": 310, "scale": 100, "opacity": 100, "card": False,
                     "items": [{"title": "Нового года", "date": "%d-01-01" % (__import__("datetime").date.today().year + 1)}]},
        "options": [("items", "Даты", "dates"), ("card", "Стекло", "bool")],
    },
    "pomodoro": {
        "name": "Таймер", "size": (250, 300),
        "defaults": {"on": True, "x": 24, "y": 40, "scale": 80, "opacity": 100,
                     "work": 25, "rest": 5, "sound": True, "ambvol": 35, "card": False},
        "options": [("work", "Работа, мин", "range", 5, 90), ("rest", "Перерыв, мин", "range", 1, 30),
                    ("sound", "Звуковой сигнал", "bool"), ("ambvol", "Громкость фона (дождь, шум)", "range", 5, 100),
                    ("card", "Стекло", "bool")],
    },
    "schedule": {
        "name": "Расписание", "size": (330, 300),
        "defaults": {"on": True, "x": 24, "y": 285, "scale": 100, "opacity": 100, "note": VAULT_SCHEDULE, "card": False},
        "options": [("note", "Заметка с расписанием", "file"), ("card", "Стекло", "bool")],
    },
    "progress": {
        "name": "Прогресс", "size": (300, 236),
        # сколько прошло от дня, недели, месяца и года; точки - недели года
        "defaults": {"on": False, "x": 1190, "y": 60, "scale": 100, "opacity": 100, "card": False,
                     "day": True, "week": True, "month": True, "year": True, "dots": True},
        "options": [("day", "День", "bool"), ("week", "Неделя", "bool"), ("month", "Месяц", "bool"),
                    ("year", "Год", "bool"), ("dots", "Точки-недели", "bool"), ("card", "Стекло", "bool")],
    },
    "scratch": {
        "name": "Черновик", "size": (300, 200),
        # текст в ~/.glzr/zebar/ryoku/scratch.txt; клик по виджету открывает окно ввода scratch_edit.pyw
        "defaults": {"on": False, "x": 1190, "y": 316, "scale": 100, "opacity": 100, "card": False},
        "options": [("card", "Стекло", "bool")],
    },
    "links": {
        "name": "Ярлыки", "size": (316, 122),
        # items: программы и папки [{title, path, icon}]. Высота окна зависит от их числа (см. size ниже)
        "defaults": {"on": True, "x": 229, "y": 40, "scale": 100, "opacity": 100, "card": False, "items": [],
                     "cols": 4, "rows": 0},
        "options": [("items", "Ярлыки", "links"), ("card", "Стекло", "bool")],
    },
}
ORDER = list(WIDGETS)
NAMES = {k: v["name"] for k, v in WIDGETS.items()}
BASE = {k: v["size"] for k, v in WIDGETS.items()}
OPTIONS = {k: v["options"] for k, v in WIDGETS.items()}
DEFAULTS = {k: v["defaults"] for k, v in WIDGETS.items()}
# edit: режим редактирования (только в нём виджеты выделяются и двигаются мышкой), snap: привязка при переносе
# radius: скругление карточек, anim: анимация появления, adapt: тёмный текст на светлых местах обоев
DEFAULTS["all"] = {"edit": False, "snap": True, "radius": 26, "anim": True, "wallfade": True, "adapt": True}
PANEL_TITLE = "Ryoku Widgets"                     # заголовок окна панели настроек: пока она открыта, идёт редактирование
GEOMETRY = ("on", "x", "y", "scale")              # от этих полей зависит окно виджета

# Готовые расстановки для экрана 1920x1080 (на другом экране места пересчитываются). Виджеты не из списка выключаются.
LAYOUTS = {
    "clean": ("Garasu", {                       # она же расстановка по умолчанию
        "clock": {"x": 808, "y": 42, "scale": 70, "style": "stack"},
        "media": {"x": 24, "y": 675, "scale": 90},
        "tasks": {"x": 1556, "y": 60, "scale": 100},
        "photo": {"x": 1616, "y": 618, "scale": 100},
        "counters": {"x": 1596, "y": 310, "scale": 100},
        "pomodoro": {"x": 24, "y": 40, "scale": 80},
        "schedule": {"x": 24, "y": 285, "scale": 100},
        "links": {"x": 229, "y": 40, "scale": 100}}),
    "minimal": ("Минимализм", {
        "clock": {"x": 56, "y": 70, "scale": 100, "style": "line"},
        "weather": {"x": 1564, "y": 70, "scale": 100},
        "media": {"x": 1344, "y": 640, "scale": 100}}),
    "full": ("Всё сразу", {
        "clock": {"x": 56, "y": 70, "scale": 100, "style": "line"},
        "sysmon": {"x": 56, "y": 290, "scale": 100},
        "weather": {"x": 400, "y": 290, "scale": 100},
        "counters": {"x": 400, "y": 460, "scale": 100},
        "photo": {"x": 1200, "y": 190, "scale": 100},
        "media": {"x": 740, "y": 640, "scale": 100},
        "tasks": {"x": 1524, "y": 70, "scale": 100},
        "calendar": {"x": 1534, "y": 520, "scale": 100}}),
    "study": ("Учёба", {
        "clock": {"x": 56, "y": 70, "scale": 100, "style": "stack"},
        "schedule": {"x": 56, "y": 440, "scale": 100},
        "links": {"x": 410, "y": 440, "scale": 100},
        "pomodoro": {"x": 1250, "y": 70, "scale": 100},
        "tasks": {"x": 1524, "y": 70, "scale": 100},
        "calendar": {"x": 1534, "y": 520, "scale": 100}}),
}


def layout(cfg, name):
    """Применить готовую расстановку к настройкам: кто включён и где стоит. Остальные настройки виджетов не меняются."""
    import ctypes
    sw, sh = ctypes.windll.user32.GetSystemMetrics(0), ctypes.windll.user32.GetSystemMetrics(1)
    kx, ky = sw / 1920, sh / 1080
    spec = LAYOUTS[name][1]
    for k in ORDER:
        cfg[k]["on"] = k in spec
        if k in spec:
            cfg[k].update(spec[k])
            cfg[k]["x"], cfg[k]["y"] = round(spec[k]["x"] * kx), round(spec[k]["y"] * ky)
            if min(kx, ky) < 0.9:
                cfg[k]["scale"] = max(40, round(spec[k]["scale"] * min(kx, ky) / 5) * 5)
    return fit_screen(cfg)


def load():
    cfg = copy.deepcopy(DEFAULTS)
    try:
        saved = json.load(open(CFG, encoding="utf-8"))
        for k in cfg:
            cfg[k].update({a: b for a, b in saved.get(k, {}).items() if a in cfg[k]})
    except Exception:
        pass
    return cfg


def save(cfg):
    # _tools: чем виджеты запускают перенос мышкой и отметку задач, и где слушать звук
    out = dict(cfg, _tools={"program": PYW,
                            "drag": os.path.join(here, "drag.pyw").replace("\\", "/"),
                            "tasks": os.path.join(here, "tasks.py").replace("\\", "/"),
                            "task_add": os.path.join(here, "task_add.pyw").replace("\\", "/"),
                            "scratch": os.path.join(here, "scratch_edit.pyw").replace("\\", "/"),
                            "panel": os.path.join(here, "widgets_panel.pyw").replace("\\", "/"),
                            "launch": os.path.join(here, "launch.pyw").replace("\\", "/"),
                            "mixer": os.path.join(here, "mixer_panel.pyw").replace("\\", "/"),
                            "calendar": os.path.join(here, "calendar_panel.pyw").replace("\\", "/"),
                            "freeze_note": os.path.join(here, "freeze_note.pyw").replace("\\", "/"),
                            "audio": "ws://127.0.0.1:%d" % AUDIO_PORT})
    tmp = CFG + ".tmp"
    json.dump(out, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, CFG)


def size(k, cfg):
    """Размер окна виджета при масштабе 100% (у часов зависит от выбранного вида)."""
    w = WIDGETS[k]
    if k == "counters":
        n = len([i for i in cfg[k].get("items", []) if i.get("title") and i.get("date")])
        return (300, 56 + 62 * max(1, n))
    if k == "links":
        # cols — значков в ряд, rows — сколько рядов минимум (их меняют края рамки в режиме правки)
        n = len([i for i in cfg[k].get("items", []) if i.get("path")])
        cols = max(1, int(cfg[k].get("cols") or 4))
        return (24 + 73 * cols, 44 + 78 * max(1, int(cfg[k].get("rows") or 0), -(-n // cols)))
    return w.get("sizes", {}).get(cfg[k].get("style"), w["size"])


def geometry(cfg):
    return {k: tuple(cfg[k][g] for g in GEOMETRY) + (cfg[k].get("style"), size(k, cfg)) for k in ORDER}


def write_zebar(cfg):
    """Пишет zpack.json (положение и размер окон) и список запуска Zebar."""
    widgets = []
    for k in ORDER:
        c = cfg[k]
        w, h = size(k, cfg)
        s = c["scale"] / 100
        widgets.append({
            "name": k, "htmlPath": "./%s.html" % k, "zOrder": "bottom_most",
            "shownInTaskbar": False, "focused": False, "resizable": False, "transparent": True,
            "includeFiles": ["*.html", "*.css", "*.js", "*.mjs", "*.json", "*.txt", "*.ttf", "*.jpg", "photos/*", "art/*", "icons/*"],
            "caching": {"defaultDuration": 31536000, "rules": []},
            "privileges": {"shellCommands": [{"program": PYW, "argsRegex": ".*"}]},
            "presets": [{
                "name": "default", "anchor": "top_left",
                "offsetX": "%dpx" % c["x"], "offsetY": "%dpx" % c["y"],
                "width": "%dpx" % round(w * s + 4), "height": "%dpx" % round(h * s + 4),
                "monitorSelection": {"type": "primary"},
                "dockToEdge": {"enabled": False, "edge": None, "windowMargin": "0px"},
            }],
        })
    pack = {
        "$schema": "https://github.com/glzr-io/zebar/raw/v3.0.0/resources/zpack-schema.json",
        "name": "ryoku", "version": "1.2.0",
        "description": "Виджеты рабочего стола в стиле Ryoku.",
        "tags": ["desktop"], "previewImages": [], "repositoryUrl": "", "widgets": widgets,
    }
    json.dump(pack, open(os.path.join(zdir, "zpack.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    settings = {
        "$schema": "https://github.com/glzr-io/zebar/raw/v3.3.1/resources/settings-schema.json",
        "startupConfigs": [{"pack": "ryoku", "widget": k, "preset": "default"} for k in ORDER if cfg[k]["on"]],
    }
    json.dump(settings, open(os.path.join(zroot, "settings.json"), "w", encoding="utf-8"), indent=2)


def fit_screen(cfg):
    """Сдвинуть виджеты, которые не помещаются на экран (нужно на экранах меньше 1920x1080)."""
    import ctypes
    sw, sh = ctypes.windll.user32.GetSystemMetrics(0), ctypes.windll.user32.GetSystemMetrics(1)
    mons = monitors()
    for k in ORDER:
        c = cfg[k]
        w, h = size(k, cfg)
        # виджет на втором мониторе остаётся там: поправляем его только в пределах этого монитора
        x0, y0, mw, mh = 0, 0, sw, sh
        cx, cy = c["x"] + w * c["scale"] / 200, c["y"] + h * c["scale"] / 200
        for l, t, r, b in mons:
            if (l, t) != (0, 0) and l <= cx < r and t <= cy < b:
                x0, y0, mw, mh = l, t, r - l, b - t
                break
        if w * c["scale"] / 100 > mw - 40:                       # слишком широкий: уменьшаем
            c["scale"] = max(40, int((mw - 40) * 100 / w))
        s = c["scale"] / 100
        c["x"] = max(x0, min(c["x"], int(x0 + mw - w * s - 16)))
        c["y"] = max(y0, min(c["y"], int(y0 + mh - h * s - 70)))
    return cfg


def monitors():
    """Прямоугольники всех мониторов (left, top, right, bottom); у основного левый верх — (0, 0)."""
    import ctypes
    from ctypes import wintypes
    out = []
    proc = ctypes.WINFUNCTYPE(ctypes.c_int, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT),
                              wintypes.LPARAM)

    def cb(hm, hdc, rc, lp):
        r = rc.contents
        out.append((r.left, r.top, r.right, r.bottom))
        return 1
    try:
        ctypes.windll.user32.EnumDisplayMonitors(None, None, proc(cb), 0)
    except Exception:
        pass
    return out


# ---- Garasu Classic: виджеты на Qt вместо Zebar. Включено, пока рядом лежит файл classic.on
# (его ставит установщик и переключатель «Лёгкие виджеты» в панели; без него — Zebar).
# classic.off — человек сам выключил их в панели (установщик и обновление этот выбор не трогают).
# classic.tried — автоматическая доустановка библиотек Qt уже была (classic_setup.py), второй раз сама не идёт.
CLASSIC = os.path.join(here, "classic.py")
CLASSIC_FLAG = os.path.join(here, "classic.on")
CLASSIC_OFF = os.path.join(here, "classic.off")
CLASSIC_TRIED = os.path.join(here, "classic.tried")


def classic_on():
    return bool(os.environ.get("GARASU_NO_ZEBAR")) or (os.path.exists(CLASSIC_FLAG) and os.path.exists(CLASSIC))


def classic_fail():
    """Qt-виджеты не запустились: выключить их и вернуть Zebar (пустой рабочий стол хуже)."""
    for f in (CLASSIC_FLAG,):
        try:
            os.remove(f)
        except OSError:
            pass
    open(CLASSIC_TRIED, "w").close()                   # и не пытаться снова ставить их автоматически
    restart_zebar()


def _classic_pids():
    try:
        import psutil
    except Exception:                                  # без psutil: спросить Windows (медленнее, но работает)
        try:
            r = subprocess.run(["powershell", "-NoProfile", "-Command",
                                "Get-CimInstance Win32_Process -Filter \"Name like 'python%'\" | "
                                "Where-Object { $_.CommandLine -match 'classic\\.py' } | ForEach-Object ProcessId"],
                               capture_output=True, text=True, timeout=20, creationflags=0x08000000)
            return [int(x) for x in r.stdout.split() if x.isdigit()]
        except Exception:
            return []
    out = []
    for p in psutil.process_iter(["name", "cmdline"]):
        try:
            if (p.info["name"] or "").lower().startswith("python") and any(
                    os.path.basename(a).lower() == "classic.py" for a in (p.info["cmdline"] or [])):
                out.append(p.pid)
        except Exception:
            pass
    return out


def stop_classic():
    for pid in _classic_pids():
        subprocess.run(["taskkill", "/f", "/pid", str(pid)], creationflags=0x08000000,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def start_classic():
    """Запустить Qt-виджеты, если ещё не запущены. Настройки и тему они подхватывают сами, перезапуск не нужен."""
    if _classic_pids():
        return
    exe = sys.executable
    w = os.path.join(os.path.dirname(exe), "pythonw.exe")
    subprocess.Popen([w if os.path.exists(w) else exe, CLASSIC], cwd=here,
                     creationflags=0x08000000 | 0x00000008 | 0x00000200,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def setup_classic_later():
    """Лёгкие виджеты ещё ни разу не включались (например, обновились со старой версии без библиотек Qt):
    в фоне доставить библиотеки и, если всё получилось, переключиться на Qt. Один раз."""
    if any(os.path.exists(f) for f in (CLASSIC_FLAG, CLASSIC_OFF, CLASSIC_TRIED)):
        return
    script = os.path.join(here, "classic_setup.py")
    if not os.path.exists(script) or not os.path.exists(os.path.join(here, "version.txt")):   # не в папке разработки
        return
    exe = sys.executable
    w = os.path.join(os.path.dirname(exe), "pythonw.exe")
    subprocess.Popen([w if os.path.exists(w) else exe, script], cwd=here,
                     creationflags=0x08000000 | 0x00000008 | 0x00000200,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def restart_zebar():
    if os.environ.get("RYOKU_DRYRUN"):               # проверочная установка: настоящие процессы не трогаем
        return
    if classic_on():                                 # виджеты рисует Qt (Garasu Classic): Zebar закрыть
        subprocess.run(["taskkill", "/f", "/im", "zebar.exe"], creationflags=0x08000000,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        start_classic()
        return
    stop_classic()
    setup_classic_later()
    NOWIN = 0x08000000
    subprocess.run(["taskkill", "/f", "/im", "zebar.exe"], creationflags=NOWIN,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if os.path.exists(ZEBAR):
        env = dict(os.environ)
        if ZEBAR_ARGS:
            env["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = ZEBAR_ARGS
        subprocess.Popen([ZEBAR, "startup"], creationflags=NOWIN | 0x00000008, env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _user32():
    import ctypes
    from ctypes import wintypes
    u = ctypes.windll.user32
    u.FindWindowW.restype = wintypes.HWND
    u.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    u.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND] + [ctypes.c_int] * 4 + [ctypes.c_uint]
    u.PostMessageW.argtypes = [wintypes.HWND, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM]
    return u


def window(k, u=None):
    return (u or _user32()).FindWindowW(None, "Zebar - ryoku / " + k)


def live(cfg, before):
    """Применить изменения положения, размера и включения без перезапуска Zebar.
    before - geometry() до изменений. Трогаются только окна тех виджетов, у которых что-то поменялось."""
    save(cfg)
    write_zebar(cfg)
    u = _user32()
    now = geometry(cfg)
    if not any(window(k, u) for k in ORDER):          # Zebar не запущен совсем
        if any(cfg[k]["on"] for k in ORDER):
            restart_zebar()
        return now
    for k in ORDER:
        if now[k] == before.get(k):
            continue
        hwnd = window(k, u)
        if not cfg[k]["on"]:
            if hwnd:
                u.PostMessageW(hwnd, 0x0010, 0, 0)    # WM_CLOSE: закрыть только этот виджет
        elif not hwnd:
            if os.path.exists(ZEBAR) and not classic_on():  # открыть только этот виджет
                subprocess.Popen([ZEBAR, "start-widget-preset", "--pack", "ryoku", "--widget-name", k,
                                  "--preset", "default"], creationflags=0x08000000,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            try:
                K = u.GetDpiForWindow(hwnd) / 96 or 1
            except Exception:
                K = 1
            w, h = size(k, cfg)
            s = cfg[k]["scale"] / 100
            u.SetWindowPos(hwnd, None, round(cfg[k]["x"] * K), round(cfg[k]["y"] * K),
                           round((w * s + 4) * K), round((h * s + 4) * K), 0x0004 | 0x0010 | 0x4000)  # ASYNC: не ждать занятое окно
    return now


def apply(cfg=None, restart=True):
    cfg = cfg or load()
    if restart:                                       # полный перезапуск: режим редактирования только при открытой панели
        cfg["all"]["edit"] = bool(_user32().FindWindowW(None, PANEL_TITLE))
    save(cfg)
    write_zebar(cfg)
    if restart:
        restart_zebar()
    return cfg


def photo_packs():
    """Папки для паков фото: по одной на каждую тему (photos/<имя темы>). Картинки в них кладёт пользователь."""
    try:
        for t in json.load(open(os.path.join(here, "themes.json"), encoding="utf-8")):
            os.makedirs(os.path.join(PHOTOS, t["id"]), exist_ok=True)
    except Exception:
        pass


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "reset":
        apply(copy.deepcopy(DEFAULTS))
    elif len(sys.argv) > 1 and sys.argv[1] == "install":        # первый запуск на новом компьютере
        os.makedirs(zdir, exist_ok=True)
        if not os.path.exists(VAULT_TASKS):
            open(VAULT_TASKS, "w", encoding="utf-8").write(
                "# Задачи\n\n- [ ] Написать сюда свои задачи вместо этой строки\n- [ ] Кликнуть по задаче в виджете\n")
        apply(fit_screen(copy.deepcopy(DEFAULTS)), restart=False)
        photo_packs()
    else:
        apply()
    if sys.stdout:
        print("ok")
