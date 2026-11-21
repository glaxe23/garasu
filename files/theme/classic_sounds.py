"""Звуки таймера как в pomodoro.html: сигнал из трёх нот и фон «дождь» / «шум».
Звук один раз синтезируется в wav (папка sounds/) и играется через winsound — без лишних библиотек.
winsound играет один звук за раз: сигнал на время прерывает фон, потом фон включается снова."""
import os, math, random, struct, wave, threading

HERE = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.join(HERE, "sounds")
SR = 22050
_lock = threading.Lock()
_now = {"amb": None, "chime": 0}   # какой фон должен играть (путь к wav) и когда закончится сигнал


def _write(path, data):
    os.makedirs(DIR, exist_ok=True)
    tmp = path + ".tmp"
    with wave.open(tmp, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(b"".join(struct.pack("<h", max(-32767, min(32767, int(v * 32767)))) for v in data))
    os.replace(tmp, path)


def _biquad(data, kind, f0, q=0.707):
    """Фильтр RBJ, как BiquadFilter в браузере (highpass / lowpass)."""
    w0 = 2 * math.pi * f0 / SR
    a = math.sin(w0) / (2 * q); c = math.cos(w0)
    if kind == "lp":
        b0, b1, b2 = (1 - c) / 2, 1 - c, (1 - c) / 2
    else:
        b0, b1, b2 = (1 + c) / 2, -(1 + c), (1 + c) / 2
    a0, a1, a2 = 1 + a, -2 * c, 1 - a
    b0, b1, b2, a1, a2 = b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0
    x1 = x2 = y1 = y2 = 0.0
    out = []
    for x in data:
        y = b0 * x + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        x2, x1, y2, y1 = x1, x, y1, y
        out.append(y)
    return out


def chime_wav():
    path = os.path.join(DIR, "chime.wav")
    if os.path.exists(path):
        return path
    n = int(SR * (0.36 + 0.65))
    d = [0.0] * n
    for i, f in enumerate((880, 1108, 1318)):
        s = int(i * 0.18 * SR)
        for k in range(int(0.65 * SR)):
            t = k / SR
            # подъём за 30 мс, затем экспоненциальный спад до тишины к 0.6 с
            g = 0.18 * (t / 0.03) if t < 0.03 else 0.18 * (0.0001 / 0.18) ** ((t - 0.03) / 0.57)
            if s + k < n:
                d[s + k] += g * math.sin(2 * math.pi * f * t)
    _write(path, d)
    return path


def amb_wav(kind, vol):
    """kind: rain | pink; vol: ambvol из настроек 0..100."""
    path = os.path.join(DIR, "%s_%d.wav" % (kind, vol))
    if os.path.exists(path):
        return path
    rnd = random.Random(7)
    n = SR * 6
    d = []
    b0 = b1 = b2 = b3 = b4 = b5 = b6 = drop = dk = 0.0
    p_drop = 0.0009 * 48000 / SR                  # в html частота капель задана для 48 кГц
    for _ in range(n):
        w = rnd.random() * 2 - 1
        b0 = 0.99886 * b0 + w * 0.0555179; b1 = 0.99332 * b1 + w * 0.0750759; b2 = 0.96900 * b2 + w * 0.1538520
        b3 = 0.86650 * b3 + w * 0.3104856; b4 = 0.55000 * b4 + w * 0.5329522; b5 = -0.7616 * b5 - w * 0.0168980
        v = (b0 + b1 + b2 + b3 + b4 + b5 + b6 + w * 0.5362) * 0.11; b6 = w * 0.115926
        if kind == "rain":
            if rnd.random() < p_drop:
                drop = 0.5 + rnd.random() * 0.6; dk = (0.9 + rnd.random() * 0.08) ** (48000 / SR)
            v = v * 0.55 + w * drop; drop *= dk
        d.append(v)
    d = _biquad(d, "hp", 500 if kind == "rain" else 250)
    d = _biquad(d, "lp", 7000 if kind == "rain" else 3200)
    f = int(SR * 0.05)                             # сшивка конца с началом без щелчка
    for i in range(f):
        k = i / f; d[i] = d[i] * k + d[n - f + i] * (1 - k)
    d = d[:n - f]
    g = vol / 100 * 0.35
    _write(path, [v * g for v in d])
    return path


def _play(path, loop):
    try:
        import winsound
        fl = winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT
        if path is None:
            winsound.PlaySound(None, 0)
        else:
            winsound.PlaySound(path, fl | (winsound.SND_LOOP if loop else 0))
    except Exception:
        pass


def ambient(kind, vol=35):
    """Включить фон (rain / pink) или выключить (None / off). Синтез в потоке, чтобы окна не стопорились."""
    def go():
        with _lock:
            path = amb_wav(kind, int(vol)) if kind and kind != "off" else None
            if path == _now["amb"]:
                return
            _now["amb"] = path
            import time
            if time.time() > _now["chime"]:       # во время сигнала фон включит сам сигнал
                _play(path, True)
    threading.Thread(target=go, daemon=True).start()


def chime():
    import time
    _now["chime"] = time.time() + 1.6

    def go():
        with _lock:
            _play(chime_wav(), False)
        time.sleep(1.1)
        with _lock:
            if _now["amb"]:
                _play(_now["amb"], True)          # вернуть фон после сигнала
    threading.Thread(target=go, daemon=True).start()


def stop():
    _now["amb"] = None
    _play(None, False)
