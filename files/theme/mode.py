"""Режимы рабочего стола Garasu.

  python mode.py            - показать текущий режим
  python mode.py daily      - повседневный: всё включено
  python mode.py work       - рабочий: задачи, календарь с заметками, таймер помодоро; без отвлекающего
  python mode.py game       - игровой: максимум производительности

Что делает игровой режим: закрывает виджеты на обоях (Zebar и его браузерные процессы) и фонового
помощника, убирает док, оставляет короткую панель, ставит плитку окон на паузу (чтобы Alt-сочетания
не мешали в играх) и включает план питания «Высокая производительность». При выходе из игрового
режима всё возвращается, включая прежний план питания.

У каждого режима свой набор и расположение виджетов: они запоминаются при переключении
в папке profiles."""
import os, sys, json, copy, subprocess

here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, here)
import widgets as W

SETTINGS = os.path.join(here, "settings.json")
PROFILES = os.path.join(here, "profiles")
NOWIN = 0x08000000
HIGH_PERF = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"
MODES = {
    "daily": ("Повседневный", "Все виджеты, плеер, фото. Как обычно."),
    "work":  ("Рабочий", "Задачи, календарь с заметками и таймер помодоро. Фото и монитор убраны."),
    "game":  ("Игровой", "Максимум производительности: без виджетов и дока, плитка на паузе, питание на максимум."),
}
# какие виджеты включены в режиме, когда он открывается впервые (дальше запоминается твоя расстановка)
FIRST = {
    "work": {"clock": True, "sysmon": False, "media": True, "tasks": True, "photo": False, "visual": False,
             "calendar": True, "pomodoro": True, "weather": False, "counters": False},
}


def options():
    o = {"dock": "auto", "side_gap": 24, "mode": "daily"}
    try:
        o.update(json.load(open(SETTINGS, encoding="utf-8")))
    except Exception:
        pass
    return o


def save_options(o):
    json.dump(o, open(SETTINGS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def run(args, **kw):
    return subprocess.run(args, creationflags=NOWIN, capture_output=True, text=True, **kw)


def ps(cmd):
    return run(["powershell", "-NoProfile", "-Command", cmd]).stdout.strip()


def stop_helper():
    ps("$a='helper'+'.pyw'; $b='media'+'.ps1'; Get-CimInstance Win32_Process | Where-Object { "
       "($_.Name -eq 'pythonw.exe' -and $_.CommandLine -like \"*$a*\") -or "
       "($_.Name -eq 'powershell.exe' -and $_.CommandLine -like \"*-File*$b*\") } | "
       "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }")


def stop_freeze():
    ps("$a='freeze'+'.pyw'; Get-CimInstance Win32_Process | Where-Object { "
       "$_.Name -eq 'pythonw.exe' -and $_.CommandLine -like \"*$a*\" } | "
       "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }")


def start_helper():
    subprocess.Popen([W.PYW, os.path.join(here, "helper.pyw")], cwd=here, creationflags=NOWIN | 0x00000008)
    # заморозка виджетов, пока их не видно (freeze.pyw); новый запуск сам будит всё, что заморозил прежний
    stop_freeze()
    subprocess.Popen([W.PYW, os.path.join(here, "freeze.pyw")], cwd=here, creationflags=NOWIN | 0x00000008)


def glaze_paused():
    try:
        return bool(json.loads(run(["glazewm", "query", "paused"], timeout=10).stdout).get("data"))
    except Exception:
        return None


def glaze_pause(want):
    now = glaze_paused()
    if now is not None and now != want:
        run(["glazewm", "command", "wm-toggle-pause"], timeout=10)


def power_active():
    out = run(["powercfg", "/getactivescheme"]).stdout
    import re
    m = re.search(r"[0-9a-fA-F]{8}-[0-9a-fA-F-]{27}", out)
    return m.group(0).lower() if m else ""


def power_set(guid):
    return run(["powercfg", "/setactive", guid]).returncode == 0


def profile_path(mode):
    return os.path.join(PROFILES, mode + ".json")


def switch(new):
    if new not in MODES:
        sys.exit("Нет такого режима: %s. Есть: %s" % (new, ", ".join(MODES)))
    o = options()
    old = o.get("mode", "daily")
    os.makedirs(PROFILES, exist_ok=True)
    if old != new and old != "game":                     # запомнить расстановку виджетов прежнего режима
        json.dump(W.load(), open(profile_path(old), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    o["mode"] = new

    if new == "game":
        if old != "game":
            cur = power_active()
            if cur and cur != HIGH_PERF and power_set(HIGH_PERF):
                o["power_prev"] = cur
        save_options(o)
        run(["taskkill", "/f", "/im", "zebar.exe"])
        W.stop_classic()                                 # Qt-виджеты (Garasu Classic) тоже выключаем
        stop_helper()
        stop_freeze()
        open(os.path.join(here, "bar_focus.txt"), "w").close()
        run([sys.executable, os.path.join(here, "ryoku.py")])          # короткая панель без дока
        glaze_pause(True)
        return

    if o.get("power_prev"):                              # выходим из игрового: вернуть прежний план питания
        power_set(o.pop("power_prev"))
    save_options(o)
    if old != new:
        if os.path.exists(profile_path(new)):
            cfg = copy.deepcopy(W.DEFAULTS)
            saved = json.load(open(profile_path(new), encoding="utf-8"))
            for k in cfg:
                cfg[k].update({a: b for a, b in saved.get(k, {}).items() if a in cfg[k]})
        else:
            cfg = W.load()
            for k, on in FIRST.get(new, {}).items():
                cfg[k]["on"] = on
        W.save(cfg)
    glaze_pause(False)
    run([sys.executable, os.path.join(here, "ryoku.py")])
    start_helper()
    W.apply(restart=True)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        switch(sys.argv[1])
    if sys.stdout:
        m = options().get("mode", "daily")
        print(m, "-", MODES[m][0])
