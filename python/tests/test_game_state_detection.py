"""Ported from GameStateDetectionTest.fs - validated against the real screenshots
checked into ff8_tthelper/screenshots/, so this exercises the actual pixel-offset
and template-diff logic, not just the algorithmic shape of it."""

import pytest

from ff8_tthelper_py.bitmap_helpers import SimpleBitmap
from ff8_tthelper_py.domain_types import (
    GamePhase,
    GameState,
    Player,
    PlayGrid,
    Rule,
    Rules,
    TurnPhase,
    OPPONENTS_TURN,
)
from ff8_tthelper_py.game_state_detection import (
    SCREENSHOT_DIR,
    read_game_phase,
    read_game_state,
    read_game_state_with_turn_phase,
    read_number_of_cards_on_card_choosing_screen,
    read_rules,
)

from .helpers import a, e, empty_slot, empty_slot_elem, f, h, hc, i, n, p, pc, t, w

Me = Player.ME
Op = Player.OP


def _load(relative_path: str) -> SimpleBitmap:
    return SimpleBitmap.from_file(str(SCREENSHOT_DIR / relative_path))


SCREENSHOT_GAME_STATES = [
    ("in-game/example_screenshot_1.jpg", GameState(
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
    )),
    ("in-game/example_screenshot_2.jpg", GameState(
        turn_phase=TurnPhase.my_card_selection(4),
        my_hand=[None, None, None, None, hc([9, 9, 5, 2], Me, e)],
        op_hand=[None, None, None, None, hc([1, 5, 3, 3], Op, n)],
        play_grid=PlayGrid([
            pc([5, 4, 5, 7], Op, -1), pc([1, 7, 8, 7], Me, 0), pc([1, 7, 6, 4], Op, 0),
            pc([7, 8, 7, 2], Me, 0), pc([4, 7, 6, 2], Me, 0), pc([5, 9, 1, 9], Me, 0),
            pc([8, 4, 8, 5], Me, 0), empty_slot, pc([9, 8, 6, 2], Me, 0),
        ]),
    )),
    ("in-game/example_screenshot_3.jpg", GameState(
        turn_phase=TurnPhase.my_card_selection(1),
        my_hand=[None, hc([9, 8, 6, 2], Me, f), hc([8, 8, 5, 2], Me, t), hc([1, 3, 8, 8], Me, p),
                 hc([7, 4, 8, 3], Me, w)],
        op_hand=[None, None, hc([7, 8, 7, 2], Op, n), hc([3, 6, 7, 3], Op, n), hc([7, 4, 2, 7], Op, f)],
        play_grid=PlayGrid([
            pc([6, 5, 8, 4], Op, -1), empty_slot_elem(h), empty_slot,
            empty_slot, empty_slot, pc([9, 9, 5, 2], Op, 1),
            empty_slot, empty_slot, pc([7, 6, 3, 1], Op, 0),
        ]),
    )),
    ("in-game/elemental_-1_in_0_1.jpg", GameState(
        turn_phase=TurnPhase.my_card_selection(1),
        my_hand=[None, hc([9, 9, 5, 2], Me, e), hc([9, 8, 6, 2], Me, f), hc([1, 7, 8, 7], Me, n),
                 hc([8, 4, 8, 5], Me, n)],
        op_hand=[None, None, hc([1, 1, 5, 4], Op, n), hc([6, 5, 8, 4], Op, n), hc([8, 2, 2, 8], Op, n)],
        play_grid=PlayGrid([
            pc([4, 6, 5, 5], Op, 0), empty_slot, pc([5, 9, 1, 9], Me, 0),
            pc([5, 3, 1, 1], Op, -1), empty_slot, empty_slot_elem(p),
            empty_slot, empty_slot, empty_slot_elem(p),
        ]),
    )),
    ("in-game/elemental_+1_in_0_0.jpg", GameState(
        turn_phase=OPPONENTS_TURN, my_hand=[], op_hand=[], play_grid=PlayGrid.empty(),
    )),
]


@pytest.mark.parametrize("path,expected", SCREENSHOT_GAME_STATES, ids=[p for p, _ in SCREENSHOT_GAME_STATES])
def test_game_state_read_correctly(path, expected):
    assert read_game_state(_load(path)) == expected


_TARGET_SELECTION_BASE = GameState(
    turn_phase=TurnPhase.my_card_selection(4),
    my_hand=SCREENSHOT_GAME_STATES[0][1].my_hand,
    op_hand=[hc([5, 4, 5, 7], Op, n), hc([4, 7, 6, 2], Op, n), hc([1, 7, 6, 4], Op, t), hc([7, 8, 7, 2], Op, n),
             hc([1, 5, 3, 3], Op, n)],
    play_grid=PlayGrid([
        empty_slot_elem(h), empty_slot, empty_slot,
        empty_slot, empty_slot, empty_slot,
        empty_slot, empty_slot, empty_slot,
    ]),
)

TARGET_SELECTION_GAME_STATES = [
    (f"in-game/target_selection_{x}_{y}.jpg",
     GameState(
         turn_phase=TurnPhase.my_target_selection(4, (x, y)),
         my_hand=_TARGET_SELECTION_BASE.my_hand,
         op_hand=_TARGET_SELECTION_BASE.op_hand,
         play_grid=_TARGET_SELECTION_BASE.play_grid,
     ))
    for y in range(3)
    for x in range(3)
]


@pytest.mark.parametrize(
    "path,expected", TARGET_SELECTION_GAME_STATES, ids=[p for p, _ in TARGET_SELECTION_GAME_STATES]
)
def test_target_selection_game_states_read_correctly(path, expected):
    assert read_game_state(_load(path)) == expected


EMPTY_PLAY_GRID_SLOT_ELEMENT_TEST_DATA = [
    (2, [[n, n, n], [f, n, p], [n, n, p]]),
    (3, [[n, n, n], [f, n, p], [n, n, p]]),
    (4, [[n, n, n], [f, n, p], [n, n, p]]),
    (10, [[n, n, n], [t, n, e], [p, n, n]]),
    (11, [[n, n, n], [t, n, e], [p, n, n]]),
    (13, [[n, n, w], [n, n, n], [n, n, a]]),
    (14, [[n, n, w], [n, n, n], [n, n, a]]),
    (15, [[n, n, w], [n, n, n], [n, n, a]]),
    (24, [[f, i, n], [n, n, n], [w, n, n]]),
    (25, [[f, i, n], [n, n, n], [w, n, n]]),
    (26, [[f, i, n], [n, n, n], [w, n, n]]),
]


@pytest.mark.parametrize("ss_num,expected_elems", EMPTY_PLAY_GRID_SLOT_ELEMENT_TEST_DATA)
def test_empty_play_grid_slot_elements_read_correctly(ss_num, expected_elems):
    screenshot = _load(f"in-game/elements/elements_{ss_num:02d}.jpg")
    state = read_game_state_with_turn_phase(TurnPhase.my_card_selection(1), screenshot)
    for idx, slot in enumerate(state.play_grid.slots):
        if slot.is_empty:
            assert slot.element == expected_elems[idx // 3][idx % 3], f"slot {idx} in screenshot {ss_num}"


@pytest.mark.parametrize("expected_phase", [GamePhase.WON, GamePhase.DRAW, GamePhase.LOST])
def test_game_phase_read_correctly(expected_phase):
    path = f"getting_out/result_{expected_phase.name.lower()}.jpg"
    assert read_game_phase(_load(path)) == expected_phase


def test_number_of_cards_on_card_choosing_screen_read_correctly():
    assert read_number_of_cards_on_card_choosing_screen(_load("getting_in/card_selection_page1.jpg")) == 11
    assert read_number_of_cards_on_card_choosing_screen(_load("getting_in/card_selection_page7.jpg")) == 9


RULE_DATA = [
    ("rules_open_sudden_random_sameplus_elemental_one.jpg",
     Rules.having([Rule.ELEMENTAL, Rule.OPEN, Rule.SAME, Rule.PLUS, Rule.RANDOM, Rule.SUDDEN_DEATH, Rule.TRADE_ONE])),
    ("rules_open_sudden_elemental_diff.jpg",
     Rules.having([Rule.OPEN, Rule.SUDDEN_DEATH, Rule.ELEMENTAL, Rule.TRADE_DIFF])),
    ("rules_random_plus_elemental_one.jpg",
     Rules.having([Rule.RANDOM, Rule.PLUS, Rule.ELEMENTAL, Rule.TRADE_ONE])),
    ("rules_open_sudden_sameplus_elemental_diff.jpg",
     Rules.having([Rule.OPEN, Rule.SUDDEN_DEATH, Rule.SAME, Rule.PLUS, Rule.ELEMENTAL, Rule.TRADE_DIFF])),
    ("rules_open_sudden_random_samepluswall_elemental_one.jpg",
     Rules.having([Rule.OPEN, Rule.SUDDEN_DEATH, Rule.RANDOM, Rule.SAME, Rule.PLUS, Rule.SAME_WALL, Rule.ELEMENTAL,
                   Rule.TRADE_ONE])),
]


@pytest.mark.parametrize("filename,expected_rules", RULE_DATA, ids=[d[0] for d in RULE_DATA])
def test_rules_read_correctly(filename, expected_rules):
    assert read_rules(_load(f"getting_in/{filename}")) == expected_rules
