# Example GUI launcher for BlindDeck (Windows).
# Copy to serve.ps1, set $BalatroDir (or BALATROBOT_GAME_DIR), keep serve.ps1 untracked.
# Sets BALATROBOT_BALATRO_PATH / LOVE_PATH / LOVELY_PATH for this session, then runs balatrobot serve.
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ServeArgs
)

$ToolRoot = $PSScriptRoot
$RepoRoot = Resolve-Path (Join-Path $ToolRoot '..\..')

$BalatroDir = $env:BALATROBOT_GAME_DIR
if (-not $BalatroDir) {
    $BalatroDir = 'C:\Program Files (x86)\Steam\steamapps\common\Balatro'
}

$env:BALATROBOT_BALATRO_PATH = $BalatroDir
$env:BALATROBOT_LOVE_PATH = Join-Path $BalatroDir 'Balatro.exe'
$env:BALATROBOT_LOVELY_PATH = Join-Path $BalatroDir 'version.dll'

Set-Location $RepoRoot
& (Join-Path $RepoRoot '.venv\Scripts\balatrobot.exe') serve @ServeArgs
