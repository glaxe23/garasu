"""Запускается из start.bat при входе в Windows: ждёт, пока поднимутся GlazeWM и панель,
и включает тот режим, который был выбран в прошлый раз (повседневный, рабочий или игровой).
В игровом режиме виджеты и помощник не запускаются вовсе."""
import os, sys, time

here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, here)
# Раньше тут было ровно 6 секунд ожидания. Теперь ждём, пока GlazeWM начнёт отвечать и запустится YASB,
# но не дольше тех же 6 секунд (минимум 1 с, чтобы Проводник успел подняться).
def _ready():
    import subprocess
    try:
        ok = subprocess.run(["glazewm", "query", "paused"], capture_output=True, timeout=3,
                            creationflags=0x08000000).returncode == 0
        tl = subprocess.run(["tasklist", "/fi", "imagename eq yasb.exe", "/nh"], capture_output=True,
                            text=True, timeout=3, creationflags=0x08000000).stdout
        return ok and "yasb.exe" in tl.lower()
    except Exception:
        return False
_t0 = time.time()
time.sleep(1)
while time.time() - _t0 < 6 and not _ready():
    time.sleep(0.5)
try:
    open(os.path.join(here, "claude_status.txt"), "w").close()      # после перезагрузки статус Claude пуст
    import mode
    mode.switch(mode.options().get("mode", "daily"))
    flag = os.path.join(here, "welcome_shown")        # первый запуск после установки: окно «С чего начать»
    if not os.path.exists(flag):
        open(flag, "w").close()
        import subprocess
        subprocess.Popen([sys.executable, os.path.join(here, "help_panel.pyw"), "welcome"], creationflags=0x08000000)
except Exception as e:
    open(os.path.join(here, "helper.log"), "a", encoding="utf-8").write("boot: %s\n" % e)
