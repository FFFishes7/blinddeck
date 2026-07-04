---Simplified game state extraction utilities
---This module provides a clean, simplified interface for extracting game state
---according to the new gamestate specification

---@class GameStateModule
---@field on_game_over (fun(state: GameState))?
---@field check_game_over fun()
---@field get_blinds_info fun(): table<string, Blind>
---@field get_gamestate fun(): GameState
---@field ensure_bosses_used fun()
local gamestate = {}

local consumable = assert(SMODS.load_file("src/lua/utils/consumable.lua"))()

-- ==========================================================================
-- State Name Mapping
-- ==========================================================================

---Converts numeric state ID to string state name
---@param state_num number The numeric state value from G.STATE
---@return string state_name The string name of the state (e.g., "SELECTING_HAND")
local function get_state_name(state_num)
  if not G or not G.STATES then
    return "UNKNOWN"
  end

  for name, value in pairs(G.STATES) do
    if value == state_num then
      return name
    end
  end

  return "UNKNOWN"
end

-- ==========================================================================
-- Deck Name Mapping
-- ==========================================================================

local DECK_KEY_TO_NAME = {
  b_red = "RED",
  b_blue = "BLUE",
  b_yellow = "YELLOW",
  b_green = "GREEN",
  b_black = "BLACK",
  b_magic = "MAGIC",
  b_nebula = "NEBULA",
  b_ghost = "GHOST",
  b_abandoned = "ABANDONED",
  b_checkered = "CHECKERED",
  b_zodiac = "ZODIAC",
  b_painted = "PAINTED",
  b_anaglyph = "ANAGLYPH",
  b_plasma = "PLASMA",
  b_erratic = "ERRATIC",
}

---Converts deck key to string deck name
---@param deck_key string The key from G.P_CENTERS (e.g., "b_red")
---@return string? deck_name The string name of the deck (e.g., "RED"), or nil if not found
local function get_deck_name(deck_key)
  return DECK_KEY_TO_NAME[deck_key]
end

-- ==========================================================================
-- Stake Name Mapping
-- ==========================================================================

local STAKE_LEVEL_TO_NAME = {
  [1] = "WHITE",
  [2] = "RED",
  [3] = "GREEN",
  [4] = "BLACK",
  [5] = "BLUE",
  [6] = "PURPLE",
  [7] = "ORANGE",
  [8] = "GOLD",
}

---Converts numeric stake level to string stake name
---@param stake_num number The numeric stake value from G.GAME.stake (1-8)
---@return string? stake_name The string name of the stake (e.g., "WHITE"), or nil if not found
local function get_stake_name(stake_num)
  return STAKE_LEVEL_TO_NAME[stake_num]
end

-- ==========================================================================
-- Card UI Description
-- ==========================================================================

---Recursively removes DynaText and other Moveable objects from UI node tree
---to prevent memory leaks from objects registering in G.I.MOVEABLE
---@param nodes table|nil UI node tree (array or single node)
local function cleanup_ui_nodes(nodes)
  if type(nodes) ~= "table" then
    return
  end

  -- Handle single node with object (DynaText, etc.)
  local config = nodes.config
  if config and config.object then
    local obj = config.object
    if obj and obj.remove then
      obj:remove() -- Removes from G.I.MOVEABLE and other tracking arrays
    end
    config.object = nil
  end

  -- Recurse into children/nodes
  if nodes.nodes then
    cleanup_ui_nodes(nodes.nodes)
  end
  if nodes.children then
    cleanup_ui_nodes(nodes.children)
  end

  -- Traverse arrays and maps to avoid missing nodes with holes
  for key, node in pairs(nodes) do
    if key ~= "nodes" and key ~= "children" and key ~= "config" and type(node) == "table" then
      cleanup_ui_nodes(node)
    end
  end
end

---Gets the description text for a card by reading from its UI elements
---Uses generate_UIBox_ability_table() directly to avoid hover() side effects
---(sound, animation, h_popup creation)
---@param card table The card object
---@return string description The description text from UI
local UI_EFFECT_FALLBACK = {
  j_misprint = "+0 to +23 Mult (random each hand)",
  j_bloodstone = "1 in 2 chance for X2 Mult (random)",
  j_8_ball = "1 in 4 chance to spawn a Tarot (random)",
}

local function is_sparse_effect(text)
  if not text or text:match("^%s*$") then
    return true
  end
  if not text:match("[%a]") then
    return true
  end
  if text:match("^[%s+%-–—xX%d%.]+$") then
    return true
  end
  return false
end

local function ui_effect_fallback(card)
  local key = card.config and card.config.center_key
  if key and UI_EFFECT_FALLBACK[key] then
    return UI_EFFECT_FALLBACK[key]
  end
  return nil
end

local function append_ui_text(parts, config)
  if not config then
    return
  end
  if config.text then
    parts[#parts + 1] = config.text
  end
  if config.object and config.object.strings then
    for _, s in ipairs(config.object.strings) do
      if type(s) == "string" and s ~= "" then
        parts[#parts + 1] = s
      end
    end
  end
end

local function collect_ui_texts(nodes, out)
  if type(nodes) ~= "table" then
    return
  end
  if nodes.config then
    append_ui_text(out, nodes.config)
  end
  if nodes.nodes then
    for _, node in ipairs(nodes.nodes) do
      collect_ui_texts(node, out)
    end
  end
  for _, node in ipairs(nodes) do
    if type(node) == "table" then
      collect_ui_texts(node, out)
    end
  end
end

local function get_card_ui_description(card)
  -- Generate UI structure directly (no hover side effects)
  local ui_table = card:generate_UIBox_ability_table()
  if not ui_table then
    return ui_effect_fallback(card) or ""
  end

  -- Extract all text nodes from the UI tree (recursive — catches highlighted values)
  local texts = {}

  if ui_table.main then
    for _, line in ipairs(ui_table.main) do
      local line_texts = {}
      collect_ui_texts(line, line_texts)
      if #line_texts > 0 then
        texts[#texts + 1] = table.concat(line_texts, "")
      end
    end
  end

  if ui_table.info then
    for _, line in ipairs(ui_table.info) do
      local line_texts = {}
      collect_ui_texts(line, line_texts)
      if #line_texts > 0 then
        texts[#texts + 1] = table.concat(line_texts, "")
      end
    end
  end

  -- Cleanup DynaText and other objects to prevent memory leak
  -- These objects register in G.I.MOVEABLE when created
  cleanup_ui_nodes(ui_table.main)
  cleanup_ui_nodes(ui_table.info)
  if ui_table.name and type(ui_table.name) == "table" then
    cleanup_ui_nodes(ui_table.name)
  end

  local description = table.concat(texts, " ")
  if is_sparse_effect(description) then
    return ui_effect_fallback(card) or description
  end
  return description
end

-- ==========================================================================
-- Card Value Converters
-- ==========================================================================

---Converts Balatro suit name to enum format
---@param suit_name string The suit name from card.config.card.suit
---@return Card.Value.Suit? suit_enum The single-letter suit enum ("H", "D", "C", "S")
local function convert_suit_to_enum(suit_name)
  if suit_name == "Hearts" then
    return "H"
  elseif suit_name == "Diamonds" then
    return "D"
  elseif suit_name == "Clubs" then
    return "C"
  elseif suit_name == "Spades" then
    return "S"
  end
  return nil
end

---Converts Balatro rank value to enum format
---@param rank_value string The rank value from card.config.card.value
---@return Card.Value.Rank? rank_enum The single-character rank enum
local function convert_rank_to_enum(rank_value)
  -- Numbers 2-9 stay the same
  if
    rank_value == "2"
    or rank_value == "3"
    or rank_value == "4"
    or rank_value == "5"
    or rank_value == "6"
    or rank_value == "7"
    or rank_value == "8"
    or rank_value == "9"
  then
    return rank_value
  elseif rank_value == "10" then
    return "T"
  elseif rank_value == "Jack" then
    return "J"
  elseif rank_value == "Queen" then
    return "Q"
  elseif rank_value == "King" then
    return "K"
  elseif rank_value == "Ace" then
    return "A"
  end
  return nil
end

-- ==========================================================================
-- Card Component Extractors
-- ==========================================================================

---Extracts modifier information from a card
---@param card table The card object
---@return Card.Modifier modifier The Card.Modifier object
local function extract_card_modifier(card)
  local modifier = {}

  -- Seal (direct property)
  if card.seal then
    modifier.seal = string.upper(card.seal)
  end

  -- Edition (table with type/key)
  if card.edition and card.edition.type then
    modifier.edition = string.upper(card.edition.type)
  end

  -- Enhancement (from ability.name for enhanced cards)
  if card.ability and card.ability.effect and card.ability.effect ~= "Base" then
    modifier.enhancement = string.upper(card.ability.effect:gsub(" Card", ""))
  end

  -- Eternal (boolean from ability)
  if card.ability and card.ability.eternal then
    modifier.eternal = true
  end

  -- Perishable (from perish_tally - only include if > 0)
  if card.ability and card.ability.perish_tally and card.ability.perish_tally > 0 then
    modifier.perishable = card.ability.perish_tally
  end

  -- Rental (boolean from ability)
  if card.ability and card.ability.rental then
    modifier.rental = true
  end

  return modifier
end

---Numeric scoring snapshot for jokers (locale-independent; mirrors card.lua joker_main inputs).
---@param card table
---@return Card.Value.Stats?
local function extract_joker_stats(card)
  if not card or not card.ability or card.ability.set ~= "Joker" then
    return nil
  end

  local a = card.ability
  local name = a.name
  local stats = {}

  if type(a.mult) == "number" and a.mult ~= 0 then
    stats.mult = a.mult
  end
  if type(a.x_mult) == "number" and a.x_mult > 1 then
    stats.x_mult = a.x_mult
  end

  if type(a.extra) == "table" then
    if type(a.extra.chips) == "number" and a.extra.chips ~= 0 then
      stats.chips = a.extra.chips
    end
    if type(a.extra.mult) == "number" and a.extra.mult ~= 0 and not stats.mult then
      stats.mult = a.extra.mult
    end
    if type(a.extra.Xmult) == "number" and a.extra.Xmult > 1 and not stats.x_mult then
      stats.x_mult = a.extra.Xmult
    end
  end

  if name == "Fortune Teller" then
    local tarot = 0
    if G and G.GAME and G.GAME.consumeable_usage_total then
      tarot = G.GAME.consumeable_usage_total.tarot or 0
    end
    stats.mult = tarot
  elseif name == "Steel Joker" then
    local tally = a.steel_tally or 0
    if tally > 0 and type(a.extra) == "number" then
      stats.steel_tally = tally
      stats.x_mult = 1 + a.extra * tally
    end
  elseif name == "Stone Joker" then
    local tally = a.stone_tally or 0
    if tally > 0 and type(a.extra) == "number" then
      stats.stone_tally = tally
      stats.chips = a.extra * tally
    end
  elseif name == "Seltzer" then
    if type(a.extra) == "number" and a.extra > 0 then
      stats.seltzer_remaining = a.extra
    end
  elseif name == "Driver's License" then
    local tally = a.driver_tally or 0
    if tally > 0 then
      stats.driver_tally = tally
    end
    if tally >= 16 and type(a.extra) == "number" then
      stats.x_mult = a.extra
    end
  elseif name == "Obelisk" then
    if type(a.extra) == "number" then
      stats.obelisk_step = a.extra
    end
    if type(a.x_mult) == "number" and a.x_mult > 1 then
      stats.x_mult = a.x_mult
    end
  elseif name == "Ride the Bus" then
    if type(a.extra) == "number" then
      stats.ride_the_bus_step = a.extra
    end
    if type(a.mult) == "number" and a.mult ~= 0 then
      stats.mult = a.mult
    end
  elseif name == "Green Joker" and type(a.extra) == "table" then
    if type(a.mult) == "number" then
      stats.mult = a.mult
    end
    if type(a.extra.hand_add) == "number" then
      stats.green_hand_add = a.extra.hand_add
    end
  elseif name == "Ice Cream" and type(a.extra) == "table" and type(a.extra.chips) == "number" then
    stats.chips = a.extra.chips
  elseif name == "Castle" and type(a.extra) == "table" and type(a.extra.chips) == "number" and a.extra.chips > 0 then
    stats.chips = a.extra.chips
  elseif name == "Popcorn" and type(a.mult) == "number" then
    stats.mult = a.mult
  elseif name == "Ceremonial Dagger" and type(a.mult) == "number" and a.mult > 0 then
    stats.mult = a.mult
  elseif name == "Red Card" and type(a.mult) == "number" and a.mult > 0 then
    stats.mult = a.mult
  elseif name == "Flash Card" and type(a.mult) == "number" then
    stats.mult = a.mult
  elseif name == "Spare Trousers" and type(a.mult) == "number" then
    stats.mult = a.mult
  elseif name == "Swashbuckler" then
    local sell_cost = 0
    if G and G.jokers and G.jokers.cards then
      for i = 1, #G.jokers.cards do
        local other = G.jokers.cards[i]
        if other ~= card and other.area and other.area == G.jokers then
          sell_cost = sell_cost + (other.sell_cost or 0)
        end
      end
    end
    stats.mult = sell_cost
  elseif
    name == "Madness"
    or name == "Vampire"
    or name == "Constellation"
    or name == "Campfire"
    or name == "Glass Joker"
  then
    if type(a.x_mult) == "number" and a.x_mult > 1 then
      stats.x_mult = a.x_mult
    end
  elseif name == "Caino" and type(a.caino_xmult) == "number" and a.caino_xmult > 1 then
    stats.caino_xmult = a.caino_xmult
  elseif name == "Yorick" and type(a.x_mult) == "number" and a.x_mult > 1 then
    stats.x_mult = a.x_mult
  elseif name == "Loyalty Card" and type(a.extra) == "table" then
    local every = a.extra.every
    if type(every) == "number" then
      stats.loyalty_every = every
      if G and G.GAME then
        local at_create = a.hands_played_at_create or 0
        stats.loyalty_remaining = (every - 1 - (G.GAME.hands_played - at_create)) % (every + 1)
      end
      if type(a.extra.Xmult) == "number" then
        stats.loyalty_x_mult = a.extra.Xmult
      end
    end
  end

  if next(stats) == nil then
    return nil
  end
  return stats
end

---Run-level counters useful for deterministic scoring (Erosion, Throwback, …).
---@return RunCounters?
local function extract_run_counters()
  if not G or not G.GAME then
    return nil
  end

  local deck_size = 0
  if G.playing_cards then
    for _ in pairs(G.playing_cards) do
      deck_size = deck_size + 1
    end
  end

  local tarot_used = 0
  if G.GAME.consumeable_usage_total and G.GAME.consumeable_usage_total.tarot then
    tarot_used = G.GAME.consumeable_usage_total.tarot
  end

  return {
    skips = G.GAME.skips or 0,
    deck_size = deck_size,
    starting_deck_size = G.GAME.starting_deck_size or 52,
    tarot_used = tarot_used,
  }
end

---Extracts value information from a card
---@param card table The card object
---@return Card.Value value The Card.Value object
local function extract_card_value(card)
  local value = {}

  -- Suit and rank (for playing cards)
  if card.config and card.config.card then
    if card.config.card.suit then
      value.suit = convert_suit_to_enum(card.config.card.suit)
    end
    if card.config.card.value then
      value.rank = convert_rank_to_enum(card.config.card.value)
    end
  end

  -- Effect description (for all cards)
  value.effect = get_card_ui_description(card)

  -- The Fool previews the last used Tarot/Planet it will copy. Balatro stores
  -- this in G.GAME.last_tarot_planet and the in-game UI shows it on the card.
  if card.config and card.config.center_key == "c_fool" then
    local copy_key = G.GAME and G.GAME.last_tarot_planet or nil
    value.copy_key = copy_key or ""
    if copy_key and G.P_CENTERS and G.P_CENTERS[copy_key] then
      local center = G.P_CENTERS[copy_key]
      value.copy_set = center.set or ""
      value.copy_label = center.name or ""
      if localize then
        local ok, localized = pcall(localize, { type = "name_text", key = copy_key, set = center.set })
        if ok and localized then
          value.copy_label = localized
        end
      end
    end
  end

  if card.ability and card.ability.set == "Joker" then
    local stats = extract_joker_stats(card)
    if stats then
      value.stats = stats
    end
    if card.config and card.config.center and type(card.config.center.rarity) == "number" then
      local rarity_names = { [1] = "COMMON", [2] = "UNCOMMON", [3] = "RARE", [4] = "LEGENDARY" }
      value.rarity = rarity_names[card.config.center.rarity]
    end
  end

  local center_key = card.config and card.config.center_key
  if center_key then
    local req = consumable.get_consumable_target_requirements(center_key)
    if req then
      if req.requires_joker then
        value.requires_joker = true
      elseif req.min and req.max then
        value.target_min = req.min
        value.target_max = req.max
      end
    end
  end

  return value
end

---Extracts state information from a card
---@param card table The card object
---@return Card.State state The Card.State object
local function extract_card_state(card)
  local state = {}

  -- Debuff
  if card.debuff then
    state.debuff = true
  end

  -- Hidden (facing == "back")
  if card.facing and card.facing == "back" then
    state.hidden = true
  end

  -- Highlighted
  if card.highlighted then
    state.highlight = true
  end

  return state
end

---Extracts cost information from a card
---@param card table The card object
---@return Card.Cost cost The Card.Cost object
local function extract_card_cost(card)
  return {
    sell = card.sell_cost or 0,
    buy = card.cost or 0,
  }
end

-- ==========================================================================
-- Card Extractor
-- ==========================================================================

---Extracts a complete Card object from a game card
---@param card table The game card object
---@param opts table|nil Extraction options
---@return Card card The Card object
local function extract_card(card, opts)
  opts = opts or {}
  -- Hidden (face-down) cards must not reveal their identity to the client.
  -- Otherwise boss blinds like The Wheel / The Mark / The Psychic are cheated,
  -- since the bot can read the real rank/suit/enhancement of every back-facing
  -- card. Mask everything except position (id), cost, and the hidden flag.
  local hidden = card.facing == "back"

  -- Determine set
  local set = "DEFAULT"
  if card.ability and card.ability.set then
    local ability_set = card.ability.set
    if ability_set == "Joker" then
      set = "JOKER"
    elseif ability_set == "Tarot" then
      set = "TAROT"
    elseif ability_set == "Planet" then
      set = "PLANET"
    elseif ability_set == "Spectral" then
      set = "SPECTRAL"
    elseif ability_set == "Voucher" then
      set = "VOUCHER"
    elseif ability_set == "Booster" then
      set = "BOOSTER"
    elseif ability_set == "Edition" then
      set = "EDITION"
    elseif card.ability.effect and card.ability.effect ~= "Base" then
      set = "ENHANCED"
    end
  end

  -- Extract key (prefer card_key for playing cards, fallback to center_key)
  local key = ""
  if card.config then
    if card.config.card_key then
      key = card.config.card_key
    elseif card.config.center_key then
      key = card.config.center_key
    end
  end

  local cost = extract_card_cost(card)
  if opts.free_pick then
    cost.original_buy = cost.buy
    cost.buy = 0
    cost.free = true
    cost.reason = "booster_pick"
  end

  if hidden then
    local state = { hidden = true }
    if card.highlighted then
      state.highlight = true
    end
    return {
      id = card.sort_id or 0,
      key = "",
      set = "DEFAULT",
      label = "",
      value = { effect = "" },
      modifier = {},
      state = state,
      cost = cost,
    }
  end

  local card_data = {
    id = card.sort_id or 0,
    key = key,
    set = set,
    label = card.label or "",
    value = extract_card_value(card),
    modifier = extract_card_modifier(card),
    cost = cost,
  }

  -- Omit empty state: Lua {} encodes as JSON [] and breaks dict-style clients
  local card_state = extract_card_state(card)
  if next(card_state) then
    card_data.state = card_state
  end

  return card_data
end

-- ==========================================================================
-- Area Extractor
-- ==========================================================================

---Extracts an Area object from a game area (like G.jokers, G.hand, etc.)
---@param area table The game area object
---@param opts table|nil Extraction options
---@return Area? area_data The Area object
local function extract_area(area, opts)
  opts = opts or {}
  if not area then
    return nil
  end

  local cards = {}
  if area.cards then
    for i, card in pairs(area.cards) do
      cards[i] = extract_card(card, opts)
    end
  end

  local area_data = {
    count = (area.config and area.config.card_count) or 0,
    limit = (area.config and area.config.card_limit) or 0,
    cards = cards,
  }

  -- Add highlighted_limit if available (for hand area)
  if area.config and area.config.highlighted_limit then
    area_data.highlighted_limit = area.config.highlighted_limit
  end

  return area_data
end

-- ==========================================================================
-- Poker Hands Extractor
-- ==========================================================================

---Extracts poker hands information
---@param hands table The G.GAME.hands table
---@return table<string, Hand> hands_data The hands information
local function extract_hand_info(hands)
  if not hands then
    return {}
  end

  local hands_data = {}
  for name, hand in pairs(hands) do
    hands_data[name] = {
      order = hand.order or 0,
      level = hand.level or 1,
      chips = hand.chips or 0,
      mult = hand.mult or 0,
      played = hand.played or 0,
      played_this_round = hand.played_this_round or 0,
      example = hand.example or {},
    }
    if hand.visible ~= nil then
      hands_data[name].visible = hand.visible
    end
  end

  return hands_data
end

-- ==========================================================================
-- Round Info Extractor
-- ==========================================================================

---Round-scoring targets (Ancient Joker suit, The Idol rank+suit, …).
---@return table<string, string>?
local function extract_round_scoring_targets()
  if not G or not G.GAME or not G.GAME.current_round then
    return nil
  end

  local cr = G.GAME.current_round
  local targets = {}

  if cr.ancient_card and cr.ancient_card.suit then
    local suit = convert_suit_to_enum(cr.ancient_card.suit)
    if suit then
      targets.ancient_suit = suit
    end
  end

  if cr.idol_card then
    if cr.idol_card.suit then
      local suit = convert_suit_to_enum(cr.idol_card.suit)
      if suit then
        targets.idol_suit = suit
      end
    end
    if cr.idol_card.rank then
      local rank = convert_rank_to_enum(cr.idol_card.rank)
      if rank then
        targets.idol_rank = rank
      end
    end
  end

  if cr.castle_card and cr.castle_card.suit then
    local suit = convert_suit_to_enum(cr.castle_card.suit)
    if suit then
      targets.castle_suit = suit
    end
  end

  if next(targets) == nil then
    return nil
  end
  return targets
end

---Extracts round state information
---@return Round round The Round object
local function extract_round_info()
  if not G or not G.GAME or not G.GAME.current_round then
    return {}
  end

  local round = {}

  if G.GAME.current_round.hands_left then
    round.hands_left = G.GAME.current_round.hands_left
  end

  if G.GAME.current_round.hands_played then
    round.hands_played = G.GAME.current_round.hands_played
  end

  if G.GAME.current_round.discards_left then
    round.discards_left = G.GAME.current_round.discards_left
  end

  if G.GAME.current_round.discards_used then
    round.discards_used = G.GAME.current_round.discards_used
  end

  if G.GAME.current_round.reroll_cost then
    round.reroll_cost = G.GAME.current_round.reroll_cost
  end

  -- Chips is stored in G.GAME not G.GAME.current_round
  if G.GAME.chips then
    round.chips = G.GAME.chips
  end

  local targets = extract_round_scoring_targets()
  if targets then
    if targets.ancient_suit then
      round.ancient_suit = targets.ancient_suit
    end
    if targets.idol_rank then
      round.idol_rank = targets.idol_rank
    end
    if targets.idol_suit then
      round.idol_suit = targets.idol_suit
    end
    if targets.castle_suit then
      round.castle_suit = targets.castle_suit
    end
  end

  return round
end

-- ==========================================================================
-- Blind Information
-- ==========================================================================

---Gets blind effect description from localization data
---@param blind_config table The blind configuration from G.P_BLINDS
---@return string effect The effect description
local function get_blind_effect_from_ui(blind_config)
  if not blind_config or not blind_config.key then
    return ""
  end

  -- Small and Big blinds have no effect
  if blind_config.key == "bl_small" or blind_config.key == "bl_big" then
    return ""
  end

  -- Access localization data directly (more reliable than using localize function)
  -- Path: G.localization.descriptions.Blind[blind_key].text
  if not G or not G.localization then ---@diagnostic disable-line: undefined-global
    return ""
  end

  local loc_data = G.localization.descriptions ---@diagnostic disable-line: undefined-global
  if not loc_data or not loc_data.Blind or not loc_data.Blind[blind_config.key] then
    return ""
  end

  local blind_data = loc_data.Blind[blind_config.key]
  if not blind_data.text or type(blind_data.text) ~= "table" then
    return ""
  end

  -- Concatenate all description lines
  local effect_parts = {}
  for _, line in ipairs(blind_data.text) do
    if line and line ~= "" then
      effect_parts[#effect_parts + 1] = line
    end
  end

  return table.concat(effect_parts, " ")
end

---Gets tag information using localize function (same approach as Tag:set_text)
---@param tag_key string The tag key from G.P_TAGS
---@return table tag_info {name: string, effect: string}
local function get_tag_info(tag_key)
  local result = { name = "", effect = "" }

  if not tag_key or not G.P_TAGS or not G.P_TAGS[tag_key] then
    return result
  end

  if not localize then ---@diagnostic disable-line: undefined-global
    return result
  end

  local tag_data = G.P_TAGS[tag_key]
  result.name = tag_data.name or ""

  -- Build loc_vars based on tag name (same logic as Tag:get_uibox_table in tag.lua:545-561)
  local loc_vars = {}
  local name = tag_data.name
  if name == "Investment Tag" then
    loc_vars = { tag_data.config and tag_data.config.dollars or 0 }
  elseif name == "Handy Tag" then
    local dollars_per_hand = tag_data.config and tag_data.config.dollars_per_hand or 0
    local hands_played = (G.GAME and G.GAME.hands_played) or 0
    loc_vars = { dollars_per_hand, dollars_per_hand * hands_played }
  elseif name == "Garbage Tag" then
    local dollars_per_discard = tag_data.config and tag_data.config.dollars_per_discard or 0
    local unused_discards = (G.GAME and G.GAME.unused_discards) or 0
    loc_vars = { dollars_per_discard, dollars_per_discard * unused_discards }
  elseif name == "Juggle Tag" then
    loc_vars = { tag_data.config and tag_data.config.h_size or 0 }
  elseif name == "Top-up Tag" then
    loc_vars = { tag_data.config and tag_data.config.spawn_jokers or 0 }
  elseif name == "Skip Tag" then
    local skip_bonus = tag_data.config and tag_data.config.skip_bonus or 0
    local skips = (G.GAME and G.GAME.skips) or 0
    loc_vars = { skip_bonus, skip_bonus * (skips + 1) }
  elseif name == "Orbital Tag" then
    local orbital_hand = "Poker Hand" -- Default placeholder
    local levels = tag_data.config and tag_data.config.levels or 0
    loc_vars = { orbital_hand, levels }
  elseif name == "Economy Tag" then
    loc_vars = { tag_data.config and tag_data.config.max or 0 }
  end

  -- Use localize with raw_descriptions type (matches Balatro's internal approach)
  local text_lines = localize({ type = "raw_descriptions", key = tag_key, set = "Tag", vars = loc_vars }) ---@diagnostic disable-line: undefined-global
  if text_lines and type(text_lines) == "table" then
    result.effect = table.concat(text_lines, " ")
  end

  return result
end

---Converts game blind status to uppercase enum
---@param status string Game status (e.g., "Defeated", "Current", "Select")
---@return string uppercase_status Uppercase status enum (e.g., "DEFEATED", "CURRENT", "SELECT")
local function convert_status_to_enum(status)
  if status == "Defeated" then
    return "DEFEATED"
  elseif status == "Skipped" then
    return "SKIPPED"
  elseif status == "Current" then
    return "CURRENT"
  elseif status == "Select" then
    return "SELECT"
  elseif status == "Upcoming" then
    return "UPCOMING"
  else
    return "UPCOMING" -- Default fallback
  end
end

---Gets comprehensive blind information for the current ante
---@return table<string, Blind> blinds Information about small, big, and boss blinds
function gamestate.get_blinds_info()
  -- Initialize with default structure matching the Blind type
  local blinds = {
    small = {
      type = "SMALL",
      status = "UPCOMING",
      name = "",
      effect = "",
      score = 0,
      tag_name = "",
      tag_effect = "",
    },
    big = {
      type = "BIG",
      status = "UPCOMING",
      name = "",
      effect = "",
      score = 0,
      tag_name = "",
      tag_effect = "",
    },
    boss = {
      type = "BOSS",
      status = "UPCOMING",
      name = "",
      effect = "",
      score = 0,
      tag_name = "",
      tag_effect = "",
    },
  }

  if not G.GAME or not G.GAME.round_resets then
    return blinds
  end

  -- Get base blind amount for current ante
  local ante = G.GAME.round_resets.ante or 1
  local base_amount = get_blind_amount(ante) ---@diagnostic disable-line: undefined-global

  -- Apply ante scaling with null check
  local ante_scaling = (G.GAME.starting_params and G.GAME.starting_params.ante_scaling) or 1

  -- Get blind choices
  local blind_choices = G.GAME.round_resets.blind_choices or {}
  local blind_states = G.GAME.round_resets.blind_states or {}

  -- ====================
  -- Small Blind
  -- ====================
  local small_choice = blind_choices.Small or "bl_small"
  if G.P_BLINDS and G.P_BLINDS[small_choice] then
    local small_blind = G.P_BLINDS[small_choice]
    blinds.small.name = small_blind.name or "Small Blind"
    blinds.small.score = math.floor(base_amount * (small_blind.mult or 1) * ante_scaling)
    blinds.small.effect = get_blind_effect_from_ui(small_blind)

    -- Set status
    if blind_states.Small then
      blinds.small.status = convert_status_to_enum(blind_states.Small)
    end

    -- Get tag information
    local small_tag_key = G.GAME.round_resets.blind_tags and G.GAME.round_resets.blind_tags.Small
    if small_tag_key then
      local tag_info = get_tag_info(small_tag_key)
      blinds.small.tag_name = tag_info.name
      blinds.small.tag_effect = tag_info.effect
    end
  end

  -- ====================
  -- Big Blind
  -- ====================
  local big_choice = blind_choices.Big or "bl_big"
  if G.P_BLINDS and G.P_BLINDS[big_choice] then
    local big_blind = G.P_BLINDS[big_choice]
    blinds.big.name = big_blind.name or "Big Blind"
    blinds.big.score = math.floor(base_amount * (big_blind.mult or 1.5) * ante_scaling)
    blinds.big.effect = get_blind_effect_from_ui(big_blind)

    -- Set status
    if blind_states.Big then
      blinds.big.status = convert_status_to_enum(blind_states.Big)
    end

    -- Get tag information
    local big_tag_key = G.GAME.round_resets.blind_tags and G.GAME.round_resets.blind_tags.Big
    if big_tag_key then
      local tag_info = get_tag_info(big_tag_key)
      blinds.big.tag_name = tag_info.name
      blinds.big.tag_effect = tag_info.effect
    end
  end

  -- ====================
  -- Boss Blind
  -- ====================
  local boss_choice = blind_choices.Boss
  if boss_choice and G.P_BLINDS and G.P_BLINDS[boss_choice] then
    local boss_blind = G.P_BLINDS[boss_choice]
    blinds.boss.name = boss_blind.name or "Boss Blind"
    blinds.boss.score = math.floor(base_amount * (boss_blind.mult or 2) * ante_scaling)
    blinds.boss.effect = get_blind_effect_from_ui(boss_blind)

    -- Set status
    if blind_states.Boss then
      blinds.boss.status = convert_status_to_enum(blind_states.Boss)
    end
  else
    -- Fallback if boss blind not yet determined
    blinds.boss.name = "Boss Blind"
    blinds.boss.score = math.floor(base_amount * 2 * ante_scaling)
  end

  -- Boss blind has no tags (tag_name and tag_effect remain empty strings)

  return blinds
end

-- ==========================================================================
-- Main Gamestate Extractor
-- ==========================================================================

---Whether the post-win victory overlay (Endless / New Run) is visible
---@return boolean
function gamestate.has_victory_overlay()
  return G.GAME ~= nil and G.GAME.won and G.OVERLAY_MENU ~= nil and G.STATE == G.STATES.ROUND_EVAL
end

---Extracts the simplified game state according to the new specification
---@return GameState gamestate The complete simplified game state
function gamestate.get_gamestate()
  if not G then
    return {
      state = "UNKNOWN",
      round_num = 0,
      ante_num = 0,
      money = 0,
    }
  end

  local state_data = {
    state = get_state_name(G.STATE),
  }

  -- Basic game info
  if G.GAME then
    state_data.round_num = G.GAME.round or 0
    state_data.ante_num = (G.GAME.round_resets and G.GAME.round_resets.ante) or 0
    state_data.money = G.GAME.dollars or 0
    state_data.bankrupt_at = G.GAME.bankrupt_at or 0
    state_data.won = G.GAME.won
    if G.GAME.won and gamestate.has_victory_overlay() then
      state_data.victory_overlay = true
    end

    -- Deck (optional)
    if G.GAME.selected_back and G.GAME.selected_back.effect and G.GAME.selected_back.effect.center then
      local deck_key = G.GAME.selected_back.effect.center.key
      state_data.deck = get_deck_name(deck_key)
    end

    -- Stake (optional)
    if G.GAME.stake then
      state_data.stake = get_stake_name(G.GAME.stake)
    end

    -- Seed (optional)
    if G.GAME.pseudorandom and G.GAME.pseudorandom.seed then
      state_data.seed = G.GAME.pseudorandom.seed
    end

    -- Used vouchers (table<string, string>)
    if G.GAME.used_vouchers then
      local used_vouchers = {}
      for voucher_name, voucher_data in pairs(G.GAME.used_vouchers) do
        if type(voucher_data) == "table" and voucher_data.description then
          used_vouchers[voucher_name] = voucher_data.description
        else
          used_vouchers[voucher_name] = ""
        end
      end
      state_data.used_vouchers = used_vouchers
    end

    -- Poker hands
    if G.GAME.hands then
      state_data.hands = extract_hand_info(G.GAME.hands)
    end

    -- Round info
    state_data.round = extract_round_info()

    local run = extract_run_counters()
    if run then
      state_data.run = run
    end

    -- Blinds info
    state_data.blinds = gamestate.get_blinds_info()
  end

  -- Always available areas
  state_data.jokers = extract_area(G.jokers)
  state_data.consumables = extract_area(G.consumeables) -- Note: typo in game code

  -- Cards remaining in deck
  if G.deck then
    state_data.cards = extract_area(G.deck)
  end

  -- Hand (count is 0 during not playing phase)
  if G.hand then
    state_data.hand = extract_area(G.hand)
  end

  -- Shop areas (available during shop phase)
  if G.shop_jokers then
    state_data.shop = extract_area(G.shop_jokers)
  end

  if G.shop_vouchers then
    state_data.vouchers = extract_area(G.shop_vouchers)
  end

  if G.shop_booster then
    state_data.packs = extract_area(G.shop_booster)
  end

  -- Pack cards area (available during pack opening phases)
  if G.pack_cards and not G.pack_cards.REMOVED then
    state_data.pack = extract_area(G.pack_cards, { free_pick = true })
  end

  if G.GAME and (G.STATE == G.STATES.GAME_OVER or G.GAME.won) then
    state_data.run_summary = gamestate.extract_run_summary()
  end

  return state_data
end

-- ==========================================================================
-- Game Over Run Summary
-- ==========================================================================

---@param entry table|number|nil
---@return number|nil
local function round_score_amt(entry)
  if entry == nil then
    return nil
  end
  if type(entry) == "number" then
    return entry
  end
  if type(entry) == "table" then
    return entry.amt or entry.amount or entry.count
  end
  return nil
end

---Extract most-played poker hand from run statistics
---@return table|nil
local function extract_most_played_hand()
  local best_name, best_count = nil, 0

  if G.GAME.hand_usage then
    for name, data in pairs(G.GAME.hand_usage) do
      local count = round_score_amt(data) or 0
      if count > best_count then
        best_count = count
        best_name = name
      end
    end
  end

  if not best_name and G.GAME.hands then
    for name, hand in pairs(G.GAME.hands) do
      local count = hand.played or 0
      if count > best_count then
        best_count = count
        best_name = name
      end
    end
  end

  if best_name then
    return { name = best_name, count = best_count }
  end
  return nil
end

---Build human-readable game-over result line
---@return string
local function extract_run_result()
  if G.STATE == G.STATES.GAME_OVER then
    local blind_name = G.GAME.blind and G.GAME.blind.name
    if not blind_name and G.GAME.round_resets then
      blind_name = G.GAME.round_resets.blind
    end
    if blind_name and blind_name ~= "" then
      return "Lost to " .. blind_name
    end
    return "Lost"
  end

  if G.GAME.won then
    return "Victory"
  end

  local blind_name = G.GAME.blind and G.GAME.blind.name
  if not blind_name and G.GAME.round_resets then
    blind_name = G.GAME.round_resets.blind
  end
  if blind_name and blind_name ~= "" then
    return "Lost to " .. blind_name
  end
  return "Lost"
end

---Extract run summary statistics shown on the game-over modal
---@return table|nil
function gamestate.extract_run_summary()
  if not G.GAME or (G.STATE ~= G.STATES.GAME_OVER and not G.GAME.won) then
    return nil
  end

  local rs = G.GAME.round_scores or {}
  local summary = {
    best_hand = round_score_amt(rs.hand),
    cards_played = round_score_amt(rs.cards_played) or round_score_amt(rs.card),
    cards_discarded = round_score_amt(rs.cards_discarded) or round_score_amt(rs.discards),
    cards_purchased = round_score_amt(rs.cards_purchased) or round_score_amt(rs.purchases),
    reroll_count = round_score_amt(rs.times_rerolled)
      or round_score_amt(rs.reroll)
      or (G.GAME.current_round and G.GAME.current_round.reroll_cost and round_score_amt(rs.shop_reroll)),
    new_discoveries = round_score_amt(rs.new_collection) or round_score_amt(rs.collection),
    result = extract_run_result(),
  }

  local most_played = extract_most_played_hand()
  if most_played then
    summary.most_played_hand = most_played
  end

  return summary
end

-- ==========================================================================
-- Save Compatibility
-- ==========================================================================

---Ensure G.GAME.bosses_used matches SMODS structure after loading saves.
---Saved runs keep nested tables but lose the metatable, so bosses_used[key] is nil.
function gamestate.ensure_bosses_used()
  if not G or not G.GAME or not G.P_BLINDS then
    return
  end

  local bu = G.GAME.bosses_used
  if type(bu) ~= "table" then
    bu = {}
    G.GAME.bosses_used = bu
  end

  local function with_metatable(boss, small, big)
    return setmetatable({ boss = boss, small = small, big = big }, {
      __index = function(t, key)
        return t.boss[key] or t.big[key] or t.small[key]
      end,
      __newindex = function(t, key, value)
        rawset(t.boss, key, value)
      end,
    })
  end

  if type(bu.boss) ~= "table" then
    local legacy = bu
    local boss, small, big = {}, {}, {}
    for k, v in pairs(G.P_BLINDS) do
      if v.boss then
        boss[k] = legacy[k] or 0
      end
      if v.small then
        small[k] = legacy[k] or 0
      end
      if v.big then
        big[k] = legacy[k] or 0
      end
    end
    bu = with_metatable(boss, small, big)
    G.GAME.bosses_used = bu
  elseif getmetatable(bu) == nil then
    bu = with_metatable(bu.boss or {}, bu.small or {}, bu.big or {})
    G.GAME.bosses_used = bu
  end

  for k, v in pairs(G.P_BLINDS) do
    if v.boss and bu.boss[k] == nil then
      bu.boss[k] = 0
    end
    if v.small and bu.small[k] == nil then
      bu.small[k] = 0
    end
    if v.big and bu.big[k] == nil then
      bu.big[k] = 0
    end
  end
end

-- ==========================================================================
-- GAME_OVER Callback Support
-- ==========================================================================

-- Callback set by endpoints that need immediate GAME_OVER notification
-- This is necessary because when G.STATE becomes GAME_OVER, the game pauses
-- (G.SETTINGS.paused = true) which stops event processing, preventing
-- normal event-based detection from working.
gamestate.on_game_over = nil

---Check and trigger GAME_OVER callback if state is GAME_OVER
---Called from love.update before game logic runs
function gamestate.check_game_over()
  if gamestate.on_game_over and G.STATE == G.STATES.GAME_OVER then
    gamestate.on_game_over(gamestate.get_gamestate())
    gamestate.on_game_over = nil
  end
end

return gamestate
