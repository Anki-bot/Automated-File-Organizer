#!/usr/bin/env python3
"""
main.py — CLI entry point for Automated File Organizer.

Usage:
    python main.py --source ./Downloads --dry-run
    python main.py --source ./messy --destination ./organized
    python main.py --source ./Downloads --undo
    python main.py --source ./Downloads --watch
    python main.py --help
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure package import works when running as script
sys.path.insert(0, str(Path(__file__).parent))

from organizer.core import (
    BOLD,
    CYAN,
    DIM,
    GRAY,
    GREEN,
    RED,
    RESET,
    YELLOW,
    FileOrganizer,
    FileOrganizerError,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="file-organizer",
        description="Automated File Organizer — sort files safely with dedup, undo, and watchdog daemon.",
        epilog=(
            "Examples:\n"
            "  python main.py --source ./Downloads --dry-run\n"
            "  python main.py --source ./Downloads\n"
            "  python main.py --source ./Downloads --destination ./Organized\n"
            "  python main.py --source ./Downloads --undo\n"
            "  python main.py --source ./Downloads --watch\n"
            "  python main.py --source ./Downloads --watch --verbose\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--source",
        "-s",
        type=str,
        default=".",
        help="Source directory to scan/watch (default: current directory '.')",
    )
    parser.add_argument(
        "--destination",
        "-d",
        type=str,
        default=None,
        help="Destination directory (default: same as --source, folders created inside source)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview file movements without actually moving anything",
    )
    parser.add_argument(
        "--undo",
        action="store_true",
        help="Undo last organization by restoring files from .organizer_history.json",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Watch source directory continuously and auto-organize new files (requires watchdog)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose debug logging",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 1.1.0",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    source = Path(args.source)
    destination = Path(args.destination) if args.destination else None

    # Guard: --undo and --dry-run / --watch combinations
    if args.undo and args.dry_run:
        print(f"{YELLOW}Warning: --dry-run has no effect with --undo; running undo anyway.{RESET}")
    if args.undo and args.watch:
        print(f"{RED}Error: --undo and --watch cannot be used together.{RESET}", file=sys.stderr)
        return 1
    if args.watch and args.dry_run:
        print(f"{YELLOW}Warning: --watch with --dry-run will only preview new files (no moves).{RESET}")

    try:
        # Watchdog mode takes over the process
        if args.watch:
            try:
                from organizer.watcher import start_watch
            except ImportError as exc:
                print(f"{RED}Error: watchdog not available: {exc}{RESET}", file=sys.stderr)
                print(f"{YELLOW}Install with: pip install -r requirements.txt{RESET}", file=sys.stderr)
                return 1
            # Pass dry_run through to organizer inside watcher
            # For --watch --dry-run, we want preview mode
            # start_watch creates its own organizer; we need to handle dry_run flag
            # Patch: create organizer with dry_run and inject into watcher
            # Simpler: if dry_run + watch, just call with dry_run=True
            if args.dry_run:
                # Lightweight watch in dry-run: still use watcher but with dry_run organizer
                from organizer.watcher import OrganizerHandler
                from watchdog.observers import Observer

                src_p = source.resolve()
                dst_p = destination.resolve() if destination else src_p
                org = FileOrganizer(source=src_p, destination=dst_p, dry_run=True, verbose=args.verbose)
                try:
                    org.validate()
                except FileOrganizerError as e:
                    print(f"{RED}Error: {e}{RESET}", file=sys.stderr)
                    return 1
                print(f"\n{BOLD}{CYAN}👀 Watchdog daemon started (DRY-RUN){RESET}")
                print(f"{DIM}   Watching   : {src_p}{RESET}")
                print(f"{DIM}   Destination: {dst_p}{RESET}")
                print(f"{GRAY}{'─' * 60}{RESET}")
                org.organize()
                handler = OrganizerHandler(org, verbose=args.verbose)
                observer = Observer()
                observer.schedule(handler, str(src_p), recursive=False)
                observer.start()
                print(f"{GREEN}  Watching for new files (preview only)... Press Ctrl+C to stop.{RESET}\n")
                try:
                    import time
                    while True:
                        time.sleep(1)
                except KeyboardInterrupt:
                    print(f"\n{YELLOW}Stopping watchdog...{RESET}")
                    observer.stop()
                observer.join()
                print(f"{GREEN}Watchdog stopped.{RESET}")
                return 0
            else:
                start_watch(source, destination, verbose=args.verbose)
                return 0

        organizer = FileOrganizer(
            source=source,
            destination=destination,
            dry_run=args.dry_run,
            verbose=args.verbose,
        )

        if args.undo:
            organizer.undo()
            return 0

        organizer.organize()
        return 0

    except FileOrganizerError as exc:
        print(f"{RED}Error: {exc}{RESET}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Interrupted by user.{RESET}")
        return 130
    except Exception as exc:  # noqa: BLE001 — top-level safety net
        print(f"{RED}Unexpected error: {exc}{RESET}", file=sys.stderr)
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
