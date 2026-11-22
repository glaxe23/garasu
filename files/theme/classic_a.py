"""Простые виджеты Garasu Classic: ярлыки, счётчики, прогресс. Размеры и отступы взяты из их html."""
import os, re, datetime
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QColor, QImage, QLinearGradient, QBrush, QPen, QPainter
import __main__ as C          # classic.py, запущенный как программа


class Links(C.Widget):
    CARD = "box"
    name = "links"
    base = (316, 122)
    CELL_W, CELL_H = 73, 78
    # ширину и высоту можно тянуть отдельно (края рамки в режиме правки): cols — значков в ряд,
    # rows — сколько рядов минимум (лишние ряды — пустое место под новые ярлыки)
    EDGES, EDGE_KEYS = True, ("cols", "rows")

    def items(self):
        return [i for i in self.cfg.get("items", []) if i.get("path")]

    def cols(self, cfg=None):
        return max(1, min(12, int((cfg or self.cfg).get("cols") or 4)))

    def size_for(self, cfg):
        n = len([i for i in cfg.get("items", []) if i.get("path")])
        cols = self.cols(cfg)
        return (24 + self.CELL_W * cols, 47 + self.CELL_H * max(1, int(cfg.get("rows") or 0), -(-n // cols)))

    def content_h(self):
        return self.size_for(self.cfg)[1]

    def state(self):
        return repr(self.items())

    def edge_drag(self, kind, dx, dy):
        n, cols = len(self.items()), self.cols(self.edrag["edge0"])
        if kind == "w":
            w0 = 24 + self.CELL_W * cols
            return {"cols": max(1, min(12, round((w0 + dx - 24) / self.CELL_W)))}
        rows0 = max(1, int(self.edrag["edge0"].get("rows") or 0), -(-n // cols))
        rows = max(1, min(12, round((self.CELL_H * rows0 + dy) / self.CELL_H)))
        return {"rows": rows if rows > -(-n // cols) else 0}      # меньше, чем нужно значкам, не бывает

    def geo(self):
        x0, top = 2 + 10, 2 + 12 + 15 + 6
        cols = self.cols()
        for i, it in enumerate(self.items()):
            yield it, QRectF(x0 + (i % cols) * self.CELL_W, top + (i // cols) * self.CELL_H, self.CELL_W, self.CELL_H)

    def draw(self, p):
        C.tag(p, self, 2 + 10 + 6, 2 + 12, "ЯРЛЫКИ")
        for it, r in self.geo():
            ix, iy = r.center().x() - 18, r.y() + 11
            icon = it.get("icon")
            img = QImage(os.path.join(C.ZDIR, "icons", icon)) if icon else QImage()
            if not img.isNull():
                p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                p.drawImage(QRectF(ix, iy, 36, 36), img)
            else:
                p.setBrush(self.c("accent")); p.setPen(Qt.PenStyle.NoPen)
                p.drawRoundedRect(QRectF(ix, iy, 36, 36), 10, 10)
                C.line(p, ix, iy + 6, (it.get("title") or "?")[:1].upper(), C.font(18, 700, "Segoe UI"),
                       self.c("pill"), 36, "center")
            C.line(p, r.x() + (r.width() - 66) / 2, iy + 41, it.get("title", ""), C.font(11, 600, C.UI),
                   self.c("fg"), 66, "center")

    def click(self, x, y):
        for it, r in self.geo():
            if r.contains(QPointF(x, y)):
                try:
                    os.startfile(it["path"])
                except OSError:
                    pass


def plural(n):
    n = abs(n) % 100; k = n % 10
    return "дней" if 10 < n < 20 else "день" if k == 1 else "дня" if 2 <= k <= 4 else "дней"


class Counters(C.Widget):
    CARD = "box"
    name = "counters"
    base = (300, 130)
    ROW = 62

    def rows(self):
        t0 = datetime.date.today()
        out = []
        for it in self.cfg.get("items", []):
            m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", (it.get("date") or "").strip())
            if not m or not it.get("title"):
                continue
            n = (datetime.date(int(m[1]), int(m[2]), int(m[3])) - t0).days
            unit = "сегодня" if n == 0 else plural(n) + " до" if n > 0 else plural(n)
            out.append((str(abs(n)), unit, it["title"], n > 0))
        return out

    def content_h(self):
        return 2 + 14 + 19 + 6 + max(1, len(self.rows())) * self.ROW + 10 + 2

    def state(self):
        return repr(self.rows())

    def draw(self, p):
        x0, y = 2 + 18, 2 + 14
        y += C.tag(p, self, x0, y, "СЧЁТЧИКИ") + 6
        for i, (num, unit, title, future) in enumerate(self.rows()):
            if i:
                p.setPen(QPen(QColor(255, 255, 255, 31), 1)); p.drawLine(QPointF(x0, y), QPointF(x0 + 260, y))
            p.setFont(C.font(40, 700, spacing=-1.5)); fm = p.fontMetrics()
            base = y + self.ROW / 2 + (fm.ascent() - fm.descent()) / 2     # line-height 1, по центру строки
            p.setPen(self.c("accent" if future else "glow"))
            nw = fm.horizontalAdvance(num)
            p.drawText(QPointF(x0 + max(92, nw) - nw, base), num)
            tx = x0 + max(92, nw) + 14
            ty = y + (self.ROW - 35) / 2
            C.line(p, tx, ty, unit, C.font(12, 600, C.UI), self.c("muted"))
            C.line(p, tx, ty + 16, title, C.font(14, 700, C.UI), self.c("fg"), x0 + 260 - tx)
            y += self.ROW
        if not self.rows():
            C.line(p, x0, y + 10, "Добавь дату в настройках виджета", C.font(12, 400, C.UI), self.c("muted"))


class Progress(C.Widget):
    CARD = "box"
    name = "progress"
    base = (300, 236)

    def values(self):
        n = datetime.datetime.now()
        d0 = datetime.datetime(n.year, n.month, n.day)
        w0 = d0 - datetime.timedelta(days=n.weekday())
        m0 = datetime.datetime(n.year, n.month, 1)
        m1 = datetime.datetime(n.year + (n.month == 12), n.month % 12 + 1, 1)
        y0, y1 = datetime.datetime(n.year, 1, 1), datetime.datetime(n.year + 1, 1, 1)
        part = lambda a, b: min(1, max(0, (n - a) / (b - a)))
        return {"day": part(d0, d0 + datetime.timedelta(days=1)), "week": part(w0, w0 + datetime.timedelta(days=7)),
                "month": part(m0, m1), "year": part(y0, y1)}

    def state(self):
        return tuple(int(x * 1000) for x in self.values().values())

    def draw(self, p):
        x0, y = 2 + 18, 2 + 14
        y += C.tag(p, self, x0, y, "ПРОГРЕСС") + 8
        v = self.values()
        W = 260
        track = C.color(self.theme.get("line", "rgba(255,255,255,0.14)"))
        for k, t in (("day", "День"), ("week", "Неделя"), ("month", "Месяц"), ("year", "Год")):
            if self.cfg.get(k) is False:
                continue
            f = C.font(13, 700, C.UI); p.setFont(f)
            C.line(p, x0, y + (34 - p.fontMetrics().height()) / 2, t, f, self.c("fg"))
            bx, bw = x0 + 62 + 10, W - 62 - 46 - 20
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(track)
            p.drawRoundedRect(QRectF(bx, y + 14, bw, 6), 3, 3)
            if v[k] > 0:
                g = QLinearGradient(bx, 0, bx + bw * v[k], 0)
                g.setColorAt(0, self.c("accent")); g.setColorAt(1, self.c("glow"))
                p.setBrush(QBrush(g)); p.drawRoundedRect(QRectF(bx, y + 14, bw * v[k], 6), 3, 3)
            f = C.font(15, 700); p.setFont(f)
            C.line(p, x0 + W - 46, y + (34 - p.fontMetrics().height()) / 2, "%d%%" % int(v[k] * 100), f,
                   self.c("glow"), 46, "right")
            y += 34
        if self.cfg.get("dots") is not False:
            y += 10
            d = (W - 25 * 3) / 26
            wk = min(51, int(v["year"] * 52))
            p.setPen(Qt.PenStyle.NoPen)
            for i in range(52):
                r = QRectF(x0 + (i % 26) * (d + 3), y + (i // 26) * (d + 3), d, d)
                if i == wk:                      # «сейчас» светится
                    g = self.c("glow", 0.35); p.setBrush(g)
                    p.drawEllipse(r.adjusted(-2.5, -2.5, 2.5, 2.5))
                p.setBrush(self.c("accent") if i < wk else self.c("glow") if i == wk else track)
                p.drawEllipse(r)


KINDS = {"links": Links, "counters": Counters, "progress": Progress}
