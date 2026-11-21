"""Значок для Garasu-Setup.exe: рисует 硝 на тёмной плитке и вставляет в готовый exe вместо стандартного.

  set_icon(exe, ico)  - нарисовать ico-файл и заменить значок в exe; возвращает строку для отчёта сборки"""
import os, struct, ctypes
from ctypes import wintypes

RT_ICON, RT_GROUP_ICON = 3, 14


def draw(ico):
    from PIL import Image, ImageDraw, ImageFont
    S = 256
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((8, 8, S - 8, S - 8), 56, fill=(18, 20, 28, 255), outline=(238, 183, 208, 255), width=6)
    font = None
    for name in ("YuGothB.ttc", "msyhbd.ttc", "msgothic.ttc", "simsun.ttc"):
        p = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", name)
        if os.path.exists(p):
            font = ImageFont.truetype(p, 150)
            break
    if font:
        box = d.textbbox((0, 0), "硝", font=font)
        d.text(((S - box[2] - box[0]) / 2, (S - box[3] - box[1]) / 2), "硝", font=font, fill=(238, 183, 208, 255))
    else:
        d.ellipse((76, 76, 180, 180), fill=(238, 183, 208, 255))
    im.save(ico, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (256, 256)])


def set_icon(exe, ico):
    draw(ico)
    raw = open(ico, "rb").read()
    _, _, count = struct.unpack_from("<HHH", raw, 0)
    entries = [struct.unpack_from("<BBBBHHII", raw, 6 + 16 * i) for i in range(count)]

    k = ctypes.windll.kernel32
    k.LoadLibraryExW.restype = wintypes.HMODULE
    k.LoadLibraryExW.argtypes = [wintypes.LPCWSTR, wintypes.HANDLE, wintypes.DWORD]
    k.FreeLibrary.argtypes = [wintypes.HMODULE]
    k.BeginUpdateResourceW.restype = wintypes.HANDLE
    k.BeginUpdateResourceW.argtypes = [wintypes.LPCWSTR, wintypes.BOOL]
    k.UpdateResourceW.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, wintypes.WORD, ctypes.c_void_p, wintypes.DWORD]
    k.EndUpdateResourceW.argtypes = [wintypes.HANDLE, wintypes.BOOL]

    # какие группы значков уже есть в exe (имя и язык): заменяем первую, чтобы Проводник взял именно её
    found = []
    NAMEPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMODULE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
    LANGPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMODULE, ctypes.c_void_p, ctypes.c_void_p, wintypes.WORD, ctypes.c_void_p)
    k.EnumResourceNamesW.argtypes = [wintypes.HMODULE, ctypes.c_void_p, NAMEPROC, ctypes.c_void_p]
    k.EnumResourceLanguagesW.argtypes = [wintypes.HMODULE, ctypes.c_void_p, ctypes.c_void_p, LANGPROC, ctypes.c_void_p]
    mod = k.LoadLibraryExW(exe, None, 0x2)                       # как файл с данными, без запуска
    if mod:
        def on_name(m, typ, name, param):
            key = name if name >> 16 == 0 else ctypes.wstring_at(name)
            def on_lang(m2, t2, n2, lang, p2):
                found.append((key, lang))
                return True
            k.EnumResourceLanguagesW(m, typ, name, LANGPROC(on_lang), None)
            return True
        k.EnumResourceNamesW(mod, RT_GROUP_ICON, NAMEPROC(on_name), None)
        k.FreeLibrary(mod)
    name, lang = found[0] if found else (1, 1033)

    h = k.BeginUpdateResourceW(exe, False)
    if not h:
        raise OSError("BeginUpdateResource: %d" % ctypes.get_last_error())
    group = struct.pack("<HHH", 0, 1, count)
    for i, (w, hh, colors, res, planes, bits, size, offset) in enumerate(entries):
        rid = 900 + i
        data = raw[offset:offset + size]
        if not k.UpdateResourceW(h, RT_ICON, rid, lang, data, len(data)):
            raise OSError("UpdateResource icon")
        group += struct.pack("<BBBBHHIH", w, hh, colors, res, planes, bits, size, rid)
    name_arg = name if isinstance(name, int) else ctypes.cast(ctypes.c_wchar_p(name), ctypes.c_void_p)
    if not k.UpdateResourceW(h, RT_GROUP_ICON, name_arg, lang, group, len(group)):
        raise OSError("UpdateResource group")
    if not k.EndUpdateResourceW(h, False):
        raise OSError("EndUpdateResource")
    return "заменён (группа %s, размеров: %d)" % (name, count)
