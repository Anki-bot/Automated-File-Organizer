"""
config.py — Central configuration for file-type to folder mapping.

Uses only standard library. All extensions are stored lowercase with leading dot.
Universal Fallback: ANY unrecognized extension or file with no extension
is automatically routed to FALLBACK_CATEGORY ("Miscellaneous").
"""

from pathlib import Path

# Primary mapping: extension -> category folder name
# Robust coverage across 6+ standard groups as required.
EXTENSION_MAP: dict[str, str] = {
    # --- Documents ---
    ".pdf": "Documents",
    ".doc": "Documents",
    ".docx": "Documents",
    ".txt": "Documents",
    ".rtf": "Documents",
    ".odt": "Documents",
    ".xls": "Documents",
    ".xlsx": "Documents",
    ".csv": "Documents",
    ".ppt": "Documents",
    ".pptx": "Documents",
    ".md": "Documents",
    ".tex": "Documents",
    ".epub": "Documents",
    ".pages": "Documents",
    ".numbers": "Documents",
    ".key": "Documents",

    # --- Images ---
    ".jpg": "Images",
    ".jpeg": "Images",
    ".png": "Images",
    ".gif": "Images",
    ".bmp": "Images",
    ".tiff": "Images",
    ".tif": "Images",
    ".webp": "Images",
    ".svg": "Images",
    ".ico": "Images",
    ".heic": "Images",
    ".raw": "Images",
    ".psd": "Images",
    ".ai": "Images",
    ".eps": "Images",
    ".cr2": "Images",
    ".nef": "Images",

    # --- Videos ---
    ".mp4": "Videos",
    ".mkv": "Videos",
    ".avi": "Videos",
    ".mov": "Videos",
    ".wmv": "Videos",
    ".flv": "Videos",
    ".webm": "Videos",
    ".m4v": "Videos",
    ".mpg": "Videos",
    ".mpeg": "Videos",
    ".3gp": "Videos",
    ".mts": "Videos",
    ".m2ts": "Videos",

    # --- Audio ---
    ".mp3": "Audio",
    ".wav": "Audio",
    ".flac": "Audio",
    ".aac": "Audio",
    ".ogg": "Audio",
    ".wma": "Audio",
    ".m4a": "Audio",
    ".aiff": "Audio",
    ".opus": "Audio",
    ".alac": "Audio",
    ".mid": "Audio",
    ".midi": "Audio",

    # --- Archives ---
    ".zip": "Archives",
    ".rar": "Archives",
    ".tar": "Archives",
    ".gz": "Archives",
    ".7z": "Archives",
    ".bz2": "Archives",
    ".xz": "Archives",
    ".iso": "Archives",
    ".dmg": "Archives",
    ".pkg": "Archives",
    ".zst": "Archives",
    ".lz4": "Archives",

    # --- Executables / Installers ---
    ".exe": "Executables",
    ".msi": "Executables",
    ".bat": "Executables",
    ".appimage": "Executables",
    ".apk": "Executables",
    ".deb": "Executables",
    ".rpm": "Executables",
    ".run": "Executables",
    ".bin": "Executables",

    # --- Code ---
    ".py": "Code",
    ".js": "Code",
    ".ts": "Code",
    ".jsx": "Code",
    ".tsx": "Code",
    ".java": "Code",
    ".c": "Code",
    ".cpp": "Code",
    ".h": "Code",
    ".hpp": "Code",
    ".cs": "Code",
    ".go": "Code",
    ".rs": "Code",
    ".rb": "Code",
    ".php": "Code",
    ".swift": "Code",
    ".kt": "Code",
    ".kts": "Code",
    ".html": "Code",
    ".htm": "Code",
    ".css": "Code",
    ".scss": "Code",
    ".json": "Code",
    ".xml": "Code",
    ".yaml": "Code",
    ".yml": "Code",
    ".toml": "Code",
    ".ini": "Code",
    ".cfg": "Code",
    ".sql": "Code",
    ".sh": "Code",
    ".bash": "Code",
    ".zsh": "Code",
    ".ipynb": "Code",
    ".r": "Code",
    ".dart": "Code",
    ".lua": "Code",
    ".pl": "Code",
}

# Fallback category for unknown extensions or files without extension
# This is the Universal Fallback — guarantees EVERY file is sortable.
# Accepted aliases in spec: "Others" or "Miscellaneous" — we use "Miscellaneous"
# and expose "Others" as an alias for compatibility.
FALLBACK_CATEGORY = "Miscellaneous"
OTHERS_ALIAS = "Others"  # alias, not used as folder but recognized if present

# Derived set of all target folder names (for skipping during scan)
CATEGORY_FOLDERS: set[str] = set(EXTENSION_MAP.values()) | {FALLBACK_CATEGORY}

# History file name for undo engine
HISTORY_FILENAME = ".organizer_history.json"


def get_category(extension: str) -> str:
    """
    Return the category folder for a given file extension.

    Universal Fallback: returns FALLBACK_CATEGORY for any unrecognized
    extension or empty string (no extension).

    Args:
        extension: File extension including leading dot (e.g. '.pdf').
                   Case-insensitive; empty string for no extension.

    Returns:
        Category folder name, or 'Miscellaneous' if not mapped.
    """
    if not extension:
        return FALLBACK_CATEGORY
    # Normalize: ensure leading dot, lowercase
    ext = extension.lower()
    if not ext.startswith("."):
        ext = f".{ext}"
    return EXTENSION_MAP.get(ext, FALLBACK_CATEGORY)


def get_category_for_path(file_path: Path) -> str:
    """
    Convenience wrapper that extracts suffix from a Path object.

    Handles files with no suffix or unknown suffix via universal fallback.
    Uses Path.suffix which returns '' for no extension.
    """
    return get_category(file_path.suffix)


# ------------------------------------------------------------------ #
# Custom Configuration Helpers
# ------------------------------------------------------------------ #

def get_default_config_dict() -> dict[str, list[str]]:
    """
    Invert EXTENSION_MAP to produce category -> [extensions] mapping.

    Used for --generate-config to emit a template JSON that users can edit.
    Extensions are sorted for deterministic output.
    """
    from collections import defaultdict

    inverted: dict[str, list[str]] = defaultdict(list)
    for ext, cat in EXTENSION_MAP.items():
        inverted[cat].append(ext)
    # Sort extensions and categories for stable output
    return {cat: sorted(exts) for cat, exts in sorted(inverted.items())}


def sanitize_extension(raw_ext: str) -> tuple[str | None, bool]:
    """
    Sanitize a single extension string.

    - Strips whitespace
    - Lowercases
    - Adds leading dot if missing (e.g., "mp4" -> ".mp4")
    - Validates non-empty after sanitization

    Returns:
        (sanitized_ext_or_None, was_sanitized) — sanitized flag True if dot was auto-added
        or case was normalized; None if invalid/empty and should be skipped.
    """
    if not isinstance(raw_ext, str):
        return None, False
    ext = raw_ext.strip().lower()
    if not ext:
        return None, False
    was_sanitized = False
    if not ext.startswith("."):
        ext = f".{ext}"
        was_sanitized = True
    elif raw_ext != ext:
        # case normalization or whitespace already handled
        was_sanitized = raw_ext.strip() != ext or raw_ext.lower() != raw_ext
    # Basic validation: after dot should have at least one alphanum char
    if len(ext) < 2 or ext == ".":
        return None, False
    return ext, was_sanitized


def load_custom_config(path: Path | str) -> tuple[dict[str, str], set[str]]:
    """
    Load and sanitize a user-provided JSON config file.

    Expected JSON format:
        {
            "CategoryA": [".ext1", ".ext2"],
            "Category B": ["mp4", ".mkv"]   # dot auto-added if missing
        }

    Completely overrides the default EXTENSION_MAP when used.

    Args:
        path: Path to .json file.

    Returns:
        (extension_map, category_folders) — extension_map is ext->category,
        category_folders is set of category names.

    Raises:
        FileNotFoundError, ValueError, OSError with helpful messages.
    """
    import json

    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config file not found: {p}")
    if not p.is_file():
        raise ValueError(f"Config path is not a file: {p}")

    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in config file {p}: {exc}") from exc
    except OSError as exc:
        raise OSError(f"Cannot read config file {p}: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"Config JSON must be an object mapping category -> [extensions], got {type(data).__name__}")

    if not data:
        raise ValueError(f"Config JSON is empty: {p}")

    extension_map: dict[str, str] = {}
    category_folders: set[str] = set()
    warnings: list[str] = []

    for category, exts in data.items():
        if not isinstance(category, str) or not category.strip():
            warnings.append(f"Skipping invalid category name: {category!r}")
            continue
        cat = category.strip()
        # Keep original casing for folder name, but strip whitespace
        if not isinstance(exts, (list, tuple)):
            raise ValueError(f"Category {cat!r} must map to a list of extensions, got {type(exts).__name__}")

        if not exts:
            warnings.append(f"Category {cat!r} has no extensions — will be ignored")
            continue

        category_folders.add(cat)
        for raw_ext in exts:
            sanitized, was_sanitized = sanitize_extension(raw_ext) if isinstance(raw_ext, str) else (None, False)
            if sanitized is None:
                warnings.append(f"Skipping invalid extension {raw_ext!r} in category {cat!r}")
                continue
            if was_sanitized:
                warnings.append(f"Sanitized {raw_ext!r} -> {sanitized!r} in category {cat!r}")
            # Deduplicate: last category wins if same extension appears twice
            if sanitized in extension_map and extension_map[sanitized] != cat:
                warnings.append(f"Extension {sanitized!r} remapped from {extension_map[sanitized]!r} to {cat!r}")
            extension_map[sanitized] = cat

    if not extension_map:
        raise ValueError(f"No valid extensions found in config file {p}")

    # Caller can inspect warnings via returned data; we also expose them via attribute
    # For now return; detailed warnings are printed by the caller with colors
    # Attach warnings for introspection if needed
    load_custom_config.warnings = warnings  # type: ignore
    return extension_map, category_folders


def generate_template_config(destination: Path | str = "organizer_config.json") -> Path:
    """
    Create a template organizer_config.json in the given location.

    Writes the default inverted mapping (category -> [exts]) as pretty JSON.

    Returns:
        Path to created file.
    """
    import json

    dest = Path(destination)
    template = get_default_config_dict()
    # Ensure parent exists
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(template, f, indent=2, sort_keys=True)
        f.write("\n")
    return dest
