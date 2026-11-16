"""Спектр звука компьютера для виджета «Музыка».

Слушает то, что играет в колонках или наушниках (WASAPI loopback, библиотека pyaudiowpatch),
считает спектр (numpy) и 30 раз в секунду рассылает 96 чисел 0..255 всем подключённым виджетам
по локальному WebSocket (только 127.0.0.1, наружу ничего не уходит и не записывается)."""
import socket, threading, time, base64, hashlib
import numpy as np
import pyaudiowpatch as pyaudio

BANDS, FPS, NFFT = 96, 30, 2048


class Server:
    def __init__(self, port, log=print, on_message=None):
        self.log = log
        self.on_message = on_message
        self.clients, self.lock = [], threading.Lock()
        self.on = False
        self.buf = np.zeros(NFFT, dtype=np.float32)
        self.fresh = 0.0
        self.stream = self.pa = None
        self.rate = 48000
        self.peak = -50.0
        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", port))
        self.sock.listen(8)
        threading.Thread(target=self.accept, daemon=True).start()
        threading.Thread(target=self.pump, daemon=True).start()
        log("audio: listening on", port)

    # ---------------------------------------------------------- подключения виджетов
    def accept(self):
        while True:
            try:
                c, _ = self.sock.accept()
                c.settimeout(3)
                req = c.recv(4096).decode("latin1")
                key = [l.split(":", 1)[1].strip() for l in req.split("\r\n") if l.lower().startswith("sec-websocket-key")]
                if not key:
                    c.close()
                    continue
                acc = base64.b64encode(hashlib.sha1((key[0] + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
                c.sendall(("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                           "Sec-WebSocket-Accept: %s\r\n\r\n" % acc).encode())
                c.settimeout(None)
                with self.lock:
                    self.clients.append(c)
                threading.Thread(target=self.reader, args=(c,), daemon=True).start()
            except Exception as e:
                self.log("audio accept", e)
                time.sleep(1)

    def reader(self, c):
        """Читает текстовые сообщения виджета (например «vol:35») и передаёт их помощнику."""
        def take(n):
            b = b""
            while len(b) < n:
                part = c.recv(n - len(b))
                if not part:
                    raise ConnectionError
                b += part
            return b
        try:
            while True:
                h = take(2)
                op, n = h[0] & 0x0F, h[1] & 0x7F
                if n == 126:
                    n = int.from_bytes(take(2), "big")
                elif n == 127:
                    n = int.from_bytes(take(8), "big")
                mask = take(4) if h[1] & 0x80 else bytes(4)
                data = bytes(b ^ mask[i % 4] for i, b in enumerate(take(n)))
                if op == 8:
                    break
                if op == 1 and self.on_message:
                    self.on_message(data.decode("utf-8", "replace"))
        except Exception:
            pass
        with self.lock:
            if c in self.clients:
                self.clients.remove(c)
        try:
            c.close()
        except Exception:
            pass

    # ---------------------------------------------------------- захват звука
    def enable(self, on):
        self.on = bool(on)

    def callback(self, data, frames, t, status):
        a = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768
        if self.channels > 1:
            a = a.reshape(-1, self.channels).mean(axis=1)
        n = min(len(a), NFFT)
        self.buf = np.concatenate((self.buf[n:], a[-n:]))
        self.fresh = time.time()
        return (None, pyaudio.paContinue)

    def open(self):
        self.pa = pyaudio.PyAudio()
        api = self.pa.get_host_api_info_by_type(pyaudio.paWASAPI)
        dev = self.pa.get_device_info_by_index(api["defaultOutputDevice"])
        if not dev.get("isLoopbackDevice"):
            for lb in self.pa.get_loopback_device_info_generator():
                if dev["name"] in lb["name"]:
                    dev = lb
                    break
        self.channels = int(dev["maxInputChannels"])
        self.rate = int(dev["defaultSampleRate"])
        self.stream = self.pa.open(format=pyaudio.paInt16, channels=self.channels, rate=self.rate, input=True,
                                   input_device_index=dev["index"], frames_per_buffer=1024,
                                   stream_callback=self.callback)
        self.opened = time.time()
        if dev["name"] != getattr(self, "last_dev", None):      # в журнал пишем только смену устройства
            self.last_dev = dev["name"]
            self.log("audio: capture", dev["name"], self.rate, "Hz", self.channels, "ch")

    def close(self):
        try:
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
            if self.pa:
                self.pa.terminate()
        except Exception:
            pass
        self.stream = self.pa = None

    def spectrum(self):
        if time.time() - self.fresh > 0.25:               # тишина: loopback ничего не присылает
            return np.zeros(BANDS)
        mag = np.abs(np.fft.rfft(self.buf * np.hanning(NFFT)))
        freqs = np.fft.rfftfreq(NFFT, 1 / self.rate)
        edges = np.geomspace(45, 14000, BANDS + 1)
        out = np.zeros(BANDS)
        for i in range(BANDS):
            m = (freqs >= edges[i]) & (freqs < edges[i + 1])
            if m.any():
                out[i] = mag[m].max()
            else:                                          # узкая полоса на низких частотах: ближайшая точка
                out[i] = mag[np.argmin(np.abs(freqs - (edges[i] + edges[i + 1]) / 2))]
        # в децибелы: тихие и громкие звуки видны одинаково хорошо, как в настоящих анализаторах
        db = 20 * np.log10(out / (NFFT / 4) + 1e-7) + np.linspace(0, 14, BANDS)   # верхние частоты тише, приподнимаем
        self.peak = max(self.peak - 0.02, db.max(), -50.0)     # автогромкость: верх шкалы медленно опускается к звуку
        return np.clip((db - (self.peak - 48)) / 48, 0, 1) ** 1.4

    def pump(self):
        while True:
            time.sleep(1 / FPS)
            try:
                want = self.on and bool(self.clients)
                if want and not self.stream:
                    self.open()
                elif not want and self.stream:
                    self.close()
                elif self.stream and time.time() - max(self.fresh, self.opened) > 45:
                    self.close()                           # давно нет данных: возможно, сменилось устройство вывода
                if not self.clients:
                    continue
                v = (self.spectrum() if self.stream else np.zeros(BANDS))
                if not v.any():                      # тишина: шлём нули 3 раза в секунду, а не 30
                    self.quiet = getattr(self, 'quiet', 0) + 1
                    if self.quiet > 3 and self.quiet % 10:
                        continue
                else:
                    self.quiet = 0
                frame = bytes([0x82, BANDS]) + (v * 255).astype(np.uint8).tobytes()
                with self.lock:
                    for c in self.clients[:]:
                        try:
                            c.sendall(frame)
                        except Exception:
                            self.clients.remove(c)
                            try:
                                c.close()
                            except Exception:
                                pass
            except Exception as e:
                self.log("audio pump", e)
                self.close()
                time.sleep(3)
