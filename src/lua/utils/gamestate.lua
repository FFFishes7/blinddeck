---Simplified game state extraction utilities
---This module provides a clean, simplified interface for extracting game state
---according to the new gamestate specification

---@class GameStateModule
---@field on_game_over (fun(state: GameState))?
---@field on_victory_overlay (fun(state: GameState))?
---@field check_game_over fun()
---@field check_victory_overlay fun()
---@field clear_play_callbacks fun()
---@field get_blinds_info fun(): table<string, Blind>
---@field get_gamestate fun(): GameState
---@field ensure_bosses_used fun()
---@field boss_reroll_has_voucher fun(): boolean
---@field boss_reroll_available fun(): boolean
---@field BOSS_REROLL_COST integer
---@field pack_is_open fun(): boolean
---@field pack_open_ready fun(): boolean
---@field pack_hand_ready fun(): boolean
---@field is_pack_skip_tag fun(tag_key: string|nil): boolean
---@field skip_settled fun(blind_key: string, opts?: { expect_pack?: boolean }): boolean
---@field tags_stack_stable fun(): boolean
---@field extract_held_tags fun(): table[]
---@field extract_cashout_preview fun(): CashoutPreview|nil
---@field get_reported_state_name fun(): string
---@field get_stake_sticker_blacklist fun(): { lines: string[], count: integer }
local gamestate = {}

gamestate.BOSS_REROLL_COST = 10

local consumable = assert(SMODS.load_file("src/lua/utils/consumable.lua"))()
local cashout_preview = assert(SMODS.load_file("src/lua/utils/cashout_preview.lua"))()
local challenges = assert(SMODS.load_file("src/lua/utils/challenges.lua"))()

---@type fun(string, table|nil): { name: string, effect: string }
local get_tag_info

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

---Pack-related G.STATES values (vanilla + SMODS)
local function is_vanilla_pack_state_name(name)
  return name == "TAROT_PACK"
    or name == "PLANET_PACK"
    or name == "SPECTRAL_PACK"
    or name == "STANDARD_PACK"
    or name == "BUFFOON_PACK"
end

---Whether a booster pack UI is open with selectable cards
---@return boolean
function gamestate.pack_is_open()
  if G.pack_cards ~= nil and not G.pack_cards.REMOVED and G.pack_cards.cards ~= nil and #G.pack_cards.cards > 0 then
    return true
  end
  return is_vanilla_pack_state_name(get_state_name(G.STATE))
end

---State string for API / play helpers (normalizes open-pack phases)
---@return string
function gamestate.get_reported_state_name()
  if gamestate.pack_is_open() then
    return "SMODS_BOOSTER_OPENED"
  end
  local name = get_state_name(G.STATE)
  if is_vanilla_pack_state_name(name) then
    return "SMODS_BOOSTER_OPENED"
  end
  return name
end

---Skip tags that open a booster immediately (game.lua config.type = new_blind_choice;
---see tag.lua Charm/Meteor/Ethereal/Standard/Buffoon — Boss Tag is excluded).
local PACK_SKIP_TAG_KEYS = {
  tag_charm = true,
  tag_buffoon = true,
  tag_ethereal = true,
  tag_meteor = true,
  tag_standard = true,
}

local function is_pack_skip_tag(tag_key)
  return tag_key ~= nil and PACK_SKIP_TAG_KEYS[tag_key] == true
end

function gamestate.is_pack_skip_tag(tag_key)
  return is_pack_skip_tag(tag_key)
end

---Untriggered pack tag still on the stack (oldest-first apply on skip).
---@return boolean
local function has_pending_pack_skip_tag()
  if G.GAME == nil or G.GAME.tags == nil then
    return false
  end
  for _, tag in ipairs(G.GAME.tags) do
    if not tag.triggered and is_pack_skip_tag(tag.key) then
      return true
    end
  end
  return false
end

---Booster from skip/buy is stable enough for API pack actions.
---@return boolean
function gamestate.pack_open_ready()
  if G.pack_cards == nil or G.pack_cards.REMOVED or G.pack_cards.cards == nil then
    return false
  end
  if not G.pack_cards.cards[1] then
    return false
  end
  if G.STATE_COMPLETE ~= true then
    return false
  end
  if G.STATE == G.STATES.SMODS_BOOSTER_OPENED then
    return true
  end
  local state_name = get_state_name(G.STATE)
  if is_vanilla_pack_state_name(state_name) then
    return true
  end
  -- Tag-skip Charm/Arcana: G.STATE can stay BLIND_SELECT while pack_cards is live.
  if G.STATE == G.STATES.BLIND_SELECT and #G.pack_cards.cards > 0 then
    return true
  end
  return false
end

---Arcana/Spectral packs need a dealt hand before glance/actions are stable.
---@return boolean
function gamestate.pack_hand_ready()
  if not gamestate.pack_open_ready() then
    return false
  end
  local first_pack_card = G.pack_cards and G.pack_cards.cards and G.pack_cards.cards[1]
  local pack_set = first_pack_card and first_pack_card.ability and first_pack_card.ability.set
  local needs_hand = pack_set == "Tarot" or pack_set == "Spectral"
  if not needs_hand then
    return true
  end
  if G.hand == nil or G.hand.REMOVED or G.hand.cards == nil or #G.hand.cards == 0 then
    return false
  end
  local first_hand = G.hand.cards[1]
  return first_hand ~= nil and first_hand.T ~= nil and first_hand.T.x ~= nil
end

---Whether skip/tag side effects have settled (blind skipped + stable screen)
---@param blind_key string lower-case blind key (e.g. "small")
---@param opts? { expect_pack?: boolean } expect_pack: skipped blind had a pack-opening tag
---@return boolean
function gamestate.skip_settled(blind_key, opts)
  opts = opts or {}
  if G.GAME == nil or G.GAME.blind_on_deck == nil or G.blind_select_opts == nil then
    return false
  end
  local blinds = gamestate.get_blinds_info()
  local blind = blinds[blind_key]
  if blind == nil or blind.status ~= "SKIPPED" then
    return false
  end

  if gamestate.pack_open_ready() then
    return gamestate.tags_stack_stable()
  end

  if has_pending_pack_skip_tag() then
    return false
  end

  -- Wait for tag yep animation + booster open after a pack skip tag on this blind.
  if opts.expect_pack then
    return false
  end

  if G.STATE == G.STATES.SMODS_BOOSTER_OPENED then
    return false
  end
  local state_name = get_state_name(G.STATE)
  if is_vanilla_pack_state_name(state_name) then
    return false
  end

  if G.STATE == G.STATES.BLIND_SELECT and G.STATE_COMPLETE then
    return gamestate.tags_stack_stable()
  end

  return false
end

---Whether any tag yep animation still holds a CONTROLLER lock.
---@return boolean
local function has_active_tag_lock()
  if G.CONTROLLER == nil or G.CONTROLLER.locks == nil or G.GAME == nil or G.GAME.tags == nil then
    return false
  end
  local tag_ids = {}
  for _, tag in ipairs(G.GAME.tags) do
    if tag.ID ~= nil then
      tag_ids[tag.ID] = true
    end
  end
  for lock_key, locked in pairs(G.CONTROLLER.locks) do
    if locked and tag_ids[lock_key] then
      return true
    end
  end
  return false
end

---Tag stack is stable enough for a held_tags snapshot (no in-flight yep/trigger).
---@return boolean
function gamestate.tags_stack_stable()
  if G.GAME == nil or G.GAME.tags == nil then
    return true
  end
  local state_name = gamestate.get_reported_state_name()
  if state_name == "MENU" or state_name == "SPLASH" or state_name == "GAME_OVER" then
    return true
  end
  if G.STATE_COMPLETE ~= true then
    return false
  end
  for _, tag in ipairs(G.GAME.tags) do
    if tag.triggered then
      return false
    end
  end
  if has_active_tag_lock() then
    return false
  end
  return true
end

---Pending held tags (untriggered), oldest first.
---@return table[]
function gamestate.extract_held_tags()
  local out = {}
  if G.GAME == nil or G.GAME.tags == nil then
    return out
  end
  for _, tag in ipairs(G.GAME.tags) do
    if not tag.triggered and tag.key then
      local info = get_tag_info(tag.key, tag)
      out[#out + 1] = {
        key = tag.key,
        name = info.name,
        effect = info.effect,
      }
    end
  end
  return out
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

local function normalize_profile_line(text)
  if not text then
    return ""
  end
  return (text:gsub("^%s+", ""):gsub("%s+$", ""):gsub("%s+", " "))
end

---@param key string Other-table key (e.g. white_sticker)
---@return string|nil
local function localize_sticker_line(key)
  local nodes = {}
  local ok = pcall(function()
    localize({ type = "descriptions", key = key, set = "Other", nodes = nodes })
  end)
  if not ok or #nodes == 0 then
    return nil
  end
  local parts = {}
  collect_ui_texts(nodes, parts)
  if #parts == 0 then
    return nil
  end
  return normalize_profile_line(table.concat(parts, ""))
end

local _stake_sticker_blacklist = nil

---Lazy cache of localized stake win sticker info lines (profile achievement text).
---@return table<string, true>
local function build_stake_sticker_blacklist()
  if _stake_sticker_blacklist then
    return _stake_sticker_blacklist
  end

  local blacklist = {}
  local seen_keys = {}

  local function register_sticker(name)
    if not name or seen_keys[name] then
      return
    end
    seen_keys[name] = true
    local key = string.lower(name) .. "_sticker"
    local text = localize_sticker_line(key)
    if text and text ~= "" then
      blacklist[text] = true
    end
  end

  local sticker_names = {}
  if G.sticker_map then
    for _, name in ipairs(G.sticker_map) do
      sticker_names[name] = true
      register_sticker(name)
    end
    for name, _ in pairs(G.sticker_map) do
      if type(name) == "string" then
        sticker_names[name] = true
        register_sticker(name)
      end
    end
  end

  if G.P_STAKES then
    for _, stake in pairs(G.P_STAKES) do
      if stake.key and sticker_names[stake.key] then
        register_sticker(stake.key)
      end
    end
  end

  _stake_sticker_blacklist = blacklist
  return blacklist
end

---@param line string
---@return boolean
local function is_profile_sticker_line(line)
  if not line or line == "" then
    return false
  end
  local normalized = normalize_profile_line(line)
  if normalized == "" then
    return false
  end
  return build_stake_sticker_blacklist()[normalized] == true
end

---Debug/test helper: sorted list of blacklisted stake sticker lines.
---@return { lines: string[], count: integer }
function gamestate.get_stake_sticker_blacklist()
  local blacklist = build_stake_sticker_blacklist()
  local lines = {}
  for text, _ in pairs(blacklist) do
    lines[#lines + 1] = text
  end
  table.sort(lines)
  return { lines = lines, count = #lines }
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

  local joker_main_only = card.ability and card.ability.set == "Joker"
  if ui_table.info and not joker_main_only then
    for _, line in ipairs(ui_table.info) do
      local line_texts = {}
      collect_ui_texts(line, line_texts)
      if #line_texts > 0 then
        local line_str = table.concat(line_texts, "")
        if not is_profile_sticker_line(line_str) then
          texts[#texts + 1] = line_str
        end
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
  elseif name == "Cloud 9" and type(a.nine_tally) == "number" and a.nine_tally > 0 then
    stats.nine_tally = a.nine_tally
  elseif name == "Rocket" and type(a.extra) == "table" and type(a.extra.dollars) == "number" then
    stats.rocket_dollars = a.extra.dollars
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
    if not copy_key then
      value.effect = value.effect:gsub("%s+None%s*$", " ")
    end
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
      if req.random_joker_effect then
        value.random_joker_effect = true
      end
      if req.requires_jokers_min then
        value.requires_jokers_min = req.requires_jokers_min
      end
      if req.min and req.max then
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

  -- Forced selection (Cerulean Bell). This is distinct from a normal
  -- highlight because the card cannot be unselected by the player.
  if card.ability and card.ability.forced_selection then
    state.forced_selection = true
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
    local state = extract_card_state(card)
    state.hidden = true
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

---True when run owns Retcon or unused Director's Cut boss reroll this ante
---@return boolean
function gamestate.boss_reroll_has_voucher()
  if not G or not G.GAME or not G.GAME.used_vouchers then
    return false
  end
  if G.GAME.used_vouchers["v_retcon"] then
    return true
  end
  if G.GAME.used_vouchers["v_directors_cut"] then
    local rerolled = G.GAME.round_resets and G.GAME.round_resets.boss_rerolled
    return not rerolled
  end
  return false
end

---True when reroll_boss endpoint would succeed (mirrors in-game button)
---@return boolean
function gamestate.boss_reroll_available()
  if not G or G.STATE ~= G.STATES.BLIND_SELECT then
    return false
  end
  if not G.GAME or G.GAME.blind_on_deck ~= "Boss" then
    return false
  end
  local boss_state = G.GAME.round_resets and G.GAME.round_resets.blind_states and G.GAME.round_resets.blind_states.Boss
  if boss_state == "Defeated" or boss_state == "Skipped" then
    return false
  end
  if not gamestate.boss_reroll_has_voucher() then
    return false
  end
  local available_money = G.GAME.dollars - G.GAME.bankrupt_at
  return available_money >= gamestate.BOSS_REROLL_COST
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

  round.boss_reroll_cost = gamestate.BOSS_REROLL_COST
  if G.GAME.round_resets then
    round.boss_rerolled = G.GAME.round_resets.boss_rerolled or false
  end
  if G.STATE == G.STATES.BLIND_SELECT then
    round.boss_reroll_available = gamestate.boss_reroll_available()
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

  if G.STATE == G.STATES.ROUND_EVAL and G.GAME.blind then
    local chips = G.GAME.chips or 0
    local blind_chips = G.GAME.blind.chips or 0
    if chips >= blind_chips then
      round.cashout_preview = cashout_preview.extract()
    end
  end

  return round
end

---Round-end cashout preview (ROUND_EVAL, round won only).
---@return CashoutPreview|nil
function gamestate.extract_cashout_preview()
  return cashout_preview.extract()
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

  local result = table.concat(effect_parts, " ")

  -- Substitute variables (e.g. #1#, #2#) with their values
  local vars = blind_config.vars
  -- Inject dynamic vars for specific boss blinds that lack them in G.P_BLINDS
  if blind_config.key == "bl_wheel" then
    vars = { (G.GAME and G.GAME.probabilities.normal) or 1, 7 }
  elseif blind_config.key == "bl_ox" then
    vars = { (G.GAME and G.GAME.current_round and G.GAME.current_round.most_played_poker_hand) or "Hand" }
  end

  if vars and type(vars) == "table" then
    for i, var in ipairs(vars) do
      result = result:gsub("#" .. i .. "#", function()
        -- Handle localization keys if necessary, or just tostring
        if type(var) == "string" and G.localization and G.localization.misc.poker_hands[var] then
          return G.localization.misc.poker_hands[var]
        end
        return tostring(var)
      end)
    end
  end

  return result
end

---Gets tag information using localize function (same approach as Tag:set_text)
---@param tag_key string The tag key from G.P_TAGS
---@param tag_instance table|nil Live tag for instance fields (e.g. Orbital hand)
---@return table tag_info {name: string, effect: string}
get_tag_info = function(tag_key, tag_instance)
  local result = { name = "", effect = "" }

  if not tag_key or not G.P_TAGS or not G.P_TAGS[tag_key] then
    return result
  end

  if not localize then ---@diagnostic disable-line: undefined-global
    return result
  end

  local tag_data = G.P_TAGS[tag_key]
  local ok_name, localized_name = pcall(localize, { type = "name_text", set = "Tag", key = tag_key }) ---@diagnostic disable-line: undefined-global
  if ok_name and type(localized_name) == "string" and localized_name ~= "" then
    result.name = localized_name
  else
    result.name = tag_data.name or ""
  end

  -- Build loc_vars based on tag key (locale-independent; mirrors tag.lua)
  local loc_vars = {}
  if tag_key == "tag_investment" then
    loc_vars = { tag_data.config and tag_data.config.dollars or 0 }
  elseif tag_key == "tag_handy" then
    local dollars_per_hand = tag_data.config and tag_data.config.dollars_per_hand or 0
    local hands_played = (G.GAME and G.GAME.hands_played) or 0
    loc_vars = { dollars_per_hand, dollars_per_hand * hands_played }
  elseif tag_key == "tag_garbage" then
    local dollars_per_discard = tag_data.config and tag_data.config.dollars_per_discard or 0
    local unused_discards = (G.GAME and G.GAME.unused_discards) or 0
    loc_vars = { dollars_per_discard, dollars_per_discard * unused_discards }
  elseif tag_key == "tag_juggle" then
    loc_vars = { tag_data.config and tag_data.config.h_size or 0 }
  elseif tag_key == "tag_top_up" then
    loc_vars = { tag_data.config and tag_data.config.spawn_jokers or 0 }
  elseif tag_key == "tag_skip" then
    local skip_bonus = tag_data.config and tag_data.config.skip_bonus or 0
    local skips = (G.GAME and G.GAME.skips) or 0
    loc_vars = { skip_bonus, skip_bonus * (skips + 1) }
  elseif tag_key == "tag_orbital" then
    local orbital_hand = "Poker Hand"
    if tag_instance and tag_instance.ability and tag_instance.ability.orbital_hand then
      orbital_hand = tag_instance.ability.orbital_hand
    end
    local levels = tag_data.config and tag_data.config.levels or 0
    loc_vars = { orbital_hand, levels }
  elseif tag_key == "tag_economy" then
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
      tag_key = "",
      tag_effect = "",
    },
    big = {
      type = "BIG",
      status = "UPCOMING",
      name = "",
      effect = "",
      score = 0,
      tag_name = "",
      tag_key = "",
      tag_effect = "",
    },
    boss = {
      type = "BOSS",
      status = "UPCOMING",
      name = "",
      effect = "",
      score = 0,
      tag_name = "",
      tag_key = "",
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
      blinds.small.tag_key = small_tag_key
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
      blinds.big.tag_key = big_tag_key
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
  if not G.GAME or not G.GAME.won or G.STATE ~= G.STATES.ROUND_EVAL then
    return false
  end
  if not G.OVERLAY_MENU then
    return false
  end
  if G.OVERLAY_MENU.get_UIE_by_ID then
    if G.OVERLAY_MENU:get_UIE_by_ID("from_game_won") then
      return true
    end
    if G.OVERLAY_MENU:get_UIE_by_ID("from_deck_won") then
      return true
    end
  end
  -- Won run with any overlay menu is the victory screen (Endless / New Run / Menu).
  return true
end

---Error response when the post-win overlay blocks other ROUND_EVAL actions
---@return Response.Endpoint.Error?
function gamestate.victory_overlay_response()
  if gamestate.has_victory_overlay() then
    return {
      message = "Victory overlay is showing — call endless or menu first",
      name = BB_ERROR_NAMES.NOT_ALLOWED,
    }
  end
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
      held_tags = {},
      held_tags_ready = true,
    }
  end

  local state_data = {
    state = gamestate.get_reported_state_name(),
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

    if G.GAME.challenge then
      state_data.challenge = challenges.active(G.GAME.challenge)
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
    local pack_choices = G.GAME and G.GAME.pack_choices
    if pack_choices and pack_choices > 0 then
      state_data.pack.choices_remaining = pack_choices
    end
  end

  if state_data.state == "SMODS_BOOSTER_OPENED" then
    state_data.pack_ready = gamestate.pack_open_ready()
    state_data.pack_hand_ready = state_data.pack_ready and gamestate.pack_hand_ready() or false
  end

  if G.GAME and (G.STATE == G.STATES.GAME_OVER or G.GAME.won) then
    state_data.run_summary = gamestate.extract_run_summary()
  end

  state_data.held_tags = gamestate.extract_held_tags()
  state_data.held_tags_ready = gamestate.tags_stack_stable()

  if state_data.state == "ROUND_EVAL" and G.GAME then
    local investment = 0
    if state_data.round and state_data.round.cashout_preview then
      investment = state_data.round.cashout_preview.investment_received or 0
    end
    if investment == 0 and state_data.victory_overlay then
      for _, tag in ipairs(state_data.held_tags) do
        if tag.key == "tag_investment" then
          local unit = 25
          if G.P_TAGS and G.P_TAGS.tag_investment and G.P_TAGS.tag_investment.config then
            unit = G.P_TAGS.tag_investment.config.dollars or unit
          end
          investment = investment + unit
        end
      end
      if investment > 0 then
        if not state_data.round then
          state_data.round = {}
        end
        if not state_data.round.cashout_preview then
          state_data.round.cashout_preview = { lines = {}, total = 0 }
        end
        state_data.round.cashout_preview.investment_received = investment
      end
    end
    if investment > 0 then
      state_data.money = (G.GAME.dollars or 0) + investment
      -- Final win may skip evaluate_round; tag stays in G.GAME.tags but is spent.
      local filtered = {}
      for _, tag in ipairs(state_data.held_tags) do
        if tag.key ~= "tag_investment" then
          filtered[#filtered + 1] = tag
        end
      end
      state_data.held_tags = filtered
    end
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

-- Callbacks set by play() for states where G.SETTINGS.paused stops E_MANAGER.
gamestate.on_game_over = nil
gamestate.on_victory_overlay = nil

---Clear play() completion callbacks (avoid double response).
function gamestate.clear_play_callbacks()
  gamestate.on_game_over = nil
  gamestate.on_victory_overlay = nil
end

---Whether play() should return on a final run win at ROUND_EVAL.
---@return boolean
local function play_won_round_eval_ready()
  if not G.GAME or not G.GAME.won or G.STATE ~= G.STATES.ROUND_EVAL then
    return false
  end
  return gamestate.has_victory_overlay()
end

---Check and trigger GAME_OVER callback if state is GAME_OVER
---Called from love.update before game logic runs
function gamestate.check_game_over()
  if gamestate.on_game_over and G.STATE == G.STATES.GAME_OVER then
    gamestate.on_game_over(gamestate.get_gamestate())
    gamestate.clear_play_callbacks()
  end
end

---Check and trigger victory-overlay callback for final run wins.
---Called from love.update before game logic runs (runs when paused).
function gamestate.check_victory_overlay()
  if gamestate.on_victory_overlay and play_won_round_eval_ready() then
    gamestate.on_victory_overlay(gamestate.get_gamestate())
    gamestate.clear_play_callbacks()
  end
end

return gamestate
