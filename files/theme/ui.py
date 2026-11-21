"""Общие элементы для панелей Garasu (tkinter): цвета темы, ползунок со свечением и плавные наведения.

Slider  - ползунок: дорожка-капсула, заливка цвета темы с мягким свечением, светлая ручка с ореолом.
          Ручка плавно доезжает до значения (клик по дорожке, колёсико, смена извне), растёт при наведении,
          чуть сжимается при нажатии и пускает световую волну. Кадры рисуются только пока что-то движется.
live(win) - включает плавную подсветку при наведении для всех кликабельных надписей и карточек окна
          (всё, у чего курсор-рука): кнопки светлеют, текстовые ссылки загораются цветом темы.
          Заодно запускает плавное появление окна (см. motion).
hidden(win, alpha) - сразу после создания окна: окно невидимо до появления, без мигания.
motion(win) - появление: окно проявляется и съезжает на 8 px вниз; закрытие: быстро гаснет.
          Выключается вместе с «Анимациями» в панели виджетов.
"""
import os, json, math, time
import tkinter as tk

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageTk
except Exception:                       # без Pillow - простой плоский ползунок
    Image = None

import fonts as _fonts                     # на Windows 10 шрифты Windows 11 подменяются
FONT, ICONS = _fonts.UI, _fonts.ICONS
ZDIR = os.path.join(os.path.expanduser("~"), ".glzr", "zebar", "ryoku")
FRAME_MS = 15


def mix(a, b, t):
    A = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    B = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(round(A[i] + (B[i] - A[i]) * t) for i in range(3))


def _rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def colors():
    """Цвета текущей темы: BG фон, FG текст, MUTED приглушённый, ACC акцент, TROUGH подложка."""
    c = {"pill": "#0c080a", "fg": "#f7e8ed", "muted": "#8d7e84", "accent": "#eeb7d0"}
    try:
        c.update(json.load(open(os.path.join(ZDIR, "theme.json"), encoding="utf-8")))
    except Exception:
        pass
    return {"BG": c["pill"], "FG": c["fg"], "MUTED": c["muted"], "ACC": c["accent"],
            "TROUGH": mix(c["pill"], "#ffffff", 0.14)}


_HALO, _LUTS = {}, {}


def _lut(k):
    """Таблица «яркость × k» для Image.point (кэш): не считаем 256 значений лямбдой каждый кадр."""
    q = max(0, int(round(k * 200)))
    t = _LUTS.get(q)
    if t is None:
        t = _LUTS[q] = [min(255, int(v * q / 200)) for v in range(256)]
    return t


def _halo(r):
    """Круглое пятно света радиусом r (маска L), мягко гаснет к краю. Кэшируется."""
    r = max(2, int(r))
    m = _HALO.get(r)
    if m is None:
        m = Image.radial_gradient("L").resize((2 * r, 2 * r))
        m = m.point(lambda v: int(255 * max(0.0, 1 - v / 255) ** 2))
        _HALO[r] = m
    return m


class Slider(tk.Canvas):
    """Ползунок. Тянется мышкой, крутится колёсиком. command(value) вызывается при каждом изменении."""
    PAD = 12
    S = 3                                   # рисуем в 3 раза крупнее и уменьшаем - края гладкие

    def __init__(self, parent, lo, hi, value, command=None, bg="#000000", track="#333333", accent="#ffffff",
                 knob="#ffffff", height=28, step=None):
        super().__init__(parent, height=height, bg=bg, highlightthickness=0, bd=0, cursor="hand2")
        self.lo, self.hi, self.value, self.command = lo, hi, value, command
        self.bg, self.track, self.accent, self.knob = bg, track, accent, knob
        self.step = step or max(1, round((hi - lo) / 40))
        self.hot = self.dragging = False
        self.pos, self.vel = float(value), 0.0      # где ручка нарисована сейчас (догоняет value)
        self.h = self.p = 0.0                         # наведение и нажатие, 0..1 (плавные)
        self.ripples = []
        self.job = None
        self.prev = 0.0
        self.photo = None
        self._cache = {}
        self.bind("<Configure>", self._resize)
        self.bind("<Button-1>", self.press)
        self.bind("<B1-Motion>", self.drag)
        self.bind("<ButtonRelease-1>", self.release)
        self.bind("<MouseWheel>", self.wheel)
        self.bind("<Enter>", lambda e: self.hover(True))
        self.bind("<Leave>", lambda e: self.hover(False))

    # ---------------------------------------------------------------- геометрия
    def _x(self, v):
        w = self.winfo_width()
        return self.PAD + (w - 2 * self.PAD) * (v - self.lo) / max(1, self.hi - self.lo)

    def _resize(self, e=None):
        self._cache.clear()
        self.photo = None
        self.draw()

    # ---------------------------------------------------------------- заготовки (кэш на размер окна)
    def _layers(self, w, h):
        c = self._cache.get("layers")
        if c:
            return c
        S, y, a, b = self.S, h / 2, self.PAD, w - self.PAD
        bg, tr, ac = _rgb(self.bg), _rgb(self.track), _rgb(self.accent)
        th = 5                                                    # толщина дорожки
        y0, y1 = (y - th / 2) * S, (y + th / 2) * S
        # дорожка: капсула цвета подложки с тонкой светлой кромкой
        base = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
        d = ImageDraw.Draw(base)
        d.rounded_rectangle(((a - th / 2) * S, y0, (b + th / 2) * S, y1), radius=th * S // 2,
                            fill=tr + (255,), outline=_rgb(mix(self.track, "#ffffff", .10)) + (255,), width=1)
        base = base.reduce(S)
        # заливка: градиент от приглушённого акцента к яркому, во всю длину (обрезается по ручке)
        grad = Image.new("RGB", (w, 1))
        px = grad.load()
        lo_c, hi_c = _rgb(mix(self.accent, self.bg, .30)), _rgb(mix(self.accent, "#ffffff", .12))
        for x in range(w):
            t = max(0.0, min(1.0, (x - a) / max(1, b - a)))
            px[x, 0] = tuple(round(lo_c[i] + (hi_c[i] - lo_c[i]) * t) for i in range(3))
        grad = grad.resize((w, h))
        fm = Image.new("L", (w * S, h * S), 0)
        ImageDraw.Draw(fm).rounded_rectangle(((a - th / 2) * S, y0, (b + th / 2) * S, y1), radius=th * S // 2, fill=255)
        fm = fm.reduce(S)
        fill = grad.convert("RGBA")
        fill.putalpha(fm)
        # свечение под заливкой: та же капсула, размытая
        gm = Image.new("L", (w, h), 0)
        ImageDraw.Draw(gm).rounded_rectangle((a - 3, y - 3.5, b + 3, y + 3.5), radius=4, fill=255)
        glow = gm.filter(ImageFilter.GaussianBlur(3.2))
        # маска краёв: всё гаснет по скруглённой форме и не доходит до края холста (никаких квадратов)
        fade = Image.new("L", (w, h), 0)
        ImageDraw.Draw(fade).rounded_rectangle((0, 1, w - 1, h - 2), radius=h // 2 - 1, fill=255)
        fade = fade.filter(ImageFilter.GaussianBlur(1.6))
        c = self._cache["layers"] = (base, fill, glow, fade, Image.new("RGB", (w, h), bg), ac)
        return c

    # ---------------------------------------------------------------- рисование
    def draw(self):
        w, h = self.winfo_width(), self.winfo_height()
        if w < 30:
            return
        if Image is None:
            return self._draw_plain(w, h)
        base, fill, glow, fade, bgimg, ac = self._layers(w, h)
        x, y = self._x(self.pos), h / 2
        xi = max(0, min(w, int(round(x))))
        out = bgimg.copy().convert("RGBA")
        # 1) свечение под заливкой и ореол вокруг ручки
        k = .30 + .25 * self.h + .20 * self.p
        if xi > 0:
            gl = Image.new("L", (w, h), 0)
            gl.paste(glow.crop((0, 0, xi, h)), (0, 0))
            out.alpha_composite(self._tint(ac, gl, k))
        r_halo = 11 + 3 * self.h + 2 * self.p
        hm = _halo(r_halo)
        lay = Image.new("L", (w, h), 0)
        lay.paste(hm, (int(x - hm.width / 2), int(y - hm.height / 2)))
        out.alpha_composite(self._tint(ac, lay, .22 + .38 * self.h + .30 * self.p))
        # 2) дорожка и заливка
        out.alpha_composite(base)
        if xi > 0:
            out.alpha_composite(fill.crop((0, 0, xi, h)), (0, 0))
        # 3) волна света при нажатии
        if self.ripples:
            now = time.perf_counter()
            rl = Image.new("L", (w * 2, h * 2), 0)
            d = ImageDraw.Draw(rl)
            for r0, rx in self.ripples:
                u = (now - r0) / .6
                rr = (8 + 14 * (1 - (1 - u) ** 3)) * 2
                d.ellipse((rx * 2 - rr, y * 2 - rr, rx * 2 + rr, y * 2 + rr), outline=int(190 * (1 - u) ** 2), width=3)
            rl = rl.reduce(2).filter(ImageFilter.GaussianBlur(.7))
            out.alpha_composite(self._tint(ac, rl))
        # 4) ручка: светлый круг с кольцом цвета темы, растёт при наведении, сжимается при нажатии
        S = self.S
        r = (7 + 1.4 * self.h) * (1 - .12 * self.p)
        kb = Image.new("RGBA", (int(2 * r + 6) * S, int(2 * r + 6) * S), (0, 0, 0, 0))
        c0 = kb.width / 2
        dk = ImageDraw.Draw(kb)
        dk.ellipse((c0 - r * S, c0 - r * S, c0 + r * S, c0 + r * S), fill=ac + (255,))
        ri = r - 2
        kn = _rgb(mix(self.knob, "#ffffff", .25 * self.h))
        dk.ellipse((c0 - ri * S, c0 - ri * S, c0 + ri * S, c0 + ri * S), fill=kn + (255,))
        kb = kb.reduce(S)
        out.alpha_composite(kb, (int(round(x - kb.width / 2)), int(round(y - kb.height / 2))))
        img = Image.composite(out.convert("RGB"), bgimg, fade)
        if self.photo is None or self.photo.width() != w or self.photo.height() != h:
            self.photo = ImageTk.PhotoImage(img)
            self.delete("all")
            self.create_image(0, 0, anchor="nw", image=self.photo)
        else:
            self.photo.paste(img)

    @staticmethod
    def _tint(color, mask, k=1.0):
        lay = Image.new("RGBA", mask.size, color + (0,))
        lay.putalpha(mask if k >= .999 else mask.point(_lut(min(1.0, k))))
        return lay

    def _draw_plain(self, w, h):
        self.delete("all")
        y, a, b = h // 2, self.PAD, w - self.PAD
        x = self._x(self.pos)
        self.create_line(a, y, b, y, fill=self.track, width=5, capstyle="round")
        if x > a + 1:
            self.create_line(a, y, x, y, fill=self.accent, width=5, capstyle="round")
        r = 7 + self.h
        self.create_oval(x - r, y - r, x + r, y + r, fill=self.knob, outline=self.accent, width=2)

    # ---------------------------------------------------------------- анимация
    def _kick(self):
        if self.job is None and self.winfo_exists():
            self.prev = time.perf_counter()
            self.job = self.after(FRAME_MS, self._tick)

    def _tick(self):
        self.job = None
        now = time.perf_counter()
        dt = min(.05, now - self.prev)
        self.prev = now
        span = max(1, self.hi - self.lo)
        if self.dragging:                                   # при перетаскивании ручка почти прилипает к мыши
            self.pos += (self.value - self.pos) * min(1.0, dt * 38)
            self.vel = 0.0
        else:                                               # иначе мягко доезжает, без перелёта
            kk = 210.0
            self.vel += (kk * (self.value - self.pos) - 2 * math.sqrt(kk) * self.vel) * dt
            self.pos += self.vel * dt
        self.h += ((1.0 if (self.hot or self.dragging) else 0.0) - self.h) * min(1.0, dt * 14)
        self.p += ((1.0 if self.dragging else 0.0) - self.p) * min(1.0, dt * 18)
        self.ripples = [r for r in self.ripples if now - r[0] < .6]
        moving = abs(self.value - self.pos) > span * .0015 or abs(self.vel) > span * .002
        busy = moving or self.ripples or abs(self.h - (1.0 if (self.hot or self.dragging) else 0.0)) > .01 \
            or abs(self.p - (1.0 if self.dragging else 0.0)) > .01
        if not moving:
            self.pos, self.vel = float(self.value), 0.0
        self.draw()
        if busy:
            self.job = self.after(FRAME_MS, self._tick)

    # ---------------------------------------------------------------- управление
    def set(self, value, notify=False):
        value = max(self.lo, min(self.hi, int(round(value))))
        if value != self.value:
            self.value = value
            self._kick()
            if notify and self.command:
                self.command(value)

    def from_x(self, x):
        w = self.winfo_width()
        t = (x - self.PAD) / max(1, w - 2 * self.PAD)
        self.set(self.lo + t * (self.hi - self.lo), notify=True)

    def press(self, e):
        self.dragging = True
        self.from_x(e.x)
        self.ripples.append((time.perf_counter(), max(self.PAD, min(self.winfo_width() - self.PAD, e.x))))
        self._kick()

    def drag(self, e):
        self.from_x(e.x)

    def release(self, e):
        self.dragging = False
        self._kick()

    def wheel(self, e):
        self.set(self.value + (self.step if e.delta > 0 else -self.step), notify=True)

    def hover(self, on):
        self.hot = on
        self._kick()


# -------------------------------------------------------------------- плавная подсветка при наведении
def _lum(c):
    r, g, b = _rgb(c)
    return .299 * r + .587 * g + .114 * b


def live(win, accent=None):
    """Плавная подсветка всего кликабельного (курсор-рука) в окне win. Вызывать один раз после создания окна:
    работает и для виджетов, созданных позже. Если программа сама перекрасит виджет, подсветка ей не мешает."""
    state = {}                                   # виджет -> (job, {член: (исходные цвета, последние наши)})
    motion(win)

    def root_of(w):
        """Самый внешний кликабельный предок того же цвета: карточка целиком, а не надпись в ней."""
        if isinstance(w, (tk.Canvas, tk.Tk, tk.Toplevel)):
            return None
        bg, found, cur = w.cget("bg"), None, w
        while cur is not None and not isinstance(cur, (tk.Tk, tk.Toplevel)):
            try:
                if cur.cget("bg") != bg:
                    break
                if str(cur.cget("cursor")) == "hand2":
                    found = cur
            except tk.TclError:
                break
            cur = cur.master
        return found

    def members(r):
        out, bg = [r], r.cget("bg")

        def walk(w):
            for c in w.winfo_children():
                if isinstance(c, tk.Canvas):
                    continue
                try:
                    if c.cget("bg") == bg:
                        out.append(c)
                        walk(c)
                except tk.TclError:
                    pass
        walk(r)
        return out

    def targets(w, acc, base_bg):
        bg = w.cget("bg")
        fg = w.cget("fg") if "fg" in w.keys() else None
        if bg == base_bg:                     # надпись-ссылка на фоне окна: загорается текст, фон не трогаем
            return bg, (mix(fg, acc, .75) if fg else None)
        hot_bg = mix(bg, "#ffffff", .16) if _lum(bg) > 110 else mix(bg, acc, .18)
        return hot_bg, fg

    def run(r, on):
        st = state.get(r)
        if st is None:
            ms = members(r)
            st = state[r] = {"job": None, "m": {}, "t": 0.0}
            acc, base_bg = accent or colors()["ACC"], win.cget("bg")   # тема могла смениться на лету
            ok = lambda c: c is None or (isinstance(c, str) and len(c) == 7 and c[0] == "#")
            for m in ms:
                fg = m.cget("fg") if "fg" in m.keys() else None
                if not (ok(m.cget("bg")) and ok(fg)):       # системные цвета по имени не трогаем
                    continue
                st["m"][m] = {"from": (m.cget("bg"), fg), "to": targets(m, acc, base_bg), "last": (m.cget("bg"), fg)}
        st["dir"] = 1 if on else -1
        if st["job"] is None:
            step(r)

    def step(r):
        st = state.get(r)
        if st is None:
            return
        st["job"] = None
        dur = .14 if st["dir"] > 0 else .24
        st["t"] = max(0.0, min(1.0, st["t"] + st["dir"] * FRAME_MS / 1000 / dur))
        u = st["t"]
        e = 1 - (1 - u) ** 3 if st["dir"] > 0 else u * u * (3 - 2 * u)
        try:
            for m, d in list(st["m"].items()):
                cur = (m.cget("bg"), m.cget("fg") if "fg" in m.keys() else None)
                if cur != d["last"]:          # программа сама перекрасила - больше не вмешиваемся
                    del state[r]
                    return
                bg = mix(d["from"][0], d["to"][0], e)
                fg = mix(d["from"][1], d["to"][1], e) if d["from"][1] and d["to"][1] else d["from"][1]
                m.configure(bg=bg) if fg is None else m.configure(bg=bg, fg=fg)
                d["last"] = (bg, fg)
        except tk.TclError:
            state.pop(r, None)
            return
        if (st["dir"] > 0 and u < 1) or (st["dir"] < 0 and u > 0):
            st["job"] = win.after(FRAME_MS, lambda: step(r))
        elif st["dir"] < 0:
            state.pop(r, None)                # вернулись к исходным цветам - забываем

    def enter(e):
        try:
            r = root_of(e.widget)
        except (tk.TclError, AttributeError):
            return
        if r is not None:
            run(r, True)

    def leave(e):
        try:
            r = root_of(e.widget)
        except (tk.TclError, AttributeError):
            return
        if r is None:
            return
        def check():
            try:
                x, y = win.winfo_pointerxy()
                under = win.winfo_containing(x, y)
            except (tk.TclError, KeyError):
                under = None
            w = under
            while w is not None:              # мышь всё ещё внутри карточки (перешла на её надпись)
                if w is r:
                    return
                w = getattr(w, "master", None)
            run(r, False)
        win.after(1, check)

    win.bind_all("<Enter>", enter, add="+")
    win.bind_all("<Leave>", leave, add="+")


# ---------- появление и закрытие окна
def _anim_on():
    """Общий переключатель «Анимации» из панели виджетов (по умолчанию включено)."""
    try:
        return bool(json.load(open(os.path.join(ZDIR, "widgets.json"), encoding="utf-8"))["all"].get("anim", True))
    except Exception:
        return True


def hidden(win, alpha):
    """Запомнить нужную прозрачность и спрятать окно до появления (иначе оно мелькнёт готовым)."""
    win._ui_alpha = alpha
    win.attributes("-alpha", 0.0 if _anim_on() else alpha)


def motion(win, dy=8, open_ms=190, close_ms=120):
    """Окно проявляется и мягко съезжает вниз на dy px (как будто выпадает из верхней панели), при закрытии гаснет.
    Кадры идут только эти доли секунды. Если программа сама сдвинет окно во время появления, сдвиг уступает ей."""
    if getattr(win, "_ui_motion", False):
        return
    win._ui_motion = True
    target = getattr(win, "_ui_alpha", None)
    if not _anim_on():
        if target is not None:
            win.attributes("-alpha", target)
        return
    if target is None:                                    # окно без hidden(): прозрачность как есть
        target = float(win.attributes("-alpha"))
    real_destroy = win.destroy
    st = {"closing": False}

    def pos():
        g = win.geometry()                                # "ШxВ+X+Y"
        x, y = g.split("+", 1)[1].split("+") if g.count("+") == 2 else ("0", "0")
        return int(x), int(y)

    def appear():
        try:
            x, y = pos()
        except (tk.TclError, ValueError):
            return
        t0, last = time.perf_counter(), [None]

        def step():
            if st["closing"]:
                return
            try:
                u = min(1.0, (time.perf_counter() - t0) * 1000 / open_ms)
                e = 1 - (1 - u) ** 3                      # быстро в начале, мягко в конце
                win.attributes("-alpha", target * e)
                if last[0] is None or pos() == last[0]:   # никто, кроме нас, окно не двигал
                    ny = round(y - dy * (1 - e))
                    win.geometry("+%d+%d" % (x, ny))
                    last[0] = (x, ny)
                if u < 1:
                    win.after(8, step)
                else:
                    _timer(False)
            except tk.TclError:
                _timer(False)
        _timer(True)
        step()

    def destroy():
        if st["closing"]:
            return
        st["closing"] = True
        try:
            a0 = float(win.attributes("-alpha"))
        except tk.TclError:
            return
        t0 = time.perf_counter()
        _timer(True)

        def step():
            try:
                u = min(1.0, (time.perf_counter() - t0) * 1000 / close_ms)
                win.attributes("-alpha", a0 * (1 - u) ** 2)
                if u < 1:
                    win.after(8, step)
                else:
                    _timer(False)
                    real_destroy()
            except tk.TclError:
                _timer(False)
        step()

    win.destroy = destroy
    win.after_idle(appear)


_fast = [0]


def _timer(on):
    """Точный таймер Windows (1 мс) только пока идёт анимация, иначе кадры не чаще раза в 15,6 мс."""
    try:
        import ctypes
        if on:
            _fast[0] += 1
            if _fast[0] == 1:
                ctypes.windll.winmm.timeBeginPeriod(1)
        elif _fast[0] > 0:
            _fast[0] -= 1
            if _fast[0] == 0:
                ctypes.windll.winmm.timeEndPeriod(1)
    except Exception:
        pass
