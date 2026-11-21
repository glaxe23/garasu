"""Стиль Проводника (Windhawk «Windows 11 File Explorer Styler») под текущую тему Garasu.
Берёт цвета из ~/.glzr/zebar/ryoku/theme.json. Если мод не установлен — тихо ничего не делает.
Запуск: python explorer_style.py   (ryoku.py вызывает его сам после смены темы)"""
import os, re, sys, json, subprocess

MOD = "windows-11-file-explorer-styler"
CLI = r"C:\Program Files\Windhawk\windhawk-cli.exe"
NOWIN = 0x08000000
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
    glass = rgb(t.get("glass", "rgba(39, 39, 48, 0.38)"))
    tint = "#8C" + hexc(mix(glass, (0, 0, 0), 0.3)).lstrip("#")      # тёмное стекло, ~55% плотности
    W, K = (255, 255, 255), (0, 0, 0)
    return {
        "theme": "TintedGlass",
        "backgroundTranslucentEffect": "acrylicblur",
        "backgroundTranslucentEffectRegion": "",
        "styleConstants[0]": f'CommonBgBrush=<WindhawkBlur BlurAmount="18" TintColor="{tint}"/>',
        "controlStyles[0].target": "TabViewItem > Grid#LayoutRoot > Canvas > Microsoft.UI.Xaml.Shapes.Path#SelectedBackgroundPath",
        "controlStyles[0].styles[0]": 'Stroke:=<SolidColorBrush Color="#FFFFFF" Opacity="0.11"/>',
        "controlStyles[0].styles[1]": "StrokeThickness=1",
        "themeResourceVariables[0]": "SystemAccentColor=" + hexc(accent),
        "themeResourceVariables[1]": "SystemAccentColorLight1=" + hexc(mix(accent, W, 0.25)),
        "themeResourceVariables[2]": "SystemAccentColorLight2=" + hexc(mix(accent, W, 0.5)),
        "themeResourceVariables[3]": "SystemAccentColorLight3=" + hexc(mix(accent, W, 0.75)),
        "themeResourceVariables[4]": "SystemAccentColorDark1=" + hexc(mix(accent, K, 0.15)),
        "themeResourceVariables[5]": "ControlCornerRadius=8",
        "themeResourceVariables[6]": "OverlayCornerRadius=12",
        "explorerFrameContainerHeight": 0,
        "xamlDiagnosticsHandling": "alert",
    }


def main():
    if not os.path.exists(CLI):
        return 0                                   # Windhawk 2.0 нет — Проводник не трогаем
    if not os.path.exists(ZTHEME):
        return 3                                   # тема Garasu ещё не применялась
    r = subprocess.run([CLI, "--json", "mod", "list"], capture_output=True, text=True, creationflags=NOWIN, timeout=30)
    if MOD not in (r.stdout or ""):
        return 0                                   # мод не поставлен — Проводник не трогаем
    settings = build(json.load(open(ZTHEME, encoding="utf-8")))
    path = os.path.join(here, "explorer-style.json")
    json.dump(settings, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if os.environ.get("RYOKU_DRYRUN"):
        return 0
    r = subprocess.run([CLI, "--quiet", "mod", "settings", "write", MOD, path],
                       capture_output=True, text=True, creationflags=NOWIN, timeout=60)
    if sys.stdout:
        print("Проводник:", "ok" if r.returncode == 0 else "ошибка " + (r.stderr or "")[-200:])
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
