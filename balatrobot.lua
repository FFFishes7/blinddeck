-- Load required files
assert(SMODS.load_file("src/lua/settings.lua"))() -- define BB_SETTINGS

-- Configure Balatro with appropriate settings from environment variables
BB_SETTINGS.setup()

-- Endpoints for the BlindDeck API
BB_ENDPOINTS = {
  -- Health endpoint
  "src/lua/endpoints/health.lua",
  -- Gamestate endpoints
  "src/lua/endpoints/gamestate.lua",
  -- Save/load endpoints
  "src/lua/endpoints/save.lua",
  "src/lua/endpoints/load.lua",
  -- Screenshot endpoint
  "src/lua/endpoints/screenshot.lua",
  -- Game control endpoints
  "src/lua/endpoints/set.lua",
  "src/lua/endpoints/add.lua",
  "src/lua/endpoints/debuff.lua",
  -- Gameplay endpoints
  "src/lua/endpoints/menu.lua",
  "src/lua/endpoints/start.lua",
  "src/lua/endpoints/challenges.lua",
  "src/lua/endpoints/challenge.lua",
  -- Blind selection endpoints
  "src/lua/endpoints/skip.lua",
  "src/lua/endpoints/select.lua",
  "src/lua/endpoints/reroll_boss.lua",
  -- Play/discard endpoints
  "src/lua/endpoints/play.lua",
  "src/lua/endpoints/discard.lua",
  -- Cash out / endless endpoints
  "src/lua/endpoints/cash_out.lua",
  "src/lua/endpoints/endless.lua",
  -- Shop endpoints
  "src/lua/endpoints/next_round.lua",
  "src/lua/endpoints/reroll.lua",
  "src/lua/endpoints/buy.lua",
  "src/lua/endpoints/pack.lua",
  -- Rearrange endpoint
  "src/lua/endpoints/rearrange.lua",
  "src/lua/endpoints/sort.lua",
  -- Sell endpoint
  "src/lua/endpoints/sell.lua",
  -- Use consumable endpoint
  "src/lua/endpoints/use.lua",
  -- If debug mode is enabled, debugger.lua will load test endpoints
}

-- Enable debug mode
if BB_SETTINGS.debug then
  assert(SMODS.load_file("src/lua/utils/debugger.lua"))() -- define BB_DEBUG
  BB_DEBUG.setup()
end

-- Load core modules
assert(SMODS.load_file("src/lua/core/server.lua"))() -- define BB_SERVER
assert(SMODS.load_file("src/lua/core/dispatcher.lua"))() -- define BB_DISPATCHER

-- Load gamestate and errors utilities
BB_GAMESTATE = assert(SMODS.load_file("src/lua/utils/gamestate.lua"))()
assert(SMODS.load_file("src/lua/utils/errors.lua"))()

-- Initialize Server
local server_success = BB_SERVER.init()
if not server_success then
  return
end

local dispatcher_ok = BB_DISPATCHER.init(BB_SERVER, BB_ENDPOINTS)
if not dispatcher_ok then
  return
end

-- Hook into love.update to run server update loop and detect GAME_OVER
local get_new_boss_hooked = false

local function hook_get_new_boss()
  if get_new_boss_hooked or type(get_new_boss) ~= "function" then
    return
  end
  local original_get_new_boss = get_new_boss
  get_new_boss = function(...)
    BB_GAMESTATE.ensure_bosses_used()
    return original_get_new_boss(...)
  end
  get_new_boss_hooked = true
  sendDebugMessage("Hooked get_new_boss() for bosses_used save compatibility", "BB.BALATROBOT")
end

local love_update = love.update
love.update = function(dt) ---@diagnostic disable-line: duplicate-set-field
  hook_get_new_boss()
  -- Check for GAME_OVER / victory overlay before game logic runs (paused-safe)
  BB_GAMESTATE.check_game_over()
  BB_GAMESTATE.check_victory_overlay()
  love_update(dt)
  BB_SERVER.update(BB_DISPATCHER)
end

sendInfoMessage("BlindDeck loaded - version " .. SMODS.current_mod.version, "BB.BALATROBOT")
