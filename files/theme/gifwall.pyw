"""Живые обои Garasu: проигрывает GIF или видео (MP4 и др.) под значками рабочего стола, на всех мониторах.

Что играть, пишет ryoku.py в gifwall.json рядом: {"path": "C:/.../anim.gif"}. Пустой path или "off": true —
плеер закрывается. Сам Windows при этом показывает первый кадр как обычные обои (его ставит ryoku.py),
поэтому, если плеер закрыт или ещё грузится, на столе просто неподвижная картинка.

Экономия:
- GIF: кадры один раз подгоняются под монитор при загрузке, дальше только показываются (почти 0 % процессора);
  память на кадры ограничена (BUDGET), большие GIF хранятся в уменьшенном виде и растягиваются при показе;
- видео: не грузится в память целиком, читается из файла по ходу показа (Qt Multimedia + FFmpeg, расшифровка
  на видеокарте, если она умеет), звук не играет, по кругу без конца;
- всё встаёт на паузу, когда рабочий стол закрыт окнами (проверка раз в секунду);
- в игровом режиме плеер не запускается.
Запуск: pythonw gifwall.pyw   (одна копия: вторая сразу закрывается, первая подхватывает новый gifwall.json)
        pythonw gifwall.pyw --still <видео> <картинка.png>   — сохранить первый кадр видео (для ryoku.py)
"""
import os, sys, json, time, ctypes, zlib, subprocess
from ctypes import wintypes as wt
import wallpaper_engine

HERE = os.path.dirname(os.path.abspath(__file__))
CONF = os.path.join(HERE, "gifwall.json")
LOG = os.path.join(HERE, "gifwall.log")
CACHE = os.path.join(HERE, "videocache")          # облегчённые копии видео (под монитор, до ~30 кадров/с)
BUDGET = 150 * 2 ** 20                      # байт на кадры всех мониторов (больше — хранить мельче)
_pylib = os.path.join(os.path.dirname(HERE), "pylib")
if os.path.isdir(_pylib):
    sys.path.insert(0, _pylib)
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"          # координаты Qt = настоящие пиксели мониторов


def log(msg):
    try:
        if os.path.exists(LOG) and os.path.getsize(LOG) > 100_000:
            os.replace(LOG, LOG + ".old")
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg.rstrip() + "\n")
    except Exception:
        pass


def conf():
    try:
        with open(CONF, encoding="utf-8") as f:
            c = json.load(f)
    except Exception:
        return None
    p = c.get("path")
    return p if p and not c.get("off") and os.path.exists(p) else None


u = ctypes.windll.user32
k32 = ctypes.windll.kernel32
for _n, _res, _args in (
        ("FindWindowW", wt.HWND, [wt.LPCWSTR, wt.LPCWSTR]),
        ("FindWindowExW", wt.HWND, [wt.HWND, wt.HWND, wt.LPCWSTR, wt.LPCWSTR]),
        ("SetParent", wt.HWND, [wt.HWND, wt.HWND]),
        ("GetWindowLongPtrW", ctypes.c_ssize_t, [wt.HWND, ctypes.c_int]),
        ("SetWindowLongPtrW", ctypes.c_ssize_t, [wt.HWND, ctypes.c_int, ctypes.c_ssize_t]),
        ("SetWindowPos", wt.BOOL, [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                   ctypes.c_uint]),
        ("SetLayeredWindowAttributes", wt.BOOL, [wt.HWND, wt.DWORD, ctypes.c_ubyte, wt.DWORD]),
        ("SendMessageTimeoutW", ctypes.c_ssize_t, [wt.HWND, ctypes.c_uint, wt.WPARAM, wt.LPARAM, ctypes.c_uint,
                                                   ctypes.c_uint, ctypes.POINTER(ctypes.c_size_t)]),
        ("IsWindow", wt.BOOL, [wt.HWND]), ("DestroyWindow", wt.BOOL, [wt.HWND]),
        ("GetAncestor", wt.HWND, [wt.HWND, ctypes.c_uint]), ("WindowFromPoint", wt.HWND, [wt.POINT]),
        ("GetClassNameW", ctypes.c_int, [wt.HWND, wt.LPWSTR, ctypes.c_int]),
        ("GetWindowTextW", ctypes.c_int, [wt.HWND, wt.LPWSTR, ctypes.c_int]),
        ("GetWindowRect", wt.BOOL, [wt.HWND, ctypes.POINTER(wt.RECT)])):
    getattr(u, _n).restype, getattr(u, _n).argtypes = _res, _args

VIDEO_EXT = (".mp4", ".m4v", ".webm", ".mkv", ".mov", ".avi", ".wmv")


def is_video(p):
    return bool(p) and p.lower().endswith(VIDEO_EXT)


def grab_still(src, out):
    """Первый кадр видео -> картинка (её ryoku.py ставит обоями Windows и берёт из неё цвета). 0 — получилось."""
    from PyQt6.QtCore import QUrl, QTimer
    from PyQt6.QtGui import QGuiApplication
    from PyQt6.QtMultimedia import QMediaPlayer, QVideoSink
    app = QGuiApplication(sys.argv[:1])
    mp, sink = QMediaPlayer(), QVideoSink()
    mp.setVideoSink(sink)
    done = [False]

    def on_frame(fr):
        if done[0] or not fr.isValid():
            return
        img = fr.toImage()
        if img.isNull():
            return
        done[0] = True
        img.save(out)
        mp.stop()
        app.quit()

    def on_err(err, text):
        log("не открыл видео %s: %s" % (os.path.basename(src), text))
        app.quit()
    sink.videoFrameChanged.connect(on_frame)
    mp.errorOccurred.connect(on_err)
    mp.setSource(QUrl.fromLocalFile(src))
    mp.play()
    QTimer.singleShot(20000, app.quit)                 # битый файл не должен висеть вечно
    app.exec()
    return 0 if done[0] and os.path.exists(out) else 2


if "--still" in sys.argv:
    _i = sys.argv.index("--still")
    try:
        sys.exit(grab_still(sys.argv[_i + 1], sys.argv[_i + 2]))
    except SystemExit:
        raise
    except Exception:
        import traceback
        log(traceback.format_exc())
        sys.exit(2)

if "--test" not in sys.argv:
    _MUTEX = k32.CreateMutexW(None, False, "Local\\GarasuGifWall")
    if k32.GetLastError() == 183:                          # уже играет: он сам перечитает gifwall.json
        sys.exit(0)
if conf() is None:
    sys.exit(0)

from PyQt6.QtCore import Qt, QTimer, QRect, QSize, QUrl
from PyQt6.QtGui import QPainter, QColor, QImageReader, QPixmap, QImage
from PyQt6.QtWidgets import QApplication, QWidget


def cls(h):
    b = ctypes.create_unicode_buffer(64)
    u.GetClassNameW(h, b, 64)
    return b.value


def wrect(h):
    r = wt.RECT()
    u.GetWindowRect(h, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom


def find_host():
    """Куда встроить плеер, чтобы он был под значками рабочего стола: (родитель, окно значков или None).
    Windows 11 24H2 и новее: значки (SHELLDLL_DefView) и WorkerW — внутри Progman; плеер кладём в Progman
    сразу под значки. Раньше: отдельный WorkerW позади окна со значками, плеер — внутрь него."""
    prog = u.FindWindowW("Progman", None)
    if not prog:
        return None, None
    res = ctypes.c_size_t()
    u.SendMessageTimeoutW(prog, 0x052C, 0xD, 0x1, 0, 1000, ctypes.byref(res))   # «создай слой обоев»
    u.SendMessageTimeoutW(prog, 0x052C, 0, 0, 0, 1000, ctypes.byref(res))
    defview = u.FindWindowExW(prog, None, "SHELLDLL_DefView", None)
    if defview and u.FindWindowExW(prog, None, "WorkerW", None):       # новый вариант
        return prog, defview
    found = []
    proc = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)

    def cb(h, l):
        if u.FindWindowExW(h, None, "SHELLDLL_DefView", None):
            nxt = u.FindWindowExW(None, h, "WorkerW", None)   # WorkerW сразу за окном со значками
            if nxt:
                found.append(nxt)
        return True
    u.EnumWindows(proc(cb), 0)
    return (found[0] if found else None), None


def monitors():
    out = []
    proc = ctypes.WINFUNCTYPE(ctypes.c_int, wt.HMONITOR, wt.HDC, ctypes.POINTER(wt.RECT), wt.LPARAM)

    def cb(hm, hdc, rc, lp):
        r = rc.contents
        out.append((r.left, r.top, r.right - r.left, r.bottom - r.top))
        return 1
    u.EnumDisplayMonitors(None, None, proc(cb), 0)
    return out


class Screen(QWidget):
    """Кусок слоя обоев размером с один монитор: показывает готовый кадр (уже подогнанный под монитор)."""

    def __init__(self, rect, frames):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.rect_, self.frames, self.i = rect, frames, 0
        self.resize(rect[2], rect[3])

    def paintEvent(self, e):
        p = QPainter(self)
        if self.frames:
            pm = self.frames[self.i % len(self.frames)]
            if pm.width() == self.width():
                p.drawPixmap(0, 0, pm)
            else:                                     # кадры хранятся уменьшенными: растянуть
                p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                p.drawPixmap(self.rect(), pm)
        else:
            p.fillRect(self.rect(), QColor(0, 0, 0))
        p.end()

    def embed(self, host, defview):
        """Вставить окно в слой обоев средствами Windows (встраивание через Qt подвешивает программу)."""
        hw = int(self.winId())
        self.show()
        u.SetParent(hw, host)
        st = u.GetWindowLongPtrW(hw, -16)
        u.SetWindowLongPtrW(hw, -16, (st & ~0x80000000) | 0x40000000)      # не POPUP, а CHILD
        hx, hy = wrect(host)[:2]
        x, y, w, h = self.rect_
        if defview:                                   # Windows 11 24H2+: «слоёное» окно сразу под значками
            u.SetWindowLongPtrW(hw, -20, u.GetWindowLongPtrW(hw, -20) | 0x80000)     # WS_EX_LAYERED
            u.SetLayeredWindowAttributes(hw, 0, 255, 2)
            u.SetWindowPos(hw, defview, x - hx, y - hy, w, h, 0x0010 | 0x0040)       # NOACTIVATE|SHOWWINDOW
        else:
            u.SetWindowPos(hw, None, x - hx, y - hy, w, h, 0x0004 | 0x0010 | 0x0040)  # + NOZORDER

    def unembed(self):
        try:
            hw = int(self.winId())
            self.hide()
            u.SetParent(hw, None)
        except Exception:
            pass
        self.deleteLater()


class Player:
    def __init__(self, app):
        self.app, self.path, self.mtime = app, None, None
        self.host, self.screens, self.mons = None, [], None
        self.delays, self.cur, self.paused, self.loader = [], 0, False, None
        self.mps, self.vws, self.embedded = [], [], False   # видео: плееры Qt и видеовиджеты (по монитору)
        self.opt = None                               # видео: идущее в фоне пересжатие в облегчённую копию
        self.play_t = QTimer(); self.play_t.setSingleShot(True); self.play_t.timeout.connect(self.next)
        self.t = QTimer(); self.t.timeout.connect(self.check); self.t.start(1000)
        self.check()

    def clear(self):
        self.play_t.stop()
        if self.loader:
            self.loader.stop(); self.loader = None
        for mp in self.mps:
            try:
                mp.stop(); mp.deleteLater()
            except Exception:
                pass
        self.mps, self.vws = [], []
        for s in self.screens:
            s.unembed()
        self.screens, self.delays, self.embedded = [], [], False

    # ---- построить заново: другая GIF, другие мониторы или Проводник перезапустился
    def build(self):
        self.clear()
        self.host, self.defview = find_host()
        self.mons = monitors()
        if not self.host:
            log("не нашёл слой обоев (Progman/WorkerW)")
            return
        if is_video(self.path):
            self.build_video()
            return
        rd = QImageReader(self.path)
        rd.setAutoTransform(True)
        n = max(1, rd.imageCount())
        sz0 = rd.size()
        need = sum(w * h * 4 for _, _, w, h in self.mons) * n
        k = min(1.0, (BUDGET / need) ** 0.5) if need else 1.0     # не влезает в память — храним мельче
        lists = {}
        for (x, y, w, h) in self.mons:
            key = (w, h)
            lists.setdefault(key, [])
            self.screens.append(Screen((x, y, w, h), lists[key]))   # одинаковые мониторы делят кадры
        self.loading = {"rd": rd, "lists": lists, "k": k, "sz0": sz0, "n": n}
        self.loader = QTimer(); self.loader.timeout.connect(self.load_some); self.loader.start(0)
        log("гружу %s: %d кадров, %dx%d, хранение %.0f%%" % (os.path.basename(self.path), n, sz0.width(),
                                                            sz0.height(), k * 100))

    # ---- видео: на каждый монитор свой плеер Qt с видеовиджетом. Кадры рисует видеокарта, процессор их
    # не трогает (раньше перевод каждого кадра в картинку ел ~35 % ядра)
    def opt_paths(self, src):
        """-> (копия, метка «копия не нужна/не вышла») для этого видео и этих мониторов."""
        try:
            mt = int(os.path.getmtime(src))
        except OSError:
            mt = 0
        mw = max(m[2] for m in self.mons); mh = max(m[3] for m in self.mons)
        key = "%08x_%dx%d" % (zlib.crc32(src.lower().encode("utf-8")) ^ mt, mw, mh)
        return os.path.join(CACHE, key + ".mp4"), os.path.join(CACHE, key + ".skip"), mw, mh

    def start_opt(self, src):
        """Один раз пересжать тяжёлое видео встроенным кодером Windows (video_opt.ps1), пока играет исходник."""
        dst, mark, mw, mh = self.opt_paths(src)
        if self.opt and self.opt["src"] == src:
            return
        self.stop_opt()
        if os.path.exists(mark):
            return
        os.makedirs(CACHE, exist_ok=True)
        key = os.path.basename(dst)[:-4]
        for f in os.listdir(CACHE):                   # копии прошлых видео больше не нужны
            if not f.startswith(key):
                try:
                    os.remove(os.path.join(CACHE, f))
                except OSError:
                    pass
        tmp = dst[:-4] + ".part.mp4"
        try:
            p = subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                                  os.path.join(HERE, "video_opt.ps1"), src, tmp, str(mw), str(mh)],
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 creationflags=0x08000000 | 0x00004000)     # без окна, пониженный приоритет
        except Exception as e:
            log("не запустил пересжатие: %s" % e); return
        self.opt = {"p": p, "src": src, "dst": dst, "tmp": tmp, "mark": mark}
        log("пересжимаю в облегчённую копию: %s" % os.path.basename(src))

    def poll_opt(self):
        o = self.opt
        if not o or o["p"].poll() is None:
            return
        self.opt = None
        out = " | ".join(l.strip() for l in o["p"].stdout.read().decode("utf-8", "replace").splitlines() if l.strip())
        code = o["p"].returncode
        log("пересжатие, код %s: %s" % (code, out))
        if code == 0 and os.path.exists(o["tmp"]):
            os.replace(o["tmp"], o["dst"])
            if o["src"] == self.path and self.mps:    # пересобрать плеер на копии (как при обычном запуске):
                self.build()                          # подмена источника на лету ломала возобновление после паузы
                log("играю облегчённую копию")
        else:
            try:
                if os.path.exists(o["tmp"]):
                    os.remove(o["tmp"])
                open(o["mark"], "w").write(out)       # 3 — и так лёгкое, 2 — не вышло: больше не пробуем
            except OSError:
                pass

    def stop_opt(self):
        if self.opt:
            try:
                self.opt["p"].kill()
            except Exception:
                pass
            self.opt = None

    def build_video(self):
        from PyQt6.QtMultimedia import QMediaPlayer
        from PyQt6.QtMultimediaWidgets import QVideoWidget
        dst = self.opt_paths(self.path)[0]
        src = dst if os.path.exists(dst) else self.path
        if src == self.path:
            self.start_opt(self.path)
        for (x, y, w, h) in self.mons:
            s = Screen((x, y, w, h), [])
            vw = QVideoWidget(s)
            vw.setGeometry(0, 0, w, h)
            vw.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatioByExpanding)   # без полос, лишнее обрезать
            mp = QMediaPlayer()                       # без QAudioOutput — звука нет
            mp.setVideoOutput(vw)
            mp.setLoops(QMediaPlayer.Loops.Infinite)
            mp.errorOccurred.connect(lambda err, text: log("ошибка видео: %s" % text))
            vw.videoSink().videoFrameChanged.connect(self.on_frame)
            self.vws.append(vw)
            mp.setSource(QUrl.fromLocalFile(src))
            self.screens.append(s)
            self.mps.append(mp)
        self.paused = False
        for mp in self.mps:
            mp.play()
        QTimer.singleShot(5000, self.on_frame)        # кадр так и не пришёл — всё равно показать
        log("включаю видео %s%s" % (os.path.basename(self.path), " (облегчённая копия)" if src != self.path else ""))

    def on_frame(self, fr=None):
        """Встраиваем окна в слой обоев только с первым кадром: без чёрной вспышки."""
        if self.embedded or not self.mps:
            return
        for s in self.screens:
            s.embed(self.host, self.defview)
        self.embedded = True
        for vw in self.vws:                           # дальше Python на каждый кадр не дёргаем — меньше нагрузки
            try:
                vw.videoSink().videoFrameChanged.disconnect(self.on_frame)
            except Exception:
                pass
        log("играю видео %s на %d мониторах" % (os.path.basename(self.path), len(self.screens)))

    def load_some(self):
        """Грузим кадры порциями, чтобы не подвешивать программу на больших GIF."""
        L = self.loading
        t0 = time.time()
        while time.time() - t0 < 0.03:
            img = L["rd"].read()
            if img.isNull():
                self.loader.stop(); self.loader = None
                self.start()
                return
            self.delays.append(max(20, L["rd"].nextImageDelay() or 100))
            for (w, h), lst in L["lists"].items():
                tw, th = max(1, round(w * L["k"])), max(1, round(h * L["k"]))
                s = img.scaled(tw, th, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                               Qt.TransformationMode.SmoothTransformation)
                s = s.copy((s.width() - tw) // 2, (s.height() - th) // 2, tw, th)
                lst.append(QPixmap.fromImage(s.convertToFormat(QImage.Format.Format_RGB32)))

    def start(self):
        if not self.delays:
            log("в GIF нет кадров"); return
        for s in self.screens:
            s.embed(self.host, self.defview)
        self.cur = 0
        log("играю %s на %d мониторах" % (os.path.basename(self.path), len(self.screens)))
        self.play_t.start(self.delays[0])

    def next(self):
        if self.paused or not self.delays:
            return
        self.cur = (self.cur + 1) % len(self.delays)
        for s in self.screens:
            s.i = self.cur; s.update()
        self.play_t.start(self.delays[self.cur])

    def check(self):
        p = conf()
        if p is None:
            self.stop_opt(); self.clear(); self.app.quit(); return
        if wallpaper_engine.is_running():
            if self.host or self.opt:
                self.stop_opt()
                self.clear()
                self.host = None
                self.paused = False
                log("Wallpaper Engine запущен — живые обои Garasu ждут его закрытия")
            return
        self.poll_opt()
        try:
            mt = os.path.getmtime(p)
        except OSError:
            mt = None
        if p != self.path or mt != self.mtime or not self.host or not u.IsWindow(self.host) \
                or monitors() != self.mons:
            self.path, self.mtime = p, mt
            self.build()
            return
        if not self.loader and not os.environ.get("GARASU_NOPAUSE"):     # NOPAUSE — только для замеров
            self.pause_hidden()

    # ---- пауза, когда стол закрыт окнами на всех мониторах: по сетке точек смотрим, видно ли рабочий стол
    def pause_hidden(self):
        seen = False
        for s in self.screens:
            x, y, w, h = s.rect_
            for i in range(1, 6):
                for j in range(1, 6):
                    hw = u.WindowFromPoint(wt.POINT(x + w * i // 6, y + h * j // 6))
                    root = u.GetAncestor(hw, 2) if hw else None          # GA_ROOT
                    if not root:
                        continue
                    if cls(root) in ("Progman", "WorkerW"):
                        seen = True; break
                    t = ctypes.create_unicode_buffer(64); u.GetWindowTextW(root, t, 64)
                    if t.value.startswith("Garasu Classic"):         # виджеты лежат на обоях — стол виден
                        seen = True; break
                if seen:
                    break
            if seen:
                break
        if seen and self.paused:
            self.paused = False
            log("стол виден — играю")
            if self.mps:
                for mp in self.mps:
                    mp.play()
            else:
                self.play_t.start(self.delays[self.cur] if self.delays else 100)
        elif not seen and not self.paused:
            self.paused = True
            log("стол закрыт окнами — пауза")
            if self.mps:
                for mp in self.mps:
                    mp.pause()
            else:
                self.play_t.stop()


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    pl = Player(app)
    app.aboutToQuit.connect(pl.clear)
    app.aboutToQuit.connect(pl.stop_opt)              # недоделанную копию начнём заново в следующий раз                 # не оставлять окна на рабочем столе
    if "--quit" in sys.argv:
        QTimer.singleShot(int(sys.argv[sys.argv.index("--quit") + 1]) * 1000, app.quit)
    return app.exec()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        import traceback
        log(traceback.format_exc())
        sys.exit(1)
