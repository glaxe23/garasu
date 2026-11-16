"""Garasu v3: панель «таблетками», док, виджеты на обоях и темы.

  python ryoku.py list          - список тем
  python ryoku.py rose          - включить тему по имени
  python ryoku.py next | prev   - следующая / предыдущая тема
  python ryoku.py C:\\путь.jpg   - тема из любой картинки
  python ryoku.py               - переприменить текущую тему

Цвета считаются из обоев (как matugen в Ryoku). Старые версии: apply.py, apply.v1.py
"""
import os, re, sys, json, shutil, ctypes, winreg, yaml
from palette import palette

here = os.path.dirname(os.path.abspath(__file__))
root = os.path.dirname(here)
home = os.path.expanduser("~")
ydir = os.path.join(home, ".config", "yasb")
gz = os.path.join(home, ".glzr", "glazewm", "config.yaml")
zdir = os.path.join(home, ".glzr", "zebar", "ryoku")
state_file = os.path.join(here, "state.json")
PYW = os.path.join(os.path.dirname(sys.executable), "pythonw.exe").replace("\\", "/")
PYW = '"%s"' % PYW if os.path.exists(PYW) else "pythonw"
SELF = os.path.join(here, "ryoku.py").replace("\\", "/")
PANEL = os.path.join(here, "themes_panel.pyw").replace("\\", "/")
CALENDAR = os.path.join(here, "calendar_panel.pyw").replace("\\", "/")
DESKTOP = os.path.join(here, "show_desktop.pyw").replace("\\", "/")

# Настройки оформления (settings.json): dock = "auto" (док прячется, выезжает от нижнего края)
# или "always" (всегда виден, окна до него не доходят); side_gap - отступ окон слева и справа.
OPTS = {"dock": "auto", "side_gap": 24, "mode": "daily"}
try:
    OPTS.update(json.load(open(os.path.join(here, "settings.json"), encoding="utf-8")))
except Exception:
    pass
DOCK_ALWAYS = OPTS["dock"] == "always"
MODE = OPTS.get("mode", "daily")            # daily / work / game, переключается mode.py

themes = json.load(open(os.path.join(here, "themes.json"), encoding="utf-8"))
def _wall(t):
    w = t["wallpaper"]
    return w if os.path.isabs(w) else os.path.join(root, "wallpapers", w)
themes = [t for t in themes if os.path.exists(_wall(t))]   # темы без скачанных обоев пропускаем
if not themes: sys.exit("Нет ни одной темы с обоями в " + os.path.join(root, "wallpapers"))
ids = [t["id"] for t in themes]


def load_state():
    try:
        return json.load(open(state_file, encoding="utf-8"))
    except Exception:
        return {"theme": ids[0]}


def pick(arg):
    """-> (id, name, путь к обоям)"""
    cur = load_state().get("theme", ids[0])
    if arg in (None, ""):
        arg = cur
    if arg in ("next", "prev"):
        i = ids.index(cur) if cur in ids else -1
        arg = ids[(i + (1 if arg == "next" else -1)) % len(ids)]
    if arg in ids:
        t = themes[ids.index(arg)]
        w = t["wallpaper"]
        if not os.path.isabs(w):
            w = os.path.join(root, "wallpapers", w)
        return t["id"], t["name"], w
    if os.path.exists(arg):
        return "custom", os.path.basename(arg), os.path.abspath(arg)
    sys.exit("Нет такой темы: %s. Есть: %s" % (arg, ", ".join(ids)))


def rgb(h):
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def mix(a, b, t):
    A, B = rgb(a), rgb(b)
    return "#%02x%02x%02x" % tuple(round(A[i] + (B[i] - A[i]) * t) for i in range(3))


def rgba(h, a):
    return "rgba(%d, %d, %d, %s)" % (*rgb(h), a)


def fix(o):   # суррогатные пары иконок -> нормальные символы
    if isinstance(o, str): return o.encode("utf-16", "surrogatepass").decode("utf-16")
    if isinstance(o, list): return [fix(x) for x in o]
    if isinstance(o, dict): return {k: fix(v) for k, v in o.items()}
    return o


def set_wallpaper(path):
    k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop", 0, winreg.KEY_SET_VALUE)
    winreg.SetValueEx(k, "WallpaperStyle", 0, winreg.REG_SZ, "10")   # заполнение
    winreg.SetValueEx(k, "TileWallpaper", 0, winreg.REG_SZ, "0")
    winreg.CloseKey(k)
    ctypes.windll.user32.SystemParametersInfoW(20, 0, path, 3)


if len(sys.argv) > 1 and sys.argv[1] == "list":
    cur = load_state().get("theme")
    for t in themes:
        print(("* " if t["id"] == cur else "  ") + t["id"].ljust(8) + t["name"])
    sys.exit()

tid, tname, wall = pick(sys.argv[1] if len(sys.argv) > 1 else None)
if not os.path.exists(wall):
    sys.exit("Не найдены обои: " + wall)
c, _ = palette(wall)

accent = c["primary"]
accent_fg = c["onPrimary"]
pill = mix(c["surface"], "#000000", 0.35)          # тёмная «таблетка» с оттенком обоев
pill_hi = mix(pill, "#ffffff", 0.10)
fg = mix(c["onSurface"], "#ffffff", 0.25)
muted = mix(c["onSurfaceVariant"], pill, 0.25)
line = "rgba(255, 255, 255, 0.09)"
glow = mix(c["primaryFixed"], "#ffffff", 0.45)     # светлый цвет для больших часов

# ---------------------------------------------------------------- стекло
# Виджеты лежат прямо на обоях, поэтому «матовое стекло» делается так: заранее размытая копия обоев
# кладётся фоном карточки и совмещается с экраном. Выглядит как настоящее размытие того, что позади.
SCREEN = (ctypes.windll.user32.GetSystemMetrics(0), ctypes.windll.user32.GetSystemMetrics(1))
glass_tint = rgba(mix(pill, accent, 0.10), 0.46)      # затемнение стекла, чтобы текст читался на любых обоях
glass_edge = "rgba(255, 255, 255, 0.24)"
bar_glass = rgba(mix(pill, accent, 0.08), 0.58)       # «таблетки» панели: полупрозрачные (размыть фон под ними YASB не умеет)
bar_glass_hi = rgba(mix(pill_hi, accent, 0.10), 0.74)
if os.path.isdir(zdir):
    try:
        from PIL import Image, ImageOps, ImageFilter
        im = ImageOps.fit(Image.open(wall).convert("RGB"), (SCREEN[0] // 2, SCREEN[1] // 2), Image.LANCZOS)
        im.filter(ImageFilter.GaussianBlur(16)).save(os.path.join(zdir, "glass.jpg"), quality=85)
    except Exception as e:
        print("glass:", e)

# ---------------------------------------------------------------- YASB: конфиг
cfg = yaml.safe_load(open(os.path.join(here, "islands.base.yaml"), encoding="utf-8"))
cfg["debug"] = False
cfg["update_check"] = False
w = cfg["widgets"]
for name in ("wallpapers", "open_meteo", "github", "windows_workspaces", "notifications", "audio_visualizer"):
    w.pop(name, None)
# Win (одна) -> win_launcher.ahk шлёт Ctrl+Alt+Shift+O -> открывается поиск приложений
w["quick_launch"]["options"]["keybindings"] = [{"keys": "ctrl+alt+shift+o", "action": "toggle_quick_launch", "screen": "active"}]
w["quick_launch"]["options"]["label"] = "硝"
w["quick_launch"]["options"]["search_placeholder"] = "Поиск приложений..."
w["taskbar"]["options"]["show_only_visible"] = False
w["taskbar"]["options"]["icon_size"] = 22
w["clock"]["options"]["label"] = "<span>\ue823</span> {%H:%M  %a %d}"
w["clock"]["options"]["callbacks"] = {"on_left": 'exec %s "%s"' % (PYW, CALENDAR),
                                     "on_middle": "toggle_label", "on_right": "toggle_calendar"}
w["clock"]["options"]["label_alt"] = "{%A, %d %B %Y}"
w["glazewm_workspaces"] = {
    "type": "glazewm.workspaces.GlazewmWorkspacesWidget",
    "options": {"offline_label": "", "hide_if_offline": True, "monitor_exclusive": False},
}
w["cpu"] = {"type": "yasb.cpu.CpuWidget", "options": {
    "label": "<span>\ueea1</span> {info[percent][total]}%", "label_alt": "<span>\ueea1</span> {info[freq][current]} MHz",
    "update_interval": 3000, "hide_decimal": True,
    "callbacks": {"on_left": "toggle_label", "on_middle": "do_nothing", "on_right": "do_nothing"}}}
w["memory"] = {"type": "yasb.memory.MemoryWidget", "options": {
    "label": "<span>\ue9d9</span> {virtual_mem_percent}%", "label_alt": "<span>\ue9d9</span> {virtual_mem_used}",
    "update_interval": 5000, "hide_decimal": True,
    "callbacks": {"on_left": "toggle_label", "on_middle": "do_nothing", "on_right": "do_nothing"}}}
w["language"] = {"type": "yasb.language.LanguageWidget", "options": {
    "label": "<span>\ue765</span> {lang[language_code]}", "label_alt": "{lang[full_name]}", "update_interval": 5,
    "callbacks": {"on_left": "toggle_menu", "on_middle": "do_nothing", "on_right": "toggle_label"}}}
w["media"] = {"type": "yasb.media_lite.MediaWidget", "options": {
    "show_thumbnail": True, "show_title": True, "show_artist": True, "scrolling_label": False,
    "image_size": 26, "thumbnail_corner_radius": 6, "max_label_size": 22, "tooltip": True,
    "callbacks": {"on_left": "toggle_media_menu", "on_middle": "do_nothing", "on_right": "do_nothing"},
    # всплывающий плеер над доком: без размытой обложки на фоне, в цветах темы (стили ниже, .media-lite-menu)
    "media_menu": {"blur": True, "artwork_background": False, "round_corners": True, "round_corners_type": "normal",
                   "border_color": "None", "alignment": "center", "direction": "up", "offset_top": 10, "offset_left": 0,
                   "image_size": 216, "thumbnail_corner_radius": 14,
                   "icons": {"play": "\ue768", "pause": "\ue769", "prev_track": "\ue892", "next_track": "\ue893",
                             "shuffle": "\ue8b1", "repeat": "\ue8ee", "repeat_one": "\ue8ed",
                             "volume": "\ue767", "mute": "\ue74f"}}}}
w["theme"] = {"type": "yasb.custom.CustomWidget", "options": {
    "label": "<span>\ue790</span>", "class_name": "theme-widget",
    "tooltip": True, "tooltip_label": "Тема: %s. Клик - выбрать тему, правый клик - следующая" % tname,
    "callbacks": {"on_left": 'exec %s "%s"' % (PYW, PANEL),
                  "on_middle": "do_nothing",
                  "on_right": 'exec %s "%s" next' % (PYW, SELF)},
    "exec_options": {"run_cmd": None, "run_once": True, "return_format": "string", "use_shell": True}}}

_mode = {"daily": ("\ue80f", "Повседневный"), "work": ("\ue821", "Рабочий"), "game": ("\ue7fc", "Игровой")}[MODE]
w["mode"] = {"type": "yasb.custom.CustomWidget", "options": {
    "label": "<span>%s</span> %s" % _mode, "class_name": "mode-widget",
    "tooltip": True, "tooltip_label": "Режим: %s. Клик - выбрать режим" % _mode[1],
    "callbacks": {"on_left": 'exec %s "%s"' % (PYW, os.path.join(here, "modes_panel.pyw").replace("\\", "/")),
                  "on_middle": "do_nothing", "on_right": "do_nothing"},
    "exec_options": {"run_cmd": None, "run_once": True, "return_format": "string", "use_shell": True}}}
# правый клик по громкости на панели открывает микшер приложений
w["volume"]["options"]["callbacks"] = {"on_left": "toggle_volume_menu",
    "on_right": 'exec %s "%s"' % (PYW, os.path.join(here, "mixer_panel.pyw").replace("\\", "/"))}

# чем сейчас занят Claude Code: строку пишет claude_status.py (его вызывают хуки Claude Code)
_status = os.path.join(here, "claude_status.txt").replace("/", "\\")
if not os.path.exists(_status):
    open(_status, "w").close()
w["claude"] = {"type": "yasb.custom.CustomWidget", "options": {
    "label": "<span>\u273b</span> {data}", "label_alt": "<span>\u273b</span>", "label_max_length": 48,
    "label_placeholder": "", "class_name": "claude-widget", "tooltip": True, "tooltip_label": "Claude: {data}",
    "exec_options": {"run_cmd": 'cmd /c type "%s"' % _status, "run_interval": 2500,
                     "return_format": "string", "hide_empty": True},
    "callbacks": {"on_left": "toggle_label", "on_middle": "do_nothing", "on_right": "do_nothing"}}}

# главное на сегодня: заметка календаря или первая невыполненная задача (строку пишет helper.pyw)
_focus = os.path.join(here, "bar_focus.txt").replace("/", "\\")
if not os.path.exists(_focus):
    open(_focus, "w").close()
import urllib.parse as _up
try:                                   # заметка с задачами: та, что выбрана в настройках виджета «Задачи»
    import widgets as _W
    _note_path = _W.load()["tasks"]["note"]
except Exception:
    _note_path = os.path.join(root, "Задачи.md")
_in_vault = "Obsidian Vault" in _note_path
_note = _up.quote(_note_path) if _in_vault else _note_path
w["focus"] = {"type": "yasb.custom.CustomWidget", "options": {
    "label": "<span>\ue73e</span> {data}", "label_alt": "<span>\ue73e</span>", "label_max_length": 46,
    "label_placeholder": "", "class_name": "focus-widget", "tooltip": True,
    "tooltip_label": "Главное сейчас: {data}. Клик - открыть задачи в Obsidian",
    "exec_options": {"run_cmd": 'cmd /c type "%s"' % _focus, "run_interval": 5000,
                     "return_format": "string", "hide_empty": True},
    "callbacks": {"on_left": 'exec cmd /c start "" "%s%s"' % ("obsidian://open?path=" if _in_vault else "", _note),
                  "on_middle": "toggle_label", "on_right": "toggle_label"}}}

w["show_desktop"] = {"type": "yasb.custom.CustomWidget", "options": {
    "label": "<span>\ue8fc</span>", "class_name": "show-desktop-widget",
    "tooltip": True, "tooltip_label": "Рабочий стол: свернуть или вернуть все окна",
    "callbacks": {"on_left": 'exec %s "%s"' % (PYW, DESKTOP), "on_middle": "do_nothing", "on_right": "do_nothing"},
    "exec_options": {"run_cmd": None, "run_once": True, "return_format": "string", "use_shell": True}}}

top = cfg["bars"]["primary-bar"]
top.pop("style", None)
top["screens"] = ["*"]
top["blur_effect"] = {"enabled": False, "dark_mode": False, "round_corners": False, "border_color": "None"}
top["dimensions"] = {"width": "100%", "height": 38}
top["padding"] = {"top": 4, "left": 8, "bottom": 0, "right": 8}
top["widgets"] = {
    "left": ["quick_launch", "glazewm_workspaces", "focus"],
    "center": ["clock", "cpu", "memory", "claude"],
    "right": ["systray", "volume", "language", "mode", "theme", "control_center"],
}
dock = json.loads(json.dumps(top))
dock["class_name"] = "yasb-dock"
dock["alignment"] = {"position": "bottom", "align": "center"}
# два режима: «прячется» (выезжает, когда подводишь мышь к нижнему краю) и «всегда виден»
# (тогда док резервирует место внизу экрана, и окна под него не заходят)
dock["window_flags"] = {"always_on_top": True, "windows_app_bar": DOCK_ALWAYS, "auto_hide": not DOCK_ALWAYS}
dock["dimensions"] = {"width": 620, "height": 50}
dock["padding"] = {"top": 0, "left": 0, "bottom": 8, "right": 0}
dock["widgets"] = {"left": [], "center": ["show_desktop", "taskbar", "media"], "right": []}
if MODE == "game":          # игровой режим: короткая панель без дока и анимаций
    dock["enabled"] = False
    top["animation"] = {"enabled": False, "duration": 0}
    top["widgets"] = {"left": ["quick_launch", "glazewm_workspaces"], "center": ["clock", "cpu", "memory"],
                      "right": ["systray", "volume", "mode"]}
cfg["bars"] = {"primary-bar": top, "dock": dock}

os.makedirs(ydir, exist_ok=True)
with open(os.path.join(ydir, "config.yaml"), "w", encoding="utf-8") as f:
    f.write("# Сгенерировано ryoku.py (C:/garasu/theme), правки лучше делать там\n")
    yaml.safe_dump(fix(cfg), f, allow_unicode=True, sort_keys=False, default_flow_style=False)

# ---------------------------------------------------------------- YASB: стили
css = open(os.path.join(here, "islands.base.css"), encoding="utf-8").read()
r, g, b = rgb(pill)
subs = {
    "--yasb-bar-bg: rgb(0, 0, 0);": f"--yasb-bar-bg: rgb({r}, {g}, {b});",
    "--yasb-popup-bg: rgba(0, 0, 0, 0.75);": f"--yasb-popup-bg: rgba({r}, {g}, {b}, 0.62);",
    "--yasb-dialog-bg: rgb(0, 0, 0);": f"--yasb-dialog-bg: rgb({r}, {g}, {b});",
    "--yasb-accent: #4cc2ff;": f"--yasb-accent: {accent};",
    "--yasb-accent-hover: #40ace2;": f"--yasb-accent-hover: {mix(accent, '#000000', 0.12)};",
    "--yasb-accent-fg: #000000;": f"--yasb-accent-fg: {accent_fg};",
    "linear-gradient(to top, #8A9AFF, #8A8AFF, #C38AFF)":
        f"linear-gradient(to top, {c['primary']}, {c['secondary']}, {c['tertiary']})",
}
for old, new in subs.items():
    css = css.replace(old, new)
css += f"""
/* ================= Ryoku: тема «{tname}» ({os.path.basename(wall)}) ================= */
.yasb-bar, .yasb-dock {{ background-color: transparent; }}
.widget {{
    background-color: {bar_glass};
    border: 1px solid {glass_edge};
    border-radius: 11px;
    padding: 0 9px;
    margin: 3px 3px;
}}
.widget:hover {{ background-color: {bar_glass_hi}; }}
.widget .label {{ color: {fg}; font-size: 11px; font-weight: 700; padding-bottom: 1px; }}
.widget .icon {{ color: {accent}; font-size: 13px; padding-right: 3px; }}
.clock-widget .label {{ color: {fg}; margin: 0; }}
.clock-widget .label.date, .clock-widget .date {{ color: {muted}; }}
.clock-widget:hover, .systray:hover, .volume-widget:hover,
.quick-launch-widget:hover, .control-center-widget:hover {{ background-color: {bar_glass_hi}; }}
.quick-launch-widget .label {{ color: {accent}; font-size: 14px; font-weight: 800; padding: 0 2px 2px 2px; }}
.theme-widget .icon, .control-center-widget .icon, .volume-widget .icon {{ color: {fg}; padding-right: 0; }}
.theme-widget:hover .icon {{ color: {accent}; }}
.cpu-widget .icon {{ color: {c['primary']}; }}
.memory-widget .icon {{ color: {c['tertiary']}; }}
.language-widget .icon {{ color: {c['secondary']}; }}
.language-widget .label {{ text-transform: uppercase; }}

/* рабочие столы: цифры, активный в рамке */
.glazewm-workspaces {{ padding: 0 5px; }}
.glazewm-workspaces .ws-btn {{
    background-color: transparent; border: 1px solid transparent; border-radius: 6px;
    color: {muted}; font-size: 11px; font-weight: 700;
    padding: 0 6px; margin: 4px 1px;
}}
.glazewm-workspaces .ws-btn.populated {{ color: {fg}; }}
.glazewm-workspaces .ws-btn.active_populated, .glazewm-workspaces .ws-btn.active_empty,
.glazewm-workspaces .ws-btn.focused_populated, .glazewm-workspaces .ws-btn.focused_empty {{
    color: {accent}; border: 1px solid {rgba(accent, 0.75)}; background-color: {rgba(accent, 0.12)};
}}
.glazewm-workspaces .ws-btn:hover {{ background-color: rgba(255, 255, 255, 0.10); }}

/* подсказки при наведении (например, название трека) */
.tooltip {{
    background-color: {rgba(mix(pill, accent, 0.10), 0.92)};
    border: 1px solid {glass_edge}; border-radius: 10px;
    color: {fg}; padding: 7px 12px; margin-top: 6px;
    font-size: 12px; font-weight: 600;
}}
.focus-widget .icon {{ color: {accent}; }}
.focus-widget .label {{ color: {fg}; }}
.claude-widget .icon {{ color: #d97757; font-family: "Segoe UI Symbol"; font-size: 14px; font-weight: 700; padding-right: 4px; }}
.claude-widget .label {{ color: {fg}; }}
.mode-widget .label {{ color: {accent}; }}
.mode-widget .icon {{ color: {accent}; }}
.show-desktop-widget .icon {{ color: {fg}; font-size: 15px; padding: 0 3px; }}
.show-desktop-widget:hover .icon {{ color: {accent}; }}

/* док снизу */
.yasb-dock .widget {{ border-radius: 14px; margin: 0 4px; padding: 0 6px; }}
.taskbar-widget .app-container {{ margin: 5px 2px; border-radius: 9px; padding: 0 7px; }}
.taskbar-widget .app-container.foreground {{ background-color: {rgba(accent, 0.28)}; padding: 0 7px; }}
.taskbar-widget .app-container:hover {{ background-color: rgba(255, 255, 255, 0.14); }}
.media-lite-widget .title {{ color: {fg}; font-size: 11px; font-weight: 700; }}
.media-lite-widget .artist {{ color: {muted}; font-size: 10px; }}
.media-lite-widget .thumbnail {{ margin-right: 6px; }}

/* всплывающий плеер над доком */
.media-lite-menu {{
    min-width: 264px; max-width: 264px;
    background-color: {rgba(mix(pill, accent, 0.10), 0.60)};
    border: 1px solid {glass_edge}; border-radius: 16px;
}}
.media-lite-menu .header {{ padding: 20px 24px 0 24px; }}
.media-lite-menu .controls {{ padding: 8px 20px 18px 20px; }}
.media-lite-menu .title {{ font-size: 16px; font-weight: 700; color: {fg}; margin-top: 10px; }}
.media-lite-menu .artist {{ font-size: 12px; font-weight: 600; color: {muted}; margin-top: 2px; margin-bottom: 10px; }}
.media-lite-menu .source {{ min-width: 16px; min-height: 16px; padding: 0; background-color: transparent; }}
.media-lite-menu .volume-button {{
    font-family: "Segoe Fluent Icons"; font-size: 15px; min-width: 24px; min-height: 24px; color: {fg};
}}
.media-lite-menu .volume-button.muted, .media-lite-menu .volume-button.unavailable {{ color: {muted}; }}
.media-lite-menu .volume-slider-popup {{
    background-color: {pill}; border: 1px solid {line}; border-radius: 10px; padding: 12px 8px;
}}
.media-lite-menu .volume-slider {{ min-height: 120px; max-height: 120px; }}
.media-lite-menu .volume-slider::groove {{ background: rgba(255, 255, 255, 0.14); width: 4px; border-radius: 2px; }}
.media-lite-menu .volume-slider::sub-page {{ background: rgba(255, 255, 255, 0.14); border-radius: 2px; }}
.media-lite-menu .volume-slider::add-page {{ background: {accent}; border-radius: 2px; }}
.media-lite-menu .btn {{
    font-family: "Segoe Fluent Icons"; font-size: 13px; font-weight: 400; color: {fg};
    margin: 4px 3px; min-width: 36px; max-width: 36px; min-height: 36px; max-height: 36px;
    border-radius: 18px; background-color: transparent;
}}
.media-lite-menu .btn:hover {{ background-color: rgba(255, 255, 255, 0.12); }}
.media-lite-menu .btn:pressed {{ background-color: rgba(255, 255, 255, 0.20); }}
.media-lite-menu .btn.play {{
    font-size: 17px; background-color: {accent}; color: {accent_fg};
    min-width: 46px; max-width: 46px; min-height: 46px; max-height: 46px; border-radius: 23px; margin: 0 8px;
}}
.media-lite-menu .btn.play:hover {{ background-color: {mix(accent, '#ffffff', 0.18)}; }}
.media-lite-menu .btn.shuffle.active, .media-lite-menu .btn.repeat.active {{ color: {accent}; }}
.media-lite-menu .btn.disabled, .media-lite-menu .btn.disabled:hover {{ color: {muted}; background-color: transparent; }}
.media-lite-menu .playback-time {{ font-size: 11px; font-weight: 600; color: {muted}; }}
.media-lite-menu .progress-slider {{ height: 12px; margin: 2px 0; }}
.media-lite-menu .progress-slider::groove {{ background: rgba(255, 255, 255, 0.14); height: 4px; border-radius: 2px; }}
.media-lite-menu .progress-slider::sub-page {{ background: {accent}; border-radius: 2px; }}
.media-lite-menu .progress-slider::handle {{
    background: {fg}; width: 10px; height: 10px; margin: -3px 0; border-radius: 5px;
}}
"""
open(os.path.join(ydir, "styles.css"), "w", encoding="utf-8").write(css)

# ---------------------------------------------------------------- Zebar: цвета виджетов
if os.path.isdir(zdir):
    json.dump({
        "id": tid, "name": tname,
        "fg": fg, "muted": muted, "accent": accent, "accent2": c["tertiary"], "accent3": c["secondary"],
        "glow": glow, "pill": pill, "line": line,
        "glass": glass_tint, "edge": glass_edge, "wall": "glass.jpg", "wallv": int(os.path.getmtime(wall)) % 100000 + len(tid),
        "screen": list(SCREEN),
    }, open(os.path.join(zdir, "theme.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# ---------------------------------------------------------------- GlazeWM: зазоры и рамка
SIDE = "%dpx" % int(OPTS["side_gap"])          # отступ окон от левого и правого края экрана
if os.path.exists(gz):
    bak = gz + ".bak"
    if not os.path.exists(bak): shutil.copy(gz, bak)
    t = open(gz, encoding="utf-8").read()
    t = re.sub(r"inner_gap: '\d+px'", "inner_gap: '10px'", t)
    t = re.sub(r"(outer_gap:\s*\n\s*top: )'\d+px'(\s*\n\s*right: )'\d+px'(\s*\n\s*bottom: )'\d+px'(\s*\n\s*left: )'\d+px'",
               lambda m: f"{m.group(1)}'6px'{m.group(2)}'{SIDE}'{m.group(3)}'10px'{m.group(4)}'{SIDE}'", t)
    t = re.sub(r"(border:\s*\n\s*enabled: true\s*\n\s*color: )'#[0-9a-fA-F]+'",
               lambda m: m.group(1) + "'" + accent + "'", t, count=1)
    open(gz, "w", encoding="utf-8").write(t)
    try:
        import subprocess
        if os.environ.get("RYOKU_DRYRUN"):          # самопроверка установщика: работающую систему не трогаем
            raise RuntimeError("dry run")
        subprocess.run(["glazewm", "command", "wm-reload-config"], creationflags=0x08000000, timeout=10,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

if not os.environ.get("RYOKU_DRYRUN"):
    set_wallpaper(wall)
json.dump({"theme": tid, "name": tname, "wallpaper": wall}, open(state_file, "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
if sys.stdout:
    print("Тема:", tid, "-", tname, "| акцент", accent, "| таблетка", pill)
