from __future__ import annotations

from pathlib import Path
import argparse
import ipaddress
import os
import socket
import subprocess
import sys
import time
import webbrowser


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
APP_PY = ROOT / "system_core" / "ui_nicegui" / "app.py"
GUI_PID_FILE = ROOT / "logs" / "gui_server.pid"
APP_ICON = ROOT / "system_core" / "icons" / "app.ico"


def get_window_icon() -> str | None:
    icon = Path(os.environ.get("AUDION_APP_ICON", str(APP_ICON)))
    return str(icon) if icon.exists() else None


def configure_windows_taskbar() -> None:
    if os.name != "nt":
        return
    app_id = os.environ.get("AUDION_APP_ID")
    if not app_id:
        clean = "".join(ch if ch.isalnum() else "." for ch in ROOT.name).strip(".")
        app_id = f"Audion.Tools.{clean or 'App'}"
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:
        pass

from system_core.core.jobs import prepare_gui_subprocess_command, utf8_subprocess_env


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audion GUI window.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--browser", action="store_true", help="Open in the default browser instead of pywebview.")
    parser.add_argument("--gui", default="edgechromium", help="pywebview backend to use on Windows.")
    parser.add_argument("--elevate", action="store_true", help="Request administrator privileges on Windows.")
    parser.add_argument("--no-elevate", action="store_true", help="Compatibility option; elevation is opt-in by default.")
    return parser.parse_args()


def is_windows_admin() -> bool:
    if os.name != "nt":
        return True
    try:
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_elevated() -> bool:
    if os.name != "nt":
        return False
    try:
        import ctypes

        params = subprocess.list2cmdline([str(Path(__file__).resolve()), *sys.argv[1:]])
        result = ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            sys.executable,
            params,
            str(ROOT),
            1,
        )
        return int(result) > 32
    except Exception as exc:
        print(f"UAC elevation failed: {exc}")
        return False


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


def choose_port(host: str, preferred_port: int) -> int:
    port = preferred_port
    while port_is_open(host, port):
        port += 1
    return port


def process_exists(pid: int) -> bool:
    try:
        import ctypes

        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False
    except Exception:
        return False


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


def kill_process_tree(pid: int) -> None:
    if pid <= 0 or not process_exists(pid):
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            creationflags=hidden_subprocess_flags(),
            startupinfo=hidden_subprocess_startupinfo(),
        )
        return
    try:
        os.kill(pid, 15)
    except OSError:
        pass


def cleanup_previous_server() -> None:
    try:
        if not GUI_PID_FILE.exists():
            return
        pid = int(GUI_PID_FILE.read_text(encoding="utf-8").strip())
        kill_process_tree(pid)
        GUI_PID_FILE.unlink(missing_ok=True)
    except Exception:
        pass


def wait_for_server(host: str, port: int, timeout: float = 20.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if port_is_open(host, port):
            return True
        time.sleep(0.2)
    return False


def start_server(host: str, port: int) -> subprocess.Popen[str] | None:
    logs = ROOT / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    stdout = (logs / "gui_server_stdout.log").open("w", encoding="utf-8")
    stderr = (logs / "gui_server_stderr.log").open("w", encoding="utf-8")
    env = utf8_subprocess_env()
    env.pop("PYTEST_CURRENT_TEST", None)
    env.pop("NICEGUI_SCREEN_TEST_PORT", None)
    env["PYTHONUNBUFFERED"] = "1"
    server = subprocess.Popen(
        prepare_gui_subprocess_command([sys.executable, "-u", str(APP_PY), "--host", host, "--port", str(port), "--no-browser"]),
        cwd=str(ROOT),
        stdout=stdout,
        stderr=stderr,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        creationflags=hidden_subprocess_flags(),
        startupinfo=hidden_subprocess_startupinfo(),
    )
    GUI_PID_FILE.write_text(str(server.pid), encoding="utf-8")
    return server


def stop_server(server: subprocess.Popen[str] | None) -> None:
    if server and server.poll() is None:
        kill_process_tree(server.pid)
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=2)
    GUI_PID_FILE.unlink(missing_ok=True)


def main() -> int:
    args = parse_args()
    assert_gui_host_allowed(args.host)
    elevation_requested = (bool(args.elevate) or env_flag_enabled("AUDION_ELEVATE")) and not args.no_elevate
    if os.name == "nt" and elevation_requested and os.environ.get("AUDION_NO_ELEVATE") != "1" and not is_windows_admin():
        if relaunch_elevated():
            return 0
        print("Administrator privileges were not granted. Continue without --elevate to run without UAC.")
        return 1

    os.environ.setdefault("PYWEBVIEW_LOG", "error")
    configure_windows_taskbar()
    cleanup_previous_server()
    port = choose_port(args.host, args.port)
    url = f"http://{args.host}:{port}/"
    server = start_server(args.host, port)

    if not wait_for_server(args.host, port):
        print(f"GUI server did not start: {url}")
        stop_server(server)
        return 1

    if args.browser:
        try:
            webbrowser.open(url)
            if server:
                print(f"GUI server is running: {url}")
                print("Close this console window to stop the server.")
                server.wait()
            return 0
        except KeyboardInterrupt:
            return 0
        finally:
            stop_server(server)

    try:
        import webview  # type: ignore
    except Exception as exc:
        print(f"pywebview is not available: {exc}")
        print(f"Browser fallback is available explicitly: {Path(__file__).name} --browser")
        stop_server(server)
        return 1

    try:
        webview.create_window("Audion Disk Tools", url, width=1600, height=900, min_size=(1180, 720))
        webview.start(
            gui=args.gui,
            debug=False,
            private_mode=False,
            storage_path=str(ROOT / "._runtime" / "webview"),
            icon=get_window_icon(),
        )
        return 0
    except Exception as exc:
        print(f"pywebview failed: {exc}")
        print(f"Browser fallback is available explicitly: {Path(__file__).name} --browser")
        return 1
    finally:
        stop_server(server)


if __name__ == "__main__":
    raise SystemExit(main())
