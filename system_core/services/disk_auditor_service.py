from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any
from datetime import datetime
import json
import os
import shutil
import subprocess
import sys

from system_core.core.jobs import (
    JobContext,
    gui_subprocess_output_kwargs,
    hidden_subprocess_kwargs,
    prepare_gui_subprocess_command,
    utf8_subprocess_env,
)
from system_core.core.terminal_render import iter_process_output_lines


def _python_executable(context: JobContext) -> Path:
    candidates = [
        context.paths.root / "runtime" / "python.exe",
        context.paths.root / "runtime" / "python" / "python.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return Path(sys.executable)


def _main_script(context: JobContext) -> Path:
    return context.paths.system_core / "main.py"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "yes", "true", "on"}


class CliPlanGuardError(RuntimeError):
    def __init__(self, message: str, guard_payload: dict[str, Any]):
        self.guard_payload = guard_payload
        super().__init__(message)


def _split_mask_text(value: Any) -> list[str]:
    if isinstance(value, list):
        raw = ",".join(str(item or "") for item in value)
    else:
        raw = str(value or "")
    for separator in ["\r\n", "\n", "\r", ";"]:
        raw = raw.replace(separator, ",")
    return [item.strip() for item in raw.split(",") if item.strip()]


def _normalize_mask_token(token: Any) -> str:
    text = str(token or "").strip().strip("\"'").replace("\\", "/").lower()
    if not text:
        return ""
    has_glob = any(mark in text for mark in "*?[]")
    has_path = "/" in text
    if has_glob or has_path:
        return text
    if text.startswith("."):
        return f"*{text}"
    return f"*.{text.lstrip('.')}"


def _normalize_mask_tokens(value: Any) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in _split_mask_text(value):
        pattern = _normalize_mask_token(item)
        key = pattern.casefold()
        if pattern and key not in seen:
            result.append(pattern)
            seen.add(key)
    return result


def _pairs_config_for_profile(context: JobContext, pair_name: str) -> Path | None:
    candidates = [
        context.paths.config / "sync_pairs.json",
        context.paths.config / "sync_pairs.example.json",
    ]
    normalized = pair_name.strip().lower()
    fallback: Path | None = None
    for candidate in candidates:
        if not candidate.exists():
            continue
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        pairs = payload.get("pairs")
        if not isinstance(pairs, list):
            continue
        if candidate.name == "sync_pairs.json" and pairs:
            fallback = candidate
        for pair in pairs:
            if isinstance(pair, dict) and _text(pair.get("name")).lower() == normalized:
                return candidate
    return fallback


def _path_history_file(context: JobContext) -> Path:
    return context.paths.config / "path_history.json"


def _history_key(role: str) -> str:
    role_clean = _text(role).lower()
    return "targets" if role_clean in {"target", "targets", "dst", "destination"} else "sources"


def _load_path_history(context: JobContext) -> dict[str, Any]:
    history_file = _path_history_file(context)
    if not history_file.exists():
        return {"sources": [], "targets": []}
    try:
        data = json.loads(history_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"sources": [], "targets": []}
    if not isinstance(data, dict):
        return {"sources": [], "targets": []}
    data.setdefault("sources", [])
    data.setdefault("targets", [])
    return data


def _save_path_history(context: JobContext, data: dict[str, Any]) -> None:
    history_file = _path_history_file(context)
    history_file.parent.mkdir(parents=True, exist_ok=True)
    history_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _record_path_history(context: JobContext, role: str, path_value: str) -> None:
    text = _text(path_value)
    if not text:
        return
    key = _history_key(role)
    data = _load_path_history(context)
    entries = data.get(key, [])
    if not isinstance(entries, list):
        entries = []

    normalized = str(Path(text).expanduser())
    now = datetime.now().isoformat(timespec="seconds")
    updated = False
    cleaned: list[dict[str, Any]] = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        path = _text(item.get("path"))
        if not path:
            continue
        if path.lower() == normalized.lower():
            item["path"] = normalized
            item["count"] = int(item.get("count", 0) or 0) + 1
            item["last_used"] = now
            updated = True
        cleaned.append(item)
    if not updated:
        cleaned.append({"path": normalized, "count": 1, "last_used": now})

    cleaned.sort(
        key=lambda item: (
            bool(item.get("pinned")),
            int(item.get("count", 0) or 0),
            str(item.get("last_used", "")),
        ),
        reverse=True,
    )
    data[key] = cleaned[:100]
    _save_path_history(context, data)


def _selected_extension_globs(parameters: dict[str, Any]) -> list[str]:
    configured_key = _text(parameters.get("extension_field"))
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

    result: list[str] = []
    seen: set[str] = set()
    group_map = parameters.get("extension_groups", {})
    if not isinstance(group_map, dict):
        group_map = {}

    def append_pattern(pattern: str) -> None:
        if pattern and pattern not in seen:
            result.append(pattern)
            seen.add(pattern)

    for item in _normalize_mask_tokens(parameters.get("manual_mask_text", "")):
        append_pattern(item)

    for item in value:
        pattern = _text(item)
        if not pattern:
            continue
        if pattern.startswith("@group:"):
            group_id = pattern.split(":", 1)[1]
            for group_pattern in group_map.get(group_id, []):
                append_pattern(_text(group_pattern))
            continue
        append_pattern(pattern)
    return result


def _extension_exclude_field_key(parameters: dict[str, Any]) -> str:
    configured_key = _text(parameters.get("extension_field"))
    if configured_key:
        return f"{configured_key}_exclude"
    if "manual_extensions" in parameters:
        return "manual_extensions_exclude"
    for key in parameters:
        if str(key).startswith("profile_extensions__"):
            return f"{key}_exclude"
    return "manual_extensions_exclude"


def _selected_exclude_extension_globs(parameters: dict[str, Any]) -> list[str]:
    value = parameters.get(_text(parameters.get("extension_exclude_field")) or _extension_exclude_field_key(parameters), [])
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
        pattern = _text(item)
        if not pattern:
            continue
        if pattern.startswith("@group:"):
            group_id = pattern.split(":", 1)[1]
            for group_pattern in group_map.get(group_id, []):
                append_pattern(_text(group_pattern))
            continue
        append_pattern(pattern)
    return result


def _remove_excluded_patterns(include_globs: list[str], exclude_globs: list[str]) -> list[str]:
    exclude_keys = {str(item or "").strip().casefold() for item in exclude_globs if str(item or "").strip()}
    if not exclude_keys:
        return include_globs
    return [item for item in include_globs if str(item or "").strip().casefold() not in exclude_keys]


def _append_extension_filter(args: list[str], parameters: dict[str, Any], context: JobContext) -> None:
    globs = _selected_extension_globs(parameters)
    exclude_globs = _selected_exclude_extension_globs(parameters)
    globs = _remove_excluded_patterns(globs, exclude_globs)
    if globs:
        value = ";".join(globs)
        context.log(f"Extension include override: {value}")
        args.extend(["--mask-globs", value])
    else:
        context.log("Extension include override: not selected.")
    if exclude_globs:
        value = ";".join(exclude_globs)
        context.log(f"Extension exclude override: {value}")
        args.extend(["--exclude-globs", value])


def _append_operation_policy(args: list[str], parameters: dict[str, Any], command: str) -> None:
    policy = _text(parameters.get("operation_policy"))
    if not policy or command not in {"compare", "sync", "backup"}:
        return
    args.extend(["--operation-policy", policy])


def _append_anchor_flag(args: list[str], parameters: dict[str, Any], command: str) -> None:
    if command in {"compare", "sync", "backup", "sync2"} and _bool(parameters.get("anchor")):
        args.append("--anchor")


def _append_apply_guard_flags(args: list[str], parameters: dict[str, Any], command: str) -> None:
    if command not in {"sync", "backup"}:
        return
    if _bool(parameters.get("override_delete_ratio")) or _bool(parameters.get("yes_delete_ratio")):
        args.append("--yes-delete-ratio")
    if _bool(parameters.get("override_filtered_hard")) or _bool(parameters.get("yes_filtered_hard")):
        args.append("--yes-filtered-hard")
    confirmation = _text(parameters.get("preflight_confirmation"))
    if confirmation and not _bool(parameters.get("dry_run")):
        args.extend(["--expect-confirmation", confirmation])


def _cli_guard_payload(output_lines: list[str]) -> dict[str, Any] | None:
    try:
        payload = json.loads("\n".join(output_lines))
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    guard = payload.get("guard")
    if not isinstance(guard, dict):
        return None
    guard.setdefault("message", str(payload.get("message") or "Plan guard blocked the operation."))
    guard.setdefault("error", str(payload.get("error") or "PlanGuard"))
    return guard


def _run_cli(context: JobContext, args: list[str]) -> dict[str, Any]:
    command = prepare_gui_subprocess_command([str(_python_executable(context)), str(_main_script(context)), *args])
    pretty = " ".join(f'"{part}"' if " " in part else part for part in command)
    context.log(f"$ {pretty}")
    output_kwargs = gui_subprocess_output_kwargs(command)

    process = subprocess.Popen(
        command,
        cwd=str(context.paths.root),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=utf8_subprocess_env({"PYTHONPATH": str(context.paths.root)}),
        **output_kwargs,
        **hidden_subprocess_kwargs(),
    )

    assert process.stdout is not None
    output_lines: list[str] = []
    try:
        for line in iter_process_output_lines(process.stdout):
            output_lines.append(line)
            if context.cancelled():
                context.log("Cancellation requested. Stopping CLI process.")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                return {"returncode": 2, "cancelled": True}
            context.log(line)
    finally:
        process.stdout.close()

    returncode = process.wait()
    context.progress(1.0)
    context.log(f"CLI exit code: {returncode}")
    if returncode != 0:
        guard = _cli_guard_payload(output_lines)
        if guard is not None:
            raise CliPlanGuardError(str(guard.get("message") or "Plan guard blocked the operation."), guard)
        raise RuntimeError(f"CLI command failed with exit code {returncode}")
    return {"returncode": returncode, "args": args, "output_lines": output_lines}


def _parse_cli_json_result(result: dict[str, Any]) -> dict[str, Any]:
    output_lines = result.get("output_lines", [])
    text = "\n".join(str(line) for line in output_lines)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("CLI did not return a JSON payload.")
        payload = json.loads(text[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("CLI returned a non-object JSON payload.")
    return payload


def _append_include_path_list(args: list[str], parameters: dict[str, Any]) -> None:
    include_path_list = _text(parameters.get("include_path_list") or parameters.get("diff_file") or parameters.get("path_list_file"))
    if include_path_list:
        args.extend(["--include-path-list", include_path_list])


def run_info(context: JobContext) -> dict[str, Any]:
    return _run_cli(context, ["info"])


def list_pairs(context: JobContext) -> dict[str, Any]:
    return _run_cli(context, ["pairs"])


def run_profile_command(context: JobContext) -> dict[str, Any]:
    parameters = context.operation.parameters
    command = _text(parameters.get("cli_command") or "compare")
    pair_name = _text(parameters.get("pair_name"))
    if not pair_name:
        raise ValueError("Profile/pair name is empty.")

    args = [command, "--pair", pair_name]
    pairs_config = _pairs_config_for_profile(context, pair_name)
    if pairs_config is not None:
        args.extend(["--pairs-config", str(pairs_config)])
    source = _text(parameters.get("source_dir") or parameters.get("source"))
    target = _text(parameters.get("target_dir") or parameters.get("target"))
    if source:
        args.extend(["--source", source])
    if target:
        args.extend(["--target", target])
    _append_extension_filter(args, parameters, context)
    _append_include_path_list(args, parameters)
    _append_operation_policy(args, parameters, command)
    _append_anchor_flag(args, parameters, command)
    if _bool(parameters.get("dry_run")):
        args.append("--dry-run")
    if command == "backup" and _bool(parameters.get("allow_hard_delete")):
        args.append("--allow-hard-delete")
    _append_apply_guard_flags(args, parameters, command)
    return _run_cli(context, args)


def run_manual_command(context: JobContext) -> dict[str, Any]:
    parameters = context.operation.parameters
    command = _text(parameters.get("cli_command") or "compare")
    mask_mode = _text(parameters.get("mask_operation_mode")).lower()
    if mask_mode:
        command = {
            "backup_mirror": "backup",
            "one_way": "sync",
            "two_way": "sync2",
        }.get(mask_mode, command)
        if mask_mode == "backup_mirror":
            parameters.setdefault("operation_policy", "mirror_safe")
    source = _text(parameters.get("source_dir"))
    target = _text(parameters.get("target_dir"))
    if not source or not target:
        raise ValueError("Manual command requires source_dir and target_dir.")

    args = [command, "--source", source, "--target", target]
    mode = _text(parameters.get("mode") or "safe")
    if command in {"compare", "sync", "backup", "sync2"}:
        args.extend(["--mode", mode])
    _append_extension_filter(args, parameters, context)
    _append_include_path_list(args, parameters)
    _append_operation_policy(args, parameters, command)
    _append_anchor_flag(args, parameters, command)
    if _bool(parameters.get("dry_run")):
        args.append("--dry-run")
    if command == "backup" and _bool(parameters.get("allow_hard_delete")):
        args.append("--allow-hard-delete")
    _append_apply_guard_flags(args, parameters, command)
    result = _run_cli(context, args)
    _record_path_history(context, "source", source)
    _record_path_history(context, "target", target)
    context.log("Updated source/target path history.")
    return result


def run_manifest_command(context: JobContext) -> dict[str, Any]:
    parameters = context.operation.parameters
    command = _text(parameters.get("cli_command") or "manifest")
    root_role = _text(parameters.get("root_role")).lower()
    if root_role in {"source", "src"}:
        root_value = _text(parameters.get("source_dir") or parameters.get("source"))
    elif root_role in {"target", "dst", "destination"}:
        root_value = _text(parameters.get("target_dir") or parameters.get("target"))
    else:
        root_value = _text(parameters.get("root_dir"))
    root = Path(root_value).expanduser() if root_value else context.paths.input
    args = [command, "--root", str(root)]

    manifest_file = _text(parameters.get("manifest_file"))
    if manifest_file:
        args.extend(["--manifest", manifest_file])
    if command == "manifest":
        args.extend(["--project-root", str(context.paths.root)])
        _append_extension_filter(args, parameters, context)
        if _bool(parameters.get("exclude_cloud_roots")):
            args.append("--exclude-cloud-roots")
    return _run_cli(context, args)


def _manifest_route(parameters: dict[str, Any], context: JobContext) -> tuple[str, str]:
    source = _text(parameters.get("source_dir") or parameters.get("source") or context.paths.input)
    target = _text(parameters.get("target_dir") or parameters.get("target") or context.paths.output)
    if not source or not target:
        raise ValueError("Manifest diff requires source and target paths.")
    return source, target


def _manifest_diff_latest_paths(context: JobContext) -> dict[str, Path]:
    return {
        "json": context.paths.report / "manifest_diff_latest.json",
        "tree": context.paths.report / "manifest_diff_latest_tree.txt",
        "one_way": context.paths.report / "manifest_diff_latest_one_way_paths.txt",
        "mirror": context.paths.report / "manifest_diff_latest_mirror_paths.txt",
    }


def _write_path_list(path: Path, title: str, paths: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"; {title}",
        "; UTF-8 relative paths. Empty/comment lines are ignored by --include-path-list.",
        "",
        *paths,
    ]
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _write_manifest_diff_tree(path: Path, payload: dict[str, Any], items: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    groups: dict[str, list[str]] = {}
    for item in items:
        action = _text(item.get("action") or "unknown")
        if action == "same":
            continue
        groups.setdefault(action, []).append(_text(item.get("rel_path")))
    lines = [
        "AUDION MANIFEST DIFF",
        f"Source: {payload.get('source_root', '')}",
        f"Target: {payload.get('target_root', '')}",
        f"Report: {payload.get('report', '')}",
        "",
    ]
    for action in sorted(groups):
        values = sorted(item for item in groups[action] if item)
        if not values:
            continue
        lines.append(f"[{action.upper()}] {len(values)}")
        lines.extend(f"  {item}" for item in values)
        lines.append("")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _copy_latest_artifact(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def run_manifest_diff_command(context: JobContext) -> dict[str, Any]:
    parameters = context.operation.parameters
    source, target = _manifest_route(parameters, context)
    mode = _text(parameters.get("mode") or "safe")
    args = ["compare", "--source", source, "--target", target, "--mode", mode]
    _append_extension_filter(args, parameters, context)
    result = _run_cli(context, args)
    payload = _parse_cli_json_result(result)
    items = [item for item in payload.get("items", []) if isinstance(item, dict)]

    one_way_paths = sorted(
        {
            _text(item.get("rel_path"))
            for item in items
            if item.get("action") in {"copy", "touch"} and _text(item.get("direction") or "source_to_target") == "source_to_target"
        }
    )
    mirror_paths = sorted(
        {
            _text(item.get("rel_path"))
            for item in items
            if item.get("action") in {"copy", "touch", "extra_target", "delete", "quarantine"}
        }
    )

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    diff_json = context.paths.report / f"manifest_diff_{stamp}.json"
    diff_tree = context.paths.report / f"manifest_diff_{stamp}_tree.txt"
    one_way_file = context.paths.report / f"manifest_diff_{stamp}_one_way_paths.txt"
    mirror_file = context.paths.report / f"manifest_diff_{stamp}_mirror_paths.txt"

    summary = {
        "source": source,
        "target": target,
        "mode": mode,
        "compare_report": payload.get("report"),
        "one_way_path_count": len([item for item in one_way_paths if item]),
        "mirror_path_count": len([item for item in mirror_paths if item]),
        "compare_summary": payload.get("summary", {}),
        "diff_tree": str(diff_tree),
        "one_way_path_list": str(one_way_file),
        "mirror_path_list": str(mirror_file),
    }
    diff_json.parent.mkdir(parents=True, exist_ok=True)
    diff_json.write_text(json.dumps({"summary": summary, "compare": payload}, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_manifest_diff_tree(diff_tree, payload, items)
    _write_path_list(one_way_file, "One-Way Source -> Target path list from manifest diff", [item for item in one_way_paths if item])
    _write_path_list(mirror_file, "BACKUP-MIRROR Source -> Target path list from manifest diff", [item for item in mirror_paths if item])

    latest = _manifest_diff_latest_paths(context)
    _copy_latest_artifact(diff_json, latest["json"])
    _copy_latest_artifact(diff_tree, latest["tree"])
    _copy_latest_artifact(one_way_file, latest["one_way"])
    _copy_latest_artifact(mirror_file, latest["mirror"])

    context.log(f"Manifest diff tree: {diff_tree}")
    context.log(f"One-Way path list: {one_way_file}")
    context.log(f"BACKUP-MIRROR path list: {mirror_file}")
    return {"summary": summary, "json": str(diff_json)}


def run_manifest_diff_apply_command(context: JobContext) -> dict[str, Any]:
    parameters = context.operation.parameters
    command = _text(parameters.get("cli_command") or "sync")
    if command not in {"sync", "backup"}:
        raise ValueError(f"Unsupported diff apply command: {command}")
    source, target = _manifest_route(parameters, context)
    mode = _text(parameters.get("mode") or "safe")
    latest = _manifest_diff_latest_paths(context)
    default_list = latest["mirror"] if command == "backup" else latest["one_way"]
    path_list = Path(_text(parameters.get("diff_file")) or str(default_list)).expanduser()
    if not path_list.exists():
        raise FileNotFoundError(f"Diff path list was not found: {path_list}. Run Diff source/target first.")
    args = [command, "--source", source, "--target", target, "--mode", mode, "--include-path-list", str(path_list)]
    if command == "backup":
        args.extend(["--operation-policy", "mirror_hard"])
    if _bool(parameters.get("dry_run")):
        args.append("--dry-run")
    _append_apply_guard_flags(args, parameters, command)
    result = _run_cli(context, args)
    _record_path_history(context, "source", source)
    _record_path_history(context, "target", target)
    context.log(f"Applied diff path list: {path_list}")
    return result


def run_manifest_diff_then_apply_command(context: JobContext) -> dict[str, Any]:
    parameters = dict(context.operation.parameters)
    apply_command = _text(parameters.get("cli_command") or "sync")
    if apply_command not in {"sync", "backup"}:
        raise ValueError(f"Unsupported manifest pipeline apply command: {apply_command}")

    context.log("Manifest pipeline: building fresh Source -> Target diff.")
    diff_parameters = dict(parameters)
    diff_parameters["diff_file"] = ""
    diff_context = replace(
        context,
        operation=replace(context.operation, parameters=diff_parameters),
    )
    diff_result = run_manifest_diff_command(diff_context)

    context.log("Manifest pipeline: applying the freshly generated diff path list.")
    apply_parameters = dict(parameters)
    apply_parameters["cli_command"] = apply_command
    apply_parameters["diff_file"] = ""
    apply_context = replace(
        context,
        operation=replace(context.operation, parameters=apply_parameters),
    )
    apply_result = run_manifest_diff_apply_command(apply_context)
    return {"diff": diff_result, "apply": apply_result}


def _is_inside(child: Path, parent: Path) -> bool:
    try:
        child_resolved = str(child.resolve())
        parent_resolved = str(parent.resolve())
        return os.path.commonpath([child_resolved, parent_resolved]) == parent_resolved
    except (OSError, ValueError):
        return False


def _clean_managed_folder(context: JobContext, folder: Path, label: str) -> dict[str, Any]:
    root = context.paths.root.resolve()
    if folder.is_symlink():
        raise RuntimeError(f"{label} is a symbolic link. Cleanup blocked.")

    folder.mkdir(parents=True, exist_ok=True)
    folder_resolved = folder.resolve()
    if not _is_inside(folder_resolved, root):
        raise RuntimeError(f"{label} path is outside project root. Cleanup blocked.")

    removed = 0
    skipped: list[str] = []
    for item in folder.iterdir():
        if item.name == ".gitkeep":
            continue
        try:
            if item.is_symlink() or item.is_file():
                item.unlink()
            elif item.is_dir():
                if not _is_inside(item, folder_resolved):
                    skipped.append(f"{item.name} (escapes {label})")
                    continue
                shutil.rmtree(item)
            removed += 1
            context.log(f"Removed from {label}: {item.name}")
        except OSError as exc:
            skipped.append(f"{item.name} ({exc})")

    return {"folder": label, "removed_items": removed, "skipped_items": skipped}


def cleanup_input_output(context: JobContext) -> dict[str, Any]:
    context.log("Cleaning managed input/output folders.")
    input_result = _clean_managed_folder(context, context.paths.input, "input")
    context.progress(0.5)
    if context.cancelled():
        return {"cancelled": True, "input": input_result}
    output_result = _clean_managed_folder(context, context.paths.output, "output")
    context.progress(1.0)
    return {"input": input_result, "output": output_result}


def cleanup_workspace(context: JobContext) -> dict[str, Any]:
    context.log("Cleaning managed workspace folder.")
    result = _clean_managed_folder(context, context.paths.workspace, "workspace")
    context.progress(1.0)
    return result


def clear_path_history(context: JobContext) -> dict[str, Any]:
    history_file = _path_history_file(context)
    if history_file.exists():
        history_file.unlink()
        context.log(f"Removed path history: {history_file}")
    else:
        context.log("Path history is already empty.")
    context.progress(1.0)
    return {"removed": str(history_file)}
