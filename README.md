# Audion Disk Tools

<!-- audion:release -->
<p align="center">
  <a href="https://audion.dev/downloads/disk-tools"><img alt="Windows" src="https://img.shields.io/badge/Windows-10%20%7C%2011-0b6db8?style=flat-square&logo=windows&logoColor=white"></a>
  <a href="https://github.com/Tensionix/disk-tools/releases/latest"><img alt="Release" src="https://img.shields.io/github/v/release/Tensionix/disk-tools?style=flat-square&label=release&color=e08a63"></a>
  <a href="https://github.com/Tensionix/disk-tools/releases"><img alt="Downloads" src="https://img.shields.io/github/downloads/Tensionix/disk-tools/total?style=flat-square&label=downloads&color=5fd08a"></a>
  <a href="https://github.com/Tensionix/disk-tools/blob/main/LICENSE"><img alt="License" src="https://img.shields.io/github/license/Tensionix/disk-tools?style=flat-square&color=5fd08a&logo=apache&logoColor=white&cacheSeconds=3600"></a>
</p>

**Version 5.17.0** · 2026-09-26 · 98.9 MB

- [Direct download](https://dl.audion.dev/disk-tools/5.17.0/Audion_Disk_Tools_v5.17.0_Full.zip) — unmetered, no rate limits
- [Project page](https://audion.dev/downloads/disk-tools) — every version and how to install
- [GitHub release](https://github.com/Tensionix/disk-tools/releases/tag/v5.17.0)

<p align="center"><img src="docs/screenshot.png" alt="The program window" width="560"></p>

`SHA-256: ac66269d96a7d974aae73a68119d7af44eb6a92f7423e82629cba0e04c5ec324`

---

An **Audion** tool, published by [Tensionix](https://github.com/Tensionix).
<!-- /audion:release -->


[Русский](Docs/README_RU.md)

A two-panel file manager for Windows: tabs and drives as in Total Commander, mask filters, saved panels, robocopy copying with BLAKE3 verification, sync, packing and unpacking — in one window, with nothing to install.

Built on .NET 10 and Avalonia; everything it needs lives in the project folder: the program with its own runtime, the PeaZip archiver, rclone, the editors Microsoft Edit and micro and a portable Windows Terminal (all MIT).

## Start

`Start.exe` in the root of the folder. Nothing to install: .NET, PeaZip and rclone travel with the program. The folder can be moved anywhere — the settings and the history of work live inside it, in `config\`.

## What it does

- **Two panels** with tabs, drives, breadcrumbs and row colours by the rules of a Total Commander theme (dark and light).
- **Mask filter** per panel: shows only the files you need together with their folder structure; copying from a filtered panel takes only them.
- **Saved panels**: the folder and the marks of one or both panels — there and back in one click.
- **Copy and move** (F5, F6) through robocopy: NTFS streams, creation and modification times, attributes, folders in 8 threads. Or rclone — switched in SETTINGS.
- **COPY, MIRROR, BISYNC** (F11, F12): add what is new, make an exact copy (it counts the deletions first), two-way sync.
- **BLAKE3 check**: after copying, source and copy are read again, the copy from disk past the cache; a move deletes the source only after a match.
- **Packing** (ALT+F5): ZIP, 7Z, SFX, TAR, TAR.GZ, TAR.ZSTD; compression, AES-256 encryption, name prefixes and suffixes with a number, layout, archive test after creation.
- **Unpacking** (ALT+F9) in batches: into the other panel or here, "smart" or each archive into its own folder; volumes and TAR inside GZ/ZSTD/XZ open on their own.
- **Explorer menu** on the right button, Recycle Bin on F8, past it — SHIFT+DEL.
- **Three interface languages**: Russian, English, German — on the fly.
- **COLORS**: your own colours for the window, panels and file types, per theme; the list background is a gradient with film grain.
- **Updates**: in the middle of the top line — the program, PeaZip and rclone with their versions and dots: green is the latest, light orange means GitHub has a newer one.

## Project folders

| Folder | Contents |
| --- | --- |
| `Start.exe` | starts the program |
| `App\` | the built program with its .NET runtime and data: translations, TC colours, mask groups |
| `Tools\` | PeaZip (only its archiving engines `7z` and `zstd` with their licences) and rclone |
| `config\settings.json` | the look and the choices: language, theme, fonts, colours, engine; survive the cleanup |
| `config\history\` | the history of work: tabs, saved panels, own masks, BISYNC pairs; removed by the cleanup |
| `._runtime\` | throwaway: operations log, GitHub's answer about versions, build stages |
| `Source\` | the program's source code |
| `Engine\` | build scripts: program, launcher, tools, verification |
| `Docs\` | documentation |

## Building and release

The program in `App\` is already built and ships as it is. It needs rebuilding only after a change in the code — that takes the .NET 10 SDK and is done on purpose.

`builder_main.cmd`:

- `[01] BUILD APP` — the checks of `[03]` first, then a rebuild of the program into `App\` (needs the .NET 10 SDK); when a check fails, `App\` is left as it was;
- `[02] START LAUNCHER` — rebuild `Start.exe` with the program icon;
- `[03] CHECKS` — scenarios in which the program once lost or damaged data (audits of 24.09.2026): verified BLAKE3 moves, STOP, masks on both engines, overlapping paths, junctions, archives, settings, the installer. They run on throwaway files in the Windows temp folder with the real robocopy, rclone and PeaZip; the Recycle Bin is not used. The report goes to `._runtime\tests\`;
- `[05] PEAZIP`, `[07] RCLONE` — force a reinstall of a tool;
- `[06] TOOLS IF NEWER` — check PeaZip and rclone against GitHub and download only what is out of date or missing;
- `[70] CLEAN CACHE` — remove intermediate build files;
- `[71] VERIFY` — check that everything is in place and the versions agree; warns when `App\` was built before the latest change in `Source\`.

Before a release, `[06]`, `[70]`, `[71]` are enough.

`cleanup_project.cmd` removes the history of work (`config\history`), the throwaway files (`._runtime`) and build leftovers (`Source\bin`, `Source\obj`, `Engine\Tests\bin`, `Engine\Tests\obj`, `tmp`); the program, the tools and `config\settings.json` stay.

## Author

Tensionix · [tensionix.com](https://tensionix.com) · [audion.dev](https://audion.dev)
