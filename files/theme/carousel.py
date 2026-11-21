"""Карусель тем для панели «Темы»: карточки с обоями стоят по кругу, боковые повёрнуты в перспективе,
под центральной светится пятно её цвета. Переход между темами едет на пружине и тормозит плавно.

Экономия: повёрнутые карточки и свечения считаются один раз и кладутся в кэш (по шагам 1/32),
цикл after() крутится только пока карусель движется, в покое не рисуется ничего.
Плавность: место карточки считается точно (без шагов), движение идёт по времени, а не по кадрам,
и на время движения таймер Windows ускоряется до 1 мс (иначе кадр не чаще раза в 15,6 мс)."""
import math
import time
import ctypes
import tkinter as tk
from PIL import Image, ImageDraw, ImageFilter, ImageOps, ImageTk

OMEGA = 15.0                    # жёсткость пружины: чем больше, тем быстрее доезжает (без отскока)
CACHE_BYTES = 36_000_000         # кэш повёрнутых карточек, не больше ~36 МБ
STEP = 32                       # на сколько шагов делится расстояние между соседними карточками (для кэша)


def _rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _solve(a, b):
    """Решение системы 8x8 методом Гаусса (без numpy: его может не быть)."""
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(m[r][c]))
        m[c], m[p] = m[p], m[c]
        for r in range(n):
            if r != c and m[c][c]:
                f = m[r][c] / m[c][c]
                for k in range(c, n + 1):
                    m[r][k] -= f * m[c][k]
    return [m[i][n] / m[i][i] for i in range(n)]


def _persp(dst, src):
    """Коэффициенты для Image.PERSPECTIVE: точка выхода dst[i] берёт цвет из точки src[i] исходника."""
    a, b = [], []
    for (x, y), (u, v) in zip(dst, src):
        a.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); b.append(u)
        a.append([0, 0, 0, x, y, 1, -v * x, -v * y]); b.append(v)
    return _solve(a, b)


def glow_color(im):
    """Самый яркий насыщенный цвет картинки: им светится пятно под карточкой (как в ролике)."""
    small = im.convert("RGB").resize((48, 27))
    q = small.quantize(6).convert("RGB")
    best, score = (200, 200, 220), -1
    for cnt, c in q.getcolors(64) or []:
        mx, mn = max(c), min(c)
        s = (mx - mn) / 255 * (0.35 + mx / 255) * (cnt ** 0.25)
        if s > score:
            best, score = c, s
    # чуть поднимаем яркость, чтобы свечение читалось на тёмном фоне
    k = 235 / max(1, max(best))
    return tuple(min(255, int(v * k)) for v in best)


class Carousel(tk.Canvas):
    def __init__(self, parent, width, height, items, current=0, on_pick=None, on_focus=None,
                 bg="#000000", accent="#ffffff", card=(300, 169)):
        super().__init__(parent, width=width, height=height, bg=bg, highlightthickness=0, bd=0)
        self.W, self.H, self.cw, self.ch = width, height, card[0], card[1]
        self.items = items                        # [(id, PIL.Image)]
        self.on_pick, self.on_focus = on_pick, on_focus
        self.bg, self.accent = bg, accent
        self.pos = self.target = float(current)
        self.vel, self.job, self.active = 0.0, None, current
        self.cache, self.glows, self.hit = {}, {}, []
        self._last, self._fast = 0.0, False
        self.frame_ms = []                        # время отрисовки кадров (для замеров)
        self._img = None
        self._warm_job, self._warm_q = None, []
        self._item = self.create_image(0, 0, anchor="nw")
        self._prep()
        self.bind("<Button-1>", self._click)
        self.bind("<MouseWheel>", lambda e: self.go(self.target + (-1 if e.delta > 0 else 1)))
        self.bind("<Configure>", lambda e: self.draw())
        self.draw()

    # ---------- подготовка
    def _prep(self):
        """Исходники карточек: скруглённые углы, стеклянный блик сверху, у активной темы рамка акцента."""
        S = 2
        cw, ch = self.cw * S, self.ch * S
        mask = Image.new("L", (cw, ch), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, cw - 1, ch - 1), radius=18 * S, fill=255)
        sheen = Image.new("L", (1, ch))
        for y in range(ch):
            sheen.putpixel((0, y), int(46 * max(0.0, 1 - y / (ch * 0.42)) ** 2))
        sheen = sheen.resize((cw, ch))
        white = Image.new("RGB", (cw, ch), (255, 255, 255))
        self.src, self.colors = [], []
        for i, (tid, im) in enumerate(self.items):
            pic = ImageOps.fit(im.convert("RGB"), (cw, ch), Image.LANCZOS)
            self.colors.append(glow_color(pic))
            pic = Image.composite(white, pic, sheen)
            d = ImageDraw.Draw(pic)
            if i == self.active:
                d.rounded_rectangle((2, 2, cw - 3, ch - 3), radius=17 * S, outline=self.accent, width=3 * S)
            else:
                d.rounded_rectangle((1, 1, cw - 2, ch - 2), radius=17 * S, outline=(255, 255, 255), width=1)
            pic = pic.convert("RGBA")
            pic.putalpha(mask)
            self.src.append(pic.resize((self.cw, self.ch), Image.LANCZOS))
        self.cache.clear()
        self._bytes = 0
        self.glows.clear()
        self._warm_later()

    def recolor(self, bg, accent, active=None):
        self.bg, self.accent = bg, accent
        if active is not None:
            self.active = active
        self.configure(bg=bg)
        self._prep()
        self.draw()

    # ---------- геометрия: где стоит карточка, если она на расстоянии d от центра
    def _place(self, d):
        a = min(abs(d), 1.0)
        far = max(0.0, abs(d) - 1.0)
        sgn = 1 if d >= 0 else -1
        off = a * self.cw * 0.62 + far * self.cw * 0.30
        s = 1 - 0.20 * a - 0.10 * far
        w = self.cw * s * (1 - 0.42 * a)          # повёрнутая карточка уже
        h = self.ch * s
        hf = h * (1 - 0.20 * a)                    # дальний край ниже: перспектива
        cx = self.W / 2 + sgn * off
        return cx, w, h, hf, sgn

    def _card(self, i, d):
        """Повёрнутая карточка i на расстоянии d (кэшируется)."""
        q = round(d * STEP)
        key = (i, q)
        got = self.cache.get(key)
        if got:
            return got
        d = q / STEP
        cx, w, h, hf, sgn = self._place(d)
        W, H = max(2, int(w + 2)), max(2, int(h + 2))
        y0, y1 = (H - h) / 2, (H + h) / 2
        f0, f1 = (H - hf) / 2, (H + hf) / 2
        if sgn > 0:      # справа: ближний край левый
            dst = [(0, y0), (W - 1, f0), (W - 1, f1), (0, y1)]
        else:
            dst = [(0, f0), (W - 1, y0), (W - 1, y1), (0, f1)]
        cw, ch = self.cw, self.ch
        src = [(0, 0), (cw, 0), (cw, ch), (0, ch)]
        # дальние карточки темнее и прозрачнее: глаз держится на центральной (затемнённые копии готовы заранее)
        dim = min(abs(d), 2.2)
        k = 1 - 0.30 * min(dim, 1) - 0.12 * max(0, dim - 1)
        base = self._dimmed(i, k)
        if abs(d) < 1e-6:
            out = base
        else:
            out = base.transform((W, H), Image.PERSPECTIVE, _persp(dst, src), Image.BILINEAR)
        fade = 1.0 if abs(d) < 1.6 else max(0.0, 1 - (abs(d) - 1.6) / 0.7)
        if fade < 1:
            out = out.copy()
            out.putalpha(out.getchannel("A").point([int(v * fade) for v in range(256)]))
        self._bytes += out.width * out.height * 4
        if self._bytes > CACHE_BYTES:             # предел памяти: убираем кадры дальних карточек, соседние оставляем
            c = round(self.target)
            self.cache = {k_: v for k_, v in self.cache.items() if k_[0] == "dim" or abs(k_[0] - c) <= 2}
            self._bytes = sum(v.width * v.height * 4 for k_, v in self.cache.items() if k_[0] != "dim")
            if self._bytes > CACHE_BYTES:
                self.cache = {k_: v for k_, v in self.cache.items() if k_[0] == "dim"}
                self._bytes = 0
        self.cache[key] = out
        return out

    def _dimmed(self, i, k):
        """Карточка i, затемнённая в k раз (12 ступеней, считаются один раз)."""
        q = round((1 - k) * 24)
        key = ("dim", i, q)
        got = self.cache.get(key)
        if got is None:
            if q == 0:
                got = self.src[i]
            else:
                r, g, b, a = self.src[i].split()
                lut = [int(v * (1 - q / 24)) for v in range(256)]
                got = Image.merge("RGBA", (r.point(lut), g.point(lut), b.point(lut), a))
            self.cache[key] = got
        return got

    GLOW_PAD, GLOW_BLUR, GLOW_DY = 42, 14, 14

    def _glow(self, i, k):
        """Ореол цвета карточки позади неё: выглядывает снизу и по бокам.
        Поле вокруг формы втрое больше радиуса размытия, поэтому размытие сходит на ноль
        внутри картинки и прямых краёв нет."""
        q = max(0, min(16, round(k * 16)))
        key = (i, q)
        got = self.glows.get(key)
        if got is not None:
            return got
        base = self.glows.get("base")
        if base is None:
            P = self.GLOW_PAD
            sw, sh = int(self.cw * 0.93), int(self.ch * 0.80)
            m = Image.new("L", (sw + 2 * P, sh + 2 * P), 0)
            ImageDraw.Draw(m).rounded_rectangle((P, P, P + sw, P + sh), radius=sh // 3, fill=255)
            base = m.filter(ImageFilter.GaussianBlur(self.GLOW_BLUR))
            self.glows["base"] = base
        g = Image.new("RGBA", base.size, self.colors[i] + (0,))
        # степень 0.6 поднимает хвост размытия: ореол виден дальше от карточки, но всё так же гаснет в ноль
        g.putalpha(base.point([int(255 * (v / 255) ** 0.6 * 0.95 * q / 16) for v in range(256)]))
        self.glows[key] = g
        return g

    # ---------- рисование
    def draw(self):
        t0 = time.perf_counter()
        frame = Image.new("RGB", (self.W, self.H), _rgb(self.bg))
        cy = self.H / 2 - 12
        self.hit = []
        n = len(self.items)
        order = sorted(range(n), key=lambda i: -abs(i - self.pos))
        # свечение под той карточкой, что ближе к центру (при переходе одно пятно гаснет, другое разгорается)
        for i in range(n):
            d = i - self.pos
            k = max(0.0, 1 - abs(d) * 1.3)
            if k > 0.02:
                g = self._glow(i, k)                      # ореол едет вместе со своей карточкой
                gx = self._place(d)[0]
                frame.paste(g, (round(gx - g.width / 2), round(cy + self.GLOW_DY - g.height / 2)), g)
        for i in order:
            d = i - self.pos
            if abs(d) > 2.35:
                continue
            im = self._card(i, d)
            cx = self._place(d)[0]                    # место точное, без шагов: нет дрожи в конце движения
            x, y = round(cx - im.width / 2), round(cy - im.height / 2)
            frame.paste(im, (x, y), im)
            self.hit.append((i, x, y, x + im.width, y + im.height))
        if self._img is not None and (self._img.width(), self._img.height()) == frame.size:
            self._img.paste(frame)                # та же картинка Tk, без пересоздания: быстрее и без мигания
        else:
            self._img = ImageTk.PhotoImage(frame)
            self.itemconfigure(self._item, image=self._img)
        self.frame_ms.append((time.perf_counter() - t0) * 1000)
        del self.frame_ms[:-200]

    # ---------- движение: пружина, кадры только пока едем
    def go(self, idx, pick=False):
        idx = max(0, min(len(self.items) - 1, int(round(idx))))
        changed = idx != round(self.target)
        self.target = float(idx)
        if changed and self.on_focus:
            self.on_focus(idx)
        if self.job is None:
            self._warm_stop()
            self._timer(True)
            self._last = time.perf_counter()
            self.job = self.after(1, self._tick)

    def _timer(self, fast):
        """Точный таймер Windows только на время движения (в покое возвращаем как было)."""
        if fast != self._fast:
            try:
                f = ctypes.windll.winmm.timeBeginPeriod if fast else ctypes.windll.winmm.timeEndPeriod
                f(1)
                self._fast = fast
            except Exception:
                pass

    def _tick(self):
        now = time.perf_counter()
        dt = min(0.05, now - self._last)
        self._last = now
        # пружина без отскока, считается по прошедшему времени: скорость одинакова при любой частоте кадров,
        # а при новом прокруте на ходу движение подхватывается без рывка
        x, v = self.pos - self.target, self.vel
        e = math.exp(-OMEGA * dt)
        t = (v + OMEGA * x) * dt
        x, v = (x + t) * e, (v - OMEGA * t) * e
        self.pos, self.vel = self.target + x, v
        if abs(x) < 0.002 and abs(v) < 0.02:
            self.pos, self.vel, self.job = self.target, 0.0, None
            self.draw()
            self._timer(False)
            self._warm_later()
            return
        self.draw()
        spent = (time.perf_counter() - now) * 1000
        self.job = self.after(max(1, int(8 - spent)), self._tick)   # цель ~120 кадров в секунду

    # ---------- прогрев: пока карусель стоит, заранее готовим кадры шага влево и вправо
    def _warm_later(self):
        """Через полсекунды покоя начать прогрев (сразу после открытия окну не мешаем)."""
        self._warm_stop()
        c = int(round(self.target))
        n = len(self.items)
        q = []
        for k in range(STEP + 1):                 # сначала ближние к покою кадры: они нужны первыми
            for side in (1, -1):
                for i in range(max(0, c - 3), min(n, c + 4)):
                    d = (i - c) - side * k / STEP
                    if abs(d) <= 2.35:
                        q.append((i, d))
        self._warm_q = q
        self._warm_job = self.after(500, self._warm_step)

    def _warm_stop(self):
        if self._warm_job is not None:
            self.after_cancel(self._warm_job)
            self._warm_job = None

    def _warm_step(self):
        """Порция работы не дольше 6 мс, потом отдаём время окну: панель не подтормаживает."""
        self._warm_job = None
        t0 = time.perf_counter()
        while self._warm_q and time.perf_counter() - t0 < 0.006:
            i, d = self._warm_q.pop(0)
            self._card(i, d)
            k = max(0.0, 1 - abs(d) * 1.3)
            if k > 0.02:
                self._glow(i, k)
        if self._warm_q:
            self._warm_job = self.after(15, self._warm_step)

    def _click(self, e):
        for i, x0, y0, x1, y1 in reversed(self.hit):          # сверху лежит тот, что нарисован последним
            if x0 <= e.x <= x1 and y0 <= e.y <= y1:
                if i == round(self.target) and abs(self.pos - self.target) < 0.2:
                    if self.on_pick:
                        self.on_pick(i)
                else:
                    self.go(i)
                return
