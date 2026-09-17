"""
File Organizer Package
A portfolio-grade CLI tool for automated file organization.
"""

from .core import FileOrganizer
from .config import CATEGORY_FOLDERS, EXTENSION_MAP, FALLBACK_CATEGORY, HISTORY_FILENAME, get_category

__all__ = [
    "FileOrganizer",
    "EXTENSION_MAP",
    "CATEGORY_FOLDERS",
    "FALLBACK_CATEGORY",
    "HISTORY_FILENAME",
    "get_category",
]
__version__ = "1.0.0"
