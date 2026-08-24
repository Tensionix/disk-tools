from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from system_core.services.rclone_service import (  # noqa: E402
    parse_listremotes_output,
    remote_name_in,
)


def test_listremotes_output_becomes_clean_names() -> None:
    text = "drive:\nyandex:\ns3backup:\n"

    assert parse_listremotes_output(text) == ["drive", "yandex", "s3backup"]


def test_listremotes_preserves_config_order_and_drops_duplicates() -> None:
    text = "zeta:\nalpha:\nZETA:\nalpha:\n"

    assert parse_listremotes_output(text) == ["zeta", "alpha"]


def test_listremotes_ignores_blank_lines_and_noise() -> None:
    text = "\n  \ndrive:\nNOTICE: config file not found\n\nyandex:\n"

    assert parse_listremotes_output(text) == ["drive", "yandex"]


def test_listremotes_ignores_lines_that_are_not_remote_names() -> None:
    text = "drive:\n-bad:\nwith/slash:\nwith:colon:\nok:\n"

    assert parse_listremotes_output(text) == ["drive", "ok"]


def test_empty_listremotes_output_gives_an_empty_list() -> None:
    assert parse_listremotes_output("") == []
    assert parse_listremotes_output(None) == []


def test_remote_name_in_is_case_insensitive_and_colon_tolerant() -> None:
    names = ["drive", "yandex"]

    assert remote_name_in(names, "drive") is True
    assert remote_name_in(names, "Drive:") is True
    assert remote_name_in(names, "s3backup") is False
    assert remote_name_in(names, "") is False
