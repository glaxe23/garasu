# Удаление Garasu: останавливает всё, возвращает панель задач, прежние настройки и обои.
$ErrorActionPreference = 'SilentlyContinue'
Add-Type -AssemblyName System.Windows.Forms
$dst = 'C:\garasu'
$ask = [System.Windows.Forms.MessageBox]::Show(
    "Выключить оформление Garasu?`r`n`r`nВернутся панель задач, меню «Пуск» по клавише Win, прежние настройки и обои.`r`n" +
    "Сами программы (GlazeWM, YASB, Zebar, AutoHotkey, Python) останутся: их можно убрать через Параметры - Приложения.",
    'Удаление Garasu', 'YesNo', 'Question')
if ($ask -ne 'Yes') { exit }

$py = (Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'pythonw.exe' -and $_.CommandLine -like '*garasu*' } | Select-Object -First 1).ExecutablePath
if ($py) { $py = Join-Path (Split-Path $py) 'python.exe' } else { $py = (Get-Command python).Source }

# если был включён игровой режим, вернуть прежний план питания
try {
    $o = Get-Content "$dst\theme\settings.json" -Raw | ConvertFrom-Json
    if ($o.power_prev) { powercfg /setactive $o.power_prev | Out-Null }
} catch {}
Get-Process glazewm, yasb, zebar | Stop-Process -Force
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*garasu*' -and $_.Name -match '^(pythonw|python|AutoHotkey64|powershell)\.exe$' -and $_.ProcessId -ne $PID } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Start-Sleep 1
if ($py -and (Test-Path $py)) { & $py "$dst\theme\hide_taskbar.pyw" show }

Remove-Item "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\Garasu.lnk" -Force
Remove-Item "$env:USERPROFILE\Desktop\Garasu - темы.lnk", "$env:USERPROFILE\Desktop\Удалить Garasu.lnk" -Force

$bak = Get-ChildItem "$dst\backup" -Directory -Filter 'before-install-*' | Sort-Object Name | Select-Object -First 1
if ($bak) {
    foreach ($f in "$env:USERPROFILE\.config\yasb\config.yaml", "$env:USERPROFILE\.config\yasb\styles.css",
                   "$env:USERPROFILE\.glzr\glazewm\config.yaml", "$env:USERPROFILE\.glzr\zebar\settings.json") {
        $saved = Join-Path $bak.FullName ($f -replace '[:\\]', '_')
        if (Test-Path $saved) { Copy-Item $saved $f -Force }
    }
    $w = Get-Content "$($bak.FullName)\wallpaper.txt" -Encoding UTF8 | Select-Object -First 1
    if ($w -and (Test-Path $w)) {
        Add-Type 'using System.Runtime.InteropServices; public class RyokuWall { [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern int SystemParametersInfo(int a, int b, string c, int d); }'
        [RyokuWall]::SystemParametersInfo(20, 0, $w, 3) | Out-Null
    }
}
[System.Windows.Forms.MessageBox]::Show("Готово. Оформление выключено.`r`nПапку C:\garasu можно удалить вручную.", 'Удаление Garasu') | Out-Null
