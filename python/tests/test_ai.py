"""Ported from AITest.fs - executeMove correctness across Same/SameWall/Plus rule combos."""

import pytest

from ff8_tthelper_py.ai import execute_move
from ff8_tthelper_py.domain_types import (
    GameState,
    PlayGrid,
    Player,
    Rule,
    Rules,
    TurnPhase,
    OPPONENTS_TURN,
)

from .helpers import e, empty_slot, empty_slot_elem, f, hc, n, pc, pce, u

Me = Player.ME
Op = Player.OP

CASES = [
    dict(
        comment="basic capture",
        before=GameState(
            turn_phase=TurnPhase.my_card_selection(0),
            my_hand=[hc([9, 9, 5, 2], Me, e), hc([5, 9, 1, 9], Me, e), hc([9, 8, 6, 2], Me, f),
                     hc([1, 7, 8, 7], Me, n), hc([8, 4, 8, 5], Me, n)],
            op_hand=[None, hc([4, 7, 6, 2], Op, n), hc([2, 7, 3, 6], Op, n), hc([6, 5, 5, 4], Op, n),
                     hc([3, 6, 7, 3], Op, n)],
            play_grid=PlayGrid([
                pc([1, 7, 6, 4], Op, 0), empty_slot, empty_slot_elem(e),
                empty_slot, empty_slot, empty_slot,
                empty_slot, empty_slot, empty_slot,
            ]),
        ),
        rules=Rules.none(),
        move=(0, 1),
        after=GameState(
            turn_phase=OPPONENTS_TURN,
            my_hand=[None, hc([5, 9, 1, 9], Me, e), hc([9, 8, 6, 2], Me, f), hc([1, 7, 8, 7], Me, n),
                     hc([8, 4, 8, 5], Me, n)],
            op_hand=[None, hc([4, 7, 6, 2], Op, n), hc([2, 7, 3, 6], Op, n), hc([6, 5, 5, 4], Op, n),
                     hc([3, 6, 7, 3], Op, n)],
            play_grid=PlayGrid([
                pc([1, 7, 6, 4], Me, 0), pce([9, 9, 5, 2], Me, 0, e), empty_slot_elem(e),
                empty_slot, empty_slot, empty_slot,
                empty_slot, empty_slot, empty_slot,
            ]),
        ),
    ),
    dict(
        comment="same rule triggered on 2/3 neighbors, third neighbor captured normally",
        before=GameState(
            turn_phase=TurnPhase.my_card_selection(4),
            my_hand=[None, None, None, None, hc([2, 8, 5, 2], Me, e)],
            op_hand=[None, None, None, None, hc([1, 5, 3, 3], Op, n)],
            play_grid=PlayGrid([
                pc([5, 4, 9, 7], Op, 0), pc([1, 7, 8, 3], Me, 0), pc([1, 7, 6, 4], Op, 0),
                pc([7, 8, 7, 8], Op, 1), pc([4, 7, 6, 2], Op, 0), pc([5, 6, 1, 9], Op, 0),
                pc([10, 4, 8, 5], Op, 0), empty_slot, pc([9, 4, 6, 2], Op, 0),
            ]),
        ),
        rules=Rules.only(Rule.SAME),
        move=(4, 7),
        after=GameState(
            turn_phase=OPPONENTS_TURN,
            my_hand=[None, None, None, None, None],
            op_hand=[None, None, None, None, hc([1, 5, 3, 3], Op, n)],
            play_grid=PlayGrid([
                pc([5, 4, 9, 7], Me, 0), pc([1, 7, 8, 3], Me, 0), pc([1, 7, 6, 4], Op, 0),
                pc([7, 8, 7, 8], Me, 1), pc([4, 7, 6, 2], Me, 0), pc([5, 6, 1, 9], Op, 0),
                pc([10, 4, 8, 5], Me, 0), pce([2, 8, 5, 2], Me, 0, e), pc([9, 4, 6, 2], Me, 0),
            ]),
        ),
    ),
    dict(
        comment="same rule triggered on 2/3 neighbors, third neighbor not captured",
        before=GameState(
            turn_phase=TurnPhase.my_card_selection(4),
            my_hand=[None, None, None, None, hc([2, 8, 5, 2], Me, e)],
            op_hand=[None, None, None, None, hc([1, 5, 3, 3], Op, n)],
            play_grid=PlayGrid([
                pc([5, 4, 9, 7], Op, 0), pc([1, 7, 8, 3], Me, 0), pc([1, 7, 6, 4], Op, 0),
                pc([7, 8, 7, 8], Op, 1), pc([4, 7, 6, 2], Op, 0), pc([5, 6, 1, 9], Op, 0),
                pc([10, 4, 8, 5], Op, 0), empty_slot, pc([9, 6, 6, 2], Op, 0),
            ]),
        ),
        rules=Rules.only(Rule.SAME),
        move=(4, 7),
        after=GameState(
            turn_phase=OPPONENTS_TURN,
            my_hand=[None, None, None, None, None],
            op_hand=[None, None, None, None, hc([1, 5, 3, 3], Op, n)],
            play_grid=PlayGrid([
                pc([5, 4, 9, 7], Me, 0), pc([1, 7, 8, 3], Me, 0), pc([1, 7, 6, 4], Op, 0),
                pc([7, 8, 7, 8], Me, 1), pc([4, 7, 6, 2], Me, 0), pc([5, 6, 1, 9], Op, 0),
                pc([10, 4, 8, 5], Me, 0), pce([2, 8, 5, 2], Me, 0, e), pc([9, 6, 6, 2], Op, 0),
            ]),
        ),
    ),
    dict(
        comment="same rule triggered on 3/3 neighbors",
        before=GameState(
            turn_phase=TurnPhase.my_card_selection(4),
            my_hand=[None, None, None, None, hc([2, 8, 5, 2], Me, e)],
            op_hand=[None, None, None, None, hc([1, 5, 3, 3], Op, n)],
            play_grid=PlayGrid([
                pc([5, 4, 9, 7], Op, 0), pc([1, 7, 8, 3], Me, 0), pc([1, 7, 6, 6], Op, 0),
                pc([7, 8, 7, 8], Op, 1), pc([4, 7, 6, 2], Op, 0), pc([5, 6, 1, 8], Op, 0),
                pc([10, 4, 8, 5], Op, 0), empty_slot, pc([9, 5, 6, 2], Op, 0),
            ]),
        ),
        rules=Rules.only(Rule.SAME),
        move=(4, 7),
        after=GameState(
            turn_phase=OPPONENTS_TURN,
            my_hand=[None, None, None, None, None],
            op_hand=[None, None, None, None, hc([1, 5, 3, 3], Op, n)],
            play_grid=PlayGrid([
                pc([5, 4, 9, 7], Me, 0), pc([1, 7, 8, 3], Me, 0), pc([1, 7, 6, 6], Op, 0),
                pc([7, 8, 7, 8], Me, 1), pc([4, 7, 6, 2], Me, 0), pc([5, 6, 1, 8], Me, 0),
                pc([10, 4, 8, 5], Me, 0), pce([2, 8, 5, 2], Me, 0, e), pc([9, 5, 6, 2], Me, 0),
            ]),
        ),
    ),
    dict(
        comment="same rule triggered on 4/4 neighbors",
        before=GameState(
            turn_phase=OPPONENTS_TURN,
            my_hand=[None, None, hc([9, 8, 6, 2], Me, u), hc([1, 7, 8, 7], Me, u), hc([8, 4, 8, 5], Me, u)],
            op_hand=[None, None, hc([4, 5, 3, 4], Op, u), hc([6, 5, 5, 4], Op, u), hc([3, 6, 7, 3], Op, u)],
            play_grid=PlayGrid([
                empty_slot, pc([9, 9, 5, 4], Me, 0), empty_slot,
                pc([1, 5, 5, 4], Me, 0), empty_slot, pc([5, 3, 1, 9], Me, 0),
                empty_slot, pc([4, 7, 3, 6], Me, 0), empty_slot,
            ]),
        ),
        rules=Rules.only(Rule.SAME),
        move=(2, 4),
        after=GameState(
            turn_phase=TurnPhase.my_card_selection(4),
            my_hand=[None, None, hc([9, 8, 6, 2], Me, u), hc([1, 7, 8, 7], Me, u), hc([8, 4, 8, 5], Me, u)],
            op_hand=[None, None, None, hc([6, 5, 5, 4], Op, u), hc([3, 6, 7, 3], Op, u)],
            play_grid=PlayGrid([
                empty_slot, pc([9, 9, 5, 4], Op, 0), empty_slot,
                pc([1, 5, 5, 4], Op, 0), pc([4, 5, 3, 4], Op, 0), pc([5, 3, 1, 9], Op, 0),
                empty_slot, pc([4, 7, 3, 6], Op, 0), empty_slot,
            ]),
        ),
    ),
    dict(
        comment="samewall rule triggered on 1 neighbor",
        before=GameState(
            turn_phase=OPPONENTS_TURN,
            my_hand=[None, None, hc([9, 8, 6, 2], Me, u), hc([1, 7, 8, 7], Me, u), hc([8, 4, 8, 5], Me, u)],
            op_hand=[None, None, hc([4, 3, 3, 10], Op, u), hc([6, 5, 5, 4], Op, u), hc([3, 6, 7, 3], Op, u)],
            play_grid=PlayGrid([
                empty_slot, pc([9, 9, 5, 4], Me, 0), empty_slot,
                pc([1, 5, 5, 4], Me, 0), empty_slot, pc([5, 3, 1, 9], Me, 0),
                empty_slot, pc([4, 7, 3, 6], Me, 0), empty_slot,
            ]),
        ),
        rules=Rules.having([Rule.SAME, Rule.SAME_WALL]),
        move=(2, 8),
        after=GameState(
            turn_phase=TurnPhase.my_card_selection(4),
            my_hand=[None, None, hc([9, 8, 6, 2], Me, u), hc([1, 7, 8, 7], Me, u), hc([8, 4, 8, 5], Me, u)],
            op_hand=[None, None, None, hc([6, 5, 5, 4], Op, u), hc([3, 6, 7, 3], Op, u)],
            play_grid=PlayGrid([
                empty_slot, pc([9, 9, 5, 4], Me, 0), empty_slot,
                pc([1, 5, 5, 4], Me, 0), empty_slot, pc([5, 3, 1, 9], Me, 0),
                empty_slot, pc([4, 7, 3, 6], Op, 0), pc([4, 3, 3, 10], Op, 0),
            ]),
        ),
    ),
    dict(
        comment="plus rule triggered on 2 neighbors",
        before=GameState(
            turn_phase=OPPONENTS_TURN,
            my_hand=[None, None, hc([9, 8, 6, 2], Me, u), hc([1, 7, 8, 7], Me, u), hc([8, 4, 8, 5], Me, u)],
            op_hand=[None, hc([2, 1, 3, 2], Op, u), hc([2, 7, 3, 6], Op, u), hc([6, 5, 5, 4], Op, u),
                     hc([3, 6, 7, 3], Op, u)],
            play_grid=PlayGrid([
                empty_slot, pc([9, 9, 5, 4], Me, 0), empty_slot,
                pc([1, 5, 5, 4], Me, 0), empty_slot, pc([5, 4, 1, 9], Me, 0),
                empty_slot, empty_slot, empty_slot,
            ]),
        ),
        rules=Rules.only(Rule.SAME).with_rule(Rule.PLUS),
        move=(1, 4),
        after=GameState(
            turn_phase=TurnPhase.my_card_selection(4),
            my_hand=[None, None, hc([9, 8, 6, 2], Me, u), hc([1, 7, 8, 7], Me, u), hc([8, 4, 8, 5], Me, u)],
            op_hand=[None, None, hc([2, 7, 3, 6], Op, u), hc([6, 5, 5, 4], Op, u), hc([3, 6, 7, 3], Op, u)],
            play_grid=PlayGrid([
                empty_slot, pc([9, 9, 5, 4], Op, 0), empty_slot,
                pc([1, 5, 5, 4], Op, 0), pc([2, 1, 3, 2], Op, 0), pc([5, 4, 1, 9], Me, 0),
                empty_slot, empty_slot, empty_slot,
            ]),
        ),
    ),
    dict(
        comment="plus rule triggered on 3 neighbors",
        before=GameState(
            turn_phase=OPPONENTS_TURN,
            my_hand=[None, None, hc([9, 8, 6, 2], Me, u), hc([1, 7, 8, 7], Me, u), hc([8, 4, 8, 5], Me, u)],
            op_hand=[None, hc([2, 1, 3, 2], Op, u), hc([2, 7, 3, 6], Op, u), hc([6, 5, 5, 4], Op, u),
                     hc([3, 6, 7, 3], Op, u)],
            play_grid=PlayGrid([
                empty_slot, pc([9, 9, 5, 4], Me, 0), empty_slot,
                pc([1, 5, 5, 4], Me, 0), empty_slot, pc([5, 3, 1, 9], Me, 0),
                empty_slot, empty_slot, empty_slot,
            ]),
        ),
        rules=Rules.having([Rule.SAME, Rule.PLUS]),
        move=(1, 4),
        after=GameState(
            turn_phase=TurnPhase.my_card_selection(4),
            my_hand=[None, None, hc([9, 8, 6, 2], Me, u), hc([1, 7, 8, 7], Me, u), hc([8, 4, 8, 5], Me, u)],
            op_hand=[None, None, hc([2, 7, 3, 6], Op, u), hc([6, 5, 5, 4], Op, u), hc([3, 6, 7, 3], Op, u)],
            play_grid=PlayGrid([
                empty_slot, pc([9, 9, 5, 4], Op, 0), empty_slot,
                pc([1, 5, 5, 4], Op, 0), pc([2, 1, 3, 2], Op, 0), pc([5, 3, 1, 9], Op, 0),
                empty_slot, empty_slot, empty_slot,
            ]),
        ),
    ),
    dict(
        comment="plus rule triggered on 4 neighbors (same sum on all 4)",
        before=GameState(
            turn_phase=OPPONENTS_TURN,
            my_hand=[None, None, hc([9, 8, 6, 2], Me, u), hc([1, 7, 8, 7], Me, u), hc([8, 4, 8, 5], Me, u)],
            op_hand=[None, None, hc([2, 1, 3, 2], Op, u), hc([6, 5, 5, 4], Op, u), hc([3, 6, 7, 3], Op, u)],
            play_grid=PlayGrid([
                empty_slot, pc([9, 9, 5, 4], Me, 0), empty_slot,
                pc([1, 5, 5, 4], Me, 0), empty_slot, pc([5, 3, 1, 9], Me, 0),
                empty_slot, pc([4, 7, 3, 6], Me, 0), empty_slot,
            ]),
        ),
        rules=Rules.having([Rule.SAME, Rule.PLUS]),
        move=(2, 4),
        after=GameState(
            turn_phase=TurnPhase.my_card_selection(4),
            my_hand=[None, None, hc([9, 8, 6, 2], Me, u), hc([1, 7, 8, 7], Me, u), hc([8, 4, 8, 5], Me, u)],
            op_hand=[None, None, None, hc([6, 5, 5, 4], Op, u), hc([3, 6, 7, 3], Op, u)],
            play_grid=PlayGrid([
                empty_slot, pc([9, 9, 5, 4], Op, 0), empty_slot,
                pc([1, 5, 5, 4], Op, 0), pc([2, 1, 3, 2], Op, 0), pc([5, 3, 1, 9], Op, 0),
                empty_slot, pc([4, 7, 3, 6], Op, 0), empty_slot,
            ]),
        ),
    ),
    dict(
        comment="plus rule triggered on 4 neighbors (2 different sums)",
        before=GameState(
            turn_phase=OPPONENTS_TURN,
            my_hand=[None, None, hc([9, 8, 6, 2], Me, u), hc([1, 7, 8, 7], Me, u), hc([8, 4, 8, 5], Me, u)],
            op_hand=[None, None, hc([2, 1, 3, 2], Op, u), hc([6, 5, 5, 4], Op, u), hc([3, 6, 7, 3], Op, u)],
            play_grid=PlayGrid([
                empty_slot, pc([9, 9, 5, 5], Me, 0), empty_slot,
                pc([1, 5, 5, 4], Me, 0), empty_slot, pc([5, 3, 1, 9], Me, 0),
                empty_slot, pc([5, 7, 3, 6], Me, 0), empty_slot,
            ]),
        ),
        rules=Rules.having([Rule.SAME, Rule.PLUS]),
        move=(2, 4),
        after=GameState(
            turn_phase=TurnPhase.my_card_selection(4),
            my_hand=[None, None, hc([9, 8, 6, 2], Me, u), hc([1, 7, 8, 7], Me, u), hc([8, 4, 8, 5], Me, u)],
            op_hand=[None, None, None, hc([6, 5, 5, 4], Op, u), hc([3, 6, 7, 3], Op, u)],
            play_grid=PlayGrid([
                empty_slot, pc([9, 9, 5, 5], Op, 0), empty_slot,
                pc([1, 5, 5, 4], Op, 0), pc([2, 1, 3, 2], Op, 0), pc([5, 3, 1, 9], Op, 0),
                empty_slot, pc([5, 7, 3, 6], Op, 0), empty_slot,
            ]),
        ),
    ),
    dict(
        comment="plus rule triggered on 2 neighbors, same triggered on 2",
        before=GameState(
            turn_phase=OPPONENTS_TURN,
            my_hand=[None, None, hc([9, 8, 6, 2], Me, u), hc([1, 7, 8, 7], Me, u), hc([8, 4, 8, 5], Me, u)],
            op_hand=[None, None, hc([2, 1, 5, 5], Op, u), hc([6, 5, 5, 4], Op, u), hc([3, 6, 7, 3], Op, u)],
            play_grid=PlayGrid([
                empty_slot, pc([9, 9, 5, 4], Me, 0), empty_slot,
                pc([1, 5, 5, 4], Me, 0), empty_slot, pc([5, 5, 1, 9], Me, 0),
                empty_slot, pc([5, 7, 3, 6], Me, 0), empty_slot,
            ]),
        ),
        rules=Rules.having([Rule.SAME, Rule.PLUS]),
        move=(2, 4),
        after=GameState(
            turn_phase=TurnPhase.my_card_selection(4),
            my_hand=[None, None, hc([9, 8, 6, 2], Me, u), hc([1, 7, 8, 7], Me, u), hc([8, 4, 8, 5], Me, u)],
            op_hand=[None, None, None, hc([6, 5, 5, 4], Op, u), hc([3, 6, 7, 3], Op, u)],
            play_grid=PlayGrid([
                empty_slot, pc([9, 9, 5, 4], Op, 0), empty_slot,
                pc([1, 5, 5, 4], Op, 0), pc([2, 1, 5, 5], Op, 0), pc([5, 5, 1, 9], Op, 0),
                empty_slot, pc([5, 7, 3, 6], Op, 0), empty_slot,
            ]),
        ),
    ),
]


@pytest.mark.parametrize("case", CASES, ids=[c["comment"] for c in CASES])
def test_execute_move(case):
    actual = execute_move(case["before"], case["rules"], case["move"])
    assert actual == case["after"], case["comment"]
