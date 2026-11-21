# Следит за тем, что сейчас играет в Windows (тот же источник, что у кнопок мультимедиа на клавиатуре).
# Раз в секунду проверяет трек; когда он меняется, сохраняет обложку в файл и печатает строку JSON.
# Запускается помощником helper.pyw:  powershell -File media.ps1 <папка для обложки> [once]
param([string]$OutDir = $env:TEMP, [string]$Mode = 'loop')
$ErrorActionPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Await($op, $type) {
    $task = $asTaskGeneric.MakeGenericMethod($type).Invoke($null, @($op))
    $task.Wait(5000) | Out-Null
    $task.Result
}
[Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager, Windows.Media.Control, ContentType = WindowsRuntime] | Out-Null
[Windows.Storage.Streams.IRandomAccessStreamWithContentType, Windows.Storage.Streams, ContentType = WindowsRuntime] | Out-Null
$mgr = Await ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager]::RequestAsync()) ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager])
$raw = Join-Path $OutDir 'art.raw'
$last = $null
while ($true) {
    $title = ''; $artist = ''; $album = ''; $hasArt = $false; $dur = 0; $app = ''
    $s = $mgr.GetCurrentSession()
    if ($s) {
        $app = [string]$s.SourceAppUserModelId
        $p = Await ($s.TryGetMediaPropertiesAsync()) ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionMediaProperties])
        if ($p) {
            $title = [string]$p.Title; $artist = [string]$p.Artist; $album = [string]$p.AlbumTitle
            $hasArt = $null -ne $p.Thumbnail
            $dur = [int]$s.GetTimelineProperties().EndTime.TotalSeconds
        }
    }
    $key = "$title|$artist|$hasArt|$app"
    if ($key -ne $last) {
        $last = $key
        $saved = $false
        if ($hasArt) {
            try {
                $stream = Await ($p.Thumbnail.OpenReadAsync()) ([Windows.Storage.Streams.IRandomAccessStreamWithContentType])
                $net = [System.IO.WindowsRuntimeStreamExtensions]::AsStreamForRead($stream)
                $fs = [System.IO.File]::Create($raw)
                $net.CopyTo($fs); $fs.Close(); $net.Close()
                $saved = (Get-Item $raw).Length -gt 0
            } catch {}
        }
        @{ title = $title; artist = $artist; album = $album; art = $saved; duration = $dur; app = $app } | ConvertTo-Json -Compress
        [Console]::Out.Flush()
    }
    if ($Mode -eq 'once') { break }
    Start-Sleep -Milliseconds 1500
}
