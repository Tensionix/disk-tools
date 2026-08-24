from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import load_yaml_or_json


SUPPORTED_LANGUAGES = {"en", "ru"}
DEFAULT_THEME = "code_dark"
THEME_ALIASES = {"dark": DEFAULT_THEME, "light": "code_light"}


@dataclass
class UiSettings:
    language: str = "ru"
    theme: str = DEFAULT_THEME
    emoji: bool = False
    allow_runtime_switching: bool = True
    advanced_open: bool = False
    workspace_source: str = ""
    workspace_target: str = ""


def _safe_language(value: Any) -> str:
    text = str(value or "ru").strip().lower()
    return text if text in SUPPORTED_LANGUAGES else "ru"


def _safe_theme(value: Any) -> str:
    text = str(value or DEFAULT_THEME).strip().lower()
    text = THEME_ALIASES.get(text, text)
    cleaned = "".join(char for char in text if char.isalnum() or char in {"_", "-"})
    return cleaned or DEFAULT_THEME


def load_ui_settings(path: Path) -> UiSettings:
    data = load_yaml_or_json(path) if path.exists() else {}
    ui_data = data.get("gui", data) if isinstance(data, dict) else {}
    if not isinstance(ui_data, dict):
        ui_data = {}
    return UiSettings(
        language=_safe_language(ui_data.get("language", "ru")),
        theme=_safe_theme(ui_data.get("theme", DEFAULT_THEME)),
        emoji=bool(ui_data.get("emoji", False)),
        allow_runtime_switching=bool(ui_data.get("allow_runtime_switching", True)),
        advanced_open=bool(ui_data.get("advanced_open", False)),
        workspace_source=str(ui_data.get("workspace_source") or "").strip(),
        workspace_target=str(ui_data.get("workspace_target") or "").strip(),
    )


def _yaml_value(value: Any) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _append_mapping(lines: list[str], title: str, values: Any) -> None:
    if not isinstance(values, dict) or not values:
        return
    lines.append("")
    lines.append(f"  {title}:")
    for key, value in values.items():
        lines.append(f"    {key}: {_yaml_value(value)}")


def save_ui_settings(path: Path, settings: UiSettings) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = load_yaml_or_json(path) if path.exists() else {}
    gui_data = existing.get("gui", existing) if isinstance(existing, dict) else {}
    if not isinstance(gui_data, dict):
        gui_data = {}

    lines = [
        "gui:",
        "  # Change to \"en\" for public GitHub builds.",
        "  # Theme ids are defined in config/ui_colors.yaml.",
        f"  language: \"{_safe_language(settings.language)}\"",
        f"  theme: \"{_safe_theme(settings.theme)}\"",
        f"  emoji: {str(bool(settings.emoji)).lower()}",
        f"  allow_runtime_switching: {str(bool(settings.allow_runtime_switching)).lower()}",
        f"  advanced_open: {str(bool(settings.advanced_open)).lower()}",
        f"  workspace_source: {_yaml_value(settings.workspace_source)}",
        f"  workspace_target: {_yaml_value(settings.workspace_target)}",
    ]
    _append_mapping(lines, "colors", gui_data.get("colors"))
    _append_mapping(lines, "fonts", gui_data.get("fonts"))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
