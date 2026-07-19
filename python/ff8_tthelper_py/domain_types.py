"""Core Triple Triad domain types. Ported from DomainTypes.fs."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum, auto
from typing import List, Optional


class GameStateDetectionError(Exception):
    pass


def digit_name_to_power(digit_name: str) -> int:
    return 10 if digit_name == "A" else int(digit_name)


def power_to_digit_name(power: int) -> str:
    return "A" if power == 10 else str(power)


class TurnPhaseKind(Enum):
    MY_CARD_SELECTION = auto()
    MY_TARGET_SELECTION = auto()
    OPPONENTS_TURN = auto()


@dataclass(frozen=True)
class TurnPhase:
    """Mirrors the F# discriminated union TurnPhase.

    Use the MyCardSelection / MyTargetSelection / OpponentsTurn
    constructors below rather than this class directly.
    """

    kind: TurnPhaseKind
    hand_index: Optional[int] = None
    grid_coords: Optional[tuple[int, int]] = None

    @staticmethod
    def my_card_selection(hand_index: int) -> "TurnPhase":
        return TurnPhase(TurnPhaseKind.MY_CARD_SELECTION, hand_index=hand_index)

    @staticmethod
    def my_target_selection(hand_index: int, grid_coords: tuple[int, int]) -> "TurnPhase":
        return TurnPhase(TurnPhaseKind.MY_TARGET_SELECTION, hand_index=hand_index, grid_coords=grid_coords)


OPPONENTS_TURN = TurnPhase(TurnPhaseKind.OPPONENTS_TURN)


class GamePhase(Enum):
    ONGOING = auto()
    WON = auto()
    DRAW = auto()
    LOST = auto()


class Element(Enum):
    EARTH = "earth"
    FIRE = "fire"
    HOLY = "holy"
    ICE = "ice"
    POISON = "poison"
    THUNDER = "thunder"
    WATER = "water"
    WIND = "wind"
    UNKNOWN = "unknown"

    @staticmethod
    def all() -> list["Element"]:
        return [
            Element.EARTH, Element.FIRE, Element.HOLY, Element.ICE,
            Element.POISON, Element.THUNDER, Element.WATER, Element.WIND,
        ]


class Player(Enum):
    ME = "me"
    OP = "op"

    @property
    def opposite(self) -> "Player":
        return Player.OP if self is Player.ME else Player.ME


@dataclass(frozen=True)
class Card:
    powers: tuple[int, int, int, int]
    power_modifier: int
    owner: Player
    element: Optional[Element]

    def modified_power(self, power_index: int) -> int:
        return self.powers[power_index] + self.power_modifier

    @property
    def with_opposite_owner(self) -> "Card":
        return replace(self, owner=self.owner.opposite)

    def __str__(self) -> str:
        powers_string = ",".join(power_to_digit_name(p) for p in self.powers)
        element_string = "None" if self.element is None else self.element.name
        return f"Card {powers_string} {self.power_modifier:+d} {self.owner.name} {element_string}"


@dataclass(frozen=True)
class PlayGridSlot:
    """Mirrors the F# union PlayGridSlot = Full of Card | Empty of Element option.

    Exactly one of `card` / `element` is meaningful, matching `is_full`.
    """

    card: Optional[Card]
    element: Optional[Element]

    @staticmethod
    def full(card: Card) -> "PlayGridSlot":
        return PlayGridSlot(card=card, element=None)

    @staticmethod
    def empty(element: Optional[Element] = None) -> "PlayGridSlot":
        return PlayGridSlot(card=None, element=element)

    @property
    def is_empty(self) -> bool:
        return self.card is None

    @property
    def is_full(self) -> bool:
        return self.card is not None

    @property
    def with_opposite_card_owner(self) -> "PlayGridSlot":
        if self.card is None:
            raise ValueError("not Full")
        return PlayGridSlot.full(self.card.with_opposite_owner)

    def __str__(self) -> str:
        if self.card is not None:
            return str(self.card)
        return f"Empty GridSlot ({self.element})"


class PlayGrid:
    """3x3 grid of PlayGridSlot, row-major, mirrors PlayGrid in DomainTypes.fs."""

    __slots__ = ("slots",)

    def __init__(self, slots: list[PlayGridSlot]):
        assert len(slots) == 9
        self.slots = slots

    def __getitem__(self, index) -> PlayGridSlot:
        if isinstance(index, tuple):
            row, col = index
            return self.slots[row * 3 + col]
        return self.slots[index]

    def __setitem__(self, index, value: PlayGridSlot) -> None:
        if isinstance(index, tuple):
            row, col = index
            self.slots[row * 3 + col] = value
        else:
            self.slots[index] = value

    def copy(self) -> "PlayGrid":
        return PlayGrid(list(self.slots))

    @staticmethod
    def empty() -> "PlayGrid":
        return PlayGrid([PlayGridSlot.empty() for _ in range(9)])

    def __eq__(self, other: object) -> bool:
        return isinstance(other, PlayGrid) and self.slots == other.slots

    def __str__(self) -> str:
        rows = []
        for y in range(3):
            row_slots = self.slots[y * 3:y * 3 + 3]
            rows.append("\t".join(str(s) for s in row_slots))
        return "PlayGrid:\r\n    " + "\r\n    ".join(rows)


# Hand = 5-element list of Optional[Card], mirrors `Card option array` in F#.
Hand = List[Optional[Card]]


def _power_modifier_char(power_modifier: int) -> str:
    return {-1: "-", 0: " ", 1: "+"}.get(power_modifier, "?")


_ELEMENT_CHARS = {
    Element.EARTH: "E", Element.FIRE: "F", Element.HOLY: "H", Element.ICE: "I",
    Element.POISON: "P", Element.THUNDER: "T", Element.WATER: "A", Element.WIND: "W",
    Element.UNKNOWN: "U",
}


def _element_option_char(element: Optional[Element]) -> str:
    return _ELEMENT_CHARS[element] if element is not None else " "


def _card_power_string(card: Card) -> str:
    return "".join(power_to_digit_name(p) for p in card.powers)


def _player_char(player: Player) -> str:
    return "m" if player is Player.ME else "o"


def _grid_slot_string(slot: PlayGridSlot) -> str:
    if slot.is_full:
        c = slot.card
        return f"{_player_char(c.owner)}{_card_power_string(c)}{_power_modifier_char(c.power_modifier)}"
    if slot.element is not None:
        return f" ({_ELEMENT_CHARS[slot.element]})  "
    return "      "


def _hand_slot_string(hand_slot: Optional[Card]) -> str:
    if hand_slot is not None:
        return f"{_card_power_string(hand_slot)}{_element_option_char(hand_slot.element)}"
    return "     "


def _hand_selected_char(turn_phase: TurnPhase, hand_index: int) -> str:
    if turn_phase.kind == TurnPhaseKind.MY_CARD_SELECTION and turn_phase.hand_index == hand_index:
        return "@"
    if turn_phase.kind == TurnPhaseKind.MY_TARGET_SELECTION and turn_phase.hand_index == hand_index:
        return "#"
    return " "


def _grid_slot_selected_char(turn_phase: TurnPhase, grid_coords: tuple[int, int]) -> str:
    if turn_phase.kind == TurnPhaseKind.MY_TARGET_SELECTION and turn_phase.grid_coords == grid_coords:
        return "@"
    return " "


class Rule(Enum):
    ELEMENTAL = auto()
    OPEN = auto()
    SAME = auto()
    SAME_WALL = auto()
    PLUS = auto()
    RANDOM = auto()
    SUDDEN_DEATH = auto()
    TRADE_ONE = auto()
    TRADE_DIFF = auto()
    TRADE_DIRECT = auto()
    UNKNOWN = auto()


TRADE_RULES = frozenset({Rule.TRADE_ONE, Rule.TRADE_DIFF, Rule.TRADE_DIRECT})


@dataclass(frozen=True)
class Rules:
    rules: frozenset[Rule] = field(default_factory=frozenset)

    def with_rule(self, rule: Rule) -> "Rules":
        return Rules(self.rules | {rule})

    def has(self, rule: Rule) -> bool:
        return rule in self.rules

    @property
    def is_valid_rule_set(self) -> bool:
        return (
            Rule.UNKNOWN not in self.rules
            and Rule.OPEN in self.rules
            and len(self.rules & TRADE_RULES) == 1
        )

    @property
    def trade_rule(self) -> Optional[Rule]:
        intersection = self.rules & TRADE_RULES
        return min(intersection, key=lambda r: r.value) if intersection else None

    @staticmethod
    def having(rules) -> "Rules":
        return Rules(frozenset(rules))

    @staticmethod
    def none() -> "Rules":
        return Rules.having([])

    @staticmethod
    def only(rule: Rule) -> "Rules":
        return Rules.having([rule])

    def __str__(self) -> str:
        return f"Rules {self.rules}"


@dataclass(frozen=True)
class GameState:
    turn_phase: TurnPhase
    my_hand: Hand
    op_hand: Hand
    play_grid: PlayGrid

    def _game_state_line(self, hand_index: int, grid_row: Optional[int]) -> str:
        if grid_row is not None:
            r = grid_row
            return (
                f"{_hand_slot_string(self.op_hand[hand_index])} "
                f"{_grid_slot_selected_char(self.turn_phase, (r, 0))}{_grid_slot_string(self.play_grid[r, 0])} |"
                f"{_grid_slot_selected_char(self.turn_phase, (r, 1))}{_grid_slot_string(self.play_grid[r, 1])} |"
                f"{_grid_slot_selected_char(self.turn_phase, (r, 2))}{_grid_slot_string(self.play_grid[r, 2])} "
                f"{_hand_selected_char(self.turn_phase, hand_index)}{_hand_slot_string(self.my_hand[hand_index])}"
            )
        return (
            f"{_hand_slot_string(self.op_hand[hand_index])}  -------+--------+------- "
            f"{_hand_selected_char(self.turn_phase, hand_index)}{_hand_slot_string(self.my_hand[hand_index])}"
        )

    def __str__(self) -> str:
        lines = [""]
        for hand_index, grid_row in [(0, 0), (1, None), (2, 1), (3, None), (4, 2)]:
            lines.append(self._game_state_line(hand_index, grid_row))
        return "\r\n".join(lines) + "\r\n"
