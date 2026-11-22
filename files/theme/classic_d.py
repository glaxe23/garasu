"""Медиа-плеер Garasu Classic: обложка, текст песни, название, волна спектра, прогресс, громкость, кнопки.
Отступы взяты из media.html. Трек берём из системных медиа-кнопок Windows (winrt, как провайдер media в Zebar),
спектр и обложку с текстом даёт тот же фоновый помощник (ws://127.0.0.1:47631 и nowplaying.json)."""
import os, json, time, socket, base64, struct, threading, asyncio, datetime
from PyQt6.QtCore import Qt, QRectF, QPointF, QTimer
from PyQt6.QtGui import QColor, QPen, QLinearGradient, QBrush, QImage, QPainter, QPainterPath
import __main__ as C
from classic_b import tools, run

try:
    from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as Manager
except Exception as _e:                      # без winrt плеер не видит музыку: пишем причину в classic.log
    Manager = None
    try:
        C.log("плеер: не загрузилась библиотека winrt (%s) — трек не будет виден" % _e)
    except Exception:
        pass


class Ws:
    """Маленький websocket-клиент: принимает спектр (96 байт), отправляет текстовые команды помощнику."""

    def __init__(self, url, on_open):
        host, port = url.split("//", 1)[1].split(":")
        self.addr, self.sock, self.on_open = (host, int(port.strip("/"))), None, on_open
        self.levels, self.last = [0.0] * 96, 0.0
        threading.Thread(target=self.loop, daemon=True).start()

    def loop(self):
        while True:
            try:
                s = socket.create_connection(self.addr, timeout=5)
                key = base64.b64encode(os.urandom(16)).decode()
                s.sendall(("GET / HTTP/1.1\r\nHost: %s:%d\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                           "Sec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n\r\n" % (*self.addr, key)).encode())
                buf = b""
                while b"\r\n\r\n" not in buf:
                    d = s.recv(1024)
                    if not d:
                        raise OSError
                    buf += d
                buf = buf.split(b"\r\n\r\n", 1)[1]
                s.settimeout(None); self.sock = s; self.on_open()
                while True:
                    while len(buf) < 2:
                        buf += self.recv(s)
                    op, n = buf[0] & 15, buf[1] & 127
                    hl = 2
                    if n == 126:
                        while len(buf) < 4: buf += self.recv(s)
                        n, hl = struct.unpack(">H", buf[2:4])[0], 4
                    elif n == 127:
                        while len(buf) < 10: buf += self.recv(s)
                        n, hl = struct.unpack(">Q", buf[2:10])[0], 10
                    while len(buf) < hl + n:
                        buf += self.recv(s)
                    data, buf = buf[hl:hl + n], buf[hl + n:]
                    if op == 2:
                        self.levels = [b / 255 for b in data[:96]]; self.last = time.time()
                    elif op == 8:
                        raise OSError
            except Exception:
                self.sock = None
                time.sleep(2.5)

    @staticmethod
    def recv(s):
        d = s.recv(4096)
        if not d:
            raise OSError
        return d

    def send(self, text):
        s = self.sock
        if not s:
            return
        data, mask = text.encode(), os.urandom(4)
        n = len(data)
        head = bytes([0x81]) + (bytes([0x80 | n]) if n < 126 else bytes([0x80 | 126]) + struct.pack(">H", n))
        try:
            s.sendall(head + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))
        except OSError:
            pass


class Smtc:
    """Текущий трек из медиа-кнопок Windows, опрос раз в секунду в своём потоке."""

    def __init__(self):
        self.now = None                   # dict или None
        self.chosen = None                # источник Windows, который сейчас показан
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self.loop.run_forever, daemon=True).start()
        threading.Thread(target=self.poll, daemon=True).start()

    def poll(self):
        while Manager:
            try:
                self.now = asyncio.run_coroutine_threadsafe(self.read(), self.loop).result(5)
            except Exception:
                pass
            time.sleep(1)

    async def pick(self):
        """Какой источник показывать. «Текущий» источник Windows бывает не тот: например, вкладка с видео
        на паузе или Telegram, а музыка играет в другом браузере. Берём тот, где сейчас реально играет
        и есть название трека; если такого нет — текущий; если и его нет — любой с названием."""
        mgr = await Manager.request_async()
        cur = mgr.get_current_session()
        try:
            all_ = list(mgr.get_sessions())
        except Exception:
            all_ = []
        info = []
        for s in all_:
            try:
                pr = await s.try_get_media_properties_async()
                info.append((s, pr, s.get_playback_info().playback_status == 4))
            except Exception:
                pass
        for s, pr, playing in info:
            if playing and pr.title:
                return s, pr
        if cur:
            return cur, await cur.try_get_media_properties_async()
        for s, pr, _ in info:
            if pr.title:
                return s, pr
        return None, None

    async def read(self):
        s, pr = await self.pick()
        self.chosen = s
        if not s:
            return None
        tl = s.get_timeline_properties()
        playing = s.get_playback_info().playback_status == 4
        sec = lambda td: td.total_seconds() if isinstance(td, datetime.timedelta) else (td or 0) / 1e7
        pos = sec(tl.position) - sec(tl.start_time)
        try:                                  # позиция обновляется плеером не всегда: досчитываем от его отметки
            upd = tl.last_updated_time.timestamp()
            if playing and upd > 0:
                pos += max(0, time.time() - upd)
        except Exception:
            pass
        return {"title": pr.title or "", "artist": pr.artist or pr.album_title or "", "playing": playing,
                "pos": pos, "len": sec(tl.end_time) - sec(tl.start_time), "at": time.time(),
                "app": s.source_app_user_model_id or ""}

    def call(self, what):
        async def go():
            s, _ = await self.pick()                 # кнопки управляют тем же источником, что показан
            if s:
                await getattr(s, what)()
        if Manager:
            asyncio.run_coroutine_threadsafe(go(), self.loop)


mmss = lambda s: "%d:%02d" % (s // 60, s % 60)
N = 56


_EV = {}


def sysvol(v=None):
    """Общая громкость Windows через pycaw: без аргумента прочитать (0..100), с аргументом поставить."""
    try:
        if "ev" not in _EV:
            from pycaw.pycaw import AudioUtilities
            _EV["ev"] = AudioUtilities.GetSpeakers().EndpointVolume
        ev = _EV["ev"]
        if v is None:
            return round(ev.GetMasterVolumeLevelScalar() * 100)
        ev.SetMasterVolumeLevelScalar(max(0, min(100, v)) / 100, None)
    except Exception:
        _EV.clear()                      # устройство сменилось: в следующий раз взять заново
    return None


class Media(C.Widget):
    name = "media"
    base = (520, 372)
    X, TOP, W = 2 + 16, 2 + 16, 482

    def card_rect(self):
        if self.cfg.get("card") is False:          # стекло выключено в настройках: плеер без карточки, как другие виджеты
            return None
        return None if self.cfg.get("solid") or not self.sess() else QRectF(2, 2, 516, 368)
    BTN = {"prev": (384, 322, 30), "play": (422, 317, 40), "next": (470, 322, 30)}
    RNG = (223, 110)                       # ползунок громкости: x, ширина; по вертикали центр 337

    def __init__(self, *a, **k):
        self.smtc, self.np, self.np_raw, self.sent, self.art = Smtc(), {}, "", None, (None, None)
        self.bars, self.peaks, self.live, self.vol_ui, self.drag = [0.0] * N, [0.0] * N, False, 50, 0
        self.fade = (None, 0)                  # прошлая обложка и начало смены (0.5 с)
        self.roll = (None, 62, 62, 0)          # текст песни: строка, откуда, куда, начало прокрутки (0.5 с)
        super().__init__(*a, **k)
        url = tools().get("audio") or "ws://127.0.0.1:47631"
        self.ws = Ws(url, lambda: setattr(self, "sent", None))
        self.anim = QTimer(self); self.anim.timeout.connect(self.wave)

    # ---- данные
    def sess(self):
        import sys
        if "--fake-media" in sys.argv:          # для снимков: проверить вид без играющей музыки
            self.bars = [abs(((i * 37) % 23) / 23 - 0.3) for i in range(N)]; self.peaks = [b + 0.08 for b in self.bars]
            return {"title": "Тестовый трек", "artist": "Исполнитель", "playing": True, "pos": 83, "len": 214,
                    "at": time.time(), "app": "test"}
        s = self.smtc.now
        return s if s and s["title"] else None

    def position(self, s):
        p = s["pos"] + (time.time() - s["at"] if s["playing"] else 0)
        return min(p, s["len"]) if s["len"] > 0 else p

    def load_np(self):
        try:
            with open(os.path.join(C.ZDIR, "nowplaying.json"), encoding="utf-8-sig") as f:
                t = f.read()
            if t != self.np_raw:
                self.np_raw, self.np = t, json.loads(t)
                if self.np.get("vol") is not None and time.time() - self.drag > 1.5:
                    self.vol_ui = self.np["vol"]
        except Exception:
            pass
        # помощник не знает громкость приложения: показываем общую громкость Windows (как dev.volume в html)
        if self.np.get("vol") is None and time.time() - self.drag > 0.8:
            v = sysvol()
            if v is not None:
                self.vol_ui = v

    def report(self, s):
        """Сообщить помощнику трек, чтобы он нашёл обложку и текст песни (как reportTrack в html)."""
        key = "|".join([s["title"], s["artist"], s["app"]]) if s else ""
        if key != self.sent and self.ws.sock:
            self.sent = key
            self.ws.send("track:" + json.dumps({"title": s["title"] if s else "", "artist": s["artist"] if s else "",
                                                "app": s["app"] if s else "", "duration": round(s["len"]) if s else 0},
                                               ensure_ascii=False))

    def state(self):
        s = self.sess()
        self.report(s)
        self.load_np()
        live = bool(s and s["playing"] and self.cfg.get("wave", True) is not False and time.time() - self.ws.last < 1.5)
        if live and not self.anim.isActive():
            self.anim.start(33)
        self.live = live
        if not s:
            return None
        return (s["title"], s["artist"], s["playing"], int(self.position(s)), round(s["len"]), self.np_raw, self.vol_ui)

    def wave(self):
        """30 раз в секунду, пока играет музыка: полоски тянутся к спектру, «шапочки» медленно падают."""
        lv = self.ws.levels if self.live else [0.0] * 96
        energy = 0
        for i in range(N):
            a = i * 96 // N; b = max(a + 1, (i + 1) * 96 // N)
            v = max(lv[a:b])
            self.bars[i] += (v - self.bars[i]) * (0.7 if v > self.bars[i] else 0.28)
            self.peaks[i] = max(self.bars[i], self.peaks[i] - 0.024)
            energy += self.bars[i] + self.peaks[i]
        if not self.live and energy < 0.02:
            self.anim.stop()
        self._cache = None; self.update()

    # ---- рисование
    def art_img(self, rel):
        if self.art[0] != rel:
            img = QImage(os.path.join(C.ZDIR, rel)) if rel else QImage()
            if self.art[0] is not None and self.anim_on():           # плавная смена обложки
                self.fade = (self.art[1], time.time()); self.anim_t.start(16)
            self.art = (rel, None if img.isNull() else img)
        return self.art[1]

    # ---- анимации: смена обложки и прокрутка текста (по 0.5 с), таймер общий с появлением
    def moving(self):
        t = time.time()
        return t - self.fade[1] < 0.5 or t - self.roll[3] < 0.5

    def animating(self):
        return super().animating() or self.moving()

    def animate(self):
        if self.moving() or self.fade[0] is not None:
            self._cache = None
            if not self.moving():
                self.fade = (None, 0)
        super().animate()

    def lyr_off(self, i):
        """translateY(62 - i*26) с transition 0.5s ease."""
        target = 62 - max(0, i) * 26
        line, a, b, t0 = self.roll
        k = C.ease(min(1, (time.time() - t0) / 0.5))
        cur = a + (b - a) * k
        if line != i:
            if line is not None and self.anim_on():
                self.roll = (i, cur, target, time.time()); self.anim_t.start(16)
            else:
                self.roll = (i, target, target, 0)
            return self.roll[1]
        return cur

    def cover(self, p, img, r):
        if img is not None:
            sc = max(150 / img.width(), 150 / img.height())
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            p.drawImage(QRectF(r.x() + (150 - img.width() * sc) / 2, r.y() + (150 - img.height() * sc) / 2,
                               img.width() * sc, img.height() * sc), img)
        else:
            g = QLinearGradient(r.topLeft(), r.bottomRight())
            g.setColorAt(0, self.c("accent")); g.setColorAt(1, self.c("accent2"))
            p.fillRect(r, QBrush(g))
            p.setFont(C.font(44, 400, "Segoe Fluent Icons")); p.setPen(self.c("pill"))
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, "\ue8d6")

    def halos(self):
        if not self.sess():
            return []
        x, y, d = self.BTN["play"]
        return [(QRectF(x, y, d, d), d / 2)]

    def hot(self):
        h = [(QRectF(x, y, d, d), d / 2) for k, (x, y, d) in self.BTN.items() if k != "play"]
        if self.cfg.get("volume", True) is not False:
            h.append((QRectF(196, 324, 24, 26), 6))
        return h

    def draw(self, p):
        s = self.sess()
        if not s:
            return
        X, T, W = self.X, self.TOP, self.W
        np = self.np if (self.np.get("title") or "") == s["title"] else {}
        # обложка 150x150, скругление 10
        if self.cfg.get("art", True) is not False:
            r = QRectF(X, T, 150, 150)
            path = QPainterPath(); path.addRoundedRect(r, 10, 10)
            p.save(); p.setClipPath(path)
            img = self.art_img(np.get("art", ""))
            k = min(1, (time.time() - self.fade[1]) / 0.5)
            if k < 1:
                self.cover(p, self.fade[0], r); p.setOpacity(k)
            self.cover(p, img, r)
            p.restore()
        # текст песни: текущая строка по центру, края гаснут
        lx = X + 150 + 18 if self.cfg.get("art", True) is not False else X
        lw = X + W - lx
        if self.cfg.get("lyrics"):
            lines = np.get("lyrics") or []
            if lines:
                pos, ln = self.position(s), s["len"]
                if np.get("synced"):
                    i = -1
                    for k, l in enumerate(lines):
                        if l[0] <= pos + 0.25:
                            i = k
                else:
                    i = min(len(lines) - 1, int(pos / ln * len(lines))) if ln > 0 else 0
                z = self.zoom()
                layer = QImage(int(lw * z) + 2, int(150 * z) + 2, QImage.Format.Format_ARGB32_Premultiplied); layer.fill(0)
                q = QPainter(layer); q.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
                q.scale(z, z)
                off = self.lyr_off(i)
                for k, l in enumerate(lines):
                    y = off + k * 26
                    if -26 < y < 150:
                        q.setOpacity(1 if k == i else 0.38)
                        C.line(q, 0, y + 4 + (18 - 17.3) / 2, l[1], C.font(13, 700 if k == i else 500, C.UI), self.c("fg"), lw)
                q.setOpacity(1)
                g = QLinearGradient(0, 0, 0, 150)
                for at, a in ((0, 0), (0.22, 255), (0.78, 255), (1, 0)):
                    g.setColorAt(at, QColor(0, 0, 0, a))
                q.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
                q.fillRect(QRectF(0, 0, lw + 1, 151), QBrush(g)); q.end()
                p.save(); p.resetTransform(); p.drawImage(QPointF(lx * z, T * z), layer); p.restore()
            else:
                hint = {"loading": "ищу текст песни…", "none": "текст этой песни не найден"}.get(np.get("state"), "")
                if hint:
                    C.line(p, lx, T + 62, hint, C.font(12, 400, C.UI), self.c("muted"), lw)
        # название и исполнитель
        y = T + 150 + 12
        y += C.line(p, X, y, s["title"], C.font(19, 700, C.UI), self.c("fg"), W)
        C.line(p, X, y + 2, s["artist"], C.font(13, 400, C.UI), self.c("muted"), W)
        # волна: 56 полосок, градиент accent -> glow снизу вверх, «шапочки» цветом текста
        if self.cfg.get("wave", True) is not False:
            bx, by, bh0 = X, 2 + 368 - 12 - 42 - 4 - 3 - 6 - 50, 50
            gap = 3; bw = (W - gap * (N - 1)) / N
            g = QLinearGradient(0, by + bh0, 0, by)
            g.setColorAt(0, self.c("accent")); g.setColorAt(1, self.c("glow"))
            p.setPen(Qt.PenStyle.NoPen)
            for i in range(N):
                bh = max(2, self.bars[i] * (bh0 - 6)); x = bx + i * (bw + gap)
                p.setOpacity(0.95); p.setBrush(QBrush(g))
                p.drawRoundedRect(QRectF(x, by + bh0 - bh, bw, bh), min(bw / 2, 2.5), min(bw / 2, 2.5))
                if self.peaks[i] > 0.03:
                    p.setOpacity(0.7); p.setBrush(self.c("fg"))
                    p.drawRect(QRectF(x, by + bh0 - max(2, self.peaks[i] * (bh0 - 6)) - 3, bw, 1.5))
            p.setOpacity(1)
        # прогресс
        py = 2 + 368 - 12 - 42 - 4 - 3
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(255, 255, 255, 36))
        p.drawRoundedRect(QRectF(X, py, W, 3), 2, 2)
        if s["len"] > 0:
            p.setBrush(self.c("accent")); p.drawRoundedRect(QRectF(X, py, W * min(1, self.position(s) / s["len"]), 3), 2, 2)
        # нижний ряд: время, громкость, кнопки
        cy = 2 + 368 - 12 - 21
        if s["len"] > 0:
            C.line(p, X, cy - 8, mmss(self.position(s)) + " / " + mmss(s["len"]), C.font(12, 600), self.c("muted"))
        if self.cfg.get("volume", True) is not False:
            v = self.vol_ui
            icon = "" if v == 0 else "" if v < 34 else "" if v < 67 else ""
            p.setFont(C.font(13, 400, "Segoe Fluent Icons")); p.setPen(self.c("fg"))
            p.drawText(QRectF(200, cy - 10, 16, 20), Qt.AlignmentFlag.AlignCenter, icon)
            rx, rw = self.RNG
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(255, 255, 255, 46))
            p.drawRoundedRect(QRectF(rx, cy - 2, rw, 4), 2, 2)
            p.setBrush(self.c("accent")); p.drawRoundedRect(QRectF(rx, cy - 2, rw * v / 100, 4), 2, 2)
            p.setBrush(QColor(0, 0, 0, 60)); p.drawEllipse(QPointF(rx + (rw - 12) * v / 100 + 6, cy + 1), 7, 7)
            p.setBrush(self.c("fg")); p.drawEllipse(QPointF(rx + (rw - 12) * v / 100 + 6, cy), 6, 6)
            C.line(p, 340, cy - 8, str(v), C.font(11, 600), self.c("muted"), 22, "right")
        for k, (x, y, d) in self.BTN.items():
            r = QRectF(x, y, d, d); col = self.c("fg")
            if k == "play":
                p.setBrush(self.c("accent")); p.drawEllipse(r); col = self.c("pill")
            p.setFont(C.font(14 if k == "play" else 12, 400, "Segoe Fluent Icons")); p.setPen(col)
            p.drawText(r, Qt.AlignmentFlag.AlignCenter,
                       {"prev": "", "next": "", "play": "" if s["playing"] else ""}[k])

    # ---- управление
    def set_volume(self, v):
        v = max(0, min(100, round(v)))
        self.vol_ui, self.drag = v, time.time()
        if self.np.get("vol") is not None:
            self.ws.send("vol:%d" % v)
        else:
            sysvol(v)
        self._cache = None; self.update()

    def click(self, x, y):
        pt = QPointF(x, y)
        for k, (bx, by, d) in self.BTN.items():
            if QRectF(bx, by, d, d).contains(pt):
                self.smtc.call({"prev": "try_skip_previous_async", "next": "try_skip_next_async",
                                "play": "try_toggle_play_pause_async"}[k])
                QTimer.singleShot(400, self.tick); return
        rx, rw = self.RNG
        if QRectF(rx - 4, 337 - 9, rw + 8, 18).contains(pt):
            self.dragging = True; self.set_volume((x - rx) / rw * 100)
        elif QRectF(196, 322, 24, 30).contains(pt):
            run(tools().get("mixer"))

    def mouseMoveEvent(self, e):
        if getattr(self, "dragging", False):
            rx, rw = self.RNG
            self.set_volume((e.position().x() / self.zoom() - rx) / rw * 100)
        else:
            super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        self.dragging = False
        super().mouseReleaseEvent(e)

    def grab_zones(self):
        """В режиме правки за кнопки и ползунок громкости окно не тащится."""
        z = super().grab_zones() + [QRectF(x, y, d, d) for x, y, d in self.BTN.values()]
        if self.cfg.get("volume", True) is not False:
            rx, rw = self.RNG
            z.append(QRectF(rx - 6, 325, rw + 12, 24))
        return z

    def wheelEvent(self, e):
        if self.cfg.get("volume", True) is not False:
            self.set_volume(self.vol_ui + (4 if e.angleDelta().y() > 0 else -4))


KINDS = {"media": Media}
