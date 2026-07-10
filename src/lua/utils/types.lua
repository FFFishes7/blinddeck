---@meta types

-- ==========================================================================
-- GameState Types
--
-- The GameState represents the current game state of the game. It's a nested
-- table that contains all the information about the game state, including
-- the current round, hand, and discards.
-- ==========================================================================

---@class GameState
---@field deck Deck? Current selected deck
---@field stake Stake? Current selected stake
---@field seed string? Seed used for the run
---@field state State Current game state
---@field round_num integer Current round number
---@field ante_num integer Current ante number
---@field money integer Current money amount
---@field used_vouchers table<string, string>? Vouchers used (name -> description)
---@field hands table<string, Hand>? Poker hands information
---@field round Round? Current round state
---@field blinds table<"small"|"big"|"boss", Blind>? Blind information
---@field jokers Area? Jokers area
---@field consumables Area? Consumables area
---@field hand Area? Hand area (available during playing phase)
---@field cards Area? Cards remaining in deck (available during run)
---@field pack Area? Currently open pack (available during opeing pack phase)
---@field shop Area? Shop area (available during shop phase)
---@field vouchers Area? Vouchers area (available during shop phase)
---@field packs Area? Booster packs area (available during shop phase)
---@field won boolean? True after defeating final Boss; stays true in endless mode
---@field victory_overlay boolean? Victory screen visible; call endless to continue
---@field run RunCounters? Run-level counters for scoring (skips, deck size, …)
---@field run_summary RunSummary? Run statistics (GAME_OVER only)
---@field held_tags HeldTag[] Pending untriggered tags (oldest first); read when held_tags_ready
---@field held_tags_ready boolean? True when held_tags snapshot is stable (no tag yep in flight)
---@field pack_ready boolean? Open booster has selectable cards (SMODS_BOOSTER_OPENED only)
---@field pack_hand_ready boolean? Hand dealt for Arcana/Spectral pack targeting (when pack_ready)

---@class HeldTag
---@field key string Stable tag id (e.g. tag_foil); use for logic, not name
---@field name string Display name (may be localized)
---@field effect string

---@class RunSummary
---@field best_hand number? Highest single-hand score this run
---@field most_played_hand table? { name: string, count: integer }
---@field cards_played integer?
---@field cards_discarded integer?
---@field cards_purchased integer?
---@field reroll_count integer?
---@field new_discoveries integer?
---@field result string Human-readable win/loss line from game UI

---@class Hand
---@field order integer The importance/ordering of the hand
---@field level integer Level of the hand in the current run
---@field chips integer Current chip value for this hand
---@field mult integer Current multiplier value for this hand
---@field played integer Total number of times this hand has been played
---@field played_this_round integer Number of times this hand has been played this round
---@field visible boolean? Whether this poker hand type is unlocked/visible (Obelisk checks)
---@field example table<integer, table> Example cards showing what makes this hand (array of [card_key, is_scored])

---@class Round
---@field hands_left integer? Number of hands remaining in this round
---@field hands_played integer? Number of hands played in this round
---@field discards_left integer? Number of discards remaining in this round
---@field discards_used integer? Number of discards used in this round
---@field reroll_cost integer? Current cost to reroll the shop
---@field chips integer? Current chips scored in this round
---@field boss_reroll_cost integer? Cost to reroll Boss blind ($10 with Director's Cut / Retcon)
---@field boss_reroll_available boolean? True when reroll_boss API action is allowed now
---@field boss_rerolled boolean? True when Boss reroll was already used this ante (Director's Cut)
---@field ancient_suit Card.Value.Suit? Suit scored by Ancient Joker this round (changes end of round)
---@field idol_rank Card.Value.Rank? Rank scored by The Idol this round
---@field idol_suit Card.Value.Suit? Suit scored by The Idol this round
---@field castle_suit Card.Value.Suit? Suit that Castle gains chips from when discarded
---@field cashout_preview CashoutPreview? Round-end income preview (ROUND_EVAL, round won)

---@class CashoutLine
---@field kind string blind|hands|discards|joker|tag|interest|rental|bonus
---@field label string
---@field dollars integer signed (+ income, - cost)
---@field key string? joker/tag key when relevant

---@class CashoutPreview
---@field lines CashoutLine[]
---@field total integer Pending cash_out dollars (excludes investment_received)
---@field investment_received integer? Investment Tag paid on boss defeat (not in total)

---@class Blind
---@field type Blind.Type Type of the blind
---@field status Blind.Status Status of the bilnd
---@field name string Name of the blind (e.g., "Small", "Big" or the Boss name)
---@field effect string Description of the blind's effect
---@field score integer Score requirement to beat this blind
---@field tag_name string? Display name of the tag associated with this blind (Small/Big only)
---@field tag_key string? Stable tag id (Small/Big only); use for logic, not tag_name
---@field tag_effect string? Description of the tag's effect (Small/Big only)

---@class Area
---@field count integer Current number of cards in this area
---@field limit integer Maximum number of cards allowed in this area
---@field highlighted_limit integer? Maximum number of cards that can be highlighted (hand area only)
---@field choices_remaining integer? Selections still required from open booster (pack area only)
---@field cards Card[] Array of cards in this area

---@class Card
---@field id integer Unique identifier for the card (sort_id)
---@field key Card.Key Specific card key (e.g., "c_fool", "j_brainstorm, "v_overstock", ...)
---@field set Card.Set Card set/type
---@field label string Display label/name of the card
---@field value Card.Value Value information for the card
---@field modifier Card.Modifier Modifier information (seals, editions, enhancements)
---@field state Card.State Current state information (debuff, hidden, highlighted, forced selection)
---@field cost Card.Cost Cost information (buy/sell prices)

---@class Card.Value
---@field suit Card.Value.Suit? Suit (Hearts, Diamonds, Clubs, Spades) - only for playing cards
---@field rank Card.Value.Rank? Rank - only for playing cards
---@field effect string Description of the card's effect (from UI)
---@field copy_key string? For The Fool: key of the last Tarot/Planet used
---@field copy_set string? For The Fool: set of the last Tarot/Planet used
---@field copy_label string? For The Fool: display label of the last Tarot/Planet used
---@field stats Card.Value.Stats? Joker scoring snapshot (jokers only; locale-independent)
---@field rarity Card.Value.Rarity? Joker rarity (jokers only)

---@alias Card.Value.Rarity "COMMON" | "UNCOMMON" | "RARE" | "LEGENDARY"

---@class Card.Value.Stats
---@field mult integer? Additive Mult for joker_main
---@field chips integer? Additive chips for joker_main
---@field x_mult number? Multiplicative Mult for joker_main
---@field seltzer_remaining integer? Seltzer hands remaining
---@field steel_tally integer? Steel cards in full deck (Steel Joker)
---@field stone_tally integer? Stone cards in full deck (Stone Joker)
---@field driver_tally integer? Modified cards in deck (Driver's License)
---@field loyalty_every integer? Loyalty Card hands between ×Mult procs
---@field loyalty_remaining integer? Loyalty Card countdown
---@field loyalty_x_mult number? Loyalty Card ×Mult proc value
---@field obelisk_step number? Obelisk increment per non-dominant hand
---@field ride_the_bus_step integer? Ride the Bus increment per no-face hand
---@field green_hand_add integer? Green Joker +Mult per hand played
---@field nine_tally integer? Nines in deck (Cloud 9 round-end payout)
---@field rocket_dollars integer? Rocket current round-end payout

---@class RunCounters
---@field skips integer Blinds skipped this run
---@field deck_size integer Cards currently in the full deck
---@field starting_deck_size integer Deck size at run start
---@field tarot_used integer Tarot cards used this run

---@class Card.Modifier
---@field seal Card.Modifier.Seal? Seal type (playing cards)
---@field edition Card.Modifier.Edition? Edition type (jokers, playing cards and NEGATIVE consumables)
---@field enhancement Card.Modifier.Enhancement? Enhancement type (playing cards)
---@field eternal boolean? If true, card cannot be sold or destroyed (jokers only)
---@field perishable integer? Number of rounds remaining (only if > 0) (jokers only)
---@field rental boolean? If true, card costs money at end of round (jokers only)

---@class Card.State
---@field debuff boolean? If true, card is debuffed and won't score
---@field hidden boolean? If true, card is face down (facing == "back")
---@field highlight boolean? If true, card is currently highlighted
---@field forced_selection boolean? If true, card is forced selected by a Boss blind (Cerulean Bell)

---@class Card.Cost
---@field sell integer Sell value of the card
---@field buy integer Buy price of the card (if in shop)

-- ==========================================================================
-- Endpoint Types
--
-- The endpoints are registered at initialization. The dispatcher will redirect
-- requests to the correct endpoint based on the Request.Endpoint.Method (and
-- Request.Endpoint.Test.Method). The validator check that the game is in the
-- correct state and check that the provided Request.Endpoint.Params follow the
-- endpoint schema. Finally, the endpoint execute function is called with the
-- Request.Endpoint.Params (or Request.Endpoint.Test.Params).
-- ==========================================================================

---@class Endpoint
---@field name string The endpoint name
---@field description string Brief description of the endpoint
---@field schema table<string, Endpoint.Schema> Schema definition for arguments validation
---@field requires_state integer[]? Optional list of required game states
---@field execute fun(args: Request.Endpoint.Params | Request.Endpoint.Test.Params, send_response: fun(response: Response.Endpoint)) Execute function

---@class Endpoint.Schema
---@field type "string"|"integer"|"array"|"boolean"|"table"
---@field required boolean?
---@field items "integer"?
---@field description string

-- ==========================================================================
-- Server Request Type
--
-- The Request.Server is the JSON-RPC 2.0 request received by the server and
-- used by the dispatcher to call the right endpoint with the correct
-- arguments.
-- ==========================================================================

---@class Request.Server
---@field jsonrpc "2.0"
---@field method Request.Endpoint.Method | Request.Endpoint.Test.Method Request method name.
---@field params Request.Endpoint.Params | Request.Endpoint.Test.Params Params to use for the requests
---@field id integer|string Request ID (required)

-- ==========================================================================
-- Endpoint Request Types
--
-- The Request.Endpoint.Method (and Request.Endpoint.Test.Method) specifies
-- the endpoint name. The Request.Endpoint.Params (and Request.Endpoint.Test.Params)
-- contains the arguments to use in the endpoint execute function.
-- ==========================================================================

---@alias Request.Endpoint.Method
---| "add" | "buy" | "cash_out" | "discard" | "endless" | "gamestate" | "health" | "load"
---| "menu" | "next_round" | "play" | "rearrange" | "reroll" | "save"
---| "screenshot" | "select" | "sell" | "set" | "skip" | "sort" | "start" | "use"
---| "challenge" | "challenges"

---@alias Request.Endpoint.Test.Method
---| "echo" | "endpoint" | "error" | "state" | "validation"

---@alias Request.Endpoint.Params
---| Request.Endpoint.Add.Params
---| Request.Endpoint.Buy.Params
---| Request.Endpoint.CashOut.Params
---| Request.Endpoint.Challenge.Params
---| Request.Endpoint.Challenges.Params
---| Request.Endpoint.Discard.Params
---| Request.Endpoint.Gamestate.Params
---| Request.Endpoint.Health.Params
---| Request.Endpoint.Load.Params
---| Request.Endpoint.Menu.Params
---| Request.Endpoint.NextRound.Params
---| Request.Endpoint.Pack.Params
---| Request.Endpoint.Play.Params
---| Request.Endpoint.Rearrange.Params
---| Request.Endpoint.Reroll.Params
---| Request.Endpoint.Save.Params
---| Request.Endpoint.Screenshot.Params
---| Request.Endpoint.Select.Params
---| Request.Endpoint.Sell.Params
---| Request.Endpoint.Set.Params
---| Request.Endpoint.Skip.Params
---| Request.Endpoint.Sort.Params
---| Request.Endpoint.Start.Params
---| Request.Endpoint.Use.Params

---@alias Request.Endpoint.Test.Params
---| Request.Endpoint.Test.Echo.Params
---| Request.Endpoint.Test.Endpoint.Params
---| Request.Endpoint.Test.Error.Params
---| Request.Endpoint.Test.State.Params
---| Request.Endpoint.Test.Validation.Params
---| Request.Endpoint.Test.ChallengeProfile.Params

-- ==========================================================================
-- Endpoint Response Types
--
-- The execute function terminates by calling the `send_response` callback.
-- Endpoints send simplified Response.Endpoint (not JSON-RPC 2.0 compliant).
-- The server automatically converts these to JSON-RPC 2.0 Response.Server:
--   - Success: Response.Endpoint → Response.Server.Success with result field
--   - Error: { message, name } → Response.Server.Error with error.code/message/data
--   - Auto-converts name (e.g., "BAD_REQUEST") to numeric code (e.g., -32001)
-- ==========================================================================

---@class Response.Endpoint.Path
---@field success boolean Whether the request was successful
---@field path string Path to the file

---@class Response.Endpoint.Health
---@field status "ok"

---@alias Response.Endpoint.GameState
---| GameState # Return the current game state of the game

---@class Response.Endpoint.Challenges
---@field challenges table[] Native challenge catalog

---@class Response.Endpoint.Test
---@field success boolean Whether the request was successful
---@field received_args table? Arguments received by the endpoint (for test endpoints)
---@field state_validated boolean? Whether the state was validated (for test endpoints)

---@class Response.Endpoint.Error
---@field message string Human-readable error message
---@field name ErrorName Error name (e.g., "BAD_REQUEST") - auto-converted to numeric code by server

---@alias Response.Endpoint
---| Response.Endpoint.Health
---| Response.Endpoint.Path
---| Response.Endpoint.GameState
---| Response.Endpoint.Challenges
---| Response.Endpoint.Test
---| Response.Endpoint.Error

-- ==========================================================================
-- Server Response Types
--
-- The server's `send_response` transforms Response.Endpoint into JSON-RPC 2.0
-- compliant Response.Server returned to the client. For errors, it converts:
--   Response.Endpoint.Error.name → Response.Server.Error.error.code (numeric)
--   Response.Endpoint.Error.name → Response.Server.Error.error.data.name (string)
-- ==========================================================================

---@class Response.Server.Success
---@field jsonrpc "2.0"
---@field result Response.Endpoint.Health | Response.Endpoint.Path | Response.Endpoint.GameState | Response.Endpoint.Challenges | Response.Endpoint.Test Response payload
---@field id integer|string Request ID (echoed from request)

---@class Response.Server.Error
---@field jsonrpc "2.0"
---@field error Response.Server.Error.Error Response error
---@field id integer|string|nil Request ID (null only if request was unparseable)

---@class Response.Server.Error.Error
---@field code ErrorCode Numeric error code following JSON-RPC 2.0 convention
---@field message string Human-readable error message
---@field data table<'name', ErrorName> Semantic error code

---@alias Response.Server
---| Response.Server.Success
---| Response.Server.Error

-- ==========================================================================
-- Error Types
-- ==========================================================================

---@alias ErrorName
---| "BAD_REQUEST" Client sent invalid data (protocol/parameter errors)
---| "INVALID_STATE" Action not allowed in current game state
---| "NOT_ALLOWED" Game rules prevent this action
---| "INTERNAL_ERROR" Server-side failure (runtime/execution errors)

---@alias ErrorCode
---| -32000 # INTERNAL_ERROR
---| -32001 # BAD_REQUEST
---| -32002 # INVALID_STATE
---| -32003 # NOT_ALLOWED

---@alias ErrorNames table<ErrorName, ErrorName>
---@alias ErrorCodes table<ErrorName, ErrorCode>

-- ==========================================================================
-- Core Infrastructure Types
-- ==========================================================================

---@class Settings
---@field host string Hostname for the HTTP server (default: "127.0.0.1")
---@field port integer Port number for the HTTP server (default: 12346)
---@field headless boolean Whether to run in headless mode (minimizes window, disables rendering)
---@field fast boolean Whether to run in fast mode (unlimited FPS, 10x game speed, 60 FPS animations)
---@field render_on_api boolean Whether to render frames only on API calls (mutually exclusive with headless)
---@field audio boolean Whether to play audio (enables sound thread and sets volume levels)
---@field debug boolean Whether debug mode is enabled (requires DebugPlus mod)
---@field force_english boolean Whether to force en-us UI (integration tests only)
---@field no_shaders boolean Whether to disable all shaders for better performance (causes visual glitches)
---@field fps_cap integer Maximum FPS cap for the game (default: 60)
---@field gamespeed integer Game speed multiplier (default: 4)
---@field animation_fps integer Animation FPS (default: 10)
---@field no_reduced_motion boolean Whether to disable reduced motion for faster animations
---@field pixel_art_smoothing boolean Whether to enable pixel art smoothing (texture_scaling = 2)
---@field setup fun()? Initialize and apply all BlindDeck settings

---@class Debug
---@field log table? DebugPlus logger instance with debug/info/error methods (nil if DebugPlus not available)
---@field setup fun()? Initialize DebugPlus integration if available

---@class Server
---@field host string Hostname for the HTTP server (copied from Settings)
---@field port integer Port number for the HTTP server (copied from Settings)
---@field server_socket TCPSocketServer? Underlying TCP socket listening for HTTP connections (nil if not initialized)
---@field client_socket TCPSocketClient? Underlying TCP socket for the connected HTTP client (nil if no client connected)
---@field current_request_id integer|string|nil Current JSON-RPC 2.0 request ID being processed (nil if no active request)
---@field client_state table? HTTP request parsing state for current client (buffer, headers, etc.) (nil if no client connected)
---@field openrpc_spec string? OpenRPC specification JSON string (loaded at init, nil before init)
---@field init? fun(): boolean Initialize HTTP server socket and load OpenRPC spec
---@field accept? fun(): boolean Accept new HTTP client connection
---@field send_response? fun(response: Response.Endpoint): boolean Send JSON-RPC 2.0 response over HTTP to client
---@field update? fun(dispatcher: Dispatcher) Main update loop - parse HTTP requests and dispatch JSON-RPC calls each frame
---@field close? fun() Close HTTP server and all connections

---@class Dispatcher
---@field endpoints table<string, Endpoint> Map of endpoint names to Endpoint definitions (registered at initialization)
---@field Server Server? Reference to the Server module for sending responses (set during initialization)
---@field register? fun(endpoint: Endpoint): boolean, string? Register a new endpoint (returns success, error_message)
---@field load_endpoints? fun(endpoint_files: string[]): boolean, string? Load and register endpoints from files (returns success, error_message)
---@field init? fun(server_module: table, endpoint_files: string[]?): boolean Initialize dispatcher with server reference and endpoint files
---@field send_error? fun(message: string, error_code: string) Send error response using server
---@field dispatch? fun(parsed: Request.Server) Dispatch JSON-RPC request to appropriate endpoint

---@class Validator
---@field validate fun(args: table, schema: table<string, Endpoint.Schema>): boolean, string?, string? Validates endpoint arguments against schema (returns success, error_message, error_code)
