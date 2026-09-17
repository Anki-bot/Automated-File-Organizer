"""
watcher.py — Background Watchdog Daemon for File Organizer.

Watches --source for new file creation events and auto-routes them
to the correct category using the same deduplication + collision logic.

Requires: pip install watchdog
"""

from __future__ import annotations

import time
from pathlib import Path

try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer

    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    # Dummy placeholders for type checkers
    FileSystemEventHandler = object  # type: ignore
    Observer = object  # type: ignore

from .config import HISTORY_FILENAME
from .core import CYAN, DIM, GRAY, GREEN, RED, RESET, YELLOW, BOLD


class OrganizerHandler(FileSystemEventHandler):  # type: ignore
    """Handles filesystem events and delegates to FileOrganizer."""

    def __init__(self, organizer, verbose: bool = False):
        super().__init__()
        self.organizer = organizer
        self.verbose = verbose

    def on_created(self, event):
        if event.is_directory:
            return
        self._handle(Path(event.src_path))

    def on_moved(self, event):
        # Handles files moved into the watched folder (e.g., drag-drop, download complete)
        if event.is_directory:
            return
        dest = getattr(event, "dest_path", None) or getattr(event, "destPath", None)
        if dest:
            self._handle(Path(dest))

    def _handle(self, path: Path):
        # Ignore hidden/history/category-internal events
        if path.name == HISTORY_FILENAME:
            return
        if path.name.startswith("._"):  # macOS resource fork
            return
        # Ignore temp download files
        if path.suffix.lower() in {".tmp", ".crdownload", ".part", ".download"}:
            if self.verbose:
                print(f"{DIM}  ⏳ Ignoring temp file: {path.name}{RESET}")
            # Still watch for the final renamed file via on_moved
            return

        # Small debounce: let file settle
        time.sleep(0.3)
        if not path.exists() or not path.is_file():
            return
        # Ignore files already inside a category subfolder when source==destination
        try:
            if self.organizer.destination in path.parents:
                rel = path.relative_to(self.organizer.destination)
                if rel.parts and rel.parts[0] in self.organizer.destination.iterdir.__self__ if False else False:
                    pass
        except Exception:
            pass

        # Only handle files that are directly in source (non-recursive watch)
        # Watchdog may emit events for subfolders if recursive; we filter
        try:
            if path.parent.resolve() != self.organizer.source.resolve():
                # If destination != source, also allow files dropped in source root only
                # Ignore events from category folders themselves
                if self.verbose:
                    print(f"{DIM}  ↷ Skipping nested file: {path}{RESET}")
                return
        except Exception:
            pass

        print(f"{DIM}  → Detected: {path.name}{RESET}")
        # Use organizer's single-file handler (handles hashing, dedup, history)
        result = self.organizer.organize_single_file(path)
        if result in ("moved", "renamed", "duplicate") and self.verbose:
            pass  # already logged inside organize_single_file


def start_watch(source: Path | str, destination: Path | str | None = None, verbose: bool = False) -> None:
    """
    Start the watchdog daemon. Blocks until Ctrl+C.

    Args:
        source: Directory to watch.
        destination: Where to organize into (defaults to source).
        verbose: Enable debug logging.
    """
    if not WATCHDOG_AVAILABLE:
        print(f"{RED}Error: 'watchdog' library not installed.{RESET}")
        print(f"{YELLOW}Install it with: pip install -r requirements.txt  (or pip install watchdog){RESET}")
        raise SystemExit(1)

    from .core import FileOrganizer, FileOrganizerError

    source_p = Path(source).resolve()
    dest_p = Path(destination).resolve() if destination else source_p

    # Validate before starting
    org = FileOrganizer(source=source_p, destination=dest_p, verbose=verbose)
    try:
        org.validate()
    except FileOrganizerError as exc:
        print(f"{RED}Error: {exc}{RESET}")
        raise SystemExit(1)

    # Initial scan: organize existing files first (optional but user-friendly)
    print(f"\n{BOLD}{CYAN}👀 Watchdog daemon started{RESET}")
    print(f"{DIM}   Watching   : {source_p}{RESET}")
    print(f"{DIM}   Destination: {dest_p}{RESET}")
    print(f"{DIM}   Press Ctrl+C to stop.{RESET}")
    print(f"{GRAY}{'─' * 60}{RESET}")

    # Do an initial organize of any lingering files
    org.organize()

    handler = OrganizerHandler(org, verbose=verbose)
    observer = Observer()
    observer.schedule(handler, str(source_p), recursive=False)
    observer.start()

    print(f"{GREEN}  Watching for new files...{RESET}\n")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Stopping watchdog...{RESET}")
        observer.stop()
    observer.join()
    print(f"{GREEN}Watchdog stopped.{RESET}")
