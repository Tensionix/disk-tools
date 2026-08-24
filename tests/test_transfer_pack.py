"""Archiving before a transfer, as a step rather than a second implementation.

The archiving section already turns many folders into one archive each, with
formats and encryption chosen per run, and it is tested on its own. The transfer
reaches for it and then sends what it produced: by that point the staging folder
is just a folder, so the machines, the operation and the engine choice are
decided exactly as they are for a plain run.
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
    PACK_BEFORE,
    PACK_MODES,
    PACK_NONE,
    OPERATION_MIRROR,
    OPERATION_ONE_WAY,
    pack_staging_dir,
    pack_then_transfer_plan,
)

ARCHIVE = {
    "formats": ["7z"],
    "encryption": "password",
    "password": "секрет",
    "level": "5",
    "name_prefix": "release_",
}


def here(path: str = "C:/master") -> RcloneEndpointSpec:
    return RcloneEndpointSpec(kind="workbench_source", spec=path, label=path, local_path=Path(path))


def remote(name: str = "r2") -> RcloneEndpointSpec:
    return RcloneEndpointSpec(
        kind="saved_remote", spec=f"{name}:releases", label=name, remote_name=name, remote_path="releases"
    )


def test_both_pack_modes_are_named_in_both_languages() -> None:
    for mode in (PACK_NONE, PACK_BEFORE):
        assert PACK_MODES[mode]["label"] and PACK_MODES[mode]["label_ru"]


def test_the_staging_folder_lives_where_cleanup_can_reach_it() -> None:
    """Under workspace, not output: output is the owner's, and files that exist
    for the length of one run have no business appearing there."""
    staging = pack_staging_dir(ROOT, "release_")

    # The archive name prefix ends in a separator; a folder named after it should
    # not carry that into its own name.
    assert staging.parts[-3:] == ("workspace", "transfer_pack", "release")
    assert "output" not in staging.parts


def test_a_name_that_cannot_be_a_folder_still_becomes_one() -> None:
    assert pack_staging_dir(ROOT, 'АИП: том 2/3').name == "АИП__том_2_3"
    assert pack_staging_dir(ROOT, "").name == "pack"


def test_the_archive_step_carries_the_sections_own_options() -> None:
    """Formats, encryption and password come from the archiving section as they
    are, so there is one answer to how an archive is made here."""
    plan = pack_then_transfer_plan(
        OPERATION_ONE_WAY, here(), [remote()], project_root=ROOT, archive_options=ARCHIVE
    )

    assert plan["pack"]["formats"] == ["7z"]
    assert plan["pack"]["encryption"] == "password"
    assert plan["pack"]["source_root"] == str(Path("C:/master"))
    assert plan["pack"]["target_root"] == str(plan["staging"])


def test_the_machines_receive_the_archives_rather_than_the_master() -> None:
    plan = pack_then_transfer_plan(
        OPERATION_MIRROR, here("C:/master"), [here("D:/replica"), remote()],
        project_root=ROOT, archive_options=ARCHIVE, russian=True,
    )

    assert [item["engine"] for item in plan["transfer"]] == [ENGINE_ROBOCOPY, ENGINE_RCLONE]
    for item in plan["transfer"]:
        command = " ".join(str(part) for part in item["command"])
        assert "transfer_pack" in command
        assert "C:\\master" not in command


def test_the_password_never_reaches_a_transfer_command() -> None:
    """It belongs to the archive step; the transfer only moves the files."""
    plan = pack_then_transfer_plan(
        OPERATION_ONE_WAY, here(), [remote()], project_root=ROOT, archive_options=ARCHIVE
    )

    for item in plan["transfer"]:
        assert "секрет" not in " ".join(str(part) for part in item["command"])
