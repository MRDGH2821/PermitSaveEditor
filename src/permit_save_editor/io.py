"""File I/O for Potion Permit save files.

Handles the auto-detection between ``.rjson`` (game's native, ROT-39 encoded)
and ``.json`` (debug/diagnostic) formats, plus a uniform ``.bak`` backup
policy: any in-place write to an existing file first renames the original to
``<name>.bak`` (if one isn't already there), so the user always has a
recovery path.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from .cipher import rot39
from .models import GameSaveData

# Suffixes the editor recognizes.
RJSON_SUFFIX = ".rjson"
JSON_SUFFIX = ".json"
BACKUP_SUFFIX = ".bak"


def is_obfuscated(path: Path) -> bool:
    """True if the file is the game's native obfuscated ``.rjson`` format."""
    return path.suffix.lower() == RJSON_SUFFIX


def load_save(path: Path | str) -> GameSaveData:
    """Read a save file and return a populated ``GameSaveData``.

    Auto-detects the format by extension: ``.rjson`` is deciphered before
    parsing, ``.json`` is parsed as-is. Raises ``ValueError`` on parse
    failure with the underlying exception chained.
    """
    path = Path(path)
    raw = path.read_text(encoding="utf-8")

    if is_obfuscated(path):
        try:
            raw = rot39(raw)
        except Exception as exc:  # pragma: no cover - rot39 can't fail on str
            raise ValueError(f"Failed to decipher {path}: {exc}") from exc

    try:
        data: dict[str, Any] = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc

    return GameSaveData.model_validate(data)


def save_save(
    save: GameSaveData,
    path: Path | str,
    *,
    obfuscate: bool | None = None,
    backup: bool = True,
) -> Path:
    """Write ``save`` to ``path``.

    Parameters
    ----------
    save:
        The data to serialize.
    path:
        Destination file. Format is chosen from the extension unless
        ``obfuscate`` is set explicitly.
    obfuscate:
        ``True`` to write a ``.rjson`` (game-native), ``False`` to write a
        ``.json`` (debug). ``None`` (default) infers from the suffix.
    backup:
        If True and the destination already exists, move the existing file
        aside to ``<name>.bak`` first (only if a ``.bak`` doesn't already
        exist). Default True.

    Returns
    -------
    The path that was actually written.
    """
    path = Path(path)
    if obfuscate is None:
        obfuscate = is_obfuscated(path) or path.suffix == ""

    if backup and path.exists():
        bak = path.with_name(path.name + BACKUP_SUFFIX)
        if not bak.exists():
            shutil.move(str(path), str(bak))

    text = json.dumps(save.model_dump(by_alias=True), indent=4, ensure_ascii=False)
    if obfuscate:
        text = rot39(text)
    path.write_text(text, encoding="utf-8")
    return path


def dump_plain_json(save: GameSaveData, path: Path | str) -> Path:
    """Write the save as a debug-friendly plain JSON (no cipher).

    This is the Python equivalent of the C# "Download Plain JSON File"
    button. Does **not** create a ``.bak`` — the user is exporting, not
    mutating the original.
    """
    path = Path(path)
    text = json.dumps(save.model_dump(by_alias=True), indent=4, ensure_ascii=False)
    path.write_text(text, encoding="utf-8")
    return path


__all__ = [
    "BACKUP_SUFFIX",
    "JSON_SUFFIX",
    "RJSON_SUFFIX",
    "dump_plain_json",
    "is_obfuscated",
    "load_save",
    "save_save",
]
