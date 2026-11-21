"""Виджеты Garasu Classic со списками: расписание. Отступы взяты из schedule.html."""
import os, json, datetime
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QColor
import __main__ as C

NAMES = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
hm = lambda m: "%02d:%02d" % (m // 60, m % 60)


def word(n):
    return "пара" if n % 10 == 1 and n % 100 != 11 else "пары" if 2 <= n % 10 <= 4 and not 10 <= n % 100 < 20 else "пар"


def wrap(p, x, top, w, text, f, col, lh):
    """Текст с переносом по словам (как .hint с line-height)."""
    p.setFont(f); p.setPen(col)
    fm = p.fontMetrics()
    words, ln, y = text.split(), "", top
    for wd in words:
        t = (ln + " " + wd).strip()
        if fm.horizontalAdvance(t) > w and ln:
            p.drawText(QPointF(x, y + (lh - fm.height()) / 2 + fm.ascent()), ln); y += lh; ln = wd
        else:
            ln = t
    if ln:
        p.drawText(QPointF(x, y + (lh - fm.height()) / 2 + fm.ascent()), ln); y += lh
    return y - top


class Schedule(C.Widget):
    CARD = "box"
    name = "schedule"
    base = (330, 300)

    def data(self):
        try:
            with open(os.path.join(C.ZDIR, "schedule.json"), encoding="utf-8-sig") as f:
                return json.load(f)
        except Exception:
            return None

    def state(self):
        n = datetime.datetime.now()
        return (n.hour, n.minute, repr(self.data()))

    def draw(self, p):
        n = datetime.datetime.now()
        wd, mn = n.weekday(), n.hour * 60 + n.minute
        X, W = 2 + 16, 326 - 32
        y = 2 + 14
        data = self.data() or {}
        days = {int(k): v for k, v in (data.get("days") or {}).items()}
        today = days.get(wd, [])
        # шапка: «РАСПИСАНИЕ  пятница ........ ещё 20 мин»
        left = ""
        cur = [q for q in today if q["from"] <= mn < q["to"]]
        if cur:
            left = "ещё %d мин" % (cur[0]["to"] - mn)
        else:
            nxt = [q for q in today if q["from"] > mn]
            if nxt:
                d = nxt[0]["from"] - mn
                left = "через " + ("%d ч " % (d // 60) if d >= 60 else "") + "%d мин" % (d % 60)
        C.tag(p, self, X, y + 1, "РАСПИСАНИЕ")
        p.setFont(C.font(11, 700, C.UI, 1.8)); tw = p.fontMetrics().horizontalAdvance("РАСПИСАНИЕ")
        C.line(p, X + tw + 8, y + 1, NAMES[wd], C.font(11, 400, C.UI), self.c("muted"))
        C.line(p, X, y, left, C.font(12, 600), self.c("fg"), W, "right")
        y += 16 + 8
        if data.get("error"):
            wrap(p, X + 2, y + 8, W - 4, data["error"], C.font(12, 400, C.UI), self.c("muted"), 17.4); return
        if not sum(len(v) for v in days.values()):
            wrap(p, X + 2, y + 8, W - 4, "В заметке пока нет пар. Открой заметку с расписанием и впиши свои.",
                 C.font(12, 400, C.UI), self.c("muted"), 17.4); return
        for i, q in enumerate(today[:5]):
            st = "past" if mn >= q["to"] else "now" if mn >= q["from"] else ""
            RH = 6 + 33 + 6                       # строка: два ряда текста и отступы 6px
            r = QRectF(X, y, W, RH)
            p.save()
            if st == "past":
                p.setOpacity(p.opacity() * 0.45)
            if st == "now":
                p.setPen(Qt.PenStyle.NoPen); p.setBrush(self.c("accent", 0.20)); p.drawRoundedRect(r, 10, 10)
                frac = (mn - q["from"]) / max(1, q["to"] - q["from"])
                p.setClipRect(r); p.setBrush(self.c("accent"))
                p.drawRect(QRectF(X, y + RH - 2, W * frac, 2)); p.setClipping(False)
            # время: начало крупнее, конец под ним
            tx, ty = X + 8, y + 6
            C.line(p, tx, ty, hm(q["from"]), C.font(14, 700), self.c("fg"), 40, "right")
            C.line(p, tx, ty + 17.5, hm(q["to"]), C.font(12, 600), self.c("muted"), 40, "right")
            nx = tx + 40 + 12
            C.line(p, nx, ty, q.get("title", ""), C.font(14, 600, C.UI), self.c("glow" if st == "now" else "fg"),
                   X + W - 8 - nx)
            C.line(p, nx, ty + 19, q.get("place", ""), C.font(11, 400, C.UI), self.c("muted"), X + W - 8 - nx)
            p.restore()
            y += RH + 2
        if len(today) > 5:
            C.line(p, X + 8, y + 4, "и ещё %d" % (len(today) - 5), C.font(11, 400, C.UI), self.c("muted")); y += 22
        if not today or mn >= today[-1]["to"]:
            for i in range(1, 8):
                d = days.get((wd + i) % 7, [])
                if d:
                    t = ("На сегодня всё. " if today else "Сегодня пар нет. ") + \
                        ("Завтра" if i == 1 else "Дальше " + NAMES[(wd + i) % 7]) + \
                        ": %d %s с %s." % (len(d), word(len(d)), hm(d[0]["from"]))
                    wrap(p, X + 2, y + 8, W - 4, t, C.font(12, 400, C.UI), self.c("muted"), 17.4)
                    break


def tools():
    try:
        with open(os.path.join(C.ZDIR, "widgets.json"), encoding="utf-8-sig") as f:
            return json.load(f).get("_tools") or {}
    except Exception:
        return {}


def run(*args):
    """Запустить помощника Гарасу (тот же, что зовёт Zebar), не дожидаясь его."""
    import subprocess
    t = tools()
    if t.get("program") and all(args):
        subprocess.Popen([t["program"], *args], creationflags=0x08000000)


def lines2(p, text, w):
    """Разбить текст на две строки по ширине (как -webkit-line-clamp: 2)."""
    fm = p.fontMetrics()
    out, ln = [], ""
    for wd in text.split():
        t = (ln + " " + wd).strip()
        if fm.horizontalAdvance(t) > w and ln:
            out.append(ln); ln = wd
        else:
            ln = t
    out.append(ln)
    if len(out) > 2:
        out = [out[0], fm.elidedText(" ".join(out[1:]), Qt.TextElideMode.ElideRight, int(w))]
    return out


class Tasks(C.Widget):
    CARD = "box"
    name = "tasks"
    base = (340, 430)
    X, W = 16, 336 - 32

    def data(self):
        try:
            with open(os.path.join(C.ZDIR, "tasks.json"), encoding="utf-8-sig") as f:
                d = json.load(f)
        except Exception:
            return None
        # клик отмечает задачу сразу, не дожидаясь, пока помощник перепишет tasks.json (до 3 с)
        now, opt = C.time.time(), getattr(self, "opt", {})
        for it in d.get("items", []):
            o = opt.get(it["text"])
            if o and now - o[1] < 3:
                if it["done"] == o[0]:
                    opt.pop(it["text"], None)
                else:
                    d["done"] = d.get("done", 0) + (1 if o[0] else -1)
                    d["open"] = d.get("open", 0) - (1 if o[0] else -1)
                    it["done"] = o[0]
        return d

    # ---- анимации как в tasks.html: квадратик заливается (0.22 с), галочка появляется с пружинкой
    # (0.3 с, задержка 0.06), полоска прогресса растёт за 0.5 с
    def chk_k(self, text, done):
        """Доля «отмеченности» квадратика: заливка и масштаб галочки (галочка может чуть перелетать 1)."""
        t0 = getattr(self, "ck", {}).get(text)
        if not t0 or not self.anim_on():
            return (1.0, 1.0) if done else (0.0, 0.0)
        t = C.time.time() - t0
        fill = min(1.0, t / 0.22)
        u = max(0.0, min(1.0, (t - 0.06) / 0.3))
        mark = 1 + 2.70158 * (u - 1) ** 3 + 1.70158 * (u - 1) ** 2      # back-out, как cubic-bezier(.3,1.6,.5,1)
        return (fill, mark) if done else (1 - fill, max(0.0, 1 - u))

    def track(self, d, rows):
        """Запомнить, какие задачи сменили отметку и как изменился прогресс, чтобы проиграть анимацию."""
        now = C.time.time()
        prev = getattr(self, "pdone", None)
        self.ck = {k: t for k, t in getattr(self, "ck", {}).items() if now - t < 0.4}
        cur = {it["text"]: it["done"] for it, _, _ in rows}
        if prev is not None:
            for k, v in cur.items():
                if k in prev and prev[k] != v:
                    self.ck[k] = now
        self.pdone = cur
        total = d.get("open", 0) + d.get("done", 0)
        frac = d.get("done", 0) / total if total else 0
        b = getattr(self, "bar", None)
        if b is None:
            self.bar = (frac, frac, 0)
        elif abs(b[1] - frac) > 1e-6:
            self.bar = (self.bar_frac(), frac, now if self.anim_on() else 0)

    def bar_frac(self):
        a, b, t0 = getattr(self, "bar", (0, 0, 0))
        t = (C.time.time() - t0) / 0.5 if t0 else 1
        return b if t >= 1 else a + (b - a) * C.ease(t)

    def animating(self):
        now = C.time.time()
        b = getattr(self, "bar", (0, 0, 0))
        return super().animating() or any(now - t < 0.4 for t in getattr(self, "ck", {}).values()) \
            or (b[2] and now - b[2] < 0.5)

    def animate(self):
        now = C.time.time()
        b = getattr(self, "bar", (0, 0, 0))
        if any(now - t < 0.4 for t in getattr(self, "ck", {}).values()) or (b[2] and now - b[2] < 0.55):
            self._cache = None
        super().animate()

    def halos(self):
        return [(self.add_rect(), 12)]

    def hot(self):
        from PyQt6.QtGui import QPainter, QImage
        img = QImage(1, 1, QImage.Format.Format_ARGB32); p = QPainter(img)
        rows = self.rows(p)[0]; p.end()
        return [(r, 8) for _, r, _ in rows]

    def grab_zones(self):
        return [self.add_rect()]            # в режиме правки виджет тащится и за строки

    def press_zones(self):
        # .item:active .chk { scale(.85) }: нажатие по строке сжимает только квадратик
        z = [(r, QRectF(r.x() + 6, r.y() + 8, 15, 15), 0.85) for r, _ in self.hot()]
        return z + [(self.add_rect(), self.add_rect(), 0.96)]

    def state(self):
        return repr(self.data())

    def rows(self, p):
        """Строки списка: (задача, rect, строки текста). Нужны и для рисования, и для кликов."""
        d = self.data() or {}
        items = [i for i in d.get("items", []) if self.cfg.get("done", True) or not i["done"]]
        items = [i for i in items if not i["done"]] + [i for i in items if i["done"]]
        p.setFont(C.font(14, 600, C.UI))
        y, out = 16 + 18 + 10, []
        for it in items[: self.cfg.get("count") or 8]:
            ls = lines2(p, it["text"], self.W - 12 - 15 - 10)
            h = 12 + len(ls) * 18.2
            out.append((it, QRectF(self.X, y, self.W, h), ls)); y += h
        return out, len(items), y

    def add_rect(self):
        return QRectF(self.X + self.W - 24, 16 - 4, 24, 24)

    def draw(self, p):
        d = self.data()
        if not d:
            return
        X, W = self.X, self.W
        total = d.get("open", 0) + d.get("done", 0)
        # шапка: ЗАДАЧИ  имя заметки ...  1 / 2  (+)
        C.tag(p, self, X, 16 + 2, "ЗАДАЧИ")
        p.setFont(C.font(11, 700, C.UI, 1.8)); tw = p.fontMetrics().horizontalAdvance("ЗАДАЧИ")
        cnt = "%d / %d" % (d.get("done", 0), total) if total else ""
        p.setFont(C.font(12, 600)); cw = p.fontMetrics().horizontalAdvance(cnt)
        C.line(p, X + tw + 8, 16 + 2, d.get("note", ""), C.font(11, 400, C.UI), self.c("muted"),
               W - tw - 8 - cw - 8 - 2 - 24 - 8)
        C.line(p, X + W - 24 - 2 - 8 - cw, 16 + 1, cnt, C.font(12, 600), self.c("fg"))
        a = self.add_rect()
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(self.c("accent")); p.drawEllipse(a)
        C.line(p, a.x(), a.y() + 1, "+", C.font(17, 700, "Segoe UI"), self.c("pill"), 24, "center")
        rows, n, y = self.rows(p)
        self.track(d, rows)
        for it, r, ls in rows:
            cx, cy = r.x() + 6, r.y() + 6 + 2
            box = QRectF(cx + 1, cy + 1, 13, 13)
            fill, mark = self.chk_k(it["text"], it["done"])
            p.setPen(C.QPen(self.c("accent"), 2)); p.setBrush(Qt.BrushStyle.NoBrush); p.drawRoundedRect(box, 4, 4)
            if fill > 0:
                p.save(); p.setOpacity(fill)
                p.setPen(Qt.PenStyle.NoPen); p.setBrush(self.c("accent")); p.drawRoundedRect(QRectF(cx, cy, 15, 15), 5, 5)
                p.restore()
            if mark > 0.01:
                p.save()
                p.translate(cx + 7.5, cy + 7.5); p.scale(mark, mark); p.translate(-cx - 7.5, -cy - 7.5)
                pen = C.QPen(self.c("pill"), 2); p.setPen(pen)
                p.drawPolyline([QPointF(cx + 4, cy + 7.5), QPointF(cx + 6.5, cy + 10), QPointF(cx + 11, cy + 4.5)])
                p.restore()
            tx = cx + 15 + 10
            col = self.c("muted") if it["done"] else self.c("fg")
            for k, t in enumerate(ls):
                h = C.line(p, tx, r.y() + 6 + k * 18.2 - 1, t, C.font(14, 600, C.UI), col)
                if it["done"]:
                    tw2 = p.fontMetrics().horizontalAdvance(t)
                    p.setPen(C.QPen(self.c("muted"), 1))
                    yy = r.y() + 6 + k * 18.2 + 10
                    p.drawLine(QPointF(tx, yy), QPointF(tx + tw2, yy))
        if not rows:
            C.line(p, X + 6, y + 6, "Все задачи выполнены. Новую добавь кнопкой +", C.font(12, 400, C.UI), self.c("muted"))
            y += 30
        if n > len(rows):
            C.line(p, X + 6, y + 6, "и ещё %d" % (n - len(rows)), C.font(12, 400, C.UI), self.c("muted")); y += 30
        y += 8
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(255, 255, 255, 36))
        p.drawRoundedRect(QRectF(X, y, W, 3), 1.5, 1.5)
        bf = self.bar_frac()
        if bf > 0.001:
            p.setBrush(self.c("accent")); p.drawRoundedRect(QRectF(X, y, W * bf, 3), 1.5, 1.5)

    def click(self, x, y):
        pt = QPointF(x, y)
        if self.add_rect().contains(pt):
            run(tools().get("task_add")); return
        from PyQt6.QtGui import QPainter, QImage
        img = QImage(1, 1, QImage.Format.Format_ARGB32); p = QPainter(img)
        rows = self.rows(p)[0]; p.end()
        for it, r, _ in rows:
            if r.contains(pt):
                run(tools().get("tasks"), "toggle", str(it["line"]))
                self.opt = getattr(self, "opt", {})
                self.opt[it["text"]] = (not it["done"], C.time.time())
                self._cache = None; self.update()
                if self.anim_on():
                    self.anim_t.start(16)
                C.QTimer.singleShot(700, self.tick)
                C.QTimer.singleShot(3100, self.tick)


KINDS = {"schedule": Schedule, "tasks": Tasks}
