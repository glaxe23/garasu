"""Виджеты Garasu Classic: черновик и таймер (помодоро). Отступы взяты из scratch.html и pomodoro.html."""
import os, json, time, datetime, threading
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QColor, QPen, QLinearGradient, QBrush, QImage, QPainter
import __main__ as C
from classic_b import tools, run

HERE = os.path.dirname(os.path.abspath(__file__))


def para_lines(p, text, w):
    """pre-wrap + word-break: сохранить переносы строк, длинные строки разбить по словам."""
    fm = p.fontMetrics()
    out = []
    for para in text.replace("\r", "").split("\n"):
        ln = ""
        for wd in para.split(" "):
            t = (ln + " " + wd) if ln else wd
            if fm.horizontalAdvance(t) > w and ln:
                out.append(ln); ln = wd
            else:
                ln = t
            while fm.horizontalAdvance(ln) > w and len(ln) > 1:      # слово длиннее строки
                k = len(ln)
                while k > 1 and fm.horizontalAdvance(ln[:k]) > w:
                    k -= 1
                out.append(ln[:k]); ln = ln[k:]
        out.append(ln)
    return out


class Scratch(C.Widget):
    CARD = "box"
    name = "scratch"
    base = (300, 200)

    def text(self):
        try:
            with open(os.path.join(C.ZDIR, "scratch.txt"), encoding="utf-8-sig") as f:
                return f.read()
        except Exception:
            return ""

    def state(self):
        return self.text()

    def draw(self, p):
        X, W, top, bottom = 2 + 18, 296 - 36, 2 + 14, 2 + 192 - 12
        y = top + C.tag(p, self, X, top, "ЧЕРНОВИК") + 8
        t = self.text()
        empty = not t.strip()
        # текст рисуем в отдельный слой и гасим низ градиентом, как mask-image в css
        z = self.zoom()
        layer = QImage(int(W * z) + 2, int((bottom - y) * z) + 2, QImage.Format.Format_ARGB32_Premultiplied)
        layer.fill(0)
        q = QPainter(layer); q.setRenderHint(QPainter.RenderHint.Antialiasing); q.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        q.scale(z, z)
        f = C.font(13, 400, C.UI); q.setFont(f)
        lh = 13 * 1.45
        fm = q.fontMetrics()
        yy = 0
        for ln in para_lines(q, "Кликни, чтобы записать мысль." if empty else t, W):
            if yy > bottom - y:
                break
            q.setPen(self.c("muted" if empty else "fg"))
            q.drawText(QPointF(0, yy + (lh - fm.height()) / 2 + fm.ascent()), ln)
            yy += lh
        h = bottom - y
        g = QLinearGradient(0, 0, 0, h)
        g.setColorAt(0, QColor(0, 0, 0, 255)); g.setColorAt(0.78, QColor(0, 0, 0, 255)); g.setColorAt(1, QColor(0, 0, 0, 0))
        q.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        q.fillRect(QRectF(0, 0, W + 1, h + 1), QBrush(g)); q.end()
        p.save(); p.resetTransform()
        p.drawImage(QPointF(X * z, y * z), layer); p.restore()

    def click(self, x, y):
        run(tools().get("scratch"))
        C.QTimer.singleShot(800, self.tick)


import classic_sounds as sounds
AMB, AMBN = ["off", "rain", "pink"], {"off": "", "rain": "дождь", "pink": "шум"}


def breathe(t):
    """@keyframes breathe: 1 → 1.07 на 30% → 1, два раза по 1.4 с."""
    t = (t % 1.4) / 1.4
    return 1 + 0.07 * (C.ease(t / 0.3) if t < 0.3 else 1 - C.ease((t - 0.3) / 0.7))


def flash(t):
    """@keyframes flash: доля цвета glow для времени (0 → 1 к 25%, держится до 60%, обратно к 100%)."""
    t = (t % 1.4) / 1.4
    return t / 0.25 if t < 0.25 else 1 if t < 0.6 else 1 - (t - 0.6) / 0.4


class Pomodoro(C.Widget):
    CARD = "box"
    name = "pomodoro"
    base = (250, 300)
    FILE = os.path.join(HERE, "pomodoro_state.json")
    CX, CY, R = 125, 39 + 84, 76                 # центр кольца: блок 168x168, отступ сверху 16+15+8
    BTN = {"reset": (41, 249, 32), "play": (83, 244, 42), "skip": (135, 249, 32), "amb": (177, 249, 32)}
    ADJ = {"minus": (6, 109), "plus": (216, 109)}

    def __init__(self, *a, **k):
        self.st = {"phase": "work", "running": False, "endsAt": 0, "left": 0, "done": 0, "day": "", "own": {}}
        try:
            with open(self.FILE, encoding="utf-8") as f:
                self.st.update(json.load(f))
        except Exception:
            pass
        self.from_zebar()
        self.pulse0 = 0
        super().__init__(*a, **k)
        if not self.st["left"]:
            self.st["left"] = self.total()

    def from_zebar(self):
        """Переход с Zebar: таймер Zebar сообщает заморозке время конца отрезка (freeze_note.json).
        Если там идёт отсчёт, который ещё не кончился и свежее нашего файла, продолжаем его."""
        note = os.path.join(HERE, "freeze_note.json")
        try:
            with open(note, encoding="utf-8") as f:
                n = json.load(f)
            ends = n.get("endsAt", 0) / 1000
            mine = os.path.getmtime(self.FILE) if os.path.exists(self.FILE) else 0
            if n.get("running") and ends > time.time() and os.path.getmtime(note) > mine                     and n.get("phase") in ("work", "rest"):
                self.st.update(running=True, endsAt=ends, phase=n["phase"], left=round(ends - time.time()))
                if n.get("amb") in ("rain", "noise"):
                    self.st["amb"] = n["amb"]
                self.save()
        except Exception:
            pass

    def save(self):
        try:
            with open(self.FILE, "w", encoding="utf-8") as f:
                json.dump(self.st, f)
        except Exception:
            pass

    def mins(self, ph):
        own = self.st.get("own") or {}
        return own.get(ph) or self.cfg.get("work" if ph == "work" else "rest", 25 if ph == "work" else 5)

    def total(self):
        return self.mins(self.st["phase"]) * 60

    def next_phase(self, finished):
        st = self.st
        if finished and st["phase"] == "work":
            st["done"] += 1
        st["phase"] = "rest" if st["phase"] == "work" else "work"
        st["left"] = self.total()
        st["running"] = finished
        st["endsAt"] = time.time() + st["left"]
        if finished and self.cfg.get("sound", True) is not False:
            sounds.chime()
        if finished and self.anim_on():          # «вдох» кольца и вспышка времени
            self.pulse0 = time.time(); self.anim_t.start(16)
        self.save()

    def state(self):
        st, today = self.st, datetime.date.today().isoformat()
        if st.get("day") != today:
            st["day"], st["done"] = today, 0; self.save()
        if st["running"]:
            st["left"] = max(0, round(st["endsAt"] - time.time()))
            if st["left"] <= 0:
                self.next_phase(True)
        self.amb_sync()
        return (st["phase"], st["running"], min(st["left"], self.total()), st["done"], self.total(), st.get("amb"))

    def amb_sync(self):
        st = self.st
        want = (st.get("amb") or "off") if st["running"] and st["phase"] == "work" else "off"
        key = (want, self.cfg.get("ambvol", 35))
        if key != getattr(self, "_amb", ("off", key[1])):
            self._amb = key
            sounds.ambient(*key)

    # ---- анимация «вдоха» после окончания этапа (2 раза по 1.4 с)
    def pulsing(self):
        return self.pulse0 and time.time() - self.pulse0 < 2.8

    # ---- кольцо плавно доезжает до нового значения за 0.5 с (stroke-dashoffset 0.5s в html):
    # при сбросе, пропуске и ±5 минут. Обычный ход по секунде не анимируется, чтобы не грузить процессор.
    def ring_frac(self, target):
        if not hasattr(self, "rf"):
            self.rf = (target, target, 0)
        a, b, t0 = self.rf
        now = time.time()
        k = min(1.0, (now - t0) / 0.5) if t0 else 1.0
        cur = a + (b - a) * C.ease(k)
        if abs(b - target) > 1e-6:
            if abs(cur - target) > 0.02 and self.anim_on():
                self.rf = (cur, target, now); self.anim_t.start(16)
                return cur
            self.rf = (target, target, 0)
            return target
        return cur

    def ring_busy(self):
        t0 = getattr(self, "rf", (0, 0, 0))[2]
        return bool(t0) and time.time() - t0 < 0.55

    def animating(self):
        return super().animating() or self.pulsing() or self.ring_busy()

    def animate(self):
        if self.ring_busy():
            self._cache = None
        if self.pulsing() or self.pulse0:
            self._cache = None
            if not self.pulsing():
                self.pulse0 = 0
        super().animate()

    def halos(self):
        x, y, d = self.BTN["play"]
        return [(QRectF(x, y, d, d), d / 2)]

    def hot(self):
        r = [(QRectF(x, y, d, d), d / 2) for x, y, d in self.BTN.values() if d != 42]
        if not self.st["running"]:
            r += [(QRectF(x, y, 28, 28), 14) for x, y in self.ADJ.values()]
        return r

    def draw(self, p):
        st = self.st
        tot = self.total(); left = min(st["left"], tot)
        X, W = 2 + 16, 246 - 32
        C.tag(p, self, X, 16, "ТАЙМЕР")
        if st["done"]:
            C.line(p, X, 16, "сегодня: %d" % st["done"], C.font(12, 600), self.c("muted"), W, "right")
        r = QRectF(self.CX - self.R, self.CY - self.R, 2 * self.R, 2 * self.R)
        pt = time.time() - self.pulse0 if self.pulsing() else None
        p.save()
        if pt is not None:
            k = breathe(pt)
            p.translate(self.CX, self.CY); p.scale(k, k); p.translate(-self.CX, -self.CY)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, 36), 9)); p.drawEllipse(r)
        frac = self.ring_frac(left / tot if tot else 0)
        if frac > 0:
            pen = QPen(self.c("accent2" if st["phase"] == "rest" else "accent"), 9)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap); p.setPen(pen)
            p.drawArc(r, 90 * 16, -int(frac * 360 * 16))     # от верха по часовой
        m, s = divmod(left, 60)
        tf = C.font(40, 700, spacing=-1); p.setFont(tf); th = p.fontMetrics().height()
        pf = C.font(12, 400, C.UI); p.setFont(pf); ph = p.fontMetrics().height()
        top = self.CY - (th + ph - 2) / 2
        tc = self.c("fg") if pt is None else C.mix(self.c("fg"), self.c("glow"), max(0, min(1, flash(pt))))
        C.line(p, self.CX - 80, top, "%02d:%02d" % (m, s), tf, tc, 160, "center")
        phase = ("работа" if st["phase"] == "work" else "перерыв") + ("" if st["running"] else " · пауза")
        amb = st.get("amb") or "off"
        if amb != "off" and st["phase"] == "work":
            phase += " · " + AMBN[amb]
        C.line(p, self.CX - 80, top + th - 2, phase, pf, self.c("muted"), 160, "center")
        p.restore()
        if not st["running"]:
            for k, (x, y) in self.ADJ.items():
                p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(255, 255, 255, 26))
                p.drawEllipse(QRectF(x, y, 28, 28))
                C.line(p, x, y + 2, "−" if k == "minus" else "+", C.font(17, 700, "Segoe UI"), self.c("fg"), 28, "center")
        icons = {"reset": "", "play": "" if st["running"] else "", "skip": "", "amb": ""}
        for k, (x, y, d) in self.BTN.items():
            rr = QRectF(x, y, d, d)
            col = self.c("fg")
            if k == "amb" and (st.get("amb") or "off") != "off":     # #amb.on
                p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(255, 255, 255, 26)); p.drawEllipse(rr)
                col = self.c("accent")
            if k == "play":
                p.setPen(Qt.PenStyle.NoPen); p.setBrush(self.c("accent")); p.drawEllipse(rr); col = self.c("pill")
            f = C.font(14 if k == "play" else 12, 400, "Segoe Fluent Icons"); p.setFont(f)
            fm = p.fontMetrics()
            p.setPen(col)
            p.drawText(rr, Qt.AlignmentFlag.AlignCenter, icons[k])

    def click(self, x, y):
        st, pt = self.st, QPointF(x, y)
        hit = lambda r: r.contains(pt)
        for k, (bx, by, d) in self.BTN.items():
            if hit(QRectF(bx, by, d, d)):
                if k == "play":
                    st["running"] = not st["running"]
                    if st["running"]:
                        st["endsAt"] = time.time() + st["left"]
                elif k == "reset":
                    st.update(running=False, phase="work"); st["left"] = self.total()
                elif k == "skip":
                    self.next_phase(False)
                elif k == "amb":
                    st["amb"] = AMB[(AMB.index(st.get("amb") or "off") + 1) % len(AMB)]
                self.save(); self.tick(); return
        if not st["running"]:
            for k, (bx, by) in self.ADJ.items():
                if hit(QRectF(bx, by, 28, 28)):
                    self.adjust(-5 if k == "minus" else 5); return

    def adjust(self, d):
        m = max(1, min(180, self.mins(self.st["phase"]) + d))
        self.st.setdefault("own", {})[self.st["phase"]] = m
        self.st["left"] = m * 60; self.save(); self.tick()

    def wheelEvent(self, e):
        if not self.st["running"]:
            self.adjust(1 if e.angleDelta().y() > 0 else -1)


def color_blend(img, acc):
    """Режим смешивания color: SetLum(акцент, Lum(фото)) по спецификации compositing (W3C)."""
    import numpy as np
    w, h = img.width(), img.height()
    src = img.convertToFormat(QImage.Format.Format_RGB32)
    a = np.frombuffer(src.constBits().asstring(src.sizeInBytes()), np.uint8).reshape(h, src.bytesPerLine() // 4, 4)[:, :w]
    b, g, r = (a[..., k].astype(np.float32) / 255 for k in (0, 1, 2))
    lum = 0.3 * r + 0.59 * g + 0.11 * b
    cr, cg, cb = acc.redF(), acc.greenF(), acc.blueF()
    d = lum - (0.3 * cr + 0.59 * cg + 0.11 * cb)
    R, G, B = cr + d, cg + d, cb + d
    l = 0.3 * R + 0.59 * G + 0.11 * B
    n, x = np.minimum(np.minimum(R, G), B), np.maximum(np.maximum(R, G), B)
    out = []
    for c in (R, G, B):                                  # ClipColor
        c = np.where(n < 0, l + (c - l) * l / np.maximum(l - n, 1e-6), c)
        c = np.where(x > 1, l + (c - l) * (1 - l) / np.maximum(x - l, 1e-6), c)
        out.append(np.clip(c * 255 + 0.5, 0, 255).astype(np.uint8))
    buf = np.dstack([out[2], out[1], out[0], np.full((h, w), 255, np.uint8)]).copy()
    res = QImage(buf.data, w, h, w * 4, QImage.Format.Format_RGB32).copy()
    return res.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)


class Photo(C.Widget):
    """Слайд-шоу из photos.json: кадр cover, смена с плавным переходом 1.2 с, оттенок темы."""
    name = "photo"
    base = (300, 400)
    SHADOWS = ()                       # у фото в html нет тени
    FADE = 1.2

    def __init__(self, *a, **k):
        self.idx, self.cur, self.prev, self.t0, self.last, self.cache = -1, None, None, 0, "", {}
        super().__init__(*a, **k)
        self.anim = C.QTimer(self); self.anim.timeout.connect(self.step)
        self.files(); self.next()
        self.flip = C.QTimer(self); self.flip.timeout.connect(self.next)
        self.flip.start(max(5, self.cfg.get("interval", 30)) * 1000)

    def files(self):
        try:
            with open(os.path.join(C.ZDIR, "photos.json"), encoding="utf-8-sig") as f:
                return json.load(f).get("files") or []
        except Exception:
            return []

    def next(self):
        fs = self.files()
        if not fs:
            self.cur = None; return
        self.idx = (self.idx + 1) % len(fs)
        self.prev, self.cur, self.t0 = self.cur, fs[self.idx], time.time()
        if self.prev and self.prev != self.cur and self.cfg.get("_anim", True):
            self.anim.start(40)
        self.step()

    def step(self):
        if time.time() - self.t0 >= self.FADE:
            self.anim.stop(); self.prev = None
        self._cache = None; self.update()

    def state(self):
        return (self.cur, repr(self.files()))

    def tick(self):
        if repr(self.files()) != self.last:
            self.last = repr(self.files()); self.idx = -1; self.prev = None; self.next()
        super().tick()

    def picture(self, rel, w, h):
        """Кадр по размеру окна (object-fit: cover) с оттенком темы. Считается один раз на фото."""
        tint = {"off": 0, "soft": 0.35, "strong": 0.6}.get(self.cfg.get("tint", "soft"), 0.35)
        key = (rel, w, h, self.theme.get("accent"), tint)
        if key in self.cache:
            return self.cache[key]
        img = QImage(os.path.join(C.ZDIR, rel))
        if img.isNull():
            return None
        img = img.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
        img = img.copy((img.width() - w) // 2, (img.height() - h) // 2, w, h).convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        if tint:
            # mix-blend-mode: color (формула W3C): цвет акцента с яркостью фото, слой с прозрачностью tint
            col = color_blend(img, self.c("accent"))
            q = QPainter(img); q.setOpacity(tint); q.drawImage(0, 0, col); q.setOpacity(tint)
            # снизу мягкая подсветка акцентом (soft-light), гаснет к 60% высоты
            g = QLinearGradient(0, h, 0, h * 0.4)
            g.setColorAt(0, self.c("accent", 0.35)); g.setColorAt(1, QColor(0, 0, 0, 0))
            q.setCompositionMode(QPainter.CompositionMode.CompositionMode_SoftLight)
            q.fillRect(img.rect(), QBrush(g)); q.end()
        if len(self.cache) > 6:
            self.cache.clear()
        self.cache[key] = img
        return img

    def draw(self, p):
        z = self.zoom()
        rad = (C.read_json("widgets.json", {}).get("all") or {}).get("radius", 26)
        r = QRectF(2, 2, 296, 396)
        p.save()
        from PyQt6.QtGui import QPainterPath
        path = QPainterPath(); path.addRoundedRect(r, rad, rad); p.setClipPath(path)
        if not self.cur:
            p.setClipping(False); C.draw_glass(p, self, r, rad)
            C.line(p, 2, 180, "Положи картинки в папку", C.font(13, 500, C.UI), self.c("muted"), 296, "center")
            C.line(p, 2, 198, os.path.join(os.path.dirname(HERE), "photos"), C.font(13, 500, C.UI), self.c("muted"), 296, "center")
            p.restore(); return
        W, H = int(296 * z), int(396 * z)
        k = min(1, (time.time() - self.t0) / self.FADE) if self.prev else 1
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        for rel, op in ((self.prev, 1), (self.cur, k)) if self.prev else ((self.cur, 1),):
            img = self.picture(rel, W, H)
            if img is not None:
                p.setOpacity(op); p.drawImage(r, img)
        p.setOpacity(1)
        if self.cfg.get("border") is not False:
            p.setClipping(False); p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(255, 255, 255, 41), 8)); p.drawRoundedRect(r.adjusted(4, 4, -4, -4), rad - 4, rad - 4)
            p.setPen(QPen(QColor(255, 255, 255, 77), 1)); p.drawRoundedRect(r.adjusted(.5, .5, -.5, -.5), rad, rad)
        p.restore()


KINDS = {"scratch": Scratch, "pomodoro": Pomodoro, "photo": Photo}
