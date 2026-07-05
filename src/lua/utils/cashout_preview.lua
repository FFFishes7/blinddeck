---Read-only round-end cashout preview mirroring G.FUNCS.evaluate_round dollar math.
---Does not mutate game state (no tag triggers, no ease_dollars, no eval rows).

---@class CashoutPreviewModule
---@field extract fun(): CashoutPreview?
local cashout_preview = {}

---@param card table
---@return string
local function card_label(card)
  if card.label and card.label ~= "" then
    return card.label
  end
  local center = card.config and card.config.center
  local key = (card.config and card.config.center_key) or (center and center.key)
  if key and localize then ---@diagnostic disable-line: undefined-global
    local ok, name = pcall(localize, { type = "name_text", set = "Joker", key = key }) ---@diagnostic disable-line: undefined-global
    if ok and type(name) == "string" and name ~= "" then
      return name
    end
  end
  if center and center.name then
    return center.name
  end
  return "Joker"
end

---@param tag table
---@return string
local function tag_label(tag)
  if tag.key and localize then ---@diagnostic disable-line: undefined-global
    local ok, name = pcall(localize, { type = "name_text", set = "Tag", key = tag.key }) ---@diagnostic disable-line: undefined-global
    if ok and type(name) == "string" and name ~= "" then
      return name
    end
  end
  if tag.name and tag.name ~= "" then
    return tag.name
  end
  return "Tag"
end

---Investment Tag and other eval tags must not call Tag:apply_to_run (side effects).
---@param tag table
---@return integer|nil dollars
local function is_boss_defeat()
  if G.GAME.blind and G.GAME.blind.boss then
    return true
  end
  if G.GAME.last_blind and G.GAME.last_blind.boss then
    return true
  end
  return false
end

local function is_investment_tag(tag)
  return tag.key == "tag_investment"
end

local function preview_tag_dollars(tag)
  if tag.config == nil or tag.config.type ~= "eval" then
    return nil
  end
  if is_investment_tag(tag) and is_boss_defeat() then
    return tag.config.dollars
  end
  if tag.triggered then
    return nil
  end
  return nil
end

---@param kind string
---@param label string
---@param dollars integer
---@param key string|nil
---@return CashoutLine
local function make_line(kind, label, dollars, key)
  local line = {
    kind = kind,
    label = label,
    dollars = dollars,
  }
  if key then
    line.key = key
  end
  return line
end

---@param lines CashoutLine[]
---@param line CashoutLine
local function push_line(lines, line)
  if line.dollars and line.dollars ~= 0 then
    lines[#lines + 1] = line
  end
end

---@return CashoutPreview|nil
function cashout_preview.extract()
  if not G or not G.GAME or not G.GAME.blind then
    return nil
  end

  local blind_chips = G.GAME.blind.chips or 0
  local chips = G.GAME.chips or 0
  if chips < blind_chips then
    return nil
  end

  local lines = {}
  local total = 0

  local blind_dollars = G.GAME.blind.dollars or 0
  push_line(lines, make_line("blind", "blind", blind_dollars))
  total = total + blind_dollars

  local hands_left = G.GAME.current_round and G.GAME.current_round.hands_left or 0
  if hands_left > 0 and not G.GAME.modifiers.no_extra_hand_money then
    local per_hand = G.GAME.modifiers.money_per_hand or 1
    local hand_dollars = hands_left * per_hand
    push_line(lines, make_line("hands", "hands", hand_dollars))
    total = total + hand_dollars
  end

  local discards_left = G.GAME.current_round and G.GAME.current_round.discards_left or 0
  if discards_left > 0 and G.GAME.modifiers.money_per_discard then
    local discard_dollars = discards_left * G.GAME.modifiers.money_per_discard
    push_line(lines, make_line("discards", "discards", discard_dollars))
    total = total + discard_dollars
  end

  for _, area in ipairs(SMODS.get_card_areas("jokers")) do
    for _, card in ipairs(area.cards) do
      local ret = card:calculate_dollar_bonus()
      if ret then
        local key = (card.config and card.config.center_key) or (card.config.center and card.config.center.key)
        push_line(lines, make_line("joker", card_label(card), ret, key))
        total = total + ret
      end
    end
  end

  for _, target in ipairs(SMODS.get_card_areas("individual", "calc_dollar_bonus")) do
    if type(target.object.calc_dollar_bonus) == "function" then
      local ret = target.object:calc_dollar_bonus()
      if ret then
        local name
        if target.set and target.key then
          if target.set == "Challenge" then
            name = localize(target.key, "challenge_names") ---@diagnostic disable-line: undefined-global
          elseif target.set == "Mod" and not (G.localization.descriptions.Mod or {})[target.key] then
            name = (SMODS.Mods[target.key] or {}).name
          else
            name = localize({ type = "name_text", set = target.set, key = target.key }) ---@diagnostic disable-line: undefined-global
          end
        end
        push_line(lines, make_line("joker", name or "Bonus", ret, target.key))
        total = total + ret
      end
    end
  end

  if G.GAME.tags then
    for _, tag in ipairs(G.GAME.tags) do
      local tag_dollars = preview_tag_dollars(tag)
      if tag_dollars then
        push_line(lines, make_line("tag", tag_label(tag), tag_dollars, tag.key))
        total = total + tag_dollars
      end
    end
  end

  local held = G.GAME.dollars or 0
  if held >= 5 and not G.GAME.modifiers.no_interest then
    local interest_amount = G.GAME.interest_amount or 1
    local interest_cap = G.GAME.interest_cap or 25
    local interest_dollars = interest_amount * math.min(math.floor(held / 5), interest_cap / 5)
    if interest_dollars > 0 then
      push_line(lines, make_line("interest", "interest", interest_dollars))
      total = total + interest_dollars
    end
  end

  local round_dollars = G.GAME.current_round and G.GAME.current_round.dollars
  if type(round_dollars) == "number" and round_dollars > 0 then
    total = round_dollars
  end

  return {
    lines = lines,
    total = total,
  }
end

return cashout_preview
