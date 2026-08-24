"""Things done to one storage, which are not transfers.

They have no second end and move nothing, so they do not belong in the row of
operations. Two of them answer a question the owner has been asking with real
money: twelve terabytes are paid for and one is used.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from system_core.services.rclone_service import (  # noqa: E402
    RCLONE_OPERATION_MODES,
    RCLONE_STORAGE_MODES,
    build_rclone_command,
)

BASE = {
    "config_scope": "portable",
    "source_kind": "saved_remote",
    "source_remote_name": "r2",
    "source_remote_path": "releases",
}


def command_for(mode: str, **extra) -> list[str]:
    spec = build_rclone_command(ROOT, ROOT / "logs", {**BASE, "mode": mode, **extra}, preview=True)
    return [str(part) for part in spec.command]


@pytest.mark.parametrize("mode", sorted(RCLONE_STORAGE_MODES))
def test_every_storage_action_is_named_and_builds(mode: str) -> None:
    assert RCLONE_OPERATION_MODES[mode]["label_ru"]
    assert "r2:releases" in command_for(mode)


def test_size_answers_how_much_is_actually_stored() -> None:
    assert command_for("storage_size")[-2:] == ["size", "r2:releases"]


def test_cleanup_removes_what_is_billed_but_never_listed() -> None:
    """An abandoned multipart upload leaves parts that do not appear in any
    listing and are charged for anyway."""
    assert "cleanup" in command_for("storage_cleanup")


def test_finding_duplicates_does_not_delete_them() -> None:
    """`dedupe` alone is interactive and will remove things. The list mode
    changes nothing, and a button labelled "find" must not decide."""
    command = command_for("storage_dedupe")

    assert command[-3:] == ["dedupe", "list", "r2:releases"]


def test_the_checksum_kind_can_be_chosen_and_defaults_to_md5() -> None:
    assert command_for("storage_hashsum")[-3:-1] == ["hashsum", "md5"]
    assert command_for("storage_hashsum", hash_kind="sha1")[-3:-1] == ["hashsum", "sha1"]


def test_storage_actions_are_not_transfer_operations() -> None:
    """Nothing here moves bytes between two ends, so none of it may leak into
    the row of five."""
    from system_core.services.transfer_service import TRANSFER_OPERATIONS

    assert not (RCLONE_STORAGE_MODES & set(TRANSFER_OPERATIONS))
