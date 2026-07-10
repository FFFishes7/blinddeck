# Convenience wrapper for BlindDeck play helpers.
# Friendly action subcommands (no JSON quoting needed):
#   .\bot.ps1 glance                      # compact state summary
#   .\bot.ps1 estimate                    # top playable hands + score estimate
#   .\bot.ps1 start DECK STAKE [SEED]      # e.g. start RED WHITE (glance lists options)
#   .\bot.ps1 challenges [--json]            # native challenge IDs and availability
#   .\bot.ps1 challenge CHALLENGE_ID          # start an unlocked challenge
#   .\bot.ps1 select                      # select current blind
#   .\bot.ps1 play 0 1 2 3 4              # play cards at hand indices
#   .\bot.ps1 discard 0 1                 # discard cards
#   .\bot.ps1 buy card 0                  # buy shop card / voucher / pack
#   .\bot.ps1 pack 0                      # take pack card (or: pack skip)
#   .\bot.ps1 cash_out / endless / next_round / reroll / reroll_boss / menu / sort rank / sell joker 0
# Debug (estimate testing only; requires $env:BALATROBOT_ALLOW_CHEATS=1):
#   .\bot.ps1 add joker j_dusk | add card D_4 enhancement=MULT | set hands 1 chips 0 | debuff 0
# JSON / advanced:
#   .\bot.ps1 state                       # full JSON envelope
#   .\bot.ps1 query deck                  # detail query (deck, hands, blinds, …)
#   .\bot.ps1 know preflight              # phase-aware verified facts (see PLAY.md §2)
#   .\bot.ps1 exec '{\"command\":\"play\",\"params\":{\"cards\":[0,1,2,3,4]}}'
#   .\bot.ps1 help [--now] [--json]        # command catalog + descriptions; --now = valid in current state
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
    Write-Host '  .\bot.ps1 glance                      (compact state summary)'
    Write-Host '  .\bot.ps1 estimate                    (top playable hands + score estimate)'
    Write-Host '  .\bot.ps1 start DECK STAKE [SEED]     (e.g. start RED WHITE; glance lists decks/stakes)'
    Write-Host '  .\bot.ps1 play 0 1 2 3 4'
    Write-Host '  .\bot.ps1 buy card 0'
    Write-Host '  .\bot.ps1 challenges [--json] | challenge CHALLENGE_ID'
    Write-Host '  .\bot.ps1 state | query | know | exec | help [--now] [--json]'
    exit 2
}

$cmd = $BotArgs[0]
$rest = @()
if ($BotArgs.Count -gt 1) {
    $rest = $BotArgs[1..($BotArgs.Count - 1)]
}

switch ($cmd) {
    'state'  { & $Python (Join-Path $ToolRoot 'state.py') @rest; exit $LASTEXITCODE }
    'query'  { & $Python (Join-Path $ToolRoot 'query.py') @rest; exit $LASTEXITCODE }
    'challenges' { & $Python (Join-Path $ToolRoot 'challenges.py') @rest; exit $LASTEXITCODE }
    'know'   { & $Python (Join-Path $ToolRoot 'know.py') @rest; exit $LASTEXITCODE }
    'exec'   { & $Python (Join-Path $ToolRoot 'exec.py') @rest; exit $LASTEXITCODE }
    'help'   { & $Python (Join-Path $ToolRoot 'help.py') @rest; exit $LASTEXITCODE }
    'glance' { & $Python (Join-Path $ToolRoot 'view.py') @rest; exit $LASTEXITCODE }
    'estimate' { & $Python (Join-Path $ToolRoot 'estimate.py') @rest; exit $LASTEXITCODE }
    default  { & $Python (Join-Path $ToolRoot 'act.py') @BotArgs; exit $LASTEXITCODE }
}
