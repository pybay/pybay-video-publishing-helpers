#!/usr/bin/env python3
"""
Fetch Google Drive Folder Metadata

Fetches file list from a Google Drive folder and saves metadata without downloading files.
This creates an audit trail of original filenames and file properties.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict

# Add parent directory to path to import our modules
sys.path.insert(0, str(Path(__file__).parent))

from google_drive_ops import get_drive_service, save_folder_metadata, extract_folder_id as extract_folder_id_ops


def fetch_folder_metadata(folder_id: str, service) -> Dict:
    """
    Fetch metadata for all files in a Google Drive folder.

    Args:
        folder_id: Google Drive folder ID
        service: Authenticated Google Drive service

    Returns:
        Dict with folder info and file list
    """
    print(f"Fetching file list from folder: {folder_id}", file=sys.stderr)

    # List files in folder
    files = list_video_files(service, folder_id)

    print(f"Found {len(files)} files", file=sys.stderr)

    # Build metadata structure
    metadata = {
        'folder_id': folder_id,
        'fetch_timestamp': datetime.now().isoformat(),
        'file_count': len(files),
        'files': []
    }

    for file_info in files:
        file_entry = {
            'id': file_info['id'],
            'name': file_info['name'],
            'size': file_info.get('size', 0),
            'mimeType': file_info.get('mimeType', ''),
            'md5Checksum': file_info.get('md5Checksum', None),
            'createdTime': file_info.get('createdTime', None),
            'modifiedTime': file_info.get('modifiedTime', None)
        }
        metadata['files'].append(file_entry)
        print(f"  {file_entry['name']} ({file_entry['size']} bytes)", file=sys.stderr)

    return metadata


def main():
    parser = argparse.ArgumentParser(
        description='Fetch Google Drive folder metadata without downloading files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fetch metadata from folder URL
  python src/google_drive_fetch_metadata.py --folder "https://drive.google.com/drive/folders/1-O4o..."

  # Fetch metadata using folder ID directly
  python src/google_drive_fetch_metadata.py --folder "1-O4oGLkeIFqZ8WJ3TexH0h0EVeaBJ_hc"

  # Save to custom location
  python src/google_drive_fetch_metadata.py --folder "1-O4o..." --output /path/to/metadata.json
        """
    )

    parser.add_argument(
        '--folder',
        type=str,
        required=True,
        help='Google Drive folder URL or ID'
    )

    parser.add_argument(
        '--year',
        type=int,
        help='PyBay year (e.g., 2025) for filename (default: current year)'
    )

    parser.add_argument(
        '--output',
        type=str,
        help='Output JSON file path (default: pybay_yt_video_download_dir/_pybay_{year}_gdrive_metadata.json)'
    )

    parser.add_argument(
        '--service-account',
        action='store_true',
        help='Use service account authentication (auto-detected if env var exists)'
    )

    parser.add_argument(
        '--service-account-env',
        type=str,
        default='GOOGLE_DRIVE_API_KEY_PYBAY',
        help='Environment variable name for service account JSON'
    )

    args = parser.parse_args()

    # Extract folder ID
    folder_id = extract_folder_id_ops(args.folder)
    print(f"Folder ID: {folder_id}", file=sys.stderr)

    # Determine year
    if args.year:
        pybay_year = args.year
    else:
        from datetime import datetime
        pybay_year = datetime.now().year

    print(f"PyBay Year: {pybay_year}", file=sys.stderr)

    # Authenticate
    print("Authenticating...", file=sys.stderr)
    service = get_drive_service(
        use_service_account=args.service_account,
        env_var=args.service_account_env
    )

    # Determine output directory
    if args.output:
        output_path = Path(args.output)
        destination_dir = output_path.parent
    else:
        destination_dir = Path('pybay_yt_video_download_dir')

    # Ensure directory exists
    destination_dir.mkdir(parents=True, exist_ok=True)

    # Save metadata using the common function
    if args.output:
        # Custom output path - call function and then move file
        temp_dest = Path('.')
        metadata_path = save_folder_metadata(service, folder_id, temp_dest, pybay_year)
        metadata_path.rename(output_path)
        print(f"\n[OK] Moved to: {output_path}", file=sys.stderr)
    else:
        # Default location
        metadata_path = save_folder_metadata(service, folder_id, destination_dir, pybay_year)
        print(f"\n[OK] Saved to: {metadata_path}", file=sys.stderr)


if __name__ == '__main__':
    main()
