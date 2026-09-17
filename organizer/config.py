"""
config.py — Central configuration for file-type to folder mapping.

Uses only standard library. All extensions are stored lowercase with leading dot.
"""

from pathlib import Path

# Primary mapping: extension -> category folder name
EXTENSION_MAP: dict[str, str] = {
    # Documents
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

    # Images
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

    # Videos
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

    # Audio
    ".mp3": "Audio",
    ".wav": "Audio",
    ".flac": "Audio",
    ".aac": "Audio",
    ".ogg": "Audio",
    ".wma": "Audio",
    ".m4a": "Audio",
    ".aiff": "Audio",
    ".opus": "Audio",

    # Archives
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

    # Executables / Installers
    ".exe": "Executables",
    ".msi": "Executables",
    ".sh": "Executables",
    ".bat": "Executables",
    ".appimage": "Executables",
    ".apk": "Executables",
    ".deb": "Executables",

    # Code
    ".py": "Code",
    ".js": "Code",
    ".ts": "Code",
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
    ".html": "Code",
    ".htm": "Code",
    ".css": "Code",
    ".json": "Code",
    ".xml": "Code",
    ".yaml": "Code",
    ".yml": "Code",
    ".toml": "Code",
    ".sql": "Code",
    ".sh": "Code",
    ".ipynb": "Code",

    # Spreadsheets (also Documents but explicit override is not needed)
    # Designated as Documents already; kept for clarity no duplication.

    # Fonts
    ".ttf": "Fonts",
    ".otf": "Fonts",
    ".woff": "Fonts",
    ".woff2": "Fonts",
}

# Fallback category for unknown extensions or files without extension
FALLBACK_CATEGORY = "Miscellaneous"

# Derived set of all target folder names (for skipping during scan)
CATEGORY_FOLDERS: set[str] = set(EXTENSION_MAP.values()) | {FALLBACK_CATEGORY}


def get_category(extension: str) -> str:
    """
    Return the category folder for a given file extension.

    Args:
        extension: File extension including leading dot (e.g. '.pdf').
                   Case-insensitive; empty string for no extension.

    Returns:
        Category folder name, or 'Miscellaneous' if not mapped.
    """
    if not extension:
        return FALLBACK_CATEGORY
    return EXTENSION_MAP.get(extension.lower(), FALLBACK_CATEGORY)


def get_category_for_path(file_path: Path) -> str:
    """Convenience wrapper that extracts suffix from a Path object."""
    return get_category(file_path.suffix)
