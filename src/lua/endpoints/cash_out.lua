-- src/lua/endpoints/cash_out.lua

-- ==========================================================================
-- CashOut Endpoint Params
-- ==========================================================================

---@class Request.Endpoint.CashOut.Params

-- ==========================================================================
-- CashOut Endpoint
-- ==========================================================================

---@type Endpoint
return {

  name = "cash_out",

  description = "Cash out and collect round rewards",

  schema = {},

  requires_state = { G.STATES.ROUND_EVAL },

  ---@param _ Request.Endpoint.CashOut.Params
  ---@param send_response fun(response: Response.Endpoint)
  execute = function(_, send_response)
    sendDebugMessage("Init cash_out()", "BB.ENDPOINTS")
    G.FUNCS.cash_out({ config = {} })

    local num_items = function(area)
      local count = 0
      if area and area.cards then
        for _, v in ipairs(area.cards) do
          if v.children.buy_button and v.children.buy_button.definition then
            count = count + 1
          end
        end
      end
      return count
    end

    -- Wait for SHOP state after state transition completes. Some skip tags
    -- (for example Holographic/Foil/Polychrome/Negative tags) mutate the next
    -- shop Joker shortly after the buy button appears, so require a few stable
    -- frames before snapshotting gamestate.
    local shop_ready_ticks = 0
    G.E_MANAGER:add_event(Event({
      trigger = "condition",
      blocking = false,
      func = function()
        local has_shop_items = false
        if G.STATE == G.STATES.SHOP and G.STATE_COMPLETE then
          has_shop_items = num_items(G.shop_booster) > 0
            or num_items(G.shop_jokers) > 0
            or num_items(G.shop_vouchers) > 0
        end

        local settled = has_shop_items and BB_GAMESTATE.tags_stack_stable()
        if settled then
          shop_ready_ticks = shop_ready_ticks + 1
        else
          shop_ready_ticks = 0
        end

        if shop_ready_ticks >= 10 then
          sendDebugMessage("Return cash_out() - reached settled SHOP state", "BB.ENDPOINTS")
          send_response(BB_GAMESTATE.get_gamestate())
          return true
        end

        return false
      end,
    }))
  end,
}
