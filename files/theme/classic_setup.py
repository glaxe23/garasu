"""Доустановка лёгких виджетов (Garasu Classic) в фоне: библиотеки Qt через pip, проверка и переключение с Zebar.

Нужна тем, у кого их нет: обновились со старой версии кнопкой обновления или при установке не было интернета.
Запускает widgets.py (setup_classic_later) один раз: сразу пишет classic.tried, чтобы не ходить по кругу.
Если человек выключил лёгкие виджеты сам (classic.off), ничего не делает. Журнал — classic.log.
  python classic_setup.py
"""
import os, sys, time, subprocess

here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, here)
NOWIN = 0x08000000
PKGS = ["PyQt6", "psutil", "numpy", "winrt-runtime", "winrt-Windows.Media.Control", "winrt-Windows.Foundation",
        "winrt-Windows.Foundation.Collections", "winrt-Windows.Storage.Streams"]


def log(msg):
    try:
        with open(os.path.join(here, "classic.log"), "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + "setup: " + msg + "\n")
    except Exception:
        pass


def python():
    """python.exe рядом с pythonw.exe: pip и проверка пишут в консоль, им нужен обычный python."""
    p = os.path.join(os.path.dirname(sys.executable), "python.exe")
    return p if os.path.exists(p) else sys.executable


def check(py):
    try:
        return subprocess.run([py, os.path.join(here, "classic.py"), "--check"], creationflags=NOWIN, timeout=120,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    except Exception:
        return False


def main():
    import widgets as W
    if any(os.path.exists(f) for f in (W.CLASSIC_FLAG, W.CLASSIC_OFF, W.CLASSIC_TRIED)):
        return 0
    open(W.CLASSIC_TRIED, "w").close()
    py = python()
    if not check(py):
        user = [] if sys.prefix != sys.base_prefix else ["--user"]      # не venv: ставим пользователю
        base = [py, "-m", "pip", "install", "--quiet", "--disable-pip-version-check", "--no-warn-script-location",
                "--prefer-binary", "--retries", "5", "--timeout", "30"] + user
        log("ставлю библиотеки Qt")
        try:
            r = subprocess.run(base + PKGS, creationflags=NOWIN, timeout=1800, capture_output=True, text=True)
            if r.returncode != 0:                                       # по одной: одна неудачная не мешает остальным
                for p in PKGS:
                    subprocess.run(base + [p], creationflags=NOWIN, timeout=1200, capture_output=True)
        except Exception as e:
            log("pip: %s" % e)
    if os.path.exists(W.CLASSIC_OFF):                                   # пока ставилось, человек выключил сам
        return 0
    if not check(py):
        log("библиотеки Qt не встали: остаются виджеты Zebar")
        return 1
    open(W.CLASSIC_FLAG, "w").close()
    log("лёгкие виджеты включены")
    W.restart_zebar()                                                   # закрыть Zebar, запустить Qt
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        log("ошибка: %s" % e)
        sys.exit(1)
