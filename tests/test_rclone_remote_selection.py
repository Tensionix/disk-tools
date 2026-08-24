"""The wizard must leave the remote it created selected for transfers.

Runs against app.py directly: a real OAuth wizard opens an interactive console,
so the loop is closed here rather than by driving the browser.
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
def clean_state(monkeypatch: pytest.MonkeyPatch) -> None:
    app.state["field_values"] = {}
    app.state["rclone_remotes"] = None
    monkeypatch.setattr(app, "safe_notify", lambda *args, **kwargs: None)


def test_created_remote_becomes_the_selected_one(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app, "rclone_remote_names", lambda: ["yandex", "drive"])

    app.select_created_rclone_remote({"auth_remote_name": "yandex"})

    assert app.state["field_values"]["rclone_remote_name"] == "yandex"


def test_trailing_colon_in_the_created_name_is_tolerated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app, "rclone_remote_names", lambda: ["drive"])

    app.select_created_rclone_remote({"auth_remote_name": "drive:"})

    assert app.state["field_values"]["rclone_remote_name"] == "drive"


def test_a_remote_that_was_not_actually_created_is_not_selected(monkeypatch: pytest.MonkeyPatch) -> None:
    """A wizard can exit zero while the operator cancelled inside the console."""
    monkeypatch.setattr(app, "rclone_remote_names", lambda: [])

    app.select_created_rclone_remote({"auth_remote_name": "yandex"})

    assert "rclone_remote_name" not in app.state["field_values"]


def test_missing_name_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app, "rclone_remote_names", lambda: ["drive"])

    app.select_created_rclone_remote({})

    assert "rclone_remote_name" not in app.state["field_values"]


def test_default_remote_name_follows_the_chosen_provider() -> None:
    assert app.rclone_default_auth_remote_name("remote_auth_wizard", "yandex") == "yandex"
    assert app.rclone_default_auth_remote_name("remote_auth_wizard", "dropbox") == "dropbox"
    assert app.rclone_default_auth_remote_name("remote_create_sftp", "drive") == "server"
