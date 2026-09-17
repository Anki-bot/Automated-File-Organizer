# 📂 Automated File Organizer

> A portfolio-grade, zero-dependency CLI tool that instantly declutters any directory — safely, previewably, and beautifully.

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)
[![Dependencies](https://img.shields.io/badge/dependencies-zero-brightgreen)](#-under-the-hood)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](#)

---

## 🚀 What it Does (Features)

| Feature | Detail |
|---------|--------|
| **One-command declutter** | Scans a messy folder and sorts every file into typed categories (`Documents`, `Images`, `Videos`, `Audio`, `Archives`, `Executables`, `Code`, `Fonts`, `Miscellaneous`). |
| **Mandatory `--dry-run`** | Preview every move before it happens. No surprises. Colored `○ →` preview with rename warnings. |
| **Never overwrites** | Collision-safe auto-renaming: `report.pdf` → `report(1).pdf` → `report(2).pdf` … up to 10 000 variants. |
| **Cross-platform paths** | 100 % `pathlib` — works identically on macOS, Linux, and Windows. |
| **Graceful error handling** | Catches missing dirs, permission errors, and I/O failures; reports them and continues. |
| **Beautiful terminal UX** | ANSI colors (Green ✔ / Yellow ○ / Red ✘), grouped output, and a formatted summary table per run. |
| **Flexible destinations** | Organize in-place (`--source ./Downloads`) or into a separate tree (`--destination ./Organized`). |
| **Zero dependencies** | Only stdlib: `pathlib`, `shutil`, `argparse`, `logging`, `collections`. |

**Supported extensions (80+):**

- **Documents:** `.pdf` `.docx` `.doc` `.txt` `.rtf` `.odt` `.xls` `.xlsx` `.csv` `.ppt` `.pptx` `.md` `.epub`
- **Images:** `.jpg` `.jpeg` `.png` `.gif` `.bmp` `.tiff` `.webp` `.svg` `.ico` `.heic` `.psd` `.ai`
- **Videos:** `.mp4` `.mkv` `.avi` `.mov` `.wmv` `.flv` `.webm` `.m4v`
- **Audio:** `.mp3` `.wav` `.flac` `.aac` `.ogg` `.wma` `.m4a` `.opus`
- **Archives:** `.zip` `.rar` `.tar` `.gz` `.7z` `.bz2` `.xz` `.iso` `.dmg`
- **Executables:** `.exe` `.msi` `.bat` `.apk` `.deb` `.AppImage`
- **Code:** `.py` `.js` `.ts` `.java` `.c` `.cpp` `.go` `.rs` `.html` `.css` `.json` `.yaml` `.sql` … (25+)
- **Fonts:** `.ttf` `.otf` `.woff` `.woff2`
- **Miscellaneous:** everything else + files without extensions

---

## 🛠 Under the Hood (Technical Architecture)

```
File_Organizer/
├── main.py                 # CLI entry point — argparse, ANSI wiring, exit codes
├── organizer/
│   ├── __init__.py         # Public exports + version
│   ├── config.py           # EXTENSION_MAP dict, get_category() pure function
│   └── core.py             # FileOrganizer class (scan → map → move → report)
└── README.md
```

### Strict OOP Separation

| Layer | File | Responsibility |
|-------|------|----------------|
| **Configuration** | `organizer/config.py` | Single source of truth for `EXTENSION_MAP`, `CATEGORY_FOLDERS`, fallback `Miscellaneous`. Pure functions, no I/O. Easy to extend — add one line per extension. |
| **Core Logic** | `organizer/core.py` | `FileOrganizer` class encapsulates all state. Methods: `validate()` → `scan()` → `_resolve_collision()` → `organize()` → `_print_summary()`. Handles `PermissionError`, `OSError`, missing dirs. Uses `shutil.move()` + `pathlib` everywhere. |
| **CLI Interface** | `main.py` | `argparse` with `--source`/`--destination`/`--dry-run`/`--verbose`. Translates CLI args into a `FileOrganizer` instance. Returns proper exit codes (0 / 1 / 130). |

### Key Design Decisions

- **`pathlib` everywhere** — no `os.path.join`; all path ops are `Path` methods for cross-platform correctness.
- **Non-recursive scan** — only top-level loose files are moved; existing category folders and subdirectories are skipped (prevents infinite nesting).
- **Collision algorithm** — `_resolve_collision()` checks `Path.exists()` in a loop and appends `(n)` before the suffix. Deterministic, bounded (10k guard).
- **Grouped + sorted output** — files grouped by category, sorted alphabetically, printed with ANSI codes (`\033[92m` etc.) without any third-party color lib.
- **Logging** — stdlib `logging` with `verbose` toggle; errors also go to colored stderr.

---

## 💻 How to Use (Commands and Examples)

### Requirements

- Python **3.8+** (uses `from __future__ import annotations`, `Path`, `shutil`)
- No `pip install` needed.

### Quick Start

```bash
# Clone / open the project
cd File_Organizer

# See all options
python main.py --help
```

### Commands

```
usage: file-organizer [-h] [--source SOURCE] [--destination DESTINATION] [--dry-run] [--verbose] [--version]

options:
  -h, --help            show this help message and exit
  --source SOURCE, -s SOURCE
                        Source directory to scan (default: current directory '.')
  --destination DESTINATION, -d DESTINATION
                        Destination directory (default: same as --source)
  --dry-run             Preview file movements without moving anything
  --verbose, -v         Enable verbose debug logging
  --version             show program's version number and exit
```

### Examples

```bash
# 1. Preview what would happen in current directory (always try this first)
python main.py --dry-run

# 2. Preview a specific folder
python main.py --source ~/Downloads --dry-run

# 3. Organize current directory in-place
python main.py

# 4. Organize Downloads in-place (creates ~/Downloads/Documents, ~/Downloads/Images, …)
python main.py --source ~/Downloads

# 5. Organize into a separate destination tree
python main.py --source ~/Downloads --destination ~/Organized

# 6. Verbose mode for debugging
python main.py --source ./test_folder --dry-run --verbose

# 7. Short flags
python main.py -s ./messy -d ./clean --dry-run -v
```

### Sample Output

**Dry-run:**
```
🔍 DRY RUN — Preview only, no files will be moved
   Source      : /Users/you/Downloads
   Destination : /Users/you/Downloads
────────────────────────────────────────────────────────────
  ○ photo.jpg → Images/photo.jpg  [Images]
  ○ report.pdf → Documents/report.pdf  [Documents]
  ○ app.zip → Archives/app.zip  [Archives]
  ○ song.mp3 → Audio/song.mp3  [Audio]
  ○ mystery.xyz → Miscellaneous/mystery.xyz  [Miscellaneous]
────────────────────────────────────────────────────────────

 Dry-Run Summary (no files moved)
  Category        Files   Status
  ──────────── ───── ──────────
  ● Archives          1   preview
  ● Audio             1   preview
  ● Documents         1   preview
  ● Images            1   preview
  ● Miscellaneous     1   preview
  ──────────── ───── ──────────
  Total (preview)     5
────────────────────────────────────────────────────────────
  Tip: Run without --dry-run to apply these changes.
```

**Live run:**
```
📁 Organizing files
   Source      : /Users/you/Downloads
   Destination : /Users/you/Downloads
────────────────────────────────────────────────────────────
  ✔ photo.jpg → Images/photo.jpg  [moved]
  ✔ report.pdf → Documents/report(1).pdf  [renamed]
────────────────────────────────────────────────────────────

 Summary
  Category        Files   Status
  ──────────── ───── ──────────
  ● Documents         1   done
  ● Images            1   done
  ──────────── ───── ──────────
  Total moved         2

  Done! Files organized in /Users/you/Downloads
```

### Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Configuration or I/O error (message on stderr) |
| `130` | Interrupted by user (`Ctrl+C`) |

### Extending Categories

Edit `organizer/config.py` — add a line to `EXTENSION_MAP`:

```python
EXTENSION_MAP = {
    # ... existing
    ".blend": "Design",
    ".fig": "Design",
}
```

No other file needs to change; `CATEGORY_FOLDERS` is derived automatically.

---

## 🧪 Manual Test

```bash
# Create a sandbox
mkdir -p /tmp/demo && cd /tmp/demo
touch report.pdf photo.jpg song.mp3 archive.zip note.txt mystery.xyz
mkdir -p Documents && touch Documents/report.pdf  # to test auto-rename

# Preview
python /path/to/File_Organizer/main.py --source /tmp/demo --dry-run

# Execute
python /path/to/File_Organizer/main.py --source /tmp/demo

# Verify
ls -R /tmp/demo
```

---

## 📄 License

MIT — use freely in portfolio, interviews, and production.

---

<p align="center"><i>Built with strict OOP, zero dependencies, and a product mindset.</i></p>
