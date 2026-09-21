"""Read an explicitly selected image with the OCR engine included in Windows."""
import json
from pathlib import Path
import subprocess

SCRIPT = r'''
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new()
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null=[Windows.Storage.StorageFile,Windows.Storage,ContentType=WindowsRuntime]
$null=[Windows.Storage.Streams.IRandomAccessStream,Windows.Storage.Streams,ContentType=WindowsRuntime]
$null=[Windows.Graphics.Imaging.BitmapDecoder,Windows.Graphics.Imaging,ContentType=WindowsRuntime]
$null=[Windows.Graphics.Imaging.SoftwareBitmap,Windows.Graphics.Imaging,ContentType=WindowsRuntime]
$null=[Windows.Media.Ocr.OcrEngine,Windows.Foundation,ContentType=WindowsRuntime]
$null=[Windows.Media.Ocr.OcrResult,Windows.Foundation,ContentType=WindowsRuntime]
$taskMethod=([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
 $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetGenericArguments().Count -eq 1 -and
 $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
} | Select-Object -First 1)
function Await($operation, $type) {
 $task=$taskMethod.MakeGenericMethod($type).Invoke($null,@($operation))
 if(-not $task.Wait(20000)){throw 'OCR timeout'}
 return $task.Result
}
$path=[Console]::In.ReadToEnd() | ConvertFrom-Json
$engine=[Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
if($null -eq $engine){throw 'No OCR language installed'}
$file=Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($path)) ([Windows.Storage.StorageFile])
$stream=Await ($file.OpenAsync(0)) ([Windows.Storage.Streams.IRandomAccessStream])
try {
 $decoder=Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
 if($decoder.PixelWidth -gt [Windows.Media.Ocr.OcrEngine]::MaxImageDimension -or $decoder.PixelHeight -gt [Windows.Media.Ocr.OcrEngine]::MaxImageDimension){throw 'Image too large'}
 $bitmap=Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
 try {
  $result=Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
  @{text=$result.Text;backend='Windows OCR';language=$engine.RecognizerLanguage.LanguageTag} | ConvertTo-Json -Compress
 } finally {$bitmap.Dispose()}
} finally {$stream.Dispose()}
'''


def read(path):
    path = Path(path).resolve(strict=True)
    if path.stat().st_size > 20 * 1024 * 1024:
        raise ValueError('Для OCR выберите изображение до 20 МБ.')
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', SCRIPT],
                            input=json.dumps(str(path)), capture_output=True, text=True, encoding='utf-8',
                            timeout=60, creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        raise ValueError('Windows OCR не прочитал изображение. Проверьте языковые компоненты OCR в параметрах Windows и размер изображения.')
    return json.loads(result.stdout.lstrip('\ufeff'))
