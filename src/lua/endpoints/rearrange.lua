-- src/lua/endpoints/rearrange.lua

-- ==========================================================================
-- Rearrange Endpoint Params
-- ==========================================================================

---@class Request.Endpoint.Rearrange.Params
---@field jokers integer[]? 0-based indices representing new order of jokers

-- ==========================================================================
-- Rearrange Endpoint
-- ==========================================================================

---@type Endpoint
return {

  name = "rearrange",

  description = "Rearrange jokers",

  schema = {
    jokers = {
      type = "array",
      required = false,
      items = "integer",
      description = "0-based indices representing new order of jokers",
    },
  },

  requires_state = { G.STATES.SELECTING_HAND, G.STATES.SHOP, G.STATES.SMODS_BOOSTER_OPENED },

  ---@param args Request.Endpoint.Rearrange.Params
  ---@param send_response fun(response: Response.Endpoint)
  execute = function(args, send_response)
    sendDebugMessage("Init rearrange()", "BB.ENDPOINTS")
    if not args.jokers then
      send_response({
        message = "Must provide jokers",
        name = BB_ERROR_NAMES.BAD_REQUEST,
      })
      return
    end

    if not G.jokers or not G.jokers.cards then
      send_response({
        message = "No jokers available to rearrange",
        name = BB_ERROR_NAMES.NOT_ALLOWED,
      })
      return
    end

    local source_array = G.jokers.cards
    local indices = args.jokers
    local type_name = "jokers"
    assert(type(indices) == "table", "indices must be a table")

    -- Log what we're rearranging
    local order_str = "[" .. table.concat(indices, ",") .. "]"
    sendDebugMessage(
      string.format("Rearranging %s (%d cards): %s", type_name, #source_array, order_str),
      "BB.ENDPOINTS"
    )

    -- Validate permutation: correct length, no duplicates, all indices present
    -- Check length matches
    if #indices ~= #source_array then
      send_response({
        message = "Must provide exactly " .. #source_array .. " indices for " .. type_name,
        name = BB_ERROR_NAMES.BAD_REQUEST,
      })
      return
    end

    -- Check for duplicates and range
    local seen = {}
    for _, idx in ipairs(indices) do
      -- Check range [0, N-1]
      if idx < 0 or idx >= #source_array then
        send_response({
          message = "Index out of range for " .. type_name .. ": " .. idx,
          name = BB_ERROR_NAMES.BAD_REQUEST,
        })
        return
      end

      -- Check for duplicates
      if seen[idx] then
        send_response({
          message = "Duplicate index in " .. type_name .. ": " .. idx,
          name = BB_ERROR_NAMES.BAD_REQUEST,
        })
        return
      end
      seen[idx] = true
    end

    -- Create new array from indices (convert 0-based to 1-based)
    local new_array = {}
    for _, old_index in ipairs(indices) do
      table.insert(new_array, source_array[old_index + 1])
    end

    -- Replace the array in game state
    G.jokers.cards = new_array

    -- Update order fields on each card
    for i, card in ipairs(new_array) do
      if card.ability then
        card.ability.order = i
      end
      if card.config and card.config.center then
        card.config.center.order = i
      end
    end

    -- Refresh CardArea positions so the visual order matches the API order.
    if G.jokers and G.jokers.align_cards then
      G.jokers:align_cards()
    end

    -- Wait for completion: state should remain stable after rearranging
    G.E_MANAGER:add_event(Event({
      trigger = "condition",
      blocking = false,
      func = function()
        -- Check that we're still in a valid state and arrays exist
        local done = false
        done = (
          G.STATE == G.STATES.SHOP
          or G.STATE == G.STATES.SELECTING_HAND
          or G.STATE == G.STATES.SMODS_BOOSTER_OPENED
        ) and G.jokers ~= nil

        if done then
          sendDebugMessage("Return rearrange()", "BB.ENDPOINTS")
          local state_data = BB_GAMESTATE.get_gamestate()
          send_response(state_data)
        end
        return done
      end,
    }))
  end,
}
