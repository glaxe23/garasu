#Requires AutoHotkey v2.0
#SingleInstance Force
; Win (одна, без других клавиш) открывает поиск приложений панели YASB вместо меню «Пуск».
; Сочетания с Win (Win+E, Win+Shift+S и т.д.) работают как обычно.
~LWin::Send "{Blind}{vkE8}"
~LWin up:: {
    if (A_PriorKey = "LWin")
        Send "^!+o"
}

; Режимы рабочего стола. Работают всегда, в том числе в игровом режиме, когда плитка окон на паузе.
;   Ctrl+Alt+1 - повседневный,  Ctrl+Alt+2 - рабочий,  Ctrl+Alt+3 - игровой
SetMode(name) {
    Run 'pythonw "' A_ScriptDir '\mode.py" ' name, A_ScriptDir, "Hide"
}
^!1::SetMode("daily")
^!2::SetMode("work")
^!3::SetMode("game")
