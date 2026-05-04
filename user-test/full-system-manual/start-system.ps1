param(
    [string]$BindHost = '127.0.0.1',
    [int]$Port = 8765,
    [switch]$NoAutoStart
)

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..')
Set-Location $repoRoot

$command = @('user-test/encounter_system_server.py', '--host', $BindHost, '--port', [string]$Port)
if ($NoAutoStart) {
    $command += '--no-auto-start'
}

python @command
