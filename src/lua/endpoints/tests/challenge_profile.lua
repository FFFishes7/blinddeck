-- Debug-only profile override for deterministic native challenge integration tests.

local saved = nil

---@type Endpoint
return {
  name = "test_challenge_profile",
  description = "Temporarily control current-profile challenge unlocks for tests",
  schema = {
    mode = { type = "string", required = true },
  },
  requires_state = { G.STATES.MENU },
  execute = function(args, send_response)
    local profile = G.PROFILES[G.SETTINGS.profile]
    if not saved then
      saved = {
        challenges_unlocked = profile.challenges_unlocked,
        all_unlocked = profile.all_unlocked,
      }
    end
    if args.mode == "unlock_all" then
      profile.challenges_unlocked = #G.CHALLENGES
      profile.all_unlocked = true
    elseif args.mode == "lock_all" then
      profile.challenges_unlocked = 0
      profile.all_unlocked = false
    elseif args.mode == "restore" then
      profile.challenges_unlocked = saved.challenges_unlocked
      profile.all_unlocked = saved.all_unlocked
      saved = nil
    else
      send_response({ message = "mode must be unlock_all, lock_all, or restore", name = BB_ERROR_NAMES.BAD_REQUEST })
      return
    end
    send_response({ success = true })
  end,
}
