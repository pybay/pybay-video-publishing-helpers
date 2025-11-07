"""
File operations module.

Handles file verification and filename parsing/renaming for video files.
Download functionality is in file_ops_parallel.py (fast parallel version).
"""

import hashlib
import re
from pathlib import Path
from typing import Optional, Tuple


def calculate_md5(file_path: Path, chunk_size: int = 8192) -> str:
    """Calculate MD5 hash of a file."""
    md5_hash = hashlib.md5()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(chunk_size), b''):
            md5_hash.update(chunk)
    return md5_hash.hexdigest()


def verify_file(local_path: Path, expected_size: int, expected_md5: Optional[str], silent: bool = False) -> bool:
    """
    Verify downloaded file integrity.

    Args:
        local_path: Path to the local file
        expected_size: Expected file size in bytes
        expected_md5: Expected MD5 hash (optional)
        silent: If True, don't print error messages (for pre-scan)

    Returns:
        True if verification passed, False otherwise
    """
    # Check size
    actual_size = local_path.stat().st_size
    if actual_size != expected_size:
        if not silent:
            print(f"\n[ERROR] Size mismatch for {local_path.name}! Expected: {expected_size}, Got: {actual_size}")
        return False

    # Check MD5 if available
    if expected_md5:
        actual_md5 = calculate_md5(local_path)
        if actual_md5 != expected_md5:
            if not silent:
                print(f"\n[ERROR] MD5 mismatch for {local_path.name}! Expected: {expected_md5}, Got: {actual_md5}")
            return False

    return True


def parse_time_from_filename(filename: str) -> Optional[Tuple[int, str]]:
    """
    Parse time from filename and return (sortable_int, original_time_str).

    Examples:
        '1145am' -> (1145, '1145am')
        '600pm' -> (1800, '600pm')
        '12:30pm' -> (1230, '12:30pm')

    Args:
        filename: Filename containing time information

    Returns:
        Tuple of (sortable_time_int, original_time_str) or None if no time found
    """
    # Match patterns like: 1145am, 600pm, 12:30pm, 1-45am, etc.
    pattern = r'(\d{1,2})[:.-]?(\d{2})?\s*(am|pm)'
    match = re.search(pattern, filename, re.IGNORECASE)

    if not match:
        return None

    hour = int(match[1])
    minute = int(match[2]) if match[2] else 0
    period = match[3].lower()
    original = match[0]

    # Convert to 24-hour for sorting
    if period == 'pm' and hour != 12:
        hour += 12
    elif period == 'am' and hour == 12:
        hour = 0

    sortable = hour * 100 + minute
    return sortable, original


def rename_with_sorted_time(filename: str) -> str:
    """
    Rename file with properly formatted time for natural sorting.

    Uses 24-hour format (e.g., "1800") for correct chronological sorting.

    Args:
        filename: Original filename

    Returns:
        New filename with formatted time in 24-hour format
    """
    time_info = parse_time_from_filename(filename)
    if not time_info:
        print(f"  [WARNING] Could not parse time from: {filename}")
        return filename

    sortable_time, original_time = time_info
    hour_24 = sortable_time // 100
    minute = sortable_time % 100

    # Always use 24-hour format: "Fisher - 1800 - Acosta..."
    new_time = f"{hour_24:02d}{minute:02d}"

    # Replace the original time string with new formatted version
    # Use regex to find and replace the time portion
    pattern = r'(\s*-\s*)?' + re.escape(original_time) + r'(\s*-\s*)?'
    return re.sub(pattern, f' - {new_time} - ', filename, count=1)


def determine_filename(original_name: str, rename_enabled: bool) -> Tuple[str, bool]:
    """
    Determine the final filename based on rename settings.

    Args:
        original_name: Original filename from Google Drive
        rename_enabled: Whether renaming is enabled

    Returns:
        Tuple of (final_filename, was_renamed)
    """
    if not rename_enabled:
        return original_name, False

    new_name = rename_with_sorted_time(original_name)
    was_renamed = (new_name != original_name)
    return new_name, was_renamed
