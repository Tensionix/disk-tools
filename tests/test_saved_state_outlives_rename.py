"""Saved state outlives a rename, and the window has to survive that.

Merging the two sections renamed the layer and dropped a pile of modes. Every
machine that had used the old sections still had `cloud` and `upload_copy_safe`
written into its GUI state — and on those machines the merged section did not
open at all. `ui.toggle` was handed a value outside its own options and raised
`ValueError: Invalid value: cloud` before a single field was drawn.

The smoke check never saw it: it builds the page from empty state, where nothing
stale exists. Only starting the window with a real saved state showed it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

gui = pytest.importorskip("system_core.ui_nicegui.app")


def open_section(saved: dict[str, str]) -> dict[str, str]:
    gui.state["field_values"] = dict(saved)
    gui.state["lines"] = []
    gui.apply_rclone_start_mode()
    return dict(gui.state["field_values"])


def visible_field_count() -> int:
    node = next(n for n in gui.root_command_nodes() if n.id == "ui_rclone_operations")
    fields = list(node.fields or [])
    defaults = {f.get("id"): gui.current_named_field_value(f.get("id"), gui.field_default(f)) for f in fields}
    return sum(1 for f in fields if gui.field_visible_when_matches(f, defaults))


@pytest.mark.parametrize("gone", ["cloud", "server", "", "  ", "нет такого"])
def test_a_layer_that_no_longer_exists_never_reaches_the_toggle(gone: str) -> None:
    """This is the exact crash: the toggle refuses a value outside its options."""
    assert gui.normalize_rclone_layer(gone) in gui.rclone_layer_defs()


def test_the_section_opens_on_a_machine_that_used_the_old_one() -> None:
    values = open_section({"rclone_layer": "cloud", "rclone_mode": "upload_copy_safe"})

    assert values["rclone_layer"] in gui.rclone_layer_defs()
    assert values["rclone_mode"] in gui.rclone_layer_modes(values["rclone_layer"])
    assert visible_field_count() > 3, "раздел открылся почти пустым"


def test_a_mode_that_outlived_its_section_is_said_out_loud() -> None:
    """Falling back silently would look like the section simply lost its fields."""
    open_section({"rclone_layer": "cloud", "rclone_mode": "upload_copy_safe"})

    said = " ".join(str(line) for line in gui.state.get("lines", []))
    assert "upload_copy_safe" in said


def test_a_mode_still_in_use_is_left_alone() -> None:
    """Only the dead ones are replaced — this must not reset the chosen screen."""
    values = open_section({"rclone_layer": "transfer", "rclone_mode": "remote_auth_wizard"})

    assert values["rclone_mode"] == "remote_auth_wizard"
    assert not gui.state.get("lines"), "ничего не должно было произойти"


def test_no_layer_name_is_written_down_where_it_can_go_stale() -> None:
    """The fallback is read off the layout table, so a rename cannot outrun it."""
    source = (ROOT / "system_core" / "ui_nicegui" / "app.py").read_text(encoding="utf-8")

    assert '"cloud"' not in source, "имя слоя снова вписано строкой"
    assert '"upload_copy_safe"' not in source.replace(
        '"upload_copy_safe": "Pipeline', ""
    ), "снесённый режим снова вписан строкой"
    assert gui.default_rclone_layer() in gui.RCLONE_LAYER_LAYOUT
