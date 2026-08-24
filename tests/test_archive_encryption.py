"""Behaviour of the archive encryption mode, which is a row of buttons in the GUI.

This module imports app.py. That costs a couple of seconds and creates the
project folders the GUI expects, but it is the only way to exercise the mode
switch itself rather than its source text.
"""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from system_core.ui_nicegui import app  # noqa: E402


@pytest.fixture(autouse=True)
def clean_field_values() -> None:
    app.state["field_values"] = {}


@pytest.mark.parametrize("mode", ["password", "names"])
def test_zip_is_never_encryptable(mode: str) -> None:
    """7-Zip closes ZIP with the broken ZipCrypto, so ZIP carries no encryption at all."""
    assert "zip" not in app.archive_encryption_supported_formats(mode)
    assert app.prune_archive_formats_for_encryption(["zip", "7z"], mode) == ["7z"]

    with pytest.raises(RuntimeError, match="only for 7Z and SFX"):
        app.assert_encryption_supported("zip", mode)


@pytest.mark.parametrize("format_id", ["tar", "gz", "zstd", "lz4"])
def test_tar_family_carries_no_encryption(format_id: str) -> None:
    with pytest.raises(RuntimeError):
        app.assert_encryption_supported(format_id, "password")


def test_encryption_is_available_for_7z_and_sfx() -> None:
    assert app.archive_encryption_supported_formats("password") == {"7z", "sfx"}
    assert app.archive_encryption_supported_formats("names") == {"7z", "sfx"}

    app.assert_encryption_supported("7z", "password")
    app.assert_encryption_supported("sfx", "names")


def test_no_encryption_keeps_every_format() -> None:
    assert app.prune_archive_formats_for_encryption(["zip", "tar"], "none") == ["zip", "tar"]


def test_seven_zip_gets_aes_and_name_encryption_only_when_asked() -> None:
    assert app.archive_encryption_args("7z", "password", "pw") == ["-ppw"]
    assert app.archive_encryption_args("7z", "names", "pw") == ["-ppw", "-mhe=on"]
    assert app.archive_encryption_args("7z", "none", "pw") == []


def test_switching_the_mode_prunes_the_selected_formats() -> None:
    app.state["field_values"]["archive_formats"] = ["zip", "7z"]

    app.set_archive_encryption_field("names")

    assert app.state["field_values"]["archive_encryption"] == "names"
    assert app.state["field_values"]["archive_formats"] == ["7z"]


def test_unknown_mode_falls_back_to_no_encryption() -> None:
    app.set_archive_encryption_field("something-else")

    assert app.state["field_values"]["archive_encryption"] == "none"


def test_scope_hint_names_the_algorithm_and_the_formats() -> None:
    app.settings.language = "ru"

    assert "все форматы" in app.archive_encryption_scope_hint("none").lower()
    for mode in ("password", "names"):
        hint = app.archive_encryption_scope_hint(mode)
        assert "AES-256" in hint
        assert "7Z, SFX" in hint
        assert "ZIP" not in hint


def test_zip_checkbox_explains_why_it_cannot_be_encrypted() -> None:
    app.settings.language = "ru"
    reason = app.archive_format_disabled_reason("zip", "password")

    assert "ZipCrypto" in reason
    assert "7Z" in reason


def test_tar_checkbox_says_the_format_has_no_encryption() -> None:
    app.settings.language = "ru"

    assert "шифрование" in app.archive_format_disabled_reason("tar", "password").lower()
