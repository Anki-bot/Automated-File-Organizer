#!/usr/bin/env python3
"""
main.py — CLI entry point for Automated File Organizer.

Usage:
    python main.py --source ./Downloads --dry-run
    python main.py --source ./messy --destination ./organized
    python main.py --help
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure package import works when running as script
sys.path.insert(0, str(Path(__file__).parent))

from organizer.core import RED, RESET, YELLOW, FileOrganizer, FileOrganizerError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="file-organizer",
        description="Automated File Organizer — sort files into categorized folders safely.",
        epilog="Example: python main.py --source ./Downloads --dry-run",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--source",
        "-s",
        type=str,
        default=".",
        help="Source directory to scan (default: current directory '.')",
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
        help="Preview file movements without actually moving anything (mandatory UX feature)",
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
        version="%(prog)s 1.0.0",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    source = Path(args.source)
    destination = Path(args.destination) if args.destination else None

    try:
        organizer = FileOrganizer(
            source=source,
            destination=destination,
            dry_run=args.dry_run,
            verbose=args.verbose,
        )
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
