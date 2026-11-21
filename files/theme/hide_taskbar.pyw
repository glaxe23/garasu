"""Делает системную панель Windows невидимой (прозрачность 0), но оставляет её на месте,
чтобы «Пуск» открывался по центру. Режим: python hide_taskbar.pyw show — вернуть как было."""
import ctypes, time, sys
u = ctypes.windll.user32
GWL_EXSTYLE, WS_EX_LAYERED, LWA_ALPHA = -20, 0x80000, 2
u.GetWindowLongW.restype = ctypes.c_long
CLS = ("Shell_TrayWnd", "Shell_SecondaryTrayWnd")
def set_alpha(a):
    for cls in CLS:
        h = u.FindWindowW(cls, None)
        if not h: continue
        if not u.IsWindowVisible(h): u.ShowWindow(h, 5)
        ex = u.GetWindowLongW(h, GWL_EXSTYLE)
        if a >= 255:
            u.SetWindowLongW(h, GWL_EXSTYLE, ex & ~WS_EX_LAYERED)
        else:
            if not ex & WS_EX_LAYERED: u.SetWindowLongW(h, GWL_EXSTYLE, ex | WS_EX_LAYERED)
            u.SetLayeredWindowAttributes(h, 0, a, LWA_ALPHA)
if len(sys.argv) > 1 and sys.argv[1] == "show":
    set_alpha(255); sys.exit()
# только один экземпляр: второй запуск сразу выходит
ctypes.windll.kernel32.CreateMutexW(None, False, "RyokuWinHideTaskbar")
if ctypes.windll.kernel32.GetLastError() == 183: sys.exit()
try:
    while True:
        set_alpha(0); time.sleep(0.5)
finally:
    set_alpha(255)
