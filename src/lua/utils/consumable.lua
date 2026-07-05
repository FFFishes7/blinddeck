---Consumable target requirements (shared by pack endpoint and gamestate extraction)

local M = {}

--- Get target requirements for a consumable card from G.P_CENTERS configuration
--- @param card_key string Card key (e.g., "c_magician")
--- @return table|nil { min, max } | { requires_jokers_min, random_joker_effect } | nil
function M.get_consumable_target_requirements(card_key)
  if card_key == "c_aura" then
    return { min = 1, max = 1 }
  end

  if card_key == "c_ankh" or card_key == "c_hex" then
    return { requires_jokers_min = 1, random_joker_effect = true }
  end

  if card_key == "c_ectoplasm" then
    return { random_joker_effect = true }
  end

  if not G or not G.P_CENTERS then
    return nil
  end

  local center = G.P_CENTERS[card_key]
  if not center or not center.config then
    return nil
  end

  local config = center.config
  if config.max_highlighted then
    return {
      min = config.min_highlighted or 1,
      max = config.max_highlighted,
    }
  end

  return nil
end

return M
