# Сколько оперативной памяти занимает Garasu по частям. Запуск: powershell -File measure.ps1
$all = Get-CimInstance Win32_Process
$zebar = @($all | Where-Object Name -eq 'zebar.exe' | ForEach-Object ProcessId)
$rows = foreach ($p in $all) {
    $g = $null; $c = [string]$p.CommandLine
    switch -Regex ($p.Name) {
        '^zebar\.exe$'            { $g = 'Zebar (виджеты на обоях): ядро' }
        '^msedgewebview2\.exe$'   { if ($c -match 'zebar' -or $zebar -contains $p.ParentProcessId) { $g = 'Zebar (виджеты на обоях): браузерные процессы' } }
        '^yasb\.exe$'             { $g = 'YASB (панель и док)' }
        '^glazewm(-watcher)?\.exe$' { $g = 'GlazeWM (плитка окон)' }
        '^AutoHotkey64\.exe$'     { if ($c -match 'garasu') { $g = 'AutoHotkey (клавиши)' } }
        '^pythonw?\.exe$'         { if ($c -match 'garasu\\theme\\(\w+)') { $g = 'Python: ' + $Matches[1] } }
        '^powershell\.exe$'       { if ($c -match 'media\.ps1') { $g = 'PowerShell: media.ps1' } }
    }
    if ($g) { [pscustomobject]@{ G = $g; MB = $p.WorkingSetSize / 1MB } }
}
$t = $rows | Group-Object G | ForEach-Object { [pscustomobject]@{ 'Часть' = $_.Name; 'Процессов' = $_.Count; 'МБ' = [math]::Round(($_.Group | Measure-Object MB -Sum).Sum) } } | Sort-Object 'МБ' -Descending
$t | Format-Table -AutoSize
"ВСЕГО: {0} МБ" -f [math]::Round(($rows | Measure-Object MB -Sum).Sum)
