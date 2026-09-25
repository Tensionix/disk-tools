# Audion Disk Tools — user guide

**Contents**

- [The window](#the-window)
- [A panel](#a-panel)
- [Keys](#keys)
- [DIFF — Shift+F2](#diff--shiftf2)
- [Masks and the filter](#masks-and-the-filter)
- [Saved panels](#saved-panels)
- [Copying and sync](#copying-and-sync)
- [Packing — Alt+F5](#packing--altf5)
- [Unpacking — Alt+F9](#unpacking--altf9)
- [SETTINGS](#settings)
- [COLORS](#colors)
- [Where things are kept](#where-things-are-kept)

## The window

At the top — everything that acts on both panels and the whole program: the sections (SETTINGS, MASKS, COLORS), in the middle — the program and its tools with their versions, on the right — the BLAKE3 and NO CACHE boxes, the eye (hidden and system files, Ctrl+H), font Aa, row density, language, theme, ABOUT.

Below — two panels. The active one has a sea-blue frame: it is the source, the other one the target. At the bottom — the status line with the progress bar and STOP, and the operation buttons under it.

A section opens in place of the panels and closes with the same button, the ✕ in its corner or Esc.

## A panel

- **Three rows above the list** that never trade places: drives, the panel controls, tabs. Only the tabs wrap; the window and the splitter stop before buttons could overlap.
- **Drives** — the first row: DRIVES opens the drive list, a click on a drive returns to the last folder opened on it, as in TC; the chevron at the end of the row lists every drive with its label and free space (Alt+F1 — the left panel, Alt+F2 — the right), the drive letter picks it at once.
- **Controls** — the second row: only what changes the view of this panel: up, reread, mark by mask, Detailed (a table) / Simple (the name column alone), on the right by the masks list - a new file in this panel's folder (Shift+F4 - in the active one), save this panel (a plus) / both panels (two pluses); on the right masks and saved.
- **The column between the panels** — what is done with files, like the vertical bar of TC; it works on the active panel: ⇄ swap the panels (Ctrl+U) · copy, cut, paste through the Windows clipboard (Ctrl+C, Ctrl+X, Ctrl+V — to and from Explorer too) · names and paths to the clipboard (Ctrl+Shift+N, Ctrl+Shift+P) · find in the panel (Ctrl+F) · unblock downloaded files. What an icon does is in its tooltip. The splitter drags by the free space of the column.
- **Tabs**: `+` or Ctrl+T — a new one with the same folder; double click, Ctrl+W or the middle button — close; right button — pin (a pinned tab stays on the left, does not close, and leaving its folder opens a new tab); Shift + right button — rename (the tab caption changes, not the folder); drag to change the order. In SETTINGS · TABS: a tab width limit, a row that wraps or scrolls with the wheel, and the right button — pin at once or a pin / rename menu.
- **`\` over the icon column**, left of "NAME" — to the root of this tab's drive.
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
| Alt+← / Alt+→ | back and forward through the folders of this tab (the arrows of the control row, the mouse side buttons) |
| Ctrl+B | flat view: every file of every subfolder in one list, with its path from this folder; with a mask filter - "every .pdf of this tree"; F5 and F6 put the files into the target with their subfolders. COPY, MIRROR, BISYNC, packing and comparing work from the usual view. Leaving the folder turns the view off |
| Space, Insert | mark and step down; a folder gets its size counted |
| Shift+Space | the exact size of the row in bytes — in the panel status line, until the next action |
| Home / ← , End / → | to the start, to the end of the list |
| Ctrl+A | mark all or clear all |
| * (numeric keypad) | invert the marks of the files (the icon - a square filled along its diagonal); folders stay, as in TC |
| Alt+Shift+Enter | sizes of every folder in the list |
| Ctrl+R | reread the panel |
| Ctrl+U | swap the panels (the ⇄ button of a panel) |
| Alt+F1 / Alt+F2 | the drive list of the left / right panel (the chevron in the drive row); the drive letter goes straight there |
| Ctrl+H | hidden and system files: show or hide, for both panels (the eye at the top) |
| Shift+F2 | DIFF (the button below): a window of its own with the differences between the two panels' folders, down to the files; with marks in the panels - only the marked. An open window comes forward and compares again |
| Ctrl+F | find in the panel: only the names with this text stay in the list; Esc — off, Enter or ↓ — to the list |
| Ctrl+C / Ctrl+X / Ctrl+V | copy / cut the marked rows to the Windows clipboard, paste from it into the active panel's folder — to and from Explorer too; pasting runs in the queue, like F5 and F6 |
| Shift+F4 | a new file in the active panel: a name and an extension (chips; a name with a dot keeps its own), straight into the editor ("OPEN IN EDITOR"); the page-with-plus icon above each panel does the same for that panel |
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
| Ctrl+Shift+N / Ctrl+Shift+P, the "names" / "paths" icons in the column between the panels | names or full paths of the marked rows to the clipboard, one per line |
| Esc | during an operation — STOP; otherwise remove the filter or close the section |

Rows can also be marked with a frame: press on an empty spot and drag.

## DIFF — Shift+F2

A window of its own beside the main one: the panels stay in view and at work - delete, look, delete, look. The window watches both folders: after an operation of the program or a change from outside it compares again in the background, keeping the filter, the order, the chosen lines and what BLAKE3 has already read. Its place and size are kept; Esc stops a comparison, and with nothing running closes the window. It compares the two panels' folders file by file, through every common subfolder. A difference deep inside shows by its own path (`proj\src\config.json`), not as a marked folder to search in. A folder missing on the other side is one line with its file count and size.

- **The table:** object · left (date, size) · right · difference. The arrow of a side shows the object in that panel; a double click on the line does the same. The headers sort: the object by its path, the sides by date, the difference by its kind. The colour of the difference: blue - leans left, turquoise - leans right, amber - other bytes (BLAKE3 ✗), orange - an error, green - BLAKE3 ✓.
- **Filters:** ALL DIFFERENCES (opens first) · ONLY LEFT · ONLY RIGHT · CHANGED · ERRORS · MATCHED. The status line ends with "the other N matched"; MATCHED lists them, for whoever looks for proof that a copy is whole. A matched pair matches in everything: a pair with other content by BLAKE3 is a difference, not a match.
- **CHECK BLAKE3** — BLAKE3 for the chosen lines, and with nothing chosen for every pair of files, the ones equal by date and size too: the same date and size prove nothing. In the difference column: BLAKE3 ✓ - the same bytes, ✗ - other bytes (such a pair joins the changed), ? - not read; the summary says how many matched with BLAKE3 ✓.
- **ERRORS** — what could not be compared: a folder that cannot be read, a link to another folder, a hash not computed. It never counts as matched.
- **MARK IN PANELS** — the chosen differences (or all shown) become marks, each on its side: on the left what the right lacks or has older, on the right the other way; other content - on both; from MATCHED - on both sides. When differences lie in subfolders, the panel switches to the flat view (Ctrl+B) and marks the files themselves; the flat view holds no empty folders - the window lists them and asks whether to carry the rest. The panel's mask filter and search are turned off, so the marks are in view and reach F5. Then F5 or F11 as usual: DIFF copies nothing itself.
- Marks in the panels before Shift+F2 narrow the comparison to those names.

## Masks and the filter

- **✱** above a panel — mark rows by mask: `*.zip 2026-* *aud*`.
- **The "masks and saved" list** — a mask group from the list turns the panel into a filter: only matching files and the folders that hold them are shown. Copying from such a panel takes only them. Remove the filter with Esc or "× FILTER" at the bottom.
- **MASKS section** — your own sets: masks as text and including or excluding extensions by groups. Pinned sets come first in the panel list.

MIRROR and BISYNC do not run under a filter: a mirror is a full copy, masks are not its scenario.

## Saved panels

The **"save the panel"** icon (a thick plus) remembers the panel with all its tabs: folders, marks, filters, pins. **"Save both"** (two overlapping pluses) — both panels the same way. A small window opens first: a name (offered, can be changed) and where to — **TO THE LIST** (Enter) or **TO A FILE…** (.json anywhere). Choosing it in the list brings everything back; a tab whose folder is gone is skipped and named in the status line. The star pins a line at the top of the list, **✎** of a saved panel renames it, writes it to a file or removes it from the list.

**SETTINGS · MASKS AND SAVED**: **EXPORT…** — all of your own in one file (mask sets, saved panels, pins, typed masks and extension sets); **IMPORT…** — add from such a file or from a panel saved to a file. Import only adds: what is here stays as it is.

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
- **Encryption** AES-256 — 7Z and SFX only; "with names" locks the file list too. ZIP is not encrypted: only the old ZipCrypto would be left for it.
- **Name**: prefix and suffix; `N` as a separate word becomes the object number.
- **SFX**: where it offers to unpack (a variable and a path with `{name}`), a wrapper without compression.
- **After**: test the archive (`7z t`, zstd's own test for zstd); delete sources — to the Recycle Bin and only once all their archives are made and tested.

## Unpacking — Alt+F9

Archives are taken from the marked items (the first volume of a split set).

- **Where**: into the other panel or here, next to the archive.
- **How**: *smart* — an archive with one folder or one file inside lands as it is, loose files get a folder named after the archive (and so does an archive whose name is taken); *each into its own folder*; *all in one place*.
- **Conflicts**: rename, replace, skip. **Password** — for locked archives. **Delete archives** — to the Recycle Bin after a good unpack, with all volumes.

TAR inside GZ, ZSTD, XZ, BZ2 opens straight through. Integrity is checked while unpacking: PeaZip compares every file's checksum.

## SETTINGS

- **Sizes** — short or in bytes.
- **Engine** — robocopy or rclone.
- **Copy times** — as the source (the default, as in TC) or the time of copying, as cp without -p on Linux. Attributes are carried either way. It is for F5 and Ctrl+V; a move (F6), COPY, MIRROR and BISYNC always keep the times.
- **Archiver** — where the PeaZip engines are: `7z`, `zstd`, `lz4`.
- **Tools** — the program, PeaZip and rclone with versions and dots; UPDATE downloads the latest version of a tool into `Tools\`, for the program it opens the release page. CHECK NOW asks GitHub without waiting six hours.
- **Program font and panel font** — JetBrains Mono by default: it ships inside the program, like Inter, with Cyrillic. Family and the size of the middle Aa; the smaller and larger steps follow from it. **FROM THE NET…** — a family from Google Fonts or Nerd Fonts: a list with search; for Nerd Fonts the archive size shows before fetching. The files go to `config\history\fonts` and are read by the program itself, nothing is installed into Windows; fetched families join the row of both blocks. Any Windows font by name can no longer be picked: the window fell on fonts the program cannot draw.

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
