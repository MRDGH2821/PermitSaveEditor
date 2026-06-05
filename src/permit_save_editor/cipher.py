"""ROT-39 cipher used by Potion Permit's `.rjson` save format.

Potion Permit stores saves in a custom 78-character alphabet with a symmetric
shift of 39 positions. Because the shift is exactly ``len(alphabet) // 2``,
applying the cipher twice returns the original — so the same function
decodes and encodes.

Characters not in the alphabet (whitespace, common ASCII punctuation outside
the 78-char key, non-ASCII) pass through unchanged.
"""

from __future__ import annotations

# 78-character custom alphabet lifted directly from the original C# source.
# Source: PermitSaveEditor/Data/DataManager.cs -> ExecuteCypher
_KEY: str = "QDXkW<_(V?cqK.lJ>-*y&zv9prf8biYCFeMxBm6ZnG3H4OuS1UaI5TwtoA#Rs!,7d2@L^gNhj)EP$0"
_KEY_LEN: int = len(_KEY)  # 78
_SHIFT: int = 39

# Precompute the lookup table once at import time: maps each key char to its
# shifted counterpart. Characters outside the key map to themselves.
_TRANS = str.maketrans(
    _KEY,
    "".join(_KEY[(i + _SHIFT) % _KEY_LEN] for i in range(_KEY_LEN)),
)


def rot39(text: str) -> str:
    """Apply the Potion Permit ROT-39 cipher.

    Symmetric: ``rot39(rot39(x)) == x`` for any string ``x``. Used both for
    decoding ``.rjson`` -> JSON and encoding JSON -> ``.rjson``.
    """
    return text.translate(_TRANS)


__all__ = ["rot39"]
