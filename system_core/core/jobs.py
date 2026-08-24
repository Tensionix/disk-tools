from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence
import ctypes
import importlib
import json
import os
import shlex
import subprocess
import traceback

from .logging_utils import append_log, timestamp
from .manifest import Operation
from .paths import ProjectPaths


LogCallback = Callable[[str], None]
ProgressCallback = Callable[[float], None]
CancelCallback = Callable[[], bool]


@dataclass
class JobContext:
    paths: ProjectPaths
    operation: Operation
    log_file: Path
    report_dir: Path
    log_callback: LogCallback | None = None
    progress_callback: ProgressCallback | None = None
    cancel_callback: CancelCallback | None = None

    def log(self, message: str) -> None:
        append_log(self.log_file, message)
        if self.log_callback:
            self.log_callback(message)

    def progress(self, value: float) -> None:
        if self.progress_callback:
            self.progress_callback(max(0.0, min(1.0, float(value))))

    def cancelled(self) -> bool:
        return bool(self.cancel_callback and self.cancel_callback())


@dataclass
class JobResult:
    ok: bool
    message: str
    data: dict[str, Any]


def utf8_subprocess_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    if extra:
        env.update(extra)
    env.pop("NO_COLOR", None)
    if env.get("CLICOLOR") == "0":
        env.pop("CLICOLOR", None)
    env["CLICOLOR"] = "1"
    env["CLICOLOR_FORCE"] = "1"
    env["FORCE_COLOR"] = "1"
    env["AUDION_GUI_TERMINAL"] = "1"
    return env


def _command_executable_name(command: Sequence[str]) -> str:
    if not command:
        return ""
    raw = str(command[0]).strip().strip('"')
    return Path(raw).name.lower()


def is_python_command(command: Sequence[str]) -> bool:
    name = _command_executable_name(command)
    return name in {"python", "python.exe", "pythonw", "pythonw.exe"} or (
        name.startswith("python3") and (name.endswith(".exe") or "." not in name)
    )


def prepare_gui_subprocess_command(command: Sequence[str]) -> list[str]:
    prepared = [str(part) for part in command]
    if not is_python_command(prepared):
        return prepared
    if any(part == "-u" for part in prepared[1:3]):
        return prepared
    return [prepared[0], "-u", *prepared[1:]]


def gui_subprocess_output_kwargs(command: Sequence[str]) -> dict[str, Any]:
    if not is_python_command(command):
        return {}
    return {"text": True, "encoding": "utf-8", "errors": "replace"}


def _windows_command_line_to_argv(command: str) -> list[str] | None:
    if os.name != "nt":
        return None
    try:
        argc = ctypes.c_int()
        shell32 = ctypes.windll.shell32  # type: ignore[attr-defined]
        shell32.CommandLineToArgvW.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_int)]
        shell32.CommandLineToArgvW.restype = ctypes.POINTER(ctypes.c_wchar_p)
        argv = shell32.CommandLineToArgvW(command, ctypes.byref(argc))
        if not argv:
            return None
        try:
            return [argv[index] for index in range(argc.value)]
        finally:
            ctypes.windll.kernel32.LocalFree(argv)  # type: ignore[attr-defined]
    except Exception:
        return None


def split_command_line(command: str) -> list[str]:
    windows_args = _windows_command_line_to_argv(command)
    if windows_args is not None:
        return windows_args
    return shlex.split(command, posix=os.name != "nt")


def direct_python_command_args(command: str) -> list[str] | None:
    try:
        args = split_command_line(command)
    except ValueError:
        return None
    if not args or not is_python_command(args):
        return None
    return prepare_gui_subprocess_command(args)


def hidden_subprocess_startupinfo() -> subprocess.STARTUPINFO | None:
    if os.name != "nt" or not hasattr(subprocess, "STARTUPINFO"):
        return None
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = 0
    return startupinfo


def hidden_subprocess_creationflags() -> int:
    if os.name == "nt" and hasattr(subprocess, "CREATE_NO_WINDOW"):
        return int(subprocess.CREATE_NO_WINDOW)
    return 0


def hidden_subprocess_kwargs() -> dict[str, Any]:
    return {
        "startupinfo": hidden_subprocess_startupinfo(),
        "creationflags": hidden_subprocess_creationflags(),
    }


def _load_callable(service: str) -> Callable[[JobContext], Any]:
    module_name, function_name = service.split(":", 1)
    module = importlib.import_module(module_name)
    return getattr(module, function_name)


def execute_operation(
    paths: ProjectPaths,
    operation: Operation,
    log_callback: LogCallback | None = None,
    progress_callback: ProgressCallback | None = None,
    cancel_callback: CancelCallback | None = None,
) -> JobResult:
    run_stamp = timestamp().replace(":", "-")
    log_file = paths.logs / f"{run_stamp}_{operation.id}.log"
    report_dir = paths.report / f"{run_stamp}_{operation.id}"
    report_dir.mkdir(parents=True, exist_ok=True)
    context = JobContext(paths, operation, log_file, report_dir, log_callback, progress_callback, cancel_callback)

    try:
        context.log(f"Starting operation: {operation.id}")
        if operation.parameters:
            context.log(f"Parameters: {json.dumps(operation.parameters, ensure_ascii=False, sort_keys=True)}")
        context.progress(0.0)
        result = _load_callable(operation.service)(context)
        context.progress(1.0)
        context.log(f"Finished operation: {operation.id}")

        if isinstance(result, dict):
            return JobResult(True, "Operation finished.", result)
        return JobResult(True, str(result or "Operation finished."), {})

    except Exception as exc:
        data: dict[str, Any] = {}
        guard_payload = getattr(exc, "guard_payload", None)
        if isinstance(guard_payload, dict):
            context.log(f"Plan guard: {exc}")
            data["guard"] = guard_payload
        else:
            context.log(traceback.format_exc())
        return JobResult(False, f"{exc.__class__.__name__}: {exc}", data)
