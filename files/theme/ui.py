"""Общие элементы для панелей Garasu (tkinter): цвета темы и ползунок в стиле виджетов."""
import os, json
import tkinter as tk

FONT, ICONS = "Segoe UI Variable Text", "Segoe Fluent Icons"
ZDIR = os.path.join(os.path.expanduser("~"), ".glzr", "zebar", "ryoku")


def mix(a, b, t):
    A = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    B = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(round(A[i] + (B[i] - A[i]) * t) for i in range(3))


def colors():
    """Цвета текущей темы: BG фон, FG текст, MUTED приглушённый, ACC акцент, TROUGH подложка."""
    c = {"pill": "#0c080a", "fg": "#f7e8ed", "muted": "#8d7e84", "accent": "#eeb7d0"}
    try:
        c.update(json.load(open(os.path.join(ZDIR, "theme.json"), encoding="utf-8")))
    except Exception:
        pass
    return {"BG": c["pill"], "FG": c["fg"], "MUTED": c["muted"], "ACC": c["accent"],
            "TROUGH": mix(c["pill"], "#ffffff", 0.14)}


class Slider(tk.Canvas):
    """Ползунок: тонкая дорожка со скруглёнными краями, пройденная часть в цвет акцента, круглая ручка.
    Тянется мышкой, крутится колёсиком. command(value) вызывается при каждом изменении."""

    def __init__(self, parent, lo, hi, value, command=None, bg="#000000", track="#333333", accent="#ffffff",
                 knob="#ffffff", height=24, step=None):
        super().__init__(parent, height=height, bg=bg, highlightthickness=0, bd=0, cursor="hand2")
        self.lo, self.hi, self.value, self.command = lo, hi, value, command
        self.track, self.accent, self.knob = track, accent, knob
        self.step = step or max(1, round((hi - lo) / 40))
        self.hot = False
        self.dragging = False
        self.bind("<Configure>", lambda e: self.draw())
        self.bind("<Button-1>", self.press)
        self.bind("<B1-Motion>", self.drag)
        self.bind("<ButtonRelease-1>", self.release)
        self.bind("<MouseWheel>", self.wheel)
        self.bind("<Enter>", lambda e: self.hover(True))
        self.bind("<Leave>", lambda e: self.hover(False))

    PAD = 9

    def draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 30:
            return
        y, a, b = h // 2, self.PAD, w - self.PAD
        x = a + (b - a) * (self.value - self.lo) / max(1, self.hi - self.lo)
        self.create_line(a, y, b, y, fill=self.track, width=5, capstyle="round")
        if x > a + 1:
            self.create_line(a, y, x, y, fill=self.accent, width=5, capstyle="round")
        r = 8 if (self.hot or self.dragging) else 7
        self.create_oval(x - r, y - r, x + r, y + r, fill=self.knob, outline=self.accent, width=2)

    def set(self, value, notify=False):
        value = max(self.lo, min(self.hi, int(round(value))))
        if value != self.value:
            self.value = value
            self.draw()
            if notify and self.command:
                self.command(value)

    def from_x(self, x):
        w = self.winfo_width()
        t = (x - self.PAD) / max(1, w - 2 * self.PAD)
        self.set(self.lo + t * (self.hi - self.lo), notify=True)

    def press(self, e):
        self.dragging = True
        self.from_x(e.x)
        self.draw()

    def drag(self, e):
        self.from_x(e.x)

    def release(self, e):
        self.dragging = False
        self.draw()

    def wheel(self, e):
        self.set(self.value + (self.step if e.delta > 0 else -self.step), notify=True)

    def hover(self, on):
        self.hot = on
        self.draw()
