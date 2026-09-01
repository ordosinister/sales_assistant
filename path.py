"""Path resolution utilities for the LME report skill.

Provides helpers to locate the repository root and resolve relative
file paths within the project.
"""

import sys
import os
from pathlib import Path


def get_project_dir() -> str:
    """Get the absolute path to the repository root.

    The function resolves the root by resolving from
    sales_assistant/path.py.

    Returns:
        str: Absolute path to the repository root directory.
    """
    project_directory = str(Path(__file__).resolve().parents[0])
    return project_directory


def get_file(relative_path: str) -> str:
    """Resolve a project-relative path to an absolute path.

    Args:
        relative_path: Path relative to the repository root.

    Returns:
        str: Normalized absolute path.
    """
    return os.path.normpath(os.path.join(get_project_dir(), relative_path))
