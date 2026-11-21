"""Garasu Classic: календарь с заметками (calendar.html). Размеры и отступы взяты из html."""
import os, json, datetime
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QColor
import __main__ as C

MONTHS = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь",
          "Ноябрь", "Декабрь"]
GEN = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября",
       "ноября", "декабря"]
X0, W = 18, 294                      # .box: margin 2 + padding 16, ширина содержимого 326 - 32
TOP, GRID = 18, 52                   # шапка высотой 24 и отступ 10 под ней
WD_H, DAY_H, GAP = 19, 30, 2


class Calendar(C.Widget):
    CARD = "box"
    name = "calendar"
    base = (330, 300)

    def __init__(self, *a, **k):
        t = datetime.date.today()
        self.view, self.sel, self.notes, self.raw, self.day = (t.year, t.month), None, {}, "", t
        super().__init__(*a, **k)

    # ---- данные
    def load(self):
        try:
            with open(os.path.join(C.ZDIR, self.NOTES), encoding="utf-8-sig") as f:
                t = f.read()
            if t != self.raw:
                self.raw, self.notes = t, json.loads(t)
        except Exception:
            pass
        today = datetime.date.today()
        if today != self.day:                    # наступил новый день
            self.day, self.view = today, (today.year, today.month)

    def days(self):
        y, m = self.view
        first = datetime.date(y, m, 1)
        start = first - datetime.timedelta(days=first.weekday())
        out = []
        for i in range(42):
            d = start + datetime.timedelta(days=i)
            if i >= 35 and d.month != m and d.day <= 7 and i % 7 == 0:
                break                            # шестая строка не нужна
            out.append(d)
        return out

    def label(self, key):
        d = datetime.date.fromisoformat(key)
        n = (d - datetime.date.today()).days
        return "сегодня" if n == 0 else "завтра" if n == 1 else "через %d дн." % n if 1 < n < 7 \
            else "%d %s" % (d.day, GEN[d.month - 1])

    def items(self):
        today = datetime.date.today().isoformat()
        out = []
        if self.sel and self.notes.get(self.sel):
            out.append((self.label(self.sel), self.notes[self.sel]))
        nxt = sorted(k for k in self.notes if k >= today and k != self.sel)
        for k in nxt[:2 if out else 3]:
            out.append((self.label(k), self.notes[k]))
        return out

    def list_top(self):
        rows = len(self.days()) // 7
        return GRID + WD_H + GAP + rows * (DAY_H + GAP) - GAP + 10 + 1 + 8

    def content_h(self):
        n = len(self.items())
        return self.list_top() + (n * 23 if n else 22) + 12 + 2

    def state(self):
        self.load()
        return (self.raw, self.view, self.sel, self.day)

    # ---- геометрия кнопок
    def cells(self):
        cw = W / 7
        top = GRID + WD_H + GAP
        for i, d in enumerate(self.days()):
            yield d, QRectF(X0 + (i % 7) * cw,
                            top + (i // 7) * (DAY_H + GAP), cw, DAY_H)

    def btns(self):
        add = QRectF(X0 + W - 24, TOP, 24, 24)
        nxt = QRectF(add.x() - 2 - 8 - 22, TOP, 22, 24)
        prv = QRectF(nxt.x() - 8 - 22, TOP, 22, 24)
        return {"prev": prv, "next": nxt, "add": add}

    def hot(self):
        b = self.btns()
        return [(b["prev"], 6), (b["next"], 6)] + [(r, 15) for _, r in self.cells()]

    # ---- рисование
    def draw(self, p):
        y, m = self.view
        b = self.btns()
        C.tag(p, self, X0, TOP + 5, "КАЛЕНДАРЬ")
        tw = C.text_w(p, "КАЛЕНДАРЬ")
        C.line(p, X0 + tw + 8, TOP + 3, "%s %d" % (MONTHS[m - 1], y), C.font(14, 700, C.UI), self.c("fg"),
               b["prev"].x() - X0 - tw - 16)
        for k, ch in (("prev", "‹"), ("next", "›")):
            C.line(p, b[k].x(), TOP + 1, ch, C.font(16, 700, "Segoe UI"), self.c("accent"), 22, "center")
        a = b["add"]
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(self.c("accent")); p.drawEllipse(a)
        C.line(p, a.x(), a.y() + 1, "+", C.font(17, 700, "Segoe UI"), self.c("pill"), 24, "center")
        cw = W / 7
        for i, s in enumerate(["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]):
            C.line(p, X0 + i * cw, GRID, s, C.font(11, 400, C.UI), self.c("muted"), cw, "center")
        today = datetime.date.today()
        k = self.slide_k()                       # листание: новая сетка въезжает на 20 px и проявляется
        p.save(); p.translate(self.sdir * 20 * (1 - k), 0)
        for d, r in self.cells():
            key = d.isoformat()
            col, wt, op = self.c("fg"), 500, 1.0
            if d == today:
                p.setPen(Qt.PenStyle.NoPen); p.setBrush(self.c("accent")); p.drawRoundedRect(r, 15, 15)
                col, wt = self.c("pill"), 700
            elif d.month != m:
                col, op = self.c("muted"), 0.6
            if key == self.sel:
                p.setPen(self.c("accent")); p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), 15, 15)
            p.setOpacity(op * k)
            p.setFont(C.font(13, wt)); p.setPen(col)
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, str(d.day))
            p.setOpacity(k)
            if self.notes.get(key):
                p.setPen(Qt.PenStyle.NoPen); p.setBrush(self.c("pill") if d == today else self.c("accent"))
                p.drawEllipse(QRectF(r.center().x() - 2, r.bottom() - 6, 4, 4))
        p.restore(); p.setOpacity(1)
        lt = self.list_top()
        p.fillRect(QRectF(X0, lt - 9, W, 1), QColor(255, 255, 255, 36))
        items = self.items()
        if not items:
            C.line(p, X0 + 2, lt + 3, "Заметок нет. Выбери день и нажми +", C.font(12, 400, C.UI),
                   self.c("muted"))
        for i, (when, text) in enumerate(items):
            ty = lt + i * 23 + 3
            C.line(p, X0 + 2, ty + 1, when, C.font(12, 700, C.UI), self.c("accent"), 74)
            C.line(p, X0 + 2 + 74 + 8, ty, text, C.font(13, 400, C.UI), self.c("fg"), W - 4 - 82)

    # ---- анимация листания (0.2 с)
    s0, sdir = 0, 1

    def slide_k(self):
        t = (C.time.time() - self.s0) / 0.2
        return 1.0 if t >= 1 else 1 - (1 - t) ** 3

    def animating(self):
        return super().animating() or self.slide_k() < 1

    def animate(self):
        if self.slide_k() < 1:
            self._cache = None
        super().animate()

    # ---- клики
    NOTES = "calendar_notes.json"

    def edit(self, key):
        """Поле ввода заметки прямо в виджете: Enter сохраняет (пусто = удалить), Esc закрывает."""
        from PyQt6.QtWidgets import QLineEdit
        if getattr(self, "_ed", None):
            self._ed.deleteLater()
        w = self

        class Ed(QLineEdit):
            def keyPressEvent(self, e):
                if e.key() == Qt.Key.Key_Escape:
                    w.close_ed()
                else:
                    super().keyPressEvent(e)

            def focusOutEvent(self, e):
                super().focusOutEvent(e); w.close_ed()
        z = self.zoom(); lt = self.list_top()
        e = self._ed = Ed(self)
        e.setGeometry(int(X0 * z), int((lt - 4) * z), int(W * z), int(28 * z))
        fg, acc = self.c("fg"), self.c("accent")
        e.setStyleSheet("QLineEdit{background:rgba(0,0,0,110);color:%s;border:1px solid %s;border-radius:%dpx;"
                        "padding:0 %dpx;font:%dpx '%s';}" % (fg.name(), acc.name(), int(9 * z), int(8 * z),
                                                             int(13 * z), C.UI))
        e.setPlaceholderText("Заметка: " + self.label(key))
        e.setText(self.notes.get(key, ""))
        e.returnPressed.connect(lambda: self.save_note(key, e.text()))
        e.show(); self.activateWindow(); e.setFocus()

    def close_ed(self):
        e, self._ed = getattr(self, "_ed", None), None
        if e:
            e.deleteLater()

    def save_note(self, key, text):
        self.load()
        notes = dict(self.notes)
        if text.strip():
            notes[key] = text.strip()
        else:
            notes.pop(key, None)
        data = json.dumps(dict(sorted(notes.items())), ensure_ascii=False, indent=1)
        with open(os.path.join(C.ZDIR, self.NOTES), "w", encoding="utf-8") as f:
            f.write(data)
        self.close_ed()
        self.place(); self._cache = None; self.update()

    def click(self, x, y, right=False):
        pt = QPointF(x, y)
        b = self.btns()
        if b["prev"].contains(pt) or b["next"].contains(pt):
            yy, mm = self.view
            mm += -1 if b["prev"].contains(pt) else 1
            self.view = (yy + (mm - 1) // 12, (mm - 1) % 12 + 1)
            if self.anim_on():
                self.s0, self.sdir = C.time.time(), (-1 if b["prev"].contains(pt) else 1)
                self.anim_t.start(16)
        elif b["add"].contains(pt):
            self.sel = self.sel or datetime.date.today().isoformat()
            self.edit(self.sel)
        else:
            for d, r in self.cells():
                if r.contains(pt):
                    self.sel = d.isoformat()
                    if right:
                        self.edit(self.sel)
        self.place(); self._cache = None; self.update()

    def rclick(self, x, y):
        """Правый клик по дню открывает его заметку (как в calendar.html); мимо дней — обычная панель."""
        if any(r.contains(QPointF(x, y)) for _, r in self.cells()):
            self.click(x, y, right=True)
            return True
        return False

    def halos(self):
        return [(self.btns()["add"], 12)]


class Visual(C.Widget):
    """visual.html: спектр звука от helper.pyw (96 чисел 30 раз в секунду), полоски с градиентом accent → glow."""
    name = "visual"
    base = (560, 150)

    def __init__(self, *a, **k):
        self.shown = [0.0] * 96
        super().__init__(*a, **k)
        from classic_d import Ws
        from classic_b import tools
        self.ws = Ws(tools().get("audio") or "ws://127.0.0.1:47631", lambda: None)
        from PyQt6.QtCore import QTimer
        self.vt = QTimer(self); self.vt.timeout.connect(self.step); self.vt.start(33)

    def step(self):
        quiet = C.time.time() - self.ws.last > 3 and max(self.shown) < 0.01
        if quiet:                                 # тишина: проверяем раз в полсекунды
            if self.vt.interval() != 500:
                self.vt.setInterval(500)
            return
        if self.vt.interval() != 33:
            self.vt.setInterval(33)
        self._cache = None; self.update()

    def state(self):
        return None

    def draw(self, p):
        from PyQt6.QtGui import QLinearGradient
        lv = self.ws.levels if C.time.time() - self.ws.last < 1.5 else [0.0] * 96
        n = max(8, min(96, int(self.cfg.get("bars") or 48)))
        w, h, x0, y0 = 556, 146, 2, 2
        gap = 3; bw = (w - gap * (n - 1)) / n
        g = QLinearGradient(0, y0 + h, 0, y0)
        g.setColorAt(0, self.c("accent")); g.setColorAt(1, self.c("glow"))
        p.setRenderHint(p.RenderHint.Antialiasing); p.setPen(Qt.PenStyle.NoPen); p.setBrush(g)
        o = float(self.cfg.get("opacity", 90)); p.setOpacity(o / 100 if o > 1 else o)
        mirror = self.cfg.get("mirror")
        for i in range(n):
            src = abs(i - (n - 1) / 2) / ((n - 1) / 2) if mirror else i / (n - 1)
            k = min(95, round(src * 95))
            sh = self.shown[i]
            self.shown[i] = sh + (lv[k] - sh) * (0.6 if lv[k] > sh else 0.18)   # быстро вверх, плавно вниз
            bh = max(3, self.shown[i] * (h - 4))
            r = min(bw / 2, 3)
            p.drawRoundedRect(QRectF(x0 + i * (bw + gap), y0 + h - bh, bw, bh), r, r)
        p.setOpacity(1)


KINDS = {"calendar": Calendar, "visual": Visual}
