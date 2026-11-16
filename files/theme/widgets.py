"""Настройки виджетов на обоях: часы, монитор, плеер, задачи, фоторамка, визуализатор.

Настройки лежат в ~/.glzr/zebar/ryoku/widgets.json. Мелочи (прозрачность, что показывать)
виджеты подхватывают сами за пару секунд. Положение, размер и включение/выключение требуют
перезапуска Zebar: это делает apply().

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
_vault = os.path.join(home, "Documents", "Obsidian Vault", "00 Входящие")
VAULT_TASKS = os.path.join(_vault if os.path.isdir(_vault) else root, "Задачи.md")
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
        "defaults": {"on": True, "x": 56, "y": 70, "scale": 100, "opacity": 86, "style": "line",
                     "seconds": True, "date": True, "h12": False},
        "options": [("style", "Вид", "choice", [("line", "В строку"), ("stack", "Стопкой"), ("analog", "Стрелки")]),
                    ("seconds", "Секунды", "bool"), ("date", "Дата", "bool"), ("h12", "12-часовой формат", "bool")],
    },
    "sysmon": {
        "name": "Монитор", "size": (320, 560),
        "defaults": {"on": True, "x": 60, "y": 290, "scale": 100, "opacity": 100,
                     "cpu": True, "memory": True, "network": True, "disk": True, "graphs": True, "card": True},
        "options": [("cpu", "Процессор", "bool"), ("memory", "Память", "bool"), ("network", "Сеть", "bool"),
                    ("disk", "Диск", "bool"), ("graphs", "Графики", "bool"), ("card", "Стекло", "bool")],
    },
    "media": {
        "name": "Плеер", "size": (520, 372),
        "defaults": {"on": True, "x": 1380, "y": 740, "scale": 100, "opacity": 96,
                     "art": True, "wave": True, "volume": True, "lyrics": True},
        # lyrics: название трека и исполнитель отправляются на lrclib.net, чтобы получить текст песни;
        # art: если Windows не даёт обложку, она ищется по названию в каталоге iTunes
        "options": [("art", "Обложка", "bool"), ("wave", "Визуализатор", "bool"), ("volume", "Громкость", "bool"),
                    ("lyrics", "Текст песни (lrclib.net)", "bool")],
    },
    "tasks": {
        "name": "Задачи", "size": (340, 430),
        "defaults": {"on": True, "x": 1540, "y": 80, "scale": 100, "opacity": 100,
                     "note": VAULT_TASKS, "count": 8, "done": False, "card": True},
        "options": [("note", "Заметка с задачами", "file"), ("count", "Сколько задач", "range", 3, 14),
                    ("done", "Показывать выполненные", "bool"), ("card", "Стекло", "bool")],
    },
    "photo": {
        "name": "Фото", "size": (300, 400),
        "defaults": {"on": True, "x": 1200, "y": 560, "scale": 100, "opacity": 100,
                     "interval": 30, "border": True},
        "options": [("interval", "Смена, сек", "range", 5, 600), ("border", "Рамка", "bool"),
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
        "defaults": {"on": False, "x": 1540, "y": 530, "scale": 100, "opacity": 100, "card": True},
        "options": [("card", "Стекло", "bool")],
    },
    "weather": {
        "name": "Погода", "size": (300, 150),
        "defaults": {"on": True, "x": 1580, "y": 540, "scale": 100, "opacity": 100, "card": True},
        "options": [("card", "Стекло", "bool")],
    },
    "counters": {
        "name": "Счётчики", "size": (300, 130),
        # items: список дат. Высота окна зависит от их числа (см. size ниже)
        "defaults": {"on": True, "x": 1580, "y": 710, "scale": 100, "opacity": 100, "card": True,
                     "items": [{"title": "Нового года", "date": "%d-01-01" % (__import__("datetime").date.today().year + 1)}]},
        "options": [("items", "Даты", "dates"), ("card", "Стекло", "bool")],
    },
    "pomodoro": {
        "name": "Таймер", "size": (250, 300),
        "defaults": {"on": False, "x": 1260, "y": 80, "scale": 100, "opacity": 100,
                     "work": 25, "rest": 5, "sound": True, "card": True},
        "options": [("work", "Работа, мин", "range", 5, 90), ("rest", "Перерыв, мин", "range", 1, 30),
                    ("sound", "Звуковой сигнал", "bool"), ("card", "Стекло", "bool")],
    },
}
ORDER = list(WIDGETS)
NAMES = {k: v["name"] for k, v in WIDGETS.items()}
BASE = {k: v["size"] for k, v in WIDGETS.items()}
OPTIONS = {k: v["options"] for k, v in WIDGETS.items()}
DEFAULTS = {k: v["defaults"] for k, v in WIDGETS.items()}
DEFAULTS["all"] = {"lock": False, "snap": True}   # lock: не двигать мышкой, snap: привязка при переносе
GEOMETRY = ("on", "x", "y", "scale")              # изменения этих полей требуют перезапуска Zebar


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
                            "mixer": os.path.join(here, "mixer_panel.pyw").replace("\\", "/"),
                            "calendar": os.path.join(here, "calendar_panel.pyw").replace("\\", "/"),
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
            "includeFiles": ["*.html", "*.css", "*.js", "*.mjs", "*.json", "*.ttf", "*.jpg", "photos/*", "art/*"],
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
    for k in ORDER:
        c = cfg[k]
        w, h = size(k, cfg)
        if w * c["scale"] / 100 > sw - 40:                       # слишком широкий: уменьшаем
            c["scale"] = max(40, int((sw - 40) * 100 / w))
        s = c["scale"] / 100
        c["x"] = max(0, min(c["x"], int(sw - w * s - 16)))
        c["y"] = max(0, min(c["y"], int(sh - h * s - 70)))
    return cfg


def restart_zebar():
    NOWIN = 0x08000000
    subprocess.run(["taskkill", "/f", "/im", "zebar.exe"], creationflags=NOWIN,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if os.path.exists(ZEBAR):
        env = dict(os.environ)
        if ZEBAR_ARGS:
            env["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = ZEBAR_ARGS
        subprocess.Popen([ZEBAR, "startup"], creationflags=NOWIN | 0x00000008, env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def apply(cfg=None, restart=True):
    cfg = cfg or load()
    save(cfg)
    write_zebar(cfg)
    if restart:
        restart_zebar()
    return cfg


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "reset":
        apply(copy.deepcopy(DEFAULTS))
    elif len(sys.argv) > 1 and sys.argv[1] == "install":        # первый запуск на новом компьютере
        os.makedirs(zdir, exist_ok=True)
        if not os.path.exists(VAULT_TASKS):
            open(VAULT_TASKS, "w", encoding="utf-8").write(
                "# Задачи\n\n- [ ] Написать сюда свои задачи вместо этой строки\n- [ ] Кликнуть по задаче в виджете\n")
        apply(fit_screen(copy.deepcopy(DEFAULTS)), restart=False)
    else:
        apply()
    if sys.stdout:
        print("ok")
