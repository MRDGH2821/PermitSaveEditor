"""Platform-aware default save directory for Potion Permit."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def default_save_dir() -> Path:
    """Return the platform-appropriate default save directory.

    The Unity game stores saves under its ``Application.persistentDataPath``,
    which the cross-platform engine maps to:

    * Windows: ``%LOCALAPPDATA%/../LocalLow/MasshiveMedia/Potion Permit``
      (the ``..`` is meaningful only when ``LOCALAPPDATA`` is set)
    * macOS:   ``~/Library/Application Support/MasshiveMedia/Potion Permit``
    * Linux:   ``~/.local/share/unity3d/MasshiveMedia/Potion Permit``
      (the path used when running the Windows game under Wine/Proton)

    The directory is created on first call if it doesn't exist.
    """
    if sys.platform == "win32":
        local_app_data = os.environ.get(
            "LOCALAPPDATA", str(Path.home() / "AppData" / "Local")
        )
        path = (Path(local_app_data) / ".." / "LocalLow" / "MasshiveMedia" / "Potion Permit").resolve()
    elif sys.platform == "darwin":
        path = Path.home() / "Library" / "Application Support" / "MasshiveMedia" / "Potion Permit"
    else:
        path = Path.home() / ".local" / "share" / "unity3d" / "MasshiveMedia" / "Potion Permit"

    path.mkdir(parents=True, exist_ok=True)
    return path


__all__ = ["default_save_dir"]
