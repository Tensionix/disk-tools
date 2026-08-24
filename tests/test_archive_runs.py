"""Archiving is exercised for real, not only described.

The point of the mode is many folders at once: every item inside the source
becomes its own archive. The other tests in this project check which formats an
encryption mode allows; none of them ever created an archive, so nothing would
have noticed if the command stopped working.

Needs the project's bundled 7-Zip. The module skips itself where that is absent
so a stripped checkout still runs the rest of the suite.
"""

from __future__ import annotations

import filecmp
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from system_core.ui_nicegui import app as gui  # noqa: E402

SEVEN_ZIP = gui.find_7zip_executable()
pytestmark = pytest.mark.skipif(SEVEN_ZIP is None, reason="the bundled 7-Zip is not installed")

FOLDERS = ("Андреевское СП", "Богандинское СП", "Боровское СП")
PASSWORD = "секрет123"


@pytest.fixture
def source(tmp_path: Path) -> Path:
    """Several folders and a loose file, with Cyrillic names and nesting."""
    root = tmp_path / "src"
    for name in FOLDERS:
        folder = root / name
        (folder / "вложенная").mkdir(parents=True)
        (folder / "отчёт.txt").write_text(f"{name}: данные\n" * 40, encoding="utf-8")
        (folder / "вложенная" / "данные.csv").write_text("колонка,значение\n1,2\n", encoding="utf-8")
    (root / "одиночный.txt").write_text("файл в корне\n", encoding="utf-8")
    return root


def archive(source: Path, target: Path, **overrides) -> list[Path]:
    options = {
        "source_root": str(source),
        "target_root": str(target),
        "formats": ["7z"],
        "encryption": "none",
        "password": "",
        "level": "1",
        "layout": "flat",
        "name_prefix": "",
        "name_suffix": "",
        "sfx_env": "",
        "sfx_path": "{name}",
        "sfx_wrappers": [],
        "verify_after_create": True,
        "delete_source": False,
    }
    options.update(overrides)
    assert gui.archive_input_folders(options) == 0
    return sorted(path for path in target.rglob("*") if path.is_file())


def test_every_item_in_the_source_becomes_its_own_archive(source: Path, tmp_path: Path) -> None:
    made = archive(source, tmp_path / "out")

    assert len(made) == len(FOLDERS) + 1
    assert {path.stem for path in made} == {*FOLDERS, "одиночный"}


def test_two_formats_at_once_produce_two_archives_each(source: Path, tmp_path: Path) -> None:
    made = archive(source, tmp_path / "out", formats=["7z", "zip"])

    assert len(made) == (len(FOLDERS) + 1) * 2
    assert {path.suffix for path in made} == {".7z", ".zip"}


def test_the_name_parts_are_applied(source: Path, tmp_path: Path) -> None:
    made = archive(source, tmp_path / "out", name_prefix="АРХ_", name_suffix="_2026")

    assert all(path.stem.startswith("АРХ_") and path.stem.endswith("_2026") for path in made)


@pytest.mark.parametrize(
    ("label", "options", "password"),
    [
        ("plain", {}, None),
        ("password", {"encryption": "password", "password": PASSWORD}, PASSWORD),
        ("names", {"encryption": "names", "password": PASSWORD}, PASSWORD),
    ],
)
def test_what_goes_in_comes_back_out(
    source: Path, tmp_path: Path, label: str, options: dict, password: str | None
) -> None:
    """The round trip is the only check that says the archive is worth having."""
    made = archive(source, tmp_path / "out", **options)
    first = next(path for path in made if path.stem == FOLDERS[0])

    restored = tmp_path / "back" / label
    restored.mkdir(parents=True)
    subprocess.run(
        [str(SEVEN_ZIP), "x", str(first), f"-o{restored}", "-y", f"-p{password}" if password else "-p"],
        capture_output=True,
        check=True,
    )

    for relative in ("", "вложенная"):
        left = source / FOLDERS[0] / relative
        right = restored / FOLDERS[0] / relative
        comparison = filecmp.dircmp(str(left), str(right))
        assert not comparison.left_only, (relative, comparison.left_only)
        assert not comparison.right_only, (relative, comparison.right_only)
        assert not comparison.diff_files, (relative, comparison.diff_files)


def test_an_encrypted_archive_refuses_the_wrong_password(source: Path, tmp_path: Path) -> None:
    """Size alone proves nothing; only the wrong password does."""
    made = archive(source, tmp_path / "out", encryption="password", password=PASSWORD)

    probe = subprocess.run(
        [str(SEVEN_ZIP), "t", str(made[0]), "-pневерный"], capture_output=True
    )

    assert probe.returncode != 0


def test_encrypting_names_hides_them_from_the_listing(source: Path, tmp_path: Path) -> None:
    made = archive(source, tmp_path / "out", encryption="names", password=PASSWORD)

    listing = subprocess.run(
        [str(SEVEN_ZIP), "l", str(made[0]), "-p"], capture_output=True
    ).stdout

    assert "отчёт".encode("utf-8") not in listing
    assert "отчёт".encode("cp866") not in listing


def test_asking_to_encrypt_a_zip_refuses_rather_than_writing_a_plain_one(
    source: Path, tmp_path: Path
) -> None:
    """ZIP carries no encryption this project will use, so the run must stop.

    Writing an unencrypted ZIP instead would be worse than refusing: the archive
    would look done while the password was quietly dropped.
    """
    with pytest.raises(RuntimeError, match="at least one archive format"):
        archive(
            source,
            tmp_path / "out",
            formats=["zip"],
            encryption="password",
            password=PASSWORD,
        )
