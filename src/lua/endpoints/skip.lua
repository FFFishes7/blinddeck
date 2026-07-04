-- src/lua/endpoints/skip.lua

-- ==========================================================================
-- Skip Endpoint Params
-- ==========================================================================

---@class Request.Endpoint.Skip.Params

-- ==========================================================================
-- Skip Endpoint
-- ==========================================================================

---@type Endpoint
return {

  name = "skip",

  description = "Skip the current blind (Small or Big only, not Boss)",

  schema = {},

  requires_state = { G.STATES.BLIND_SELECT },

  ---@param _ Request.Endpoint.Skip.Params
  ---@param send_response fun(response: Response.Endpoint)
  execute = function(_, send_response)
    sendDebugMessage("Init skip()", "BB.ENDPOINTS")
    BB_GAMESTATE.ensure_bosses_used()

    -- Get the current blind on deck (similar to select endpoint)
    local current_blind = G.GAME.blind_on_deck
    assert(current_blind ~= nil, "skip() called with no blind on deck")
    local current_blind_key = string.lower(current_blind)
    local blind = BB_GAMESTATE.get_blinds_info()[current_blind_key]
    assert(blind ~= nil, "skip() blind not found: " .. current_blind)

    if blind.type == "BOSS" then
      sendDebugMessage("skip() cannot skip Boss blind: " .. current_blind, "BB.ENDPOINTS")
      send_response({
        message = "Cannot skip Boss blind",
        name = BB_ERROR_NAMES.NOT_ALLOWED,
      })
      return
    end

    -- Get the skip button from the tag element
    local blind_pane = G.blind_select_opts[current_blind_key]
    assert(blind_pane ~= nil, "skip() blind pane not found: " .. current_blind)
    local tag_element = blind_pane:get_UIE_by_ID("tag_" .. current_blind)
    assert(tag_element ~= nil, "skip() tag element not found: " .. current_blind)
    local skip_button = tag_element.children[2]
    assert(skip_button ~= nil, "skip() skip button not found: " .. current_blind)

    -- Execute blind skip
    G.FUNCS.skip_blind(skip_button)

    -- Wait for the skip to complete and for tag side effects to settle. Some
    -- tags update money or open a booster immediately after the blind status
    -- flips to SKIPPED, so returning on the first skipped frame can expose stale
    -- money/state to bot.ps1 glance.
    local settled_once = false
    G.E_MANAGER:add_event(Event({
      trigger = "condition",
      blocking = true,
      func = function()
        local blinds = BB_GAMESTATE.get_blinds_info()
        local skipped = (
          G.GAME.blind_on_deck ~= nil
          and G.blind_select_opts ~= nil
          and blinds[current_blind_key].status == "SKIPPED"
        )
        local stable_state = G.STATE == G.STATES.BLIND_SELECT or G.STATE == G.STATES.SMODS_BOOSTER_OPENED
        local done = skipped and stable_state and settled_once
        if done then
          sendDebugMessage("Return skip()", "BB.ENDPOINTS")
          local state_data = BB_GAMESTATE.get_gamestate()
          send_response(state_data)
        end
        if skipped and stable_state then
          settled_once = true
        end

        return done
      end,
    }))
  end,
}
