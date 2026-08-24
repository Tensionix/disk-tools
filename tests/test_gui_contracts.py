"""Guards for GUI contracts that live in app.py source rather than in the manifest.

These read the source with ast instead of importing app.py: importing the GUI
module builds project paths, loads the manifest and pulls in NiceGUI, which is
far more than a contract check needs.
"""

from __future__ import annotations

from pathlib import Path
import ast
import re
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

APP = ROOT / "system_core" / "ui_nicegui" / "app.py"
STYLES = ROOT / "system_core" / "ui_nicegui"


def rclone_fields() -> dict[str, dict]:
    tree = ast.parse(APP.read_text(encoding="utf-8"))
    node = next(
        item
        for item in tree.body
        if isinstance(item, ast.FunctionDef) and item.name == "rclone_command_node"
    )
    fields: dict[str, dict] = {}
    for dict_node in ast.walk(node):
        if not isinstance(dict_node, ast.Dict):
            continue
        # Field dicts mix literals with references such as `remote_modes`, so keep
        # only the literal pairs instead of evaluating the whole dict.
        entry = {
            key.value: value.value
            for key, value in zip(dict_node.keys, dict_node.values)
            if isinstance(key, ast.Constant)
            and isinstance(key.value, str)
            and isinstance(value, ast.Constant)
        }
        if isinstance(entry.get("id"), str):
            fields[entry["id"]] = entry
    return fields


def test_remote_field_is_a_picker_over_real_remotes() -> None:
    field = rclone_fields()["rclone_remote_name"]

    assert field["type"] == "rclone_remote_picker"


def test_remote_field_does_not_invent_a_remote_that_may_not_exist() -> None:
    field = rclone_fields()["rclone_remote_name"]

    assert field["default"] == ""
    assert field.get("placeholder") == "drive"


def test_remote_name_runtime_default_is_empty_not_a_phantom_remote() -> None:
    """rclone_cache_fields carried its own "drive" fallback, which rebuilt the phantom."""
    source = APP.read_text(encoding="utf-8")
    tree = ast.parse(source)
    node = next(
        item
        for item in tree.body
        if isinstance(item, ast.FunctionDef) and item.name == "rclone_cache_fields"
    )
    block = "\n".join(source.splitlines()[node.lineno - 1 : node.end_lineno])
    remote_line = next(line for line in block.splitlines() if '"remote_name":' in line)

    assert '"drive"' not in remote_line


def function_source(name: str) -> str:
    source = APP.read_text(encoding="utf-8")
    tree = ast.parse(source)
    node = next(
        item
        for item in tree.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == name
    )
    return "\n".join(source.splitlines()[node.lineno - 1 : node.end_lineno])


def test_remote_choice_is_a_button_row_not_a_dropdown() -> None:
    """Project rule: a mutually exclusive choice is a row of buttons; dropdowns are for data lists."""
    body = function_source("render_rclone_remote_picker_field")

    assert "ui.select(" not in body
    assert "ui.button(" in body


def css_rule(selector: str) -> str:
    """Body of the CSS rule whose selector list contains `selector`.

    Matches grouped selectors, so adding a second class to a rule does not break
    the check the way an index-based slice would.
    """
    source = "\n".join(path.read_text(encoding="utf-8") for path in sorted(STYLES.glob("*.css")))
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", source):
        selectors = [item.strip() for item in match.group(1).replace("\n", " ").split(",")]
        if selector in selectors:
            return match.group(2)
    raise AssertionError(f"CSS rule not found: {selector}")


@pytest.mark.parametrize("row_class", [".audion-rclone-remote-row", ".audion-rclone-provider-row"])
def test_button_rows_wrap_as_a_whole(row_class: str) -> None:
    """Project rule: the chip wraps as a whole, the caption inside it does not."""
    assert "flex-wrap: wrap;" in css_rule(row_class)


@pytest.mark.parametrize(
    "content_selector",
    [".audion-rclone-remote-chip .q-btn__content", ".audion-rclone-provider-tile .q-btn__content"],
)
def test_button_captions_never_wrap_inside_the_button(content_selector: str) -> None:
    assert "white-space: nowrap;" in css_rule(content_selector)


def archive_fields() -> dict[str, dict]:
    tree = ast.parse(APP.read_text(encoding="utf-8"))
    node = next(
        item
        for item in tree.body
        if isinstance(item, ast.FunctionDef) and item.name == "archive_create_command_node"
    )
    fields: dict[str, dict] = {}
    for dict_node in ast.walk(node):
        if not isinstance(dict_node, ast.Dict):
            continue
        entry = {
            key.value: value.value
            for key, value in zip(dict_node.keys, dict_node.values)
            if isinstance(key, ast.Constant)
            and isinstance(key.value, str)
            and isinstance(value, ast.Constant)
        }
        if isinstance(entry.get("id"), str):
            fields[entry["id"]] = entry
    return fields


def test_archive_encryption_is_a_button_row_not_a_dropdown() -> None:
    assert archive_fields()["archive_encryption"]["type"] == "archive_encryption_buttons"

    body = function_source("render_archive_encryption_field")
    assert "ui.select(" not in body
    assert "ui.toggle(" in body


def test_archive_encryption_buttons_keep_the_format_pruning_handler() -> None:
    """Switching the mode must still drop formats that cannot carry it."""
    body = function_source("render_archive_encryption_field")

    assert "set_archive_encryption_field" in body


def test_missing_rclone_offers_to_install_itself() -> None:
    """A missing backend must offer installation, the way the archive panel does for PeaZip."""
    body = function_source("command_tree")
    branch = body[body.index('pending.id == "ui_rclone_operations"') :]
    branch = branch[: branch.index("is_disk_route_node(pending)")]

    assert "if rclone_path is None:" in branch
    assert "start_install_rclone" in branch
    assert "start_install_system_rclone" in branch


def test_panel_says_whether_rclone_is_the_project_copy_or_the_system_one() -> None:
    """A portable tool must not silently run on whatever rclone the machine happens to have."""
    body = function_source("command_tree")
    branch = body[body.index('pending.id == "ui_rclone_operations"') :]
    branch = branch[: branch.index("is_disk_route_node(pending)")]

    assert "is_relative_to(ROOT)" in branch
    assert "PORTABLE" in branch and "SYSTEM" in branch


def test_installing_rclone_refreshes_the_panel() -> None:
    """Without a refresh the panel keeps offering to install an rclone that is already there."""
    for name in ("start_install_rclone", "start_install_system_rclone"):
        body = function_source(name)
        assert "command_tree.refresh()" in body, name
        assert "invalidate_rclone_remote_cache()" in body, name


def test_rclone_panel_opens_on_a_fact_not_on_a_constant() -> None:
    """Upload copy is only a useful landing screen once a remote exists."""
    body = function_source("select_command_node")

    assert "apply_rclone_start_mode()" in body

    start = function_source("rclone_start_mode")
    assert "find_rclone_executable" in start
    assert "rclone_remote_names()" in start
    assert "remote_auth_wizard" in start


def test_start_mode_never_overrides_a_mode_the_operator_chose() -> None:
    """The behaviour itself is checked by running it in
    test_saved_state_outlives_rename.py, which may import the GUI. Here only the
    shape: the function reads the held mode and can return without touching it.
    """
    body = function_source("apply_rclone_start_mode")

    assert 'values.get("rclone_mode")' in body, "выбранный режим даже не читается"
    assert "return" in body, "нет пути, на котором выбранный режим остаётся"
    assert "rclone_layer_modes" in body, "режим не сверяется с тем, что существует"


def test_provider_choice_is_a_tile_row_not_a_dropdown() -> None:
    body = function_source("render_rclone_auth_manager_field")
    wizard = body[body.index('mode == "remote_auth_wizard"') :]
    wizard = wizard[: wizard.index("else:")]

    assert "ui.select(" not in wizard
    assert "audion-rclone-provider-tile" in wizard
    assert "RCLONE_AUTH_BACKENDS" in wizard


def test_finished_wizard_selects_the_remote_it_created() -> None:
    body = function_source("start_rclone_operations")

    assert "select_created_rclone_remote(options)" in body
    assert "remote_auth_wizard" in body


def test_styles_live_in_files_rather_than_inside_app_py() -> None:
    """add_styles was a 2464-line function holding ~100 KB of CSS as a literal."""
    body = function_source("add_styles")

    assert "application_css(" in body
    assert len(body.splitlines()) < 30
    assert {path.name for path in STYLES.glob("*.css")} >= {"tokens.css", "theme.css"}


def test_every_stylesheet_has_balanced_braces() -> None:
    for path in sorted(STYLES.glob("*.css")):
        text = path.read_text(encoding="utf-8")
        assert text.count("{") == text.count("}"), path.name


def test_the_window_has_one_transfer_section_rather_than_two_layers() -> None:
    """Cloud and Server were split by tool, not by task.

    The same operation therefore lived in two places with two mental models, and
    the endpoint route existed only in Server — so cloud to cloud, the thing the
    section was built for, could not be reached from the Cloud window at all.

    One section now, and its shape comes from one table: the layer's set of modes
    is derived from its groups rather than spelled out beside them, which is what
    let a mode be listed in a group and missing from the layer and so never
    appear.
    """
    import sys

    ROOT = Path(__file__).resolve().parents[1]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from system_core.ui_nicegui.app import RCLONE_LAYER_LAYOUT

    assert list(RCLONE_LAYER_LAYOUT) == ["transfer"]

    groups = RCLONE_LAYER_LAYOUT["transfer"]["groups"]
    assert [group["id"] for group in groups] == [
        "transfer_run",
        "cloud_storage",
        "cloud_auth",
        "cloud_diag",
    ]
    for group in groups:
        assert group["title"] and group["title_ru"]
        assert group["default"] in group["modes"]


def test_no_mode_is_offered_that_no_longer_exists() -> None:
    """A group naming a deleted mode draws a button that raises when pressed."""
    import sys

    ROOT = Path(__file__).resolve().parents[1]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from system_core.services.rclone_service import RCLONE_OPERATION_MODES
    from system_core.ui_nicegui.app import RCLONE_LAYER_LAYOUT

    offered = {
        mode
        for layer in RCLONE_LAYER_LAYOUT.values()
        for group in layer["groups"]
        for mode in group["modes"]
    }

    assert not (offered - set(RCLONE_OPERATION_MODES)), "в группе есть режим, которого больше нет"


def test_the_status_row_says_which_state_the_run_is_in() -> None:
    """Colour carries the state, so the state has to be decided in one place."""
    from system_core.ui_nicegui import app as gui

    previous = dict(gui.state)
    try:
        gui.state["running"] = True
        assert gui.run_state() == "running"
        assert "audion-status-running" in gui.status_row_classes()

        gui.state["running"] = False
        gui.state["exit_code"] = None
        assert gui.run_state() == "idle"

        gui.state["exit_code"] = 0
        assert gui.run_state() == "done"
        assert "audion-status-done" in gui.status_row_classes()

        gui.state["exit_code"] = 2
        assert gui.run_state() == "error"
        assert "audion-status-error" in gui.status_row_classes()
    finally:
        gui.state.update(previous)


def test_the_clock_reads_as_minutes_and_seconds() -> None:
    from system_core.ui_nicegui import app as gui

    assert gui.elapsed_text(None) == "—"
    assert gui.elapsed_text(0) == "00:00"
    assert gui.elapsed_text(63.4) == "01:03"
    assert gui.elapsed_text(3599) == "59:59"


def test_the_status_row_is_styled_for_every_state() -> None:
    stylesheet = (ROOT / "system_core" / "ui_nicegui" / "theme.css").read_text(encoding="utf-8")

    for rule in (
        ".audion-status-row",
        ".audion-status-running",
        ".audion-status-done",
        ".audion-status-error",
        ".audion-status-bar",
    ):
        assert rule in stylesheet, rule


def test_the_panel_writes_only_what_changed() -> None:
    """An idle window used to send ten element updates a second."""
    body = function_source("build_ui")

    assert 'shown = {' in body
    assert "def show(" in body
    assert "if shown[key] != value:" in body
