# Final Fantasy VIII Triple Triad AI

This program will autonomously play a game of Triple Triad within Final Fantasy VIII (Steam edition, Windows). Game state is read from screenshots and the game is controlled by emulating keystrokes. Best moves are determined by a full depth alpha-beta minimax search that maximizes the card difference. All rule combinations that contain the Open rule are supported, and **the AI is guaranteed to win the game if it is possible**.

[![](http://img.youtube.com/vi/TWLy6QsqN-4/0.jpg)](http://www.youtube.com/watch?v=TWLy6QsqN-4 "AI in action")

## Requirements

This is a Windows-only tool:

- Windows, with the display set to exactly **1920x1080** (the screenshot-reading code assumes this resolution).
- Final Fantasy VIII (Steam edition, app id 39150).
- [AutoHotkey](https://www.autohotkey.com/) installed — used to send keystrokes to the game and (optionally) to clear old Steam screenshots. Get `AutoHotkey.exe`'s install path; you'll need it below.
- A match using the **Open** rule (or any rule combination that includes Open) — no other rule sets are supported.

## Building

The project (`ff8_tthelper.fsproj`) is an old-style, non-SDK MSBuild project targeting .NET Framework 4.6. `dotnet build` will not work on it. NuGet packages (NUnit 2.6.3, NUnitTestAdapter, FsUnit) are already vendored under `packages/`, so no NuGet restore step is required as-is.

On Windows, build with any modern MSBuild that has the F# workload installed — Visual Studio no longer needs to be 2015 specifically. The simplest option:

1. Install **[Build Tools for Visual Studio](https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022)** (free), selecting the ".NET desktop build tools" workload, which includes F# and the .NET Framework 4.6 targeting pack. Visual Studio Community with the same workload also works.
2. From a "Developer Command Prompt", run:
   ```
   msbuild ff8_tthelper.sln
   ```
   or open `ff8_tthelper.sln` in Visual Studio and build (F6) / run (Ctrl+F5) from there.

This was verified end-to-end in this change (not on Windows, since this environment is Linux, but as a toolchain-equivalence check): installing `mono-complete` + `fsharp` on Ubuntu 24.04 and building with `xbuild` against Mono's bundled F# 4.0 compiler and its `v4.6-api` reference assemblies (which is what `TargetFrameworkVersion=v4.6` in the `.fsproj` resolves to) produces a clean build with **0 errors, 0 warnings** for both `Debug` and `Release` configurations, and the resulting `ff8_tthelper.exe` starts correctly under `mono` (env var validation runs, then it blocks waiting for a screenshot, as expected). No source changes were needed to get it compiling — the code itself had not drifted from a buildable state. This only proves the F# code and project file are sound; it is **not** a substitute for building and running on real Windows, since the app depends on Windows-only APIs (see below).

## Configuration

Three previously-hardcoded, machine-specific paths in `Program.fs` are now read from environment variables (set these before running):

| Variable | Required | Meaning |
|---|---|---|
| `FF8_SCREENSHOT_DIR` | **Yes** | Folder where Steam saves FF8 screenshots, e.g. `<SteamLibrary>\userdata\<your Steam id3>\760\remote\39150\screenshots` |
| `FF8_AHK_EXE` | No (defaults to `C:\Program Files\AutoHotkey\AutoHotkey.exe`) | Path to `AutoHotkey.exe` |
| `FF8_LOG_FILE` | No (defaults to `<temp dir>\ff8helper_log.txt`) | Path to the log file |

If `FF8_SCREENSHOT_DIR` isn't set, the program fails immediately at startup with a clear error message instead of silently misbehaving.

`send.ahk` and `clearScreenshots.ahk` are resolved relative to the working directory (two levels up, i.e. the project root) rather than via an env var — this matches the original layout and only works when running from `bin\Debug\` or `bin\Release\`, e.g. via Visual Studio's Ctrl+F5. Same for `images\` and `screenshots\`, referenced from `GameStateDetection.fs`.

## Running

1. Set `FF8_SCREENSHOT_DIR` (and `FF8_AHK_EXE` if AutoHotkey isn't in the default location).
2. Run `ff8_tthelper.exe` (e.g. Ctrl+F5 in Visual Studio, so the working directory is `bin\Debug\` and the relative script/image paths resolve correctly).
3. Run Final Fantasy VIII at 1920x1080 and start a game of Triple Triad using the Open rule (or a combo including it).
4. Press **F12** on the rules screen to start the AI. It plays the match and picks up from the spoils screen.

`Program.fs`'s `main` currently calls `playOneGameAtATimeStartingFromRulesScreen()`; the other modes (`bootstrap`, `playOneTurnAtATime`, `autoPlayAgainstThatSittingDude`, etc.) are still in the file, commented out at the bottom of `main`, for manual use if needed.

## Known issues / things not fixed

- `clearScreenshots.ahk` clicks hardcoded screen coordinates in Steam's screenshot manager UI to delete old screenshots. It's wired up in `Program.fs` (`clearSteamScreenshots`) but the call site in `takeScreenshot` is commented out, so it's currently dead code. If Steam's UI has moved since this was written, the coordinates will be wrong — untested, left as-is since it isn't on the active `playOneGameAtATimeStartingFromRulesScreen()` path.
- No compile errors or missing dependencies were found — the project builds cleanly as committed (see "Building" above). Nothing needed patching beyond the path parameterization described here.
