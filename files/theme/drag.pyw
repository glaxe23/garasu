"""Выделение, перенос и изменение размера виджета мышкой.
Виджет запускает этот скрипт один раз, когда по нему кликнули:   pythonw drag.pyw clock
Пока скрипт работает, виджет считается выделенным (показывает окантовку и квадратик в углу).

  - зажал виджет и тащишь                -> окно едет за курсором
  - зажал квадратик в правом нижнем углу -> меняется размер
  - кликнул шестерёнку в правом верхнем  -> открываются настройки этого виджета
  - кликнул мимо виджета или нажал Esc   -> скрипт завершается, окантовка пропадает

Привязка: при переносе виджет «прилипает» к краям и центру экрана и к краям и центрам других
виджетов, в этот момент видна направляющая линия. Размер меняется шагами по 5%.
Зажатый Shift временно отключает привязку. Совсем выключить - галочка в панели «Виджеты».

Новое место и размер записываются в widgets.json и zpack.json, поэтому сохраняются после перезагрузки."""
import os, sys, time, ctypes
from ctypes import wintypes

name = sys.argv[1] if len(sys.argv) > 1 else ""
# зоны кнопок и ползунков внутри виджета (доли ширины и высоты окна): нажатие там окно не двигает
ZONES = []
for z in (sys.argv[2].split(";") if len(sys.argv) > 2 else []):
    try:
        ZONES.append(tuple(float(v) for v in z.split(",")))
    except ValueError:
        pass
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import widgets as W

if name not in W.ORDER:
    sys.exit()
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass
u = ctypes.windll.user32
u.FindWindowW.restype = wintypes.HWND
u.WindowFromPoint.restype = wintypes.HWND
u.WindowFromPoint.argtypes = [wintypes.POINT]
u.GetAncestor.restype = wintypes.HWND
u.GetAncestor.argtypes = [wintypes.HWND, ctypes.c_uint]
hwnd = u.FindWindowW(None, "Zebar - ryoku / " + name)
if not hwnd:
    sys.exit()
try:
    K = u.GetDpiForWindow(hwnd) / 96 or 1     # масштаб экрана Windows (1.0 = 100%)
except Exception:
    K = 1
GRIP = round(26 * K)                          # зона квадратика в правом нижнем углу окна
SW, SH = u.GetSystemMetrics(0), u.GetSystemMetrics(1)
BW, BH = W.size(name, W.load())
NOSIZE, NOMOVE, NOZ, NOACT = 0x0001, 0x0002, 0x0004, 0x0010


TH = round(12 * K)                           # на каком расстоянии срабатывает привязка


class Guides:
    """Две тонкие линии во весь экран: показывают, к чему прилип виджет."""
    def __init__(self):
        self.tk = None

    def start(self):
        import json, tkinter as tk
        color = "#eeb7d0"
        try:
            color = json.load(open(os.path.join(W.zdir, "theme.json"), encoding="utf-8"))["accent"]
        except Exception:
            pass
        self.tk = tk.Tk()
        self.tk.withdraw()
        self.lines = []
        for _ in range(2):
            t = tk.Toplevel(self.tk)
            t.title("Ryoku Guide")
            t.overrideredirect(True)
            t.attributes("-topmost", True)
            t.configure(bg=color)
            t.withdraw()
            self.lines.append(t)
        self.shown = [None, None]

    def show(self, gx, gy):
        if self.tk is None:
            if gx is None and gy is None:
                return
            self.start()
        for i, (g, geo) in enumerate(((gx, "2x%d+%d+0"), (gy, "%dx2+0+%d"))):
            if g != self.shown[i]:
                self.shown[i] = g
                if g is None:
                    self.lines[i].withdraw()
                else:
                    self.lines[i].geometry(geo % ((SH, int(g) - 1) if i == 0 else (SW, int(g) - 1)))
                    self.lines[i].deiconify()
        self.tk.update()

    def hide(self):
        if self.tk is not None:
            self.show(None, None)


guides = Guides()


def targets():
    """Линии, к которым можно прилипнуть: (координата, каким местом виджета)."""
    wa = wintypes.RECT()
    u.SystemParametersInfoW(0x30, 0, ctypes.byref(wa), 0)        # рабочая область без верхней панели
    xs = [(wa.left, "start"), (wa.right, "end"), ((wa.left + wa.right) / 2, "center")]
    ys = [(wa.top, "start"), (wa.bottom, "end"), ((wa.top + wa.bottom) / 2, "center")]
    for other in W.ORDER:
        if other == name:
            continue
        h = u.FindWindowW(None, "Zebar - ryoku / " + other)
        if not h or not u.IsWindowVisible(h):
            continue
        o = wintypes.RECT()
        u.GetWindowRect(h, ctypes.byref(o))
        xs += [(o.left, "start"), (o.right, "end"), (o.right, "start"), (o.left, "end"), ((o.left + o.right) / 2, "center")]
        ys += [(o.top, "start"), (o.bottom, "end"), (o.bottom, "start"), (o.top, "end"), ((o.top + o.bottom) / 2, "center")]
    return xs, ys


def snap(pos, size, lines):
    """Ближайшая линия в пределах TH -> (новая позиция, координата линии), иначе (pos, None)."""
    best, line, dist = pos, None, TH + 1
    for v, kind in lines:
        cand = v if kind == "start" else v - size if kind == "end" else v - size / 2
        if abs(cand - pos) < dist:
            best, line, dist = round(cand), v, abs(cand - pos)
    return best, line


def lbutton():
    return bool(u.GetAsyncKeyState(0x01) & 0x8000)


def cursor():
    pt = wintypes.POINT()
    u.GetCursorPos(ctypes.byref(pt))
    return pt


def rect():
    rc = wintypes.RECT()
    u.GetWindowRect(hwnd, ctypes.byref(rc))
    return rc


def on_widget(pt):
    """Курсор над нашим виджетом и его не закрывает другое окно."""
    top = u.WindowFromPoint(pt)
    return bool(top) and u.GetAncestor(top, 2) == hwnd


def move(pt, rc):
    dx, dy = pt.x - rc.left, pt.y - rc.top
    x0, y0 = rc.left, rc.top
    x, y = x0, y0
    w, h = rc.right - rc.left, rc.bottom - rc.top
    use_snap = W.load()["all"].get("snap", True)
    xs, ys = targets() if use_snap else ([], [])
    while lbutton():
        pt = cursor()
        nx = max(-40, min(SW - 60, pt.x - dx))
        ny = max(0, min(SH - 40, pt.y - dy))
        if use_snap and not u.GetAsyncKeyState(0x10) & 0x8000:      # Shift отключает привязку
            nx, gx = snap(nx, w, xs)
            ny, gy = snap(ny, h, ys)
            guides.show(gx, gy)
        else:
            guides.hide()
        if (nx, ny) != (x, y):
            x, y = nx, ny
            u.SetWindowPos(hwnd, None, x, y, 0, 0, NOSIZE | NOZ | NOACT)
        time.sleep(0.008)
    guides.hide()
    if abs(x - x0) + abs(y - y0) > 3:
        cfg = W.load()
        cfg[name]["x"], cfg[name]["y"] = round(x / K), round(y / K)
        W.apply(cfg, restart=False)


def resize(pt, rc):
    cfg = W.load()
    s0 = s = cfg[name]["scale"]
    w0 = max(1, rc.right - rc.left)
    k = w0 / (BW * s0 / 100 + 4)              # пикселей экрана на один пиксель виджета
    cx0 = pt.x
    step = 5 if cfg["all"].get("snap", True) else 1
    while lbutton():
        ns = s0 * (w0 + cursor().x - cx0) / w0
        if not u.GetAsyncKeyState(0x10) & 0x8000:
            ns = round(ns / step) * step                        # ровные шаги по 5%
        ns = max(40, min(200, round(ns)))
        if ns != s:
            s = ns
            u.SetWindowPos(hwnd, None, 0, 0, round((BW * s / 100 + 4) * k), round((BH * s / 100 + 4) * k),
                           NOMOVE | NOZ | NOACT)
        time.sleep(0.008)
    if s != s0:
        cfg = W.load()
        cfg[name]["scale"] = s
        W.apply(cfg, restart=False)


def act():
    """Кнопка только что нажата: решаем, что делать. False = кликнули мимо, пора выходить."""
    pt, rc = cursor(), rect()
    if not on_widget(pt):
        return False
    fx = (pt.x - rc.left) / max(1, rc.right - rc.left)
    fy = (pt.y - rc.top) / max(1, rc.bottom - rc.top)
    if any(len(z) == 4 and z[0] <= fx <= z[2] and z[1] <= fy <= z[3] for z in ZONES):
        while lbutton():                                          # кнопка или ползунок: окно не трогаем
            time.sleep(0.01)
        return True
    if pt.x >= rc.right - GRIP and pt.y <= rc.top + GRIP:           # шестерёнка: настройки этого виджета
        import subprocess
        subprocess.Popen([W.PYW, os.path.join(W.here, 'widgets_panel.pyw'), name], creationflags=0x08000000)
        while lbutton():
            time.sleep(0.01)
    elif pt.x >= rc.right - GRIP and pt.y >= rc.bottom - GRIP:
        resize(pt, rc)
    else:
        move(pt, rc)
    return True


end = time.time() + 1800                      # страховка: через полчаса выделение снимется само
if lbutton():                                 # клик, которым виджет выделили: сразу можно тащить
    act()
was_down = lbutton()
while time.time() < end and u.IsWindow(hwnd):
    down = lbutton()
    if down and not was_down and not act():
        break
    if u.GetAsyncKeyState(0x02) & 0x8000 and not on_widget(cursor()):   # правый клик мимо
        break
    if u.GetAsyncKeyState(0x1B) & 0x8000:                               # Esc
        break
    was_down = lbutton()
    time.sleep(0.015)
