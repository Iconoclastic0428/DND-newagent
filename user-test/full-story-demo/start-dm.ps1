param(
    [string]$BindHost = '127.0.0.1',
    [int]$Port = 8766
)

Set-Location (Resolve-Path (Join-Path $PSScriptRoot '..\..'))
powershell -ExecutionPolicy Bypass -File .\user-test\full-story-demo\start-controller.ps1 -BindHost $BindHost -Port $Port -ControllerId dm
