"""The person picks an operation; the engine follows from the pair.

Robocopy is demoted from a section to an engine rather than retired: for folder
to folder it is faster and it carries the NTFS attribute bits that rclone drops
on Windows. It steps aside the moment something it cannot do is asked for.
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
    OPERATION_ONE_WAY,
    OPERATION_RCLONE_COMMAND,
    OPERATION_TWO_WAY,
    OPERATION_VERIFY,
    TRANSFER_OPERATIONS,
    bisync_workdir_args,
    fan_out_commands,
    mirror_guard_args,
    robocopy_time_args,
    transfer_engine,
    transfer_plan,
)


def here(path: str = "C:/work") -> RcloneEndpointSpec:
    return RcloneEndpointSpec(kind="workbench_source", spec=path, label=path, local_path=Path(path))


def share(path: str = "//nas/backup") -> RcloneEndpointSpec:
    windows = path.replace("/", "\\")
    return RcloneEndpointSpec(kind="workbench_target", spec=windows, label=windows, local_path=Path(windows))


def remote(name: str = "r2_media") -> RcloneEndpointSpec:
    return RcloneEndpointSpec(kind="saved_remote", spec=f"{name}:data", label=name, remote_name=name)


@pytest.mark.parametrize("operation", [OPERATION_ONE_WAY, OPERATION_MIRROR])
def test_folder_to_folder_stays_with_robocopy(operation: str) -> None:
    """Faster, and it is the only one of the two that carries attribute bits."""
    assert transfer_engine(operation, here("C:/in"), here("D:/out")) == ENGINE_ROBOCOPY


@pytest.mark.parametrize("operation", [OPERATION_ONE_WAY, OPERATION_MIRROR])
def test_a_share_is_still_robocopy_territory(operation: str) -> None:
    assert transfer_engine(operation, here(), share()) == ENGINE_ROBOCOPY


@pytest.mark.parametrize("operation", [OPERATION_ONE_WAY, OPERATION_MIRROR, OPERATION_TWO_WAY, OPERATION_VERIFY])
def test_anything_touching_a_remote_goes_to_rclone(operation: str) -> None:
    """Robocopy cannot see a saved remote at all."""
    assert transfer_engine(operation, here(), remote()) == ENGINE_RCLONE
    assert transfer_engine(operation, remote(), here()) == ENGINE_RCLONE


def test_two_way_sync_is_rclone_even_between_two_local_folders() -> None:
    """Robocopy has no mode that remembers the previous run."""
    assert transfer_engine(OPERATION_TWO_WAY, here("C:/in"), here("D:/out")) == ENGINE_RCLONE


def test_asking_for_hashes_hands_a_local_pair_to_rclone() -> None:
    """This is the reason the sections were merged: Robocopy cannot compare by hash."""
    assert transfer_engine(OPERATION_ONE_WAY, here("C:/in"), here("D:/out"), by_hash=True) == ENGINE_RCLONE
    assert transfer_engine(OPERATION_VERIFY, here("C:/in"), here("D:/out")) == ENGINE_RCLONE


def test_the_window_can_say_which_engine_runs_and_why() -> None:
    plan = transfer_plan(OPERATION_VERIFY, here("C:/in"), here("D:/out"), russian=True)

    assert plan["engine_label"] == "RClone"
    assert plan["operation_label"] == "Сверить"
    assert "хеш" in plan["engine_reason"].lower()

    local = transfer_plan(OPERATION_MIRROR, here("C:/in"), here("D:/out"), russian=True)
    assert local["engine_label"] == "Robocopy"
    assert "NTFS" in local["engine_reason"]


def test_every_operation_is_named_in_both_languages() -> None:
    for operation in (OPERATION_ONE_WAY, OPERATION_MIRROR, OPERATION_TWO_WAY, OPERATION_VERIFY):
        assert TRANSFER_OPERATIONS[operation]["label"] and TRANSFER_OPERATIONS[operation]["label_ru"]


def test_a_mirror_and_a_one_way_run_are_not_the_same_operation() -> None:
    """The difference is not deletion policy — it is whether the destination is
    allowed anything of its own.

    A mirror's destination is a copy and owns nothing, which is how a reference
    machine and its replicas work. A one-way destination has a life of its own:
    something lands on Google and has to reach Mega, where other things already
    live, and making Mega identical to Google would wipe them.

    Only the mirror deletes, and that is what makes it a mirror.
    """
    assert OPERATION_MIRROR != OPERATION_ONE_WAY
    assert OPERATION_RCLONE_COMMAND[OPERATION_MIRROR] == "sync"
    assert OPERATION_RCLONE_COMMAND[OPERATION_ONE_WAY] == "copy"
    assert OPERATION_RCLONE_COMMAND[OPERATION_TWO_WAY] == "bisync"
    assert set(OPERATION_RCLONE_COMMAND) == set(TRANSFER_OPERATIONS)


def test_two_way_memory_stays_inside_the_project() -> None:
    """rclone would keep it in %LOCALAPPDATA%. This project keeps its own state.

    Under config, not workspace: cleanup empties workspace, and losing these
    listings fails quietly by forcing a full resync — the one moment two-way
    sync has to be told which side wins.
    """
    args = bisync_workdir_args(Path("E:/TOOLS/Refactor/Audion Disk Tools"))

    assert args[0] == "--workdir"
    assert Path(args[1]).parts[-2:] == ("config", "bisync")
    assert "AppData" not in args[1]


def test_the_delete_ceiling_is_available_and_not_imposed() -> None:
    """Off unless asked for. A default would be a guess at how the owner works,
    and a release that drops a hundred old files is ordinary."""
    assert mirror_guard_args() == []
    assert mirror_guard_args(None) == []
    assert mirror_guard_args(0) == []
    assert mirror_guard_args(5) == ["--max-delete", "5"]


def test_one_master_reaches_every_machine_in_one_run() -> None:
    """The shape a source/target pair could not express, and the one in daily use."""
    machines = [here("D:/replica"), share("//office/mirror"), remote("r2_media")]

    plans = fan_out_commands(OPERATION_MIRROR, here("C:/master"), machines, russian=True)

    assert [plan["index"] for plan in plans] == [0, 1, 2]
    assert [plan["engine"] for plan in plans] == [ENGINE_ROBOCOPY, ENGINE_ROBOCOPY, ENGINE_RCLONE]
    assert all(plan["operation_label"] == "Зеркало" for plan in plans)


def test_coarse_time_flags_are_left_off_for_ntfs_to_ntfs() -> None:
    """They used to be on every run, widening "unchanged" to two seconds for free."""
    assert robocopy_time_args(Path("C:/in"), Path("C:/out")) == []


def test_a_share_gets_the_coarse_time_flags() -> None:
    """A NAS or Samba share stores time coarsely, which is what they are for."""
    assert robocopy_time_args(Path("C:/in"), Path(r"\\nas\backup")) == ["/FFT", "/DST"]
    assert robocopy_time_args(Path(r"\\nas\backup"), Path("C:/out")) == ["/FFT", "/DST"]
