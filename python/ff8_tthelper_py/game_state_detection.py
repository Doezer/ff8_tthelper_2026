"""Screenshot -> GameState detection. Ported from GameStateDetection.fs.

Only the runtime detection path is ported (`read_game_state`, `read_rules`,
`read_game_phase`, `read_spoils_selection_number`,
`read_number_of_cards_on_card_choosing_screen`). The F# `Bootstrap` module
(and the `Polygon`/`BitmapMask.PolygonMask` machinery it alone uses) is a
one-time offline tool that regenerated the template PNGs under `images/`
from raw example screenshots - those images are already committed, so
there's nothing at runtime that needs it.

Two functions deviate from a literal translation, deliberately:

- `_read_card_owner` here does a full vectorized scan of its test
  rectangle. The F# version stops scanning early once one color's pixel
  count reaches 50, purely as a speed hack for its per-pixel loop; with
  numpy the full scan is fast enough that the hack isn't needed, and this
  avoids a subtle case where early-exit truncation could pick a different
  winner than a full count would.
- `_get_play_grid_slot_element_only_bitmap` vectorizes the F# per-pixel
  alpha-decomposition loop with numpy. Same formula, same result, no
  loop-order dependence in the original to worry about.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from .bitmap_helpers import (
    Rect,
    SimpleBitmap,
    bitmap_diff,
    filtered_sub_bitmap,
    is_pixel_between,
    is_whitish_pixel,
    sub_bitmap,
)
from .domain_types import (
    Card,
    Element,
    GamePhase,
    GameState,
    Hand,
    Player,
    PlayGrid,
    PlayGridSlot,
    Rule,
    Rules,
    TurnPhase,
    TurnPhaseKind,
    GameStateDetectionError,
    OPPONENTS_TURN,
    digit_name_to_power,
    power_to_digit_name,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
IMAGE_DIR = _REPO_ROOT / "ff8_tthelper" / "images"
SCREENSHOT_DIR = _REPO_ROOT / "ff8_tthelper" / "screenshots"

Point = Tuple[int, int]

# --- Screen geometry (all pixel coordinates assume a 1920x1080 capture) ---

_MY_HAND_POSITION: Point = (1381, 93)
_OPPONENT_HAND_POSITION: Point = (331, 94)
_OPPONENT_HAND_CARD_OFFSETS = [(0, y) for y in (0, 154, 308, 462, 616)]
_MY_HAND_CARD_OFFSETS = [(0, y) for y in (0, 154, 309, 463, 617)]
_CARD_SELECTION_OFFSET: Point = (-45, 0)
_FIELD_CARD_X_OFFSETS = (0, 240, 480)
_FIELD_CARD_Y_OFFSETS = (0, 308, 617)

_DIGIT_SIZE = (26, 36)
_TOP_DIGIT_OFFSET: Point = (15, 0)
_LEFT_DIGIT_OFFSET: Point = (0, 39)
_RIGHT_DIGIT_OFFSET: Point = (30, 39)
_BOTTOM_DIGIT_OFFSET: Point = (15, 78)
_CARD_POWER_OFFSETS = (_TOP_DIGIT_OFFSET, _LEFT_DIGIT_OFFSET, _RIGHT_DIGIT_OFFSET, _BOTTOM_DIGIT_OFFSET)

_POWER_MODIFIER_OFFSET: Point = (66, 138)
_POWER_MODIFIER_SIZE = (45, 20)


def _add(p: Point, q: Point) -> Point:
    return p[0] + q[0], p[1] + q[1]


_OPPONENT_HAND_CARD_POSITIONS = [_add(_OPPONENT_HAND_POSITION, o) for o in _OPPONENT_HAND_CARD_OFFSETS]
_MY_HAND_CARD_POSITIONS = [_add(_MY_HAND_POSITION, o) for o in _MY_HAND_CARD_OFFSETS]
_PLAY_GRID_CARD_POSITIONS = [
    (616 + _FIELD_CARD_X_OFFSETS[col], 93 + _FIELD_CARD_Y_OFFSETS[row])
    for row in range(3)
    for col in range(3)
]

_CURSOR_SIZE = (67, 46)
_CARD_SELECTION_CURSOR_POSITIONS = [(1260, y) for y in (258, 402, 546, 690, 834)]
_TARGET_SELECTION_CURSOR_POSITIONS = [
    [(x, y) for x in (630, 870, 1110)] for y in (258, 546, 834)
]  # indexed [row][col]

_ELEMENT_SIZE = (54, 64)
_CARD_ELEMENT_OFFSET: Point = (149, 10)
_PLAY_GRID_SLOT_ELEMENT_OFFSET: Point = (76, 107)

_RESULT_DRAW_RECT = Rect(837, 438, 3, 205)
_RESULT_WIN_RECT = Rect(1324, 438, 34, 78)
_RESULT_LOSE_RECT = Rect(1320, 551, 47, 57)

_SPOILS_SELECT_NUMBER_RECT = Rect(823, 110, 21, 41)


def _card_choosing_screen_card_symbol_rect(i: int) -> Rect:
    return Rect(509, int(221 + 58.5 * (i - 1)), 6, 11)


def _rule_bullet_rect(i: int, j: int) -> Rect:
    return Rect(695 + j * 64, 203 + i * 36, 12, 17)


def _rule_rect(i: int, j: int) -> Rect:
    bullet = _rule_bullet_rect(i, j)
    return Rect(bullet.x + bullet.width + 20, bullet.y, 373, bullet.height)


def _rect_at(point: Point, size: Tuple[int, int]) -> Rect:
    return Rect(point[0], point[1], size[0], size[1])


def _get_digit_bitmap(screenshot: SimpleBitmap, point: Point) -> SimpleBitmap:
    return filtered_sub_bitmap(screenshot, _rect_at(point, _DIGIT_SIZE), is_whitish_pixel(130, 13))


def _get_cursor_bitmap(screenshot: SimpleBitmap, point: Point) -> SimpleBitmap:
    return filtered_sub_bitmap(screenshot, _rect_at(point, _CURSOR_SIZE), is_whitish_pixel(200, 10))


def _get_power_modifier_bitmap(screenshot: SimpleBitmap, card_top_left: Point) -> SimpleBitmap:
    rect = _rect_at(_add(card_top_left, _POWER_MODIFIER_OFFSET), _POWER_MODIFIER_SIZE)
    return filtered_sub_bitmap(screenshot, rect, is_whitish_pixel(160, 10))


def _get_card_element_bitmap(screenshot: SimpleBitmap, card_top_left: Point) -> SimpleBitmap:
    rect = _rect_at(_add(card_top_left, _CARD_ELEMENT_OFFSET), _ELEMENT_SIZE)
    return sub_bitmap(screenshot, rect)


def _get_play_grid_slot_element_bitmap(screenshot: SimpleBitmap, card_top_left: Point) -> SimpleBitmap:
    rect = _rect_at(_add(card_top_left, _PLAY_GRID_SLOT_ELEMENT_OFFSET), _ELEMENT_SIZE)
    return sub_bitmap(screenshot, rect)


# Per-row polygons covering the area the target-selection cursor's highlight/shadow
# overlaps when it sits on a grid slot. Ported from GameStateDetection.fs's
# `playGridSlotElementMasks` (originally `Polygon`/`BitmapMask.PolygonMask` ray-casting;
# rasterized here with PIL.ImageDraw instead - same fill result, far less code, and this
# is the one place outside the offline `Bootstrap` module that polygon masking is used at
# runtime, so it couldn't just be dropped like the rest of Polygon.fs was).
_PLAY_GRID_SLOT_ELEMENT_MASK_POINTS: List[List[Point]] = [
    [(0, 56), (25, 56), (25, 58), (27, 58), (27, 63), (0, 63)],
    [(0, 36), (25, 36), (25, 38), (28, 38), (28, 52), (25, 52), (25, 54), (24, 54), (24, 56),
     (22, 56), (22, 59), (21, 59), (21, 61), (18, 61), (18, 63), (0, 63)],
    [(0, 15), (27, 15), (28, 16), (28, 30), (25, 34), (25, 35), (20, 40), (19, 40), (19, 43),
     (3, 43), (3, 45), (6, 48), (6, 63), (0, 63)],
]


def _rasterize_polygon_mask(points: List[Point], width: int, height: int) -> np.ndarray:
    from PIL import Image, ImageDraw

    img = Image.new("1", (width, height), 0)
    ImageDraw.Draw(img).polygon(points, fill=1)
    return np.array(img, dtype=bool)


def _load_masked_elementless_play_grid_slot_bitmap(row: int, col: int) -> SimpleBitmap:
    bitmap = SimpleBitmap.from_file(str(IMAGE_DIR / f"play_grid_slot_element_empty_{row}_{col}.png"))
    mask = _rasterize_polygon_mask(_PLAY_GRID_SLOT_ELEMENT_MASK_POINTS[row], bitmap.width, bitmap.height)
    bitmap.pixels[mask] = (0, 0, 0, 0)  # exclude the cursor-covered area from bitmap_diff comparisons
    return bitmap


_empty_elementless_play_grid_slot_bitmaps: List[List[SimpleBitmap]] = [
    [_load_masked_elementless_play_grid_slot_bitmap(row, col) for col in range(3)]
    for row in range(3)
]


def _get_play_grid_slot_element_only_bitmap(
    screenshot: SimpleBitmap, row: int, col: int, transparent_when_empty: bool
) -> Optional[SimpleBitmap]:
    """Undo alpha compositing to isolate just the elemental-tile pixels, if any.

    C_o = C_a*alpha_a + C_b*(1-alpha_a)   (alpha_b = 1, background is opaque)
    ==> C_a = (C_o - C_b*(1-alpha_a)) / alpha_a
    C_o = actual screenshot color, C_b = same slot with no element overlay.
    """
    actual = _get_play_grid_slot_element_bitmap(screenshot, _PLAY_GRID_CARD_POSITIONS[row * 3 + col])
    elementless = _empty_elementless_play_grid_slot_bitmaps[row][col]

    if bitmap_diff(actual, elementless) < 0.02:
        return None

    c_o = actual.pixels.astype(np.int32)
    c_b = elementless.pixels.astype(np.float64)
    alpha_a = 0.64

    # F# truncates `float(chan_b) * (1-alpha_a)/alpha_a` to int *before* subtracting from
    # chan_o - matching that order matters, doing the whole thing in float and truncating
    # once at the end gives different (off-by-one) results for some pixels.
    term2 = np.trunc(c_b[..., :3] * (1.0 - alpha_a) / alpha_a).astype(np.int32)
    decomposed = np.maximum(0, c_o[..., :3] - term2).astype(np.uint8)

    b_alpha = c_b[..., 3] == 0
    close_to_background = (np.abs(c_o[..., :3] - c_b[..., :3]).sum(axis=-1)) <= 15
    is_background = b_alpha | close_to_background

    empty_color = (0, 0, 0, 0) if transparent_when_empty else (0, 0, 0, 255)

    out = np.empty_like(actual.pixels)
    out[..., :3] = decomposed
    out[..., 3] = 255
    out[is_background] = empty_color

    return SimpleBitmap(out)


_model_cursor = SimpleBitmap.from_file(str(IMAGE_DIR / "cursor.png"))


def _is_cursor_at_point(screenshot: SimpleBitmap, point: Point) -> bool:
    return bitmap_diff(_model_cursor, _get_cursor_bitmap(screenshot, point)) < 0.10


_ME_COLOR_BOUNDS = ((178, 209, 242, 255), (188, 219, 255, 255))
_OP_COLOR_BOUNDS = ((241, 176, 208, 255), (253, 187, 220, 255))


def _read_card_owner(screenshot: SimpleBitmap, card_pos: Point) -> Player:
    rect = Rect(card_pos[0] - 1, card_pos[1] + 3, 200, 15)
    sub = screenshot.crop(rect).pixels

    is_my_pixel = is_pixel_between(_ME_COLOR_BOUNDS[0][:3], _ME_COLOR_BOUNDS[1][:3])(sub)
    is_op_pixel = is_pixel_between(_OP_COLOR_BOUNDS[0][:3], _OP_COLOR_BOUNDS[1][:3])(sub)

    my_count = int(np.count_nonzero(is_my_pixel))
    op_count = int(np.count_nonzero(is_op_pixel))

    if my_count > op_count and my_count > 15:
        return Player.ME
    if my_count < op_count and op_count > 15:
        return Player.OP
    raise GameStateDetectionError("Unable to determine card owner")


_model_power_modifier_minus = SimpleBitmap.from_file(str(IMAGE_DIR / "power_modifier_minus.png"))
_model_power_modifier_plus = SimpleBitmap.from_file(str(IMAGE_DIR / "power_modifier_plus.png"))


def _read_power_modifier(screenshot: SimpleBitmap, card_top_left: Point) -> int:
    actual = _get_power_modifier_bitmap(screenshot, card_top_left)
    if bitmap_diff(actual, _model_power_modifier_minus) < 0.12:
        return -1
    if bitmap_diff(actual, _model_power_modifier_plus) < 0.12:
        return 1
    return 0


_NAMED_ELEMENTS = [e for e in Element.all() if e not in (Element.HOLY, Element.WATER, Element.UNKNOWN)]
_model_card_elements: List[Tuple[Element, SimpleBitmap]] = [
    (e, SimpleBitmap.from_file(str(IMAGE_DIR / f"element_{e.value}.png"))) for e in _NAMED_ELEMENTS
]


def _read_card_element(screenshot: SimpleBitmap, card_top_left: Point) -> Optional[Element]:
    card_element_bm = _get_card_element_bitmap(screenshot, card_top_left)
    candidates = [(e, bitmap_diff(card_element_bm, model)) for e, model in _model_card_elements]
    candidates = [c for c in candidates if c[1] < 0.10]
    if not candidates:
        return None
    return min(candidates, key=lambda c: c[1])[0]


_model_digits: List[SimpleBitmap] = [
    SimpleBitmap.from_file(str(IMAGE_DIR / f"digit{power_to_digit_name(i)}.png")) for i in range(1, 11)
]


def _read_digit_value(digit_bitmap: SimpleBitmap) -> Optional[int]:
    candidates = [(i + 1, bitmap_diff(digit_bitmap, model)) for i, model in enumerate(_model_digits)]
    if not [c for c in candidates if c[1] < 0.17]:
        return None
    return min(candidates, key=lambda c: c[1])[0]


def _read_card(
    screenshot: SimpleBitmap,
    owner: Optional[Player],
    power_modifier: Optional[int],
    element: Optional[Element],
    card_top_left_corner: Point,
) -> Optional[Card]:
    powers = [_read_digit_value(_get_digit_bitmap(screenshot, _add(card_top_left_corner, o))) for o in _CARD_POWER_OFFSETS]
    if any(p is None for p in powers):
        return None

    card_owner = owner if owner is not None else _read_card_owner(screenshot, card_top_left_corner)
    card_power_modifier = power_modifier if power_modifier is not None else _read_power_modifier(screenshot, card_top_left_corner)
    card_element = element if element is not None else _read_card_element(screenshot, card_top_left_corner)

    return Card(powers=tuple(powers), power_modifier=card_power_modifier, owner=card_owner, element=card_element)


def _read_hand(
    screenshot: SimpleBitmap, owner: Player, hand_card_base_positions: List[Point], selected_index: Optional[int]
) -> Hand:
    def shift_if_selected(i: int, pos: Point) -> Point:
        if selected_index is not None and i == selected_index:
            return _add(pos, _CARD_SELECTION_OFFSET)
        return pos

    return [
        _read_card(screenshot, owner, 0, None, shift_if_selected(i, pos))
        for i, pos in enumerate(hand_card_base_positions)
    ]


_ELEM_NAME_TO_ELEMENT = {e.value: e for e in Element.all()}
_MODEL_EMPTY_PLAY_GRID_SLOT_ELEMENTS: List[Tuple[SimpleBitmap, Element]] = [
    (SimpleBitmap.from_file(str(IMAGE_DIR / f"slot_element_{elem.value}{i}.png")), elem)
    for elem, num in [
        (Element.EARTH, 2), (Element.FIRE, 4), (Element.HOLY, 2), (Element.ICE, 3),
        (Element.POISON, 4), (Element.THUNDER, 3), (Element.WATER, 3), (Element.WIND, 4),
    ]
    for i in range(1, num + 1)
]


def _read_empty_play_grid_slot_element(screenshot: SimpleBitmap, row: int, col: int) -> Optional[Element]:
    bitmap = _get_play_grid_slot_element_only_bitmap(screenshot, row, col, transparent_when_empty=False)
    if bitmap is None:
        return None
    return min(
        ((bitmap_diff(model, bitmap), elem) for model, elem in _MODEL_EMPTY_PLAY_GRID_SLOT_ELEMENTS),
        key=lambda t: t[0],
    )[1]


def _read_play_grid(screenshot: SimpleBitmap) -> PlayGrid:
    slots = []
    for i, pos in enumerate(_PLAY_GRID_CARD_POSITIONS):
        card = _read_card(screenshot, None, None, Element.UNKNOWN, pos)
        if card is not None:
            slots.append(PlayGridSlot.full(card))
        else:
            slots.append(PlayGridSlot.empty(_read_empty_play_grid_slot_element(screenshot, i // 3, i % 3)))
    return PlayGrid(slots)


def _read_turn_phase(screenshot: SimpleBitmap) -> TurnPhase:
    selected_card_index = None
    for i, pos in enumerate(_MY_HAND_CARD_POSITIONS):
        shifted = _add(pos, _CARD_SELECTION_OFFSET)
        if _read_card(screenshot, Player.ME, 0, Element.UNKNOWN, shifted) is not None:
            selected_card_index = i
            break

    if selected_card_index is None:
        return OPPONENTS_TURN

    if _is_cursor_at_point(screenshot, _CARD_SELECTION_CURSOR_POSITIONS[selected_card_index]):
        return TurnPhase.my_card_selection(selected_card_index)

    for row in range(3):
        for col in range(3):
            if _is_cursor_at_point(screenshot, _TARGET_SELECTION_CURSOR_POSITIONS[row][col]):
                return TurnPhase.my_target_selection(selected_card_index, (col, row))

    raise GameStateDetectionError("My turn but could not find selection cursor")


def read_game_state_with_turn_phase(forced_turn_phase: Optional[TurnPhase], screenshot: SimpleBitmap) -> GameState:
    turn_phase = forced_turn_phase if forced_turn_phase is not None else _read_turn_phase(screenshot)

    if turn_phase.kind == TurnPhaseKind.OPPONENTS_TURN:
        return GameState(turn_phase=turn_phase, op_hand=[], my_hand=[], play_grid=PlayGrid.empty())

    selected_index = turn_phase.hand_index
    op_hand = _read_hand(screenshot, Player.OP, _OPPONENT_HAND_CARD_POSITIONS, None)
    my_hand = _read_hand(screenshot, Player.ME, _MY_HAND_CARD_POSITIONS, selected_index)
    play_grid = _read_play_grid(screenshot)
    return GameState(turn_phase=turn_phase, op_hand=op_hand, my_hand=my_hand, play_grid=play_grid)


def read_game_state(screenshot: SimpleBitmap) -> GameState:
    return read_game_state_with_turn_phase(None, screenshot)


def _get_game_phase_detection_bitmap(game_phase: GamePhase, screenshot: SimpleBitmap) -> SimpleBitmap:
    rect = {GamePhase.DRAW: _RESULT_DRAW_RECT, GamePhase.WON: _RESULT_WIN_RECT, GamePhase.LOST: _RESULT_LOSE_RECT}[game_phase]
    return sub_bitmap(screenshot, rect)


_model_game_phase_detection_bitmaps = [
    (GamePhase.WON, SimpleBitmap.from_file(str(IMAGE_DIR / "model_result_won.png"))),
    (GamePhase.DRAW, SimpleBitmap.from_file(str(IMAGE_DIR / "model_result_draw.png"))),
    (GamePhase.LOST, SimpleBitmap.from_file(str(IMAGE_DIR / "model_result_lost.png"))),
]


def read_game_phase(screenshot: SimpleBitmap) -> GamePhase:
    candidates = [
        (phase, bitmap_diff(_get_game_phase_detection_bitmap(phase, screenshot), model))
        for phase, model in _model_game_phase_detection_bitmaps
    ]
    phase, diff = min(candidates, key=lambda c: c[1])
    return phase if diff < 0.03 else GamePhase.ONGOING


_model_spoils_selection_number_bitmaps = [
    (1, SimpleBitmap.from_file(str(IMAGE_DIR / "model_spoils_number_1.png"))),
    (2, SimpleBitmap.from_file(str(IMAGE_DIR / "model_spoils_number_2.png"))),
    (4, SimpleBitmap.from_file(str(IMAGE_DIR / "model_spoils_number_4.png"))),
]


def read_spoils_selection_number(screenshot: SimpleBitmap) -> Optional[int]:
    bm = sub_bitmap(screenshot, _SPOILS_SELECT_NUMBER_RECT)
    candidates = [(num, bitmap_diff(bm, model)) for num, model in _model_spoils_selection_number_bitmaps]
    num, diff = min(candidates, key=lambda c: c[1])
    return num if diff < 0.03 else None


_model_card_symbol = SimpleBitmap.from_file(str(IMAGE_DIR / "model_card_symbol.png"))


def read_number_of_cards_on_card_choosing_screen(screenshot: SimpleBitmap) -> int:
    # Cards fill symbol slots 1..N; the count is (index of the first *absent* slot) - 1,
    # scanning from slot 2 (slot 1 is always present whenever there's at least one card).
    for i in range(2, 13):
        diff = bitmap_diff(sub_bitmap(screenshot, _card_choosing_screen_card_symbol_rect(i)), _model_card_symbol)
        if diff > 0.03:
            return i - 1
    raise GameStateDetectionError("Could not determine number of cards on card choosing screen")


_model_rule_bullet = SimpleBitmap.from_file(str(IMAGE_DIR / "model_rulebullet.png"))

_model_rules: List[Tuple[List[Rule], SimpleBitmap]] = [
    ([Rule.ELEMENTAL], SimpleBitmap.from_file(str(IMAGE_DIR / "model_rule_elemental.png"))),
    ([Rule.OPEN], SimpleBitmap.from_file(str(IMAGE_DIR / "model_rule_open.png"))),
    ([Rule.PLUS], SimpleBitmap.from_file(str(IMAGE_DIR / "model_rule_plus.png"))),
    ([Rule.SAME], SimpleBitmap.from_file(str(IMAGE_DIR / "model_rule_same.png"))),
    ([Rule.SAME, Rule.PLUS], SimpleBitmap.from_file(str(IMAGE_DIR / "model_rule_sameplus.png"))),
    ([Rule.SAME, Rule.PLUS, Rule.SAME_WALL], SimpleBitmap.from_file(str(IMAGE_DIR / "model_rule_samepluswall.png"))),
    ([Rule.RANDOM], SimpleBitmap.from_file(str(IMAGE_DIR / "model_rule_random.png"))),
    ([Rule.SUDDEN_DEATH], SimpleBitmap.from_file(str(IMAGE_DIR / "model_rule_sudden_death.png"))),
    ([Rule.TRADE_ONE], SimpleBitmap.from_file(str(IMAGE_DIR / "model_rule_trade_one.png"))),
    ([Rule.TRADE_DIFF], SimpleBitmap.from_file(str(IMAGE_DIR / "model_rule_trade_diff.png"))),
]


def read_rules(screenshot: SimpleBitmap) -> Rules:
    def rule_exists_in_index(i: int, j: int) -> bool:
        diff = bitmap_diff(_model_rule_bullet, sub_bitmap(screenshot, _rule_bullet_rect(i, j)))
        return diff < 0.02

    def most_likely_rule(i: int, j: int) -> List[Rule]:
        rule_bitmap = sub_bitmap(screenshot, _rule_rect(i, j))
        candidates = [(rule, bitmap_diff(rule_bitmap, model)) for rule, model in _model_rules]
        rule, diff = min(candidates, key=lambda c: c[1])
        return [Rule.UNKNOWN] if diff > 0.03 else rule

    rules: List[Rule] = []
    for j in range(2):
        for i in range(16):
            if rule_exists_in_index(i, j):
                rules.extend(most_likely_rule(i, j))
    return Rules.having(rules)
