"""Стеклянные переключатели для панелей Garasu (tkinter + Pillow).

Toggle  - вкл/выкл: вдавленная дорожка, стеклянный ползунок с пиксельной иконкой из точек,
          неоновая дуга, которая обегает ползунок, волна света при щелчке, пружина с лёгким перелётом.
Segment - выбор из нескольких вариантов (подписи), стеклянная «капсула» переезжает к выбранному.

Каждый кадр рисуется в Pillow в 3 раза крупнее и уменьшается - так края гладкие.
Анимация крутится только пока ползунок едет, на него навели мышь или идёт волна; в покое CPU не тратится.
Если Pillow нет, рисуется простая плоская версия теми же цветами.
"""
import math, time, ctypes
import tkinter as tk
import tkinter.font as tkfont
import fonts

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageTk, ImageChops
except Exception:                       # без Pillow - упрощённый вид
    Image = None

try:
    ctypes.windll.winmm.timeBeginPeriod(1)      # таймер Windows точнее 1 мс: кадры идут ровно
except Exception:
    pass

SS = 3                                   # во сколько раз крупнее рисуем перед уменьшением
FPS_MS = 16


def rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def hexc(c):
    return "#%02x%02x%02x" % tuple(int(v) for v in c)


def lerp(a, b, t):
    return a + (b - a) * t


def mixc(a, b, t):
    return tuple(int(round(lerp(a[i], b[i], t))) for i in range(3))


def neon(c, sat=.62):
    """Тот же оттенок, но сочнее и ярче - чтобы неон светился даже у бледной темы."""
    import colorsys
    h, s, v = colorsys.rgb_to_hsv(*[x / 255 for x in c])
    if s < .08:
        return mixc(c, WHITE, .35)
    return tuple(int(x * 255) for x in colorsys.hsv_to_rgb(h, max(s, sat), 1.0))


def ease(u):
    return 1 - (1 - u) ** 3


BLACK, WHITE = (0, 0, 0), (255, 255, 255)

# иконки из точек 5x5 для ползунка вкл/выкл
DOT_OFF = [".###.", "#...#", "#...#", "#...#", ".###."]
DOT_ON = [".....", "....#", "...#.", "#.#..", ".#..."]


def _grid(rows):
    n = len(rows)
    c = (n - 1) / 2
    return [(i - c, j - c) for j, r in enumerate(rows) for i, ch in enumerate(r) if ch == "#"]


def sq_point(cx, cy, a, b, deg, n=None):
    """Точка на контуре «таблетки» (полностью скруглённый прямоугольник, как кнопки Garasu):
    луч из центра под углом deg (против часовой, 0 = вправо). a, b - полуширина и полувысота."""
    th = math.radians(deg)
    dx, dy = math.cos(th), -math.sin(th)
    r = min(a, b)
    hx, hy = a - r, b - r                                   # прямые участки
    if abs(dy) > 1e-9:
        t = b / abs(dy)
        if abs(t * dx) <= hx:
            return cx + t * dx, cy + t * dy
    if abs(dx) > 1e-9 and hy > 0:
        t = a / abs(dx)
        if abs(t * dy) <= hy:
            return cx + t * dx, cy + t * dy
    ox, oy = math.copysign(hx, dx), math.copysign(hy, dy)   # центр нужного скругления
    p = dx * ox + dy * oy
    t = p + math.sqrt(max(0.0, p * p - (ox * ox + oy * oy) + r * r))
    return cx + t * dx, cy + t * dy


def sq_poly(cx, cy, a, b, n=4.2, steps=72):
    return [sq_point(cx, cy, a, b, 360 * i / steps, n) for i in range(steps)]


# ------------------------------------------------------------------ заготовки Pillow
_LUTS = {}


def lut(k):
    """Таблица «яркость × k» для Image.point, кэшируется: быстрее, чем считать лямбдой 256 значений каждый кадр."""
    q = max(0, int(round(k * 200)))
    t = _LUTS.get(q)
    if t is None:
        t = _LUTS[q] = [min(255, int(v * q / 200)) for v in range(256)]
    return t


def _tint(color, mask, k=1.0):
    lay = Image.new("RGBA", mask.size, tuple(color) + (0,))
    lay.putalpha(mask if abs(k - 1) < .001 else mask.point(lut(k)))
    return lay


def _vgrad(size, box, c0, c1):
    """Вертикальный градиент в пределах box по высоте, на всё изображение size."""
    W, H = size
    y0, y1 = box[1], box[3]
    col = Image.new("RGB", (1, H))
    px = col.load()
    for y in range(H):
        px[0, y] = mixc(c0, c1, max(0.0, min(1.0, (y - y0) / max(1, y1 - y0))))
    return col.resize((W, H)).convert("RGBA")


_SPRITES = {}


def _sprite(r):
    """Круглое пятно света радиусом r (маска L), мягко гаснет к краю."""
    r = max(2, int(r))
    m = _SPRITES.get(r)
    if m is None:
        m = Image.radial_gradient("L").resize((2 * r, 2 * r))       # 0 в центре, 255 по краю
        m = m.point(lambda v: int(255 * max(0.0, 1 - v / 255) ** 2))
        _SPRITES[r] = m
    return m


def _put_light(img, color, cx, cy, r, k, clip=None):
    """Положить пятно света цвета color с силой k (0..1) в точку, опционально обрезав маской clip."""
    if k <= 0.01:
        return
    m = _sprite(r)
    x, y = int(cx - m.width / 2), int(cy - m.height / 2)
    x0, y0 = max(0, x), max(0, y)                       # работаем только с квадратиком пятна, а не со всей картинкой
    x1, y1 = min(img.width, x + m.width), min(img.height, y + m.height)
    if x1 <= x0 or y1 <= y0:
        return
    lay = m.crop((x0 - x, y0 - y, x1 - x, y1 - y))
    if clip is not None:
        lay = ImageChops.multiply(lay, clip.crop((x0, y0, x1, y1)))
    img.alpha_composite(_tint(color, lay, k), (x0, y0))


class _Glass(tk.Canvas):
    """Общая часть: дорожка, ползунок, дуга, пружина, мышь и клавиши."""
    M, PAD = 7, 3

    def __init__(self, parent, n, idx, tw, th, thumb_w, step, bg, command=None):
        self.n, self.idx, self.px, self.vel = n, idx, float(idx), 0.0
        self.tw, self.th, self.step = tw, th, step
        self.a, self.b = thumb_w / 2, th / 2 - self.PAD
        self.bgc = rgb(bg)
        self.command = command
        self.W, self.H = tw + 2 * self.M, th + 2 * self.M
        super().__init__(parent, width=self.W, height=self.H, bg=bg, highlightthickness=0, bd=0,
                         cursor="hand2", takefocus=1)
        self.hover = self.press = 0.0
        self.over = self.pressed = self.dragging = False
        self.mouse = None
        self.ripples = []
        self.arc = self._rest_deg(idx)
        self.arc_anim = None
        self.job = None
        self.prev = time.perf_counter()
        self._cache = {}
        if Image is not None:
            self.photo = ImageTk.PhotoImage("RGB", (self.W, self.H))
            self.item = self.create_image(0, 0, anchor="nw", image=self.photo)
        self.bind("<ButtonPress-1>", self._down)
        self.bind("<B1-Motion>", self._move)
        self.bind("<ButtonRelease-1>", self._up)
        self.bind("<Enter>", lambda e: self._hover(True))
        self.bind("<Leave>", lambda e: self._hover(False))
        self.bind("<Motion>", lambda e: setattr(self, "mouse", (e.x, e.y)))
        self.bind("<space>", lambda e: self.select((self.idx + 1) % self.n))
        self.bind("<Return>", lambda e: self.select((self.idx + 1) % self.n))
        self.bind("<Left>", lambda e: self.select(self.idx - 1))
        self.bind("<Right>", lambda e: self.select(self.idx + 1))
        self.after_idle(self.draw)

    # --- что меняется у наследников
    def _rest_deg(self, i):
        return 90

    def _arc_to(self, old, new):
        d = 1 if new < old else -1                       # полный оборот по ходу движения
        return self.arc - 360 * d

    def _t_track(self):
        return 0.0

    def _t_thumb(self):
        return 1.0

    def _color(self):
        return (255, 255, 255)

    def _icons(self, img, cx, cy, sx, sy):
        pass

    def _labels(self):
        pass

    def recolor(self, bg=None, fg=None, accent=None, muted=None):
        """Сменить цвета на лету (например, после смены темы)."""
        if bg:
            self.bgc = rgb(bg)
            self.configure(bg=bg)
        if fg:
            self.fgc = rgb(fg)
        if accent:
            self.acc = rgb(accent)
        if muted:
            self.mut = rgb(muted)
        self._cache.clear()
        self.draw()

    # --- состояние
    def select(self, i, notify=True, animate=True):
        i = max(0, min(self.n - 1, i))
        if i != self.idx:
            old, self.idx = self.idx, i
            if animate:
                self.arc_anim = (self.arc, self._arc_to(old, i), time.perf_counter())
                self.ripples.append(time.perf_counter())
            if notify and self.command:
                self.command(i)
        if not animate:
            self.px, self.vel, self.arc, self.arc_anim = float(i), 0.0, self._rest_deg(i), None
            self.draw()
        self._run()

    def _hover(self, on):
        self.over = on
        if not on:
            self.mouse = None
        self._run()

    def _slot_at(self, x):
        return round((x - self.M - self.PAD - self.a) / max(1, self.step))

    def _down(self, e):
        self.focus_set()
        self.pressed, self.dragging = True, False
        self.d0, self.p0 = e.x, self.px
        self._run()

    def _move(self, e):
        self.mouse = (e.x, e.y)
        if not self.pressed:
            return
        dx = e.x - self.d0
        if abs(dx) > 4:
            self.dragging = True
        if self.dragging:
            nx = max(-.08, min(self.n - 1 + .08, self.p0 + dx / max(1, self.step)))
            self.vel, self.px = (nx - self.px) * 60, nx
            self._run()

    def _up(self, e):
        if not self.pressed:
            return
        self.pressed = False
        if self.dragging:
            new = round(self.px)
        elif self.n == 2:
            new = 1 - self.idx
        else:
            new = self._slot_at(e.x)
        self.dragging = False
        if new == self.idx:
            self.ripples.append(time.perf_counter())
        self.select(new)

    # --- анимация
    def _run(self):
        if self.job is None:
            self.prev = time.perf_counter()
            self.job = self.after(1, self._tick)

    def _tick(self):
        self.job = None
        if not self.winfo_exists():
            return
        now = time.perf_counter()
        dt = min(.05, now - self.prev)
        self.prev = now
        if not self.dragging:                                  # пружина с лёгким перелётом
            k = 190.0
            c = 2 * math.sqrt(k) * .58
            steps = int(dt / .004) + 1
            h = dt / steps
            for _ in range(steps):
                self.vel += (k * (self.idx - self.px) - c * self.vel) * h
                self.px += self.vel * h
        self.hover += ((1.0 if self.over else 0.0) - self.hover) * min(1, dt * 10)
        self.press += ((1.0 if self.pressed else 0.0) - self.press) * min(1, dt * 18)
        if self.arc_anim:
            a0, a1, st = self.arc_anim
            u = min(1.0, (now - st) / (.7 if abs(a1 - a0) < 300 else .95))
            self.arc = lerp(a0, a1, ease(u))
            if u >= 1:
                self.arc, self.arc_anim = ((a1 + 180) % 360) - 180, None
        self.ripples = [r for r in self.ripples if now - r < .9]
        self.draw()
        moving = (self.dragging or abs(self.idx - self.px) > .0015 or abs(self.vel) > .003 or self.arc_anim
                  or self.ripples or abs(self.hover - (1.0 if self.over else 0.0)) > .01
                  or abs(self.press - (1.0 if self.pressed else 0.0)) > .01 or self.over)
        if moving:
            nxt = FPS_MS - (time.perf_counter() - now) * 1000
            self.job = self.after(max(1, int(nxt)), self._tick)
        elif abs(self.px - self.idx) > 0:
            self.px, self.vel = float(self.idx), 0.0
            self.draw()

    # --- рисование
    def _track_box(self, S=1):
        M = self.M
        return (M * S, M * S, (M + self.tw) * S, (M + self.th) * S)

    def _track_layer(self, t):
        key = ("track", round(t))
        if key in self._cache:
            return self._cache[key]
        S = SS
        size = (self.W * S, self.H * S)
        x0, y0, x1, y1 = self._track_box(S)
        r = self.th / 2 * S
        bg = self.bgc
        mask = Image.new("L", size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((x0, y0, x1, y1), r, fill=255)
        img = Image.new("RGBA", size, (0, 0, 0, 0))
        sh = Image.new("L", size, 0)                              # мягкая тень, как у карточек
        ImageDraw.Draw(sh).rounded_rectangle((x0, y0 + 2 * S, x1, y1 + 2 * S), r, fill=60)
        img.alpha_composite(_tint(BLACK, sh.filter(ImageFilter.GaussianBlur(3 * S))))
        c0 = mixc(bg, WHITE, .14) if t < .5 else self._track_on()   # выкл: TROUGH, вкл: акцент темы
        body = Image.new("RGBA", size, c0 + (255,))
        body.putalpha(mask)
        img.alpha_composite(body)
        top = _vgrad(size, (x0, y0, x1, y0 + (y1 - y0) * .55), (255, 255, 255), (0, 0, 0)).getchannel("R")
        img.alpha_composite(_tint(WHITE, ImageChops.multiply(top, mask), .08 if t < .5 else .14))  # свет сверху
        edge = Image.new("L", size, 0)                            # тонкая светлая кромка
        ImageDraw.Draw(edge).rounded_rectangle((x0, y0, x1, y1), r, outline=255, width=max(1, int(S * .9)))
        img.alpha_composite(_tint(WHITE, edge, .11 if t < .5 else .22))
        self._cache[key] = img
        self._cache[("tmask",)] = mask
        return img

    def _track_on(self):
        return self.acc

    def _thumb_fill(self, t):
        return self.fgc

    def _thumb_layer(self, t):
        key = ("thumb", round(t))
        if key in self._cache:
            return self._cache[key]
        S, g = SS, 6
        a, b = self.a * S, self.b * S
        W, H = int(2 * a + 2 * g * S), int(2 * b + 2 * g * S)
        cx, cy = W / 2, H / 2
        poly = sq_poly(cx, cy, a, b)
        mask = Image.new("L", (W, H), 0)
        ImageDraw.Draw(mask).polygon(poly, fill=255)
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sh = Image.new("L", (W, H), 0)                              # мягкая тень под ручкой
        ImageDraw.Draw(sh).polygon(sq_poly(cx, cy + 1.6 * S, a, b), fill=120)
        img.alpha_composite(_tint(BLACK, sh.filter(ImageFilter.GaussianBlur(2 * S))))
        c = self._thumb_fill(t)
        body = Image.new("RGBA", (W, H), c + (255,))
        body.putalpha(mask)
        img.alpha_composite(body)
        sheen = _vgrad((W, H), (0, cy - b, 0, cy + b * .2), (255, 255, 255), (0, 0, 0)).getchannel("R")
        img.alpha_composite(_tint(WHITE, ImageChops.multiply(sheen, mask), .18))    # свет сверху
        rim = Image.new("L", (W, H), 0)
        ImageDraw.Draw(rim).polygon(sq_poly(cx, cy, a - .4 * S, b - .4 * S), outline=255, width=int(S * .9))
        img.alpha_composite(_tint(WHITE, rim, .28))
        self._cache[key] = (img, mask)
        return img, mask

    def draw(self):
        if Image is None:
            return self._draw_plain()
        S = SS
        t, tt, col = self._t_track(), self._t_thumb(), self._color()
        h = self.hover
        I = .9 + .35 * h
        st = 0 if self.dragging else min(.14, abs(self.vel) * .045)       # растяжка на скорости
        sx, sy = 1 + st - .04 * self.press, 1 - st * .5 - .07 * self.press
        vpx = max(-.05, min(self.n - 1 + .05, self.px))                  # перелёт не вылезает за дорожку
        cx = (self.M + self.PAD + self.a + self.step * vpx) * S
        cy = (self.M + self.th / 2 - .6 * h) * S
        a, b = self.a * S * sx, self.b * S * sy
        span = 160 * (1 - .45 * math.sin(math.pi * self._arc_u()))
        ra, rb = a + 2.2 * S, b + 2.2 * S
        ax, ay = sq_point(cx, cy, ra, rb, self.arc)

        size = (self.W * S, self.H * S)
        img = Image.new("RGBA", size, self.bgc + (255,))
        _put_light(img, col, cx, cy, (self.b + 13) * S, .18 * I)          # мягкое свечение вокруг
        L0, L1 = self._track_layer(0), self._track_layer(1)
        tr = L0 if t <= .001 else L1 if t >= .999 else Image.blend(L0, L1, t)
        img.alpha_composite(tr)
        tmask = self._cache[("tmask",)]
        _put_light(img, col, ax, ay, 26 * S, .22 * I, tmask)               # неон подсвечивает дорожку
        if self.ripples:                                                     # волна света при щелчке
            rl = Image.new("L", size, 0)
            d = ImageDraw.Draw(rl)
            for r0 in self.ripples:
                k = (time.perf_counter() - r0) / .9
                rr = (self.a + 2 + min(self.tw * .6, 34) * (1 - (1 - k) ** 3)) * S
                d.ellipse((cx - rr, cy - rr * .62, cx + rr, cy + rr * .62), outline=int(200 * (1 - k) ** 2),
                          width=int(1.6 * S))
            rl = ImageChops.multiply(rl.filter(ImageFilter.GaussianBlur(.8 * S)), tmask)
            img.alpha_composite(_tint(col, rl))

        T0, M0 = self._thumb_layer(0)
        T1, _ = self._thumb_layer(1)
        th = T0 if tt <= .001 else T1 if tt >= .999 else Image.blend(T0, T1, tt)
        m = M0
        if abs(sx - 1) > .004 or abs(sy - 1) > .004:
            nw, nh = int(th.width * sx), int(th.height * sy)
            th, m = th.resize((nw, nh), Image.BILINEAR), m.resize((nw, nh), Image.BILINEAR)
        th = th.copy()
        ix, iy = sq_point(th.width / 2, th.height / 2, a, b, self.arc)       # свет неона внутри стекла
        _put_light(th, col, ix, iy, self.b * 1.7 * S, .20 * I, m)
        if self.mouse is not None and h > .02:                               # блик за курсором
            mx = self.mouse[0] * S - (cx - th.width / 2)
            my = self.mouse[1] * S - (cy - th.height / 2)
            _put_light(th, WHITE, mx, my, 14 * S, .22 * h, m)
        img.alpha_composite(th, (int(cx - th.width / 2), int(cy - th.height / 2)))
        self._icons(img, cx, cy, sx, sy)

        # неоновая дуга: точки по контуру ползунка, яркая середина и гаснущие концы
        arc = Image.new("RGBA", size, (0, 0, 0, 0))
        core = Image.new("L", size, 0)
        da, dc = ImageDraw.Draw(arc), ImageDraw.Draw(core)
        nseg = 36
        pts = [sq_point(cx, cy, ra, rb, self.arc - span / 2 + span * i / nseg) for i in range(nseg + 1)]
        for i in range(nseg):
            pr = math.sin(math.pi * (i + .5) / nseg) ** .7
            da.line((pts[i], pts[i + 1]), fill=col + (int(255 * pr * min(1, I)),), width=int(1.5 * S))
            dc.line((pts[i], pts[i + 1]), fill=int(255 * pr ** 1.8), width=int(.8 * S))
        small = img.convert("RGB").reduce(S).convert("RGBA")
        arc1 = arc.reduce(S)
        for rad, k in ((4, 1.2), (1.6, 1.0)):
            gl = arc1.filter(ImageFilter.GaussianBlur(rad))
            gl.putalpha(gl.getchannel("A").point(lut(k)))
            small.alpha_composite(gl)
        small.alpha_composite(arc1)
        cw = lerp(.5, .35, t)
        small.alpha_composite(_tint(WHITE, core.reduce(S), cw * min(1, I)))
        # свет гаснет по форме капсулы и не доходит до края холста — без квадратной рамки
        out = Image.composite(small.convert("RGB"), Image.new("RGB", small.size, self.bgc), self._fade())
        self.photo.paste(out)
        self._labels()

    def _fade(self):
        """Маска: капсула дорожки, расширенная на пару пикселей и мягко размытая; к краю холста — ноль."""
        m = self._cache.get(("fade",))
        if m is None:
            S, g = SS, max(2, self.M - 4)
            m = Image.new("L", (self.W * S, self.H * S), 0)
            x0, y0 = (self.M - g) * S, (self.M - g) * S
            x1, y1 = (self.W - self.M + g) * S, (self.H - self.M + g) * S
            ImageDraw.Draw(m).rounded_rectangle((x0, y0, x1, y1), radius=(y1 - y0) // 2, fill=255)
            m = m.reduce(S).filter(ImageFilter.GaussianBlur(g / 2.2))
            self._cache[("fade",)] = m
        return m

    def _arc_u(self):
        if not self.arc_anim:
            return 0.0
        return min(1.0, (time.perf_counter() - self.arc_anim[2]) / (.7 if abs(self.arc_anim[1] - self.arc_anim[0]) < 300 else .95))

    def _draw_plain(self):
        self.delete("shape")
        x0, y0, x1, y1 = self._track_box()
        r = self.th / 2
        tc = mixc(self.bgc, BLACK, .45) if self._t_track() < .5 else mixc(self.bgc, self._color(), .45)
        self.create_oval(x0, y0, x0 + 2 * r, y1, fill=hexc(tc), outline="", tags="shape")
        self.create_oval(x1 - 2 * r, y0, x1, y1, fill=hexc(tc), outline="", tags="shape")
        self.create_rectangle(x0 + r, y0, x1 - r, y1, fill=hexc(tc), outline="", tags="shape")
        cx = self.M + self.PAD + self.a + self.step * self.px
        cy = self.M + self.th / 2
        self.create_rectangle(cx - self.a, cy - self.b, cx + self.a, cy + self.b, fill=hexc(mixc(self.fgc, WHITE, .4)),
                              outline=hexc(self._color()), width=2, tags="shape")
        self.tag_lower("shape")
        self._labels()


class Toggle(_Glass):
    """Вкл/выкл. command(bool) вызывается при переключении."""

    def __init__(self, parent, on, command=None, bg="#0c080a", fg="#f7e8ed", accent="#eeb7d0", muted="#8d7e84",
                 scale=1.0):
        self.fgc, self.acc, self.mut = rgb(fg), rgb(accent), rgb(muted)
        th = round(22 * scale)
        thumb = th - 2 * self.PAD
        tw = round(th * 1.95)
        cb = (lambda i: command(bool(i))) if command else None
        super().__init__(parent, 2, 1 if on else 0, tw, th, thumb, tw - 2 * self.PAD - thumb, bg, cb)

    @property
    def on(self):
        return bool(self.idx)

    def set(self, on, animate=False, notify=False):
        self.select(1 if on else 0, notify=notify, animate=animate)

    def _rest_deg(self, i):
        return 125 if i == 0 else -55

    def _arc_to(self, old, new):
        tgt = self._rest_deg(new)                       # всегда по часовой, как колесо, что катится
        a = self.arc
        while tgt > a - 60:
            tgt -= 360
        return tgt

    def _t_track(self):
        return max(0.0, min(1.0, self.px))

    _t_thumb = _t_track

    def _color(self):                       # дуга: приглушённая когда выкл, светлый акцент когда вкл
        return mixc(mixc(self.mut, self.fgc, .45), mixc(self.acc, WHITE, .5), max(0.0, min(1.0, self.px)))

    def _thumb_fill(self, t):               # ручка: приглушённая / светлая, как у ползунков панелей
        return mixc(self.mut, self.fgc, .3) if t < .5 else mixc(self.fgc, WHITE, .4)


class Segment(_Glass):
    """Выбор из вариантов. variants: [(значение, подпись), ...]. command(значение)."""

    def __init__(self, parent, variants, value, command=None, bg="#0c080a", fg="#f7e8ed", accent="#eeb7d0",
                 muted="#8d7e84", font=(fonts.UI, 9, "bold"), height=26):
        self.fgc, self.acc, self.mut = rgb(fg), rgb(accent), rgb(muted)
        self.values = [v for v, _ in variants]
        self.titles = [t for _, t in variants]
        f = tkfont.Font(font=font)
        slot = max(f.measure(t) for t in self.titles) + 26
        n = len(variants)
        tw = slot * n + 2 * self.PAD
        idx = self.values.index(value) if value in self.values else 0
        cb = (lambda i: command(self.values[i])) if command else None
        self.font = font
        self.text_ids = []
        super().__init__(parent, n, idx, tw, height, slot - 2, slot, bg, cb)
        for i, t in enumerate(self.titles):
            x = self.M + self.PAD + slot / 2 + slot * i
            self.text_ids.append(self.create_text(x, self.M + height / 2, text=t, font=font, fill=fg))

    @property
    def value(self):
        return self.values[self.idx]

    def set(self, value, animate=False, notify=False):
        if value in self.values:
            self.select(self.values.index(value), notify=notify, animate=animate)

    def _t_track(self):
        return 0.0

    def _t_thumb(self):
        return 1.0

    def _color(self):
        return mixc(self.acc, WHITE, .45)

    def _thumb_fill(self, t):
        return self.acc

    def _labels(self):
        for i, tid in enumerate(self.text_ids):
            k = min(1.0, abs(self.px - i) * 1.4)                 # под капсулой - тёмный текст, вдали - обычный
            c = mixc(self.bgc, self.fgc if i == self.idx else mixc(self.fgc, self.mut, .5), k)
            self.itemconfigure(tid, fill=hexc(c))
            self.tag_raise(tid)


def _demo():
    root = tk.Tk()
    root.configure(bg="#0c080a")
    for on in (False, True):
        Toggle(root, on, print).pack(padx=20, pady=6)
    Toggle(root, True, print, scale=1.6).pack(padx=20, pady=6)
    Segment(root, [("a", "Цифры"), ("b", "Стрелки"), ("c", "Кольцо")], "b", print).pack(padx=20, pady=10)
    root.mainloop()


if __name__ == "__main__":
    _demo()
