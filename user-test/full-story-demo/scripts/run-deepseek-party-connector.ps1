param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [string]$EnvPath = "",
    [int]$MaxActions = 60,
    [double]$PollIntervalSeconds = 0.5,
    [double]$MonsterTurnDelaySeconds = 0.2,
    [double]$RequestTimeoutSeconds = 0,
    [string]$TranscriptPath = "C:\tmp\dnd-web-deepseek-demo-20260514\deepseek-party-transcript.md",
    [switch]$DisableAutoEndMonsterTurns,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..\..")
if (-not $EnvPath) {
    $EnvPath = Join-Path $RepoRoot ".env"
}
if (-not (Test-Path -LiteralPath $EnvPath)) {
    throw "Required env file not found: $EnvPath"
}

$TranscriptDir = Split-Path -Parent $TranscriptPath
if ($TranscriptDir) {
    New-Item -ItemType Directory -Force -Path $TranscriptDir | Out-Null
}

$ArgsList = @(
    "user-test\web_story_demo_party_connector.py",
    "--base-url", $BaseUrl,
    "--env-path", $EnvPath,
    "--max-actions", "$MaxActions",
    "--poll-interval-seconds", "$PollIntervalSeconds",
    "--monster-turn-delay-seconds", "$MonsterTurnDelaySeconds",
    "--request-timeout-seconds", "$RequestTimeoutSeconds",
    "--transcript-path", $TranscriptPath,
    "--verbose"
)

if ($DisableAutoEndMonsterTurns) {
    $ArgsList += "--disable-auto-end-monster-turns"
}

Write-Host "Starting DeepSeek four-player connector against $BaseUrl"
Write-Host "Player env: $EnvPath"
Write-Host "Transcript: $TranscriptPath"

if ($DryRun) {
    Write-Host "Dry run command:"
    Write-Host '$env:PYTHONPATH="."'
    Write-Host "python $($ArgsList -join ' ')"
    exit 0
}

Set-Location $RepoRoot
$env:PYTHONPATH = "."
& python @ArgsList
