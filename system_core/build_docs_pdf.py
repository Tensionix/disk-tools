from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / "docs"
PDF_DIR = DOCS_DIR / "PDF"
WORKSPACE_DIR = ROOT / "workspace"

OFFICE_ROOT = Path(r"E:\TOOLS\Audion Office OCR AI")
OFFICE_PROJECT_ROOT = OFFICE_ROOT / "Audion Office OCR AI"


def first_existing_path(*candidates: Path) -> Path:
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


DEFAULT_ENGINE = first_existing_path(
    OFFICE_ROOT / "system_core" / "dev_markdown_pdf_engine.py",
    OFFICE_PROJECT_ROOT / "system_core" / "dev_markdown_pdf_engine.py",
)
DEFAULT_PDF_PYTHON = first_existing_path(
    OFFICE_ROOT / "runtime" / "python.exe",
    OFFICE_PROJECT_ROOT / "runtime" / "python.exe",
)
DEFAULT_PLAYWRIGHT_BROWSERS = first_existing_path(
    OFFICE_ROOT / "runtime" / ".playwright",
    OFFICE_PROJECT_ROOT / "runtime" / ".playwright",
)

SKIP_DIRS = {
    ".git",
    "._runtime",
    "__pycache__",
    "input",
    "logs",
    "output",
    "release",
    "report",
    "runtime",
    "wheelhouse",
    "workspace",
    "PDF",
}

ROOT_DOCS = [
    "USER_GUIDE_RU.md",
    "USER_GUIDE_EN.md",
    "README_RU.md",
    "README.md",
    "Audion_Disk_Tools_RClone.md",
    "install/README_INSTALL.md",
]


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Audion Disk Tools Markdown guides as PDF files under docs/PDF.",
    )
    parser.add_argument(
        "--theme",
        choices=["both", "dark", "light-sand"],
        default="both",
        help="PDF theme to render. Default keeps the upstream engine default: both.",
    )
    parser.add_argument(
        "--source",
        action="append",
        default=[],
        help="Markdown file or folder to render. Can be repeated. Default: curated guide/doc set.",
    )
    parser.add_argument(
        "--out-dir",
        default=str(PDF_DIR),
        help="Output directory. Default: docs/PDF.",
    )
    parser.add_argument(
        "--engine",
        default=os.environ.get("AUDION_MARKDOWN_PDF_ENGINE", str(DEFAULT_ENGINE)),
        help="Path to dev_markdown_pdf_engine.py.",
    )
    parser.add_argument(
        "--pdf-python",
        default=os.environ.get("AUDION_MARKDOWN_PDF_PYTHON", str(DEFAULT_PDF_PYTHON)),
        help="Python runtime to use if the current runtime lacks markdown/pdf dependencies.",
    )
    parser.add_argument(
        "--playwright-browsers-path",
        default=os.environ.get("PLAYWRIGHT_BROWSERS_PATH", ""),
        help="Optional Playwright browser payload path.",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove existing PDF files from the output directory before rendering.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned conversions without rendering.",
    )
    return parser.parse_args(argv)


def is_markdown(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in {".md", ".markdown"}


def project_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    return path.resolve()


def iter_markdown(root: Path) -> list[Path]:
    if is_markdown(root):
        return [root.resolve()]
    if not root.is_dir():
        return []
    results: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            dirname
            for dirname in dirnames
            if dirname not in SKIP_DIRS and not dirname.startswith(".")
        ]
        current = Path(dirpath)
        for filename in sorted(filenames, key=str.lower):
            candidate = current / filename
            if is_markdown(candidate):
                results.append(candidate.resolve())
    return results


def collect_default_sources() -> list[Path]:
    docs: list[Path] = []
    for rel_path in ROOT_DOCS:
        candidate = ROOT / rel_path
        if is_markdown(candidate):
            docs.append(candidate.resolve())
    if DOCS_DIR.exists():
        for candidate in sorted(DOCS_DIR.glob("*.md"), key=lambda item: item.name.lower()):
            if is_markdown(candidate):
                docs.append(candidate.resolve())
    return dedupe_sources(docs)


def collect_sources(values: list[str]) -> list[Path]:
    if not values:
        return collect_default_sources()
    docs: list[Path] = []
    for value in values:
        docs.extend(iter_markdown(project_path(value)))
    return dedupe_sources(docs)


def dedupe_sources(sources: list[Path]) -> list[Path]:
    seen: set[str] = set()
    result: list[Path] = []
    for source in sources:
        key = str(source.resolve()).lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(source.resolve())
    return result


def current_runtime_has_pdf_deps() -> bool:
    try:
        import markdown_it  # noqa: F401
        import playwright  # noqa: F401
    except Exception:
        return False
    return True


def choose_playwright_browsers(explicit: str) -> Path | None:
    if explicit:
        path = project_path(explicit)
        return path if path.exists() else None
    project_payload = ROOT / "runtime" / ".playwright"
    if project_payload.exists():
        return project_payload
    if DEFAULT_PLAYWRIGHT_BROWSERS.exists():
        return DEFAULT_PLAYWRIGHT_BROWSERS
    return None


def maybe_reexec_with_pdf_python(args: argparse.Namespace, argv: list[str]) -> int | None:
    if args.dry_run or current_runtime_has_pdf_deps():
        return None
    pdf_python = project_path(args.pdf_python)
    current_python = Path(sys.executable).resolve()
    if not pdf_python.exists() or pdf_python.resolve() == current_python:
        return None

    env = os.environ.copy()
    browsers = choose_playwright_browsers(args.playwright_browsers_path)
    if browsers is not None:
        env["PLAYWRIGHT_BROWSERS_PATH"] = str(browsers)
    command = [str(pdf_python), str(Path(__file__).resolve()), *argv]
    return subprocess.call(command, cwd=str(ROOT), env=env)


def load_engine(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Markdown PDF engine was not found: {path}")
    spec = importlib.util.spec_from_file_location("audion_external_markdown_pdf_engine", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load Markdown PDF engine: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.BASE_DIR = ROOT
    module.INPUT_DIR = ROOT / "input"
    return module


def safe_clean_output(out_dir: Path) -> None:
    resolved = out_dir.resolve()
    allowed = PDF_DIR.resolve()
    try:
        resolved.relative_to(allowed)
    except ValueError:
        raise RuntimeError(f"Refusing to clean outside docs/PDF: {resolved}")
    if not resolved.exists():
        return
    for pdf in resolved.rglob("*.pdf"):
        pdf.unlink()
    for directory in sorted((item for item in resolved.rglob("*") if item.is_dir()), reverse=True):
        try:
            directory.rmdir()
        except OSError:
            pass


def write_source_list(sources: list[Path]) -> Path:
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    path = WORKSPACE_DIR / "docs_pdf_sources.json"
    path.write_text(
        json.dumps([str(source) for source in sources], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def ensure_output_readme(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    readme = out_dir / "README.txt"
    readme.write_text(
        "Audion Disk Tools PDF documentation output.\n"
        "Generated by install\\Build-Docs-PDF.cmd / system_core\\build_docs_pdf.py.\n"
        "Default themes: dark and light-sand.\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    raw_args = sys.argv[1:] if argv is None else argv
    args = parse_args(raw_args)

    reexec_code = maybe_reexec_with_pdf_python(args, raw_args)
    if reexec_code is not None:
        return int(reexec_code)

    sources = collect_sources(args.source)
    if not sources:
        print("[INFO] No Markdown sources found.")
        return 0

    out_dir = project_path(args.out_dir)
    engine_path = project_path(args.engine)
    browsers = choose_playwright_browsers(args.playwright_browsers_path)
    if browsers is not None:
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(browsers)

    if args.clean and not args.dry_run:
        safe_clean_output(out_dir)
    ensure_output_readme(out_dir)

    source_list = write_source_list(sources)
    print("======================================================================")
    print("AUDION DISK TOOLS DOCS PDF")
    print("======================================================================")
    print(f"Root       : {ROOT}")
    print(f"Engine     : {engine_path}")
    print(f"Output     : {out_dir}")
    print(f"Sources    : {len(sources)}")
    if browsers is not None:
        print(f"Browsers   : {browsers}")
    print()

    engine = load_engine(engine_path)
    engine_args = [
        "--theme",
        args.theme,
        "--output-mode",
        "mirror-output",
        "--out-dir",
        str(out_dir),
        "--base-root",
        str(DOCS_DIR),
        "--source-list",
        str(source_list),
    ]
    if args.dry_run:
        engine_args.append("--dry-run")

    return int(engine.main(engine_args))


if __name__ == "__main__":
    raise SystemExit(main())
