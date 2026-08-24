"""The passphrase for an encrypted config: where it travels and where it must not.

The portable-disk plan rests on this. A config that travels is a config that can
be found, and encryption is what makes finding it worthless — but only if the
phrase reaches rclone without being written down anywhere on the way.

The live cases run rclone itself against a throwaway config, because whether a
config is encrypted is not something to infer from bytes: rclone owns the format
and has changed it before.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from system_core.services.rclone_service import (  # noqa: E402
    CONFIG_PASSPHRASE_ENV,
    config_is_encrypted,
    config_passphrase_env,
    find_rclone_executable,
    parse_config_dump,
)

RCLONE = find_rclone_executable(ROOT)
PHRASE = "фраза для проверки 2026"
PLAIN = (
    "[eden]\ntype = sftp\nhost = 198.51.100.10\nuser = root\n"
    "[r2]\ntype = s3\nprovider = Cloudflare\nsecret_access_key = верхсекретно\n"
)

live = pytest.mark.skipif(RCLONE is None, reason="rclone не установлен в проект")


def rclone(config: Path, *args: str, phrase: str | None = None, feed: str | None = None):
    env = os.environ.copy()
    env.update(config_passphrase_env(phrase))
    env["PYTHONUTF8"] = "1"
    return subprocess.run(
        [str(RCLONE), "--config", str(config), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, input=feed,
    )


def test_the_phrase_travels_in_the_environment_not_on_the_command_line() -> None:
    """An argument shows up in the process list and in every log line that echoes
    the command. The config is the one file on a travelling disk that must stay
    unreadable."""
    assert config_passphrase_env("секрет") == {CONFIG_PASSPHRASE_ENV: "секрет"}


@pytest.mark.parametrize("empty", ["", None])
def test_no_phrase_means_no_variable_at_all(empty) -> None:
    """An empty variable is not the same as an absent one: rclone would take it
    as a phrase and fail against a plain config."""
    assert config_passphrase_env(empty) == {}


def test_a_plain_config_reads_without_a_phrase(tmp_path: Path) -> None:
    assert config_is_encrypted("", 0) is False


@live
def test_an_encrypted_config_is_recognised_by_the_run_that_fails(tmp_path: Path) -> None:
    config = tmp_path / "rclone.conf"
    config.write_text(PLAIN, encoding="utf-8")

    done = rclone(config, "config", "dump")
    assert done.returncode == 0
    assert config_is_encrypted(done.stdout, done.returncode) is False

    rclone(config, "config", "encryption", "set", feed=f"{PHRASE}\n{PHRASE}\n")

    done = rclone(config, "config", "dump")
    assert done.returncode != 0
    assert config_is_encrypted(done.stdout + done.stderr, done.returncode) is True


@live
def test_encryption_hides_the_names_as_well_as_the_secrets(tmp_path: Path) -> None:
    """A found disk should not even reveal which storages are in use."""
    config = tmp_path / "rclone.conf"
    config.write_text(PLAIN, encoding="utf-8")
    rclone(config, "config", "encryption", "set", feed=f"{PHRASE}\n{PHRASE}\n")

    sealed = config.read_text(encoding="utf-8", errors="replace")

    assert "верхсекретно" not in sealed
    assert "eden" not in sealed and "cloudflare" not in sealed.lower()
    assert sealed.splitlines()[0].startswith("# Encrypted")


@live
def test_the_right_phrase_opens_it_and_a_wrong_one_does_not(tmp_path: Path) -> None:
    config = tmp_path / "rclone.conf"
    config.write_text(PLAIN, encoding="utf-8")
    rclone(config, "config", "encryption", "set", feed=f"{PHRASE}\n{PHRASE}\n")

    wrong = rclone(config, "config", "dump", phrase="не та фраза")
    assert wrong.returncode != 0
    assert parse_config_dump(wrong.stdout) == {}

    right = rclone(config, "config", "dump", phrase=PHRASE)
    assert right.returncode == 0
    backends = parse_config_dump(right.stdout)
    assert set(backends) == {"eden", "r2"}
    # Everything downstream keeps working through the encryption: the route line
    # needs these types to say whether a copy can stay inside the service.
    assert backends["r2"].type == "s3" and backends["r2"].provider == "Cloudflare"


def test_the_window_hands_the_phrase_to_every_rclone_run() -> None:
    """It used to be held and never passed: the field existed and the runs did
    not carry it."""
    import re

    source = (ROOT / "system_core" / "ui_nicegui" / "app.py").read_text(encoding="utf-8")
    body = re.search(r"def rclone_process_env.*?\n(?=\ndef )", source, re.S)

    assert body, "нет общего места, где собирается окружение для rclone"
    assert "config_passphrase_env" in body.group(0)
    assert source.count("env=rclone_process_env()") >= 4, "часть запусков пойдёт без фразы"
