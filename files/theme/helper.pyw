"""Фоновый помощник виджетов Garasu. Запускается из start.bat, работает в одном экземпляре.

  - Задачи: следит за заметкой Obsidian и обновляет tasks.json для виджета «Задачи».
  - Фото: следит за папкой C:/garasu/photos, делает уменьшенные копии для виджета «Фото».
  - Музыка: слушает звук компьютера и отдаёт спектр виджету «Музыка» (если стоит библиотека
    pyaudiowpatch и виджет включён). См. audio.py.
"""
import os, re, sys, json, time, ctypes, hashlib, threading, subprocess, urllib.request, urllib.parse

ctypes.windll.kernel32.CreateMutexW(None, False, "RyokuWinHelper")
if ctypes.windll.kernel32.GetLastError() == 183:
    sys.exit()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import widgets as W
import tasks as T

LOG = os.path.join(W.here, "helper.log")
PDIR = os.path.join(W.zdir, "photos")
EXT = (".jpg", ".jpeg", ".png", ".webp", ".bmp")


def log(*a):
    try:
        if os.path.exists(LOG) and os.path.getsize(LOG) > 200000:
            os.remove(LOG)
        open(LOG, "a", encoding="utf-8").write(time.strftime("%H:%M:%S ") + " ".join(str(x) for x in a) + "\n")
    except Exception:
        pass


def mtime(p):
    try:
        return os.path.getmtime(p)
    except OSError:
        return 0


def sync_photos(last):
    """Уменьшенные копии картинок из папки photos -> в папку виджета, список -> photos.json."""
    os.makedirs(W.PHOTOS, exist_ok=True)
    src = sorted(f for f in os.listdir(W.PHOTOS) if f.lower().endswith(EXT))
    sig = [(f, mtime(os.path.join(W.PHOTOS, f))) for f in src]
    if sig == last:
        return last
    from PIL import Image, ImageOps
    os.makedirs(PDIR, exist_ok=True)
    keep = []
    for f, mt in sig:
        name = hashlib.md5(("%s|%s" % (f, mt)).encode("utf-8")).hexdigest()[:12] + ".jpg"
        out = os.path.join(PDIR, name)
        if not os.path.exists(out):
            try:
                im = ImageOps.exif_transpose(Image.open(os.path.join(W.PHOTOS, f))).convert("RGB")
                im.thumbnail((1000, 1000))
                im.save(out, quality=88)
            except Exception as e:
                log("photo", f, e)
                continue
        keep.append(name)
    for f in os.listdir(PDIR):                       # старые уменьшенные копии больше не нужны
        if f not in keep:
            try:
                os.remove(os.path.join(PDIR, f))
            except OSError:
                pass
    tmp = os.path.join(W.zdir, "photos.json.tmp")
    json.dump({"files": ["photos/" + k for k in keep]}, open(tmp, "w", encoding="utf-8"))
    os.replace(tmp, os.path.join(W.zdir, "photos.json"))
    log("photos:", len(keep))
    return sig


# ---------------------------------------------------------------- что сейчас играет: обложка и текст песни
ART = os.path.join(W.zdir, "art")
NOW = {"title": "", "artist": "", "art": "", "lyrics": [], "synced": False, "state": "off", "app": "", "vol": None}
track = {"key": "", "fetched": ""}


def write_now():
    tmp = os.path.join(W.zdir, "nowplaying.json.tmp")
    json.dump(NOW, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(tmp, os.path.join(W.zdir, "nowplaying.json"))


def media_watch():
    """Читает строки от media.ps1: когда трек меняется, готовит обложку для виджета."""
    os.makedirs(ART, exist_ok=True)
    ps1 = os.path.join(W.here, "media.ps1")
    while True:
        try:
            p = subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps1, ART],
                                 stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, creationflags=0x08000000,
                                 encoding="utf-8", errors="replace")
            for line in p.stdout:
                line = line.strip()
                if not line.startswith("{"):
                    continue
                info = json.loads(line)
                art = ""
                if info.get("art"):
                    try:
                        from PIL import Image, ImageOps
                        name = hashlib.md5((info["title"] + "|" + info["artist"]).encode("utf-8")).hexdigest()[:12] + ".jpg"
                        im = ImageOps.fit(Image.open(os.path.join(ART, "art.raw")).convert("RGB"), (400, 400))
                        im.save(os.path.join(ART, name), quality=88)
                        art = "art/" + name
                        for f in os.listdir(ART):
                            if f.endswith(".jpg") and f != name:
                                os.remove(os.path.join(ART, f))
                    except Exception as e:
                        log("art", e)
                key = info["title"] + "|" + info["artist"]
                if not art and info["title"]:
                    art = online_art(info["title"], info["artist"])
                if key != track["key"]:
                    NOW.update(lyrics=[], synced=False, state="off")
                    track["key"], track["fetched"] = key, ""
                NOW.update(title=info["title"], artist=info["artist"], art=art, duration=info.get("duration", 0),
                           app=info.get("app", ""))
                write_now()
        except Exception as e:
            log("media", e)
        time.sleep(5)


def same(a, b):
    """Похожи ли две строки (без регистра, знаков и пробелов)."""
    n = lambda s: re.sub(r"[\W_]+", "", s.lower())
    a, b = n(a), n(b)
    return bool(a and b) and (a in b or b in a)


def find_art_url(t, a):
    """Ссылка на обложку: сначала iTunes, потом Deezer. Исполнителей через запятую пробуем по одному."""
    people = [p.strip() for p in re.split(r",|&| feat\.? | ft\.? | x ", a) if p.strip()] or [""]

    def ok(track, names):
        return same(track, t) and (not people[0] or any(same(n, p) for n in names for p in people))

    for who in people[:2] + [""]:
        term = (who + " " + t).strip()
        try:
            res = get_json("https://itunes.apple.com/search?" + urllib.parse.urlencode(
                {"term": term, "entity": "song", "limit": 8})).get("results", [])
            hit = next((r for r in res if ok(r.get("trackName", ""), [r.get("artistName", "")])), None)
            if hit:
                return hit["artworkUrl100"].replace("100x100bb", "600x600bb")
        except Exception as e:
            log("itunes", e)
        try:
            res = get_json("https://api.deezer.com/search?" + urllib.parse.urlencode({"q": term, "limit": 8})).get("data", [])
            hit = next((r for r in res if ok(r.get("title", ""), [r.get("artist", {}).get("name", "")])), None)
            if hit and hit.get("album", {}).get("cover_big"):
                return hit["album"]["cover_big"]
        except Exception as e:
            log("deezer", e)
    return ""


def online_art(title, artist):
    """Обложка из каталога iTunes, когда Windows её не даёт (например, сайт в браузере). '' если не нашлась."""
    try:
        if not W.load()["media"]["art"]:
            return ""
        t, a = tidy(title, artist)
        name = hashlib.md5((title + "|" + artist).encode("utf-8")).hexdigest()[:12] + ".jpg"
        out = os.path.join(ART, name)
        if not os.path.exists(out):
            url = find_art_url(t, a)
            if not url:
                log("art online: not found", t, "|", a)
                return ""
            req = urllib.request.Request(url, headers={"User-Agent": "desktop-widget/1.0"})
            with urllib.request.urlopen(req, timeout=12) as r:
                data = r.read()
            open(out, "wb").write(data)
            log("art online: ok")
        for f in os.listdir(ART):
            if f.endswith(".jpg") and f != name:
                os.remove(os.path.join(ART, f))
        return "art/" + name
    except Exception as e:
        log("art online", e)
        return ""


def tidy(title, artist):
    """«Исполнитель - Песня (Official Video)» с YouTube -> (песня, исполнитель)."""
    t = re.sub(r"[\(\[][^)\]]*[\)\]]", "", title).strip()
    if " - " in t:
        a, t2 = t.split(" - ", 1)
        return t2.strip(), a.strip()
    return t, re.sub(r"\s*-\s*Topic$|VEVO$", "", artist).strip()


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "desktop-widget/1.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_lyrics(title, artist):
    """Текст песни с lrclib.net. Наружу уходят только название и исполнитель."""
    t, a = tidy(title, artist)
    if not t:
        return [], False
    q = urllib.parse.urlencode({"track_name": t, "artist_name": a})
    found = None
    try:
        found = get_json("https://lrclib.net/api/get?" + q)
    except Exception:
        try:
            res = get_json("https://lrclib.net/api/search?" + q) or get_json(
                "https://lrclib.net/api/search?" + urllib.parse.urlencode({"q": (a + " " + t).strip()}))
            found = next((r for r in res if r.get("syncedLyrics")), res[0] if res else None)
        except Exception as e:
            log("lyrics", e)
    if not found or not (found.get("syncedLyrics") or found.get("plainLyrics")):
        lrc = netease_lyrics(t, a)                      # второй источник
        if not lrc:
            return [], False
        found = {"syncedLyrics": lrc}
    if found.get("syncedLyrics"):
        out = []
        for line in found["syncedLyrics"].splitlines():
            m = re.match(r"\[(\d+):(\d+(?:\.\d+)?)\]\s*(.*)", line)
            if m and m.group(3).strip():
                out.append([int(m.group(1)) * 60 + float(m.group(2)), m.group(3).strip()])
        return out, True
    return [[0, l.strip()] for l in (found.get("plainLyrics") or "").splitlines() if l.strip()], False


def netease_lyrics(t, a):
    """Текст с таймкодами из открытого каталога NetEase (music.163.com). '' если нет."""
    try:
        api = "https://music.163.com/api/"
        res = get_json(api + "search/get?" + urllib.parse.urlencode({"s": (a + " " + t).strip(), "type": 1, "limit": 5}))
        for s in res.get("result", {}).get("songs", []):
            if same(s.get("name", ""), t) and (not a or any(same(x.get("name", ""), a) for x in s.get("artists", []))):
                lrc = (get_json(api + "song/lyric?id=%s&lv=1&kv=1&tv=-1" % s["id"]).get("lrc") or {}).get("lyric", "")
                lines = [l for l in lrc.splitlines() if not re.search(r"\]\s*(作词|作曲|编曲|制作)", l)]
                if len(lines) > 3:
                    return "\n".join(lines)
    except Exception as e:
        log("netease", e)
    return ""


# ---------------------------------------------------------------- громкость приложения, в котором играет музыка
import queue
vol_q = queue.Queue()


def on_track(info):
    """Плеер на обоях сообщил, что играет: готовим обложку, а текст песни подтянет lyrics_watch.
    Раньше за этим следил отдельный процесс PowerShell (media.ps1), он занимал около 90 МБ."""
    title, artist = str(info.get("title", "")), str(info.get("artist", ""))
    key = title + "|" + artist
    if key != track["key"]:
        NOW.update(lyrics=[], synced=False, state="off")
        track["key"], track["fetched"] = key, ""
    NOW.update(title=title, artist=artist, app=str(info.get("app", "")), duration=info.get("duration", 0))
    if key != track.get("art_key"):
        track["art_key"] = key
        NOW["art"] = ""
        write_now()
        os.makedirs(ART, exist_ok=True)
        art = online_art(title, artist) if title else ""
        if track["key"] == key:
            NOW["art"] = art
    write_now()


def on_ws(msg):
    if msg.startswith("track:"):
        try:
            on_track(json.loads(msg[6:]))
        except Exception as e:
            log("track", e)
        return
    if msg.startswith("vol:"):
        try:
            vol_q.put(max(0, min(100, int(float(msg[4:])))))
        except ValueError:
            pass


def app_sessions(AudioUtilities):
    """Звуковые сессии приложения, которое играет трек (по имени из Windows, например Chrome -> chrome.exe)."""
    app = re.sub(r"[\W_]+", "", (NOW.get("app") or "").lower().replace(".exe", ""))
    live, match = [], []
    for s in AudioUtilities.GetAllSessions():
        if not s.Process:
            continue
        name = re.sub(r"[\W_]+", "", s.Process.name().lower().replace(".exe", ""))
        if app and name and (name in app or app in name):
            match.append(s)
        elif s.State == 1:
            live.append(s)
    return match or live          # не узнали приложение: берём всё, что сейчас звучит


def volume_watch():
    try:
        import comtypes
        from pycaw.pycaw import AudioUtilities
        comtypes.CoInitialize()
    except Exception as e:
        log("app volume off:", e)
        return
    log("app volume: ready")
    while True:
        try:
            try:
                v = vol_q.get(timeout=2.5)
                while not vol_q.empty():
                    v = vol_q.get_nowait()
                for s in app_sessions(AudioUtilities):
                    s.SimpleAudioVolume.SetMasterVolume(v / 100, None)
                cur = v
            except queue.Empty:
                ss = app_sessions(AudioUtilities) if NOW.get("title") else []
                cur = round(max(s.SimpleAudioVolume.GetMasterVolume() for s in ss) * 100) if ss else None
            if cur != NOW.get("vol"):
                NOW["vol"] = cur
                write_now()
        except Exception as e:
            log("volume", e)
            time.sleep(2)


def lyrics_watch():
    while True:
        time.sleep(2.5)
        try:
            on = W.load()["media"]["lyrics"]
            key = track["key"]
            if not on:
                if NOW["state"] != "off":
                    NOW.update(lyrics=[], synced=False, state="off")
                    track["fetched"] = ""
                    write_now()
                continue
            if key and key != "|" and track["fetched"] != key:
                track["fetched"] = key
                NOW.update(lyrics=[], synced=False, state="loading")
                write_now()
                lines, synced = fetch_lyrics(NOW["title"], NOW["artist"])
                if track["key"] == key:
                    NOW.update(lyrics=lines, synced=synced, state="ok" if lines else "none")
                    write_now()
                    log("lyrics:", len(lines), "synced" if synced else "plain")
        except Exception as e:
            log("lyrics loop", e)


FOCUS = os.path.join(W.here, "bar_focus.txt")


def write_focus(tasks_data):
    """Одна строка для панели: заметка календаря на сегодня, иначе первая невыполненная задача."""
    text = ""
    try:
        notes = json.load(open(os.path.join(W.zdir, "calendar_notes.json"), encoding="utf-8"))
        today = notes.get(time.strftime("%Y-%m-%d"), "")
        if today:
            text = "сегодня: " + today
    except Exception:
        pass
    if not text and tasks_data:
        first = next((i["text"] for i in tasks_data.get("items", []) if not i["done"]), "")
        left = tasks_data.get("open", 0)
        if first:
            text = first + ("  +%d" % (left - 1) if left > 1 else "")
    text = " ".join(text.split())
    if len(text) > 44:
        text = text[:43].rstrip() + "…"
    try:
        if not os.path.exists(FOCUS) or open(FOCUS, encoding="utf-8").read() != text:
            open(FOCUS, "w", encoding="utf-8").write(text)
    except Exception as e:
        log("focus", e)


def main():
    log("start")
    threading.Thread(target=lyrics_watch, daemon=True).start()
    threading.Thread(target=volume_watch, daemon=True).start()
    audio = None
    try:
        import audio as A
        audio = A.Server(W.AUDIO_PORT, log, on_ws)
    except Exception as e:
        log("audio off:", e)
    last_note, last_cal, last_photos, tick = None, None, None, 0
    while True:
        try:
            cfg = W.load()
            note = cfg["tasks"]["note"]
            key = (note, mtime(note))
            cal = mtime(os.path.join(W.zdir, "calendar_notes.json"))
            if key != last_note or (cal, time.strftime("%d")) != last_cal:
                last_note, last_cal = key, (cal, time.strftime("%d"))
                write_focus(T.sync(cfg))
            if tick % 3 == 0:
                last_photos = sync_photos(last_photos)
            if audio:
                audio.enable(cfg["visual"]["on"] or (cfg["media"]["on"] and cfg["media"]["wave"]))
        except Exception as e:
            log("loop", e)
        tick += 1
        time.sleep(2.0)


main()
