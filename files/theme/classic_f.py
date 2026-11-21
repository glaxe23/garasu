"""Погода и монитор системы для Garasu Classic. Размеры и отступы взяты из weather.html и sysmon.html.

Погода: место по интернет-адресу (ipinfo.io), сама погода с open-meteo.com, раз в час, как провайдер weather у Zebar.
Монитор: psutil, процессор и сеть раз в 2 секунды, память раз в 3, диск раз в минуту.
"""
import os, json, math, time, threading, urllib.request
from PyQt6.QtCore import Qt, QRectF, QPointF, QTimer, QByteArray
from PyQt6.QtGui import QColor, QPen, QPainterPath, QPainter
from PyQt6.QtSvg import QSvgRenderer
import __main__ as C


def hexa(c, what="stroke"):
    """Цвет для SVG: QtSvg понимает только #rrggbb, прозрачность отдельным атрибутом."""
    return '%s="#%02x%02x%02x" %s-opacity="%.3f"' % (what, c.red(), c.green(), c.blue(), what, c.alphaF())


# ---------------------------------------------------------------- погода
SUN = '<circle class="acc" cx="32" cy="32" r="11"/><path class="acc" d="M32 8v6M32 50v6M8 32h6M50 32h6M15 15l4 4M45 45l4 4M49 15l-4 4M19 45l-4 4"/>'
MOON = '<path class="acc" d="M42 38A16 16 0 0 1 26 16a16 16 0 1 0 16 22z"/>'
CLOUD = '<path d="M20 46h26a10 10 0 0 0 1-20 14 14 0 0 0-27 3 8.5 8.5 0 0 0 0 17z"/>'
SMALL_SUN = '<circle class="acc" cx="46" cy="18" r="7"/><path class="acc" d="M46 5v3M59 18h-3M55 9l-2 2"/>'
SMALL_MOON = '<path class="acc" d="M54 20a9 9 0 0 1-9-12 9 9 0 1 0 9 12z"/>'
RAIN = '<path class="acc" d="M24 52l-2 6M33 52l-2 6M42 52l-2 6"/>'
HEAVY = '<path class="acc" d="M22 51l-3 8M30 51l-3 8M38 51l-3 8M46 51l-3 8"/>'
SNOW = '<circle class="fill" cx="24" cy="55" r="2.2"/><circle class="fill" cx="33" cy="58" r="2.2"/><circle class="fill" cx="42" cy="55" r="2.2"/>'
BOLT = '<path class="fill" d="M35 46l-8 10h6l-3 8 9-11h-6z"/>'
UP = '<g transform="translate(0,-6)">' + CLOUD + '</g>'
MAP = {
    "clear_day": (SUN, "ясно"), "clear_night": (MOON, "ясная ночь"),
    "cloudy_day": (SMALL_SUN + CLOUD, "облачно"), "cloudy_night": (SMALL_MOON + CLOUD, "облачно"),
    "light_rain": (UP + RAIN, "небольшой дождь"), "heavy_rain": (UP + HEAVY, "сильный дождь"),
    "snow": (UP + SNOW, "снег"), "thunder": (UP + BOLT, "гроза"),
}


def status(code, day):
    """Код погоды WMO -> вид, так же, как делит Zebar."""
    dn = "_day" if day else "_night"
    if code == 0: return "clear" + dn
    if code <= 50: return "cloudy" + dn
    if code <= 62: return "light_rain"
    if code <= 70: return "heavy_rain"
    if code <= 79: return "snow"
    if code <= 84: return "heavy_rain"
    if code <= 94: return "snow"
    return "thunder"


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "garasu-classic"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


class Weather(C.Widget):
    CARD = "box"
    name = "weather"
    base = (300, 150)
    DATA = {"w": None, "busy": False, "next": 0, "wait": 60, "t0": time.time(), "fail": False}

    @classmethod
    def fetch(cls):
        d = cls.DATA
        try:
            fake = os.environ.get("CLASSIC_FAKE_WEATHER")
            if fake:                                   # для проверок без сети: "код,температура,ветер,день"
                c, t, wnd, day = fake.split(",")
                w = {"status": status(int(c), day == "1"), "temp": float(t), "wind": float(wnd)}
            else:
                lat, lon = get_json("https://ipinfo.io/json")["loc"].split(",")
                cur = get_json("https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s"
                               "&current=temperature_2m,weather_code,wind_speed_10m,is_day" % (lat, lon))["current"]
                w = {"status": status(int(cur["weather_code"]), cur.get("is_day", 1) == 1),
                     "temp": float(cur["temperature_2m"]), "wind": cur.get("wind_speed_10m")}
            d.update(w=w, fail=False, wait=60, next=time.time() + 3600)
        except Exception:
            # при входе в Windows сеть бывает ещё не готова: пробуем снова через 1, 2, 4… до 10 минут
            d.update(fail=True, next=time.time() + d["wait"], wait=min(d["wait"] * 2, 600))
        d["busy"] = False

    def tick(self):
        d = Weather.DATA
        if not d["busy"] and time.time() >= d["next"]:
            d["busy"] = True
            threading.Thread(target=Weather.fetch, daemon=True).start()
        super().tick()

    def view(self):
        d = Weather.DATA
        w = d["w"]
        if w:
            icon, text = MAP.get(w["status"], (CLOUD, ""))
            wind = "ветер %d км/ч" % math.floor(w["wind"] + 0.5) if w.get("wind") is not None else ""
            return icon, str(math.floor(w["temp"] + 0.5)), text, wind
        late = d["fail"] or time.time() - d["t0"] > 30
        return CLOUD, "–", "нет связи, попробую ещё" if late else "загружаю…", ""

    def state(self):
        return self.view()

    def draw(self, p):
        icon, temp, text, wind = self.view()
        # .box: 296×146 с отступом 2, padding 14px 18px, по центру: значок 78px, зазор 16px, колонка текста
        icon = icon.replace('class="acc"', hexa(self.c("accent"))) \
                   .replace('class="fill"', hexa(self.c("accent"), "fill") + ' stroke="none"')
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64"><g fill="none" %s stroke-width="3.2"'
               ' stroke-linecap="round" stroke-linejoin="round">%s</g></svg>' % (hexa(self.c("glow")), icon))
        QSvgRenderer(QByteArray(svg.encode())).render(p, QRectF(2 + 18, 2 + (146 - 78) / 2, 78, 78))
        x = 2 + 18 + 78 + 16
        cw = 296 - 36 - 78 - 16
        f_temp = C.font(50, 700, spacing=-2); p.setFont(f_temp); fm = p.fontMetrics()
        lh = 50 * 1.05
        f_st, f_w = C.font(13, 600, C.UI), C.font(12, 400, C.UI)
        p.setFont(f_st); h_st = p.fontMetrics().height()
        p.setFont(f_w); h_w = p.fontMetrics().height()
        col_h = 15 + lh + h_st + ((1 + h_w) if wind else 0)
        y = 2 + 14 + (146 - 28 - col_h) / 2
        y += C.tag(p, self, x, y, "ПОГОДА")
        p.setFont(f_temp); p.setPen(self.c("fg"))
        base = y + (lh - (fm.ascent() + fm.descent())) / 2 + fm.ascent()
        p.drawText(QPointF(x, base), temp)
        tw = fm.horizontalAdvance(temp)
        C.line(p, x + tw + 2, y + 8, "°C", C.font(22, 700), self.c("fg"))
        y += lh
        y += C.line(p, x, y, text, f_st, self.c("fg"), cw)
        if wind:
            C.line(p, x, y + 1, wind, f_w, self.c("muted"), cw)


# ---------------------------------------------------------------- монитор
def size(b, per=""):
    """Как size() в common.js: 1536 -> «1.5 KiB»."""
    u = ["B", "KiB", "MiB", "GiB", "TiB"]
    i, v = 0, b or 0
    while v >= 1024 and i < len(u) - 1:
        v /= 1024; i += 1
    return (str(int(v + 0.5)) if i == 0 else "%.1f" % v) + " " + u[i] + per


class Sysmon(C.Widget):
    name = "sysmon"
    base = (320, 560)
    N = 60

    def __init__(self, cfg, theme):
        import psutil
        self.ps = psutil
        self.cpu_h, self.down_h, self.up_h = [0.0] * self.N, [0.0] * self.N, [0.0] * self.N
        self.cpu = self.mem = self.disk = self.rate = None
        self.net0, self.ver, self.n = None, 0, 0
        psutil.cpu_percent(None)                       # первый замер всегда 0, дальше — за прошедшие 2 с
        super().__init__(cfg, theme)
        self.sample()
        self.sample_t = QTimer(self); self.sample_t.timeout.connect(self.sample); self.sample_t.start(2000)

    def net_bytes(self):
        s = r = 0
        for name, c in self.ps.net_io_counters(pernic=True).items():
            if "loopback" not in name.lower():
                s += c.bytes_sent; r += c.bytes_recv
        return time.time(), r, s

    def sample(self):
        ps = self.ps
        try:
            self.cpu = ps.cpu_percent(None)
            if self.n % 3 == 0 or self.mem is None:
                vm = ps.virtual_memory(); self.mem = (vm.percent, vm.used, vm.total)
            if self.n % 30 == 0 or self.disk is None:
                du = ps.disk_usage("C:\\"); self.disk = (du.total - du.free, du.total)
            now = self.net_bytes()
            if self.net0:
                dt = max(0.5, now[0] - self.net0[0])
                self.rate = (max(0, now[1] - self.net0[1]) / dt, max(0, now[2] - self.net0[2]) / dt)
            self.net0 = now
        except Exception:
            pass
        self.n += 1
        for h, v in ((self.cpu_h, self.cpu), (self.down_h, (self.rate or (0, 0))[0]), (self.up_h, (self.rate or (0, 0))[1])):
            h.append(v or 0); h.pop(0)
        self.ver += 1
        self.tick()

    def state(self):
        return self.ver

    def on(self, k):
        return self.cfg.get(k) is not False

    def card_on(self):
        return self.cfg.get("card") is not False          # как в html: стекло, если card не false

    def layout(self):
        """Высота содержимого .wrap (без отступа 2 px)."""
        h = 0
        if self.on("cpu"):
            h += (34 + 8 if self.on("graphs") else 0) + 23
        if self.on("memory"):
            h += 23 * 3
        if self.on("network"):
            h += 20 + (70 if self.on("graphs") else 0) + 10 + 23 * 2
        if self.on("disk"):
            h += 20 + 4 + 7 + 14 + 23 * 2
        return h + (16 + 12 if self.card_on() else 0)

    def content_h(self):
        return self.layout() + 4

    def card_rect(self):
        return QRectF(2, 2, 316, self.layout()) if self.card_on() else None

    def row(self, p, x, y, w, label, value, mark=None):
        f = C.font(14, 500)
        p.setFont(f); fm = p.fontMetrics()
        top = y + (23 - fm.height()) / 2
        if mark is not None:
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(mark)
            p.drawRoundedRect(QRectF(x, y + 5, 3, 13), 1.5, 1.5)
        C.line(p, x + 12, top, label, f, self.c("fg"))
        C.line(p, x, top, value, C.font(14, 600), self.c("fg"), w, "right")

    def graph(self, p, r, data, mx, col, fill):
        path = QPainterPath()
        n = len(data)
        for i, v in enumerate(data):
            pt = QPointF(r.x() + i / (n - 1) * r.width(), r.y() + r.height() - 1 - min(1, v / mx) * (r.height() - 3))
            path.lineTo(pt) if i else path.moveTo(pt)
        pen = QPen(col, 1.3); pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(pen); p.drawPath(path)
        if fill:
            path.lineTo(r.right(), r.bottom()); path.lineTo(r.x(), r.bottom()); path.closeSubpath()
            c = QColor(col); c.setAlphaF(c.alphaF() * 0.22)
            p.setPen(Qt.PenStyle.NoPen); p.fillPath(path, c)

    def draw(self, p):
        pad = 16 if self.card_on() else 0
        x, y, w = 2 + pad, 2 + pad, 316 - 2 * pad
        if self.on("cpu"):
            if self.on("graphs"):
                self.graph(p, QRectF(x, y, w, 34), self.cpu_h, 100, self.c("glow"), True)
                y += 34 + 8
            self.row(p, x, y, w, "Процессор", "–" if self.cpu is None else "%.1f%%" % self.cpu, self.c("accent")); y += 23
        if self.on("memory"):
            m = self.mem
            self.row(p, x, y, w, "Память", "%d%%" % math.floor(m[0] + 0.5) if m else "–", self.c("accent2")); y += 23
            self.row(p, x, y, w, "Занято памяти", size(m[1]) if m else "–"); y += 23
            self.row(p, x, y, w, "Всего памяти", size(m[2]) if m else "–"); y += 23
        if self.on("network"):
            y += 20
            if self.on("graphs"):
                mx = max([1024] + self.down_h + self.up_h) * 1.1
                f = C.font(11, 400); p.setFont(f); fh = p.fontMetrics().height()
                labels = [size(mx * k / 4, "/s") for k in (4, 3, 2, 1)] + ["0 B/s"]
                p.setOpacity(0.8)
                for i, s in enumerate(labels):                # justify-content: space-between по высоте 70
                    C.line(p, x + 12, y + i * (70 - fh) / 4, s, f, self.c("fg"))
                p.setOpacity(1)
                r = QRectF(x + 74 + 8, y, w - 82, 70)
                self.graph(p, r, self.up_h, mx, self.c("accent2"), False)
                self.graph(p, r, self.down_h, mx, self.c("accent"), False)
                y += 70
            y += 10
            rt = self.rate
            self.row(p, x, y, w, "Загрузка", size(rt[0], "/s") if rt else "–", self.c("accent")); y += 23
            self.row(p, x, y, w, "Отдача", size(rt[1], "/s") if rt else "–", self.c("accent2")); y += 23
        if self.on("disk"):
            y += 20 + 4
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(0, 0, 0, 107))
            p.drawRoundedRect(QRectF(x, y, w, 7), 3.5, 3.5)
            if self.disk:
                p.setBrush(self.c("glow"))
                p.drawRoundedRect(QRectF(x, y, w * self.disk[0] / self.disk[1], 7), 3.5, 3.5)
            y += 7 + 14
            d = self.disk
            self.row(p, x, y, w, "Диск занят", size(d[0]) if d else "–"); y += 23
            self.row(p, x, y, w, "Всего", size(d[1]) if d else "–")


KINDS = {"weather": Weather, "sysmon": Sysmon}
