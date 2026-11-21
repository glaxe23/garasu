"""Обновление Garasu с GitHub без переустановки.

  python update.py check     - напечатать «local remote»: версию на компьютере и последнюю на GitHub
  python update.py apply     - скачать последнюю версию и заменить файлы оформления

Меняются только файлы программы (скрипты, виджеты, запуск). Личное не трогается: настройки, расстановка
виджетов, темы, заметки, обои, настройки GlazeWM. Версия на компьютере записана в version.txt; в папке
разработки этого файла нет, и обновление там отключено."""
import os, re, sys, json, shutil, zipfile, tempfile, urllib.request

here = os.path.dirname(os.path.abspath(__file__))
root = os.path.dirname(here)
REPO = "glaxe23/garasu"
API = "https://api.github.com/repos/%s/releases/latest" % REPO
VFILE = os.path.join(here, "version.txt")


def num(s):
    m = re.search(r"\d+(?:\.\d+)+|\d+", s or "")
    return tuple(int(x) for x in m.group(0).split(".")) if m else ()


def local():
    try:
        return open(VFILE, encoding="utf-8").read().strip()
    except OSError:
        return ""


def latest():
    """(версия, ссылка на архив) последнего релиза."""
    req = urllib.request.Request(API, headers={"User-Agent": "garasu-updater", "Accept": "application/vnd.github+json"})
    d = json.load(urllib.request.urlopen(req, timeout=20))
    return ".".join(str(n) for n in num(d.get("tag_name", ""))), d.get("zipball_url", "")


def install(files, dst_root, zdir):
    """Разложить папку files из архива по местам: theme и запуск в папку установки, виджеты в папку Zebar."""
    n = 0
    for sub, to in (("theme", os.path.join(dst_root, "theme")), ("zebar", zdir)):
        for name in os.listdir(os.path.join(files, sub)):
            s, d = os.path.join(files, sub, name), os.path.join(to, name)
            if os.path.isdir(s):                               # папки (если появятся в новых версиях) — целиком
                shutil.copytree(s, d, dirs_exist_ok=True)
            else:
                shutil.copy2(s, d)
            n += 1
    for name in ("start.bat", "uninstall.ps1", "Uninstall.bat"):
        if os.path.exists(os.path.join(files, name)):
            shutil.copy2(os.path.join(files, name), os.path.join(dst_root, name))
            n += 1
    return n


def apply():
    if not local():
        return "В папке разработки обновление отключено."
    ver, url = latest()
    if not url or num(ver) <= num(local()):
        return "Уже последняя версия: %s" % local()
    tmp = tempfile.mkdtemp(prefix="garasu-upd-", dir=root)       # рядом с установкой: в пути нет кириллицы
    try:
        z = os.path.join(tmp, "new.zip")
        req = urllib.request.Request(url, headers={"User-Agent": "garasu-updater"})
        with urllib.request.urlopen(req, timeout=120) as r, open(z, "wb") as f:
            shutil.copyfileobj(r, f)
        with zipfile.ZipFile(z) as zf:
            zf.extractall(tmp)
        files = next((os.path.join(d, "files") for d, ds, _ in os.walk(tmp) if "files" in ds
                      and os.path.exists(os.path.join(d, "files", "theme", "ryoku.py"))), None)
        if not files:
            return "В архиве релиза нет файлов программы."
        sys.path.insert(0, here)
        import widgets as W
        n = install(files, root, W.zdir)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    # перечитать новые скрипты отдельными процессами: панель, список виджетов и сами виджеты
    import subprocess
    NOWIN = 0x08000000
    subprocess.run([sys.executable, os.path.join(here, "ryoku.py")], creationflags=NOWIN)
    try:
        W.stop_classic()                       # Qt-виджеты перезапустятся уже с новым кодом (их поднимет widgets.py)
    except Exception:
        pass
    subprocess.run([sys.executable, os.path.join(here, "widgets.py")], creationflags=NOWIN)
    return "Обновлено до %s (файлов: %d)" % (ver, n)


if __name__ == "__main__":
    try:
        if len(sys.argv) > 1 and sys.argv[1] == "apply":
            out = apply()
        else:
            out = "%s %s" % (local() or "-", latest()[0] or "-")
    except Exception as e:
        out = "ошибка: %s" % e
    if sys.stdout:
        print(out)
