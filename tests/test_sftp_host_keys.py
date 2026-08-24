"""Asking the server for the host key type that can actually be checked.

Found in the field, on a real server. A server offers three host keys — ed25519,
ecdsa, rsa — while known_hosts usually holds whichever one was recorded first.
OpenSSH notices that and asks for the type it can verify. rclone's Go library
does not: it takes whatever it prefers, looks that up, finds an entry for the
host but not for that key, and reports `knownhosts: key mismatch`.

That message reads like an interception and is nothing of the sort, so it sends
people to check their network when the answer is a one-line setting. The remote
is now told which types to ask for, read from the file it will be checked
against.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from system_core.services.rclone_service import build_rclone_command, known_host_key_algorithms  # noqa: E402


@pytest.fixture
def known_hosts(tmp_path: Path) -> Path:
    path = tmp_path / "known_hosts"
    path.write_text(
        "# a comment\n"
        "198.51.100.10 ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIExample1\n"
        "198.51.100.20 ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQExample2\n"
        "198.51.100.30,alias.example ecdsa-sha2-nistp256 AAAAE2VjZHNhLXNoYTItbmlzdHExample3\n"
        "198.51.100.40 ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIExample4\n"
        "198.51.100.40 ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQExample5\n"
        "|1|hashedsalt=|hashedhost= ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIExample6\n",
        encoding="utf-8",
    )
    return path


def test_the_recorded_type_is_what_gets_asked_for(known_hosts: Path) -> None:
    assert known_host_key_algorithms(known_hosts, "198.51.100.10") == ["ssh-ed25519"]


def test_an_rsa_entry_also_covers_the_modern_signatures(known_hosts: Path) -> None:
    """Same key, newer signature algorithm — servers have defaulted to the SHA-2
    forms for years, and asking only for ssh-rsa would fail against them."""
    assert known_host_key_algorithms(known_hosts, "198.51.100.20") == [
        "rsa-sha2-512",
        "rsa-sha2-256",
        "ssh-rsa",
    ]


def test_a_host_listed_beside_an_alias_is_still_found(known_hosts: Path) -> None:
    assert known_host_key_algorithms(known_hosts, "alias.example") == ["ecdsa-sha2-nistp256"]


def test_several_recorded_types_are_all_offered(known_hosts: Path) -> None:
    assert known_host_key_algorithms(known_hosts, "198.51.100.40") == [
        "ssh-ed25519",
        "rsa-sha2-512",
        "rsa-sha2-256",
        "ssh-rsa",
    ]


@pytest.mark.parametrize("host", ["203.0.113.99", "", None])
def test_an_unknown_host_asks_for_nothing_in_particular(known_hosts: Path, host) -> None:
    """A new host has nothing to verify against, and guessing helps nobody."""
    assert known_host_key_algorithms(known_hosts, host) == []


def test_a_hashed_entry_is_skipped_rather_than_guessed_at(known_hosts: Path) -> None:
    """Matching those needs the name hashed with each salt in turn — more
    machinery than this is worth, and getting it wrong would be silent."""
    assert known_host_key_algorithms(known_hosts, "hashedhost=") == []


def test_an_unreadable_file_is_not_an_error(tmp_path: Path) -> None:
    assert known_host_key_algorithms(tmp_path / "nowhere", "198.51.100.10") == []
    assert known_host_key_algorithms("", "198.51.100.10") == []


def test_the_created_remote_carries_the_algorithms(known_hosts: Path, tmp_path: Path) -> None:
    spec = build_rclone_command(
        ROOT,
        tmp_path,
        {
            "mode": "remote_create_sftp",
            "auth_remote_name": "server",
            "sftp_host": "198.51.100.10",
            "sftp_user": "root",
            "sftp_port": "22",
            "sftp_auth_method": "agent",
            "sftp_known_hosts_file": str(known_hosts),
        },
        preview=True,
    )
    command = [str(part) for part in spec.command]

    assert "host_key_algorithms" in command
    assert command[command.index("host_key_algorithms") + 1] == "ssh-ed25519"


def test_a_host_with_nothing_recorded_leaves_the_choice_to_rclone(known_hosts: Path, tmp_path: Path) -> None:
    spec = build_rclone_command(
        ROOT,
        tmp_path,
        {
            "mode": "remote_create_sftp",
            "auth_remote_name": "server",
            "sftp_host": "203.0.113.99",
            "sftp_user": "root",
            "sftp_port": "22",
            "sftp_auth_method": "agent",
            "sftp_known_hosts_file": str(known_hosts),
        },
        preview=True,
    )

    assert "host_key_algorithms" not in [str(part) for part in spec.command]
