-- List native Balatro challenges and their profile-specific availability.

local CHALLENGES = assert(SMODS.load_file("src/lua/utils/challenges.lua"))()

---@type Endpoint
return {
  name = "challenges",
  description = "List native challenges with unlock, completion, and setup details",
  schema = {},
  requires_state = nil,
  execute = function(_, send_response)
    send_response({ challenges = CHALLENGES.catalog() })
  end,
}
