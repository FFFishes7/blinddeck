-- src/lua/endpoints/sort.lua

-- ==========================================================================
-- Sort Endpoint Params
-- ==========================================================================

---@class Request.Endpoint.Sort.Params
---@field mode string? sort mode: rank, rank-desc, rank-asc, suit, suit-desc, suit-asc

-- ==========================================================================
-- Sort Endpoint
-- ==========================================================================

---@type Endpoint
return {

  name = "sort",

  description = "Sort hand cards using Balatro's native hand sort logic",

  schema = {
    mode = {
      type = "string",
      required = false,
      description = "Sort mode: rank/rank-desc/value, rank-asc, suit/suit-desc, or suit-asc",
    },
  },

  -- Balatro's Rank/Suit hand-sort buttons are only shown during hand selection;
  -- the overlay hides them while a booster pack is open (even Arcana/Spectral,
  -- where hand cards are visible for targeting). Keep the API in lockstep with
  -- the UI: sort is SELECTING_HAND-only.
  requires_state = { G.STATES.SELECTING_HAND },

  ---@param args Request.Endpoint.Sort.Params
  ---@param send_response fun(response: Response.Endpoint)
  execute = function(args, send_response)
    sendDebugMessage("Init sort()", "BB.ENDPOINTS")

    if not G.hand or not G.hand.cards or #G.hand.cards == 0 then
      send_response({
        message = "No hand available to sort",
        name = BB_ERROR_NAMES.NOT_ALLOWED,
      })
      return
    end

    local mode = args.mode or "rank"
    local method = nil

    if mode == "rank" or mode == "rank-desc" or mode == "value" or mode == "value-desc" then
      method = "desc"
    elseif mode == "rank-asc" or mode == "value-asc" then
      method = "asc"
    elseif mode == "suit" or mode == "suit-desc" then
      method = "suit desc"
    elseif mode == "suit-asc" then
      method = "suit asc"
    else
      send_response({
        message = "Sort mode must be one of: rank, rank-desc, rank-asc, suit, suit-desc, suit-asc",
        name = BB_ERROR_NAMES.BAD_REQUEST,
      })
      return
    end

    sendDebugMessage(string.format("Sorting hand with native method '%s'", method), "BB.ENDPOINTS")

    -- These are the same CardArea:sort methods used by Balatro's built-in
    -- "Rank" and "Suit" hand sort buttons.
    G.hand:sort(method)

    G.E_MANAGER:add_event(Event({
      trigger = "condition",
      blocking = false,
      func = function()
        local done = G.STATE == G.STATES.SELECTING_HAND and G.hand ~= nil
        if done then
          sendDebugMessage("Return sort()", "BB.ENDPOINTS")
          send_response(BB_GAMESTATE.get_gamestate())
        end
        return done
      end,
    }))
  end,
}
