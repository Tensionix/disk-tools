"""The project folder as the whole tool, copyable to a disk and opened elsewhere.

rclone resolves a relative path against the working directory, which for this
project is its own root — checked against a live server rather than assumed. So a
key kept inside the project keeps working after the folder moves to another
machine with a different drive letter, and an absolute path does not.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from system_core.services.rclone_service import (  # noqa: E402
    build_rclone_command,
    import_ssh_material,
    portable_path,
)


def test_material_inside_the_project_is_written_relative(tmp_path: Path) -> None:
    inside = tmp_path / "config" / "ssh" / "server.key"
    inside.parent.mkdir(parents=True)
    inside.write_text("key", encoding="utf-8")

    assert portable_path(inside, tmp_path) == str(Path("config") / "ssh" / "server.key")


def test_material_outside_is_left_exactly_as_written(tmp_path: Path) -> None:
    """Not ours to rewrite, and it will not travel anyway."""
    outside = "E:/TOOLS/some_key_ed25519"

    assert portable_path(outside, tmp_path) == outside


@pytest.mark.parametrize("value", ["", "   ", None])
def test_nothing_is_invented_from_an_empty_path(value, tmp_path: Path) -> None:
    assert portable_path(value, tmp_path) == ""


def test_importing_copies_rather_than_moves(tmp_path: Path) -> None:
    """The original stays where the rest of the system expects it, and a project
    that turns out not to need the key can be emptied without hunting for the
    only copy."""
    origin = tmp_path / "elsewhere" / "id_ed25519"
    origin.parent.mkdir(parents=True)
    origin.write_text("secret", encoding="utf-8")
    project = tmp_path / "project"
    project.mkdir()

    landed = import_ssh_material(origin, project, "eden.key")

    assert landed == project / "config" / "ssh" / "eden.key"
    assert landed.read_text(encoding="utf-8") == "secret"
    assert origin.is_file(), "исходный ключ должен остаться на месте"


def test_importing_a_missing_file_says_so(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="не найден"):
        import_ssh_material(tmp_path / "nowhere", tmp_path, "x.key")


def test_two_servers_bringing_an_id_rsa_each_both_arrive(tmp_path: Path) -> None:
    """`id_rsa` is the most common key name there is, so this pair is ordinary.

    Overwriting the first would cost access to that server silently — the key is
    still named in the config, still found on disk, and no longer the right key.
    """
    project = tmp_path / "project"
    project.mkdir()
    first, second = tmp_path / "eden" / "id_rsa", tmp_path / "waicore" / "id_rsa"
    for key, body in ((first, "первый"), (second, "второй")):
        key.parent.mkdir(parents=True)
        key.write_text(body, encoding="utf-8")

    landed_first = import_ssh_material(first, project, "id_rsa")
    landed_second = import_ssh_material(second, project, "id_rsa")

    assert landed_first != landed_second
    assert landed_first.read_text(encoding="utf-8") == "первый"
    assert landed_second.read_text(encoding="utf-8") == "второй"


def test_the_same_key_imported_twice_does_not_pile_up_copies(tmp_path: Path) -> None:
    """Pressing the button again is not a request for a second key."""
    project = tmp_path / "project"
    project.mkdir()
    origin = tmp_path / "elsewhere" / "id_ed25519"
    origin.parent.mkdir(parents=True)
    origin.write_text("secret", encoding="utf-8")

    once = import_ssh_material(origin, project, "id_ed25519")
    twice = import_ssh_material(origin, project, "id_ed25519")

    assert once == twice
    assert sorted(p.name for p in (project / "config" / "ssh").iterdir()) == ["id_ed25519"]


def test_the_window_offers_the_import_rather_than_only_holding_it(tmp_path: Path) -> None:
    """It was built, tested and unreachable: no control in the window called it,
    so the config could travel and the key it points at could not."""
    import re

    source = (ROOT / "system_core" / "ui_nicegui" / "app.py").read_text(encoding="utf-8")
    body = re.search(r"def take_ssh_material_into_project.*?\n(?=\ndef )", source, re.S)

    assert body, "нет действия, которое кладёт ключ в проект"
    assert "import_ssh_material" in body.group(0)
    assert "portable_path" in body.group(0), "поле должно получить путь относительно проекта"
    assert source.count("take_ssh_material_into_project") >= 2, "объявлено, но ничем не вызывается"
    assert "on_click=lambda name=field: take_ssh_material_into_project(name)" in source, "кнопка не нажимается"
    for field in ("rclone_sftp_key_file", "rclone_sftp_known_hosts_file"):
        assert re.search(rf'render_ssh_material_field\(\s*"{field}"', source), f"{field} без кнопки"


def test_a_created_remote_carries_project_relative_paths(tmp_path: Path) -> None:
    key = tmp_path / "config" / "ssh" / "eden.key"
    hosts = tmp_path / "config" / "ssh" / "known_hosts"
    key.parent.mkdir(parents=True)
    key.write_text("key", encoding="utf-8")
    hosts.write_text("198.51.100.10 ssh-ed25519 AAAAExample\n", encoding="utf-8")

    spec = build_rclone_command(
        tmp_path,
        tmp_path / "logs",
        {
            "mode": "remote_create_sftp",
            "auth_remote_name": "eden",
            "sftp_host": "198.51.100.10",
            "sftp_user": "root",
            "sftp_port": "22",
            "sftp_auth_method": "key_file",
            "sftp_key_file": str(key),
            "sftp_known_hosts_file": str(hosts),
        },
        preview=True,
    )
    command = [str(part) for part in spec.command]

    assert command[command.index("key_file") + 1] == str(Path("config") / "ssh" / "eden.key")
    assert command[command.index("known_hosts_file") + 1] == str(Path("config") / "ssh" / "known_hosts")
    assert str(tmp_path) not in " ".join(command[command.index("key_file"):]), "абсолютный путь не переживёт переезд"


def test_a_key_taken_into_the_project_cannot_reach_the_repository() -> None:
    r"""The button that copies a key into `config\ssh` was added before the folder
    was protected: `config/rclone/*` was in .gitignore and the key folder was not,
    so an imported private key would have travelled to GitHub on the next publish.

    Проверяется закрытость папки, а не одна конкретная запись: `config/ssh/`
    закрывает её целиком и строже, чем `config/ssh/*`. Прежняя пара правил
    держала папку в репозитории пустым маркером `.gitkeep`; маркеры в проектах
    запрещены отдельно, и требовать их здесь — значит требовать нарушения.
    """
    rules = [line.strip() for line in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()]

    closed = {"config/ssh/", "config/ssh/*", "config/ssh"} & set(rules)
    assert closed, "приватный ключ уедет в репозиторий"

    allowed_back = [rule for rule in rules if rule.startswith("!config/ssh")]
    assert not allowed_back, "исключение возвращает содержимое папки ключей: %s" % allowed_back


def test_cleanup_does_not_reach_inside_config_at_all() -> None:
    r"""The banner has always said config is protected; the script did not agree.

    It deleted `config\rclone_endpoint_history.json` by name, and the sweep for
    generated files walks the whole project, so a stray `.bak` or `.tmp` beside a
    private key was fair game. Nothing under config is a build product: keys and
    rclone.conf travel with the project and cannot be regenerated, profiles and
    caches are the owner's own state.
    """
    script = (ROOT / "cleanup_project.cmd").read_text(encoding="utf-8", errors="replace")
    guard = script[script.index(":IS_PROTECTED_GENERATED_FILE") :]
    guard = guard[: guard.index("exit /b 1")]

    assert r"%BASE_DIR%\config" in guard, "чистка снова ходит внутрь config"
    assert "rclone_endpoint_history" not in script, "именованное удаление из config вернулось"
    assert r"REMOVE_FILE \"%BASE_DIR%\config" not in script, "из config снова удаляют по имени"
    assert r"REMOVE_DIR \"%BASE_DIR%\config" not in script, "из config снова удаляют папку"
