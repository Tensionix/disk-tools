# Audion Disk Tools — user guide

**Contents**

- [The window](#the-window)
- [A panel](#a-panel)
- [Keys](#keys)
- [Masks and the filter](#masks-and-the-filter)
- [Saved panels](#saved-panels)
- [Copying and sync](#copying-and-sync)
- [Packing — Alt+F5](#packing--altf5)
- [Unpacking — Alt+F9](#unpacking--altf9)
- [SETTINGS](#settings)
- [COLORS](#colors)
- [Where things are kept](#where-things-are-kept)

## The window

At the top — the sections (SETTINGS, MASKS, COLORS), in the middle — the program and its tools with their versions, on the right — the BLAKE3 and NO CACHE boxes, the view: font Aa, row density, language, theme, ABOUT.

Below — two panels. The active one has a sea-blue frame: it is the source, the other one the target. At the bottom — the status line with the progress bar and STOP, and the operation buttons under it.

A section opens in place of the panels and closes with the same button, the ✕ in its corner or Esc.

## A panel

- **Three rows above the list** that never trade places: drives, the panel controls, tabs. Only the tabs wrap; the window and the splitter stop before buttons could overlap.
- **Drives** — the first row: DRIVES opens the drive list, a click on a drive returns to the last folder opened on it, as in TC.
- **Controls** — the second row: up, reread, mark by mask, Detailed / Simple (the name column alone), ⇄ swap the panels (Ctrl+U), Unblock (takes the "downloaded from the internet" mark off the selected files), NAMES and PATHS (to the clipboard); on the right masks and saved, + PANEL, + BOTH.
- **Tabs**: `+` or Ctrl+T — a new one with the same folder; double click, Ctrl+W or the middle button — close; right button — pin (a pinned tab stays on the left, does not close, and leaving its folder opens a new tab); drag to change the order. In SETTINGS · TABS: a tab width limit, a row that wraps or scrolls with the wheel, and the right button — pin at once or a pin / rename menu (the tab caption changes, not the folder).
- **Breadcrumbs** of the path — a click on any part goes there.
- **Columns** NAME, TYPE, DATE, TIME, SIZE; a click on a header sorts, folders always on top.
- **Sizes** short (KB, MB, GB) or exact in bytes — SETTINGS · SIZES. Sizes of marked folders are counted in the background.
- **Status line** of the panel: marked of total, files, folders, free space; sizes in a warm colour.

## Keys

| Key | Action |
| --- | --- |
| Tab | other panel |
| Ctrl+Tab, Ctrl+Shift+Tab | next and previous tab |
| Enter, double click | open a folder or a file; on ".." — up |
| Backspace | up, the cursor lands on the folder you left |
| Space, Insert | mark and step down; a folder gets its size counted |
| Shift+Space | the exact size of the row in bytes — in the panel status line, until the next action |
| Home / ← , End / → | to the start, to the end of the list |
| Ctrl+A | mark all or clear all |
| Ctrl+R | reread the panel |
| Ctrl+U | swap the panels (the ⇄ button of a panel) |
| Menu key, Shift+F10, right button | Explorer menu |
| F1 | the hot key memo; the user guide and the documentation folder are in the ABOUT menu |
| F2 | rename |
| F4 | open the file in the editor: Microsoft Edit from Tools\edit by default; micro (Tools\micro), Notepad or one of your own — SETTINGS · EDITOR AND TERMINAL |
| Ctrl+Enter | a terminal: on a folder — in it; .ps1, .cmd, .bat, .exe, .py are run and the window stays open; on another file — in its folder. The terminal is Windows Terminal from Tools\terminal (its config is config\terminal, laid over after every update), else the system one |
| F5 / F6 | copy / move to the other panel |
| F7 | new folder |
| F8 | delete to the Recycle Bin |
| Shift+Del | delete past the Recycle Bin |
| F11 / F12 | COPY / MIRROR |
| Alt+F5 / Alt+F9 | pack / unpack |
| Ctrl+Shift+N / Ctrl+Shift+P, the NAMES / PATHS buttons of the panel | names or full paths of the marked rows to the clipboard, one per line |
| Esc | during an operation — STOP; otherwise remove the filter or close the section |

Rows can also be marked with a frame: press on an empty spot and drag.

## Masks and the filter

- **✱** above a panel — mark rows by mask: `*.zip 2026-* *aud*`.
- **The "masks and saved" list** — a mask group from the list turns the panel into a filter: only matching files and the folders that hold them are shown. Copying from such a panel takes only them. Remove the filter with Esc or "× FILTER" at the bottom.
- **MASKS section** — your own sets: masks as text and including or excluding extensions by groups. Pinned sets come first in the panel list.

MIRROR and BISYNC do not run under a filter: a mirror is a full copy, masks are not its scenario.

## Saved panels

**+ PANEL** remembers the folder and the marks of this panel, **+ BOTH** — of both. Choosing it in the list brings everything back. The star pins a line at the top of the list.

## Copying and sync

- **F5 / F6** — the marked items (or the row under the cursor) to the other panel. Matching names are updated.
- **F11 COPY** — add to the target what is missing or older there; deletes nothing. Counts what will go before it starts.
- **F12 MIRROR** — the target becomes an exact copy: extras are deleted. Counts the deletions first; over two hundred — it warns.
- **BISYNC** — two-way sync through rclone; whole folder only. The first run of a pair takes the source as right.

The scope is the marked items; nothing marked — the whole open folder. Operations queue one at a time; STOP or Esc stops the current one and clears the queue. The log is in `._runtime\logs`.

**Engine** — SETTINGS · ENGINE: robocopy (NTFS streams, times, attributes, 8 threads for folders) or rclone.

**BLAKE3** — the box at the top. After copying, source and copy are read again and compared; both source and copy are read from disk past the Windows cache. A verified move deletes a source file only after a match. For F11 and F12 only the files that moved are checked.

**NO CACHE** — the box beside it. robocopy writes past the Windows file cache (the `/J` switch): data does not pile up in RAM by gigabytes, and the real speed of a slow drive shows at once, without a rush and a drop. Often useful for big files; the speed depends on the drive and the data, and on thousands of small files it can be lower. The device keeps its own cache — safe removal is still needed. The robocopy engine only.

## Packing — Alt+F5

The marked items are packed into the other panel (a panel on the drive list means next to the source).

- **Formats**: ZIP, 7Z, SFX, TAR, TAR.GZ, TAR.ZSTD — several at once. TAR.LZ4 is off while there is no `lz4.exe`.
- **Compression** 0–9; **archives** — each separately or all in one; **layout** — into one folder or each into its own.
- **Encryption** AES-256 — 7Z and SFX only; "with names" locks the file list too. ZIP is not encrypted: 7-Zip would use the old ZipCrypto.
- **Name**: prefix and suffix; `N` as a separate word becomes the object number.
- **SFX**: where it offers to unpack (a variable and a path with `{name}`), a wrapper without compression.
- **After**: test the archive (`7z t`, zstd's own test for zstd); delete sources — to the Recycle Bin and only once all their archives are made and tested.

## Unpacking — Alt+F9

Archives are taken from the marked items (the first volume of a split set).

- **Where**: into the other panel or here, next to the archive.
- **How**: *smart* — an archive with one folder or one file inside lands as it is, loose files get a folder named after the archive (and so does an archive whose name is taken); *each into its own folder*; *all in one place*.
- **Conflicts**: rename, replace, skip. **Password** — for locked archives. **Delete archives** — to the Recycle Bin after a good unpack, with all volumes.

TAR inside GZ, ZSTD, XZ, BZ2 opens straight through. Integrity is checked while unpacking: 7-Zip compares every file's checksum.

## SETTINGS

- **Sizes** — short or in bytes.
- **Engine** — robocopy or rclone.
- **Archiver** — where 7-Zip, zstd and lz4 are.
- **Tools** — the program, PeaZip and rclone with versions and dots; UPDATE downloads the latest version of a tool into `Tools\`, for the program it opens the release page. CHECK NOW asks GitHub without waiting six hours.
- **Program font and panel font** — family and the size of the middle Aa; the smaller and larger steps follow from it.

## COLORS

Each theme has its own colours: window and frame backgrounds, the list background (top and bottom of the gradient), column headers, text, cursor, the active panel frame, marks, accents, the progress bar — and the file type colours from the TC rules. A changed colour shows its code highlighted, ↺ brings the original back. **Grain** 0–3 — film texture over the list background; it also smooths the steps of the gradient.

The colour window: a saturation-value square, a hue strip, fields R, G, B and `#hex` — drag or type, everything follows.

## Where things are kept

- `config\settings.json` — the look and the choices: language, theme, fonts, density, colours and grain, engine, BLAKE3, NO CACHE, packing choices. Survives the cleanup.
- `config\history\session.json` — the tabs of both panels, the window, the MASKS draft, BISYNC pairs;
- `config\history\library.json` — your mask sets, saved panels, pinned items;
- `config\history\mask_cache.json`, `profile_extension_pins.json` — history of masks and extension sets;
- `config\history\bisync\` — the state of BISYNC syncs.
- `._runtime\logs\` — the operations log by day; `._runtime\updates.json` — GitHub's last answer about versions.

The language comes from Windows on the first start; once chosen with RU/EN/DE it is kept.

`config\history` and `._runtime` go in the cleanup before a release; they can also be deleted by hand at any time — the program starts with a clean history, the look stays.
