"""One master, a list of machines, and the single-target fields kept in step.

The section used to have one destination. That is the special case: a reference
folder changes and the change is carried out to every other machine, which a pair
cannot express and which nobody does three times by hand without eventually
forgetting one.

The list is the new truth, but the first entry is mirrored back into the old
single-target fields, so the panels, previews and command builder that read them
keep working while the section is being rebuilt around them.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def gui():
    from system_core.ui_nicegui import app as module

    module.state["transfer_targets"] = None
    module.state["field_values"] = {}
    yield module
    module.state["transfer_targets"] = None
    module.state["field_values"] = {}


def test_the_list_starts_from_whatever_the_single_target_already_held(gui) -> None:
    gui.state["field_values"].update(
        {"rclone_target_kind": "saved_remote", "rclone_target_remote_name": "r2",
         "rclone_target_remote_path": "releases"}
    )

    rows = gui.transfer_target_rows()

    assert len(rows) == 1
    assert rows[0]["remote_name"] == "r2" and rows[0]["remote_path"] == "releases"


def test_the_first_machine_stays_mirrored_into_the_old_fields(gui, monkeypatch) -> None:
    """Everything else in the section still reads those, and will for a while."""
    monkeypatch.setattr(gui.command_tree, "refresh", lambda: None)

    gui.set_transfer_target_rows(
        [
            {"kind": "saved_remote", "remote_name": "server", "remote_path": "/srv/mirror"},
            {"kind": "saved_remote", "remote_name": "r2", "remote_path": "releases"},
        ]
    )

    assert gui.state["field_values"]["rclone_target_remote_name"] == "server"
    assert gui.state["field_values"]["rclone_target_remote_path"] == "/srv/mirror"


def test_machines_are_added_and_dropped(gui, monkeypatch) -> None:
    monkeypatch.setattr(gui.command_tree, "refresh", lambda: None)

    gui.add_transfer_target()
    gui.add_transfer_target()
    assert len(gui.transfer_target_rows()) == 3

    gui.remove_transfer_target(1)
    assert len(gui.transfer_target_rows()) == 2


def test_the_last_machine_cannot_be_dropped(gui, monkeypatch) -> None:
    """An empty list would leave a run button with nothing behind it."""
    monkeypatch.setattr(gui.command_tree, "refresh", lambda: None)

    gui.remove_transfer_target(0)

    assert len(gui.transfer_target_rows()) == 1


def test_each_machine_gets_its_own_engine(gui, monkeypatch) -> None:
    """They need not be alike: a second disk, a server, a cloud."""
    from system_core.services.rclone_service import RemoteBackend
    from system_core.services.transfer_service import (
        ENGINE_RCLONE,
        ENGINE_ROBOCOPY,
        OPERATION_MIRROR,
        fan_out_commands,
    )

    monkeypatch.setattr(gui.command_tree, "refresh", lambda: None)
    gui.state["rclone_remote_backends"] = {"r2": RemoteBackend("s3", "Cloudflare")}
    gui.state["field_values"]["rclone_source_kind"] = "workbench_source"
    gui.set_transfer_target_rows(
        [
            {"kind": "workbench_target", "remote_name": "", "remote_path": ""},
            {"kind": "saved_remote", "remote_name": "r2", "remote_path": "releases"},
        ]
    )

    source = gui.endpoint_spec(gui.current_rclone_options(), "source")
    targets = [gui.transfer_target_endpoint(row) for row in gui.transfer_target_rows()]
    run = fan_out_commands(OPERATION_MIRROR, source, targets, russian=True)

    assert [item["engine"] for item in run] == [ENGINE_ROBOCOPY, ENGINE_RCLONE]
    assert "/MIR" in run[0]["command"]
    assert run[1]["command"][1] == "sync"
