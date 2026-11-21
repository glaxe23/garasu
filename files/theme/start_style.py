"""Стиль меню «Пуск» (Windhawk «Windows 11 Start Menu Styler») под текущую тему Garasu.
Пуск остаётся на своём месте (по центру над панелью задач), меняется только вид: тёмное стекло,
скругления и акцент из темы. Цвета берёт из ~/.glzr/zebar/ryoku/theme.json.
Если мод не установлен — тихо ничего не делает.
Запуск: python start_style.py   (ryoku.py вызывает его сам после смены темы)"""
import os, re, sys, json, subprocess

MOD = "windows-11-start-menu-styler"
CLI = r"C:\Program Files\Windhawk\windhawk-cli.exe"
NOWIN = 0x08000000
TASK = "RyokuStyle"          # задача Планировщика с правами администратора (ставит style_task_install.ps1)
WIDTH, HEIGHT = 680, 620     # размер «Пуска»
here = os.path.dirname(os.path.abspath(__file__))
ZTHEME = os.path.join(os.path.expanduser("~"), ".glzr", "zebar", "ryoku", "theme.json")


def rgb(s):
    s = s.strip()
    m = re.match(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", s)
    if m:
        return tuple(int(x) for x in m.groups())
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def hexc(t):
    return "#%02X%02X%02X" % tuple(max(0, min(255, round(v))) for v in t)


def mix(a, b, k):
    return tuple(x + (y - x) * k for x, y in zip(a, b))


def build(t):
    accent = rgb(t["accent"])
    fg = rgb(t.get("fg", "#ffffff"))
    glass = rgb(t.get("glass", "rgba(39, 39, 48, 0.38)"))
    W, K = (255, 255, 255), (0, 0, 0)
    tint = "#A6" + hexc(mix(glass, K, 0.35)).lstrip("#")       # тёмное стекло, ~65% плотности
    tile = "#26" + hexc(mix(glass, W, 0.10)).lstrip("#")       # плашки чуть светлее фона
    blur = f'<WindhawkBlur BlurAmount="30" TintColor="{tint}"/>'
    s = {
        "theme": "",
        "disableNewStartMenuLayout": "",
        "webContentStyles[0].target": "",
        "webContentStyles[0].styles[0]": "",
        "webContentCustomJs": "",
        "styleConstants[0]": "CommonBgBrush=" + blur,
    }
    A = hexc(accent); F = hexc(fg); AL = hexc(mix(accent, W, 0.35))
    line = '<SolidColorBrush Color="#FFFFFF" Opacity="0.12"/>'
    head = ["Foreground=" + A, "FontWeight=Bold", "FontSize=11", "CharacterSpacing=160"]
    rules = [
        # фон: стекло вместо акрила Windows, скругление и тонкая светлая рамка, как у карточек Garasu
        ("Border#AcrylicBorder", ["Background:=" + blur, "CornerRadius=16",
                                  'BorderBrush:=<SolidColorBrush Color="#FFFFFF" Opacity="0.14"/>',
                                  "BorderThickness=1"]),
        ("Border#AcrylicOverlay", ["Visibility=Collapsed"]),
        ("StartDocked.StartSizingFramePanel", ["CornerRadius=16", f"Width={WIDTH}", f"MaxWidth={WIDTH}", f"MinWidth={WIDTH}"]),
        # размер: чуть компактнее стандартного
        ("StartDocked.StartSizingFrame", [f"Width={WIDTH}", f"MaxWidth={WIDTH}", f"MinWidth={WIDTH}", f"MaxHeight={HEIGHT}"]),
        ("StartDocked.LauncherFrame > Grid#RootGrid > Grid#RootContent", [f"Width={WIDTH}", f"MaxWidth={WIDTH}", f"MinWidth={WIDTH}"]),
        # строка поиска: стеклянная «таблетка» с тонкой рамкой, лупа в цвете акцента
        ("StartDocked.SearchBoxToggleButton", ["CornerRadius=20", "Background=Transparent"]),
        ("Border#TaskbarSearchBackground", ["CornerRadius=20", "Background=" + tile,
                                            "BorderBrush:=" + line, "BorderThickness=1"]),
        ("TextBlock#PlaceholderText", ["Foreground=" + F, "Opacity=0.55"]),
        # заголовки разделов как у виджетов: капсом, разреженно, жирно, цветом акцента
        ("TextBlock#PinnedListHeaderText", head + ["Text=ЗАКРЕПЛЕНО"]),
        ("TextBlock#AllAppsHeading", head + ["Text=ВСЕ ПРИЛОЖЕНИЯ"]),
        # кнопки «Все >» / «Назад»: маленькая стеклянная таблетка
        ("Grid#ContentBorder > Border#BackgroundBorder", ["CornerRadius=12", "Background=" + tile,
                                                          "BorderBrush:=" + line, "BorderThickness=1"]),
        # плитки приложений: мягкое скругление подсветки при наведении
        ("Grid#DroppedFlickerWorkaroundWrapper > Border#BackgroundBorder", ["CornerRadius=12"]),
        ("TextBlock#AppDisplayName", ["Foreground=" + F]),
        # нижняя полоса: прозрачная, отделена тонкой линией, значки в светлом акценте
        ("StartDocked.NavigationPaneView", ["Background=Transparent", "BorderBrush:=" + line,
                                            "BorderThickness=0,1,0,0"]),
        ("TextBlock#UserTileNameText", ["Foreground=" + F]),
        ("StartDocked.NavigationPaneButton > Grid > Border#BackgroundBorder", ["CornerRadius=10"]),
        ("FontIcon > Grid > TextBlock", ["Foreground=" + AL]),
        ("StartDocked.NavigationPaneButton#PowerButton > Grid > Border#BackgroundBorder", ["CornerRadius=10"]),
    ]
    for i, (target, styles) in enumerate(rules):
        s[f"controlStyles[{i}].target"] = target
        for j, st in enumerate(styles):
            s[f"controlStyles[{i}].styles[{j}]"] = st
    for i, v in enumerate([
        "SystemAccentColor=" + hexc(accent),
        "SystemAccentColorLight1=" + hexc(mix(accent, W, 0.25)),
        "SystemAccentColorLight2=" + hexc(mix(accent, W, 0.5)),
        "SystemAccentColorLight3=" + hexc(mix(accent, W, 0.75)),
        "SystemAccentColorDark1=" + hexc(mix(accent, K, 0.15)),
        "ControlCornerRadius=8",
        "OverlayCornerRadius=12",
    ]):
        s[f"themeResourceVariables[{i}]"] = v
    return s


def main():
    if not os.path.exists(CLI):
        return 0                                   # Windhawk 2.0 нет — Пуск не трогаем
    if not os.path.exists(ZTHEME):
        return 3                                   # тема Garasu ещё не применялась
    r = subprocess.run([CLI, "--json", "mod", "list"], capture_output=True, text=True, creationflags=NOWIN, timeout=30)
    if MOD not in (r.stdout or ""):
        return 0                                   # мод не поставлен — Пуск не трогаем
    settings = build(json.load(open(ZTHEME, encoding="utf-8")))
    path = os.path.join(here, "start-style.json")
    json.dump(settings, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if os.environ.get("RYOKU_DRYRUN"):
        return 0
    # есть задача RyokuStyle — пишем через неё, без окна UAC; иначе пробуем напрямую (нужен администратор)
    t = subprocess.run(["schtasks", "/run", "/tn", TASK], capture_output=True, text=True, creationflags=NOWIN, timeout=30)
    if t.returncode == 0:
        r = t
    else:
        r = subprocess.run([CLI, "--quiet", "mod", "settings", "write", MOD, path],
                           capture_output=True, text=True, creationflags=NOWIN, timeout=60)
    if sys.stdout:
        print("Пуск:", "ok" if r.returncode == 0 else "ошибка " + (r.stderr or "")[-200:])
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
