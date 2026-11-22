# Удаление Garasu: останавливает всё, возвращает панель задач, прежние настройки и обои.
#   -TestRoot <папка>  проверка: удалить проверочную установку (install.ps1 -TestRoot) без окон,
#                      не трогая настоящий рабочий стол, программы, обои и панель задач
param([string]$TestRoot)
$ErrorActionPreference = 'SilentlyContinue'
Add-Type -AssemblyName System.Windows.Forms
$dst = Split-Path -Parent $MyInvocation.MyCommand.Path
function Msg([string]$text, [string]$buttons = 'OK') {
    if ($TestRoot) { Write-Host $text; return 'Yes' }
    return [System.Windows.Forms.MessageBox]::Show($text, 'Удаление Garasu', $buttons, 'Information')
}
# Защита: «Uninstall.bat» есть и в скачанном архиве (папка files). Запуск оттуда снёс бы настройки
# настоящей установки, а её файлы остались бы. Удаляем только из папки установки (там есть venv).
if (-not ((Test-Path -LiteralPath "$dst\venv") -and (Test-Path -LiteralPath "$dst\theme\ryoku.py"))) {
    Msg "Это не папка установки Garasu.`r`n`r`nУдаляй ярлыком «Удалить Garasu» на рабочем столе." | Out-Null
    exit 2
}
$ask = Msg ("Выключить оформление Garasu?`r`n`r`nВернутся панель задач, меню «Пуск» по клавише Win, прежние настройки и обои.`r`n" +
    "Файлы останутся на диске. После проверки папку Garasu можно удалить вручную.`r`n" +
    "Стиль Проводника выключится. Сами программы (GlazeWM, YASB, Zebar, AutoHotkey, Python, Windhawk) останутся: их можно убрать через Параметры - Приложения.") 'YesNo'
if ("$ask" -ne 'Yes') { exit }

$py = "$dst\venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $py)) { $py = (Get-Command python).Source }
$desktop = [Environment]::GetFolderPath('Desktop'); $startup = [Environment]::GetFolderPath('Startup')
if ($TestRoot) {
    $env:USERPROFILE = Join-Path $TestRoot 'home'; $env:APPDATA = Join-Path $TestRoot 'appdata'
    $desktop = Join-Path $TestRoot 'Desktop'; $startup = Join-Path $TestRoot 'Startup'
}

if (-not $TestRoot) {
    # если был включён игровой режим, вернуть прежний план питания
    try {
        $o = Get-Content "$dst\theme\settings.json" -Raw | ConvertFrom-Json
        if ($o.power_prev) { powercfg /setactive $o.power_prev | Out-Null }
    } catch {}
    Get-Process glazewm, yasb, zebar | Stop-Process -Force
}
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine.ToLower().Contains($dst.ToLower()) -and $_.Name -match '^(pythonw|python|AutoHotkey64|powershell)\.exe$' -and $_.ProcessId -ne $PID } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Start-Sleep 1
if (-not $TestRoot) {
    if ($py -and (Test-Path $py)) { & $py "$dst\theme\hide_taskbar.pyw" show }
    # запасной возврат панели задач без Python (если Python сломан или удалён антивирусом): убрать прозрачность
    try {
        Add-Type 'using System; using System.Runtime.InteropServices; public class GarasuBar {
            [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern IntPtr FindWindowW(string c, string t);
            [DllImport("user32.dll")] public static extern int GetWindowLongW(IntPtr h, int i);
            [DllImport("user32.dll")] public static extern int SetWindowLongW(IntPtr h, int i, int v);
            [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
            [DllImport("user32.dll")] public static extern IntPtr FindWindowExW(IntPtr p, IntPtr a, string c, string t); }'
        $bars = @([GarasuBar]::FindWindowW('Shell_TrayWnd', $null))
        $h = [IntPtr]::Zero
        while (($h = [GarasuBar]::FindWindowExW([IntPtr]::Zero, $h, 'Shell_SecondaryTrayWnd', $null)) -ne [IntPtr]::Zero) { $bars += $h }
        foreach ($b in $bars) {
            if ($b -eq [IntPtr]::Zero) { continue }
            $ex = [GarasuBar]::GetWindowLongW($b, -20)
            if ($ex -band 0x80000) { [GarasuBar]::SetWindowLongW($b, -20, $ex -band (-bnot 0x80000)) | Out-Null }
            [GarasuBar]::ShowWindow($b, 5) | Out-Null
        }
    } catch {}
    # стиль Проводника: если мод Windhawk ставил наш установщик, выключаем его (сам Windhawk остаётся)
    $whCli = "$env:ProgramFiles\Windhawk\windhawk-cli.exe"
    if ((Test-Path -LiteralPath "$dst\theme\explorer_mod_by_ryoku.txt") -and (Test-Path -LiteralPath $whCli)) {
        & $whCli --quiet mod disable windows-11-file-explorer-styler | Out-Null
    }
}

Remove-Item "$startup\Garasu.lnk", "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\Garasu.lnk" -Force
Remove-Item "$desktop\Garasu - темы.lnk", "$desktop\Удалить Garasu.lnk", "$env:USERPROFILE\Desktop\Garasu - темы.lnk", "$env:USERPROFILE\Desktop\Удалить Garasu.lnk" -Force

# настройки, которых до установки не было, убираем совсем; те, что были, ниже вернутся из backup
$cfgs = "$env:USERPROFILE\.config\yasb\config.yaml", "$env:USERPROFILE\.config\yasb\styles.css",
        "$env:USERPROFILE\.glzr\glazewm\config.yaml", "$env:USERPROFILE\.glzr\zebar\settings.json"

# Сохраняем папку виджетов: в ней лежат черновик и личные файлы.
$bak = Get-ChildItem "$dst\backup" -Directory -Filter 'before-install-*' | Sort-Object Name | Select-Object -First 1
if ($bak) {
    foreach ($f in $cfgs) {
        $restored = $false
        foreach ($n in ($f -replace '[:\\]', '_'), ($f.Substring($env:USERPROFILE.Length) -replace '[:\\]', '_')) {
            $saved = Join-Path $bak.FullName $n
            if (Test-Path -LiteralPath $saved) { Copy-Item -LiteralPath $saved $f -Force -ErrorAction Stop; $restored = $true; break }
        }
        if (!$restored) { Remove-Item -LiteralPath $f -Force }
    }
    $w = Get-Content "$($bak.FullName)\wallpaper.txt" -Encoding UTF8 | Select-Object -First 1
    if ($w -and (Test-Path -LiteralPath $w) -and -not $TestRoot) {
        Add-Type 'using System.Runtime.InteropServices; public class RyokuWall { [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern int SystemParametersInfo(int a, int b, string c, int d); }'
        [RyokuWall]::SystemParametersInfo(20, 0, $w, 3) | Out-Null
    }
}
Msg "Оформление выключено. Папка Garasu и черновик сохранены." | Out-Null
exit 0
