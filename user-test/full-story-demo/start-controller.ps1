param(
    [string]$BindHost = '127.0.0.1',
    [int]$Port = 8766,
    [string]$ControllerId
)

if (-not $ControllerId) {
    throw 'ControllerId is required. Example: player-1-controller or dm'
}

Set-Location (Resolve-Path (Join-Path $PSScriptRoot '..\..'))
python user-test/encounter_controller_client.py --controller-id $ControllerId --host $BindHost --port $Port
