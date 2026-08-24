"""The argv that will actually run, for every operation on both engines.

Up to here the transfer layer only decided things. This is where a decision
becomes a command, and it is the first place a mistake would touch real disks —
so every shape is pinned, including the ones that must be refused.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from system_core.services.rclone_service import RcloneEndpointSpec  # noqa: E402
from system_core.services.transfer_service import (  # noqa: E402
    ENGINE_RCLONE,
    ENGINE_ROBOCOPY,
    OPERATION_MIRROR,
    OPERATION_MOVE,
    OPERATION_ONE_WAY,
    OPERATION_TWO_WAY,
    OPERATION_VERIFY,
    build_transfer_command,
    extension_filter_args,
    fan_out_commands,
    normalize_extension_masks,
    write_filter_file,
    run_succeeded,
)


def here(path: str = "C:/master") -> RcloneEndpointSpec:
    return RcloneEndpointSpec(kind="workbench_source", spec=path, label=path, local_path=Path(path))


def share(path: str = r"\\nas\backup") -> RcloneEndpointSpec:
    return RcloneEndpointSpec(kind="workbench_target", spec=path, label=path, local_path=Path(path))


def remote(name: str = "r2") -> RcloneEndpointSpec:
    return RcloneEndpointSpec(
        kind="saved_remote", spec=f"{name}:releases", label=name, remote_name=name, remote_path="releases"
    )


@pytest.mark.parametrize(
    ("operation", "expected"),
    [
        (OPERATION_ONE_WAY, "copy"),
        (OPERATION_MIRROR, "sync"),
        (OPERATION_TWO_WAY, "bisync"),
        (OPERATION_VERIFY, "check"),
    ],
)
def test_each_operation_becomes_its_rclone_command(operation: str, expected: str) -> None:
    command = build_transfer_command(operation, here(), remote(), engine=ENGINE_RCLONE, rclone_exe="rclone.exe")

    assert command[:2] == ["rclone.exe", expected]
    assert command[2:4] == ["C:/master", "r2:releases"]


def test_a_local_copy_is_robocopy_and_carries_the_flags_that_earn_their_place() -> None:
    command = build_transfer_command(
        OPERATION_ONE_WAY, here("C:/in"), here("D:/out"), engine=ENGINE_ROBOCOPY, threads=16
    )

    assert command[:3] == ["robocopy", "C:\\in", "D:\\out"]
    assert "/E" in command and "/COPY:DAT" in command and "/XJ" in command
    assert "/MT:16" in command
    assert "/MIR" not in command, "копирование не должно удалять в приёмнике"
    # Both volumes are NTFS on this machine, so the coarse-time flags stay off.
    assert "/FFT" not in command


def test_a_mirror_is_the_only_robocopy_run_that_deletes() -> None:
    command = build_transfer_command(OPERATION_MIRROR, here("C:/in"), here("D:/out"), engine=ENGINE_ROBOCOPY)

    assert "/MIR" in command
    # /MIR already implies /E; passing both is noise the log has to carry.
    assert "/E" not in command


def test_a_share_brings_the_coarse_time_flags_back() -> None:
    command = build_transfer_command(OPERATION_ONE_WAY, here("C:/in"), share(), engine=ENGINE_ROBOCOPY)

    assert "/FFT" in command and "/DST" in command


@pytest.mark.parametrize("operation", [OPERATION_TWO_WAY, OPERATION_VERIFY])
def test_robocopy_refuses_what_it_cannot_do_instead_of_guessing(operation: str) -> None:
    """A mismatch here is a programming error, not the user's, and it says so."""
    with pytest.raises(ValueError, match="transfer_engine"):
        build_transfer_command(operation, here("C:/in"), here("D:/out"), engine=ENGINE_ROBOCOPY)


def test_the_mirror_ceiling_reaches_the_command_only_when_asked_for() -> None:
    plain = build_transfer_command(OPERATION_MIRROR, here(), remote(), engine=ENGINE_RCLONE)
    capped = build_transfer_command(
        OPERATION_MIRROR, here(), remote(), engine=ENGINE_RCLONE, delete_ceiling=50
    )

    assert "--max-delete" not in plain
    assert capped[-2:] == ["--max-delete", "50"]


def test_two_way_keeps_its_memory_in_the_project() -> None:
    command = build_transfer_command(
        OPERATION_TWO_WAY, remote("gdrive"), remote("r2"), engine=ENGINE_RCLONE, project_root=ROOT
    )

    assert "--workdir" in command
    assert "AppData" not in " ".join(command)


def test_robocopy_success_is_a_bitmask_not_a_zero() -> None:
    """Bit 0 means files were copied, bit 1 that extras exist, bit 2 that some
    mismatched. Reading it as nought-or-error calls every successful copy a
    failure, which is the classic way to get this wrong."""
    for code in (0, 1, 2, 3, 7):
        assert run_succeeded(ENGINE_ROBOCOPY, code)
    for code in (8, 16):
        assert not run_succeeded(ENGINE_ROBOCOPY, code)
    assert run_succeeded(ENGINE_RCLONE, 0)
    assert not run_succeeded(ENGINE_RCLONE, 1)


def test_move_carries_over_and_clears_the_source() -> None:
    """One of the few places Robocopy matches rclone command for command."""
    local = build_transfer_command(OPERATION_MOVE, here("C:/in"), here("D:/out"), engine=ENGINE_ROBOCOPY)
    cloud = build_transfer_command(OPERATION_MOVE, here(), remote(), engine=ENGINE_RCLONE)

    assert "/MOVE" in local
    assert cloud[1] == "move"


@pytest.mark.parametrize(
    ("engine", "expected"),
    [(ENGINE_RCLONE, ["--dry-run"]), (ENGINE_ROBOCOPY, ["/L", "/BYTES", "/FP"])],
)
def test_a_dry_run_is_a_switch_on_any_operation_not_a_mode_of_its_own(engine: str, expected: list[str]) -> None:
    """Every operation has a version of "show me first", and the project already
    carried one — robocopy_scan — as a separate mode, which is a flag wearing a
    button. Seeing what a mirror to three machines would delete is exactly when
    it matters."""
    target = remote() if engine == ENGINE_RCLONE else here("D:/out")

    plain = build_transfer_command(OPERATION_MIRROR, here("C:/in"), target, engine=engine)
    dry = build_transfer_command(OPERATION_MIRROR, here("C:/in"), target, engine=engine, dry_run=True)

    assert not any(flag in plain for flag in expected)
    assert all(flag in dry for flag in expected)
    # Nothing else moves: the same run, only watched.
    assert [item for item in dry if item not in expected] == plain


def test_the_whole_fan_out_is_built_before_anything_runs() -> None:
    """So a refusal on the third machine is found before the first is touched."""
    machines = [here("D:/replica"), share(), remote()]

    run = fan_out_commands(OPERATION_MIRROR, here("C:/master"), machines, russian=True, threads=8)

    assert [item["index"] for item in run] == [0, 1, 2]
    assert [item["engine"] for item in run] == [ENGINE_ROBOCOPY, ENGINE_ROBOCOPY, ENGINE_RCLONE]
    assert all(item["command"] for item in run)
    assert "/MIR" in run[0]["command"]
    assert run[2]["command"][1] == "sync"


def test_a_pointless_pair_is_refused_and_carries_no_command() -> None:
    run = fan_out_commands(OPERATION_MIRROR, here("C:/master"), [here("C:/master"), here("D:/ok")], russian=True)

    assert run[0]["refused"] and not run[0]["command"]
    assert not run[1]["refused"] and run[1]["command"]


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        (["docx", ".pdf", "*.mp4"], ["*.docx", "*.pdf", "*.mp4"]),
        ("docx, pdf; mp4", ["*.docx", "*.pdf", "*.mp4"]),
        (["DOCX", "docx", "*.DOCX"], ["*.docx"]),
        ([], []),
        (None, []),
    ],
)
def test_extensions_are_accepted_however_they_are_written(given, expected) -> None:
    """The picker offers groups and single entries, and the same extension can
    arrive from two groups at once."""
    assert normalize_extension_masks(given) == expected


def test_each_engine_is_told_the_same_choice_in_its_own_words() -> None:
    masks = ["*.docx", "*.pdf"]

    assert extension_filter_args(ENGINE_RCLONE, masks) == ["--include", "*.docx", "--include", "*.pdf"]
    assert extension_filter_args(ENGINE_ROBOCOPY, masks) == ["*.docx", "*.pdf"]
    assert extension_filter_args(ENGINE_RCLONE, []) == []


def test_robocopy_masks_sit_where_robocopy_expects_them() -> None:
    """Straight after source and destination. Anywhere else and robocopy reads
    them as another argument entirely."""
    command = build_transfer_command(
        OPERATION_MIRROR, here("C:/in"), here("D:/out"), engine=ENGINE_ROBOCOPY, masks=["docx"]
    )

    assert command[:4] == ["robocopy", r"C:\in", r"D:\out", "*.docx"]


def test_the_rclone_pattern_matches_at_every_depth() -> None:
    """`*.docx` reaches files in subfolders; the obvious-looking `**/*.docx`
    misses everything in the top folder, which is where they usually are.
    Measured against a real tree, not assumed."""
    command = build_transfer_command(
        OPERATION_ONE_WAY, here(), remote(), engine=ENGINE_RCLONE, masks=["docx"]
    )

    assert "--include" in command
    assert command[command.index("--include") + 1] == "*.docx"
    assert not any(str(part).startswith("**/") for part in command)


def test_a_whole_filename_stays_a_whole_filename() -> None:
    """Thumbs.db and desktop.ini are the ones people actually want gone. Turning
    them into *.thumbs.db matches nothing at all."""
    assert normalize_extension_masks(["tmp", "Thumbs.db", "desktop.ini", ".BAK"]) == [
        "*.tmp",
        "Thumbs.db",
        "desktop.ini",
        "*.bak",
    ]


def test_excluding_without_including_is_take_everything_except() -> None:
    junk = ["tmp", "bak", "Thumbs.db"]

    cloud = build_transfer_command(OPERATION_ONE_WAY, here(), remote(), engine=ENGINE_RCLONE, excluded_masks=junk)
    local = build_transfer_command(
        OPERATION_ONE_WAY, here("C:/in"), here("D:/out"), engine=ENGINE_ROBOCOPY, excluded_masks=junk
    )

    assert cloud.count("--exclude") == 3
    assert "--include" not in cloud
    assert local[local.index("/XF") + 1 :] == ["*.tmp", "*.bak", "Thumbs.db"]


def test_an_exclusion_beside_an_inclusion_is_left_off_the_rclone_command() -> None:
    """Any --include already excludes everything else — rclone's own rule,
    checked across five orderings against a real tree. A flag that changes
    nothing is a question for whoever reads the log."""
    command = build_transfer_command(
        OPERATION_ONE_WAY, here(), remote(), engine=ENGINE_RCLONE, masks=["docx"], excluded_masks=["tmp"]
    )

    assert "--include" in command
    assert "--exclude" not in command


def test_an_extension_in_both_lists_is_not_carried() -> None:
    command = build_transfer_command(
        OPERATION_ONE_WAY, here(), remote(), engine=ENGINE_RCLONE, masks=["docx", "tmp"], excluded_masks=["tmp"]
    )

    assert command.count("--include") == 1
    assert "*.tmp" not in command


def test_a_long_list_of_masks_goes_to_a_file(tmp_path) -> None:
    """The whole library is 301 extensions: 602 arguments and nearly five
    thousand characters. That fits the command line and fits nobody's eyes."""
    many = [f"e{index:03d}" for index in range(40)]

    command = build_transfer_command(
        OPERATION_ONE_WAY, here(), remote(), engine=ENGINE_RCLONE,
        masks=many, project_root=tmp_path,
    )

    assert "--filter-from" in command
    assert "--include" not in command
    assert len(" ".join(command)) < 200

    rules = (tmp_path / "workspace" / "transfer_filter.txt").read_text(encoding="utf-8").splitlines()
    assert rules[-1] == "- *", "без закрывающего правила пройдёт всё неназванное"
    assert "+ *.e000" in rules


def test_a_short_list_stays_on_the_command_line(tmp_path) -> None:
    """A file for two masks hides what is happening behind a path."""
    command = build_transfer_command(
        OPERATION_ONE_WAY, here(), remote(), engine=ENGINE_RCLONE,
        masks=["docx", "pdf"], project_root=tmp_path,
    )

    assert "--filter-from" not in command
    assert command.count("--include") == 2


def test_exclusions_are_written_before_inclusions(tmp_path) -> None:
    """Rules are read top to bottom and the first match decides, so an exclusion
    below its inclusion would never be reached."""
    write_filter_file(tmp_path / "f.txt", ["*.docx"], ["*.tmp", "Thumbs.db"])

    rules = [line for line in (tmp_path / "f.txt").read_text(encoding="utf-8").splitlines()
             if not line.startswith("#")]

    assert rules == ["- *.tmp", "- Thumbs.db", "+ *.docx", "- *"]


def test_rclone_switches_never_reach_robocopy() -> None:
    """The first end-to-end run came back with a fatal 16 because --config and
    friends were handed to Robocopy along with everything else."""
    import re
    from pathlib import Path as _Path

    source = _Path(__file__).resolve().parents[1] / "system_core" / "ui_nicegui" / "app.py"
    body = re.search(
        r"def transfer_run_operation.*?\n(?=\ndef )", source.read_text(encoding="utf-8"), re.S
    ).group(0)

    assert "if item[\"engine\"] == ENGINE_RCLONE:" in body
    assert "raise_on_failure=False" in body, "битовую маску Robocopy судит вызывающий, а не запускатель"


def test_the_delete_ceiling_reaches_the_command_from_the_window() -> None:
    """Built in the service, tested there, and until now unreachable: the window
    had no field for it, so `--max-delete` could never appear in a real run.

    This is the same shape as the pack switch that was drawn but never read —
    a capability that exists everywhere except where somebody could use it.
    """
    from system_core.ui_nicegui import app as gui

    source = RcloneEndpointSpec(kind="workbench_source", spec="C:/master", label="master", local_path=Path("C:/master"))
    target = RcloneEndpointSpec(kind="saved_remote", spec="r2:media", label="r2", remote_name="r2")

    gui.state.setdefault("field_values", {})["transfer_delete_ceiling"] = 2
    run = fan_out_commands(
        OPERATION_MIRROR, source, [target], project_root=Path("."),
        delete_ceiling=gui.current_transfer_delete_ceiling(),
    )
    assert "--max-delete" in run[0]["command"]
    assert "2" in [str(x) for x in run[0]["command"]]

    gui.state["field_values"]["transfer_delete_ceiling"] = None
    run = fan_out_commands(
        OPERATION_MIRROR, source, [target], project_root=Path("."),
        delete_ceiling=gui.current_transfer_delete_ceiling(),
    )
    assert "--max-delete" not in run[0]["command"], "потолок не должен появляться сам"
