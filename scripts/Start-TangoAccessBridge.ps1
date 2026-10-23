param([string]$AccessFile = 'C:\Users\windows\Desktop\Interfaz TANGO FONTELA Version2 SEPARACION FAC REM.mdb')
$root = Split-Path $PSScriptRoot -Parent
$spool = Join-Path $root 'backend\.tango_access_bridge'
[void][IO.Directory]::CreateDirectory($spool)
$stop = Join-Path $spool 'stop'
if (Test-Path -LiteralPath $stop) {Remove-Item -LiteralPath $stop -Force}
$heartbeat = Join-Path $spool 'heartbeat.json'
if (Test-Path -LiteralPath $heartbeat) {
    $state = Get-Content -Raw -LiteralPath $heartbeat | ConvertFrom-Json
    if ([DateTimeOffset]::UtcNow.ToUnixTimeSeconds() - [long]$state.utc -lt 20) {
        Write-Output 'El conector Access ya está iniciado.'
        exit
    }
}
$runtime = Get-Command pwsh -ErrorAction SilentlyContinue
$exe = if ($runtime) {$runtime.Source} else {Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'}
$worker = Join-Path $PSScriptRoot 'TangoAccessBridge.ps1'
$arguments = '-NoProfile -NonInteractive -STA -File "'+$worker+'" -BridgeRoot "'+$spool+'" -AccessFile "'+$AccessFile+'"'
$process = Start-Process -FilePath $exe -ArgumentList $arguments -WindowStyle Hidden -PassThru -RedirectStandardError (Join-Path $spool 'startup.error.log') -RedirectStandardOutput (Join-Path $spool 'startup.log')
for ($attempt=0; $attempt -lt 20; $attempt++) {
    Start-Sleep -Milliseconds 300
    if (Test-Path -LiteralPath $heartbeat) {
        $state=Get-Content -Raw -LiteralPath $heartbeat | ConvertFrom-Json
        if ([DateTimeOffset]::UtcNow.ToUnixTimeSeconds() - [long]$state.utc -lt 10) {
            Write-Output ('Conector Access iniciado. PID '+$process.Id)
            exit
        }
    }
    if ($process.HasExited) {break}
}
throw 'No se pudo iniciar el conector. Revisá backend/.tango_access_bridge/startup.error.log.'
