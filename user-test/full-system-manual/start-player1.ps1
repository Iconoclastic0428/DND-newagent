param(
    [string]$BindHost = '127.0.0.1',
    [int]$Port = 8765
)

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..')
Set-Location $repoRoot
python user-test/encounter_player_client.py --host $BindHost --port $Port
