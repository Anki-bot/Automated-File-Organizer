"""
core.py — Core FileOrganizer class.

Responsibilities:
- Scanning source directory (non-recursive, files only at top level)
- Mapping files to categories via config
- Dry-run preview
- Safe moving with auto-rename on collision
- Summary reporting with ANSI colors
- Logging
"""

from __future__ import annotations

import logging
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

from .config import CATEGORY_FOLDERS, get_category_for_path

# ANSI color codes (standard, no external deps)
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
WHITE = "\033[97m"
GRAY = "\033[90m"


class FileOrganizerError(Exception):
    """Base exception for organizer errors."""
    pass


class FileOrganizer:
    """
    Orchestrates scanning, categorization, and safe moving of files.

    Attributes:
        source: Absolute Path of the directory to scan.
        destination: Absolute Path where category folders will be created.
                     Defaults to source if not provided.
        dry_run: If True, only preview actions without moving files.
        logger: Standard library logger instance.
    """

    def __init__(
        self,
        source: Path | str,
        destination: Path | str | None = None,
        dry_run: bool = False,
        verbose: bool = False,
    ) -> None:
        self.source = Path(source).resolve()
        self.destination = Path(destination).resolve() if destination else self.source
        self.dry_run = dry_run
        self.verbose = verbose

        self.logger = self._setup_logger(verbose)

        # Internal state populated during execution
        self._file_map: Dict[Path, str] = {}  # file -> category
        self._results: Counter = Counter()  # category -> count moved/previewed
        self._errors: List[Tuple[Path, str]] = []
        self._skipped: int = 0

    # ------------------------------------------------------------------ #
    # Logger
    # ------------------------------------------------------------------ #
    @staticmethod
    def _setup_logger(verbose: bool) -> logging.Logger:
        logger = logging.getLogger("FileOrganizer")
        # Avoid duplicate handlers on re-instantiation
        if not logger.handlers:
            handler = logging.StreamHandler()
            fmt = "%(levelname)s: %(message)s"
            handler.setFormatter(logging.Formatter(fmt))
            logger.addHandler(handler)
        logger.setLevel(logging.DEBUG if verbose else logging.INFO)
        return logger

    # ------------------------------------------------------------------ #
    # Validation
    # ------------------------------------------------------------------ #
    def validate(self) -> None:
        """Validate source and destination paths, raising on fatal errors."""
        if not self.source.exists():
            raise FileOrganizerError(f"Source directory does not exist: {self.source}")
        if not self.source.is_dir():
            raise FileOrganizerError(f"Source is not a directory: {self.source}")

        # Destination will be created if needed; but check if it's a file
        if self.destination.exists() and not self.destination.is_dir():
            raise FileOrganizerError(
                f"Destination exists and is not a directory: {self.destination}"
            )

    # ------------------------------------------------------------------ #
    # Scanning
    # ------------------------------------------------------------------ #
    def scan(self) -> Dict[Path, str]:
        """
        Scan source directory for files at the top level.

        - Ignores directories (including already-organized category folders)
        - Ignores hidden files starting with '.' (optional: still organizes them)
          Currently includes hidden files but skips directories.

        Returns:
            Mapping of file Path -> category string.
        """
        self._file_map.clear()
        self._skipped = 0

        try:
            entries = list(self.source.iterdir())
        except PermissionError as exc:
            raise FileOrganizerError(f"Permission denied reading source: {exc}") from exc

        for entry in entries:
            # Skip directories entirely — we only organize loose files
            if entry.is_dir():
                # Silently skip category folders and any other dirs
                self._skipped += 1
                if self.verbose:
                    self.logger.debug(f"Skipping directory: {entry.name}")
                continue

            if not entry.is_file():
                self._skipped += 1
                continue

            # Skip the organizer's own script files if source is project root
            # (avoid moving main.py etc. when demoing in project folder)
            # We still include them by default; user can move them. No hard skip.

            category = get_category_for_path(entry)
            self._file_map[entry] = category

        return self._file_map

    # ------------------------------------------------------------------ #
    # Auto-rename logic
    # ------------------------------------------------------------------ #
    @staticmethod
    def _resolve_collision(target: Path) -> Path:
        """
        If target exists, generate a new name like 'file(1).ext', 'file(2).ext'.

        Never overwrites. Uses pathlib for cross-platform safety.
        """
        if not target.exists():
            return target

        stem = target.stem
        suffix = target.suffix
        parent = target.parent

        counter = 1
        while True:
            candidate = parent / f"{stem}({counter}){suffix}"
            if not candidate.exists():
                return candidate
            counter += 1
            # Safety guard against infinite loop
            if counter > 10000:
                raise FileOrganizerError(f"Too many collisions for {target.name}")

    # ------------------------------------------------------------------ #
    # Move / Dry-run
    # ------------------------------------------------------------------ #
    def organize(self) -> Counter:
        """
        Execute organization (or dry-run preview).

        Ensures:
        - validate() called
        - scan() called if file map empty
        - destination category folders created as needed
        - each file moved safely with collision handling

        Returns:
            Counter with category -> number of files processed.
        """
        self.validate()

        if not self._file_map:
            self.scan()

        if not self._file_map:
            self._print_no_files()
            return Counter()

        self._results.clear()
        self._errors.clear()

        # Group by category for cleaner output
        grouped: Dict[str, List[Path]] = defaultdict(list)
        for f, cat in self._file_map.items():
            grouped[cat].append(f)

        # Sort categories and files for deterministic output
        for cat in sorted(grouped):
            grouped[cat] = sorted(grouped[cat])

        if self.dry_run:
            self._print_dry_run_header()
        else:
            self._print_header()
            # Ensure destination exists
            try:
                self.destination.mkdir(parents=True, exist_ok=True)
            except PermissionError as exc:
                raise FileOrganizerError(
                    f"Permission denied creating destination: {exc}"
                ) from exc

        for category in sorted(grouped):
            files = grouped[category]
            dest_folder = self.destination / category

            if not self.dry_run:
                try:
                    dest_folder.mkdir(parents=True, exist_ok=True)
                except PermissionError as exc:
                    for f in files:
                        self._errors.append((f, f"Cannot create folder {category}: {exc}"))
                    self.logger.error(f"{RED}Cannot create {dest_folder}: {exc}{RESET}")
                    continue

            for src in files:
                target = dest_folder / src.name
                # Resolve intra-run identity: if organizing within source,
                # dest_folder is inside source, but we already skipped dirs.
                if not self.dry_run:
                    target = self._resolve_collision(target)
                    try:
                        shutil.move(str(src), str(target))
                        self._results[category] += 1
                        self._print_move(src, target, category, renamed=(target.name != src.name))
                    except PermissionError as exc:
                        self._errors.append((src, str(exc)))
                        self._print_error(src, f"Permission denied: {exc}")
                    except OSError as exc:
                        self._errors.append((src, str(exc)))
                        self._print_error(src, str(exc))
                else:
                    # Dry-run: simulate collision check without moving
                    will_rename = target.exists()
                    preview_target = self._resolve_collision(target) if will_rename else target
                    self._results[category] += 1
                    self._print_dry_move(src, preview_target, category, renamed=will_rename)

        self._print_summary()
        return self._results

    # ------------------------------------------------------------------ #
    # Pretty printing (ANSI colors)
    # ------------------------------------------------------------------ #
    def _print_header(self) -> None:
        print(f"\n{BOLD}{CYAN}📁 Organizing files{RESET}")
        print(f"{DIM}   Source      : {self.source}{RESET}")
        print(f"{DIM}   Destination : {self.destination}{RESET}")
        print(f"{GRAY}{'─' * 60}{RESET}")

    def _print_dry_run_header(self) -> None:
        print(f"\n{BOLD}{YELLOW}🔍 DRY RUN — Preview only, no files will be moved{RESET}")
        print(f"{DIM}   Source      : {self.source}{RESET}")
        print(f"{DIM}   Destination : {self.destination}{RESET}")
        print(f"{GRAY}{'─' * 60}{RESET}")

    def _print_no_files(self) -> None:
        print(f"\n{YELLOW}⚠  No files to organize in {self.source}{RESET}")
        if self._skipped:
            print(f"{DIM}   Skipped {self._skipped} directorie(s).{RESET}")

    def _print_move(self, src: Path, dst: Path, category: str, renamed: bool) -> None:
        rel_src = src.name
        rel_dst = f"{category}/{dst.name}"
        tag = f"{YELLOW}renamed{RESET}" if renamed else f"{GREEN}moved{RESET}"
        print(f"  {GREEN}✔{RESET} {rel_src} {GRAY}→{RESET} {rel_dst}  {DIM}[{tag}{DIM}]{RESET}")
        if self.verbose:
            self.logger.debug(f"Moved {src} -> {dst}")

    def _print_dry_move(self, src: Path, dst: Path, category: str, renamed: bool) -> None:
        rel_src = src.name
        rel_dst = f"{category}/{dst.name}"
        rename_note = f" {YELLOW}(will rename){RESET}" if renamed else ""
        print(f"  {YELLOW}○{RESET} {rel_src} {GRAY}→{RESET} {rel_dst}{rename_note}  {DIM}[{category}]{RESET}")

    def _print_error(self, src: Path, msg: str) -> None:
        print(f"  {RED}✘{RESET} {src.name} {RED}— {msg}{RESET}")

    def _print_summary(self) -> None:
        total = sum(self._results.values())
        print(f"\n{GRAY}{'─' * 60}{RESET}")

        if self.dry_run:
            print(f"{BOLD}{YELLOW} Dry-Run Summary (no files moved){RESET}")
        else:
            print(f"{BOLD}{GREEN} Summary{RESET}")

        if not self._results:
            print(f"{DIM}  Nothing to do.{RESET}")
            return

        # Calculate column widths for table
        cat_width = max(len(c) for c in self._results) + 2
        cat_width = max(cat_width, len("Category") + 2)
        count_width = max(len(str(v)) for v in self._results.values())
        count_width = max(count_width, len("Files"))

        # Header
        header = f"  {BOLD}{'Category'.ljust(cat_width)}{'Files'.rjust(count_width)}   Status{RESET}"
        print(header)
        print(f"  {GRAY}{'─' * cat_width} {'─' * count_width} {'─' * 10}{RESET}")

        for category in sorted(self._results):
            count = self._results[category]
            status = f"{YELLOW}preview{RESET}" if self.dry_run else f"{GREEN}done{RESET}"
            # Color category dot
            dot = f"{CYAN}●{RESET}"
            print(f"  {dot} {category.ljust(cat_width - 2)}{str(count).rjust(count_width)}   {status}")

        print(f"  {GRAY}{'─' * cat_width} {'─' * count_width} {'─' * 10}{RESET}")
        total_label = "Total (preview)" if self.dry_run else "Total moved"
        print(f"  {BOLD}{total_label.ljust(cat_width)}{str(total).rjust(count_width)}{RESET}")

        if self._errors:
            print(f"\n{RED}{BOLD}  {len(self._errors)} error(s):{RESET}")
            for p, msg in self._errors:
                print(f"    {RED}•{RESET} {p.name}: {msg}")

        if self._skipped:
            print(f"\n{DIM}  Skipped {self._skipped} directorie(s) (not organized).{RESET}")

        print(f"{GRAY}{'─' * 60}{RESET}")
        if self.dry_run:
            print(f"{YELLOW}  Tip: Run without --dry-run to apply these changes.{RESET}\n")
        else:
            print(f"{GREEN}  Done! Files organized in {self.destination}{RESET}\n")

    # ------------------------------------------------------------------ #
    # Convenience: one-shot classmethod
    # ------------------------------------------------------------------ #
    @classmethod
    def run(
        cls,
        source: Path | str,
        destination: Path | str | None = None,
        dry_run: bool = False,
        verbose: bool = False,
    ) -> Counter:
        """One-liner to scan + organize."""
        inst = cls(source=source, destination=destination, dry_run=dry_run, verbose=verbose)
        return inst.organize()
