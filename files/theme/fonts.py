"""Шрифты Windows 11 и их замена на Windows 10.

В Windows 11 есть «Segoe Fluent Icons» (значки) и «Segoe UI Variable» (текст). В Windows 10 их нет,
зато есть «Segoe MDL2 Assets» и «Segoe UI». Ставить шрифты Windows 11 на «десятку» нельзя: по лицензии
Microsoft они только для разработки. Поэтому подменяем на встроенные шрифты «десятки».

  import fonts
  fonts.ICONS, fonts.UI          — имена шрифтов, которые есть на этом компьютере
  fonts.family("Segoe UI Variable Text")  — то же для любого имени
  fonts.icons_text(s)            — заменить значки, которых нет в MDL2, на похожие (только на Windows 10)
"""
import os

_DIRS = [os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"),
         os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "Fonts")]


def _has(*files):
    return any(os.path.exists(os.path.join(d, f)) for d in _DIRS for f in files)


_FAKE10 = bool(os.environ.get("GARASU_FAKE_WIN10"))     # проверка на Windows 11: вести себя как на Windows 10
HAS_FLUENT = _has("SegoeIcons.ttf", "Segoe Fluent Icons.ttf") and not _FAKE10
HAS_VARIABLE = _has("SegUIVar.ttf", "SegoeUI-VF.ttf") and not _FAKE10
ICONS = "Segoe Fluent Icons" if HAS_FLUENT else "Segoe MDL2 Assets"
UI = "Segoe UI Variable Text" if HAS_VARIABLE else "Segoe UI"
DISPLAY = "Segoe UI Variable Display" if HAS_VARIABLE else "Segoe UI"

# значки из Fluent, которых нет в MDL2 (Windows 10): чем их заменить. Оба варианта проверены по таблицам шрифтов.
_MISSING = {"\ue62e": "\ue769",   # пауза
            "\ueea1": "\ue950",   # процессор
            "\uf285": "\ue708",   # не беспокоить
            "\ue7aa": "\ue91b",   # обои (картинка)
            }


def family(name):
    """Имя шрифта, который точно есть: шрифты Windows 11 подменяются на шрифты Windows 10."""
    if name == "Segoe Fluent Icons":
        return ICONS
    if name and name.startswith("Segoe UI Variable") and not HAS_VARIABLE:
        return "Segoe UI"
    return name


def icons_text(s):
    if HAS_FLUENT or not s:
        return s
    for a, b in _MISSING.items():
        s = s.replace(a, b)
    return s


def css(text):
    """Стили (YASB): на Windows 10 имена шрифтов Windows 11 заменить на шрифты Windows 10."""
    if not HAS_FLUENT:
        text = text.replace('"Segoe Fluent Icons"', '"Segoe MDL2 Assets"').replace("'Segoe Fluent Icons'", "'Segoe MDL2 Assets'")
    if not HAS_VARIABLE:
        for v in ("Segoe UI Variable Text", "Segoe UI Variable Display", "Segoe UI Variable Small", "Segoe UI Variable"):
            text = text.replace('"%s"' % v, '"Segoe UI"').replace("'%s'" % v, "'Segoe UI'")
    return text


if __name__ == "__main__":
    print("значки:", ICONS, "| текст:", UI, "| Windows 11 шрифты:", HAS_FLUENT, HAS_VARIABLE)
