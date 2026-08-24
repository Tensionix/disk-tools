"""One section moves data, and the tool that does it is not the user's problem.

Until now the window was split by tool: a Network section that was Robocopy and a
Cloud section that was rclone. That put the same operation in two places with two
mental models, and left the one thing Robocopy cannot do — comparing by hash —
unavailable exactly where a copy over a flaky share needs it most.

Here the person picks an operation. The engine follows from the pair and from whether
hashes were asked for, and the window says which one will run, the same way it
says how the bytes will travel.

Robocopy is not retired: for folder to folder and folder to share it is faster
and it carries the NTFS attribute bits that rclone drops on Windows. It is
demoted from a section to an engine.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
import ctypes
import re
import os

from .rclone_service import RcloneEndpointSpec, route_objection


OPERATION_ONE_WAY = "one_way"
OPERATION_MIRROR = "mirror"
OPERATION_MOVE = "move"
OPERATION_TWO_WAY = "two_way"
OPERATION_VERIFY = "verify"

# What separates a mirror from a one-way sync is not deletion policy — it is
# whether the destination is allowed anything of its own.
#
# A mirror's destination is a copy and owns nothing: whatever is there and not at
# the source is a discrepancy, and clearing it is the point. That is the shape of
# a reference machine and its replicas.
#
# A one-way destination has a life of its own. Something lands on Google and has
# to reach Mega, where other things already live; making Mega identical to Google
# would wipe them. Clouds are a mesh, not a master with copies, which is why the
# section needs both.
TRANSFER_OPERATIONS: dict[str, dict[str, str]] = {
    OPERATION_ONE_WAY: {
        "label": "One-way",
        "label_ru": "Односторонняя",
        "description": "Carry what is here over there. The destination keeps everything of its own.",
        "description_ru": "Донести своё туда. Приёмник сохраняет всё собственное.",
    },
    OPERATION_MIRROR: {
        "label": "Backup mirror",
        "label_ru": "Зеркало",
        "description": "The destination is a copy and owns nothing: anything extra there is cleared.",
        "description_ru": "Приёмник — копия и своего не имеет: всё лишнее в нём убирается.",
    },
    OPERATION_MOVE: {
        "label": "Move",
        "label_ru": "Перенести",
        "description": "Carry it over and clear it from here. The source is empty afterwards.",
        "description_ru": "Донести туда и убрать отсюда. Источник после этого пуст.",
    },
    OPERATION_TWO_WAY: {
        "label": "Two-way sync",
        "label_ru": "Двусторонняя",
        "description": "Carry changes both ways, remembering the previous run.",
        "description_ru": "Разносить изменения в обе стороны, помня прошлый прогон.",
    },
    OPERATION_VERIFY: {
        "label": "Verify",
        "label_ru": "Сверить",
        "description": "Change nothing and report what differs.",
        "description_ru": "Ничего не менять и сообщить, что расходится.",
    },
}

# What each one becomes on the command line. The mirror is the only one that
# deletes, and that is exactly what makes it a mirror.
OPERATION_RCLONE_COMMAND: dict[str, str] = {
    OPERATION_ONE_WAY: "copy",
    OPERATION_MIRROR: "sync",
    OPERATION_MOVE: "move",
    OPERATION_TWO_WAY: "bisync",
    OPERATION_VERIFY: "check",
}

# The project's own local engine, and what each operation is called there.
#
# `run_manual_command` is richer than anything this module builds: it carries the
# quarantine policy, the thirty-four extension groups and the comparison report.
# So for a local pair it is not replaced — the operation simply chooses which of
# its commands runs, and three top-level sections that differed by this one word
# stop needing to exist separately.
#
# Move is absent on purpose: that engine has no such command, so it stays with
# Robocopy's /MOVE.
ENGINE_AUDITOR = "auditor"

OPERATION_AUDITOR_COMMAND: dict[str, str] = {
    OPERATION_MIRROR: "backup",
    OPERATION_ONE_WAY: "sync",
    OPERATION_TWO_WAY: "sync2",
    OPERATION_VERIFY: "compare",
}

ENGINE_ROBOCOPY = "robocopy"
ENGINE_RCLONE = "rclone"

# Seeing what a run would do, before it does it. Not an operation of its own:
# every operation has a version of this question, and the project already carries
# one as a separate mode — robocopy_scan — which is a flag wearing a button.
DRY_RUN_ARGS: dict[str, list[str]] = {
    ENGINE_RCLONE: ["--dry-run"],
    # /L lists without copying. /BYTES and /FP make the listing worth reading:
    # exact sizes and full paths rather than rounded numbers and bare names.
    ENGINE_ROBOCOPY: ["/L", "/BYTES", "/FP"],
}

ENGINE_LABELS: dict[str, dict[str, str]] = {
    ENGINE_ROBOCOPY: {"label": "Robocopy", "label_ru": "Robocopy"},
    ENGINE_RCLONE: {"label": "RClone", "label_ru": "RClone"},
}


def transfer_engine(
    operation: str,
    source: RcloneEndpointSpec,
    target: RcloneEndpointSpec,
    *,
    by_hash: bool = False,
) -> str:
    """Which tool runs this pair, given the operation.

    Robocopy wins where it is genuinely better — both ends on this machine or on
    a share — because it is faster and it copies the NTFS attribute bits, which
    rclone does not carry on Windows. It loses the moment something it cannot do
    is asked for: a remote, a hash comparison, or a two-way run.
    """
    if source.kind == "url" or source.local_path is None or target.local_path is None:
        return ENGINE_RCLONE
    if operation == OPERATION_TWO_WAY:
        return ENGINE_RCLONE
    if by_hash or operation == OPERATION_VERIFY:
        return ENGINE_RCLONE
    return ENGINE_ROBOCOPY


def engine_reason(engine: str, operation: str, source: RcloneEndpointSpec, target: RcloneEndpointSpec) -> dict[str, str]:
    """Why that engine, in one line the window can print under the choice."""
    if source.kind == "url":
        return {
            "reason": "The storage fetches the link itself, so the file never comes down this channel.",
            "reason_ru": "Хранилище само заберёт файл по ссылке — он не пойдёт через ваш канал.",
        }
    if source.local_path is None or target.local_path is None:
        return {
            "reason": "One side is a saved remote, which only RClone can reach.",
            "reason_ru": "Один из концов — сохранённый remote, до него доходит только RClone.",
        }
    if operation == OPERATION_TWO_WAY:
        return {
            "reason": "Two-way sync remembers the previous run. Robocopy has no such mode.",
            "reason_ru": "Двусторонняя помнит прошлый прогон. У Robocopy такого режима нет.",
        }
    if engine == ENGINE_RCLONE:
        return {
            "reason": "Comparing by hash. Robocopy weighs size and timestamp only.",
            "reason_ru": "Сверка по хешам. Robocopy взвешивает только размер и время.",
        }
    return {
        "reason": "Both sides are on this machine: Robocopy is faster and carries NTFS attribute bits.",
        "reason_ru": "Оба конца на этой машине: Robocopy быстрее и несёт биты атрибутов NTFS.",
    }


def path_is_unc(path: Path | None) -> bool:
    if path is None:
        return False
    text = str(path)
    return text.startswith("\\\\") or str(path.anchor).startswith("\\\\")


def volume_filesystem(path: Path | None) -> str:
    """The filesystem of the volume a path sits on, uppercased, or "" if unknown.

    Only used to decide whether coarse timestamps are a thing here, so an unknown
    answer is not a problem — it simply means the widening flags are left off.
    """
    if path is None or os.name != "nt" or path_is_unc(path):
        return ""
    anchor = str(path.anchor)
    if not anchor:
        return ""
    name = ctypes.create_unicode_buffer(261)
    filesystem = ctypes.create_unicode_buffer(261)
    try:
        ok = ctypes.windll.kernel32.GetVolumeInformationW(  # type: ignore[attr-defined]
            ctypes.c_wchar_p(anchor),
            name,
            ctypes.sizeof(name) // ctypes.sizeof(ctypes.c_wchar),
            None,
            None,
            None,
            filesystem,
            ctypes.sizeof(filesystem) // ctypes.sizeof(ctypes.c_wchar),
        )
    except Exception:
        return ""
    return filesystem.value.strip().upper() if ok else ""


def robocopy_time_args(source: Path | None, target: Path | None) -> list[str]:
    """The two flags that only make sense where timestamps are coarse.

    /FFT declares file times equal within two seconds and /DST absorbs the
    one-hour daylight-saving shift. They exist for FAT and for shares served by
    Samba or a NAS, where the stored resolution is coarse.

    They used to be passed on every run. On NTFS to NTFS that buys nothing and
    costs something: the window of "this file has not changed" is widened to two
    seconds, so a file written just after the previous pass can be skipped. The
    flags now follow the volumes.
    """
    for path in (source, target):
        if path_is_unc(path):
            return ["/FFT", "/DST"]
        filesystem = volume_filesystem(path)
        if filesystem and filesystem != "NTFS":
            return ["/FFT", "/DST"]
    return []


def bisync_workdir_args(project_root: Path) -> list[str]:
    """Keep the two-way memory inside the project instead of in the system.

    Two-way sync works by remembering both listings from the prior run, and by
    default it remembers into %LOCALAPPDATA%\\rclone\\bisync — outside the project,
    on the machine that ran it. This project keeps its state in its own folder.

    It goes under config rather than workspace on purpose: cleanup clears
    workspace, and losing these listings does not fail loudly. It forces a full
    resync on the next run, which is the one moment two-way sync has to be told
    which side wins.
    """
    return ["--workdir", str(project_root / "config" / "bisync")]


def mirror_guard_args(ceiling: int | None = None) -> list[str]:
    """A ceiling on how much one mirror run may delete, when one is asked for.

    Off unless set. The owner has mirrored this way for twenty five years without
    it, so imposing a number here would be guessing at their work and capping it:
    a release that drops a hundred old files is ordinary, and a default would
    stop it. Available, not assumed.

    Where it earns its place is the master folder failing to mount, reading as
    empty, and that emptiness being carried to every replica. Robocopy /MIR has
    no equivalent — an empty source empties the destination and no flag says
    otherwise.
    """
    if not ceiling or ceiling < 0:
        return []
    return ["--max-delete", str(int(ceiling))]


def transfer_plan(
    operation: str,
    source: RcloneEndpointSpec,
    target: RcloneEndpointSpec,
    *,
    by_hash: bool = False,
    russian: bool = False,
) -> dict[str, Any]:
    """Everything the window states above the run button, in one call."""
    engine = transfer_engine(operation, source, target, by_hash=by_hash)
    reason = engine_reason(engine, operation, source, target)
    key = "label_ru" if russian else "label"
    return {
        "operation": operation,
        "operation_label": TRANSFER_OPERATIONS[operation][key],
        "target": target.label,
        "engine": engine,
        "engine_label": ENGINE_LABELS[engine][key],
        "engine_reason": reason["reason_ru" if russian else "reason"],
    }


ROBOCOPY_BASE = ("/E", "/COPY:DAT", "/DCOPY:DAT", "/XJ", "/NP", "/TEE")

PACK_NONE = "none"
PACK_BEFORE = "before"

PACK_MODES: dict[str, dict[str, str]] = {
    PACK_NONE: {
        "label": "As it lies",
        "label_ru": "Как есть",
        "description": "Send the files themselves.",
        "description_ru": "Отправлять сами файлы.",
    },
    PACK_BEFORE: {
        "label": "Pack first",
        "label_ru": "Сначала упаковать",
        "description": "Archive the master, then send the archives. Fewer, larger objects, and a password if one is set.",
        "description_ru": "Заархивировать эталон, потом отправить архивы. Меньше объектов, крупнее каждый, и пароль если задан.",
    },
}


def pack_staging_dir(project_root: Path, label: str = "pack") -> Path:
    """Where the archives wait between being made and being sent.

    Under workspace rather than output: output is the owner's, and a transfer's
    intermediate files have no business appearing there. Cleanup empties
    workspace, which is exactly right for something that exists for one run.
    """
    safe = "".join(char if char.isalnum() or char in "._-" else "_" for char in label).strip("_") or "pack"
    return project_root / "workspace" / "transfer_pack" / safe


def pack_then_transfer_plan(
    operation: str,
    source: RcloneEndpointSpec,
    targets: list[RcloneEndpointSpec],
    *,
    project_root: Path,
    archive_options: dict[str, Any],
    russian: bool = False,
    **command_options: Any,
) -> dict[str, Any]:
    """Archive the master, then send the archives — as two steps, not one.

    The archiving section already does this well: many folders in, one archive
    each, formats and encryption chosen per run. Reaching for it rather than
    growing a second copy inside the transfer keeps one answer to "how is an
    archive made here".

    Only the source changes. The machines, the operation and the engine choice
    are decided exactly as they are for a plain run, because by then the staging
    folder is just a folder.
    """
    staging = pack_staging_dir(project_root, str(archive_options.get("name_prefix") or "pack"))
    packed_source = RcloneEndpointSpec(
        kind="workbench_source",
        spec=str(staging),
        label=str(staging),
        local_path=staging,
    )
    return {
        "pack": {
            **archive_options,
            "source_root": str(source.local_path or source.spec),
            "target_root": str(staging),
        },
        "staging": staging,
        "transfer": fan_out_commands(
            operation, packed_source, targets, russian=russian, **command_options
        ),
    }


def normalize_extension_masks(values: Any) -> list[str]:
    """Turn whatever the extension picker hands over into plain `*.ext` masks.

    It may arrive as `docx`, `.docx` or `*.docx`, and the same extension may come
    from two groups at once — the picker offers groups and individual entries
    both. Order is kept so a person reading the built command sees what they
    chose, in the order they chose it.
    """
    if isinstance(values, str):
        values = re.split(r"[,;\s]+", values)
    if not isinstance(values, (list, tuple, set)):
        return []
    masks: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        if text.startswith("*."):
            text = text.lower()
        elif text.startswith("."):
            text = "*" + text.lower()
        elif "." in text:
            # A dot inside means a whole filename, not an extension. Thumbs.db and
            # desktop.ini are the ones people actually want gone, and turning them
            # into *.thumbs.db matches nothing at all. The spelling is left as
            # written — it is a name, and a name is read by a person.
            pass
        elif not text.startswith("*"):
            text = "*." + text.lower()
        # Windows does not distinguish case here and neither should the list, or
        # the same extension arrives twice from two groups spelled differently.
        key = text.casefold()
        if key not in seen:
            seen.add(key)
            masks.append(text)
    return masks


# Above this many masks the command stops being readable and starts being a wall.
# The whole library is 301 extensions — 602 arguments and nearly five thousand
# characters, which fits the command line and fits nobody's eyes.
FILTER_FILE_THRESHOLD = 12


def write_filter_file(path: Path, masks: list[str], excluded: list[str] | None = None) -> Path:
    """The chosen extensions as an rclone filter file.

    Rules are read in order and the first match wins, so the exclusions go first
    and a closing `- *` drops everything not named. Written whole each time: a
    filter file that is half of the previous run is worse than none.
    """
    lines = [
        "# Собрано разделом Трансфер данных. Правила читаются сверху вниз,",
        "# первое совпадение решает.",
    ]
    lines.extend(f"- {mask}" for mask in (excluded or []))
    if masks:
        lines.extend(f"+ {mask}" for mask in masks)
        lines.append("- *")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return path


def extension_filter_args(
    engine: str,
    masks: list[str],
    excluded: list[str] | None = None,
    filter_file: Path | None = None,
) -> list[str]:
    """The same choice of extensions, said in each engine's own words.

    rclone wants `--include *.docx`, and the pattern matches at every depth. The
    obvious-looking `**/*.docx` does not: it misses everything in the top folder,
    which is where the files usually are. Measured, not assumed.

    Robocopy takes bare masks, and they must sit straight after the source and
    destination — anywhere else and it reads them as another argument entirely.

    Excluded extensions are a second question, not a correction to the first.
    Where something is included, everything else is already out: rclone's own
    rule, checked across five orderings, is that any --include excludes the rest.
    So the excluded list earns its place in the other case — take everything
    except this — which is how a person says "clone the folder but not the
    leftovers".
    """
    kept = [mask for mask in masks if mask not in (excluded or [])]
    dropped = list(excluded or [])
    if engine == ENGINE_RCLONE:
        if filter_file is not None and len(kept) + len(dropped) > FILTER_FILE_THRESHOLD:
            write_filter_file(filter_file, kept, dropped)
            return ["--filter-from", str(filter_file)]
        args = [item for mask in kept for item in ("--include", mask)]
        # Adding --exclude beside --include changes nothing, and a flag that
        # changes nothing in a logged command is a question for whoever reads it.
        if not kept:
            args = [item for mask in dropped for item in ("--exclude", mask)]
        return args
    args = list(kept)
    if dropped:
        args.extend(["/XF", *dropped])
    return args


def build_transfer_command(
    operation: str,
    source: RcloneEndpointSpec,
    target: RcloneEndpointSpec,
    *,
    engine: str,
    rclone_exe: str = "rclone",
    robocopy_exe: str = "robocopy",
    project_root: Path | None = None,
    threads: int = 8,
    retries: int = 2,
    delete_ceiling: int | None = None,
    dry_run: bool = False,
    masks: list[str] | None = None,
    excluded_masks: list[str] | None = None,
    extra: list[str] | None = None,
) -> list[str]:
    """The argv that will actually run for one source-target pair.

    The operation is the same word whichever engine takes it — that is the whole
    point of merging the sections — so the difference between `rclone sync` and
    `robocopy /MIR` stops being something anyone has to know.

    Two-way and verify never reach Robocopy: it has neither. The caller is
    expected to have asked `transfer_engine` first, so a mismatch here is a
    programming error rather than a user's, and it says so.
    """
    if source.kind == "url":
        # Fetching a link is its own command: the storage pulls the file, so it
        # never travels down this channel on its way back up. Nothing else can be
        # asked of a link — there is nothing there to mirror against, compare
        # with, or carry changes back to.
        if operation != OPERATION_ONE_WAY:
            raise ValueError(
                f"A link can only be fetched, not '{operation}'. There is nothing at the far end to compare with."
            )
        command = [rclone_exe, "copyurl", source.spec, target.spec, "--auto-filename"]
        if dry_run:
            command.extend(DRY_RUN_ARGS[ENGINE_RCLONE])
        command.extend(extra or [])
        return command

    if engine == ENGINE_RCLONE:
        command = [rclone_exe, OPERATION_RCLONE_COMMAND[operation], source.spec, target.spec]
        command.extend(
            extension_filter_args(
                ENGINE_RCLONE,
                normalize_extension_masks(masks),
                normalize_extension_masks(excluded_masks),
                (project_root / 'workspace' / 'transfer_filter.txt') if project_root else None,
            )
        )
        if operation == OPERATION_MIRROR:
            command.extend(mirror_guard_args(delete_ceiling))
        if operation == OPERATION_TWO_WAY and project_root is not None:
            command.extend(bisync_workdir_args(project_root))
        if dry_run:
            command.extend(DRY_RUN_ARGS[ENGINE_RCLONE])
        command.extend(extra or [])
        return command

    if operation in {OPERATION_TWO_WAY, OPERATION_VERIFY}:
        raise ValueError(
            f"Robocopy cannot do '{operation}'. Ask transfer_engine() first — it hands this pair to RClone."
        )
    command = [robocopy_exe, str(source.local_path), str(target.local_path)]
    command.extend(extension_filter_args(ENGINE_ROBOCOPY, normalize_extension_masks(masks)))
    excluded = normalize_extension_masks(excluded_masks)
    if operation == OPERATION_MIRROR:
        # /MIR implies /E and adds the deletions that make it a mirror.
        command.append("/MIR")
        command.extend(item for item in ROBOCOPY_BASE if item != "/E")
    else:
        command.extend(ROBOCOPY_BASE)
    if operation == OPERATION_MOVE:
        # Copies, then removes from the source — files and the directories that
        # held them. Robocopy does have this; it is one of the few places where
        # it matches rclone command for command.
        command.append("/MOVE")
    command.extend(robocopy_time_args(source.local_path, target.local_path))
    command.extend([f"/MT:{max(1, min(128, threads))}", f"/R:{retries}", f"/W:{retries}"])
    if excluded:
        command.extend(["/XF", *excluded])
    if dry_run:
        command.extend(DRY_RUN_ARGS[ENGINE_ROBOCOPY])
    command.extend(extra or [])
    return command



# Robocopy answers in a bitmask, not in the usual nought-or-error: bit 0 means
# files were copied, bit 1 that extras exist at the destination, bit 2 that some
# mismatched. Anything below 8 is a success and most wrappers get this wrong,
# reporting every successful copy as a failure.
ROBOCOPY_SUCCESS_BELOW = 8


def run_succeeded(engine: str, exit_code: int) -> bool:
    if engine == ENGINE_ROBOCOPY:
        return 0 <= exit_code < ROBOCOPY_SUCCESS_BELOW
    return exit_code == 0


def fan_out_commands(
    operation: str,
    source: RcloneEndpointSpec,
    targets: list[RcloneEndpointSpec],
    *,
    by_hash: bool = False,
    russian: bool = False,
    **command_options: Any,
) -> list[dict[str, Any]]:
    """The whole run: one entry per machine, each with its own engine and argv.

    Built in full before anything starts, so the window can show what is about to
    happen to all of them and a refusal on machine three is discovered before
    machine one is touched. The order given is kept — a fan-out reads as a list,
    and a list that reorders itself is unreadable.
    """
    prepared: list[dict[str, Any]] = []
    for index, target in enumerate(targets):
        plan = transfer_plan(operation, source, target, by_hash=by_hash, russian=russian)
        objection = route_objection(OPERATION_RCLONE_COMMAND[operation], source, target)
        prepared.append(
            {
                "index": index,
                **plan,
                "refused": objection["reason_ru" if russian else "reason"] if objection else "",
                "command": []
                if objection
                else build_transfer_command(
                    operation, source, target, engine=plan["engine"], **command_options
                ),
            }
        )
    return prepared
