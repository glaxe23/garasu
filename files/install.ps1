# Установщик Garasu с окном. Запускается из «Установить.bat» или из Garasu-Setup.exe.
# Параметр -Check: только проверить компьютер и показать, что будет сделано, ничего не меняя.
param([switch]$Check)
$ErrorActionPreference = 'Continue'
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

$src = Split-Path -Parent $MyInvocation.MyCommand.Path
$dst = 'C:\garasu'
$log = Join-Path $env:TEMP 'garasu-install.log'
"=== $(Get-Date) ===" | Out-File $log -Encoding utf8
$script:problems = @()
$script:py = $null

# ---------------------------------------------------------------- окно
$bg = [Drawing.Color]::FromArgb(14, 16, 20); $fg = [Drawing.Color]::FromArgb(238, 232, 236)
$acc = [Drawing.Color]::FromArgb(238, 183, 208); $mut = [Drawing.Color]::FromArgb(140, 132, 138)
$form = New-Object Windows.Forms.Form
$form.Text = 'Установка Garasu'; $form.Size = New-Object Drawing.Size(660, 600)
$form.StartPosition = 'CenterScreen'; $form.FormBorderStyle = 'FixedSingle'; $form.MaximizeBox = $false
$form.BackColor = $bg; $form.ForeColor = $fg; $form.Font = New-Object Drawing.Font('Segoe UI', 10)

$title = New-Object Windows.Forms.Label
$title.Text = '硝  Garasu'; $title.Font = New-Object Drawing.Font('Segoe UI', 20, [Drawing.FontStyle]::Bold)
$title.ForeColor = $acc; $title.Location = '24,16'; $title.AutoSize = $true
$sub = New-Object Windows.Forms.Label
$sub.Text = "Рабочий стол Windows в стиле Ryoku: окна плиткой, панель и док, виджеты на обоях, темы и режимы.`r`n`r`n" +
    "Что будет сделано:`r`n" +
    "  •  установятся бесплатные программы GlazeWM, YASB, Zebar, AutoHotkey и Python (если их нет);`r`n" +
    "  •  файлы оформления скопируются в C:\garasu, скачаются обои;`r`n" +
    "  •  включится автозапуск. Системная панель задач станет невидимой, клавиша Win будет открывать поиск.`r`n`r`n" +
    "Нужен интернет, 5-10 минут. Когда Windows спросит разрешение на установку программ, нажимай «Да».`r`n" +
    "Всё возвращается назад через «Удалить Garasu»."
$sub.Location = '26,64'; $sub.Size = New-Object Drawing.Size(600, 190)
$box = New-Object Windows.Forms.RichTextBox
$box.Location = '26,262'; $box.Size = New-Object Drawing.Size(594, 190); $box.ReadOnly = $true; $box.BorderStyle = 'None'
$box.BackColor = [Drawing.Color]::FromArgb(24, 27, 33); $box.ForeColor = $fg; $box.Font = New-Object Drawing.Font('Consolas', 9.5)
$bar = New-Object Windows.Forms.ProgressBar
$bar.Location = '26,464'; $bar.Size = New-Object Drawing.Size(594, 10); $bar.Maximum = 100
$go = New-Object Windows.Forms.Button
$go.Text = 'Установить'; $go.Location = '356,490'; $go.Size = New-Object Drawing.Size(140, 40); $go.FlatStyle = 'Flat'
$go.BackColor = $acc; $go.ForeColor = $bg; $go.Font = New-Object Drawing.Font('Segoe UI', 10.5, [Drawing.FontStyle]::Bold)
$go.FlatAppearance.BorderSize = 0
$close = New-Object Windows.Forms.Button
$close.Text = 'Закрыть'; $close.Location = '506,490'; $close.Size = New-Object Drawing.Size(114, 40); $close.FlatStyle = 'Flat'
$close.BackColor = [Drawing.Color]::FromArgb(40, 44, 52); $close.ForeColor = $fg; $close.FlatAppearance.BorderSize = 0
$form.Controls.AddRange(@($title, $sub, $box, $bar, $go, $close))
$close.Add_Click({ $form.Close() })

function Pump { [System.Windows.Forms.Application]::DoEvents() }
function Say([string]$text, $color = $fg) {
    $box.SelectionStart = $box.TextLength; $box.SelectionColor = $color
    $box.AppendText($text + "`r`n"); $box.ScrollToCaret(); Add-Content $log $text -Encoding utf8; Pump
}
function Ok([string]$t) { Say "   + $t" ([Drawing.Color]::FromArgb(150, 220, 160)) }
function Bad([string]$t) { Say "   ! $t" ([Drawing.Color]::FromArgb(255, 150, 150)); $script:problems += $t }
function Step([string]$t, [int]$pct) { Say $t $acc; $bar.Value = $pct; Pump }

# Запустить программу без окна и дождаться её, не замораживая окно установщика. Возвращает код выхода.
function Run([string]$file, [string]$arguments) {
    try {
        $psi = New-Object Diagnostics.ProcessStartInfo
        $psi.FileName = $file; $psi.Arguments = $arguments; $psi.UseShellExecute = $false; $psi.CreateNoWindow = $true
        $psi.RedirectStandardOutput = $true; $psi.RedirectStandardError = $true
        $p = [Diagnostics.Process]::Start($psi)
        $o = $p.StandardOutput.ReadToEndAsync(); $e = $p.StandardError.ReadToEndAsync()
        while (-not $p.HasExited) { Pump; Start-Sleep -Milliseconds 80 }
        Add-Content $log ("> $file $arguments`r`n" + $o.Result + $e.Result) -Encoding utf8
        return $p.ExitCode
    } catch { Add-Content $log "> $file $arguments : $_" -Encoding utf8; return -1 }
}
function RefreshPath {
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
}
function FindPython {
    $c = @()
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { $c += $cmd.Source }
    $c += Get-ChildItem "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe", "$env:ProgramFiles\Python3*\python.exe",
        "$env:LOCALAPPDATA\Python\pythoncore-*\python.exe" -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | ForEach-Object FullName
    foreach ($p in $c) {
        if ($p -like '*WindowsApps*') { continue }      # заглушка из магазина Microsoft, не настоящий Python
        try {
            $v = & $p -c "import sys; print(sys.version_info[0] * 100 + sys.version_info[1])" 2>$null
            if ([int]$v -ge 310) { return (& $p -c "import sys; print(sys.executable)") }
        } catch {}
    }
    return $null
}
$apps = @(
    @{ id = 'glzr-io.glazewm';       name = 'GlazeWM (окна плиткой)';   exe = @("$env:ProgramFiles\glzr.io\GlazeWM\glazewm.exe") },
    @{ id = 'AmN.yasb';              name = 'YASB (панель и док)';      exe = @("$env:ProgramFiles\YASB\yasb.exe") },
    @{ id = 'glzr-io.zebar';         name = 'Zebar (виджеты на обоях)'; exe = @("$env:ProgramFiles\glzr.io\Zebar\zebar.exe") },
    @{ id = 'AutoHotkey.AutoHotkey'; name = 'AutoHotkey (клавиши)';     exe = @("$env:LOCALAPPDATA\Programs\AutoHotkey\v2\AutoHotkey64.exe", "$env:ProgramFiles\AutoHotkey\v2\AutoHotkey64.exe") }
)
function Has($app) { foreach ($e in $app.exe) { if (Test-Path $e) { return $true } }; return $false }

function Install {
    $go.Enabled = $false; $close.Enabled = $false
    $winget = (Get-Command winget -ErrorAction SilentlyContinue).Source

    # ---------------------------------------------------------- 1. проверка
    Step 'Шаг 1 из 6. Проверка компьютера' 3
    $build = [Environment]::OSVersion.Version.Build
    if ($build -lt 22000) { Bad 'Это не Windows 11: скруглённые углы и рамки окон могут не работать.' } else { Ok "Windows 11 (сборка $build)" }
    if (-not $winget) { Bad 'Не найден winget (установщик программ Windows). Обнови «Установщик приложения» в Microsoft Store и запусти установку ещё раз.'; return }
    Ok 'winget найден'
    foreach ($a in $apps) { if (Has $a) { Ok "$($a.name): уже стоит" } else { Say "   - $($a.name): будет установлено" $mut } }
    $script:py = FindPython
    if ($script:py) { Ok "Python: $($script:py)" } else { Say '   - Python: будет установлен' $mut }
    if ($Check) { Say 'Режим проверки: дальше ничего не меняю.' $acc; return }

    # ---------------------------------------------------------- 2. программы
    Step 'Шаг 2 из 6. Программы (самый долгий шаг)' 10
    $i = 0
    foreach ($a in $apps) {
        $i++
        if (-not (Has $a)) {
            Say "   ставлю $($a.name)..." $mut
            Run $winget "install -e --id $($a.id) --silent --accept-package-agreements --accept-source-agreements" | Out-Null
            if (Has $a) { Ok "$($a.name): установлено" } else { Bad "$($a.name): не удалось установить" }
        }
        $bar.Value = 10 + $i * 8; Pump
    }
    if (-not $script:py) {
        Say '   ставлю Python 3.12...' $mut
        Run $winget 'install -e --id Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements' | Out-Null
        RefreshPath
        $script:py = FindPython
    }
    if (-not $script:py) { Bad 'Python не установился. Поставь его с python.org и запусти установку ещё раз.'; return }
    $pyw = Join-Path (Split-Path $script:py) 'pythonw.exe'
    Step 'Шаг 3 из 6. Библиотеки Python' 50
    Run $script:py '-m pip install --user --quiet --disable-pip-version-check pillow materialyoucolor pyyaml numpy pyaudiowpatch pycaw' | Out-Null
    if ((Run $script:py '-c "import PIL, yaml, materialyoucolor"') -eq 0) { Ok 'основные библиотеки готовы' } else { Bad 'Библиотеки Python не поставились: темы работать не будут.' }
    if ((Run $script:py '-c "import numpy, pyaudiowpatch, pycaw"') -ne 0) { Say '   (звуковые библиотеки не поставились: не будет визуализатора и микшера, остальное работает)' $mut }

    # ---------------------------------------------------------- 4. файлы
    Step 'Шаг 4 из 6. Файлы оформления' 62
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $bak = "$dst\backup\before-install-$stamp"
    $yasb = "$env:USERPROFILE\.config\yasb"; $glaze = "$env:USERPROFILE\.glzr\glazewm"; $zebar = "$env:USERPROFILE\.glzr\zebar"
    New-Item -ItemType Directory -Force "$dst\theme", "$dst\wallpapers", "$dst\photos", $bak, $yasb, $glaze, "$zebar\ryoku" | Out-Null
    foreach ($f in "$yasb\config.yaml", "$yasb\styles.css", "$glaze\config.yaml", "$zebar\settings.json") {
        if (Test-Path $f) { Copy-Item $f (Join-Path $bak ($f -replace '[:\\]', '_')) -Force }
    }
    (Get-ItemProperty 'HKCU:\Control Panel\Desktop').WallPaper | Set-Content "$bak\wallpaper.txt" -Encoding utf8
    Copy-Item "$src\theme\*" "$dst\theme" -Recurse -Force
    Copy-Item "$src\zebar\*" "$zebar\ryoku" -Recurse -Force
    Copy-Item "$src\glazewm-config.yaml" "$glaze\config.yaml" -Force
    Copy-Item "$src\uninstall.ps1", "$src\Uninstall.bat" $dst -Force
    # в скриптах запуска путь к Python подставляется полный: так работает, даже если Python не прописан в PATH
    (Get-Content "$src\start.bat") -replace '\bpythonw\b', "`"$pyw`"" | Set-Content "$dst\start.bat" -Encoding ascii
    $ahk = Get-Content "$dst\theme\win_launcher.ahk" -Raw -Encoding UTF8
    [IO.File]::WriteAllText("$dst\theme\win_launcher.ahk", $ahk.Replace("Run 'pythonw `"'", "Run '`"$pyw`" `"'"), (New-Object Text.UTF8Encoding($true)))
    if (-not (Test-Path "$dst\theme\settings.json")) {
        '{"dock": "auto", "side_gap": 24, "mode": "daily", "auto_game": true, "games": [], "auto_theme": {"on": false, "day": "sky", "night": "night", "day_from": 8, "night_from": 20}}' |
            Set-Content "$dst\theme\settings.json" -Encoding ascii
    }
    Ok "файлы скопированы, прежние настройки сохранены в backup"

    # ---------------------------------------------------------- 5. обои
    Step 'Шаг 5 из 6. Обои (из открытого репозитория Ryoku на GitHub)' 72
    $base = 'https://raw.githubusercontent.com/ryoku-dev/ryoku/HEAD/ryoku/assets/wallpapers/'
    $themes = Get-Content "$dst\theme\themes.json" -Raw -Encoding UTF8 | ConvertFrom-Json
    $got = @()
    foreach ($t in $themes) {
        $out = Join-Path "$dst\wallpapers" $t.wallpaper
        if (-not (Test-Path $out)) { Run 'curl.exe' "-sSL --fail --max-time 180 -o `"$out`" `"$base$($t.wallpaper)`"" | Out-Null }
        if ((Test-Path $out) -and (Get-Item $out).Length -gt 10000) { $got += $t; Ok $t.name } else { Remove-Item $out -ErrorAction SilentlyContinue; Say "   - не скачалось: $($t.name)" $mut }
        $bar.Value = [Math]::Min(88, $bar.Value + 2); Pump
    }
    if ($got.Count -eq 0) { Bad 'Обои не скачались (нет интернета или GitHub недоступен). Запусти установку ещё раз позже.'; return }
    Get-ChildItem "$dst\wallpapers" -File | Select-Object -First 2 | ForEach-Object { if (-not (Test-Path "$dst\photos\$($_.Name)")) { Copy-Item $_.FullName "$dst\photos" } }

    # ---------------------------------------------------------- 6. настройка и запуск
    Step 'Шаг 6 из 6. Настройка и запуск' 90
    if ((Run $script:py "`"$dst\theme\widgets.py`" install") -ne 0) { Bad 'Не удалось подготовить виджеты.' }
    if ((Run $script:py "`"$dst\theme\ryoku.py`" $($got[0].id)") -eq 0) { Ok "тема «$($got[0].id)» применена" } else { Bad 'Тема не применилась.' }
    $sh = New-Object -ComObject WScript.Shell
    $l = $sh.CreateShortcut("$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\Garasu.lnk")
    $l.TargetPath = "$dst\start.bat"; $l.WorkingDirectory = $dst; $l.WindowStyle = 7; $l.Save()
    $l = $sh.CreateShortcut("$env:USERPROFILE\Desktop\Garasu - темы.lnk")
    $l.TargetPath = $pyw; $l.Arguments = "`"$dst\theme\themes_panel.pyw`""; $l.WorkingDirectory = "$dst\theme"; $l.Save()
    $l = $sh.CreateShortcut("$env:USERPROFILE\Desktop\Удалить Garasu.lnk")
    $l.TargetPath = "$dst\Uninstall.bat"; $l.WorkingDirectory = $dst; $l.Save()
    Get-Process glazewm, yasb, zebar -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep 1
    Start-Process "$dst\start.bat" -WindowStyle Hidden
    $bar.Value = 100
    Ok 'автозапуск включён, рабочий стол запускается'
}

$go.Add_Click({
    try { Install } catch { Bad "Ошибка установщика: $_" }
    $close.Enabled = $true
    if ($Check) { $go.Enabled = $true; return }
    Say ''
    if ($script:problems.Count) {
        Say 'Установка закончена, но были проблемы (подробности в журнале):' ([Drawing.Color]::FromArgb(255, 200, 120))
        Say "   $log" $mut
    } elseif ($bar.Value -eq 100) {
        Say 'Готово! Через несколько секунд появятся панель и виджеты.' ([Drawing.Color]::FromArgb(150, 220, 160))
        Say 'Win - поиск приложений.  Кнопка с палитрой на панели - темы.' $fg
        Say 'Alt+1..9 - рабочие столы.  Alt+Shift+Q - закрыть окно.  Ctrl+Alt+1/2/3 - режимы.' $fg
    }
})
if ($Check) { $go.Text = 'Проверить' }
[void]$form.ShowDialog()
