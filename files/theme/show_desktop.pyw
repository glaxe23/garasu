"""Свернуть/вернуть все окна программ. Виджеты Zebar, бар YASB и помощники не трогает
(Win+D прятал и их). Второе нажатие возвращает то, что свернули."""
import ctypes, json, os
from ctypes import wintypes

u = ctypes.windll.user32
k32 = ctypes.windll.kernel32
dwm = ctypes.windll.dwmapi
STATE = os.path.join(os.environ.get("TEMP", "."), "garasu_show_desktop.json")
KEEP_EXE = {"zebar.exe", "yasb.exe", "pythonw.exe", "python.exe", "glazewm.exe", "glazewm-watcher.exe",
            "autohotkey64.exe", "autohotkey.exe", "autohotkeyux.exe", "explorer.exe"}
KEEP_CLASS = {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"}


def exe(h):
    pid = wintypes.DWORD()
    u.GetWindowThreadProcessId(h, ctypes.byref(pid))
    hp = k32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not hp:
        return ""
    buf = ctypes.create_unicode_buffer(520)
    n = wintypes.DWORD(520)
    ok = k32.QueryFullProcessImageNameW(hp, 0, buf, ctypes.byref(n))
    k32.CloseHandle(hp)
    return os.path.basename(buf.value).lower() if ok else ""


def cls(h):
    b = ctypes.create_unicode_buffer(256)
    u.GetClassNameW(h, b, 256)
    return b.value


def cloaked(h):
    v = ctypes.c_int(0)
    dwm.DwmGetWindowAttribute(h, 14, ctypes.byref(v), ctypes.sizeof(v))
    return v.value != 0


def app_windows():
    out = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(h, _):
        if not u.IsWindowVisible(h) or u.IsIconic(h) or u.GetWindow(h, 4):  # GW_OWNER
            return True
        if u.GetWindowLongW(h, -20) & 0x80 or cloaked(h):  # WS_EX_TOOLWINDOW
            return True
        if u.GetWindowTextLengthW(h) == 0 or cls(h) in KEEP_CLASS:
            return True
        e = exe(h)
        # Проводник: оставляем рабочий стол и панель, но обычные окна папок сворачиваем
        if e in KEEP_EXE and not (e == "explorer.exe" and cls(h) == "CabinetWClass"):
            return True
        out.append(h)
        return True

    u.EnumWindows(cb, 0)
    return out


def load():
    try:
        return [h for h in json.load(open(STATE)) if u.IsWindow(h) and u.IsIconic(h)]
    except Exception:
        return []


import sys
wins = app_windows()
if "--dry" in sys.argv:  # проверка: только показать, что свернётся
    for h in wins:
        b = ctypes.create_unicode_buffer(200); u.GetWindowTextW(h, b, 200)
        print(exe(h), "|", cls(h), "|", b.value)
    sys.exit()
if wins:
    for h in wins:
        u.ShowWindow(h, 6)  # SW_MINIMIZE
    json.dump(wins, open(STATE, "w"))
else:
    saved = load()
    for h in reversed(saved):
        u.ShowWindow(h, 9)  # SW_RESTORE
    if saved:
        u.SetForegroundWindow(saved[0])
    try:
        os.remove(STATE)
    except OSError:
        pass
