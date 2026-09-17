#!/usr/bin/env python3
"""
main.py — CLI entry point for Automated File Organizer.

Usage:
    python main.py --source ./Downloads --dry-run
    python main.py --source ./messy --destination ./organized
    python main.py --source ./Downloads --undo
    python main.py --source ./Downloads --watch
    python main.py --config my_config.json --source ./Downloads
    python main.py --generate-config
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
        description="Automated File Organizer — sort files safely with dedup, undo, watchdog, and custom JSON config.",
        epilog=(
            "Examples:\n"
            "  python main.py --source ./Downloads --dry-run\n"
            "  python main.py --source ./Downloads\n"
            "  python main.py --source ./Downloads --destination ./Organized\n"
            "  python main.py --source ./Downloads --undo\n"
            "  python main.py --source ./Downloads --watch\n"
            "  python main.py --source ./Downloads --watch --verbose\n"
            "  python main.py --config organizer_config.json --source ./Downloads\n"
            "  python main.py --generate-config\n"
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
        "--config",
        type=str,
        default=None,
        help="Path to custom JSON config file (e.g., organizer_config.json). Overrides default mappings.",
    )
    parser.add_argument(
        "--generate-config",
        action="store_true",
        help="Generate a template organizer_config.json in the current directory with default mappings",
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


def handle_generate_config() -> int:
    """Generate template config JSON in current directory."""
    from organizer.config import generate_template_config

    dest = Path.cwd() / "organizer_config.json"
    if dest.exists():
        print(f"{YELLOW}⚠  {dest} already exists — overwriting.{RESET}")

    try:
        out = generate_template_config(dest)
        print(f"{GREEN}✔ Template config generated: {out}{RESET}")
        print(f"{DIM}  Edit {out} to customize categories, then run:{RESET}")
        print(f"{DIM}    python main.py --config {out.name} --source ./your_folder{RESET}")
        print(f"{DIM}  Example template structure:{RESET}")
        print(f'{DIM}    {{"Movies": [".mp4", ".mkv"], "Tax Documents": [".pdf", ".xls"]}}{RESET}')
        return 0
    except OSError as exc:
        print(f"{RED}✘ Failed to generate config: {exc}{RESET}", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # Handle --generate-config immediately (does not require source validation)
    if args.generate_config:
        return handle_generate_config()

    source = Path(args.source)
    destination = Path(args.destination) if args.destination else None
    config_path = Path(args.config) if args.config else None

    # Validate config path early for clearer error
    # When --config is provided, defaults are completely cleared and ONLY JSON is used (no merging)
    if config_path:
        if not config_path.exists():
            print(f"{RED}Error: Config file not found: {config_path}{RESET}", file=sys.stderr)
            return 1
        print(f"{CYAN}  ↳ Custom config override: {config_path} — default categories will be cleared{RESET}")
        # Quick JSON syntax check for early feedback (detailed sanitization happens in core)
        try:
            import json
            with open(config_path, "r", encoding="utf-8") as _f:
                _data = json.load(_f)
            if not isinstance(_data, dict):
                raise ValueError("JSON root must be an object")
        except json.JSONDecodeError as exc:
            print(f"{RED}Error: Invalid JSON in config file {config_path}: {exc}{RESET}", file=sys.stderr)
            return 1
        except ValueError as exc:
            print(f"{RED}Error: Config error: {exc}{RESET}", file=sys.stderr)
            return 1
        except OSError as exc:
            print(f"{RED}Error: Cannot read config file {config_path}: {exc}{RESET}", file=sys.stderr)
            return 1
    else:
        # No custom config — using defaults
        pass

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
            if args.dry_run:
                # Lightweight watch in dry-run: still use watcher but with dry_run organizer
                from organizer.watcher import OrganizerHandler
                from watchdog.observers import Observer

                src_p = source.resolve()
                dst_p = destination.resolve() if destination else src_p
                try:
                    org = FileOrganizer(
                        source=src_p,
                        destination=dst_p,
                        dry_run=True,
                        verbose=args.verbose,
                        config_path=config_path,
                    )
                except FileOrganizerError as e:
                    print(f"{RED}Error: {e}{RESET}", file=sys.stderr)
                    return 1
                try:
                    org.validate()
                except FileOrganizerError as e:
                    print(f"{RED}Error: {e}{RESET}", file=sys.stderr)
                    return 1
                print(f"\n{BOLD}{CYAN}👀 Watchdog daemon started (DRY-RUN){RESET}")
                print(f"{DIM}   Watching   : {src_p}{RESET}")
                print(f"{DIM}   Destination: {dst_p}{RESET}")
                if config_path:
                    print(f"{DIM}   Config      : {config_path.resolve()}{RESET}")
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
                start_watch(source, destination, verbose=args.verbose, config_path=config_path)
                return 0

        try:
            organizer = FileOrganizer(
                source=source,
                destination=destination,
                dry_run=args.dry_run,
                verbose=args.verbose,
                config_path=config_path,
            )
        except FileOrganizerError as e:
            print(f"{RED}Error: {e}{RESET}", file=sys.stderr)
            return 1

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
