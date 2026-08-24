"""How the bytes travel, decided from the pair rather than from a mode.

The cloud section exists to move data between clouds, and until now the one
thing it never said was whether that happens inside the provider or by way of
this machine. It was not even askable: the endpoint route was declared only in
the Server layer, so cloud→cloud could not be reached from the Cloud window at
all.

This is the fact the redesign is built on. `--server-side-across-configs` is not
a mode anyone should have to know about and pick — it follows from the two
backends, and rclone already records both in its config.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from system_core.services.rclone_service import (  # noqa: E402
    TRANSIT_FROM_HERE,
    TRANSIT_LABELS,
    TRANSIT_LOCAL,
    TRANSIT_PROVIDER_SIDE,
    TRANSIT_THROUGH_HERE,
    TRANSIT_TO_HERE,
    RcloneEndpointSpec,
    RemoteBackend,
    backend_service_name,
    parse_config_dump,
    route_objection,
    transit_sentence,
    transit_args,
    transit_kind,
)

ALL_KINDS = (TRANSIT_LOCAL, TRANSIT_FROM_HERE, TRANSIT_TO_HERE, TRANSIT_THROUGH_HERE, TRANSIT_PROVIDER_SIDE)

TYPES = {
    "gdrive_work": RemoteBackend("drive"),
    "gdrive_home": RemoteBackend("drive"),
    "r2_media": RemoteBackend("s3", "Cloudflare"),
    "r2_backup": RemoteBackend("s3", "Cloudflare"),
    "wasabi_cold": RemoteBackend("s3", "Wasabi"),
    "yandex": RemoteBackend("yandex"),
    "server": RemoteBackend("sftp"),
}


def remote(name: str) -> RcloneEndpointSpec:
    return RcloneEndpointSpec(kind="saved_remote", spec=f"{name}:data", label=name, remote_name=name)


def here(path: str = "C:/work") -> RcloneEndpointSpec:
    return RcloneEndpointSpec(kind="workbench_source", spec=path, label=path, local_path=Path(path))


@pytest.mark.parametrize(
    ("source", "target", "expected"),
    [
        (here("C:/in"), here("D:/out"), TRANSIT_LOCAL),
        # Publishing a release: the data starts here. Calling this transit would
        # misdescribe the route this window is used for most.
        (here(), remote("r2_media"), TRANSIT_FROM_HERE),
        (here(), remote("yandex"), TRANSIT_FROM_HERE),
        (remote("yandex"), here(), TRANSIT_TO_HERE),
        # Different providers: nobody can do this directly, there is no protocol
        # by which one cloud fetches from another, so it really does pass through.
        (remote("yandex"), remote("gdrive_work"), TRANSIT_THROUGH_HERE),
        (remote("r2_media"), remote("server"), TRANSIT_THROUGH_HERE),
        # Same backend, two accounts or two buckets — this is the case worth having.
        (remote("gdrive_work"), remote("gdrive_home"), TRANSIT_PROVIDER_SIDE),
        (remote("r2_media"), remote("r2_backup"), TRANSIT_PROVIDER_SIDE),
    ],
)
def test_the_pair_decides_how_the_bytes_travel(
    source: RcloneEndpointSpec, target: RcloneEndpointSpec, expected: str
) -> None:
    assert transit_kind(source, target, TYPES) == expected


def test_sending_and_passing_through_are_not_the_same_word() -> None:
    """They were one label once, which described an upload as transit."""
    upload = transit_kind(here(), remote("r2_media"), TYPES)
    relay = transit_kind(remote("yandex"), remote("r2_media"), TYPES)

    assert upload != relay
    assert TRANSIT_LABELS[upload]["label_ru"] == "с этого компьютера"
    assert TRANSIT_LABELS[relay]["label_ru"] == "транзитом через этот компьютер"


def test_an_unknown_remote_is_treated_as_transit() -> None:
    """Guessing "direct" from missing information would promise what it cannot keep."""
    assert transit_kind(remote("brand_new"), remote("r2_media"), TYPES) == TRANSIT_THROUGH_HERE
    assert transit_kind(remote("a"), remote("b"), {}) == TRANSIT_THROUGH_HERE


def test_the_flag_is_added_only_where_it_means_something() -> None:
    """The command the window shows has to describe what will actually happen."""
    assert transit_args(TRANSIT_PROVIDER_SIDE) == ["--server-side-across-configs"]
    for kind in (TRANSIT_LOCAL, TRANSIT_FROM_HERE, TRANSIT_TO_HERE, TRANSIT_THROUGH_HERE):
        assert transit_args(kind) == []


def test_backend_types_are_read_from_the_config_rclone_already_keeps() -> None:
    dump = json.dumps(
        {
            "r2_media": {"type": "s3", "provider": "Cloudflare", "access_key_id": "x"},
            "gdrive_work": {"type": "drive", "token": "{}"},
            "broken": {"no_type_here": "1"},
        }
    )

    assert parse_config_dump(dump) == {
        "r2_media": RemoteBackend("s3", "Cloudflare"),
        "gdrive_work": RemoteBackend("drive"),
    }


@pytest.mark.parametrize("text", ["", "   ", "not json at all", "[]", None])
def test_an_unreadable_config_dump_yields_nothing_rather_than_raising(text: object) -> None:
    assert parse_config_dump(text) == {}


def test_every_transit_kind_can_be_named_in_both_languages() -> None:
    """The window states the route in words, so no kind may be unlabelled."""
    for kind in ALL_KINDS:
        assert TRANSIT_LABELS[kind]["label"]
        assert TRANSIT_LABELS[kind]["label_ru"]
    assert set(TRANSIT_LABELS) == set(ALL_KINDS), "ярлык без состояния или состояние без ярлыка"


def test_two_servers_are_not_one_service_just_because_both_speak_sftp() -> None:
    """For a cloud the backend is the service — `drive` means Google and nothing
    else. For SFTP it means any machine that speaks SSH, and two of them have no
    path between them: rclone pulls from one and pushes to the other through
    here. Calling that direct would promise a route that does not exist.
    """
    servers = {
        "eden": RemoteBackend("sftp", host="135.106.178.57"),
        "waicore": RemoteBackend("sftp", host="178.17.50.161"),
        "eden_backup": RemoteBackend("sftp", host="135.106.178.57"),
    }

    assert transit_kind(remote("eden"), remote("waicore"), servers) == TRANSIT_THROUGH_HERE
    # Two paths on one machine can be moved between without leaving it.
    assert transit_kind(remote("eden"), remote("eden_backup"), servers) == TRANSIT_PROVIDER_SIDE


def test_a_host_based_backend_with_no_host_recorded_is_treated_as_transit() -> None:
    """Nothing to compare means nothing can be promised."""
    vague = {"a": RemoteBackend("sftp"), "b": RemoteBackend("sftp")}

    assert transit_kind(remote("a"), remote("b"), vague) == TRANSIT_THROUGH_HERE


def test_two_s3_services_are_not_one_service() -> None:
    """R2 and Wasabi share the s3 backend and share no machines.

    Type alone would have called this direct. rclone would then fall back to a
    normal transfer and the window would have promised a route it cannot take.
    """
    assert transit_kind(remote("r2_media"), remote("wasabi_cold"), TYPES) == TRANSIT_THROUGH_HERE
    assert transit_kind(remote("r2_media"), remote("r2_backup"), TYPES) == TRANSIT_PROVIDER_SIDE


def test_the_sentence_names_the_service_doing_the_work() -> None:
    """"By the provider" named nobody, and in Russian reads as the ISP."""
    kind = transit_kind(remote("r2_media"), remote("r2_backup"), TYPES)

    assert transit_sentence(kind, remote("r2_media"), remote("r2_backup"), TYPES, russian=True) == (
        "напрямую, силами Cloudflare R2"
    )
    assert transit_sentence(kind, remote("r2_media"), remote("r2_backup"), TYPES) == (
        "directly, inside Cloudflare R2"
    )

    drive = transit_kind(remote("gdrive_work"), remote("gdrive_home"), TYPES)
    assert transit_sentence(drive, remote("gdrive_work"), remote("gdrive_home"), TYPES, russian=True) == (
        "напрямую, силами Google Drive"
    )


@pytest.mark.parametrize(
    ("backend", "expected"),
    [
        (RemoteBackend("s3", "Cloudflare"), "Cloudflare R2"),
        (RemoteBackend("s3", "Wasabi"), "Wasabi"),
        (RemoteBackend("s3", "SomethingNew"), "SomethingNew (S3)"),
        (RemoteBackend("s3"), "S3"),
        (RemoteBackend("drive"), "Google Drive"),
        (RemoteBackend("sftp"), "SFTP"),
    ],
)
def test_a_service_is_called_by_its_own_name(backend: RemoteBackend, expected: str) -> None:
    assert backend_service_name(backend) == expected


def test_a_sentence_without_a_service_is_left_alone() -> None:
    """Only the direct case names anybody; the others must not sprout a blank."""
    for kind in (TRANSIT_LOCAL, TRANSIT_FROM_HERE, TRANSIT_TO_HERE, TRANSIT_THROUGH_HERE):
        sentence = transit_sentence(kind, here(), remote("r2_media"), TYPES, russian=True)
        assert "{service}" not in sentence and sentence


def test_copying_a_folder_to_a_folder_points_at_robocopy() -> None:
    """This project already does local copying better, one section away."""
    objection = route_objection("route_copy", here("C:/in"), here("D:/out"))

    assert objection is not None
    assert "Robocopy" in objection["reason_ru"]


def test_comparing_two_local_folders_is_allowed_here() -> None:
    """Robocopy weighs size and time; rclone can compare by hash. That is a reason."""
    assert route_objection("route_check", here("C:/in"), here("D:/out")) is None


@pytest.mark.parametrize(
    ("source", "target"),
    [
        (here("C:/same"), here("C:/same")),
        (remote("r2_media"), remote("r2_media")),
    ],
)
def test_a_route_that_ends_where_it_starts_is_refused(
    source: RcloneEndpointSpec, target: RcloneEndpointSpec
) -> None:
    """Both slots offer the whole endpoint list, so this pair is buildable today."""
    assert route_objection("route_copy", source, target) is not None
