# Audion Disk Tools — user guide

**Contents**

- [The window](#the-window)
- [A panel](#a-panel)
- [Keys](#keys)
- [DIFF — Shift+F2](#diff--shiftf2)
- [Masks and the filter](#masks-and-the-filter)
- [Search](#search)
- [Saved panels](#saved-panels)
- [Copying and sync](#copying-and-sync)
- [Packing — Alt+F5](#packing--altf5)
- [Unpacking — Alt+F9](#unpacking--altf9)
- [SETTINGS](#settings)
- [COLORS](#colors)
- [Where things are kept](#where-things-are-kept)

## The window

At the top — everything that acts on both panels and the whole program: the sections (SETTINGS, MASKS, COLORS), in the middle — the program and its tools with their versions, on the right — the BLAKE3 box, MT with the thread count, the NO CACHE box, the eye (hidden and system files, Ctrl+H), font Aa, row density, language, theme, ABOUT.

Below — two panels. The active one has a sea-blue frame: it is the source, the other one the target. At the bottom — the status line with the progress bar and STOP, and the operation buttons under it.

A section opens in place of the panels and closes with the same button, the ✕ in its corner or Esc.

## A panel

- **Three rows above the list** that never trade places: drives, the panel controls, tabs. Only the tabs wrap; the window and the splitter stop before buttons could overlap.
- **Drives** — the first row: DRIVES opens the drive list, a click on a drive returns to the last folder opened on it, as in TC; the chevron at the end of the row lists every drive with its label and free space (Alt+F1 — the left panel, Alt+F2 — the right), the drive letter picks it at once.
- **Controls** — the second row: only what changes the view of this panel: up, reread, mark by mask, Detailed (a table) / Simple (the name column alone), on the right by the masks list - a new file in this panel's folder (Shift+F4 - in the active one), save this panel (a floppy disk) / both panels (two floppy disks); on the right masks and saved.
- **The column between the panels** — what is done with files, like the vertical bar of TC; it works on the active panel: ⇄ swap the panels (Ctrl+U) · copy, cut, paste through the Windows clipboard (Ctrl+C, Ctrl+X, Ctrl+V — to and from Explorer too) · names and paths to the clipboard (Ctrl+Shift+N, Ctrl+Shift+P) · go to the path in the clipboard · search (Ctrl+F) · unblock downloaded files. What an icon does is in its tooltip. The button icons come from the Lucide set. The splitter drags by the free space of the column.
- **Tabs**: `+` or Ctrl+T — a new one with the same folder; double click, Ctrl+W or the middle button — close; the active tab carries **⋮** — its menu: pin, rename, the folder name back, **drive name in the caption** ("U|Projects" — for folders of one name on two drives), **label** — the meaning of the tab ("video here", "documents here"): a dot of that file family's colour before the caption; not a filter, the folder shows everything as usual, **duplicate** or **move to the other panel**, **delete the tab**; right button — pin (a pinned tab stays on the left, does not close, and leaving its folder opens a new tab); Shift + right button — rename (the tab caption changes, not the folder); drag to change the order; an unpinned tab dropped among the pinned ones is pinned in that place, and a tab pinned by the right button joins the end of the pinned group. In SETTINGS · TABS: a tab width limit, a row that wraps or scrolls with the wheel, and the right button — pin at once or a pin / rename menu.
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
| * (numeric keypad) | invert the marks of the files (the icon - a circle of two halves); folders stay, as in TC |
| Alt+Shift+Enter | sizes of every folder in the list |
| Ctrl+R | reread the panel |
| Ctrl+U | swap the panels (the ⇄ button of a panel) |
| Alt+F1 / Alt+F2 | the drive list of the left / right panel (the chevron in the drive row); the drive letter goes straight there |
| Ctrl+H | hidden and system files: show or hide, for both panels (the eye at the top) |
| Shift+F2 | DIFF (the button below): a window of its own with the differences between the two panels' folders, down to the files; with marks in the panels - only the marked. An open window comes forward and compares again |
| Ctrl+F, Alt+F7 | search: the Search window — name, MASKS types, time, a regular expression; the found files as a flat list in the panel; Esc or Ctrl+B — back to the folder |
| F | narrow the list: only the names with this text stay; Esc — off, Enter or ↓ — to the list |
| Ctrl+C / Ctrl+X / Ctrl+V | copy / cut the marked rows to the Windows clipboard, paste from it into the active panel's folder — to and from Explorer too; pasting runs in the queue, like F5 and F6 |
| Shift+F4 | a new file in the active panel: a name and an extension (chips; a name with a dot keeps its own), straight into the editor ("OPEN IN EDITOR"); the page-with-plus icon above each panel does the same for that panel |
| Menu key, Shift+F10, right button | Explorer menu |
| F1 | the hot key memo; the user guide (MD, and PDF for those whose .md does not open) and the documentation folder are in the ABOUT menu |
| F2 | rename |
| F4 | open the file in the editor: Microsoft Edit from Tools\edit by default; micro (Tools\micro), Notepad or one of your own — SETTINGS · EDITOR AND TERMINAL |
| Ctrl+Enter | a terminal: on a folder — in it; .ps1, .cmd, .bat, .exe, .py are run and the window stays open; on another file — in its folder. The terminal is Windows Terminal from Tools\terminal (its config is config\terminal, laid over after every update), else the system one |
| F5 / F6 | copy / move to the other panel |
| F7 | new folder |
| F8 | delete what is marked to the Recycle Bin, with a progress bar and STOP; what does not fit into the bin is left alone |
| Del | the same as F8, plus the Windows progress window |
| Shift+Del | delete what is marked past the Recycle Bin, with a progress bar and STOP |
| F11 / F12 | COPY / MIRROR |
| Alt+F5 / Alt+F9 | pack / unpack |
| Ctrl+Shift+N / Ctrl+Shift+P, the "names" / "paths" icons in the column between the panels | names or full paths of the marked rows to the clipboard, one per line |
| the "go to path" icon under "paths"; "Open the path in the clipboard" in the tab menu (⋮) | the path in the clipboard opens in the active panel (from the menu - in that tab): a folder as it is, a file path as its folder with the cursor on the file (a mask or the F line hiding that file is taken off, and that is said); quotes, spaces around it, `file:///` and `%VARIABLES%` do no harm |
| Esc | during an operation — STOP; otherwise remove the filter or close the section |

Rows can also be marked with a frame: press on a row and move up or down.

**Drag and drop.** A row pulled sideways can be carried with the mouse to Explorer, the desktop, a messenger or the other panel: a marked row takes all the marked ones, an unmarked row goes alone. The files are copied and stay here. The other way: files from Explorer or the other panel dropped onto the list are copied into this panel's folder, through the same queue as Ctrl+V - after a question, as with F5: from where, to where, what, and which names the folder already has. In Explorer, Explorer copies by itself and asks only about names that meet. With Shift they are moved: the program moves them itself, after the copy is checked, so Explorer deletes nothing on its side.

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
- **How a mask is read** — one rule everywhere (MASKS, mark by mask, search): a word is a part of the name (`example` → `*example*`, it finds `example` without an extension too), a leading dot is an extension (`.png` → `*.png`), a name with a dot stays as is (`readme.md`), with `*` and `?` — a mask as written; `*.` — files without an extension.
- **BY TIME** in the same list: changed within an hour, a day (today and yesterday), a week — exactly what is painted "not older than 1 hour / day / week". It is a filter, as a mask group: copying and moving from such a panel take only these files (robocopy `/MAXAGE`, rclone `--max-age`), and so do the count before F11 and the BLAKE3 check. MIRROR and BISYNC do not run under a filter.
- **Row colours** take their masks from MASKS: each family (documents, images, archives, video, audio, apps, temporary) is painted with its colour of the theme. The themes are `config\colors\themes.json` (dark and light, carried over from the owner's TC themes): they hold only colours and the order of the rules, what to paint is up to the MASKS family. "Development and config" is not painted. Scripts that start a process (`bat`, `cmd`, `ps1`, `vbs`) are executables; code that only lies there (`js`, `py`, `cpp`, `psm1`) is development. The mask `*.` is files without an extension: `id_rsa`, `credentials`, `README`, `.env`, `.bashrc` (keys, passwords, configs, Linux files).
- **MASKS section** — your own sets: masks as text and including or excluding extensions by groups. Pinned sets come first in the panel list.

MIRROR and BISYNC do not run under a filter: a mirror is a full copy, masks are not its scenario.

## Search

**Ctrl+F**, **Alt+F7** or the **CTRL+F SEARCH** button at the bottom (next to DIFF) open the Search window — a window of its own, as in Total Commander: it has its own taskbar button and the program stays free while it searches. Already open, it comes to the front and takes the folder of the active panel. The magnifier in the middle column is the quick filter **F** over the list in view.

- **Where** — the folder, with all its subfolders: the folder of the active panel at first (on the list of drives — the other panel's, else the one searched last). Until a path is typed by hand, Where follows the panel: back in the search window, it holds the folder the active panel is in now. **PANEL FOLDER** takes it again after a typed path.
- **Search** — one line for everything: first the badges of the pressed MASKS groups and families — like their buttons, in their colours (× or Backspace in an empty field take one off), then your own keys, comma separated; the line grows only as it fills:
  - an extension (`.dwg`, `*.max`, `*.` — no extension) is added to the groups: any of the types fits;
  - a word or a mask is the name: a word is found anywhere in the name (`report`), a mask is as in MASKS (`2026-*`); any of them fits;
  - `/…/` is a .NET regular expression on the name, case-insensitive (`/^IMG_\d{4}/`); a mistake in it shows at once and FIND waits for the fix.

  Under the field, a summary of what will be found; **Enter** — find.
- **Types** — **MASKS GROUPS ▾**: the families in lines with a hairline between them; the family button on the left, its groups on the right. A pressed group becomes a badge in the field; the family button puts the whole family in as one badge, and its groups go dim — they are in it already. Nothing pressed and no extensions — every type. While the query is being made the groups are open; once a search starts they fold and the table takes the whole height; the same button opens them again.
- **Changed** — any time, within an hour, a day, a week: the same as the row colours.

**FIND** (Enter in the field or in the Where line) walks the tree in the background: the table fills as it goes, the progress line tells how many were found, how many folders and files were looked at and where the search is now. **STOP** or **Esc** end it at once, even in the middle of a big folder; what was found stays. The search stops by itself at 500,000 finds — the progress line says "limit: … this is not the whole answer": the rest of the tree was not looked at, narrow the query. The table sorts by File, Size and Changed; the names are in the panel's colours.

With what was found:

- **TO PANEL** — the found files as a flat list in the active panel (names with their subfolders): exactly the rows of the table, after STOP too — the tree is not read again. A refresh of the panel (Ctrl+R, the end of an operation, changes on disk) updates the size and time of these files and drops the gone ones, but adds none: a new search is FIND only. From there everything goes to the other panel: **F5** / **F6** — copy or move (the files land in their subfolders), **Alt+F5** — pack; **F8** — delete right here. Folders from the results are not copied, COPY, MIRROR and BISYNC do not run from them. **Esc** or **Ctrl+B** in the panel — back to the folder.
- **GO TO FILE**, a double click or **Enter** in the table — the file's folder in the active panel, the cursor on it, the main window in front.
- **CLEAR** — the table, the field and the groups empty, the folder stays; the query is made anew.

The buttons are one line at the bottom: CLEAR, CLOSE, TO PANEL, GO TO FILE on the left, FIND and STOP on the right.

The window keeps its place and size; it closes with the program.

## Saved panels

The **"save the panel"** icon (a floppy disk) remembers the panel with all its tabs: folders, marks, filters, pins. **"Save both"** (two floppy disks) — both panels the same way. A small window opens first: a name (offered, can be changed) and where to — **TO THE LIST** (Enter) or **TO A FILE…** (.json anywhere; the window opens in Downloads). The name can be picked from a drop-down of the saved ones: then the first button turns into **OVERWRITE** (amber) — that record takes the panels as they are now, its name and star stay. Choosing a record in the masks and saved list brings everything back; a tab whose folder is gone is skipped and named in the status line. Before that, what both panels showed saves itself as **Latest** — one record, written over every time; Latest renamed becomes an ordinary record and is no longer written over. The star pins a line at the top of the list, **✎** of a saved panel renames it, writes it to a file or **DELETES** it from the list (folders and .json files on the disks are not touched). Long names in the list end in an ellipsis, the full name is in the tooltip. To the right of the two floppy disks is **IMPORT**: a .json file written by **TO A FILE…** or SETTINGS · EXPORT comes back into the panels. A menu of four lines, a pair of icons before each (two columns - both panels, a square - this one; a plus - added to the tabs, the round arrow - in their place): **Add to both panels** (the file's left panel to the left panel's tabs, its right to the right), **Replace both panels**, **Add to this panel** and **Replace this panel** (every tab of the file into the panel pressed). A file of one panel goes into this panel under "both". Before an import the panels as they were save themselves into the **Latest** record.

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

**MT** — a box and the thread count beside it (1 to 128; the arrows or the mouse wheel over the number). robocopy copies in that many threads (the `/MT` switch), rclone moves that many files at once (`--transfers`, BISYNC too). Wins on thousands of small files, on SSDs and over the network. Big files between hard disks copy faster in one thread: the heads do not jump between files. Unchecked — one thread. On by default, 8 threads.

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

Each theme has its own colours: window and frame backgrounds, the list background (top and bottom of the gradient), column headers, text, cursor, the active panel frame, marks, accents, the progress bar — and the file type colours from the rules of the theme. A changed colour shows its code highlighted, ↺ brings the original back. **Grain** 0–3 — film texture over the list background; it also smooths the steps of the gradient.

The colour window: a saturation-value square, a hue strip, fields R, G, B and `#hex` — drag or type, everything follows.

## Where things are kept

- `config\settings.json` — the look and the choices: language, theme, fonts, density, colours and grain, engine, BLAKE3, MT and the thread count, NO CACHE, packing choices. Survives the cleanup.
- `config\history\session.json` — the tabs of both panels, the window, the MASKS draft, BISYNC pairs;
- `config\history\library.json` — your mask sets, saved panels, pinned items;
- `config\history\mask_cache.json`, `profile_extension_pins.json` — history of masks and extension sets;
- `config\history\bisync\` — the state of BISYNC syncs.
- `._runtime\logs\` — the operations log by day; `._runtime\updates.json` — GitHub's last answer about versions.

The language comes from Windows on the first start; once chosen with RU/EN/DE it is kept.

`config\history` and `._runtime` go in the cleanup before a release; they can also be deleted by hand at any time — the program starts with a clean history, the look stays.
