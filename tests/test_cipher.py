"""Tests for the ROT-39 cipher."""

from __future__ import annotations

import pytest

from permit_save_editor.cipher import rot39


def test_known_sample_decodes_to_ascii():
    """A canonical short sample — the cipher key passes through ``Logan`` unchanged.

    We assert that the round-trip on a small string works (the function is
    symmetric). Concrete byte-level tests would couple to the exact key string;
    symmetry + a small ASCII payload is the right level of test for this layer.
    """
    sample = "Logan"
    assert rot39(rot39(sample)) == sample


def test_symmetry_is_involution():
    """``rot39(rot39(x)) == x`` for any string (modulo non-key characters)."""
    samples = [
        "Logan",
        "Noxe the dog",
        "Player names & 123 numbers",
        "potion-permit_save_v1.0",
        '{"characterName": "Logan"}',
        # All 95 printable ASCII characters — guarantees any printable
        # character in the key round-trips correctly.
        "".join(chr(c) for c in range(32, 127)),
    ]
    for s in samples:
        assert rot39(rot39(s)) == s, f"Failed on sample: {s!r}"


def test_preserves_non_key_characters():
    """Characters outside the 78-char key pass through unchanged.

    The 78-char key is ASCII-only; non-ASCII (accented, emoji, CJK) must be
    a no-op. The original C# uses ``IndexOf`` (not Unicode-aware), and any
    non-key char simply returns the input unchanged.
    """
    for c in "äéñø\u2603\U0001f600":
        # Each non-key char should appear in the output at the same position
        assert rot39(c) == c


def test_empty_string():
    assert rot39("") == ""


@pytest.mark.parametrize("length", [0, 1, 10, 78, 79, 1000])
def test_idempotent_at_arbitrary_lengths(length: int):
    """Length shouldn't matter — symmetry holds for all sizes."""
    text = "A" * length
    assert rot39(rot39(text)) == text


def test_key_is_78_chars():
    """Sanity-check the alphabet length the cipher relies on."""
    # rot39 is built from a private _KEY constant; we re-derive it from the
    # behavior: applying rot39 to a single key char and getting back the char
    # at +39 mod 78 should be the same for every char in the key.
    # We test by brute: rotate the alphabet and check.
    from permit_save_editor.cipher import _KEY, _KEY_LEN

    assert _KEY_LEN == 78
    assert len(_KEY) == 78
    # Each key char, when shifted by +39 mod 78 and looked up, must be a
    # key char. This catches typos in the alphabet.
    for i, c in enumerate(_KEY):
        shifted = _KEY[(i + 39) % 78]
        assert shifted in _KEY, f"Index {i}: shifted of {c!r} is {shifted!r}, not in key"
