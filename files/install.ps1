# Установщик Garasu с окном. Запускается из «Install.bat» или из Garasu-Setup.exe.
#   -Check            только проверить компьютер и показать, что будет сделано, ничего не меняя
#   -Auto             без окна: сразу установить и выйти (код выхода = число проблем)
#   -TestRoot <папка> проверочная установка в отдельную папку: ничего не запускает и не трогает настоящий рабочий стол
param([switch]$Check, [switch]$Auto, [string]$TestRoot)
$ErrorActionPreference = 'Continue'
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()
try { [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12 } catch {}
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch {}
$env:PYTHONIOENCODING = 'utf-8'; $env:PYTHONUTF8 = '1'

$src = Split-Path -Parent $MyInvocation.MyCommand.Path
$dst = 'C:\garasu'
$userHome = $env:USERPROFILE
$desktop = [Environment]::GetFolderPath('Desktop')        # не «папка пользователя\Desktop»: у многих рабочий стол лежит в OneDrive
$startup = [Environment]::GetFolderPath('Startup')
if ($TestRoot) {
    $dst = Join-Path $TestRoot 'garasu'; $userHome = Join-Path $TestRoot 'home'
    $desktop = Join-Path $TestRoot 'Desktop'; $startup = Join-Path $TestRoot 'Startup'
    New-Item -ItemType Directory -Force $userHome, $desktop, $startup | Out-Null
    $env:USERPROFILE = $userHome; $env:RYOKU_DRYRUN = '1'
}
if (-not $desktop) { $desktop = Join-Path $userHome 'Desktop' }
if (-not $startup) { $startup = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Startup' }
$tmp = Join-Path $env:TEMP 'garasu-dl'
$log = Join-Path $env:TEMP 'garasu-install.log'
"=== $(Get-Date) ===" | Out-File $log -Encoding utf8
$script:problems = @()
$script:py = $null
$script:done = $false
$script:stopped = $false

# ---------------------------------------------------------------- окно
$bg = [Drawing.Color]::FromArgb(14, 16, 20); $fg = [Drawing.Color]::FromArgb(238, 232, 236)
$acc = [Drawing.Color]::FromArgb(238, 183, 208); $mut = [Drawing.Color]::FromArgb(140, 132, 138)
$form = New-Object Windows.Forms.Form
$form.Text = 'Установка Garasu'; $form.Size = New-Object Drawing.Size(660, 730)
$form.StartPosition = 'CenterScreen'; $form.FormBorderStyle = 'FixedSingle'; $form.MaximizeBox = $false
$form.BackColor = $bg; $form.ForeColor = $fg; $form.Font = New-Object Drawing.Font('Segoe UI', 10)

$title = New-Object Windows.Forms.Label
$title.Text = '硝  Garasu'; $title.Font = New-Object Drawing.Font('Segoe UI', 20, [Drawing.FontStyle]::Bold)
$title.ForeColor = $acc; $title.Location = '24,16'; $title.AutoSize = $true
$sub = New-Object Windows.Forms.Label
$sub.Text = "Рабочий стол Windows в стиле Ryoku: окна плиткой, панель и док, виджеты на обоях, темы и режимы.`r`n`r`n" +
    "Что будет сделано:`r`n" +
    "  •  установятся бесплатные программы GlazeWM, YASB, Zebar, AutoHotkey и Python (если их нет);`r`n" +
    "  •  файлы оформления скопируются в папку ниже, скачаются обои;`r`n" +
    "  •  включится автозапуск. Системная панель задач станет невидимой, клавиша Win будет открывать поиск;`r`n" +
    "  •  по галочке ниже: Проводник в тёмном стекле под цвет темы (бесплатная программа Windhawk).`r`n`r`n" +
    "Нужен интернет, 5-10 минут. Когда Windows спросит разрешение на установку программ, нажимай «Да».`r`n" +
    "Всё возвращается назад через «Удалить Garasu»."
$sub.Location = '26,64'; $sub.Size = New-Object Drawing.Size(600, 236)
$pathLbl = New-Object Windows.Forms.Label
$pathLbl.Text = 'Папка установки:'; $pathLbl.Location = '26,310'; $pathLbl.AutoSize = $true; $pathLbl.ForeColor = $mut
$pathBox = New-Object Windows.Forms.TextBox
$pathBox.Text = $dst; $pathBox.Location = '160,307'; $pathBox.Size = New-Object Drawing.Size(346, 26); $pathBox.BorderStyle = 'FixedSingle'
$pathBox.BackColor = [Drawing.Color]::FromArgb(24, 27, 33); $pathBox.ForeColor = $fg
$browse = New-Object Windows.Forms.Button
$browse.Text = 'Обзор...'; $browse.Location = '516,305'; $browse.Size = New-Object Drawing.Size(104, 30); $browse.FlatStyle = 'Flat'
$browse.BackColor = [Drawing.Color]::FromArgb(40, 44, 52); $browse.ForeColor = $fg; $browse.FlatAppearance.BorderSize = 0
$browse.Add_Click({
    $d = New-Object Windows.Forms.FolderBrowserDialog
    $d.Description = 'Выбери, где создать папку garasu. В пути должны быть только английские буквы.'
    if ($d.ShowDialog() -eq 'OK') { $pathBox.Text = (Join-Path $d.SelectedPath 'garasu') }
})
$glassBox = New-Object Windows.Forms.CheckBox
$glassBox.Text = 'Стеклянный Проводник (поставит Windhawk 2.0 и мод File Explorer Styler)'
$glassBox.Checked = $true; $glassBox.Location = '26,344'; $glassBox.Size = New-Object Drawing.Size(594, 24); $glassBox.ForeColor = $fg
# Windows 10: всё, что есть только в Windows 11, не ставим. GARASU_FAKE_WIN10 — проверка этого режима на Windows 11.
$osBuild = [Environment]::OSVersion.Version.Build
$win10 = ($osBuild -lt 22000) -or [bool]$env:GARASU_FAKE_WIN10
if ($win10) {
    # мод Windhawk для Проводника написан под Windows 11: на «десятке» он не работает, Windhawk был бы лишним
    $glassBox.Checked = $false; $glassBox.Enabled = $false
    $glassBox.Text = 'Стеклянный Проводник — только для Windows 11'
    $sub.Text = $sub.Text.Replace("  •  по галочке ниже: Проводник в тёмном стекле под цвет темы (бесплатная программа Windhawk).`r`n",
        "  •  Windows 10: окна останутся с прямыми углами, стеклянный Проводник недоступен, остальное как в Windows 11.`r`n")
}
$box = New-Object Windows.Forms.RichTextBox
$box.Location = '26,376'; $box.Size = New-Object Drawing.Size(594, 200); $box.ReadOnly = $true; $box.BorderStyle = 'None'
$box.BackColor = [Drawing.Color]::FromArgb(24, 27, 33); $box.ForeColor = $fg; $box.Font = New-Object Drawing.Font('Consolas', 9.5)
$bar = New-Object Windows.Forms.ProgressBar
$bar.Location = '26,588'; $bar.Size = New-Object Drawing.Size(594, 10); $bar.Maximum = 100
$go = New-Object Windows.Forms.Button
$go.Text = 'Установить'; $go.Location = '356,616'; $go.Size = New-Object Drawing.Size(140, 40); $go.FlatStyle = 'Flat'
$go.BackColor = $acc; $go.ForeColor = $bg; $go.Font = New-Object Drawing.Font('Segoe UI', 10.5, [Drawing.FontStyle]::Bold)
$go.FlatAppearance.BorderSize = 0
$close = New-Object Windows.Forms.Button
$close.Text = 'Закрыть'; $close.Location = '506,616'; $close.Size = New-Object Drawing.Size(114, 40); $close.FlatStyle = 'Flat'
$close.BackColor = [Drawing.Color]::FromArgb(40, 44, 52); $close.ForeColor = $fg; $close.FlatAppearance.BorderSize = 0
$logBtn = New-Object Windows.Forms.Button
$logBtn.Text = 'Журнал'; $logBtn.Location = '26,616'; $logBtn.Size = New-Object Drawing.Size(114, 40); $logBtn.FlatStyle = 'Flat'
$logBtn.BackColor = [Drawing.Color]::FromArgb(40, 44, 52); $logBtn.ForeColor = $fg; $logBtn.FlatAppearance.BorderSize = 0
$logBtn.Visible = $false
$form.Controls.AddRange(@($title, $sub, $pathLbl, $pathBox, $browse, $glassBox, $box, $bar, $go, $close, $logBtn))
$close.Add_Click({ $form.Close() })
$logBtn.Add_Click({ Start-Process notepad.exe "`"$log`"" })

function Pump { [System.Windows.Forms.Application]::DoEvents() }
function Note([string]$text) { try { Add-Content -LiteralPath $log -Value $text -Encoding utf8 } catch {} }
function Say([string]$text, $color = $fg) {
    $box.SelectionStart = $box.TextLength; $box.SelectionColor = $color
    $box.AppendText($text + "`r`n"); $box.ScrollToCaret(); Note $text; Pump
    if ($Auto) { Write-Host $text }
}
function Ok([string]$t) { Say "   + $t" ([Drawing.Color]::FromArgb(150, 220, 160)) }
function Bad([string]$t) { Say "   ! $t" ([Drawing.Color]::FromArgb(255, 150, 150)); $script:problems += $t }
function Step([string]$t, [int]$pct) { Say $t $acc; $bar.Value = $pct; Pump }

# Запустить программу без окна и дождаться её, не замораживая окно установщика. Возвращает код выхода.
function Run([string]$file, [string]$arguments, [int]$timeoutSec = 1500) {
    try {
        $psi = New-Object Diagnostics.ProcessStartInfo
        $psi.FileName = $file; $psi.Arguments = $arguments; $psi.UseShellExecute = $false; $psi.CreateNoWindow = $true
        $psi.RedirectStandardOutput = $true; $psi.RedirectStandardError = $true
        try { $p = [Diagnostics.Process]::Start($psi) }
        catch {
            # 740: программе нужны права администратора (обычно установщик с сайта). Без «оболочки» Windows
            # такая программа не запускается вовсе, поэтому запускаем через неё: Windows спросит «Разрешить?».
            $w32 = $_.Exception.InnerException
            if (-not $w32) { $w32 = $_.Exception }
            if ($w32.NativeErrorCode -ne 740) { throw }
            Note "> $file : нужны права администратора, запускаю с запросом Windows"
            try {
                $p = Start-Process -FilePath $file -ArgumentList $arguments -Verb RunAs -PassThru
                $null = $p.Handle          # без этого PowerShell теряет код выхода (ExitCode пустой)
            } catch { Note "> $file : отказ в правах ($_)"; return 1223 }      # 1223 = пользователь нажал «Нет»
            $end = (Get-Date).AddSeconds($timeoutSec)
            while (-not $p.HasExited) {
                Pump; Start-Sleep -Milliseconds 120
                if ((Get-Date) -gt $end) { Note "> $file $arguments : прервано по времени"; return -2 }
            }
            Note "> $file $arguments [с правами администратора, код $($p.ExitCode)]"
            return $p.ExitCode
        }
        $o = $p.StandardOutput.ReadToEndAsync(); $e = $p.StandardError.ReadToEndAsync()
        $end = (Get-Date).AddSeconds($timeoutSec)
        while (-not $p.HasExited) {
            Pump; Start-Sleep -Milliseconds 80
            if ((Get-Date) -gt $end) { try { $p.Kill() } catch {}; Note "> $file $arguments : прервано по времени"; return -2 }
        }
        $text = ''
        try { $text = $o.Result + $e.Result } catch {}
        if ($text.Length -gt 6000) { $text = $text.Substring($text.Length - 6000) }
        Note ("> $file $arguments`r`n[код $($p.ExitCode)] " + $text)
        return $p.ExitCode
    } catch { Note "> $file $arguments : $_"; return -1 }
}
function RefreshPath {
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
}
# Скачать файл: пробует адреса по очереди, сначала curl, потом средствами PowerShell. $true, если файл получен.
function Download([string[]]$urls, [string]$out, [int]$minBytes = 10000, [int]$maxTime = 600) {
    foreach ($u in $urls) {
        Remove-Item -LiteralPath $out -Force -ErrorAction SilentlyContinue
        if (Get-Command curl.exe -ErrorAction SilentlyContinue) {
            Run 'curl.exe' "-sSL --fail --retry 2 --retry-delay 2 --connect-timeout 20 --max-time $maxTime -o `"$out`" `"$u`"" ($maxTime * 3 + 60) | Out-Null
        }
        if (-not ((Test-Path -LiteralPath $out) -and (Get-Item -LiteralPath $out).Length -ge $minBytes)) {
            try { (New-Object Net.WebClient).DownloadFile($u, $out) } catch { Note "download $u : $_" }
        }
        if ((Test-Path -LiteralPath $out) -and (Get-Item -LiteralPath $out).Length -ge $minBytes) { return $true }
    }
    Remove-Item -LiteralPath $out -Force -ErrorAction SilentlyContinue
    return $false
}

# Подходит ли этот Python: 64 бита, версия 3.10-3.14, есть окна (tkinter) и создание окружений (venv).
function TestPython([string]$p) {
    try {
        $v = & $p -c "import sys, tkinter, venv, ensurepip, ssl; print(sys.version_info[0] * 100 + sys.version_info[1], sys.maxsize > 2**32)" 2>$null
        if ($LASTEXITCODE -eq 0 -and "$v" -match '^(\d+) True') { $n = [int]$Matches[1]; return ($n -ge 310 -and $n -le 314) }
    } catch {}
    return $false
}
function FindPython {
    $c = @()
    $c += Get-ChildItem "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe", "$env:ProgramFiles\Python3*\python.exe",
        "$env:LOCALAPPDATA\Python\pythoncore-*\python.exe", "C:\Python3*\python.exe" -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending | ForEach-Object FullName
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { $c += $cmd.Source }
    foreach ($p in $c) { if ($p -and (TestPython $p)) { return $p } }      # путь берём как есть: в нём может быть кириллица
    return $null
}
$PF = $env:ProgramFiles
$apps = @(
    # ver: проверенная версия. winget ставит именно её: новая версия программы может не понять наши настройки.
    @{ id = 'glzr-io.glazewm'; ver = '3.10.1'; name = 'GlazeWM (окна плиткой)'; exe = @("$PF\glzr.io\GlazeWM\glazewm.exe")
       url = 'https://github.com/glzr-io/glazewm/releases/download/v3.10.1/glazewm-v3.10.1.exe'; file = 'glazewm-setup.exe'; args = '/quiet /norestart' },
    @{ id = 'AmN.yasb'; ver = '2.0.8'; name = 'YASB (панель и док)'; exe = @("$PF\YASB\yasb.exe")
       url = 'https://github.com/amnweb/yasb/releases/download/v2.0.8/yasb-2.0.8-x64.msi'; file = 'yasb.msi'; args = 'msi' },
    @{ id = 'glzr-io.zebar'; ver = '3.3.1'; name = 'Zebar (виджеты на обоях)'; exe = @("$PF\glzr.io\Zebar\zebar.exe")
       url = 'https://github.com/glzr-io/zebar/releases/download/v3.3.1/zebar-v3.3.1-opt1-x64.msi'; file = 'zebar.msi'; args = 'msi' },
    @{ id = 'AutoHotkey.AutoHotkey'; name = 'AutoHotkey (клавиши)'
       exe = @("$env:LOCALAPPDATA\Programs\AutoHotkey\v2\AutoHotkey64.exe", "$PF\AutoHotkey\v2\AutoHotkey64.exe")
       url = @('https://github.com/AutoHotkey/AutoHotkey/releases/download/v2.0.31/AutoHotkey_2.0.31_setup.exe', 'https://www.autohotkey.com/download/ahk-v2.exe'); file = 'autohotkey-setup.exe'; args = '/silent' }
)
$pythonApp = @{ id = 'Python.Python.3.12'; name = 'Python 3.12'
    url = 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe'; file = 'python-setup.exe'
    args = '/passive InstallAllUsers=0 PrependPath=1 Include_launcher=0 Include_test=0' }
# Windhawk 2.0 (пока тестовая версия): только в ней есть windhawk-cli, через который ставится мод Проводника.
# winget не используем: там старая 1.7 без windhawk-cli.
$whCli = "$PF\Windhawk\windhawk-cli.exe"
$whMod = 'windows-11-file-explorer-styler'
$windhawkApp = @{ id = 'RamenSoftware.Windhawk'; name = 'Windhawk 2.0 (стиль Проводника)'; exe = @($whCli)
    url = 'https://github.com/ramensoftware/windhawk/releases/download/2.0.0-alpha.8/windhawk_setup.exe'; file = 'windhawk-setup.exe'; args = '/S' }
function Has($app) { foreach ($e in $app.exe) { if (Test-Path -LiteralPath $e) { return $true } }; return $false }
# WebView2 (движок, на котором работает Zebar). В Windows 11 есть всегда, в Windows 10 — почти всегда (приходит с Edge).
function HasWebView2 {
    foreach ($k in 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}',
                   'HKLM:\SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}',
                   'HKCU:\Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}') {
        $pv = (Get-ItemProperty -Path $k -Name pv -ErrorAction SilentlyContinue).pv
        if ($pv -and $pv -ne '0.0.0.0') { return $true }
    }
    return $false
}
$webviewApp = @{ id = 'Microsoft.EdgeWebView2Runtime'; name = 'WebView2 (для виджетов Zebar)'
    url = 'https://go.microsoft.com/fwlink/p/?LinkId=2124703'; file = 'webview2-setup.exe'; args = '/silent /install' }

# Поставить программу: сначала через winget, если не вышло, скачать установщик напрямую у разработчика.
function InstallApp($app, $winget, [scriptblock]$ready) {
    if ($winget) {
        $wg = "install -e --id $($app.id) --source winget --silent --accept-package-agreements --accept-source-agreements"
        if ($app.ver) { Run $winget "$wg --version $($app.ver)" | Out-Null }       # сначала проверенная версия
        if (-not (& $ready)) { Run $winget $wg | Out-Null }                       # её нет в winget — последняя
        if (& $ready) { return $true }
        Say "     через winget не вышло, скачиваю напрямую..." $mut
    }
    # качаем в папку установки: в её пути нет кириллицы (в отличие от TEMP при русском имени пользователя)
    $dl = "$dst\_downloads"
    New-Item -ItemType Directory -Force $dl | Out-Null
    $f = Join-Path $dl $app.file
    if (-not (Download @($app.url) $f 500000)) {
        Note "не скачалось: $($app.url)"
        Say "     не скачалось: нет доступа к $(([Uri]@($app.url)[0]).Host). Проверь интернет или включи VPN и нажми «Ещё раз»." $mut
        return $false
    }
    Unblock-File -LiteralPath $f -ErrorAction SilentlyContinue
    if ($app.args -eq 'msi') { $code = Run 'msiexec.exe' "/i `"$f`" /passive /norestart" }
    else { $code = Run $f $app.args }
    if (& $ready) { return $true }
    if ($code -eq 1223) { Say '     установка отменена: на вопрос Windows «Разрешить вносить изменения?» нужно ответить «Да».' $mut }
    elseif ($code -eq -1) { Say '     установщик не запустился: похоже, его заблокировал антивирус.' $mut }
    else { Say "     установщик программы закончил с ошибкой (код $code)." $mut }
    return $false
}

function Install {
    # папка установки: только английские буквы, цифры и - _ . без пробелов. Иначе часть программ не найдёт свои файлы.
    if (-not $TestRoot) {
        $want = $pathBox.Text.Trim().TrimEnd('\')
        if ($want -notmatch '^[A-Za-z]:(\\[A-Za-z0-9_.\-]+)+$') {
            Bad 'Папка установки: нужен путь вида D:\Programs\garasu, только английские буквы и цифры, без пробелов.'; return
        }
        $script:dst = $want
    }
    $go.Enabled = $false; $close.Enabled = $false; $pathBox.Enabled = $false; $browse.Enabled = $false
    $winget = (Get-Command winget -ErrorAction SilentlyContinue).Source

    # ---------------------------------------------------------- 1. проверка
    Step 'Шаг 1 из 6. Проверка компьютера' 3
    Note "папка установщика: $src | пользователь: $userHome | рабочий стол: $desktop | TEMP: $env:TEMP"
    $build = $osBuild
    # 1809 (17763) — минимум для лёгких виджетов Qt, плеера (кнопки медиа Windows) и программ оформления
    if ($build -lt 17763) { Bad "Windows слишком старая (сборка $build). Нужна Windows 10 версии 1809 или новее: обнови Windows через Центр обновления."; return }
    if ($win10) {
        Ok "Windows 10 (сборка $build): ставлю всё, что работает на Windows 10"
        Say '     будут прямые углы окон; стеклянный Проводник пропущу (он только для Windows 11)' $mut
        Say '     значки и шрифты Windows 11 заменятся встроенными шрифтами Windows 10' $mut
    } else { Ok "Windows 11 (сборка $build)" }
    if (-not [Environment]::Is64BitOperatingSystem) { Bad 'Нужна 64-разрядная Windows.'; return }
    if ($winget) { Ok 'winget найден' } else { Say '   - winget не найден: программы скачаю напрямую с сайтов разработчиков' $mut }
    foreach ($a in $apps) {
        if (Has $a) {
            $v = ''
            foreach ($e in $a.exe) { if (Test-Path -LiteralPath $e) { $v = "$((Get-Item -LiteralPath $e).VersionInfo.ProductVersion)".Trim(); break } }
            Ok "$($a.name): уже стоит $v"
            if ($a.ver -and $v -and $v -notmatch '^0\.0' -and -not $v.StartsWith($a.ver)) {
                Say "     проверено на версии $($a.ver). Если что-то будет выглядеть не так, обнови или поставь её." $mut
            }
        } else { Say "   - $($a.name): будет установлено" $mut }
    }
    $script:py = FindPython
    if ($script:py) { Ok "Python: $($script:py)" } else { Say '   - Python: будет установлен' $mut }
    $script:glass = $glassBox.Checked -and -not $TestRoot -and -not $win10
    if ($script:glass) {
        if (Has $windhawkApp) { Ok 'Windhawk 2.0: уже стоит' }
        elseif (Test-Path -LiteralPath "$PF\Windhawk\windhawk.exe") {
            Say '   - Windhawk стоит старый (без windhawk-cli): стиль Проводника пропущу. Обнови Windhawk до 2.0 и нажми «Ещё раз».' $mut
            $script:glass = $false
        } else { Say "   - $($windhawkApp.name): будет установлено" $mut }
    }
    if ($Check) { Say 'Режим проверки: дальше ничего не меняю.' $acc; return }

    # ---------------------------------------------------------- 2. программы
    Step 'Шаг 2 из 6. Программы (самый долгий шаг)' 10
    $i = 0
    foreach ($a in $apps) {
        $i++
        if (-not (Has $a)) {
            Say "   ставлю $($a.name)..." $mut
            $app = $a
            if (InstallApp $a $winget { Has $app }) { Ok "$($a.name): установлено" } else { Bad "$($a.name): не удалось установить" }
        }
        $bar.Value = 10 + $i * 8; Pump
    }
    if (-not $script:py) {
        Say '   ставлю Python 3.12...' $mut
        InstallApp $pythonApp $winget { RefreshPath; [bool](FindPython) } | Out-Null
        RefreshPath
        $script:py = FindPython
    }
    if (-not $script:py) { Bad 'Python не установился. Поставь Python 3.12 с python.org и запусти установку ещё раз.'; return }
    # Windhawk необязателен: если не встал, остальное оформление всё равно ставится
    if ($script:glass -and -not (Has $windhawkApp)) {
        Say "   ставлю $($windhawkApp.name)..." $mut
        if (InstallApp $windhawkApp $null { Has $windhawkApp }) { Ok "$($windhawkApp.name): установлено" }
        else { Say '   - Windhawk не встал: Проводник останется обычным, остальное поставлю.' $mut; $script:glass = $false }
    }

    # ---------------------------------------------------------- 3. свой Python в папке установки
    # Отдельное окружение C:\garasu\venv: путь без кириллицы и пробелов, библиотеки не смешиваются с чужими.
    Step 'Шаг 3 из 6. Библиотеки Python' 46
    New-Item -ItemType Directory -Force $dst | Out-Null
    # повторная установка поверх работающей: старые помощники и виджеты держат venv и старый код.
    # Без остановки venv не пересоздаётся (pythonw.exe занят), а после запуска были бы копии старых и новых процессов.
    $ours = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.CommandLine -and $_.CommandLine.ToLower().Contains($dst.ToLower() + '\') -and
        $_.Name -match '^(pythonw?|AutoHotkey64)\.exe$' -and $_.ProcessId -ne $PID })
    if ($ours.Count) {
        $ours | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
        Note "остановлено процессов прежней установки: $($ours.Count)"; Start-Sleep 1
        $script:stopped = $true          # если установка оборвётся, Finish запустит прежнюю установку обратно
    }
    $vpy = "$dst\venv\Scripts\python.exe"; $pyw = "$dst\venv\Scripts\pythonw.exe"
    $pipUser = ''
    function DropVenv {
        if (Test-Path -LiteralPath "$dst\venv\Scripts") { cmd /c rmdir "`"$dst\venv\Scripts`"" 2>$null }   # ссылка-папка удаляется без содержимого
        Remove-Item -LiteralPath "$dst\venv" -Recurse -Force -ErrorAction SilentlyContinue
    }
    if (-not ((Test-Path -LiteralPath $vpy) -and (Run $vpy '-c "import pip, tkinter"') -eq 0)) {
        DropVenv
        Run $script:py "-m venv `"$dst\venv`"" | Out-Null
        if (-not ((Test-Path -LiteralPath $vpy) -and (Run $vpy '-c "import pip"') -eq 0)) {
            # способ 2: окружение без pip, pip ставится отдельно
            DropVenv
            Run $script:py "-m venv --without-pip `"$dst\venv`"" | Out-Null
            if (Test-Path -LiteralPath $vpy) { Run $vpy '-m ensurepip --default-pip' | Out-Null }
        }
        if (-not ((Test-Path -LiteralPath $vpy) -and (Test-Path -LiteralPath $pyw) -and (Run $vpy '-c "import pip, tkinter"') -eq 0)) {
            # способ 3: без окружения. venv\Scripts становится ссылкой на папку установленного Python,
            # поэтому скрипты запуска находят venv\Scripts\pythonw.exe как обычно, а библиотеки ставятся пользователю.
            DropVenv
            New-Item -ItemType Directory -Force "$dst\venv" | Out-Null
            cmd /c mklink /J "`"$dst\venv\Scripts`"" "`"$(Split-Path $script:py)`"" | Out-Null
            $pipUser = ' --user'
            Note "venv не создался, использую Python напрямую: $($script:py)"
        }
    }
    if (-not ((Test-Path -LiteralPath $vpy) -and (Test-Path -LiteralPath $pyw) -and (Run $vpy '-c "import tkinter"') -eq 0)) {
        Bad "Не удалось подготовить Python ($($script:py)). Возможно, его блокирует антивирус. Подробности в журнале."; return
    }
    if ((Run $vpy '-c "import pip"') -ne 0) { Run $vpy '-m ensurepip --user' | Out-Null }
    $pip = '-m pip install --quiet --disable-pip-version-check --no-warn-script-location --prefer-binary --retries 5 --timeout 30' + $pipUser
    # Поставить группу библиотек. Сначала одной командой (быстрее); если не вышло — по одной, чтобы одна
    # неудачная библиотека не утянула за собой остальные. $true, если проверочный import проходит.
    function PipGroup([string]$imports, [string[]]$pkgs) {
        $test = "-c `"import $imports`""
        if ((Run $vpy $test) -eq 0) { return $true }
        Run $vpy "$pip $($pkgs -join ' ')" | Out-Null
        if ((Run $vpy $test) -eq 0) { return $true }
        foreach ($p in $pkgs) { Run $vpy "$pip $p" | Out-Null }
        return (Run $vpy $test) -eq 0
    }
    if (PipGroup 'PIL, yaml, materialyoucolor' @('pillow', 'materialyoucolor', 'pyyaml')) { Ok 'основные библиотеки готовы' }
    else { Bad 'Библиотеки Python не скачались (нет доступа к pypi.org): темы работать не будут.' }
    $bar.Value = 52; Pump
    if (-not (PipGroup 'numpy, pyaudiowpatch, pycaw' @('numpy', 'pyaudiowpatch', 'pycaw'))) {
        Say '   (часть звуковых библиотек не поставилась: может не быть визуализатора или микшера, остальное работает)' $mut
    }
    $bar.Value = 56; Pump
    # лёгкие виджеты на Qt (Garasu Classic): ~100 МБ памяти вместо ~800 МБ у Zebar. Не поставились — виджеты рисует Zebar.
    Say '   лёгкие виджеты (Qt): скачиваю около 80 МБ...' $mut
    $script:qtOk = PipGroup 'PyQt6.QtWidgets, PyQt6.QtSvg, psutil, numpy, winrt.windows.media.control' @('PyQt6', 'psutil', 'numpy',
        'winrt-runtime', 'winrt-Windows.Media.Control', 'winrt-Windows.Foundation', 'winrt-Windows.Foundation.Collections', 'winrt-Windows.Storage.Streams')
    if ($script:qtOk) { Ok 'лёгкие виджеты (Qt) готовы' } else { Say '   (библиотеки Qt не поставились: виджеты будет рисовать Zebar, он тяжелее, но работает так же)' $mut }
    # виджеты рисует Zebar — ему нужен WebView2. На старых и урезанных Windows 10 его бывает нет.
    if (-not $script:qtOk -and -not $TestRoot -and -not (HasWebView2)) {
        Say "   ставлю $($webviewApp.name)..." $mut
        if (InstallApp $webviewApp $winget { HasWebView2 }) { Ok "$($webviewApp.name): установлено" }
        else { Bad 'WebView2 не установился: виджеты на обоях не появятся. Поставь его с сайта Microsoft (Microsoft Edge WebView2) и нажми «Ещё раз».' }
    }

    # ---------------------------------------------------------- 4. файлы
    Step 'Шаг 4 из 6. Файлы оформления' 62
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $bak = "$dst\backup\before-install-$stamp"
    $yasb = "$userHome\.config\yasb"; $glaze = "$userHome\.glzr\glazewm"; $zebar = "$userHome\.glzr\zebar"
    New-Item -ItemType Directory -Force "$dst\theme", "$dst\wallpapers", "$dst\photos", $bak, $yasb, $glaze, "$zebar\ryoku" | Out-Null
    foreach ($f in "$yasb\config.yaml", "$yasb\styles.css", "$glaze\config.yaml", "$zebar\settings.json") {
        if (Test-Path -LiteralPath $f) { Copy-Item -LiteralPath $f (Join-Path $bak (($f.Substring($userHome.Length)) -replace '[:\\]', '_')) -Force }
    }
    try { (Get-ItemProperty 'HKCU:\Control Panel\Desktop').WallPaper | Set-Content "$bak\wallpaper.txt" -Encoding utf8 } catch {}
    Copy-Item "$src\theme\*" "$dst\theme" -Recurse -Force
    Copy-Item "$src\zebar\*" "$zebar\ryoku" -Recurse -Force
    # в настройках GlazeWM и в подсказке виджета «Фото» путь к папке установки подставляется настоящий
    $dstF = $dst.Replace('\', '/')
    $utf8 = New-Object Text.UTF8Encoding($false)
    $g = [IO.File]::ReadAllText("$src\glazewm-config.yaml", $utf8)
    [IO.File]::WriteAllText("$glaze\config.yaml", $g.Replace('pythonw C:/garasu/', "$dstF/venv/Scripts/pythonw.exe $dstF/"), $utf8)
    $ph = "$zebar\ryoku\photo.html"
    if (Test-Path -LiteralPath $ph) { [IO.File]::WriteAllText($ph, [IO.File]::ReadAllText($ph, $utf8).Replace('C:\garasu\photos', "$dst\photos"), $utf8) }
    Copy-Item "$src\uninstall.ps1", "$src\Uninstall.bat", "$src\start.bat" $dst -Force

    if (-not (Test-Path -LiteralPath "$dst\theme\settings.json")) {
        '{"dock": "auto", "side_gap": 24, "mode": "daily", "auto_game": true, "games": [], "auto_theme": {"on": false, "day": "sky", "night": "night", "day_from": 8, "night_from": 20}}' |
            Set-Content "$dst\theme\settings.json" -Encoding ascii
    }
    if ((Test-Path -LiteralPath "$dst\theme\ryoku.py") -and (Test-Path -LiteralPath "$zebar\ryoku\common.js") -and (Test-Path -LiteralPath "$dst\start.bat")) {
        Ok 'файлы скопированы, прежние настройки сохранены в backup'
    } else { Bad 'Файлы оформления не скопировались. Распакуй архив целиком в обычную папку и запусти установку ещё раз.'; return }

    # ---------------------------------------------------------- 5. обои
    Step 'Шаг 5 из 6. Обои (из открытого репозитория Ryoku на GitHub)' 72
    $mirrors = @('https://raw.githubusercontent.com/ryoku-dev/ryoku/HEAD/ryoku/assets/wallpapers/',
                 'https://github.com/ryoku-dev/ryoku/raw/HEAD/ryoku/assets/wallpapers/',
                 'https://cdn.jsdelivr.net/gh/ryoku-dev/ryoku@HEAD/ryoku/assets/wallpapers/')
    $themes = Get-Content -LiteralPath "$dst\theme\themes.json" -Raw -Encoding UTF8 | ConvertFrom-Json
    $got = @(); $failed = 0
    foreach ($t in $themes) {
        $out = Join-Path "$dst\wallpapers" $t.wallpaper
        $have = (Test-Path -LiteralPath $out) -and (Get-Item -LiteralPath $out).Length -gt 10000
        if (-not $have -and -not ($failed -ge 2 -and $got.Count -eq 0)) {          # два подряд не скачались: сети нет, не ждём остальные
            $have = Download ($mirrors | ForEach-Object { $_ + $t.wallpaper }) $out 10000 180
        }
        if ($have) { $got += $t; Ok $t.name } else { $failed++; Say "   - не скачалось: $($t.name)" $mut }
        $bar.Value = [Math]::Min(88, $bar.Value + 2); Pump
    }
    $themeArg = $null
    if ($got.Count) { $themeArg = $got[0].id }
    else {
        # обоев нет: рисуем свои, чтобы установка всё равно закончилась. Скачать остальные можно повторным запуском.
        Say '   обои не скачались (GitHub недоступен): ставлю запасные, остальные можно докачать повторной установкой' $mut
        $fb = "$dst\wallpapers\garasu-default.png"
        Run $vpy "`"$dst\theme\fallback_wall.py`" `"$fb`"" | Out-Null
        if (Test-Path -LiteralPath $fb) { $themeArg = "`"$fb`"" } else { Bad 'Не удалось получить ни одних обоев.' }
    }
    Get-ChildItem "$dst\wallpapers" -File | Select-Object -First 2 | ForEach-Object { if (-not (Test-Path -LiteralPath "$dst\photos\$($_.Name)")) { Copy-Item -LiteralPath $_.FullName "$dst\photos" } }

    # ---------------------------------------------------------- 6. настройка и запуск
    Step 'Шаг 6 из 6. Настройка и запуск' 90
    RefreshPath
    $env:Path = "$PF\glzr.io\GlazeWM;$PF\glzr.io\Zebar;$PF\YASB;" + $env:Path
    # флаг classic.on: виджеты рисует Qt. Ставим, только если classic.py сам подтвердил, что библиотеки на месте.
    # classic.off: человек сам выключил лёгкие виджеты в панели — при переустановке его выбор не трогаем.
    if (Test-Path -LiteralPath "$dst\theme\classic.off") { Note 'лёгкие виджеты выключены пользователем (classic.off)' }
    elseif ($script:qtOk -and (Run $vpy "`"$dst\theme\classic.py`" --check") -eq 0) {
        Set-Content -LiteralPath "$dst\theme\classic.on" -Value 'Garasu Classic' -Encoding utf8
    } else { Remove-Item -LiteralPath "$dst\theme\classic.on" -Force -ErrorAction SilentlyContinue }
    if ((Run $vpy "`"$dst\theme\widgets.py`" install") -ne 0) { Bad 'Не удалось подготовить виджеты.' }
    if ($themeArg) {
        if ((Run $vpy "`"$dst\theme\ryoku.py`" $themeArg") -eq 0) { Ok 'тема применена' } else { Bad 'Тема не применилась.' }
    }
    # мод Проводника из каталога Windhawk; цвета под тему ему потом пишет ryoku.py (через explorer_style.py)
    if ($script:glass) {
        $hadMod = (Run $whCli "mod show $whMod") -eq 0
        if ($hadMod -or (Run $whCli "--quiet mod install $whMod" 600) -eq 0) {
            if (-not $hadMod) { Set-Content -LiteralPath "$dst\theme\explorer_mod_by_ryoku.txt" -Value $whMod -Encoding utf8 }
            Run $whCli "mod enable $whMod" | Out-Null
            if ((Run $vpy "`"$dst\theme\explorer_style.py`"") -eq 0) { Ok 'Проводник: тёмное стекло под цвет темы' }
            else { Say '   - Проводник: мод стоит, но цвета не записались (подробности в журнале)' $mut }
        } else { Say '   - Проводник: мод Windhawk не поставился, Проводник останется обычным (подробности в журнале)' $mut }
    }
    try {
        $sh = New-Object -ComObject WScript.Shell
        $links = @(
            @{ path = "$startup\Garasu.lnk"; target = "$dst\start.bat"; args = ''; dir = $dst; style = 7 },
            @{ path = "$desktop\Garasu - темы.lnk"; target = $pyw; args = "`"$dst\theme\themes_panel.pyw`""; dir = "$dst\theme"; style = 1 },
            @{ path = "$desktop\Удалить Garasu.lnk"; target = "$dst\Uninstall.bat"; args = ''; dir = $dst; style = 1 })
        foreach ($k in $links) {
            try {
                $l = $sh.CreateShortcut($k.path); $l.TargetPath = $k.target; $l.Arguments = $k.args
                $l.WorkingDirectory = $k.dir; $l.WindowStyle = $k.style; $l.Save()
            } catch { Note "ярлык $($k.path): $_" }
        }
    } catch { Note "ярлыки: $_" }
    if (Test-Path -LiteralPath "$startup\Garasu.lnk") { Ok 'автозапуск включён' }
    else { Bad "Не удалось включить автозапуск. Запускай вручную: $dst\start.bat" }
    if ($TestRoot) {
        # проверка скачивания картинок для виджета «Фото»: по одной на тему
        if ((Run $vpy "`"$dst\theme\pack_fetch.py`" --limit 1" 900) -eq 0) { Ok 'картинки для виджета «Фото»: проверка скачивания прошла' }
        $bar.Value = 100; $script:done = $true; Ok 'проверочная установка: запуск пропущен'; return
    }
    # картинки для виджета «Фото» (около 150 МБ) качаются в фоне: установка их не ждёт
    Start-Process $pyw -ArgumentList "`"$dst\theme\pack_fetch.py`"" -WorkingDirectory "$dst\theme" -WindowStyle Hidden
    Say '   картинки для виджета «Фото» скачиваются в фоне, появятся через несколько минут' $mut

    Get-Process glazewm, yasb, zebar -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep 1
    Start-Process "$dst\start.bat" -WindowStyle Hidden
    $up = $false
    foreach ($n in 1..40) {
        Pump; Start-Sleep -Milliseconds 500
        if ((Get-Process glazewm -ErrorAction SilentlyContinue) -and (Get-Process yasb -ErrorAction SilentlyContinue)) { $up = $true; break }
    }
    $bar.Value = 100; $script:done = $true
    if ($up) { Ok 'рабочий стол запускается' } else { Bad 'Программы не запустились сами. Перезагрузи компьютер: после входа всё стартует автоматически.' }
}

function Finish {
    try { Copy-Item -LiteralPath $log "$dst\install.log" -Force -ErrorAction SilentlyContinue } catch {}
    $close.Enabled = $true
    if ($Check) { $go.Enabled = $true; return }
    Say ''
    if ($script:stopped -and -not $script:done -and -not $TestRoot -and (Test-Path -LiteralPath "$dst\start.bat")) {
        # переустановка оборвалась после остановки прежних помощников: вернуть клавишу Win, панель и виджеты
        Start-Process "$dst\start.bat" -WindowStyle Hidden -ErrorAction SilentlyContinue
        Note 'установка оборвалась: прежний рабочий стол запущен снова'
    }
    $script:stopped = $false
    if ($script:problems.Count) {
        $go.Enabled = $true; $pathBox.Enabled = $true; $browse.Enabled = $true; $go.Text = 'Ещё раз'; $logBtn.Visible = $true
        Say 'Были проблемы. Можно нажать «Ещё раз»: уже сделанное не повторяется.' ([Drawing.Color]::FromArgb(255, 200, 120))
        Say 'Если не помогло, нажми «Журнал» и пришли этот файл автору.' $mut
    } elseif ($script:done) {
        Say 'Готово! Через несколько секунд появятся панель и виджеты.' ([Drawing.Color]::FromArgb(150, 220, 160))
        Say 'Win - поиск приложений.  Кнопка с палитрой на панели - темы.' $fg
        Say 'Alt+1..9 - рабочие столы.  Alt+Shift+Q - закрыть окно.  Ctrl+Alt+1/2/3 - режимы.' $fg
    }
}

$go.Add_Click({
    $script:problems = @(); $script:done = $false
    try { Install } catch { Bad "Ошибка установщика: $_"; Note $_.ScriptStackTrace }
    Finish
})
if ($Check) { $go.Text = 'Проверить' }
if ($Auto) {
    try { Install } catch { Bad "Ошибка установщика: $_"; Note $_.ScriptStackTrace }
    Finish
    exit $script:problems.Count
}
[void]$form.ShowDialog()
