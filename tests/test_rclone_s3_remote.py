"""Connecting Cloudflare R2 and its S3-compatible relatives from the window.

Twelve terabytes are paid for and one is used, because until now the wizard knew
six providers and all six were OAuth. S3 was not among them, so R2, Wasabi and
Selectel could only be set up by hand in `rclone config` — which meant, in
practice, that they were not set up.

The secret does not pass through this program. The window points at the file on
this machine that already holds the keys and names the section inside it; what
lands in the project's rclone.conf is a reference to where they live, not the
keys. This matters here more than usual: these projects are portable and travel
on a removable disk, and a disk that never carried the keys cannot lose them.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from system_core.services.rclone_service import (  # noqa: E402
    RCLONE_AUTH_MODES,
    RCLONE_OPERATION_MODES,
    RCLONE_S3_PROVIDERS,
    build_rclone_command,
    normalize_s3_credentials_file,
    normalize_s3_endpoint,
    normalize_s3_profile,
    normalize_s3_provider,
)

R2_ENDPOINT = "https://abc123.r2.cloudflarestorage.com"
SECRET = "wJalrXUtnFEMIK7MDENGbPxRfiCYEXAMPLEKEY"


@pytest.fixture
def credentials(tmp_path: Path) -> Path:
    """An AWS-style credentials file, the shape rclone expects."""
    path = tmp_path / "credentials"
    path.write_text(
        "[default]\n"
        "aws_access_key_id = AKIADEFAULT\n"
        f"aws_secret_access_key = {SECRET}\n"
        "\n"
        "[r2-releases]\n"
        "aws_access_key_id = AKIARELEASES\n"
        f"aws_secret_access_key = {SECRET}\n",
        encoding="utf-8",
    )
    return path


def test_the_s3_branch_is_offered_beside_the_others() -> None:
    assert "remote_create_s3" in RCLONE_AUTH_MODES
    assert RCLONE_OPERATION_MODES["remote_create_s3"]["label_ru"]


@pytest.mark.parametrize(
    ("given", "expected"),
    [("Cloudflare", "Cloudflare"), ("cloudflare", "Cloudflare"), ("WASABI", "Wasabi"), ("", "Cloudflare")],
)
def test_the_provider_name_is_matched_however_it_is_typed(given: str, expected: str) -> None:
    assert normalize_s3_provider(given) == expected


def test_every_named_provider_carries_a_hint_and_a_label() -> None:
    """The endpoint is the field people get wrong, so each provider shows its shape."""
    for name, item in RCLONE_S3_PROVIDERS.items():
        assert item["label"] and item["label_ru"]
        if name != "AWS":
            assert item["endpoint_hint"], f"{name} needs an endpoint and has no hint for it"


def test_an_endpoint_without_a_scheme_still_works() -> None:
    assert normalize_s3_endpoint("abc123.r2.cloudflarestorage.com") == R2_ENDPOINT
    assert normalize_s3_endpoint(R2_ENDPOINT + "/") == R2_ENDPOINT


def test_amazon_needs_no_endpoint_and_everyone_else_does() -> None:
    """Left empty for R2 the remote silently resolves to Amazon and fails with an
    error that says nothing about the real cause."""
    assert normalize_s3_endpoint("", provider="AWS") == ""

    with pytest.raises(ValueError, match="Cloudflare"):
        normalize_s3_endpoint("", provider="Cloudflare")


def test_the_keys_are_pointed_at_rather_than_typed(credentials: Path) -> None:
    assert normalize_s3_credentials_file(str(credentials)) == str(credentials)
    assert normalize_s3_credentials_file(f'"{credentials}"') == str(credentials)


def test_an_empty_path_means_look_where_rclone_always_looks() -> None:
    assert normalize_s3_credentials_file("") == ""


def test_a_file_that_is_not_there_is_refused_now_rather_than_at_first_use(tmp_path: Path) -> None:
    """The remote would otherwise be created, look healthy, and fail later with an
    authentication error that says nothing about a missing file."""
    with pytest.raises(ValueError, match="not found"):
        normalize_s3_credentials_file(str(tmp_path / "nowhere" / "credentials"))


@pytest.mark.parametrize(
    ("given", "expected"), [("", "default"), ("r2-releases", "r2-releases"), ("[r2-releases]", "r2-releases")]
)
def test_the_profile_names_a_section_of_that_file(given: str, expected: str) -> None:
    """One file can hold the keys for several storages, one section each."""
    assert normalize_s3_profile(given) == expected


def test_the_built_command_carries_no_secret_at_all(credentials: Path, tmp_path: Path) -> None:
    spec = build_rclone_command(
        ROOT,
        tmp_path,
        {
            "mode": "remote_create_s3",
            "auth_remote_name": "r2",
            "s3_provider": "Cloudflare",
            "s3_endpoint": R2_ENDPOINT,
            "s3_credentials_file": str(credentials),
            "s3_profile": "r2-releases",
        },
        preview=True,
    )
    text = " ".join(str(part) for part in spec.command)

    assert SECRET not in text
    assert "secret_access_key" not in text
    # env_auth true is what makes the credentials file work at all: rclone only
    # consults the AWS SDK chain — and therefore shared_credentials_file and
    # profile — when it is true. With false it looks for access_key_id in the
    # config, finds nothing, and signs with an empty key; R2 answers
    # `InvalidArgument: Authorization`, which reads like a wrong key rather than
    # a missing one. Measured against a live bucket, not inferred.
    # no_check_bucket is what Cloudflare documents for object-level tokens.
    assert "env_auth true" in text
    assert f"shared_credentials_file {credentials}" in text
    assert "profile r2-releases" in text
    assert "provider Cloudflare" in text
    assert R2_ENDPOINT in text
    assert "region auto" in text
    assert "no_check_bucket true" in text


def test_the_credentials_path_also_goes_into_the_environment(tmp_path: Path) -> None:
    """rclone writes `shared_credentials_file` into the config and then does not
    use it.

    Behind `env_auth = true` the lookup runs through the AWS SDK chain, which
    reads `AWS_SHARED_CREDENTIALS_FILE` instead. A named section fails with
    "failed to get shared config profile" until the path is in the environment as
    well — measured against a live R2 bucket, where the same remote went from
    refusing to working with nothing else changed.
    """
    from system_core.services.rclone_service import S3_CREDENTIALS_ENV, s3_credentials_env

    config = (
        "[r2]\ntype = s3\nenv_auth = true\n"
        "shared_credentials_file = E:/keys/r2_credentials\nprofile = audion_r2\n"
    )

    assert s3_credentials_env(config) == {S3_CREDENTIALS_ENV: "E:/keys/r2_credentials"}


def test_nothing_is_set_when_remotes_disagree_about_the_file() -> None:
    """One variable cannot serve two files, and picking one would break whichever
    remote was not picked. rclone is left to its own devices instead."""
    from system_core.services.rclone_service import s3_credentials_env

    two = (
        "[r2]\nshared_credentials_file = E:/keys/one\n"
        "[wasabi]\nshared_credentials_file = E:/keys/two\n"
    )

    assert s3_credentials_env(two) == {}
    assert s3_credentials_env("") == {}
    assert s3_credentials_env("[sftp]\ntype = sftp\n") == {}


def test_the_window_hands_that_path_to_every_rclone_run() -> None:
    """It was the config key alone that failed; the environment is where it works."""
    import re

    source = (ROOT / "system_core" / "ui_nicegui" / "app.py").read_text(encoding="utf-8")
    body = re.search(r"def rclone_process_env.*?\n(?=\ndef )", source, re.S)

    assert body, "нет общего места, где собирается окружение для rclone"
    assert "s3_credentials_env" in body.group(0)
