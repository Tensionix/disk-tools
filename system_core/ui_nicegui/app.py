from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any
import atexit
import argparse
import ctypes
import hashlib
import json
import logging
import os
import ipaddress
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from ctypes import wintypes

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nicegui import app as nicegui_app, core, run, ui  # type: ignore
from nicegui.element import Element as NiceGuiElement  # type: ignore

AUDION_CANONICAL_TOOLTIP_DELAY_MS = 1500
AUDION_CANONICAL_TOOLTIP_HIDE_DELAY_MS = 100
AUDION_CANONICAL_TOOLTIP_TRANSITION_MS = 100


def install_audion_canonical_tooltip_defaults() -> None:
    try:
        from nicegui.elements.tooltip import Tooltip as NiceGuiTooltip  # type: ignore
    except Exception:
        return
    if getattr(NiceGuiTooltip, "_audion_canonical_tooltip_defaults", False):
        return
    original_init = NiceGuiTooltip.__init__

    def audion_tooltip_init(self: Any, text: str = "") -> None:
        original_init(self, text)
        self.props["delay"] = AUDION_CANONICAL_TOOLTIP_DELAY_MS
        self.props["hide-delay"] = AUDION_CANONICAL_TOOLTIP_HIDE_DELAY_MS
        self.props["transition-duration"] = AUDION_CANONICAL_TOOLTIP_TRANSITION_MS
        self.classes("audion-tooltip")

    NiceGuiTooltip.__init__ = audion_tooltip_init  # type: ignore[method-assign]
    NiceGuiTooltip._audion_canonical_tooltip_defaults = True  # type: ignore[attr-defined]


install_audion_canonical_tooltip_defaults()


AUDION_CANONICAL_UI_CSS = """
<style id="audion-canonical-tooltip-icon-style">
  html body .q-tooltip,
  html body .audion-tooltip {
    background: rgb(23, 33, 43) !important;
    background-color: rgb(23, 33, 43) !important;
    color: #f4f8fb !important;
    border: 1px solid rgba(88, 166, 255, 0.24) !important;
    border-radius: 8px !important;
    box-shadow: 0 12px 28px rgba(0, 0, 0, 0.34) !important;
  }
  html body .q-icon.material-icons,
  html body .q-icon.material-symbols-outlined,
  html body .q-icon.material-symbols-rounded,
  html body i.material-icons,
  html body i.material-symbols-outlined,
  html body i.material-symbols-rounded,
  html body .q-btn .q-icon,
  html body .q-btn .material-icons,
  html body .q-btn .material-symbols-outlined,
  html body .q-btn .material-symbols-rounded,
  html body .q-field .q-field__append .q-icon,
  html body .q-field .q-field__prepend .q-icon,
  html body .q-item .q-icon,
  html body .q-menu .q-icon,
  html body .audion-label-icon,
  html body .audion-path-option-pin,
  html body .audion-select-option-pin {
    font-size: 14px !important;
    width: 14px !important;
    min-width: 14px !important;
    height: 14px !important;
    line-height: 14px !important;
  }
  html body .material-icons,
  html body .q-icon.material-icons {
    font-family: "Material Icons" !important;
  }
  html body .material-symbols-outlined,
  html body .q-icon.material-symbols-outlined {
    font-family: "Material Symbols Outlined" !important;
  }
  html body .material-symbols-rounded,
  html body .q-icon.material-symbols-rounded {
    font-family: "Material Symbols Rounded" !important;
  }
</style>
"""


def add_audion_canonical_ui_styles() -> None:
    ui.add_head_html(AUDION_CANONICAL_UI_CSS)



def audion_tooltip_path_text(path_value: Any) -> str:
    raw = str(path_value or "").strip()
    if not raw:
        return ""
    try:
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = ROOT / path
        return str(path)
    except Exception:
        return raw


def audion_folder_button_tooltip(folder_id: str, path_value: Any) -> str:
    key = str(folder_id or "folder").strip().lower()
    path_text = audion_tooltip_path_text(path_value)
    if getattr(settings, "language", "ru") == "ru":
        descriptions = {
            "logs": "папку логов запусков и вывода терминала",
            "report": "папку отчётов и результатов операций",
            "reports": "папку отчётов и результатов операций",
            "config": "папку конфигурации проекта: manifest, GUI-настройки и кэши",
            "state": "папку рабочего состояния GUI",
            "project": "корневую папку проекта",
            "root": "корневую папку проекта",
            "data": "папку данных проекта",
            "pipeline": "папку pipeline-артефактов и промежуточных результатов",
            "github": "папку GitHub-артефактов проекта",
            "install": "папку install/runtime-артефактов проекта",
        }
        description = descriptions.get(key, f"папку {folder_id}")
        return f"Открыть {description}: {path_text}" if path_text else f"Открыть {description}."
    descriptions = {
        "logs": "the logs folder with run and terminal output",
        "report": "the reports/results folder",
        "reports": "the reports/results folder",
        "config": "the project config folder with manifest, GUI settings, and caches",
        "state": "the GUI state folder",
        "project": "the project root folder",
        "root": "the project root folder",
        "data": "the project data folder",
        "pipeline": "the pipeline artifacts and intermediate results folder",
        "github": "the project GitHub artifacts folder",
        "install": "the project install/runtime artifacts folder",
    }
    description = descriptions.get(key, f"the {folder_id} folder")
    return f"Open {description}: {path_text}" if path_text else f"Open {description}."


def audion_terminal_action_tooltip(action: str) -> str:
    key = str(action or "").strip().lower()
    if getattr(settings, "language", "ru") == "ru":
        tips = {
            "clear_terminal_window": "Очистить только видимое окно терминала. Файлы логов, отчёты и результаты операций не удаляются.",
            "expand": "Открыть терминал в большом окне, чтобы читать длинный вывод без тесной панели.",
            "expand_log": "Открыть терминал в большом окне, чтобы читать длинный вывод без тесной панели.",
            "pin_command": "Закрепить текущую команду в истории терминала для быстрого повторного запуска.",
            "unpin_command": "Открепить текущую команду от верхней части истории терминала.",
            "clear_history": "Очистить историю команд терминала. Закреплённые команды и файлы логов не удаляются.",
            "terminal_shell": "Выбрать оболочку, в которой будут запускаться команды терминала.",
            "terminal_history": "Выбрать ранее сохранённую или закреплённую команду терминала.",
            "terminal_command": "Команда, которая будет выполнена из выбранной рабочей папки.",
            "terminal_cwd": "Рабочая папка терминала. Команда будет запущена именно отсюда.",
            "pick_folder": "Выбрать рабочую папку терминала через системный диалог.",
            "terminal_run": "Запустить введённую команду в выбранной оболочке и рабочей папке.",
            "latest_report": "Открыть последний созданный отчёт, если он уже есть.",
            "command_preview": "Показать команду, которая будет запущена с текущими параметрами, без выполнения операции.",
            "report_view": "Открыть встроенный список отчётов без перехода в проводник.",
            "close": "Закрыть большое окно терминала и вернуться к основной панели.",
        }
    else:
        tips = {
            "clear_terminal_window": "Clear only the visible terminal window. Log files, reports, and operation results are not deleted.",
            "expand": "Open the terminal in a large window for reading long output comfortably.",
            "expand_log": "Open the terminal in a large window for reading long output comfortably.",
            "pin_command": "Pin the current terminal command for quick reuse.",
            "unpin_command": "Remove the current command from the pinned command list.",
            "clear_history": "Clear terminal command history. Pinned commands and log files are not deleted.",
            "terminal_shell": "Choose the shell used to run terminal commands.",
            "terminal_history": "Pick a saved or pinned terminal command.",
            "terminal_command": "Command to run from the selected working folder.",
            "terminal_cwd": "Terminal working folder. Commands are started from here.",
            "pick_folder": "Choose the terminal working folder with the system dialog.",
            "terminal_run": "Run the entered command in the selected shell and working folder.",
            "latest_report": "Open the latest generated report, if one exists.",
            "command_preview": "Show the command that would run with the current settings, without executing it.",
            "report_view": "Open the built-in reports list without switching to the file explorer.",
            "close": "Close the large terminal window and return to the main panel.",
        }
    return tips.get(key, key.replace("_", " ").strip())


from system_core.core.config import load_yaml_or_json
from system_core.core.jobs import direct_python_command_args, execute_operation, gui_subprocess_output_kwargs, utf8_subprocess_env
from system_core.core.manifest import CommandNode, Operation, load_manifest
from system_core.core.paths import ensure_project_dirs, get_project_paths, open_folder
from system_core.core.terminal_render import iter_process_output_lines, terminal_html as _terminal_html, terminal_lines_html as _terminal_lines_html
from system_core.core.ui_settings import load_ui_settings, save_ui_settings
from system_core.auditor_core import (
    ANCHOR_FILE_NAME,
    build_filter_spec,
    build_filter_spec_from_pair,
    build_preflight_card,
    load_pairs,
    load_presets,
    normalize_operation_policy,
    scan_dir,
    should_include_file,
)
from system_core.ui_nicegui.workbench import (
    WORKBENCH_FEEDBACK_CSS,
    WORKBENCH_LAYOUT_CSS,
    WORKBENCH_OVERRIDE_CSS,
    WorkbenchAdapter,
    WorkbenchConfig,
    WorkbenchHandlers,
    WorkbenchRenderer,
    WorkbenchRole,
    canonical_role,
)
from system_core.services.rclone_service import (
    RCLONE_AUTH_BACKENDS,
    RCLONE_S3_PROVIDERS,
    RCLONE_AUTH_MODES,
    RCLONE_CONFIG_SCOPES,
    RCLONE_DEFAULT_CONFIG_SCOPE,
    RCLONE_ENDPOINT_KINDS,
    RCLONE_DEFAULT_PROFILE,
    RCLONE_FLAG_PROFILES,
    RCLONE_OPERATION_MODES,
    RCLONE_REMOTE_MODES,
    RCLONE_ROUTE_MODES,
    RCLONE_SFTP_AUTH_METHODS,
    RCLONE_SOURCE_MODES,
    RCLONE_TARGET_MODES,
    RCLONE_TRANSFER_MODES,
    build_rclone_command,
    command_display,
    endpoint_spec,
    expected_rclone_executable,
    find_rclone_executable,
    route_objection,
    transit_kind,
    transit_sentence,
    remote_types,
    config_is_encrypted,
    config_passphrase_env,
    s3_credentials_env,
    RcloneEndpointSpec,
    import_ssh_material,
    parse_config_dump,
    portable_path,
    normalize_auth_backend,
    normalize_s3_profile,
    normalize_s3_provider,
    normalize_config_scope,
    normalize_flag_profile,
    normalize_log_level,
    normalize_rclone_mode,
    normalize_optional_file,
    normalize_remote_name,
    normalize_remote_path,
    normalize_server_host,
    normalize_server_port,
    normalize_server_user,
    normalize_sftp_auth_method,
    parse_listremotes_output,
    parse_rclone_progress_line,
    remote_name_in,
    portable_rclone_cache_dir,
    portable_rclone_config_path,
    rclone_cache_dir_for_scope,
    rclone_config_file_for_scope,
    rclone_global_config_args,
    redact_rclone_line,
    require_sftp_known_hosts_file,
    rclone_log_path,
    rclone_mode_label,
    secure_rclone_config_permissions,
    system_rclone_config_path,
)
from system_core.services.transfer_service import (
    ENGINE_RCLONE,
    OPERATION_AUDITOR_COMMAND,
    OPERATION_MIRROR,
    fan_out_commands,
    run_succeeded,
    OPERATION_RCLONE_COMMAND,
    PACK_BEFORE,
    PACK_MODES,
    PACK_NONE,
    TRANSFER_OPERATIONS,
    pack_staging_dir,
    robocopy_time_args,
    transfer_plan,
)

paths = get_project_paths(ROOT)
ensure_project_dirs(paths)
manifest = load_manifest(paths.config / "tool_manifest.yaml")
settings_path = paths.config / "gui_settings.yaml"
settings = load_ui_settings(settings_path)

def _clear_portable_workspace_settings() -> None:
    for attr in ("source_path", "destination_path", "workspace_source", "workspace_target"):
        if hasattr(settings, attr):
            setattr(settings, attr, "")


_clear_portable_workspace_settings()


def display_path(path_value: Any) -> str:
    text = str(path_value or "").strip()
    if not text:
        return ""
    path = Path(text).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    try:
        resolved = path.resolve()
        relative = resolved.relative_to(ROOT)
    except (OSError, ValueError):
        return str(path)
    return str(relative) or "."



def configure_tooltip_timing() -> None:
    if getattr(NiceGuiElement, "_audion_tooltip_timing_patched", False):
        return

    def audion_tooltip(self: NiceGuiElement, text: str) -> NiceGuiElement:
        from nicegui.elements.tooltip import Tooltip  # type: ignore

        self.props["aria-label"] = text
        tooltip = Tooltip(text)
        tooltip.props["target"] = f"#{self.html_id}"
        tooltip.props["delay"] = 1500
        tooltip.props["hide-delay"] = 100
        tooltip.props["transition-duration"] = 100
        return self

    NiceGuiElement.tooltip = audion_tooltip  # type: ignore[method-assign]
    NiceGuiElement._audion_tooltip_timing_patched = True  # type: ignore[attr-defined]


configure_tooltip_timing()


def terminal_lines_html(lines, leading_newline: bool = False) -> str:
    return _terminal_lines_html(lines, leading_newline=False).replace("\n", "")


def terminal_html(lines) -> str:
    return _terminal_html(lines).replace("\n", "")
tool_info: dict[str, Any] = manifest.raw.get("tool", {})
ui_info: dict[str, Any] = manifest.raw.get("ui", {})

DEFAULT_THEME_ID = "code_dark"
THEME_ALIASES = {"dark": "code_dark", "light": "code_light"}


def _string_map(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key).strip(): str(item).strip() for key, item in value.items() if str(key).strip()}


def load_ui_colors(path: Path) -> dict[str, Any]:
    data = load_yaml_or_json(path) if path.exists() else {}
    if not isinstance(data, dict):
        data = {}

    themes: dict[str, dict[str, Any]] = {}
    themes_raw = data.get("themes", {})
    if not isinstance(themes_raw, dict):
        themes_raw = {}
    for theme_id, theme_data in themes_raw.items():
        if not isinstance(theme_data, dict):
            continue
        normalized_id = str(theme_id).strip().lower()
        if not normalized_id:
            continue
        themes[normalized_id] = {
            "label": str(theme_data.get("label") or normalized_id).strip(),
            "label_ru": str(theme_data.get("label_ru") or theme_data.get("label") or normalized_id).strip(),
            "mode": "dark" if str(theme_data.get("mode", "dark")).lower() == "dark" else "light",
            "tokens": _string_map(theme_data.get("tokens", {})),
        }

    if DEFAULT_THEME_ID not in themes:
        themes[DEFAULT_THEME_ID] = {
            "label": "Code Dark",
            "label_ru": "Code Темная",
            "mode": "dark",
            "tokens": {
                "color-background-primary": "#141413",
                "color-background-secondary": "#1f1e1a",
                "color-background-tertiary": "#0f0f0e",
                "color-text-primary": "#faf9f5",
                "color-text-secondary": "#e8e6dc",
                "color-text-tertiary": "#b0aea5",
                "color-border-tertiary": "rgba(250, 249, 245, 0.15)",
                "color-border-secondary": "rgba(250, 249, 245, 0.3)",
                "color-border-primary": "rgba(250, 249, 245, 0.4)",
                "color-accent-primary": "#d97757",
                "color-accent-secondary": "#6a9bcc",
                "color-accent-tertiary": "#788c5d",
            },
        }

    return {
        "ramps": data.get("ramps", {}) if isinstance(data.get("ramps", {}), dict) else {},
        "tokens": _string_map(data.get("tokens", {})),
        "themes": themes,
    }


ui_colors = load_ui_colors(paths.config / "ui_colors.yaml")


def tolerate_missing_process_pool() -> None:
    """Keep the GUI usable if a portable Windows environment blocks multiprocessing."""
    try:
        import nicegui.run as nicegui_run  # type: ignore
    except Exception:
        return

    original_setup = getattr(nicegui_run, "setup", None)
    if not callable(original_setup):
        return

    def safe_setup() -> None:
        try:
            original_setup()
        except (OSError, PermissionError) as exc:
            logging.warning("NiceGUI process pool disabled: %s", exc)
            nicegui_run.process_pool = None

    nicegui_run.setup = safe_setup


tolerate_missing_process_pool()

LABELS = {
    "ru": {
        "workspace": "Рабочие папки",
        "operations": "Операции",
        "maintenance": "Обслуживание",
        "status": "Статус",
        "log": "Журнал операции",
        "idle": "Ожидание",
        "running": "Выполняется",
        "done": "Готово",
        "error": "Ошибка",
        "cancel": "Отменить",
        "another_running": "Другая операция уже выполняется.",
        "confirm_title": "Подтвердите действие",
        "confirm_note": "Действие может изменить управляемую рабочую область.",
        "run": "Запустить",
        "back": "Назад",
        "selected_operation": "Выбрана команда",
        "open_menu": "Открыть",
        "parameters": "Параметры",
        "section_paths": "Пути",
        "section_filters": "Фильтры",
        "section_extensions": "Расширения",
        "section_options": "Опции",
        "extension_quick_groups": "Быстрые наборы",
        "extension_family_documents": "Документы и текст",
        "extension_family_development": "Разработка и конфиги",
        "extension_family_apps": "Приложения и Windows",
        "extension_family_archives": "Архивы",
        "extension_family_audio": "Аудио",
        "extension_family_video": "Видео",
        "extension_family_graphics": "Картинки",
        "extension_family_other": "Прочее",
        "extension_select_all": "Все",
        "extension_select_none": "Снять",
        "advanced": "Дополнительно",
        "actions": "Действия",
        "close": "Закрыть",
        "logs": "Логи",
        "report": "Отчёты",
        "latest_report": "Последний",
        "latest_report_missing": "Отчётов пока нет.",
        "latest_report_opened": "Открыт последний отчёт.",
        "config": "Настройки",
        "expand": "Развернуть",
        "clear_terminal_window": "Очистить окно терминала",
        "add_file_short": "Добавить файл...",
        "add_files": "Добавить файлы...",
        "add_folder": "Добавить папку...",
        "file_list": "File List",
        "file_list_button": "Список",
        "file_list_empty": "В источнике нет файлов.",
        "file_list_missing": "Источник не найден: {path}",
        "file_list_ready": "File list generated: {count}.",
        "workspace_routes": "Действия",
        "workspace_staging": "Staging",
        "source_folder": "Источник",
        "target_folder": "Назначение",
        "choose_source": "Источник...",
        "choose_target": "Цель...",
        "source_selected": "Источник выбран.",
        "target_selected": "Назначение выбрано.",
        "source_folder_missing": "Источник не найден: {path}",
        "clear_io_short": "Сбросить",
        "delete_io_short": "Удалить",
        "terminal_file": "File",
        "stage_files": "Добавление файлов в input",
        "stage_folder": "Добавление папки в input",
        "picker_cancelled": "Выбор отменен.",
        "path_history": "История путей",
        "workspace_folders": "Папки",
        "workspace_import": "INPUT",
        "import_paths": "Импорт путей",
        "export_paths": "Экспорт путей",
        "path_history_empty": "История путей пуста.",
        "path_history_imported": "История путей импортирована.",
        "path_history_exported": "История путей экспортирована.",
        "profile_bundle": "Архив профилей",
        "profile_bundle_desc": "Импорт/экспорт конфигурации сохранённых профилей.",
        "pin_path": "Закр.",
        "unpin_path": "Откр.",
        "pick_folder": "Выбрать",
        "path_required": "Выберите путь.",
        "path_pinned": "Путь закреплен.",
        "path_unpinned": "Закрепление снято.",
        "operation_done": "Операция завершена.",
        "operation_failed": "Операция завершилась с кодом {code}.",
        "guard_delete_ratio_title": "Обнаружено массовое удаление",
        "guard_delete_ratio_body": "Будет безвозвратно удалено {n} из {m} файлов цели ({p}%). Продолжить?",
        "guard_filtered_hard_title": "Жёсткое зеркало с фильтром",
        "guard_filtered_hard_body": "Из цели будут удалены только файлы, попавшие под фильтр. Так редко задумывают. Продолжить?",
        "select_required": "Выберите хотя бы один пункт: {field}",
        "theme": "Тема",
        "theme_saved": "Тема сохранена. Перезагружаю интерфейс.",
        "resize_panels": "Изменить ширину панелей",
        "terminal_shell": "Shell",
        "terminal_history": "История команд",
        "terminal_history_empty": "Нет сохранённых команд",
        "terminal_command": "Команда",
        "terminal_cwd": "Рабочая папка",
        "terminal_run": "ВЫПОЛНИТЬ",
        "terminal_clear": "Очистить",
        "pin_command": "Pin",
        "unpin_command": "Unpin",
        "clear_history": "Очистить",
        "clear_command_cache": "Кэш",
        "history_cleared": "История команд очищена; закреплённые команды сохранены.",
        "command_cache_cleared": "Кэш команд очищен.",
        "terminal_command_required": "Введите команду.",
        "terminal_command_done": "Команда завершена.",
        "terminal_sensitive_not_saved": "Команда похожа на содержащую секреты и не сохранена в историю.",
        "terminal_sensitive_not_pinned": "Команда похожа на содержащую секреты и не закреплена.",
        "lang_switch": "EN",
    },
    "en": {
        "workspace": "Workspace folders",
        "operations": "Operations",
        "maintenance": "Maintenance",
        "status": "Status",
        "log": "Operation log",
        "idle": "Idle",
        "running": "Running",
        "done": "Done",
        "error": "Error",
        "cancel": "Cancel",
        "another_running": "Another operation is already running.",
        "confirm_title": "Confirm action",
        "confirm_note": "This action may change the managed workspace.",
        "run": "Run",
        "back": "Back",
        "selected_operation": "Selected command",
        "open_menu": "Open",
        "parameters": "Parameters",
        "section_paths": "Paths",
        "section_filters": "Filters",
        "section_extensions": "Extensions",
        "section_options": "Options",
        "extension_quick_groups": "Quick sets",
        "extension_family_documents": "Documents and text",
        "extension_family_development": "Development and config",
        "extension_family_apps": "Apps and Windows",
        "extension_family_archives": "Archives",
        "extension_family_audio": "Audio",
        "extension_family_video": "Video",
        "extension_family_graphics": "Images",
        "extension_family_other": "Other",
        "extension_select_all": "All",
        "extension_select_none": "None",
        "advanced": "Advanced",
        "actions": "Actions",
        "close": "Close",
        "logs": "Logs",
        "report": "Report",
        "latest_report": "Latest report",
        "latest_report_missing": "No reports yet.",
        "latest_report_opened": "Latest report opened.",
        "config": "CONFIG",
        "expand": "Expand",
        "add_file_short": "Add file...",
        "add_files": "Add files...",
        "add_folder": "Add folder...",
        "file_list": "File List",
        "file_list_button": "List",
        "file_list_empty": "Source has no files.",
        "file_list_missing": "Source was not found: {path}",
        "file_list_ready": "File list generated: {count}.",
        "workspace_routes": "Actions",
        "workspace_staging": "Staging",
        "source_folder": "Source",
        "target_folder": "Target",
        "choose_source": "Source...",
        "choose_target": "Target...",
        "source_selected": "Source selected.",
        "target_selected": "Target selected.",
        "source_folder_missing": "Source was not found: {path}",
        "clear_io_short": "Reset",
        "delete_io_short": "Delete",
        "terminal_file": "File",
        "stage_files": "Adding files to input",
        "stage_folder": "Adding folder to input",
        "picker_cancelled": "Selection cancelled.",
        "path_history": "Path history",
        "workspace_folders": "Folders",
        "workspace_import": "INPUT",
        "import_paths": "Import paths",
        "export_paths": "Export paths",
        "path_history_empty": "Path history is empty.",
        "path_history_imported": "Path history imported.",
        "path_history_exported": "Path history exported.",
        "profile_bundle": "Profile archive",
        "profile_bundle_desc": "Import/export saved profile configuration.",
        "pin_path": "Pin",
        "unpin_path": "Unpin",
        "pick_folder": "Pick",
        "path_required": "Choose a path.",
        "path_pinned": "Path pinned.",
        "path_unpinned": "Path unpinned.",
        "operation_done": "Operation finished.",
        "operation_failed": "Operation finished with exit code {code}.",
        "guard_delete_ratio_title": "Large deletion detected",
        "guard_delete_ratio_body": "{n} of {m} target files ({p}%) will be permanently deleted. Continue?",
        "guard_filtered_hard_title": "Filtered hard mirror",
        "guard_filtered_hard_body": "Only files matching the filter will be deleted from the target. This is rarely intended. Continue?",
        "select_required": "Select at least one item: {field}",
        "theme": "Theme",
        "theme_saved": "Theme saved. Reloading UI.",
        "resize_panels": "Resize panels",
        "clear_terminal_window": "Clear terminal window",
        "terminal_shell": "Shell",
        "terminal_history": "Command history",
        "terminal_history_empty": "No saved commands",
        "terminal_command": "Command",
        "terminal_cwd": "Working folder",
        "terminal_run": "RUN",
        "terminal_clear": "Clear",
        "pin_command": "Pin",
        "unpin_command": "Unpin",
        "clear_history": "History",
        "clear_command_cache": "Cache",
        "history_cleared": "Command history cleared; pinned commands were kept.",
        "command_cache_cleared": "Command cache cleared.",
        "terminal_command_required": "Enter a command.",
        "terminal_command_done": "Command finished.",
        "terminal_sensitive_not_saved": "Command looks sensitive and was not saved to history.",
        "terminal_sensitive_not_pinned": "Command looks sensitive and was not pinned.",
        "lang_switch": "RU",
    },
}

PICKER_BOOTSTRAP = r"""
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
try {
  Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class AudionDpiAwareness {
  [DllImport("user32.dll")]
  public static extern bool SetProcessDpiAwarenessContext(IntPtr dpiContext);
  [DllImport("shcore.dll")]
  public static extern int SetProcessDpiAwareness(int value);
}
"@
  try { [AudionDpiAwareness]::SetProcessDpiAwarenessContext([IntPtr](-4)) | Out-Null }
  catch { [AudionDpiAwareness]::SetProcessDpiAwareness(2) | Out-Null }
} catch {}
Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.Application]::EnableVisualStyles()
"""

TERMINAL_COMMAND_HISTORY_PATH = paths.config / "terminal_commands.json"
TERMINAL_COMMAND_HISTORY_LIMIT = 200
# Terminal-bar prelude. Redirected stdout makes PowerShell fall back to the OEM code page
# and drop ANSI colour, so both are pinned explicitly before the user's command runs.
POWERSHELL_UTF8_PREAMBLE = (
    "$audionUtf8 = [System.Text.UTF8Encoding]::new($false); "
    "[Console]::InputEncoding = $audionUtf8; "
    "[Console]::OutputEncoding = $audionUtf8; "
    "$OutputEncoding = $audionUtf8; "
    "if (Get-Variable PSStyle -ErrorAction SilentlyContinue) { $PSStyle.OutputRendering = 'ANSI' }; "
)
TERMINAL_SENSITIVE_RE = re.compile(
    r"(?i)(authorization\s*:|bearer\s+\S+|access[_-]?token|refresh[_-]?token|client[_-]?secret|api[_-]?key|password|passwd|secret|token|(^|\s)-p(?:\S|$))"
)


def terminal_command_is_sensitive(command: Any) -> bool:
    return bool(TERMINAL_SENSITIVE_RE.search(str(command or "")))


def redact_terminal_command_for_log(command: Any) -> str:
    text = str(command or "")
    text = re.sub(r"(?i)(authorization\s*:\s*bearer\s+)[^\s\"']+", r"\1[REDACTED]", text)
    text = re.sub(r"(?i)(bearer\s+)[^\s\"']+", r"\1[REDACTED]", text)
    text = re.sub(
        r"(?i)(--?(?:access[_-]?token|refresh[_-]?token|client[_-]?secret|api[_-]?key|password|passwd|secret|token)(?:=|\s+))\S+",
        r"\1[REDACTED]",
        text,
    )
    text = re.sub(r"(?i)(^|\s)-p\S+", r"\1-p[REDACTED]", text)
    return text


def clean_terminal_commands(items: Any) -> list[str]:
    result: list[str] = []
    if not isinstance(items, list):
        return result
    for item in items:
        text = str(item).strip()
        if terminal_command_is_sensitive(text):
            continue
        if text and text not in result:
            result.append(text)
    return result[:TERMINAL_COMMAND_HISTORY_LIMIT]


def resolved_terminal_cwd(value: Any) -> str:
    """Absolute terminal CWD, falling back to the project root.

    The project is portable, so a cached folder can outlive the copy that produced it.
    A relative value is read against the current ROOT, and anything that is no longer a
    directory resets to the start state instead of lingering in the CWD field.
    """
    text = str(value or "").strip()
    if not text:
        return str(ROOT)
    candidate = Path(os.path.expandvars(text)).expanduser()
    if not candidate.is_absolute():
        candidate = ROOT / candidate
    try:
        candidate = candidate.resolve()
    except OSError:
        return str(ROOT)
    return str(candidate) if candidate.is_dir() else str(ROOT)


def stored_terminal_cwd(value: Any) -> str:
    """Terminal CWD as written to disk: project-local folders stay relative to ROOT."""
    resolved = Path(resolved_terminal_cwd(value))
    try:
        return str(resolved.relative_to(Path(ROOT).resolve()))
    except ValueError:
        return str(resolved)


def load_terminal_cache() -> dict[str, Any]:
    default = {
        "history": [],
        "pinned": [],
        "last": "",
        "shell": "powershell",
        "cwd": str(ROOT),
    }
    if not TERMINAL_COMMAND_HISTORY_PATH.exists():
        return default
    try:
        raw = json.loads(TERMINAL_COMMAND_HISTORY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logging.warning("Could not load terminal command history: %s", exc)
        return default
    if not isinstance(raw, dict):
        return default
    shell = str(raw.get("shell") or default["shell"]).strip().lower()
    if shell not in {"pwsh", "powershell", "cmd"}:
        shell = "powershell"
    cwd = resolved_terminal_cwd(raw.get("cwd"))
    return {
        "history": clean_terminal_commands(raw.get("history", [])),
        "pinned": clean_terminal_commands(raw.get("pinned", [])),
        "last": str(raw.get("last") or "").strip(),
        "shell": shell,
        "cwd": cwd,
    }


initial_terminal_cache = load_terminal_cache()

state: dict[str, Any] = {
    "running": False,
    "cancel": False,
    "progress": 0.0,
    "status": "",
    "lines": [],
    "log_version": 0,
    "terminal_epoch": 0,
    "terminal_scroll_top_seq": 0,
    "terminal_total_lines": 0,
    "exit_code": None,
    "command_path": [],
    "pending_command": None,
    "last_plan": None,
    "rclone_remotes": None,
    "field_values": {},
    "field_widgets": {},
    "extension_info_contexts": {},
    "terminal_cache": initial_terminal_cache,
    "terminal_shell": str(initial_terminal_cache.get("shell") or "powershell"),
    "terminal_command": "",
    "terminal_command_version": 0,
    "terminal_cwd": str(initial_terminal_cache.get("cwd") or ROOT),
    "terminal_cwd_version": 0,
    "workspace_source_path": str(paths.input),
    "workspace_target_path": str(paths.output),
    "workspace_feedback": {},
    "rclone_progress": {},
}

PATH_HISTORY_LIMIT = 100
TERMINAL_HISTORY_LIMIT = 2000
MASK_CACHE_PATH = paths.config / "mask_cache.json"
MASK_CACHE_LIMIT = 200
RCLONE_COMMAND_CACHE_PATH = paths.config / "rclone_command_cache.json"
RCLONE_COMMAND_CACHE_LIMIT = 120
RCLONE_ENDPOINT_HISTORY_PATH = paths.config / "rclone_endpoint_history.json"
RCLONE_ENDPOINT_HISTORY_LIMIT = 80
RCLONE_BWLIMIT_MB_PRESETS = [
    *range(1, 10),
    *range(10, 100, 10),
    100,
    150,
    200,
    300,
    500,
    900,
]
PROFILE_EXTENSION_PINS_PATH = paths.config / "profile_extension_pins.json"
REPORT_EXTENSIONS = {".txt", ".md", ".html", ".htm", ".json"}
REPORT_EXTENSION_SCORE = {".txt": 5, ".md": 4, ".html": 3, ".htm": 3, ".json": 2}
ARCHIVE_FORMATS: dict[str, dict[str, str]] = {
    "zip": {"label": "ZIP", "type": "zip", "ext": ".zip", "mode": "direct"},
    "7z": {"label": "7Z", "type": "7z", "ext": ".7z", "mode": "direct"},
    "sfx": {"label": "SFX", "type": "7z", "ext": ".exe", "mode": "sfx"},
    "lz4": {"label": "TAR.LZ4", "type": "lz4", "ext": ".tar.lz4", "mode": "tar_compress"},
    "tar": {"label": "TAR", "type": "tar", "ext": ".tar", "mode": "direct_tar"},
    "gz": {"label": "TAR.GZ", "type": "gzip", "ext": ".tar.gz", "mode": "tar_compress"},
    "zstd": {"label": "TAR.ZSTD", "type": "zstd", "ext": ".tar.zst", "mode": "tar_compress"},
}
# Multi-dot suffixes this tool emits. Checked longest-first so that ".tar.gz" wins
# over ".gz"; anything not listed here keeps a single Path.suffix.
ARCHIVE_COMPOUND_EXTENSIONS: tuple[str, ...] = (
    ".sha256.txt",
    ".tar.zstd",
    ".tar.lz4",
    ".tar.zst",
    ".tar.bz2",
    ".tar.gz",
    ".tar.xz",
)
SFX_WRAPPER_FORMATS: dict[str, dict[str, str]] = {
    "zip": {"label": "ZIP", "type": "zip", "ext": ".zip"},
    "7z": {"label": "7Z", "type": "7z", "ext": ".7z"},
    "zstd": {"label": "ZSTD", "type": "zstd", "ext": ".zst"},
    "tar": {"label": "TAR", "type": "tar", "ext": ".tar"},
    "gz": {"label": "GZ", "type": "gzip", "ext": ".gz"},
}
SFX_ENV_NONE = "__none__"
SFX_ENV_OPTIONS = {
    SFX_ENV_NONE: "",
    "%LOCALDATA%": "LOCALDATA",
    "%USERDATA%": "USERDATA",
    "%USERPROFILE%": "USERPROFILE",
    "%PROGRAMDATA%": "PROGRAMDATA",
    "%PROGRAMFILES%": "PROGRAMFILES 64",
    "%PROGRAMFILES_X86%": "PROGRAMFILES x86",
    "%COMMONPROGRAMFILES%": "COMMONFILES 64",
    "%COMMONPROGRAMFILES_X86%": "COMMONFILES x86",
    "%PUBLIC%": "PUBLIC",
    "%SYSTEMDRIVE%": "SYSTEMDRIVE",
    "%TEMP%": "TEMP",
    "%DOCUMENTS%": "DOCUMENTS",
    "%DOWNLOADS%": "DOWNLOADS",
    "%DESKTOP%": "DESKTOP",
}
SFX_INSTALL_ENV_PATHS = {
    "": "",
    "%LOCALDATA%": "%LOCALAPPDATA%",
    "%USERDATA%": "%APPDATA%",
    "%USERPROFILE%": "%USERPROFILE%",
    "%PROGRAMDATA%": "%PROGRAMDATA%",
    "%PROGRAMFILES%": "%ProgramFiles%",
    "%PROGRAMFILES_X86%": "%ProgramFiles(x86)%",
    "%COMMONPROGRAMFILES%": "%CommonProgramFiles%",
    "%COMMONPROGRAMFILES_X86%": "%CommonProgramFiles(x86)%",
    "%PUBLIC%": "%PUBLIC%",
    "%SYSTEMDRIVE%": "%SYSTEMDRIVE%",
    "%TEMP%": "%TEMP%",
    "%DOCUMENTS%": "%USERPROFILE%\\Documents",
    "%DOWNLOADS%": "%USERPROFILE%\\Downloads",
    "%DESKTOP%": "%USERPROFILE%\\Desktop",
}
ARCHIVE_LEVEL_OPTIONS = {
    "0": "0",
    "1": "1",
    "3": "3",
    "5": "5",
    "7": "7",
    "9": "9",
}
ARCHIVE_ENCRYPTION_OPTIONS = {
    "none": {"label": "No encryption", "label_ru": "Не шифровать"},
    "password": {"label": "Encrypt", "label_ru": "Зашифровать"},
    "names": {"label": "Encrypt names", "label_ru": "Зашифровать с именами"},
}
# ZIP is deliberately absent: 7-Zip encrypts ZIP with ZipCrypto, the broken PKZIP
# cipher, and the AES-256 alternative produces archives Windows Explorer cannot
# open. ZIP stays the format everyone can read; encryption belongs to 7Z and SFX,
# which use AES-256 already.
ARCHIVE_ENCRYPTION_ALGORITHM = "AES-256"
ARCHIVE_PASSWORD_FORMATS = {"7z", "sfx"}
ARCHIVE_NAME_ENCRYPTION_FORMATS = {"7z", "sfx"}
SFX_WRAPPER_LEVEL = "0"
ARCHIVE_NAME_INVALID_CHARS = '<>:"/\\|?*'
archive_state: dict[str, Any] = {
    "formats": ["zip"],
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
    "underscore_spaces": False,
    "delete_source": False,
}
NETWORK_OPERATION_MODES: dict[str, dict[str, str]] = {
    "robocopy_safe": {
        "label": "Copy over Ethernet - Safe",
        "label_ru": "Копировать по сети - безопасно",
        "description": "Robocopy /Z with conservative retries.",
        "description_ru": "Robocopy /Z с мягкими повторами.",
    },
    "robocopy_fast": {
        "label": "Copy over Ethernet - Fast",
        "label_ru": "Копировать по сети - быстро",
        "description": "Robocopy without restartable mode for stable LAN.",
        "description_ru": "Robocopy без /Z для стабильной LAN.",
    },
    "robocopy_large": {
        "label": "Copy Large Files - Unbuffered",
        "label_ru": "Крупные файлы - unbuffered",
        "description": "Robocopy /J for video, ISO and other large files.",
        "description_ru": "Robocopy /J для видео, ISO и других крупных файлов.",
    },
    "robocopy_update": {
        "label": "Update Existing - No Delete",
        "label_ru": "Обновить без удаления",
        "description": "Robocopy /XO keeps destination-only files.",
        "description_ru": "Robocopy /XO оставляет лишнее в цели.",
    },
    "robocopy_mirror": {
        "label": "Mirror - Destructive",
        "label_ru": "Зеркало - удаляет лишнее",
        "description": "Robocopy /MIR deletes destination-only files.",
        "description_ru": "Robocopy /MIR удаляет лишнее в цели.",
    },
    "robocopy_scan": {
        "label": "Scan Only - Compare",
        "label_ru": "Только сканирование",
        "description": "Robocopy /L compares without copying.",
        "description_ru": "Robocopy /L сравнивает без копирования.",
    },
    "pack_stage": {
        "label": "Pack Small Files - Local Stage",
        "label_ru": "Мелкие файлы - local stage",
        "description": "Create local 7Z, test/hash, then transfer by Robocopy.",
        "description_ru": "Создать локальный 7Z, проверить/хешировать и передать Robocopy.",
    },
    "pack_direct": {
        "label": "Pack Small Files - Direct to Share",
        "label_ru": "Мелкие файлы - сразу в шару",
        "description": "Create 7Z directly on the target share.",
        "description_ru": "Создать 7Z сразу на сетевой цели.",
    },
    "verify_archive": {
        "label": "Verify Archive",
        "label_ru": "Проверить архив",
        "description": "Run 7Z integrity test and optional SHA256.",
        "description_ru": "Проверить архив через 7Z и опциональный SHA256.",
    },
    "extract_archive": {
        "label": "Extract Archive",
        "label_ru": "Распаковать архив",
        "description": "Extract selected 7Z archive into the target area.",
        "description_ru": "Распаковать выбранный 7Z в целевую область.",
    },
    "open_archive": {
        "label": "Open Archive in PeaZip",
        "label_ru": "Открыть архив в PeaZip",
        "description": "Open the selected archive in PeaZip GUI.",
        "description_ru": "Открыть выбранный архив в GUI PeaZip.",
    },
}
NETWORK_ARCHIVE_TOOL_MODES = {"pack_stage", "pack_direct", "verify_archive", "extract_archive", "open_archive"}
NETWORK_PANELS = {
    "transfer": {"label": "TRANSFER", "label_ru": "ПЕРЕДАЧА"},
    "smb_share": {"label": "SMB SHARE", "label_ru": "SMB SHARE"},
}
SMB_SHARE_ACTIONS = {
    "source_read": {"role": "source", "access": "Read", "label": "SOURCE R", "label_ru": "SOURCE R"},
    "source_write": {"role": "source", "access": "Change", "label": "SOURCE RW", "label_ru": "SOURCE RW"},
    "target_read": {"role": "target", "access": "Read", "label": "TARGET R", "label_ru": "TARGET R"},
    "target_write": {"role": "target", "access": "Change", "label": "TARGET RW", "label_ru": "TARGET RW"},
    "show_paths": {"role": "", "access": "", "label": "Show paths", "label_ru": "Пути"},
    "remove_source": {"role": "source", "access": "", "label": "Remove SOURCE", "label_ru": "Снять SOURCE"},
    "remove_target": {"role": "target", "access": "", "label": "Remove TARGET", "label_ru": "Снять TARGET"},
}


def split_mask_text(value: Any) -> list[str]:
    if isinstance(value, list):
        raw = ",".join(str(item or "") for item in value)
    else:
        raw = str(value or "")
    for separator in ["\r\n", "\n", "\r", ";"]:
        raw = raw.replace(separator, ",")
    return [item.strip() for item in raw.split(",") if item.strip()]


def normalize_mask_token(token: Any) -> str:
    text = str(token or "").strip().strip("\"'").replace("\\", "/").lower()
    if not text:
        return ""
    if any(mark in text for mark in "*?[]") or "/" in text:
        return text
    if text.startswith("."):
        return f"*{text}"
    return f"*.{text.lstrip('.')}"


def normalize_mask_tokens(value: Any) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in split_mask_text(value):
        pattern = normalize_mask_token(item)
        key = pattern.casefold()
        if pattern and key not in seen:
            result.append(pattern)
            seen.add(key)
    return result


def masks_to_text(masks: list[str]) -> str:
    return ", ".join(masks)


def empty_mask_cache() -> dict[str, Any]:
    return {"history": []}


def load_mask_cache() -> dict[str, Any]:
    if not MASK_CACHE_PATH.exists():
        return empty_mask_cache()
    try:
        raw = json.loads(MASK_CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logging.warning("Could not load mask cache: %s", exc)
        return empty_mask_cache()
    if not isinstance(raw, dict):
        return empty_mask_cache()
    history = raw.get("history", [])
    if not isinstance(history, list):
        history = []
    cleaned: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in history:
        if not isinstance(item, dict):
            continue
        text = masks_to_text(normalize_mask_tokens(item.get("text", "")))
        key = text.casefold()
        if not text or key in seen:
            continue
        seen.add(key)
        cleaned.append(
            {
                "text": text,
                "pinned": bool(item.get("pinned", False)),
                "count": int(item.get("count", 0) or 0),
                "last_used": str(item.get("last_used") or ""),
            }
        )
    cleaned.sort(key=lambda item: (bool(item.get("pinned")), int(item.get("count", 0) or 0), str(item.get("last_used", ""))), reverse=True)
    return {"history": cleaned[:MASK_CACHE_LIMIT]}


def save_mask_cache(cache: dict[str, Any]) -> None:
    MASK_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    MASK_CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def record_mask_cache(text: Any, *, pinned: bool | None = None, remove: bool = False) -> str:
    normalized = masks_to_text(normalize_mask_tokens(text))
    if not normalized:
        return ""
    cache = load_mask_cache()
    now = datetime.now().isoformat(timespec="seconds")
    history = cache.get("history", [])
    if not isinstance(history, list):
        history = []
    updated: list[dict[str, Any]] = []
    found = False
    for item in history:
        if not isinstance(item, dict):
            continue
        item_text = masks_to_text(normalize_mask_tokens(item.get("text", "")))
        if not item_text:
            continue
        if item_text.casefold() == normalized.casefold():
            found = True
            if remove:
                continue
            item["text"] = normalized
            item["count"] = int(item.get("count", 0) or 0) + 1
            item["last_used"] = now
            if pinned is not None:
                item["pinned"] = pinned
        updated.append(item)
    if not found and not remove:
        updated.append({"text": normalized, "pinned": bool(pinned), "count": 1, "last_used": now})
    updated.sort(key=lambda item: (bool(item.get("pinned")), int(item.get("count", 0) or 0), str(item.get("last_used", ""))), reverse=True)
    save_mask_cache({"history": updated[:MASK_CACHE_LIMIT]})
    return normalized


def _empty_rclone_endpoint_history() -> dict[str, list[dict[str, Any]]]:
    return {"users": [], "hosts": []}


def _coerce_endpoint_history_entry(item: Any) -> dict[str, Any] | None:
    if isinstance(item, str):
        text = item.strip()
        if not text:
            return None
        return {"value": text, "count": 1, "last_used": ""}
    if not isinstance(item, dict):
        return None
    text = str(item.get("value") or "").strip()
    if not text:
        return None
    try:
        count = max(1, int(item.get("count", 1) or 1))
    except (TypeError, ValueError):
        count = 1
    return {"value": text, "count": count, "last_used": str(item.get("last_used") or "").strip()}


def _normalize_endpoint_history_entries(entries: Any) -> list[dict[str, Any]]:
    if not isinstance(entries, list):
        return []
    merged: dict[str, dict[str, Any]] = {}
    for item in entries:
        entry = _coerce_endpoint_history_entry(item)
        if entry is None:
            continue
        key = str(entry["value"]).casefold()
        current = merged.get(key)
        if current is None:
            merged[key] = entry
            continue
        current["count"] = int(current.get("count", 0) or 0) + int(entry.get("count", 0) or 0)
        if str(entry.get("last_used", "")) >= str(current.get("last_used", "")):
            current["value"] = entry["value"]
            current["last_used"] = entry.get("last_used", "")
    result = list(merged.values())
    result.sort(key=lambda item: (int(item.get("count", 0) or 0), str(item.get("last_used", ""))), reverse=True)
    return result[:RCLONE_ENDPOINT_HISTORY_LIMIT]


def load_rclone_endpoint_history() -> dict[str, list[dict[str, Any]]]:
    if not RCLONE_ENDPOINT_HISTORY_PATH.exists():
        return _empty_rclone_endpoint_history()
    try:
        raw = json.loads(RCLONE_ENDPOINT_HISTORY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty_rclone_endpoint_history()
    if not isinstance(raw, dict):
        return _empty_rclone_endpoint_history()
    return {
        "users": _normalize_endpoint_history_entries(raw.get("users", [])),
        "hosts": _normalize_endpoint_history_entries(raw.get("hosts", [])),
    }


def save_rclone_endpoint_history(data: dict[str, Any]) -> None:
    normalized = {
        "users": _normalize_endpoint_history_entries(data.get("users", [])),
        "hosts": _normalize_endpoint_history_entries(data.get("hosts", [])),
    }
    RCLONE_ENDPOINT_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    RCLONE_ENDPOINT_HISTORY_PATH.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")


def record_rclone_endpoint_history(user: Any = "", host: Any = "") -> None:
    data = load_rclone_endpoint_history()
    now = datetime.now().isoformat(timespec="seconds")
    updates = {
        "users": str(user or "").strip(),
        "hosts": str(host or "").strip(),
    }
    changed = False
    for key, value in updates.items():
        if not value:
            continue
        entries = list(data.get(key, []))
        found = False
        for item in entries:
            if str(item.get("value", "")).casefold() != value.casefold():
                continue
            item["value"] = value
            item["count"] = int(item.get("count", 0) or 0) + 1
            item["last_used"] = now
            found = True
            changed = True
            break
        if not found:
            entries.append({"value": value, "count": 1, "last_used": now})
            changed = True
        data[key] = _normalize_endpoint_history_entries(entries)
    if changed:
        save_rclone_endpoint_history(data)


def clear_rclone_endpoint_history() -> None:
    if RCLONE_ENDPOINT_HISTORY_PATH.exists():
        RCLONE_ENDPOINT_HISTORY_PATH.unlink()


def rclone_endpoint_history_options(kind: str, current: Any = "") -> list[str]:
    key = "hosts" if str(kind or "").strip().lower() in {"host", "hosts", "ip"} else "users"
    current_text = str(current or "").strip()
    values = [str(item.get("value") or "").strip() for item in load_rclone_endpoint_history().get(key, [])]
    result: list[str] = []
    seen: set[str] = set()
    for value in [current_text, *values]:
        if not value or value.casefold() in seen:
            continue
        seen.add(value.casefold())
        result.append(value)
    return result


def clear_rclone_endpoint_history_from_ui(*, reset_fields: bool = True) -> None:
    clear_rclone_endpoint_history()
    if reset_fields:
        set_field_value("rclone_sftp_user", "user")
        set_field_value("rclone_sftp_host", "")
        set_field_value("rclone_sftp_port", "22")
    add_log("RClone endpoint user/host history cleared.")
    safe_notify("RClone endpoint cache cleared." if settings.language != "ru" else "Кэш user/host RClone очищен.", "positive")
    command_tree.refresh()


def rclone_cache_fields(values: dict[str, Any] | None = None) -> dict[str, str]:
    source = values if isinstance(values, dict) else state.setdefault("field_values", {})
    mode = normalize_rclone_mode(source.get("rclone_mode", source.get("mode", "transfer_run")))
    auth_method = normalize_sftp_auth_method(source.get("rclone_sftp_auth_method", source.get("sftp_auth_method", "agent")))
    return {
        "mode": mode,
        "config_scope": normalize_config_scope(source.get("rclone_config_scope", source.get("config_scope", RCLONE_DEFAULT_CONFIG_SCOPE))),
        "custom_config": str(source.get("rclone_custom_config", source.get("custom_config", "")) or "").strip(),
        "remote_name": str(source.get("rclone_remote_name", source.get("remote_name", "")) or "").strip().rstrip(":"),
        "remote_path": str(source.get("rclone_remote_path", source.get("remote_path", "")) or "").strip(),
        "flag_profile": normalize_flag_profile(source.get("rclone_flag_profile", source.get("flag_profile", RCLONE_DEFAULT_PROFILE))),
        "bwlimit": str(source.get("rclone_bwlimit", source.get("bwlimit", "")) or "").strip(),
        "log_level": normalize_log_level(source.get("rclone_log_level", source.get("log_level", "INFO"))),
        "source_kind": str(source.get("rclone_source_kind", source.get("source_kind", "saved_remote")) or "saved_remote").strip(),
        "source_remote_name": str(source.get("rclone_source_remote_name", source.get("source_remote_name", "drive")) or "drive").strip().rstrip(":"),
        "source_remote_path": str(source.get("rclone_source_remote_path", source.get("source_remote_path", "Backup")) or "").strip(),
        "target_kind": str(source.get("rclone_target_kind", source.get("target_kind", "saved_remote")) or "saved_remote").strip(),
        "target_remote_name": str(source.get("rclone_target_remote_name", source.get("target_remote_name", "server")) or "server").strip().rstrip(":"),
        "target_remote_path": str(source.get("rclone_target_remote_path", source.get("target_remote_path", "/home/user/backups")) or "").strip(),
        "auth_backend": normalize_auth_backend(source.get("rclone_auth_backend", source.get("auth_backend", "drive"))),
        "auth_remote_name": str(source.get("rclone_auth_remote_name", source.get("auth_remote_name", "server" if mode == "remote_create_sftp" else "drive")) or "").strip().rstrip(":"),
        "sftp_user": str(source.get("rclone_sftp_user", source.get("sftp_user", "user")) or "").strip(),
        "sftp_host": str(source.get("rclone_sftp_host", source.get("sftp_host", "")) or "").strip(),
        "sftp_port": str(source.get("rclone_sftp_port", source.get("sftp_port", "22")) or "22").strip(),
        "sftp_remote_path": str(source.get("rclone_sftp_remote_path", source.get("sftp_remote_path", "/home/user/backups")) or "").strip(),
        "sftp_auth_method": auth_method,
        "sftp_key_file": str(source.get("rclone_sftp_key_file", source.get("sftp_key_file", "")) or "").strip(),
        "sftp_known_hosts_file": str(source.get("rclone_sftp_known_hosts_file", source.get("sftp_known_hosts_file", "")) or "").strip(),
    }


def rclone_cache_key(fields: dict[str, Any]) -> str:
    normalized = rclone_cache_fields(fields)
    return json.dumps(normalized, ensure_ascii=False, sort_keys=True)


def empty_rclone_command_cache() -> dict[str, Any]:
    return {"history": []}


def load_rclone_command_cache() -> dict[str, Any]:
    if not RCLONE_COMMAND_CACHE_PATH.exists():
        return empty_rclone_command_cache()
    try:
        raw = json.loads(RCLONE_COMMAND_CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logging.warning("Could not load rclone command cache: %s", exc)
        return empty_rclone_command_cache()
    if not isinstance(raw, dict):
        return empty_rclone_command_cache()
    history = raw.get("history", [])
    if not isinstance(history, list):
        history = []
    cleaned: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in history:
        if not isinstance(item, dict):
            continue
        fields = item.get("fields")
        if not isinstance(fields, dict):
            continue
        normalized = rclone_cache_fields(fields)
        key = rclone_cache_key(normalized)
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(
            {
                "fields": normalized,
                "pinned": bool(item.get("pinned", False)),
                "count": int(item.get("count", 0) or 0),
                "last_used": str(item.get("last_used") or ""),
            }
        )
    cleaned.sort(key=lambda item: (bool(item.get("pinned")), int(item.get("count", 0) or 0), str(item.get("last_used", ""))), reverse=True)
    return {"history": cleaned[:RCLONE_COMMAND_CACHE_LIMIT]}


def save_rclone_command_cache(cache: dict[str, Any]) -> None:
    RCLONE_COMMAND_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    RCLONE_COMMAND_CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def record_rclone_command_cache(fields: dict[str, Any], *, pinned: bool | None = None, remove: bool = False) -> dict[str, str]:
    normalized = rclone_cache_fields(fields)
    cache = load_rclone_command_cache()
    now = datetime.now().isoformat(timespec="seconds")
    history = cache.get("history", [])
    if not isinstance(history, list):
        history = []
    key = rclone_cache_key(normalized)
    updated: list[dict[str, Any]] = []
    found = False
    for item in history:
        if not isinstance(item, dict):
            continue
        item_fields = item.get("fields")
        if not isinstance(item_fields, dict):
            continue
        if rclone_cache_key(item_fields) == key:
            found = True
            if remove:
                continue
            item["fields"] = normalized
            item["count"] = int(item.get("count", 0) or 0) + 1
            item["last_used"] = now
            if pinned is not None:
                item["pinned"] = bool(pinned)
        updated.append(item)
    if not found and not remove:
        updated.append({"fields": normalized, "pinned": bool(pinned), "count": 1, "last_used": now})
    updated.sort(key=lambda item: (bool(item.get("pinned")), int(item.get("count", 0) or 0), str(item.get("last_used", ""))), reverse=True)
    save_rclone_command_cache({"history": updated[:RCLONE_COMMAND_CACHE_LIMIT]})
    return normalized


def rclone_command_cache_label(fields: dict[str, Any], *, pinned: bool = False) -> str:
    mode = normalize_rclone_mode(fields.get("mode"))
    remote = str(fields.get("remote_name") or "drive").strip().rstrip(":") or "drive"
    remote_path = str(fields.get("remote_path") or "").strip().replace("\\", "/")
    profile = normalize_flag_profile(fields.get("flag_profile"))
    if mode in RCLONE_ROUTE_MODES:
        src = f"{fields.get('source_kind')}:{fields.get('source_remote_name', '')}/{fields.get('source_remote_path', '')}"
        dst = f"{fields.get('target_kind')}:{fields.get('target_remote_name', '')}/{fields.get('target_remote_path', '')}"
        path_label = f"{src} -> {dst}"
    elif mode in RCLONE_AUTH_MODES:
        path_label = str(fields.get("auth_remote_name") or remote or "remote")
    else:
        path_label = f"{remote}:{remote_path}" if mode in RCLONE_REMOTE_MODES else "-"
    prefix = "PIN | " if pinned else ""
    return f"{prefix}{rclone_mode_label(mode, settings.language)} | {path_label} | {profile}"


def rclone_command_cache_options(current_fields: dict[str, Any]) -> dict[str, str]:
    options: dict[str, str] = {}
    for item in load_rclone_command_cache().get("history", []):
        if not isinstance(item, dict) or not isinstance(item.get("fields"), dict):
            continue
        fields = item["fields"]
        key = rclone_cache_key(fields)
        label = rclone_command_cache_label(fields, pinned=bool(item.get("pinned")))
        options[key] = label
    current_key = rclone_cache_key(current_fields)
    if current_key not in options:
        options[current_key] = rclone_command_cache_label(current_fields)
    return options


def rclone_command_cache_selection(value: Any) -> dict[str, str] | None:
    selected_key = str(value or "").strip()
    if not selected_key:
        return None
    for item in load_rclone_command_cache().get("history", []):
        if not isinstance(item, dict) or not isinstance(item.get("fields"), dict):
            continue
        fields = item["fields"]
        if rclone_cache_key(fields) == selected_key:
            return rclone_cache_fields(fields)
    return None


def apply_rclone_cached_fields(fields: dict[str, str]) -> None:
    mapping = {
        "mode": "rclone_mode",
        "config_scope": "rclone_config_scope",
        "custom_config": "rclone_custom_config",
        "remote_name": "rclone_remote_name",
        "remote_path": "rclone_remote_path",
        "flag_profile": "rclone_flag_profile",
        "bwlimit": "rclone_bwlimit",
        "log_level": "rclone_log_level",
        "source_kind": "rclone_source_kind",
        "source_remote_name": "rclone_source_remote_name",
        "source_remote_path": "rclone_source_remote_path",
        "target_kind": "rclone_target_kind",
        "target_remote_name": "rclone_target_remote_name",
        "target_remote_path": "rclone_target_remote_path",
        "auth_backend": "rclone_auth_backend",
        "auth_remote_name": "rclone_auth_remote_name",
        "sftp_user": "rclone_sftp_user",
        "sftp_host": "rclone_sftp_host",
        "sftp_port": "rclone_sftp_port",
        "sftp_remote_path": "rclone_sftp_remote_path",
        "sftp_auth_method": "rclone_sftp_auth_method",
        "sftp_key_file": "rclone_sftp_key_file",
        "sftp_known_hosts_file": "rclone_sftp_known_hosts_file",
    }
    for source_key, field_key in mapping.items():
        if source_key in fields:
            set_field_value(field_key, fields.get(source_key, ""))


def _normalize_selection_items(value: Any) -> list[str]:
    raw = value if isinstance(value, list) else []
    result: list[str] = []
    seen: set[str] = set()
    for item in raw:
        text = str(item or "").strip()
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


def _selection_key(include: Any, exclude: Any) -> str:
    return json.dumps(
        {"include": _normalize_selection_items(include), "exclude": _normalize_selection_items(exclude)},
        ensure_ascii=False,
        sort_keys=True,
    )


def _selection_label(include: Any, exclude: Any, *, pinned: bool = False) -> str:
    include_items = _normalize_selection_items(include)
    exclude_items = _normalize_selection_items(exclude)

    def compact(items: list[str]) -> str:
        if not items:
            return "-"
        visible = ", ".join(items[:6])
        return f"{visible} +{len(items) - 6}" if len(items) > 6 else visible

    prefix = "PIN  " if pinned else ""
    return f"{prefix}ВКЛ: {compact(include_items)} | ИСКЛ: {compact(exclude_items)}"


def load_profile_extension_cache() -> dict[str, Any]:
    if not PROFILE_EXTENSION_PINS_PATH.exists():
        return {"history": []}
    try:
        data = json.loads(PROFILE_EXTENSION_PINS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"history": []}
    if not isinstance(data, dict):
        return {"history": []}
    history = data.get("history", [])
    return {"history": history if isinstance(history, list) else []}


def save_profile_extension_cache(data: dict[str, Any]) -> None:
    PROFILE_EXTENSION_PINS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROFILE_EXTENSION_PINS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def record_profile_extension_cache(include: Any, exclude: Any, *, pinned: bool | None = None, remove: bool = False) -> tuple[list[str], list[str]]:
    include_items = _normalize_selection_items(include)
    exclude_items = _normalize_selection_items(exclude)
    if not include_items and not exclude_items:
        return include_items, exclude_items

    key = _selection_key(include_items, exclude_items)
    now = datetime.now().isoformat(timespec="seconds")
    updated: list[dict[str, Any]] = []
    matched = False
    for raw_item in load_profile_extension_cache().get("history", []):
        if not isinstance(raw_item, dict):
            continue
        item_include = _normalize_selection_items(raw_item.get("include", []))
        item_exclude = _normalize_selection_items(raw_item.get("exclude", []))
        if not item_include and not item_exclude:
            continue
        item = {
            "include": item_include,
            "exclude": item_exclude,
            "pinned": bool(raw_item.get("pinned", False)),
            "count": int(raw_item.get("count", 0) or 0),
            "last_used": str(raw_item.get("last_used") or ""),
        }
        if _selection_key(item_include, item_exclude) == key:
            matched = True
            if remove:
                continue
            item["count"] = int(item["count"]) + 1
            item["last_used"] = now
            if pinned is not None:
                item["pinned"] = bool(pinned)
        updated.append(item)
    if not matched and not remove:
        updated.append({"include": include_items, "exclude": exclude_items, "pinned": bool(pinned), "count": 1, "last_used": now})
    updated.sort(key=lambda item: (bool(item.get("pinned")), int(item.get("count", 0) or 0), str(item.get("last_used", ""))), reverse=True)
    save_profile_extension_cache({"history": updated[:MASK_CACHE_LIMIT]})
    return include_items, exclude_items


def profile_extension_cache_options(current_include: Any, current_exclude: Any) -> list[str]:
    options: list[str] = []
    seen: set[str] = set()
    current_include_items = _normalize_selection_items(current_include)
    current_exclude_items = _normalize_selection_items(current_exclude)
    if current_include_items or current_exclude_items:
        label = _selection_label(current_include_items, current_exclude_items)
        options.append(label)
        seen.add(_selection_key(current_include_items, current_exclude_items))
    for item in load_profile_extension_cache().get("history", []):
        if not isinstance(item, dict):
            continue
        include_items = _normalize_selection_items(item.get("include", []))
        exclude_items = _normalize_selection_items(item.get("exclude", []))
        key = _selection_key(include_items, exclude_items)
        if (not include_items and not exclude_items) or key in seen:
            continue
        options.append(_selection_label(include_items, exclude_items, pinned=bool(item.get("pinned"))))
        seen.add(key)
    return options


def profile_extension_cache_selection(label: Any) -> tuple[list[str], list[str]] | None:
    text = str(label or "").strip()
    if text.startswith("PIN  "):
        text = text[5:].strip()
    for item in load_profile_extension_cache().get("history", []):
        if not isinstance(item, dict):
            continue
        include_items = _normalize_selection_items(item.get("include", []))
        exclude_items = _normalize_selection_items(item.get("exclude", []))
        if _selection_label(include_items, exclude_items) == text:
            return include_items, exclude_items
    return None


def set_archive_format(format_id: str, enabled: bool) -> None:
    selected = [str(item) for item in archive_state.get("formats", []) if str(item) in ARCHIVE_FORMATS]
    if enabled and format_id not in selected:
        selected.append(format_id)
    if not enabled and format_id in selected:
        selected.remove(format_id)
    archive_state["formats"] = selected


def normalize_archive_encryption_mode(mode: Any) -> str:
    text = str(mode or "none").strip().lower()
    return text if text in ARCHIVE_ENCRYPTION_OPTIONS else "none"


def archive_encryption_supported_formats(mode: Any) -> set[str]:
    encryption_mode = normalize_archive_encryption_mode(mode)
    if encryption_mode == "none":
        return set(ARCHIVE_FORMATS)
    if encryption_mode == "names":
        return set(ARCHIVE_NAME_ENCRYPTION_FORMATS)
    return set(ARCHIVE_PASSWORD_FORMATS)


def archive_format_supports_encryption(format_id: Any, mode: Any) -> bool:
    return str(format_id).lower() in archive_encryption_supported_formats(mode)


def archive_format_backend_available(format_id: Any) -> bool:
    archive_id = str(format_id).lower()
    if archive_id == "zstd":
        return find_zstd_executable() is not None
    if archive_id == "lz4":
        return find_lz4_executable() is not None
    return archive_id in ARCHIVE_FORMATS


def sfx_wrapper_backend_available(wrapper_id: Any) -> bool:
    wrapper = str(wrapper_id).lower()
    if wrapper == "zstd":
        return find_zstd_executable() is not None
    return wrapper in SFX_WRAPPER_FORMATS


def archive_format_disabled_reason(format_id: Any, mode: Any) -> str:
    archive_id = str(format_id).lower()
    label = ARCHIVE_FORMATS.get(archive_id, {}).get("label", archive_id.upper())
    russian = settings.language == "ru"
    if not archive_format_supports_encryption(archive_id, mode):
        if archive_id == "zip":
            return archive_encryption_zip_note()
        return (
            f"{label} не умеет шифрование: в этом формате его нет."
            if russian
            else f"{label} carries no encryption: the format has none."
        )
    if not archive_format_backend_available(archive_id):
        if archive_id == "lz4":
            return (
                "LZ4 недоступен: в portable-комплекте нет lz4.exe."
                if russian
                else "LZ4 is unavailable: the portable kit has no lz4.exe."
            )
        if archive_id == "zstd":
            return (
                "ZSTD недоступен: в portable-комплекте нет zstd.exe."
                if russian
                else "ZSTD is unavailable: the portable kit has no zstd.exe."
            )
        return f"{label} недоступен: backend не найден." if russian else f"{label} is unavailable: backend not found."
    return ""


def prune_archive_formats_for_encryption(formats: Any, mode: Any) -> list[str]:
    supported = archive_encryption_supported_formats(mode)
    return [
        str(item).lower()
        for item in formats
        if (
            str(item).lower() in ARCHIVE_FORMATS
            and str(item).lower() in supported
            and archive_format_backend_available(str(item).lower())
        )
    ] if isinstance(formats, list) else []


def normalize_sfx_wrapper_formats(formats: Any) -> list[str]:
    if not isinstance(formats, list):
        return []
    return [
        str(item).lower()
        for item in formats
        if str(item).lower() in SFX_WRAPPER_FORMATS and sfx_wrapper_backend_available(str(item).lower())
    ]


def known_env_locations() -> dict[str, Path]:
    user_profile = Path(os.environ.get("USERPROFILE") or Path.home())
    return {
        "%LOCALDATA%": Path(os.environ.get("LOCALAPPDATA") or user_profile / "AppData" / "Local"),
        "%USERDATA%": Path(os.environ.get("APPDATA") or user_profile / "AppData" / "Roaming"),
        "%USERPROFILE%": user_profile,
        "%PROGRAMDATA%": Path(os.environ.get("PROGRAMDATA") or "C:\\ProgramData"),
        "%PROGRAMFILES%": Path(os.environ.get("ProgramW6432") or os.environ.get("ProgramFiles") or "C:\\Program Files"),
        "%PROGRAMFILES_X86%": Path(os.environ.get("ProgramFiles(x86)") or os.environ.get("ProgramFiles") or "C:\\Program Files (x86)"),
        "%COMMONPROGRAMFILES%": Path(os.environ.get("CommonProgramW6432") or os.environ.get("CommonProgramFiles") or "C:\\Program Files\\Common Files"),
        "%COMMONPROGRAMFILES_X86%": Path(os.environ.get("CommonProgramFiles(x86)") or os.environ.get("CommonProgramFiles") or "C:\\Program Files (x86)\\Common Files"),
        "%PUBLIC%": Path(os.environ.get("PUBLIC") or "C:\\Users\\Public"),
        "%SYSTEMDRIVE%": Path(f"{os.environ.get('SystemDrive') or 'C:'}\\"),
        "%TEMP%": Path(os.environ.get("TEMP") or os.environ.get("TMP") or user_profile / "AppData" / "Local" / "Temp"),
        "%DOCUMENTS%": user_profile / "Documents",
        "%DOWNLOADS%": user_profile / "Downloads",
        "%DESKTOP%": user_profile / "Desktop",
    }


def normalize_sfx_extract_tail(template: Any, folder_name: str = "{name}") -> str:
    tail = str(template or "").strip()
    tail = tail.replace("{name}", folder_name).replace("{NAME}", folder_name)
    tail = tail.replace("<name>", "<имя>").replace("<NAME>", "<имя>")
    tail = tail.replace("<имя>", folder_name).replace("/", "\\")
    return tail.strip("\\")


def normalize_sfx_env_key(env_key: Any) -> str:
    env_text = str(env_key or "").strip().upper()
    if env_text == SFX_ENV_NONE.upper():
        return ""
    return env_text if env_text in SFX_ENV_OPTIONS else ""


def resolve_sfx_extract_path(env_key: Any, template: Any, folder_name: str = "{name}") -> str:
    env_text = normalize_sfx_env_key(env_key)
    tail = normalize_sfx_extract_tail(template, folder_name)
    if not env_text:
        return tail
    base = known_env_locations().get(env_text, known_env_locations()["%LOCALDATA%"])
    if not tail:
        return str(base)
    return str((base / tail).resolve())


def sfx_install_path_template(env_key: Any, template: Any, folder_name: str) -> str:
    env_text = normalize_sfx_env_key(env_key)
    base = SFX_INSTALL_ENV_PATHS.get(env_text, "")
    tail = normalize_sfx_extract_tail(template, folder_name)
    if not base:
        return tail
    return base if not tail else f"{base}\\{tail}"


def sfx_path_display(env_key: Any, template: Any) -> str:
    env_text = normalize_sfx_env_key(env_key)
    tail = normalize_sfx_extract_tail(template)
    if not env_text:
        return tail
    return env_text if not tail else f"{env_text}\\{tail}"


def tr(key: str, **kwargs: Any) -> str:
    lang = settings.language if settings.language in LABELS else "en"
    text = LABELS.get(lang, LABELS["en"]).get(key, key)
    return text.format(**kwargs) if kwargs else text


def em(key: str) -> str:
    if not bool(getattr(settings, "emoji", False)):
        return ""
    return {
        "workspace": "📁 ",
        "operations": "⚙ ",
        "maintenance": "🧰 ",
        "status": "● ",
        "log": "🖥 ",
    }.get(key, "")


def app_title() -> str:
    title = str(ui_info.get("title") or tool_info.get("name") or "Audion GUI Tool")
    return title[:-3] if title.endswith(" UI") else title


def normalize_theme_id(theme_id: Any) -> str:
    text = str(theme_id or DEFAULT_THEME_ID).strip().lower()
    return THEME_ALIASES.get(text, text)


def active_theme() -> str:
    theme_id = normalize_theme_id(settings.theme)
    themes = ui_colors["themes"]
    if theme_id in themes:
        return theme_id
    return DEFAULT_THEME_ID if DEFAULT_THEME_ID in themes else next(iter(themes))


def active_theme_data() -> dict[str, Any]:
    return dict(ui_colors["themes"][active_theme()])


def active_theme_mode() -> str:
    return str(active_theme_data().get("mode", "dark"))


def theme_label(theme_id: str) -> str:
    theme_data = ui_colors["themes"].get(theme_id, {})
    label_key = "label_ru" if settings.language == "ru" else "label"
    return str(theme_data.get(label_key) or theme_data.get("label") or theme_id)


def theme_options() -> dict[str, str]:
    return {theme_id: theme_label(theme_id) for theme_id in ui_colors["themes"]}


def set_theme(theme_id: Any) -> None:
    selected = normalize_theme_id(theme_id)
    if selected not in ui_colors["themes"]:
        return
    settings.theme = selected
    save_ui_settings(settings_path, settings)
    safe_notify(tr("theme_saved"), "positive")
    reload_ui()


def theme_change_handler(event: Any) -> None:
    set_theme(getattr(event, "value", None))

def reload_ui() -> None:
    ui.run_javascript(
        """
        (() => {
          try {
            if ('scrollRestoration' in window.history) {
              window.history.scrollRestoration = 'manual';
            }
            window.sessionStorage.setItem('audion_force_scroll_top', '1');
            window.scrollTo(0, 0);
            document.documentElement.scrollTop = 0;
            document.body.scrollTop = 0;
          } catch (error) {}
          window.location.reload();
        })();
        """
    )

def theme_variables() -> dict[str, str]:
    variables: dict[str, str] = {}
    for ramp_name, stops in ui_colors["ramps"].items():
        if not isinstance(stops, dict):
            continue
        for stop, color in stops.items():
            variables[f"color-{ramp_name}-{stop}"] = str(color).strip()
    variables.update(ui_colors["tokens"])
    variables.update(_string_map(active_theme_data().get("tokens", {})))
    variables.setdefault("color-background-primary", "#141413")
    variables.setdefault("color-background-secondary", "#1f1e1a")
    variables.setdefault("color-background-tertiary", "#0f0f0e")
    variables.setdefault("color-text-primary", "#faf9f5")
    variables.setdefault("color-text-secondary", "#e8e6dc")
    variables.setdefault("color-text-tertiary", "#b0aea5")
    variables.setdefault("color-border-tertiary", "rgba(250, 249, 245, 0.15)")
    variables.setdefault("color-border-secondary", "rgba(250, 249, 245, 0.3)")
    variables.setdefault("color-border-primary", "rgba(250, 249, 245, 0.4)")
    variables.setdefault("color-accent-primary", "#d97757")
    variables.setdefault("color-accent-secondary", "#6a9bcc")
    variables.setdefault("color-accent-tertiary", "#788c5d")
    variables.setdefault("font-sans", "Inter, Segoe UI, Arial, sans-serif")
    variables.setdefault("font-mono", "Cascadia Mono, Consolas, monospace")
    variables.setdefault("border-radius-md", "8px")
    variables.setdefault("border-radius-lg", "12px")
    return variables


def add_log(message: str) -> None:
    text = str(message)
    lines = text.splitlines() or [""]
    for line in lines:
        state["lines"].append(line.rstrip("\r"))
    state["terminal_total_lines"] = int(state.get("terminal_total_lines", 0)) + len(lines)
    state["lines"] = state["lines"][-TERMINAL_HISTORY_LIMIT:]
    state["log_version"] = int(state["log_version"]) + 1


def clear_terminal_log() -> None:
    state["lines"] = []
    state["terminal_epoch"] = int(state.get("terminal_epoch", 0)) + 1
    state["terminal_total_lines"] = 0
    state["log_version"] = int(state["log_version"]) + 1


def progress_text() -> str:
    return f"{round(max(0.0, min(1.0, float(state['progress']))) * 100):.0f}%"


def safe_notify(message: str, kind: str = "info", **notify_kwargs: Any) -> None:
    notify_type = str(notify_kwargs.pop("type", kind))
    options = {"message": str(message), "type": notify_type, **notify_kwargs}
    delivered = False
    for client in list(nicegui_app.clients()):
        if getattr(client, "_deleted", False) or not client.has_socket_connection:
            continue
        try:
            client.outbox.enqueue_message("notify", options, client.id)
            delivered = True
        except Exception as exc:
            logging.warning("NiceGUI notification delivery failed for client %s: %s", getattr(client, "id", "?"), exc)
    if delivered:
        return

    try:
        ui.notify(message, type=notify_type, **notify_kwargs)
    except RuntimeError as exc:
        message_text = str(exc)
        if "slot belongs to has been deleted" not in message_text and "current slot cannot be determined" not in message_text:
            raise
        logging.warning("NiceGUI notification skipped because no live client slot was available: %s", message)


RUN_STATE_LABELS = {
    "idle": ("idle", "audion-status-idle"),
    "running": ("running", "audion-status-running"),
    "done": ("done", "audion-status-done"),
    "error": ("error", "audion-status-error"),
}


def run_state() -> str:
    """Which of the four states the panel is showing.

    Colour carries this everywhere it appears, so it is decided once.
    """
    if bool(state["running"]):
        return "running"
    exit_code = state.get("exit_code")
    if exit_code is None:
        return "idle"
    return "done" if int(exit_code or 0) == 0 else "error"


def status_row_classes() -> str:
    return f"audion-status-row {RUN_STATE_LABELS[run_state()][1]}"


def status_state_text() -> str:
    return tr(RUN_STATE_LABELS[run_state()][0]).upper()


def elapsed_text(seconds: float | None) -> str:
    """A run's own clock, mm:ss, or an em dash before anything has run.

    The start is noticed by the refresh timer rather than written by the code that
    starts a run: there are several such places, and none of them has to know
    about the panel.
    """
    if seconds is None:
        return "—"
    total = max(0, int(seconds))
    return f"{total // 60:02d}:{total % 60:02d}"


def status_dot_classes() -> str:
    base = "audion-status-dot text-lg leading-none"
    if bool(state["running"]):
        return f"{base} text-sky-400 animate-pulse"
    if state.get("exit_code") is None:
        return f"{base} text-gray-500"
    if int(state.get("exit_code") or 0) == 0:
        return f"{base} text-green-400"
    return f"{base} text-red-400"


def set_progress(value: float) -> None:
    state["progress"] = max(0.0, min(1.0, float(value)))


def cancel_requested() -> bool:
    return bool(state["cancel"])


def hidden_subprocess_flags() -> int:
    if os.name == "nt" and hasattr(subprocess, "CREATE_NO_WINDOW"):
        return int(subprocess.CREATE_NO_WINDOW)
    return 0


def hidden_subprocess_startupinfo() -> subprocess.STARTUPINFO | None:
    if os.name != "nt" or not hasattr(subprocess, "STARTUPINFO"):
        return None
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = 0
    return startupinfo


def resolve_dialog_powershell() -> list[str]:
    candidates = [
        [str(paths.system_core / "powershell" / "pwsh.exe"), "-NoLogo", "-NoProfile", "-STA", "-Command"],
        ["pwsh.exe", "-NoLogo", "-NoProfile", "-STA", "-Command"],
        ["powershell.exe", "-NoProfile", "-STA", "-ExecutionPolicy", "Bypass", "-Command"],
    ]
    for candidate in candidates:
        exe = candidate[0]
        if Path(exe).exists() or shutil.which(exe):
            return candidate
    raise RuntimeError("PowerShell was not found for Windows picker.")


_PICKER_RUN_LOCK = threading.Lock()
_PICKER_JOB_LOCK = threading.Lock()
_PICKER_SHUTDOWN = threading.Event()
_PICKER_JOB_HANDLE: int | None = None


class _JobObjectBasicLimitInformation(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class _IoCounters(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_uint64),
        ("WriteOperationCount", ctypes.c_uint64),
        ("OtherOperationCount", ctypes.c_uint64),
        ("ReadTransferCount", ctypes.c_uint64),
        ("WriteTransferCount", ctypes.c_uint64),
        ("OtherTransferCount", ctypes.c_uint64),
    ]


class _JobObjectExtendedLimitInformation(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _JobObjectBasicLimitInformation),
        ("IoInfo", _IoCounters),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


def close_picker_job() -> None:
    global _PICKER_JOB_HANDLE
    _PICKER_SHUTDOWN.set()
    with _PICKER_JOB_LOCK:
        handle = _PICKER_JOB_HANDLE
        _PICKER_JOB_HANDLE = None
    if os.name == "nt" and handle:
        ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle(wintypes.HANDLE(handle))


def _picker_job_handle() -> int | None:
    global _PICKER_JOB_HANDLE
    if os.name != "nt" or _PICKER_SHUTDOWN.is_set():
        return None
    with _PICKER_JOB_LOCK:
        if _PICKER_SHUTDOWN.is_set():
            return None
        if _PICKER_JOB_HANDLE:
            return _PICKER_JOB_HANDLE
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        job = kernel32.CreateJobObjectW(None, None)
        if not job:
            logging.warning("Could not create the Windows picker job: %s", ctypes.get_last_error())
            return None
        info = _JobObjectExtendedLimitInformation()
        info.BasicLimitInformation.LimitFlags = 0x00002000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        configured = kernel32.SetInformationJobObject(
            wintypes.HANDLE(job),
            9,
            ctypes.byref(info),
            ctypes.sizeof(info),
        )
        if not configured:
            error = ctypes.get_last_error()
            kernel32.CloseHandle(wintypes.HANDLE(job))
            logging.warning("Could not configure the Windows picker job: %s", error)
            return None
        _PICKER_JOB_HANDLE = int(job)
        return _PICKER_JOB_HANDLE


def _assign_picker_to_job(process: subprocess.Popen[str]) -> None:
    handle = _picker_job_handle()
    if os.name != "nt" or not handle:
        if _PICKER_SHUTDOWN.is_set() and process.poll() is None:
            process.kill()
        return
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    assigned = kernel32.AssignProcessToJobObject(
        wintypes.HANDLE(handle),
        wintypes.HANDLE(int(process._handle)),  # type: ignore[attr-defined]
    )
    if not assigned:
        logging.warning("Could not attach picker PID %s to its Windows job: %s", process.pid, ctypes.get_last_error())


def parse_picker_paths(text: str) -> list[Path]:
    import json

    payload = text.strip()
    if not payload:
        return []
    data = json.loads(payload)
    if isinstance(data, str):
        data = [data]
    return [Path(str(item)).resolve() for item in data if str(item).strip()]


def ps_single_quote(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def run_picker_script(script: str, error_message: str) -> list[Path]:
    if not _PICKER_RUN_LOCK.acquire(blocking=False):
        raise RuntimeError("A Windows picker is already open.")
    process: subprocess.Popen[str] | None = None
    try:
        if _PICKER_SHUTDOWN.is_set():
            raise RuntimeError("Windows picker supervisor is shutting down.")
        _picker_job_handle()
        process = subprocess.Popen(
            [*resolve_dialog_powershell(), script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=hidden_subprocess_flags(),
            startupinfo=hidden_subprocess_startupinfo(),
        )
        _assign_picker_to_job(process)
        if _PICKER_SHUTDOWN.is_set():
            if process.poll() is None:
                process.kill()
            raise RuntimeError("Windows picker supervisor is shutting down.")
        try:
            stdout, stderr = process.communicate(timeout=3600)
        except subprocess.TimeoutExpired as exc:
            process.kill()
            process.communicate()
            raise RuntimeError("Windows picker timed out.") from exc
        if process.returncode != 0:
            raise RuntimeError(stderr.strip() or error_message)
        return parse_picker_paths(stdout)
    finally:
        if process is not None and process.poll() is None:
            process.kill()
        _PICKER_RUN_LOCK.release()


atexit.register(close_picker_job)
nicegui_app.on_shutdown(close_picker_job)


def pick_json_open_file(title: str) -> list[Path]:
    script = PICKER_BOOTSTRAP + f"""
$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Title = {ps_single_quote(title)}
$dialog.Multiselect = $false
$dialog.Filter = 'JSON files|*.json|All files|*.*'
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {{
  @($dialog.FileName) | ConvertTo-Json -Compress
}}
"""
    return run_picker_script(script, f"{title} picker failed.")


def pick_json_save_file(title: str, default_name: str) -> list[Path]:
    script = PICKER_BOOTSTRAP + f"""
$dialog = New-Object System.Windows.Forms.SaveFileDialog
$dialog.Title = {ps_single_quote(title)}
$dialog.FileName = {ps_single_quote(default_name)}
$dialog.Filter = 'JSON files|*.json|All files|*.*'
$dialog.DefaultExt = 'json'
$dialog.AddExtension = $true
$dialog.OverwritePrompt = $true
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {{
  @($dialog.FileName) | ConvertTo-Json -Compress
}}
"""
    return run_picker_script(script, f"{title} picker failed.")


def pick_single_file() -> list[Path]:
    script = PICKER_BOOTSTRAP + f"""
$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Title = {ps_single_quote(tr("add_file_short"))}
$dialog.Multiselect = $false
$dialog.Filter = 'All supported files|*.*|All files|*.*'
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {{
  @($dialog.FileName) | ConvertTo-Json -Compress
}}
"""
    return run_picker_script(script, "File picker failed.")


def pick_folder() -> list[Path]:
    script = PICKER_BOOTSTRAP + f"""
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = {ps_single_quote(tr("add_folder"))}
$dialog.ShowNewFolderButton = $false
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {{
  @($dialog.SelectedPath) | ConvertTo-Json -Compress
}}
"""
    return run_picker_script(script, "Folder picker failed.")


def pick_path_history_import_file() -> list[Path]:
    return pick_json_open_file(tr("import_paths"))


def pick_path_history_export_file() -> list[Path]:
    return pick_json_save_file(tr("export_paths"), "audion_path_history.json")


def find_7zip_executable() -> Path | None:
    candidates = [
        ROOT / "Tools" / "PeaZip" / "res" / "7z" / "7z.exe",
        ROOT / "Tools" / "PeaZip" / "res" / "7z" / "7za.exe",
        ROOT / "Tools" / "PeaZip" / "res" / "bin" / "7z" / "7z.exe",
        ROOT / "Tools" / "PeaZip" / "res" / "bin" / "7z" / "7za.exe",
        ROOT / "Tools" / "PeaZip" / "res" / "bin" / "7z.exe",
        ROOT / "Tools" / "PeaZip" / "res" / "bin" / "7za.exe",
        ROOT / "Tools" / "7zip" / "bin" / "7z.exe",
        ROOT / "Tools" / "7zip" / "bin" / "7za.exe",
    ]
    for name in ("7za.exe", "7z.exe", "7za", "7z"):
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def find_sfx_module(sevenzip: Path) -> Path | None:
    roots = [
        sevenzip.parent,
        ROOT / "Tools" / "7zip" / "bin",
        ROOT / "Tools" / "PeaZip" / "res" / "7z",
        ROOT / "Tools" / "PeaZip" / "res" / "bin" / "7z",
        ROOT / "Tools" / "PeaZip" / "res" / "bin",
    ]
    names = ("7z.sfx", "7zCon.sfx", "7zSD.sfx", "7zS.sfx", "7z.sfx.exe")
    for root in roots:
        if not root.exists():
            continue
        for name in names:
            candidate = root / name
            if candidate.exists():
                return candidate
        for candidate in root.rglob("*.sfx"):
            if candidate.is_file():
                return candidate
    return None


def find_peazip_executable() -> Path | None:
    candidates = [
        ROOT / "Tools" / "PeaZip" / "peazip.exe",
        ROOT / "Tools" / "PeaZip" / "peazip_portable.exe",
    ]
    for name in ("peazip.exe", "peazip_portable.exe"):
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def find_zstd_executable() -> Path | None:
    candidates = [
        ROOT / "Tools" / "PeaZip" / "res" / "bin" / "zstd" / "zstd.exe",
        ROOT / "Tools" / "zstd" / "zstd.exe",
    ]
    for name in ("zstd.exe", "zstd"):
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def find_lz4_executable() -> Path | None:
    candidates = [
        ROOT / "Tools" / "PeaZip" / "res" / "bin" / "lz4" / "lz4.exe",
        ROOT / "Tools" / "lz4" / "lz4.exe",
    ]
    for name in ("lz4.exe", "lz4"):
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def zstd_compression_args(level: str) -> list[str]:
    try:
        numeric_level = int(str(level).strip())
    except ValueError:
        numeric_level = 5
    if numeric_level <= 0:
        return ["--fast=1"]
    return [f"-{min(19, numeric_level)}"]


def run_zstd_compress(source: Path, target: Path, level: str) -> int:
    zstd = find_zstd_executable()
    if zstd is None:
        raise RuntimeError("ZSTD executable was not found. Install PeaZip portable or add zstd.exe to Tools.")
    command = [
        str(zstd),
        "-f",
        "-T0",
        *zstd_compression_args(level),
        "-o",
        str(target),
        str(source),
    ]
    return run_archive_command(command, source.parent)


def run_zstd_test(archive_path: Path) -> int:
    zstd = find_zstd_executable()
    if zstd is None:
        raise RuntimeError("ZSTD executable was not found. Install PeaZip portable or add zstd.exe to Tools.")
    command = [
        str(zstd),
        "-t",
        str(archive_path),
    ]
    return run_archive_command(command, archive_path.parent)


# Per-file logging plus progress on stdout. Cancellation is only observed between
# output lines, so a silent 7-Zip run would leave the Cancel button unresponsive
# until the whole archive is finished.
SEVENZIP_PROGRESS_ARGS: tuple[str, ...] = ("-bb1", "-bsp1", "-bso1", "-bse1")

LZ4_MISSING_MESSAGE = "LZ4 executable was not found. Add lz4.exe to Tools\\lz4 to enable TAR.LZ4."


def lz4_compression_args(level: str) -> list[str]:
    try:
        numeric_level = int(str(level).strip())
    except ValueError:
        numeric_level = 1
    if numeric_level <= 0:
        return ["--fast"]
    return [f"-{min(12, numeric_level)}"]


def run_lz4_compress(source: Path, target: Path, level: str) -> int:
    """Compress through lz4.exe.

    The bundled 7-Zip carries lz4 only as a codec, not as an archive type, so
    `7z a -tlz4` fails with "Unsupported archive type". TAR.LZ4 therefore goes
    through the standalone CLI, the same way TAR.ZSTD uses zstd.exe.
    """
    lz4 = find_lz4_executable()
    if lz4 is None:
        raise RuntimeError(LZ4_MISSING_MESSAGE)
    command = [
        str(lz4),
        "-f",
        *lz4_compression_args(level),
        str(source),
        str(target),
    ]
    return run_archive_command(command, source.parent)


def run_lz4_test(archive_path: Path) -> int:
    lz4 = find_lz4_executable()
    if lz4 is None:
        raise RuntimeError(LZ4_MISSING_MESSAGE)
    command = [
        str(lz4),
        "-t",
        str(archive_path),
    ]
    return run_archive_command(command, archive_path.parent)


def install_portable_peazip() -> int:
    installer = ROOT / "install" / "Install-Portable-PeaZip.cmd"
    if not installer.exists():
        raise RuntimeError(f"PeaZip installer was not found: {installer}")
    command = ["cmd.exe", "/c", str(installer), "/NOPAUSE"]
    return run_archive_command(command, ROOT)


def install_portable_lz4() -> int:
    installer = ROOT / "install" / "Install-Portable-LZ4.cmd"
    if not installer.exists():
        raise RuntimeError(f"LZ4 installer was not found: {installer}")
    command = ["cmd.exe", "/c", str(installer), "/NOPAUSE"]
    return run_archive_command(command, ROOT)


def install_portable_rclone() -> int:
    installer = ROOT / "install" / "Install-Portable-Rclone.cmd"
    if not installer.exists():
        raise RuntimeError(f"Rclone installer was not found: {installer}")
    command = ["cmd.exe", "/c", str(installer), "/NOPAUSE"]
    return run_archive_command(command, ROOT)


def install_system_rclone() -> int:
    installer = ROOT / "install" / "Install-System-Rclone.cmd"
    if not installer.exists():
        raise RuntimeError(f"System Rclone installer was not found: {installer}")
    command = ["cmd.exe", "/c", str(installer), "/NOPAUSE"]
    return run_archive_command(command, ROOT)


def split_archive_name(path: Path) -> tuple[str, str]:
    """Split a file name into (stem, extension) using known compound suffixes.

    `Path.suffixes` treats every dot as an extension boundary, so a source folder
    named `Проект v1.2` would yield the extension `.2.7z` and the deduplicated
    name `Проект v1_002.2.7z`. Only the compound suffixes this tool actually
    produces are recognised; everything else falls back to a single suffix.
    """
    name = path.name
    lowered = name.casefold()
    for compound in ARCHIVE_COMPOUND_EXTENSIONS:
        if lowered.endswith(compound) and len(name) > len(compound):
            return name[: -len(compound)], name[-len(compound) :]
    suffix = path.suffix
    if not suffix:
        return name, ""
    return name[: -len(suffix)], suffix


def archive_sequence_candidate(path: Path, index: int) -> Path:
    stem, extension = split_archive_name(path)
    return path.with_name(f"{stem}_{index:03d}{extension}")


def unique_archive_path(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(2, 10000):
        candidate = archive_sequence_candidate(path, index)
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Could not create a unique archive name for: {path}")


def archive_base_name(source: Path) -> str:
    return source.name if source.is_dir() else (source.stem or source.name)


def sanitize_archive_name_part(value: Any) -> str:
    text = str(value or "")
    cleaned = []
    for char in text:
        if char in ARCHIVE_NAME_INVALID_CHARS or ord(char) < 32:
            cleaned.append("_")
        else:
            cleaned.append(char)
    return "".join(cleaned)


def archive_sequence_part(value: Any, sequence_number: int | None = None) -> str:
    text = str(value or "")
    if sequence_number is None or not text:
        return text
    number = str(sequence_number)
    separators = {".", "_", "-", " "}
    result: list[str] = []
    for index, char in enumerate(text):
        if char != "N":
            result.append(char)
            continue
        left_ok = index == 0 or text[index - 1] in separators
        right_ok = index == len(text) - 1 or text[index + 1] in separators
        result.append(number if left_ok and right_ok else char)
    return "".join(result)


def archive_display_name(
    source: Path,
    name_prefix: Any = "",
    name_suffix: Any = "",
    sequence_number: int | None = None,
    underscore_spaces: bool = False,
) -> str:
    base_name = archive_base_name(source)
    prefix = sanitize_archive_name_part(archive_sequence_part(name_prefix, sequence_number))
    suffix = sanitize_archive_name_part(archive_sequence_part(name_suffix, sequence_number))
    display_name = f"{prefix}{base_name}{suffix}".strip(" .")
    if underscore_spaces:
        display_name = display_name.replace(" ", "_")
    return display_name or base_name


def archive_output_path(
    source: Path,
    format_id: str,
    layout: str,
    output_root: Path | None = None,
    name_prefix: Any = "",
    name_suffix: Any = "",
    sequence_number: int | None = None,
    underscore_spaces: bool = False,
) -> Path:
    info = ARCHIVE_FORMATS[format_id]
    base_name = archive_base_name(source)
    display_name = archive_display_name(source, name_prefix, name_suffix, sequence_number, underscore_spaces)
    root = output_root or current_target_path()
    target_root = root / base_name if layout == "per_folder" else root
    target_root.mkdir(parents=True, exist_ok=True)
    return unique_archive_path(target_root / f"{display_name}{info['ext']}")


def archive_target_root(source: Path, layout: str, output_root: Path | None = None) -> Path:
    root = output_root or current_target_path()
    target_root = root / archive_base_name(source) if layout == "per_folder" else root
    target_root.mkdir(parents=True, exist_ok=True)
    return target_root


def archive_encryption_args(archive_type: str, encryption_mode: str, password: str) -> list[str]:
    if encryption_mode == "none":
        return []
    if not password:
        raise RuntimeError("Encryption password is required.")
    args = [f"-p{password}"]
    if encryption_mode == "names" and archive_type == "7z":
        args.append("-mhe=on")
    return args


def redact_archive_command(command: list[str]) -> str:
    safe: list[str] = []
    redact_next = False
    for arg in command:
        text = str(arg)
        if redact_next:
            safe.append("[REDACTED]")
            redact_next = False
            continue
        if text.lower() == "-p":
            safe.append("-p")
            redact_next = True
        elif text.lower().startswith("-p") and len(text) > 2:
            safe.append("-p[REDACTED]")
        else:
            safe.append(text)
    return subprocess.list2cmdline(safe)


def assert_encryption_supported(format_id: str, encryption_mode: str) -> None:
    mode = normalize_archive_encryption_mode(encryption_mode)
    if mode == "none":
        return
    if format_id in archive_encryption_supported_formats(mode):
        return
    if mode == "names":
        raise RuntimeError(f"Name encryption is supported only for 7Z and SFX. Unsupported format: {format_id.upper()}")
    raise RuntimeError(f"Encryption is supported only for 7Z and SFX. Unsupported format: {format_id.upper()}")


def run_archive_command(command: list[str], cwd: Path) -> int:
    add_log(f"RUN: {redact_archive_command(command)}")
    process = subprocess.Popen(
        command,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        env=rclone_process_env(),
        creationflags=hidden_subprocess_flags(),
        startupinfo=hidden_subprocess_startupinfo(),
    )
    assert process.stdout is not None
    try:
        for line in iter_process_output_lines(process.stdout):
            if line:
                add_log(line)
            if cancel_requested():
                add_log("Cancellation requested.")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                return 2
    finally:
        process.stdout.close()
    return int(process.wait() or 0)


def write_sfx_config(path: Path, title: str, install_path: str) -> None:
    escaped_title = title.replace("\\", "\\\\").replace('"', '\\"')
    lines = [
        ";!@Install@!UTF-8!",
        f'Title="{escaped_title}"',
    ]
    if install_path:
        escaped_path = install_path.replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'InstallPath="{escaped_path}"')
    lines.extend(
        [
            'GUIMode="2"',
            ";!@InstallEnd@!",
        ]
    )
    config = "\r\n".join(lines) + "\r\n"
    path.write_text(config, encoding="utf-8-sig", newline="")


def create_sfx_wrapper_archive(sevenzip: Path, sfx_path: Path, wrapper_id: str) -> Path:
    info = SFX_WRAPPER_FORMATS[wrapper_id]
    target = unique_archive_path(sfx_path.parent / f"{sfx_path.name}{info['ext']}")
    archive_type = info["type"]
    if wrapper_id == "zstd":
        exit_code = run_zstd_compress(sfx_path, target, SFX_WRAPPER_LEVEL)
        if exit_code != 0:
            raise RuntimeError(f"SFX wrapper {info['label']} failed for {sfx_path.name} [{exit_code}]")
        return target
    command = [
        str(sevenzip),
        "a",
        f"-t{archive_type}",
        "-sccUTF-8",
        str(target),
        sfx_path.name,
        *SEVENZIP_PROGRESS_ARGS,
    ]
    if archive_type != "tar":
        command.insert(3, f"-mx={SFX_WRAPPER_LEVEL}")
        command.insert(4, "-mmt=on")
    exit_code = run_archive_command(command, sfx_path.parent)
    if exit_code != 0:
        raise RuntimeError(f"SFX wrapper {info['label']} failed for {sfx_path.name} [{exit_code}]")
    return target


def create_sfx_wrapper_archives(sevenzip: Path, sfx_path: Path, wrapper_ids: list[str]) -> list[Path]:
    created: list[Path] = []
    for wrapper_id in normalize_sfx_wrapper_formats(wrapper_ids):
        add_log(f"  SFX WRAP {SFX_WRAPPER_FORMATS[wrapper_id]['label']}")
        wrapped = create_sfx_wrapper_archive(sevenzip, sfx_path, wrapper_id)
        created.append(wrapped)
        add_log(f"  SFX WRAP OK -> {wrapped}")
    return created


def archive_test_args(encryption_mode: str, password: str) -> list[str]:
    if normalize_archive_encryption_mode(encryption_mode) == "none" or not password:
        return []
    return [f"-p{password}"]


def archive_is_zstd_stream(archive_path: Path) -> bool:
    name = archive_path.name.lower()
    return name.endswith((".zst", ".zstd", ".tar.zst", ".tar.zstd"))


def archive_is_lz4_stream(archive_path: Path) -> bool:
    return archive_path.name.lower().endswith(".lz4")


def verify_created_archive(sevenzip: Path, archive_path: Path, encryption_mode: str, password: str) -> None:
    if archive_is_zstd_stream(archive_path):
        exit_code = run_zstd_test(archive_path)
        if exit_code != 0:
            raise RuntimeError(f"ZSTD verification failed for {archive_path.name} [{exit_code}]")
        add_log(f"  ZSTD TEST OK -> {archive_path}")
        return
    if archive_is_lz4_stream(archive_path):
        exit_code = run_lz4_test(archive_path)
        if exit_code != 0:
            raise RuntimeError(f"LZ4 verification failed for {archive_path.name} [{exit_code}]")
        add_log(f"  LZ4 TEST OK -> {archive_path}")
        return
    command = [
        str(sevenzip),
        "t",
        "-sccUTF-8",
        *archive_test_args(encryption_mode, password),
        str(archive_path),
        *SEVENZIP_PROGRESS_ARGS,
    ]
    exit_code = run_archive_command(command, archive_path.parent)
    if exit_code != 0:
        raise RuntimeError(f"Archive verification failed for {archive_path.name} [{exit_code}]")
    add_log(f"  TEST OK -> {archive_path}")


def create_sfx_archive(
    sevenzip: Path,
    source: Path,
    target: Path,
    level: str,
    temp_root: Path,
    sfx_env: str,
    sfx_path: str,
    encryption_mode: str,
    password: str,
    sfx_wrappers: list[str],
) -> list[Path]:
    sfx_module = find_sfx_module(sevenzip)
    if sfx_module is None:
        raise RuntimeError("SFX module was not found in Tools\\7zip\\bin. Add 7z.sfx/7zCon.sfx/7zSD.sfx to enable SFX.")

    base_name = archive_base_name(source)
    stage_dir = temp_root / base_name / "sfx"
    stage_dir.mkdir(parents=True, exist_ok=True)
    stage_archive = stage_dir / f"{base_name}.7z"
    stage_config = stage_dir / "config.txt"
    install_path = sfx_install_path_template(sfx_env, sfx_path, base_name)

    command = [
        str(sevenzip),
        "a",
        "-t7z",
        f"-mx={level}",
        "-mmt=on",
        "-sccUTF-8",
        *archive_encryption_args("7z", encryption_mode, password),
        str(stage_archive),
        source.name,
        *SEVENZIP_PROGRESS_ARGS,
    ]
    exit_code = run_archive_command(command, source.parent)
    if exit_code != 0:
        raise RuntimeError(f"SFX payload failed for {source.name} [{exit_code}]")

    write_sfx_config(stage_config, base_name, install_path)
    with target.open("wb") as output:
        output.write(sfx_module.read_bytes())
        output.write(stage_config.read_bytes())
        output.write(stage_archive.read_bytes())
    add_log(f"  SFX INSTALL PATH -> {install_path}")
    return create_sfx_wrapper_archives(sevenzip, target, sfx_wrappers)


def create_archive_for_folder(
    sevenzip: Path,
    source: Path,
    format_id: str,
    level: str,
    layout: str,
    output_root: Path,
    temp_root: Path,
    name_prefix: str,
    name_suffix: str,
    sequence_number: int,
    underscore_spaces: bool,
    sfx_env: str,
    sfx_path: str,
    encryption_mode: str,
    password: str,
    sfx_wrappers: list[str],
) -> list[Path]:
    info = ARCHIVE_FORMATS[format_id]
    assert_encryption_supported(format_id, encryption_mode)
    target = archive_output_path(source, format_id, layout, output_root, name_prefix, name_suffix, sequence_number, underscore_spaces)
    base_name = archive_base_name(source)
    archive_type = info["type"]
    mode = info["mode"]
    wrapper_paths: list[Path] = []

    if mode == "direct":
        command = [
            str(sevenzip),
            "a",
            f"-t{archive_type}",
            f"-mx={level}",
            "-mmt=on",
            "-sccUTF-8",
            *archive_encryption_args(archive_type, encryption_mode, password),
            str(target),
            source.name,
            *SEVENZIP_PROGRESS_ARGS,
        ]
        exit_code = run_archive_command(command, source.parent)
    elif mode == "direct_tar":
        command = [
            str(sevenzip),
            "a",
            "-ttar",
            "-sccUTF-8",
            str(target),
            source.name,
            *SEVENZIP_PROGRESS_ARGS,
        ]
        exit_code = run_archive_command(command, source.parent)
    elif mode == "sfx":
        wrapper_paths = create_sfx_archive(sevenzip, source, target, level, temp_root, sfx_env, sfx_path, encryption_mode, password, sfx_wrappers)
        exit_code = 0
    else:
        stage_dir = temp_root / base_name
        stage_dir.mkdir(parents=True, exist_ok=True)
        stage_tar = stage_dir / f"{base_name}.tar"
        tar_command = [
            str(sevenzip),
            "a",
            "-ttar",
            "-sccUTF-8",
            str(stage_tar),
            source.name,
            *SEVENZIP_PROGRESS_ARGS,
        ]
        exit_code = run_archive_command(tar_command, source.parent)
        if exit_code == 0:
            if format_id == "zstd":
                exit_code = run_zstd_compress(stage_tar, target, level)
            elif format_id == "lz4":
                exit_code = run_lz4_compress(stage_tar, target, level)
            else:
                compress_command = [
                    str(sevenzip),
                    "a",
                    f"-t{archive_type}",
                    f"-mx={level}",
                    "-mmt=on",
                    "-sccUTF-8",
                    str(target),
                    stage_tar.name,
                    *SEVENZIP_PROGRESS_ARGS,
                ]
                exit_code = run_archive_command(compress_command, stage_dir)

    if exit_code != 0:
        raise RuntimeError(f"{ARCHIVE_FORMATS[format_id]['label']} failed for {source.name} [{exit_code}]")
    return [target, *wrapper_paths] if mode == "sfx" else [target]


def archive_input_folders(options: dict[str, Any]) -> int:
    source_root = Path(str(options.get("source_root") or paths.input)).expanduser().resolve()
    output_root = Path(str(options.get("target_root") or paths.output)).expanduser().resolve()
    if not source_root.exists():
        raise RuntimeError(tr("source_folder_missing", path=source_root))
    if not source_root.is_dir() and not source_root.is_file():
        raise RuntimeError(f"Unsupported source path: {source_root}")
    output_root.mkdir(parents=True, exist_ok=True)

    encryption_mode = normalize_archive_encryption_mode(options.get("encryption"))
    password = str(options.get("password") or "")
    selected_formats = prune_archive_formats_for_encryption(options.get("formats", []), encryption_mode)
    if not selected_formats:
        raise RuntimeError("Select at least one archive format.")
    if encryption_mode != "none" and not password:
        raise RuntimeError("Encryption password is required.")

    sevenzip = find_7zip_executable()
    if sevenzip is None:
        installer = ROOT / "install" / "Install-Portable-7Zip.cmd"
        raise RuntimeError(f"7-Zip was not found. Install it first: {installer}")

    level = str(options.get("level") or "1")
    if level not in ARCHIVE_LEVEL_OPTIONS:
        level = "1"
    layout = "per_folder" if options.get("layout") == "per_folder" else "flat"
    name_prefix = sanitize_archive_name_part(options.get("name_prefix"))
    name_suffix = sanitize_archive_name_part(options.get("name_suffix"))
    sfx_env = str(options.get("sfx_env") or "")
    sfx_path = str(options.get("sfx_path") or "{name}").replace("<name>", "<имя>")
    sfx_wrappers = normalize_sfx_wrapper_formats(options.get("sfx_wrappers", []))
    verify_after_create = bool(options.get("verify_after_create", True))
    underscore_spaces = bool(options.get("underscore_spaces"))
    delete_source = bool(options.get("delete_source"))

    source_parent = source_root.parent if source_root.is_file() else source_root
    sources = (
        [source_root]
        if source_root.is_file()
        else sorted(
            (item for item in source_root.iterdir() if item.is_dir() or item.is_file()),
            key=lambda item: (0 if item.is_dir() else 1, item.name.casefold()),
        )
    )
    add_log("Archive source items")
    add_log(f"SOURCE: {source_root}")
    add_log(f"TARGET: {output_root}")
    add_log("FORMATS: " + ", ".join(ARCHIVE_FORMATS[item]["label"] for item in selected_formats))
    add_log(f"ENCRYPTION: {ARCHIVE_ENCRYPTION_OPTIONS[encryption_mode]['label']}")
    add_log(f"LEVEL: {level}")
    add_log(f"LAYOUT: {'folder per archive' if layout == 'per_folder' else 'flat output'}")
    if name_prefix or name_suffix:
        add_log(f"NAME: {name_prefix}<source>{name_suffix}")
    add_log(f"ARCHIVE NAME SPACES: {'underscore' if underscore_spaces else 'keep'}")
    if "sfx" in selected_formats:
        sfx_display = sfx_path_display(sfx_env, sfx_path)
        add_log(f"SFX PATH: {sfx_display if sfx_display else 'not set'}")
        if sfx_display:
            add_log(f"SFX SAMPLE: {resolve_sfx_extract_path(sfx_env, sfx_path)}")
        if sfx_wrappers:
            add_log("SFX WRAPPERS: " + ", ".join(SFX_WRAPPER_FORMATS[item]["label"] for item in sfx_wrappers))
    add_log(f"VERIFY AFTER CREATE: {'yes' if verify_after_create else 'no'}")
    add_log(f"DELETE SOURCE: {'yes' if delete_source else 'no'}")
    add_log(f"7-ZIP: {sevenzip}")

    if not sources:
        add_log("No folders or files found in source.")
        return 0

    total = len(sources) * len(selected_formats)
    done = 0
    temp_root = paths.workspace / "_archive_tmp" / datetime.now().strftime("%Y%m%d_%H%M%S")
    try:
        for source_index, source in enumerate(sources, start=1):
            if cancel_requested():
                add_log("Cancellation requested.")
                return 2
            source_resolved = source.resolve()
            if source_resolved.parent != source_parent:
                raise RuntimeError(f"Refusing unexpected source item: {source}")
            source_kind = "DIR" if source.is_dir() else "FILE"
            add_log(f"[{source_index}/{len(sources)}] {source_kind} {source.name}")
            created: list[Path] = []
            for format_id in selected_formats:
                if cancel_requested():
                    add_log("Cancellation requested.")
                    return 2
                add_log(f"  {ARCHIVE_FORMATS[format_id]['label']}")
                archive_paths = create_archive_for_folder(
                    sevenzip,
                    source,
                    format_id,
                    level,
                    layout,
                    output_root,
                    temp_root,
                    name_prefix,
                    name_suffix,
                    source_index,
                    underscore_spaces,
                    sfx_env,
                    sfx_path,
                    encryption_mode,
                    password,
                    sfx_wrappers if format_id == "sfx" else [],
                )
                created.extend(archive_paths)
                done += 1
                set_progress(done / max(1, total))
                for archive_path in archive_paths:
                    add_log(f"  OK -> {archive_path}")
                if verify_after_create:
                    for archive_path in archive_paths:
                        add_log(f"  TEST -> {archive_path}")
                        verify_created_archive(sevenzip, archive_path, encryption_mode, password)
            if delete_source and created:
                add_log(f"  DELETE SOURCE -> {source}")
                if source.is_dir():
                    shutil.rmtree(source)
                else:
                    source.unlink()
        add_log(f"Done: {done} archive(s).")
        return 0
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


async def start_archive_input_folders(options: dict[str, Any] | None = None) -> None:
    if state["running"]:
        safe_notify(tr("another_running"), "warning")
        return

    if options is None:
        options = {
            "formats": list(archive_state.get("formats") or []),
            "encryption": normalize_archive_encryption_mode(archive_state.get("encryption")),
            "password": str(archive_state.get("password") or ""),
            "level": str(archive_state.get("level") or "1"),
            "layout": str(archive_state.get("layout") or "flat"),
            "name_prefix": str(archive_state.get("name_prefix") or ""),
            "name_suffix": str(archive_state.get("name_suffix") or ""),
            "sfx_env": str(archive_state.get("sfx_env") or ""),
            "sfx_path": str(archive_state.get("sfx_path") or "{name}"),
            "sfx_wrappers": normalize_sfx_wrapper_formats(archive_state.get("sfx_wrappers", [])),
            "verify_after_create": bool(archive_state.get("verify_after_create", True)),
            "underscore_spaces": bool(archive_state.get("underscore_spaces")),
            "delete_source": bool(archive_state.get("delete_source")),
        }
    options["source_root"] = str(current_source_path())
    options["target_root"] = str(current_target_path())
    options["encryption"] = normalize_archive_encryption_mode(options.get("encryption"))
    options["formats"] = prune_archive_formats_for_encryption(options.get("formats", []), options["encryption"])
    if not options["formats"]:
        safe_notify("Select at least one archive format.", "warning")
        return
    if options["encryption"] != "none" and not str(options.get("password") or ""):
        safe_notify("Encryption password is required.", "warning")
        return
    if options["delete_source"]:
        with ui.dialog() as dialog, ui.card().classes("rounded-lg"):
            ui.label(tr("confirm_title")).classes("text-base font-semibold")
            post_check = " and archive verification" if bool(options.get("verify_after_create", True)) else ""
            ui.label(f"Source folders and files in {options['source_root']} will be deleted after successful archive creation{post_check}.").classes("text-sm text-gray-400")
            ui.label(tr("confirm_note")).classes("text-xs text-gray-500")
            with ui.row().classes("gap-2"):
                ui.button(tr("cancel"), on_click=dialog.close).props("dense flat")
                ui.button(tr("run"), on_click=lambda: dialog.submit(True)).props("dense color=negative")
        confirmed = await dialog
        if not confirmed:
            return

    title = "Archive source"
    state.update(
        {
            "running": True,
            "cancel": False,
            "progress": 0.02,
            "status": f"{tr('running')}: {title}",
            "lines": [],
            "log_version": int(state["log_version"]) + 1,
            "terminal_epoch": int(state.get("terminal_epoch", 0)) + 1,
            "terminal_total_lines": 0,
            "exit_code": None,
        }
    )
    try:
        exit_code = await run.io_bound(archive_input_folders, options)
        state["exit_code"] = exit_code
        state["progress"] = 1.0
        state["status"] = f"{tr('done')}: {title} [{exit_code}]"
        safe_notify(tr("operation_done") if exit_code == 0 else tr("operation_failed", code=exit_code), "positive" if exit_code == 0 else "negative")
    except Exception as exc:
        state["exit_code"] = 1
        state["progress"] = max(float(state["progress"]), 0.98)
        state["status"] = f"{tr('error')}: {exc}"
        add_log(f"ERROR: {exc.__class__.__name__}: {exc}")
        safe_notify(str(exc), "negative")
    finally:
        state["running"] = False


def normalize_network_mode(mode: Any) -> str:
    text = str(mode or "robocopy_safe").strip().lower()
    return text if text in NETWORK_OPERATION_MODES else "robocopy_safe"




def pending_needs_peazip_tools(pending: CommandNode | None) -> bool:
    if pending is None:
        return False
    if pending.id == "ui_archive_input_folders":
        return True
    if pending.id != "ui_network_operations":
        return False
    values = state.setdefault("field_values", {})
    panel = normalize_network_panel(values.get("network_panel", "transfer"))
    mode = normalize_network_mode(values.get("network_mode", "robocopy_safe"))
    return panel == "transfer" and mode in NETWORK_ARCHIVE_TOOL_MODES


def current_peazip_dependency(pending: CommandNode | None) -> tuple[str, Path | None]:
    if pending is not None and pending.id == "ui_archive_input_folders":
        return "7Z", find_7zip_executable()
    values = state.setdefault("field_values", {})
    mode = normalize_network_mode(values.get("network_mode", "robocopy_safe"))
    if mode == "open_archive":
        return "PEAZIP", find_peazip_executable()
    return "7Z", find_7zip_executable()










def archive_compression_level(value: Any) -> str:
    level = str(value or "1").strip()
    return level if level in ARCHIVE_LEVEL_OPTIONS else "1"


def unique_folder_path(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(2, 10000):
        candidate = path.with_name(f"{path.name}_{index:03d}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Could not create a unique folder name for: {path}")










def clear_stage_archive(local_archive: Path, reason: str) -> None:
    """Drop the local staging archive.

    `7z a` appends to an existing archive instead of replacing it, so a stage file
    left behind by an interrupted run would end up inside the next archive without
    any error: the local/remote SHA256 pair still matches and `7z t` still passes.
    The stage folder is working space, so the file is also removed once the transfer
    has been verified instead of being kept as a second full-size copy.
    """
    if not local_archive.exists():
        return
    if not local_archive.is_file():
        raise RuntimeError(f"Stage archive path is not a file: {local_archive}")
    try:
        local_archive.unlink()
    except OSError as exc:
        add_log(f"STAGE WARNING: could not remove {local_archive} ({exc}).")
        return
    add_log(f"STAGE CLEANUP: removed {local_archive.name} ({reason}).")














def run_network_command(
    command: list[str],
    cwd: Path,
    *,
    success_codes: set[int],
    warning_codes: set[int] | None = None,
    label: str = "",
) -> int:
    warning_codes = warning_codes or set()
    add_log(f"RUN: {subprocess.list2cmdline(command)}")
    process = subprocess.Popen(
        command,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        env=rclone_process_env(),
        creationflags=hidden_subprocess_flags(),
        startupinfo=hidden_subprocess_startupinfo(),
    )
    assert process.stdout is not None
    try:
        for line in iter_process_output_lines(process.stdout):
            if line:
                add_log(line)
            if cancel_requested():
                add_log("Cancellation requested.")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                return 2
    finally:
        process.stdout.close()

    exit_code = int(process.wait() or 0)
    add_log(f"EXIT CODE: {exit_code}")
    if exit_code in warning_codes:
        add_log(f"WARNING: {label or 'command'} finished with non-fatal warning code {exit_code}.")
        return exit_code
    if exit_code not in success_codes:
        raise RuntimeError(f"{label or 'Command'} failed with exit code {exit_code}.")
    return exit_code




def sevenzip_create_archive(sevenzip: Path, source: Path, archive_path: Path, level: str, solid: bool) -> int:
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        str(sevenzip),
        "a",
        "-t7z",
        f"-mx={level}",
        "-mmt=on",
        "-ms=on" if solid else "-ms=off",
        "-sccUTF-8",
        str(archive_path),
        source.name if source.name else str(source),
        *SEVENZIP_PROGRESS_ARGS,
    ]
    return run_network_command(command, source.parent if source.name else ROOT, success_codes={0, 1}, warning_codes={1}, label="7Z archive")


def sevenzip_test_archive(sevenzip: Path, archive_path: Path) -> int:
    command = [
        str(sevenzip),
        "t",
        str(archive_path),
        *SEVENZIP_PROGRESS_ARGS,
    ]
    return run_network_command(command, ROOT, success_codes={0}, label="7Z test")


def sevenzip_extract_archive(sevenzip: Path, archive_path: Path, extract_root: Path) -> int:
    extract_root.mkdir(parents=True, exist_ok=True)
    command = [
        str(sevenzip),
        "x",
        str(archive_path),
        f"-o{extract_root}",
        "-y",
        *SEVENZIP_PROGRESS_ARGS,
    ]
    return run_network_command(command, ROOT, success_codes={0, 1}, warning_codes={1}, label="7Z extract")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(8 * 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            if cancel_requested():
                raise RuntimeError("Cancellation requested.")
    return digest.hexdigest()


def write_sha256_log(archive_path: Path, digest: str, label: str) -> Path:
    paths.logs.mkdir(parents=True, exist_ok=True)
    safe_name = sanitize_archive_name_part(archive_path.name).strip(" .") or "archive"
    target = unique_archive_path(paths.logs / f"{safe_name}.{label}.sha256.txt")
    target.write_text(f"{digest}  {archive_path}\n", encoding="utf-8")
    add_log(f"SHA256 {label}: {digest}")
    add_log(f"SHA256 LOG {label}: {target}")
    return target














def normalize_network_panel(value: Any) -> str:
    text = str(value or "transfer").strip().lower()
    return text if text in NETWORK_PANELS else "transfer"


def current_windows_principal() -> str:
    user = str(os.environ.get("USERNAME") or "").strip()
    domain = str(os.environ.get("USERDOMAIN") or "").strip()
    if domain and user:
        return f"{domain}\\{user}"
    return user or "Users"


def smb_share_prefix(value: Any) -> str:
    text = str(value or "Audion").strip()
    cleaned = "".join(char if char.isalnum() else "_" for char in text).strip("_")
    return cleaned or "Audion"


def smb_share_name(prefix: Any, role: str) -> str:
    role_label = "Source" if role == "source" else "Target"
    name = f"{smb_share_prefix(prefix)}_{role_label}"
    return name[:80]


def smb_share_unc(name: str) -> str:
    computer = str(os.environ.get("COMPUTERNAME") or socket.gethostname() or "localhost").strip()
    return f"\\\\{computer}\\{name}"


def path_is_unc(path: Path) -> bool:
    text = str(path)
    return text.startswith("\\\\") or str(path.anchor).startswith("\\\\")


def path_is_mapped_network_drive(path: Path) -> bool:
    if os.name != "nt" or path_is_unc(path):
        return False
    drive = str(path.drive or "").strip()
    if not drive:
        return False
    result = subprocess.run(
        ["net", "use", drive],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        creationflags=hidden_subprocess_flags(),
        startupinfo=hidden_subprocess_startupinfo(),
    )
    return result.returncode == 0


def shareable_local_folder(role: str) -> Path:
    role_clean = str(role or "").strip().lower()
    if role_clean == "source":
        path = current_source_path().expanduser()
        if not path.exists():
            raise RuntimeError(tr("source_folder_missing", path=path))
    elif role_clean == "target":
        path = current_target_path().expanduser()
        path.mkdir(parents=True, exist_ok=True)
    else:
        raise RuntimeError(f"Unsupported SMB share role: {role}")
    if path_is_unc(path):
        raise RuntimeError(f"SMB share can be created only for a local folder, not UNC path: {path}")
    if path_is_mapped_network_drive(path):
        raise RuntimeError(f"SMB share can be created only for a local folder, not mapped network drive: {path}")
    if not path.is_dir():
        raise RuntimeError(f"SMB share path is not a folder: {path}")
    return path.resolve()


def resolve_network_powershell() -> list[str]:
    if shutil.which("powershell.exe"):
        return ["powershell.exe", "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command"]
    bundled_pwsh = paths.system_core / "powershell" / "pwsh.exe"
    if bundled_pwsh.exists():
        return [str(bundled_pwsh), "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command"]
    if shutil.which("pwsh.exe"):
        return ["pwsh.exe", "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command"]
    raise RuntimeError("PowerShell was not found for SMB share operations.")


def run_smb_powershell(script: str, label: str) -> int:
    command = [*resolve_network_powershell(), script]
    return run_network_command(command, ROOT, success_codes={0}, label=label)


def smb_principal(options: dict[str, Any]) -> str:
    principal = str(options.get("share_principal") or "").strip()
    return principal or current_windows_principal()


def create_or_update_smb_share(role: str, access: str, options: dict[str, Any]) -> int:
    folder = shareable_local_folder(role)
    prefix = options.get("share_prefix")
    name = smb_share_name(prefix, role)
    principal = smb_principal(options)
    access_right = "Change" if access == "Change" else "Read"
    access_param = "ChangeAccess" if access_right == "Change" else "ReadAccess"
    add_log(f"SMB SHARE {role.upper()} {access_right.upper()}")
    add_log(f"PATH: {folder}")
    add_log(f"NAME: {name}")
    add_log(f"UNC: {smb_share_unc(name)}")
    add_log(f"PRINCIPAL: {principal}")
    if access_right == "Change":
        add_log("WARNING: Share grants write/change access. NTFS permissions are not modified.")
    else:
        add_log("NOTE: Share grants read access. NTFS permissions are not modified.")
    script = f"""
$ErrorActionPreference = 'Stop'
$name = {ps_single_quote(name)}
$path = {ps_single_quote(str(folder))}
$principal = {ps_single_quote(principal)}
$right = {ps_single_quote(access_right)}
$existing = Get-SmbShare -Name $name -ErrorAction SilentlyContinue
if ($null -eq $existing) {{
    New-SmbShare -Name $name -Path $path -{access_param} $principal | Out-Null
}} elseif ([string]$existing.Path -ne $path) {{
    throw "Share '$name' already exists at '$($existing.Path)'. Remove it first or change the prefix."
}}
Get-SmbShareAccess -Name $name | Where-Object {{ $_.AccountName -eq $principal }} | ForEach-Object {{
    Revoke-SmbShareAccess -Name $name -AccountName $_.AccountName -Force
}}
Grant-SmbShareAccess -Name $name -AccountName $principal -AccessRight $right -Force | Out-Null
Write-Host "SMB SHARE READY: \\\\$env:COMPUTERNAME\\$name"
Write-Host "PATH: $path"
Write-Host "PRINCIPAL: $principal"
Write-Host "ACCESS: $right"
"""
    return run_smb_powershell(script, f"SMB share {role}")


def remove_smb_share(role: str, options: dict[str, Any]) -> int:
    name = smb_share_name(options.get("share_prefix"), role)
    add_log(f"SMB SHARE REMOVE {role.upper()}")
    add_log(f"NAME: {name}")
    script = f"""
$ErrorActionPreference = 'Stop'
$name = {ps_single_quote(name)}
$existing = Get-SmbShare -Name $name -ErrorAction SilentlyContinue
if ($null -eq $existing) {{
    Write-Host "SMB SHARE NOT FOUND: $name"
}} else {{
    Remove-SmbShare -Name $name -Force
    Write-Host "SMB SHARE REMOVED: $name"
}}
"""
    return run_smb_powershell(script, f"Remove SMB share {role}")


def show_smb_share_paths(options: dict[str, Any]) -> int:
    prefix = options.get("share_prefix")
    names = [smb_share_name(prefix, "source"), smb_share_name(prefix, "target")]
    add_log("SMB SHARE PATHS")
    for role, name in (("source", names[0]), ("target", names[1])):
        add_log(f"{role.upper()} EXPECTED: {smb_share_unc(name)}")
    script_names = "@(" + ", ".join(ps_single_quote(name) for name in names) + ")"
    script = f"""
$ErrorActionPreference = 'Stop'
foreach ($name in {script_names}) {{
    $share = Get-SmbShare -Name $name -ErrorAction SilentlyContinue
    if ($null -eq $share) {{
        Write-Host "NOT SHARED: $name"
        continue
    }}
    Write-Host "SHARED: \\\\$env:COMPUTERNAME\\$name"
    Write-Host "PATH: $($share.Path)"
    Get-SmbShareAccess -Name $name | ForEach-Object {{
        Write-Host ("ACCESS: {{0}} {{1}}" -f $_.AccountName, $_.AccessRight)
    }}
}}
"""
    return run_smb_powershell(script, "Show SMB shares")


def smb_share_operations(options: dict[str, Any]) -> int:
    action = str(options.get("share_action") or "show_paths").strip().lower()
    if action in {"show_paths", ""}:
        return show_smb_share_paths(options)
    if action in {"remove_source", "remove_target"}:
        return remove_smb_share("source" if action.endswith("source") else "target", options)
    item = SMB_SHARE_ACTIONS.get(action)
    if not item:
        raise RuntimeError(f"Unsupported SMB share action: {action}")
    role = str(item.get("role") or "")
    access = str(item.get("access") or "Read")
    return create_or_update_smb_share(role, access, options)






def current_rclone_options() -> dict[str, Any]:
    fields = rclone_cache_fields()
    return {
        **fields,
        "sftp_password": str(state.setdefault("field_values", {}).get("rclone_sftp_password") or ""),
        "source_path": str(current_source_path()),
        "target_path": str(current_target_path()),
    }


def update_rclone_progress_from_line(line: str, title: str) -> None:
    parsed = parse_rclone_progress_line(line)
    if not parsed:
        return
    progress = state.setdefault("rclone_progress", {})
    if not isinstance(progress, dict):
        progress = {}
        state["rclone_progress"] = progress
    progress.update(parsed)

    percent = progress.get("percent", progress.get("check_percent", progress.get("file_percent")))
    parts = [f"Rclone: {title}"]
    if percent is not None:
        try:
            percent_value = max(0.0, min(100.0, float(percent)))
            state["progress"] = percent_value / 100.0
            parts.append(f"{percent_value:.1f}%")
        except (TypeError, ValueError):
            pass
    if progress.get("transferred"):
        parts.append(str(progress["transferred"]))
    if progress.get("speed"):
        parts.append(str(progress["speed"]))
    if progress.get("eta"):
        parts.append(f"ETA {progress['eta']}")
    if progress.get("checks"):
        parts.append(f"checks {progress['checks']}")
    if progress.get("files"):
        parts.append(f"files {progress['files']}")
    if progress.get("retries") is not None:
        parts.append(f"retries {progress['retries']}")
    if progress.get("errors") is not None:
        parts.append(f"errors {progress['errors']}")
    state["status"] = " | ".join(parts)


def rclone_process_env() -> dict[str, str]:
    """The environment an rclone run needs, including the config passphrase.

    Through the environment rather than the command line: an argument is visible
    in the process list and in every log line that echoes the command, and the
    config is the one file on a travelling disk that must stay unreadable.

    The phrase is held for the session only — never written to the command cache
    and never to a file.

    The S3 credentials file travels the same way, and not by choice: rclone keeps
    `shared_credentials_file` in the config but the AWS SDK chain behind
    `env_auth = true` reads its own variable, so a named profile is only found
    when the path is in the environment too.
    """
    extra = dict(config_passphrase_env(state.get("rclone_config_passphrase")))
    try:
        config_path = rclone_config_file_for_scope(ROOT, current_rclone_options())
        if config_path and config_path.is_file():
            extra.update(s3_credentials_env(config_path.read_text(encoding="utf-8", errors="replace")))
    except (OSError, ValueError):
        pass  # an unreadable or unset config is reported by rclone itself, in its own words
    return utf8_subprocess_env(extra)


def run_rclone_command(command: list[str], cwd: Path, *, label: str = "Rclone", raise_on_failure: bool = True) -> int:
    add_log(f"RUN: {redact_rclone_line(command_display(command))}")
    process = subprocess.Popen(
        command,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        env=rclone_process_env(),
        creationflags=hidden_subprocess_flags(),
        startupinfo=hidden_subprocess_startupinfo(),
    )
    assert process.stdout is not None
    try:
        for line in iter_process_output_lines(process.stdout):
            if line:
                safe_line = redact_rclone_line(line)
                add_log(safe_line)
                update_rclone_progress_from_line(safe_line, label)
            if cancel_requested():
                add_log("Cancellation requested.")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                return 2
    finally:
        process.stdout.close()

    exit_code = int(process.wait() or 0)
    add_log(f"EXIT CODE: {exit_code}")
    # Robocopy answers in a bitmask where anything below 8 is success, so a
    # caller that runs both engines has to judge the number itself.
    if exit_code != 0 and raise_on_failure:
        raise RuntimeError(f"{label} failed with exit code {exit_code}.")
    return exit_code


def run_logged_command(command: list[str], cwd: Path, *, label: str = "Command") -> int:
    add_log(f"RUN: {command_display(command)}")
    process = subprocess.Popen(
        command,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        env=rclone_process_env(),
        creationflags=hidden_subprocess_flags(),
        startupinfo=hidden_subprocess_startupinfo(),
    )
    assert process.stdout is not None
    try:
        for line in iter_process_output_lines(process.stdout):
            if line:
                add_log(line)
            if cancel_requested():
                add_log("Cancellation requested.")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                return 2
    finally:
        process.stdout.close()
    exit_code = int(process.wait() or 0)
    add_log(f"EXIT CODE: {exit_code}")
    # Robocopy answers in a bitmask where anything below 8 is success, so a
    # caller that runs both engines has to judge the number itself.
    if exit_code != 0 and raise_on_failure:
        raise RuntimeError(f"{label} failed with exit code {exit_code}.")
    return exit_code


def launch_visible_rclone_command(command: list[str], cwd: Path, *, label: str = "Rclone") -> int:
    add_log(f"OPEN CONSOLE: {redact_rclone_line(command_display(command))}")
    if os.name == "nt":
        flags = int(getattr(subprocess, "CREATE_NEW_CONSOLE", 0))
        subprocess.Popen(
            command,
            cwd=str(cwd),
            env=utf8_subprocess_env(),
            creationflags=flags,
        )
    else:
        subprocess.Popen(command, cwd=str(cwd), env=utf8_subprocess_env())
    add_log(f"{label} interactive process was opened in a visible console.")
    return 0


def read_rclone_remote_names(rclone: Path, options: dict[str, Any]) -> list[str]:
    process = subprocess.run(
        [str(rclone), *rclone_global_config_args(ROOT, options, ensure_dirs=True), "listremotes"],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=rclone_process_env(),
        creationflags=hidden_subprocess_flags(),
        startupinfo=hidden_subprocess_startupinfo(),
        check=False,
    )
    return parse_listremotes_output(process.stdout)


def read_rclone_remote_backends(rclone: Path, options: dict[str, Any]) -> dict[str, Any]:
    """What kind of storage each saved remote is, from rclone's own config dump.

    The route line needs this and nothing else can supply it: two remotes on the
    same service can be copied between inside that service, and the only way to
    know they are on the same service is the backend rclone recorded.

    Read beside the remote list and cached with it, so it costs one call per
    change to the config rather than one per redraw.
    """
    process = subprocess.run(
        [str(rclone), *rclone_global_config_args(ROOT, options, ensure_dirs=True), "config", "dump"],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=rclone_process_env(),
        creationflags=hidden_subprocess_flags(),
        startupinfo=hidden_subprocess_startupinfo(),
        check=False,
    )
    return parse_config_dump(process.stdout)


def invalidate_rclone_remote_cache() -> None:
    state["rclone_remotes"] = None
    state["rclone_config_encrypted"] = None


def rclone_remote_names() -> list[str]:
    """Remote names from the active config, cached so a GUI refresh costs nothing."""
    options = current_rclone_options()
    rclone = find_rclone_executable(ROOT)
    config_file = rclone_config_file_for_scope(ROOT, options)
    try:
        stamp = str(config_file.stat().st_mtime_ns) if config_file is not None and config_file.exists() else "0"
    except OSError:
        stamp = "0"
    key = "" if rclone is None else "|".join([str(rclone), *rclone_global_config_args(ROOT, options), stamp])
    cached = state.get("rclone_remotes")
    if isinstance(cached, dict) and cached.get("key") == key:
        return list(cached.get("names", []))
    names: list[str] = []
    backends: dict[str, Any] = {}
    if rclone is not None:
        try:
            names = read_rclone_remote_names(rclone, options)
        except Exception:
            names = []
        try:
            backends = read_rclone_remote_backends(rclone, options)
        except Exception:
            backends = {}
    state["rclone_remotes"] = {"key": key, "names": names, "backends": backends}
    return list(names)


def rclone_remote_exists(rclone: Path, remote_name: str, options: dict[str, Any]) -> bool:
    return remote_name_in(read_rclone_remote_names(rclone, options), remote_name)


def obscure_rclone_password(rclone: Path, password: str, options: dict[str, Any]) -> str:
    if not password:
        raise RuntimeError("SFTP password is required.")
    add_log("Rclone obscure: password sent through stdin; clear text is not logged.")
    add_log("SECURITY: rclone obscure is reversible obfuscation, not encrypted config protection.")
    process = subprocess.Popen(
        [str(rclone), *rclone_global_config_args(ROOT, options, ensure_dirs=True), "obscure", "-"],
        cwd=str(ROOT),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=rclone_process_env(),
        creationflags=hidden_subprocess_flags(),
        startupinfo=hidden_subprocess_startupinfo(),
    )
    stdout, stderr = process.communicate(password + "\n")
    if process.returncode:
        raise RuntimeError(f"rclone obscure failed: {str(stderr or '').strip()}")
    obscured = str(stdout or "").strip().splitlines()[0].strip() if stdout else ""
    if not obscured:
        raise RuntimeError("rclone obscure did not return an obscured password.")
    return obscured


def sftp_remote_endpoint_label(options: dict[str, Any]) -> str:
    user = normalize_server_user(options.get("sftp_user"))
    host = normalize_server_host(options.get("sftp_host"))
    port = normalize_server_port(options.get("sftp_port"))
    path = str(options.get("sftp_remote_path") or "").strip() or "/"
    return f"sftp://{user}@{host}:{port}{path if path.startswith('/') else '/' + path}"


def run_rclone_create_sftp_remote(options: dict[str, Any]) -> int:
    rclone = find_rclone_executable(ROOT)
    if rclone is None:
        raise RuntimeError("rclone.exe was not found. Install rclone or place it into Tools\\rclone\\rclone.exe.")

    remote_name = normalize_remote_name(options.get("auth_remote_name") or "server")
    user = normalize_server_user(options.get("sftp_user"))
    host = normalize_server_host(options.get("sftp_host"))
    port = normalize_server_port(options.get("sftp_port"))
    auth_method = normalize_sftp_auth_method(options.get("sftp_auth_method"))
    known_hosts = require_sftp_known_hosts_file(options.get("sftp_known_hosts_file"))
    key_file = normalize_optional_file(options.get("sftp_key_file"))
    log_file = rclone_log_path(paths.logs, "remote_create_sftp")

    exists = rclone_remote_exists(rclone, remote_name, options)
    command = [
        str(rclone),
        *rclone_global_config_args(ROOT, options, ensure_dirs=True),
        "--log-file",
        str(log_file),
        "--log-level",
        normalize_log_level(options.get("log_level")),
        "config",
        "update" if exists else "create",
        remote_name,
    ]
    if not exists:
        command.append("sftp")
    else:
        command.extend(["type", "sftp"])
    command.extend(["host", host, "user", user, "port", port])

    if auth_method == "agent":
        command.extend(["key_use_agent", "true"])
    elif auth_method == "key_file":
        if not key_file:
            raise RuntimeError("SFTP key file is required.")
        command.extend(["key_file", key_file])
    elif auth_method == "password":
        obscured = obscure_rclone_password(rclone, str(options.get("sftp_password") or ""), options)
        command.extend(["pass", obscured, "--no-obscure"])

    command.extend(["known_hosts_file", known_hosts])

    add_log(f"SFTP REMOTE: {remote_name}:")
    add_log(f"CONFIG SCOPE: {normalize_config_scope(options.get('config_scope'))}")
    try:
        add_log(f"CONFIG FILE: {rclone_config_file_for_scope(ROOT, options)}")
    except Exception as exc:
        add_log(f"CONFIG FILE: ERROR: {exc}")
    add_log(f"ENDPOINT: {sftp_remote_endpoint_label(options)}")
    add_log(f"AUTH: {auth_method}; password/key passphrases are not logged.")
    result = run_rclone_command(command, ROOT, label=f"SFTP remote {remote_name}")
    if result == 0:
        secure_rclone_config_permissions(rclone_config_file_for_scope(ROOT, options))
        add_log(f"Rclone remote {'updated' if exists else 'created'}: {remote_name}:")
    return result


def transfer_run_operation(options: dict[str, Any]) -> int:
    """One master, the list of machines, one run — the section's own button.

    Everything the window has been showing — which engine, which route, which
    masks — is built here into real commands and executed. The whole plan is
    assembled before the first machine is touched, so a pair that will be refused
    is known in advance rather than discovered halfway through the list.
    """
    source = endpoint_spec(options, "source")
    targets = [transfer_target_endpoint(row) for row in transfer_target_rows()]
    operation = current_transfer_operation()

    # Packing first is a step, not a setting: the archives are made, and the
    # machines then receive those instead of the master. Until this was wired the
    # button rendered, named the format and the staging folder, and the run sent
    # the raw files anyway — a button that lies is worse than one that is missing.
    if current_transfer_pack_mode() == PACK_BEFORE and source.local_path is None:
        # Asked for and impossible: there is nothing here to archive, the files
        # are already at the far end. Skipping quietly would be the same lie the
        # button told before it was wired.
        raise RuntimeError(
            "Упаковать можно только то, что лежит на этой машине. Источник — сохранённый remote."
            if settings.language == "ru"
            else "Only what is on this machine can be packed. The source is a saved remote."
        )
    if current_transfer_pack_mode() == PACK_BEFORE and source.local_path is not None:
        staging = pack_staging_dir(ROOT, str(current_named_field_value("archive_name_prefix", "pack") or "pack"))
        add_log(f"PACK: {source.local_path} -> {staging}")
        shutil.rmtree(staging, ignore_errors=True)
        archive_code = archive_input_folders(
            {
                "source_root": str(source.local_path),
                "target_root": str(staging),
                "formats": current_named_field_value("archive_formats", ["7z"]) or ["7z"],
                "encryption": str(current_named_field_value("archive_encryption", "none") or "none"),
                "password": str(state.get("archive_password") or ""),
                "level": str(current_named_field_value("archive_level", "5") or "5"),
            }
        )
        if archive_code != 0:
            add_log(f"PACK: ОШИБКА [{archive_code}] — переносить нечего")
            set_progress(1.0)
            return archive_code
        made = sorted(p.name for p in staging.rglob("*") if p.is_file())
        add_log(f"PACK: готово, архивов {len(made)}")
        source = RcloneEndpointSpec(
            kind="workbench_source", spec=str(staging), label=str(staging), local_path=staging
        )
    masks = options.get("transfer_masks") or []
    excluded = options.get("transfer_excluded_masks") or []

    run = fan_out_commands(
        operation,
        source,
        targets,
        russian=settings.language == "ru",
        rclone_exe=str(find_rclone_executable(ROOT) or "rclone"),
        project_root=ROOT,
        dry_run=bool(current_named_field_value("run_dry", False)),
        masks=masks,
        excluded_masks=excluded,
        delete_ceiling=current_transfer_delete_ceiling(),
    )

    add_log(f"TRANSFER: {TRANSFER_OPERATIONS[operation]['label_ru' if settings.language == 'ru' else 'label']}")
    add_log(f"SOURCE: {source.label}")
    add_log(f"MACHINES: {len(run)}")
    ceiling = current_transfer_delete_ceiling()
    if ceiling:
        add_log(f"CEILING: остановлюсь, если удалений больше {ceiling}")
    if masks or excluded:
        add_log(f"MASKS: +{len(masks)} -{len(excluded)}")

    worst = 0
    for item in run:
        if cancel_requested():
            add_log("TRANSFER: остановлено по запросу")
            break
        label = f"[{item['index'] + 1}/{len(run)}] {item['target']}"
        if item["refused"]:
            add_log(f"{label}: НЕ ПОЙДЁТ — {item['refused']}")
            worst = max(worst, 1)
            continue
        add_log(f"{label}: {item['engine_label']} — {item['engine_reason']}")
        command = list(item["command"])
        if item["engine"] == ENGINE_RCLONE:
            # --config and friends are rclone's own; handing them to Robocopy is
            # how the first run came back with a fatal 16.
            command[1:1] = rclone_global_config_args(ROOT, options, ensure_dirs=True)
        code = run_rclone_command(command, ROOT, label=label, raise_on_failure=False)
        if run_succeeded(item["engine"], code):
            add_log(f"{label}: готово [{code}]")
        else:
            add_log(f"{label}: ОШИБКА [{code}]")
            worst = max(worst, code)
        set_progress((item["index"] + 1) / max(1, len(run)))

    set_progress(1.0)
    return worst


def rclone_operations(options: dict[str, Any]) -> int:
    mode = normalize_rclone_mode(options.get("mode"))
    if mode == "transfer_run":
        return transfer_run_operation(options)
    if mode == "remote_create_sftp":
        result = run_rclone_create_sftp_remote(options)
        if result == 0:
            record_rclone_command_cache(rclone_cache_fields(options))
            record_rclone_endpoint_history(options.get("sftp_user"), options.get("sftp_host"))
        set_progress(1.0)
        return result

    spec = build_rclone_command(ROOT, paths.logs, options)
    add_log(f"Rclone operations: {rclone_mode_label(mode, settings.language)}")
    add_log(f"RCLONE: {spec.command[0]}")
    add_log(f"CONFIG SCOPE: {spec.config_scope}")
    if spec.config_file is not None:
        add_log(f"CONFIG FILE: {spec.config_file}")
    if spec.cache_dir is not None:
        add_log(f"CACHE DIR: {spec.cache_dir}")
    add_log(f"LOG: {spec.log_file}")
    if spec.remote_spec:
        add_log(f"REMOTE: {spec.remote_spec or '<root>'}")
    if spec.source_spec:
        add_log(f"SOURCE ENDPOINT: {spec.source_spec}")
    if spec.target_spec:
        add_log(f"TARGET ENDPOINT: {spec.target_spec}")
    if spec.local_source is not None:
        add_log(f"WORKBENCH SOURCE: {spec.local_source}")
    if spec.local_target is not None:
        add_log(f"WORKBENCH TARGET: {spec.local_target}")
    if spec.report_file is not None:
        add_log(f"CHECK REPORT: {spec.report_file}")

    if spec.interactive:
        result = launch_visible_rclone_command(spec.command, ROOT, label=spec.title)
    else:
        result = run_rclone_command(spec.command, ROOT, label=spec.title)

    if result == 0:
        record_rclone_command_cache(rclone_cache_fields(options))
        if mode in RCLONE_SOURCE_MODES:
            remember_path("source", str(current_source_path()))
        if mode in RCLONE_TARGET_MODES:
            remember_path("target", str(current_target_path()))
    set_progress(1.0)
    return result


def select_created_rclone_remote(options: dict[str, Any]) -> None:
    """Close the loop: a remote the wizard just created becomes the selected one.

    Without this the operator finishes authorization and still has to find the new
    name and pick it by hand before anything can be copied.
    """
    created = str(options.get("auth_remote_name") or "").strip().rstrip(":")
    if not created:
        return
    invalidate_rclone_remote_cache()
    if not remote_name_in(rclone_remote_names(), created):
        return
    set_field_value("rclone_remote_name", created)
    add_log(f"Remote is now selected for transfers: {created}:")
    safe_notify(
        f"Облако {created}: подключено и выбрано."
        if settings.language == "ru"
        else f"Cloud {created}: is connected and selected.",
        "positive",
    )


async def start_rclone_operations(options: dict[str, Any]) -> None:
    if state["running"]:
        safe_notify(tr("another_running"), "warning")
        return

    mode = normalize_rclone_mode(options.get("mode"))
    title = rclone_mode_label(mode, settings.language)
    state.update(
        {
            "running": True,
            "cancel": False,
            "progress": 0.02,
            "status": f"{tr('running')}: {title}",
            "lines": [],
            "log_version": int(state["log_version"]) + 1,
            "terminal_epoch": int(state.get("terminal_epoch", 0)) + 1,
            "terminal_total_lines": 0,
            "exit_code": None,
            "rclone_progress": {},
        }
    )
    try:
        exit_code = await run.io_bound(rclone_operations, options)
        state["exit_code"] = exit_code
        state["progress"] = 1.0
        state["status"] = f"{tr('done')}: {title} [{exit_code}]"
        safe_notify(tr("operation_done") if exit_code == 0 else tr("operation_failed", code=exit_code), "positive" if exit_code == 0 else "negative")
        if exit_code == 0 and mode in {"remote_auth_wizard", "remote_create_sftp"}:
            select_created_rclone_remote(options)
    except Exception as exc:
        state["exit_code"] = 1
        state["progress"] = max(float(state["progress"]), 0.98)
        state["status"] = f"{tr('error')}: {exc}"
        add_log(f"ERROR: {exc.__class__.__name__}: {exc}")
        safe_notify(str(exc), "negative")
    finally:
        state["running"] = False
        invalidate_rclone_remote_cache()
        command_tree.refresh()


async def start_install_peazip() -> None:
    if state["running"]:
        safe_notify(tr("another_running"), "warning")
        return

    title = "Install PeaZip"
    state.update(
        {
            "running": True,
            "cancel": False,
            "progress": 0.02,
            "status": f"{tr('running')}: {title}",
            "lines": [],
            "log_version": int(state["log_version"]) + 1,
            "terminal_epoch": int(state.get("terminal_epoch", 0)) + 1,
            "terminal_total_lines": 0,
            "exit_code": None,
        }
    )
    try:
        exit_code = await run.io_bound(install_portable_peazip)
        state["exit_code"] = exit_code
        state["progress"] = 1.0
        state["status"] = f"{tr('done')}: {title} [{exit_code}]"
        safe_notify("PeaZip installed." if exit_code == 0 else tr("operation_failed", code=exit_code), "positive" if exit_code == 0 else "negative")
    except Exception as exc:
        state["exit_code"] = 1
        state["progress"] = max(float(state["progress"]), 0.98)
        state["status"] = f"{tr('error')}: {exc}"
        add_log(f"ERROR: {exc.__class__.__name__}: {exc}")
        safe_notify(str(exc), "negative")
    finally:
        state["running"] = False


async def start_install_lz4() -> None:
    if state["running"]:
        safe_notify(tr("another_running"), "warning")
        return

    title = "Install LZ4"
    state.update(
        {
            "running": True,
            "cancel": False,
            "progress": 0.02,
            "status": f"{tr('running')}: {title}",
            "lines": [],
            "log_version": int(state["log_version"]) + 1,
            "terminal_epoch": int(state.get("terminal_epoch", 0)) + 1,
            "terminal_total_lines": 0,
            "exit_code": None,
        }
    )
    try:
        exit_code = await run.io_bound(install_portable_lz4)
        state["exit_code"] = exit_code
        state["progress"] = 1.0
        state["status"] = f"{tr('done')}: {title} [{exit_code}]"
        safe_notify("LZ4 installed." if exit_code == 0 else tr("operation_failed", code=exit_code), "positive" if exit_code == 0 else "negative")
    except Exception as exc:
        state["exit_code"] = 1
        state["progress"] = max(float(state["progress"]), 0.98)
        state["status"] = f"{tr('error')}: {exc}"
        add_log(f"ERROR: {exc.__class__.__name__}: {exc}")
        safe_notify(str(exc), "negative")
    finally:
        state["running"] = False
    command_tree.refresh()


async def start_install_rclone() -> None:
    if state["running"]:
        safe_notify(tr("another_running"), "warning")
        return

    title = "Install Rclone"
    state.update(
        {
            "running": True,
            "cancel": False,
            "progress": 0.02,
            "status": f"{tr('running')}: {title}",
            "lines": [],
            "log_version": int(state["log_version"]) + 1,
            "terminal_epoch": int(state.get("terminal_epoch", 0)) + 1,
            "terminal_total_lines": 0,
            "exit_code": None,
        }
    )
    try:
        exit_code = await run.io_bound(install_portable_rclone)
        state["exit_code"] = exit_code
        state["progress"] = 1.0
        state["status"] = f"{tr('done')}: {title} [{exit_code}]"
        safe_notify("Rclone installed." if exit_code == 0 else tr("operation_failed", code=exit_code), "positive" if exit_code == 0 else "negative")
    except Exception as exc:
        state["exit_code"] = 1
        state["progress"] = max(float(state["progress"]), 0.98)
        state["status"] = f"{tr('error')}: {exc}"
        add_log(f"ERROR: {exc.__class__.__name__}: {exc}")
        safe_notify(str(exc), "negative")
    finally:
        state["running"] = False
        invalidate_rclone_remote_cache()
        command_tree.refresh()


async def start_install_system_rclone() -> None:
    if state["running"]:
        safe_notify(tr("another_running"), "warning")
        return

    title = "Install System Rclone"
    state.update(
        {
            "running": True,
            "cancel": False,
            "progress": 0.02,
            "status": f"{tr('running')}: {title}",
            "lines": [],
            "log_version": int(state["log_version"]) + 1,
            "terminal_epoch": int(state.get("terminal_epoch", 0)) + 1,
            "terminal_total_lines": 0,
            "exit_code": None,
        }
    )
    try:
        exit_code = await run.io_bound(install_system_rclone)
        state["exit_code"] = exit_code
        state["progress"] = 1.0
        state["status"] = f"{tr('done')}: {title} [{exit_code}]"
        safe_notify("System Rclone installed." if exit_code == 0 else tr("operation_failed", code=exit_code), "positive" if exit_code == 0 else "negative")
    except Exception as exc:
        state["exit_code"] = 1
        state["progress"] = max(float(state["progress"]), 0.98)
        state["status"] = f"{tr('error')}: {exc}"
        add_log(f"ERROR: {exc.__class__.__name__}: {exc}")
        safe_notify(str(exc), "negative")
    finally:
        state["running"] = False
        invalidate_rclone_remote_cache()
        command_tree.refresh()


def _plain_text(value: Any) -> str:
    return str(value or "").strip()


def _selected_extension_globs(parameters: dict[str, Any]) -> list[str]:
    configured_key = _plain_text(parameters.get("extension_field"))
    if configured_key:
        value = parameters.get(configured_key, [])
    else:
        value = []
        for key, item in parameters.items():
            if str(key).startswith("profile_extensions__") or key == "manual_extensions":
                value = item
                break

    if not isinstance(value, list):
        return []

    group_map = parameters.get("extension_groups", {})
    if not isinstance(group_map, dict):
        group_map = {}

    result: list[str] = []
    seen: set[str] = set()

    def append_pattern(pattern: str) -> None:
        if pattern and pattern not in seen:
            result.append(pattern)
            seen.add(pattern)

    for item in normalize_mask_tokens(parameters.get("manual_mask_text", "")):
        append_pattern(item)

    for item in value:
        pattern = _plain_text(item)
        if not pattern:
            continue
        if pattern.startswith("@group:"):
            group_id = pattern.split(":", 1)[1]
            for group_pattern in group_map.get(group_id, []):
                append_pattern(_plain_text(group_pattern))
            continue
        append_pattern(pattern)
    return result


def _extension_exclude_field_key(parameters: dict[str, Any]) -> str:
    configured_key = _plain_text(parameters.get("extension_field"))
    if configured_key:
        return f"{configured_key}_exclude"
    if "manual_extensions" in parameters:
        return "manual_extensions_exclude"
    for key in parameters:
        if str(key).startswith("profile_extensions__"):
            return f"{key}_exclude"
    return "manual_extensions_exclude"


def _selected_exclude_extension_globs(parameters: dict[str, Any]) -> list[str]:
    value = parameters.get(_plain_text(parameters.get("extension_exclude_field")) or _extension_exclude_field_key(parameters), [])
    if not isinstance(value, list):
        return []

    group_map = parameters.get("extension_groups", {})
    if not isinstance(group_map, dict):
        group_map = {}

    result: list[str] = []
    seen: set[str] = set()

    def append_pattern(pattern: str) -> None:
        if pattern and pattern not in seen:
            result.append(pattern)
            seen.add(pattern)

    for item in value:
        pattern = _plain_text(item)
        if not pattern:
            continue
        if pattern.startswith("@group:"):
            group_id = pattern.split(":", 1)[1]
            for group_pattern in group_map.get(group_id, []):
                append_pattern(_plain_text(group_pattern))
            continue
        append_pattern(pattern)
    return result


def _dedupe_patterns(items: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        pattern = str(item or "").strip()
        if not pattern:
            continue
        key = pattern.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(pattern)
    return result


def _remove_excluded_patterns(include_globs: list[str], exclude_globs: list[str]) -> list[str]:
    exclude_keys = {str(item or "").strip().casefold() for item in exclude_globs if str(item or "").strip()}
    if not exclude_keys:
        return include_globs
    return [item for item in include_globs if str(item or "").strip().casefold() not in exclude_keys]


def _parameters_for_preview(node: CommandNode) -> dict[str, Any]:
    parameters = dict(node.parameters)
    values = state.setdefault("field_values", {})
    for field in node.fields:
        if is_display_only_field(field):
            continue
        key = field_id(field)
        if key:
            default = field_default(field)
            if str(field.get("type", field.get("kind", "text"))).lower() in {"mask_text", "mask-text"}:
                parameters[key] = live_field_value(key, default)
            else:
                parameters[key] = values.get(key, default)
            if is_extension_filter_field(field, key):
                exclude_key = f"{key}_exclude"
                parameters[exclude_key] = values.get(exclude_key, field.get("exclude_default", []))
                parameters.setdefault("extension_exclude_field", exclude_key)
    return parameters


DISK_ROUTE_SERVICES = (":run_profile_command", ":run_manual_command")


def is_disk_route_node(node: Any) -> bool:
    return isinstance(node, CommandNode) and str(node.service or "").endswith(DISK_ROUTE_SERVICES)


def _node_cli_command(parameters: dict[str, Any]) -> str:
    mask_mode = _plain_text(parameters.get("mask_operation_mode")).lower()
    if mask_mode:
        return {"backup_mirror": "backup", "one_way": "sync", "two_way": "sync2", "compare": "compare"}.get(mask_mode, "compare")
    return _plain_text(parameters.get("cli_command")) or "compare"


def pending_route_context(node: CommandNode) -> dict[str, Any]:
    """Route, policy and anchor requirement of a pending disk command, without scanning."""
    parameters = _parameters_for_preview(node)
    command = _node_cli_command(parameters)
    policy_value = _plain_text(parameters.get("operation_policy"))
    try:
        policy = normalize_operation_policy(policy_value, command=command,
                                            mirror=bool(parameters.get("mirror", False)))
    except ValueError:
        policy = "copy_update"
    if command == "sync2":
        policy = "sync2"
    anchor_required = bool(parameters.get("anchor", False))
    return {
        "command": command,
        "operation_policy": policy,
        "anchor": anchor_required,
        "note": str((pair or {}).get("note", "") or ""),
        "source_root": str(current_source_path()),
        "target_root": str(current_target_path()),
        "dry_run": bool(parameters.get("dry_run", False)),
    }


def remember_plan_from_cli(data: Any) -> bool:
    """Keep the last plan head produced by the CLI so the preflight card can reuse its numbers."""
    if not isinstance(data, dict):
        return False
    lines = data.get("output_lines")
    if not isinstance(lines, list):
        return False
    text = "\n".join(str(line) for line in lines)
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return False
    try:
        payload = json.loads(text[start : end + 1])
    except (json.JSONDecodeError, ValueError):
        return False
    if not isinstance(payload, dict):
        return False
    runtime_info = payload.get("runtime") if isinstance(payload.get("runtime"), dict) else {}
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else payload.get("plan_summary")
    if not isinstance(summary, dict):
        return False
    source_root = str(payload.get("source_root") or runtime_info.get("source_root") or "")
    target_root = str(payload.get("target_root") or runtime_info.get("target_root") or "")
    if not source_root or not target_root:
        return False
    state["last_plan"] = {
        "source_root": source_root,
        "target_root": target_root,
        "mode": str(payload.get("mode") or runtime_info.get("mode") or "safe"),
        "operation_policy": str(payload.get("operation_policy") or runtime_info.get("operation_policy") or "copy_update"),
        "anchor": bool(payload.get("anchor", runtime_info.get("anchor", False))),
        "summary": summary,
        "preview": bool(payload.get("action") in {"compare", "compare_two_way"} or runtime_info.get("dry_run")),
    }
    return True


def matching_last_plan(context: dict[str, Any]) -> dict[str, Any] | None:
    last = state.get("last_plan")
    if not isinstance(last, dict):
        return None
    if not paths_equal(last.get("source_root"), context["source_root"]):
        return None
    if not paths_equal(last.get("target_root"), context["target_root"]):
        return None
    if str(last.get("operation_policy")) != context["operation_policy"]:
        return None
    return last


def pending_preflight_card(node: CommandNode) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Live anchor/space checks over the current route, planned numbers from the last preview."""
    context = pending_route_context(node)
    last = matching_last_plan(context)
    plan = {
        "source_root": context["source_root"],
        "target_root": context["target_root"],
        "operation_policy": context["operation_policy"],
        "mode": str((last or {}).get("mode") or "safe"),
        "anchor": context["anchor"] or bool((last or {}).get("anchor", False)),
        "summary": dict((last or {}).get("summary") or {}),
    }
    return build_preflight_card(plan), last


def pending_confirmation_token(node: CommandNode) -> str:
    """Token that binds an apply to the preview shown in the card, for mirror policies only."""
    context = pending_route_context(node)
    if context["command"] not in {"sync", "backup"} or context["dry_run"]:
        return ""
    if context["operation_policy"] not in {"mirror_safe", "mirror_hard"}:
        return ""
    card, last = pending_preflight_card(node)
    if last is None or not last.get("preview"):
        return ""
    return str(card["confirmation"]["token"])


def active_file_list_filter() -> tuple[Any | None, str]:
    node = state.get("pending_command")
    if not isinstance(node, CommandNode):
        return None, "all files"

    parameters = _parameters_for_preview(node)
    selected_globs = _selected_extension_globs(parameters)
    selected_exclude_globs = _selected_exclude_extension_globs(parameters)
    selected_globs = _remove_excluded_patterns(selected_globs, selected_exclude_globs)

    if selected_globs or selected_exclude_globs:
        return build_filter_spec(include_globs=selected_globs, exclude_globs=selected_exclude_globs, preset_config_path=paths.config / "sync_presets.json"), f"{node.display_title(settings.language)}: selected masks"

    return None, "all files"


def _human_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"


def _write_file_list_report(source: Path, filter_label: str, records: list[Any], stats: Any) -> Path:
    paths.report.mkdir(parents=True, exist_ok=True)
    report_path = paths.report / f"file_list_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    lines = [
        "AUDION FILE LIST",
        f"Source: {source}",
        f"Filter: {filter_label}",
        f"Matched files: {len(records)}",
        f"Scanned files: {getattr(stats, 'total_files', 0)}",
        f"Skipped by include: {getattr(stats, 'skipped_by_include', 0)}",
        f"Skipped by exclude: {getattr(stats, 'skipped_by_exclude', 0)}",
        "",
    ]
    lines.extend(f"{record.rel_path}\t{record.size}" for record in records)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def input_file_list_lines(source: Path, filter_spec: Any | None = None, filter_label: str = "all files") -> tuple[list[str], int]:
    if not source.exists():
        return [tr("file_list_missing", path=source)], 0
    if source.is_file():
        size = source.stat().st_size
        included, reason = should_include_file(source.name, size, filter_spec)
        lines = [f"Source file: {source}", f"Filter: {filter_label}"]
        if not included:
            lines.append(f"File excluded by filter: {reason or 'not matched'}")
            return lines, 0
        paths.report.mkdir(parents=True, exist_ok=True)
        report_path = paths.report / f"file_list_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        report_path.write_text(
            "\n".join(["AUDION FILE LIST", f"Source: {source}", f"Filter: {filter_label}", "Matched files: 1", "", f"{source.name}\t{size}"]) + "\n",
            encoding="utf-8",
        )
        lines.extend(["Matched files: 1", f"Full list: {report_path}", "", f"001. {_human_size(size):>10}  {source.name}"])
        return lines, 1
    if not source.is_dir():
        return [f"Unsupported source path: {source}"], 0

    bundle = scan_dir(source, project_root=ROOT, filter_spec=filter_spec)
    records = sorted(bundle.files.values(), key=lambda item: item.rel_path.casefold())
    if not records:
        return [
            f"Source: {source}",
            f"Filter: {filter_label}",
            tr("file_list_empty"),
            f"Scanned files: {bundle.stats.total_files}",
            f"Skipped by include: {bundle.stats.skipped_by_include}",
            f"Skipped by exclude: {bundle.stats.skipped_by_exclude}",
        ], 0

    report_path = _write_file_list_report(source, filter_label, records, bundle.stats)
    number_width = max(3, len(str(len(records))))
    lines = [
        f"Source: {source}",
        f"Filter: {filter_label}",
        f"Matched files: {len(records)}",
        f"Scanned files: {bundle.stats.total_files}",
        f"Skipped by include: {bundle.stats.skipped_by_include}",
        f"Skipped by exclude: {bundle.stats.skipped_by_exclude}",
        f"Full list: {report_path}",
        "",
        f"{'No.':>{number_width}}  {'Size':>10}  Path",
        f"{'-' * number_width}  {'-' * 10}  ----",
    ]
    preview_limit = TERMINAL_HISTORY_LIMIT
    for index, record in enumerate(records[:preview_limit], start=1):
        lines.append(f"{index:0{number_width}d}. {_human_size(record.size):>10}  {record.rel_path}")
    if len(records) > preview_limit:
        lines.append("")
        lines.append(f"Terminal preview limited to {preview_limit} files. Full list is saved above.")
    return lines, len(records)


async def show_input_file_list() -> None:
    if state["running"]:
        safe_notify(tr("another_running"), "warning")
        return

    title = tr("file_list")
    state.update(
        {
            "running": True,
            "cancel": False,
            "progress": 0.02,
            "status": f"{tr('running')}: {title}",
            "lines": [],
            "log_version": int(state["log_version"]) + 1,
            "terminal_epoch": int(state.get("terminal_epoch", 0)) + 1,
            "terminal_total_lines": 0,
            "exit_code": None,
        }
    )
    try:
        filter_spec, filter_label = active_file_list_filter()
        lines, count = await run.io_bound(input_file_list_lines, current_source_path(), filter_spec, filter_label)
        for line in lines:
            add_log(line)
        state["terminal_scroll_top_seq"] = int(state["log_version"])
        state["exit_code"] = 0
        state["progress"] = 1.0
        state["status"] = f"{tr('done')}: {title} [{count}]"
        safe_notify(tr("file_list_ready", count=count), "positive")
    except Exception as exc:
        state["exit_code"] = 1
        state["progress"] = max(float(state["progress"]), 0.98)
        state["status"] = f"{tr('error')}: {exc}"
        add_log(f"ERROR: {exc.__class__.__name__}: {exc}")
        safe_notify(str(exc), "negative")
    finally:
        state["running"] = False


def file_list_click_handler():
    async def handler() -> None:
        await show_input_file_list()

    return handler


async def confirm_plan_guard(guard: dict[str, Any]) -> bool:
    kind = str(guard.get("kind") or "")
    if kind == "delete_ratio":
        files_to_delete = int(guard.get("files_to_delete", 0) or 0)
        target_files = int(guard.get("target_files", 0) or 0)
        ratio = float(guard.get("ratio", 0.0) or 0.0)
        title = tr("guard_delete_ratio_title")
        body = tr("guard_delete_ratio_body", n=files_to_delete, m=target_files, p=round(ratio * 100))
    elif kind == "filtered_hard":
        title = tr("guard_filtered_hard_title")
        body = tr("guard_filtered_hard_body")
    else:
        return False

    with ui.dialog() as dialog, ui.card().classes("audion-dialog rounded-lg"):
        ui.label(title).classes("text-base font-semibold")
        ui.label(body).classes("text-sm text-gray-400")
        with ui.row().classes("gap-2"):
            ui.button(tr("cancel"), on_click=dialog.close).props("dense flat")
            ui.button(tr("run"), on_click=lambda: dialog.submit(True)).props("dense color=negative")
    return bool(await dialog)


def operation_with_guard_override(operation: Operation, guard: dict[str, Any]) -> Operation:
    parameters = dict(operation.parameters)
    kind = str(guard.get("kind") or "")
    if kind == "delete_ratio":
        parameters["override_delete_ratio"] = True
    elif kind == "filtered_hard":
        parameters["override_filtered_hard"] = True
    return replace(operation, kind="safe", parameters=parameters)


async def start_operation(operation: Operation) -> None:
    if state["running"]:
        safe_notify(tr("another_running"), "warning")
        return

    if operation.kind == "dangerous":
        with ui.dialog() as dialog, ui.card().classes("rounded-lg"):
            ui.label(tr("confirm_title")).classes("text-base font-semibold")
            ui.label(operation.display_description(settings.language)).classes("text-sm text-gray-400")
            ui.label(tr("confirm_note")).classes("text-xs text-gray-500")
            with ui.row().classes("gap-2"):
                ui.button(tr("cancel"), on_click=dialog.close).props("dense flat")
                ui.button(tr("run"), on_click=lambda: dialog.submit(True)).props("dense color=negative")
        confirmed = await dialog
        if not confirmed:
            return

    state.update(
        {
            "running": True,
            "cancel": False,
            "progress": 0.02,
            "status": f"{tr('running')}: {operation.display_title(settings.language)}",
            "lines": [],
            "log_version": int(state["log_version"]) + 1,
            "terminal_epoch": int(state.get("terminal_epoch", 0)) + 1,
            "terminal_total_lines": 0,
            "exit_code": None,
        }
    )
    started = time.perf_counter()
    try:
        result = await run.io_bound(
            execute_operation,
            paths,
            operation,
            add_log,
            set_progress,
            cancel_requested,
        )
        elapsed = time.perf_counter() - started
        plan_remembered = remember_plan_from_cli(result.data)
        guard = result.data.get("guard") if isinstance(result.data, dict) else None
        if not result.ok and isinstance(guard, dict):
            state["exit_code"] = 1
            state["progress"] = 1.0
            state["status"] = f"{tr('error')}: {operation.display_title(settings.language)} [1] {elapsed:.1f}s"
            state["running"] = False
            if await confirm_plan_guard(guard):
                await start_operation(operation_with_guard_override(operation, guard))
            else:
                safe_notify(result.message, "negative")
            return
        state["exit_code"] = 0 if result.ok else 1
        state["progress"] = 1.0
        state["status"] = f"{tr('done') if result.ok else tr('error')}: {operation.display_title(settings.language)} [{state['exit_code']}] {elapsed:.1f}s"
        safe_notify(result.message, "positive" if result.ok else "negative")
        if plan_remembered and is_disk_route_node(state.get("pending_command")):
            command_tree.refresh()
    except Exception as exc:
        state["exit_code"] = 1
        state["progress"] = max(float(state["progress"]), 0.98)
        state["status"] = f"{tr('error')}: {exc}"
        add_log(f"ERROR: {exc.__class__.__name__}: {exc}")
        safe_notify(str(exc), "negative")
    finally:
        state["running"] = False


def terminal_shell_options() -> dict[str, str]:
    options: dict[str, str] = {}
    bundled_pwsh = paths.system_core / "powershell" / "pwsh.exe"
    if bundled_pwsh.exists() or shutil.which("pwsh.exe"):
        options["pwsh"] = "PowerShell 7"
    options["powershell"] = "PowerShell"
    if os.name == "nt":
        options["cmd"] = "CMD"
    return options


def terminal_command_args(shell_id: str, command: str) -> list[str]:
    direct_python = direct_python_command_args(command)
    if direct_python:
        return direct_python

    # The terminal bar runs arbitrary third-party tools, so the child console is pinned to
    # UTF-8 and ANSI first. Redirected stdout otherwise falls back to the OEM code page,
    # dropping arrows and check marks, and PowerShell 7 turns colour off entirely.
    shell = str(shell_id or "powershell").strip().lower()
    if shell == "cmd":
        return ["cmd.exe", "/d", "/s", "/c", f"chcp 65001>nul & {command}"]

    payload = POWERSHELL_UTF8_PREAMBLE + command
    bundled_pwsh = paths.system_core / "powershell" / "pwsh.exe"
    if shell == "pwsh" and bundled_pwsh.exists():
        return [str(bundled_pwsh), "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", payload]
    if shell == "pwsh" and shutil.which("pwsh.exe"):
        return ["pwsh.exe", "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", payload]
    return ["powershell.exe", "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", payload]


def terminal_cwd() -> Path:
    raw = str(state.get("terminal_cwd") or ROOT).strip()
    try:
        candidate = Path(raw).expanduser().resolve()
    except OSError:
        return ROOT
    return candidate if candidate.exists() and candidate.is_dir() else ROOT


def terminal_cache() -> dict[str, Any]:
    cache = state.get("terminal_cache")
    if not isinstance(cache, dict):
        cache = load_terminal_cache()
        state["terminal_cache"] = cache
    cache["history"] = clean_terminal_commands(cache.get("history", []))
    cache["pinned"] = clean_terminal_commands(cache.get("pinned", []))
    return cache


def save_terminal_cache() -> None:
    cache = terminal_cache()
    current_command = str(state.get("terminal_command") or "").strip()
    cache["history"] = clean_terminal_commands(cache.get("history", []))
    cache["pinned"] = clean_terminal_commands(cache.get("pinned", []))
    cache["last"] = "" if terminal_command_is_sensitive(current_command) else current_command
    shell = str(state.get("terminal_shell") or "powershell").strip().lower()
    cache["shell"] = shell if shell in {"pwsh", "powershell", "cmd"} else "powershell"
    cache["cwd"] = stored_terminal_cwd(state.get("terminal_cwd"))
    TERMINAL_COMMAND_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    TERMINAL_COMMAND_HISTORY_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def remove_terminal_command_from_cache(command: str) -> None:
    command = command.strip()
    if not command:
        return
    cache = terminal_cache()
    cache["history"] = [item for item in cache["history"] if item != command]
    cache["pinned"] = [item for item in cache["pinned"] if item != command]
    if str(cache.get("last") or "").strip() == command:
        cache["last"] = ""


def remember_terminal_command(command: str) -> bool:
    command = command.strip()
    if not command:
        return False
    if terminal_command_is_sensitive(command):
        remove_terminal_command_from_cache(command)
        state["terminal_command"] = command
        save_terminal_cache()
        return False
    cache = terminal_cache()
    history = [command, *[item for item in cache["history"] if item != command]]
    cache["history"] = history[:TERMINAL_COMMAND_HISTORY_LIMIT]
    state["terminal_command"] = command
    save_terminal_cache()
    return True


def terminal_command_options() -> dict[str, str]:
    cache = terminal_cache()
    pinned = clean_terminal_commands(cache.get("pinned", []))
    history = [item for item in clean_terminal_commands(cache.get("history", [])) if item not in pinned]
    last = str(cache.get("last") or "").strip()
    current = str(state.get("terminal_command") or "").strip()
    if terminal_command_is_sensitive(last):
        last = ""
    if terminal_command_is_sensitive(current):
        current = ""
    ordered = [*pinned]
    for command in (current, last, *history):
        if command and command not in ordered:
            ordered.append(command)
    options: dict[str, str] = {}
    for command in ordered[:TERMINAL_COMMAND_HISTORY_LIMIT]:
        options[command] = terminal_command_option_label(command, command in pinned)
    if not options:
        options[""] = tr("terminal_history_empty")
    return options


def terminal_command_option_label(command: str, pinned: bool = False) -> str:
    text = " ".join(str(command or "").split())
    if len(text) > 120:
        text = f"{text[:117]}..."
    return f"PIN {text}" if pinned else text


def terminal_history_value() -> str | None:
    options = terminal_command_options()
    current = str(state.get("terminal_command") or "").strip()
    last = str(terminal_cache().get("last") or "").strip()
    for command in (current, last):
        if command and command in options:
            return command
    if "" in options:
        return ""
    return None


def terminal_command_is_pinned() -> bool:
    command = str(state.get("terminal_command") or "").strip()
    return bool(command and command in terminal_cache().get("pinned", []))


def event_value(event: Any) -> Any:
    if hasattr(event, "value"):
        return event.value
    args = getattr(event, "args", None)
    if isinstance(args, list) and args:
        return args[0]
    if isinstance(args, dict):
        return args.get("value") or args.get("inputValue") or args.get("input")
    return args


def set_terminal_command(value: Any) -> None:
    state["terminal_command"] = str(value or "").strip()
    save_terminal_cache()


def resolve_terminal_history_value(value: Any) -> str:
    value = event_value(value)
    if isinstance(value, dict):
        value = value.get("value") or value.get("label") or value.get("name") or ""
    if isinstance(value, list) and value:
        value = value[0]
    text = str(value or "").strip()
    options = terminal_command_options()
    if text in options:
        return text
    for command, label in options.items():
        if text == str(label).strip():
            return command
    return text


def select_terminal_history(value: Any) -> None:
    set_terminal_command(resolve_terminal_history_value(value))
    state["terminal_command_version"] = int(state.get("terminal_command_version", 0)) + 1


def set_terminal_shell(value: Any) -> None:
    shell = str(value or "powershell").strip().lower()
    state["terminal_shell"] = shell if shell in {"pwsh", "powershell", "cmd"} else "powershell"
    save_terminal_cache()


def set_terminal_cwd(value: Any) -> None:
    state["terminal_cwd"] = str(value or "").strip() or str(ROOT)
    state["terminal_cwd_version"] = int(state.get("terminal_cwd_version", 0)) + 1
    save_terminal_cache()


def pin_terminal_command() -> None:
    command = str(state.get("terminal_command") or "").strip()
    if not command:
        safe_notify(tr("terminal_command_required"), "warning")
        return
    if terminal_command_is_sensitive(command):
        remove_terminal_command_from_cache(command)
        save_terminal_cache()
        safe_notify(tr("terminal_sensitive_not_pinned"), "warning")
        state["terminal_command_version"] = int(state.get("terminal_command_version", 0)) + 1
        return
    cache = terminal_cache()
    cache["pinned"] = [command, *[item for item in cache["pinned"] if item != command]][:TERMINAL_COMMAND_HISTORY_LIMIT]
    remember_terminal_command(command)
    state["terminal_command_version"] = int(state.get("terminal_command_version", 0)) + 1


def unpin_terminal_command() -> None:
    command = str(state.get("terminal_command") or "").strip()
    if not command:
        safe_notify(tr("terminal_command_required"), "warning")
        return
    cache = terminal_cache()
    cache["pinned"] = [item for item in cache["pinned"] if item != command]
    if terminal_command_is_sensitive(command):
        remove_terminal_command_from_cache(command)
        save_terminal_cache()
    else:
        remember_terminal_command(command)
    state["terminal_command_version"] = int(state.get("terminal_command_version", 0)) + 1


def clear_terminal_command_history() -> None:
    cache = terminal_cache()
    cache["history"] = [item for item in cache["history"] if item in cache["pinned"]]
    cache["last"] = ""
    state["terminal_command"] = ""
    save_terminal_cache()
    safe_notify(tr("history_cleared"), "positive")
    state["terminal_command_version"] = int(state.get("terminal_command_version", 0)) + 1


def clear_terminal_command_cache() -> None:
    cache = terminal_cache()
    cache["history"] = []
    cache["pinned"] = []
    cache["last"] = ""
    state["terminal_command"] = ""
    state["terminal_command_version"] = int(state.get("terminal_command_version", 0)) + 1
    save_terminal_cache()
    safe_notify(tr("command_cache_cleared"), "positive")


def execute_terminal_command(command: str, cwd: str, shell_id: str) -> int:
    workdir = terminal_cwd()
    try:
        requested = Path(cwd).expanduser().resolve()
        if requested.exists() and requested.is_dir():
            workdir = requested
    except OSError:
        pass

    add_log(f"{workdir}> {redact_terminal_command_for_log(command)}")
    command_args = terminal_command_args(shell_id, command)
    output_kwargs = gui_subprocess_output_kwargs(command_args)
    process = subprocess.Popen(
        command_args,
        cwd=str(workdir),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        env=utf8_subprocess_env(),
        **output_kwargs,
        creationflags=hidden_subprocess_flags(),
        startupinfo=hidden_subprocess_startupinfo(),
    )

    assert process.stdout is not None
    for line in iter_process_output_lines(process.stdout):
        add_log(line)
        if cancel_requested() and process.poll() is None:
            add_log("Cancellation requested.")
            process.terminate()
            return 2
    return int(process.wait() or 0)


async def start_terminal_command() -> None:
    if state["running"]:
        safe_notify(tr("another_running"), "warning")
        return
    command = str(state.get("terminal_command") or "").strip()
    if not command:
        safe_notify(tr("terminal_command_required"), "warning")
        return
    command_saved = remember_terminal_command(command)
    if not command_saved:
        safe_notify(tr("terminal_sensitive_not_saved"), "warning")
    state["terminal_command_version"] = int(state.get("terminal_command_version", 0)) + 1

    state.update(
        {
            "running": True,
            "cancel": False,
            "progress": 0.02,
            "status": f"{tr('running')}: {redact_terminal_command_for_log(command)}",
            "lines": [],
            "log_version": int(state["log_version"]) + 1,
            "terminal_epoch": int(state.get("terminal_epoch", 0)) + 1,
            "terminal_total_lines": 0,
            "exit_code": None,
        }
    )
    started = time.perf_counter()
    try:
        exit_code = await run.io_bound(
            execute_terminal_command,
            command,
            str(state.get("terminal_cwd") or ROOT),
            str(state.get("terminal_shell") or "powershell"),
        )
        elapsed = time.perf_counter() - started
        state["exit_code"] = exit_code
        state["progress"] = 1.0
        state["status"] = f"{tr('done') if exit_code == 0 else tr('error')}: {tr('terminal_command_done')} [{exit_code}] {elapsed:.1f}s"
        safe_notify(tr("terminal_command_done") if exit_code == 0 else tr("operation_failed", code=exit_code), "positive" if exit_code == 0 else "negative")
    except Exception as exc:
        state["exit_code"] = 1
        state["progress"] = max(float(state["progress"]), 0.98)
        state["status"] = f"{tr('error')}: {exc}"
        add_log(f"ERROR: {exc.__class__.__name__}: {exc}")
        safe_notify(str(exc), "negative")
    finally:
        state["running"] = False


def terminal_run_click_handler():
    async def handler() -> None:
        await start_terminal_command()

    return handler


async def terminal_pick_cwd_click_handler() -> None:
    try:
        selected = await run.io_bound(pick_folder)
    except Exception as exc:
        safe_notify(str(exc), "negative")
        return
    if not selected:
        safe_notify(tr("picker_cancelled"), "warning")
        return
    set_terminal_cwd(str(selected[0]))


def toggle_language() -> None:
    settings.language = "en" if settings.language == "ru" else "ru"
    save_ui_settings(settings_path, settings)
    reload_ui()


def current_source_path() -> Path:
    return Path(str(state.get("workspace_source_path") or paths.input)).expanduser()


def current_target_path() -> Path:
    return Path(str(state.get("workspace_target_path") or paths.output)).expanduser()


def save_workspace_paths() -> None:
    settings.workspace_source = ""
    settings.workspace_target = ""
    save_ui_settings(settings_path, settings)


def save_workspace_path(kind: str, value: Any) -> None:
    raw_text = str(value or "").strip()
    text = str(Path(raw_text).expanduser()) if raw_text else str(default_workspace_path(kind))
    if canonical_role(kind) == "target":
        state["workspace_target_path"] = text
    else:
        state["workspace_source_path"] = text
    save_workspace_paths()


def default_workspace_path(role: str) -> Path:
    return paths.output if canonical_role(role) == "target" else paths.input


def open_file(path: Path) -> None:
    item = path.resolve()
    if item.is_dir():
        open_folder(item)
        return
    if not item.exists():
        raise FileNotFoundError(str(item))
    if os.name == "nt":
        os.startfile(str(item))  # type: ignore[attr-defined]
        return
    if sys.platform == "darwin":
        subprocess.Popen(["open", str(item)])
        return
    subprocess.Popen(["xdg-open", str(item)])


def latest_report_file() -> Path | None:
    folders: list[Path] = []
    for candidate in [current_target_path(), paths.output, paths.report]:
        if candidate not in folders:
            folders.append(candidate)
    for folder in folders:
        if not folder.exists():
            continue
        candidates: list[tuple[Path, float, int]] = []
        for item in folder.rglob("*"):
            if not item.is_file() or item.suffix.lower() not in REPORT_EXTENSIONS:
                continue
            try:
                modified = item.stat().st_mtime
            except OSError:
                continue
            candidates.append((item, modified, REPORT_EXTENSION_SCORE.get(item.suffix.lower(), 0)))
        if not candidates:
            continue
        newest = max(modified for _item, modified, _score in candidates)
        recent = [candidate for candidate in candidates if newest - candidate[1] <= 10]
        return max(recent, key=lambda candidate: (candidate[2], candidate[1]))[0]
    return None


def open_latest_report() -> Path | None:
    report_path = latest_report_file()
    if report_path is None:
        return None
    open_file(report_path)
    return report_path


def open_workspace_folder(role: str) -> None:
    folder = current_target_path() if role == "target" else current_source_path()
    if role != "target" and not folder.exists():
        raise FileNotFoundError(tr("source_folder_missing", path=folder))
    if folder.is_file():
        if os.name == "nt":
            subprocess.Popen(["explorer.exe", f"/select,{folder}"])
        else:
            open_folder(folder.parent)
        return
    open_folder(folder)


def mark_workspace_feedback(role: str, action: str) -> None:
    state["workspace_feedback"] = {"role": canonical_role(role), "action": str(action or "path")}


def _save_workbench_path(role: WorkbenchRole, value: Any) -> None:
    save_workspace_path("target" if role == "target" else "source", value)


def _workspace_feedback() -> dict[str, str]:
    value = state.get("workspace_feedback")
    return dict(value) if isinstance(value, dict) else {}


def _clear_workspace_feedback() -> None:
    state["workspace_feedback"] = {}


def absolute_project_path(path_value: Any) -> Path:
    path = Path(str(path_value or "")).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    return path


def normalized_absolute_path(path_value: Any) -> Path:
    return absolute_project_path(path_value).resolve(strict=False)


def paths_equal(left: Any, right: Any) -> bool:
    return os.path.normcase(str(normalized_absolute_path(left))) == os.path.normcase(str(normalized_absolute_path(right)))


def remove_path_tree(path: Path) -> int:
    is_junction = bool(getattr(os.path, "isjunction", lambda _path: False)(path))
    if path.is_symlink() or is_junction:
        if path.is_dir():
            path.rmdir()
        else:
            path.unlink()
        return 1
    if path.is_file():
        path.unlink()
        return 1
    if path.is_dir():
        shutil.rmtree(path)
        return 1
    return 0


def clear_directory_contents(folder: Path) -> int:
    removed = 0
    if not folder.exists():
        return removed
    for child in sorted(folder.iterdir(), key=lambda item: item.name.casefold()):
        # .gitkeep is not spared: input and output must be genuinely empty after a
        # clear, so nobody has to wonder what the leftover file is or whether it is
        # safe to delete. The folders themselves come from install\init_folders.cmd.
        removed += remove_path_tree(child)
    return removed


def validate_workspace_delete_target(path_value: Any) -> Path:
    target = normalized_absolute_path(path_value)
    if target.parent == target:
        raise RuntimeError(f"Refusing to delete a filesystem root: {target}")
    if paths_equal(target, ROOT):
        raise RuntimeError(f"Refusing to delete the project root: {target}")
    return target


def delete_workspace_path_contents(path_value: Any) -> dict[str, Any]:
    target = validate_workspace_delete_target(path_value)
    if not target.exists() and not target.is_symlink():
        return {"path": str(target), "kind": "missing", "removed": 0}
    is_junction = bool(getattr(os.path, "isjunction", lambda _path: False)(target))
    if target.is_file() or target.is_symlink() or is_junction:
        return {"path": str(target), "kind": "file", "removed": remove_path_tree(target)}
    if not target.is_dir():
        raise RuntimeError(f"Unsupported workspace path: {target}")
    return {"path": str(target), "kind": "folder", "removed": clear_directory_contents(target)}


def delete_workspace_io_contents(source: Path, target: Path) -> dict[str, Any]:
    source_result = delete_workspace_path_contents(source)
    if paths_equal(source, target):
        target_result = {"path": str(normalized_absolute_path(target)), "kind": "same", "removed": 0}
    else:
        target_result = delete_workspace_path_contents(target)
    return {"source": source_result, "target": target_result}


WORKBENCH_CONFIG = WorkbenchConfig(
    root=ROOT,
    input_path=paths.input,
    output_path=paths.output,
    history_path=paths.config / "path_history.json",
    history_limit=PATH_HISTORY_LIMIT,
)
WORKBENCH_ADAPTER = WorkbenchAdapter(
    config=WORKBENCH_CONFIG,
    current_path_callback=lambda role: current_target_path() if role == "target" else current_source_path(),
    save_path_callback=_save_workbench_path,
    language_callback=lambda: settings.language,
    translate_callback=tr,
    log_callback=add_log,
    notify_callback=safe_notify,
    reload_callback=lambda _delay=0: reload_ui(),
    busy_callback=lambda: bool(state.get("running")),
    feedback_callback=_workspace_feedback,
    set_feedback_callback=mark_workspace_feedback,
    clear_feedback_callback=_clear_workspace_feedback,
)
WORKBENCH_ADAPTER.validate()
WORKBENCH_ADAPTER.ensure_initial_history()


def canonical_workspace_pin_click_handler(role: str, pinned: bool):
    async def handler() -> None:
        path_value = str(current_target_path() if role == "target" else current_source_path())
        if not path_value:
            safe_notify(tr("path_required"), "warning")
            return
        try:
            await run.io_bound(WORKBENCH_ADAPTER.set_path_pinned, role, path_value, pinned)
            mark_workspace_feedback(role, "pin" if pinned else "unpin")
            add_log(f"{'Pinned' if pinned else 'Unpinned'} {role} path: {path_value}")
            reload_ui()
        except Exception as exc:
            add_log(f"ERROR: {exc.__class__.__name__}: {exc}")
            safe_notify(str(exc), "negative")

    return handler


def canonical_workspace_delete_path_click_handler(role: str):
    async def handler() -> None:
        if state["running"]:
            safe_notify(tr("another_running"), "warning")
            return
        path = current_target_path() if role == "target" else current_source_path()
        path_value = str(path)
        if not path_value:
            safe_notify(tr("path_required"), "warning")
            return
        external_source = role != "target" and not paths_equal(path, paths.input)
        if external_source:
            is_file = path.is_file()
            with ui.dialog() as dialog, ui.card().classes("audion-dialog rounded-lg"):
                title = "Удалить исходный файл?" if is_file else "Очистить внешний ИСТОЧНИК?"
                if settings.language != "ru":
                    title = "Delete the source file?" if is_file else "Clear the external SOURCE?"
                ui.label(title).classes("text-base font-semibold")
                warning = (
                    "Будет удалён исходный файл. Другой копии может не существовать."
                    if is_file
                    else "Будут безвозвратно удалены все файлы и вложенные папки."
                )
                if settings.language != "ru":
                    warning = (
                        "The source file will be deleted. Another copy may not exist."
                        if is_file
                        else "All files and nested folders will be permanently deleted."
                    )
                ui.label(warning).classes("text-sm text-gray-300")
                ui.label(str(normalized_absolute_path(path))).classes("max-w-3xl break-all font-mono text-xs text-gray-400")
                with ui.row().classes("gap-2"):
                    ui.button(tr("cancel"), on_click=dialog.close).props("dense flat")
                    ui.button(tr("delete_io_short"), on_click=lambda: dialog.submit(True)).props("dense color=negative")
            if not await dialog:
                return
        try:
            result = await run.io_bound(delete_workspace_path_contents, path)
            if result.get("kind") == "file":
                await run.io_bound(WORKBENCH_ADAPTER.delete_path_history, role, path_value)
                save_workspace_path("target" if role == "target" else "source", "")
            mark_workspace_feedback(role, "delete")
            add_log(
                f"Cleared {'TARGET' if role == 'target' else 'SOURCE'}: {result.get('path')} "
                f"[kind={result.get('kind')}, removed={result.get('removed', 0)}]"
            )
            reload_ui()
        except Exception as exc:
            add_log(f"ERROR: {exc.__class__.__name__}: {exc}")
            safe_notify(str(exc), "negative")

    return handler


def canonical_workspace_path_select_handler(role: str):
    async def handler(event: Any) -> None:
        path_value = str(getattr(event, "value", "") or "").strip()
        if not path_value:
            return
        save_workspace_path("target" if role == "target" else "source", path_value)
        await run.io_bound(WORKBENCH_ADAPTER.remember_path, role, path_value)
        mark_workspace_feedback(role, "path")
        add_log(f"{'TARGET' if role == 'target' else 'SOURCE'} -> {path_value}")
        reload_ui()

    return handler


def canonical_workspace_pick_click_handler(role: str):
    async def handler() -> None:
        if state["running"]:
            safe_notify(tr("another_running"), "warning")
            return
        try:
            selected = await run.io_bound(pick_folder)
        except Exception as exc:
            add_log(f"ERROR: {exc.__class__.__name__}: {exc}")
            safe_notify(str(exc), "negative")
            return
        if not selected:
            add_log(tr("picker_cancelled"))
            return
        path_value = str(selected[0])
        save_workspace_path("target" if role == "target" else "source", path_value)
        await run.io_bound(WORKBENCH_ADAPTER.remember_path, role, path_value)
        mark_workspace_feedback(role, "path")
        add_log(f"{'TARGET' if role == 'target' else 'SOURCE'} -> {path_value}")
        reload_ui()

    return handler


def canonical_workspace_open_click_handler(role: str):
    async def handler() -> None:
        try:
            await run.io_bound(open_workspace_folder, role)
            current = current_target_path() if role == "target" else current_source_path()
            add_log(f"Opened {'target' if role == 'target' else 'source'} folder: {current}")
        except Exception as exc:
            add_log(f"ERROR: {exc.__class__.__name__}: {exc}")
            safe_notify(str(exc), "negative")

    return handler


def canonical_workspace_single_file_click_handler():
    async def handler() -> None:
        if state["running"]:
            safe_notify(tr("another_running"), "warning")
            return
        try:
            selected = await run.io_bound(pick_single_file)
        except Exception as exc:
            add_log(f"ERROR: {exc.__class__.__name__}: {exc}")
            safe_notify(str(exc), "negative")
            return
        if not selected:
            add_log(tr("picker_cancelled"))
            return
        path_value = str(selected[0])
        save_workspace_path("source", path_value)
        await run.io_bound(WORKBENCH_ADAPTER.remember_path, "source", path_value)
        mark_workspace_feedback("source", "path")
        add_log(f"SOURCE FILE -> {path_value}")
        reload_ui()

    return handler


def canonical_reset_workspace_paths_click_handler():
    async def handler() -> None:
        if state["running"]:
            safe_notify(tr("another_running"), "warning")
            return
        result = await run.io_bound(WORKBENCH_ADAPTER.clear_path_history_cache_keep_pins)
        save_workspace_path("source", "")
        save_workspace_path("target", "")
        add_log(f"Workspace route reset: SOURCE -> {paths.input}")
        add_log(f"Workspace route reset: TARGET -> {paths.output}")
        add_log(
            "Workspace path cache cleared: "
            f"sources={result.get('removed_sources', 0)}, targets={result.get('removed_targets', 0)}, "
            f"pins kept={result.get('kept_pins', 0)}"
        )
        safe_notify(tr("operation_done"), "positive")
        reload_ui()

    return handler


def canonical_workspace_delete_both_click_handler():
    async def handler() -> None:
        if state["running"]:
            safe_notify(tr("another_running"), "warning")
            return
        source = current_source_path()
        target = current_target_path()
        source_external = not paths_equal(source, paths.input)
        with ui.dialog() as dialog, ui.card().classes("audion-dialog rounded-lg"):
            ui.label("Удалить содержимое I/O?" if settings.language == "ru" else "Delete I/O contents?").classes("text-base font-semibold")
            warning = (
                "Будут удалены файлы ИСТОЧНИКА и НАЗНАЧЕНИЯ. Внешний ИСТОЧНИК может быть единственным экземпляром."
                if source_external
                else "Будут удалены файлы ИСТОЧНИКА и НАЗНАЧЕНИЯ."
            )
            if settings.language != "ru":
                warning = (
                    "SOURCE and TARGET files will be deleted. The external SOURCE may be the only copy."
                    if source_external
                    else "SOURCE and TARGET files will be deleted."
                )
            ui.label(warning).classes("text-sm text-gray-300")
            ui.label(f"SOURCE: {normalized_absolute_path(source)}").classes("max-w-3xl break-all font-mono text-xs text-gray-400")
            ui.label(f"TARGET: {normalized_absolute_path(target)}").classes("max-w-3xl break-all font-mono text-xs text-gray-400")
            with ui.row().classes("gap-2"):
                ui.button(tr("cancel"), on_click=dialog.close).props("dense flat")
                ui.button(tr("delete_io_short"), on_click=lambda: dialog.submit(True)).props("dense color=negative")
        if not await dialog:
            return
        state["running"] = True
        try:
            result = await run.io_bound(delete_workspace_io_contents, source, target)
            source_result = result.get("source", {})
            target_result = result.get("target", {})
            if source_result.get("kind") == "file":
                await run.io_bound(WORKBENCH_ADAPTER.delete_path_history, "source", str(source))
                save_workspace_path("source", "")
            if target_result.get("kind") == "file":
                await run.io_bound(WORKBENCH_ADAPTER.delete_path_history, "target", str(target))
                save_workspace_path("target", "")
            add_log(
                f"Cleared SOURCE: {source_result.get('path')} "
                f"[kind={source_result.get('kind')}, removed={source_result.get('removed', 0)}]"
            )
            add_log(
                f"Cleared TARGET: {target_result.get('path')} "
                f"[kind={target_result.get('kind')}, removed={target_result.get('removed', 0)}]"
            )
            mark_workspace_feedback("source", "delete")
            reload_ui()
        except Exception as exc:
            add_log(f"ERROR: {exc.__class__.__name__}: {exc}")
            safe_notify(str(exc), "negative")
        finally:
            state["running"] = False

    return handler


WORKBENCH_RENDERER = WorkbenchRenderer(
    adapter=WORKBENCH_ADAPTER,
    handlers=WorkbenchHandlers(
        delete_path=canonical_workspace_delete_path_click_handler,
        pin_path=canonical_workspace_pin_click_handler,
        select_path=canonical_workspace_path_select_handler,
        pick_path=canonical_workspace_pick_click_handler,
        open_path=canonical_workspace_open_click_handler,
        add_file=canonical_workspace_single_file_click_handler,
        reset_paths=canonical_reset_workspace_paths_click_handler,
        delete_io=canonical_workspace_delete_both_click_handler,
        list_files=show_input_file_list,
    ),
    display_path_callback=display_path,
)


def cache_action_tooltip(action: str, subject: str) -> str:
    key = str(action or "").strip().lower()
    item = subject if subject else ("значение" if settings.language == "ru" else "value")
    if settings.language == "ru":
        tips = {
            "normalize": f"Привести {item} к аккуратному виду: убрать лишние пробелы, повторы и пустые элементы.",
            "pin": f"Закрепить текущий {item} в локальном кэше, чтобы он оставался в списке быстрых вариантов.",
            "unpin": f"Снять закрепление с текущего {item}. Сам текст не очищается, меняется только статус в кэше.",
            "delete": f"Удалить текущий {item} из локального кэша. Уже введённое значение в поле не стирается автоматически.",
            "clear": f"Очистить поле {item}. Это не удаляет закреплённые варианты из кэша.",
            "pick": f"Выбрать сохранённый {item} из локального кэша и вставить его в поле.",
        }
    else:
        tips = {
            "normalize": f"Normalize the current {item}: remove extra spaces, duplicates, and empty items.",
            "pin": f"Pin the current {item} in local cache so it stays in quick choices.",
            "unpin": f"Unpin the current {item}. The field text is not cleared.",
            "delete": f"Delete the current {item} from local cache. The already entered field value is not automatically cleared.",
            "clear": f"Clear the {item} field. Pinned cache entries are not deleted.",
            "pick": f"Pick a saved {item} from local cache and insert it into the field.",
        }
    return tips.get(key, item)


def command_visual_tone(item: Operation | CommandNode) -> str:
    parameters = getattr(item, "parameters", {})
    parameter_parts: list[str] = []
    if isinstance(parameters, dict):
        for key, value in parameters.items():
            parameter_parts.append(str(key))
            if isinstance(value, (str, int, float, bool)):
                parameter_parts.append(str(value))
    identity_parts = [
        getattr(item, "id", ""),
        getattr(item, "kind", ""),
        getattr(item, "title", ""),
        getattr(item, "title_ru", ""),
        getattr(item, "service", ""),
        " ".join(parameter_parts),
    ]
    descriptive_parts = [
        getattr(item, "description", ""),
        getattr(item, "description_ru", ""),
    ]
    identity_text = " ".join(identity_parts).casefold()
    descriptive_text = " ".join(descriptive_parts).casefold()
    text = f"{identity_text} {descriptive_text}"
    destructive_markers = (
        "dangerous",
        "destructive",
        "delete",
        "remove",
        "cleanup",
        "clean",
        "prune",
        "purge",
        "mirror",
        "delete_source",
        "удал",
        "очист",
        "зеркал",
        "лишн",
    )
    status_identity_markers = (
        "diagnostic",
        "diagnostics",
        "doctor",
        "status",
        "info",
        "list",
        "version",
        "verify",
        "check",
        "test",
        "audit",
        "report",
        "scan",
        "validate",
        "dry-run",
        "dry run",
        "диагност",
        "статус",
        "информац",
        "список",
        "версия",
        "провер",
        "тест",
        "аудит",
        "отчет",
        "отчёт",
    )
    status_description_markers = (
        "diagnostic",
        "diagnostics",
        "doctor",
        "status",
        "version",
        "verify",
        "check",
        "test",
        "audit",
        "report",
        "scan",
        "validate",
        "dry-run",
        "dry run",
        "диагност",
        "статус",
        "версия",
        "провер",
        "тест",
        "аудит",
        "отчет",
        "отчёт",
    )
    if any(marker in text for marker in destructive_markers):
        return "risk"
    has_interactive_fields = bool(getattr(item, "fields", ()))
    if any(marker in identity_text for marker in status_identity_markers):
        return "status"
    if not has_interactive_fields and any(marker in descriptive_text for marker in status_description_markers):
        return "status"
    return "neutral"


def operation_row_classes(item: Operation | CommandNode, *, compact: bool = False, tone_enabled: bool = True) -> str:
    tone = command_visual_tone(item) if tone_enabled else "neutral"
    row_classes = f"audion-operation-row audion-operation-row-{tone}"
    if compact:
        row_classes += " audion-operation-row-compact"
    return row_classes


def operation_button(operation: Operation) -> None:
    with ui.element("div").classes(operation_row_classes(operation)):
        ui.button(
            operation.display_title(settings.language),
            on_click=operation_click_handler(operation),
        ).props("dense flat no-wrap").classes("audion-action audion-operation-button rounded-lg")
        ui.label(operation.display_description(settings.language)).classes("audion-operation-description")


def operation_click_handler(operation: Operation):
    async def handler() -> None:
        await start_operation(operation)

    return handler


def refresh_after_operation_click_handler(operation: Operation):
    async def handler() -> None:
        await start_operation(operation)
        command_tree.refresh()

    return handler


async def import_path_history_click_handler() -> None:
    if state["running"]:
        safe_notify(tr("another_running"), "warning")
        return
    try:
        selected = await run.io_bound(pick_path_history_import_file)
        if not selected:
            add_log(tr("picker_cancelled"))
            return
        counts = await run.io_bound(import_path_history_from_file, selected[0])
        add_log(f"Imported path history from {selected[0]} ({counts['sources']} sources, {counts['targets']} targets).")
        safe_notify(tr("path_history_imported"), "positive")
        command_tree.refresh()
    except Exception as exc:
        add_log(f"ERROR: {exc.__class__.__name__}: {exc}")
        safe_notify(str(exc), "negative")


async def export_path_history_click_handler() -> None:
    if state["running"]:
        safe_notify(tr("another_running"), "warning")
        return
    try:
        selected = await run.io_bound(pick_path_history_export_file)
        if not selected:
            add_log(tr("picker_cancelled"))
            return
        counts = await run.io_bound(export_path_history_to_file, selected[0])
        add_log(f"Exported path history to {selected[0]} ({counts['sources']} sources, {counts['targets']} targets).")
        if counts["sources"] == 0 and counts["targets"] == 0:
            safe_notify(tr("path_history_empty"), "warning")
        else:
            safe_notify(tr("path_history_exported"), "positive")
    except Exception as exc:
        add_log(f"ERROR: {exc.__class__.__name__}: {exc}")
        safe_notify(str(exc), "negative")


async def open_latest_report_click_handler() -> None:
    try:
        report_path = await run.io_bound(open_latest_report)
        if report_path is None:
            safe_notify(tr("latest_report_missing"), "warning")
            return
        add_log(f"Opened latest report: {report_path}")
        safe_notify(tr("latest_report_opened"), "positive")
    except Exception as exc:
        add_log(f"ERROR: {exc.__class__.__name__}: {exc}")
        safe_notify(str(exc), "negative")


def path_picker_click_handler(field_key: str):
    async def handler() -> None:
        try:
            selected = await run.io_bound(pick_folder)
            if not selected:
                add_log(tr("picker_cancelled"))
                return
            set_field_value(field_key, str(selected[0]))
            command_tree.refresh()
        except Exception as exc:
            add_log(f"ERROR: {exc.__class__.__name__}: {exc}")
            safe_notify(str(exc), "negative")

    return handler


def path_history_change_handler(field_key: str):
    def handler(event: Any) -> None:
        set_field_value(field_key, event.value or "")
        command_tree.refresh()

    return handler


def pin_path_click_handler(field_key: str, role: str):
    async def handler() -> None:
        path_value = str(state.setdefault("field_values", {}).get(field_key) or "").strip()
        if not path_value:
            safe_notify(tr("path_required"), "warning")
            return
        try:
            should_pin = not is_path_pinned(role, path_value)
            await run.io_bound(set_path_pinned, role, path_value, should_pin)
            safe_notify(tr("path_pinned") if should_pin else tr("path_unpinned"), "positive")
            add_log(f"{'Pinned' if should_pin else 'Unpinned'} {role} path: {path_value}")
            command_tree.refresh()
        except Exception as exc:
            add_log(f"ERROR: {exc.__class__.__name__}: {exc}")
            safe_notify(str(exc), "negative")

    return handler


def operation_to_command_node(operation: Operation) -> CommandNode:
    return CommandNode(
        id=operation.id,
        title=operation.title,
        description=operation.description,
        service=operation.service,
        kind=operation.kind,
        title_ru=operation.title_ru,
        description_ru=operation.description_ru,
        parameters=dict(operation.parameters),
        fields=operation.fields,
    )


def maintenance_operation_node(operation_id: str) -> CommandNode | None:
    for operation in manifest.maintenance_operations:
        if operation.id == operation_id:
            return operation_to_command_node(operation)
    return None


def maintenance_command_node(diagnostics_node: CommandNode | None) -> CommandNode:
    children: list[CommandNode] = []
    if diagnostics_node is not None:
        children.append(diagnostics_node)
    cleanup_workspace = maintenance_operation_node("cleanup_workspace")
    if cleanup_workspace is not None:
        children.append(cleanup_workspace)
    return CommandNode(
        id="maintenance",
        title="Maintenance",
        title_ru="Обслуживание",
        description="Diagnostics and workspace cleanup.",
        description_ru="Диагностика и очистка workspace.",
        children=tuple(children),
    )


def archive_create_command_node() -> CommandNode:
    return CommandNode(
        id="ui_archive_input_folders",
        title="Archiving",
        title_ru="Архивация",
        description="Create archives from files and folders in the selected source into the selected target.",
        description_ru="Создать архивы из файлов и папок выбранного источника в выбранную цель.",
        kind="dangerous",
        fields=(
            {
                "id": "archive_formats",
                "type": "checkboxes",
                "label": "Formats",
                "label_ru": "Форматы",
                "section": "archive_options",
                "span": "full",
                "default": ["zip"],
                "min_selected": 1,
                "options": [
                    {"value": format_id, "label": info["label"], "label_ru": info["label"]}
                    for format_id, info in ARCHIVE_FORMATS.items()
                    if archive_format_backend_available(format_id)
                ],
            },
            {
                "id": "archive_level",
                "type": "select",
                "label": "Compression level",
                "label_ru": "Уровень сжатия",
                "section": "archive_options",
                "ui_hidden": True,
                "default": "1",
                "options": [
                    {"value": value, "label": label, "label_ru": label}
                    for value, label in ARCHIVE_LEVEL_OPTIONS.items()
                ],
            },
            {
                "id": "archive_encryption",
                "type": "archive_encryption_buttons",
                "label": "Encryption",
                "label_ru": "Шифрование",
                "section": "encryption_options",
                "class": "audion-archive-encryption-field",
                "default": "none",
                "refresh_on_change": True,
                "options": [
                    {"value": value, "label": item["label"], "label_ru": item["label_ru"]}
                    for value, item in ARCHIVE_ENCRYPTION_OPTIONS.items()
                ],
            },
            {
                "id": "archive_password",
                "type": "secret",
                "label": "Password",
                "label_ru": "Пароль",
                "section": "encryption_options",
                "class": "audion-archive-password-field",
                "default": "",
                "compact": True,
                "placeholder": "password",
            },
            {
                "id": "archive_layout",
                "type": "inline_radio_chips",
                "label": "Output",
                "label_ru": "Куда класть",
                "section": "archive_options",
                "class": "audion-archive-layout-field",
                "default": "flat",
                "options": [
                    {"value": "flat", "label": "TARGET", "label_ru": "ЦЕЛЬ"},
                    {"value": "per_folder", "label": "TARGET/<name>", "label_ru": "ЦЕЛЬ/<имя>"},
                ],
            },
            {
                "id": "archive_name_prefix",
                "type": "text",
                "label": "Archive file prefix",
                "label_ru": "Префикс файла архива",
                "section": "archive_options",
                "default": "",
                "placeholder": "backup_",
                "class": "audion-archive-name-prefix",
                "hint": "Added before the source item name. Use N. or N_ for sequential numbering.",
                "hint_ru": "Добавляется перед именем исходного элемента. N. или N_ включают последовательную нумерацию.",
            },
            {
                "id": "archive_name_suffix",
                "type": "text",
                "label": "Archive file suffix",
                "label_ru": "Суффикс файла архива",
                "section": "archive_options",
                "default": "",
                "placeholder": "_2026-06",
                "class": "audion-archive-name-suffix",
                "hint": "Added after the source item name, before the extension. Use _N for sequential numbering.",
                "hint_ru": "Добавляется после имени исходного элемента, перед расширением. _N включает последовательную нумерацию.",
            },
            {
                "id": "sfx_extract_path",
                "type": "env_path",
                "label": "SFX auto extract",
                "label_ru": "SFX автоэкстракция",
                "section": "sfx_options",
                "span": "full",
                "default": "{name}",
                "env_field": "sfx_extract_env",
                "env_default": SFX_ENV_NONE,
                "placeholder": "{name}",
                "hint": "Optional SFX install/extract path. {name} is replaced with the source item name; leave empty for SFX default behavior.",
                "hint_ru": "Необязательный путь установки/распаковки SFX. {name} заменяется именем исходного элемента; пустое поле оставляет поведение SFX по умолчанию.",
            },
            {
                "id": "sfx_wrappers",
                "type": "checkboxes",
                "label": "Archive after SFX compression",
                "label_ru": "Архивировать после SFX-компрессии",
                "section": "sfx_options",
                "span": "full",
                "default": [],
                "options": [
                    {"value": format_id, "label": info["label"], "label_ru": info["label"]}
                    for format_id, info in SFX_WRAPPER_FORMATS.items()
                ],
                "hint": "Only when SFX is selected. Creates a send-friendly archive containing the SFX .exe.",
                "hint_ru": "Только если выбран SFX. Создаёт удобный для отправки архив, внутри которого лежит SFX .exe.",
            },
            {
                "id": "archive_verify_after_create",
                "type": "checkbox",
                "label": "Verify archives after compression",
                "label_ru": "Проверить архивы после сжатия",
                "section": "archive_options",
                "class": "audion-archive-post-action audion-archive-verify-action",
                "default": True,
                "tooltip": "Run integrity test for every created archive before optional source deletion.",
                "tooltip_ru": "Проверяет каждый созданный архив перед возможным удалением исходников.",
            },
            {
                "id": "archive_underscore_spaces",
                "type": "checkbox",
                "label": "Spaces -> _",
                "label_ru": "Пробелы -> _",
                "section": "archive_options",
                "class": "audion-archive-post-action audion-archive-underscore-action",
                "default": False,
                "tooltip": "Replace spaces with underscore in created archive file names, including archives placed inside TARGET/<name>. Source names, archive contents and the TARGET/<name> folder itself are not renamed.",
                "tooltip_ru": "Заменяет пробелы на нижнее подчёркивание в имени создаваемого архива, в том числе внутри папки ЦЕЛЬ/<имя>. Исходники, содержимое архива и сама папка ЦЕЛЬ/<имя> не переименовываются.",
            },
            {
                "id": "archive_delete_source",
                "type": "checkbox",
                "label": "Delete source files and folders",
                "label_ru": "Удалить исходные файлы и папки",
                "section": "archive_options",
                "class": "audion-archive-post-action audion-archive-delete-action",
                "default": False,
                "tooltip": "Runs only after successful creation and, if enabled, successful archive verification.",
                "tooltip_ru": "Сработает только после успешного создания и, если включено, успешной проверки архивов.",
            },
        ),
    )


# Which modes actually read which option, so a field is shown only where it does
# something. Derived from the runners of the former network section.
NETWORK_PACK_MODES = ["pack_stage", "pack_direct"]




def rclone_command_node() -> CommandNode:
    remote_modes = sorted(RCLONE_REMOTE_MODES)
    route_modes = sorted(RCLONE_ROUTE_MODES)
    auth_modes = sorted(RCLONE_AUTH_MODES)
    transfer_modes = sorted(RCLONE_TRANSFER_MODES)
    config_manager_modes = ["config"]
    preview_modes = sorted(set(transfer_modes) | set(route_modes))
    return CommandNode(
        id="ui_rclone_operations",
        # `dry_run` объявлен, чтобы общий переключатель безопасности показывался
        # и здесь: сборка трансфера читает его напрямую, как и все остальные.
        parameters={"dry_run": False},
        title="DATA TRANSFER",
        title_ru="ТРАНСФЕР ДАННЫХ",
        description="One master, a list of machines, one run. Folder, share, server and cloud alike; the engine follows from each pair.",
        description_ru="Один эталон, список машин, один запуск. Папка, шара, сервер и облако наравне; движок под каждую пару выбирается сам.",
        kind="safe",
        fields=(
            {
                "id": "rclone_layer",
                "type": "rclone_layer_toggle",
                "label": "RClone layer",
                "label_ru": "Слой RClone",
                "section": "rclone_mode",
                "span": "full",
                "default": default_rclone_layer(),
                "refresh_on_change": True,
            },
            {
                "id": "rclone_mode",
                "type": "rclone_mode_tiles",
                "label": "Mode",
                "label_ru": "Режим",
                "section": "rclone_mode",
                "span": "full",
                "default": RCLONE_LAYER_LAYOUT[default_rclone_layer()].get("default"),
                "refresh_on_change": True,
            },
            {
                "id": "transfer_pack",
                "type": "transfer_pack",
                "label": "Contents",
                "label_ru": "Наполнение",
                "section": "rclone_route",
                "span": "full",
                "display_only": True,
                "visible_when": {"rclone_mode": ["transfer_run"]},
                "refresh_on_change": True,
            },
            {
                "id": "transfer_targets",
                "type": "transfer_targets",
                "label": "Machines",
                "label_ru": "Машины",
                "section": "rclone_route",
                "span": "full",
                "display_only": True,
                "visible_when": {"rclone_mode": ["transfer_run"]},
                "refresh_on_change": True,
            },
            {
                "id": "transfer_operation",
                "type": "transfer_operation",
                "label": "Operation",
                "label_ru": "Операция",
                "section": "rclone_route",
                "span": "full",
                "display_only": True,
                "visible_when": {"rclone_mode": ["transfer_run"]},
                "refresh_on_change": True,
            },
            {
                "id": "transfer_route",
                "type": "transfer_route",
                "label": "What will happen",
                "label_ru": "Что произойдёт",
                "section": "rclone_route",
                "span": "full",
                "display_only": True,
                "visible_when": {"rclone_mode": ["transfer_run"]},
            },
            {
                "id": "rclone_plain_summary",
                "type": "rclone_plain_summary",
                "label": "What this does",
                "label_ru": "Что произойдёт",
                "section": "rclone_mode",
                "span": "full",
                "display_only": True,
            },
            {
                "id": "rclone_config_manager",
                "type": "rclone_config_manager",
                "label": "RClone config scope",
                "label_ru": "RClone config",
                "section": "rclone_config",
                "span": "full",
                "display_only": True,
                "visible_when": {"rclone_mode": config_manager_modes},
            },
            {
                "id": "rclone_remote_name",
                "type": "rclone_remote_picker",
                "label": "Remote",
                "label_ru": "Remote",
                "section": "rclone_remote",
                "default": "",
                "placeholder": "drive",
                "class": "audion-rclone-remote-name-field",
                "visible_when": {"rclone_mode": remote_modes},
                "refresh_on_change": True,
                "hint": "Clouds you have already connected. A name can also be typed.",
                "hint_ru": "Облака, которые уже подключены. Имя можно и ввести вручную.",
            },
            {
                "id": "rclone_remote_path",
                "type": "text",
                "label": "Remote path",
                "label_ru": "Путь remote",
                "section": "rclone_remote",
                "class": "audion-rclone-remote-path-field",
                "default": "",
                "placeholder": "Folder/Subfolder",
                "visible_when": {"rclone_mode": remote_modes},
                "refresh_on_change": True,
                "hint": "Empty path means remote root.",
                "hint_ru": "Пустой путь означает корень remote.",
            },
            {
                "id": "rclone_endpoint_workbench",
                "type": "rclone_endpoint_workbench",
                "label": "Endpoint route",
                "label_ru": "Маршрут endpoint-ов",
                "section": "rclone_route",
                "span": "full",
                "display_only": True,
                "visible_when": {"rclone_mode": route_modes},
            },
            {
                "id": "rclone_auth_manager",
                "type": "rclone_auth_manager",
                "label": "Remote authorization",
                "label_ru": "Авторизация remote",
                "section": "rclone_auth",
                "span": "full",
                "display_only": True,
                "visible_when": {"rclone_mode": auth_modes},
            },
            {
                "id": "rclone_flag_profile",
                "type": "select",
                "label": "Flag profile",
                "label_ru": "Профиль флагов",
                "section": "rclone_flags",
                "default": RCLONE_DEFAULT_PROFILE,
                "visible_when": {"rclone_mode": transfer_modes},
                "refresh_on_change": True,
                "options": [
                    {"value": profile_id, "label": item["label"], "label_ru": item["label_ru"]}
                    for profile_id, item in RCLONE_FLAG_PROFILES.items()
                ],
            },
            {
                "id": "rclone_log_level",
                "type": "select",
                "label": "Log level",
                "label_ru": "Log level",
                "section": "rclone_flags",
                "default": "INFO",
                "visible_when": {"rclone_mode": transfer_modes},
                "refresh_on_change": True,
                "options": [
                    {"value": "INFO", "label": "INFO", "label_ru": "INFO"},
                    {"value": "DEBUG", "label": "DEBUG", "label_ru": "DEBUG"},
                ],
            },
            {
                "id": "rclone_bwlimit",
                "type": "rclone_bwlimit",
                "label": "Bandwidth limit",
                "label_ru": "Ограничение скорости",
                "section": "rclone_flags",
                "span": "full",
                "default": "",
                "visible_when": {"rclone_mode": transfer_modes},
                "refresh_on_change": True,
                "hint": "Optional controlled --bwlimit: unlimited, speed preset, or custom speed.",
                "hint_ru": "Необязательный --bwlimit: без лимита, выбор скорости или своя скорость.",
            },
            {
                "id": "rclone_command_preview",
                "type": "rclone_command_preview",
                "label": "Command constructor",
                "label_ru": "Конструктор команды",
                "section": "rclone_preview",
                "span": "full",
                "display_only": True,
                "visible_when": {"rclone_mode": preview_modes},
            },
        ),
    )


def _iter_command_nodes(nodes: list[CommandNode] | tuple[CommandNode, ...]) -> list[CommandNode]:
    result: list[CommandNode] = []
    for node in nodes:
        result.append(node)
        if node.children:
            result.extend(_iter_command_nodes(node.children))
    return result


def manual_extension_field_template() -> dict[str, Any]:
    for node in _iter_command_nodes(tuple(manifest.operation_groups)):
        for field in node.fields:
            if field_id(field) == "manual_extensions":
                template = dict(field)
                template["section"] = "mask_extensions"
                template["label"] = "Pick extensions"
                template["label_ru"] = "Выбрать расширения"
                template["hint"] = "Checked extensions are merged with the comma-separated mask field above."
                template["hint_ru"] = "Отмеченные расширения добавляются к маскам из поля выше."
                return template
    return {
        "id": "manual_extensions",
        "type": "checkboxes",
        "label": "Pick extensions",
        "label_ru": "Выбрать расширения",
        "section": "mask_extensions",
        "span": "full",
        "default": [],
        "options": [],
    }


def mask_command_node() -> CommandNode:
    extension_field = manual_extension_field_template()
    return CommandNode(
        id="ui_mask_copy",
        title="Masks",
        title_ru="Маски",
        description="Manual comma-separated masks with cache and extension picker.",
        description_ru="Ручные маски через запятую, кэш наборов и выбор расширений.",
        service="system_core.services.disk_auditor_service:run_manual_command",
        kind="dangerous",
        parameters={
            "extension_groups": dict(manifest.operation_groups[0].parameters.get("extension_groups", {})) if manifest.operation_groups else {},
            "cli_command": "sync",
            "mask_operation_mode": "one_way",
            "dry_run": False,
        },
        fields=(
            {
                "id": "mask_operation_mode",
                "type": "mode_buttons",
                "label": "Operation",
                "label_ru": "Операция",
                "section": "mask_mode",
                "span": "full",
                "default": "one_way",
                "options": [
                    {
                        "value": "backup_mirror",
                        "label": "BACKUP MIRROR (quarantine)",
                        "label_ru": "BACKUP MIRROR (карантин)",
                    },
                    {"value": "one_way", "label": "ONE-WAY", "label_ru": "ONE-WAY"},
                    {"value": "two_way", "label": "TWO-WAY", "label_ru": "TWO-WAY"},
                ],
                "hint": (
                    "BACKUP MIRROR here uses mirror_safe: target-only files are moved to "
                    "_audion_quarantine, not hard-deleted. ONE-WAY keeps target-only files. "
                    "TWO-WAY exchanges both ways without deletions."
                ),
                "hint_ru": (
                    "BACKUP MIRROR здесь работает в режиме mirror_safe: target-only файлы "
                    "переносятся в _audion_quarantine, а не удаляются. ONE-WAY оставляет "
                    "target-only файлы. TWO-WAY обменивает файлы в обе стороны без удалений."
                ),
            },
            {
                "id": "manual_mask_text",
                "type": "mask_text",
                "label": "Comma-separated masks",
                "label_ru": "Маски через запятую",
                "section": "mask_text",
                "span": "full",
                "default": "",
                "placeholder": "",
                "hint": "Normalize turns extensions into globs: jpg, .PNG -> *.jpg, *.png.",
                "hint_ru": "Нормализация превращает расширения в globs: jpg, .PNG -> *.jpg, *.png.",
            },
            extension_field,
        ),
    )


def root_command_nodes() -> list[CommandNode]:
    if manifest.operation_groups:
        diagnostics_node = next((node for node in manifest.operation_groups if node.id == "diagnostics"), None)
        nodes = [node for node in manifest.operation_groups if node.id != "diagnostics"]
        # Transfer leads: it is the everyday run — one reference machine, a list of
        # replicas — and it is the section that folded the two old ones together.
        # `manual_backup_apply` stays right below it as the auditor's own pair run,
        # with BLAKE3 comparison, quarantine and the comparison report.
        root_order = {
            "ui_rclone_operations": 0,
            "manual_backup_apply": 1,
            "ui_mask_copy": 3,
            "ui_archive_input_folders": 6,
            "manifest_tools": 9,
            "maintenance": 11,
        }
        indexed_nodes = list(enumerate(nodes))
        indexed_nodes.sort(key=lambda item: (root_order.get(item[1].id, 100), item[0]))
        nodes = [node for _, node in indexed_nodes]
        mask_insert_at = next((index + 1 for index, node in enumerate(nodes) if node.id == "manual_sync2_apply"), len(nodes))
        nodes.insert(mask_insert_at, mask_command_node())
        archive_node = archive_create_command_node()
        archive_insert_at = next((index + 1 for index, node in enumerate(nodes) if node.id == "ui_mask_copy"), len(nodes))
        nodes.insert(archive_insert_at, archive_node)
        # ОПЕРАЦИИ ПО СЕТИ больше не показываются: всё, что раздел делал, теперь
        # делает Трансфер данных — те же пять операций над списком машин, с тем же
        # Robocopy внутри, но без второго набора кнопок для того же самого.
        #
        # Код раздела пока на месте: он вплетён в подтверждения, кэш команд и
        # терминал, и вынимать его надо по одной функции с проверкой на каждом
        # шаге. Отцепить от входа — обратимо и проверяемо, удалять — нет.
        network_insert_at = archive_insert_at + 1
        nodes.insert(network_insert_at, rclone_command_node())
        nodes.append(maintenance_command_node(diagnostics_node))
        indexed_nodes = list(enumerate(nodes))
        indexed_nodes.sort(key=lambda item: (root_order.get(item[1].id, 100), item[0]))
        nodes = [node for _, node in indexed_nodes]
        return nodes
    return [operation_to_command_node(operation) for operation in manifest.operations]


def current_command_level() -> tuple[list[CommandNode], list[CommandNode]]:
    trail: list[CommandNode] = []
    nodes = root_command_nodes()
    for node_id in list(state.get("command_path", [])):
        node = next((candidate for candidate in nodes if candidate.id == node_id), None)
        if node is None:
            state["command_path"] = []
            state["pending_command"] = None
            clear_profile_extension_state()
            return [], root_command_nodes()
        trail.append(node)
        nodes = list(node.children)
    return trail, nodes


def clear_profile_extension_state() -> None:
    for bucket_name in ("field_values", "field_widgets", "extension_info_contexts"):
        bucket = state.setdefault(bucket_name, {})
        if isinstance(bucket, dict):
            for key in [item_key for item_key in bucket if str(item_key).startswith("profile_extensions__")]:
                bucket.pop(key, None)


def enter_command_node(node: CommandNode) -> None:
    clear_profile_extension_state()
    state["pending_command"] = None
    state["command_path"] = [*state.get("command_path", []), node.id]
    command_tree.refresh()


def select_command_node(node: CommandNode) -> None:
    clear_profile_extension_state()
    if node.id == "ui_rclone_operations":
        apply_rclone_start_mode()
    state["pending_command"] = node
    command_tree.refresh()


async def activate_command_node(node: CommandNode) -> None:
    if node.children:
        enter_command_node(node)
        return
    if node.fields:
        select_command_node(node)
        return
    state["pending_command"] = None
    await start_operation(node.to_operation(apply_safety_switches(node, dict(node.parameters))))


def command_click_handler(node: CommandNode):
    async def handler() -> None:
        await activate_command_node(node)

    return handler


def go_back_command() -> None:
    if state.get("pending_command") is not None:
        clear_profile_extension_state()
        state["pending_command"] = None
    else:
        path = list(state.get("command_path", []))
        if path:
            path.pop()
        state["command_path"] = path
    command_tree.refresh()


def field_id(field: dict[str, Any]) -> str:
    return str(field.get("id") or field.get("name") or "").strip()


def field_label(field: dict[str, Any]) -> str:
    language = settings.language
    if language == "ru" and field.get("label_ru"):
        return str(field["label_ru"])
    return str(field.get("label") or field.get("title") or field_id(field))


def field_hint(field: dict[str, Any]) -> str:
    language = settings.language
    if language == "ru" and field.get("hint_ru"):
        return str(field["hint_ru"])
    return str(field.get("hint") or "")


def field_tooltip(field: dict[str, Any]) -> str:
    key_id = field_id(field)
    if key_id in {"archive_formats", "sfx_wrappers"} or is_extension_filter_field(field, key_id):
        return ""
    language = settings.language
    keys = ["tooltip", "description", "hint"]
    if language == "ru":
        keys = ["tooltip_ru", "description_ru", "hint_ru", *keys]
    for key in keys:
        value = str(field.get(key) or "").strip()
        if value:
            return value
    if language == "ru":
        fallback = {
            "archive_encryption": "Выберите, шифровать ли архив. Обычный ZIP/7Z может требовать пароль, а шифрование имён файлов доступно только для 7Z/SFX.",
            "archive_password": "Пароль для зашифрованных архивов. Если выбран режим без шифрования, поле можно оставить пустым.",
            "archive_layout": "Куда положить готовые архивы: прямо в целевую папку или в отдельную подпапку с именем исходного элемента.",
            "archive_name_prefix": "Текст перед именем каждого архива. Например backup_ превратит Folder.zip в backup_Folder.zip.",
            "archive_name_suffix": "Текст после имени исходного элемента, но до расширения архива. Удобно для даты или версии.",
            "sfx_extract_path": "Путь, куда SFX-архив будет предлагать распаковку. {name} заменяется именем исходной папки или файла.",
            "archive_verify_after_create": "После создания каждый архив будет проверен встроенным тестом. Это медленнее, но безопаснее перед удалением исходников.",
            "archive_delete_source": "Удаляет исходные файлы и папки только после успешного создания архива и, если включено, успешной проверки.",
            "rclone_layer": "Выберите слой RClone: облачные операции или серверные remote.",
            "rclone_mode": "Выберите конкретную RClone-команду. Подсказка внизу покажет, что будет делать pipeline.",
            "rclone_config_manager": "Установка RClone и перенос config между portable- и system-режимами.",
            "rclone_remote_name": "Имя remote из rclone config без двоеточия. Например drive, s3backup или yandex.",
            "rclone_remote_path": "Папка внутри выбранного remote. Пустое поле означает корень remote.",
            "rclone_endpoint_workbench": "Настройка Source/Target endpoint-ов для route-команд RClone.",
            "rclone_auth_manager": "Помогает создать или обновить remote без ручного набора длинной команды.",
            "rclone_flag_profile": "Набор безопасных флагов RClone. Для обычной работы лучше начинать с дефолтного профиля.",
            "rclone_log_level": "INFO короче и спокойнее, DEBUG пишет больше технических деталей для диагностики.",
            "rclone_bwlimit": "Ограничивает скорость RClone, чтобы не забивать сеть или облачный лимит.",
            "rclone_command_preview": "Показывает итоговую команду RClone перед запуском, чтобы можно было проверить путь и флаги.",
            "manual_mask_text": "Ручной список масок через запятую. Например *.pdf, *.docx или !*.tmp для исключений.",
        }
    else:
        fallback = {
            "archive_encryption": "Choose whether archives are encrypted. File-name encryption is available only for 7Z/SFX.",
            "archive_password": "Password for encrypted archives. Leave empty when encryption is disabled.",
            "archive_layout": "Choose where created archives are placed: directly in Target or in a per-source subfolder.",
            "archive_name_prefix": "Text added before each archive name.",
            "archive_name_suffix": "Text added after the source name and before the archive extension.",
            "sfx_extract_path": "Suggested extraction path for SFX archives. {name} becomes the source item name.",
            "archive_verify_after_create": "Tests every created archive before optional source deletion.",
            "archive_delete_source": "Deletes source files and folders only after successful create and optional verification.",
            "rclone_layer": "Choose the RClone layer: cloud operations or server remote.",
            "rclone_mode": "Choose the concrete RClone command.",
            "rclone_config_manager": "Install RClone and move config between portable and system scopes.",
            "rclone_remote_name": "Remote name from rclone config without a trailing colon.",
            "rclone_remote_path": "Folder inside the selected remote. Empty means remote root.",
            "rclone_endpoint_workbench": "Configure Source/Target endpoints for RClone route commands.",
            "rclone_auth_manager": "Create or update remotes without manually typing long commands.",
            "rclone_flag_profile": "Safe RClone flag preset.",
            "rclone_log_level": "INFO is shorter; DEBUG writes more diagnostics.",
            "rclone_bwlimit": "Limits RClone transfer speed.",
            "rclone_command_preview": "Shows the final RClone command before launch.",
            "manual_mask_text": "Comma-separated manual masks, for example *.pdf, *.docx, or !*.tmp.",
        }
    if key_id in fallback:
        return fallback[key_id]
    kind = str(field.get("type", field.get("kind", "text"))).lower()
    label = field_label(field)
    if kind in {"checkbox", "bool", "boolean", "toggle"}:
        return f"Включает или выключает параметр «{label}» для текущего запуска." if language == "ru" else f"Turns the '{label}' option on or off for this run."
    if kind in {"select", "choice", "format"}:
        return f"Выберите значение для поля «{label}». Оно попадёт в команду при запуске операции." if language == "ru" else f"Choose the '{label}' value used by the operation command."
    if kind in {"text", "secret", "password", "number", "int", "integer", "float"}:
        return f"Введите значение для поля «{label}». Оставьте пустым, если этот параметр не нужен." if language == "ru" else f"Enter the '{label}' value. Leave empty when this option is not needed."
    return ""


def field_default(field: dict[str, Any]) -> Any:
    if "default" in field:
        return field["default"]
    kind = str(field.get("type", field.get("kind", "text"))).lower()
    options = field.get("options", [])
    if kind in {"checkboxes", "multi_checkbox", "multicheckbox", "multi-select", "multiselect"}:
        if not isinstance(options, list):
            return []
        selected: list[Any] = []
        for option in options:
            if isinstance(option, dict) and option.get("default", False):
                selected.append(option.get("value", option.get("id", option.get("label"))))
        return selected
    if isinstance(options, list) and options:
        first = options[0]
        if isinstance(first, dict):
            return first.get("value", first.get("id", ""))
        return first
    return ""


def current_field_value(field: dict[str, Any]) -> Any:
    key = field_id(field)
    values = state.setdefault("field_values", {})
    if key not in values:
        values[key] = field_default(field)
    return values[key]


def set_field_value(key: str, value: Any) -> None:
    state.setdefault("field_values", {})[key] = value


def register_field_widget(key: str, widget: Any) -> None:
    state.setdefault("field_widgets", {})[key] = widget


def live_field_value(key: str, default: Any = "") -> Any:
    widget = state.setdefault("field_widgets", {}).get(key)
    if widget is not None and hasattr(widget, "value"):
        return widget.value
    return state.setdefault("field_values", {}).get(key, default)


def set_archive_encryption_field(value: Any, *, refresh: bool = False) -> None:
    mode = normalize_archive_encryption_mode(value)
    values = state.setdefault("field_values", {})
    values["archive_encryption"] = mode
    values["archive_formats"] = prune_archive_formats_for_encryption(values.get("archive_formats", ["zip"]), mode)
    if refresh and "command_tree" in globals():
        command_tree.refresh()


def current_named_field_value(key: str, default: Any) -> Any:
    values = state.setdefault("field_values", {})
    if key not in values:
        values[key] = default
    return values[key]


def _extension_base_field_key(key: str) -> str:
    return key[:-8] if key.endswith("_exclude") else key


def _extension_label_map(field: dict[str, Any]) -> dict[str, str]:
    labels: dict[str, str] = {}
    for option_key, option_text in quick_checkbox_groups(field):
        labels[str(option_key)] = option_text
    for section in grouped_checkbox_sections(field):
        for option in section.get("options", []):
            labels[str(option_value(option))] = option_label(option)
    for option_key, option_text in checkbox_options(field):
        labels.setdefault(str(option_key), option_text)
    return labels


def _selection_info_items(items: Any, field: dict[str, Any]) -> tuple[list[str], list[str]]:
    labels = _extension_label_map(field)
    groups: list[str] = []
    masks: list[str] = []
    seen_groups: set[str] = set()
    seen_masks: set[str] = set()
    for raw_item in _normalize_selection_items(items):
        label = labels.get(raw_item, raw_item)
        if raw_item.startswith("@group:"):
            group_label = label or raw_item.split(":", 1)[1]
            if group_label not in seen_groups:
                groups.append(group_label)
                seen_groups.add(group_label)
        elif label not in seen_masks:
            masks.append(label)
            seen_masks.add(label)
    return groups, masks


def extension_selection_info_text(field: dict[str, Any], include_items: Any, exclude_items: Any) -> str:
    include_groups, include_masks = _selection_info_items(include_items, field)
    exclude_groups, exclude_masks = _selection_info_items(exclude_items, field)
    if settings.language == "ru":
        return "\n".join(
            [
                f"ВКЛЮЧИТЬ группы: {', '.join(include_groups) if include_groups else '—'}",
                f"ВКЛЮЧИТЬ маски: {', '.join(include_masks) if include_masks else '—'}",
                f"ИСКЛЮЧИТЬ группы: {', '.join(exclude_groups) if exclude_groups else '—'}",
                f"ИСКЛЮЧИТЬ маски: {', '.join(exclude_masks) if exclude_masks else '—'}",
            ]
        )
    return "\n".join(
        [
            f"INCLUDE groups: {', '.join(include_groups) if include_groups else '-'}",
            f"INCLUDE masks: {', '.join(include_masks) if include_masks else '-'}",
            f"EXCLUDE groups: {', '.join(exclude_groups) if exclude_groups else '-'}",
            f"EXCLUDE masks: {', '.join(exclude_masks) if exclude_masks else '-'}",
        ]
    )


def update_extension_selection_info(item_key: str) -> None:
    base_key = _extension_base_field_key(item_key)
    context = state.setdefault("extension_info_contexts", {}).get(base_key)
    if not isinstance(context, dict):
        return
    widget = context.get("widget")
    if widget is None or not hasattr(widget, "value"):
        return
    field = context.get("field")
    if not isinstance(field, dict):
        return
    include_key = str(context.get("include_key") or base_key)
    exclude_key = str(context.get("exclude_key") or f"{base_key}_exclude")
    values = state.setdefault("field_values", {})
    widget.value = extension_selection_info_text(
        field,
        values.get(include_key, field_default(field)),
        values.get(exclude_key, field.get("exclude_default", [])),
    )


def mask_cache_options(current: str = "") -> list[str]:
    options: list[str] = []
    seen: set[str] = set()
    current_text = masks_to_text(normalize_mask_tokens(current))
    if current_text:
        options.append(current_text)
        seen.add(current_text.casefold())
    for item in load_mask_cache().get("history", []):
        if not isinstance(item, dict):
            continue
        text = masks_to_text(normalize_mask_tokens(item.get("text", "")))
        if not text or text.casefold() in seen:
            continue
        prefix = "PIN  " if bool(item.get("pinned")) else ""
        options.append(f"{prefix}{text}")
        seen.add(text.casefold())
    return options


def clean_mask_cache_selection(value: Any) -> str:
    text = str(value or "").strip()
    if text.startswith("PIN  "):
        text = text[5:].strip()
    return masks_to_text(normalize_mask_tokens(text))


def set_mask_text(value: Any, *, refresh: bool = False) -> str:
    normalized = masks_to_text(normalize_mask_tokens(value))
    set_field_value("manual_mask_text", normalized)
    if refresh and "command_tree" in globals():
        command_tree.refresh()
    return normalized


def expand_extension_selection(items: Any, group_map: Any) -> list[str]:
    values = items if isinstance(items, list) else []
    groups = group_map if isinstance(group_map, dict) else {}
    result: list[str] = []
    seen: set[str] = set()

    def append(pattern: Any) -> None:
        normalized = normalize_mask_token(pattern)
        key = normalized.casefold()
        if normalized and key not in seen:
            result.append(normalized)
            seen.add(key)

    for item in values:
        text = str(item or "").strip()
        if not text:
            continue
        if text.startswith("@group:"):
            group_id = text.split(":", 1)[1]
            for group_pattern in groups.get(group_id, []):
                append(group_pattern)
            continue
        append(text)
    return result


def sync_manual_mask_text_from_picker(include_items: Any | None = None, exclude_items: Any | None = None) -> None:
    node = state.get("pending_command")
    group_map = node.parameters.get("extension_groups", {}) if isinstance(node, CommandNode) else {}
    values = state.setdefault("field_values", {})
    selected_include = include_items if include_items is not None else values.get("manual_extensions", [])
    selected_exclude = exclude_items if exclude_items is not None else values.get("manual_extensions_exclude", [])
    include_globs = expand_extension_selection(selected_include, group_map)
    exclude_globs = expand_extension_selection(selected_exclude, group_map)
    exclude_keys = {item.casefold() for item in exclude_globs}
    next_picker_globs = [item for item in include_globs if item.casefold() not in exclude_keys]
    previous_picker_globs = [
        normalize_mask_token(item)
        for item in state.get("manual_mask_picker_globs", [])
        if normalize_mask_token(item)
    ]
    previous_keys = {item.casefold() for item in previous_picker_globs}
    current_custom = [
        item
        for item in normalize_mask_tokens(current_named_field_value("manual_mask_text", ""))
        if item.casefold() not in previous_keys and item.casefold() not in exclude_keys
    ]
    combined = masks_to_text(normalize_mask_tokens([*current_custom, *next_picker_globs]))
    state["manual_mask_picker_globs"] = next_picker_globs
    set_field_value("manual_mask_text", combined)
    if core.loop is not None:
        command_tree.refresh()


def normalize_mask_text_click_handler():
    def handler() -> None:
        normalized = set_mask_text(current_named_field_value("manual_mask_text", ""), refresh=True)
        if normalized:
            safe_notify(f"Маски нормализованы: {normalized}", "positive")
        else:
            safe_notify("Введите маски через запятую.", "warning")

    return handler


def pin_mask_text_click_handler(pinned: bool):
    def handler() -> None:
        normalized = record_mask_cache(current_named_field_value("manual_mask_text", ""), pinned=pinned)
        if not normalized:
            safe_notify("Введите маски через запятую.", "warning")
            return
        set_field_value("manual_mask_text", normalized)
        safe_notify("Маски закреплены." if pinned else "Маски откреплены.", "positive")
        command_tree.refresh()

    return handler


def delete_mask_text_click_handler():
    def handler() -> None:
        normalized = record_mask_cache(current_named_field_value("manual_mask_text", ""), remove=True)
        if normalized:
            set_field_value("manual_mask_text", normalized)
            safe_notify("Набор масок удалён из кэша.", "positive")
        else:
            safe_notify("Введите маски через запятую.", "warning")
        command_tree.refresh()

    return handler


def is_path_pinned(role: str, path_value: str) -> bool:
    path_text = str(path_value or "").strip()
    if not path_text:
        return False
    normalized = WORKBENCH_ADAPTER.normalize_history_path(path_text).casefold()
    return any(
        bool(item.get("pinned")) and str(item.get("path", "")).casefold() == normalized
        for item in WORKBENCH_ADAPTER.history_entries(role)
    )


def set_path_pinned(role: str, path_value: str, pinned: bool) -> None:
    WORKBENCH_ADAPTER.set_path_pinned(role, path_value, pinned)


def remember_path(role: str, path_value: str) -> None:
    WORKBENCH_ADAPTER.remember_path(role, path_value)


def import_path_history_from_file(file_path: Path) -> dict[str, int]:
    incoming_raw = json.loads(file_path.read_text(encoding="utf-8"))
    if isinstance(incoming_raw, dict) and isinstance(incoming_raw.get("pairs"), list):
        incoming_raw = {
            "sources": [item.get("source") for item in incoming_raw["pairs"] if isinstance(item, dict)],
            "targets": [item.get("target") for item in incoming_raw["pairs"] if isinstance(item, dict)],
        }
    incoming = WORKBENCH_ADAPTER.history.normalize(incoming_raw)
    current = WORKBENCH_ADAPTER.history.normalize(WORKBENCH_ADAPTER.history.load())
    merged = {
        "sources": WORKBENCH_ADAPTER.history.normalize_entries([*current["sources"], *incoming["sources"]]),
        "targets": WORKBENCH_ADAPTER.history.normalize_entries([*current["targets"], *incoming["targets"]]),
    }
    WORKBENCH_ADAPTER.history.save(merged)
    return {"sources": len(merged["sources"]), "targets": len(merged["targets"])}


def export_path_history_to_file(file_path: Path) -> dict[str, int]:
    data = WORKBENCH_ADAPTER.history.normalize(WORKBENCH_ADAPTER.history.load())
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"sources": len(data["sources"]), "targets": len(data["targets"])}


def _load_json_file(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default
    return data if isinstance(data, dict) else default


def path_history_options(role: str, current: str = "") -> list[str]:
    options: list[str] = []
    seen: set[str] = set()
    current_text = str(current or "").strip()
    if current_text:
        options.append(current_text)
        seen.add(current_text.lower())
    for item in WORKBENCH_ADAPTER.history_entries(role):
        path = str(item.get("path", "")).strip()
        if not path or path.lower() in seen:
            continue
        options.append(path)
        seen.add(path.lower())
    return options


def select_options(field: dict[str, Any]) -> dict[Any, str] | list[Any]:
    options = field.get("options", [])
    if not isinstance(options, list):
        return []
    if all(isinstance(option, dict) for option in options):
        result: dict[Any, str] = {}
        for option in options:
            value = option.get("value", option.get("id", ""))
            if settings.language == "ru" and option.get("label_ru"):
                label = str(option["label_ru"])
            else:
                label = str(option.get("label") or option.get("title") or value)
            result[value] = label
        return result
    return options


def option_value(option: Any) -> Any:
    if isinstance(option, dict):
        return option.get("value", option.get("id", option.get("label", "")))
    return option


def option_label(option: Any) -> str:
    if not isinstance(option, dict):
        return str(option)
    language = settings.language
    if language == "ru" and option.get("label_ru"):
        return str(option["label_ru"])
    return str(option.get("label") or option.get("title") or option_value(option))


def option_tooltip(option: Any) -> str:
    if not isinstance(option, dict):
        return ""
    language = settings.language
    keys = ["tooltip", "description", "hint"]
    if language == "ru":
        keys = ["tooltip_ru", "description_ru", "hint_ru", *keys]
    for key in keys:
        value = str(option.get(key) or "").strip()
        if value:
            return value
    return ""


def checkbox_options(field: dict[str, Any]) -> list[tuple[Any, str]]:
    options = field.get("options", [])
    if not isinstance(options, list):
        return []
    return [(option_value(option), option_label(option)) for option in options]


def grouped_checkbox_sections(field: dict[str, Any]) -> list[dict[str, Any]]:
    groups = field.get("groups", [])
    if isinstance(groups, list) and groups:
        sections: list[dict[str, Any]] = []
        for group in groups:
            if not isinstance(group, dict):
                continue
            options = group.get("options", [])
            if not isinstance(options, list) or not options:
                continue
            group_id = str(group.get("id") or "").strip()
            indexed_options = list(enumerate(options))
            indexed_options.sort(key=lambda item: extension_option_rank(group_id, item[1], item[0]))
            options = [option for _index, option in indexed_options]
            if settings.language == "ru" and group.get("label_ru"):
                label = str(group["label_ru"])
            else:
                label = str(group.get("label") or group.get("title") or group.get("id") or "")
            sections.append({"id": str(group_id or label).strip(), "label": label, "options": options})
        if sections:
            return sections
    options = field.get("options", [])
    return [{"label": "", "options": options}] if isinstance(options, list) and options else []


def quick_checkbox_groups(field: dict[str, Any]) -> list[tuple[Any, str]]:
    groups = field.get("quick_groups", [])
    if not isinstance(groups, list):
        return []
    result = [(option_value(group), option_label(group)) for group in groups]
    indexed = list(enumerate(result))
    indexed.sort(key=lambda item: extension_quick_group_rank(item[1], item[0]))
    return [item for _index, item in indexed]


def grouped_quick_checkbox_groups(field: dict[str, Any]) -> list[tuple[str, list[tuple[Any, str]]]]:
    grouped: dict[str, list[tuple[Any, str]]] = {}
    for option_key, option_text in quick_checkbox_groups(field):
        section_id = extension_section_id_from_value(option_key)
        family_id = "profile" if section_id.startswith("profile_preset__") else extension_family_id({"id": section_id})
        grouped.setdefault(family_id, []).append((option_key, option_text))
    order = ["profile", *EXTENSION_FAMILY_ORDER]
    result = [(family_id, grouped.pop(family_id)) for family_id in order if family_id in grouped]
    result.extend(grouped.items())
    return result


def is_checkbox_group(field: dict[str, Any]) -> bool:
    kind = str(field.get("type", field.get("kind", "text"))).lower()
    return kind in {"checkboxes", "multi_checkbox", "multicheckbox", "multi-select", "multiselect"}


def is_display_only_field(field: dict[str, Any]) -> bool:
    kind = str(field.get("type", field.get("kind", "text"))).lower()
    return bool(field.get("display_only")) or kind in {"display", "display-only", "readonly"}


def is_workbench_route_field(field: dict[str, Any]) -> bool:
    key = field_id(field).lower()
    return key in {
        "source_dir",
        "source_folder",
        "source_path",
        "input_dir",
        "input_folder",
        "input_path",
        "target_dir",
        "target_folder",
        "target_path",
        "output_dir",
        "output_folder",
        "output_path",
        "destination_dir",
        "destination_folder",
        "destination_path",
    }


def field_visible_when_matches(field: dict[str, Any], defaults: dict[str, Any]) -> bool:
    condition = field.get("visible_when") or field.get("show_when")
    if not isinstance(condition, dict):
        return True
    values = state.setdefault("field_values", {})
    for key, expected in condition.items():
        current = values.get(str(key), defaults.get(str(key), ""))
        if isinstance(expected, list):
            if current not in expected:
                return False
        elif current != expected:
            return False
    return True


def command_visible_fields(fields: tuple[dict[str, Any], ...] | list[dict[str, Any]]) -> list[dict[str, Any]]:
    defaults = {field_id(field): field_default(field) for field in fields if field_id(field)}
    return [
        field
        for field in fields
        if not is_workbench_route_field(field) and field_visible_when_matches(field, defaults)
    ]


def workbench_value_for_field(field: dict[str, Any]) -> str:
    key = field_id(field).lower()
    if any(part in key for part in ("target", "output", "destination")):
        return str(current_target_path())
    return str(current_source_path())


EXTENSION_FAMILY_ORDER = ["documents", "graphics", "archives", "video", "audio", "apps", "development", "other"]
EXTENSION_SECTION_ORDER = {
    "microsoft_office": 0,
    "text_markup": 1,
    "document_viewers": 2,
    "print_plot": 3,
    "graphics_common": 10,
    "graphics_print_design": 11,
    "graphics_camera_raw": 12,
    "graphics_fonts": 13,
    "graphics_assets": 14,
    "graphics_cad_legacy": 15,
    "common_archives": 20,
    "disk_images_packages": 21,
    "split_legacy_archives": 22,
    "video_modern": 30,
    "video_common_legacy": 31,
    "video_web_mobile": 32,
    "video_transport_dvd": 33,
    "video_codecs_subtitles": 34,
    "audio_common_compressed": 40,
    "audio_lossless": 41,
    "audio_multichannel_voice": 42,
    "audio_midi_tracker": 43,
    "audio_legacy": 44,
    "playlists_cues": 45,
    "windows_apps": 50,
    "shortcuts_links": 51,
    "app_scripts": 52,
    "app_packages": 53,
    "code_languages": 60,
    "python_notebooks": 61,
    "web_frontend": 62,
    "shell_scripts": 63,
    "config_data": 64,
    "infrastructure": 65,
}
EXTENSION_OPTION_ORDER = {
    "microsoft_office": [
        "*.docx", "*.xlsx", "*.pptx", "*.doc", "*.xls", "*.ppt",
        "*.one", "*.onetoc2", "*.pub", "*.vsd", "*.accdb", "*.oft",
    ],
    "text_markup": [
        "*.txt", "*.md", "*.markdown", "*.rtf", "*.csv", "*.xml",
        "*.html", "*.htm", "*.mht", "*.ini", "*.cfg", "*.conf", "*.tab", "*.dif",
    ],
    "document_viewers": ["*.pdf", "*.xps", "*.chm", "*.djvu", "*.djv"],
    "print_plot": ["*.prn", "*.plt"],
    "graphics_common": [
        "*.jpg", "*.jpeg", "*.png", "*.webp", "*.gif", "*.bmp", "*.tif", "*.tiff",
        "*.heic", "*.jxl", "*.ico", "*.cur", "*.ani", "*.dib", "*.rle",
    ],
    "graphics_print_design": [
        "*.psd", "*.svg", "*.svgz", "*.eps", "*.emf", "*.wmf", "*.exr", "*.hdr", "*.dpx",
    ],
    "graphics_camera_raw": [
        "*.dng", "*.raw", "*.cr3", "*.cr2", "*.nef", "*.arw", "*.orf", "*.rw2",
        "*.raf", "*.pef", "*.srw", "*.3fr", "*.ari", "*.bay", "*.braw", "*.cap",
        "*.crw", "*.data", "*.dcr", "*.dcs", "*.drf", "*.eip", "*.erf", "*.fff",
        "*.gpr", "*.iiq", "*.k25", "*.kdc", "*.mdc", "*.mef", "*.mos", "*.mrw",
        "*.nrw", "*.obm", "*.ptx", "*.pxn", "*.r3d", "*.rwl", "*.rwz", "*.sr2",
        "*.srf", "*.x3f",
    ],
    "common_archives": ["*.zip", "*.7z", "*.rar", "*.tar", "*.gz", "*.bz2"],
    "disk_images_packages": ["*.iso", "*.img", "*.cab", "*.rpm", "*.tib", "*.nrg"],
    "split_legacy_archives": [
        "*.r0?", "*.r1?", "*.r2?", "*.r3?", "*.r4?", "*.r5?", "*.r6?", "*.r7?",
        "*.r8?", "*.r9?", "*.a0?", "*.a1?", "*.arj", "*.ace", "*.lzh", "*.lha",
        "*.cpio", "*.z", "*.zz", "*.zoo", "*.uc2",
    ],
    "video_modern": ["*.mp4", "*.mkv", "*.mov", "*.webm", "*.mxf"],
    "video_common_legacy": ["*.avi", "*.wmv", "*.mpeg", "*.mpg", "*.m4v", "*.asf", "*.divx", "*.mpe"],
    "video_web_mobile": ["*.flv", "*.f4v", "*.3gp", "*.3g2", "*.ogv", "*.ogm", "*.dv", "*.amv", "*.3gp2", "*.3gpp", "*.3gpp2", "*.3mm"],
    "video_transport_dvd": ["*.mts", "*.m2ts", "*.ts", "*.vob", "*.ifo", "*.m2v", "*.m2t", "*.m2p", "*.m2s"],
    "video_codecs_subtitles": ["*.srt", "*.avif", "*.heif", "*.av1", "*.vp9", "*.m1v"],
    "audio_common_compressed": ["*.mp3", "*.m4a", "*.aac", "*.ogg", "*.opus", "*.wma", "*.m4b", "*.mp2", "*.mp1", "*.mpga", "*.oga", "*.aax", "*.m4p", "*.m4r"],
    "audio_lossless": ["*.wav", "*.flac", "*.aiff", "*.aif", "*.alac", "*.ape", "*.wv", "*.tak", "*.tta", "*.caf", "*.aifc"],
    "audio_multichannel_voice": ["*.mka", "*.ac3", "*.eac3", "*.dts", "*.amr", "*.vox", "*.mogg"],
    "audio_midi_tracker": ["*.mid", "*.midi", "*.mod", "*.xm", "*.s3m", "*.sid", "*.spc", "*.snd", "*.voc"],
    "audio_legacy": ["*.cda", "*.ra", "*.ram", "*.rm", "*.rmi", "*.mpa", "*.mpc", "*.movpkg", "*.rmx", "*.rv"],
    "playlists_cues": ["*.m3u", "*.m3u8", "*.cue", "*.fpl"],
    "windows_apps": ["*.exe", "*.msi", "*.msp", "*.com", "*.scr", "*.cpl", "*.pif"],
    "shortcuts_links": ["*.lnk", "*.url"],
    "app_scripts": ["*.jar", "*.vbs", "*.vbe"],
    "app_packages": ["*.app", "*.bin", "*.dex", "*.wgt", "*.widget"],
    "code_languages": ["*.js", "*.ts", "*.tsx", "*.jsx", "*.py", "*.java", "*.cs", "*.go", "*.rs", "*.c", "*.cpp", "*.h", "*.hpp", "*.kt", "*.swift"],
    "python_notebooks": ["*.py", "*.ipynb", "*.pyw"],
    "web_frontend": ["*.html", "*.css", "*.js", "*.ts", "*.tsx", "*.jsx", "*.scss"],
    "shell_scripts": ["*.ps1", "*.sh", "*.bat", "*.cmd", "*.bash", "*.zsh", "*.psm1", "*.psd1"],
    "config_data": ["*.json", "*.yaml", "*.yml", "*.toml", "*.ini", "*.cfg", "*.conf"],
    "infrastructure": ["*.sql", "*.tf", "*.tfvars", "*.hcl", "*.nix"],
}


def extension_section_id_from_value(value: Any) -> str:
    text = str(value or "").strip()
    if text.startswith("@group:"):
        text = text.split(":", 1)[1]
    return text.strip().lower()


def extension_family_id(section: dict[str, Any]) -> str:
    section_id = str(section.get("id") or section.get("label") or "").strip().lower()
    if section_id in {"microsoft_office", "text_markup", "document_viewers", "print_plot"}:
        return "documents"
    if section_id.startswith("graphics_"):
        return "graphics"
    if section_id in {"common_archives", "disk_images_packages", "split_legacy_archives"}:
        return "archives"
    if section_id.startswith("video_"):
        return "video"
    if section_id.startswith("audio_") or section_id == "playlists_cues":
        return "audio"
    if section_id in {"windows_apps", "shortcuts_links", "app_scripts", "app_packages"}:
        return "apps"
    if section_id in {"python_notebooks", "shell_scripts", "web_frontend", "config_data", "infrastructure", "code_languages"}:
        return "development"
    return "other"


def extension_family_rank(family_id: str) -> int:
    try:
        return EXTENSION_FAMILY_ORDER.index(family_id)
    except ValueError:
        return len(EXTENSION_FAMILY_ORDER)


def extension_section_rank(section_id: str) -> int:
    return EXTENSION_SECTION_ORDER.get(extension_section_id_from_value(section_id), 1000)


def extension_option_rank(section_id: str, option: Any, index: int) -> tuple[int, int]:
    ordered = EXTENSION_OPTION_ORDER.get(extension_section_id_from_value(section_id), [])
    value = str(option_value(option) if isinstance(option, dict) else option or "").strip().casefold()
    order_map = {item.casefold(): item_index for item_index, item in enumerate(ordered)}
    return (order_map.get(value, 1000 + index), index)


def extension_quick_group_rank(group: tuple[Any, str], index: int) -> tuple[int, int, int]:
    section_id = extension_section_id_from_value(group[0])
    if section_id.startswith("profile_preset__"):
        return (-1, index, index)
    family = extension_family_id({"id": section_id})
    return (extension_family_rank(family), extension_section_rank(section_id), index)


def extension_family_title(family_id: str) -> str:
    if family_id == "profile":
        return "Профиль" if settings.language == "ru" else "Profile"
    return tr(f"extension_family_{family_id}") if family_id in {
        "documents",
        "development",
        "apps",
        "archives",
        "audio",
        "video",
        "graphics",
        "other",
    } else tr("extension_family_other")


def grouped_extension_families(sections: list[dict[str, Any]]) -> list[tuple[str, list[dict[str, Any]]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for section in sections:
        groups.setdefault(extension_family_id(section), []).append(section)
    for family_sections in groups.values():
        family_sections.sort(key=lambda section: extension_section_rank(str(section.get("id") or "")))
    ordered = [(family_id, groups.pop(family_id)) for family_id in EXTENSION_FAMILY_ORDER if family_id in groups]
    ordered.extend(groups.items())
    return ordered


def field_container_classes(field: dict[str, Any]) -> str:
    extra_classes = str(field.get("class") or field.get("classes") or "").strip()
    span = str(field.get("span") or field.get("width") or "").lower()
    if span in {"full", "wide", "100%", "1/-1"}:
        base_classes = "audion-field audion-field-wide"
        return f"{base_classes} {extra_classes}".strip()
    kind = str(field.get("type", field.get("kind", "text"))).lower()
    if kind in {"textarea", "multiline", "mask_text", "mask-text", "path", "file", "folder", "path_history", "path-history", "path_combo", "path-combo"}:
        base_classes = "audion-field audion-field-wide"
        return f"{base_classes} {extra_classes}".strip()
    if is_display_only_field(field):
        base_classes = "audion-field audion-field-wide"
        return f"{base_classes} {extra_classes}".strip()
    if kind in {"env_path", "env-path", "sfx_path", "sfx-path"}:
        base_classes = "audion-field audion-field-wide audion-sfx-path-field"
        return f"{base_classes} {extra_classes}".strip()
    if kind in {"secret", "password"} or bool(field.get("compact")):
        base_classes = "audion-field audion-field-compact"
        return f"{base_classes} {extra_classes}".strip()
    if is_checkbox_group(field):
        base_classes = "audion-field audion-field-wide"
        return f"{base_classes} {extra_classes}".strip()
    if kind in {"select", "choice", "format", "mode_buttons", "mode-buttons", "inline_mode_buttons", "inline-mode-buttons", "inline_radio_chips", "inline-radio-chips", "segmented", "network_tabs", "network-tabs", "archive_encryption_buttons", "archive-encryption-buttons"}:
        base_classes = "audion-field audion-field-select"
        return f"{base_classes} {extra_classes}".strip()
    base_classes = "audion-field"
    return f"{base_classes} {extra_classes}".strip()


def number_value_for_field(field: dict[str, Any], value: Any) -> int | float:
    kind = str(field.get("type", field.get("kind", "text"))).lower()
    is_integer = kind in {"int", "integer"}
    try:
        number = float(value)
    except (TypeError, ValueError):
        default = field_default(field)
        try:
            number = float(default)
        except (TypeError, ValueError):
            try:
                number = float(field.get("min", 0) or 0)
            except (TypeError, ValueError):
                number = 0.0

    minimum = field.get("min")
    maximum = field.get("max")
    if minimum not in {None, ""}:
        try:
            number = max(number, float(minimum))
        except (TypeError, ValueError):
            pass
    if maximum not in {None, ""}:
        try:
            number = min(number, float(maximum))
        except (TypeError, ValueError):
            pass
    return int(round(number)) if is_integer else number


def spin_number_field(field: dict[str, Any], field_key: str, number_input: Any, direction: int) -> None:
    try:
        step = float(field.get("step", 1) or 1)
    except (TypeError, ValueError):
        step = 1.0
    value = number_value_for_field(field, number_input.value)
    next_value = number_value_for_field(field, float(value) + (step * direction))
    set_field_value(field_key, next_value)
    number_input.value = next_value


def field_section_id(field: dict[str, Any]) -> str:
    explicit = str(field.get("section") or field.get("group") or field.get("field_section") or "").strip().lower()
    if explicit:
        return explicit.replace(" ", "_").replace("-", "_")

    key = field_id(field).lower()
    kind = str(field.get("type", field.get("kind", "text"))).lower()
    role = str(field.get("role") or field.get("history") or "").lower()
    label = field_label(field).lower()

    if kind in {"path", "file", "folder", "path_history", "path-history", "path_combo", "path-combo"}:
        return "paths"
    if role in {"source", "sources", "target", "targets", "dst", "destination"}:
        return "paths"
    if any(token in key for token in ("source", "target", "root_dir", "manifest_file", "folder", "path")):
        return "paths"
    if is_checkbox_group(field) or any(token in key for token in ("extension", "extensions", "mask", "preset")):
        return "extensions"
    if kind in {"checkbox", "bool", "boolean", "toggle"} or any(token in key for token in ("exclude", "filter", "ignore")):
        return "filters"
    if any(token in label for token in ("filter", "extension", "расшир")):
        return "filters"
    return "options"


def field_section_order(section_id: str) -> int:
    order = {
        "mask_mode": 0,
        "mask_text": 1,
        "network_panel": 0,
        "network_mode": 0,
        "paths": 0,
        "filters": 1,
        "extensions": 2,
        "mask_extensions": 2,
        "profile_extensions": 2,
        "options": 3,
        "network_options": 3,
        "archive_options": 3,
        "network_archive": 4,
        "encryption_options": 4,
        "network_safety": 5,
        "network_share": 5,
        "rclone_mode": 0,
        "rclone_config": 1,
        "rclone_remote": 2,
        "rclone_route": 2,
        "rclone_auth": 2,
        "rclone_flags": 3,
        "rclone_preview": 4,
        "sfx_options": 5,
    }
    return order.get(section_id, 50)


def field_section_title(section_id: str) -> str:
    normalized = str(section_id or "options").strip().lower().replace("-", "_")
    if normalized == "archive_options":
        return "Архив" if settings.language == "ru" else "Archive"
    if normalized == "network_mode":
        return ""
    if normalized == "network_panel":
        return ""
    if normalized == "network_options":
        return "Копирование" if settings.language == "ru" else "Copy"
    if normalized == "network_archive":
        return "Архив" if settings.language == "ru" else "Archive"
    if normalized == "network_safety":
        return "Проверки" if settings.language == "ru" else "Checks"
    if normalized == "network_share":
        return ""
    if normalized == "rclone_mode":
        return ""
    if normalized == "rclone_config":
        return ""
    if normalized == "rclone_remote":
        return ""
    if normalized == "rclone_route":
        return "Source / Target" if settings.language != "ru" else "Источник / приёмник"
    if normalized == "rclone_auth":
        return ""
    if normalized == "rclone_flags":
        return "Флаги и логи" if settings.language == "ru" else "Flags and logs"
    if normalized == "rclone_preview":
        return ""
    if normalized == "encryption_options":
        return "ШИФРОВАНИЕ" if settings.language == "ru" else "ENCRYPTION"
    if normalized == "sfx_options":
        return "SFX" if settings.language == "ru" else "SFX"
    if normalized == "mask_mode":
        return ""
    if normalized == "mask_text":
        return "МАСКИ" if settings.language == "ru" else "MASKS"
    if normalized == "mask_extensions":
        return "РАСШИРЕНИЯ" if settings.language == "ru" else "EXTENSIONS"
    if normalized == "profile_extensions":
        return "РАСШИРЕНИЯ ПРОФИЛЯ" if settings.language == "ru" else "PROFILE EXTENSIONS"
    known = {
        "paths": "section_paths",
        "filters": "section_filters",
        "extensions": "section_extensions",
        "options": "section_options",
        "parameters": "parameters",
    }
    if normalized in known:
        return tr(known[normalized])
    return normalized.replace("_", " ").strip().title()


def field_section_tooltip(section_id: str) -> str:
    normalized = str(section_id or "options").strip().lower().replace("-", "_")
    if normalized in {"extensions", "mask_extensions", "profile_extensions"}:
        return ""
    if settings.language == "ru":
        tips = {
            "paths": "Маршрут операции: источник, цель, файлы и рабочие папки. Эти значения передаются в CLI как runtime-параметры.",
            "filters": "Флаги и фильтры запуска. Галочки не описываются отдельно, смысл держится на уровне группы.",
            "extensions": "Фильтр расширений. Пустой выбор означает работу без ручного ограничения по маскам.",
            "mask_text": "Ручные маски через запятую, с кэшем, pin/unpin и синхронизацией с выбором расширений.",
            "mask_extensions": "Быстрые группы и точечные расширения. Выбранное превращается в include/exclude mask-globs.",
            "profile_extensions": "Закрепляемый набор include/exclude расширений для профиля.",
            "archive_options": "Настройки упаковки: формат, имя, уровень сжатия, SFX и поведение с исходниками.",
            "encryption_options": "Параметры шифрования только для форматов, которые реально его поддерживают.",
            "rclone_mode": "Выбор облачного слоя и конкретной RClone-команды. Запуск остаётся через portable/system rclone.",
            "rclone_config": "Установка, выбор scope и обмен portable/system RClone config.",
            "rclone_remote": "Remote name и remote path для одиночных cloud-команд.",
            "rclone_route": "Маршрут source/target endpoint-ов для RClone route-команд.",
            "rclone_auth": "Создание OAuth/SFTP remote без ручного переписывания команды.",
            "rclone_flags": "Флаги RClone, уровень логирования и ограничение скорости.",
            "rclone_preview": "Превью итоговой команды и путей перед запуском.",
            "sfx_options": "SFX-распаковка и путь назначения через env-aware шаблон.",
        }
    else:
        tips = {
            "paths": "Operation route: source, target, files, and working folders. Values are passed to the CLI as runtime parameters.",
            "filters": "Run flags and filters. Checkbox details live at the group level.",
            "extensions": "Extension filtering. Empty selection means no manual mask restriction.",
            "mask_text": "Manual comma-separated masks with cache, pin/unpin, and extension picker sync.",
            "mask_extensions": "Quick groups and exact extensions. Selections become include/exclude mask globs.",
            "profile_extensions": "Pinned include/exclude extension set for a profile.",
            "archive_options": "Packing settings: format, name, compression level, SFX, and source cleanup behavior.",
            "encryption_options": "Encryption settings only for formats that actually support them.",
            "rclone_mode": "Pick the cloud layer and concrete RClone command. Execution still uses portable/system rclone.",
            "rclone_config": "Install, select scope, and import/export portable/system RClone config.",
            "rclone_remote": "Remote name and remote path for single cloud commands.",
            "rclone_route": "Source/target endpoint route for RClone route commands.",
            "rclone_auth": "Create OAuth/SFTP remotes without hand-writing the command.",
            "rclone_flags": "RClone flags, log level, and bandwidth limit.",
            "rclone_preview": "Preview of the final command and paths before run.",
            "sfx_options": "SFX extraction and destination path through an env-aware template.",
        }
    return tips.get(normalized, "")


def grouped_fields(fields: list[dict[str, Any]]) -> list[tuple[str, list[dict[str, Any]]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for field in fields:
        groups.setdefault(field_section_id(field), []).append(field)
    return sorted(groups.items(), key=lambda item: (field_section_order(item[0]), item[0]))


def is_extension_filter_field(field: dict[str, Any], key: str | None = None) -> bool:
    field_key = key if key is not None else field_id(field)
    return is_checkbox_group(field) and (
        bool(field.get("extension_filter"))
        or field_key == "manual_extensions"
        or field_key.startswith("profile_extensions__")
    )


def _exclude_extension_field(include_field: dict[str, Any]) -> dict[str, Any]:
    field = dict(include_field)
    include_key = field_id(include_field)
    field["id"] = f"{include_key}_exclude"
    field["label"] = "Exclude extensions"
    field["label_ru"] = "Исключить расширения"
    field["hint"] = "Selected masks are removed after include/profile filters are applied. Group checkboxes expand to --exclude-globs."
    field["hint_ru"] = "Выбранные маски убираются после include/profile-фильтров. Группы разворачиваются в --exclude-globs."
    field["default"] = []
    field.pop("min_selected", None)
    return field


def active_config_is_encrypted() -> bool:
    """Whether the config in use needs a phrase, asked of rclone rather than guessed.

    An encrypted config fails to dump instead of coming back empty, so the answer
    is in the exit code. Cached with the remote list, because it changes exactly
    when the config file does.
    """
    cached = state.get("rclone_config_encrypted")
    if isinstance(cached, bool):
        return cached
    rclone = find_rclone_executable(ROOT)
    if rclone is None:
        return False
    options = current_rclone_options()
    probe = subprocess.run(
        [str(rclone), *rclone_global_config_args(ROOT, options), "config", "dump"],
        cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=utf8_subprocess_env(), creationflags=hidden_subprocess_flags(),
        startupinfo=hidden_subprocess_startupinfo(), stdin=subprocess.DEVNULL, check=False,
    )
    answer = config_is_encrypted((probe.stdout or "") + (probe.stderr or ""), probe.returncode)
    state["rclone_config_encrypted"] = answer
    return answer


def take_ssh_material_into_project(field: str) -> None:
    """Copy the key or known_hosts named in this field into the project.

    Until this ran, the portable-disk plan had a hole in it: the config could
    travel and the key it points at could not, so the folder arrived on another
    machine complete and unable to connect. Afterwards the field holds a path
    relative to the project, which is what survives a different drive letter.
    """
    russian = settings.language == "ru"
    current = str(current_named_field_value(field, "") or "").strip().strip('"')
    if not current:
        safe_notify("Сначала укажите путь к файлу." if russian else "Enter the file path first.", "warning")
        return
    try:
        landed = import_ssh_material(current, ROOT, Path(current).name)
    except (ValueError, OSError) as failure:
        safe_notify(str(failure), "negative")
        return
    set_rclone_field_and_refresh(field, portable_path(landed, ROOT))
    safe_notify(
        f"В проекте: {portable_path(landed, ROOT)}" if russian else f"In the project: {portable_path(landed, ROOT)}",
        "positive",
    )


def render_ssh_material_field(field: str, label: str, placeholder: str, tooltip: str) -> None:
    """A path plus the one action that makes the path travel."""
    russian = settings.language == "ru"
    value = str(current_named_field_value(field, "") or "")
    with ui.row().classes("w-full items-center gap-2 flex-nowrap"):
        ui.input(
            label=label,
            value=value,
            placeholder=placeholder,
            on_change=lambda event: set_rclone_field_and_refresh(field, str(event.value or "")),
        ).props("dense outlined").classes("min-w-0 flex-1").tooltip(tooltip)
        ui.button(
            icon="move_to_inbox",
            on_click=lambda name=field: take_ssh_material_into_project(name),
        ).props("dense flat round").classes("audion-action audion-folder-icon-button").tooltip(
            "Скопировать файл в config\\ssh, чтобы он ездил вместе с проектом. Оригинал останется на месте."
            if russian
            else "Copy the file into config\\ssh so it travels with the project. The original stays where it is."
        )


def render_config_passphrase_field() -> None:
    """Asked once a session, held in memory, never written down.

    Only shown when the config actually is encrypted — a field for a phrase that
    nothing wants is a question with no answer.
    """
    if not active_config_is_encrypted():
        return
    russian = settings.language == "ru"
    held = bool(state.get("rclone_config_passphrase"))
    with ui.element("div").classes("audion-config-passphrase"):
        ui.input(
            label="Фраза конфига" if russian else "Config passphrase",
            value="",
            password=True,
            password_toggle_button=True,
            on_change=lambda event: state.update({"rclone_config_passphrase": str(event.value or "")}),
        ).props("dense outlined autocomplete=off").classes("audion-secret-input w-full").tooltip(
            "Конфиг зашифрован. Фраза нужна на этот запуск, в файлы и кэш команд она не попадает "
            "и в командную строку тоже — уходит через окружение процесса."
            if russian
            else "The config is encrypted. The phrase is needed for this run only; it is written to no "
            "file and to no command line — it goes through the process environment."
        )
        ui.label(
            ("Фраза введена — команды пойдут с ней." if held else "Без фразы rclone не прочитает конфиг.")
            if russian
            else ("Phrase entered — runs will carry it." if held else "Without it rclone cannot read the config.")
        ).classes("audion-field-hint")


def render_run_controls(node: CommandNode | None) -> None:
    """Всё, что уточняет запуск, — одной строкой.

    Потолок удалений и переключатели осторожности отвечают на один вопрос: как
    именно пройдёт этот запуск. Стояли они в трёх разных местах и занимали три
    строки высоты; теперь это ряд с переносом, а объяснения — под ним.

    Потолок показывается только у зеркала: удаляет только оно, и число рядом с
    односторонним копированием обещало бы защиту, которой там не от чего быть.
    """
    russian = settings.language == "ru"
    mirror = (
        node is not None
        and "cli_command" in (node.parameters or {})
        and current_transfer_operation() == OPERATION_MIRROR
    )
    offered = [
        key for key in SAFETY_SWITCHES
        if node is not None and command_supports_switch(node, key)
    ]
    if not mirror and not offered:
        return

    with ui.element("div").classes("audion-run-controls"):
        for switch_id in offered:
            switch = SAFETY_SWITCHES[switch_id]
            ui.checkbox(
                str(switch["label"] if russian else switch["label_en"]),
                value=bool(current_named_field_value(switch_id, False)),
                on_change=lambda event, key=switch_id: set_rclone_field_and_refresh(key, bool(event.value)),
            ).props("dense").classes(
                "audion-single-checkbox audion-chip-checkbox audion-safety-switch"
            ).tooltip(
                str(switch["hint"] if russian else switch["hint_en"])
            )
        if mirror:
            render_delete_ceiling_chip(russian)

    if offered and any(bool(current_named_field_value(key, False)) for key in offered):
        ui.label(
            "Включено — запуск ничего не изменит или отложит лишнее вместо удаления."
            if russian
            else "On — the run will change nothing, or set extras aside instead of deleting."
        ).classes("audion-field-hint audion-safety-note")


def render_safety_switches(node: CommandNode | None) -> None:
    """Rehearsal and caution, asked once above the fields.

    They used to be commands of their own — backup-dry beside backup, a
    quarantine variant beside the mirror — which put a rehearsal in the list at
    the same weight as the thing itself. There are far more real runs than
    rehearsals, and the list should say so.

    A switch is only offered where the command's service already understands the
    parameter. Showing one that would be ignored is worse than not showing it.
    """
    if node is None:
        return
    offered = [key for key in SAFETY_SWITCHES if command_supports_switch(node, key)]
    if not offered:
        return
    russian = settings.language == "ru"
    with ui.element("div").classes("audion-safety-switches"):
        for switch_id in offered:
            switch = SAFETY_SWITCHES[switch_id]
            ui.checkbox(
                str(switch["label"] if russian else switch["label_en"]),
                value=bool(current_named_field_value(switch_id, False)),
                on_change=lambda event, key=switch_id: set_rclone_field_and_refresh(key, bool(event.value)),
            ).props("dense").classes(
                "audion-single-checkbox audion-chip-checkbox audion-safety-switch"
            ).tooltip(
                str(switch["hint"] if russian else switch["hint_en"])
            )
    if any(bool(current_named_field_value(key, False)) for key in offered):
        ui.label(
            "Включено — запуск ничего не изменит или отложит лишнее вместо удаления."
            if russian
            else "On — the run will change nothing, or set extras aside instead of deleting."
        ).classes("audion-field-hint audion-safety-note")


TRANSFER_OPERATION_FIELD: dict[str, Any] = {
    "id": "transfer_operation",
    "type": "transfer_operation",
    "label": "Operation",
    "label_ru": "Операция",
    "display_only": True,
}


def render_fields_grid(fields: list[dict[str, Any]]) -> None:
    node = state.get("pending_command")
    # Where the service takes a cli_command, the operation is the first question
    # and the fields below are its arguments. Three sections used to answer it by
    # existing separately.
    if node is not None and "cli_command" in (node.parameters or {}):
        render_transfer_operation_field(
            TRANSFER_OPERATION_FIELD,
            "ОПЕРАЦИЯ" if settings.language == "ru" else "OPERATION",
            "",
        )
    render_config_passphrase_field()
    render_run_controls(node)
    with ui.element("div").classes("audion-fields-grid"):
        for section_id, section_fields in grouped_fields(fields):
            section_classes = f"audion-field-section audion-field-section-{section_id}"
            section = ui.element("section").classes(section_classes)
            section_tip = field_section_tooltip(section_id)
            with section:
                section_title = field_section_title(section_id)
                if section_title:
                    title_label = ui.label(section_title).classes("audion-section-title")
                    if section_tip:
                        title_label.tooltip(section_tip)
                with ui.element("div").classes("audion-section-fields"):
                    for field in section_fields:
                        render_field(field)


def extension_checkbox_tone_class(option_key: Any, option_text: str) -> str:
    raw_key = str(option_key or "").strip().lower()
    raw_text = str(option_text or "").strip().lower()
    token = f"{raw_key} {raw_text}"
    group_id = raw_key.removeprefix("@group:") if raw_key.startswith("@group:") else ""
    extension = raw_key.removeprefix("*").lower()

    if raw_key in {"zip", "7z", "sfx"}:
        return "audion-chip-type-archive-direct"
    if raw_key in {"tar", "gz", "zstd", "lz4"}:
        return "audion-chip-type-archive-tar"

    if group_id:
        if any(part in group_id for part in ("microsoft_office", "document_viewers", "print_plot")):
            return "audion-chip-type-doc"
        if any(part in group_id for part in ("text_markup", "python_notebooks", "shell_scripts", "web_frontend", "code_languages")):
            return "audion-chip-type-dev"
        if any(part in group_id for part in ("config_data", "infrastructure")):
            return "audion-chip-type-config"
        if any(part in group_id for part in ("common_archives", "disk_images", "split_legacy", "app_packages", "windows_apps")):
            return "audion-chip-type-archive"
        if any(part in group_id for part in ("audio_lossless", "camera_raw", "graphics_print_design", "graphics_fonts")):
            return "audion-chip-type-lossless"
        if any(part in group_id for part in ("audio_common_compressed", "audio_multichannel", "audio_legacy", "video_", "graphics_common")):
            return "audion-chip-type-lossy"
        if any(part in group_id for part in ("apps", "shortcuts", "graphics_assets", "cad_legacy")):
            return "audion-chip-type-binary"

    doc_exts = {
        ".accdb", ".doc", ".docx", ".oft", ".one", ".onetoc2", ".ppt", ".pptx", ".pub",
        ".rtf", ".vsd", ".xls", ".xlsx", ".chm", ".djv", ".djvu", ".pdf", ".xps",
        ".plt", ".prn",
    }
    dev_exts = {
        ".bash", ".bat", ".c", ".cmd", ".cpp", ".cs", ".css", ".go", ".h", ".hpp",
        ".htm", ".html", ".ipynb", ".java", ".js", ".jsx", ".kt", ".lua", ".markdown",
        ".md", ".php", ".ps1", ".psd1", ".psm1", ".py", ".pyw", ".rb", ".rs", ".scss",
        ".sh", ".sql", ".srt", ".swift", ".tf", ".tfvars", ".ts", ".tsx", ".vbe", ".vbs",
        ".vue", ".zsh",
    }
    config_exts = {
        ".cfg", ".conf", ".csv", ".data", ".dif", ".env", ".hcl", ".ini", ".json", ".lock", ".log",
        ".mht", ".nix", ".tab", ".toml", ".txt", ".xml", ".yaml", ".yml",
    }
    archive_exts = {
        ".7z", ".a0?", ".a1?", ".ace", ".apk", ".appx", ".arj", ".bz2", ".cab", ".cpio",
        ".dmg", ".gz", ".img", ".iso", ".jar", ".lha", ".lzh", ".msi", ".nrg", ".pkg", ".r0?",
        ".r1?", ".r2?", ".r3?", ".r4?", ".r5?", ".r6?", ".r7?", ".r8?", ".r9?", ".rar", ".rpm",
        ".tar", ".tgz", ".tib", ".uc2", ".vhd", ".vhdx", ".wim", ".xz", ".z", ".zip", ".zoo",
        ".zst", ".zz",
    }
    binary_exts = {
        ".app", ".bin", ".com", ".cpl", ".dex", ".dll", ".dwg", ".exe", ".icl", ".icn", ".lnk",
        ".msix", ".ocx", ".pif", ".scr", ".sys", ".url", ".wgt", ".widget",
    }
    lossless_exts = {
        ".abr", ".afm", ".aif", ".aifc", ".aiff", ".alac", ".ani", ".ape", ".atn", ".bmp",
        ".cda", ".cur", ".dff", ".dib", ".dsf", ".emf", ".exr", ".flac", ".fpl", ".gif", ".grd",
        ".hdr", ".ico", ".jxl", ".m3u", ".m3u8", ".mid", ".midi", ".mod", ".otf", ".pbm", ".pcd",
        ".pcx", ".pfb", ".pfm", ".pgm", ".pic", ".pix", ".png", ".psd", ".rle", ".s3m", ".sid",
        ".snd", ".spc", ".svg", ".svgz", ".tak", ".tga", ".tif", ".tiff", ".ttf", ".tta", ".voc",
        ".wav", ".w64", ".wmf", ".wor", ".wv", ".xbm", ".xif", ".xm", ".xpm", ".ai", ".cue",
        ".dpx", ".eps", ".indd", ".msp",
    }
    raw_exts = {
        ".3fr", ".ari", ".arw", ".bay", ".cap", ".cr2", ".cr3", ".crw", ".dcr", ".dcs",
        ".dng", ".drf", ".eip", ".erf", ".fff", ".gpr", ".iiq", ".k25", ".kdc", ".mdc",
        ".mef", ".mos", ".mrw", ".nef", ".nrw", ".obm", ".orf", ".pef", ".ptx", ".pxn", ".r3d",
        ".raf", ".raw", ".rwl", ".rw2", ".rwz", ".sr2", ".srf", ".srw", ".x3f",
    }
    lossy_exts = {
        ".3g2", ".3gp", ".3gp2", ".3gpp", ".3gpp2", ".3mm", ".aac", ".aax", ".ac3", ".amr",
        ".amv", ".asf", ".avi", ".av1", ".avif", ".awb", ".caf", ".divx", ".dts", ".dv", ".eac3",
        ".f4v", ".flv", ".heic", ".heif", ".ifo", ".jpg", ".jpeg", ".m1v", ".m2p", ".m2s", ".m2t",
        ".m2ts", ".m2v", ".m4a", ".m4b", ".m4p", ".m4r", ".m4v", ".mka", ".mkv", ".mogg", ".mov",
        ".movpkg", ".mp1", ".mp2", ".mp3", ".mp4", ".mpa", ".mpc", ".mpe", ".mpeg", ".mpg", ".mpga",
        ".mts", ".mxf", ".oga", ".ogg", ".ogm", ".ogv", ".opus", ".ra", ".ram", ".rm", ".rmi", ".rmx",
        ".rv", ".ts", ".vob", ".vox", ".vp9", ".webm", ".webp", ".wma", ".wmv",
    }

    if extension in doc_exts:
        return "audion-chip-type-doc"
    if extension in dev_exts:
        return "audion-chip-type-dev"
    if extension in config_exts:
        return "audion-chip-type-config"
    if extension in archive_exts:
        return "audion-chip-type-archive"
    if extension in binary_exts:
        return "audion-chip-type-binary"
    if extension in raw_exts or "raw" in token:
        return "audion-chip-type-lossless"
    if extension in lossless_exts:
        return "audion-chip-type-lossless"
    if extension in lossy_exts:
        return "audion-chip-type-lossy"
    return "audion-chip-type-neutral"


def add_checkbox_control(
    option_key: Any,
    option_text: str,
    selected: set[Any],
    controls: dict[Any, Any],
    sync_checkboxes: Any,
    css_class: str,
    disabled: bool = False,
    disabled_reason: str = "",
) -> None:
    if option_key in controls:
        return
    checkbox = ui.checkbox(
        option_text,
        value=(option_key in selected) and not disabled,
        on_change=lambda _event: sync_checkboxes(True),
    ).props("dense" + (" disable" if disabled else ""))
    tone_class = extension_checkbox_tone_class(option_key, option_text)
    checkbox.classes(css_class + f" audion-chip-checkbox {tone_class}" + (" audion-checkbox-disabled" if disabled else ""))
    if disabled and disabled_reason:
        checkbox.tooltip(disabled_reason)
    checkbox._audion_disabled = disabled
    controls[option_key] = checkbox


def set_checkbox_keys(keys: list[Any], controls: dict[Any, Any], checked: bool, sync_checkboxes: Any) -> None:
    for option_key in keys:
        checkbox = controls.get(option_key)
        if checkbox is not None and not bool(getattr(checkbox, "_audion_disabled", False)):
            checkbox.value = checked
    sync_checkboxes(True)


def extension_section_option_count(section: dict[str, Any]) -> int:
    options = section.get("options", [])
    return len(options) if isinstance(options, list) else 0


def extension_short_run_span_classes(run_length: int) -> list[str]:
    full = "audion-extension-block-span-full"
    half = "audion-extension-block-span-half"
    third = "audion-extension-block-span-third"
    if run_length <= 0:
        return []
    if run_length == 1:
        return [full]
    if run_length == 2:
        return [half, half]
    classes = [third] * run_length
    remainder = run_length % 3
    if remainder == 2:
        for index in range(run_length - 2, run_length):
            classes[index] = half
    elif remainder == 1:
        for index in range(max(0, run_length - 4), run_length):
            classes[index] = half
    return classes


def extension_block_span_classes(sections: list[dict[str, Any]]) -> list[str]:
    full = "audion-extension-block-span-full"
    result = [""] * len(sections)
    pending_short_indices: list[int] = []

    def flush_short_run() -> None:
        nonlocal pending_short_indices
        for section_index, span_class in zip(pending_short_indices, extension_short_run_span_classes(len(pending_short_indices))):
            result[section_index] = span_class
        pending_short_indices = []

    for section_index, section in enumerate(sections):
        if extension_section_option_count(section) >= 20:
            flush_short_run()
            result[section_index] = full
        else:
            pending_short_indices.append(section_index)
    flush_short_run()
    return result


def archive_level_option_values(allowed: set[str] | None = None) -> list[str]:
    values = [str(value) for value in ARCHIVE_LEVEL_OPTIONS.keys()]
    return [value for value in values if allowed is None or value in allowed]


def archive_level_next_value(current: Any, delta: int, allowed: set[str] | None = None) -> str:
    values = archive_level_option_values(allowed)
    if not values:
        return "1"
    normalized = archive_compression_level(current)
    try:
        index = values.index(normalized)
    except ValueError:
        index = values.index("1") if "1" in values else 0
    return values[(index + delta) % len(values)]


def render_archive_level_chip(
    field_key: str = "archive_level",
    *,
    caption: str | None = None,
    allowed: set[str] | None = None,
) -> None:
    values = archive_level_option_values(allowed)
    current = archive_compression_level(current_named_field_value(field_key, "1"))
    if current not in values:
        current = "1" if "1" in values else (values[0] if values else "1")
    set_field_value(field_key, current)
    value_label: Any = None

    def set_level(next_value: Any) -> None:
        nonlocal value_label
        normalized = archive_compression_level(next_value)
        if normalized not in values:
            normalized = "1" if "1" in values else (values[0] if values else "1")
        set_field_value(field_key, normalized)
        if value_label is not None:
            value_label.text = normalized

    def spin(delta: int) -> None:
        set_level(archive_level_next_value(current_named_field_value(field_key, "1"), delta, allowed))

    tooltip = "Уровень сжатия: 0 без сжатия, 9 максимум." if settings.language == "ru" else "Compression level: 0 stores, 9 compresses most."
    with ui.element("div").classes("audion-archive-level-chip").tooltip(tooltip):
        ui.label(caption or ("Уровень" if settings.language == "ru" else "Level")).classes("audion-archive-level-caption")
        with ui.element("div").classes("audion-archive-level-spinner"):
            value_label = ui.label(current if current in values else "1").classes("audion-archive-level-value")
            with ui.element("div").classes("audion-archive-level-spin-stack"):
                ui.button(icon="keyboard_arrow_up", on_click=lambda: spin(1)).props("dense flat round").classes("audion-archive-level-spin")
                ui.button(icon="keyboard_arrow_down", on_click=lambda: spin(-1)).props("dense flat round").classes("audion-archive-level-spin")


def render_checkbox_group_field(field: dict[str, Any], key: str, label: str, value: Any, hint: str) -> None:
    selected = set(value if isinstance(value, list) else [])
    disabled_options: set[Any] = set()
    disabled_reasons: dict[Any, str] = {}
    if key == "archive_formats":
        encryption_mode = normalize_archive_encryption_mode(current_named_field_value("archive_encryption", "none"))
        selected = set(prune_archive_formats_for_encryption(list(selected), encryption_mode))
        disabled_reasons = {
            option_key: reason
            for option_key, _option_text in checkbox_options(field)
            if (reason := archive_format_disabled_reason(option_key, encryption_mode))
        }
        disabled_options = set(disabled_reasons)
        set_field_value(key, list(selected))
    controls: dict[Any, Any] = {}

    def sync_checkboxes(update_mask_text: bool = False, item_key: str = key) -> None:
        selected_keys = [option_key for option_key, checkbox in controls.items() if bool(checkbox.value)]
        set_field_value(item_key, selected_keys)
        update_extension_selection_info(str(item_key))
        pending_node = state.get("pending_command")
        sync_mask_picker = isinstance(pending_node, CommandNode) and pending_node.id == "ui_mask_copy"
        if update_mask_text and sync_mask_picker and item_key == "manual_extensions":
            sync_manual_mask_text_from_picker(include_items=selected_keys)
        elif update_mask_text and sync_mask_picker and item_key == "manual_extensions_exclude":
            sync_manual_mask_text_from_picker(exclude_items=selected_keys)

    ui.label(label).classes("audion-field-label audion-checkbox-title")
    if key in {"archive_formats", "sfx_wrappers"}:
        line_classes = "audion-extension-options audion-extension-options-archive-line"
        if key == "archive_formats":
            line_classes += " audion-archive-format-row"
        with ui.element("div").classes(line_classes):
            if key == "archive_formats":
                render_archive_level_chip()
            for option_key, option_text in checkbox_options(field):
                add_checkbox_control(
                    option_key,
                    option_text,
                    selected,
                    controls,
                    sync_checkboxes,
                    "audion-extension-checkbox audion-archive-format-checkbox",
                    option_key in disabled_options,
                    disabled_reasons.get(option_key, ""),
                )
        sync_checkboxes()
        return

    quick_groups = quick_checkbox_groups(field)
    if quick_groups:
        group_label = field.get("quick_groups_label_ru" if settings.language == "ru" else "quick_groups_label")
        with ui.element("div").classes("audion-checkbox-family audion-quick-family"):
            ui.label(str(group_label or tr("extension_quick_groups"))).classes("audion-extension-family-title")
            with ui.element("div").classes("audion-quick-family-groups"):
                for family_id, family_groups in grouped_quick_checkbox_groups(field):
                    with ui.element("div").classes(f"audion-quick-family-group audion-quick-family-group-{family_id}"):
                        ui.label(extension_family_title(family_id)).classes("audion-quick-family-title")
                        with ui.element("div").classes("audion-quick-grid"):
                            for option_key, option_text in family_groups:
                                add_checkbox_control(
                                    option_key,
                                    option_text,
                                    selected,
                                    controls,
                                    sync_checkboxes,
                                    "audion-preset-checkbox",
                                    option_key in disabled_options,
                                    disabled_reasons.get(option_key, ""),
                                )

    sections = grouped_checkbox_sections(field)
    if sections:
        with ui.element("div").classes("audion-extension-families"):
            for family_id, family_sections in grouped_extension_families(sections):
                with ui.element("div").classes(f"audion-checkbox-family audion-extension-family audion-extension-family-{family_id}"):
                    ui.label(extension_family_title(family_id)).classes("audion-extension-family-title")
                    with ui.element("div").classes("audion-extension-section-grid"):
                        span_classes = extension_block_span_classes(family_sections)
                        for section_index, section in enumerate(family_sections):
                            section_label = str(section.get("label") or "")
                            section_options = [
                                (option_value(option), option_label(option))
                                for option in section.get("options", [])
                            ]
                            section_keys = [option_key for option_key, _option_text in section_options]
                            option_count = len(section_options)
                            section_id_class = f"audion-extension-block-{extension_section_id_from_value(section.get('id') or section_label)}"
                            size_class = "audion-extension-block-long" if option_count >= 20 else "audion-extension-block-medium" if option_count > 10 else "audion-extension-block-short"
                            span_class = span_classes[section_index] if section_index < len(span_classes) else "audion-extension-block-span-full"
                            options_class = "audion-extension-options-columns" if option_count > 3 else "audion-extension-options-linear"
                            with ui.element("div").classes(f"audion-extension-block {section_id_class} {size_class} {span_class}"):
                                with ui.row().classes("audion-extension-block-head w-full items-center gap-1"):
                                    if section_label:
                                        ui.label(section_label).classes("audion-extension-block-title")
                                        ui.element("span").classes("audion-extension-head-separator")
                                    ui.button(
                                        tr("extension_select_all"),
                                        on_click=lambda item_keys=section_keys: set_checkbox_keys(item_keys, controls, True, sync_checkboxes),
                                    ).props("dense flat no-wrap").classes("audion-mini-action rounded-md")
                                    ui.button(
                                        tr("extension_select_none"),
                                        on_click=lambda item_keys=section_keys: set_checkbox_keys(item_keys, controls, False, sync_checkboxes),
                                    ).props("dense flat no-wrap").classes("audion-mini-action rounded-md")
                                with ui.element("div").classes(f"audion-extension-options {options_class}"):
                                    for option_key, option_text in section_options:
                                        add_checkbox_control(
                                            option_key,
                                            option_text,
                                            selected,
                                            controls,
                                            sync_checkboxes,
                                            "audion-extension-checkbox",
                                            option_key in disabled_options,
                                            disabled_reasons.get(option_key, ""),
                                        )

    if not controls:
        flat_options_class = (
            "audion-extension-options-archive-line"
            if key in {"archive_formats", "sfx_wrappers"}
            else "audion-extension-options-flat"
        )
        checkbox_class = (
            "audion-extension-checkbox audion-archive-format-checkbox"
            if key in {"archive_formats", "sfx_wrappers"}
            else "audion-extension-checkbox"
        )
        with ui.element("div").classes(f"audion-extension-options {flat_options_class}"):
            for option_key, option_text in checkbox_options(field):
                add_checkbox_control(
                    option_key,
                    option_text,
                    selected,
                    controls,
                    sync_checkboxes,
                    checkbox_class,
                    option_key in disabled_options,
                    disabled_reasons.get(option_key, ""),
                )
    if hint:
        ui.label(hint).classes("audion-field-hint")
    sync_checkboxes()


def render_extension_include_exclude_field(field: dict[str, Any], key: str, _label: str, value: Any, hint: str) -> None:
    include_field = dict(field)
    include_field["label"] = "Include"
    include_field["label_ru"] = "ВКЛЮЧИТЬ"
    include_key = key

    exclude_field = _exclude_extension_field(field)
    exclude_key = field_id(exclude_field)
    exclude_value = current_named_field_value(exclude_key, field.get("exclude_default", []))

    def set_profile_extension_selection(include_items: Any, exclude_items: Any) -> None:
        set_field_value(include_key, _normalize_selection_items(include_items))
        set_field_value(exclude_key, _normalize_selection_items(exclude_items))
        update_extension_selection_info(include_key)
        command_tree.refresh()

    def pin_profile_extension_selection(pinned: bool) -> None:
        include_items = state.setdefault("field_values", {}).get(include_key, field_default(field))
        exclude_items = state.setdefault("field_values", {}).get(exclude_key, field.get("exclude_default", []))
        stored_include, stored_exclude = record_profile_extension_cache(include_items, exclude_items, pinned=pinned)
        if not stored_include and not stored_exclude:
            safe_notify("Выберите расширения перед сохранением набора.", "warning")
            return
        safe_notify("Набор расширений закреплён." if pinned else "Набор расширений откреплён.", "positive")
        command_tree.refresh()

    def delete_profile_extension_selection() -> None:
        include_items = state.setdefault("field_values", {}).get(include_key, field_default(field))
        exclude_items = state.setdefault("field_values", {}).get(exclude_key, field.get("exclude_default", []))
        stored_include, stored_exclude = record_profile_extension_cache(include_items, exclude_items, remove=True)
        if not stored_include and not stored_exclude:
            safe_notify("Выберите сохранённый набор расширений.", "warning")
            return
        safe_notify("Набор расширений удалён из кэша.", "positive")
        command_tree.refresh()

    def apply_profile_extension_cache(selection: Any) -> None:
        cached = profile_extension_cache_selection(selection)
        if cached is None:
            return
        set_profile_extension_selection(cached[0], cached[1])

    show_extension_summary = key != "manifest_extensions" and is_extension_filter_field(field, key)
    if show_extension_summary:
        with ui.element("div").classes("audion-extension-summary-sticky"):
            with ui.element("div").classes("audion-mask-tools audion-profile-extension-tools"):
                ui.button(icon="push_pin", on_click=lambda: pin_profile_extension_selection(True)).props("dense flat round").classes("audion-action audion-folder-icon-button").tooltip(cache_action_tooltip("pin", "набор расширений профиля" if settings.language == "ru" else "profile extension set"))
                ui.button(icon="block", on_click=lambda: pin_profile_extension_selection(False)).props("dense flat round").classes("audion-action audion-folder-icon-button").tooltip(cache_action_tooltip("unpin", "набор расширений профиля" if settings.language == "ru" else "profile extension set"))
                ui.button(icon="delete", on_click=delete_profile_extension_selection).props("dense flat round").classes("audion-action audion-folder-icon-button").tooltip(cache_action_tooltip("delete", "набор расширений профиля" if settings.language == "ru" else "profile extension set"))
                ui.button(
                    "ОЧИСТИТЬ" if settings.language == "ru" else "CLEAR",
                    icon="backspace",
                    on_click=lambda: set_profile_extension_selection([], []),
                ).props("dense flat no-wrap").classes("audion-action audion-extension-clear-button rounded-md").tooltip(
                    "Очистить собранные расширения. Пусто = все файлы." if settings.language == "ru" else "Clear collected extensions. Empty = all files."
                )
                ui.select(
                    options=profile_extension_cache_options(value, exclude_value),
                    value=None,
                    on_change=lambda event: apply_profile_extension_cache(event.value),
                ).props("dense outlined clearable options-dense popup-content-class=audion-select-popup").classes("audion-mask-cache-select min-w-0 flex-1")
            info_widget = ui.textarea(
                label="Собранные расширения" if settings.language == "ru" else "Collected extensions",
                value=extension_selection_info_text(field, value, exclude_value),
            ).props("dense outlined readonly rows=4 no-resize").classes("audion-extension-selection-info w-full")
        state.setdefault("extension_info_contexts", {})[include_key] = {
            "field": field,
            "include_key": include_key,
            "exclude_key": exclude_key,
            "widget": info_widget,
        }
        register_field_widget(f"{include_key}__info", info_widget)

    with ui.element("div").classes("audion-extension-mode-field"):
        with ui.tabs().props("dense active-color=primary indicator-color=primary").classes("audion-extension-mode-tabs") as tabs:
            include_tab = ui.tab("ВКЛЮЧИТЬ" if settings.language == "ru" else "INCLUDE")
            exclude_tab = ui.tab("ИСКЛЮЧИТЬ" if settings.language == "ru" else "EXCLUDE")
        with ui.tab_panels(tabs, value=include_tab).props("animated keep-alive").classes("audion-extension-mode-panels"):
            with ui.tab_panel(include_tab).classes("audion-extension-mode-panel"):
                render_checkbox_group_field(include_field, include_key, "ВКЛЮЧИТЬ" if settings.language == "ru" else "INCLUDE", value, hint)
            with ui.tab_panel(exclude_tab).classes("audion-extension-mode-panel"):
                render_checkbox_group_field(exclude_field, exclude_key, "ИСКЛЮЧИТЬ" if settings.language == "ru" else "EXCLUDE", exclude_value, field_hint(exclude_field))


def current_network_share_options(action_id: str) -> dict[str, Any]:
    values = state.setdefault("field_values", {})
    return {
        "panel": "smb_share",
        "share_action": action_id,
        "share_principal": values.get("network_share_principal", current_windows_principal()),
        "share_prefix": values.get("network_share_prefix", "Audion"),
    }






def rclone_preview_spec() -> Any:
    return build_rclone_command(ROOT, paths.logs, current_rclone_options(), preview=True)


def rclone_constructor_cache_click_handler(action: str):
    def handler() -> None:
        fields = rclone_cache_fields()
        if action == "pin":
            record_rclone_command_cache(fields, pinned=True)
            safe_notify("Rclone command pinned.", "positive")
        elif action == "unpin":
            record_rclone_command_cache(fields, pinned=False)
            safe_notify("Rclone command unpinned.", "positive")
        elif action == "delete":
            record_rclone_command_cache(fields, remove=True)
            safe_notify("Rclone command deleted from cache.", "positive")
        command_tree.refresh()

    return handler


def rclone_constructor_cache_select(event: Any) -> None:
    fields = rclone_command_cache_selection(getattr(event, "value", None))
    if fields is None:
        return
    apply_rclone_cached_fields(fields)
    safe_notify("Rclone command template loaded.", "positive")
    command_tree.refresh()


def set_rclone_field_and_refresh(key: str, value: Any) -> None:
    set_field_value(key, value)
    command_tree.refresh()


def rclone_auto_remote_names() -> set[str]:
    return {"", "server", *RCLONE_AUTH_BACKENDS.keys()}


def rclone_remote_name_is_auto(value: Any) -> bool:
    return str(value or "").strip().rstrip(":").casefold() in rclone_auto_remote_names()


def rclone_default_auth_remote_name(mode: Any, backend: Any = "drive") -> str:
    normalized_mode = normalize_rclone_mode(mode)
    if normalized_mode == "remote_create_sftp":
        return "server"
    return normalize_auth_backend(backend)


def set_rclone_mode_from_tile(mode: str) -> None:
    normalized = normalize_rclone_mode(mode)
    values = state.setdefault("field_values", {})
    current_remote = values.get("rclone_auth_remote_name", "")
    if normalized in RCLONE_AUTH_MODES and rclone_remote_name_is_auto(current_remote):
        values["rclone_auth_remote_name"] = rclone_default_auth_remote_name(
            normalized,
            values.get("rclone_auth_backend", "drive"),
        )
    values["rclone_mode"] = normalized
    state.pop("rclone_run_tooltip", None)
    command_tree.refresh()


def set_rclone_auth_backend_and_refresh(value: Any) -> None:
    backend = normalize_auth_backend(value)
    values = state.setdefault("field_values", {})
    current_remote = values.get("rclone_auth_remote_name", "")
    values["rclone_auth_backend"] = backend
    if rclone_remote_name_is_auto(current_remote):
        values["rclone_auth_remote_name"] = backend
    command_tree.refresh()


def set_rclone_config_scope_and_refresh(value: Any) -> None:
    scope = normalize_config_scope(value)
    set_field_value("rclone_config_scope", scope)
    if scope == "portable":
        portable_rclone_config_path(ROOT).parent.mkdir(parents=True, exist_ok=True)
        portable_rclone_cache_dir(ROOT).mkdir(parents=True, exist_ok=True)
    invalidate_rclone_remote_cache()
    command_tree.refresh()


def current_rclone_config_options() -> dict[str, Any]:
    values = state.setdefault("field_values", {})
    return {
        "config_scope": normalize_config_scope(values.get("rclone_config_scope", RCLONE_DEFAULT_CONFIG_SCOPE)),
        "custom_config": str(values.get("rclone_custom_config") or "").strip(),
    }


def rclone_backup_file(path: Path, label: str) -> Path | None:
    if not path.exists():
        return None
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = path.with_name(f"{path.name}.{stamp}.bak")
    shutil.copy2(path, backup)
    add_log(f"RClone {label} backup: {backup}")
    return backup


def import_system_rclone_config_to_portable() -> None:
    src = system_rclone_config_path()
    dst = portable_rclone_config_path(ROOT)
    if not src.exists():
        safe_notify(f"System RClone config was not found: {src}", "warning")
        add_log(f"RClone import skipped: system config not found: {src}")
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    rclone_backup_file(dst, "portable config")
    shutil.copy2(src, dst)
    set_field_value("rclone_config_scope", "portable")
    add_log(f"RClone config imported: {src} -> {dst}")
    safe_notify("System RClone config imported to portable.", "positive")
    command_tree.refresh()


def export_portable_rclone_config_to_system() -> None:
    src = portable_rclone_config_path(ROOT)
    dst = system_rclone_config_path()
    if not src.exists():
        safe_notify(f"Portable RClone config was not found: {src}", "warning")
        add_log(f"RClone export skipped: portable config not found: {src}")
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    rclone_backup_file(dst, "system config")
    shutil.copy2(src, dst)
    add_log(f"RClone config exported: {src} -> {dst}")
    safe_notify("Portable RClone config exported to system.", "positive")
    command_tree.refresh()


def rclone_config_absolute_path_warnings(config_file: Path) -> list[str]:
    if not config_file.exists():
        return []
    warnings: list[str] = []
    try:
        lines = config_file.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        return [f"Cannot read config: {exc}"]
    for index, line in enumerate(lines, 1):
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or not value:
            continue
        if re.match(r"^[A-Za-z]:[\\/]", value) or value.startswith("\\\\"):
            warnings.append(f"line {index}: {key} = {value}")
        if len(warnings) >= 30:
            warnings.append("... more absolute paths omitted")
            break
    return warnings


def run_rclone_config_doctor() -> None:
    options = current_rclone_config_options()
    scope = normalize_config_scope(options.get("config_scope"))
    try:
        config_file = rclone_config_file_for_scope(ROOT, options)
        cache_dir = rclone_cache_dir_for_scope(ROOT, options)
    except Exception as exc:
        safe_notify(str(exc), "negative")
        add_log(f"RClone config doctor error: {exc}")
        return

    add_log("======================================================================")
    add_log("RCLONE CONFIG DOCTOR")
    add_log(f"Scope: {scope}")
    add_log(f"Config: {config_file}")
    add_log(f"Config exists: {bool(config_file and config_file.exists())}")
    if cache_dir is not None:
        add_log(f"Cache: {cache_dir}")
    rclone = find_rclone_executable(ROOT)
    add_log(f"Executable: {rclone or expected_rclone_executable(ROOT)}")
    if rclone is None:
        safe_notify("Rclone executable was not found.", "warning")
        return

    command = [str(rclone), *rclone_global_config_args(ROOT, options, ensure_dirs=True), "listremotes"]
    process = subprocess.run(
        command,
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=rclone_process_env(),
        creationflags=hidden_subprocess_flags(),
        startupinfo=hidden_subprocess_startupinfo(),
        check=False,
    )
    remotes = [line.strip() for line in str(process.stdout or "").splitlines() if line.strip()]
    add_log(f"listremotes exit: {process.returncode}")
    add_log("Remotes: " + (", ".join(remotes) if remotes else "(none)"))
    if process.returncode:
        add_log("STDERR: " + redact_rclone_line(str(process.stderr or "").strip()))

    warnings = rclone_config_absolute_path_warnings(config_file) if config_file is not None else []
    if warnings:
        add_log("Absolute path warnings:")
        for warning in warnings:
            add_log(f"  {warning}")
    else:
        add_log("Absolute path warnings: none")
    safe_notify("RClone config doctor finished.", "positive" if process.returncode == 0 else "warning")


def rclone_select_dict(items: dict[str, dict[str, str]]) -> dict[str, str]:
    label_key = "label_ru" if settings.language == "ru" else "label"
    return {key: str(item.get(label_key) or item.get("label") or key) for key, item in items.items()}


def archive_encryption_scope_hint(mode: Any) -> str:
    """Name the algorithm and the formats a mode can use, instead of hiding both."""
    russian = settings.language == "ru"
    formats = ", ".join(
        str(ARCHIVE_FORMATS.get(item, {}).get("label", str(item).upper()))
        for item in sorted(archive_encryption_supported_formats(mode))
    )
    algorithm = ARCHIVE_ENCRYPTION_ALGORITHM
    normalized = normalize_archive_encryption_mode(mode)
    if normalized == "none":
        return "Доступны все форматы." if russian else "Every format is available."
    if normalized == "names":
        return (
            f"{algorithm}. Шифруются и содержимое, и имена файлов. Форматы: {formats}."
            if russian
            else f"{algorithm}. Both contents and file names are encrypted. Formats: {formats}."
        )
    return (
        f"{algorithm}. Содержимое шифруется, имена файлов остаются видимыми. Форматы: {formats}."
        if russian
        else f"{algorithm}. Contents are encrypted, file names stay visible. Formats: {formats}."
    )


def archive_encryption_zip_note() -> str:
    russian = settings.language == "ru"
    return (
        "ZIP не шифруется намеренно: 7-Zip закрывает ZIP устаревшим ZipCrypto, "
        "а вариант с AES-256 не открывается встроенным Проводником Windows. "
        "Для защищённого архива берите 7Z или SFX."
        if russian
        else "ZIP is deliberately not encrypted: 7-Zip closes ZIP with the legacy ZipCrypto, "
        "and the AES-256 variant cannot be opened by Windows Explorer. "
        "Use 7Z or SFX for a protected archive."
    )


def render_archive_encryption_field(field: dict[str, Any], key: str, label: str, value: Any, hint: str) -> None:
    """Encryption is a mode, so it is a row of buttons rather than a dropdown."""
    current = normalize_archive_encryption_mode(value)
    russian = settings.language == "ru"
    options = {
        mode: str(item["label_ru" if russian else "label"])
        for mode, item in ARCHIVE_ENCRYPTION_OPTIONS.items()
    }
    ui.label(label).classes("audion-field-label")
    ui.toggle(
        options=options,
        value=current,
        on_change=lambda event: set_archive_encryption_field(event.value, refresh=True),
    ).props("dense spread no-caps").classes("audion-mode-toggle audion-archive-encryption-toggle w-full")
    ui.label(archive_encryption_scope_hint(current)).classes("audion-field-hint audion-archive-encryption-scope")
    if current != "none":
        ui.label(archive_encryption_zip_note()).classes("audion-field-hint audion-archive-encryption-zip-note")
    if hint:
        ui.label(hint).classes("audion-field-hint")


def default_rclone_layer() -> str:
    """The first layer that exists, rather than a name written down somewhere.

    Merging the sections renamed the layers, and every place that had `cloud`
    spelled out kept pointing at a layer that was gone. The toggle was handed a
    value outside its own options and refused to build — so the section did not
    open at all for anyone whose saved state still said `cloud`.
    """
    return next(iter(RCLONE_LAYER_LAYOUT), "transfer")


def rclone_jump_to_auth_wizard() -> None:
    state.setdefault("field_values", {})["rclone_layer"] = default_rclone_layer()
    set_rclone_mode_from_tile("remote_auth_wizard")


def rclone_start_mode() -> str:
    """The step the operator actually needs first, rather than a fixed default.

    Opening on the transfer itself is only useful once there is somewhere to send
    to. Without rclone, or without a single configured remote, the first useful
    screen is the one that creates a connection.
    """
    if find_rclone_executable(ROOT) is None:
        return "remote_auth_wizard"
    if not rclone_remote_names():
        return "remote_auth_wizard"
    return str(RCLONE_LAYER_LAYOUT[default_rclone_layer()].get("default") or "transfer_run")


def apply_rclone_start_mode() -> None:
    values = state.setdefault("field_values", {})
    layer = normalize_rclone_layer(values.get("rclone_layer"))
    values["rclone_layer"] = layer
    held = str(values.get("rclone_mode") or "")
    if held and held in rclone_layer_modes(layer):
        return  # the operator already chose a mode in this session
    if held:
        # A mode that outlived its section. Nothing crashes — the fields simply
        # gate on modes it is not in, so the section opens nearly empty and looks
        # broken rather than saying anything.
        add_log(f"RCLONE: режим «{held}» больше не существует, открываю раздел заново")
    values["rclone_mode"] = rclone_start_mode()


def render_rclone_remote_picker_field(field: dict[str, Any], key: str, label: str, value: Any, hint: str) -> None:
    """Pick a remote that actually exists instead of typing a name that may not."""
    russian = settings.language == "ru"
    names = rclone_remote_names()
    current = str(value or "").strip().rstrip(":")
    if not current and names:
        current = names[0]
        set_field_value(key, current)

    ui.label(label).classes("audion-field-label")
    if names:
        # A remote is a mutually exclusive choice, so it is a row of buttons, not a dropdown.
        chips = list(names)
        if current and not remote_name_in(names, current):
            chips.append(current)
        with ui.element("div").classes("audion-rclone-remote-row"):
            for name in chips:
                known = remote_name_in(names, name)
                classes = "audion-rclone-remote-chip"
                if name == current:
                    classes += " audion-rclone-remote-chip-active"
                if not known:
                    classes += " audion-rclone-remote-chip-unknown"
                tooltip = (
                    f"Использовать {name}: как remote для этой операции."
                    if known
                    else f"{name}: нет в текущем конфиге RClone. Проверьте scope конфигурации."
                ) if russian else (
                    f"Use {name}: as the remote for this operation."
                    if known
                    else f"{name}: is not in the current RClone config. Check the config scope."
                )
                ui.button(
                    name,
                    on_click=lambda item_name=name: set_rclone_field_and_refresh(key, item_name),
                ).props("dense flat no-caps no-wrap").classes(classes).tooltip(tooltip)
    else:
        ui.input(
            value=current,
            placeholder=str(field.get("placeholder") or "drive"),
            on_change=lambda event: set_field_value(key, str(event.value or "").strip().rstrip(":")),
        ).props("dense outlined").classes("w-full")
        with ui.row().classes("audion-rclone-empty-remotes w-full items-center gap-2"):
            ui.button(
                "ПОДКЛЮЧИТЬ ОБЛАКО" if russian else "CONNECT A CLOUD",
                icon="cloud_sync",
                on_click=rclone_jump_to_auth_wizard,
            ).props("dense flat no-wrap").classes("audion-action rounded-lg")
            ui.label(
                "Подключённых облаков пока нет. Мастер создаст первое."
                if russian
                else "No clouds connected yet. The wizard creates the first one."
            ).classes("audion-field-hint min-w-0 flex-1")
    if hint:
        ui.label(hint).classes("audion-field-hint")


def render_rclone_config_manager_field(field: dict[str, Any], label: str, hint: str) -> None:
    ui.label(label).classes("audion-field-label")
    options = current_rclone_config_options()
    scope = normalize_config_scope(options.get("config_scope"))
    custom_config = str(options.get("custom_config") or "")
    try:
        config_file = rclone_config_file_for_scope(ROOT, options)
        cache_dir = rclone_cache_dir_for_scope(ROOT, options)
    except Exception as exc:
        config_file = None
        cache_dir = None
        add_log(f"RClone config scope error: {exc}")

    with ui.element("div").classes("audion-rclone-config-manager"):
        with ui.row().classes("w-full items-center gap-2"):
            ui.label("Installer RClone").classes("audion-field-hint audion-rclone-config-subtitle")
            ui.button("System", on_click=start_install_system_rclone).props("dense flat no-caps").classes("audion-action rounded-lg").tooltip(
                "Install/update user-scope system RClone in LOCALAPPDATA and user PATH. Does not touch system config."
                if settings.language != "ru"
                else "Установить/обновить user-scope system RClone в LOCALAPPDATA и user PATH. System config не трогает."
            )
            ui.button("Portable", on_click=start_install_rclone).props("dense flat no-caps").classes("audion-action rounded-lg").tooltip(
                "Install/update Tools\\rclone. Does not touch configs."
                if settings.language != "ru"
                else "Установить/обновить Tools\\rclone. Конфиги не трогает."
            )

        with ui.row().classes("w-full items-center gap-2"):
            ui.label("Configuration").classes("audion-field-hint audion-rclone-config-subtitle")
            ui.toggle(
                options=rclone_select_dict(RCLONE_CONFIG_SCOPES),
                value=scope,
                on_change=lambda event: set_rclone_config_scope_and_refresh(event.value),
            ).props("dense no-caps").classes("audion-mode-toggle audion-rclone-scope-toggle").tooltip(
                "Choose which rclone.conf commands will use: portable, system, or an explicit custom path."
                if settings.language != "ru"
                else "Выбрать rclone.conf для команд: portable, system или явный custom path."
            )
            ui.button("Import", on_click=import_system_rclone_config_to_portable).props("dense flat no-caps").classes("audion-action rounded-lg").tooltip(
                "Copy system rclone.conf to portable config with backup."
                if settings.language != "ru"
                else "Скопировать system rclone.conf в portable config с backup."
            )
            ui.button("Export", on_click=export_portable_rclone_config_to_system).props("dense flat no-caps").classes("audion-action rounded-lg").tooltip(
                "Copy portable rclone.conf to system config with backup."
                if settings.language != "ru"
                else "Скопировать portable rclone.conf в system config с backup."
            )
            ui.button("Doctor", on_click=run_rclone_config_doctor).props("dense flat no-caps").classes("audion-action rounded-lg").tooltip(
                "Read-only check: active config path, remotes, and absolute path warnings."
                if settings.language != "ru"
                else "Read-only проверка: active config path, remotes и предупреждения об абсолютных путях."
            )

        if scope == "custom":
            ui.input(
                label="Custom config path" if settings.language != "ru" else "Custom config path",
                value=custom_config,
                placeholder=str(portable_rclone_config_path(ROOT)),
                on_change=lambda event: (set_field_value("rclone_custom_config", str(event.value or "").strip()), command_tree.refresh()),
            ).props("dense outlined").classes("w-full").tooltip(
                "Path to a specific rclone.conf. This is configuration, not an install target."
                if settings.language != "ru"
                else "Путь к конкретному rclone.conf. Это конфигурация, не место установки."
            )

        active_line = f"ACTIVE: {config_file}" if config_file is not None else "ACTIVE: <invalid>"
        if cache_dir is not None:
            active_line += f" | CACHE: {cache_dir}"
        ui.label(active_line).classes("audion-field-hint audion-rclone-config-path")
    if hint:
        ui.label(hint).classes("audion-field-hint")


def rclone_bwlimit_preset_options() -> dict[str, str]:
    return {str(value): f"{value} M" for value in RCLONE_BWLIMIT_MB_PRESETS}


def rclone_bwlimit_mb(value: Any) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    match = re.fullmatch(r"(\d+)\s*(?:m|M)?", text)
    if not match:
        return None
    number = int(match.group(1))
    return number if number > 0 else None


def rclone_bwlimit_current_mode(current: Any) -> str:
    current_text = str(current or "").strip()
    if not current_text:
        return "off"
    stored = str(state.setdefault("field_values", {}).get("rclone_bwlimit_mode") or "").strip().lower()
    if stored in {"preset", "custom"}:
        return stored
    mb = rclone_bwlimit_mb(current_text)
    return "preset" if mb in RCLONE_BWLIMIT_MB_PRESETS else "custom"


def set_rclone_bwlimit_mode(mode: Any) -> None:
    normalized = str(mode or "off").strip().lower()
    if normalized not in {"off", "preset", "custom"}:
        normalized = "off"
    values = state.setdefault("field_values", {})
    values["rclone_bwlimit_mode"] = normalized
    if normalized == "off":
        values["rclone_bwlimit"] = ""
    elif normalized == "preset":
        current_mb = rclone_bwlimit_mb(values.get("rclone_bwlimit"))
        preset = str(current_mb if current_mb in RCLONE_BWLIMIT_MB_PRESETS else values.get("rclone_bwlimit_preset_mb") or 10)
        if preset not in rclone_bwlimit_preset_options():
            preset = "10"
        values["rclone_bwlimit_preset_mb"] = preset
        values["rclone_bwlimit"] = f"{preset}M"
    else:
        current_mb = rclone_bwlimit_mb(values.get("rclone_bwlimit"))
        custom = int(current_mb or values.get("rclone_bwlimit_custom_mb") or 10)
        custom = max(1, min(900, custom))
        values["rclone_bwlimit_custom_mb"] = custom
        values["rclone_bwlimit"] = f"{custom}M"
    command_tree.refresh()


def set_rclone_bwlimit_preset(value: Any) -> None:
    text = str(value or "").strip()
    if text not in rclone_bwlimit_preset_options():
        text = "10"
    values = state.setdefault("field_values", {})
    values["rclone_bwlimit_mode"] = "preset"
    values["rclone_bwlimit_preset_mb"] = text
    values["rclone_bwlimit"] = f"{text}M"
    command_tree.refresh()


def set_rclone_bwlimit_custom(value: Any, control: Any | None = None) -> None:
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        number = 10
    number = max(1, min(900, number))
    values = state.setdefault("field_values", {})
    values["rclone_bwlimit_mode"] = "custom"
    values["rclone_bwlimit_custom_mb"] = number
    values["rclone_bwlimit"] = f"{number}M"
    if control is not None:
        control.value = number
    command_tree.refresh()


def spin_rclone_bwlimit_custom(control: Any, direction: int) -> None:
    current = rclone_bwlimit_mb(state.setdefault("field_values", {}).get("rclone_bwlimit")) or control.value or 10
    try:
        number = int(round(float(current))) + int(direction)
    except (TypeError, ValueError):
        number = 10
    set_rclone_bwlimit_custom(number, control)


def render_rclone_bwlimit_field(field: dict[str, Any], label: str, hint: str) -> None:
    current = str(current_named_field_value("rclone_bwlimit", field_default(field) or "") or "").strip()
    mode = rclone_bwlimit_current_mode(current)
    current_mb = rclone_bwlimit_mb(current)
    values = state.setdefault("field_values", {})
    preset_value = str(current_mb if current_mb in RCLONE_BWLIMIT_MB_PRESETS else values.get("rclone_bwlimit_preset_mb") or 10)
    if preset_value not in rclone_bwlimit_preset_options():
        preset_value = "10"
    custom_value = int(current_mb or values.get("rclone_bwlimit_custom_mb") or 10)
    custom_value = max(1, min(900, custom_value))

    ui.label(label).classes("audion-field-label")
    with ui.element("div").classes("audion-bwlimit-shell"):
        ui.toggle(
            options={
                "off": "Без лимита" if settings.language == "ru" else "Unlimited",
                "preset": "Выбор скорости" if settings.language == "ru" else "Speed preset",
                "custom": "Своя скорость" if settings.language == "ru" else "Custom speed",
            },
            value=mode,
            on_change=lambda event: set_rclone_bwlimit_mode(event.value),
        ).props("dense spread no-caps").classes("audion-mode-toggle audion-bwlimit-toggle w-full").tooltip(
            "Off не добавляет --bwlimit. Выбор скорости и своя скорость взаимоисключающие, чтобы значения не накладывались."
            if settings.language == "ru"
            else "Off does not add --bwlimit. Speed preset and custom speed are mutually exclusive."
        )
        with ui.element("div").classes("audion-bwlimit-row"):
            ui.select(
                options=rclone_bwlimit_preset_options(),
                value=preset_value,
                on_change=lambda event: set_rclone_bwlimit_preset(event.value),
            ).props(
                "dense outlined options-dense popup-content-class=audion-select-popup" + (" disable" if mode != "preset" else "")
            ).classes("audion-select audion-bwlimit-select").tooltip(
                "Фиксированные M-лимиты: 1..9, 10..90, 100, 150, 200, 300, 500, 900."
                if settings.language == "ru"
                else "Fixed M limits: 1..9, 10..90, 100, 150, 200, 300, 500, 900."
            )
            number_input = ui.number(
                value=custom_value,
                min=1,
                max=900,
                step=1,
                on_change=lambda event: set_rclone_bwlimit_custom(event.value),
            ).props("dense outlined suffix=M" + (" disable" if mode != "custom" else "")).classes("audion-number audion-bwlimit-number")
            with number_input.add_slot("append"):
                with ui.element("div").classes("audion-number-spinner"):
                    ui.button(icon="keyboard_arrow_up", on_click=lambda control=number_input: spin_rclone_bwlimit_custom(control, 1)).props(
                        "dense flat round" + (" disable" if mode != "custom" else "")
                    ).classes("audion-number-spin-button")
                    ui.button(icon="keyboard_arrow_down", on_click=lambda control=number_input: spin_rclone_bwlimit_custom(control, -1)).props(
                        "dense flat round" + (" disable" if mode != "custom" else "")
                    ).classes("audion-number-spin-button")
            ui.label(f"--bwlimit {current}" if current else "без ограничения" if settings.language == "ru" else "unlimited").classes(
                "audion-bwlimit-summary"
            )
    if hint:
        ui.label(hint).classes("audion-field-hint")


def rclone_endpoint_preview(role: str) -> tuple[str, str]:
    try:
        spec = endpoint_spec(current_rclone_options(), role)
        return spec.label, spec.spec
    except Exception as exc:
        return f"ERROR: {exc}", ""


# The window's shape, in one place instead of eight hand-written lists.
#
# Layers and their panel groups used to be spelled out four times over — two
# languages by two layers — with the set of modes repeated again inside each.
# A mode added to some of those lists and not the others simply did not appear,
# which is how the endpoint route came to exist for years while being
# unreachable from the Cloud window.
RCLONE_LAYER_LAYOUT: dict[str, dict[str, Any]] = {
    "transfer": {
        "label": "Data transfer",
        "label_ru": "Трансфер данных",
        "default": "transfer_run",
        "groups": [
            {
                "id": "transfer_run",
                "title": "Transfer",
                "title_ru": "Перенос",
                "hint": "One master, a list of machines, one run. The engine follows from each pair.",
                "hint_ru": "Один эталон, список машин, один запуск. Движок под каждую пару выбирается сам.",
                "default": "transfer_run",
                "modes": ["transfer_run"],
            },
            {
                "id": "cloud_storage",
                "title": "Storage",
                "title_ru": "Хранилище",
                "hint": "What is there, how much it takes, duplicates, links and checksums. Nothing is moved.",
                "hint_ru": "Что лежит, сколько занято, дубликаты, ссылки и суммы. Ничего не переносится.",
                "default": "storage_size",
                "modes": [
                    "storage_size",
                    "storage_cleanup",
                    "storage_dedupe",
                    "storage_link",
                    "storage_hashsum",
                    "list_remote_path",
                    "mkdir_remote",
                    "about_remote",
                ],
            },
            {
                "id": "cloud_auth",
                "title": "Connections",
                "title_ru": "Подключения",
                "hint": "Clouds through the browser, R2 and S3-compatible by keys, SFTP, config encryption.",
                "hint_ru": "Облака через браузер, R2 и S3-совместимые по ключам, SFTP, шифрование конфига.",
                "default": "remote_auth_wizard",
                "modes": [
                    "remote_auth_wizard",
                    "remote_create_s3",
                    "remote_create_sftp",
                    "config_encrypt",
                    "config_encryption_check",
                    "config_decrypt",
                ],
            },
            {
                "id": "cloud_diag",
                "title": "Diagnostics",
                "title_ru": "Диагностика",
                "hint": "Remotes, a quick test, rclone itself, and its own config session.",
                "hint_ru": "Список remote, быстрая проверка, сам rclone и его собственная настройка.",
                "default": "list_remotes",
                "modes": ["list_remotes", "remote_test", "version", "config", "gui"],
            },
        ],
    },
}


def rclone_layer_defs() -> dict[str, dict[str, Any]]:
    """Layers, read off the one layout table.

    The hint each layer shows is its groups named in order, so it describes what
    is actually there rather than promising a list somebody has to remember to
    update.
    """
    russian = settings.language == "ru"
    key = "title_ru" if russian else "title"
    defs: dict[str, dict[str, Any]] = {}
    for layer, item in RCLONE_LAYER_LAYOUT.items():
        groups = item["groups"]
        defs[layer] = {
            "label": str(item["label_ru" if russian else "label"]),
            "hint": ", ".join(str(group[key]) for group in groups),
            "default": str(item["default"]),
            "modes": {mode for group in groups for mode in group["modes"]},
        }
    return defs


def rclone_mode_panel_groups() -> list[dict[str, Any]]:
    russian = settings.language == "ru"
    layer = normalize_rclone_layer(current_named_field_value("rclone_layer", default_rclone_layer()))
    groups = RCLONE_LAYER_LAYOUT[layer]["groups"]
    return [
        {
            "id": str(group["id"]),
            "title": str(group["title_ru" if russian else "title"]),
            "hint": str(group.get("hint_ru" if russian else "hint", "")) or ", ".join(
                str(RCLONE_OPERATION_MODES[mode]["label_ru" if russian else "label"])
                for mode in group["modes"]
            ),
            "default": str(group["default"]),
            "modes": list(group["modes"]),
        }
        for group in groups
    ]


def normalize_rclone_layer(value: Any) -> str:
    """A layer that no longer exists falls back to one that does.

    Saved state outlives a rename. `cloud` was written into gui_settings on every
    machine that used the two old sections, and it must not be able to reach the
    toggle after the merge.
    """
    text = str(value or "").strip().lower()
    return text if text in rclone_layer_defs() else default_rclone_layer()


def rclone_layer_modes(layer: Any) -> set[str]:
    item = rclone_layer_defs()[normalize_rclone_layer(layer)]
    return {str(mode) for mode in item.get("modes", set())}


def set_rclone_layer_from_toggle(value: Any) -> None:
    layer = normalize_rclone_layer(value)
    values = state.setdefault("field_values", {})
    values["rclone_layer"] = layer
    current_mode = normalize_rclone_mode(values.get("rclone_mode", "transfer_run"))
    if current_mode not in rclone_layer_modes(layer):
        values["rclone_mode"] = str(rclone_layer_defs()[layer].get("default") or "transfer_run")
    command_tree.refresh()


def render_rclone_layer_toggle_field(field: dict[str, Any], label: str, hint: str) -> None:
    current = normalize_rclone_layer(current_named_field_value("rclone_layer", field_default(field) or default_rclone_layer()))
    defs = rclone_layer_defs()
    ui.label(label).classes("audion-field-label")
    ui.toggle(
        options={layer_id: str(item.get("label") or layer_id) for layer_id, item in defs.items()},
        value=current,
        on_change=lambda event: set_rclone_layer_from_toggle(event.value),
    ).props("dense spread no-caps").classes("audion-mode-toggle audion-rclone-layer-toggle w-full")
    ui.label(str(defs[current].get("hint") or "")).classes("audion-field-hint audion-rclone-layer-hint")
    if hint:
        ui.label(hint).classes("audion-field-hint")


def rclone_mode_tile_groups() -> list[dict[str, Any]]:
    return rclone_mode_panel_groups()










def set_network_mode_from_tile(mode: Any) -> None:
    set_field_value("network_mode", normalize_network_mode(mode))
    command_tree.refresh()






def rclone_mode_panel_id(mode: str) -> str:
    normalized = normalize_rclone_mode(mode)
    for group in rclone_mode_panel_groups():
        if normalized in {str(mode_id) for mode_id in group["modes"]}:
            return str(group["id"])
    return "transfer"


def rclone_mode_panel_group(panel_id: Any, current_mode: str) -> dict[str, Any]:
    panel = str(panel_id or "").strip()
    groups = rclone_mode_panel_groups()
    for group in groups:
        if panel == str(group["id"]):
            return group
    current_panel = rclone_mode_panel_id(current_mode)
    for group in groups:
        if current_panel == str(group["id"]):
            return group
    return groups[0]


def set_rclone_panel_from_tab(panel_id: Any) -> None:
    current = normalize_rclone_mode(current_named_field_value("rclone_mode", "transfer_run"))
    group = rclone_mode_panel_group(panel_id, current)
    set_rclone_mode_from_tile(str(group.get("default") or group["modes"][0]))








def rclone_mode_pipeline_hint(mode: str) -> str:
    normalized = normalize_rclone_mode(mode)
    if settings.language == "ru":
        hints = {
            "version": "Pipeline: найти rclone.exe -> rclone version -> вывод в правый терминал.",
            "list_remotes": "Pipeline: rclone listremotes -> показать настроенные remotes.",
            "remote_test": "Pipeline: remote/path -> rclone lsf --max-depth 1 -> быстрый smoke доступа.",
            "about_remote": "Pipeline: remote:path -> rclone about -> quota/usage.",
            "list_remote_path": "Pipeline: remote:path -> rclone lsf -> список папки.",
            "mkdir_remote": "Pipeline: remote:path -> rclone mkdir -> создать папку.",
            "remote_create_sftp": "Pipeline: user@host:port + auth -> rclone config create/update <remote> sftp -> затем использовать remote:path.",
            "remote_auth_wizard": "Pipeline: remote name + backend -> отдельное окно rclone config create -> browser/OAuth -> remote:path.",
            "config": "Pipeline: отдельное окно rclone config для редких backend-ов и ручной настройки.",
            "gui": "Pipeline: отдельное окно официального local rclone GUI.",
        }
    else:
        hints = {
            "version": "Pipeline: find rclone.exe -> rclone version -> stream to the right terminal.",
            "list_remotes": "Pipeline: rclone listremotes -> show configured remotes.",
            "remote_test": "Pipeline: remote/path -> rclone lsf --max-depth 1 -> quick access smoke test.",
            "about_remote": "Pipeline: remote:path -> rclone about -> quota/usage.",
            "list_remote_path": "Pipeline: remote:path -> rclone lsf -> folder listing.",
            "mkdir_remote": "Pipeline: remote:path -> rclone mkdir -> create folder.",
            "remote_create_sftp": "Pipeline: user@host:port + auth -> rclone config create/update <remote> sftp -> then use remote:path.",
            "remote_auth_wizard": "Pipeline: remote name + backend -> separate rclone config create window -> browser/OAuth -> remote:path.",
            "config": "Pipeline: separate rclone config window for rare backends and manual setup.",
            "gui": "Pipeline: separate official local rclone GUI window.",
        }
    item = RCLONE_OPERATION_MODES[normalized]
    description = str(item.get("description_ru" if settings.language == "ru" else "description") or "")
    return f"{description}\n{hints.get(normalized, '')}".strip()


def render_rclone_mode_tiles_field(field: dict[str, Any], label: str, hint: str) -> None:
    current = normalize_rclone_mode(current_named_field_value("rclone_mode", field_default(field) or "transfer_run"))
    active_panel = rclone_mode_panel_id(current)
    active_group = rclone_mode_panel_group(active_panel, current)
    if not rclone_remote_names():
        russian = settings.language == "ru"
        ui.label(
            "Подключённых облаков пока нет, поэтому раздел открыт на шаге подключения. "
            "Мастер авторизации создаст первое, и остальные режимы станут осмысленными."
            if russian
            else "No clouds are connected yet, so the section opens on the connection step. "
            "The auth wizard creates the first one, and the other modes start to make sense."
        ).classes("audion-field-hint audion-rclone-first-run")
    with ui.element("div").classes("audion-rclone-mode-stack"):
        with ui.tabs(value=active_panel, on_change=lambda event: set_rclone_panel_from_tab(event.value)).props(
            "dense no-caps active-color=primary indicator-color=primary"
        ).classes("audion-rclone-panel-tabs w-full"):
            for group in rclone_mode_panel_groups():
                ui.tab(str(group["id"]), label=str(group["title"])).tooltip(str(group["hint"]))

        ui.label(str(active_group["hint"])).classes("audion-rclone-panel-hint")
        with ui.element("div").classes("audion-rclone-mode-grid"):
            for mode_id in [str(item) for item in active_group["modes"]]:
                item = RCLONE_OPERATION_MODES[mode_id]
                mode_label = str(item.get("label_ru" if settings.language == "ru" else "label") or mode_id)
                is_active = current == mode_id
                classes = "audion-rclone-mode-tile"
                if is_active:
                    classes += " audion-rclone-mode-tile-active"
                ui.button(
                    mode_label,
                    on_click=lambda item_mode=mode_id: set_rclone_mode_from_tile(item_mode),
                ).props("dense flat no-caps no-wrap").classes(classes).tooltip(rclone_mode_pipeline_hint(mode_id))
    ui.label(rclone_mode_pipeline_hint(current).replace("\n", " ")).classes("audion-rclone-mode-current")
    if hint:
        ui.label(hint).classes("audion-field-hint")


def rclone_auth_wizard_tooltip(remote_name: str, backend: str) -> str:
    command = f"rclone config create {remote_name or '<remote>'} {backend or '<backend>'}"
    if settings.language == "ru":
        if backend == "yandex":
            return (
                f"ЗАПУСТИТЬ откроет отдельное окно RClone: {command}. "
                "Remote name уже задан в GUI. Если RClone спросит Client ID и Client Secret, оставьте пусто и нажмите Enter. "
                "Advanced config - Enter/No. Auto config/browser - Yes. В браузере войдите в Yandex и разрешите доступ. "
                f"После success используйте remote как {remote_name or 'yandex'}:<путь>."
            )
        return (
            f"ЗАПУСТИТЬ откроет отдельное окно RClone: {command}. "
            "Remote name уже задан в GUI. Вопросы без собственных ключей/advanced-настроек оставляйте по умолчанию. "
            "Если откроется браузер, войдите в provider и разрешите доступ. "
            f"После success используйте remote как {remote_name or '<remote>'}:<путь>."
        )
    if backend == "yandex":
        return (
            f"RUN opens a separate RClone window: {command}. "
            "Remote name is already set in the GUI. If RClone asks for Client ID and Client Secret, leave them blank and press Enter. "
            "Advanced config: Enter/No. Auto config/browser: Yes. Sign in to Yandex in the browser and allow access. "
            f"After success, use the remote as {remote_name or 'yandex'}:<path>."
        )
    return (
        f"RUN opens a separate RClone window: {command}. "
        "Remote name is already set in the GUI. Keep default answers unless you have custom provider keys or advanced settings. "
        "If a browser opens, sign in and allow access. "
        f"After success, use the remote as {remote_name or '<remote>'}:<path>."
    )


def rclone_endpoint_path_for_display(remote_path: str) -> str:
    try:
        return normalize_remote_path(str(remote_path or ""))
    except ValueError:
        return "<invalid-path>"


def rclone_sftp_run_tooltip(remote_name: str, user: str, host: str, port: str, remote_path: str, auth_method: str) -> str:
    endpoint = f"{user or '<user>'}@{host or '<host>'}:{port or '22'}:{remote_path or '/'}"
    remote_spec = f"{remote_name or 'server'}:{rclone_endpoint_path_for_display(remote_path)}"
    if settings.language == "ru":
        auth_note = {
            "agent": "Auth=ssh-agent: пароль в GUI не вводится; RClone будет использовать ssh-agent.",
            "password": "Auth=password: пароль вводится в masked поле, затем отправляется в rclone obscure - через stdin и не пишется в cache/history.",
            "key_file": "Auth=key_file: укажите путь к private key; пароль в project cache не сохраняется.",
        }.get(auth_method, "Auth задаётся выбранным методом.")
        return (
            f"ЗАПУСТИТЬ создаст/обновит SFTP remote без интерактивного ввода: {remote_name or 'server'} -> {endpoint}. "
            f"{auth_note} После success используйте endpoint в маршрутах как {remote_spec}."
        )
    auth_note = {
        "agent": "Auth=ssh-agent: no GUI password is entered; RClone uses ssh-agent.",
        "password": "Auth=password: the masked password is sent to rclone obscure - through stdin and is not saved to cache/history.",
        "key_file": "Auth=key_file: enter the private key path; no password is stored in project cache.",
    }.get(auth_method, "Auth is controlled by the selected method.")
    return (
        f"RUN creates/updates an SFTP remote without interactive input: {remote_name or 'server'} -> {endpoint}. "
        f"{auth_note} After success, use the endpoint in routes as {remote_spec}."
    )


def rclone_pending_run_tooltip(node: CommandNode) -> str:
    if node.id != "ui_rclone_operations":
        return tr("run")
    mode = normalize_rclone_mode(current_named_field_value("rclone_mode", "transfer_run"))
    values = state.setdefault("field_values", {})
    if mode == "remote_auth_wizard":
        remote_default = "drive"
        remote_name = str(values.get("rclone_auth_remote_name") or remote_default).strip().rstrip(":") or remote_default
        backend = normalize_auth_backend(values.get("rclone_auth_backend", "drive"))
        return rclone_auth_wizard_tooltip(remote_name, backend)
    if mode == "remote_create_sftp":
        remote_name = str(values.get("rclone_auth_remote_name") or "server").strip().rstrip(":") or "server"
        user = str(values.get("rclone_sftp_user") or "user")
        host = str(values.get("rclone_sftp_host") or "")
        port = str(values.get("rclone_sftp_port") or "22")
        remote_path = str(values.get("rclone_sftp_remote_path") or "/home/user/backups")
        auth_method = normalize_sftp_auth_method(values.get("rclone_sftp_auth_method", "agent"))
        return rclone_sftp_run_tooltip(remote_name, user, host, port, remote_path, auth_method)
    if mode in {"config", "gui"}:
        return (
            "Откроется отдельное видимое окно RClone. Используйте его только для интерактивной настройки; токены не сохраняются в project JSON/YAML."
            if settings.language == "ru"
            else "A separate visible RClone window opens. Use it for interactive setup only; tokens are not saved in project JSON/YAML."
        )
    if mode in RCLONE_ROUTE_MODES:
        try:
            spec = rclone_preview_spec()
            route = f"{spec.source_spec or '<source>'} -> {spec.target_spec or '<target>'}"
        except Exception:
            route = "<source> -> <target>"
        return (
            f"Запустить route-mode без отдельного окна: RClone будет копировать/проверять {route}; прогресс и retries видны справа."
            if settings.language == "ru"
            else f"Run the route mode without a separate window: RClone copies/checks {route}; progress and retries are shown on the right."
        )
    return (
        "Запустить выбранную RClone-команду. Обычные операции идут в правом терминале; interactive modes открывают отдельное окно."
        if settings.language == "ru"
        else "Run the selected RClone command. Normal operations stream to the right terminal; interactive modes open a separate window."
    )


def sync_rclone_run_tooltip(tooltip: str) -> None:
    key = "rclone_run_tooltip"
    if state.get(key) == tooltip:
        return
    state[key] = tooltip
    ui.timer(0.05, command_tree.refresh, once=True)


def rclone_apply_auth_remote_to_endpoint(role: str, remote_name: str, remote_path: str) -> None:
    try:
        normalized_remote = normalize_remote_name(remote_name)
        normalized_path = normalize_remote_path(str(remote_path or ""))
    except ValueError as exc:
        safe_notify(str(exc), "warning")
        return
    set_field_value(f"rclone_{role}_kind", "saved_remote")
    set_field_value(f"rclone_{role}_remote_name", normalized_remote)
    set_field_value(f"rclone_{role}_remote_path", normalized_path)
    safe_notify(
        (f"{'Источник' if role == 'source' else 'Приёмник'}: {normalized_remote}:{normalized_path}" if settings.language == "ru" else f"{role.title()}: {normalized_remote}:{normalized_path}"),
        "positive",
    )
    command_tree.refresh()


def rclone_apply_auth_endpoint_tooltip(role: str, remote_name: str, remote_path: str) -> str:
    spec = f"{remote_name or 'server'}:{rclone_endpoint_path_for_display(remote_path)}"
    if settings.language == "ru":
        side = "SOURCE endpoint" if role == "source" else "TARGET endpoint"
        return f"Записать этот SFTP remote в {side}: {spec}. После этого Copy endpoint route использует именно этот remote:path."
    side = "SOURCE endpoint" if role == "source" else "TARGET endpoint"
    return f"Set this server remote as {side}: {spec}. Copy endpoint route will use this exact remote:path."


def render_rclone_endpoint_panel(role: str, title: str, default_kind: str) -> None:
    kind_key = f"rclone_{role}_kind"
    remote_key = f"rclone_{role}_remote_name"
    path_key = f"rclone_{role}_remote_path"
    kind = str(current_named_field_value(kind_key, default_kind) or default_kind)
    remote_default = "server" if role == "target" else "drive"
    path_default = "/home/user/backups" if role == "target" else "Backup"
    remote_name = str(current_named_field_value(remote_key, remote_default) or remote_default).strip().rstrip(":")
    remote_path = str(current_named_field_value(path_key, path_default) or "").strip()
    preview_label, preview_spec = rclone_endpoint_preview(role)

    with ui.expansion(title, value=(role == "source")).classes("audion-rclone-endpoint-expansion w-full"):
        # A link is somewhere to fetch from, so it is offered to the source only.
        kinds = dict(RCLONE_ENDPOINT_KINDS)
        if role != "source":
            kinds.pop("url", None)
        ui.select(
            options=rclone_select_dict(kinds),
            label="Тип endpoint" if settings.language == "ru" else "Endpoint type",
            value=kind,
            on_change=lambda event, item_key=kind_key: set_rclone_field_and_refresh(item_key, event.value),
        ).props("dense outlined options-dense popup-content-class=audion-select-popup").classes("audion-select w-full").tooltip(
            "Выберите локальный Workbench endpoint или сохранённый RClone remote."
            if settings.language == "ru"
            else "Choose a local Workbench endpoint or a saved RClone remote."
        )

        if kind == "url":
            ui.input(
                label="Ссылка" if settings.language == "ru" else "Link",
                value=str(current_named_field_value("rclone_source_url", "") or ""),
                placeholder="https://example.com/setup-3.0.1.exe",
                on_change=lambda event: set_rclone_field_and_refresh("rclone_source_url", str(event.value or "")),
            ).props("dense outlined").classes("w-full").tooltip(
                "Файл заберёт само хранилище — через ваш канал он не пойдёт. "
                "Только http и https. Имя возьмётся из ссылки."
                if settings.language == "ru"
                else "The storage fetches the file itself; it never comes down your channel. "
                "http and https only. The name is taken from the link."
            )
        elif kind == "saved_remote":
            with ui.row().classes("w-full items-start gap-2"):
                ui.input(
                    label="Remote",
                    value=remote_name,
                    placeholder=remote_default,
                    on_change=lambda event, item_key=remote_key: set_rclone_field_and_refresh(item_key, str(event.value or "").strip().rstrip(":")),
                ).props("dense outlined").classes("audion-rclone-remote-name-input").tooltip(
                    "Имя remote из rclone.conf без двоеточия." if settings.language == "ru" else "Remote name from rclone.conf without trailing colon."
                )
                ui.input(
                    label="Remote path" if settings.language != "ru" else "Путь remote",
                    value=remote_path,
                    placeholder=path_default,
                    on_change=lambda event, item_key=path_key: set_rclone_field_and_refresh(item_key, str(event.value or "")),
                ).props("dense outlined").classes("min-w-0 flex-1").tooltip(
                    "Путь внутри remote; пусто означает root." if settings.language == "ru" else "Path inside the remote; empty means root."
                )
        else:
            local_path = current_source_path() if kind == "workbench_source" else current_target_path()
            ui.label(str(local_path)).classes("audion-field-hint audion-rclone-endpoint-local truncate")

        with ui.element("div").classes("audion-rclone-preview audion-rclone-endpoint-preview"):
            with ui.element("div").classes("audion-rclone-preview-line"):
                ui.label("PREVIEW").classes("audion-rclone-preview-key")
                ui.label(preview_label).classes("audion-rclone-preview-value")
            if preview_spec:
                with ui.element("div").classes("audion-rclone-preview-line"):
                    ui.label("SPEC").classes("audion-rclone-preview-key")
                    ui.label(preview_spec).classes("audion-rclone-preview-value")


def render_rclone_endpoint_workbench_field(field: dict[str, Any], label: str, hint: str) -> None:
    ui.label(label).classes("audion-field-label")
    render_rclone_endpoint_panel("source", "SOURCE ENDPOINT" if settings.language != "ru" else "ИСТОЧНИК", "saved_remote")
    render_rclone_endpoint_panel("target", "TARGET ENDPOINT" if settings.language != "ru" else "ПРИЁМНИК", "saved_remote")
    try:
        spec = rclone_preview_spec()
        route = f"{spec.source_spec or '<source>'} -> {spec.target_spec or '<target>'}"
    except Exception as exc:
        route = f"ERROR: {exc}"
    ui.label(route).classes("audion-field-hint audion-rclone-route-summary")
    if hint:
        ui.label(hint).classes("audion-field-hint")


def current_transfer_operation() -> str:
    value = str(current_named_field_value("transfer_operation", OPERATION_MIRROR) or OPERATION_MIRROR)
    return value if value in TRANSFER_OPERATIONS else OPERATION_MIRROR


def current_transfer_delete_ceiling() -> int | None:
    """The number typed into the ceiling field, or nothing at all.

    Nothing is the default and stays the default. Zero is also nothing here — a
    ceiling of zero would forbid every deletion, which is not a mirror, and the
    number field can hold a bare 0 while the person is still typing.
    """
    raw = current_named_field_value("transfer_delete_ceiling", None)
    try:
        ceiling = int(float(raw))
    except (TypeError, ValueError):
        return None
    return ceiling if ceiling > 0 else None


def transfer_target_rows() -> list[dict[str, str]]:
    """The machines the master goes to.

    Kept as a list from the start, with the section's existing single target as
    the first entry, because one destination is the special case and several is
    the daily one: a reference folder changes and the change is carried out to
    every other machine. A pair could not say that, and saying it three times by
    hand is how a machine gets forgotten.
    """
    rows = state.get("transfer_targets")
    if isinstance(rows, list) and rows:
        return [dict(row) for row in rows if isinstance(row, dict)]
    values = state.setdefault("field_values", {})
    return [
        {
            "kind": str(values.get("rclone_target_kind") or "saved_remote"),
            "remote_name": str(values.get("rclone_target_remote_name") or ""),
            "remote_path": str(values.get("rclone_target_remote_path") or ""),
        }
    ]


def set_transfer_target_rows(rows: list[dict[str, str]]) -> None:
    state["transfer_targets"] = [dict(row) for row in rows]
    # The first machine stays mirrored into the single-target fields, so the
    # existing panels, previews and command builder keep working unchanged.
    if rows:
        values = state.setdefault("field_values", {})
        values["rclone_target_kind"] = rows[0].get("kind", "saved_remote")
        values["rclone_target_remote_name"] = rows[0].get("remote_name", "")
        values["rclone_target_remote_path"] = rows[0].get("remote_path", "")
    command_tree.refresh()


def transfer_target_endpoint(row: dict[str, str]):
    options = current_rclone_options()
    options = {
        **options,
        "target_kind": row.get("kind", "saved_remote"),
        "target_remote_name": row.get("remote_name", ""),
        "target_remote_path": row.get("remote_path", ""),
    }
    return endpoint_spec(options, "target")


def render_transfer_targets_field(field: dict[str, Any], label: str, hint: str) -> None:
    """One master, several machines, one run — each row saying its own route."""
    russian = settings.language == "ru"
    rows = transfer_target_rows()
    operation = current_transfer_operation()
    backends = remote_types({"remote_types": rclone_remote_backends()})

    try:
        source = endpoint_spec(current_rclone_options(), "source")
    except Exception:  # noqa: BLE001
        source = None

    ui.label(label).classes("audion-field-label")
    with ui.element("div").classes("audion-transfer-targets"):
        for index, row in enumerate(rows):
            with ui.element("div").classes("audion-transfer-target-row"):
                ui.label(f"{index + 1}").classes("audion-transfer-target-index")
                ui.select(
                    options=rclone_select_dict(RCLONE_ENDPOINT_KINDS),
                    value=row.get("kind") or "saved_remote",
                    on_change=lambda event, i=index: update_transfer_target(i, "kind", event.value),
                ).props("dense outlined options-dense popup-content-class=audion-select-popup").classes(
                    "audion-select audion-transfer-target-kind"
                )
                if (row.get("kind") or "saved_remote") == "saved_remote":
                    ui.select(
                        options=rclone_endpoint_history_options("remote", row.get("remote_name", "")),
                        value=row.get("remote_name") or None,
                        with_input=True,
                        new_value_mode="add-unique",
                        on_change=lambda event, i=index: update_transfer_target(
                            i, "remote_name", str(event.value or "").strip().rstrip(":")
                        ),
                    ).props("dense outlined options-dense placeholder=remote").classes(
                        "audion-select audion-transfer-target-remote"
                    )
                    ui.input(
                        value=row.get("remote_path", ""),
                        placeholder="releases",
                        on_change=lambda event, i=index: update_transfer_target(
                            i, "remote_path", str(event.value or "")
                        ),
                    ).props("dense outlined").classes("min-w-0 flex-1")

                if source is not None:
                    try:
                        target = transfer_target_endpoint(row)
                        plan = transfer_plan(operation, source, target, russian=russian)
                        route = transit_sentence(
                            transit_kind(source, target, backends), source, target, backends, russian=russian
                        )
                        ui.label(f"{plan['engine_label']} - {route}").classes(
                            "audion-field-hint audion-transfer-target-route"
                        )
                    except Exception:  # noqa: BLE001 - half-typed rows are normal
                        pass

                ui.button(
                    icon="close", on_click=lambda i=index: remove_transfer_target(i)
                ).props("dense flat round").classes("audion-transfer-target-remove").tooltip(
                    "Убрать машину из списка" if russian else "Drop this machine from the list"
                )

    ui.button(
        "Добавить машину" if russian else "Add a machine", icon="add", on_click=add_transfer_target
    ).props("dense flat no-caps").classes("audion-transfer-target-add")
    if hint:
        ui.label(hint).classes("audion-field-hint")


def update_transfer_target(index: int, key: str, value: Any) -> None:
    rows = transfer_target_rows()
    if 0 <= index < len(rows):
        rows[index][key] = str(value or "")
        set_transfer_target_rows(rows)


def add_transfer_target() -> None:
    rows = transfer_target_rows()
    rows.append({"kind": "saved_remote", "remote_name": "", "remote_path": ""})
    set_transfer_target_rows(rows)


def remove_transfer_target(index: int) -> None:
    rows = transfer_target_rows()
    if len(rows) <= 1:
        # The section always has somewhere to send to; emptying the list would
        # leave a run button with nothing behind it.
        return
    if 0 <= index < len(rows):
        rows.pop(index)
        set_transfer_target_rows(rows)


def current_transfer_pack_mode() -> str:
    value = str(current_named_field_value("transfer_pack_mode", PACK_NONE) or PACK_NONE)
    return value if value in PACK_MODES else PACK_NONE


def render_transfer_pack_field(field: dict[str, Any], label: str, hint: str) -> None:
    """Send the files, or pack them first and send the archives.

    The archiving section already makes archives well — many folders in, one each,
    formats and encryption per run — so this reaches for it rather than growing a
    second copy. Where it goes and how is decided afterwards exactly as for a
    plain run: by then the staging folder is just a folder.
    """
    russian = settings.language == "ru"
    current = current_transfer_pack_mode()
    ui.label(label).classes("audion-field-label")
    with ui.element("div").classes("audion-transfer-pack-row"):
        for mode_id, item in PACK_MODES.items():
            classes = "audion-transfer-pack-tile"
            if mode_id == current:
                classes += " audion-transfer-pack-tile-active"
            ui.button(
                str(item["label_ru" if russian else "label"]),
                on_click=lambda item_id=mode_id: set_rclone_field_and_refresh("transfer_pack_mode", item_id),
            ).props("dense flat no-caps no-wrap").classes(classes).tooltip(
                str(item["description_ru" if russian else "description"])
            )

    if current == PACK_BEFORE:
        staging = pack_staging_dir(ROOT, str(current_named_field_value("archive_name_prefix", "pack") or "pack"))
        formats = current_named_field_value("archive_formats", ["7z"]) or ["7z"]
        encryption = str(current_named_field_value("archive_encryption", "none") or "none")
        with ui.element("div").classes("audion-transfer-pack-summary"):
            for key, value in (
                ("ФОРМАТ" if russian else "FORMAT", ", ".join(str(item) for item in formats)),
                ("ЗАЩИТА" if russian else "ENCRYPTION", encryption),
                ("СБОРКА" if russian else "STAGING", str(staging)),
            ):
                with ui.element("div").classes("audion-transfer-pack-line"):
                    ui.label(key).classes("audion-transfer-pack-key")
                    ui.label(value).classes("audion-transfer-pack-value")
        ui.label(
            "Настройки берутся из раздела Архивация. Промежуточные архивы лежат в workspace "
            "и снимаются чисткой — в output они не появляются."
            if russian
            else "Settings come from the Archiving section. The archives wait in workspace and are "
            "cleared by cleanup; they never appear in output."
        ).classes("audion-field-hint")
    if hint:
        ui.label(hint).classes("audion-field-hint")


def delete_ceiling_step(value: int, delta: int) -> int | None:
    """Следующее значение потолка. Ниже нуля — пустота, то есть без потолка."""
    step = 1 if value < 10 else (10 if value < 100 else 100)
    nxt = value + step * delta
    if nxt < 0:
        return None
    return nxt


def render_delete_ceiling_chip(russian: bool) -> None:
    """Потолок удалений: подпись, число и два шеврона — как уровень сжатия."""
    raw = current_named_field_value("transfer_delete_ceiling", None)
    try:
        current = int(float(raw)) if raw not in (None, "") else None
    except (TypeError, ValueError):
        current = None

    empty = "без потолка" if russian else "no ceiling"
    value_label: Any = None

    def show(next_value: int | None) -> None:
        set_rclone_field_and_refresh("transfer_delete_ceiling", next_value)

    def spin(delta: int) -> None:
        base = current if current is not None else (0 if delta > 0 else None)
        if base is None:
            return
        show(delete_ceiling_step(base, delta) if current is not None else 1)

    tooltip = (
        "Пусто — без потолка. С числом запуск остановится, не начав удалять, "
        "если в приёмнике лишних файлов оказалось больше: обычно это значит, "
        "что источник смонтировался не туда."
        if russian
        else "Empty means no ceiling. With a number the run stops before deleting anything "
        "if the destination holds more extras than that — usually a sign the source "
        "mounted somewhere unexpected."
    )
    with ui.element("div").classes("audion-transfer-ceiling-row"):
        with ui.element("div").classes("audion-archive-level-chip audion-transfer-ceiling-chip").tooltip(tooltip):
            ui.label(
                "Стоп, если удалений больше" if russian else "Stop if deletions exceed"
            ).classes("audion-archive-level-caption")
            with ui.element("div").classes("audion-archive-level-spinner"):
                value_label = ui.label(str(current) if current is not None else empty).classes(
                    "audion-archive-level-value"
                )
                with ui.element("div").classes("audion-archive-level-spin-stack"):
                    ui.button(icon="keyboard_arrow_up", on_click=lambda: spin(1)).props(
                        "dense flat round"
                    ).classes("audion-archive-level-spin")
                    ui.button(icon="keyboard_arrow_down", on_click=lambda: spin(-1)).props(
                        "dense flat round"
                    ).classes("audion-archive-level-spin")


def render_transfer_operation_field(field: dict[str, Any], label: str, hint: str) -> None:
    """The five operations, as a row of buttons.

    A mutually exclusive choice is a row of buttons in this project, never a
    dropdown — and each of these is a different thing done to the destination,
    not a setting on one thing. What separates them is whether the destination is
    allowed anything of its own: a mirror's is a copy and owns nothing, a one-way
    destination has a life of its own.
    """
    russian = settings.language == "ru"
    current = current_transfer_operation()
    # A command that runs the project's own local engine offers the four it has.
    # Move is not among them, and a button that raises when pressed is worse than
    # one that is not there.
    node = state.get("pending_command")
    offered = TRANSFER_OPERATIONS
    if node is not None and "cli_command" in (node.parameters or {}):
        offered = {key: item for key, item in TRANSFER_OPERATIONS.items() if key in OPERATION_AUDITOR_COMMAND}
        if current not in offered:
            current = OPERATION_MIRROR

    ui.label(label).classes("audion-field-label")
    ui.toggle(
        options={
            operation_id: str(item["label_ru" if russian else "label"])
            for operation_id, item in offered.items()
        },
        value=current,
        on_change=lambda event: set_rclone_field_and_refresh("transfer_operation", event.value),
    ).props("dense spread no-caps").classes(
        "audion-mode-toggle audion-transfer-operation-toggle w-full"
    ).tooltip(
        "Что делаем с приёмником. Выбранное описано строкой ниже."
        if russian
        else "What happens to the destination. The chosen one is described below."
    )
    ui.label(
        str(TRANSFER_OPERATIONS[current]["description_ru" if russian else "description"])
    ).classes("audion-field-hint audion-transfer-operation-current")

    # A dry run is not a sixth operation. Every one of the five has a version of
    # "show me first", and the project already carried one — robocopy_scan — as a
    # mode of its own, which is a flag wearing a button. Before a mirror deletes
    # on three machines is exactly when the question gets asked.
    if hint:
        ui.label(hint).classes("audion-field-hint")


def render_transfer_route_field(field: dict[str, Any], label: str, hint: str) -> None:
    """What will run, where it will go, and why — before anything runs.

    This is the line the window never had. It used to be impossible to tell from
    the screen whether a copy between two clouds would pass through this machine
    or stay inside the provider, or which of the two tools would do the work.
    """
    russian = settings.language == "ru"
    operation = current_transfer_operation()
    ui.label(label).classes("audion-field-label")

    try:
        options = current_rclone_options()
        source = endpoint_spec(options, "source")
        target = endpoint_spec(options, "target")
    except Exception as error:  # noqa: BLE001 - a half-filled pair is normal while typing
        ui.label(
            f"Маршрут пока не собран: {error}" if russian else f"Route not complete yet: {error}"
        ).classes("audion-field-hint")
        return

    objection = route_objection(OPERATION_RCLONE_COMMAND[operation], source, target)
    if objection:
        with ui.element("div").classes("audion-transfer-route audion-transfer-route-refused"):
            ui.label("НЕ ПОЙДЁТ" if russian else "REFUSED").classes("audion-transfer-route-key")
            ui.label(str(objection["reason_ru" if russian else "reason"])).classes("audion-transfer-route-value")
        return

    backends = remote_types({"remote_types": rclone_remote_backends()})
    plan = transfer_plan(operation, source, target, russian=russian)
    sentence = transit_sentence(transit_kind(source, target, backends), source, target, backends, russian=russian)

    with ui.element("div").classes("audion-transfer-route"):
        for key, value in (
            ("КУДА" if russian else "ROUTE", f"{source.label} -> {target.label}"),
            ("КАК" if russian else "PATH", sentence),
            ("ЧЕМ" if russian else "ENGINE", f"{plan['engine_label']} - {plan['engine_reason']}"),
        ):
            with ui.element("div").classes("audion-transfer-route-line"):
                ui.label(key).classes("audion-transfer-route-key")
                ui.label(value).classes("audion-transfer-route-value")
    if hint:
        ui.label(hint).classes("audion-field-hint")


def rclone_remote_backends() -> dict[str, Any]:
    """Backend types of the saved remotes, read once and cached with the list.

    `rclone config dump` is the only way to know whether two remotes sit on the
    same service, which is what decides a direct transfer. It is read from the
    same place the remote list comes from, so it costs nothing extra.
    """
    # A probe may seed this directly; otherwise it comes from the same cache the
    # remote list uses, filled by asking for the list first.
    seeded = state.get("rclone_remote_backends")
    if isinstance(seeded, dict) and seeded:
        return seeded
    rclone_remote_names()
    cached = state.get("rclone_remotes")
    if isinstance(cached, dict) and isinstance(cached.get("backends"), dict):
        return dict(cached["backends"])
    return {}


def render_rclone_s3_fields(remote_name: str) -> None:
    """Connect Cloudflare R2 and its S3-compatible relatives.

    No key and no secret are asked for. The owner points at the file on this
    machine that already holds them and names the section inside it, so nothing
    secret enters the program or the project's rclone.conf — which matters here
    because these projects are portable and travel on a removable disk.
    """
    russian = settings.language == "ru"
    provider = normalize_s3_provider(current_named_field_value("rclone_s3_provider", "Cloudflare"))
    details = RCLONE_S3_PROVIDERS[provider]

    ui.label("Хранилище" if russian else "Storage").classes("audion-field-label")
    with ui.element("div").classes("audion-rclone-provider-row"):
        for provider_id, item in RCLONE_S3_PROVIDERS.items():
            classes = "audion-rclone-provider-tile"
            if provider_id == provider:
                classes += " audion-rclone-provider-tile-active"
            ui.button(
                str(item["label_ru" if russian else "label"]),
                on_click=lambda item_id=provider_id: set_rclone_field_and_refresh("rclone_s3_provider", item_id),
            ).props("dense flat no-caps no-wrap").classes(classes).tooltip(
                (f"Адрес вида {item['endpoint_hint']}" if russian else f"Endpoint like {item['endpoint_hint']}")
                if item["endpoint_hint"]
                else ("Amazon работает по региону, адрес не нужен." if russian else "Amazon works by region; no endpoint.")
            )

    if provider != "AWS":
        ui.input(
            label="Адрес хранилища" if russian else "Endpoint",
            value=str(current_named_field_value("rclone_s3_endpoint", "") or ""),
            placeholder=str(details["endpoint_hint"]),
            on_change=lambda event: set_rclone_field_and_refresh("rclone_s3_endpoint", str(event.value or "")),
        ).props("dense outlined").classes("w-full").tooltip(
            "Без него remote уедет на Amazon и упадёт с ошибкой, которая ничего не скажет о причине. "
            "У Cloudflare адрес содержит идентификатор аккаунта."
            if russian
            else "Without it the remote resolves to Amazon and fails with an error that says nothing about "
            "the cause. Cloudflare's address carries the account id."
        )

    ui.input(
        label="Файл с ключами" if russian else "Credentials file",
        value=str(current_named_field_value("rclone_s3_credentials_file", "") or ""),
        placeholder=r"%USERPROFILE%\.aws\credentials",
        on_change=lambda event: set_rclone_field_and_refresh("rclone_s3_credentials_file", str(event.value or "")),
    ).props("dense outlined").classes("w-full").tooltip(
        "Путь к файлу на этой машине, где ключи уже лежат. В программу они не попадают и в проекте не "
        "сохраняются — в rclone.conf уйдёт только ссылка на этот файл. Пусто означает, что rclone поищет "
        "там, где ищет всегда.\n\n"
        "Формат — как у AWS, секция на хранилище:\n"
        "[r2-releases]\n"
        "aws_access_key_id = ...\n"
        "aws_secret_access_key = ..."
        if russian
        else "Path to the file on this machine that already holds the keys. They never enter the program and "
        "are never stored in the project: rclone.conf gets a reference to this file. Empty means rclone looks "
        "where it always looks.\n\n"
        "AWS format, one section per storage:\n"
        "[r2-releases]\n"
        "aws_access_key_id = ...\n"
        "aws_secret_access_key = ..."
    )

    if provider == "Cloudflare":
        # The link, not the menu path: Cloudflare renames its menu items and this
        # deep link has outlived several of those renames. It is the answer to
        # "where do I even get these keys", asked at the moment it is asked.
        ui.link(
            "Где взять ключи R2 — панель Cloudflare" if russian else "Where to get R2 keys — Cloudflare dashboard",
            "https://dash.cloudflare.com/?to=/:account/r2/overview",
            new_tab=True,
        ).classes("audion-field-hint").tooltip(
            "Account Details → рядом с API Tokens кнопка Manage → Create Account API token.\n"
            "Права: Object Read & Write, с ограничением на нужные бакеты.\n"
            "Secret Access Key показывается один раз — запишите сразу.\n\n"
            "Бакет заводится там же однажды, как диск. Дальше внутри ничего создавать "
            "не нужно: путь r2:releases/3.0.1/setup.exe пишется сразу, папок в S3 нет — "
            "косые черты просто часть имени объекта."
            if russian
            else "Account Details → Manage next to API Tokens → Create Account API token.\n"
            "Permission: Object Read & Write, scoped to the buckets you need.\n"
            "The Secret Access Key is shown once — write it down now.\n\n"
            "A bucket is made there once, like a disk. Nothing inside it needs creating: "
            "r2:releases/3.0.1/setup.exe is written straight away, because S3 has no "
            "folders — the slashes are just part of the file name."
        )

    ui.input(
        label="Секция в файле" if russian else "Profile",
        value=str(current_named_field_value("rclone_s3_profile", "") or ""),
        placeholder="default",
        on_change=lambda event: set_rclone_field_and_refresh("rclone_s3_profile", str(event.value or "")),
    ).props("dense outlined").classes("w-full").tooltip(
        "Один файл может держать ключи от нескольких хранилищ, каждое под своим именем в квадратных скобках. "
        "Пусто означает default."
        if russian
        else "One file can hold the keys for several storages, each under its own name in square brackets. "
        "Empty means default."
    )

    endpoint = str(current_named_field_value("rclone_s3_endpoint", "") or "") or str(details["endpoint_hint"])
    profile = normalize_s3_profile(current_named_field_value("rclone_s3_profile", ""))
    with ui.element("div").classes("audion-rclone-preview audion-rclone-auth-preview"):
        with ui.element("div").classes("audion-rclone-preview-line"):
            ui.label("STORAGE").classes("audion-rclone-preview-key")
            ui.label(f"{details['label']} - {endpoint}").classes("audion-rclone-preview-value")
        with ui.element("div").classes("audion-rclone-preview-line"):
            ui.label("KEYS").classes("audion-rclone-preview-key")
            ui.label(
                f"{current_named_field_value('rclone_s3_credentials_file', '') or 'где rclone ищет всегда'} [{profile}]"
            ).classes("audion-rclone-preview-value")
        with ui.element("div").classes("audion-rclone-preview-line"):
            ui.label("REMOTE").classes("audion-rclone-preview-key")
            ui.label(f"{remote_name}:").classes("audion-rclone-preview-value")


def render_rclone_auth_manager_field(field: dict[str, Any], label: str, hint: str) -> None:
    ui.label(label).classes("audion-field-label")
    mode = normalize_rclone_mode(current_named_field_value("rclone_mode", "remote_create_sftp"))
    backend = normalize_auth_backend(current_named_field_value("rclone_auth_backend", "drive"))
    remote_default = rclone_default_auth_remote_name(mode, backend)
    remote_name = str(current_named_field_value("rclone_auth_remote_name", remote_default) or remote_default).strip().rstrip(":")

    with ui.expansion("REMOTE" if settings.language != "ru" else "REMOTE", value=True).classes("audion-rclone-auth-expansion w-full"):
        ui.input(
            label="Remote name" if settings.language != "ru" else "Имя remote",
            value=remote_name,
            placeholder=remote_default,
            on_change=lambda event: set_rclone_field_and_refresh("rclone_auth_remote_name", str(event.value or "").strip().rstrip(":")),
        ).props("dense outlined").classes("w-full").tooltip(
            "Введите только имя без двоеточия. Пример: server или drive. После success используйте как server:/path или drive:Folder."
            if settings.language == "ru"
            else "Enter only the name, without ':'. Example: server or drive. After success, use it as server:/path or drive:Folder."
        )

        if mode == "remote_auth_wizard":
            russian = settings.language == "ru"
            ui.label("Провайдер" if russian else "Provider").classes("audion-field-label")
            # A provider is a mutually exclusive choice, so it is a row of buttons.
            # A newcomer looks for "Яндекс.Диск", not for an abstract backend id.
            with ui.element("div").classes("audion-rclone-provider-row"):
                for backend_id, item in RCLONE_AUTH_BACKENDS.items():
                    classes = "audion-rclone-provider-tile"
                    if backend_id == backend:
                        classes += " audion-rclone-provider-tile-active"
                    ui.button(
                        str(item["label_ru" if russian else "label"]),
                        on_click=lambda item_id=backend_id: set_rclone_auth_backend_and_refresh(item_id),
                    ).props("dense flat no-caps no-wrap").classes(classes).tooltip(
                        rclone_auth_wizard_tooltip(rclone_default_auth_remote_name(mode, backend_id), backend_id)
                    )
            ui.label(
                "ЗАПУСТИТЬ откроет отдельное окно RClone; оставляйте provider keys пустыми, если у вас нет своих."
                if russian
                else "RUN opens a separate RClone window; leave provider keys blank unless you have your own."
            ).classes("audion-field-hint")
        elif mode == "remote_create_s3":
            render_rclone_s3_fields(remote_name)
        else:
            user = str(current_named_field_value("rclone_sftp_user", "user") or "user")
            host = str(current_named_field_value("rclone_sftp_host", "") or "")
            port = str(current_named_field_value("rclone_sftp_port", "22") or "22")
            remote_path = str(current_named_field_value("rclone_sftp_remote_path", "/home/user/backups") or "/home/user/backups")
            auth_method = normalize_sftp_auth_method(current_named_field_value("rclone_sftp_auth_method", "agent"))
            sftp_run_tip = rclone_sftp_run_tooltip(remote_name, user, host, port, remote_path, auth_method)
            with ui.row().classes("audion-rclone-inline-endpoint w-full items-start gap-1"):
                ui.select(
                    options=rclone_endpoint_history_options("user", user),
                    value=user or None,
                    with_input=True,
                    new_value_mode="add-unique",
                    on_change=lambda event: set_rclone_field_and_refresh("rclone_sftp_user", str(event.value or "")),
                ).props("dense outlined options-dense popup-content-class=audion-select-popup placeholder=user").classes("audion-select audion-rclone-user-input").tooltip(
                    "Введите только SSH user без @. Пример: user." if settings.language == "ru" else "Enter only the SSH user, without @. Example: user."
                )
                ui.label("@").classes("audion-rclone-endpoint-separator")
                ui.select(
                    options=rclone_endpoint_history_options("host", host),
                    value=host or None,
                    with_input=True,
                    new_value_mode="add-unique",
                    on_change=lambda event: set_rclone_field_and_refresh("rclone_sftp_host", str(event.value or "")),
                ).props("dense outlined options-dense popup-content-class=audion-select-popup placeholder=203.0.113.10").classes("audion-select audion-rclone-host-input min-w-0 flex-1").tooltip(
                    "Введите IP или DNS host без ssh:// и без пути. Пример: 203.0.113.10."
                    if settings.language == "ru"
                    else "Enter an IP or DNS host without ssh:// and without a path. Example: 203.0.113.10."
                )
                ui.label(":").classes("audion-rclone-endpoint-separator")
                ui.input(
                    value=port,
                    placeholder="22",
                    on_change=lambda event: set_rclone_field_and_refresh("rclone_sftp_port", str(event.value or "22")),
                ).props("dense outlined").classes("audion-rclone-port-input").tooltip(
                    "Введите TCP port. Обычно 22." if settings.language == "ru" else "Enter the TCP port. Usually 22."
                )
            ui.input(
                label="Remote path" if settings.language != "ru" else "Путь на сервере",
                value=remote_path,
                placeholder="/home/user/backups",
                on_change=lambda event: set_rclone_field_and_refresh("rclone_sftp_remote_path", str(event.value or "")),
            ).props("dense outlined").classes("w-full").tooltip(
                "Введите абсолютный путь на сервере. Пример: /home/user/backups. Кнопки ниже могут записать его в SOURCE/TARGET как server:/home/user/backups."
                if settings.language == "ru"
                else "Enter the absolute server path. Example: /home/user/backups. The buttons below can set it as SOURCE/TARGET: server:/home/user/backups."
            )
            ui.select(
                options=rclone_select_dict(RCLONE_SFTP_AUTH_METHODS),
                label="Auth",
                value=auth_method,
                on_change=lambda event: set_rclone_field_and_refresh("rclone_sftp_auth_method", event.value),
            ).props("dense outlined options-dense popup-content-class=audion-select-popup").classes("audion-select w-full").tooltip(
                "ssh-agent: без пароля в GUI. password: masked ввод, затем rclone obscure - через stdin. key_file: путь к private key."
                if settings.language == "ru"
                else "ssh-agent: no GUI password. password: masked input, then rclone obscure - through stdin. key_file: private key path."
            )
            if auth_method == "password":
                ui.input(
                    label="Password" if settings.language != "ru" else "Пароль",
                    value="",
                    password=True,
                    password_toggle_button=True,
                    on_change=lambda event: set_field_value("rclone_sftp_password", str(event.value or "")),
                ).props("dense outlined autocomplete=off").classes("audion-secret-input w-full").tooltip(
                    "Введите пароль SSH/SFTP для этого запуска. Он не сохраняется в cache/history; GUI передаст его в rclone obscure - через stdin."
                    if settings.language == "ru"
                    else "Enter the SSH/SFTP password for this run. It is not saved to cache/history; the GUI sends it to rclone obscure - through stdin."
                )
            elif auth_method == "key_file":
                render_ssh_material_field(
                    "rclone_sftp_key_file",
                    "Key file" if settings.language != "ru" else "Файл ключа",
                    r"%USERPROFILE%\.ssh\id_rsa",
                    "Введите путь к private key. Пример: %USERPROFILE%\\.ssh\\id_rsa. Для passphrase предпочтительнее ssh-agent."
                    if settings.language == "ru"
                    else "Enter the private key path. Example: %USERPROFILE%\\.ssh\\id_rsa. Prefer ssh-agent for passphrase-protected keys.",
                )
            render_ssh_material_field(
                "rclone_sftp_known_hosts_file",
                "known_hosts",
                r"%USERPROFILE%\.ssh\known_hosts",
                "Обязательно для SFTP: путь к known_hosts, чтобы rclone проверял host key сервера. Пример: %USERPROFILE%\\.ssh\\known_hosts."
                if settings.language == "ru"
                else "Required for SFTP: known_hosts path so rclone verifies the server host key. Example: %USERPROFILE%\\.ssh\\known_hosts.",
            )
            endpoint_line = f"SFTP {user}@{host or '<host>'}:{port}:{remote_path}"
            remote_line = f"{remote_name}:{remote_path.lstrip('/') if remote_path else ''}"
            with ui.element("div").classes("audion-rclone-preview audion-rclone-auth-preview").tooltip(sftp_run_tip):
                with ui.element("div").classes("audion-rclone-preview-line"):
                    ui.label("ENDPOINT").classes("audion-rclone-preview-key")
                    ui.label(endpoint_line).classes("audion-rclone-preview-value")
                with ui.element("div").classes("audion-rclone-preview-line"):
                    ui.label("REMOTE").classes("audion-rclone-preview-key")
                    ui.label(remote_line).classes("audion-rclone-preview-value")
            with ui.row().classes("audion-rclone-auth-actions w-full items-center gap-2"):
                ui.button(
                    icon="login",
                    on_click=lambda name=remote_name, path=remote_path: rclone_apply_auth_remote_to_endpoint("source", name, path),
                ).props("dense flat round").classes("audion-action audion-folder-icon-button").tooltip(
                    rclone_apply_auth_endpoint_tooltip("source", remote_name, remote_path)
                )
                ui.button(
                    icon="outbox",
                    on_click=lambda name=remote_name, path=remote_path: rclone_apply_auth_remote_to_endpoint("target", name, path),
                ).props("dense flat round").classes("audion-action audion-folder-icon-button").tooltip(
                    rclone_apply_auth_endpoint_tooltip("target", remote_name, remote_path)
                )
                ui.button(
                    icon="backspace",
                    on_click=lambda: clear_rclone_endpoint_history_from_ui(),
                ).props("dense flat round").classes("audion-action audion-folder-icon-button").tooltip(
                    "Очистить кэш SFTP user/host и сбросить видимый host." if settings.language == "ru" else "Clear the SFTP user/host cache and reset the visible host."
                )
                ui.label(
                    "SOURCE / TARGET" if settings.language != "ru" else "В SOURCE / TARGET"
                ).classes("audion-field-hint min-w-0 flex-1")
    if hint:
        ui.label(hint).classes("audion-field-hint")


def rclone_plain_summary(spec: Any) -> tuple[str, str]:
    """One sentence saying what the run will do and what it will not touch.

    Built entirely from the already-assembled command spec, so it costs no network
    call and no scan: the operator sees the direction and the consequence before
    pressing RUN, not the flag list.
    """
    russian = settings.language == "ru"
    mode = str(getattr(spec, "mode", ""))
    remote = str(getattr(spec, "remote_spec", "") or "") or ("облако" if russian else "the cloud")
    source_spec = str(getattr(spec, "source_spec", "") or "")
    target_spec = str(getattr(spec, "target_spec", "") or "")
    local_source = display_path(getattr(spec, "local_source", None))
    local_target = display_path(getattr(spec, "local_target", None))

    # Storage and config modes arrived after this function was written and never
    # got a sentence, so half the section showed a RUN button over nothing. The
    # cleanup one matters most: it is the only mode here that removes anything.
    if mode == "storage_size":
        return (
            (f"Посчитаю, сколько занято в {remote}. Ничего не меняется."
             if russian else f"Measures how much {remote} holds. Nothing is changed."),
            "readonly",
        )
    if mode == "storage_dedupe":
        return (
            (f"Покажу в {remote} объекты с одинаковыми именами. Только список, ничего не удаляется."
             if russian else f"Lists objects in {remote} that share a name. A list only; nothing is deleted."),
            "readonly",
        )
    if mode == "storage_cleanup":
        return (
            (f"Уберу из {remote} брошенные части многочастных заливок — их не видно в списке файлов, "
             "а платят за них. Целые файлы не трогаются, но убранное не возвращается."
             if russian else f"Removes abandoned multipart uploads from {remote} — invisible in listings "
             "and still billed. Whole files are untouched, and what goes does not come back."),
            "write",
        )
    if mode == "storage_hashsum":
        return (
            (f"Посчитаю контрольные суммы для {remote} и покажу списком. Ничего не меняется."
             if russian else f"Computes checksums for {remote} and lists them. Nothing is changed."),
            "readonly",
        )
    if mode == "storage_link":
        return (
            (f"Получу публичную ссылку на {remote}. Ссылка открывает доступ всем, у кого она есть."
             if russian else f"Fetches a public link to {remote}. Anyone holding the link has access."),
            "interactive",
        )
    if mode == "remote_create_s3":
        return (
            ("Запишу подключение к S3-совместимому хранилищу — R2, Wasabi, Selectel и другим — "
             "по ключу и endpoint. Файлы не трогаются."
             if russian else "Writes a connection to S3-compatible storage — R2, Wasabi, Selectel and others — "
             "by key and endpoint. No files are touched."),
            "interactive",
        )
    if mode == "config_encryption_check":
        return (
            ("Проверю, зашифрован ли конфиг rclone. Только чтение."
             if russian else "Checks whether the rclone config is encrypted. Read-only."),
            "readonly",
        )
    if mode == "config_encrypt":
        return (
            ("Зашифрую конфиг rclone: имена подключений и ключи станут нечитаемы без фразы. "
             "Фразу нигде не записываю — потеряется, конфиг не открыть."
             if russian else "Encrypts the rclone config: connection names and keys become unreadable without the phrase. "
             "The phrase is not written down anywhere — lose it and the config stays shut."),
            "write",
        )
    if mode == "config_decrypt":
        return (
            ("Сниму шифрование с конфига rclone. Ключи и имена подключений станут видны любому, "
             "кто откроет файл."
             if russian else "Removes encryption from the rclone config. Keys and connection names become visible "
             "to anyone who opens the file."),
            "write",
        )
    if mode == "mkdir_remote":
        if remote.endswith(":"):
            return (
                (
                    f"Путь внутри {remote} не задан, создавать нечего. Заполните «Путь remote»."
                    if russian
                    else f"No path inside {remote} is set, so there is nothing to create. Fill in the remote path."
                ),
                "interactive",
            )
        return (
            (
                f"Создам папку {remote} в облаке. Файлы не трогаются."
                if russian
                else f"Creates the folder {remote} in the cloud. No files are touched."
            ),
            "write",
        )
    if mode == "list_remote_path":
        return (
            (
                f"Покажу, что лежит в {remote}. Только чтение."
                if russian
                else f"Lists what is inside {remote}. Read-only."
            ),
            "readonly",
        )
    if mode == "about_remote":
        return (
            (
                f"Покажу занятое место и квоту для {remote}. Только чтение."
                if russian
                else f"Shows used space and quota for {remote}. Read-only."
            ),
            "readonly",
        )
    if mode == "remote_test":
        return (
            (
                f"Проверю доступ к {remote}, прочитав один уровень. Ничего не меняется."
                if russian
                else f"Checks access to {remote} by reading one level. Nothing changes."
            ),
            "readonly",
        )
    if mode == "list_remotes":
        return (
            (
                "Покажу список подключённых облаков. Только чтение."
                if russian
                else "Lists the connected clouds. Read-only."
            ),
            "readonly",
        )
    if mode == "version":
        return ("Покажу версию rclone." if russian else "Shows the rclone version.", "readonly")
    if mode in {"config", "gui", "remote_auth_wizard", "remote_create_sftp"}:
        return (
            (
                "Откроется отдельное окно rclone для настройки. Файлы не трогаются."
                if russian
                else "Opens a separate rclone window for setup. No files are touched."
            ),
            "interactive",
        )
    return ("", "readonly")


def render_rclone_plain_summary_field(field: dict[str, Any], label: str, hint: str) -> None:
    """What this run does, in a sentence, for every mode that has a RUN button."""
    try:
        sentence, tone = rclone_plain_summary(rclone_preview_spec())
    except Exception:
        if not rclone_remote_names():
            sentence, tone = (
                (
                    "Пока не подключено ни одно облако, запускать нечего. Начните с шага подключения."
                    if settings.language == "ru"
                    else "With no cloud connected there is nothing to run yet. Start with the connection step."
                ),
                "interactive",
            )
        else:
            sentence, tone = "", "readonly"
    if not sentence:
        return
    ui.label(sentence).classes(f"audion-rclone-plain audion-rclone-plain-{tone}")
    if hint:
        ui.label(hint).classes("audion-field-hint")


def render_rclone_command_preview_field(field: dict[str, Any], label: str, hint: str) -> None:
    ui.label(label).classes("audion-field-label")
    pending = state.get("pending_command")
    if isinstance(pending, CommandNode) and pending.id == "ui_rclone_operations":
        sync_rclone_run_tooltip(rclone_pending_run_tooltip(pending))
    fields = rclone_cache_fields()
    rclone_path = find_rclone_executable(ROOT)
    try:
        spec = rclone_preview_spec()
        command_text = command_display(spec.command)
        mode_line = f"MODE: {rclone_mode_label(spec.mode, settings.language)}"
        if spec.remote_spec:
            mode_line += f" | REMOTE: {spec.remote_spec or '<root>'}"
        if spec.source_spec:
            mode_line += f" | SOURCE: {spec.source_spec}"
        if spec.target_spec:
            mode_line += f" | TARGET: {spec.target_spec}"
        if spec.local_source is not None:
            mode_line += f" | SOURCE: {spec.local_source}"
        if spec.local_target is not None:
            mode_line += f" | TARGET: {spec.local_target}"
        config_line = f"CONFIG: {spec.config_scope}"
        if spec.config_file is not None:
            config_line += f" | {spec.config_file}"
        cache_line = f"CACHE: {spec.cache_dir}" if spec.cache_dir is not None else "CACHE: system default"
        log_line = f"LOG: {spec.log_file}"
        if spec.report_file is not None:
            log_line += f" | CHECK: {spec.report_file}"
    except Exception as exc:
        if not rclone_remote_names():
            command_text = (
                "Команда появится, когда будет подключено хотя бы одно облако.\n"
                "Начните с OAuth / config -> Мастер авторизации."
                if settings.language == "ru"
                else "The command appears once at least one cloud is connected.\n"
                "Start with OAuth / config -> Auth wizard."
            )
        else:
            command_text = f"ERROR: {exc.__class__.__name__}: {exc}"
        mode_line = f"MODE: {rclone_mode_label(fields.get('mode'), settings.language)}"
        config_line = "CONFIG: unavailable until fields are valid"
        cache_line = "CACHE: unavailable until fields are valid"
        log_line = "LOG: unavailable until fields are valid"

    exe_line = str(rclone_path or expected_rclone_executable(ROOT))
    if rclone_path is None:
        exe_line += "  [not installed]"

    with ui.element("div").classes("audion-mask-tools audion-rclone-cache-tools"):
        ui.button(icon="push_pin", on_click=rclone_constructor_cache_click_handler("pin")).props("dense flat round").classes("audion-action audion-folder-icon-button").tooltip(cache_action_tooltip("pin", "текущую команду RClone" if settings.language == "ru" else "current RClone command"))
        ui.button(icon="block", on_click=rclone_constructor_cache_click_handler("unpin")).props("dense flat round").classes("audion-action audion-folder-icon-button").tooltip(cache_action_tooltip("unpin", "текущую команду RClone" if settings.language == "ru" else "current RClone command"))
        ui.button(icon="delete", on_click=rclone_constructor_cache_click_handler("delete")).props("dense flat round").classes("audion-action audion-folder-icon-button").tooltip(cache_action_tooltip("delete", "текущую команду RClone" if settings.language == "ru" else "current RClone command"))
        ui.select(
            options=rclone_command_cache_options(fields),
            value=None,
            on_change=rclone_constructor_cache_select,
        ).props("dense outlined clearable options-dense popup-content-class=audion-select-popup").classes("audion-mask-cache-select min-w-0 flex-1")

    with ui.element("div").classes("audion-rclone-preview"):
        with ui.element("div").classes("audion-rclone-preview-line"):
            ui.label("EXE").classes("audion-rclone-preview-key")
            ui.label(exe_line).classes("audion-rclone-preview-value")
        with ui.element("div").classes("audion-rclone-preview-line"):
            ui.label("ROUTE").classes("audion-rclone-preview-key")
            ui.label(mode_line).classes("audion-rclone-preview-value")
        with ui.element("div").classes("audion-rclone-preview-line"):
            ui.label("CONFIG").classes("audion-rclone-preview-key")
            ui.label(config_line).classes("audion-rclone-preview-value")
        with ui.element("div").classes("audion-rclone-preview-line"):
            ui.label("CACHE").classes("audion-rclone-preview-key")
            ui.label(cache_line).classes("audion-rclone-preview-value")
        preview_spec_obj = locals().get("spec")
        if preview_spec_obj is not None and (getattr(preview_spec_obj, "source_spec", "") or getattr(preview_spec_obj, "target_spec", "")):
            with ui.element("div").classes("audion-rclone-preview-line"):
                ui.label("SOURCE").classes("audion-rclone-preview-key")
                ui.label(getattr(preview_spec_obj, "source_spec", "") or "-").classes("audion-rclone-preview-value")
            with ui.element("div").classes("audion-rclone-preview-line"):
                ui.label("TARGET").classes("audion-rclone-preview-key")
                ui.label(getattr(preview_spec_obj, "target_spec", "") or "-").classes("audion-rclone-preview-value")
        with ui.element("div").classes("audion-rclone-preview-line"):
            ui.label("LOG").classes("audion-rclone-preview-key")
            ui.label(log_line).classes("audion-rclone-preview-value")
        ui.textarea(value=command_text).props("dense outlined readonly rows=5 no-resize").classes("audion-rclone-command-preview w-full")
    if hint:
        ui.label(hint).classes("audion-field-hint")


def set_mode_button_field_value(item_key: str, next_value: Any, refresh: bool) -> None:
    set_field_value(item_key, next_value)
    if refresh:
        command_tree.refresh()


def render_field(field: dict[str, Any]) -> None:
    key = field_id(field)
    if not key:
        return
    kind = str(field.get("type", field.get("kind", "text"))).lower()
    if bool(field.get("ui_hidden")):
        current_field_value(field)
        return
    label = field_label(field)
    value = current_field_value(field)
    hint = field_hint(field)

    field_container = ui.element("div").classes(field_container_classes(field))
    if not is_extension_filter_field(field, key):
        tooltip = field_tooltip(field)
        if tooltip:
            field_container.tooltip(tooltip)

    with field_container:
        if kind in {"rclone_command_preview", "rclone-command-preview"}:
            render_rclone_command_preview_field(field, label, hint)
            return

        if kind == "transfer_pack":
            render_transfer_pack_field(field, label, hint)
            return

        if kind == "transfer_targets":
            render_transfer_targets_field(field, label, hint)
            return

        if kind == "transfer_operation":
            render_transfer_operation_field(field, label, hint)
            return

        if kind == "transfer_route":
            render_transfer_route_field(field, label, hint)
            return

        if kind in {"rclone_mode_tiles", "rclone-mode-tiles"}:
            render_rclone_mode_tiles_field(field, label, hint)
            return

        if kind in {"rclone_layer_toggle", "rclone-layer-toggle"}:
            render_rclone_layer_toggle_field(field, label, hint)
            return


        if kind in {"rclone_plain_summary", "rclone-plain-summary"}:
            render_rclone_plain_summary_field(field, label, hint)
            return

        if kind in {"archive_encryption_buttons", "archive-encryption-buttons"}:
            render_archive_encryption_field(field, key, label, value, hint)
            return

        if kind in {"rclone_remote_picker", "rclone-remote-picker"}:
            render_rclone_remote_picker_field(field, key, label, value, hint)
            return

        if kind in {"rclone_config_manager", "rclone-config-manager"}:
            render_rclone_config_manager_field(field, label, hint)
            return

        if kind in {"rclone_endpoint_workbench", "rclone-endpoint-workbench"}:
            render_rclone_endpoint_workbench_field(field, label, hint)
            return

        if kind in {"rclone_auth_manager", "rclone-auth-manager"}:
            render_rclone_auth_manager_field(field, label, hint)
            return

        if kind in {"rclone_bwlimit", "rclone-bwlimit"}:
            render_rclone_bwlimit_field(field, label, hint)
            return


        if kind in {"env_path", "env-path", "sfx_path", "sfx-path"}:
            env_key = str(field.get("env_field") or f"{key}_env")
            env_default = str(field.get("env_default", ""))
            env_value = str(current_named_field_value(env_key, env_default) or env_default)
            resolved: Any = None

            def refresh_resolved() -> None:
                if resolved is not None:
                    resolved.text = resolve_sfx_extract_path(
                        state.setdefault("field_values", {}).get(env_key, env_default),
                        state.setdefault("field_values", {}).get(key, field_default(field)),
                    )

            ui.label(label).classes("audion-field-label")
            with ui.row().classes("w-full items-start gap-2"):
                ui.select(
                    options=SFX_ENV_OPTIONS,
                    value=env_value,
                    on_change=lambda event, item_key=env_key: (set_field_value(item_key, event.value if event.value is not None else env_default), refresh_resolved()),
                ).props("dense outlined options-dense popup-content-class=audion-select-popup").classes("audion-select audion-sfx-env-select")
                ui.input(
                    value=str(value or ""),
                    placeholder=str(field.get("placeholder", "")),
                    on_change=lambda event, item_key=key: (set_field_value(item_key, str(event.value or "")), refresh_resolved()),
                ).props("dense outlined").classes("audion-sfx-path-input min-w-0 flex-1")
                ui.button(
                    tr("pick_folder"),
                    on_click=path_picker_click_handler(key),
                ).props("dense flat no-wrap").classes("audion-action w-20 rounded-lg")
            resolved = ui.label(resolve_sfx_extract_path(env_value, value)).classes("audion-sfx-resolved-path")
            if hint:
                ui.label(hint).classes("audion-field-hint")
            return

        if kind in {"select", "choice", "format"}:
            if key == "network_archive_level":
                render_archive_level_chip(
                    "network_archive_level",
                    caption="Уровень 7Z" if settings.language == "ru" else "7Z level",
                    allowed={"0", "1", "3", "5"},
                )
                if hint:
                    ui.label(hint).classes("audion-field-hint")
                return
            if bool(field.get("refresh_on_change")):
                on_change = lambda event, item_key=key: (set_field_value(item_key, event.value), command_tree.refresh())
            else:
                on_change = lambda event, item_key=key: set_field_value(item_key, event.value)
            ui.select(
                options=select_options(field),
                label=label,
                value=value,
                on_change=on_change,
            ).props("dense outlined options-dense popup-content-class=audion-select-popup").classes("audion-select w-full")
            if hint:
                ui.label(hint).classes("audion-field-hint")
            return

        if kind in {"mode_buttons", "mode-buttons", "segmented"}:
            ui.label(label).classes("audion-field-label")
            ui.toggle(
                options=select_options(field),
                value=value,
                on_change=(
                    lambda event, item_key=key: (set_field_value(item_key, event.value), command_tree.refresh())
                    if bool(field.get("refresh_on_change"))
                    else set_field_value(item_key, event.value)
                ),
            ).props("dense spread no-caps").classes("audion-mode-toggle w-full")
            if hint:
                ui.label(hint).classes("audion-field-hint")
            return

        if kind in {"inline_mode_buttons", "inline-mode-buttons"}:
            with ui.element("div").classes("audion-inline-mode-field"):
                ui.label(label).classes("audion-field-label audion-inline-mode-label")
                ui.toggle(
                    options=select_options(field),
                    value=value,
                    on_change=(
                        lambda event, item_key=key: (set_field_value(item_key, event.value), command_tree.refresh())
                        if bool(field.get("refresh_on_change"))
                        else set_field_value(item_key, event.value)
                    ),
                ).props("dense spread no-caps").classes("audion-mode-toggle audion-inline-mode-toggle w-full")
            if hint:
                ui.label(hint).classes("audion-field-hint")
            return

        if kind in {"inline_radio_chips", "inline-radio-chips"}:
            with ui.element("div").classes("audion-inline-radio-field"):
                ui.label(label).classes("audion-field-label audion-inline-radio-label")
                ui.radio(
                    options=select_options(field),
                    value=value,
                    on_change=(
                        lambda event, item_key=key: (set_field_value(item_key, event.value), command_tree.refresh())
                        if bool(field.get("refresh_on_change"))
                        else set_field_value(item_key, event.value)
                    ),
                ).props("dense inline").classes("audion-choice-row audion-chip-choice audion-inline-radio-chips")
            if hint:
                ui.label(hint).classes("audion-field-hint")
            return

        if kind in {"network_tabs", "network-tabs"}:
            tab_value = normalize_network_panel(value)

            def set_network_tab(event: Any, item_key: str = key) -> None:
                set_field_value(item_key, normalize_network_panel(event.value))
                command_tree.refresh()

            tab_options = select_options(field)
            if isinstance(tab_options, dict):
                tab_items = [(str(option_value), str(option_label)) for option_value, option_label in tab_options.items()]
            else:
                tab_items = [(str(option), str(option)) for option in tab_options]
            with ui.tabs(value=tab_value, on_change=set_network_tab).props(
                "dense no-caps active-color=primary indicator-color=primary"
            ).classes("audion-network-tabs w-full"):
                for option_value, option_label in tab_items:
                    ui.tab(option_value, label=option_label)
            if hint:
                ui.label(hint).classes("audion-field-hint")
            return

        if kind in {"mask_text", "mask-text"}:
            ui.label(label).classes("audion-field-label")
            mask_textarea: Any = None

            def apply_mask_text(next_value: Any, *, notify: bool = False, cache_pin: bool | None = None, cache_remove: bool = False) -> None:
                normalized = masks_to_text(normalize_mask_tokens(next_value))
                set_field_value(key, normalized)
                if mask_textarea is not None:
                    mask_textarea.value = normalized
                if cache_remove:
                    record_mask_cache(normalized, remove=True)
                    safe_notify("Набор масок удалён из кэша.", "positive")
                    command_tree.refresh()
                    return
                if cache_pin is not None:
                    if not normalized:
                        safe_notify("Введите маски через запятую.", "warning")
                        return
                    record_mask_cache(normalized, pinned=cache_pin)
                    safe_notify("Маски закреплены." if cache_pin else "Маски откреплены.", "positive")
                    command_tree.refresh()
                    return
                if notify:
                    if normalized:
                        safe_notify(f"Маски нормализованы: {normalized}", "positive")
                    else:
                        safe_notify("Введите маски через запятую.", "warning")

            def live_mask_text() -> Any:
                return mask_textarea.value if mask_textarea is not None else current_named_field_value(key, "")

            def clear_mask_text() -> None:
                set_field_value(key, "")
                state["manual_mask_picker_globs"] = []
                if key == "manual_mask_text":
                    set_field_value("manual_extensions", [])
                    set_field_value("manual_extensions_exclude", [])
                    update_extension_selection_info("manual_extensions")
                    update_extension_selection_info("manual_extensions_exclude")
                if mask_textarea is not None:
                    mask_textarea.value = ""
                command_tree.refresh()

            with ui.element("div").classes("audion-mask-tools"):
                ui.button(icon="auto_fix_high", on_click=lambda: apply_mask_text(live_mask_text(), notify=True)).props("dense flat round").classes("audion-action audion-folder-icon-button").tooltip(cache_action_tooltip("normalize", "список масок" if settings.language == "ru" else "mask list"))
                ui.button(icon="push_pin", on_click=lambda: apply_mask_text(live_mask_text(), cache_pin=True)).props("dense flat round").classes("audion-action audion-folder-icon-button").tooltip(cache_action_tooltip("pin", "список масок" if settings.language == "ru" else "mask list"))
                ui.button(icon="block", on_click=lambda: apply_mask_text(live_mask_text(), cache_pin=False)).props("dense flat round").classes("audion-action audion-folder-icon-button").tooltip(cache_action_tooltip("unpin", "список масок" if settings.language == "ru" else "mask list"))
                ui.button(icon="delete", on_click=lambda: apply_mask_text(live_mask_text(), cache_remove=True)).props("dense flat round").classes("audion-action audion-folder-icon-button").tooltip(cache_action_tooltip("delete", "список масок" if settings.language == "ru" else "mask list"))
                ui.button(icon="backspace", on_click=clear_mask_text).props("dense flat round").classes("audion-action audion-folder-icon-button").tooltip(cache_action_tooltip("clear", "масок" if settings.language == "ru" else "masks"))
                ui.select(
                    options=mask_cache_options(str(value or "")),
                    value=None,
                    on_change=lambda event: apply_mask_text(clean_mask_cache_selection(event.value)),
                ).props("dense outlined clearable options-dense popup-content-class=audion-select-popup").classes("audion-mask-cache-select min-w-0 flex-1").tooltip(cache_action_tooltip("pick", "список масок" if settings.language == "ru" else "mask list"))
            mask_textarea = ui.textarea(
                value=str(value or ""),
                placeholder=str(field.get("placeholder", "")),
                on_change=lambda event, item_key=key: set_field_value(item_key, str(event.value or "")),
            ).props("dense outlined autogrow rows=4").classes("audion-mask-textarea w-full")
            register_field_widget(key, mask_textarea)
            if hint:
                ui.label(hint).classes("audion-field-hint")
            return

        if kind in {"secret", "password"}:
            ui.input(
                label=label,
                value=str(value) if value is not None else "",
                placeholder=str(field.get("placeholder", "")),
                password=True,
                password_toggle_button=True,
                on_change=lambda event, item_key=key: set_field_value(item_key, event.value),
            ).props("dense outlined autocomplete=off").classes("audion-secret-input w-full")
            if hint:
                ui.label(hint).classes("audion-field-hint")
            return

        if kind in {"radio", "radiobuttons", "radio-buttons"}:
            ui.label(label).classes("audion-field-label")
            ui.radio(
                options=select_options(field),
                value=value,
                on_change=lambda event, item_key=key: set_field_value(item_key, event.value),
            ).props("dense inline").classes("audion-choice-row audion-chip-choice")
            if hint:
                ui.label(hint).classes("audion-field-hint")
            return

        if kind in {"number", "int", "integer", "float"}:
            number_input = ui.number(
                label=label,
                value=value if value != "" else None,
                min=field.get("min"),
                max=field.get("max"),
                step=field.get("step", 1),
                on_change=lambda event, item_key=key: set_field_value(item_key, event.value),
            ).props("dense outlined").classes("audion-number w-full")
            with number_input.add_slot("append"):
                with ui.element("div").classes("audion-number-spinner"):
                    ui.button(
                        icon="keyboard_arrow_up",
                        on_click=lambda item_key=key, item_field=field, control=number_input: spin_number_field(item_field, item_key, control, 1),
                    ).props("dense flat round").classes("audion-number-spin-button")
                    ui.button(
                        icon="keyboard_arrow_down",
                        on_click=lambda item_key=key, item_field=field, control=number_input: spin_number_field(item_field, item_key, control, -1),
                    ).props("dense flat round").classes("audion-number-spin-button")
            if hint:
                ui.label(hint).classes("audion-field-hint")
            return

        if kind in {"checkbox", "bool", "boolean", "toggle"}:
            ui.checkbox(
                label,
                value=bool(value),
                on_change=lambda event, item_key=key: set_field_value(item_key, bool(event.value)),
            ).props("dense").classes("audion-single-checkbox audion-chip-checkbox")
            if hint:
                ui.label(hint).classes("audion-field-hint")
            return

        if kind in {"path_history", "path-history", "path_combo", "path-combo"}:
            role = str(field.get("role") or field.get("history") or "source")
            options = path_history_options(role, str(value or ""))
            pinned = is_path_pinned(role, str(value or ""))
            with ui.row().classes("w-full items-start gap-2"):
                ui.select(
                    options=options,
                    label=label,
                    value=str(value or "") or None,
                    with_input=True,
                    new_value_mode="add-unique",
                    clearable=True,
                    on_change=path_history_change_handler(key),
                ).props("dense outlined options-dense popup-content-class=audion-select-popup").classes("audion-select min-w-0 flex-1")
                ui.button(
                    tr("unpin_path") if pinned else tr("pin_path"),
                    on_click=pin_path_click_handler(key, role),
                ).props("dense flat no-wrap").classes("audion-action w-20 rounded-lg")
                ui.button(
                    tr("pick_folder"),
                    on_click=path_picker_click_handler(key),
                ).props("dense flat no-wrap").classes("audion-action w-20 rounded-lg")
            if hint:
                ui.label(hint).classes("audion-field-hint")
            return

        if is_extension_filter_field(field, key):
            render_extension_include_exclude_field(field, key, label, value, hint)
            return

        if is_checkbox_group(field):
            render_checkbox_group_field(field, key, label, value, hint)
            return

        def default_text_change(event: Any, item_key: str = key) -> None:
            set_field_value(item_key, event.value)
            if bool(field.get("refresh_on_change")):
                command_tree.refresh()

        ui.input(
            label=label,
            value=str(value) if value is not None else "",
            placeholder=str(field.get("placeholder", "")),
            on_change=default_text_change,
        ).props("dense outlined").classes("w-full")
        if hint:
            ui.label(hint).classes("audion-field-hint")


SAFETY_SWITCHES: dict[str, dict[str, Any]] = {
    "run_dry": {
        "parameter": "dry_run",
        "value": True,
        "label": "Сухой прогон",
        "label_en": "Dry run",
        "hint": "Показать, что произошло бы, и ничего не делать.",
        "hint_en": "Show what would happen and do nothing.",
    },
    "run_quarantine": {
        "parameter": "operation_policy",
        "value": "mirror_safe",
        "label": "Лишнее откладывать, а не удалять",
        "label_en": "Set extras aside instead of deleting",
        "hint": "Файлы, которых нет в источнике, уезжают в карантин.",
        "hint_en": "Files missing from the source go to quarantine instead.",
    },
}


def command_supports_switch(node: CommandNode, switch_id: str) -> bool:
    """Whether this switch means anything for this command.

    Judged by the parameter the service already understands: a command that
    carries `dry_run` in its manifest entry knows what to do with it, and one
    that does not would silently ignore the switch — which is worse than not
    offering it.
    """
    return SAFETY_SWITCHES[switch_id]["parameter"] in (node.parameters or {})


def apply_selected_operation(node: CommandNode, parameters: dict[str, Any]) -> dict[str, Any]:
    """One command where there were three, told apart by the chosen operation.

    BACKUP-MIRROR, One-Way sync and Two-Way sync ran the same service through the
    same four fields and differed by a single word — `cli_command`. That made
    three sections out of one, and the difference between them was invisible in
    the manifest until you diffed the entries.

    The operation buttons carry that word now. The service is untouched: it still
    does the quarantine policy, the extension groups and the comparison report,
    all of which this project's own transfer builder does not.
    """
    if "cli_command" not in (node.parameters or {}):
        return parameters
    operation = current_transfer_operation()
    command = OPERATION_AUDITOR_COMMAND.get(operation)
    if not command:
        # Refusing loudly, because the alternative is worse than an error: the
        # parameter would keep whatever the manifest carried, and choosing Move
        # would quietly run a mirror — deleting at the destination instead of
        # emptying the source.
        label = TRANSFER_OPERATIONS.get(operation, {}).get(
            "label_ru" if settings.language == "ru" else "label", operation
        )
        raise RuntimeError(
            f"Операция «{label}» не поддерживается этой командой. Выберите другую."
            if settings.language == "ru"
            else f"This command has no '{label}'. Choose a different operation."
        )
    parameters["cli_command"] = command
    return parameters


def apply_safety_switches(node: CommandNode, parameters: dict[str, Any]) -> dict[str, Any]:
    """Trying something first is not a separate command.

    The manifest used to carry four: backup-dry, sync-dry, sync2-dry and a
    quarantine variant, each a copy of a real command with one value changed.
    That put rehearsals beside the real thing, at the same size, in the same
    list — and there are far more real runs than rehearsals.

    Now the question is asked once, above the operation, and applies to whatever
    is selected.
    """
    parameters = apply_selected_operation(node, parameters)
    for switch_id, switch in SAFETY_SWITCHES.items():
        if not command_supports_switch(node, switch_id):
            continue
        if bool(current_named_field_value(switch_id, False)):
            parameters[switch["parameter"]] = switch["value"]
    return parameters


def operation_from_pending_command(node: CommandNode) -> Operation:
    parameters = apply_safety_switches(node, dict(node.parameters))
    values = state.setdefault("field_values", {})
    for field in node.fields:
        if is_display_only_field(field):
            continue
        key = field_id(field)
        default = field_default(field)
        if key and is_workbench_route_field(field):
            parameters[key] = workbench_value_for_field(field)
        elif key:
            if str(field.get("type", field.get("kind", "text"))).lower() in {"mask_text", "mask-text"}:
                parameters[key] = live_field_value(key, default)
            else:
                parameters[key] = values.get(key, default)
            if is_extension_filter_field(field, key):
                exclude_key = f"{key}_exclude"
                parameters[exclude_key] = values.get(exclude_key, [])
                parameters.setdefault("extension_exclude_field", exclude_key)
    if "manual_mask_text" in parameters:
        parameters["manual_mask_text"] = masks_to_text(normalize_mask_tokens(parameters.get("manual_mask_text", "")))
    if is_disk_route_node(node):
        parameters.setdefault("source_dir", str(current_source_path()))
        parameters.setdefault("target_dir", str(current_target_path()))
        confirmation = pending_confirmation_token(node)
        if confirmation:
            parameters.setdefault("preflight_confirmation", confirmation)
    return node.to_operation(parameters)


def validate_pending_fields(node: CommandNode) -> bool:
    values = state.setdefault("field_values", {})
    for field in command_visible_fields(node.fields):
        if not is_checkbox_group(field):
            continue
        min_selected = int(field.get("min_selected", 0) or 0)
        if min_selected <= 0:
            continue
        key = field_id(field)
        selected = values.get(key, field_default(field))
        if not isinstance(selected, list) or len(selected) < min_selected:
            safe_notify(tr("select_required", field=field_label(field)), "warning")
            return False
    return True


async def run_pending_command(node: CommandNode) -> None:
    if not validate_pending_fields(node):
        return
    if node.id == "ui_mask_copy":
        normalized = set_mask_text(current_named_field_value("manual_mask_text", ""))
        if normalized:
            record_mask_cache(normalized)
    if node.id == "ui_archive_input_folders":
        values = state.setdefault("field_values", {})
        await start_archive_input_folders(
            {
                "formats": values.get("archive_formats", ["zip"]),
                "encryption": values.get("archive_encryption", "none"),
                "password": values.get("archive_password", ""),
                "level": values.get("archive_level", "1"),
                "layout": values.get("archive_layout", "flat"),
                "name_prefix": values.get("archive_name_prefix", ""),
                "name_suffix": values.get("archive_name_suffix", ""),
                "sfx_env": values.get("sfx_extract_env", ""),
                "sfx_path": values.get("sfx_extract_path", "{name}"),
                "sfx_wrappers": values.get("sfx_wrappers", []),
                "verify_after_create": values.get("archive_verify_after_create", True),
                "underscore_spaces": values.get("archive_underscore_spaces", False),
                "delete_source": values.get("archive_delete_source", False),
            }
        )
        return
    if node.id == "ui_rclone_operations":
        await start_rclone_operations(current_rclone_options())
        return
    await start_operation(operation_from_pending_command(node))


def run_pending_click_handler(node: CommandNode):
    async def handler() -> None:
        await run_pending_command(node)

    return handler


def command_node_button(node: CommandNode, *, compact: bool = False, tone_enabled: bool = True) -> None:
    has_children = bool(node.children)
    label = node.display_title(settings.language)
    description = node.display_description(settings.language)
    if has_children and not description:
        description = tr("open_menu")

    row_classes = operation_row_classes(node, compact=compact, tone_enabled=tone_enabled)
    with ui.element("div").classes(row_classes):
        ui.button(
            label,
            on_click=command_click_handler(node),
        ).props("dense flat no-wrap").classes("audion-action audion-operation-button rounded-lg")
        ui.label(description).classes("audion-operation-description")


async def run_inline_command_node(node: CommandNode) -> None:
    if not validate_pending_fields(node):
        return
    await start_operation(operation_from_pending_command(node))


def inline_command_click_handler(node: CommandNode):
    async def handler() -> None:
        await run_inline_command_node(node)

    return handler


def manifest_section_label(section: str) -> str:
    section = str(section or "pipeline").strip().lower()
    labels_ru = {
        "pipeline": "Готовый маршрут Source -> Target",
        "review": "Сначала проверить Diff",
        "checksums": "Служебные __CHECKSUMS__.b3",
    }
    labels_en = {
        "pipeline": "Ready Source -> Target pipeline",
        "review": "Review Diff first",
        "checksums": "Standalone __CHECKSUMS__.b3",
    }
    labels = labels_ru if settings.language == "ru" else labels_en
    return labels.get(section, section)


def render_manifest_extension_summary(field: dict[str, Any]) -> None:
    key = field_id(field)
    if not key:
        return
    exclude_field = _exclude_extension_field(field)
    exclude_key = field_id(exclude_field)
    values = state.setdefault("field_values", {})
    include_value = values.get(key, field_default(field))
    exclude_value = values.get(exclude_key, field.get("exclude_default", []))

    def clear_selection() -> None:
        set_field_value(key, [])
        set_field_value(exclude_key, [])
        update_extension_selection_info(key)
        command_tree.refresh()

    with ui.element("div").classes("audion-manifest-extension-summary w-full"):
        with ui.element("div").classes("audion-mask-tools audion-profile-extension-tools"):
            ui.button(
                "ОЧИСТИТЬ" if settings.language == "ru" else "CLEAR",
                icon="backspace",
                on_click=clear_selection,
            ).props("dense flat no-wrap").classes("audion-action audion-extension-clear-button rounded-md").tooltip(
                "Очистить выбор. Пусто = все файлы." if settings.language == "ru" else "Clear selection. Empty = all files."
            )
        info_widget = ui.textarea(
            label="Собранные расширения" if settings.language == "ru" else "Collected extensions",
            value=extension_selection_info_text(field, include_value, exclude_value),
        ).props("dense outlined readonly autogrow rows=3").classes("audion-extension-selection-info w-full")
    state.setdefault("extension_info_contexts", {})[key] = {
        "field": field,
        "include_key": key,
        "exclude_key": exclude_key,
        "widget": info_widget,
    }
    register_field_widget(f"{key}__info", info_widget)


def render_manifest_tools_panel(parent: CommandNode, nodes: list[CommandNode]) -> None:
    description = parent.display_description(settings.language)
    if description:
        ui.label(description).classes("audion-field-hint")

    visible_fields = command_visible_fields(parent.fields)
    extension_fields = [field for field in visible_fields if is_extension_filter_field(field)]
    option_fields = [field for field in visible_fields if field not in extension_fields]
    if option_fields:
        render_fields_grid(option_fields)
    for field in extension_fields:
        render_manifest_extension_summary(field)

    section_order = ["pipeline", "review", "checksums"]
    grouped: dict[str, list[CommandNode]] = {section: [] for section in section_order}
    for node in nodes:
        section = str(node.parameters.get("manifest_section") or "pipeline").strip().lower()
        grouped.setdefault(section, []).append(node)

    with ui.element("div").classes("audion-manifest-actions"):
        for section in [*section_order, *[key for key in grouped if key not in section_order]]:
            section_nodes = grouped.get(section, [])
            if not section_nodes:
                continue
            ui.label(manifest_section_label(section)).classes("audion-manifest-section-title")
            for node in section_nodes:
                row_classes = operation_row_classes(node, compact=False, tone_enabled=True)
                with ui.element("div").classes(row_classes):
                    ui.button(
                        node.display_title(settings.language),
                        on_click=inline_command_click_handler(node),
                    ).props("dense flat no-wrap").classes("audion-action audion-operation-button rounded-lg")
                    ui.label(node.display_description(settings.language)).classes("audion-operation-description")

    if extension_fields:
        ui.label("Настройка фильтра расширений" if settings.language == "ru" else "Extension filter setup").classes(
            "audion-manifest-section-title audion-manifest-extension-picker-title"
        )
        render_fields_grid(extension_fields)


PREFLIGHT_STATUS_TONE = {
    "ok": "audion-preflight-ok",
    "none": "audion-preflight-ok",
    "disabled": "audion-preflight-muted",
    "unknown": "audion-preflight-muted",
    "low": "audion-preflight-warn",
    "high": "audion-preflight-warn",
    "missing": "audion-preflight-bad",
    "insufficient": "audion-preflight-bad",
    "blocked": "audion-preflight-bad",
}


def preflight_row(label: str, status: str, text: str) -> None:
    with ui.element("div").classes("audion-preflight-line"):
        ui.label(label).classes("audion-preflight-key")
        ui.label(str(status).upper()).classes(f"audion-preflight-status {PREFLIGHT_STATUS_TONE.get(status, 'audion-preflight-muted')}")
        ui.label(text).classes("audion-preflight-value")


def preflight_anchor_text(anchor: dict[str, Any], russian: bool) -> str:
    if not anchor.get("required"):
        return (
            f"Якорь {ANCHOR_FILE_NAME} для этой пары не требуется."
            if russian
            else f"No {ANCHOR_FILE_NAME} required for this pair."
        )
    if anchor.get("ok"):
        return f"{ANCHOR_FILE_NAME}: SOURCE + TARGET"
    missing = [
        name
        for name, present in (("SOURCE", anchor.get("source_present")), ("TARGET", anchor.get("target_present")))
        if not present
    ]
    joined = " + ".join(missing)
    return (
        f"Нет {ANCHOR_FILE_NAME}: {joined}. Похоже на отключённый монтаж, а не на пустую папку."
        if russian
        else f"Missing {ANCHOR_FILE_NAME}: {joined}. This looks like a disconnected mount, not an empty folder."
    )


def render_preflight_card(node: CommandNode) -> None:
    russian = settings.language == "ru"
    try:
        card, last = pending_preflight_card(node)
    except Exception as exc:
        ui.label(f"PREFLIGHT: {exc.__class__.__name__}: {exc}").classes("audion-field-hint")
        return

    free_space = card["free_space"]
    removals = card["removals"]
    with ui.element("div").classes("audion-preflight-card"):
        ui.label("ПРОВЕРКА ПЕРЕД ЗАПУСКОМ" if russian else "PREFLIGHT").classes("audion-section-title")
        preflight_row(
            "ЯКОРЬ" if russian else "ANCHOR",
            str(card["anchor"]["status"]),
            preflight_anchor_text(card["anchor"], russian),
        )
        if last is None:
            preflight_row(
                "МЕСТО" if russian else "SPACE",
                "unknown",
                (
                    f"Свободно на TARGET: {free_space['target_free_text']}. Объём записи станет известен после Compare или Dry run."
                    if russian
                    else f"Free on TARGET: {free_space['target_free_text']}. Planned bytes need a Compare or Dry run first."
                ),
            )
            preflight_row(
                "УДАЛЕНИЯ" if russian else "REMOVALS",
                "unknown",
                (
                    "Плана ещё нет. Сначала Compare или Dry run по этому маршруту."
                    if russian
                    else "No plan yet. Run Compare or Dry run on this route first."
                ),
            )
            return

        preflight_row(
            "МЕСТО" if russian else "SPACE",
            str(free_space["status"]),
            (
                f"Запись {free_space['bytes_to_write_text']} при свободных {free_space['target_free_text']} на TARGET."
                if russian
                else f"Writing {free_space['bytes_to_write_text']} against {free_space['target_free_text']} free on TARGET."
            ),
        )
        removal_text = (
            f"Удалить {removals['files_to_delete']}, в карантин {removals['files_to_quarantine']} "
            f"из {removals['target_files']} файлов TARGET ({removals['share_text']})."
            if russian
            else f"Delete {removals['files_to_delete']}, quarantine {removals['files_to_quarantine']} "
            f"of {removals['target_files']} target files ({removals['share_text']})."
        )
        if removals["guard_would_block"]:
            removal_text += (
                f" Порог {int(removals['ratio_limit'] * 100)}% остановит применение без подтверждения."
                if russian
                else f" The {int(removals['ratio_limit'] * 100)}% ratio guard will stop the apply without a confirmation."
            )
        preflight_row("УДАЛЕНИЯ" if russian else "REMOVALS", str(removals["status"]), removal_text)

        token = pending_confirmation_token(node)
        if token:
            preflight_row(
                "PREVIEW",
                "ok",
                (f"Запуск привязан к этому просмотру: {token}" if russian else f"Apply is bound to this preview: {token}"),
            )


def command_nav_row(trail: list[CommandNode], pending: CommandNode | None) -> None:
    can_go_back = pending is not None or bool(trail)
    if pending is not None:
        title = pending.display_title(settings.language)
    elif trail:
        title = " / ".join(node.display_title(settings.language) for node in trail)
    else:
        title = ""
    if not can_go_back and not title:
        return

    with ui.row().classes("audion-command-nav w-full items-center gap-2"):
        if can_go_back:
            ui.button(
                tr("back"),
                on_click=go_back_command,
            ).props("dense flat no-wrap").classes("audion-action audion-nav-back rounded-lg")
        ui.label(title).classes("audion-command-title min-w-0 flex-1 truncate")
        if pending is not None:
            run_tooltip = str(state.get("rclone_run_tooltip") or rclone_pending_run_tooltip(pending)) if pending.id == "ui_rclone_operations" else tr("run")
            run_button = ui.button(
                tr("run"),
                on_click=run_pending_click_handler(pending),
            ).props("dense flat no-wrap").classes("audion-action audion-nav-run-button rounded-lg")
            run_button.tooltip(run_tooltip)


@ui.refreshable
def command_tree() -> None:
    trail, nodes = current_command_level()
    pending = state.get("pending_command")
    command_nav_row(trail, pending)

    if pending is not None:
        if pending_needs_peazip_tools(pending):
            backend_name, backend_path = current_peazip_dependency(pending)
            with ui.row().classes("w-full items-center gap-2"):
                if backend_path is None:
                    ui.button(
                        "INSTALL PEAZIP",
                        on_click=start_install_peazip,
                    ).props("dense flat no-wrap").classes("audion-action rounded-lg")
                    backend_label = "PeaZip/7Z portable is not installed."
                else:
                    ui.label(backend_name).classes("audion-field-label")
                    backend_label = str(backend_path)
                ui.label(backend_label).classes("audion-field-hint min-w-0 flex-1 truncate")
        if pending.id == "ui_archive_input_folders":
            lz4_path = find_lz4_executable()
            with ui.row().classes("w-full items-center gap-2"):
                if lz4_path is None:
                    ui.button(
                        "INSTALL LZ4",
                        on_click=start_install_lz4,
                    ).props("dense flat no-wrap").classes("audion-action rounded-lg").tooltip(
                        "TAR.LZ4 нужен отдельный lz4.exe: во вложенном 7-Zip lz4 есть только как кодек."
                        if settings.language == "ru"
                        else "TAR.LZ4 needs a standalone lz4.exe: the bundled 7-Zip carries lz4 only as a codec."
                    )
                    lz4_label = (
                        "TAR.LZ4 недоступен, пока не установлен lz4.exe."
                        if settings.language == "ru"
                        else "TAR.LZ4 stays disabled until lz4.exe is installed."
                    )
                else:
                    ui.label("LZ4").classes("audion-field-label")
                    lz4_label = str(lz4_path)
                ui.label(lz4_label).classes("audion-field-hint min-w-0 flex-1 truncate")
        if pending.id == "ui_rclone_operations":
            rclone_path = find_rclone_executable(ROOT)
            russian = settings.language == "ru"
            with ui.row().classes("w-full items-center gap-2"):
                if rclone_path is None:
                    # Same affordance the archive panel already gives for PeaZip and LZ4:
                    # a missing backend offers to install itself instead of only saying it is missing.
                    ui.button(
                        "УСТАНОВИТЬ PORTABLE" if russian else "INSTALL PORTABLE",
                        on_click=start_install_rclone,
                    ).props("dense flat no-wrap").classes("audion-action rounded-lg").tooltip(
                        f"Положить rclone.exe в {ROOT / 'Tools' / 'rclone'} внутри проекта. Систему не трогает, конфиги не трогает."
                        if russian
                        else f"Put rclone.exe into {ROOT / 'Tools' / 'rclone'} inside the project. Touches neither the system nor any config."
                    )
                    ui.button(
                        "УСТАНОВИТЬ SYSTEM" if russian else "INSTALL SYSTEM",
                        on_click=start_install_system_rclone,
                    ).props("dense flat no-wrap").classes("audion-action rounded-lg").tooltip(
                        "Поставить rclone в профиль пользователя (LOCALAPPDATA и user PATH). Права администратора не нужны, system config не трогает."
                        if russian
                        else "Install rclone into the user profile (LOCALAPPDATA and user PATH). No administrator rights, leaves the system config alone."
                    )
                    ui.label(
                        "RClone не установлен. Portable — обычный путь: rclone ложится внутрь проекта и едет вместе с ним. System нужен, только если хочется иметь rclone во всей системе."
                        if russian
                        else "RClone is not installed. Portable is the normal path: rclone goes inside the project and travels with it. System is only for having rclone available system-wide."
                    ).classes("audion-field-hint min-w-0 flex-1")
                else:
                    portable = rclone_path.is_relative_to(ROOT)
                    ui.label("EXE" if russian else "RCLONE").classes("audion-field-label")
                    ui.label("PORTABLE" if portable else "SYSTEM").classes(
                        f"audion-rclone-origin audion-rclone-origin-{'portable' if portable else 'system'}"
                    ).tooltip(
                        (
                            "rclone лежит внутри проекта и переносится вместе с ним."
                            if portable
                            else "Используется системный rclone: своей копии в проекте нет. Это рабочий вариант, но на другой машине его может не оказаться."
                        )
                        if russian
                        else (
                            "rclone lives inside the project, so it travels with it."
                            if portable
                            else "The system rclone is in use: there is no project copy. That works, but another machine may not have it."
                        )
                    )
                    ui.label(str(rclone_path)).classes("audion-field-hint min-w-0 flex-1 truncate")
                    if not portable:
                        ui.button(
                            "В ПРОЕКТ" if russian else "INTO PROJECT",
                            on_click=start_install_rclone,
                        ).props("dense flat no-wrap").classes("audion-action rounded-lg").tooltip(
                            f"Положить свою копию rclone в {ROOT / 'Tools' / 'rclone'}, чтобы проект не зависел от системы."
                            if russian
                            else f"Put a project copy of rclone into {ROOT / 'Tools' / 'rclone'} so the project stops depending on the system."
                        )
        if is_disk_route_node(pending):
            render_preflight_card(pending)
        visible_fields = command_visible_fields(pending.fields)
        if visible_fields:
            render_fields_grid(visible_fields)
        description = pending.display_description(settings.language)
        if description and not visible_fields:
            ui.label(description).classes("text-sm text-gray-400")
        return

    if trail and trail[-1].id == "manifest_tools":
        render_manifest_tools_panel(trail[-1], nodes)
        return

    tone_enabled = bool(trail)
    for node in nodes:
        command_node_button(node, tone_enabled=tone_enabled)


def operation_by_id(operation_id: str) -> Operation | None:
    for operation in [*manifest.operations, *manifest.maintenance_operations]:
        if operation.id == operation_id:
            return operation
    return None


_application_css_cache: dict[str, str] = {}


def application_css(name: str) -> str:
    """A stylesheet that lives next to this module rather than inside it.

    They are plain files rather than one string literal so that rule order — which
    decides which of two equally specific rules wins — is visible and editable, and
    so that add_styles stops being a 2464-line function.
    """
    if name not in _application_css_cache:
        path = Path(__file__).resolve().with_name(name)
        _application_css_cache[name] = path.read_text(encoding="utf-8")
    return _application_css_cache[name]


def add_styles() -> None:
    add_audion_canonical_ui_styles()
    variables_css = "\n".join(
        f"            --{key}: {value};"
        for key, value in sorted(theme_variables().items())
    )
    ui.add_head_html(
        "<style>\n"
        ":root {\n"
        f"{variables_css}\n"
        "}\n"
        f"{application_css('tokens.css')}"
        f"{application_css('theme.css')}"
        "</style>"
    )


def build_ui() -> None:
    ensure_project_dirs(paths)
    if not state["status"]:
        state["status"] = tr("idle")
    if active_theme_mode() == "dark":
        ui.dark_mode().enable()
    else:
        ui.dark_mode().disable()
    add_styles()
    ui.add_head_html(f"<style>{WORKBENCH_LAYOUT_CSS}\n{WORKBENCH_OVERRIDE_CSS}</style>")
    ui.add_head_html(WORKBENCH_FEEDBACK_CSS)

    with ui.header().classes("audion-header h-[42px] items-center justify-between px-4"):
        ui.label(app_title()).classes("audion-header-title text-lg font-bold")
        with ui.row().classes("audion-header-controls items-center gap-2"):
            ui.icon("palette").classes("text-lg")
            ui.select(
                options=theme_options(),
                value=active_theme(),
                on_change=theme_change_handler,
            ).props("dense outlined options-dense").classes("audion-theme-select")
            ui.button(tr("lang_switch"), on_click=toggle_language).props("dense flat").classes("audion-action rounded-lg")
            cancel_button = ui.button(tr("cancel"), on_click=lambda: state.update({"cancel": True})).props("dense flat color=negative")
            cancel_button.visible = False

    with ui.element("div").classes("audion-shell"):
        with ui.column().classes("audion-pane audion-scroll gap-3"):
            with ui.column().classes("audion-panel audion-workspace-panel w-full gap-2 p-2"):
                WORKBENCH_RENDERER.render_address_rows()
                WORKBENCH_RENDERER.render_action_bar()
            ui.label(f"{em('operations')}{tr('operations')}").classes("audion-section-heading")
            command_tree()

        ui.element("div").classes("audion-splitter").props(f'title="{tr("resize_panels")}"')

        with ui.element("div").classes("audion-pane audion-right gap-2 pt-3"):
            # The status row is its own panel now: one line carrying state, message,
            # clock and progress, instead of a caption above a bar.
            with ui.element("div").classes(status_row_classes()) as status_row:
                status_dot_main = ui.element("span").classes("audion-status-dot-mark")
                status_state_label = ui.label(status_state_text()).classes("audion-status-state")
                status_label = ui.label(str(state["status"])).classes("audion-status-message")
                status_clock = ui.label(elapsed_text(None)).classes("audion-status-clock")
                with ui.element("div").classes("audion-status-bar"):
                    status_bar_fill = ui.element("i").style("width: 0%")
                status_percent = ui.label(progress_text()).classes("audion-status-percent")

            with ui.column().classes("audion-terminal-panel w-full gap-2 p-3"):
                with ui.row().classes("audion-log-toolbar w-full items-center gap-2"):
                    ui.label(f"{em('log')}{tr('log')}").classes("text-base font-semibold")
                    ui.space()
                    ui.button(tr("logs"), on_click=lambda: open_folder(paths.logs)).props("dense flat").classes("audion-action rounded-lg").tooltip(audion_folder_button_tooltip("logs", paths.logs))
                    ui.button(tr("report"), on_click=lambda: open_folder(paths.report)).props("dense flat").classes("audion-action rounded-lg").tooltip(audion_folder_button_tooltip("report", paths.report))
                    ui.button(tr("latest_report"), on_click=open_latest_report_click_handler).props("dense flat no-wrap").classes("audion-action rounded-lg").tooltip(audion_terminal_action_tooltip("latest_report"))
                    ui.button(tr("config"), on_click=lambda: open_folder(paths.config)).props("dense flat").classes("audion-action rounded-lg").tooltip(audion_folder_button_tooltip("config", paths.config))
                    clear_log_button = ui.button(icon="delete_sweep", on_click=clear_terminal_log).props("dense flat round").classes("audion-action audion-log-icon-button")
                    clear_log_button.tooltip(audion_terminal_action_tooltip("clear_terminal_window"))
                    expand_log_button = ui.button(icon="open_in_full", on_click=lambda: log_dialog.open()).props("dense flat round").classes("audion-action audion-log-icon-button")
                    expand_log_button.tooltip(audion_terminal_action_tooltip("expand"))
                ui.html(
                    f'<div id="audion-terminal-main" class="audion-terminal" data-history-limit="{TERMINAL_HISTORY_LIMIT}">{terminal_html([])}</div>',
                    sanitize=False,
                ).classes("audion-terminal-host w-full min-h-[66vh]")
                with ui.row().classes("audion-terminal-command-row"):
                    terminal_shell_select = ui.select(
                        options=terminal_shell_options(),
                        label=tr("terminal_shell"),
                        value=str(state.get("terminal_shell") or "powershell"),
                        on_change=lambda event: set_terminal_shell(event.value),
                    ).props("dense outlined options-dense popup-content-class=audion-select-popup").classes("audion-terminal-command audion-terminal-shell").tooltip(audion_terminal_action_tooltip("terminal_shell"))
                    terminal_history_select = ui.select(
                        options=terminal_command_options(),
                        label=tr("terminal_history"),
                        value=terminal_history_value(),
                        on_change=lambda event: select_terminal_history(event),
                    ).props("dense outlined options-dense popup-content-class=audion-select-popup").classes("audion-terminal-command audion-terminal-history").tooltip(audion_terminal_action_tooltip("terminal_history"))
                    terminal_pin_button = ui.button(
                        icon="push_pin",
                        on_click=pin_terminal_command,
                    ).props("dense flat round").classes("audion-action audion-terminal-icon-button audion-terminal-pin")
                    terminal_pin_button.tooltip(audion_terminal_action_tooltip("pin_command"))
                    terminal_unpin_button = ui.button(
                        icon="block",
                        on_click=unpin_terminal_command,
                    ).props("dense flat round").classes("audion-action audion-terminal-icon-button audion-terminal-unpin")
                    terminal_unpin_button.tooltip(audion_terminal_action_tooltip("unpin_command"))
                    terminal_history_clear_button = ui.button(
                        icon="delete",
                        on_click=clear_terminal_command_history,
                    ).props("dense flat round").classes("audion-action audion-terminal-icon-button audion-terminal-history-clear")
                    terminal_history_clear_button.tooltip(audion_terminal_action_tooltip("clear_history"))
                    ui.button(
                        tr("terminal_run"),
                        on_click=terminal_run_click_handler(),
                    ).props("dense flat no-wrap").classes("audion-action audion-terminal-run rounded-lg").tooltip(audion_terminal_action_tooltip("terminal_run"))
                with ui.row().classes("audion-terminal-command-input-row"):
                    terminal_command_input = ui.textarea(
                        label=tr("terminal_command"),
                        value=str(state.get("terminal_command") or ""),
                        on_change=lambda event: set_terminal_command(event.value),
                    ).props(
                        "dense outlined autogrow autocomplete=off autocorrect=off autocapitalize=off spellcheck=false"
                    ).classes("audion-terminal-command audion-terminal-command-input").tooltip(audion_terminal_action_tooltip("terminal_command"))
                with ui.row().classes("audion-terminal-cwd-row"):
                    terminal_cwd_input = ui.input(
                        label=tr("terminal_cwd"),
                        value=str(state.get("terminal_cwd") or ROOT),
                        on_change=lambda event: set_terminal_cwd(event.value),
                    ).props("dense outlined").classes("audion-terminal-command").tooltip(audion_terminal_action_tooltip("terminal_cwd"))
                    ui.button(
                        tr("pick_folder"),
                        on_click=terminal_pick_cwd_click_handler,
                    ).props("dense flat no-wrap").classes("audion-action audion-terminal-picker rounded-lg").tooltip(audion_terminal_action_tooltip("pick_folder"))
                with ui.row().classes("audion-terminal-footer w-full items-center gap-2 px-1 pt-1"):
                    status_dot = ui.label("●").classes(status_dot_classes())
                    terminal_status_label = ui.label(str(state["status"])).classes("min-w-0 flex-1 truncate text-xs")

    with ui.dialog() as log_dialog:
        with ui.card().classes("audion-dialog h-[92vh] w-[92vw] rounded-lg p-3"):
            with ui.row().classes("w-full items-center gap-2"):
                ui.label(f"{em('log')}{tr('log')}").classes("text-base font-semibold")
                ui.space()
                clear_dialog_log_button = ui.button(icon="delete_sweep", on_click=clear_terminal_log).props("dense flat round").classes("audion-action audion-log-icon-button")
                clear_dialog_log_button.tooltip(audion_terminal_action_tooltip("clear_terminal_window"))
                ui.button(tr("config"), on_click=lambda: open_folder(paths.config)).props("dense flat").classes("audion-action rounded-lg").tooltip(audion_folder_button_tooltip("config", paths.config))
                ui.button(tr("close"), on_click=log_dialog.close).props("dense flat").classes("audion-action rounded-lg").tooltip(audion_terminal_action_tooltip("close"))
            ui.html(
                f'<div id="audion-terminal-expanded" class="audion-terminal audion-terminal-expanded" data-history-limit="{TERMINAL_HISTORY_LIMIT}">{terminal_html([])}</div>',
                sanitize=False,
            ).classes("audion-terminal-host w-full")

    ui.run_javascript(
        """
        (() => {
          window.audionTerminalUpdate = (terminalId, html, reset) => {
            const terminal = document.getElementById(terminalId);
            if (!terminal) return;
            const pre = terminal.querySelector('.audion-terminal-pre');
            if (!pre) return;

            const nearBottom = terminal.scrollTop + terminal.clientHeight >= terminal.scrollHeight - 8;
            if (reset) {
              pre.innerHTML = '';
            }
            if (html) {
              pre.insertAdjacentHTML('beforeend', html);
            }
            const limit = Number(terminal.dataset.historyLimit || '1500');
            let lineCount = pre.querySelectorAll(':scope > .audion-terminal-line').length;
            while (lineCount > limit) {
              const firstLine = pre.querySelector(':scope > .audion-terminal-line');
              if (!firstLine) break;
              const next = firstLine.nextSibling;
              firstLine.remove();
              if (next && next.nodeType === Node.TEXT_NODE && next.textContent.startsWith('\\n')) {
                if (next.textContent.length === 1) {
                  next.remove();
                } else {
                  next.textContent = next.textContent.slice(1);
                }
              }
              lineCount -= 1;
            }
            if (reset || nearBottom) {
              requestAnimationFrame(() => {
                terminal.scrollTop = terminal.scrollHeight;
              });
            }
          };

          const storageKey = 'audion_disk_auditor_terminal_width_px';
          const defaultWidth = 666;
          const minLeft = 460;
          const minRight = 460;

          const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

          const applyWidth = (width) => {
            const shell = document.querySelector('.audion-shell');
            if (!shell) return;
            const rect = shell.getBoundingClientRect();
            const maxRight = Math.max(minRight, rect.width - minLeft - 40);
            const next = clamp(Number(width) || defaultWidth, minRight, maxRight);
            shell.style.setProperty('--audion-terminal-width', `${Math.round(next)}px`);
            localStorage.setItem(storageKey, String(Math.round(next)));
          };

          const setup = () => {
            const shell = document.querySelector('.audion-shell');
            const splitter = document.querySelector('.audion-splitter');
            if (!shell || !splitter) {
              setTimeout(setup, 80);
              return;
            }
            if (splitter.dataset.audionReady === '1') return;
            splitter.dataset.audionReady = '1';

            applyWidth(localStorage.getItem(storageKey) || defaultWidth);

            let dragging = false;
            const updateFromEvent = (event) => {
              if (!dragging) return;
              const rect = shell.getBoundingClientRect();
              const rightWidth = rect.right - event.clientX - 10;
              applyWidth(rightWidth);
            };

            splitter.addEventListener('pointerdown', (event) => {
              dragging = true;
              splitter.setPointerCapture?.(event.pointerId);
              document.body.classList.add('audion-resizing');
              event.preventDefault();
            });
            splitter.addEventListener('pointermove', updateFromEvent);
            splitter.addEventListener('pointerup', (event) => {
              dragging = false;
              splitter.releasePointerCapture?.(event.pointerId);
              document.body.classList.remove('audion-resizing');
            });
            splitter.addEventListener('pointercancel', () => {
              dragging = false;
              document.body.classList.remove('audion-resizing');
            });
            window.addEventListener('resize', () => applyWidth(localStorage.getItem(storageKey) || defaultWidth));
          };

          setup();
        })();
        """
    )

    last_log_version = {"value": -1}
    last_terminal_epoch = {"value": -1}
    last_terminal_totals = {"audion-terminal-main": 0, "audion-terminal-expanded": 0}
    last_terminal_cwd_version = {"value": -1}
    last_terminal_command_version = {"value": -1}

    refresh_timer: Any | None = None

    # Every one of these used to be written twice a second whether or not it had
    # changed, so an idle window still sent ten element updates a second. Holding
    # the last value makes an idle panel cost nothing and pays for the clock.
    shown = {"status": None, "state": None, "row": None, "clock": None, "percent": None, "fill": None}
    run_clock: dict[str, float | None] = {"started": None, "frozen": None}

    def refresh() -> None:
        nonlocal refresh_timer
        try:
            running = bool(state["running"])
            if running and run_clock["started"] is None:
                run_clock["started"] = time.monotonic()
                run_clock["frozen"] = None
            elif not running and run_clock["started"] is not None:
                run_clock["frozen"] = time.monotonic() - run_clock["started"]
                run_clock["started"] = None
            seconds = (
                time.monotonic() - run_clock["started"]
                if run_clock["started"] is not None
                else run_clock["frozen"]
            )

            def show(key: str, value: Any, assign: Any) -> None:
                if shown[key] != value:
                    shown[key] = value
                    assign(value)

            message = str(state["status"])
            show("status", message, lambda value: (
                setattr(status_label, "text", value),
                setattr(terminal_status_label, "text", value),
            ))
            show("state", status_state_text(), lambda value: setattr(status_state_label, "text", value))
            show("row", status_row_classes(), lambda value: (
                status_row.classes(replace=value),
                status_dot.classes(replace=status_dot_classes()),
            ))
            show("clock", elapsed_text(seconds), lambda value: setattr(status_clock, "text", value))
            show("percent", progress_text(), lambda value: setattr(status_percent, "text", value))
            show("fill", f"{float(state['progress']) * 100:.1f}%",
                 lambda value: status_bar_fill.style(f"width: {value}"))
            cwd_version = int(state.get("terminal_cwd_version", 0))
            if cwd_version != last_terminal_cwd_version["value"]:
                last_terminal_cwd_version["value"] = cwd_version
                terminal_cwd_input.value = str(state.get("terminal_cwd") or ROOT)
            command_version = int(state.get("terminal_command_version", 0))
            if command_version != last_terminal_command_version["value"]:
                last_terminal_command_version["value"] = command_version
                terminal_command_input.value = str(state.get("terminal_command") or "")
                terminal_history_select.set_options(terminal_command_options())
            log_version = int(state["log_version"])
            if log_version != last_log_version["value"]:
                last_log_version["value"] = log_version
                terminal_epoch = int(state.get("terminal_epoch", 0))
                epoch_changed = terminal_epoch != last_terminal_epoch["value"]
                last_terminal_epoch["value"] = terminal_epoch
                current_lines = list(state["lines"])
                total_lines = int(state.get("terminal_total_lines", len(current_lines)))
                visible_start_total = max(0, total_lines - len(current_lines))
                for terminal_id, previous_total in list(last_terminal_totals.items()):
                    reset = epoch_changed or previous_total < visible_start_total or total_lines < previous_total
                    if reset:
                        payload = terminal_lines_html(current_lines)
                        last_terminal_totals[terminal_id] = total_lines
                    else:
                        new_count = max(0, total_lines - previous_total)
                        payload = terminal_lines_html(current_lines[-new_count:] if new_count else [], leading_newline=previous_total > 0)
                        last_terminal_totals[terminal_id] = total_lines
                    if payload or reset:
                        ui.run_javascript(
                            "window.audionTerminalUpdate"
                            f"({json.dumps(terminal_id)}, {json.dumps(payload)}, {json.dumps(reset)});"
                        )
            cancel_button.visible = bool(state["running"])
        except RuntimeError as exc:
            message = str(exc)
            if "slot belongs to has been deleted" not in message and "current slot cannot be determined" not in message:
                raise
            logging.warning("NiceGUI refresh timer stopped because the client slot was deleted.")
            if refresh_timer is not None:
                refresh_timer.deactivate()

    refresh_timer = ui.timer(0.5, refresh)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audion NiceGUI shell.")
    parser.add_argument("--host", default=str(ui_info.get("host", "127.0.0.1")))
    parser.add_argument("--port", type=int, default=int(ui_info.get("port", 8080)))
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    return parser.parse_args()


def env_flag_enabled(name: str) -> bool:
    return str(os.environ.get(name, "")).strip().lower() in {"1", "true", "yes", "on"}


def is_loopback_gui_host(host: str) -> bool:
    normalized = str(host or "").strip().lower().strip("[]")
    if normalized == "localhost":
        return True
    if not normalized:
        return False
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def assert_gui_host_allowed(host: str) -> None:
    if is_loopback_gui_host(host):
        return
    if env_flag_enabled("AUDION_ALLOW_REMOTE_GUI"):
        print("WARNING: AUDION_ALLOW_REMOTE_GUI=1 is set. Remote GUI + terminal execution is an RCE surface.")
        return
    raise SystemExit(
        "Refusing non-loopback host for a GUI with terminal execution. "
        "Use 127.0.0.1/localhost/::1, or set AUDION_ALLOW_REMOTE_GUI=1 explicitly."
    )


def port_is_open(host: str, port: int) -> bool:
    family = socket.AF_INET6 if ":" in str(host or "") else socket.AF_INET
    try:
        with socket.socket(family, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.3)
            return sock.connect_ex((host, port)) == 0
    except OSError:
        return False


def build_ui_once() -> dict[str, int]:
    """Build the whole page once, headlessly, and report what came of it.

    `--smoke` used to print a line and return, so an app could ship a `build_ui`
    that raised on its first statement and still pass — twice in this fleet it did.
    Here the page is actually built: no browser and no HTTP request, so whatever
    the app defers until a client attaches is skipped, but every widget is
    constructed and the stylesheet has to arrive.
    """
    import asyncio
    import logging
    import re

    from nicegui import core
    from nicegui.client import Client
    from nicegui.page import page as page_definition

    async def build() -> tuple[int, str]:
        core.loop = asyncio.get_running_loop()
        # Work deferred to a connected browser fails here and says nothing about
        # the build. An exception raised by build_ui itself still propagates.
        core.loop.set_exception_handler(lambda _loop, _context: None)
        logging.getLogger("nicegui").setLevel(logging.CRITICAL)
        client = Client(page_definition("/__smoke__"))
        with client:
            build_ui()
        report = len(client.elements), client.shared_head_html + client.head_html
        # The page starts work that waits for a browser to attach. Nothing will
        # attach, so stop it deliberately instead of letting the loop close on it.
        pending = asyncio.all_tasks(core.loop) - {asyncio.current_task()}
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        return report

    element_count, head = asyncio.run(build())
    if element_count < 2:
        raise RuntimeError("build_ui produced no widgets")
    # Token prefixes differ between apps, so look for any custom property rather
    # than for one project's naming.
    if not re.search(r"--[\w-]+\s*:", head):
        raise RuntimeError("the stylesheet never reached the page")
    return {"elements": element_count, "stylesheet_bytes": len(head)}


def main() -> int:
    args = parse_args()
    ensure_project_dirs(paths)
    assert_gui_host_allowed(args.host)
    if args.smoke:
        try:
            report = build_ui_once()
        except Exception as error:  # noqa: BLE001
            print(f"FAIL nicegui shell: {ROOT}: {error}")
            return 1
        print(
            f"OK nicegui shell: {ROOT}"
            f" | widgets={report['elements']}"
            f" | stylesheet={report['stylesheet_bytes']} bytes"
        )
        return 0

    if port_is_open(args.host, args.port):
        url = f"http://{args.host}:{args.port}/"
        print(f"GUI already appears to be running: {url}")
        if not args.no_browser:
            webbrowser.open(url)
        return 0

    ui.run(
        root=build_ui,
        title=app_title(),
        host=args.host,
        port=args.port,
        reload=False,
        native=False,
        show=not args.no_browser,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
