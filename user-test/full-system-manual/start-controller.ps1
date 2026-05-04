param(
    [Parameter(Mandatory = $true)]
    [string]$ControllerId,
    [string]$BindHost = '127.0.0.1',
    [int]$Port = 8765
)

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..')
Set-Location $repoRoot
python user-test/encounter_controller_client.py --controller-id $ControllerId --host $BindHost --port $Port
