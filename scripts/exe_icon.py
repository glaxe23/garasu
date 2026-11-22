"""Встраивает значок установщика Garasu в ресурсы Windows EXE."""
import struct, ctypes
from ctypes import wintypes

RT_ICON, RT_GROUP_ICON = 3, 14


def set_icon(exe, ico):
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
