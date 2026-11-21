"""Скачивает аниме-картинки для виджета «Фото»: по паку на тему, в папки photos/<имя темы>.

  pythonw pack_fetch.py              - скачать всё, чего ещё нет (запускается в фоне после установки)
  python pack_fetch.py --limit 1     - не больше одной картинки на тему (для проверки)

Список лежит рядом в anime_packs.json. Картинки берутся с wallhaven.cc и принадлежат своим авторам:
в самом Garasu их нет, они скачиваются на компьютер пользователя. Большие уменьшаются до 1200 точек.
Уже скачанные пропускаются, поэтому прерванную загрузку можно продолжить повторным запуском."""
import os, sys, json, time, subprocess, urllib.request

here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, here)
import widgets as W

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) garasu-photo-packs"
LOG = os.path.join(here, "helper.log")


def log(*a):
    try:
        open(LOG, "a", encoding="utf-8").write(time.strftime("%H:%M:%S packs: ") + " ".join(str(x) for x in a) + "\n")
    except OSError:
        pass
    if sys.stdout:
        print(*a)


def download(url, out):
    try:                                        # curl берёт сертификаты из Windows и умеет повторять попытку
        r = subprocess.run(["curl.exe", "-sSL", "--fail", "--retry", "2", "--connect-timeout", "20", "--max-time", "240",
                            "-A", UA, "-o", out, url], creationflags=0x08000000, capture_output=True, timeout=300)
        if r.returncode == 0 and os.path.getsize(out) > 20000:
            return True
    except Exception:
        pass
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=120) as resp, open(out, "wb") as f:
            f.write(resp.read())
        return os.path.getsize(out) > 20000
    except Exception:
        return False


def main(limit=None):
    from PIL import Image
    try:
        packs = json.load(open(os.path.join(here, "anime_packs.json"), encoding="utf-8"))
    except Exception as e:
        log("нет списка:", e)
        return 0
    got = failed = 0
    for theme, items in packs.items():
        folder = os.path.join(W.PHOTOS, theme)
        os.makedirs(folder, exist_ok=True)
        for it in items[:limit]:
            out = os.path.join(folder, "anime-%s.jpg" % it["id"])
            if os.path.exists(out):
                continue
            tmp = out + ".part"
            ok = download(it["url"], tmp)
            if ok:
                try:
                    im = Image.open(tmp).convert("RGB")
                    im.thumbnail((1200, 1200))
                    im.save(out, quality=86, optimize=True)
                    got += 1
                except Exception:
                    ok = False
            if os.path.exists(tmp):
                os.remove(tmp)
            if not ok:
                failed += 1
                if failed >= 3 and got == 0:             # сайт недоступен: не тянем время
                    log("сайт с картинками недоступен, скачаю при следующем запуске")
                    return got
    log("скачано картинок: %d, не удалось: %d" % (got, failed))
    return got


if __name__ == "__main__":
    lim = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
    main(lim)
