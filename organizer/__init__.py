"""
File Organizer Package
A portfolio-grade CLI tool for automated file organization.
"""

from .core import FileOrganizer
from .config import EXTENSION_MAP, CATEGORY_FOLDERS, get_category

__all__ = ["FileOrganizer", "EXTENSION_MAP", "CATEGORY_FOLDERS", "get_category"]
__version__ = "1.0.0"
