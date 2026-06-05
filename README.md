# Permit Save Editor

A cross-platform save editor for **Potion Permit**, ported from the original
WPF/.NET app to Python + PySide6.

> **Status:** functional port — all original features reproduced plus a CLI
> for batch operations.

## What it does

- Load Potion Permit `.rjson` save files (custom ROT-39 cipher over a 78-char
  alphabet)
- Edit the same fields the WPF editor exposed: player/dog names, gold, wood,
  stone, carpenter/blacksmith/badge level, three fishing levels, gender, and
  five character colors (skin, hair, eyes, outfit, cape)
- Bulk-unlock: all skins, hair, clothes, capes, fast-travel points, recipes,
  potions, and heal-all NPCs
- Export the loaded save as a plain `.json` (cipher-free) for debugging

## Installation

Requires **Python 3.11+** and [uv](https://docs.astral.sh/uv/).

```bash
# CLI only (no GUI deps)
uv sync

# CLI + GUI
uv sync --extra gui
```

## Usage

### GUI

```bash
uv run --extra gui ppse gui
```

Or after install: `ppse gui`.

The GUI mirrors the WPF original: a General tab (stats + character) and an
Unlockables tab (eight bulk-unlock buttons). Dark theme, file picker defaults
to the game's save directory, `.bak` backup is written before any in-place save.

### CLI

```bash
uv run ppse --help
uv run ppse inspect path/to/GameSave1.rjson
uv run ppse convert path/to/GameSave1.rjson          # → GameSave1.json
uv run ppse convert path/to/GameSave1.json           # → GameSave1.rjson
uv run ppse set    path/to/GameSave1.rjson --gold 999999 --carpenter-level 2
uv run ppse unlock path/to/GameSave1.rjson --all
uv run ppse paths                                    # print default save dir
```

Every command that writes to a save file creates a `.bak` first, so the
original is always recoverable.

### Save file location

| OS      | Path                                                                |
|---------|---------------------------------------------------------------------|
| Windows | `%LOCALAPPDATA%\..\LocalLow\MasshiveMedia\Potion Permit\`            |
| macOS   | `~/Library/Application Support/MasshiveMedia/Potion Permit/`        |
| Linux   | `~/.local/share/unity3d/MasshiveMedia/Potion Permit/` *(Wine/Proton)* |

The GUI's file picker opens the platform-appropriate directory by default.
Use `uv run ppse paths` to print it.

## Development

```bash
uv sync --extra gui
uv run pytest                              # run the test suite
uv run pytest --cov=permit_save_editor     # with coverage
uv run ruff check .                        # lint
uv run ruff format .                       # format
```

## Architecture

```
src/permit_save_editor/
├── __init__.py          # public API re-exports + __version__
├── __main__.py          # `python -m permit_save_editor`
├── cli.py               # typer app — subcommand dispatch
├── cipher.py            # rot39() — the game's Caesar cipher
├── io.py                # load_save / save_save with .bak handling
├── paths.py             # default save directory per platform
├── models.py            # pydantic v2 models (GameSaveData + sub-models)
├── commands/            # one module per typer subcommand
│   ├── gui.py           # launch the PySide6 GUI
│   ├── inspect.py       # headless save summary
│   ├── unlock.py        # bulk-unlock flags
│   ├── set.py           # set individual fields
│   └── convert.py       # .rjson <-> .json round-trip
└── ui/                  # PySide6 frontend
    ├── main_window.py   # the ported MainWindow
    └── theme.py         # dark QSS stylesheet
```

`cipher.py`, `io.py`, and `models.py` have **no GUI dependencies** — they are
the regression-testable core. The CLI uses them directly; the GUI is just a
Qt front-end on top.

## License

MIT.
