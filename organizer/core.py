"""
core.py — Core FileOrganizer class.

Responsibilities:
- Scanning source directory (non-recursive, files only at top level)
- Mapping files to categories via config (with universal fallback)
- Cryptographic deduplication (SHA-256) before moving
- Dry-run preview
- Safe moving with auto-rename on collision
- Transaction log (.organizer_history.json) for undo
- Undo engine: restore files, clean empty folders, delete history
- Single-file routing (for watchdog daemon)
- Summary reporting with ANSI colors
- Logging
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

from .config import CATEGORY_FOLDERS, HISTORY_FILENAME, get_category_for_path

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
        # Transaction log: new_path (str) -> original_path (str)
        self._history: Dict[str, str] = {}
        # Deduplication counter
        self._duplicates: int = 0

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

    @property
    def history_path(self) -> Path:
        """Path to the hidden transaction log in the destination folder."""
        return self.destination / HISTORY_FILENAME

    # ------------------------------------------------------------------ #
    # Hashing — Cryptographic Deduplication
    # ------------------------------------------------------------------ #
    @staticmethod
    def _hash_file(path: Path, chunk_size: int = 8192) -> str:
        """
        Compute SHA-256 hash of a file.

        Reads in chunks to handle large files without loading into memory.
        Raises OSError if file cannot be read.
        """
        sha256 = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(chunk_size), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    @staticmethod
    def _is_duplicate(src: Path, dst: Path) -> bool:
        """
        Return True if src and dst have identical SHA-256 hash.

        Returns False if either file cannot be hashed or hashes differ.
        Caller should handle OSError separately if needed.
        """
        return FileOrganizer._hash_file(src) == FileOrganizer._hash_file(dst)

    # ------------------------------------------------------------------ #
    # Scanning
    # ------------------------------------------------------------------ #
    def scan(self) -> Dict[Path, str]:
        """
        Scan source directory for files at the top level.

        - Ignores directories (including already-organized category folders)
        - Ignores the history file itself (.organizer_history.json)
        - Universal fallback: every file gets a category (Miscellaneous if unknown)

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
            # Never organize the history file itself
            if entry.name == HISTORY_FILENAME:
                self._skipped += 1
                if self.verbose:
                    self.logger.debug(f"Skipping history file: {entry.name}")
                continue

            # Skip directories entirely — we only organize loose files
            if entry.is_dir():
                self._skipped += 1
                if self.verbose:
                    self.logger.debug(f"Skipping directory: {entry.name}")
                continue

            if not entry.is_file():
                self._skipped += 1
                continue

            # Universal fallback handled inside get_category_for_path
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
    # Transaction log (history)
    # ------------------------------------------------------------------ #
    def _load_history(self) -> Dict[str, str]:
        """Load existing history file if present, else return empty dict."""
        hp = self.history_path
        # Also check source if destination differs and file not in destination
        alt = self.source / HISTORY_FILENAME
        target = hp if hp.exists() else alt if alt.exists() else None
        if target is None:
            return {}
        try:
            with open(target, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return {str(k): str(v) for k, v in data.items()}
                return {}
        except (json.JSONDecodeError, OSError) as exc:
            self.logger.warning(f"Could not read history file {target}: {exc}")
            return {}

    def _save_history(self) -> None:
        """
        Persist transaction log to destination/.organizer_history.json.
        Merges with any existing history so multiple runs accumulate safely.
        Only called when not in dry-run and at least one file was moved.
        """
        if not self._history:
            return

        # Merge with existing to avoid losing prior transactions
        existing = self._load_history()
        # New entries take precedence (in case of re-run on same file)
        merged = {**existing, **self._history}

        try:
            self.history_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.history_path, "w", encoding="utf-8") as f:
                json.dump(merged, f, indent=2, sort_keys=True)
            if self.verbose:
                self.logger.debug(f"History saved to {self.history_path} ({len(merged)} entries)")
        except OSError as exc:
            self.logger.error(f"{RED}Failed to write history file {self.history_path}: {exc}{RESET}")
            # Non-fatal: organizing succeeded, just log failure
            self._errors.append((self.history_path, f"Failed to write history: {exc}"))

    # ------------------------------------------------------------------ #
    # Single-file handler (used by batch and watchdog)
    # ------------------------------------------------------------------ #
    def _wait_for_stable(self, path: Path, timeout: float = 6.0, interval: float = 0.5) -> bool:
        """
        Wait until file size is stable (download complete).

        Returns True if stable within timeout, False otherwise.
        """
        start = time.time()
        last_size = -1
        stable_count = 0
        while time.time() - start < timeout:
            try:
                cur_size = path.stat().st_size
            except OSError:
                return False
            if cur_size == last_size and cur_size != -1:
                stable_count += 1
                if stable_count >= 2:
                    return True
            else:
                stable_count = 0
            last_size = cur_size
            time.sleep(interval)
        # Timeout: assume stable if file still exists
        return path.exists()

    def organize_single_file(self, file_path: Path | str) -> str | None:
        """
        Organize a single file (used by watchdog and manual calls).

        Handles deduplication, collision, history, and colored output.
        Waits briefly for file to be fully written.

        Args:
            file_path: Absolute or relative path to file inside source.

        Returns:
            Status string: "moved", "renamed", "duplicate", "skipped", "error", or None if ignored.
        """
        src = Path(file_path).resolve()

        # Ignore history file, directories, non-existent, or outside source
        if src.name == HISTORY_FILENAME:
            return "skipped"
        if not src.exists() or not src.is_file():
            return "skipped"
        # Only handle files directly in source (watchdog may give nested, we still handle)
        # But respect that we don't organize files already inside category folders in destination
        # If destination == source, ignore files already inside category folders
        try:
            # If file is inside destination/category folder, ignore (already organized)
            if self.destination in src.parents:
                rel = src.relative_to(self.destination)
                if rel.parts and rel.parts[0] in CATEGORY_FOLDERS:
                    if self.verbose:
                        self.logger.debug(f"Skipping already-organized file: {src}")
                    return "skipped"
        except ValueError:
            pass

        # Wait for file to be fully written (important for downloads)
        # Only wait if file was recently modified (< 2s ago)
        try:
            age = time.time() - src.stat().st_mtime
            if age < 2.0:
                self._wait_for_stable(src)
        except OSError:
            pass

        # Double-check file still exists after wait
        if not src.exists():
            return "skipped"

        category = get_category_for_path(src)
        dest_folder = self.destination / category

        try:
            dest_folder.mkdir(parents=True, exist_ok=True)
        except PermissionError as exc:
            self._print_error(src, f"Cannot create folder {category}: {exc}")
            return "error"

        target = dest_folder / src.name

        # --- DRY-RUN PREVIEW ---
        if self.dry_run:
            if target.exists() and target.is_file():
                try:
                    if self._is_duplicate(src, target):
                        self._print_dry_duplicate(src, target, category)
                        return "duplicate"
                    else:
                        preview = self._resolve_collision(target)
                        renamed = preview.name != src.name
                        self._print_dry_move(src, preview, category, renamed=renamed)
                        return "renamed" if renamed else "moved"
                except OSError:
                    preview = self._resolve_collision(target)
                    self._print_dry_move(src, preview, category, renamed=(preview.name != src.name))
                    return "preview"
            else:
                self._print_dry_move(src, target, category, renamed=False)
                return "moved"

        # --- REAL MODE: DEDUPLICATION CHECK ---
        if target.exists():
            if target.is_file():
                try:
                    if self._is_duplicate(src, target):
                        # Duplicate -> delete source to save space
                        try:
                            src.unlink()
                        except OSError as exc:
                            self._print_error(src, f"Failed to delete duplicate: {exc}")
                            return "error"
                        self._duplicates += 1
                        self._print_duplicate(src, target, category)
                        return "duplicate"
                    else:
                        # Hash mismatch -> auto-rename
                        target = self._resolve_collision(target)
                except OSError as exc:
                    # Hashing failed -> fallback to rename
                    if self.verbose:
                        self.logger.debug(f"Hash check failed for {src.name}: {exc}, falling back to rename")
                    target = self._resolve_collision(target)
            else:
                target = self._resolve_collision(target)

        # --- MOVE ---
        try:
            original = str(src.resolve())
            # Re-check resolved target hasn't become duplicate during wait
            # (rare but safe)
            shutil.move(str(src), str(target))
            self._results[category] += 1
            self._history[str(target.resolve())] = original
            # Save history incrementally for watchdog (so each file is logged)
            # We do batch save at end for organize(), but for single file we save immediately
            # To avoid excessive I/O, we merge and write
            self._save_history()
            renamed = target.name != Path(original).name
            self._print_move(src, target, category, renamed=renamed)
            return "renamed" if renamed else "moved"
        except PermissionError as exc:
            self._print_error(src, f"Permission denied: {exc}")
            return "error"
        except OSError as exc:
            self._print_error(src, str(exc))
            return "error"

    # ------------------------------------------------------------------ #
    # Move / Dry-run (batch)
    # ------------------------------------------------------------------ #
    def organize(self) -> Counter:
        """
        Execute organization (or dry-run preview).

        Ensures:
        - validate() called
        - scan() called if file map empty
        - destination category folders created as needed
        - each file moved safely with deduplication + collision handling
        - transaction log written (if not dry-run)

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
        self._history.clear()
        self._duplicates = 0

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
                # Delegate to single-file logic for deduplication consistency
                # But for batch we want to avoid re-resolving category/counter double-increment issues
                # So we inline deduplication + move here to preserve grouping + summary logic
                target = dest_folder / src.name

                if not self.dry_run:
                    # --- DEDUPLICATION ---
                    if target.exists() and target.is_file():
                        try:
                            if self._is_duplicate(src, target):
                                try:
                                    src.unlink()
                                except OSError as exc:
                                    self._errors.append((src, f"Failed to delete duplicate: {exc}"))
                                    self._print_error(src, f"Failed to delete duplicate: {exc}")
                                    continue
                                self._duplicates += 1
                                self._print_duplicate(src, target, category)
                                continue
                            else:
                                target = self._resolve_collision(target)
                        except OSError as exc:
                            if self.verbose:
                                self.logger.debug(f"Hash check failed for {src.name}: {exc}")
                            target = self._resolve_collision(target)
                    elif target.exists():
                        target = self._resolve_collision(target)

                    # --- MOVE ---
                    try:
                        original = str(src.resolve())
                        shutil.move(str(src), str(target))
                        self._results[category] += 1
                        self._history[str(target.resolve())] = original
                        self._print_move(src, target, category, renamed=(target.name != src.name))
                    except PermissionError as exc:
                        self._errors.append((src, str(exc)))
                        self._print_error(src, f"Permission denied: {exc}")
                    except OSError as exc:
                        self._errors.append((src, str(exc)))
                        self._print_error(src, str(exc))
                else:
                    # Dry-run: simulate dedup + collision check without moving
                    if target.exists() and target.is_file():
                        try:
                            if self._is_duplicate(src, target):
                                self._print_dry_duplicate(src, target, category)
                                self._results[category] += 1  # count as previewed duplicate
                                continue
                        except OSError:
                            pass
                        # Not duplicate -> will rename if needed
                        will_rename = True
                        preview_target = self._resolve_collision(target)
                        self._results[category] += 1
                        self._print_dry_move(src, preview_target, category, renamed=will_rename)
                    else:
                        will_rename = False
                        self._results[category] += 1
                        self._print_dry_move(src, target, category, renamed=will_rename)

        if not self.dry_run and self._history:
            self._save_history()
            print(f"{DIM}  ↳ History saved: {self.history_path} ({len(self._history)} file(s) logged){RESET}")
        if not self.dry_run and self._duplicates:
            print(f"{YELLOW}  ↳ Duplicates deleted: {self._duplicates}{RESET}")

        self._print_summary()
        return self._results

    # ------------------------------------------------------------------ #
    # Undo engine
    # ------------------------------------------------------------------ #
    def undo(self) -> int:
        """
        Undo the last organize operation by reading the history file.

        - Reads destination/.organizer_history.json (falls back to source)
        - Moves each file from new_path back to original_path
        - Handles collisions on restore with auto-rename
        - Deletes empty category folders
        - Deletes the history file

        Returns:
            Number of files restored (0 if nothing to undo).
        """
        # Determine where history lives
        hp = self.history_path
        alt = self.source / HISTORY_FILENAME

        # Prefer destination, then source, then report missing
        history_file: Path | None = None
        if hp.exists():
            history_file = hp
        elif alt.exists():
            history_file = alt
        else:
            # Also check if source==destination, already covered; just warn
            expected = hp
            print(f"\n{YELLOW}⚠  Nothing to undo — no history file found.{RESET}")
            print(f"{DIM}   Expected: {expected}{RESET}")
            print(f"{DIM}   Tip: Run without --undo to organize files first.{RESET}\n")
            return 0

        # Load history
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except json.JSONDecodeError as exc:
            print(f"{RED}✘ History file is corrupted: {history_file}: {exc}{RESET}")
            return 0
        except OSError as exc:
            print(f"{RED}✘ Cannot read history file {history_file}: {exc}{RESET}")
            return 0

        if not isinstance(raw, dict) or not raw:
            print(f"\n{YELLOW}⚠  History file is empty — nothing to undo.{RESET}")
            print(f"{DIM}   File: {history_file}{RESET}\n")
            # Clean up empty file
            try:
                history_file.unlink()
            except OSError:
                pass
            return 0

        # Normalize to Path objects: new_path -> original_path
        entries: List[Tuple[Path, Path]] = []
        for new_s, orig_s in raw.items():
            entries.append((Path(new_s), Path(orig_s)))

        print(f"\n{BOLD}{CYAN}↩  Undoing last organization{RESET}")
        print(f"{DIM}   History file: {history_file}{RESET}")
        print(f"{DIM}   Entries     : {len(entries)}{RESET}")
        print(f"{GRAY}{'─' * 60}{RESET}")

        restored = 0
        errors: List[Tuple[Path, str]] = []
        # Track categories that might become empty
        touched_categories: set[str] = set()

        for new_path, orig_path in sorted(entries, key=lambda x: x[0].name):
            # Record category for cleanup
            try:
                # Category is parent folder name of new_path
                touched_categories.add(new_path.parent.name)
            except Exception:
                pass

            if not new_path.exists():
                msg = "file not found (already moved or deleted)"
                print(f"  {YELLOW}○{RESET} {new_path.name} {DIM}— {msg}{RESET}")
                errors.append((new_path, msg))
                continue

            # Ensure original parent exists
            try:
                orig_path.parent.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                print(f"  {RED}✘{RESET} {new_path.name} {RED}— cannot create original folder: {exc}{RESET}")
                errors.append((new_path, str(exc)))
                continue

            # Resolve collision if something now occupies original path
            restore_target = orig_path
            if restore_target.exists():
                restore_target = self._resolve_collision(restore_target)
                print(f"  {YELLOW}⚠{RESET} {orig_path.name} already exists, will restore as {restore_target.name}")

            try:
                shutil.move(str(new_path), str(restore_target))
                restored += 1
                renamed = restore_target.name != orig_path.name
                tag = f"{YELLOW}renamed{RESET}" if renamed else f"{GREEN}restored{RESET}"
                print(f"  {GREEN}✔{RESET} {new_path.name} {GRAY}→{RESET} {restore_target}  {DIM}[{tag}{DIM}]{RESET}")
            except PermissionError as exc:
                errors.append((new_path, f"Permission denied: {exc}"))
                print(f"  {RED}✘{RESET} {new_path.name} {RED}— Permission denied: {exc}{RESET}")
            except OSError as exc:
                errors.append((new_path, str(exc)))
                print(f"  {RED}✘{RESET} {new_path.name} {RED}— {exc}{RESET}")

        # Clean up empty category folders in destination
        cleaned: List[str] = []
        # Check both touched categories and all known categories
        candidates = touched_categories | CATEGORY_FOLDERS
        for cat in sorted(candidates):
            folder = self.destination / cat
            # Only delete if it's a known category or was touched, exists, and is empty
            if folder.exists() and folder.is_dir():
                # Only auto-delete if it's a category folder we manage
                if cat in CATEGORY_FOLDERS or cat in touched_categories:
                    try:
                        # Check if empty (no files/dirs inside, ignoring hidden files?)
                        if not any(folder.iterdir()):
                            folder.rmdir()
                            cleaned.append(cat)
                            print(f"  {DIM}🗑  Removed empty folder: {cat}/{RESET}")
                    except OSError as exc:
                        if self.verbose:
                            self.logger.debug(f"Could not remove {folder}: {exc}")

        # Delete history file
        try:
            history_file.unlink()
            print(f"{DIM}  🗑  Deleted history file: {history_file.name}{RESET}")
        except OSError as exc:
            print(f"{RED}✘ Could not delete history file {history_file}: {exc}{RESET}")
            errors.append((history_file, str(exc)))

        # Summary
        print(f"\n{GRAY}{'─' * 60}{RESET}")
        if restored:
            print(f"{BOLD}{GREEN} Undo complete — {restored} file(s) restored{RESET}")
        else:
            print(f"{BOLD}{YELLOW} Undo finished — no files were restored{RESET}")

        if cleaned:
            print(f"{DIM}  Cleaned {len(cleaned)} empty folder(s): {', '.join(cleaned)}{RESET}")

        if errors:
            print(f"{YELLOW}  {len(errors)} warning(s) during undo (see above).{RESET}")

        print(f"{GRAY}{'─' * 60}{RESET}\n")
        return restored

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

    def _print_duplicate(self, src: Path, dst: Path, category: str) -> None:
        """Log duplicate deletion (hash match)."""
        print(f"  {MAGENTA}✦{RESET} {src.name} {GRAY}→{RESET} {category}/{dst.name}  {YELLOW}[Duplicate deleted]{RESET} {DIM}(SHA-256 match){RESET}")

    def _print_dry_duplicate(self, src: Path, dst: Path, category: str) -> None:
        """Preview duplicate deletion in dry-run."""
        print(f"  {YELLOW}○{RESET} {src.name} {GRAY}→{RESET} {category}/{dst.name}  {YELLOW}[would delete — duplicate]{RESET} {DIM}(SHA-256 match){RESET}")

    def _print_error(self, src: Path, msg: str) -> None:
        print(f"  {RED}✘{RESET} {src.name} {RED}— {msg}{RESET}")

    def _print_summary(self) -> None:
        total = sum(self._results.values())
        print(f"\n{GRAY}{'─' * 60}{RESET}")

        if self.dry_run:
            print(f"{BOLD}{YELLOW} Dry-Run Summary (no files moved){RESET}")
        else:
            print(f"{BOLD}{GREEN} Summary{RESET}")

        if not self._results and not self._duplicates:
            print(f"{DIM}  Nothing to do.{RESET}")
            return

        # Calculate column widths for table
        if self._results:
            cat_width = max(len(c) for c in self._results) + 2
        else:
            cat_width = len("Category") + 2
        cat_width = max(cat_width, len("Category") + 2)
        if self._results:
            count_width = max(len(str(v)) for v in self._results.values())
        else:
            count_width = len("Files")
        count_width = max(count_width, len("Files"))

        # Header
        if self._results:
            header = f"  {BOLD}{'Category'.ljust(cat_width)}{'Files'.rjust(count_width)}   Status{RESET}"
            print(header)
            print(f"  {GRAY}{'─' * cat_width} {'─' * count_width} {'─' * 10}{RESET}")

            for category in sorted(self._results):
                count = self._results[category]
                status = f"{YELLOW}preview{RESET}" if self.dry_run else f"{GREEN}done{RESET}"
                dot = f"{CYAN}●{RESET}"
                print(f"  {dot} {category.ljust(cat_width - 2)}{str(count).rjust(count_width)}   {status}")

            print(f"  {GRAY}{'─' * cat_width} {'─' * count_width} {'─' * 10}{RESET}")
        total_label = "Total (preview)" if self.dry_run else "Total moved"
        print(f"  {BOLD}{total_label.ljust(cat_width)}{str(total).rjust(count_width)}{RESET}")
        if self._duplicates:
            dup_label = "Duplicates deleted" if not self.dry_run else "Duplicates (would delete)"
            color = YELLOW if self.dry_run else MAGENTA
            print(f"  {BOLD}{color}{dup_label.ljust(cat_width)}{str(self._duplicates).rjust(count_width)}{RESET}")

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
