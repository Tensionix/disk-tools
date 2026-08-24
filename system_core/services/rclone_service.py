from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
import json
import os
import re
import shutil
import subprocess


RCLONE_OPERATION_MODES: dict[str, dict[str, str]] = {
    "version": {
        "label": "Version",
        "label_ru": "Версия",
        "description": "Show rclone diagnostics.",
        "description_ru": "Показать диагностику rclone.",
    },
    "config": {
        "label": "Config",
        "label_ru": "Настройка",
        "description": "Open interactive rclone config in a visible console.",
        "description_ru": "Открыть интерактивную настройку rclone в отдельной консоли.",
    },
    "gui": {
        "label": "GUI",
        "label_ru": "GUI",
        "description": "Open the official local rclone GUI.",
        "description_ru": "Открыть официальный локальный rclone GUI.",
    },
    "list_remotes": {
        "label": "List remotes",
        "label_ru": "Список remote",
        "description": "Show configured rclone remotes.",
        "description_ru": "Показать настроенные rclone remote.",
    },
    "about_remote": {
        "label": "About remote",
        "label_ru": "Инфо remote",
        "description": "Show remote quota and usage.",
        "description_ru": "Показать квоту и занятое место remote.",
    },
    "list_remote_path": {
        "label": "List remote path",
        "label_ru": "Список папки",
        "description": "List files/folders under remote:path with lsf.",
        "description_ru": "Показать remote:path через lsf.",
    },
    "mkdir_remote": {
        "label": "Make remote folder",
        "label_ru": "Создать папку",
        "description": "Create a remote folder.",
        "description_ru": "Создать папку на remote.",
    },
    "transfer_run": {
        "label": "Transfer",
        "label_ru": "Перенос",
        "description": "One master, a list of machines, one of five operations.",
        "description_ru": "Один эталон, список машин, одна из пяти операций.",
    },
    "storage_size": {
        "label": "How much is stored",
        "label_ru": "Сколько занято",
        "description": "Total size and object count under the path.",
        "description_ru": "Общий объём и число объектов по пути.",
    },
    "storage_cleanup": {
        "label": "Clear unfinished uploads",
        "label_ru": "Убрать недозалитое",
        "description": "Remove abandoned multipart uploads. They are invisible in listings and still billed.",
        "description_ru": "Удалить брошенные части многочастных заливок: в списке файлов их не видно, а платят за них.",
    },
    "storage_dedupe": {
        "label": "Find duplicates",
        "label_ru": "Найти дубликаты",
        "description": "List objects sharing a name. Nothing is deleted without asking.",
        "description_ru": "Показать объекты с одинаковыми именами. Ничего не удаляется без вопроса.",
    },
    "storage_link": {
        "label": "Public link",
        "label_ru": "Публичная ссылка",
        "description": "Generate a link to the object, where the storage supports it.",
        "description_ru": "Выдать ссылку на объект, если хранилище это умеет.",
    },
    "storage_hashsum": {
        "label": "Checksum file",
        "label_ru": "Файл контрольных сумм",
        "description": "Produce hashes for everything under the path, to publish beside a release.",
        "description_ru": "Посчитать хеши всего по пути — чтобы выложить рядом с релизом.",
    },
    "config_encrypt": {
        "label": "Encrypt the config",
        "label_ru": "Зашифровать конфиг",
        "description": "Set a passphrase on rclone.conf so a lost disk gives up nothing — not even which clouds are used.",
        "description_ru": "Поставить фразу на rclone.conf, чтобы потерянный диск не выдал ничего — даже того, какими облаками вы пользуетесь.",
    },
    "config_encryption_check": {
        "label": "Is the config encrypted",
        "label_ru": "Проверить шифрование конфига",
        "description": "Report whether the active config is protected.",
        "description_ru": "Сообщить, защищён ли текущий конфиг.",
    },
    "config_decrypt": {
        "label": "Remove config encryption",
        "label_ru": "Снять шифрование конфига",
        "description": "Take the passphrase off. The file becomes readable by anything that can open it.",
        "description_ru": "Убрать фразу. Файл станет читаемым для всего, что сможет его открыть.",
    },
    "remote_create_s3": {
        "label": "Create/update S3 remote",
        "label_ru": "Создать/обновить S3 remote",
        "description": "Connect Cloudflare R2, Wasabi, Selectel or any S3-compatible storage by keys.",
        "description_ru": "Подключить Cloudflare R2, Wasabi, Selectel или любое S3-совместимое хранилище по ключам.",
    },
    "remote_create_sftp": {
        "label": "Create/update SFTP remote",
        "label_ru": "Создать SFTP remote",
        "description": "Create or update an SFTP remote from GUI fields.",
        "description_ru": "Создать или обновить SFTP remote из полей GUI.",
    },
    "remote_auth_wizard": {
        "label": "OAuth providers",
        "label_ru": "Провайдеры OAuth",
        "description": "Open a focused rclone provider authorization wizard.",
        "description_ru": "Открыть мастер авторизации облачного provider-а RClone.",
    },
    "remote_test": {
        "label": "Test remote",
        "label_ru": "Тест remote",
        "description": "Run a quick lsf test for remote:path.",
        "description_ru": "Быстро проверить remote:path через lsf.",
    },
}

RCLONE_REMOTE_MODES = {"about_remote", "list_remote_path", "mkdir_remote", "remote_test"}
# The endpoint route is gone: five operations over a list of machines say the
# same thing without needing six modes to say it, and without the copy and the
# check being different buttons that take the same pair.
RCLONE_ROUTE_MODES: set[str] = set()
RCLONE_AUTH_MODES = {"remote_create_sftp", "remote_create_s3", "remote_auth_wizard"}
RCLONE_CONFIG_MODES = {"config_encrypt", "config_encryption_check", "config_decrypt"}

# Things done to one storage rather than between two. They are not transfers and
# do not belong in the row of operations: nothing moves, there is no second end.
RCLONE_STORAGE_MODES = {
    "storage_size",
    "storage_cleanup",
    "storage_dedupe",
    "storage_link",
    "storage_hashsum",
}

# S3 is one backend serving many storages, and each wants its own endpoint. These
# are the ones worth a name in the window; anything else goes in as a custom
# endpoint with the provider left as Other.
RCLONE_S3_PROVIDERS: dict[str, dict[str, str]] = {
    "Cloudflare": {
        "label": "Cloudflare R2",
        "label_ru": "Cloudflare R2",
        "endpoint_hint": "https://<account_id>.r2.cloudflarestorage.com",
        "region": "auto",
    },
    "Wasabi": {
        "label": "Wasabi",
        "label_ru": "Wasabi",
        "endpoint_hint": "https://s3.<region>.wasabisys.com",
        "region": "",
    },
    "Selectel": {
        "label": "Selectel",
        "label_ru": "Selectel",
        "endpoint_hint": "https://s3.storage.selcloud.ru",
        "region": "ru-1",
    },
    "AWS": {
        "label": "Amazon S3",
        "label_ru": "Amazon S3",
        "endpoint_hint": "",
        "region": "",
    },
    "Other": {
        "label": "Other S3-compatible",
        "label_ru": "Другое S3-совместимое",
        "endpoint_hint": "https://s3.example.com",
        "region": "",
    },
}
RCLONE_TRANSFER_MODES = {"transfer_run"}
RCLONE_SOURCE_MODES: set[str] = set()
RCLONE_TARGET_MODES: set[str] = set()
# config_encrypt asks for the phrase twice on the terminal, the same way the
# OAuth wizard needs a browser: it belongs in its own window, not in a field.
RCLONE_INTERACTIVE_MODES = {"config", "gui", "remote_auth_wizard", "config_encrypt", "config_decrypt"}

RCLONE_ENDPOINT_KINDS: dict[str, dict[str, str]] = {
    # A link is a source and never a destination: it is somewhere to fetch from,
    # and the fetch happens on the storage's side, so the file never comes down
    # this machine's channel on its way up again.
    "url": {"label": "Link", "label_ru": "Ссылка"},
    "workbench_source": {"label": "Workbench Source", "label_ru": "Workbench Источник"},
    "workbench_target": {"label": "Workbench Target", "label_ru": "Workbench Цель"},
    "saved_remote": {"label": "Saved remote", "label_ru": "Saved remote"},
}

RCLONE_AUTH_BACKENDS: dict[str, dict[str, str]] = {
    "yandex": {"label": "Yandex Disk", "label_ru": "Яндекс.Диск"},
    "drive": {"label": "Google Drive", "label_ru": "Google Drive"},
    "onedrive": {"label": "OneDrive", "label_ru": "OneDrive"},
    "dropbox": {"label": "Dropbox", "label_ru": "Dropbox"},
    "box": {"label": "Box", "label_ru": "Box"},
    "mega": {"label": "Mega", "label_ru": "Mega"},
}

RCLONE_SFTP_AUTH_METHODS: dict[str, dict[str, str]] = {
    "agent": {"label": "ssh-agent", "label_ru": "ssh-agent"},
    "key_file": {"label": "Key file", "label_ru": "Файл ключа"},
    "password": {"label": "Password", "label_ru": "Пароль"},
}

RCLONE_CONFIG_SCOPES: dict[str, dict[str, str]] = {
    "portable": {"label": "Portable", "label_ru": "Portable"},
    "system": {"label": "System", "label_ru": "System"},
    "custom": {"label": "Custom path", "label_ru": "Custom path"},
}
RCLONE_DEFAULT_CONFIG_SCOPE = "portable"

RCLONE_FLAG_PROFILES: dict[str, dict[str, Any]] = {
    "safe_yandex_upload": {
        "label": "safe_cloud_upload",
        "label_ru": "safe_cloud_upload",
        "args": [
            "--transfers",
            "1",
            "--checkers",
            "1",
            "--retries",
            "10",
            "--low-level-retries",
            "50",
            "--retries-sleep",
            "10s",
            "--timeout",
            "10m",
            "--contimeout",
            "30s",
            "--stats",
            "1s",
            "--progress",
        ],
    },
    "unstable_mobile": {
        "label": "unstable_mobile",
        "label_ru": "unstable_mobile",
        "args": [
            "--transfers",
            "1",
            "--checkers",
            "1",
            "--retries",
            "20",
            "--low-level-retries",
            "80",
            "--retries-sleep",
            "15s",
            "--timeout",
            "15m",
            "--contimeout",
            "45s",
            "--stats",
            "1s",
            "--progress",
        ],
    },
    "balanced": {
        "label": "balanced",
        "label_ru": "balanced",
        "args": [
            "--transfers",
            "2",
            "--checkers",
            "4",
            "--retries",
            "5",
            "--low-level-retries",
            "20",
            "--retries-sleep",
            "10s",
            "--timeout",
            "10m",
            "--contimeout",
            "30s",
            "--stats",
            "1s",
            "--progress",
        ],
    },
    "fast_lan_to_cloud": {
        "label": "fast_lan_to_cloud",
        "label_ru": "fast_lan_to_cloud",
        "args": [
            "--transfers",
            "4",
            "--checkers",
            "8",
            "--retries",
            "3",
            "--low-level-retries",
            "10",
            "--timeout",
            "10m",
            "--contimeout",
            "30s",
            "--stats",
            "1s",
            "--progress",
        ],
    },
}

RCLONE_DEFAULT_PROFILE = "safe_yandex_upload"

_SECRET_PATTERNS = (
    re.compile(
        r'(?i)("?(?:access_token|refresh_token|client_secret|password|secret_access_key)"?\s*[:=]\s*)("[^"]*"|\S+)'
    ),
    # `rclone config create name s3 secret_access_key VALUE` puts the secret in a
    # positional pair, with no colon or equals sign for the rule above to catch.
    re.compile(r"(?i)(\bsecret_access_key\s+)(\S+)"),
    re.compile(r'(?i)(\btoken\s*=\s*)\{.*\}'),
    re.compile(r"(?i)(\bBearer\s+)[A-Za-z0-9._~+/=-]+"),
    re.compile(r"(?i)(\b(?:pass|key_file_pass)\s+)(\S+)"),
)
_ANSI_PATTERN = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_PERCENT_PATTERN = re.compile(r"(?<![\d.])(\d+(?:\.\d+)?)%")


@dataclass(frozen=True)
class RcloneCommandSpec:
    mode: str
    title: str
    command: list[str]
    log_file: Path
    remote_spec: str = ""
    local_source: Path | None = None
    local_target: Path | None = None
    report_file: Path | None = None
    interactive: bool = False
    source_spec: str = ""
    target_spec: str = ""
    config_scope: str = RCLONE_DEFAULT_CONFIG_SCOPE
    config_file: Path | None = None
    cache_dir: Path | None = None


@dataclass(frozen=True)
class RcloneEndpointSpec:
    kind: str
    spec: str
    label: str
    local_path: Path | None = None
    remote_name: str = ""
    remote_path: str = ""


TRANSIT_LOCAL = "local"
TRANSIT_FROM_HERE = "from_here"
TRANSIT_TO_HERE = "to_here"
TRANSIT_THROUGH_HERE = "through_here"
TRANSIT_PROVIDER_SIDE = "provider_side"

# Sending and passing through are not the same thing and must not share a word.
# On an upload the computer is where the data comes from; only when both ends are
# elsewhere is it a waypoint, and then "транзитом" is the accurate word.
TRANSIT_LABELS: dict[str, dict[str, str]] = {
    TRANSIT_LOCAL: {
        "label": "on this computer",
        "label_ru": "на этом компьютере",
    },
    TRANSIT_FROM_HERE: {
        "label": "from this computer",
        "label_ru": "с этого компьютера",
    },
    TRANSIT_TO_HERE: {
        "label": "to this computer",
        "label_ru": "на этот компьютер",
    },
    TRANSIT_THROUGH_HERE: {
        "label": "through this computer, in transit",
        "label_ru": "транзитом через этот компьютер",
    },
    # {service} is filled in with the actual name — "Cloudflare R2", "Google
    # Drive". "By the provider" named nobody: in Russian провайдер reads as the
    # internet provider first, and either way it does not say who does the work.
    TRANSIT_PROVIDER_SIDE: {
        "label": "directly, inside {service}",
        "label_ru": "напрямую, силами {service}",
    },
}


@dataclass(frozen=True)
class RemoteBackend:
    """What a saved remote actually is, as rclone recorded it.

    `type` decides whether a copy can stay inside the service. `provider` only
    exists for the S3 family, where one backend serves many services — s3 alone
    does not tell Cloudflare R2 from Wasabi or Selectel, and the window has to
    name the service that will be doing the work.
    """

    type: str = ""
    provider: str = ""
    host: str = ""


# One backend, many services. Naming "S3" where the answer is "Cloudflare R2"
# tells the user nothing they can act on.
BACKEND_SERVICE_NAMES: dict[str, str] = {
    "drive": "Google Drive",
    "onedrive": "OneDrive",
    "yandex": "Yandex Disk",
    "dropbox": "Dropbox",
    "box": "Box",
    "mega": "Mega",
    "sftp": "SFTP",
    "ftp": "FTP",
    "webdav": "WebDAV",
    "s3": "S3",
}
BACKEND_SERVICE_NAMES_RU = {**BACKEND_SERVICE_NAMES, "yandex": "Яндекс.Диск"}

S3_SERVICE_NAMES: dict[str, str] = {
    "cloudflare": "Cloudflare R2",
    "aws": "Amazon S3",
    "wasabi": "Wasabi",
    "selectel": "Selectel",
    "storj": "Storj",
    "minio": "MinIO",
    "digitalocean": "DigitalOcean Spaces",
    "scaleway": "Scaleway",
}


CONFIG_PASSPHRASE_ENV = "RCLONE_CONFIG_PASS"


def config_passphrase_env(passphrase: str | None) -> dict[str, str]:
    """The passphrase for an encrypted config, handed over out of sight.

    Through the environment rather than the command line: an argument shows up in
    the process list and in every log line that echoes the command, and this file
    is the one thing on a travelling disk that must not be readable.

    Empty means the config is not encrypted and rclone needs nothing.
    """
    text = str(passphrase or "")
    return {CONFIG_PASSPHRASE_ENV: text} if text else {}


S3_CREDENTIALS_ENV = "AWS_SHARED_CREDENTIALS_FILE"


def s3_credentials_env(config_text: Any) -> dict[str, str]:
    """The credentials file an S3 remote points at, handed over through the
    environment because the config key alone does not reach.

    rclone accepts `shared_credentials_file` in the config and writes it there,
    but with `env_auth = true` the lookup runs through the AWS SDK chain, and the
    chain reads its own variable instead: a named section fails with "failed to
    get shared config profile" while `AWS_SHARED_CREDENTIALS_FILE` makes the same
    remote work. Measured against a live R2 bucket on rclone 1.75.0 — with
    env_auth false the file is not read at all and requests go out unsigned,
    which R2 reports as `InvalidArgument: Authorization`.

    Several remotes naming several different files cannot be served by one
    variable, so nothing is set and rclone is left to its own devices: guessing
    which file wins would break whichever remote is not chosen.
    """
    files = {
        match.strip()
        for match in re.findall(r"^\s*shared_credentials_file\s*=\s*(.+?)\s*$", str(config_text or ""), re.M)
        if match.strip()
    }
    return {S3_CREDENTIALS_ENV: files.pop()} if len(files) == 1 else {}


def config_is_encrypted(dump_output: Any, exit_code: int = 0) -> bool:
    """Whether the active config is encrypted, judged from `config dump`.

    An encrypted config that was not given a passphrase fails rather than
    returning an empty set, so a non-zero exit with nothing parsable is the
    signal. Guessing from the file's bytes would be fragile — rclone owns the
    format and it has changed before.
    """
    if exit_code == 0:
        return False
    text = str(dump_output or "").lower()
    return "password" in text or "encrypt" in text



def parse_config_dump(text: Any) -> dict[str, RemoteBackend]:
    """Map remote name -> backend from `rclone config dump` output.

    Both facts are already in the config — the window never has to ask the user
    what kind of remote they made.
    """
    try:
        document = json.loads(str(text or "").strip() or "{}")
    except Exception:
        return {}
    if not isinstance(document, dict):
        return {}
    backends: dict[str, RemoteBackend] = {}
    for name, section in document.items():
        if not isinstance(section, dict):
            continue
        backend_type = str(section.get("type") or "").strip().lower()
        if backend_type:
            backends[str(name)] = RemoteBackend(
                type=backend_type,
                provider=str(section.get("provider") or "").strip(),
                host=str(section.get("host") or section.get("url") or "").strip(),
            )
    return backends


def backend_service_name(backend: RemoteBackend, *, russian: bool = False) -> str:
    """What to call the service in a sentence a person reads."""
    if backend.type == "s3" and backend.provider:
        named = S3_SERVICE_NAMES.get(backend.provider.strip().lower())
        if named:
            return named
        return f"{backend.provider.strip()} (S3)"
    table = BACKEND_SERVICE_NAMES_RU if russian else BACKEND_SERVICE_NAMES
    return table.get(backend.type, backend.type or ("хранилище" if russian else "the service"))


def transit_kind(
    source: RcloneEndpointSpec, target: RcloneEndpointSpec, backends: dict[str, RemoteBackend]
) -> str:
    """How the bytes will actually travel between these two endpoints.

    This is the fact the window was missing. The section exists for moving data
    between clouds, and whether that happens inside the provider or by way of
    this machine is not a mode anybody should have to pick — it follows from the
    pair, and rclone already knows both backends.

    Server-side copy needs the same backend on both ends: two Google Drive
    accounts, two R2 buckets, two S3-compatible remotes. Across providers there
    is no protocol for one to fetch from the other, so the bytes come here first
    whatever flags are set.

    Sending and passing through are kept apart. Uploading a release to R2 starts
    here — the computer is the source, not a waypoint — and calling that transit
    would misdescribe the one route this window is used for most.
    """
    source_remote = source.remote_name if source.local_path is None else ""
    target_remote = target.remote_name if target.local_path is None else ""
    if not source_remote and not target_remote:
        return TRANSIT_LOCAL
    if not source_remote:
        return TRANSIT_FROM_HERE
    if not target_remote:
        return TRANSIT_TO_HERE
    # Compared by backend type only. Two S3 remotes at different services —
    # R2 and Wasabi — share the type but not the machines, and rclone falls back
    # to a normal transfer; the flag is harmless there, the promise would not be.
    source_backend = backends.get(source_remote, RemoteBackend())
    target_backend = backends.get(target_remote, RemoteBackend())
    if not source_backend.type or source_backend.type != target_backend.type:
        return TRANSIT_THROUGH_HERE
    source_service = _service_key(source_backend)
    if source_service != _service_key(target_backend):
        return TRANSIT_THROUGH_HERE
    # Two unknowns are not a match. A backend whose service is the host, with no
    # host recorded, tells us nothing — and nothing is not grounds for promising
    # a route that skips this machine.
    if source_backend.type in HOST_IS_THE_SERVICE and not source_service:
        return TRANSIT_THROUGH_HERE
    return TRANSIT_PROVIDER_SIDE


# For a cloud the backend is the service: `drive` means Google and nothing else,
# so two `drive` remotes are two accounts at one company and a copy can stay
# inside it. For these the backend says nothing of the kind — one `sftp` is any
# machine that speaks SSH, and two of them are two machines with no path between
# them. The service is the host.
HOST_IS_THE_SERVICE = {"sftp", "ftp", "webdav", "http", "smb", "nfs"}


def _service_key(backend: RemoteBackend) -> str:
    """What has to match for a copy to be able to stay where it is."""
    if backend.type in HOST_IS_THE_SERVICE:
        return backend.host.strip().lower()
    if backend.type == "s3":
        return backend.provider.strip().lower()
    return ""


def transit_sentence(
    kind: str,
    source: RcloneEndpointSpec,
    target: RcloneEndpointSpec,
    backends: dict[str, RemoteBackend],
    *,
    russian: bool = False,
) -> str:
    """The route in words, with the service named where one does the work."""
    template = TRANSIT_LABELS[kind]["label_ru" if russian else "label"]
    if "{service}" not in template:
        return template
    backend = backends.get(target.remote_name) or backends.get(source.remote_name) or RemoteBackend()
    return template.format(service=backend_service_name(backend, russian=russian))


def route_objection(mode: str, source: RcloneEndpointSpec, target: RcloneEndpointSpec) -> dict[str, str] | None:
    """Why this pair does not belong in this section, if it does not.

    The endpoint list is offered whole to both slots, so pairs can be built that
    rclone will execute and nobody wants: a folder onto itself, or a local copy
    this project already does better one section away.

    Copying folder to folder on Windows is Robocopy's job — it is native, it
    keeps NTFS attributes and it is faster. Comparing two local folders is not:
    Robocopy weighs size and timestamp, rclone can compare by hash, and that is
    a real reason to be here. So the objection follows the verb, not the pair.
    """
    if source.local_path is not None and target.local_path is not None:
        if source.local_path == target.local_path:
            return {
                "reason": "Source and target are the same folder.",
                "reason_ru": "Источник и приёмник — одна и та же папка.",
            }
        if mode in {"route_copy", "upload_copy_safe", "download_copy_safe"}:
            return {
                "reason": "Copying folder to folder is Robocopy's job: native to Windows, "
                "keeps NTFS attributes, faster. Comparing two local folders by hash is "
                "worth doing here — copying them is not.",
                "reason_ru": "Копирование папки в папку делает Robocopy: он родной для Windows, "
                "сохраняет атрибуты NTFS и быстрее. Сверять две локальные папки по хешам здесь "
                "стоит, копировать — нет.",
            }
    if source.remote_name and source.remote_name == target.remote_name:
        if (source.remote_path or "") == (target.remote_path or ""):
            return {
                "reason": "Source and target are the same place in the same remote.",
                "reason_ru": "Источник и приёмник — одно и то же место в одном remote.",
            }
    return None


def remote_types(options: dict[str, Any]) -> dict[str, RemoteBackend]:
    """Backends the GUI has already read, or nothing.

    The service builds commands without running any, so it never calls
    `rclone config dump` itself; the window reads it once when the remote list
    is refreshed and passes it down. With nothing to go on the pair is treated
    as transit, which is the safe reading — it means the flag is left off.
    """
    value = options.get("remote_types")
    if isinstance(value, dict):
        return {
            str(name): item if isinstance(item, RemoteBackend) else RemoteBackend(type=str(item).strip().lower())
            for name, item in value.items()
            if item
        }
    return parse_config_dump(value) if value else {}


def transit_args(kind: str) -> list[str]:
    """The flag that lets rclone keep a same-backend copy inside the provider.

    Passing it when the ends differ is harmless — rclone falls back to a normal
    transfer — but it is only added where it means something, so the command the
    window shows stays an honest description of what will happen.
    """
    return ["--server-side-across-configs"] if kind == TRANSIT_PROVIDER_SIDE else []


def find_rclone_executable(root: Path) -> Path | None:
    candidates = [
        root / "Tools" / "rclone" / "rclone.exe",
        root / "tools" / "rclone" / "rclone.exe",
        root / "runtime" / "rclone" / "rclone.exe",
        root / "runtime" / "tools" / "rclone" / "rclone.exe",
        root / "system_core" / "rclone.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    for name in ("rclone.exe", "rclone"):
        found = shutil.which(name)
        if found:
            return Path(found)
    return None


def expected_rclone_executable(root: Path) -> Path:
    return root / "Tools" / "rclone" / "rclone.exe"


def normalize_rclone_mode(value: Any) -> str:
    text = str(value or "version").strip().lower()
    return text if text in RCLONE_OPERATION_MODES else "version"


def rclone_mode_label(mode: Any, language: str = "en") -> str:
    normalized = normalize_rclone_mode(mode)
    item = RCLONE_OPERATION_MODES[normalized]
    key = "label_ru" if language == "ru" else "label"
    return str(item.get(key) or item.get("label") or normalized)


def normalize_log_level(value: Any) -> str:
    text = str(value or "INFO").strip().upper()
    return "DEBUG" if text == "DEBUG" else "INFO"


def normalize_config_scope(value: Any) -> str:
    text = str(value or RCLONE_DEFAULT_CONFIG_SCOPE).strip().lower()
    return text if text in RCLONE_CONFIG_SCOPES else RCLONE_DEFAULT_CONFIG_SCOPE


def normalize_flag_profile(value: Any) -> str:
    text = str(value or RCLONE_DEFAULT_PROFILE).strip()
    return text if text in RCLONE_FLAG_PROFILES else RCLONE_DEFAULT_PROFILE


def normalize_endpoint_kind(value: Any, *, default: str = "saved_remote") -> str:
    text = str(value or default).strip().lower()
    return text if text in RCLONE_ENDPOINT_KINDS else default


def normalize_auth_backend(value: Any) -> str:
    text = str(value or "drive").strip().lower()
    return text if text in RCLONE_AUTH_BACKENDS else "drive"


def normalize_sftp_auth_method(value: Any) -> str:
    text = str(value or "agent").strip().lower()
    return text if text in RCLONE_SFTP_AUTH_METHODS else "agent"


def parse_listremotes_output(text: Any) -> list[str]:
    """Turn `rclone listremotes` stdout into clean remote names.

    rclone prints one `name:` per line. Order is preserved so the GUI list
    matches the config file; blanks, duplicates and anything that does not look
    like a remote name are dropped rather than shown to the user.
    """
    names: list[str] = []
    seen: set[str] = set()
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line or not line.endswith(":"):
            continue
        try:
            name = normalize_remote_name(line)
        except ValueError:
            continue
        key = name.lower()
        if key not in seen:
            seen.add(key)
            names.append(name)
    return names


def remote_name_in(names: Iterable[str], remote_name: Any) -> bool:
    try:
        needle = normalize_remote_name(remote_name).lower()
    except ValueError:
        return False
    return any(str(name).strip().lower() == needle for name in names)


def normalize_remote_name(value: Any, *, required: bool = True) -> str:
    text = str(value or "").strip().rstrip(":").strip()
    if not text:
        if required:
            raise ValueError("Rclone remote name is required.")
        return ""
    if text.startswith("-"):
        raise ValueError("Rclone remote name cannot start with '-'.")
    if any(char in text for char in (":", "/", "\\", "\r", "\n", "\0")):
        raise ValueError("Rclone remote name must not contain ':', slashes, or control characters.")
    return text


def normalize_remote_path(value: Any) -> str:
    text = str(value or "").strip()
    text = text[1:] if text.startswith(":") else text
    text = text.replace("\\", "/")
    if any(char in text for char in ("\r", "\n", "\0")):
        raise ValueError("Rclone remote path must not contain control characters.")
    return text


def remote_spec(remote_name: Any, remote_path: Any = "") -> str:
    remote = normalize_remote_name(remote_name)
    path = normalize_remote_path(remote_path)
    return f"{remote}:{path}"


def normalize_server_host(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError("SFTP host is required.")
    if any(char in text for char in (" ", "\t", "\r", "\n", "\0", "/", "\\")):
        raise ValueError("SFTP host must be a host name or IP address without spaces/slashes.")
    return text


def normalize_server_port(value: Any) -> str:
    text = str(value or "22").strip()
    try:
        port = int(text)
    except ValueError as exc:
        raise ValueError("SFTP port must be a number.") from exc
    if port < 1 or port > 65535:
        raise ValueError("SFTP port must be in range 1..65535.")
    return str(port)


def normalize_server_user(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError("SFTP user is required.")
    if any(char in text for char in (" ", "\t", "\r", "\n", "\0", "@", ":", "/", "\\")):
        raise ValueError("SFTP user must not contain spaces or @:/\\ characters.")
    return text


def normalize_optional_file(value: Any) -> str:
    text = str(value or "").strip()
    if any(char in text for char in ("\r", "\n", "\0")):
        raise ValueError("Path must not contain control characters.")
    return text


def normalize_source_url(value: Any) -> str:
    """The link to fetch from.

    Only http and https: rclone would take other schemes, and a transfer that
    quietly reads a local file because the text looked like a path is a surprise
    nobody wants at the far end.
    """
    text = str(value or "").strip()
    if not text:
        raise ValueError("A link is required.")
    if not text.lower().startswith(("http://", "https://")):
        raise ValueError(f"Only http and https links are accepted: {text}")
    return text


def normalize_s3_provider(value: Any) -> str:
    text = str(value or "").strip()
    for known in RCLONE_S3_PROVIDERS:
        if text.lower() == known.lower():
            return known
    return "Cloudflare"


def normalize_s3_endpoint(value: Any, *, provider: str = "Cloudflare") -> str:
    """The address of the storage, if it needs one.

    Amazon works off its region and wants no endpoint. Everything else does:
    R2's carries the account id, and without it the remote resolves to Amazon
    and fails with an error that says nothing about the real cause.
    """
    text = str(value or "").strip().rstrip("/")
    if provider == "AWS":
        return ""
    if not text:
        raise ValueError(
            f"Endpoint is required for {provider}. "
            f"Expected something like {RCLONE_S3_PROVIDERS.get(provider, {}).get('endpoint_hint', 'https://…')}"
        )
    if not text.startswith(("http://", "https://")):
        text = "https://" + text
    return text


def normalize_s3_credentials_file(value: Any) -> str:
    """Where on this machine the keys for this storage already live.

    An AWS-style credentials file: sections by name, each holding
    aws_access_key_id and aws_secret_access_key. One file can carry several
    storages, which is why the profile is asked for separately.

    Empty is allowed and means rclone looks where it always looks —
    AWS_SHARED_CREDENTIALS_FILE, or the user's home directory. Naming a file that
    is not there is not allowed: the remote would be created, look healthy, and
    fail on first use with an authentication error that says nothing about a
    missing file.
    """
    text = str(value or "").strip().strip('"')
    if not text:
        return ""
    path = Path(text).expanduser()
    if not path.is_file():
        raise ValueError(f"Credentials file was not found: {path}")
    return str(path)


def normalize_s3_profile(value: Any) -> str:
    """Which section of that file. Defaults to the one AWS tooling defaults to."""
    text = str(value or "").strip().strip("[]")
    return text or "default"


PORTABLE_SSH_DIR = ("config", "ssh")


def portable_path(value: Any, project_root: Path) -> str:
    """A path inside the project, written relative so the folder can travel.

    rclone resolves a relative path against the working directory, which for this
    project is its own root — checked against a live server, not assumed. So a
    key kept at config\\ssh\\eden.key still works after the folder is copied to a
    different disk with a different letter, and an absolute path does not.

    Anything outside the project is left exactly as written: it is not ours to
    rewrite, and it will not travel anyway.
    """
    text = str(value or "").strip().strip('"')
    if not text:
        return ""
    try:
        resolved = Path(text).expanduser().resolve()
        return str(resolved.relative_to(project_root.resolve()))
    except (ValueError, OSError):
        return text


def import_ssh_material(source: Any, project_root: Path, name: str) -> Path:
    """Copy a key or a known_hosts file into the project so it travels with it.

    The copy is deliberate rather than a move: the original stays where the rest
    of the system expects it, and a project that turns out not to need the key
    can be emptied without hunting for where the only copy went.

    A name already taken is never overwritten. `id_rsa` is the most common key
    name there is, so two servers bringing one each is ordinary — and silently
    replacing the first would cost access to that server without a word. The
    same file imported twice returns what is already there instead of piling up
    copies.
    """
    origin = Path(str(source or "").strip().strip('"')).expanduser()
    if not origin.is_file():
        raise ValueError(f"Файл не найден: {origin}")
    folder = project_root.joinpath(*PORTABLE_SSH_DIR)
    folder.mkdir(parents=True, exist_ok=True)
    stem, suffix = Path(name).stem, Path(name).suffix
    target = folder / name
    attempt = 1
    while target.exists():
        if target.read_bytes() == origin.read_bytes():
            return target
        attempt += 1
        target = folder / f"{stem}-{attempt}{suffix}"
    shutil.copyfile(origin, target)
    return target


def known_host_key_algorithms(known_hosts_file: Any, host: Any) -> list[str]:
    """The host key types already recorded for this host, in the order found.

    A server usually offers three keys — ed25519, ecdsa and rsa — while
    known_hosts holds whichever one was recorded the first time. OpenSSH notices
    that and asks the server for the type it can already check. rclone's Go
    library does not: it takes whatever it prefers, looks that up, finds an entry
    for the host but not for that key, and reports `knownhosts: key mismatch` —
    which reads like an attack and is nothing of the sort.

    So the remote is told to ask for the types that can actually be verified.
    Returning nothing is fine and means "let rclone choose": either the file is
    unreadable or the host is new, and in both cases guessing helps nobody.
    """
    path = normalize_optional_file(known_hosts_file)
    name = str(host or "").strip()
    if not path or not name:
        return []
    algorithms: list[str] = []
    try:
        for raw_line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 3:
                continue
            hosts, algorithm = parts[0], parts[1]
            # Hashed entries (|1|...) cannot be matched by name without hashing
            # the name with each salt, which is more machinery than this is worth.
            if hosts.startswith("|"):
                continue
            if name not in [item.strip() for item in hosts.split(",")]:
                continue
            for candidate in _rsa_variants(algorithm):
                if candidate not in algorithms:
                    algorithms.append(candidate)
    except Exception:
        return []
    return algorithms


def _rsa_variants(algorithm: str) -> list[str]:
    """An entry written as ssh-rsa also verifies the modern SHA-2 signatures.

    They are the same key; only the signature algorithm differs, and servers
    have defaulted to the SHA-2 forms for years.
    """
    if algorithm == "ssh-rsa":
        return ["rsa-sha2-512", "rsa-sha2-256", "ssh-rsa"]
    return [algorithm]


def require_sftp_known_hosts_file(value: Any) -> str:
    text = normalize_optional_file(value)
    if not text:
        raise ValueError("SFTP known_hosts file is required for host key verification.")
    return text


def portable_rclone_config_path(root: Path) -> Path:
    return root / "config" / "rclone" / "rclone.conf"


def portable_rclone_cache_dir(root: Path) -> Path:
    return root / "tmp" / "rclone-cache"


def system_rclone_config_path() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "rclone" / "rclone.conf"
    return Path.home() / "AppData" / "Roaming" / "rclone" / "rclone.conf"


def rclone_config_file_for_scope(root: Path, options: dict[str, Any]) -> Path | None:
    scope = normalize_config_scope(options.get("config_scope"))
    if scope == "system":
        return system_rclone_config_path()
    if scope == "custom":
        custom_path = normalize_optional_file(options.get("custom_config"))
        if not custom_path:
            raise ValueError("Custom RClone config path is required.")
        return Path(custom_path).expanduser()
    return portable_rclone_config_path(root)


def rclone_cache_dir_for_scope(root: Path, options: dict[str, Any]) -> Path | None:
    scope = normalize_config_scope(options.get("config_scope"))
    if scope == "system":
        return None
    return portable_rclone_cache_dir(root)


def rclone_global_config_args(root: Path, options: dict[str, Any], *, ensure_dirs: bool = False) -> list[str]:
    scope = normalize_config_scope(options.get("config_scope"))
    if scope == "system":
        return []

    config_file = rclone_config_file_for_scope(root, options)
    cache_dir = rclone_cache_dir_for_scope(root, options)
    if config_file is None:
        return []

    if ensure_dirs:
        config_file.parent.mkdir(parents=True, exist_ok=True)
        if cache_dir is not None:
            cache_dir.mkdir(parents=True, exist_ok=True)
        secure_rclone_config_permissions(config_file)

    args = ["--config", str(config_file)]
    if cache_dir is not None:
        args.extend(["--cache-dir", str(cache_dir)])
    return args


def secure_rclone_config_permissions(config_file: Path | None) -> None:
    if config_file is None or os.name == "nt" or not config_file.exists():
        return
    try:
        os.chmod(config_file, 0o600)
    except OSError:
        return


def endpoint_spec(options: dict[str, Any], role: str) -> RcloneEndpointSpec:
    kind = normalize_endpoint_kind(options.get(f"{role}_kind"), default="saved_remote")
    if kind == "url":
        if role != "source":
            raise ValueError("A link can only be the source of a transfer, never its destination.")
        url = normalize_source_url(options.get("source_url"))
        return RcloneEndpointSpec(kind=kind, spec=url, label=url)
    if kind == "workbench_source":
        path = _path_from_option(options, "source_path")
        return RcloneEndpointSpec(kind=kind, spec=str(path), label=f"Workbench Source: {path}", local_path=path)
    if kind == "workbench_target":
        path = _path_from_option(options, "target_path")
        return RcloneEndpointSpec(kind=kind, spec=str(path), label=f"Workbench Target: {path}", local_path=path)

    default_remote = "drive" if role == "source" else "server"
    default_path = "Audion" if role == "source" else "/home/user/backups"
    remote_name = normalize_remote_name(options.get(f"{role}_remote_name", options.get("remote_name", default_remote)))
    remote_path = normalize_remote_path(options.get(f"{role}_remote_path", options.get("remote_path", default_path)))
    spec = remote_spec(remote_name, remote_path)
    return RcloneEndpointSpec(
        kind=kind,
        spec=spec,
        label=f"{remote_name}:{remote_path}" if remote_path else f"{remote_name}:",
        remote_name=remote_name,
        remote_path=remote_path,
    )


def _sanitize_file_part(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in value).strip("_")
    return cleaned or "rclone"


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    for index in range(2, 10000):
        candidate = path.with_name(f"{stem}_{index:03d}{suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Could not allocate unique path: {path}")


def rclone_log_path(logs_dir: Path, mode: str, *, preview: bool = False) -> Path:
    cleaned = _sanitize_file_part(mode)
    if preview:
        return logs_dir / f"YYYYMMDD_HHMMSS_rclone_{cleaned}.log"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return _unique_path(logs_dir / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_rclone_{cleaned}.log")


def rclone_report_path(logs_dir: Path, mode: str, suffix: str, *, preview: bool = False) -> Path:
    cleaned = _sanitize_file_part(mode)
    cleaned_suffix = _sanitize_file_part(suffix)
    if preview:
        return logs_dir / f"YYYYMMDD_HHMMSS_rclone_{cleaned}.{cleaned_suffix}.txt"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return _unique_path(logs_dir / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_rclone_{cleaned}.{cleaned_suffix}.txt")


def _profile_args(profile: Any, bwlimit: Any = "") -> list[str]:
    profile_id = normalize_flag_profile(profile)
    args = list(RCLONE_FLAG_PROFILES[profile_id]["args"])
    limit = str(bwlimit or "").strip()
    if limit:
        if limit.startswith("-") or any(char in limit for char in ("\r", "\n", "\0")):
            raise ValueError("Rclone bwlimit value is invalid.")
        args.extend(["--bwlimit", limit])
    return args


def _path_from_option(options: dict[str, Any], key: str) -> Path:
    return Path(str(options.get(key) or "")).expanduser()


def build_rclone_command(root: Path, logs_dir: Path, options: dict[str, Any], *, preview: bool = False) -> RcloneCommandSpec:
    mode = normalize_rclone_mode(options.get("mode"))
    rclone = find_rclone_executable(root) or expected_rclone_executable(root)
    if not preview and not rclone.exists():
        raise RuntimeError("rclone.exe was not found. Install rclone or place it into Tools\\rclone\\rclone.exe.")

    config_scope = normalize_config_scope(options.get("config_scope"))
    config_file = rclone_config_file_for_scope(root, options)
    cache_dir = rclone_cache_dir_for_scope(root, options)
    log_file = rclone_log_path(logs_dir, mode, preview=preview)
    command = [
        str(rclone),
        *rclone_global_config_args(root, options, ensure_dirs=not preview),
        "--log-file",
        str(log_file),
        "--log-level",
        normalize_log_level(options.get("log_level")),
    ]
    remote = ""
    source: Path | None = None
    target: Path | None = None
    report: Path | None = None
    source_endpoint = ""
    target_endpoint = ""

    if mode == "version":
        command.append("version")
    elif mode == "config":
        command.append("config")
    elif mode == "gui":
        command.append("gui")
    elif mode == "list_remotes":
        command.append("listremotes")
    elif mode == "remote_auth_wizard":
        remote_name = normalize_remote_name(options.get("auth_remote_name", options.get("remote_name", "drive")))
        backend = normalize_auth_backend(options.get("auth_backend"))
        command.extend(["config", "create", remote_name, backend])
    elif mode in RCLONE_STORAGE_MODES:
        spec = endpoint_spec(options, "source").spec
        if mode == "storage_size":
            command.extend(["size", spec])
        elif mode == "storage_cleanup":
            command.extend(["cleanup", spec, "-v"])
        elif mode == "storage_dedupe":
            # list is the only mode that changes nothing; deleting duplicates is
            # a decision, and a decision is not made by a button labelled "find".
            command.extend(["dedupe", "list", spec])
        elif mode == "storage_link":
            command.extend(["link", spec])
        else:
            command.extend(["hashsum", str(options.get("hash_kind") or "md5"), spec])
    elif mode in RCLONE_CONFIG_MODES:
        action = {"config_encrypt": "set", "config_encryption_check": "check", "config_decrypt": "remove"}[mode]
        command.extend(["config", "encryption", action])
    elif mode == "remote_create_s3":
        remote_name = normalize_remote_name(options.get("auth_remote_name", options.get("remote_name", "r2")))
        provider = normalize_s3_provider(options.get("s3_provider"))
        endpoint = normalize_s3_endpoint(options.get("s3_endpoint"), provider=provider)
        region = str(options.get("s3_region") or RCLONE_S3_PROVIDERS[provider]["region"]).strip()
        # No key and no secret pass through here. The window points at the file on
        # this machine that already holds them and names the section inside it, so
        # the secret never enters the program, is never typed into a field that
        # could be screenshotted, and never lands in the project's rclone.conf —
        # what lands there is a reference to where the keys live.
        #
        # env_auth = true is what makes the credentials file work at all. rclone
        # documents shared_credentials_file and profile as part of the AWS SDK
        # chain, and that chain is only consulted when env_auth is true; with
        # false rclone looks for access_key_id in the config itself, finds
        # nothing, and signs the request with an empty key. R2 answers that with
        # `InvalidArgument: Authorization`, which reads like a bad key rather
        # than a missing one — measured against a live bucket.
        command.extend(["config", "create", remote_name, "s3", "provider", provider, "env_auth", "true"])
        # Cloudflare documents this for tokens with object-level permissions,
        # which is what a transfer needs: without it rclone probes the bucket
        # itself, and an Object Read & Write token is not allowed to.
        command.extend(["no_check_bucket", "true"])
        credentials_file = normalize_s3_credentials_file(options.get("s3_credentials_file"))
        if credentials_file:
            command.extend(["shared_credentials_file", credentials_file])
        command.extend(["profile", normalize_s3_profile(options.get("s3_profile"))])
        if endpoint:
            command.extend(["endpoint", endpoint])
        if region:
            command.extend(["region", region])
    elif mode == "remote_create_sftp":
        remote_name = normalize_remote_name(options.get("auth_remote_name", options.get("remote_name", "server")))
        host = normalize_server_host(options.get("sftp_host"))
        user = normalize_server_user(options.get("sftp_user"))
        port = normalize_server_port(options.get("sftp_port"))
        auth_method = normalize_sftp_auth_method(options.get("sftp_auth_method"))
        command.extend(["config", "create", remote_name, "sftp", "host", host, "user", user, "port", port])
        if auth_method == "agent":
            command.extend(["key_use_agent", "true"])
        elif auth_method == "password":
            command.extend(["pass", "[REDACTED]", "--no-obscure"])
        elif auth_method == "key_file":
            key_file = normalize_optional_file(options.get("sftp_key_file"))
            if not key_file:
                raise ValueError("SFTP key file is required.")
            command.extend(["key_file", portable_path(key_file, root)])
        known_hosts = require_sftp_known_hosts_file(options.get("sftp_known_hosts_file"))
        command.extend(["known_hosts_file", portable_path(known_hosts, root)])
        algorithms = known_host_key_algorithms(known_hosts, host)
        if algorithms:
            command.extend(["host_key_algorithms", " ".join(algorithms)])
    elif mode in RCLONE_ROUTE_MODES:
        src = endpoint_spec(options, "source")
        dst = endpoint_spec(options, "target")
        source_endpoint = src.spec
        target_endpoint = dst.spec
        if mode == "route_copy":
            if not preview and src.local_path is not None and not src.local_path.exists():
                raise RuntimeError(f"Source endpoint was not found: {src.local_path}")
            if not preview and dst.local_path is not None:
                dst.local_path.mkdir(parents=True, exist_ok=True)
            command.extend(["copy", src.spec, dst.spec])
            command.extend(transit_args(transit_kind(src, dst, remote_types(options))))
            command.extend(_profile_args(options.get("flag_profile"), options.get("bwlimit")))
        elif mode == "route_check":
            if not preview and src.local_path is not None and not src.local_path.exists():
                raise RuntimeError(f"Source endpoint was not found: {src.local_path}")
            report = rclone_report_path(logs_dir, mode, "combined", preview=preview)
            command.extend(["check", src.spec, dst.spec, "--one-way", "--combined", str(report)])
            command.extend(_profile_args(options.get("flag_profile"), options.get("bwlimit")))
        elif mode == "route_list_source":
            command.extend(["lsf", src.spec, "--max-depth", "1"])
        elif mode == "route_list_target":
            command.extend(["lsf", dst.spec, "--max-depth", "1"])
        elif mode == "route_mkdir_target":
            command.extend(["mkdir", dst.spec])
        elif mode == "route_about_target":
            command.extend(["about", dst.spec])
    else:
        remote = remote_spec(options.get("remote_name"), options.get("remote_path"))
        if mode == "about_remote":
            command.extend(["about", remote])
        elif mode == "list_remote_path":
            command.extend(["lsf", remote])
        elif mode == "mkdir_remote":
            command.extend(["mkdir", remote])
        elif mode == "remote_test":
            command.extend(["lsf", remote, "--max-depth", "1"])
        elif mode == "upload_copy_safe":
            source = _path_from_option(options, "source_path")
            if not preview and not source.exists():
                raise RuntimeError(f"Workbench Source was not found: {source}")
            command.extend(["copy", str(source), remote])
            command.extend(_profile_args(options.get("flag_profile"), options.get("bwlimit")))
        elif mode == "download_copy_safe":
            target = _path_from_option(options, "target_path")
            if not preview:
                target.mkdir(parents=True, exist_ok=True)
            command.extend(["copy", remote, str(target)])
            command.extend(_profile_args(options.get("flag_profile"), options.get("bwlimit")))
        elif mode == "check_one_way":
            source = _path_from_option(options, "source_path")
            if not preview and not source.exists():
                raise RuntimeError(f"Workbench Source was not found: {source}")
            report = rclone_report_path(logs_dir, mode, "combined", preview=preview)
            command.extend(["check", str(source), remote, "--one-way", "--combined", str(report)])
            command.extend(_profile_args(options.get("flag_profile"), options.get("bwlimit")))
        else:
            raise RuntimeError(f"Unsupported rclone mode: {mode}")

    return RcloneCommandSpec(
        mode=mode,
        title=rclone_mode_label(mode),
        command=command,
        log_file=log_file,
        remote_spec=remote,
        local_source=source,
        local_target=target,
        report_file=report,
        interactive=mode in RCLONE_INTERACTIVE_MODES,
        source_spec=source_endpoint,
        target_spec=target_endpoint,
        config_scope=config_scope,
        config_file=config_file,
        cache_dir=cache_dir,
    )


def command_display(command: list[str]) -> str:
    return subprocess.list2cmdline(command)


def redact_rclone_line(value: Any) -> str:
    text = str(value)
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(r"\1[REDACTED]", text)
    return text


def parse_rclone_progress_line(value: Any) -> dict[str, Any]:
    text = _ANSI_PATTERN.sub("", str(value or "")).replace("\r", "").strip()
    if not text:
        return {}

    result: dict[str, Any] = {}

    transferred = re.search(r"(?i)\bTransferred:\s*(.+)$", text)
    if transferred:
        body = transferred.group(1).strip()
        result["transferred"] = body
        percent = _PERCENT_PATTERN.search(body)
        if percent:
            try:
                result["percent"] = max(0.0, min(100.0, float(percent.group(1))))
            except ValueError:
                pass
        speed_eta = re.search(r",\s*([^,]+/s)\s*,\s*ETA\s+(.+)$", body, flags=re.IGNORECASE)
        if speed_eta:
            result["speed"] = speed_eta.group(1).strip()
            result["eta"] = speed_eta.group(2).strip()
        return result

    checks = re.search(r"(?i)\bChecks:\s*([0-9]+)\s*/\s*([0-9]+)(?:,\s*([0-9.]+)%)?", text)
    if checks:
        done = int(checks.group(1))
        total = int(checks.group(2))
        result["checks"] = f"{done}/{total}"
        if checks.group(3):
            try:
                result["check_percent"] = max(0.0, min(100.0, float(checks.group(3))))
            except ValueError:
                pass
        return result

    transferred_files = re.search(r"(?i)\bTransferred:\s*([0-9]+)\s*/\s*([0-9]+)(?:,\s*([0-9.]+)%)?", text)
    if transferred_files:
        done = int(transferred_files.group(1))
        total = int(transferred_files.group(2))
        result["files"] = f"{done}/{total}"
        if transferred_files.group(3):
            try:
                result["percent"] = max(0.0, min(100.0, float(transferred_files.group(3))))
            except ValueError:
                pass
        return result

    errors = re.search(r"(?i)\bErrors:\s*([0-9]+)", text)
    if errors:
        result["errors"] = int(errors.group(1))
        return result

    retries = re.search(r"(?i)\bRetries:\s*([0-9]+)", text)
    if retries:
        result["retries"] = int(retries.group(1))
        return result

    elapsed = re.search(r"(?i)\bElapsed time:\s*(.+)$", text)
    if elapsed:
        result["elapsed"] = elapsed.group(1).strip()
        return result

    file_percent = _PERCENT_PATTERN.search(text)
    if file_percent and text.lstrip().startswith("*"):
        try:
            result["file_percent"] = max(0.0, min(100.0, float(file_percent.group(1))))
        except ValueError:
            pass
    return result
