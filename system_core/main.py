from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import argparse
import json
import sys

THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

from auditor_core import (
    ANCHOR_FILE_NAME,
    DeleteRatioExceeded,
    FilteredHardMirrorBlocked,
    PreviewConfirmationMismatch,
    SourceUnreachable,
    apply_plan,
    build_filter_spec,
    build_filter_spec_from_pair,
    compare_dirs,
    compare_dirs_two_way,
    default_pair_config_path,
    default_preset_config_path,
    get_pair_by_name,
    pair_list_report,
    pair_runtime_settings,
    project_root_from_file,
    resolve_existing_dir,
    normalize_rel_text,
    normalize_operation_policy,
    verify_manifest,
    write_anchor,
    write_manifest,
)


def print_json(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def optional_csv_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--include-globs", action="append", help="Semicolon-separated include patterns")
    parser.add_argument("--mask-globs", action="append", help="Semicolon-separated file masks that override include patterns for the current run")
    parser.add_argument("--exclude-globs", action="append", help="Semicolon-separated exclude patterns")
    parser.add_argument("--include-dirs", action="append", help="Semicolon-separated relative include dirs")
    parser.add_argument("--exclude-dirs", action="append", help="Semicolon-separated relative exclude dirs")
    parser.add_argument("--include-path-list", help="UTF-8 file with relative paths to include")
    parser.add_argument("--include-presets", action="append", help="Semicolon-separated include preset names")
    parser.add_argument("--exclude-presets", action="append", help="Semicolon-separated exclude preset names")
    parser.add_argument("--exclude-if-size-gt", type=int, help="Exclude files larger than this size in bytes")
    parser.add_argument("--exclude-if-size-lt", type=int, help="Exclude files smaller than this size in bytes")
    parser.add_argument("--exclude-hidden", action="store_true", help="Exclude dot-prefixed hidden paths")
    parser.add_argument("--preset-config", help="Path to sync preset config JSON")


def add_compare_like_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--source", help="Source directory")
    parser.add_argument("--target", help="Target directory")
    parser.add_argument("--pair", help="Use a named pair from config")
    parser.add_argument("--pairs-config", help="Path to sync pairs config JSON")
    parser.add_argument("--mode", choices=("quick", "safe", "strict"), default="safe")
    parser.add_argument("--mirror", action="store_true", help="Mirror target-only files according to operation policy")
    parser.add_argument("--operation-policy", choices=("copy_update", "mirror_safe", "mirror_hard"), help="copy_update, mirror_safe, or mirror_hard")
    parser.add_argument("--anchor", action="store_true", help=f"Require {ANCHOR_FILE_NAME} at both roots before scanning")
    optional_csv_args(parser)


def add_confirmation_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--expect-confirmation", help="Confirmation token from the preview this apply belongs to")


def add_apply_guard_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--yes-delete-ratio", action="store_true", help="Confirm applying a plan that deletes a large share of target files")
    parser.add_argument("--yes-filtered-hard", action="store_true", help="Confirm mirror_hard with a filtered target scope")
    add_confirmation_arg(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="audion-disk-auditor",
        description="Audion Disk Auditor: manifest audit, verify, compare, one-way sync, backup mirror and two-way sync.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("info", help="Show project info")

    parser_pairs = subparsers.add_parser("pairs", help="List configured sync pairs")
    parser_pairs.add_argument("--pairs-config", help="Path to sync pairs config JSON")
    parser_pairs.add_argument("--preset-config", help="Path to sync preset config JSON")
    parser_pairs.add_argument("--names-only", action="store_true", help="Print only pair names")

    parser_anchor = subparsers.add_parser("anchor", help=f"Write {ANCHOR_FILE_NAME} into a directory that is really mounted")
    parser_anchor.add_argument("path", help="Directory that should carry the anchor")

    parser_manifest = subparsers.add_parser("manifest", help="Create __CHECKSUMS__.b3 for a directory")
    parser_manifest.add_argument("--root", required=True, help="Directory to scan")
    parser_manifest.add_argument("--manifest", help="Custom manifest path")
    parser_manifest.add_argument("--exclude-cloud-roots", action="store_true", help="Skip known cloud roots")
    parser_manifest.add_argument("--project-root", help="Directory to auto-exclude from manifest")
    optional_csv_args(parser_manifest)

    parser_verify = subparsers.add_parser("verify", help="Verify __CHECKSUMS__.b3 against files")
    parser_verify.add_argument("--root", required=True, help="Directory that owns the manifest")
    parser_verify.add_argument("--manifest", help="Custom manifest path")

    parser_compare = subparsers.add_parser("compare", help="Compare source and target directories")
    add_compare_like_args(parser_compare)

    parser_sync = subparsers.add_parser("sync", help="Sync source into target without deleting extras")
    add_compare_like_args(parser_sync)
    parser_sync.add_argument("--dry-run", action="store_true", help="Do not copy or delete anything")
    parser_sync.add_argument("--preview", action="store_true", help="Alias for --dry-run")
    add_apply_guard_args(parser_sync)

    parser_backup = subparsers.add_parser("backup", help="Apply source-to-target backup policy")
    add_compare_like_args(parser_backup)
    parser_backup.add_argument("--dry-run", action="store_true", help="Preview without writing, deleting, or quarantining")
    parser_backup.add_argument("--preview", action="store_true", help="Alias for --dry-run")
    parser_backup.add_argument("--allow-hard-delete", action="store_true", help="Compatibility no-op: backup hard mirror is explicit by command/policy")
    add_apply_guard_args(parser_backup)

    parser_sync2 = subparsers.add_parser("sync2", help="Two-way full sync without deletions")
    parser_sync2.add_argument("--source", help="First directory")
    parser_sync2.add_argument("--target", help="Second directory")
    parser_sync2.add_argument("--pair", help="Use a named pair from config")
    parser_sync2.add_argument("--pairs-config", help="Path to sync pairs config JSON")
    parser_sync2.add_argument("--mode", choices=("quick", "safe", "strict"), default="safe")
    parser_sync2.add_argument("--anchor", action="store_true", help=f"Require {ANCHOR_FILE_NAME} at both roots before scanning")
    parser_sync2.add_argument("--dry-run", action="store_true", help="Do not copy or touch anything")
    parser_sync2.add_argument("--preview", action="store_true", help="Alias for --dry-run")
    optional_csv_args(parser_sync2)
    add_confirmation_arg(parser_sync2)

    return parser


def cmd_info() -> int:
    root = project_root_from_file()
    payload = {
        "project": "Audion Disk Auditor",
        "project_root": str(root),
        "python_executable": sys.executable,
        "python_version": sys.version.split()[0],
        "default_preset_config": str(default_preset_config_path()),
        "default_pair_config": str(default_pair_config_path()),
        "message": "Use launcher_project.cmd for interactive flows or main.py subcommands for automation.",
    }
    print_json(payload)
    return 0


def _split_args(value: list[str] | None) -> list[str]:
    result: list[str] = []
    if not value:
        return result
    for raw in value:
        for item in str(raw).replace(",", ";").split(";"):
            cleaned = item.strip()
            if cleaned:
                result.append(cleaned)
    return result


def _load_include_path_list(path_value: str | None) -> list[str]:
    if not path_value:
        return []
    path = Path(path_value).expanduser()
    result: list[str] = []
    seen: set[str] = set()
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        text = raw_line.strip()
        if not text or text.startswith("#") or text.startswith(";"):
            continue
        rel_path = normalize_rel_text(text.split("\t", 1)[0])
        key = rel_path.lower()
        if rel_path and key not in seen:
            result.append(rel_path)
            seen.add(key)
    return result


def _runtime_filter_spec(args: argparse.Namespace):
    mask_globs = _split_args(getattr(args, "mask_globs", None))
    include_globs = _split_args(getattr(args, "include_globs", None))
    exclude_globs = _split_args(getattr(args, "exclude_globs", None))
    include_dirs = _split_args(getattr(args, "include_dirs", None))
    exclude_dirs = _split_args(getattr(args, "exclude_dirs", None))
    include_paths = _load_include_path_list(getattr(args, "include_path_list", None))
    include_presets = _split_args(getattr(args, "include_presets", None))
    exclude_presets = _split_args(getattr(args, "exclude_presets", None))
    has_filter = any(
        [
            mask_globs,
            include_globs,
            exclude_globs,
            include_dirs,
            exclude_dirs,
            include_paths,
            include_presets,
            exclude_presets,
            getattr(args, "exclude_if_size_gt", None) is not None,
            getattr(args, "exclude_if_size_lt", None) is not None,
            bool(getattr(args, "exclude_hidden", False)),
        ]
    )
    if not has_filter:
        return None
    preset_cfg = Path(args.preset_config).expanduser() if getattr(args, "preset_config", None) else default_preset_config_path()
    return build_filter_spec(
        include_globs=mask_globs or include_globs,
        exclude_globs=exclude_globs,
        include_dirs=include_dirs,
        exclude_dirs=exclude_dirs,
        include_paths=include_paths,
        include_presets=include_presets,
        exclude_presets=exclude_presets,
        exclude_if_size_gt=getattr(args, "exclude_if_size_gt", None),
        exclude_if_size_lt=getattr(args, "exclude_if_size_lt", None),
        exclude_hidden=bool(getattr(args, "exclude_hidden", False)),
        preset_config_path=preset_cfg,
    )


def _filter_has_selected_masks(filter_spec) -> bool:
    return bool(filter_spec and (filter_spec.include_globs or filter_spec.include_dirs or filter_spec.include_paths or filter_spec.include_preset_names))


def _pair_requires_masks(pair: dict) -> bool:
    name = str(pair.get("name", "")).strip().lower()
    return name == "copy_by_mask" or bool(pair.get("requires_masks", False))


def resolve_runtime(args: argparse.Namespace) -> tuple[Path, Path, dict]:
    pair_cfg = Path(args.pairs_config).expanduser() if getattr(args, "pairs_config", None) else default_pair_config_path()
    preset_cfg = Path(args.preset_config).expanduser() if getattr(args, "preset_config", None) else default_preset_config_path()
    mask_globs = _split_args(getattr(args, "mask_globs", None))
    exclude_globs = _split_args(getattr(args, "exclude_globs", None))

    if getattr(args, "pair", None):
        pair = get_pair_by_name(args.pair, config_path=pair_cfg)
        source_value = getattr(args, "source", None) or str(pair["source"])
        target_value = getattr(args, "target", None) or str(pair["target"])
        source = resolve_existing_dir(source_value)
        target_path = Path(target_value).expanduser()
        target = resolve_existing_dir(str(target_path)) if target_path.exists() else target_path.resolve()
        runtime = pair_runtime_settings(pair)
        filter_spec = build_filter_spec_from_pair(pair, preset_config_path=preset_cfg)
        if mask_globs:
            filter_spec = replace(filter_spec, include_globs=mask_globs)
        if exclude_globs:
            merged_exclude_globs = [*filter_spec.exclude_globs]
            seen_exclude_globs = {item.lower() for item in merged_exclude_globs}
            for pattern in exclude_globs:
                if pattern.lower() not in seen_exclude_globs:
                    merged_exclude_globs.append(pattern)
                    seen_exclude_globs.add(pattern.lower())
            filter_spec = replace(filter_spec, exclude_globs=merged_exclude_globs)
        if _pair_requires_masks(pair) and not _filter_has_selected_masks(filter_spec):
            raise ValueError("copy_by_mask requires at least one extension mask or extension group.")
        return source, target, {
            "pair": pair,
            "filter_spec": filter_spec,
            "mode": runtime["mode"],
            "mirror": runtime["mirror"],
            "operation_policy": runtime["operation_policy"],
            "sync_kind": runtime["sync_kind"],
            "anchor": runtime["anchor"] or bool(getattr(args, "anchor", False)),
            "note": runtime["note"],
            "warnings": runtime["warnings"],
            "pairs_config": str(pair_cfg),
            "preset_config": str(preset_cfg),
        }

    if not getattr(args, "source", None) or not getattr(args, "target", None):
        raise ValueError("Provide --source and --target, or use --pair.")

    source = resolve_existing_dir(args.source)
    target_raw = Path(args.target).expanduser()
    target = target_raw.resolve() if target_raw.exists() else target_raw.resolve()
    filter_spec = _runtime_filter_spec(args)
    return source, target, {
        "pair": None,
        "filter_spec": filter_spec,
        "mode": getattr(args, "mode", "safe"),
        "mirror": bool(getattr(args, "mirror", False)),
        "operation_policy": normalize_operation_policy(
            getattr(args, "operation_policy", None),
            command=getattr(args, "command", None),
            mirror=bool(getattr(args, "mirror", False)),
        ),
        "sync_kind": "sync",
        "anchor": bool(getattr(args, "anchor", False)),
        "note": "",
        "warnings": [],
        "pairs_config": str(pair_cfg),
        "preset_config": str(preset_cfg),
    }


def _confirm_guard(prompt: str) -> bool:
    if not sys.stdin.isatty():
        return False
    answer = input("Proceed? [y/N] ").strip().lower()
    return answer in {"y", "yes"}


def _apply_plan_with_guards(plan: dict, args: argparse.Namespace, *, dry_run: bool) -> dict:
    delete_ratio_confirmed = bool(getattr(args, "yes_delete_ratio", False))
    filtered_hard_confirmed = bool(getattr(args, "yes_filtered_hard", False))
    expect_confirmation = getattr(args, "expect_confirmation", None)
    while True:
        try:
            return apply_plan(
                plan,
                dry_run=dry_run,
                override_delete_ratio=delete_ratio_confirmed,
                override_filtered_hard=filtered_hard_confirmed,
                expect_confirmation=expect_confirmation,
            )
        except DeleteRatioExceeded as exc:
            if delete_ratio_confirmed:
                raise
            prompt = (
                f"Large deletion detected: {exc.files_to_delete} of {exc.target_files} "
                f"target files ({exc.ratio:.0%}) will be permanently deleted. Continue?"
            )
            if not sys.stdin.isatty():
                raise
            print(prompt, file=sys.stderr)
            if not _confirm_guard(prompt):
                raise
            delete_ratio_confirmed = True
        except FilteredHardMirrorBlocked as exc:
            if filtered_hard_confirmed:
                raise
            prompt = (
                "Filtered hard mirror: only files matching the filter will be deleted "
                "from the target. Continue?"
            )
            if not sys.stdin.isatty():
                raise
            print(str(exc), file=sys.stderr)
            if not _confirm_guard(prompt):
                raise
            filtered_hard_confirmed = True


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "info":
            return cmd_info()

        if args.command == "pairs":
            pair_cfg = Path(args.pairs_config).expanduser() if args.pairs_config else default_pair_config_path()
            preset_cfg = Path(args.preset_config).expanduser() if args.preset_config else default_preset_config_path()
            if args.names_only:
                for item in pair_list_report(config_path=pair_cfg, preset_config_path=preset_cfg)["pairs"]:
                    print(item["name"])
                return 0
            payload = pair_list_report(config_path=pair_cfg, preset_config_path=preset_cfg)
            print_json(payload)
            return 0

        if args.command == "anchor":
            print_json(write_anchor(Path(args.path).expanduser()))
            return 0

        if args.command == "manifest":
            root = resolve_existing_dir(args.root)
            manifest_path = Path(args.manifest).expanduser() if args.manifest else None
            auto_project_root = Path(args.project_root).expanduser() if args.project_root else project_root_from_file()
            payload = write_manifest(
                root,
                manifest_path=manifest_path,
                exclude_cloud_roots=args.exclude_cloud_roots,
                project_root=auto_project_root,
                filter_spec=_runtime_filter_spec(args),
            )
            print_json(payload)
            return 0 if not payload["hash_failures"] else 1

        if args.command == "verify":
            root = resolve_existing_dir(args.root)
            manifest_path = Path(args.manifest).expanduser() if args.manifest else None
            payload = verify_manifest(root, manifest_path=manifest_path)
            print_json(payload)
            return 0 if payload["ok"] else 1

        if args.command in {"compare", "sync", "backup", "sync2"}:
            source, target, runtime = resolve_runtime(args)
            mode = runtime["mode"] if getattr(args, "pair", None) else args.mode
            requested_sync_kind = runtime["sync_kind"] if getattr(args, "pair", None) else ("sync2" if args.command == "sync2" else "backup" if args.command == "backup" else "sync")
            operation_policy = runtime["operation_policy"] if getattr(args, "pair", None) else normalize_operation_policy(
                getattr(args, "operation_policy", None),
                command=args.command,
                mirror=bool(getattr(args, "mirror", False)),
            )
            mirror = runtime["mirror"] if getattr(args, "pair", None) else operation_policy in {"mirror_safe", "mirror_hard"}
            dry_run = False
            if args.command in {"sync", "backup", "sync2"}:
                dry_run = bool(args.dry_run or getattr(args, "preview", False))

            anchor_required = bool(runtime["anchor"])
            if requested_sync_kind == "sync2":
                plan = compare_dirs_two_way(
                    source,
                    target,
                    mode=mode,
                    filter_spec=runtime["filter_spec"],
                    warnings=runtime["warnings"],
                    anchor=anchor_required,
                )
            else:
                plan = compare_dirs(
                    source,
                    target,
                    mode=mode,
                    mirror=mirror,
                    operation_policy=operation_policy,
                    filter_spec=runtime["filter_spec"],
                    warnings=runtime["warnings"],
                    anchor=anchor_required,
                )

            if args.command == "compare":
                payload = {
                    "runtime": {
                        "mode": mode,
                        "mirror": mirror,
                        "operation_policy": operation_policy,
                        "sync_kind": requested_sync_kind,
                        "anchor": anchor_required,
                        "note": runtime["note"],
                        "source_root": str(source),
                        "target_root": str(target),
                        "pair": runtime["pair"].get("name") if runtime["pair"] else None,
                        "pairs_config": runtime["pairs_config"],
                        "preset_config": runtime["preset_config"],
                        "warnings": runtime["warnings"],
                    },
                    **plan,
                }
                print_json(payload)
                return 0

            result = _apply_plan_with_guards(plan, args, dry_run=dry_run)
            payload = {
                "runtime": {
                    "mode": mode,
                    "mirror": mirror,
                    "operation_policy": operation_policy,
                    "sync_kind": requested_sync_kind,
                    "dry_run": dry_run,
                    "anchor": anchor_required,
                    "note": runtime["note"],
                    "source_root": str(source),
                    "target_root": str(target),
                    "pair": runtime["pair"].get("name") if runtime["pair"] else None,
                    "pairs_config": runtime["pairs_config"],
                    "preset_config": runtime["preset_config"],
                    "warnings": runtime["warnings"],
                },
                "preflight": plan.get("preflight"),
                "plan_report": plan["report"],
                "apply_report": result["report"],
                "plan_summary": plan["summary"],
                "apply_summary": result["summary"],
                "plan_summary_reports": plan.get("summary_reports"),
                "apply_summary_reports": result.get("summary_reports"),
                "filter_spec": runtime["filter_spec"].to_json() if runtime["filter_spec"] else None,
            }
            print_json(payload)
            fatal_count = int(result["summary"].get("errors", 0)) + int(result["summary"].get("conflicts", 0))
            return 0 if fatal_count == 0 else 1

    except Exception as exc:
        payload = {
            "error": exc.__class__.__name__,
            "message": str(exc),
        }
        if isinstance(exc, DeleteRatioExceeded):
            payload["guard"] = {
                "kind": "delete_ratio",
                "files_to_delete": exc.files_to_delete,
                "target_files": exc.target_files,
                "ratio": exc.ratio,
            }
        elif isinstance(exc, FilteredHardMirrorBlocked):
            payload["guard"] = {"kind": "filtered_hard"}
        elif isinstance(exc, SourceUnreachable):
            payload["guard"] = {
                "kind": "source_unreachable",
                "role": exc.role,
                "root": str(exc.root),
                "anchor": str(exc.anchor),
            }
        elif isinstance(exc, PreviewConfirmationMismatch):
            payload["guard"] = {
                "kind": "preview_confirmation",
                "expected": exc.expected,
                "actual": exc.actual,
            }
        print_json(payload)
        return 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
