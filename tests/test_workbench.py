from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from system_core.ui_nicegui.workbench import WorkbenchConfig, WorkbenchHistory  # noqa: E402


def make_history(tmp_path: Path) -> WorkbenchHistory:
    config = WorkbenchConfig(
        root=tmp_path,
        input_path=tmp_path / "input",
        output_path=tmp_path / "output",
        history_path=tmp_path / "config" / "path_history.json",
        history_limit=8,
    )
    return WorkbenchHistory(config)


def test_initial_history_contains_project_io(tmp_path: Path) -> None:
    history = make_history(tmp_path)
    history.ensure_initial()

    assert [entry["path"] for entry in history.entries("source")] == [str(tmp_path / "input")]
    assert [entry["path"] for entry in history.entries("target")] == [str(tmp_path / "output")]


def test_clear_cache_keeps_pins_only(tmp_path: Path) -> None:
    history = make_history(tmp_path)
    source = tmp_path / "external" / "source"
    target = tmp_path / "external" / "target"
    history.remember("source", str(source))
    history.remember("target", str(target))
    history.set_pinned("source", str(source), True, required_message="path required")

    result = history.clear_cache_keep_pins()

    assert result == {"removed_sources": 0, "removed_targets": 1, "kept_pins": 1}
    assert history.entries("source")[0]["path"] == str(source)
    assert history.entries("source")[0]["pinned"] is True
    assert history.entries("target") == []


def test_delete_history_returns_next_or_project_default(tmp_path: Path) -> None:
    history = make_history(tmp_path)
    first = tmp_path / "source-a"
    second = tmp_path / "source-b"
    history.remember("source", str(first))
    history.remember("source", str(second))

    result = history.delete("source", str(second), required_message="path required")
    assert result == {"removed": 1, "next_path": str(first)}

    result = history.delete("source", str(first), required_message="path required")
    assert result == {"removed": 1, "next_path": str(tmp_path / "input")}
