$ErrorActionPreference = 'Stop'
$app = Join-Path $env:LOCALAPPDATA 'FridayAssistant'
$zip = Join-Path $env:TEMP 'Friday-Portable.zip'
$url = 'https://github.com/happyfox102/---------------/releases/latest/download/Friday-Portable.zip'
Write-Host 'Скачивание Пятницы...'
Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing
# Preserve existing settings, history and Windows-protected credentials.
New-Item $app -ItemType Directory -Force | Out-Null
Expand-Archive $zip -DestinationPath $app -Force
$exe = Get-ChildItem $app -Filter 'Пятница.exe' -Recurse | Select-Object -First 1
if (-not $exe) { throw 'В архиве не найден Пятница.exe' }
$desktop = [Environment]::GetFolderPath('Desktop')
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut((Join-Path $desktop 'Пятница.lnk'))
$shortcut.TargetPath = $exe.FullName
$shortcut.WorkingDirectory = $exe.DirectoryName
$shortcut.IconLocation = "$($exe.FullName),0"
$shortcut.Save()
Remove-Item $zip -Force -ErrorAction SilentlyContinue
Write-Host "Готово. Ярлык создан: $desktop\Пятница.lnk"
Start-Process $exe.FullName
