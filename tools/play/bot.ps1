# Convenience wrapper for local BalatroBot helper scripts.
# Examples:
#   .\bot.ps1 state
#   .\bot.ps1 know preflight
#   .\bot.ps1 play 0 1 2 3 4
#   .\bot.ps1 pack skip
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$BotArgs
)

$ToolRoot = $PSScriptRoot
$Root = Resolve-Path (Join-Path $ToolRoot '..\..')
$Python = Join-Path $Root '.venv\Scripts\python.exe'

if (-not (Test-Path $Python)) {
    Write-Error "Missing virtualenv python: $Python"
    exit 2
}

if ($BotArgs.Count -eq 0) {
    Write-Host 'Usage:'
    Write-Host '  .\bot.ps1 help              list all commands (state-aware)'
    Write-Host '  .\bot.ps1 state'
    Write-Host '  .\bot.ps1 know preflight'
    Write-Host '  .\bot.ps1 play 0 1 2 3 4'
    Write-Host '  .\bot.ps1 discard 0 1'
    Write-Host '  .\bot.ps1 buy card 0'
    Write-Host '  .\bot.ps1 pack 0 [target...]'
    Write-Host '  .\bot.ps1 pack skip'
    exit 2
}

$cmd = $BotArgs[0]
$rest = @()
if ($BotArgs.Count -gt 1) {
    $rest = $BotArgs[1..($BotArgs.Count - 1)]
}

switch ($cmd) {
    'state' { & $Python (Join-Path $ToolRoot 'state.py') @rest; exit $LASTEXITCODE }
    'hand'  { & $Python (Join-Path $ToolRoot 'hand.py') @rest; exit $LASTEXITCODE }
    'know'  { & $Python (Join-Path $ToolRoot 'know.py') @rest; exit $LASTEXITCODE }
    'rpc'   { & $Python (Join-Path $ToolRoot 'rpc.py') @rest; exit $LASTEXITCODE }
    default { & $Python (Join-Path $ToolRoot 'act.py') $cmd @rest; exit $LASTEXITCODE }
}
