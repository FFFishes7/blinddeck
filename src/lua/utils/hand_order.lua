-- src/lua/utils/hand_order.lua

-- Utilities for making API argument order drive Balatro actions that normally
-- sort selected hand cards by their on-screen x position.

---@class HandOrderUtils
local M = {}

---@param indices integer[]
---@return fun()
function M.apply_arg_order(indices)
  local saved = {}
  local base_x = G.hand and G.hand.T and G.hand.T.x or 0

  for arg_pos, card_index in ipairs(indices) do
    local card = G.hand and G.hand.cards and G.hand.cards[card_index + 1]
    if card and card.T then
      saved[#saved + 1] = { card = card, x = card.T.x }
      card.T.x = base_x + (arg_pos * 0.001)
    end
  end

  return function()
    for _, item in ipairs(saved) do
      if item.card and item.card.T then
        item.card.T.x = item.x
      end
    end
  end
end

return M
