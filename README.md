# Automated File Organizer (CLI)

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Zero External Dependencies](https://img.shields.io/badge/dependencies-zero-brightgreen.svg)](#under-the-hood)

A robust, dependency-free command-line interface (CLI) utility engineered to categorize, sort, and organize unstructured directories at scale. Built with strict Object-Oriented principles, defensive file I/O operations, and user safety as core requirements.

---

## 🚀 What It Does

Most file sorters fail in production because they overwrite duplicates or run destructively without warning. This tool bridges everyday file management with system-level safety:

- **Non-Destructive Dry Runs (`--dry-run`):** Preview directory mutations and category distribution before moving a single byte.
- **Duplicate Collision Handling:** Automatically resolves naming conflicts with numeric increments (e.g., `report.pdf` → `report(1).pdf`)—files are never overwritten.
- **Dynamic Category Mapping:** Maps files into clean functional buckets (Documents, Images, Audio, Video, Archives, Code) with fallback handling for unknown extensions.
- **Rich Terminal Feedback:** Color-coded status updates and an execution summary table using native ANSI escape codes.

---

## 🖥 Terminal Experience

$ python main.py --source ./Downloads --dry-run

🔍 DRY RUN — Preview only, no files will be moved
   Source      : /Users/username/Downloads
   Destination : /Users/username/Downloads
────────────────────────────────────────────────────────────
  ○ quarterly_q3.pdf    → Documents/quarterly_q3.pdf   [Documents]
  ○ raw_footage.mp4     → Videos/raw_footage.mp4       [Videos]
  ○ profile_avatar.png  → Images/profile_avatar.png    [Images]

────────────────────────────────────────────────────────────
 Dry-Run Summary (no files moved)
 Category     Files   Status
 ───────────  ─────  ──────────
 ● Documents    1     preview
 ● Videos       1     preview
 ● Images       1     preview
 ───────────  ─────  ──────────
 Total (preview)  3
────────────────────────────────────────────────────────────
 Tip: Run without --dry-run to apply these changes.

---

## 🛠 Under the Hood

### System Architecture
The application is structured into decoupled modules to isolate business logic from CLI handling:

File_Organizer/
├── organizer/
│   ├── __init__.py
│   ├── config.py       # Extension-to-folder mapping rules
│   └── core.py         # FileOrganizer engine (I/O, collision, scan logic)
├── main.py             # CLI parser (argparse) & entry point
├── .gitignore          # System & bytecode exclusion
└── README.md

### Key Engineering Decisions
- **Standard Library Only:** Relies exclusively on `pathlib`, `shutil`, and `argparse` to eliminate supply-chain vulnerabilities and ensure cross-platform compatibility without virtual environment setup.
- **Pathlib Over OS Strings:** Leverages `pathlib.Path` objects for path arithmetic, avoiding OS-specific delimiter bugs between Windows (`\`) and POSIX (`/`).
- **Idempotent Operations:** Target category directories are created lazily using `mkdir(parents=True, exist_ok=True)`.

---

## 💻 Usage

### Prerequisites
- Python 3.9 or higher installed.

### Quick Start

# Clone the repository
git clone https://github.com/Anki-bot/Automated-File-Organizer.git
cd automated-file-organizer

# 1. Preview file movements (Safe Mode)
python main.py --source /path/to/target/folder --dry-run

# 2. Execute organization in-place
python main.py --source /path/to/target/folder

# 3. Organize into a custom output directory
python main.py --source /path/to/input --destination /path/to/organized_output

---

## 🗺 Roadmap
- [ ] Watchdog daemon mode for automatic background sorting on download events
- [ ] Custom user configuration via JSON/YAML dotfiles (`~/.organizerrc`)
- [ ] Undo transaction log to reverse recent file movements