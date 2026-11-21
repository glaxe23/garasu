"""Плавная смена обоев через встроенный интерфейс Windows IDesktopWallpaper.

Windows сама делает мягкое перетекание старых обоев в новые (как в слайд-шоу).
Чистый ctypes, без сторонних библиотек. Если что-то не получилось, set() вернёт False,
и вызывающий код поставит обои старым способом (SystemParametersInfo, рывком).
"""
import ctypes
from ctypes import wintypes

_ole = ctypes.OleDLL("ole32")


class GUID(ctypes.Structure):
    _fields_ = [("a", wintypes.DWORD), ("b", wintypes.WORD), ("c", wintypes.WORD), ("d", ctypes.c_ubyte * 8)]


def _guid(s):
    g = GUID()
    _ole.CLSIDFromString(ctypes.c_wchar_p(s), ctypes.byref(g))
    return g


CLSID_DesktopWallpaper = "{C2CF3110-460E-4fc1-B9D0-8A1C0C9CC4BD}"
IID_IDesktopWallpaper = "{B92B56A9-8B55-4E14-9A89-0199BBB6F93B}"
DWPOS_FILL = 4

# номера методов в таблице IDesktopWallpaper (после трёх методов IUnknown)
_SET_WALLPAPER, _SET_POSITION, _RELEASE = 3, 10, 2


def _method(obj, index, *argtypes):
    vtbl = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    proto = ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p, *argtypes)
    return proto(vtbl[index])


def set(path):
    """Ставит обои на все мониторы с плавным переходом. True — получилось."""
    inited = False
    obj = ctypes.c_void_p()
    try:
        try:
            _ole.CoInitializeEx(None, 2)       # COINIT_APARTMENTTHREADED
            inited = True
        except OSError:
            pass                               # поток уже инициализирован иначе — это не мешает
        _ole.CoCreateInstance(ctypes.byref(_guid(CLSID_DesktopWallpaper)), None, 0x17,   # CLSCTX_ALL
                              ctypes.byref(_guid(IID_IDesktopWallpaper)), ctypes.byref(obj))
        _method(obj, _SET_POSITION, ctypes.c_int)(obj, DWPOS_FILL)
        _method(obj, _SET_WALLPAPER, wintypes.LPCWSTR, wintypes.LPCWSTR)(obj, None, path)
        return True
    except Exception:
        return False
    finally:
        if obj:
            try:
                ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(
                    ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents[_RELEASE])(obj)
            except Exception:
                pass
        if inited:
            _ole.CoUninitialize()
