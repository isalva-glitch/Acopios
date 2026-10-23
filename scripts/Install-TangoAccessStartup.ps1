param([switch]$Remove)
$ErrorActionPreference = 'Stop'
$startup = [Environment]::GetFolderPath('Startup')
$linkPath = Join-Path $startup 'Acopios - Conector Tango.lnk'
if ($Remove) {
    if (Test-Path -LiteralPath $linkPath) {Remove-Item -LiteralPath $linkPath -Force}
    Write-Output 'Inicio automatico del conector desactivado.'
    exit
}
$launcher = Join-Path $PSScriptRoot 'Start-TangoAccessBridge.ps1'
if (-not (Test-Path -LiteralPath $launcher)) {throw 'No se encontro el iniciador del conector.'}
$shell = New-Object -ComObject WScript.Shell
try {
    $shortcut = $shell.CreateShortcut($linkPath)
    $shortcut.TargetPath = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $shortcut.Arguments = '-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + $launcher + '"'
    $shortcut.WorkingDirectory = Split-Path $PSScriptRoot -Parent
    $shortcut.WindowStyle = 7
    $shortcut.Description = 'Inicia el conector de consultas Tango de Acopios al ingresar a Windows.'
    $shortcut.Save()
} finally {
    [void][Runtime.InteropServices.Marshal]::ReleaseComObject($shell)
}
Write-Output 'Inicio automatico del conector configurado para este usuario.'