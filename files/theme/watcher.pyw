"""Сторож Garasu: лёгкий фоновый скрипт, работает всегда (в том числе в игровом режиме).

1. Автоматический игровой режим. Когда в Steam запускается игра (или запущена программа из списка
   "games" в settings.json), включает игровой режим; когда игра закрыта, возвращает прежний режим.
   Если ты сам сменил режим во время игры, сторож не спорит: он действует только в момент запуска и
   закрытия игры. Выключается в панели режимов («Игровой режим сам при запуске игры»).

2. Тема по времени суток. В заданный час включает дневную или ночную тему. Срабатывает только при
   переходе день/ночь, поэтому вручную выбранная тема держится до следующего перехода.
   Настраивается внизу панели тем.

Проверка раз в 5 секунд: одно чтение реестра и маленького файла, нагрузки практически нет."""
import os, sys, json, time, ctypes, winreg, subprocess

ctypes.windll.kernel32.CreateMutexW(None, False, "RyokuWinWatcher")
if ctypes.windll.kernel32.GetLastError() == 183:
    sys.exit()

here = os.path.dirname(os.path.abspath(__file__))
SETTINGS = os.path.join(here, "settings.json")
PY = sys.executable.replace("pythonw.exe", "python.exe")
NOWIN = 0x08000000


def options():
    o = {"mode": "daily", "auto_game": True, "games": [],
         "auto_theme": {"on": False, "day": "sky", "night": "night", "day_from": 8, "night_from": 20}}
    try:
        o.update(json.load(open(SETTINGS, encoding="utf-8")))
    except Exception:
        pass
    return o


def patch(**kw):
    o = options()
    o.update(kw)
    json.dump(o, open(SETTINGS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def log(*a):
    try:
        open(os.path.join(here, "helper.log"), "a", encoding="utf-8").write(
            time.strftime("%H:%M:%S watcher: ") + " ".join(str(x) for x in a) + "\n")
    except Exception:
        pass


def steam_game():
    """Номер игры, запущенной через Steam (0, если ничего не запущено)."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
            return int(winreg.QueryValueEx(k, "RunningAppID")[0])
    except OSError:
        return 0


def listed_game(names):
    if not names:
        return False
    try:
        out = subprocess.run(["tasklist", "/fo", "csv", "/nh"], capture_output=True, text=True,
                             creationflags=NOWIN, encoding="cp866", errors="replace").stdout.lower()
        return any('"%s"' % n.lower() in out for n in names)
    except Exception:
        return False


def run(script, arg):
    subprocess.run([PY, os.path.join(here, script), arg], creationflags=NOWIN, cwd=here)


def main():
    was_game, last_part, tick = None, None, 0
    while True:
        try:
            o = options()
            # ---- игра
            if o.get("auto_game", True):
                game = bool(steam_game()) or listed_game(o.get("games"))
                if was_game is None:
                    was_game = game and o.get("mode") == "game"     # при старте ничего не переключаем
                if game and not was_game and o.get("mode") != "game":
                    log("game started -> game mode")
                    patch(auto_prev=o.get("mode", "daily"))
                    run("mode.py", "game")
                elif not game and was_game:
                    prev = o.get("auto_prev")
                    if prev and o.get("mode") == "game":
                        log("game closed ->", prev)
                        run("mode.py", prev)
                    if prev:
                        o = options()
                        o.pop("auto_prev", None)
                        json.dump(o, open(SETTINGS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
                was_game = game
            else:
                was_game = None
            # ---- тема по времени
            at = o.get("auto_theme") or {}
            if at.get("on"):
                h = time.localtime().tm_hour
                d0, n0 = int(at.get("day_from", 8)), int(at.get("night_from", 20))
                part = "day" if (d0 <= h < n0 if d0 < n0 else not (n0 <= h < d0)) else "night"
                if last_part is None:
                    last_part = part                                # при старте тему не трогаем
                elif part != last_part:
                    last_part = part
                    log("theme by time ->", at.get(part))
                    if at.get(part):
                        run("ryoku.py", at[part])
            else:
                last_part = None
        except Exception as e:
            log("error", e)
        tick += 1
        time.sleep(5)


main()
