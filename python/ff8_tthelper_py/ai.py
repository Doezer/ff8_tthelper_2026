"""Full-depth alpha-beta minimax Triple Triad AI. Ported from AI.fs.

`AI.fs`'s `evaluateNode`/`evaluateGridSlot` (a positional heuristic) are
dead code in the original - `alphaBeta`'s leaf evaluation actually calls
`cardBalance`, not `evaluateNode`, and nothing else calls it either. It
was left out here rather than ported for no purpose.

Everything else - including the exact move-generation order and the
capture/cascade rules for Same/SameWall/Plus - is ported faithfully,
since it's what the game-tree search and its "guaranteed win" property
depend on. `AI.fs` also pre-allocates and reuses grid/hand buffers across
recursive calls purely to reduce .NET GC pressure; that's a performance
detail with no behavioral effect, so this port just allocates normally.
"""

from __future__ import annotations

from dataclasses import replace
from typing import List, Optional, Tuple

from .domain_types import (
    OPPONENTS_TURN,
    Card,
    GameState,
    Hand,
    PlayGrid,
    PlayGridSlot,
    Player,
    Rule,
    Rules,
    TurnPhase,
    TurnPhaseKind,
)

Move = Tuple[int, int]  # (hand_index, grid_index 0..8)
Powers = Tuple[int, int, int, int]

_INT32_MIN = -2147483648
_INT32_MAX = 2147483647


def is_terminal_node(node: GameState) -> bool:
    return node.my_hand[4] is None or node.op_hand[4] is None


def _count_hand_cards(hand: Hand) -> int:
    first_full_index = next((i for i, c in enumerate(hand) if c is not None), None)
    return 5 - first_full_index if first_full_index is not None else 0


def _empty_neighbors(node: GameState, gi: int) -> List[Tuple[int, int]]:
    candidates = ((gi - 3, 0), (gi - 1, 1), (gi + 1, 2), (gi + 3, 3))
    return [
        (ngi, power_index)
        for ngi, power_index in candidates
        if 0 <= ngi <= 8
        and ((gi % 3 == ngi % 3) != (gi // 3 == ngi // 3))  # row xor col changed, not both
        and node.play_grid[ngi].is_empty
    ]


def _can_card_be_captured(
    node: GameState, other_player_max_powers: List[Powers], grid_index: int, grid_slot: PlayGridSlot
) -> bool:
    return any(
        other_player_max_powers[neighbor_index][3 - power_index] > grid_slot.card.powers[power_index]
        for neighbor_index, power_index in _empty_neighbors(node, grid_index)
    )


def _card_powers_in_grid_slot_with_element(card: Card, slot_elem) -> Powers:
    if slot_elem is None:
        return card.powers
    return tuple((p + 1) if card.element == slot_elem else (p - 1) for p in card.powers)  # type: ignore[return-value]


def _max_powers_in_grid_slot_with_elem(hand: Hand, elem) -> Powers:
    # NB: matches AI.fs's `maxPowersInGridSlotWithElem` exactly, including that despite its
    # name it does *not* take an elementwise max - it's an Array.fold that discards the
    # accumulator on every Some, so the result is just the last hand card's (transformed)
    # powers. Ported as-is since AITest.fs's expectations were written against this behavior.
    max_ps: Powers = (-1, -1, -1, -1)
    for card in hand:
        if card is not None:
            max_ps = _card_powers_in_grid_slot_with_element(card, elem)
    return max_ps


def _hand_max_powers_in_empty_grid_slots(node: GameState, hand: Hand) -> List[Powers]:
    result = []
    for slot in node.play_grid.slots:
        if slot.is_full:
            result.append(())
        else:
            result.append(_max_powers_in_grid_slot_with_elem(hand, slot.element))
    return result


def card_balance(node: GameState) -> int:
    grid_balance = sum(
        0 if slot.is_empty else (1 if slot.card.owner is Player.ME else -1)
        for slot in node.play_grid.slots
    )
    return grid_balance + _count_hand_cards(node.my_hand) - _count_hand_cards(node.op_hand)


def _hand_without(hand_index: int, hand: Hand) -> Hand:
    new_hand: Hand = [None] * 5
    if hand_index < 4:
        new_hand[hand_index + 1:5] = hand[hand_index + 1:5]
    new_hand[1:hand_index + 1] = hand[0:hand_index]
    new_hand[0] = None
    return new_hand


def _neighbor_index_if_exists(play_grid: PlayGrid, gi: int, direction: int) -> int:
    if direction == 0:
        return gi - 3 if gi >= 3 and play_grid[gi - 3].is_full else -1
    if direction == 1:
        return gi - 1 if gi not in (0, 3, 6) and play_grid[gi - 1].is_full else -1
    if direction == 2:
        return gi + 1 if gi not in (2, 5, 8) and play_grid[gi + 1].is_full else -1
    return gi + 3 if gi <= 5 and play_grid[gi + 3].is_full else -1


def _get_cascading_neighbor_indexes(play_grid: PlayGrid, rules: Rules, gi: int, new_card: Card) -> List[int]:
    casc_indexes: List[int] = []

    if rules.has(Rule.SAME) or rules.has(Rule.SAME_WALL):
        for direction in (0, 1, 2, 3):
            neighbor_index = _neighbor_index_if_exists(play_grid, gi, direction)
            if neighbor_index >= 0 and play_grid[neighbor_index].card.powers[3 - direction] == new_card.powers[direction]:
                casc_indexes.insert(0, neighbor_index)

        same_wall_applies = rules.has(Rule.SAME_WALL) and (
            (gi in (0, 1, 2) and new_card.powers[0] == 10)
            or (gi in (0, 3, 6) and new_card.powers[1] == 10)
            or (gi in (2, 5, 8) and new_card.powers[2] == 10)
            or (gi in (6, 7, 8) and new_card.powers[3] == 10)
        )
        if len(casc_indexes) == 1 and not same_wall_applies:
            casc_indexes = []

    if rules.has(Rule.PLUS):
        casc_indexes_before_plus = list(casc_indexes)

        def power_sum(direction: int) -> int:
            neighbor_index = _neighbor_index_if_exists(play_grid, gi, direction)
            if neighbor_index >= 0:
                return play_grid[neighbor_index].card.powers[3 - direction] + new_card.powers[direction]
            return -1

        p0, p1, p2, p3 = power_sum(0), power_sum(1), power_sum(2), power_sum(3)
        if p0 >= 0 and (p0 == p1 or p0 == p2 or p0 == p3):
            casc_indexes.insert(0, gi - 3)
        if p1 >= 0 and (p1 == p0 or p1 == p2 or p1 == p3):
            casc_indexes.insert(0, gi - 1)
        if p2 >= 0 and (p2 == p0 or p2 == p1 or p2 == p3):
            casc_indexes.insert(0, gi + 1)
        if p3 >= 0 and (p3 == p0 or p3 == p1 or p3 == p2):
            casc_indexes.insert(0, gi + 3)
        if len(casc_indexes) - len(casc_indexes_before_plus) < 2:
            casc_indexes = casc_indexes_before_plus

    return casc_indexes


def _update_play_grid(play_grid: PlayGrid, rules: Rules, gi: int, new_card: Card) -> PlayGrid:
    new_play_grid = play_grid.copy()

    target_slot = play_grid[gi]
    if target_slot.element is None:
        updated_card = new_card
    else:
        modifier = 1 if target_slot.element == new_card.element else -1
        updated_card = replace(new_card, power_modifier=modifier)
    new_play_grid[gi] = PlayGridSlot.full(updated_card)

    new_card_owner = new_card.owner

    def update_neighbor(base_gi: int, neighbor_index: int, this_power_index: int, cascade: bool) -> None:
        neighbor_slot = new_play_grid[neighbor_index]
        if neighbor_slot.card.owner != new_card_owner:
            updated_new_card = new_play_grid[base_gi].card
            neighbor_power = neighbor_slot.card.modified_power(3 - this_power_index)
            if neighbor_power < updated_new_card.modified_power(this_power_index):
                new_play_grid[neighbor_index] = neighbor_slot.with_opposite_card_owner
                if cascade:
                    update_neighbors(neighbor_index, True)

    def update_neighbors(gi2: int, cascade: bool) -> None:
        if _neighbor_index_if_exists(play_grid, gi2, 0) >= 0:
            update_neighbor(gi2, gi2 - 3, 0, cascade)
        if _neighbor_index_if_exists(play_grid, gi2, 1) >= 0:
            update_neighbor(gi2, gi2 - 1, 1, cascade)
        if _neighbor_index_if_exists(play_grid, gi2, 2) >= 0:
            update_neighbor(gi2, gi2 + 1, 2, cascade)
        if _neighbor_index_if_exists(play_grid, gi2, 3) >= 0:
            update_neighbor(gi2, gi2 + 3, 3, cascade)

    for neighbor_index in _get_cascading_neighbor_indexes(play_grid, rules, gi, new_card):
        if new_play_grid[neighbor_index].card.owner != new_card_owner:
            new_play_grid[neighbor_index] = new_play_grid[neighbor_index].with_opposite_card_owner
            update_neighbors(neighbor_index, True)

    update_neighbors(gi, False)  # normal strength based capture

    return new_play_grid


def execute_move(node: GameState, rules: Rules, move: Move) -> GameState:
    hand_index, play_grid_index = move
    is_maximizing_player = node.turn_phase.kind != TurnPhaseKind.OPPONENTS_TURN
    new_turn_phase = OPPONENTS_TURN if is_maximizing_player else TurnPhase.my_card_selection(4)
    new_op_hand = node.op_hand if is_maximizing_player else _hand_without(hand_index, node.op_hand)
    new_my_hand = node.my_hand if not is_maximizing_player else _hand_without(hand_index, node.my_hand)
    source_hand = node.my_hand if is_maximizing_player else node.op_hand

    new_play_grid = _update_play_grid(node.play_grid, rules, play_grid_index, source_hand[hand_index])
    return GameState(turn_phase=new_turn_phase, my_hand=new_my_hand, op_hand=new_op_hand, play_grid=new_play_grid)


def _child_states(node: GameState, rules: Rules) -> List[Tuple[Move, GameState]]:
    is_maximizing_player = node.turn_phase.kind != TurnPhaseKind.OPPONENTS_TURN
    source_hand = node.my_hand if is_maximizing_player else node.op_hand

    valid_moves = [
        (hi, gi)
        for hi in range(5)
        for gi in range(9)
        if source_hand[hi] is not None and node.play_grid[gi].is_empty
    ]
    moves_with_states = [(move, execute_move(node, rules, move)) for move in valid_moves]

    if is_maximizing_player and source_hand[0] is not None:
        def sort_key(move_and_state: Tuple[Move, GameState]) -> int:
            (_, gi), s = move_and_state
            can_be_captured = _can_card_be_captured(
                s, _hand_max_powers_in_empty_grid_slots(s, s.op_hand), gi, s.play_grid[gi]
            )
            return 1 if can_be_captured else -1

        moves_with_states.sort(key=sort_key)  # stable, matches Array.sortInPlaceBy

    return moves_with_states


def _alpha_beta(
    node: GameState, rules: Rules, is_trade_one: bool, depth: int, alpha: int, beta: int
) -> Tuple[Move, int]:
    if depth == 0 or is_terminal_node(node):
        bal = card_balance(node)
        value = min(1, max(bal, -1)) if is_trade_one else bal
        return (-1, -1), value

    children = _child_states(node, rules)

    if node.turn_phase.kind != TurnPhaseKind.OPPONENTS_TURN:
        v = _INT32_MIN
        best_move: Move = (-1, -1)
        alpha2 = alpha
        for move, child in children:
            if beta <= alpha2:
                break
            new_v = _alpha_beta(child, rules, is_trade_one, depth - 1, alpha2, beta)[1]
            if new_v > v:
                v, best_move = new_v, move
                alpha2 = max(alpha2, new_v)
        return best_move, v
    else:
        v = _INT32_MAX
        best_move = (-1, -1)
        beta2 = beta
        for move, child in children:
            if beta2 <= alpha:
                break
            new_v = _alpha_beta(child, rules, is_trade_one, depth - 1, alpha, beta2)[1]
            if new_v < v:
                v, best_move = new_v, move
                beta2 = min(beta2, new_v)
        return best_move, v


def get_best_move(node: GameState, rules: Rules, depth: int) -> Tuple[Move, int]:
    return _alpha_beta(node, rules, rules.has(Rule.TRADE_ONE), depth, _INT32_MIN, _INT32_MAX)
