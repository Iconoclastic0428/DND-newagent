param(
    [string]$BindHost = '127.0.0.1',
    [int]$Port = 8766
)

Set-Location (Resolve-Path (Join-Path $PSScriptRoot '..\..'))
python user-test/story_demo_system_server.py --host $BindHost --port $Port
