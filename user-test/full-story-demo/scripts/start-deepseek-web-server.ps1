param(
    [string]$HostName = "127.0.0.1",
    [int]$HttpPort = 8000,
    [int]$WsPort = 8767,
    [string]$EnvPath = "",
    [string]$PlayerEnvPath = "",
    [string]$CharacterLoadPath = "",
    [string]$MirrorBaseUrl = "",
    [string]$TrajectoryDir = "C:\tmp\dnd-web-deepseek-demo-20260514\trajectories",
    [int]$LlmPlayerMaxActionsPerPump = 4,
    [switch]$ServerSidePlayers,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..\..")
if (-not $EnvPath) {
    $EnvPath = Join-Path $RepoRoot ".env"
}
if (-not $PlayerEnvPath) {
    $PlayerEnvPath = Join-Path $RepoRoot "user-test\llm-players\deepseek-v4-flash-player.env"
}
if (-not $CharacterLoadPath) {
    $CharacterLoadPath = Join-Path $RepoRoot "user-test\saved-characters\lmop-balanced-test-party.json"
}
if (-not $MirrorBaseUrl) {
    $MirrorBaseUrl = "file:///" + ((Join-Path $RepoRoot "5etools-mirror-2.github.io") -replace "\\", "/") + "/"
}

foreach ($PathToCheck in @($EnvPath, $PlayerEnvPath, $CharacterLoadPath)) {
    if (-not (Test-Path -LiteralPath $PathToCheck)) {
        throw "Required file not found: $PathToCheck"
    }
}

New-Item -ItemType Directory -Force -Path $TrajectoryDir | Out-Null

$ArgsList = @(
    "user-test\web_story_demo_server.py",
    "--host", $HostName,
    "--http-port", "$HttpPort",
    "--ws-port", "$WsPort",
    "--env-path", $EnvPath,
    "--base-url", $MirrorBaseUrl,
    "--load-characters", $CharacterLoadPath,
    "--trajectory-dir", $TrajectoryDir
)

if ($ServerSidePlayers) {
    foreach ($ControllerId in @("player-1-controller", "player-2-controller", "player-3-controller", "player-4-controller")) {
        $ArgsList += @("--llm-player", "$ControllerId=$PlayerEnvPath")
    }
    $ArgsList += @("--llm-player-max-actions-per-pump", "$LlmPlayerMaxActionsPerPump")
}

Write-Host "Starting DeepSeek web demo server from $RepoRoot"
Write-Host "DM env: $EnvPath"
if ($ServerSidePlayers) {
    Write-Host "Server-side LLM players: enabled via $PlayerEnvPath"
} else {
    Write-Host "Server-side LLM players: disabled; use run-deepseek-party-connector.ps1 for four autonomous players."
}
Write-Host "Open: http://$HostName`:$HttpPort/?portal=dm&autoconnect=1"

if ($DryRun) {
    Write-Host "Dry run command:"
    Write-Host "python $($ArgsList -join ' ')"
    exit 0
}

Set-Location $RepoRoot
& python @ArgsList
