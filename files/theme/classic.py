"""Garasu Classic: старые виджеты Гарасу (вид как в Zebar) на лёгком Qt вместо WebView2.

Читает те же файлы, что и Zebar-виджеты: ~/.glzr/zebar/ryoku/theme.json (цвета) и
widgets.json (включён ли виджет, место, масштаб, прозрачность), поэтому панель настроек и темы работают как раньше.
Включается файлом classic.on рядом (его ставит установщик или переключатель в панели «Виджеты»), запускает widgets.py.
Запуск:  python classic.py [--shot ПАПКА] [--quit СЕКУНД] [--check]
  --shot   нарисовать виджеты в картинки поверх обоев и выйти (для сравнения с Zebar)
  --check  только проверить, что нужные библиотеки есть (код выхода 0 — можно включать)
Ошибки пишутся в classic.log рядом. Если библиотек нет, сам возвращает Zebar.
"""
import os, sys, json, time
for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):   # numpy (оттенок фото): без этого
    os.environ.setdefault(_v, "1")                                         # OpenBLAS держит буфер под каждое ядро, ~+450 МБ
HERE = os.path.dirname(os.path.abspath(__file__))          # папка theme: тут же widgets.py и classic_*.py
LOG = os.path.join(HERE, "classic.log")
_pylib = os.path.join(os.path.dirname(HERE), "pylib")      # библиотеки рядом с установкой (у разработчика), иначе из venv
if os.path.isdir(_pylib):
    sys.path.insert(0, _pylib)
sys.path.insert(0, HERE)


def log(msg):
    try:
        if os.path.exists(LOG) and os.path.getsize(LOG) > 200_000:
            os.replace(LOG, LOG + ".old")
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg.rstrip() + "\n")
    except Exception:
        pass


def _excepthook(t, v, tb):
    """Ошибка внутри отрисовки не должна ронять все виджеты: PyQt6 без своего обработчика завершает программу."""
    import traceback
    log("".join(traceback.format_exception(t, v, tb)))


sys.excepthook = _excepthook

try:
    from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF, QRect, QPoint
    from PyQt6.QtGui import QPainter, QColor, QFont, QFontDatabase, QImage, QGuiApplication, QPen, QCursor, QBrush, QRadialGradient
    from PyQt6.QtWidgets import QApplication, QWidget
    if "--check" in sys.argv:
        import PyQt6.QtSvg, numpy, psutil                   # без них не будет погоды, монитора и оттенка фото
        import winrt.windows.media.control                  # плеер
        _app = QApplication(["garasu-check"])               # Qt реально запускается (плагин окон Windows на месте)
        _ok = bool(QGuiApplication.primaryScreen())
        print("ok" if _ok else "нет экрана")
        sys.exit(0 if _ok else 1)
except ImportError as e:
    if "--check" in sys.argv:
        print("нет библиотеки:", e)
        sys.exit(1)
    log("нет библиотеки (%s)" % e)
    import widgets as _W
    _W.classic_fail()
    sys.exit(1)

_MUTEX = None
if not any(a in sys.argv for a in ("--shot", "--check")):  # одна копия виджетов: вторую просто закрываем
    import ctypes
    _MUTEX = ctypes.windll.kernel32.CreateMutexW(None, False, "Local\\GarasuClassic")
    if ctypes.windll.kernel32.GetLastError() == 183:       # ERROR_ALREADY_EXISTS
        sys.exit(0)

ZDIR = os.path.join(os.path.expanduser("~"), ".glzr", "zebar", "ryoku")
import fonts


def read_json(name, default):
    try:
        with open(os.path.join(ZDIR, name), encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return default


def color(s, alpha=None):
    """'#rrggbb' или 'rgba(r, g, b, a)' -> QColor."""
    s = (s or "#ffffff").strip()
    if s.startswith("rgba"):
        r, g, b, a = [float(x) for x in s[s.index("(") + 1:-1].split(",")]
        c = QColor(int(r), int(g), int(b), int(a * 255))
    else:
        c = QColor(s)
    if alpha is not None:
        c.setAlphaF(alpha)
    return c


def save_cfg(name, **kv):
    if os.environ.get("CLASSIC_NOSAVE"):                       # для проверок: ничего не записывать
        print("save", name, kv); return
    try:
        sys.path.insert(0, HERE)
        import widgets as W
        cfg = W.load(); cfg[name].update(kv); W.apply(cfg, restart=False)
    except Exception:
        path = os.path.join(ZDIR, "widgets.json")
        cfg = read_json("widgets.json", {})
        if name in cfg:
            cfg[name].update(kv)
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            os.replace(tmp, path)


KEYS = ("fg", "muted", "accent", "accent2", "accent3", "glow", "pill", "line", "glass", "edge")


def palette(theme, light):
    """Цвета виджета как paint() в common.js: на светлом месте обоев текст тёмный, акценты притемнены."""
    pal = {k: color(theme.get(k)) for k in KEYS if theme.get(k)}
    if light:
        pal["fg"], pal["muted"], pal["line"] = QColor("#17171e"), QColor("#50505c"), QColor(0, 0, 0, 41)
        for k in ("accent", "accent2", "accent3", "glow"):
            if k in pal:
                c, f = pal[k], 0.34 if k == "glow" else 0.48
                pal[k] = QColor(round(c.red() * f), round(c.green() * f), round(c.blue() * f), c.alpha())
    return pal


def mix(a, b, t):
    return QColor(*[round(x + (y - x) * t) for x, y in zip(a.getRgb(), b.getRgb())])


def ease(t):
    """cubic-bezier(0.2, 0.8, 0.2, 1) примерно: быстрый старт, мягкая посадка."""
    return 1 - (1 - t) ** 3


def screen_for(rect):
    """Монитор, на котором центр окна, а если центр ни на одном (монитор отключили) — ближайший."""
    c = rect.center()
    s = QGuiApplication.screenAt(QPoint(int(c.x()), int(c.y())))
    if s is not None:
        return s
    best, dist = QGuiApplication.primaryScreen(), None
    for sc in QGuiApplication.screens():
        g = sc.geometry()
        dx = max(g.left() - c.x(), 0, c.x() - g.right())
        dy = max(g.top() - c.y(), 0, c.y() - g.bottom())
        if dist is None or dx * dx + dy * dy < dist:
            best, dist = sc, dx * dx + dy * dy
    return best


def fit_wall(img, w, h, cache):
    """Обои под монитор другого размера: заполнение с обрезкой по центру, как у Windows. Кэш на смену обоев."""
    if img.width() == w and img.height() == h:
        return img
    k = (img.cacheKey(), w, h)
    if k not in cache:
        s = img.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
        cache[k] = s.copy((s.width() - w) // 2, (s.height() - h) // 2, w, h)
    return cache[k]


WALL = {"key": None, "img": None}


def wall_lum(theme, rect):
    """Средняя яркость обоев под окном виджета (как contrast() в common.js, по картинке 16x16)."""
    key = (theme.get("wall"), theme.get("wallv"))
    if WALL["key"] != key:
        img = QImage(os.path.join(ZDIR, theme.get("wall") or "_wall.jpg"))
        WALL.update(key=key, img=None if img.isNull() else img)
    img = WALL["img"]
    if img is None:
        return 0
    scr = screen_for(rect).geometry()                         # на втором мониторе — свои координаты и размер
    sw, sh = scr.width(), scr.height()
    kx, ky = img.width() / sw, img.height() / sh
    rx, ry = rect.x() - scr.x(), rect.y() - scr.y()
    part = img.copy(int(rx * kx), int(ry * ky), int(rect.width() * kx), int(rect.height() * ky))
    part = part.scaled(16, 16, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
    tot = 0
    for y in range(16):
        for x in range(16):
            c = part.pixelColor(x, y)
            tot += 0.2126 * c.red() + 0.7152 * c.green() + 0.0722 * c.blue()
    return tot / 256 / 255


FAMILY = "Space Grotesk"


def load_font():
    global FAMILY
    fid = QFontDatabase.addApplicationFont(os.path.join(ZDIR, "SpaceGrotesk.ttf"))
    fams = QFontDatabase.applicationFontFamilies(fid) if fid >= 0 else []
    if fams:
        FAMILY = fams[0]


def font(px, weight=400, family=None, spacing=0.0):
    f = QFont(fonts.family(family) if family else FAMILY)     # на Windows 10 — шрифты Windows 10
    f.setPixelSize(max(1, int(round(px))))
    f.setWeight(QFont.Weight(weight))
    if spacing:
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
    f.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    f.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    return f


class Widget(QWidget):
    """Окно виджета. Рисует в «базовых» координатах (как в html, ширина base), а окно масштабирует."""
    name = "widget"
    base = (300, 200)        # размер окна при scale=100 (как sizes в widgets.py)
    poll = 1.0
    # тени под содержимым: (размытие, плотность, сдвиг вниз) в базовых пикселях.
    # Виджет без карточки в common.css: drop-shadow(0 1px 2px .6) и drop-shadow(0 0 14px .42)
    SHADOWS = ((14, 0.42, 0), (2, 0.60, 1))

    def __init__(self, cfg, theme):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
                         | Qt.WindowType.WindowStaysOnBottomHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle("Garasu Classic · " + self.name)
        self.cfg, self.theme = cfg, theme
        self._cache, self.hover, self.light = None, None, False
        self.place()
        self.pal = self.pal_from = palette(theme, False)
        self.tw0 = 0                                   # начало плавной смены цветов
        self.born = None                               # начало анимации появления
        self.delay = 0.06 + __import__("random").random() * 0.22
        self.setMouseTracking(True)
        self.anim_t = QTimer(self); self.anim_t.timeout.connect(self.animate)
        self.contrast()

    def place(self):
        k = self.cfg.get("scale", 100) / 100
        w, h = self.size_for(self.cfg)
        h = max(h, self.content_h())
        x, y, w, h = int(self.cfg.get("x", 0)), int(self.cfg.get("y", 0)), int(w * k), int(h * k)
        r = QRect(x, y, w, h)
        if QGuiApplication.screenAt(r.center()) is None:       # монитор отключили: показать на ближайшем
            a = screen_for(r).availableGeometry()              # (в настройках место не меняется — вернётся,
            x = max(a.left(), min(x, a.right() - w))           #  когда монитор снова подключат)
            y = max(a.top(), min(y, a.bottom() - h))
        self.setGeometry(x, y, w, h)

    @staticmethod
    def allcfg():
        """all из widgets.json; перечитывается, только когда файл изменился (зовётся при каждой отрисовке)."""
        try:
            m = os.path.getmtime(os.path.join(ZDIR, "widgets.json"))
        except OSError:
            m = 0
        c = Widget.__dict__.get("_all")
        if c is None or c[0] != m:
            Widget._all = c = (m, read_json("widgets.json", {}).get("all") or {})
        return c[1]

    def anim_on(self):
        return self.allcfg().get("anim", True) is not False

    # ---- живые настройки: тема, место, масштаб, прозрачность (их меняет панель настроек)
    def reconfig(self, cfg, theme):
        if cfg != self.cfg:
            moved = any(cfg.get(k) != self.cfg.get(k) for k in ("x", "y", "scale", "cols", "rows"))
            self.cfg = cfg
            if moved and not getattr(self, "edrag", None):
                self.place()
            self._cache = None; self._st = object()
        if theme != self.theme:
            self.theme = theme
            self.contrast(force=True)

    def contrast(self, force=False):
        light = False
        try:
            if self.allcfg().get("adapt", True) is not False and self.theme.get("wall") and not self.cfg.get("card"):
                lum = wall_lum(self.theme, self.geometry())
                light = lum > 0.52 if self.light else lum > 0.60     # с запасом, чтобы не мигало
        except Exception:
            light = False
        if light != self.light or force:
            self.light = light
            self.pal_from = {k: self.c(k) for k in self.pal}
            self.pal = palette(self.theme, light)
            self.tw0 = time.time() if self.anim_on() and self.isVisible() else 0
            self._cache = None; self.update()
            if self.tw0:
                self.anim_t.start(16)

    # ---- анимации: появление (0.6 с) и смена цветов (0.7 с), таймер работает только пока они идут
    def animating(self):
        t = time.time()
        return (self.born is not None and t - self.born < self.delay + 0.6) or (self.tw0 and t - self.tw0 < 0.7)             or (self.hover is not None and t - getattr(self, "hv0", 0) < 0.15) or self.press_busy()             or (getattr(self, "halo", None) is not None and t - getattr(self, "ha0", 0) < 0.28)

    def animate(self):
        if self.tw0 or self.hover is not None or getattr(self, "prs", None) or getattr(self, "halo", None) is not None:
            self._cache = None
        if not self.animating():
            self.anim_t.stop(); self.tw0 = 0; self._cache = None
        self.update()

    def showEvent(self, e):
        if self.born is None:
            self.born = time.time() if self.anim_on() else 0
            if self.born:
                self.anim_t.start(16)

    # ---- подсветка кнопок под мышкой (как button:hover в html)
    def hot(self):
        """Кнопки виджета: список (rect, радиус) в базовых координатах."""
        return []

    def hot_at(self, x, y):
        for i, (r, rad) in enumerate(self.hot()):
            if r.contains(QPointF(x, y)):
                return i
        return None

    # ---- нажатие (как .click:active / button:active: scale(.96) за 0.12 с) и свечение главных кнопок
    def halos(self):
        """Главные круглые кнопки (play, «+»): вокруг них свечение акцента при наведении и нажатии.
        Список (rect, радиус) в базовых координатах."""
        return []

    def press_zones(self):
        """Где нажатие сжимает кнопку: (где нажать, что сжать, масштаб) в базовых координатах."""
        return [(r, r, 0.96) for r, _ in self.hot()] + [(r, r, 0.96) for r, _ in self.halos()]

    def press_k(self):
        """Насколько кнопка сейчас сжата: 0 — нет, 1 — полностью."""
        s = getattr(self, "prs", None)
        if not s:
            return 0.0
        t = time.time()
        if s["up"] is None:
            return min(1.0, (t - s["t"]) / 0.12)
        k = s["k"] * (1 - (t - s["up"]) / 0.12)
        if k <= 0:
            self.prs = None
            return 0.0
        return k

    def press_busy(self):
        s = getattr(self, "prs", None)
        return bool(s) and time.time() - (s["up"] or s["t"]) < 0.14

    def press_start(self, x, y):
        if not self.anim_on():
            return
        for hit, rect, sc in self.press_zones():
            if hit.contains(QPointF(x, y)):
                self.prs = {"r": QRectF(rect), "s": sc, "t": time.time(), "up": None, "k": 0}
                self.anim_t.start(16); self._cache = None; self.update()
                return

    def press_end(self):
        s = getattr(self, "prs", None)
        if s and s["up"] is None:
            s["k"] = self.press_k(); s["up"] = time.time()
            self.anim_t.start(16)

    def press_apply(self, body):
        """Сжать нажатую кнопку прямо в готовой картинке содержимого (стекло рисуется отдельно)."""
        k = self.press_k()
        if k <= 0:
            return
        z, s = self.zoom(), self.prs
        r = s["r"]
        pr = QRectF(r.x() * z, r.y() * z, r.width() * z, r.height() * z).adjusted(-1, -1, 1, 1).toAlignedRect()
        pr = pr.intersected(body.rect())
        sub = body.copy(pr)
        q = QPainter(body)
        q.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        q.fillRect(pr, Qt.GlobalColor.transparent)
        q.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        q.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        sc = 1 - (1 - s["s"]) * ease(k)
        c = QPointF(pr.center())
        q.translate(c); q.scale(sc, sc); q.translate(-c)
        q.drawImage(QPointF(pr.topLeft()), sub); q.end()

    def draw_halo(self, p):
        """button.play:hover — кольцо 4px (на нажатии 7px) и мягкое свечение акцента вокруг кнопки."""
        i = getattr(self, "halo", None)
        hs = self.halos()
        if i is None or i >= len(hs):
            return
        r, rad = hs[i]
        k = min(1.0, (time.time() - getattr(self, "ha0", 0)) / 0.28) if self.anim_on() else 1.0
        pk = self.press_k() if getattr(self, "prs", None) and self.prs["r"] == r else 0
        a = self.c("accent")
        p.setPen(Qt.PenStyle.NoPen)
        g = QRadialGradient(r.center() + QPointF(0, 3 - pk), r.width() / 2 + 16)
        c0, c1 = QColor(a), QColor(a)
        c0.setAlphaF(0.42 * 0.55 * k); c1.setAlphaF(0)
        g.setColorAt(r.width() / 2 / (r.width() / 2 + 16), c0); g.setColorAt(1, c1)
        p.setBrush(QBrush(g)); p.drawEllipse(r.center(), r.width() / 2 + 16, r.height() / 2 + 16)
        w = (4 + 3 * pk) * k
        ring = QColor(a); ring.setAlphaF(0.16 * k)
        p.setBrush(ring)
        p.drawRoundedRect(r.adjusted(-w, -w, w, w), rad + w, rad + w)

    def mouseMoveEvent(self, e):
        z = self.zoom()
        bx, by = e.position().x() / z, e.position().y() / z
        h = self.hot_at(bx, by)
        if getattr(self, "edrag", None):
            self.drag_to(e.globalPosition()); return
        if h != self.hover:
            self.hover = h; self._cache = None; self.update()
            if h is not None and self.anim_on():           # подсветка проявляется за 150 мс
                self.hv0 = time.time(); self.anim_t.start(16)
        ha = next((i for i, (r, _) in enumerate(self.halos()) if r.contains(QPointF(bx, by))), None)
        if ha != getattr(self, "halo", None):
            self.halo = ha; self.ha0 = time.time(); self._cache = None; self.update()
            if ha is not None:
                self.anim_t.start(16)
        if h is None and ha is not None:
            h = -1                                          # для курсора-руки
        if self.editing() and h is None:
            W, H, lx, ly = self.width(), self.height(), e.position().x(), e.position().y()
            edge = self.edge_at(lx, ly)
            cur = Qt.CursorShape.SizeFDiagCursor if self.selected() and lx >= W - self.GRIP and ly >= H - self.GRIP \
                else Qt.CursorShape.PointingHandCursor if self.selected() and lx >= W - self.GEAR and ly <= self.GEAR \
                else Qt.CursorShape.SizeHorCursor if edge == "w" else Qt.CursorShape.SizeVerCursor if edge == "h" \
                else Qt.CursorShape.SizeAllCursor
        else:
            cur = Qt.CursorShape.PointingHandCursor if h is not None else Qt.CursorShape.ArrowCursor
        self.setCursor(cur)

    def leaveEvent(self, e):
        if self.hover is not None or getattr(self, "halo", None) is not None:
            self.hover = None; self.halo = None; self._cache = None; self.update()

    def draw_hover(self, p):
        hs = self.hot()
        if self.hover is not None and self.hover < len(hs):
            r, rad = hs[self.hover]
            p.setPen(Qt.PenStyle.NoPen)
            k = min(1.0, (time.time() - getattr(self, "hv0", 0)) / 0.15)
            p.setBrush(QColor(0, 0, 0, int(26 * k)) if self.light else QColor(255, 255, 255, int(31 * k)))
            p.drawRoundedRect(r, rad, rad)

    def size_for(self, cfg):
        return self.base

    def content_h(self):
        """Высота содержимого в базовых пикселях, если оно выше окна из widgets.py (окно подрастёт)."""
        return 0

    # ---- режим правки (как drag.pyw у Zebar): включён, пока открыта панель «Виджеты» (all.edit).
    # Виджет тащится мышкой, квадратик в правом нижнем углу меняет размер, шестерёнка открывает настройки.
    # Привязка к краям экрана и к другим виджетам; Shift её отключает. Место и размер пишутся в widgets.json.
    GRIP, GEAR, TH = 18, 24, 12
    SEL = {"w": None}                     # выделенный виджет (один на все окна)
    WINS = []                             # все окна, для привязки

    def editing(self):
        return bool(self.allcfg().get("edit"))

    GROUP = set()                             # ещё выделенные с Ctrl: двигаются вместе с главным

    def selected(self):
        return Widget.SEL["w"] is self or self in Widget.GROUP

    def group(self):
        """Остальные виджеты группы (без себя)."""
        return [w for w in Widget.GROUP | {Widget.SEL["w"]} if w is not None and w is not self and w.isVisible()]

    def select(self, on=True):
        old = Widget.SEL["w"]
        Widget.SEL["w"] = self if on else None
        for w in {old, self}:
            if w is not None:
                w.update()
        if on:
            if not hasattr(Widget, "_watch"):
                Widget._watch = QTimer(); Widget._watch.timeout.connect(Widget.watch_outside)
            Widget._watch.start(60)

    @staticmethod
    def watch_outside():
        """Клик мимо всех виджетов или Esc снимает выделение (как в drag.pyw)."""
        w = Widget.SEL["w"]
        import ctypes
        u = ctypes.windll.user32
        down = bool(u.GetAsyncKeyState(0x01) & 0x8000) or bool(u.GetAsyncKeyState(0x02) & 0x8000)
        if w is None or not w.editing() or u.GetAsyncKeyState(0x1B) & 0x8000 or \
                (down and not any(o.isVisible() and o.geometry().contains(QCursor.pos()) for o in Widget.WINS)):
            Widget.SEL["w"] = None
            Widget._watch.stop()
            for o in list(Widget.GROUP) + [w]:
                if o is not None:
                    o.update()
            Widget.GROUP.clear()

    def grab_zones(self):
        """Где нажатие в режиме правки не двигает окно (кнопки, ползунки): базовые координаты."""
        return [r for r, _ in self.hot()]

    def mousePressEvent(self, e):
        z = self.zoom()
        x, y = e.position().x() / z, e.position().y() / z
        self.edrag = None
        if e.button() == Qt.MouseButton.LeftButton:
            self.press_start(x, y)
        if e.button() == Qt.MouseButton.RightButton:
            if self.rclick(x, y):
                return
            if not self.editing():
                from classic_b import tools, run
                if tools().get("panel"):
                    run(tools()["panel"], self.name)
            return
        if e.button() == Qt.MouseButton.LeftButton and self.editing() \
                and not any(r.contains(QPointF(x, y)) for r in self.grab_zones()):
            lx, ly, W, H = e.position().x(), e.position().y(), self.width(), self.height()
            if self.selected() and lx >= W - self.GEAR and ly <= self.GEAR:
                from classic_b import tools, run
                if tools().get("panel"):
                    run(tools()["panel"], self.name)
                return
            self.setFocusPolicy(Qt.FocusPolicy.StrongFocus); self.activateWindow(); self.setFocus()
            if e.modifiers() & Qt.KeyboardModifier.ControlModifier:      # Ctrl+клик: добавить или убрать из группы
                cur = Widget.SEL["w"]
                if cur is None:
                    self.select()
                elif cur is self:
                    pass
                elif self in Widget.GROUP:
                    Widget.GROUP.discard(self)
                else:
                    Widget.GROUP.add(self)
                self.update(); return
            kind = "size" if self.selected() and lx >= W - self.GRIP and ly >= H - self.GRIP \
                else self.edge_at(lx, ly) or "move"
            if not self.selected():
                Widget.GROUP.clear()
                for o in Widget.WINS:
                    o.update()
            elif Widget.SEL["w"] is not self:              # тащим члена группы: он становится главным
                Widget.GROUP.discard(self); Widget.GROUP.add(Widget.SEL["w"])
            self.select()
            self.gpos0 = {o: o.pos() for o in self.group()}
            self.edrag = {"kind": kind, "g0": e.globalPosition(), "pos0": self.pos(), "moved": False,
                         "scale0": self.cfg.get("scale", 100), "w0": W, "x": x, "y": y,
                         "edge0": {k: self.cfg.get(k) for k in self.EDGE_KEYS}}
            return
        self.click(x, y)

    # ---- края рамки (только у виджетов с EDGES, сейчас у ярлыков): правый край тянет ширину,
    # нижний — высоту, каждую отдельно. Уголок справа внизу по-прежнему меняет масштаб целиком.
    EDGES, EDGE, EDGE_KEYS = False, 9, ()

    def edge_at(self, lx, ly):
        """'w' — правый край, 'h' — нижний край выделенного виджета, None — не край (пиксели окна)."""
        if not (self.EDGES and self.selected()):
            return None
        W, H = self.width(), self.height()
        if lx >= W - self.EDGE and ly > self.GEAR:
            return "w"
        if ly >= H - self.EDGE:
            return "h"
        return None

    def edge_drag(self, kind, dx, dy):
        """Сдвиг края на dx/dy базовых пикселей от начала: виджет сам решает, что поменять. Вернуть dict или None."""
        return None

    # ---- привязка как в Figma: края и центры экрана и соседей, равные отступы; направляющие видны
    def others(self):
        moving = getattr(self, "gpos0", {}) if getattr(self, "edrag", None) else {}
        return [o.geometry() for o in Widget.WINS if o is not self and o.isVisible() and o not in moving]

    @staticmethod
    def span(g, ax):
        """(начало, конец) прямоугольника по оси: ax 0 = x, 1 = y."""
        return (g.x(), g.x() + g.width()) if ax == 0 else (g.y(), g.y() + g.height())

    def snap_axis(self, pos, size, ax, cross):
        """Лучшее положение по оси ax и направляющие к нему. cross = (начало, конец) по другой оси."""
        sp = self.span
        a0, a1 = sp(self.drag_screen().availableGeometry(), ax)
        others = self.others()
        lines = [(a0, "start", None), (a1, "end", None), ((a0 + a1) / 2, "center", None)]
        for g in others:
            l, r = sp(g, ax)
            lines += [(l, "start", g), (r, "end", g), (r, "start", g), (l, "end", g), ((l + r) / 2, "center", g)]
        best, dist, guides = pos, self.TH + 0.5, []
        for v, kind, g in lines:
            cand = v if kind == "start" else v - size if kind == "end" else v - size / 2
            dd = abs(cand - pos)
            if dd < dist - 0.5:
                best, dist, guides = round(cand), dd, []
            if abs(dd - dist) <= 0.5:
                guides.append(("line", ax, v, g))
        # равные отступы: сосед в одном ряду и промежуток, который уже есть между другими виджетами
        def overlap(c1, c2):
            return min(c1[1], c2[1]) - max(c1[0], c2[0]) > 0
        row = [g for g in others if overlap(cross, sp(g, 1 - ax))]
        gaps = []
        for g1 in others:
            for g2 in others:
                gap = sp(g2, ax)[0] - sp(g1, ax)[1]
                if 4 <= gap <= 300 and overlap(sp(g1, 1 - ax), sp(g2, 1 - ax)):
                    gaps.append((gap, g1, g2))
        for g in row:
            l, r = sp(g, ax)
            for gap, g1, g2 in gaps:
                for cand, seg in ((r + gap, (r, r + gap)), (l - gap - size, (l - gap, l))):
                    dd = abs(cand - pos)
                    if dd < dist - 0.5:
                        best, dist = round(cand), dd
                        guides = [("gap", ax, seg, g, (sp(g1, ax)[1], sp(g2, ax)[0], g1, g2), gap)]
        if dist > self.TH:
            return pos, []
        return best, guides

    def drag_screen(self):
        """Монитор, к краям которого липнет виджет: тот, где сейчас мышь (виджет можно унести на второй)."""
        return QGuiApplication.screenAt(QCursor.pos()) or screen_for(self.geometry())

    def drag_to(self, g):
        d = self.edrag
        dx, dy = g.x() - d["g0"].x(), g.y() - d["g0"].y()
        if not d["moved"] and abs(dx) + abs(dy) < 4:
            return
        d["moved"] = True
        free = bool(QApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier) \
            or self.allcfg().get("snap", True) is False
        guides = []
        if d["kind"] in ("w", "h"):
            k = max(0.2, d["scale0"] / 100)
            ch = self.edge_drag(d["kind"], dx / k, dy / k)
            if ch and any(self.cfg.get(a) != b for a, b in ch.items()):
                self.cfg = dict(self.cfg, **ch)
                self.place(); self._cache = None; self.update()
            return
        if d["kind"] == "move":
            vg = QGuiApplication.primaryScreen().virtualGeometry()       # все мониторы вместе
            nx = max(vg.left() - 40, min(vg.right() - 60, round(d["pos0"].x() + dx)))
            ny = max(vg.top(), min(vg.bottom() - 40, round(d["pos0"].y() + dy)))
            W, H = self.width(), self.height()
            if not free:
                nx, gx = self.snap_axis(nx, W, 0, (ny, ny + H))
                ny, gy = self.snap_axis(ny, H, 1, (nx, nx + W))
                guides = gx + gy
            self.move(nx, ny)
            for o, p0 in getattr(self, "gpos0", {}).items():
                o.move(p0.x() + nx - d["pos0"].x(), p0.y() + ny - d["pos0"].y())
        else:
            ns = d["scale0"] * (d["w0"] + dx) / d["w0"]
            snapped = False
            if not free:                                        # правый или нижний край к краям соседей и экрана
                sc = max(1, self.cfg.get("scale", 100))
                best = self.TH + 0.5
                for ax, kk, org in ((0, self.width() / sc, self.x()), (1, self.height() / sc, self.y())):
                    for gg in self.others() + [screen_for(self.geometry()).availableGeometry()]:
                        for v in self.span(gg, ax):
                            c = (v - org) / kk
                            if abs((c - ns) * kk) < best:
                                best, ns, snapped = abs((c - ns) * kk), c, True
                                guides = [("line", ax, v, gg)]
                if not snapped:
                    ns = round(ns / 5) * 5                      # ровные шаги по 5%
            ns = max(40, min(200, round(ns)))
            if ns != self.cfg.get("scale", 100):
                self.cfg = dict(self.cfg, scale=ns)
                self.place(); self._cache = None; self.update()
        Guides.show_for(self, guides)

    def mouseReleaseEvent(self, e):
        d, self.edrag = getattr(self, "edrag", None), None
        self.press_end()
        Guides.show_for(self, [])
        if not d:
            return
        if not d["moved"]:                                      # просто клик: обычное действие виджета
            self.click(d["x"], d["y"])
        elif d["kind"] == "move":
            g0 = dict(getattr(self, "gpos0", {}), **{}); g0[self] = d["pos0"]
            Widget.UNDO.append((None, [(o, {"x": p0.x(), "y": p0.y()}) for o, p0 in g0.items()]))
            for o in g0:
                save_cfg(o.name, x=o.x(), y=o.y())
                o.cfg = dict(o.cfg, x=o.x(), y=o.y())
                o._cache = None; o.contrast(); o.update()     # под виджетом другие обои (или другой монитор)
        elif d["kind"] in ("w", "h"):
            Widget.UNDO.append((self, d["edge0"]))
            save_cfg(self.name, **{k: self.cfg.get(k) for k in self.EDGE_KEYS})
        else:
            Widget.UNDO.append((self, {"scale": d["scale0"]}))
            save_cfg(self.name, scale=self.cfg["scale"])

    # ---- клавиатура в режиме правки: стрелки двигают выделенный виджет на 1 px (Shift — на 10),
    # Ctrl+Z отменяет последний сдвиг или изменение размера, Esc снимает выделение
    UNDO = []

    def keyPressEvent(self, e):
        if not (self.editing() and self.selected()):
            return
        k, mods = e.key(), e.modifiers()
        step = 10 if mods & Qt.KeyboardModifier.ShiftModifier else 1
        dxy = {Qt.Key.Key_Left: (-step, 0), Qt.Key.Key_Right: (step, 0),
               Qt.Key.Key_Up: (0, -step), Qt.Key.Key_Down: (0, step)}.get(k)
        if dxy and mods & Qt.KeyboardModifier.ControlModifier and self.group():
            # Ctrl+стрелка: выровнять группу по краю главного (← левый, → правый, ↑ верх, ↓ низ)
            Widget.UNDO.append((None, [(o, {"x": o.x(), "y": o.y()}) for o in self.group()]))
            for o in self.group():
                nx = self.x() if k == Qt.Key.Key_Left else self.x() + self.width() - o.width()                     if k == Qt.Key.Key_Right else o.x()
                ny = self.y() if k == Qt.Key.Key_Up else self.y() + self.height() - o.height()                     if k == Qt.Key.Key_Down else o.y()
                o.move(nx, ny); o.cfg = dict(o.cfg, x=nx, y=ny); save_cfg(o.name, x=nx, y=ny)
        elif dxy:
            ws = [self] + self.group()
            if not getattr(self, "_nudge", None):              # одна запись отмены на серию нажатий
                Widget.UNDO.append((None, [(o, {"x": o.x(), "y": o.y()}) for o in ws]))
                self._nudge = QTimer(self); self._nudge.setSingleShot(True)
                self._nudge.timeout.connect(self.nudge_save)
            for o in ws:
                o.move(o.x() + dxy[0], o.y() + dxy[1])
                o.cfg = dict(o.cfg, x=o.x(), y=o.y())
            self._nudge.start(500)
        elif k == Qt.Key.Key_Z and mods & Qt.KeyboardModifier.ControlModifier:
            Widget.undo()
        elif k == Qt.Key.Key_Escape:
            self.select(False)

    def nudge_save(self):
        for o in [self] + self.group():
            save_cfg(o.name, x=o.x(), y=o.y())
        self._nudge = None

    @staticmethod
    def undo():
        if not Widget.UNDO:
            return
        w, old = Widget.UNDO.pop()
        for w, old in (old if w is None else [(w, old)]):
            w.cfg = dict(w.cfg, **old)
            w.place(); w._cache = None; w.update()
            save_cfg(w.name, **old)

    def draw_edit(self, p):
        """Рамка режима правки поверх виджета (в пикселях окна, как .frame/.grip/.gear в common.css)."""
        W, H = self.width(), self.height()
        p.setOpacity(1); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(0, 0, W, H, QColor(0, 0, 0, 1))             # чтобы окно ловило мышь и на пустых местах
        sel = self.selected()
        acc, pill = self.c("accent"), self.c("pill")
        pen = QPen(acc, 2, Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.setBrush(QColor(acc.red(), acc.green(), acc.blue(), 20) if sel else Qt.BrushStyle.NoBrush)
        p.setOpacity(1 if sel else 0.45)
        p.drawRoundedRect(QRectF(2, 2, W - 4, H - 4), 12, 12)
        if sel:
            p.setPen(QPen(pill, 2)); p.setBrush(acc)
            p.drawRoundedRect(QRectF(W - 17, H - 17, 15, 15), 4, 4)
            if self.EDGES:                         # ручки-полоски посередине правого и нижнего края
                p.drawRoundedRect(QRectF(W - 7, H / 2 - 14, 6, 28), 3, 3)
                p.drawRoundedRect(QRectF(W / 2 - 14, H - 7, 28, 6), 3, 3)
            p.drawRoundedRect(QRectF(W - self.GEAR + 1, 1, self.GEAR - 2, self.GEAR - 2), 7, 7)
            p.setFont(font(12, 400, "Segoe Fluent Icons")); p.setPen(pill)
            p.drawText(QRectF(W - self.GEAR + 1, 1, self.GEAR - 2, self.GEAR - 2),
                       Qt.AlignmentFlag.AlignCenter, "\ue713")

    def click(self, x, y):
        pass

    def rclick(self, x, y):
        """Свой правый клик виджета (у календаря — заметка дня). True — обработан, панель не открывать."""
        return False

    def zoom(self):
        return max(0.2, self.width() / (self.base_w() + 4))   # как fit() в common.js

    def base_w(self):
        return self.size_for(self.cfg)[0]

    def c(self, key, alpha=None):
        c = self.pal.get(key)
        if c is None:
            c = color(self.theme.get(key))
        elif self.tw0 and key in self.pal_from:
            c = mix(self.pal_from[key], c, ease(min(1, (time.time() - self.tw0) / 0.7)))
        c = QColor(c)
        if alpha is not None:
            c.setAlphaF(alpha)
        return c

    def frame(self):
        """Готовая картинка виджета: содержимое плюс тень под ним (как drop-shadow в common.css)."""
        w, h = self.width(), self.height()
        body = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied); body.fill(0)
        p = QPainter(body)
        p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        z = self.zoom(); p.scale(z, z)
        self.draw_hover(p)
        self.draw(p); p.end()
        self.press_apply(body)
        if getattr(self, "halo", None) is not None:     # свечение подкладывается под готовые кнопки
            p = QPainter(body); p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationOver)
            p.scale(z, z); self.draw_halo(p); p.end()
        card = self.card_rect()
        out = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied); out.fill(0)
        p = QPainter(out)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        # две тени: широкая мягкая (14px, .42) и плотная рядом (2px, .6, вниз на 1px)
        op = self.cfg.get("opacity", 100) / 100
        # на светлых обоях вместо тени светлый ореол: drop-shadow(0 0 10px rgba(255,255,255,.55))
        shadows = ((10, 0.55, 0),) if self.light and self.SHADOWS else self.SHADOWS
        col = QColor(255, 255, 255) if self.light else None
        if card is not None:                     # .card-bg: тень карточки 0 18px 46px .24, у текста только text-shadow
            g = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied); g.fill(0)
            q = QPainter(g); q.scale(z, z); draw_glass(q, self, card, self.radius()); q.end()
            # окно не больше карточки (отступ 2 px): тень 0 18px 46px обрезалась бы краем окна в прямую полосу,
            # поэтому только тонкий мягкий контур, целиком внутри окна
            p.setOpacity(0.35 * op); p.drawImage(0, 0, shadow(g, 2 * z))
            p.setOpacity(op); p.drawImage(0, 0, g)
            shadows, col = ((8, 0.22, 1),), None
        for blur, alpha, dy in shadows:
            p.setOpacity(alpha * op)
            p.drawImage(QPointF(0, dy * z), shadow(body, blur * z, col))
        p.setOpacity(op)
        p.drawImage(0, 0, body); p.end()
        return out

    # ---- стеклянная карточка (.card-bg)
    CARD = None                              # "box": карточка во всё окно, если в настройках card не false

    def card_rect(self):
        if self.CARD == "box" and self.cfg.get("card") is not False:
            z = self.zoom()
            return QRectF(2, 2, self.width() / z - 4, self.height() / z - 4)
        return None

    def radius(self):
        return (self.allcfg().get("radius") or 26)

    WALL = {}

    def wall_blur(self, r):
        """Кусок обоев (theme.wall, уже размытых) точно под прямоугольником r (базовые координаты)."""
        name = self.theme.get("wall")
        if not name:
            return None
        key = (name, self.theme.get("wallv", 0))
        if Widget.WALL.get("key") != key:
            img = QImage(os.path.join(ZDIR, name))
            if img.isNull():
                return None
            sw, sh = self.theme.get("screen", [1920, 1080])
            old = Widget.WALL.get("img")              # прошлые обои: стекло плавно перейдёт с них
            Widget.WALL = {"key": key, "old": old, "t": time.time(), "img": img.scaled(sw, sh, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                                          Qt.TransformationMode.SmoothTransformation)}
        z = self.zoom(); g = self.geometry()
        scr = screen_for(g).geometry()                 # второй монитор: обои подогнаны под его размер
        gx, gy = g.x() - scr.x(), g.y() - scr.y()
        sized = Widget.WALL.setdefault("sized", {})
        self._wall_old = None
        old = Widget.WALL.get("old")
        dt = time.time() - Widget.WALL.get("t", 0)
        if old is not None and dt >= 0.7:
            Widget.WALL["old"] = None
        elif old is not None and self.anim_on():
            old = fit_wall(old, scr.width(), scr.height(), sized)
            self._wall_old = (old.copy(int(gx + r.x() * z), int(gy + r.y() * z), int(r.width() * z),
                                       int(r.height() * z)), dt / 0.7)
        return fit_wall(Widget.WALL["img"], scr.width(), scr.height(), sized).copy(
            int(gx + r.x() * z), int(gy + r.y() * z), int(r.width() * z), int(r.height() * z))

    def paintEvent(self, e):
        if self._cache is None:
            self._cache = self.frame()
        p = QPainter(self)
        if self.born:                                  # появление: проявление со сдвигом снизу и лёгким ростом
            t = (time.time() - self.born - self.delay) / 0.6
            if t < 1:
                k = ease(max(0.0, t))
                p.setOpacity(k)
                p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                w, h = self.width(), self.height()
                p.translate(w / 2, h / 2 + 14 * self.zoom() * (1 - k))
                sc = 0.98 + 0.02 * k; p.scale(sc, sc); p.translate(-w / 2, -h / 2)
        p.drawImage(0, 0, self._cache)
        if self.editing():
            p.resetTransform(); self.draw_edit(p)
        p.end()

    def state(self):
        """Что показывает виджет сейчас; перерисовка только когда это изменилось."""
        return None

    def tick(self):
        st = self.state()
        if st != getattr(self, "_st", object()):
            self._st, self._cache = st, None
            self.update()

    def draw(self, p):
        pass


def shadow(img, blur, col=None):
    """Размытая копия по форме картинки (чёрная, а на светлых обоях белая).
    Размытие дешёвое: уменьшить и растянуть обратно (дважды)."""
    w, h = img.width(), img.height()
    m = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied); m.fill(0)
    p = QPainter(m); p.drawImage(0, 0, img)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    p.fillRect(0, 0, w, h, col or QColor(0, 0, 0)); p.end()
    if blur < 1:
        return m
    k = max(1.0, blur / 1.5)
    sm = Qt.TransformationMode.SmoothTransformation
    for _ in range(2):
        m = m.scaled(max(1, int(w / k)), max(1, int(h / k)), Qt.AspectRatioMode.IgnoreAspectRatio, sm)
        m = m.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio, sm)
    return m


def text_w(p, s):
    return p.fontMetrics().horizontalAdvance(s)


class Clock(Widget):
    name = "clock"
    SHADOWS = ((8, 0.22, 1),)          # у часов в html только text-shadow 0 1px 8px .22
    SIZES = {"line": (1100, 170), "stack": (430, 350), "analog": (300, 330)}
    DAYS = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
    GEN = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября",
           "октября", "ноября", "декабря"]

    def size_for(self, cfg):
        return self.SIZES.get(cfg.get("style", "stack"), self.SIZES["stack"])

    def state(self):
        import time
        t = time.localtime()
        return (t.tm_hour, t.tm_min, t.tm_sec if self.cfg.get("seconds") else 0, t.tm_mday)

    def draw(self, p):
        import time
        t = time.localtime()
        h = t.tm_hour
        if self.cfg.get("h12"):
            h = h % 12 or 12
        hh, mm = "%02d" % h, "%02d" % t.tm_min
        style = self.cfg.get("style", "stack")
        if style == "line":
            return self.draw_line(p, t, hh, mm)
        if style == "analog":
            return self.draw_analog(p, t)
        # .stack: padding 6px 0 0 4px; цифры 700 168px, line-height .84, letter-spacing -6px
        size, lh = 168, 168 * 0.84
        p.setFont(font(size, 700, spacing=-6))
        fm = p.fontMetrics()
        x0, y0 = 4, 6
        # в css строка высотой lh, текст по центру строки по вертикали (half-leading)
        base1 = y0 + (lh - (fm.ascent() + fm.descent())) / 2 + fm.ascent()
        p.setPen(self.c("glow"))
        p.drawText(QPointF(x0, base1), hh)
        p.setPen(self.c("accent"))
        p.drawText(QPointF(x0, base1 + lh), mm)
        numw = max(text_w(p, hh), text_w(p, mm))
        if self.cfg.get("date", True) or self.cfg.get("seconds"):
            sx, sy = x0 + numw + 22, y0 + 8
            if self.cfg.get("date", True):
                p.setFont(font(15, 700, "Segoe UI Variable Text", 4))
                p.setPen(self.c("accent"))
                sy += p.fontMetrics().ascent()
                p.drawText(QPointF(sx, sy), self.DAYS[t.tm_wday].upper())
                p.setFont(font(24, 600, "Segoe UI Variable Text"))
                p.setPen(self.c("fg"))
                sy += 6 + p.fontMetrics().height()
                p.drawText(QPointF(sx, sy), "%d %s" % (t.tm_mday, self.GEN[t.tm_mon - 1]))
            if self.cfg.get("seconds"):
                p.setFont(font(22, 600))
                p.setPen(self.c("muted"))
                sy += 6 + p.fontMetrics().height()
                p.drawText(QPointF(sx, sy), "%02d" % t.tm_sec)


    def draw_line(self, p, t, hh, mm):
        """.line: «07:06 45 – 20/11» по общей базовой линии, gap 26px, цвет glow."""
        tail = ""
        if self.cfg.get("h12"):
            tail = "AM" if t.tm_hour < 12 else "PM"
        sec = " ".join(x for x in ("%02d" % t.tm_sec if self.cfg.get("seconds") else "", tail) if x)
        big = font(132, 700, spacing=-3)
        p.setFont(big); fm = p.fontMetrics()
        base = 8 + (132 - (fm.ascent() + fm.descent())) / 2 + fm.ascent()
        glow = self.c("glow")
        items = [(hh + ":" + mm, big, 1.0, 0)]
        if sec:
            items.append((sec, font(34, 600), 0.8, -12))
        if self.cfg.get("date", True):
            items.append(("–", font(110, 500, spacing=-3), 0.85, 0))
            items.append(("%02d/%02d" % (t.tm_mday, t.tm_mon), big, 1.0, 0))
        x = 0
        for i, (txt, f, op, ml) in enumerate(items):
            if i:
                x += 26 + ml
            p.setFont(f); p.setPen(glow); p.setOpacity(op)
            p.drawText(QPointF(x, base), txt)
            x += text_w(p, txt)
        p.setOpacity(1)

    def draw_analog(self, p, t):
        """.analog: стеклянный циферблат 280px (svg 280×280) и подпись под ним."""
        import math
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        ox, oy = 10, 2
        face = QRectF(ox, oy, 280, 280)
        draw_glass(p, self, face, 140)
        p.save(); p.translate(ox, oy)
        fg = self.c("fg")
        for i in range(0, 60, 5):
            q = i % 15 == 0
            p.save(); p.translate(140, 140); p.rotate(i * 6)
            c = QColor(fg); c.setAlphaF(0.9 if q else 0.45)
            pen = QPen(c, 4 if q else 2); pen.setCapStyle(Qt.PenCapStyle.RoundCap); p.setPen(pen)
            p.drawLine(QPointF(0, 14 - 140), QPointF(0, (30 if q else 24) - 140))
            p.restore()

        def hand(deg, col, w, y1, y2):
            p.save(); p.translate(140, 140); p.rotate(deg)
            pen = QPen(col, w); pen.setCapStyle(Qt.PenCapStyle.RoundCap); p.setPen(pen)
            p.drawLine(QPointF(0, y1 - 140), QPointF(0, y2 - 140)); p.restore()
        H, M, S = t.tm_hour, t.tm_min, t.tm_sec
        hand((H % 12) * 30 + M / 2, fg, 7, 140, 74)
        hand(M * 6 + S / 10, self.c("glow"), 5, 140, 42)
        if self.cfg.get("seconds"):
            hand(S * 6, self.c("accent"), 2, 158, 34)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(self.c("accent"))
        p.drawEllipse(QPointF(140, 140), 6, 6)
        p.restore()
        if self.cfg.get("date", True):
            cap = "%s, %d %s" % (self.DAYS[t.tm_wday], t.tm_mday, self.GEN[t.tm_mon - 1])
            line(p, 2, oy + 280 + 8, cap, font(15, 600, UI), fg, w=296, align="center")


def draw_glass(p, wdg, r, radius=26):
    """Стекло .card-bg: оттенок pill, затемнение glass, свет сверху, тонкая кромка."""
    from PyQt6.QtGui import QPainterPath, QLinearGradient
    path = QPainterPath(); path.addRoundedRect(r, radius, radius)
    p.save(); p.setRenderHint(QPainter.RenderHint.Antialiasing); p.setPen(Qt.PenStyle.NoPen)
    blur = getattr(wdg, "wall_blur", lambda r: None)(r)
    p.setClipPath(path)
    if blur is not None:
        old = getattr(wdg, "_wall_old", None)
        if old:                                   # смена обоев: старые тают, новые проявляются
            o = p.opacity(); p.drawImage(r, old[0]); p.setOpacity(o * old[1])
        p.drawImage(r, blur)
        if old:
            p.setOpacity(o)
    else:
        p.fillPath(path, wdg.c("pill"))
    p.fillPath(path, wdg.c("glass", ) if wdg.theme.get("glass") else QColor(12, 8, 10, 92))
    g = QLinearGradient(r.topLeft(), r.bottomLeft())
    g.setColorAt(0, QColor(255, 255, 255, 20)); g.setColorAt(0.45, QColor(255, 255, 255, 0))
    p.fillPath(path, g)
    p.setClipping(False)
    edge = wdg.c("edge") if wdg.theme.get("edge") else QColor(255, 255, 255, 28)
    p.setPen(QPen(edge, 1)); p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(path)
    p.restore()


def line(p, x, top, text, f, col, w=None, align="left"):
    """Строка текста как в css: top — верх строки (line-height normal). Возвращает высоту строки."""
    p.setFont(f); p.setPen(col)
    fm = p.fontMetrics()
    if w is not None:
        text = fm.elidedText(text, Qt.TextElideMode.ElideRight, int(w))
        tw = fm.horizontalAdvance(text)
        if align == "right": x += w - tw
        elif align == "center": x += (w - tw) / 2
    p.drawText(QPointF(x, top + fm.ascent()), text)
    return fm.height()


UI = fonts.UI


def tag(p, wdg, x, top, text):
    """Подпись вида «СЧЁТЧИКИ»: 11px, жирная, разрядка 1.8px, цвет акцента."""
    line(p, x, top, text, font(11, 700, UI, 1.8), wdg.c("accent"))
    return 15                      # line-height normal у 11px Segoe UI в браузере


KINDS = {"clock": Clock}


def load_kinds():
    import classic_a
    KINDS.update(classic_a.KINDS)
    import classic_b
    KINDS.update(classic_b.KINDS)
    import classic_c
    KINDS.update(classic_c.KINDS)
    import classic_d
    KINDS.update(classic_d.KINDS)
    import classic_e
    KINDS.update(classic_e.KINDS)
    import classic_f
    KINDS.update(classic_f.KINDS)


class Guides(QWidget):
    """Прозрачное окно на весь экран поверх всего: розовые направляющие и отступы, пока тащишь виджет.
    Мышь проходит сквозь него."""
    ONE = None
    COL = QColor(255, 64, 160)

    def __init__(self):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool |
                         Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowTransparentForInput)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setGeometry(QGuiApplication.primaryScreen().virtualGeometry())     # на все мониторы
        self.w, self.guides = None, []

    @staticmethod
    def show_for(w, guides):
        if Guides.ONE is None:
            if not guides:
                return
            Guides.ONE = Guides()
        g = Guides.ONE
        g.w, g.guides = w, guides
        vg = QGuiApplication.primaryScreen().virtualGeometry()
        if guides and g.geometry() != vg:                       # мониторы подключили или убрали
            g.setGeometry(vg)
        if os.environ.get("CLASSIC_NOSHOW"):                  # для записи ролика: окно не показывать
            return
        g.setVisible(bool(guides)); g.update()

    def paintEvent(self, e):
        p = QPainter(self); o = self.geometry().topLeft()
        p.translate(-o.x(), -o.y()); Guides.paint(p, self.w, self.guides); p.end()

    @staticmethod
    def paint(p, w, guides):
        if not guides or w is None:
            return
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        col, me, sp = Guides.COL, w.geometry(), Widget.span
        for gd in guides:
            if gd[0] == "line":
                _, ax, v, g = gd
                if g is None:                                   # край или центр экрана: линия во весь экран
                    lo, hi = -10000, 10000
                else:
                    lo = min(sp(me, 1 - ax)[0], sp(g, 1 - ax)[0]) - 12
                    hi = max(sp(me, 1 - ax)[1], sp(g, 1 - ax)[1]) + 12
                p.setPen(QPen(col, 1.5))
                if ax == 0:
                    p.drawLine(QPointF(v, lo), QPointF(v, hi))
                else:
                    p.drawLine(QPointF(lo, v), QPointF(hi, v))
                continue
            _, ax, seg, g, ref, gap = gd
            for (a0, a1), (r1, r2) in ((seg, (me, g)), ((ref[0], ref[1]), (ref[2], ref[3]))):
                c0 = max(sp(r1, 1 - ax)[0], sp(r2, 1 - ax)[0])
                c1 = min(sp(r1, 1 - ax)[1], sp(r2, 1 - ax)[1])
                c = (c0 + c1) / 2
                p.setPen(QPen(col, 1.5)); p.setBrush(col)
                if ax == 0:
                    p.drawLine(QPointF(a0, c), QPointF(a1, c))
                    p.drawLine(QPointF(a0, c - 5), QPointF(a0, c + 5)); p.drawLine(QPointF(a1, c - 5), QPointF(a1, c + 5))
                    box = QRectF((a0 + a1) / 2 - 18, c - 22, 36, 17)
                else:
                    p.drawLine(QPointF(c, a0), QPointF(c, a1))
                    p.drawLine(QPointF(c - 5, a0), QPointF(c + 5, a0)); p.drawLine(QPointF(c - 5, a1), QPointF(c + 5, a1))
                    box = QRectF(c + 6, (a0 + a1) / 2 - 8, 36, 17)
                p.setPen(Qt.PenStyle.NoPen); p.drawRoundedRect(box, 4, 4)
                p.setPen(QColor(255, 255, 255)); p.setFont(font(11, 600))
                p.drawText(box, Qt.AlignmentFlag.AlignCenter, str(round(gap)))


def main():
    app = QApplication(sys.argv)
    load_font()
    load_kinds()
    theme, conf = read_json("theme.json", {}), read_json("widgets.json", {})
    wins = [K(conf[n], theme) for n, K in KINDS.items() if conf.get(n, {}).get("on")]
    Widget.WINS = wins
    if "--shot" in sys.argv:
        out = sys.argv[sys.argv.index("--shot") + 1]
        os.makedirs(out, exist_ok=True)
        import time                         # дать фоновым потокам (музыка) прочитать данные
        t0 = time.time()
        while time.time() - t0 < 2.5:
            app.processEvents(); time.sleep(0.05)
        for w in wins:
            w.tick()
        wall = QImage(os.path.join(ZDIR, theme.get("wall", "_wall.jpg")))
        sw, sh = theme.get("screen", [1920, 1080])
        wall = wall.scaled(sw, sh, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                           Qt.TransformationMode.SmoothTransformation)
        for w in wins:
            g = w.geometry()
            img = wall.copy(g).convertToFormat(QImage.Format.Format_ARGB32)
            p = QPainter(img)
            p.drawImage(0, 0, w.frame())
            p.end()
            img.save(os.path.join(out, w.name + "_qt.png"))
            print(w.name, "light" if w.light else "dark")
        return 0
    for w in wins:
        w.show()
    stamp = {}

    def live():
        changed = False
        for n in ("theme.json", "widgets.json"):
            try:
                m = os.path.getmtime(os.path.join(ZDIR, n))
            except OSError:
                m = 0
            changed |= stamp.get(n) != m; stamp[n] = m
        if changed:
            th, cf = read_json("theme.json", {}), read_json("widgets.json", {})
            if th and cf:
                for w in wins:
                    if w.name in cf:
                        w.reconfig(cf[w.name], th)
                        w.setVisible(bool(cf[w.name].get("on")))
                    w.update()                                   # рамка режима правки
                have = {w.name for w in wins}
                for n, K in KINDS.items():
                    if n not in have and cf.get(n, {}).get("on"):
                        w = K(cf[n], th); wins.append(w); w.show()
        for w in wins:
            w.tick()
    timer = QTimer(); timer.timeout.connect(live); timer.start(1000)

    def screens_changed(*a):
        """Монитор подключили, отключили или сменили разрешение: виджеты встают на свои места
        (а виджеты с отключённого монитора временно переезжают на оставшийся)."""
        def again():
            for w in wins:
                if not getattr(w, "edrag", None):
                    w.place(); w._cache = None; w.contrast(); w.update()
        QTimer.singleShot(800, again)
    app.screenAdded.connect(screens_changed)
    app.screenRemoved.connect(screens_changed)
    app.primaryScreenChanged.connect(screens_changed)
    for s in app.screens():
        s.geometryChanged.connect(screens_changed)
    app.screenAdded.connect(lambda s: s.geometryChanged.connect(screens_changed))
    if "--quit" in sys.argv:
        QTimer.singleShot(int(sys.argv[sys.argv.index("--quit") + 1]) * 1000, app.quit)
    return app.exec()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        import traceback
        log("виджеты не запустились:\n" + traceback.format_exc())
        if not any(a in sys.argv for a in ("--shot", "--check")):
            import widgets as _W
            _W.classic_fail()                               # пустой стол хуже Zebar: возвращаем его
        sys.exit(1)
