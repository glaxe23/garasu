"""Заморозка виджетов, пока их не видно.

Когда каждое окно виджета (Zebar - ryoku / ...) целиком закрыто другим окном дольше FREEZE_AFTER секунд,
процессы отрисовки виджетов (msedgewebview2 --type=renderer из webview-cache\\ryoku) ставятся на паузу,
а их память отдаётся системе. Как только хоть один виджет снова виден, процессы сразу продолжают работу:
страницы не перезагружаются, поэтому виджеты появляются мгновенно и с тем же состоянием.

Не замораживаем: в режиме редактирования, пока играет фон таймера, и будим за WAKE_BEFORE с до конца
отрезка помодоро (время конца пишет freeze_note.pyw, его зовёт виджет таймера).
Лог: freeze.log рядом. Выключить: удалить строку запуска в mode.py или создать файл freeze.off рядом.
"""
import os, sys, time, json, atexit, ctypes, ctypes.wintypes as wt

here = os.path.dirname(os.path.abspath(__file__))
zdir = os.path.join(os.path.expanduser("~"), ".glzr", "zebar", "ryoku")
CFG = os.path.join(zdir, "widgets.json")
NOTE = os.path.join(here, "freeze_note.json")
OFF = os.path.join(here, "freeze.off")
LOG = os.path.join(here, "freeze.log")
FREEZE_AFTER = 3.0
WAKE_BEFORE = 4.0
POLL = 0.3

u32 = ctypes.WinDLL("user32", use_last_error=True)
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
ntdll = ctypes.WinDLL("ntdll")
dwm = ctypes.WinDLL("dwmapi")
psapi = ctypes.WinDLL("psapi")

k32.OpenProcess.restype = wt.HANDLE
k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
k32.CloseHandle.argtypes = [wt.HANDLE]
k32.CreateToolhelp32Snapshot.restype = wt.HANDLE
ntdll.NtSuspendProcess.argtypes = [wt.HANDLE]
ntdll.NtResumeProcess.argtypes = [wt.HANDLE]
ntdll.NtQueryInformationProcess.argtypes = [wt.HANDLE, ctypes.c_int, ctypes.c_void_p, wt.ULONG, ctypes.POINTER(wt.ULONG)]
psapi.EmptyWorkingSet.argtypes = [wt.HANDLE]
u32.GetWindowLongW.restype = ctypes.c_long

PROCESS_SUSPEND_RESUME = 0x0800
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_QUERY_LIMITED = 0x1000
PROCESS_SET_QUOTA = 0x0100


def log(*a):
    try:
        if os.path.exists(LOG) and os.path.getsize(LOG) > 200_000:
            os.replace(LOG, LOG + ".old")
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("%H:%M:%S ") + " ".join(str(x) for x in a) + "\n")
    except Exception:
        pass


# ---------- процессы ----------
class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [("dwSize", wt.DWORD), ("cntUsage", wt.DWORD), ("th32ProcessID", wt.DWORD),
                ("th32DefaultHeapID", ctypes.c_void_p), ("th32ModuleID", wt.DWORD), ("cntThreads", wt.DWORD),
                ("th32ParentProcessID", wt.DWORD), ("pcPriClassBase", ctypes.c_long), ("dwFlags", wt.DWORD),
                ("szExeFile", ctypes.c_wchar * 260)]


def list_procs(name):
    snap = k32.CreateToolhelp32Snapshot(2, 0)
    out = []
    e = PROCESSENTRY32W(); e.dwSize = ctypes.sizeof(e)
    ok = k32.Process32FirstW(snap, ctypes.byref(e))
    while ok:
        if e.szExeFile.lower() == name:
            out.append(e.th32ProcessID)
        ok = k32.Process32NextW(snap, ctypes.byref(e))
    k32.CloseHandle(snap)
    return out


def cmdline(pid):
    h = k32.OpenProcess(PROCESS_QUERY_LIMITED, False, pid)
    if not h:
        return ""
    try:
        n = wt.ULONG(0)
        ntdll.NtQueryInformationProcess(h, 60, None, 0, ctypes.byref(n))     # ProcessCommandLineInformation
        if not n.value:
            return ""
        buf = ctypes.create_string_buffer(n.value)
        if ntdll.NtQueryInformationProcess(h, 60, buf, n.value, ctypes.byref(n)) != 0:
            return ""
        length = ctypes.c_ushort.from_buffer(buf, 0).value
        ptr = ctypes.c_void_p.from_buffer(buf, 8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 4).value
        return ctypes.wstring_at(ptr, length // 2) if ptr else ""
    finally:
        k32.CloseHandle(h)


_cmd_cache = {}


def renderers():
    """PID процессов отрисовки виджетов (браузер ryoku)."""
    pids = list_procs("msedgewebview2.exe")
    alive = set(pids)
    for p in list(_cmd_cache):
        if p not in alive:
            del _cmd_cache[p]
    out = []
    for p in pids:
        if p not in _cmd_cache:
            _cmd_cache[p] = cmdline(p).lower()
        c = _cmd_cache[p]
        if "webview-cache\\ryoku" in c and "--type=renderer" in c:
            out.append(p)
    return out


frozen = set()


def freeze_all():
    for p in renderers():
        if p in frozen:
            continue
        h = k32.OpenProcess(PROCESS_SUSPEND_RESUME | PROCESS_QUERY_INFORMATION | PROCESS_SET_QUOTA, False, p)
        if not h:
            continue
        if ntdll.NtSuspendProcess(h) == 0:
            frozen.add(p)
            psapi.EmptyWorkingSet(h)
        k32.CloseHandle(h)


def wake_all():
    for p in list(frozen):
        h = k32.OpenProcess(PROCESS_SUSPEND_RESUME, False, p)
        if h:
            ntdll.NtResumeProcess(h)
            k32.CloseHandle(h)
        frozen.discard(p)


def wake_everything():
    """На всякий случай: продолжить все процессы виджетов (если прошлый запуск упал, не разбудив)."""
    for p in renderers():
        h = k32.OpenProcess(PROCESS_SUSPEND_RESUME, False, p)
        if h:
            # NtResumeProcess снимает одну паузу; лишний вызов для работающего процесса безвреден
            ntdll.NtResumeProcess(h)
            k32.CloseHandle(h)
    frozen.clear()


# ---------- окна ----------
WNDENUM = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
SKIP_CLASS = {"progman", "workerw", "shell_traywnd", "shell_secondarytraywnd", "windows.ui.core.corewindow"}
WS_EX_TOOLWINDOW, WS_EX_TRANSPARENT, WS_EX_NOACTIVATE = 0x80, 0x20, 0x08000000


def title(h):
    n = u32.GetWindowTextLengthW(h)
    b = ctypes.create_unicode_buffer(n + 1)
    u32.GetWindowTextW(h, b, n + 1)
    return b.value


def cls(h):
    b = ctypes.create_unicode_buffer(128)
    u32.GetClassNameW(h, b, 128)
    return b.value


def rect(h):
    r = wt.RECT()
    if dwm.DwmGetWindowAttribute(h, 9, ctypes.byref(r), ctypes.sizeof(r)) != 0:   # видимые границы без тени
        u32.GetWindowRect(h, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom


def cloaked(h):
    v = ctypes.c_int(0)
    dwm.DwmGetWindowAttribute(h, 14, ctypes.byref(v), 4)
    return v.value != 0


def pid_of(h):
    p = wt.DWORD()
    u32.GetWindowThreadProcessId(h, ctypes.byref(p))
    return p.value


_exe_cache = {}


def exe_of(pid):
    if pid in _exe_cache:
        return _exe_cache[pid]
    name = ""
    h = k32.OpenProcess(PROCESS_QUERY_LIMITED, False, pid)
    if h:
        b = ctypes.create_unicode_buffer(520); n = wt.DWORD(520)
        if k32.QueryFullProcessImageNameW(h, 0, b, ctypes.byref(n)):
            name = os.path.basename(b.value).lower()
        k32.CloseHandle(h)
    if len(_exe_cache) > 500:
        _exe_cache.clear()
    _exe_cache[pid] = name
    return name


SKIP_EXE = {"zebar.exe", "yasb.exe", "glazewm.exe", "glazewm-watcher.exe", "msedgewebview2.exe"}


def desktop_hidden():
    """True, если каждое окно виджета целиком закрыто каким-то обычным окном."""
    widgets, covers = [], []

    def cb(h, _):
        if not u32.IsWindowVisible(h) or u32.IsIconic(h) or cloaked(h):
            return True
        t = title(h)
        if t.startswith("Zebar - ryoku /"):
            r = rect(h)
            if r[2] > r[0] and r[3] > r[1]:
                widgets.append(r)
            return True
        if cls(h).lower() in SKIP_CLASS:
            return True
        ex = u32.GetWindowLongW(h, -20)
        if ex & (WS_EX_TOOLWINDOW | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE):
            return True
        if exe_of(pid_of(h)) in SKIP_EXE:
            return True
        r = rect(h)
        if r[2] - r[0] < 200 or r[3] - r[1] < 200:
            return True
        covers.append(r)
        return True

    u32.EnumWindows(WNDENUM(cb), 0)
    if not widgets:
        return False
    for w in widgets:
        if not any(c[0] <= w[0] and c[1] <= w[1] and c[2] >= w[2] and c[3] >= w[3] for c in covers):
            return False
    return True


# ---------- исключения ----------
def edit_mode():
    try:
        return bool(json.load(open(CFG, encoding="utf-8")).get("all", {}).get("edit"))
    except Exception:
        return False


def pomodoro():
    """(время конца отрезка в секундах или 0, играет ли фон)."""
    try:
        n = json.load(open(NOTE, encoding="utf-8"))
        ends = float(n.get("endsAt") or 0) / 1000 if n.get("running") else 0
        amb = bool(n.get("running")) and n.get("phase") == "work" and n.get("amb", "off") != "off"
        return ends, amb
    except Exception:
        return 0, False


# ---------- основной цикл ----------
def main():
    wake_everything()
    atexit.register(wake_all)
    log("start", os.getpid())
    hidden_since = None
    last_rescan = 0
    while True:
        try:
            now = time.time()
            ends, amb = pomodoro()
            soon = ends and -30 < ends - now < WAKE_BEFORE
            allow = not os.path.exists(OFF) and not edit_mode() and not amb and not soon
            hidden = allow and desktop_hidden()
            if hidden:
                hidden_since = hidden_since or now
                if now - hidden_since >= FREEZE_AFTER:
                    if not frozen:
                        freeze_all()
                        log("freeze", sorted(frozen))
                        last_rescan = now
                    elif now - last_rescan > 5:          # Zebar перезапустился — новые процессы тоже заморозить
                        last_rescan = now
                        freeze_all()
            else:
                hidden_since = None
                if frozen:
                    wake_all()
                    log("wake", "soon" if soon else "amb" if amb else "visible")
        except Exception as e:
            log("err", repr(e))
        time.sleep(POLL)


if __name__ == "__main__":
    try:
        main()
    finally:
        wake_all()
