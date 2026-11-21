#Requires AutoHotkey v2.0
#SingleInstance Force
; Win открывает обычное меню «Пуск» Windows, его оформление делает мод Windhawk
; «Windows 11 Start Menu Styler» (стиль Garasu пишет theme\start_style.py).
; Клавишу Win этот скрипт не перехватывает.

; Режимы рабочего стола. Работают всегда, в том числе в игровом режиме, когда плитка окон на паузе.
;   Ctrl+Alt+1 - повседневный,  Ctrl+Alt+2 - рабочий,  Ctrl+Alt+3 - игровой
SetMode(name) {
    Run '"' A_ScriptDir '\..\venv\Scripts\pythonw.exe" "' A_ScriptDir '\mode.py" ' name, A_ScriptDir, "Hide"
}
^!1::SetMode("daily")
^!2::SetMode("work")
^!3::SetMode("game")

; Привычные клавиши Windows для окон в плитке (Win+D, Win+E, Alt+Tab и Alt+F4 работают сами):
;   Win+вверх - развернуть окно, Win+вниз - свернуть, Win+влево / вправо - передвинуть окно
Glaze(cmd) {
    Run 'glazewm command ' cmd, , "Hide"
}
#Up::Glaze("toggle-fullscreen")
#Down::Glaze("toggle-minimized")
#Left::Glaze("move --direction left")
#Right::Glaze("move --direction right")

; Ctrl+Alt+H - шпаргалка по клавишам (повторное нажатие закрывает)
^!h::Run '"' A_ScriptDir '\..\venv\Scripts\pythonw.exe" "' A_ScriptDir '\help_panel.pyw"', A_ScriptDir, "Hide"
