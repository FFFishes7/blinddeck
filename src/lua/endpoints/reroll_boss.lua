-- src/lua/endpoints/reroll_boss.lua

-- ==========================================================================
-- Reroll Boss Endpoint Params
-- ==========================================================================

---@class Request.Endpoint.RerollBoss.Params

-- ==========================================================================
-- Reroll Boss Endpoint (Director's Cut / Retcon)
-- ==========================================================================

---@type Endpoint
return {

  name = "reroll_boss",

  description = "Reroll the Boss blind for $10 (Director's Cut or Retcon voucher)",

  schema = {},

  requires_state = { G.STATES.BLIND_SELECT },

  ---@param _ Request.Endpoint.RerollBoss.Params
  ---@param send_response fun(response: Response.Endpoint)
  execute = function(_, send_response)
    sendDebugMessage("Init reroll_boss()", "BB.ENDPOINTS")

    if not G.GAME or G.GAME.blind_on_deck ~= "Boss" then
      send_response({
        message = "Boss reroll is only available when the Boss blind is on deck",
        name = BB_ERROR_NAMES.NOT_ALLOWED,
      })
      return
    end

    local boss_state = G.GAME.round_resets
      and G.GAME.round_resets.blind_states
      and G.GAME.round_resets.blind_states.Boss
    if boss_state == "Defeated" or boss_state == "Skipped" then
      send_response({
        message = "Boss blind is no longer selectable",
        name = BB_ERROR_NAMES.NOT_ALLOWED,
      })
      return
    end

    if not BB_GAMESTATE.boss_reroll_has_voucher() then
      send_response({
        message = "Boss reroll requires Director's Cut or Retcon voucher (or already used this ante)",
        name = BB_ERROR_NAMES.NOT_ALLOWED,
      })
      return
    end

    local cost = BB_GAMESTATE.BOSS_REROLL_COST
    local available_money = G.GAME.dollars - G.GAME.bankrupt_at
    if available_money < cost then
      send_response({
        message = "Not enough dollars to reroll boss. Available: " .. available_money .. ", Required: " .. cost,
        name = BB_ERROR_NAMES.NOT_ALLOWED,
      })
      return
    end

    if not G.blind_select_opts or not G.blind_select_opts.boss then
      send_response({
        message = "Boss blind selection UI is not ready",
        name = BB_ERROR_NAMES.NOT_ALLOWED,
      })
      return
    end

    BB_GAMESTATE.ensure_bosses_used()
    local old_boss = G.GAME.round_resets.blind_choices.Boss
    local money_before = G.GAME.dollars

    sendDebugMessage(
      string.format("Rerolling boss (was=%s, money=$%d, cost=$%d)", tostring(old_boss), money_before, cost),
      "BB.ENDPOINTS"
    )

    G.FUNCS.reroll_boss(nil)

    local frames = 0
    local max_frames = 300

    G.E_MANAGER:add_event(Event({
      trigger = "condition",
      blocking = false,
      func = function()
        frames = frames + 1
        local lock_clear = not G.CONTROLLER.locks or not G.CONTROLLER.locks.boss_reroll
        local boss_ready = G.blind_select_opts and G.blind_select_opts.boss
        local boss_changed = G.GAME.round_resets.blind_choices.Boss ~= old_boss
        if lock_clear and boss_ready and boss_changed then
          sendDebugMessage("Return reroll_boss()", "BB.ENDPOINTS")
          send_response(BB_GAMESTATE.get_gamestate())
          return true
        end
        if frames >= max_frames then
          send_response({
            message = "Boss reroll timed out waiting for UI",
            name = BB_ERROR_NAMES.INTERNAL_ERROR,
          })
          return true
        end
        return false
      end,
    }))
  end,
}
