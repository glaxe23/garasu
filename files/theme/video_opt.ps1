param([string]$src, [string]$dst, [int]$mw = 1920, [int]$mh = 1080)
# Облегчённая копия видео для живых обоев Garasu. Встроенный в Windows MediaTranscoder (аппаратный кодер),
# ничего ставить не надо. Копия: не больше монитора (с сохранением пропорций), не больше ~30 кадров/с, H.264.
# Коды выхода: 0 — копия готова (dst), 3 — видео и так лёгкое, копия не нужна, 2 — не получилось.
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.Encoding]::UTF8
try {
    Add-Type -AssemblyName System.Runtime.WindowsRuntime
    $null = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
    $null = [Windows.Media.Transcoding.MediaTranscoder, Windows.Media.Transcoding, ContentType = WindowsRuntime]
    $null = [Windows.Media.MediaProperties.MediaEncodingProfile, Windows.Media.MediaProperties, ContentType = WindowsRuntime]
    $ext = [System.WindowsRuntimeSystemExtensions].GetMethods()
    $asTask = ($ext | ? { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
    $asTaskP = ($ext | ? { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncActionWithProgress`1' })[0]
    function Await($op, $t) { $task = $asTask.MakeGenericMethod($t).Invoke($null, @($op)); $task.Wait(-1) | Out-Null; $task.Result }

    $in = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($src)) ([Windows.Storage.StorageFile])
    $sp = Await ([Windows.Media.MediaProperties.MediaEncodingProfile]::CreateFromFileAsync($in)) ([Windows.Media.MediaProperties.MediaEncodingProfile])
    $sv = $sp.Video
    $sw = [double]$sv.Width; $sh = [double]$sv.Height
    $fn = [int]$sv.FrameRate.Numerator; $fd = [int][Math]::Max(1, $sv.FrameRate.Denominator)
    $fps = $fn / $fd
    if ($sw -le 0 -or $sh -le 0) { "нет видеодорожки"; exit 2 }

    # размер: накрыть самый большой монитор, но не больше исходника
    $k = [Math]::Min(1.0, [Math]::Max($mw / $sw, $mh / $sh))
    $tw = [int]([Math]::Round($sw * $k / 2) * 2); $th = [int]([Math]::Round($sh * $k / 2) * 2)
    # частота: делим ровно (60 -> 30, 50 -> 25, 120 -> 30), чтобы движение оставалось ровным
    $n = 1; if ($fps -gt 31) { $n = [int][Math]::Ceiling($fps / 30) }
    $tfps = $fps / $n
    $kbps = [int][Math]::Max(2000, $tw * $th * $tfps * 0.1 / 1000)
    $heavy = ($k -lt 0.95) -or ($n -gt 1) -or ($sv.Subtype -ne "H264") -or ($sv.Bitrate -gt 2.5 * $kbps * 1000)
    "исходник {0}x{1} {2:N1} к/с {3} {4} кбит/с -> {5}x{6} {7:N1} к/с {8} кбит/с" -f $sw, $sh, $fps, $sv.Subtype, [int]($sv.Bitrate / 1000), $tw, $th, $tfps, $kbps
    if (-not $heavy) { "копия не нужна"; exit 3 }

    $dir = Await ([Windows.Storage.StorageFolder]::GetFolderFromPathAsync((Split-Path $dst))) ([Windows.Storage.StorageFolder])
    $out = Await ($dir.CreateFileAsync((Split-Path $dst -Leaf), [Windows.Storage.CreationCollisionOption]::ReplaceExisting)) ([Windows.Storage.StorageFile])
    $prof = [Windows.Media.MediaProperties.MediaEncodingProfile]::CreateMp4([Windows.Media.MediaProperties.VideoEncodingQuality]::HD1080p)
    $prof.Audio = $null                                  # звук обоям не нужен
    $v = $prof.Video
    $v.Width = $tw; $v.Height = $th; $v.Bitrate = $kbps * 1000
    $v.FrameRate.Numerator = $fn; $v.FrameRate.Denominator = $fd * $n
    $v.PixelAspectRatio.Numerator = 1; $v.PixelAspectRatio.Denominator = 1
    $tr = New-Object Windows.Media.Transcoding.MediaTranscoder
    $tr.HardwareAccelerationEnabled = $true
    $tr.VideoProcessingAlgorithm = [Windows.Media.Transcoding.MediaVideoProcessingAlgorithm]::MrfCrf444   # качественное уменьшение
    $sw2 = [Diagnostics.Stopwatch]::StartNew()
    $prep = Await ($tr.PrepareFileTranscodeAsync($in, $out, $prof)) ([Windows.Media.Transcoding.PrepareTranscodeResult])
    if (-not $prep.CanTranscode) { "нельзя перекодировать: " + $prep.FailureReason; exit 2 }
    $task = $asTaskP.MakeGenericMethod([double]).Invoke($null, @($prep.TranscodeAsync()))
    $task.Wait(-1) | Out-Null
    "копия готова за {0:N0} c" -f $sw2.Elapsed.TotalSeconds
    exit 0
} catch {
    "ошибка: " + $_.Exception.Message
    exit 2
}
