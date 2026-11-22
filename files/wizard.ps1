# Визуальное оформление мастера. Координаты заданы для рабочей области 960 × 560.
$paper = [Drawing.ColorTranslator]::FromHtml('#f6efde')
$ink = [Drawing.ColorTranslator]::FromHtml('#272723')
$wine = [Drawing.ColorTranslator]::FromHtml('#963e4c')
$creamMuted = [Drawing.ColorTranslator]::FromHtml('#665d50')
$form.AutoScaleMode = 'None'
$form.ClientSize = '960,560'
$form.BackColor = $paper
$form.ForeColor = $ink
$version = (Get-Content -LiteralPath (Join-Path $src 'theme/version.txt') -Raw).Trim()
$form.Text = "Garasu $version — установка"
$form.Icon = New-Object Drawing.Icon((Join-Path $src 'garasu.ico'), 32, 32)
$form.AutoScroll = $true
$hero = New-Object Windows.Forms.PictureBox
$hero.Location = '420,0'
$hero.Size = '540,560'
$hero.SizeMode = 'StretchImage'
$hero.Image = [Drawing.Image]::FromFile((Join-Path $src 'dream-chaser.gif'))
$form.Controls.Add($hero)
$hero.SendToBack()

function MakeLabel($caption, $bounds, $family, $size, $style, $color) {
    $label = New-Object Windows.Forms.Label
    $label.Text = $caption
    $label.Bounds = New-Object Drawing.Rectangle -ArgumentList $bounds
    $label.BackColor = $paper
    $label.ForeColor = $color
    $label.Font = New-Object Drawing.Font($family, $size, [Drawing.FontStyle]$style, [Drawing.GraphicsUnit]::Pixel)
    $form.Controls.Add($label)
    $label.BringToFront()
    return $label
}
function StyleButton($button, $bounds, $primary) {
    $button.Bounds = New-Object Drawing.Rectangle -ArgumentList $bounds
    $button.FlatStyle = 'Flat'
    $button.FlatAppearance.BorderSize = 0
    $button.Cursor = 'Hand'
    $button.Font = New-Object Drawing.Font('Segoe UI',10,[Drawing.FontStyle]::Bold)
    if ($primary) { $button.BackColor = $ink; $button.ForeColor = $paper }
    else { $button.BackColor = [Drawing.ColorTranslator]::FromHtml('#e6ddca'); $button.ForeColor = $ink }
}
$brand = MakeLabel 'G' @(46,32,32,28) 'Arial Black' 18 'Italic' $paper
$brand.BackColor = $ink; $brand.TextAlign = 'MiddleCenter'
$wordmark = MakeLabel 'G A R A S U' @(88,37,180,22) 'Segoe UI' 14 'Bold' $ink
$kicker = MakeLabel 'ОФОРМЛЕНИЕ WINDOWS' @(45,147,330,23) 'Segoe UI' 12 'Bold' $wine
$headline = MakeLabel 'Garasu' @(38,165,380,105) 'Arial Black' 74 'Bold, Italic' $ink
$headline.AutoSize = $false
$headline.Text = ''
$headline.Image = [Drawing.Image]::FromFile((Join-Path $src 'wordmark.png'))
$headline.ImageAlign = 'MiddleLeft'
$intro = MakeLabel "Виджеты и живые обои`r`nдля твоего рабочего стола." @(46,277,358,67) 'Segoe UI' 22 'Regular' $ink
$next = New-Object Windows.Forms.Button
$next.Text = 'Начать установку    →'
StyleButton $next @(46,363,215,46) $true
$form.Controls.Add($next)
$foot = MakeLabel '' @(46,513,340,24) 'Segoe UI' 13 'Regular' $creamMuted
$rule = New-Object Windows.Forms.Panel
$rule.Bounds = '46,499,340,1'; $rule.BackColor = [Drawing.ColorTranslator]::FromHtml('#c3b9a8')
$form.Controls.Add($rule)
$sheet = New-Object Windows.Forms.Panel
$sheet.Bounds = '0,0,665,560'; $sheet.BackColor = $paper
$form.Controls.Add($sheet); $sheet.SendToBack(); $hero.SendToBack()
$title.AutoSize = $false; $title.Bounds = '44,80,612,54'
$title.BackColor = $paper; $title.ForeColor = $ink
$title.Font = New-Object Drawing.Font('Segoe UI',24,[Drawing.FontStyle]::Bold)
$sub.Bounds = '47,144,578,155'; $sub.ForeColor = $creamMuted
$sub.Font = New-Object Drawing.Font('Segoe UI',10)
$sub.Text = "Будут установлены недостающие программы: GlazeWM, YASB, Zebar, AutoHotkey и Python. Garasu скачает обои и включит автозапуск. Системная панель задач скроется, клавиша Win будет открывать поиск.`r`n`r`nПонадобятся интернет и около 5–10 минут. Изменения можно отменить через «Удалить Garasu»."
$pathLbl.Location = '46,300'; $pathLbl.ForeColor = $ink
$pathBox.Bounds = '47,327,435,28'; $pathBox.BackColor = [Drawing.Color]::White; $pathBox.ForeColor = $ink
StyleButton $browse @(492,322,110,32) $false
$glassBox.Bounds = '46,373,570,45'; $glassBox.ForeColor = $ink
$glassBox.BackColor = $paper
$box.Bounds = '46,151,571,248'
$box.BackColor = $ink; $box.ForeColor = $paper
StyleButton $go @(46,438,180,42) $true
StyleButton $close @(239,438,114,42) $false
StyleButton $logBtn @(367,438,114,42) $false
$track = New-Object Windows.Forms.Panel
$track.Bounds = '46,410,571,5'; $track.BackColor = [Drawing.ColorTranslator]::FromHtml('#dfd5c4')
$fill = New-Object Windows.Forms.Panel
$fill.Height = 5; $fill.Width = 0; $fill.BackColor = $wine
$track.Controls.Add($fill); $form.Controls.Add($track)
$bar.Visible = $false
function ShowStage([string]$stage) {
    $script:stage = $stage
    $welcome = $stage -eq 'welcome'
    $config = $stage -eq 'config'
    foreach ($control in @($kicker,$headline,$intro,$next)) { $control.Visible = $welcome }
    foreach ($control in @($sub,$pathLbl,$pathBox,$browse,$glassBox)) { $control.Visible = $config }
    $sheet.Visible = !$welcome; $title.Visible = !$welcome
    $box.Visible = !$welcome -and !$config; $track.Visible = $box.Visible
    $go.Visible = $config; $close.Visible = !$welcome; $logBtn.Visible = $false
    switch ($stage) {
        welcome { $foot.Text = 'Добро пожаловать'; $form.AcceptButton = $next }
        config { $title.Text = 'Параметры установки'; $foot.Text = "Garasu   /   $version"; $form.AcceptButton = $go }
        running { $title.Text = 'Установка Garasu'; $foot.Text = 'Ход установки'; $form.AcceptButton = $null }
        result { $foot.Text = 'Итог установки'; $form.AcceptButton = $close }
    }
}
$next.Add_Click({ ShowStage config })
$form.Add_FormClosing({ param($sender,$eventArgs) if ($script:stage -eq 'running') { $eventArgs.Cancel = $true } })
$form.Add_FormClosed({ $hero.Image.Dispose() })
ShowStage welcome
