"""A link as the third kind of source.

Not a general endpoint: a link is somewhere to fetch from, and the fetch happens
on the storage's side, so a file pulled into R2 never comes down this machine's
channel on its way back up. That is the whole reason it is worth having — and it
is also why nothing else can be asked of it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from system_core.services.rclone_service import (  # noqa: E402
    RCLONE_ENDPOINT_KINDS,
    RcloneEndpointSpec,
    endpoint_spec,
    normalize_source_url,
)
from system_core.services.transfer_service import (  # noqa: E402
    ENGINE_RCLONE,
    OPERATION_MIRROR,
    OPERATION_ONE_WAY,
    OPERATION_TWO_WAY,
    OPERATION_VERIFY,
    build_transfer_command,
    engine_reason,
    transfer_engine,
)

URL = "https://example.com/setup-3.0.1.exe"


def link() -> RcloneEndpointSpec:
    return RcloneEndpointSpec(kind="url", spec=URL, label=URL)


def remote(name: str = "r2") -> RcloneEndpointSpec:
    return RcloneEndpointSpec(
        kind="saved_remote", spec=f"{name}:releases", label=name, remote_name=name, remote_path="releases"
    )


def test_a_link_is_offered_as_an_endpoint_kind() -> None:
    assert RCLONE_ENDPOINT_KINDS["url"]["label_ru"] == "Ссылка"


@pytest.mark.parametrize("bad", ["", "   ", "ftp://example.com/x", r"C:\local\file.exe", "example.com/x"])
def test_only_http_links_are_accepted(bad: str) -> None:
    """rclone would take other schemes, and a transfer that quietly reads a local
    file because the text looked like a path surprises somebody at the far end."""
    with pytest.raises(ValueError):
        normalize_source_url(bad)


def test_a_good_link_survives_untouched() -> None:
    assert normalize_source_url(f"  {URL}  ") == URL


def test_a_link_can_only_be_the_source() -> None:
    with pytest.raises(ValueError, match="never its destination"):
        endpoint_spec({"target_kind": "url", "source_url": URL}, "target")


def test_fetching_a_link_is_its_own_command() -> None:
    command = build_transfer_command(
        OPERATION_ONE_WAY, link(), remote(), engine=ENGINE_RCLONE, rclone_exe="rclone.exe"
    )

    assert command[:4] == ["rclone.exe", "copyurl", URL, "r2:releases"]
    assert "--auto-filename" in command


@pytest.mark.parametrize("operation", [OPERATION_MIRROR, OPERATION_TWO_WAY, OPERATION_VERIFY])
def test_nothing_but_fetching_can_be_asked_of_a_link(operation: str) -> None:
    """There is nothing at the far end to mirror against or carry changes back to."""
    with pytest.raises(ValueError, match="only be fetched"):
        build_transfer_command(operation, link(), remote(), engine=ENGINE_RCLONE)


def test_the_window_says_the_file_will_not_come_through_this_channel() -> None:
    assert transfer_engine(OPERATION_ONE_WAY, link(), remote()) == ENGINE_RCLONE

    reason = engine_reason(ENGINE_RCLONE, OPERATION_ONE_WAY, link(), remote())

    assert "ваш канал" in reason["reason_ru"]


def test_a_dry_run_still_applies_to_a_fetch() -> None:
    command = build_transfer_command(
        OPERATION_ONE_WAY, link(), remote(), engine=ENGINE_RCLONE, dry_run=True
    )

    assert "--dry-run" in command
