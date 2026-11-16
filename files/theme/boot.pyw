"""Запускается из start.bat при входе в Windows: ждёт, пока поднимутся GlazeWM и панель,
и включает тот режим, который был выбран в прошлый раз (повседневный, рабочий или игровой).
В игровом режиме виджеты и помощник не запускаются вовсе."""
import os, sys, time

here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, here)
time.sleep(6)
try:
    open(os.path.join(here, "claude_status.txt"), "w").close()      # после перезагрузки статус Claude пуст
    import mode
    mode.switch(mode.options().get("mode", "daily"))
except Exception as e:
    open(os.path.join(here, "helper.log"), "a", encoding="utf-8").write("boot: %s\n" % e)
