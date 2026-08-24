from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Iterable
import hashlib
import json
import os
import shutil
import time

try:
    from blake3 import blake3 as _blake3_factory
except Exception:
    _blake3_factory = None

DEFAULT_EXCLUDES = {
    "System Volume Information",
    "$RECYCLE.BIN",
    "Recycler",
    "Recycled",
}

ANCHOR_FILE_NAME = ".audion-anchor"

SERVICE_FILES = {
    "__CHECKSUMS__.b3",
    "__CHECKSUMS__.b3.bak",
    "__CHECKSUMS__.b3.tmp",
    "__CHECKSUMS__.err",
    "__CHECKSUMS__.verify.log",
    ANCHOR_FILE_NAME,
}

SERVICE_DIRS = {
    "_audion_quarantine",
}

SERVICE_FILE_GLOBS = (
    "__CHECKSUMS__*.tmp",
    "*.audion_tmp_*",
)

VALID_COMPARE_MODES = {"quick", "safe", "strict"}
VALID_OPERATION_POLICIES = {"copy_update", "mirror_safe", "mirror_hard"}
DEPRECATED_DRY_RUN_WARNING = "Deprecated config key ignored: dry_run_default. Use operation_policy instead."
QUARANTINE_DIR_NAME = "_audion_quarantine"
DELETE_RATIO_LIMIT = 0.50
DELETE_COUNT_FLOOR = 50
FREE_SPACE_HEADROOM = 1.10


class DeleteRatioExceeded(RuntimeError):
    """Raised when a plan would delete a suspiciously large share of the target."""

    def __init__(self, files_to_delete: int, target_files: int, ratio: float):
        self.files_to_delete = files_to_delete
        self.target_files = target_files
        self.ratio = ratio
        super().__init__(
            f"Refusing to apply: plan would delete {files_to_delete} of {target_files} "
            f"target files ({ratio:.0%}). Re-run with override_delete_ratio=True to proceed."
        )


class FilteredHardMirrorBlocked(RuntimeError):
    """Raised when hard mirror is combined with a filtered target scope."""


class SourceUnreachable(RuntimeError):
    """Raised when an anchored root exists but carries no anchor file.

    This is deliberately not a FileNotFoundError: the root itself resolved. A
    mounted remote root whose peer is asleep or disconnected presents as an
    existing but empty directory, and an empty scan of such a root reads as
    "delete everything in target".
    """

    def __init__(self, role: str, root: Path):
        self.role = role
        self.root = root
        self.anchor = anchor_path(root)
        super().__init__(
            f"The {role} root exists but its anchor file is missing: {self.anchor}. "
            f"This usually means a disconnected or asleep mount rather than an empty folder. "
            f"Run 'main.py anchor \"{root}\"' once the root is really mounted, or drop "
            f"\"anchor\": true from the pair."
        )


class PreviewConfirmationMismatch(RuntimeError):
    """Raised when an apply is bound to a confirmation token from another plan."""

    def __init__(self, expected: str, actual: str):
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"Refusing to apply: the plan does not match the confirmed preview. "
            f"Preview token was {expected!r}, this plan is {actual!r}. "
            f"Rebuild the preview and confirm it again."
        )


DEFAULT_CLOUD_ROOTS = (
    "Dropbox",
    os.path.join("CLOUDS", "Dropbox"),
    "Yandex.Disk",
    os.path.join("CLOUDS", "Yandex.Disk"),
    os.path.join("CLOUDS", "pCloud"),
    os.path.join("CLOUDS", "MEGA"),
)

PRESET_FILE_NAME = "sync_presets.json"
PAIRS_FILE_NAME = "sync_pairs.json"
PAIR_EXAMPLE_FILE_NAME = "sync_pairs.example.json"


@dataclass
class FileRecord:
    rel_path: str
    abs_path: str
    size: int
    mtime_ns: int
    hash_hex: str | None = None

    def to_json(self) -> dict:
        return asdict(self)


@dataclass
class ScanStats:
    total_files: int = 0
    total_dirs: int = 0
    total_bytes: int = 0
    considered_files: int = 0
    considered_dirs: int = 0
    considered_bytes: int = 0
    matched_by_include: int = 0
    skipped_by_include: int = 0
    skipped_by_exclude: int = 0

    def to_json(self) -> dict:
        return asdict(self)


@dataclass
class FilterSpec:
    include_globs: list[str]
    exclude_globs: list[str]
    include_dirs: list[str]
    exclude_dirs: list[str]
    include_paths: list[str] | None = None
    exclude_if_size_gt: int | None = None
    exclude_if_size_lt: int | None = None
    exclude_hidden: bool = False
    include_mode: str = "include_then_exclude"
    include_preset_names: list[str] | None = None
    exclude_preset_names: list[str] | None = None

    def to_json(self) -> dict:
        return asdict(self)


@dataclass
class ScanBundle:
    files: dict[str, FileRecord]
    dirs: set[str]
    stats: ScanStats


def timestamp_slug() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    counter = 1
    while True:
        candidate = parent / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def project_root_from_file() -> Path:
    return Path(__file__).resolve().parents[1]


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def log_path(kind: str, ext: str = "json") -> Path:
    root = project_root_from_file()
    ensure_dir(root / "logs")
    return unique_path(root / "logs" / f"{timestamp_slug()}_{kind}.{ext}")


def output_path(kind: str, ext: str = "json") -> Path:
    root = project_root_from_file()
    ensure_dir(root / "output")
    return unique_path(root / "output" / f"{timestamp_slug()}_{kind}.{ext}")


def save_json(path: Path, payload: dict) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def save_text(path: Path, text: str) -> None:
    ensure_dir(path.parent)
    path.write_text(text, encoding="utf-8", newline="\n")


def normalize_rel_path(path: Path) -> str:
    return path.as_posix()


def normalize_rel_text(value: str) -> str:
    return value.replace("\\", "/").strip("/")


def resolve_existing_dir(raw_path: str) -> Path:
    path = Path(raw_path).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"Path was not found: {path}")
    if not path.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {path}")
    return path.resolve()


def is_relative_to(path: Path, other: Path) -> bool:
    try:
        path.relative_to(other)
        return True
    except ValueError:
        return False


def ensure_non_overlapping_dirs(source: Path, target: Path) -> None:
    if source == target:
        raise ValueError("Source and target must be different directories.")
    if is_relative_to(source, target):
        raise ValueError("Source directory is inside target. Refusing overlapping sync.")
    if is_relative_to(target, source):
        raise ValueError("Target directory is inside source. Refusing overlapping sync.")


def anchor_path(root: Path) -> Path:
    return Path(root) / ANCHOR_FILE_NAME


def anchor_exists(root: Path) -> bool:
    try:
        return anchor_path(root).is_file()
    except OSError:
        return False


def write_anchor(root: Path) -> dict:
    """Create the anchor file that marks a root as really mounted."""
    root = resolve_existing_dir(str(root))
    target = anchor_path(root)
    existed = target.is_file()
    if not existed:
        target.write_text(
            "Audion Disk Tools mount anchor.\n"
            "Its presence proves this root is really mounted, not an empty stand-in for a\n"
            "disconnected peer. Pairs with \"anchor\": true refuse to build a plan without it.\n"
            f"created {time.strftime('%Y-%m-%d %H:%M:%S')}\n",
            encoding="utf-8",
            newline="\n",
        )
    return {
        "action": "anchor",
        "root": str(root),
        "anchor": str(target),
        "created": not existed,
    }


def ensure_anchored_root(root: Path, role: str) -> None:
    if not anchor_exists(root):
        raise SourceUnreachable(role, Path(root))


def ensure_anchored_roots(source: Path, target: Path) -> None:
    """Verify both roots before scanning, so unreachable never reads as empty."""
    ensure_anchored_root(source, "source")
    ensure_anchored_root(target, "target")


def _project_config_dir() -> Path:
    root = project_root_from_file()
    ensure_dir(root / "config")
    return root / "config"


def default_preset_config_path() -> Path:
    return _project_config_dir() / PRESET_FILE_NAME


def default_pair_config_path() -> Path:
    return _project_config_dir() / PAIRS_FILE_NAME


def default_pair_example_path() -> Path:
    return _project_config_dir() / PAIR_EXAMPLE_FILE_NAME


def split_patterns(raw_values: Iterable[str] | None) -> list[str]:
    result: list[str] = []
    if not raw_values:
        return result
    for raw in raw_values:
        if raw is None:
            continue
        for piece in str(raw).replace("\n", ";").replace(",", ";").split(";"):
            item = piece.strip()
            if item:
                result.append(item)
    return result


def load_json_file(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Config file was not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_presets(config_path: Path | None = None) -> dict:
    path = config_path or default_preset_config_path()
    payload = load_json_file(path)
    presets = payload.get("presets")
    if not isinstance(presets, dict):
        raise ValueError(f"Preset file has invalid format: {path}")
    return presets


def load_pairs(config_path: Path | None = None) -> list[dict]:
    path = config_path or default_pair_config_path()
    payload = load_json_file(path)
    pairs = payload.get("pairs")
    if not isinstance(pairs, list):
        raise ValueError(f"Pair file has invalid format: {path}")
    return pairs


def get_pair_by_name(name: str, config_path: Path | None = None) -> dict:
    for pair in load_pairs(config_path=config_path):
        if str(pair.get("name", "")).strip().lower() == name.strip().lower():
            return pair
    raise KeyError(f"Pair was not found: {name}")


def _normalize_dir_rules(items: Iterable[str]) -> list[str]:
    rules: list[str] = []
    seen: set[str] = set()
    for item in items:
        rule = normalize_rel_text(str(item))
        if not rule:
            continue
        rule = rule.lower()
        if rule not in seen:
            seen.add(rule)
            rules.append(rule)
    return rules


def build_filter_spec(
    *,
    include_globs: Iterable[str] | None = None,
    exclude_globs: Iterable[str] | None = None,
    include_dirs: Iterable[str] | None = None,
    exclude_dirs: Iterable[str] | None = None,
    include_paths: Iterable[str] | None = None,
    include_presets: Iterable[str] | None = None,
    exclude_presets: Iterable[str] | None = None,
    exclude_if_size_gt: int | None = None,
    exclude_if_size_lt: int | None = None,
    exclude_hidden: bool = False,
    include_mode: str = "include_then_exclude",
    preset_config_path: Path | None = None,
) -> FilterSpec:
    preset_map: dict = {}
    include_preset_names = [str(item).strip() for item in (include_presets or []) if str(item).strip()]
    exclude_preset_names = [str(item).strip() for item in (exclude_presets or []) if str(item).strip()]

    if include_preset_names or exclude_preset_names:
        preset_map = load_presets(preset_config_path)

    merged_include_globs = split_patterns(include_globs)
    merged_exclude_globs = split_patterns(exclude_globs)
    merged_include_dirs = split_patterns(include_dirs)
    merged_exclude_dirs = split_patterns(exclude_dirs)

    for name in include_preset_names:
        preset = preset_map.get(name)
        if not isinstance(preset, dict):
            raise KeyError(f"Include preset was not found: {name}")
        merged_include_globs.extend(split_patterns(preset.get("include_globs", [])))
        merged_exclude_globs.extend(split_patterns(preset.get("exclude_globs", [])))
        merged_include_dirs.extend(split_patterns(preset.get("include_dirs", [])))
        merged_exclude_dirs.extend(split_patterns(preset.get("exclude_dirs", [])))

    for name in exclude_preset_names:
        preset = preset_map.get(name)
        if not isinstance(preset, dict):
            raise KeyError(f"Exclude preset was not found: {name}")
        merged_exclude_globs.extend(split_patterns(preset.get("exclude_globs", [])))
        merged_exclude_dirs.extend(split_patterns(preset.get("exclude_dirs", [])))

    def _dedupe(items: Iterable[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for item in items:
            norm = item.strip()
            if not norm:
                continue
            key = norm.lower()
            if key in seen:
                continue
            seen.add(key)
            result.append(norm)
        return result

    return FilterSpec(
        include_globs=_dedupe(merged_include_globs),
        exclude_globs=_dedupe(merged_exclude_globs),
        include_dirs=_normalize_dir_rules(merged_include_dirs),
        exclude_dirs=_normalize_dir_rules(merged_exclude_dirs),
        include_paths=[normalize_rel_text(item).lower() for item in _dedupe(include_paths or [])],
        exclude_if_size_gt=exclude_if_size_gt,
        exclude_if_size_lt=exclude_if_size_lt,
        exclude_hidden=exclude_hidden,
        include_mode=include_mode,
        include_preset_names=include_preset_names,
        exclude_preset_names=exclude_preset_names,
    )


def build_filter_spec_from_pair(pair: dict, preset_config_path: Path | None = None) -> FilterSpec:
    return build_filter_spec(
        include_globs=pair.get("include_globs"),
        exclude_globs=pair.get("exclude_globs"),
        include_dirs=pair.get("include_dirs"),
        exclude_dirs=pair.get("exclude_dirs"),
        include_presets=pair.get("include_presets"),
        exclude_presets=pair.get("exclude_presets"),
        exclude_if_size_gt=pair.get("exclude_if_size_gt"),
        exclude_if_size_lt=pair.get("exclude_if_size_lt"),
        exclude_hidden=bool(pair.get("exclude_hidden", False)),
        include_mode=str(pair.get("include_mode", "include_then_exclude")),
        preset_config_path=preset_config_path,
    )


def normalize_operation_policy(value: object | None, *, command: str | None = None, mirror: bool = False) -> str:
    raw = str(value or "").strip().lower().replace("-", "_")
    aliases = {
        "": "",
        "copy": "copy_update",
        "copy_update": "copy_update",
        "copy/update": "copy_update",
        "sync": "copy_update",
        "one_way": "copy_update",
        "oneway": "copy_update",
        "backup": "mirror_safe",
        "mirror": "mirror_safe",
        "mirror_safe": "mirror_safe",
        "safe_mirror": "mirror_safe",
        "mirror_hard": "mirror_hard",
        "hard_mirror": "mirror_hard",
        "delete_mirror": "mirror_hard",
    }
    if raw:
        policy = aliases.get(raw)
        if policy not in VALID_OPERATION_POLICIES:
            raise ValueError(f"Unsupported operation_policy: {value}")
        return policy

    command_key = str(command or "").strip().lower()
    if command_key == "backup" or mirror:
        return "mirror_hard"
    return "copy_update"


def operation_policy_is_mirror(policy: str) -> bool:
    return policy in {"mirror_safe", "mirror_hard"}


def filter_has_include_scope(filter_spec: FilterSpec | None) -> bool:
    if filter_spec is None:
        return False
    return bool(filter_spec.include_globs or filter_spec.include_dirs or filter_spec.include_paths or filter_spec.include_preset_names)


def pair_runtime_settings(pair: dict) -> dict:
    sync_kind = str(pair.get("sync_kind", "")).strip().lower()
    if not sync_kind:
        sync_kind = "backup" if bool(pair.get("mirror", False)) else "sync"
    if sync_kind not in {"sync", "backup", "sync2"}:
        raise ValueError(f"Unsupported sync_kind in pair: {sync_kind}")
    warnings: list[str] = []
    if "dry_run_default" in pair:
        warnings.append(DEPRECATED_DRY_RUN_WARNING)
    operation_policy = normalize_operation_policy(
        pair.get("operation_policy"),
        command="backup" if sync_kind == "backup" else sync_kind,
        mirror=bool(pair.get("mirror", False)),
    )
    return {
        "mode": str(pair.get("mode", "safe")),
        "mirror": operation_policy_is_mirror(operation_policy),
        "operation_policy": operation_policy,
        "sync_kind": sync_kind,
        "anchor": bool(pair.get("anchor", False)),
        "note": str(pair.get("note", "") or ""),
        "warnings": warnings,
    }


def pair_list_report(config_path: Path | None = None, preset_config_path: Path | None = None) -> dict:
    path = config_path or default_pair_config_path()
    pairs = load_pairs(path)
    items: list[dict] = []
    for pair in pairs:
        filter_spec = build_filter_spec_from_pair(pair, preset_config_path=preset_config_path)
        runtime = pair_runtime_settings(pair)
        items.append(
            {
                "name": pair.get("name"),
                "source": pair.get("source"),
                "target": pair.get("target"),
                "mode": runtime["mode"],
                "mirror": runtime["mirror"],
                "operation_policy": runtime["operation_policy"],
                "sync_kind": runtime["sync_kind"],
                "anchor": runtime["anchor"],
                "note": runtime["note"],
                "warnings": runtime["warnings"],
                "include_presets": filter_spec.include_preset_names,
                "exclude_presets": filter_spec.exclude_preset_names,
                "include_globs": filter_spec.include_globs,
                "exclude_globs": filter_spec.exclude_globs,
            }
        )
    payload = {
        "action": "pairs",
        "config": str(path),
        "count": len(items),
        "pairs": items,
    }
    report = output_path("pairs")
    save_json(report, payload)
    payload["report"] = str(report)
    return payload


def should_skip_path(
    abs_path: Path,
    root: Path,
    *,
    project_root: Path | None = None,
    exclude_cloud_roots: bool = False,
    extra_skip_paths: Iterable[Path] | None = None,
) -> bool:
    rel = abs_path.relative_to(root)
    parts_lower = {part.lower() for part in rel.parts}

    for name in DEFAULT_EXCLUDES:
        if name.lower() in parts_lower:
            return True

    for dirname in SERVICE_DIRS:
        if dirname.lower() in parts_lower:
            return True

    name_lower = abs_path.name.lower()
    if name_lower in {name.lower() for name in SERVICE_FILES}:
        return True

    for pattern in SERVICE_FILE_GLOBS:
        if fnmatchcase(name_lower, pattern.lower()):
            return True

    if extra_skip_paths:
        try:
            abs_resolved = abs_path.resolve()
        except OSError:
            abs_resolved = abs_path
        abs_key = os.path.normcase(str(abs_resolved))
        for skip_path in extra_skip_paths:
            try:
                skip_resolved = skip_path.resolve()
            except OSError:
                skip_resolved = skip_path
            if abs_key == os.path.normcase(str(skip_resolved)):
                return True

    if project_root is not None:
        try:
            project_root = project_root.resolve()
        except Exception:
            project_root = project_root
        if is_relative_to(project_root, root) and is_relative_to(abs_path, project_root):
            return True

    if exclude_cloud_roots:
        rel_norm = str(rel).replace("/", os.sep).replace("\\", os.sep).lower()
        for cloud_root in DEFAULT_CLOUD_ROOTS:
            if rel_norm == cloud_root.lower():
                return True
            prefix = cloud_root.lower() + os.sep
            if rel_norm.startswith(prefix):
                return True

    return False


def _lower_path_parts(rel_path: str) -> list[str]:
    return [part.lower() for part in normalize_rel_text(rel_path).split("/") if part]


def _matches_any_glob(path_value: str, patterns: Iterable[str], file_name: str | None = None) -> bool:
    value_lower = normalize_rel_text(path_value).lower()
    name_lower = file_name.lower() if file_name else ""
    for pattern in patterns:
        p = pattern.lower()
        if fnmatchcase(value_lower, p):
            return True
        if name_lower and fnmatchcase(name_lower, p):
            return True
    return False


def _match_dir_rule(rel_path: str, rules: Iterable[str]) -> bool:
    rel_lower = normalize_rel_text(rel_path).lower()
    parts = [part for part in rel_lower.split("/") if part]
    for rule in rules:
        if not rule:
            continue
        if "/" in rule:
            if rel_lower == rule or rel_lower.startswith(rule + "/"):
                return True
        else:
            if rule in parts:
                return True
    return False


def should_include_file(rel_path: str, size: int, filter_spec: FilterSpec | None) -> tuple[bool, str | None]:
    if filter_spec is None:
        return True, None

    rel_norm = normalize_rel_text(rel_path)
    name = Path(rel_norm).name
    parent = normalize_rel_text(str(Path(rel_norm).parent)) if Path(rel_norm).parent != Path(".") else ""
    parent_key = parent.lower()

    if filter_spec.exclude_hidden:
        for part in [item for item in rel_norm.split("/") if item]:
            if part.startswith("."):
                return False, "hidden"

    if filter_spec.include_dirs:
        if not parent:
            return False, "outside_include_dirs"
        include_dir_hit = False
        for rule in filter_spec.include_dirs:
            if parent_key == rule or parent_key.startswith(rule + "/"):
                include_dir_hit = True
                break
        if not include_dir_hit:
            return False, "outside_include_dirs"

    if filter_spec.include_paths:
        include_path_set = getattr(filter_spec, "_include_path_set", None)
        if include_path_set is None:
            include_path_set = set(filter_spec.include_paths)
            setattr(filter_spec, "_include_path_set", include_path_set)
        if rel_norm.lower() not in include_path_set:
            return False, "outside_include_paths"

    include_patterns = filter_spec.include_globs
    if include_patterns:
        if not _matches_any_glob(rel_norm, include_patterns, file_name=name):
            return False, "include_glob_miss"

    if filter_spec.exclude_dirs and (parent and _match_dir_rule(parent, filter_spec.exclude_dirs)):
        return False, "exclude_dir"

    if filter_spec.exclude_globs and _matches_any_glob(rel_norm, filter_spec.exclude_globs, file_name=name):
        return False, "exclude_glob"

    if filter_spec.exclude_if_size_gt is not None and size > int(filter_spec.exclude_if_size_gt):
        return False, "size_gt"

    if filter_spec.exclude_if_size_lt is not None and size < int(filter_spec.exclude_if_size_lt):
        return False, "size_lt"

    return True, None


def _external_b3sum_path() -> str | None:
    root = project_root_from_file()
    candidates = [
        root / "b3sum.exe",
        root / "system_core" / "b3sum.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return shutil.which("b3sum.exe") or shutil.which("b3sum")


def hash_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    if _blake3_factory is not None:
        hasher = _blake3_factory()
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(chunk_size)
                if not chunk:
                    break
                hasher.update(chunk)
        return hasher.hexdigest()

    external = _external_b3sum_path()
    if external:
        import subprocess

        completed = subprocess.run(
            [external, str(path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode == 0:
            line = completed.stdout.strip().splitlines()[0].strip()
            return line.split(" ", 1)[0]

    raise RuntimeError("BLAKE3 hashing is unavailable. Install Python package 'blake3' or ship b3sum.exe.")


def scan_dir(
    root: Path,
    *,
    project_root: Path | None = None,
    exclude_cloud_roots: bool = False,
    filter_spec: FilterSpec | None = None,
    extra_skip_paths: Iterable[Path] | None = None,
) -> ScanBundle:
    root = root.resolve()
    result: dict[str, FileRecord] = {}
    kept_dirs: set[str] = set()
    stats = ScanStats()

    for dirpath, dirnames, filenames in os.walk(root):
        dir_path = Path(dirpath)
        rel_dir = normalize_rel_path(dir_path.relative_to(root)) if dir_path != root else ""
        if rel_dir:
            stats.total_dirs += 1
            if not filter_has_include_scope(filter_spec):
                if not (filter_spec and filter_spec.exclude_dirs and _match_dir_rule(rel_dir, filter_spec.exclude_dirs)):
                    kept_dirs.add(rel_dir)

        next_dirs: list[str] = []
        for dirname in dirnames:
            full = dir_path / dirname
            if should_skip_path(
                full,
                root,
                project_root=project_root,
                exclude_cloud_roots=exclude_cloud_roots,
                extra_skip_paths=extra_skip_paths,
            ):
                continue
            next_dirs.append(dirname)
        dirnames[:] = next_dirs

        kept_file_here = False
        for filename in filenames:
            full = dir_path / filename
            if should_skip_path(
                full,
                root,
                project_root=project_root,
                exclude_cloud_roots=exclude_cloud_roots,
                extra_skip_paths=extra_skip_paths,
            ):
                continue
            try:
                stat_info = full.stat()
            except OSError:
                continue
            stats.total_files += 1
            stats.total_bytes += stat_info.st_size
            rel_path = normalize_rel_path(full.relative_to(root))
            include_ok, reason = should_include_file(rel_path, stat_info.st_size, filter_spec)
            if not include_ok:
                if reason in {"include_glob_miss", "outside_include_dirs", "outside_include_paths"}:
                    stats.skipped_by_include += 1
                else:
                    stats.skipped_by_exclude += 1
                continue
            stats.matched_by_include += 1
            stats.considered_files += 1
            stats.considered_bytes += stat_info.st_size
            kept_file_here = True
            result[rel_path] = FileRecord(
                rel_path=rel_path,
                abs_path=str(full),
                size=stat_info.st_size,
                mtime_ns=stat_info.st_mtime_ns,
            )

        if kept_file_here:
            current = Path(rel_dir)
            while str(current) not in ("", "."):
                kept_dirs.add(normalize_rel_path(current))
                current = current.parent

    stats.considered_dirs = len(kept_dirs)
    return ScanBundle(files=result, dirs=kept_dirs, stats=stats)


def write_manifest(
    root: Path,
    *,
    manifest_path: Path | None = None,
    exclude_cloud_roots: bool = False,
    project_root: Path | None = None,
    filter_spec: FilterSpec | None = None,
) -> dict:
    root = root.resolve()
    project_root = project_root.resolve() if project_root else None

    if manifest_path is None:
        manifest_path = root / "__CHECKSUMS__.b3"
    manifest_path = manifest_path.expanduser().resolve()

    error_path = root / "__CHECKSUMS__.err"
    if manifest_path == (root / "__CHECKSUMS__.b3").resolve():
        backup_path = root / "__CHECKSUMS__.b3.bak"
    else:
        backup_path = manifest_path.with_name(f"{manifest_path.name}.bak")
    temp_path = manifest_path.with_name(f"{manifest_path.name}.tmp")

    scan_excludes = []
    for candidate in (manifest_path, backup_path, temp_path, error_path, root / "__CHECKSUMS__.verify.log"):
        try:
            resolved = candidate.resolve()
        except OSError:
            resolved = candidate
        if is_relative_to(resolved, root):
            scan_excludes.append(resolved)

    if manifest_path.exists():
        try:
            shutil.copy2(manifest_path, backup_path)
        except OSError:
            pass

    if error_path.exists():
        try:
            error_path.unlink()
        except OSError:
            pass

    bundle = scan_dir(
        root,
        project_root=project_root,
        exclude_cloud_roots=exclude_cloud_roots,
        filter_spec=filter_spec,
        extra_skip_paths=scan_excludes,
    )
    records = bundle.files

    failed: list[dict] = []
    total = 0

    with manifest_path.open("w", encoding="utf-8", newline="\n") as handle:
        mode_note = " (cloud roots excluded)" if exclude_cloud_roots else ""
        handle.write(f"; BLAKE3 checksums generated {time.strftime('%Y-%m-%d %H:%M:%S')} in {root}{mode_note}\n")
        for rel_path in sorted(records):
            record = records[rel_path]
            total += 1
            try:
                record.hash_hex = hash_file(Path(record.abs_path))
                handle.write(f"{record.hash_hex}  {record.rel_path}\n")
            except Exception as exc:
                failed.append({"path": record.rel_path, "error": f"{exc.__class__.__name__}: {exc}"})

    if failed:
        error_path.write_text(
            "\n".join(f"{item['path']} :: {item['error']}" for item in failed) + "\n",
            encoding="utf-8",
        )

    payload = {
        "action": "manifest",
        "root": str(root),
        "manifest": str(manifest_path),
        "errors_file": str(error_path),
        "files_written": total - len(failed),
        "hash_failures": failed,
        "exclude_cloud_roots": exclude_cloud_roots,
        "filter_spec": filter_spec.to_json() if filter_spec else None,
        "scan": bundle.stats.to_json(),
    }
    report = output_path("manifest_report")
    save_json(report, payload)
    payload["report"] = str(report)
    return payload


def parse_manifest(manifest_path: Path) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for raw_line in manifest_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip("\r\n")
        if not line or line.startswith(";"):
            continue
        parts = line.split("  ", 1)
        if len(parts) != 2:
            continue
        hash_hex, rel_path = parts[0].strip(), parts[1].strip()
        if hash_hex and rel_path:
            entries.append((hash_hex, rel_path))
    return entries


def verify_manifest(root: Path, manifest_path: Path | None = None) -> dict:
    root = root.resolve()
    if manifest_path is None:
        manifest_path = root / "__CHECKSUMS__.b3"

    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest was not found: {manifest_path}")

    mismatched: list[str] = []
    missing: list[str] = []
    os_errors: list[dict] = []
    checked = 0

    for expected_hash, rel_path in parse_manifest(manifest_path):
        checked += 1
        file_path = Path(rel_path)
        if not file_path.is_absolute():
            file_path = root / rel_path
        try:
            if not file_path.exists():
                missing.append(rel_path)
                continue
            actual_hash = hash_file(file_path)
            if actual_hash.lower() != expected_hash.lower():
                mismatched.append(rel_path)
        except OSError as exc:
            os_errors.append({"path": rel_path, "error": f"{exc.__class__.__name__}: {exc}"})

    verify_log = root / "__CHECKSUMS__.verify.log"
    lines: list[str] = []
    lines.append(f"; Verify run: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"; Root: {root}")
    lines.append(f"; Manifest: {manifest_path}")
    lines.append(f"; Checked: {checked}")
    lines.append(f"; Mismatched: {len(mismatched)}")
    lines.append(f"; Missing: {len(missing)}")
    lines.append(f"; OS errors: {len(os_errors)}")
    lines.append("")

    if mismatched:
        lines.append("[MISMATCHED FILES]")
        lines.extend(mismatched)
        lines.append("")

    if missing:
        lines.append("[MISSING FILES]")
        lines.extend(missing)
        lines.append("")

    if os_errors:
        lines.append("[OS ERRORS]")
        lines.extend(f"{item['path']} :: {item['error']}" for item in os_errors)
        lines.append("")

    verify_log.write_text("\n".join(lines) + "\n", encoding="utf-8")

    ok = not mismatched and not missing and not os_errors
    payload = {
        "action": "verify",
        "root": str(root),
        "manifest": str(manifest_path),
        "checked": checked,
        "mismatched": mismatched,
        "missing": missing,
        "os_errors": os_errors,
        "verify_log": str(verify_log),
        "ok": ok,
    }
    report = output_path("verify_report")
    save_json(report, payload)
    payload["report"] = str(report)
    return payload


def _safe_copy2(src: Path, dst: Path) -> None:
    ensure_dir(dst.parent)
    temp_name = f".{dst.name}.audion_tmp_{timestamp_slug()}"
    temp_path = unique_path(dst.with_name(temp_name))
    shutil.copy2(src, temp_path)
    os.replace(temp_path, dst)


def _format_bytes(size: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    value = float(size)
    unit_index = 0
    while value >= 1024 and unit_index < len(units) - 1:
        value /= 1024
        unit_index += 1
    if unit_index == 0:
        return f"{int(value)} {units[unit_index]}"
    return f"{value:.2f} {units[unit_index]}"


def _paths_for_copy_dirs(items: list[dict]) -> set[str]:
    dirs: set[str] = set()
    for item in items:
        if item["action"] != "copy":
            continue
        parent = Path(item["rel_path"]).parent
        while str(parent) not in ("", "."):
            dirs.add(normalize_rel_path(parent))
            parent = parent.parent
    return dirs


def _build_plan_summary(
    source_bundle: ScanBundle,
    target_bundle: ScanBundle,
    items: list[dict],
    counts: dict[str, int],
    *,
    operation_policy: str,
    mirror_scope: str,
) -> dict:
    bytes_to_copy = 0
    bytes_to_delete = 0
    bytes_to_quarantine = 0
    new_files_to_copy = 0
    changed_files_to_copy = 0
    for item in items:
        if item["action"] == "copy" and item.get("source"):
            bytes_to_copy += int(item["source"]["size"])
            if item.get("reason") == "missing_in_target":
                new_files_to_copy += 1
            else:
                changed_files_to_copy += 1
        if item["action"] == "delete" and item.get("target"):
            bytes_to_delete += int(item["target"]["size"])
        if item["action"] == "quarantine" and item.get("target"):
            bytes_to_quarantine += int(item["target"]["size"])

    dirs_to_create = sorted(_paths_for_copy_dirs(items) - target_bundle.dirs)
    target_only_dirs = sorted(target_bundle.dirs - source_bundle.dirs)
    dirs_to_delete = target_only_dirs if operation_policy == "mirror_hard" else []
    dirs_to_quarantine = target_only_dirs if operation_policy == "mirror_safe" else []

    return {
        "operation_policy": operation_policy,
        "mirror_scope": mirror_scope,
        "source_total_files": source_bundle.stats.total_files,
        "source_total_dirs": source_bundle.stats.total_dirs,
        "source_total_bytes": source_bundle.stats.total_bytes,
        "source_considered_files": source_bundle.stats.considered_files,
        "source_considered_dirs": source_bundle.stats.considered_dirs,
        "source_considered_bytes": source_bundle.stats.considered_bytes,
        "target_total_files": target_bundle.stats.total_files,
        "target_total_dirs": target_bundle.stats.total_dirs,
        "target_total_bytes": target_bundle.stats.total_bytes,
        "target_considered_files": target_bundle.stats.considered_files,
        "target_considered_dirs": target_bundle.stats.considered_dirs,
        "target_considered_bytes": target_bundle.stats.considered_bytes,
        "matched_by_include": source_bundle.stats.matched_by_include,
        "skipped_by_include": source_bundle.stats.skipped_by_include,
        "skipped_by_exclude": source_bundle.stats.skipped_by_exclude,
        "files_to_copy": counts["copy"],
        "new_files_to_copy": new_files_to_copy,
        "changed_files_to_copy": changed_files_to_copy,
        "files_to_update": changed_files_to_copy,
        "files_to_touch": counts["touch"],
        "files_to_delete": counts["delete"],
        "files_to_quarantine": counts["quarantine"],
        "extra_target_files": counts["extra_target"],
        "same_files": counts["same"],
        "plan_errors": counts["errors"],
        "dirs_to_create": len(dirs_to_create),
        "dirs_to_delete": len(dirs_to_delete),
        "dirs_to_quarantine": len(dirs_to_quarantine),
        "bytes_to_copy": bytes_to_copy,
        "bytes_to_delete": bytes_to_delete,
        "bytes_to_quarantine": bytes_to_quarantine,
        "planned_create_dirs": dirs_to_create,
        "planned_delete_dirs": dirs_to_delete,
        "planned_quarantine_dirs": dirs_to_quarantine,
    }


def _paths_for_copy_dirs_by_direction(items: list[dict]) -> tuple[set[str], set[str]]:
    to_target: set[str] = set()
    to_source: set[str] = set()
    for item in items:
        if item["action"] != "copy":
            continue
        parent = Path(item["rel_path"]).parent
        direction = str(item.get("direction", "source_to_target"))
        while str(parent) not in ("", "."):
            norm = normalize_rel_path(parent)
            if direction == "target_to_source":
                to_source.add(norm)
            else:
                to_target.add(norm)
            parent = parent.parent
    return to_target, to_source


def _build_two_way_plan_summary(
    source_bundle: ScanBundle,
    target_bundle: ScanBundle,
    items: list[dict],
    counts: dict[str, int],
) -> dict:
    bytes_s2t = 0
    bytes_t2s = 0
    for item in items:
        if item["action"] != "copy":
            continue
        direction = str(item.get("direction", "source_to_target"))
        if direction == "target_to_source" and item.get("target"):
            bytes_t2s += int(item["target"]["size"])
        elif item.get("source"):
            bytes_s2t += int(item["source"]["size"])

    dirs_to_create_in_target, dirs_to_create_in_source = _paths_for_copy_dirs_by_direction(items)
    dirs_to_create_in_target = sorted(dirs_to_create_in_target - target_bundle.dirs)
    dirs_to_create_in_source = sorted(dirs_to_create_in_source - source_bundle.dirs)

    return {
        "operation_policy": "sync2",
        "mirror_scope": "none",
        "source_total_files": source_bundle.stats.total_files,
        "source_total_dirs": source_bundle.stats.total_dirs,
        "source_total_bytes": source_bundle.stats.total_bytes,
        "source_considered_files": source_bundle.stats.considered_files,
        "source_considered_dirs": source_bundle.stats.considered_dirs,
        "source_considered_bytes": source_bundle.stats.considered_bytes,
        "target_total_files": target_bundle.stats.total_files,
        "target_total_dirs": target_bundle.stats.total_dirs,
        "target_total_bytes": target_bundle.stats.total_bytes,
        "target_considered_files": target_bundle.stats.considered_files,
        "target_considered_dirs": target_bundle.stats.considered_dirs,
        "target_considered_bytes": target_bundle.stats.considered_bytes,
        "matched_by_include": source_bundle.stats.matched_by_include,
        "skipped_by_include": source_bundle.stats.skipped_by_include,
        "skipped_by_exclude": source_bundle.stats.skipped_by_exclude,
        "files_to_copy": counts["copy_source_to_target"] + counts["copy_target_to_source"],
        "files_to_copy_source_to_target": counts["copy_source_to_target"],
        "files_to_copy_target_to_source": counts["copy_target_to_source"],
        "files_to_touch": counts["touch_source_to_target"] + counts["touch_target_to_source"],
        "files_to_touch_source_to_target": counts["touch_source_to_target"],
        "files_to_touch_target_to_source": counts["touch_target_to_source"],
        "same_files": counts["same"],
        "conflict_files": counts["conflict"],
        "plan_errors": counts["errors"],
        "dirs_to_create": len(dirs_to_create_in_target) + len(dirs_to_create_in_source),
        "dirs_to_create_in_target": len(dirs_to_create_in_target),
        "dirs_to_create_in_source": len(dirs_to_create_in_source),
        "bytes_to_copy": bytes_s2t + bytes_t2s,
        "bytes_to_copy_source_to_target": bytes_s2t,
        "bytes_to_copy_target_to_source": bytes_t2s,
        "planned_create_dirs": dirs_to_create_in_target,
        "planned_create_dirs_in_target": dirs_to_create_in_target,
        "planned_create_dirs_in_source": dirs_to_create_in_source,
        "planned_delete_dirs": [],
    }


def _summary_to_text(title: str, summary: dict) -> str:
    lines = [title, "=" * len(title), ""]
    key_order = [
        "operation_policy",
        "mirror_scope",
        "source_total_files",
        "source_total_dirs",
        "source_total_bytes",
        "source_considered_files",
        "source_considered_dirs",
        "source_considered_bytes",
        "target_total_files",
        "target_total_dirs",
        "target_total_bytes",
        "target_considered_files",
        "target_considered_dirs",
        "target_considered_bytes",
        "matched_by_include",
        "skipped_by_include",
        "skipped_by_exclude",
        "files_to_copy",
        "new_files_to_copy",
        "changed_files_to_copy",
        "files_to_update",
        "files_to_copy_source_to_target",
        "files_to_copy_target_to_source",
        "files_to_touch",
        "files_to_touch_source_to_target",
        "files_to_touch_target_to_source",
        "files_to_delete",
        "files_to_quarantine",
        "extra_target_files",
        "same_files",
        "conflict_files",
        "plan_errors",
        "dirs_to_create",
        "dirs_to_create_in_target",
        "dirs_to_create_in_source",
        "dirs_to_delete",
        "dirs_to_quarantine",
        "bytes_to_copy",
        "bytes_to_copy_source_to_target",
        "bytes_to_copy_target_to_source",
        "bytes_to_delete",
        "bytes_to_quarantine",
        "would_copy",
        "would_copy_bytes",
        "would_copy_source_to_target",
        "would_copy_target_to_source",
        "would_copy_bytes_source_to_target",
        "would_copy_bytes_target_to_source",
        "would_touch",
        "would_touch_source_to_target",
        "would_touch_target_to_source",
        "would_delete",
        "would_delete_bytes",
        "would_delete_dirs",
        "would_quarantine",
        "would_quarantine_bytes",
        "would_quarantine_dirs",
        "would_create_dirs",
        "would_create_dirs_in_target",
        "would_create_dirs_in_source",
        "copied",
        "copied_bytes",
        "copied_source_to_target",
        "copied_target_to_source",
        "copied_bytes_source_to_target",
        "copied_bytes_target_to_source",
        "touched",
        "touched_source_to_target",
        "touched_target_to_source",
        "deleted",
        "deleted_bytes",
        "deleted_dirs",
        "quarantined",
        "quarantined_bytes",
        "quarantined_dirs",
        "verified",
        "created_dirs",
        "created_dirs_in_target",
        "created_dirs_in_source",
        "conflicts",
        "skipped",
        "errors",
        "elapsed_seconds",
    ]
    if summary.get("mirror_scope") == "filtered" and str(summary.get("operation_policy", "")).startswith("mirror_"):
        lines.append("Filtered mirror: only files matching selected filters are considered. Out-of-scope target files are ignored.")
        lines.append("")
    for key in key_order:
        if key not in summary:
            continue
        value = summary[key]
        if key.endswith("_bytes"):
            lines.append(f"{key}: {value} ({_format_bytes(int(value))})")
        else:
            lines.append(f"{key}: {value}")
    if "planned_create_dirs" in summary:
        lines.append("")
        lines.append("planned_create_dirs:")
        for item in summary["planned_create_dirs"][:100]:
            lines.append(f"  - {item}")
    if "planned_create_dirs_in_target" in summary:
        lines.append("")
        lines.append("planned_create_dirs_in_target:")
        for item in summary["planned_create_dirs_in_target"][:100]:
            lines.append(f"  - {item}")
    if "planned_create_dirs_in_source" in summary:
        lines.append("")
        lines.append("planned_create_dirs_in_source:")
        for item in summary["planned_create_dirs_in_source"][:100]:
            lines.append(f"  - {item}")
    if "planned_delete_dirs" in summary:
        lines.append("")
        lines.append("planned_delete_dirs:")
        for item in summary["planned_delete_dirs"][:100]:
            lines.append(f"  - {item}")
    if "planned_quarantine_dirs" in summary:
        lines.append("")
        lines.append("planned_quarantine_dirs:")
        for item in summary["planned_quarantine_dirs"][:100]:
            lines.append(f"  - {item}")
    if summary.get("phase_skip_reason"):
        lines.append("")
        lines.append(str(summary["phase_skip_reason"]))
    return "\n".join(lines) + "\n"


def write_summary_bundle(kind: str, payload: dict, summary: dict, prefix: str) -> dict:
    json_path = output_path(f"{prefix}_{kind}_summary")
    txt_path = output_path(f"{prefix}_{kind}_summary", ext="txt")
    save_json(json_path, {"kind": kind, "summary": summary, "payload": payload})
    save_text(txt_path, _summary_to_text(f"{prefix.upper()} {kind.upper()} SUMMARY", summary))
    return {"json": str(json_path), "txt": str(txt_path)}


def _existing_ancestor(path: Path) -> Path | None:
    candidate = Path(path)
    while True:
        if candidate.exists():
            return candidate
        parent = candidate.parent
        if parent == candidate:
            return None
        candidate = parent


def free_space_bytes(path: Path) -> int | None:
    anchor = _existing_ancestor(path)
    if anchor is None:
        return None
    try:
        return int(shutil.disk_usage(anchor).free)
    except OSError:
        return None


def plan_confirmation_hash(plan: dict) -> str:
    """Fingerprint the route and the numbers a preview showed to the operator."""
    summary = plan.get("summary", {}) or {}
    payload = {
        "source_root": str(plan.get("source_root") or ""),
        "target_root": str(plan.get("target_root") or ""),
        "operation_policy": str(plan.get("operation_policy") or summary.get("operation_policy") or ""),
        "mode": str(plan.get("mode") or ""),
        "mirror_scope": str(summary.get("mirror_scope") or ""),
        "files_to_copy": int(summary.get("files_to_copy", 0) or 0),
        "files_to_delete": int(summary.get("files_to_delete", 0) or 0),
        "files_to_quarantine": int(summary.get("files_to_quarantine", 0) or 0),
        "bytes_to_copy": int(summary.get("bytes_to_copy", 0) or 0),
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:12].upper()


def plan_confirmation_token(plan: dict) -> str:
    summary = plan.get("summary", {}) or {}
    policy = str(plan.get("operation_policy") or summary.get("operation_policy") or "copy_update")
    base = {
        "mirror_hard": "DELETE",
        "mirror_safe": "MIRROR",
        "copy_update": "COPY",
        "sync2": "SYNC2",
    }.get(policy, "APPLY")
    return f"{base} {plan_confirmation_hash(plan)}"


def build_preflight_card(plan: dict) -> dict:
    """Three checks an operator should see before Apply, plus the preview binding.

    This is the small replacement for the deleted live-diagnostics screen: it runs
    over an already-built plan instead of probing the network on its own.
    """
    summary = plan.get("summary", {}) or {}
    policy = str(plan.get("operation_policy") or summary.get("operation_policy") or "copy_update")
    source_root = Path(str(plan.get("source_root") or ""))
    target_root = Path(str(plan.get("target_root") or ""))

    anchor_required = bool(plan.get("anchor", False))
    source_anchor = anchor_exists(source_root)
    target_anchor = anchor_exists(target_root)
    anchor_ok = (source_anchor and target_anchor) if anchor_required else True

    bytes_to_write = int(summary.get("bytes_to_copy_source_to_target", summary.get("bytes_to_copy", 0)) or 0)
    target_free = free_space_bytes(target_root)
    if target_free is None:
        space_status = "unknown"
    elif target_free < bytes_to_write:
        space_status = "insufficient"
    elif target_free < bytes_to_write * FREE_SPACE_HEADROOM:
        space_status = "low"
    else:
        space_status = "ok"

    files_to_delete = int(summary.get("files_to_delete", 0) or 0)
    files_to_quarantine = int(summary.get("files_to_quarantine", 0) or 0)
    removals = files_to_delete + files_to_quarantine
    target_files = int(summary.get("target_considered_files", summary.get("target_total_files", 0)) or 0)
    share = (removals / target_files) if target_files > 0 else 0.0
    would_block = (
        policy == "mirror_hard"
        and files_to_delete >= DELETE_COUNT_FLOOR
        and target_files > 0
        and (files_to_delete / target_files) > DELETE_RATIO_LIMIT
    )
    if would_block:
        removal_status = "blocked"
    elif removals == 0:
        removal_status = "none"
    elif share > DELETE_RATIO_LIMIT:
        removal_status = "high"
    else:
        removal_status = "ok"

    return {
        "operation_policy": policy,
        "anchor": {
            "required": anchor_required,
            "source_present": source_anchor,
            "target_present": target_anchor,
            "anchor_file": ANCHOR_FILE_NAME,
            "status": "disabled" if not anchor_required else ("ok" if anchor_ok else "missing"),
            "ok": anchor_ok,
        },
        "free_space": {
            "bytes_to_write": bytes_to_write,
            "bytes_to_write_text": _format_bytes(bytes_to_write),
            "target_free_bytes": target_free,
            "target_free_text": _format_bytes(target_free) if target_free is not None else "unknown",
            "status": space_status,
            "ok": space_status in {"ok", "low", "unknown"},
        },
        "removals": {
            "files_to_delete": files_to_delete,
            "files_to_quarantine": files_to_quarantine,
            "files_total": removals,
            "target_files": target_files,
            "share": round(share, 4),
            "share_text": f"{share:.0%}" if target_files > 0 else "n/a",
            "ratio_limit": DELETE_RATIO_LIMIT,
            "count_floor": DELETE_COUNT_FLOOR,
            "guard_would_block": would_block,
            "status": removal_status,
            "ok": not would_block,
        },
        "confirmation": {
            "hash": plan_confirmation_hash(plan),
            "token": plan_confirmation_token(plan),
        },
    }


def compare_dirs(
    source: Path,
    target: Path,
    *,
    mode: str = "quick",
    mirror: bool = False,
    operation_policy: str | None = None,
    filter_spec: FilterSpec | None = None,
    warnings: list[str] | None = None,
    anchor: bool = False,
) -> dict:
    source = source.resolve()
    target = target.resolve()
    mode = mode.lower()
    if mode not in VALID_COMPARE_MODES:
        raise ValueError(f"Unsupported compare mode: {mode}")
    policy = normalize_operation_policy(operation_policy, mirror=mirror)
    mirror = operation_policy_is_mirror(policy)
    mirror_scope = "filtered" if mirror and filter_has_include_scope(filter_spec) else "full" if mirror else "none"

    ensure_non_overlapping_dirs(source, target)
    if anchor:
        ensure_anchored_roots(source, target)

    auto_project_root = project_root_from_file()
    source_bundle = scan_dir(source, project_root=auto_project_root, filter_spec=filter_spec)
    target_bundle = scan_dir(target, project_root=auto_project_root, filter_spec=filter_spec)
    source_map = source_bundle.files
    target_map = target_bundle.files

    items: list[dict] = []
    counts = {
        "copy": 0,
        "touch": 0,
        "delete": 0,
        "quarantine": 0,
        "same": 0,
        "extra_target": 0,
        "errors": 0,
    }

    for rel_path in sorted(set(source_map) | set(target_map)):
        src = source_map.get(rel_path)
        dst = target_map.get(rel_path)

        if src and not dst:
            items.append(
                {
                    "action": "copy",
                    "direction": "source_to_target",
                    "reason": "missing_in_target",
                    "rel_path": rel_path,
                    "source": src.to_json(),
                    "target": None,
                }
            )
            counts["copy"] += 1
            continue

        if dst and not src:
            if policy == "mirror_hard":
                action = "delete"
            elif policy == "mirror_safe":
                action = "quarantine"
            else:
                action = "extra_target"
            items.append(
                {
                    "action": action,
                    "direction": "target_only",
                    "reason": "missing_in_source",
                    "rel_path": rel_path,
                    "source": None,
                    "target": dst.to_json(),
                }
            )
            counts[action] += 1
            continue

        assert src is not None and dst is not None

        if mode == "strict" and src.size == dst.size:
            try:
                if src.hash_hex is None:
                    src.hash_hex = hash_file(Path(src.abs_path))
                if dst.hash_hex is None:
                    dst.hash_hex = hash_file(Path(dst.abs_path))
                if src.hash_hex == dst.hash_hex:
                    action = "same" if src.mtime_ns == dst.mtime_ns else "touch"
                    items.append(
                        {
                            "action": action,
                            "direction": "both" if action == "same" else "source_to_target",
                            "reason": "strict_hash_match" if action == "same" else "same_hash_different_mtime",
                            "rel_path": rel_path,
                            "source": src.to_json(),
                            "target": dst.to_json(),
                        }
                    )
                    counts[action] += 1
                    continue
                items.append(
                    {
                        "action": "copy",
                        "direction": "source_to_target",
                        "reason": "strict_hash_diff",
                        "rel_path": rel_path,
                        "source": src.to_json(),
                        "target": dst.to_json(),
                    }
                )
                counts["copy"] += 1
                continue
            except Exception as exc:
                items.append(
                    {
                        "action": "error",
                        "direction": "both",
                        "reason": f"hash_failed: {exc.__class__.__name__}: {exc}",
                        "rel_path": rel_path,
                        "source": src.to_json(),
                        "target": dst.to_json(),
                    }
                )
                counts["errors"] += 1
                continue

        if src.size == dst.size and src.mtime_ns == dst.mtime_ns:
            items.append(
                {
                    "action": "same",
                    "direction": "both",
                    "reason": "size_and_mtime_match",
                    "rel_path": rel_path,
                    "source": src.to_json(),
                    "target": dst.to_json(),
                }
            )
            counts["same"] += 1
            continue

        if mode == "safe" and src.size == dst.size:
            try:
                if src.hash_hex is None:
                    src.hash_hex = hash_file(Path(src.abs_path))
                if dst.hash_hex is None:
                    dst.hash_hex = hash_file(Path(dst.abs_path))
                if src.hash_hex == dst.hash_hex:
                    items.append(
                        {
                            "action": "touch",
                            "direction": "source_to_target",
                            "reason": "same_hash_different_mtime",
                            "rel_path": rel_path,
                            "source": src.to_json(),
                            "target": dst.to_json(),
                        }
                    )
                    counts["touch"] += 1
                    continue
            except Exception as exc:
                items.append(
                    {
                        "action": "error",
                        "direction": "both",
                        "reason": f"hash_failed: {exc.__class__.__name__}: {exc}",
                        "rel_path": rel_path,
                        "source": src.to_json(),
                        "target": dst.to_json(),
                    }
                )
                counts["errors"] += 1
                continue

        items.append(
            {
                "action": "copy",
                "direction": "source_to_target",
                "reason": "metadata_or_content_diff",
                "rel_path": rel_path,
                "source": src.to_json(),
                "target": dst.to_json(),
            }
        )
        counts["copy"] += 1

    summary = _build_plan_summary(
        source_bundle,
        target_bundle,
        items,
        counts,
        operation_policy=policy,
        mirror_scope=mirror_scope,
    )
    payload = {
        "action": "compare",
        "mode": mode,
        "mirror": mirror,
        "operation_policy": policy,
        "mirror_scope": mirror_scope,
        "anchor": bool(anchor),
        "source_root": str(source),
        "target_root": str(target),
        "filter_spec": filter_spec.to_json() if filter_spec else None,
        "source_scan": source_bundle.stats.to_json(),
        "target_scan": target_bundle.stats.to_json(),
        "summary": summary,
        "items": items,
        "warnings": warnings or [],
    }
    payload["preflight"] = build_preflight_card(payload)
    report = output_path(f"compare_{mode}")
    save_json(report, payload)
    payload["report"] = str(report)
    payload["summary_reports"] = write_summary_bundle("plan", payload, summary, prefix="compare")
    return payload


def compare_dirs_two_way(
    source: Path,
    target: Path,
    *,
    mode: str = "safe",
    filter_spec: FilterSpec | None = None,
    warnings: list[str] | None = None,
    anchor: bool = False,
) -> dict:
    source = source.resolve()
    target = target.resolve()
    mode = mode.lower()
    if mode not in VALID_COMPARE_MODES:
        raise ValueError(f"Unsupported compare mode: {mode}")

    ensure_non_overlapping_dirs(source, target)
    if anchor:
        ensure_anchored_roots(source, target)

    auto_project_root = project_root_from_file()
    source_bundle = scan_dir(source, project_root=auto_project_root, filter_spec=filter_spec)
    target_bundle = scan_dir(target, project_root=auto_project_root, filter_spec=filter_spec)
    source_map = source_bundle.files
    target_map = target_bundle.files

    items: list[dict] = []
    counts = {
        "copy_source_to_target": 0,
        "copy_target_to_source": 0,
        "touch_source_to_target": 0,
        "touch_target_to_source": 0,
        "same": 0,
        "conflict": 0,
        "errors": 0,
    }

    for rel_path in sorted(set(source_map) | set(target_map)):
        src = source_map.get(rel_path)
        dst = target_map.get(rel_path)

        if src and not dst:
            items.append(
                {
                    "action": "copy",
                    "direction": "source_to_target",
                    "reason": "missing_in_target",
                    "rel_path": rel_path,
                    "source": src.to_json(),
                    "target": None,
                }
            )
            counts["copy_source_to_target"] += 1
            continue

        if dst and not src:
            items.append(
                {
                    "action": "copy",
                    "direction": "target_to_source",
                    "reason": "missing_in_source",
                    "rel_path": rel_path,
                    "source": None,
                    "target": dst.to_json(),
                }
            )
            counts["copy_target_to_source"] += 1
            continue

        assert src is not None and dst is not None

        if mode == "strict" and src.size == dst.size:
            try:
                if src.hash_hex is None:
                    src.hash_hex = hash_file(Path(src.abs_path))
                if dst.hash_hex is None:
                    dst.hash_hex = hash_file(Path(dst.abs_path))
                if src.hash_hex == dst.hash_hex:
                    if src.mtime_ns == dst.mtime_ns:
                        items.append(
                            {
                                "action": "same",
                                "direction": "both",
                                "reason": "strict_hash_match",
                                "rel_path": rel_path,
                                "source": src.to_json(),
                                "target": dst.to_json(),
                            }
                        )
                        counts["same"] += 1
                    elif src.mtime_ns >= dst.mtime_ns:
                        items.append(
                            {
                                "action": "touch",
                                "direction": "source_to_target",
                                "reason": "same_hash_sync_mtime",
                                "rel_path": rel_path,
                                "source": src.to_json(),
                                "target": dst.to_json(),
                            }
                        )
                        counts["touch_source_to_target"] += 1
                    else:
                        items.append(
                            {
                                "action": "touch",
                                "direction": "target_to_source",
                                "reason": "same_hash_sync_mtime",
                                "rel_path": rel_path,
                                "source": src.to_json(),
                                "target": dst.to_json(),
                            }
                        )
                        counts["touch_target_to_source"] += 1
                    continue
                if src.mtime_ns == dst.mtime_ns:
                    items.append(
                        {
                            "action": "conflict",
                            "direction": "both",
                            "reason": "strict_same_mtime_different_content",
                            "rel_path": rel_path,
                            "source": src.to_json(),
                            "target": dst.to_json(),
                        }
                    )
                    counts["conflict"] += 1
                    continue
            except Exception as exc:
                items.append(
                    {
                        "action": "error",
                        "direction": "both",
                        "reason": f"hash_failed: {exc.__class__.__name__}: {exc}",
                        "rel_path": rel_path,
                        "source": src.to_json(),
                        "target": dst.to_json(),
                    }
                )
                counts["errors"] += 1
                continue

        if src.size == dst.size and src.mtime_ns == dst.mtime_ns:
            items.append(
                {
                    "action": "same",
                    "direction": "both",
                    "reason": "size_and_mtime_match",
                    "rel_path": rel_path,
                    "source": src.to_json(),
                    "target": dst.to_json(),
                }
            )
            counts["same"] += 1
            continue

        if mode == "safe" and src.size == dst.size:
            try:
                if src.hash_hex is None:
                    src.hash_hex = hash_file(Path(src.abs_path))
                if dst.hash_hex is None:
                    dst.hash_hex = hash_file(Path(dst.abs_path))
                if src.hash_hex == dst.hash_hex:
                    if src.mtime_ns >= dst.mtime_ns:
                        items.append(
                            {
                                "action": "touch",
                                "direction": "source_to_target",
                                "reason": "same_hash_sync_mtime",
                                "rel_path": rel_path,
                                "source": src.to_json(),
                                "target": dst.to_json(),
                            }
                        )
                        counts["touch_source_to_target"] += 1
                    else:
                        items.append(
                            {
                                "action": "touch",
                                "direction": "target_to_source",
                                "reason": "same_hash_sync_mtime",
                                "rel_path": rel_path,
                                "source": src.to_json(),
                                "target": dst.to_json(),
                            }
                        )
                        counts["touch_target_to_source"] += 1
                    continue
            except Exception as exc:
                items.append(
                    {
                        "action": "error",
                        "direction": "both",
                        "reason": f"hash_failed: {exc.__class__.__name__}: {exc}",
                        "rel_path": rel_path,
                        "source": src.to_json(),
                        "target": dst.to_json(),
                    }
                )
                counts["errors"] += 1
                continue

        if src.mtime_ns > dst.mtime_ns:
            items.append(
                {
                    "action": "copy",
                    "direction": "source_to_target",
                    "reason": "source_is_newer",
                    "rel_path": rel_path,
                    "source": src.to_json(),
                    "target": dst.to_json(),
                }
            )
            counts["copy_source_to_target"] += 1
            continue

        if dst.mtime_ns > src.mtime_ns:
            items.append(
                {
                    "action": "copy",
                    "direction": "target_to_source",
                    "reason": "target_is_newer",
                    "rel_path": rel_path,
                    "source": src.to_json(),
                    "target": dst.to_json(),
                }
            )
            counts["copy_target_to_source"] += 1
            continue

        items.append(
            {
                "action": "conflict",
                "direction": "both",
                "reason": "same_mtime_different_content_or_size",
                "rel_path": rel_path,
                "source": src.to_json(),
                "target": dst.to_json(),
            }
        )
        counts["conflict"] += 1

    summary = _build_two_way_plan_summary(source_bundle, target_bundle, items, counts)
    payload = {
        "action": "compare_two_way",
        "mode": mode,
        "mirror": False,
        "anchor": bool(anchor),
        "source_root": str(source),
        "target_root": str(target),
        "filter_spec": filter_spec.to_json() if filter_spec else None,
        "source_scan": source_bundle.stats.to_json(),
        "target_scan": target_bundle.stats.to_json(),
        "summary": summary,
        "items": items,
        "warnings": warnings or [],
    }
    payload["preflight"] = build_preflight_card(payload)
    report = output_path(f"compare_twoway_{mode}")
    save_json(report, payload)
    payload["report"] = str(report)
    payload["summary_reports"] = write_summary_bundle("plan", payload, summary, prefix="sync2")
    return payload


def _resolve_item_paths(source_root: Path, target_root: Path, rel_path: str, direction: str) -> tuple[Path, Path, Path]:
    if direction == "target_to_source":
        copy_from_root = target_root
        copy_to_root = source_root
    else:
        copy_from_root = source_root
        copy_to_root = target_root
    src_path = copy_from_root / rel_path
    dst_path = copy_to_root / rel_path
    return copy_to_root, src_path, dst_path


def _ensure_missing_dirs(dst_path: Path, target_root: Path, created_dirs: set[str], applied: dict) -> None:
    parent = dst_path.parent
    missing_dirs: list[Path] = []
    probe = parent
    while probe != target_root and not probe.exists():
        missing_dirs.append(probe)
        probe = probe.parent
    for created in reversed(missing_dirs):
        ensure_dir(created)
        created_rel = normalize_rel_path(created.relative_to(target_root))
        if created_rel not in created_dirs:
            created_dirs.add(created_rel)
            side = "source" if target_root == Path(applied["_source_root"]) else "target"
            applied["created_dirs"].append({"rel_path": created_rel, "side": side})


def _build_apply_summary(applied: dict, plan: dict, *, dry_run: bool) -> dict:
    copied_s2t = sum(1 for item in applied["copied"] if item.get("direction") == "source_to_target")
    copied_t2s = sum(1 for item in applied["copied"] if item.get("direction") == "target_to_source")
    copied_bytes_s2t = sum(int(item.get("size", 0)) for item in applied["copied"] if item.get("direction") == "source_to_target")
    copied_bytes_t2s = sum(int(item.get("size", 0)) for item in applied["copied"] if item.get("direction") == "target_to_source")
    touched_s2t = sum(1 for item in applied["touched"] if item.get("direction") == "source_to_target")
    touched_t2s = sum(1 for item in applied["touched"] if item.get("direction") == "target_to_source")
    created_in_target = sum(1 for item in applied["created_dirs"] if item.get("side") == "target")
    created_in_source = sum(1 for item in applied["created_dirs"] if item.get("side") == "source")
    deleted_bytes = sum(int(item.get("size", 0)) for item in applied["deleted"])
    quarantined_bytes = sum(int(item.get("size", 0)) for item in applied["quarantined"])
    copied_bytes = copied_bytes_s2t + copied_bytes_t2s

    if dry_run:
        summary = {
            "operation_policy": plan.get("operation_policy", plan.get("summary", {}).get("operation_policy", "")),
            "mirror_scope": plan.get("mirror_scope", plan.get("summary", {}).get("mirror_scope", "none")),
            "would_copy": len(applied["copied"]),
            "would_copy_bytes": copied_bytes,
            "would_copy_source_to_target": copied_s2t,
            "would_copy_target_to_source": copied_t2s,
            "would_copy_bytes_source_to_target": copied_bytes_s2t,
            "would_copy_bytes_target_to_source": copied_bytes_t2s,
            "would_touch": len(applied["touched"]),
            "would_touch_source_to_target": touched_s2t,
            "would_touch_target_to_source": touched_t2s,
            "would_delete": len(applied["deleted"]),
            "would_delete_bytes": deleted_bytes,
            "would_delete_dirs": len(plan.get("summary", {}).get("planned_delete_dirs", [])),
            "would_quarantine": len(applied["quarantined"]),
            "would_quarantine_bytes": quarantined_bytes,
            "would_quarantine_dirs": len(plan.get("summary", {}).get("planned_quarantine_dirs", [])),
            "would_create_dirs": len(plan.get("summary", {}).get("planned_create_dirs", []))
                + len(plan.get("summary", {}).get("planned_create_dirs_in_target", []))
                + len(plan.get("summary", {}).get("planned_create_dirs_in_source", [])),
            "would_create_dirs_in_target": len(plan.get("summary", {}).get("planned_create_dirs_in_target", plan.get("summary", {}).get("planned_create_dirs", []))),
            "would_create_dirs_in_source": len(plan.get("summary", {}).get("planned_create_dirs_in_source", [])),
            "conflicts": len(applied["conflicts"]),
            "skipped": len(applied["skipped"]),
            "errors": len(applied["errors"]),
        }
        if applied.get("phase_skip_reason"):
            summary["phase_skip_reason"] = applied["phase_skip_reason"]
        return summary

    summary = {
        "operation_policy": plan.get("operation_policy", plan.get("summary", {}).get("operation_policy", "")),
        "mirror_scope": plan.get("mirror_scope", plan.get("summary", {}).get("mirror_scope", "none")),
        "copied": len(applied["copied"]),
        "copied_bytes": copied_bytes,
        "copied_source_to_target": copied_s2t,
        "copied_target_to_source": copied_t2s,
        "copied_bytes_source_to_target": copied_bytes_s2t,
        "copied_bytes_target_to_source": copied_bytes_t2s,
        "touched": len(applied["touched"]),
        "touched_source_to_target": touched_s2t,
        "touched_target_to_source": touched_t2s,
        "deleted": len(applied["deleted"]),
        "deleted_bytes": deleted_bytes,
        "deleted_dirs": len(applied["deleted_dirs"]),
        "quarantined": len(applied["quarantined"]),
        "quarantined_bytes": quarantined_bytes,
        "quarantined_dirs": len(applied["quarantined_dirs"]),
        "verified": len(applied["verified"]),
        "created_dirs": len(applied["created_dirs"]),
        "created_dirs_in_target": created_in_target,
        "created_dirs_in_source": created_in_source,
        "conflicts": len(applied["conflicts"]),
        "skipped": len(applied["skipped"]),
        "errors": len(applied["errors"]),
    }
    if applied.get("phase_skip_reason"):
        summary["phase_skip_reason"] = applied["phase_skip_reason"]
    return summary
def _item_size_for_copy(item: dict, direction: str) -> int:
    size_src = item.get("target") if direction == "target_to_source" else item.get("source")
    return int((size_src or {}).get("size", 0))


def _source_mtime_for_item(item: dict, direction: str) -> int:
    time_source = item.get("target") if direction == "target_to_source" else item.get("source")
    return int((time_source or {}).get("mtime_ns", 0))


def _create_parent_dirs_for_copy(copy_to_root: Path, dst_path: Path, side: str, created_dir_keys: set[tuple[str, str]], applied: dict) -> None:
    parent = dst_path.parent
    if parent == copy_to_root:
        ensure_dir(parent)
        return
    missing_dirs: list[Path] = []
    probe = parent
    while probe != copy_to_root and not probe.exists():
        missing_dirs.append(probe)
        probe = probe.parent
    ensure_dir(parent)
    for created in reversed(missing_dirs):
        created_rel = normalize_rel_path(created.relative_to(copy_to_root))
        created_key = (side, created_rel)
        if created_key not in created_dir_keys:
            created_dir_keys.add(created_key)
            applied["created_dirs"].append({"rel_path": created_rel, "side": side})


def _verify_copied_file(src_path: Path, dst_path: Path, rel_path: str, direction: str, applied: dict) -> None:
    try:
        src_stat = src_path.stat()
        dst_stat = dst_path.stat()
        if src_stat.st_size != dst_stat.st_size:
            applied["errors"].append({"rel_path": rel_path, "error": "verify_failed: size_mismatch", "direction": direction})
            return
        src_hash = hash_file(src_path)
        dst_hash = hash_file(dst_path)
        if src_hash != dst_hash:
            applied["errors"].append({"rel_path": rel_path, "error": "verify_failed: hash_mismatch", "direction": direction})
            return
        applied["verified"].append({"rel_path": rel_path, "direction": direction, "hash": src_hash})
    except Exception as exc:
        applied["errors"].append({"rel_path": rel_path, "error": f"verify_failed: {exc.__class__.__name__}: {exc}", "direction": direction})


def _unique_quarantine_path(quarantine_root: Path, rel_path: str) -> Path:
    candidate = quarantine_root / normalize_rel_text(rel_path)
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    return unique_path(candidate.with_name(f"{stem}_{timestamp_slug()}{suffix}"))


def _quarantine_target_file(target_root: Path, quarantine_root: Path, operation_id: str, item: dict, applied: dict) -> None:
    rel_path = item["rel_path"]
    source_path = target_root / rel_path
    if not source_path.exists():
        applied["quarantined"].append(
            {
                "original_rel_path": rel_path,
                "quarantine_rel_path": None,
                "size": int((item.get("target") or {}).get("size", 0)),
                "mtime_ns": int((item.get("target") or {}).get("mtime_ns", 0)),
                "reason": "target_only",
                "operation_id": operation_id,
                "missing_before_quarantine": True,
            }
        )
        return
    stat_info = source_path.stat()
    quarantine_path = _unique_quarantine_path(quarantine_root, rel_path)
    ensure_dir(quarantine_path.parent)
    shutil.move(str(source_path), str(quarantine_path))
    applied["quarantined"].append(
        {
            "original_rel_path": rel_path,
            "quarantine_rel_path": normalize_rel_path(quarantine_path.relative_to(target_root)),
            "size": int(stat_info.st_size),
            "mtime_ns": int(stat_info.st_mtime_ns),
            "reason": "target_only",
            "operation_id": operation_id,
        }
    )


def _quarantine_empty_dirs(target_root: Path, quarantine_root: Path, operation_id: str, planned_dirs: list[str], applied: dict) -> None:
    for rel_dir in sorted(planned_dirs, key=lambda value: value.count("/"), reverse=True):
        path = target_root / rel_dir
        try:
            if not path.exists() or not path.is_dir():
                continue
            if any(path.iterdir()):
                continue
            quarantine_dir = quarantine_root / normalize_rel_text(rel_dir)
            ensure_dir(quarantine_dir)
            path.rmdir()
            applied["quarantined_dirs"].append(
                {
                    "original_rel_path": rel_dir,
                    "quarantine_rel_path": normalize_rel_path(quarantine_dir.relative_to(target_root)),
                    "reason": "target_only_empty_dir",
                    "operation_id": operation_id,
                }
            )
        except OSError:
            continue


def _write_quarantine_reports(target_root: Path, operation_id: str, applied: dict) -> dict | None:
    if not applied["quarantined"] and not applied["quarantined_dirs"]:
        return None
    payload = {
        "operation_id": operation_id,
        "target_root": str(target_root),
        "quarantine_root": str(target_root / QUARANTINE_DIR_NAME / operation_id),
        "files": applied["quarantined"],
        "dirs": applied["quarantined_dirs"],
    }
    json_path = output_path("quarantine_report")
    txt_path = output_path("quarantine_report", ext="txt")
    save_json(json_path, payload)
    lines = [
        "AUDION QUARANTINE REPORT",
        "========================",
        "",
        f"operation_id: {operation_id}",
        f"target_root: {target_root}",
        f"quarantine_root: {target_root / QUARANTINE_DIR_NAME / operation_id}",
        "",
        "files:",
    ]
    for item in applied["quarantined"]:
        lines.append(f"  - {item.get('original_rel_path')} -> {item.get('quarantine_rel_path')} ({item.get('size', 0)} bytes)")
    lines.append("")
    lines.append("dirs:")
    for item in applied["quarantined_dirs"]:
        lines.append(f"  - {item.get('original_rel_path')} -> {item.get('quarantine_rel_path')}")
    save_text(txt_path, "\n".join(lines) + "\n")
    return {"json": str(json_path), "txt": str(txt_path)}


def apply_plan(
    plan: dict,
    *,
    dry_run: bool = False,
    allow_hard_delete: bool = True,
    override_delete_ratio: bool = False,
    override_filtered_hard: bool = False,
    expect_confirmation: str | None = None,
) -> dict:
    source_root = Path(plan["source_root"])
    target_root = Path(plan["target_root"])
    started_at = time.time()
    operation_policy = str(plan.get("operation_policy") or plan.get("summary", {}).get("operation_policy") or "copy_update")
    operation_id = timestamp_slug()
    summary = plan.get("summary", {})

    expected = str(expect_confirmation or "").strip()
    if expected:
        actual = plan_confirmation_token(plan)
        if expected.upper() != actual.upper():
            raise PreviewConfirmationMismatch(expected, actual)

    if not dry_run and bool(plan.get("anchor", False)):
        ensure_anchored_roots(source_root, target_root)

    files_to_delete = int(summary.get("files_to_delete", 0))
    target_files = int(summary.get("target_considered_files", summary.get("target_total_files", 0)) or 0)
    if (
        not dry_run
        and allow_hard_delete
        and operation_policy == "mirror_hard"
        and files_to_delete >= DELETE_COUNT_FLOOR
        and target_files > 0
        and (files_to_delete / target_files) > DELETE_RATIO_LIMIT
        and not override_delete_ratio
    ):
        raise DeleteRatioExceeded(files_to_delete, target_files, files_to_delete / target_files)

    mirror_scope = str(summary.get("mirror_scope", ""))
    if (
        not dry_run
        and allow_hard_delete
        and operation_policy == "mirror_hard"
        and mirror_scope == "filtered"
        and not override_filtered_hard
    ):
        raise FilteredHardMirrorBlocked(
            "Refusing mirror_hard with a filtered scope: only files matching the "
            "filter would be deleted from the target, which is rarely intended. "
            "Re-run with override_filtered_hard=True to proceed."
        )

    applied = {
        "_source_root": str(source_root),
        "_target_root": str(target_root),
        "copied": [],
        "verified": [],
        "touched": [],
        "quarantined": [],
        "quarantined_dirs": [],
        "deleted": [],
        "deleted_dirs": [],
        "created_dirs": [],
        "conflicts": [],
        "skipped": [],
        "errors": [],
        "phase_skip_reason": "",
    }
    created_dir_keys: set[tuple[str, str]] = set()
    copy_items: list[dict] = []
    touch_items: list[dict] = []
    quarantine_items: list[dict] = []
    delete_items: list[dict] = []

    for item in plan["items"]:
        action = item["action"]
        rel_path = item["rel_path"]
        direction = str(item.get("direction", "source_to_target"))

        if action in {"same", "extra_target", "extra_source"}:
            applied["skipped"].append({"rel_path": rel_path, "action": action, "direction": direction})
            continue

        if action == "conflict":
            applied["conflicts"].append({"rel_path": rel_path, "reason": item.get("reason", "conflict")})
            continue

        if action == "error":
            applied["errors"].append({"rel_path": rel_path, "error": item.get("reason", "unknown")})
            continue

        if dry_run:
            if action == "copy":
                applied["copied"].append({"rel_path": rel_path, "dry_run": True, "size": _item_size_for_copy(item, direction), "direction": direction})
            elif action == "touch":
                applied["touched"].append({"rel_path": rel_path, "dry_run": True, "direction": direction})
            elif action == "quarantine":
                target_item = item.get("target") or {}
                applied["quarantined"].append(
                    {
                        "original_rel_path": rel_path,
                        "quarantine_rel_path": None,
                        "dry_run": True,
                        "size": int(target_item.get("size", 0)),
                        "mtime_ns": int(target_item.get("mtime_ns", 0)),
                        "reason": "target_only",
                        "operation_id": operation_id,
                    }
                )
            elif action == "delete":
                applied["deleted"].append({"rel_path": rel_path, "dry_run": True, "size": int(item.get("target", {}).get("size", 0)), "direction": direction})
            else:
                applied["errors"].append({"rel_path": rel_path, "error": item.get("reason", "unknown"), "direction": direction})
            continue

        if action == "copy":
            copy_items.append(item)
        elif action == "touch":
            touch_items.append(item)
        elif action == "quarantine":
            quarantine_items.append(item)
        elif action == "delete":
            delete_items.append(item)
        else:
            applied["errors"].append({"rel_path": rel_path, "error": item.get("reason", "unknown_action"), "direction": direction})

    for item in copy_items:
        rel_path = item["rel_path"]
        direction = str(item.get("direction", "source_to_target"))
        target_side_root, _src_path, dst_path = _resolve_item_paths(source_root, target_root, rel_path, direction)
        side = "source" if target_side_root == source_root else "target"
        try:
            _create_parent_dirs_for_copy(target_side_root, dst_path, side, created_dir_keys, applied)
        except Exception as exc:
            applied["errors"].append({"rel_path": rel_path, "error": f"{exc.__class__.__name__}: {exc}", "direction": direction})

    for item in copy_items:
        rel_path = item["rel_path"]
        direction = str(item.get("direction", "source_to_target"))
        _target_side_root, src_path, dst_path = _resolve_item_paths(source_root, target_root, rel_path, direction)
        try:
            _safe_copy2(src_path, dst_path)
            applied["copied"].append({"rel_path": rel_path, "size": _item_size_for_copy(item, direction), "direction": direction})
        except Exception as exc:
            applied["errors"].append({"rel_path": rel_path, "error": f"{exc.__class__.__name__}: {exc}", "direction": direction})

    for item in copy_items:
        rel_path = item["rel_path"]
        direction = str(item.get("direction", "source_to_target"))
        _target_side_root, src_path, dst_path = _resolve_item_paths(source_root, target_root, rel_path, direction)
        if dst_path.exists():
            _verify_copied_file(src_path, dst_path, rel_path, direction, applied)

    for item in touch_items:
        rel_path = item["rel_path"]
        direction = str(item.get("direction", "source_to_target"))
        _target_side_root, _src_path, dst_path = _resolve_item_paths(source_root, target_root, rel_path, direction)
        try:
            source_mtime_ns = _source_mtime_for_item(item, direction)
            os.utime(dst_path, ns=(source_mtime_ns, source_mtime_ns))
            applied["touched"].append({"rel_path": rel_path, "direction": direction})
        except Exception as exc:
            applied["errors"].append({"rel_path": rel_path, "error": f"{exc.__class__.__name__}: {exc}", "direction": direction})

    destructive_items = quarantine_items or delete_items or plan.get("summary", {}).get("planned_delete_dirs") or plan.get("summary", {}).get("planned_quarantine_dirs")
    if applied["errors"] and destructive_items:
        applied["phase_skip_reason"] = "Deletion/quarantine phase skipped because earlier phase had errors."

    if not applied["errors"]:
        if quarantine_items:
            quarantine_root = target_root / QUARANTINE_DIR_NAME / operation_id
            for item in quarantine_items:
                try:
                    _quarantine_target_file(target_root, quarantine_root, operation_id, item, applied)
                except Exception as exc:
                    applied["errors"].append({"rel_path": item.get("rel_path", ""), "error": f"{exc.__class__.__name__}: {exc}", "direction": "target_only"})
            _quarantine_empty_dirs(
                target_root,
                quarantine_root,
                operation_id,
                list(plan.get("summary", {}).get("planned_quarantine_dirs", [])),
                applied,
            )

        if delete_items and allow_hard_delete:
            for item in delete_items:
                rel_path = item["rel_path"]
                dst_path = target_root / rel_path
                try:
                    if dst_path.exists():
                        size = dst_path.stat().st_size if dst_path.is_file() else 0
                        dst_path.unlink()
                        applied["deleted"].append({"rel_path": rel_path, "size": int(size), "direction": "target_only"})
                    else:
                        applied["deleted"].append({"rel_path": rel_path, "size": int(item.get("target", {}).get("size", 0)), "direction": "target_only"})
                except Exception as exc:
                    applied["errors"].append({"rel_path": rel_path, "error": f"{exc.__class__.__name__}: {exc}", "direction": "target_only"})

            planned_delete_dirs = sorted(plan.get("summary", {}).get("planned_delete_dirs", []), key=lambda x: x.count("/"), reverse=True)
            for rel_dir in planned_delete_dirs:
                path = target_root / rel_dir
                try:
                    if path.exists() and path.is_dir():
                        path.rmdir()
                        applied["deleted_dirs"].append({"rel_path": rel_dir})
                except OSError:
                    continue

    summary = _build_apply_summary(applied, plan, dry_run=dry_run)
    summary["elapsed_seconds"] = round(time.time() - started_at, 3)
    quarantine_reports = _write_quarantine_reports(target_root, operation_id, applied) if not dry_run else None

    payload = {
        "action": "sync_apply",
        "dry_run": dry_run,
        "operation_id": operation_id,
        "operation_policy": operation_policy,
        "anchor": bool(plan.get("anchor", False)),
        "confirmation": plan_confirmation_token(plan),
        "source_root": str(source_root),
        "target_root": str(target_root),
        "quarantine_root": str(target_root / QUARANTINE_DIR_NAME / operation_id) if quarantine_items else None,
        "warnings": plan.get("warnings", []),
        "summary": summary,
        "details": {
            key: value
            for key, value in applied.items()
            if not key.startswith("_")
        },
        "quarantine_reports": quarantine_reports,
    }
    report_prefix = "sync2_apply" if plan.get("action") == "compare_two_way" else "sync_apply"
    summary_prefix = "sync2" if plan.get("action") == "compare_two_way" else "sync"
    report = output_path(report_prefix)
    save_json(report, payload)
    payload["report"] = str(report)
    payload["summary_reports"] = write_summary_bundle("apply", payload, summary, prefix=summary_prefix)
    return payload
