-- src/lua/endpoints/start.lua

-- ==========================================================================
-- Start Endpoint Params
-- ==========================================================================

---@class Request.Endpoint.Start.Params
---@field deck Deck deck enum value (e.g., "RED", "BLUE", "YELLOW")
---@field stake Stake stake enum value (e.g., "WHITE", "RED", "GREEN", "BLACK", "BLUE", "PURPLE", "ORANGE", "GOLD")
---@field seed string? optional seed for the run

-- ==========================================================================
-- Start Endpoint Utils
-- ==========================================================================

local DECK_ENUM_TO_KEY = {
  RED = "b_red",
  BLUE = "b_blue",
  YELLOW = "b_yellow",
  GREEN = "b_green",
  BLACK = "b_black",
  MAGIC = "b_magic",
  NEBULA = "b_nebula",
  GHOST = "b_ghost",
  ABANDONED = "b_abandoned",
  CHECKERED = "b_checkered",
  ZODIAC = "b_zodiac",
  PAINTED = "b_painted",
  ANAGLYPH = "b_anaglyph",
  PLASMA = "b_plasma",
  ERRATIC = "b_erratic",
}

local STAKE_ENUM_TO_NUMBER = {
  WHITE = 1,
  RED = 2,
  GREEN = 3,
  BLACK = 4,
  BLUE = 5,
  PURPLE = 6,
  ORANGE = 7,
  GOLD = 8,
}

-- ==========================================================================
-- Start Endpoint
-- ==========================================================================

---@type Endpoint
return {

  name = "start",

  description = "Start a new game run with specified deck and stake",

  schema = {
    deck = {
      type = "string",
      required = true,
      description = "Deck enum value (e.g., 'RED', 'BLUE', 'YELLOW')",
    },
    stake = {
      type = "string",
      required = true,
      description = "Stake enum value (e.g., 'WHITE', 'RED', 'GREEN', 'BLACK', 'BLUE', 'PURPLE', 'ORANGE', 'GOLD')",
    },
    seed = {
      type = "string",
      required = false,
      description = "Optional seed for the run",
    },
  },

  requires_state = { G.STATES.MENU },

  ---@param args Request.Endpoint.Start.Params
  ---@param send_response fun(response: Response.Endpoint)
  execute = function(args, send_response)
    sendDebugMessage("Init start()", "BB.ENDPOINTS")

    -- Validate and map stake enum
    local stake_number = STAKE_ENUM_TO_NUMBER[args.stake]
    if not stake_number then
      sendDebugMessage("start() called with invalid stake enum: " .. tostring(args.stake), "BB.ENDPOINTS")
      send_response({
        message = "Invalid stake enum. Must be one of: WHITE, RED, GREEN, BLACK, BLUE, PURPLE, ORANGE, GOLD. Got: "
          .. tostring(args.stake),
        name = BB_ERROR_NAMES.BAD_REQUEST,
      })
      return
    end

    -- Validate and map deck enum
    local deck_key = DECK_ENUM_TO_KEY[args.deck]
    if not deck_key then
      sendDebugMessage("start() called with invalid deck enum: " .. tostring(args.deck), "BB.ENDPOINTS")
      send_response({
        message = "Invalid deck enum. Must be one of: RED, BLUE, YELLOW, GREEN, BLACK, MAGIC, NEBULA, GHOST, ABANDONED, CHECKERED, ZODIAC, PAINTED, ANAGLYPH, PLASMA, ERRATIC. Got: "
          .. tostring(args.deck),
        name = BB_ERROR_NAMES.BAD_REQUEST,
      })
      return
    end

    -- Reset the game (setup_run and exit_overlay_menu)
    G.FUNCS.setup_run({ config = {} })
    G.FUNCS.exit_overlay_menu()

    -- Find and set the deck by center key (locale-independent)
    local deck_found = false
    if G.P_CENTER_POOLS and G.P_CENTER_POOLS.Back then
      for _, deck_data in pairs(G.P_CENTER_POOLS.Back) do
        if deck_data.key == deck_key then
          sendDebugMessage("Setting deck to: " .. deck_key .. " (from enum: " .. args.deck .. ")", "BB.ENDPOINTS")
          G.GAME.selected_back:change_to(deck_data)
          if G.GAME.viewed_back then
            G.GAME.viewed_back:change_to(deck_data)
          end
          deck_found = true
          break
        end
      end
    end

    if not deck_found then
      sendDebugMessage("start() deck not found in game data: " .. deck_key, "BB.ENDPOINTS")
      send_response({
        message = "Deck not found in game data: " .. deck_key,
        name = BB_ERROR_NAMES.INTERNAL_ERROR,
      })
      return
    end

    -- Start the run with stake number and optional seed
    local run_params = { stake = stake_number }
    if args.seed then
      run_params.seed = args.seed
    end

    sendDebugMessage(
      "Starting run with stake="
        .. tostring(stake_number)
        .. " ("
        .. args.stake
        .. "), seed="
        .. tostring(args.seed or "none"),
      "BB.ENDPOINTS"
    )
    G.FUNCS.start_run(nil, run_params)

    -- Wait for run to start using Balatro's Event Manager
    G.E_MANAGER:add_event(Event({
      no_delete = true,
      trigger = "condition",
      blocking = false,
      func = function()
        local done = (
          G.GAME.blind_on_deck ~= nil
          and G.blind_select_opts ~= nil
          and G.blind_select_opts["small"]:get_UIE_by_ID("tag_Small") ~= nil
        )
        if done then
          sendDebugMessage("Return start()", "BB.ENDPOINTS")
          local state_data = BB_GAMESTATE.get_gamestate()
          send_response(state_data)
        end

        return done
      end,
    }))
  end,
}
