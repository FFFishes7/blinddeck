-- Challenge catalog and lookup helpers shared by challenge endpoints/gamestate.

local challenges = {}

local function current_profile()
  if not G or not G.PROFILES or not G.SETTINGS then
    return nil
  end
  return G.PROFILES[G.SETTINGS.profile]
end

local function localize_name(id)
  local ok, name = pcall(localize, id, "challenge_names")
  if ok and type(name) == "string" and name ~= "" then
    return name
  end
  return id
end

local function json_safe(value, depth)
  depth = depth or 0
  if depth > 8 then
    return nil
  end
  local value_type = type(value)
  if value_type == "string" or value_type == "number" or value_type == "boolean" then
    return value
  end
  if value_type ~= "table" then
    return nil
  end

  local out = {}
  for key, child in pairs(value) do
    if type(key) == "string" or type(key) == "number" then
      local safe_child = json_safe(child, depth + 1)
      if safe_child ~= nil then
        out[key] = safe_child
      end
    end
  end
  return out
end

---@param challenge table
---@param index integer
---@return boolean
function challenges.is_unlocked(challenge, index)
  if SMODS and type(SMODS.challenge_is_unlocked) == "function" then
    local ok, unlocked = pcall(SMODS.challenge_is_unlocked, challenge, index)
    if ok then
      return unlocked == true
    end
  end
  local profile = current_profile()
  return profile ~= nil and type(profile.challenges_unlocked) == "number" and index <= profile.challenges_unlocked
end

---@param id string
---@return table|nil challenge
---@return integer|nil index
function challenges.find(id)
  if not G or type(G.CHALLENGES) ~= "table" then
    return nil, nil
  end
  for index, challenge in ipairs(G.CHALLENGES) do
    if challenge.id == id then
      return challenge, index
    end
  end
  return nil, nil
end

---@param challenge table
---@param index integer
---@return table
function challenges.serialize(challenge, index)
  local profile = current_profile()
  local completed = false
  if profile and profile.challenge_progress and profile.challenge_progress.completed and challenge.id then
    completed = profile.challenge_progress.completed[challenge.id] == true
  end

  return {
    id = challenge.id,
    index = index,
    name = localize_name(challenge.id),
    unlocked = challenges.is_unlocked(challenge, index),
    completed = completed,
    deck = json_safe(challenge.deck),
    jokers = json_safe(challenge.jokers) or {},
    consumables = json_safe(challenge.consumeables) or {},
    vouchers = json_safe(challenge.vouchers) or {},
    rules = json_safe(challenge.rules) or {},
    restrictions = json_safe(challenge.restrictions) or {},
  }
end

---@return table[]
function challenges.catalog()
  local catalog = {}
  if not G or type(G.CHALLENGES) ~= "table" then
    return catalog
  end
  for index, challenge in ipairs(G.CHALLENGES) do
    catalog[#catalog + 1] = challenges.serialize(challenge, index)
  end
  return catalog
end

---@param id string|nil
---@return table|nil
function challenges.active(id)
  if type(id) ~= "string" then
    return nil
  end
  local challenge, index = challenges.find(id)
  if not challenge then
    return { id = id, name = id }
  end
  local entry = challenges.serialize(challenge, index)
  return { id = entry.id, name = entry.name }
end

return challenges
