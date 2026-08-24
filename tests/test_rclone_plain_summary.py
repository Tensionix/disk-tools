"""Every runnable rclone mode must say what it does and what it leaves alone."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from system_core.ui_nicegui import app  # noqa: E402


@dataclass
class Spec:
    mode: str
    remote_spec: str = ""
    source_spec: str = ""
    target_spec: str = ""
    local_source: Path | None = None
    local_target: Path | None = None


@pytest.fixture(autouse=True)
def russian() -> None:
    app.settings.language = "ru"


INFO_MODES = ["list_remote_path", "about_remote", "remote_test", "list_remotes", "version"]
SETUP_MODES = ["config", "gui", "remote_auth_wizard", "remote_create_sftp"]

# Read off the live set rather than written out here. The hand-written list
# outlived the modes it named: five of them were gone and the tests still asked
# for their sentences, so a section that no longer existed looked covered.
#
# transfer_run is excluded on purpose: it is the one mode whose explanation is
# not a sentence. It gets a whole route field — direction, engine, and a refusal
# when the pair is impossible — drawn by render_transfer_route_field.
LIVE_MODES = sorted(set(app.RCLONE_OPERATION_MODES) - {"transfer_run"})


@pytest.mark.parametrize("mode", LIVE_MODES)
def test_every_mode_has_a_sentence(mode: str) -> None:
    sentence, tone = app.rclone_plain_summary(
        Spec(mode=mode, remote_spec="yandex:Backup", source_spec="drive:A", target_spec="yandex:B")
    )

    assert sentence
    assert tone in {"write", "readonly", "interactive"}


@pytest.mark.parametrize("mode", INFO_MODES)
def test_read_only_modes_promise_not_to_change_anything(mode: str) -> None:
    sentence, tone = app.rclone_plain_summary(Spec(mode=mode, remote_spec="yandex:Backup"))

    assert tone == "readonly"
    assert "не меняется" in sentence or "Только чтение" in sentence or "версию" in sentence


def test_the_transfer_explains_itself_through_its_own_route_field() -> None:
    """Not a sentence but a whole field, and it must be on screen in that mode.

    Without it the section is a RUN button over a pair nobody can check: which
    way the data goes, which engine carries it, and whether the pair is refused
    at all were invisible before this field existed.
    """
    node = next(n for n in app.root_command_nodes() if n.id == "ui_rclone_operations")
    route = next((f for f in (node.fields or []) if f.get("id") == "transfer_route"), None)

    assert route, "у трансфера нет поля маршрута"
    assert "transfer_run" in route.get("visible_when", {}).get("rclone_mode", [])


def test_the_one_mode_that_removes_things_says_so() -> None:
    """A vague label is exactly what a destructive action must not hide behind."""
    sentence, tone = app.rclone_plain_summary(Spec(mode="storage_cleanup", remote_spec="yandex:Backup"))

    assert tone == "write"
    assert "не возвращается" in sentence


def test_the_sentence_matches_the_command_that_will_run() -> None:
    """The first draft of these sentences said dedupe merges duplicates and
    cleanup empties the trash. It runs `dedupe list`, which changes nothing, and
    `cleanup`, which drops abandoned multipart uploads — so both were wrong about
    a destructive operation, which is worse than saying nothing at all.
    """
    dedupe, tone = app.rclone_plain_summary(Spec(mode="storage_dedupe", remote_spec="yandex:Backup"))
    assert tone == "readonly"
    assert "ничего не удаляется" in dedupe.lower()

    cleanup, _ = app.rclone_plain_summary(Spec(mode="storage_cleanup", remote_spec="yandex:Backup"))
    assert "многочастн" in cleanup, "должно говорить про недозалитые части, а не про корзину"


def test_mkdir_without_a_path_says_there_is_nothing_to_create() -> None:
    """rclone mkdir yandex: with no path is a trap: it looks armed and does nothing useful."""
    sentence, tone = app.rclone_plain_summary(Spec(mode="mkdir_remote", remote_spec="yandex:"))

    assert tone == "interactive"
    assert "нечего" in sentence

    ready, ready_tone = app.rclone_plain_summary(Spec(mode="mkdir_remote", remote_spec="yandex:Backup"))
    assert ready_tone == "write"
    assert "Создам папку" in ready


def test_unknown_mode_stays_silent_rather_than_guessing() -> None:
    assert app.rclone_plain_summary(Spec(mode="something_new"))[0] == ""
