-- Start one unlocked native Balatro challenge from the title menu.

local CHALLENGES = assert(SMODS.load_file("src/lua/utils/challenges.lua"))()

---@type Endpoint
return {
  name = "challenge",
  description = "Start an unlocked native challenge by its stable challenge ID",
  schema = {
    id = {
      type = "string",
      required = true,
      description = "Native challenge ID returned by the challenges endpoint",
    },
  },
  requires_state = { G.STATES.MENU },
  execute = function(args, send_response)
    local challenge, index = CHALLENGES.find(args.id)
    if not challenge then
      send_response({
        message = "Unknown challenge ID: " .. args.id,
        name = BB_ERROR_NAMES.BAD_REQUEST,
      })
      return
    end
    if not CHALLENGES.is_unlocked(challenge, index) then
      send_response({
        message = "Challenge is locked: " .. args.id,
        name = BB_ERROR_NAMES.NOT_ALLOWED,
      })
      return
    end

    G.FUNCS.setup_run({ config = {} })
    G.FUNCS.exit_overlay_menu()
    G.FUNCS.start_run(nil, { stake = 1, challenge = challenge })

    G.E_MANAGER:add_event(Event({
      no_delete = true,
      trigger = "condition",
      blocking = false,
      func = function()
        local blind_ready = G.blind_select_opts
          and G.blind_select_opts.small
          and G.blind_select_opts.small:get_UIE_by_ID("tag_Small") ~= nil
        local done = G.GAME
          and G.GAME.challenge == args.id
          and G.STATE == G.STATES.BLIND_SELECT
          and G.STATE_COMPLETE == true
          and blind_ready
        if done then
          send_response(BB_GAMESTATE.get_gamestate())
        end
        return done
      end,
    }))
  end,
}
