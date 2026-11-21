"""Значок программы, ярлыка или папки -> PNG-файл (для виджета «Ярлыки»).

Ярлык (.lnk) сначала раскрывается до самой программы: так значок получается без стрелки в углу.
Значок берётся крупным (64 точки), чтобы быть чётким и на экранах с увеличенным масштабом."""
import os, ctypes, hashlib, subprocess
import ctypes.wintypes as wt

N = 64


def resolve(path):
    """Для ярлыка .lnk вернуть (файл со значком, номер значка); для остального (путь, 0)."""
    if not path.lower().endswith(".lnk"):
        return path, 0
    try:
        ps = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:GARASU_LNK);"
              "[Console]::OutputEncoding=[Text.Encoding]::UTF8; $s.TargetPath; $s.IconLocation")
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, timeout=15,
                             env=dict(os.environ, GARASU_LNK=path), creationflags=0x08000000).stdout.decode("utf-8", "replace")
        lines = [l.strip() for l in out.splitlines() if l.strip()]
        target = lines[0] if lines else ""
        icon, _, idx = (lines[1] if len(lines) > 1 else "").rpartition(",")
        icon = os.path.expandvars(icon)
        if icon and os.path.exists(icon):
            return icon, int(idx or 0)
        if target and os.path.exists(target):
            return target, 0
    except Exception:
        pass
    return path, 0


def _draw(hicon):
    from PIL import Image
    user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [("biSize", wt.DWORD), ("biWidth", ctypes.c_long), ("biHeight", ctypes.c_long),
                    ("biPlanes", wt.WORD), ("biBitCount", wt.WORD), ("biCompression", wt.DWORD),
                    ("biSizeImage", wt.DWORD), ("biXPelsPerMeter", ctypes.c_long),
                    ("biYPelsPerMeter", ctypes.c_long), ("biClrUsed", wt.DWORD), ("biClrImportant", wt.DWORD)]

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
    bmi = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), N, -N, 1, 32, 0, 0, 0, 0, 0, 0)
    screen = user32.GetDC(None)
    dc = gdi32.CreateCompatibleDC(screen)
    bits = ctypes.c_void_p()
    bmp = gdi32.CreateDIBSection(dc, ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0)
    old = gdi32.SelectObject(dc, bmp)
    user32.DrawIconEx(dc, 0, 0, hicon, N, N, 0, None, 3)
    img = Image.frombuffer("RGBA", (N, N), ctypes.string_at(bits, N * N * 4), "raw", "BGRA", 0, 1).copy()
    gdi32.SelectObject(dc, old)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(dc)
    user32.ReleaseDC(None, screen)
    user32.DestroyIcon(hicon)
    return img if img.getbbox() else None


def icon_image(path):
    """Картинка PIL со значком файла или папки, None если достать не удалось."""
    src, idx = resolve(path)
    if src == path and path.lower().endswith(".lnk"):
        return None            # ярлык не раскрылся: виджет покажет плитку с буквой, а не лист со стрелкой
    user32, shell32 = ctypes.windll.user32, ctypes.windll.shell32
    # 1) значок нужного размера прямо из файла программы (exe, dll, ico): чёткий и без стрелки ярлыка
    user32.PrivateExtractIconsW.argtypes = [ctypes.c_wchar_p, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                            ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_uint),
                                            ctypes.c_uint, ctypes.c_uint]
    h, iid = ctypes.c_void_p(), ctypes.c_uint()
    if os.path.isfile(src) and user32.PrivateExtractIconsW(src, idx, N, N, ctypes.byref(h), ctypes.byref(iid), 1, 0) > 0 and h.value:
        img = _draw(h.value)
        if img:
            return img

    # 2) значок, который показывает Проводник (папки, документы, ссылки)
    class SHFILEINFO(ctypes.Structure):
        _fields_ = [("hIcon", ctypes.c_void_p), ("iIcon", ctypes.c_int), ("dwAttributes", wt.DWORD),
                    ("szDisplayName", ctypes.c_wchar * 260), ("szTypeName", ctypes.c_wchar * 80)]
    shell32.SHGetFileInfoW.argtypes = [ctypes.c_wchar_p, wt.DWORD, ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint]
    shell32.SHGetFileInfoW.restype = ctypes.c_void_p
    info = SHFILEINFO()
    if shell32.SHGetFileInfoW(src, 0, ctypes.byref(info), ctypes.sizeof(info), 0x100) and info.hIcon:
        return _draw(info.hIcon)
    return None


def save_icon(path, folder):
    """Сохраняет значок в папку и возвращает имя файла ('' если не вышло)."""
    try:
        img = icon_image(path)
        if img is None:
            return ""
        os.makedirs(folder, exist_ok=True)
        name = hashlib.md5(("v2|" + path.lower()).encode("utf-8")).hexdigest()[:12] + ".png"
        img.save(os.path.join(folder, name), optimize=True)
        return name
    except Exception:
        return ""
