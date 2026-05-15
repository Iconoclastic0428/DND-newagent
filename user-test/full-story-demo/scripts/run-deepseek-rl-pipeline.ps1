param(
    [string]$OutputRoot = "runs\deepseek-rl-pipeline",
    [string]$RunId = "",
    [string]$EnvPath = "",
    [string]$PlayerEnvPath = "",
    [int]$MaxActions = 60,
    [int]$HttpPort = 8000,
    [int]$WsPort = 8767,
    [double]$PreConnectorDelaySeconds = 5,
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

$ArgsList = @(
    "user-test\run_deepseek_rl_pipeline.py",
    "--output-root", $OutputRoot,
    "--env-path", $EnvPath,
    "--player-env-path", $PlayerEnvPath,
    "--max-actions", "$MaxActions",
    "--http-port", "$HttpPort",
    "--ws-port", "$WsPort",
    "--pre-connector-delay-seconds", "$PreConnectorDelaySeconds"
)

if ($RunId) {
    $ArgsList += @("--run-id", $RunId)
}
if ($DryRun) {
    $ArgsList += "--dry-run"
}

Set-Location $RepoRoot
& python @ArgsList
