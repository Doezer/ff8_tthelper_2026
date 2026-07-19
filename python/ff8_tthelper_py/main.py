"""Orchestration / entry point. Ported from Program.fs.

Machine-specific paths are read from environment variables, matching the
F# project's own port (see ff8_tthelper/Program.fs and its README):

- FF8_SCREENSHOT_DIR (required): folder where Steam saves FF8 screenshots.
- FF8_AHK_EXE (optional): path to AutoHotkey.exe.
- FF8_LOG_FILE (optional): path to the log file.

`Program.fs` locates a screenshot's arrival via a Windows `FileSystemWatcher`.
This port polls the screenshot directory instead - much less code, works
the same way from the caller's point of view (block until a new screenshot
file appears), and the poll interval (50ms) is well under the timings this
tool already sleeps for between key presses.
"""

from __future__ import annotations

import os
import random
import re
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Set

from . import ai
from . import game_state_detection as gsd
from .bitmap_helpers import SimpleBitmap
from .domain_types import (
    Card,
    GamePhase,
    GameState,
    Player,
    PlayGrid,
    PlayGridSlot,
    Rule,
    Rules,
    TurnPhase,
    TurnPhaseKind,
    Element,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _env_or_default(name: str, default: str) -> str:
    return os.environ.get(name) or default


def _required_env(name: str, explanation: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Environment variable {name} is not set. {explanation}")
    return value


LOG_FILE = _env_or_default("FF8_LOG_FILE", str(Path(tempfile.gettempdir()) / "ff8helper_log.txt"))
SCREEN_CAPTURE_DIR = _required_env(
    "FF8_SCREENSHOT_DIR",
    "Set it to your Steam screenshot folder for FF8, e.g. "
    r"<SteamLibrary>\userdata\<your Steam id3>\760\remote\39150\screenshots",
)
SCREENSHOT_FILE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{5}\.jpg$")
SCREENSHOT_HOTKEY = "F12"

AHK_PROG = _env_or_default("FF8_AHK_EXE", r"C:\Program Files\AutoHotkey\AutoHotkey.exe")
SEND_SCRIPT = _env_or_default("FF8_SEND_SCRIPT", str(_REPO_ROOT / "ff8_tthelper" / "send.ahk"))
CLEAR_SCRIPT = _env_or_default("FF8_CLEAR_SCRIPT", str(_REPO_ROOT / "ff8_tthelper" / "clearScreenshots.ahk"))

_log_file_handle = open(LOG_FILE, "a", encoding="utf-8")


def log(msg: str) -> None:
    to_write = f"{datetime.now()}: {msg}"
    _log_file_handle.write(to_write + "\n")
    _log_file_handle.flush()
    print(to_write)


def print_state(state: GameState) -> None:
    log(f"{state}-------------------------------------- b={ai.card_balance(state)}\r\n")


def read_game_state_from_screenshot(screenshot_path: str) -> GameState:
    log(f"Reading GameState from {screenshot_path}")
    t0 = time.time()
    screenshot = SimpleBitmap.from_file(screenshot_path)
    state = gsd.read_game_state(screenshot)
    log(f"GameState read in {int((time.time() - t0) * 1000)} ms")
    return state


def send_key(key: str) -> None:
    subprocess.run([AHK_PROG, SEND_SCRIPT, key], check=True)


def send_and_sleep(key: str, ms: int) -> None:
    send_key(key)
    time.sleep(ms / 1000)


def clear_steam_screenshots() -> None:
    log("Clearing Steam screenshots")
    subprocess.run([AHK_PROG, CLEAR_SCRIPT], check=True)


def _select_hand_card(offset: int) -> None:
    log(f"Selecting hand card with offset {offset}")
    key = "Up" if offset < 0 else "Down"
    for _ in range(abs(offset)):
        send_and_sleep(key, 20)
    send_and_sleep("x", 20)


def _select_target_slot(row_offset: int, col_offset: int) -> None:
    log(f"Selecting target slot with offset ({row_offset}, {col_offset})")
    if row_offset == -1:
        send_and_sleep("Up", 20)
    elif row_offset == 1:
        send_and_sleep("Down", 20)
    if col_offset == -1:
        send_and_sleep("Left", 20)
    elif col_offset == 1:
        send_and_sleep("Right", 20)
    send_and_sleep("x", 20)


def play_one_turn(state: GameState, rules: Rules) -> None:
    t0 = time.time()
    (src_hand_index, target_grid_index), value = ai.get_best_move(state, rules, 9)
    took_ms = int((time.time() - t0) * 1000)
    print_state(state)
    log(
        f"Best move is {src_hand_index} -> ({target_grid_index // 3},{target_grid_index % 3}) "
        f"with value {value} (took {took_ms} ms)"
    )
    print_state(ai.execute_move(state, rules, (src_hand_index, target_grid_index)))

    turn_phase = state.turn_phase
    if turn_phase.kind == TurnPhaseKind.MY_CARD_SELECTION:
        _select_hand_card(src_hand_index - turn_phase.hand_index)
    elif turn_phase.kind == TurnPhaseKind.MY_TARGET_SELECTION:
        send_key("c")
        _select_hand_card(src_hand_index - turn_phase.hand_index)

    # Now selecting target, cursor at (1,1)
    row_offset, col_offset = target_grid_index // 3 - 1, target_grid_index % 3 - 1
    _select_target_slot(row_offset, col_offset)


def _list_screenshot_files(directory: str) -> Set[str]:
    return {f for f in os.listdir(directory) if SCREENSHOT_FILE_PATTERN.match(f)}


def wait_for_screenshot(poll_interval: float = 0.05) -> str:
    before = _list_screenshot_files(SCREEN_CAPTURE_DIR)
    while True:
        time.sleep(poll_interval)
        after = _list_screenshot_files(SCREEN_CAPTURE_DIR)
        new_files = after - before
        if new_files:
            newest = max(new_files, key=lambda f: os.path.getmtime(os.path.join(SCREEN_CAPTURE_DIR, f)))
            return os.path.join(SCREEN_CAPTURE_DIR, newest)
        before = after


def wait_for_screenshot_bitmap() -> SimpleBitmap:
    tries_left = 5
    while tries_left > 0:
        filename = wait_for_screenshot()
        try:
            return SimpleBitmap.from_file(filename)
        except Exception:
            tries_left -= 1
            log("Failed to read screenshot")
    raise RuntimeError("Failed to read screenshot after 5 tries")


def wait_for_user_to_press_screenshot_hotkey() -> None:
    log(f"\r\n--------Press {SCREENSHOT_HOTKEY} inside game")
    wait_for_screenshot()
    log("pressed")


def play_one_turn_at_a_time(rules: Rules) -> None:
    while True:
        log("\r\nTake screenshot to play one turn")
        screenshot_filename = wait_for_screenshot()
        state = read_game_state_from_screenshot(screenshot_filename)
        if state.turn_phase.kind == TurnPhaseKind.OPPONENTS_TURN:
            log("Not my turn...")
        else:
            log("My turn, calculating best move...")
            play_one_turn(state, rules)


def take_screenshot() -> SimpleBitmap:
    before = _list_screenshot_files(SCREEN_CAPTURE_DIR)

    # Send the hotkey after 200ms, when the poll loop below is definitely running.
    timer = threading.Timer(0.2, send_key, args=(SCREENSHOT_HOTKEY,))
    timer.start()

    deadline = time.time() + 4.0
    new_file: Optional[str] = None
    while time.time() < deadline:
        time.sleep(0.05)
        new_files = _list_screenshot_files(SCREEN_CAPTURE_DIR) - before
        if new_files:
            new_file = max(new_files, key=lambda f: os.path.getmtime(os.path.join(SCREEN_CAPTURE_DIR, f)))
            break
    timer.cancel()

    if new_file is None:
        log("Timed out while waiting for screenshot, retrying...")
        return take_screenshot()

    time.sleep(0.1)
    path = os.path.join(SCREEN_CAPTURE_DIR, new_file)
    try:
        return SimpleBitmap.from_file(path)
    except Exception:
        time.sleep(0.1)
        return SimpleBitmap.from_file(path)


def choose_cards() -> None:
    log("Choosing cards")

    send_and_sleep("Left", 150)
    send_and_sleep("Up", 20)

    t0 = time.time()
    num_cards_on_page = gsd.read_number_of_cards_on_card_choosing_screen(take_screenshot())
    log(f"Detected {num_cards_on_page} cards on page (took {int((time.time() - t0) * 1000)} ms)")
    for _ in range(11 - num_cards_on_page):
        send_and_sleep("Up", 20)

    cards_to_take_from_last_page = min(5, num_cards_on_page)
    for i in range(1, cards_to_take_from_last_page + 1):
        send_and_sleep("x", 20)
        if i != cards_to_take_from_last_page:
            send_and_sleep("Up", 20)

    if num_cards_on_page < 5:
        send_and_sleep("Left", 150)
        send_and_sleep("Up", 20)
        remaining = 5 - num_cards_on_page
        for i in range(1, remaining + 1):
            send_and_sleep("x", 20)
            if i != remaining:
                send_and_sleep("Up", 20)

    time.sleep(1.0)
    send_and_sleep("x", 2500)
    log("Cards chosen!")


def play_match(rules: Rules) -> None:
    last_screenshot = take_screenshot()
    while gsd.read_game_phase(last_screenshot) == GamePhase.ONGOING:
        state = gsd.read_game_state(last_screenshot)
        while (
            state.turn_phase.kind == TurnPhaseKind.OPPONENTS_TURN
            and gsd.read_game_phase(last_screenshot) == GamePhase.ONGOING
        ):
            log("Waiting for my turn...")
            time.sleep(1.0)
            last_screenshot = take_screenshot()
            state = gsd.read_game_state(last_screenshot)
        if gsd.read_game_phase(last_screenshot) == GamePhase.ONGOING:
            log("My turn now, calculating best move...")
            play_one_turn(state, rules)
            time.sleep(1.5)
            last_screenshot = take_screenshot()

    result = gsd.read_game_phase(last_screenshot)
    log(f"Game ended, result: {result}")
    time.sleep(0.5)
    send_and_sleep("x", 2000)  # Dismiss Won/Draw/Lost screen
    if result == GamePhase.DRAW:
        play_match(rules)


def choose_spoils() -> None:
    spoils_selection_number = gsd.read_spoils_selection_number(take_screenshot())
    if spoils_selection_number is not None:
        log(f"Choosing {spoils_selection_number} cards for spoils")
        if spoils_selection_number == 1:
            for _ in range(random.randrange(5)):  # randomize the chosen card
                send_and_sleep("Right", 80)
        for _ in range(spoils_selection_number):
            send_and_sleep("x", 400)
            send_and_sleep("Right", 80)
        send_and_sleep("x", 1300)
        for _ in range(spoils_selection_number):
            send_and_sleep("x", 1300)
        time.sleep(2.0)
    else:
        log("Nothing to do, waiting for game to end...")
        time.sleep(10.0)


def start_game_against_that_sitting_dude(i: int) -> None:
    log("--------------------------------------------------------")
    log(f"Starting game {i}")
    send_and_sleep("s", 700)  # Play game?
    send_and_sleep("x", 2000)  # Yes
    send_and_sleep("x", 2000)  # Talking
    send_and_sleep("x", 1700)  # Rules
    choose_cards()


def auto_play_against_that_sitting_dude(rules: Rules) -> None:
    wait_for_user_to_press_screenshot_hotkey()
    i = 0
    while True:
        start_game_against_that_sitting_dude(i)
        play_match(rules)
        choose_spoils()
        i += 1


def play_one_game_at_a_time_starting_from_rules_screen() -> None:
    while True:
        log("Take screenshot in rules screen to play one game")
        rules = gsd.read_rules(wait_for_screenshot_bitmap())
        if not rules.is_valid_rule_set:
            log(f"Invalid rule set: {rules.rules}")
        else:
            log(f"Read valid rules: {rules.rules}")
            send_and_sleep("x", 1700)  # dismiss rules
            if not rules.has(Rule.RANDOM):
                choose_cards()
            play_match(rules)


def play_game(init_state: GameState, rules: Rules) -> GameState:
    state = init_state
    while not ai.is_terminal_node(state):
        log("Game state before move:")
        print_state(state)
        t0 = time.time()
        move, value = ai.get_best_move(state, rules, 9)
        took_ms = int((time.time() - t0) * 1000)
        log(f"Best move is {move[0]} -> ({move[1] // 3},{move[1] % 3}) with value {value} (took {took_ms} ms)")
        state = ai.execute_move(state, rules, move)

    print_state(state)
    return state


def play_screenshot(screenshot_path: str, rules: Rules) -> GameState:
    return play_game(read_game_state_from_screenshot(screenshot_path), rules)


TEST_STATE = GameState(
    turn_phase=TurnPhase.my_card_selection(4),
    my_hand=[None, None, None, None, Card((9, 8, 6, 2), 0, Player.ME, None)],
    op_hand=[None, None, None, None, Card((5, 6, 3, 7), 0, Player.OP, None)],
    play_grid=PlayGrid([
        PlayGridSlot.full(Card((9, 9, 5, 2), -1, Player.OP, Element.UNKNOWN)),
        PlayGridSlot.full(Card((6, 6, 3, 1), -1, Player.OP, Element.UNKNOWN)),
        PlayGridSlot.full(Card((7, 1, 1, 3), 0, Player.OP, Element.UNKNOWN)),
        PlayGridSlot.full(Card((9, 9, 5, 2), 0, Player.OP, Element.UNKNOWN)),
        PlayGridSlot.full(Card((5, 9, 1, 9), 0, Player.OP, Element.UNKNOWN)),
        PlayGridSlot.full(Card((1, 7, 6, 4), 0, Player.OP, Element.UNKNOWN)),
        PlayGridSlot.full(Card((8, 4, 8, 5), 0, Player.ME, Element.UNKNOWN)),
        PlayGridSlot.empty(),
        PlayGridSlot.full(Card((1, 7, 8, 7), 0, Player.OP, Element.UNKNOWN)),
    ]),
)


def main() -> int:
    t0 = time.time()

    # Choose mode by uncommenting one line below:
    # bootstrap() is not ported - see game_state_detection.py's module docstring.
    # play_screenshot(str(gsd.SCREENSHOT_DIR / "in-game" / "card_with_power_a.jpg"), Rules.none())
    # play_game(TEST_STATE, Rules(frozenset({Rule.SAME})))
    # play_one_turn_at_a_time(Rules.none())
    # auto_play_against_that_sitting_dude(Rules.none())
    play_one_game_at_a_time_starting_from_rules_screen()

    log(f"Time elapsed: {int((time.time() - t0) * 1000)} ms")
    return 0


if __name__ == "__main__":
    sys.exit(main())
