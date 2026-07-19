# ff8_tthelper (Python port)

A Python port of the F# `ff8_tthelper` tool in `../ff8_tthelper/`, which
autonomously plays Triple Triad in Final Fantasy VIII (Steam, Windows) by
reading screenshots and driving AutoHotkey. See the root `README.md` for
what this tool does and its hard requirements (Windows, 1920x1080, the
Open rule, AutoHotkey installed).

This port is functionally faithful to the F# original - same detection
thresholds, same alpha-beta search and capture/cascade rules, validated
against the same real screenshots the F# tests use (see "Tests" below).
A few implementation details were deliberately *not* carried over 1:1;
each is called out in the relevant module's docstring
(`bitmap_helpers.py`, `ai.py`, `game_state_detection.py`).

## Requirements

- Windows, 1920x1080 display, AutoHotkey installed - same as the F# version.
- **[PyPy3](https://www.pypy.org/)**, not CPython, to run the app itself.
  The AI's search is a plain recursive alpha-beta minimax (same algorithm
  as the F# original) and CPython's interpreter overhead makes the
  worst-case opening move (empty board, full hands, depth 9) take
  20-40 seconds. PyPy's JIT cuts that to single digits. CPython works
  fine too if you don't mind that one-time delay at the start of each
  match - every other move is much faster since the search tree shrinks
  fast as the grid fills.

## Setup

```powershell
# Install PyPy3 (portable zip from https://www.pypy.org/download.html, or via a package manager)
pypy3 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

Pillow builds from source on PyPy on some platforms; if `pip install` fails
trying to compile it, install PyPy's prebuilt wheels' build prerequisites
(zlib/libjpeg dev headers) or fall back to `python -m venv` with regular
CPython (works fine, just slower - see above).

## Configuration

Same three environment variables as the F# version:

| Variable | Required | Meaning |
|---|---|---|
| `FF8_SCREENSHOT_DIR` | **Yes** | Folder where Steam saves FF8 screenshots |
| `FF8_AHK_EXE` | No (defaults to `C:\Program Files\AutoHotkey\AutoHotkey.exe`) | Path to `AutoHotkey.exe` |
| `FF8_LOG_FILE` | No (defaults to `<temp dir>\ff8helper_log.txt`) | Path to the log file |

`send.ahk`/`clearScreenshots.ahk` default to the copies in
`../ff8_tthelper/` (reused rather than duplicated); override with
`FF8_SEND_SCRIPT`/`FF8_CLEAR_SCRIPT` if you want your own copies.

## Running

```powershell
.venv\Scripts\pypy3 -m ff8_tthelper_py.main
```

Same flow as the F# version: get FF8 to a Triple Triad match's rules
screen with the Open rule, press F12 to start the AI.

`main.py`'s `main()` calls `play_one_game_at_a_time_starting_from_rules_screen()`,
matching `Program.fs`'s active entry point; the other modes
(`play_one_turn_at_a_time`, `auto_play_against_that_sitting_dude`, etc.)
are still in the file for manual use, same as the original.

## Tests

```
pip install -r requirements-dev.txt
pytest
```

`tests/test_ai.py` ports every case from `AITest.fs` (Same/SameWall/Plus
rule interactions). `tests/test_game_state_detection.py` ports
`GameStateDetectionTest.fs` and runs against the real screenshots checked
into `../ff8_tthelper/screenshots/` - not synthetic fixtures, the actual
pixel-offset and template-diff detection logic exercised end-to-end.
All 45 tests pass under both CPython and PyPy3.

## What wasn't ported, and why

- **`Bootstrap` module / `Polygon.fs`'s ray-casting engine**: `Bootstrap`
  is a one-time offline tool that regenerated the template images under
  `../ff8_tthelper/images/` from raw example screenshots. Those images
  are already committed, so nothing at runtime needs to regenerate them.
  The one runtime use of polygon masking outside `Bootstrap`
  (`playGridSlotElementMasks`, masking out the area the target-selection
  cursor covers) is ported, but with `PIL.ImageDraw` rasterizing the
  polygons instead of a hand-rolled ray-casting algorithm.
- **`AI.fs`'s `evaluateNode`/`evaluateGridSlot`**: dead code in the F#
  original - `alphaBeta`'s leaf evaluation calls `cardBalance`, not
  `evaluateNode`, and nothing else calls it either.
- **Buffer pre-allocation** in `AI.fs`'s search (reused grid/hand arrays
  to reduce .NET GC pressure): a performance detail with no behavioral
  effect: this port allocates normally.
