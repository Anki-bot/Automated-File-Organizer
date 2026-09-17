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
