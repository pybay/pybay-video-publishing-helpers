"""
Path utilities module.

Handles path conversion (especially Windows to WSL) and validation
for cross-platform compatibility.
"""

import os
import sys
import re
import subprocess
from pathlib import Path
from typing import Optional


def convert_windows_path_to_wsl(path_str: str) -> str:
    """
    Convert Windows path to WSL path if needed.

    Uses WSL's built-in wslpath utility if available, falls back to manual conversion.

    Examples:
        C:\\Users\\chris\\Downloads -> /mnt/c/Users/chris/Downloads
        "C:\\Users\\chris\\Downloads" -> /mnt/c/Users/chris/Downloads
        /mnt/c/... -> /mnt/c/... (unchanged)

    Args:
        path_str: Path string (Windows or WSL format)

    Returns:
        WSL-compatible path string
    """
    # Remove surrounding quotes if present
    path_str = path_str.strip().strip('"').strip("'")

    # Check if it's a Windows path (C:\... or D:\... etc)
    windows_path_pattern = r'^([A-Za-z]):[/\\](.*)$'
    match = re.match(windows_path_pattern, path_str)

    if match:
        # Try using WSL's built-in wslpath utility first
        try:
            result = subprocess.run(
                ['wslpath', path_str],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                wsl_path = result.stdout.strip()
                print(f"[INFO] Converted Windows path to WSL: {wsl_path}")
                return wsl_path
        except (FileNotFoundError, subprocess.TimeoutExpired):
            # wslpath not available or timed out, fall back to manual conversion
            pass

        # Manual conversion fallback
        drive_letter = match.group(1).lower()
        rest_of_path = match.group(2)
        # Convert backslashes to forward slashes
        rest_of_path = rest_of_path.replace('\\', '/')
        wsl_path = f"/mnt/{drive_letter}/{rest_of_path}"
        print(f"[INFO] Converted Windows path to WSL: {wsl_path}")
        return wsl_path

    return path_str


def validate_download_path(path_str: str) -> Path:
    """
    Validate and return Path object for download location.

    Automatically converts Windows paths to WSL format if running in WSL.

    Args:
        path_str: Path string to validate

    Returns:
        Validated Path object
    """
    # Convert Windows path to WSL if needed
    path_str = convert_windows_path_to_wsl(path_str)

    path = Path(path_str).expanduser().resolve()

    # Check if path exists
    if not path.exists():
        print(f"\nPath does not exist: {path}")
        create = input("Would you like to create this directory? (y/n): ").strip().lower()
        if create == 'y':
            try:
                path.mkdir(parents=True, exist_ok=True)
                print(f"[OK] Created directory: {path}")
            except Exception as e:
                print(f"ERROR: Could not create directory: {e}")
                sys.exit(1)
        else:
            print("Exiting. Please provide a valid directory path.")
            sys.exit(1)

    # Check if it's a directory
    if not path.is_dir():
        print(f"ERROR: Path is not a directory: {path}")
        sys.exit(1)

    # Check if writable
    test_file = path / '.write_test'
    try:
        test_file.touch()
        test_file.unlink()
        print(f"[OK] Download location validated: {path}\n")
    except Exception as e:
        print(f"ERROR: Directory is not writable: {e}")
        sys.exit(1)

    return path


def get_download_path(path_arg: Optional[str]) -> Path:
    """
    Get and validate download path from argument or user input.

    Args:
        path_arg: Path from command-line argument, or None to prompt user

    Returns:
        Validated Path object for download destination
    """
    if path_arg:
        return validate_download_path(path_arg)
    else:
        path_input = input("Enter download destination path: ").strip()
        return validate_download_path(path_input)
