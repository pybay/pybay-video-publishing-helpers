#!/usr/bin/env python3
"""
PyBay Video Renamer v2 - Token-Based Matching

Uses JSON metadata as the source of truth and matches video files using tokens.

Approach:
1. Load structured metadata from JSON
2. For each JSON entry, search for video files with matching tokens (room + time)
3. For unmatched files, attempt best-effort parsing from filename
4. Generate new filenames in format: {title} — {name} (PyBay {year}).ext
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import subprocess


def extract_year_from_url(url: str) -> int:
    """Extract year from PyBay URL."""
    match = re.search(r'(\d{4})/?$', url.strip())
    if match:
        return int(match.group(1))
    raise ValueError(f"Could not extract year from URL: {url}")


def fetch_talk_metadata(year: int, url: str, destination: Path) -> Path:
    """Run scraper_pybayorg_talk_metadata.py to fetch talk metadata."""
    json_filename = f"_pybay_{year}_talk_data.json"
    json_path = destination / json_filename

    print(f"Fetching talk metadata from {url}...", file=sys.stderr)

    result = subprocess.run([
        sys.executable,
        'src/scraper_pybayorg_talk_metadata.py',
        '--url', url,
        '--output', str(json_path),
        '--format', 'json'
    ], capture_output=True, text=True)

    if result.returncode != 0:
        print(f"[ERROR] Failed to fetch metadata:", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(1)

    print(result.stderr, file=sys.stderr)
    return json_path


def load_talk_metadata(json_path: Path) -> List[Dict]:
    """Load talk metadata from JSON file."""
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def normalize_time_to_24h(time_str: str) -> str:
    """
    Convert time to 24-hour format for matching.

    Examples:
        "10:00 am" -> "1000"
        "2:30 pm" -> "1430"
        "1000" -> "1000"
        "1430" -> "1430"
    """
    # Extract digits
    digits = re.sub(r'[^\d]', '', time_str)

    if not digits:
        return ""

    # Determine AM/PM
    am_pm = 'am' if 'am' in time_str.lower() else 'pm' if 'pm' in time_str.lower() else None

    # Parse hour and minute
    # For times like "2:30" we get "230", need to parse correctly
    if len(digits) == 4:
        # Already 24-hour format like "1430" or "10:00" -> "1000"
        hour = int(digits[:2])
        minute = int(digits[2:4])
    elif len(digits) == 3:
        # Could be "2:30" -> "230" or "9:00" -> "900" or "230" (2:30pm without colon)
        # Check if there's a colon in original string
        if ':' in time_str:
            # It's like "2:30" -> hour is 1 digit
            hour = int(digits[0])
            minute = int(digits[1:3])
        else:
            # It's like "230" or "900" without colon
            # Heuristic: if first digit is 0-2, it's probably H:MM (e.g., "230" = 2:30)
            # If first digit is 9, it's probably HH:M (e.g., "900" = 9:00)
            first_digit = int(digits[0])
            if first_digit <= 2:
                # Treat as H:MM (e.g., "230" = 2:30pm)
                hour = first_digit
                minute = int(digits[1:3])
            else:
                # Treat as H:MM for 3-9 range too (e.g., "315" = 3:15)
                hour = first_digit
                minute = int(digits[1:3])
    elif len(digits) == 2:
        # Just hour like "10" or "09"
        hour = int(digits)
        minute = 0
    elif len(digits) == 1:
        # Single digit hour like "9"
        hour = int(digits)
        minute = 0
    else:
        # Fallback
        hour = int(digits[:2])
        minute = 0

    # Convert to 24-hour if we have AM/PM
    if am_pm:
        if am_pm == 'pm' and hour != 12:
            hour += 12
        elif am_pm == 'am' and hour == 12:
            hour = 0

    return f"{hour:02d}{minute:02d}"


def format_time_for_filename(time_str: str) -> str:
    """
    Format time for use in filename.

    Examples:
        "10:00 am" -> "1000am"
        "2:30 pm" -> "1430pm" (but we'll use 1430am format)
    """
    time_24h = normalize_time_to_24h(time_str)
    if not time_24h:
        return ""

    hour = int(time_24h[:2])
    minute = time_24h[2:]

    # Determine am/pm from 24-hour
    am_pm = 'am' if hour < 12 else 'pm'

    return f"{time_24h}{am_pm}"


def extract_tokens_from_filename(filename: str) -> Dict[str, str]:
    """
    Extract searchable tokens from filename.

    Returns dict with: room, time, lastname, extension, and original filename

    Expected format: {Room} - {Time} - {LastName} - {Title}.ext
    Example: Robertson - 1000 - Brousseau - Welcome Remarks.mp4
    """
    # Remove extension
    name_without_ext = Path(filename).stem
    extension = Path(filename).suffix[1:]  # Remove leading dot

    # Extract time - matches various formats:
    # - Pure digits: "1000", "230"
    # - With am/pm: "10am", "230PM", "10Am", "230Pm"
    # - With colon: "6:30PM", "10:00am", "14:30" (24-hour European)
    time_match = re.search(r'\b(\d{1,2}:?\d{0,2}\s?(?:am|pm|AM|PM|Am|Pm|aM|pM)?)\b', name_without_ext, re.IGNORECASE)
    time_token = time_match.group(1) if time_match else None

    # Extract room (typically first word before " - ")
    room_match = re.match(r'^([^-]+?)\s*-', name_without_ext)
    room_token = room_match.group(1).strip() if room_match else None

    # Extract lastname (word after time, before title)
    # Pattern: Room - Time - LastName - Title
    # Note: LastName can contain hyphens (e.g., "Hatfield-Dodds")
    lastname_token = None
    if time_token:
        # Match pattern after the time: " - {LastName} - "
        # Use lookahead to match until we hit " - " (not just "-")
        lastname_pattern = rf'\b{time_token}\b\s*-\s*(.+?)\s+-\s+'
        lastname_match = re.search(lastname_pattern, name_without_ext)
        if lastname_match:
            lastname_token = lastname_match.group(1).strip()

    return {
        'filename': filename,
        'room': room_token,
        'time': time_token,
        'lastname': lastname_token,
        'extension': extension,
        'name_without_ext': name_without_ext
    }


def find_video_for_talk(talk: Dict, video_files: List[Path]) -> Optional[Path]:
    """
    Find video file matching this talk using token-based search.

    Matches on: room (case-insensitive) + time (24-hour normalized) + name verification

    Name verification: At least one of firstname OR lastname must match (case-insensitive partial match)
    """
    talk_room = talk['room'].lower()
    talk_time_24h = normalize_time_to_24h(talk['start_time'])

    # Handle both old format (firstname/lastname) and new format (speakers array)
    talk_speakers = []
    if 'speakers' in talk and isinstance(talk['speakers'], list):
        # New format - array of speakers
        for speaker in talk['speakers']:
            talk_speakers.append({
                'firstname': speaker.get('firstname', '').lower(),
                'lastname': speaker.get('lastname', '').lower()
            })
    else:
        # Old format - backwards compatibility
        talk_speakers.append({
            'firstname': talk.get('firstname', '').lower(),
            'lastname': talk.get('lastname', '').lower()
        })

    for video_path in video_files:
        tokens = extract_tokens_from_filename(video_path.name)

        # Skip if already processed (starts with underscore or has new naming pattern)
        if video_path.name.startswith('_') or ' — ' in video_path.name:
            continue

        # Match room
        if tokens['room'] and tokens['room'].lower() != talk_room:
            continue

        # Match time
        if tokens['time']:
            video_time_24h = normalize_time_to_24h(tokens['time'])
            if video_time_24h != talk_time_24h:
                continue
        else:
            continue  # Can't match without time

        # Verify name - at least one speaker's name should match
        # This prevents mismatches when two talks are in same room at same time (rare but possible)
        video_lastname_raw = tokens.get('lastname')
        video_lastname = (video_lastname_raw or '').lower() if video_lastname_raw is not None else ''

        name_matches = False

        # Check if ANY speaker matches the video filename
        for speaker in talk_speakers:
            talk_firstname = speaker['firstname']
            talk_lastname = speaker['lastname']

            if video_lastname and talk_lastname and talk_lastname != '.':
                # Check if talk lastname appears in video lastname (handles multi-part names like "van Rossum")
                if talk_lastname in video_lastname or video_lastname in talk_lastname:
                    name_matches = True
                    break

            # If we have firstname in talk metadata, check that too
            if not name_matches and talk_firstname and video_lastname:
                # Sometimes firstname might appear in the lastname position
                if talk_firstname in video_lastname or video_lastname in talk_firstname:
                    name_matches = True
                    break

        # If no lastname extracted from video, or no name data in any speaker, accept the match
        # (backwards compatible with files that don't have clear name structure)
        if not video_lastname:
            name_matches = True
        elif not any(s['firstname'] or s['lastname'] for s in talk_speakers):
            name_matches = True

        if name_matches:
            # Found a match!
            return video_path

    return None


def generate_new_filename(talk: Dict, year: int, extension: str) -> str:
    """
    Generate new filename from talk metadata.

    Format: {talk_title} — {speaker1} & {speaker2} & ... ({year}).{ext}

    Handles both old format (firstname/lastname keys) and new format (speakers array)
    """
    talk_title = talk['talk_title']

    # Check if using new speakers array format
    if 'speakers' in talk and isinstance(talk['speakers'], list):
        # New format with speakers array
        speaker_names = []
        for speaker in talk['speakers']:
            firstname = speaker.get('firstname', '')
            lastname = speaker.get('lastname', '')

            # Build individual speaker name
            name_parts = []
            if firstname:
                name_parts.append(firstname)
            if lastname and lastname != '.':
                name_parts.append(lastname)

            if name_parts:
                speaker_names.append(' '.join(name_parts))

        # Join multiple speakers with " & "
        speaker_name = ' & '.join(speaker_names) if speaker_names else 'Unknown Speaker'
    else:
        # Old format with firstname/lastname keys (backwards compatibility)
        firstname = talk.get('firstname', '')
        lastname = talk.get('lastname', '')

        name_parts = []
        if firstname:
            name_parts.append(firstname)
        if lastname and lastname != '.':
            name_parts.append(lastname)

        speaker_name = ' '.join(name_parts) if name_parts else 'Unknown Speaker'

    # Build new filename using em dash (—)
    new_filename = f"{talk_title} — {speaker_name} (PyBay {year}).{extension}"

    # Sanitize filename (remove invalid characters for filesystems)
    # Windows doesn't allow: < > : " / \ | ? *
    new_filename = re.sub(r'[<>:"/\\|?*]', '', new_filename)

    return new_filename


def create_rename_mapping_from_json(
    talks: List[Dict],
    video_dir: Path,
    year: int
) -> Tuple[Dict[str, str], List[str], List[Path]]:
    """
    Create rename mapping using JSON as source of truth.

    Returns:
        - rename_map: Dict[old_filename, new_filename] for matched files
        - skipped_talks: List of talk titles that had no matching video file
        - unmatched_files: List of video files that didn't match any talk
    """
    # Get all video files
    video_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.webm']
    video_files = []

    for ext in video_extensions:
        video_files.extend(video_dir.glob(f'*{ext}'))
        video_files.extend(video_dir.glob(f'*{ext.upper()}'))

    # Filter out already-renamed files and already-flagged files
    # Skip files starting with _ (metadata) or ! (flagged for review) or containing — (already renamed)
    video_files = [v for v in video_files if not (v.name.startswith(('_', '!')) or ' — ' in v.name)]

    print(f"\nFound {len(video_files)} video files to process", file=sys.stderr)
    print(f"Loaded {len(talks)} talks from metadata\n", file=sys.stderr)

    rename_map = {}
    matched_files = set()
    skipped_talks = []

    # Iterate through talks and find matching video files
    for talk in talks:
        video_path = find_video_for_talk(talk, video_files)

        if video_path:
            tokens = extract_tokens_from_filename(video_path.name)
            new_filename = generate_new_filename(talk, year, tokens['extension'])

            rename_map[video_path.name] = new_filename
            matched_files.add(video_path)

            print(f"[MATCH] {video_path.name}", file=sys.stderr)
            print(f"     -> {new_filename}", file=sys.stderr)
        else:
            skipped_talks.append(talk['talk_title'])
            print(f"[NO VIDEO] {talk['room']} - {talk['start_time']} - {talk['talk_title']}", file=sys.stderr)

    # Find unmatched video files and flag them for review
    unmatched_files = [v for v in video_files if v not in matched_files]

    if unmatched_files:
        print(f"\n[WARNING] {len(unmatched_files)} video files did not match any talk in JSON:", file=sys.stderr)
        for video in unmatched_files:
            print(f"  - {video.name}", file=sys.stderr)

            # Add unmatched files to rename_map with [REVIEW_NEEDED] prefix
            # Using "!" prefix to sort first (! comes before letters and numbers in ASCII)
            if not video.name.startswith('![REVIEW_NEEDED]_'):
                new_name = f"![REVIEW_NEEDED]_{video.name}"
                rename_map[video.name] = new_name
                print(f"     -> Will flag for review: {new_name}", file=sys.stderr)

    print(f"\nSummary:", file=sys.stderr)
    print(f"  Matched: {len(matched_files)}", file=sys.stderr)
    print(f"  Talks without video: {len(skipped_talks)}", file=sys.stderr)
    print(f"  Videos without metadata: {len(unmatched_files)}", file=sys.stderr)

    return rename_map, skipped_talks, unmatched_files


def fix_missing_pybay_prefix(filename: str) -> Optional[str]:
    """
    Convert filenames with (YYYY) to (PyBay YYYY) format.

    Examples:
        "Some Talk — John Doe (2025).mp4" -> "Some Talk — John Doe (PyBay 2025).mp4"
        "Talk — Speaker (2024).mp4" -> "Talk — Speaker (PyBay 2024).mp4"
        "Already Fixed (PyBay 2025).mp4" -> None (no change needed)

    Args:
        filename: The filename to check

    Returns:
        New filename if conversion needed, None otherwise
    """
    # Pattern: match (YYYY).ext but NOT (PyBay YYYY).ext
    # Negative lookbehind to ensure "PyBay " is not already there
    pattern = r'\((?!PyBay\s)(\d{4})\)(\.\w+)$'

    match = re.search(pattern, filename)
    if match:
        year = match.group(1)
        extension = match.group(2)
        # Replace (YYYY) with (PyBay YYYY)
        new_filename = re.sub(pattern, rf'(PyBay {year}){extension}', filename)
        return new_filename

    return None


def check_and_fix_pybay_prefix(video_dir: Path, dry_run: bool = False) -> int:
    """
    Check for files with old (YYYY) format and convert to (PyBay YYYY).

    Args:
        video_dir: Directory containing video files
        dry_run: If True, only show what would be renamed

    Returns:
        Number of files fixed
    """
    video_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.webm']
    video_files = []

    for ext in video_extensions:
        video_files.extend(video_dir.glob(f'*{ext}'))
        video_files.extend(video_dir.glob(f'*{ext.upper()}'))

    # Filter to only files that look like they were already renamed (have em dash)
    renamed_files = [v for v in video_files if ' — ' in v.name]

    fixes_needed = []
    for video_path in renamed_files:
        new_name = fix_missing_pybay_prefix(video_path.name)
        if new_name:
            fixes_needed.append((video_path, new_name))

    if not fixes_needed:
        return 0

    print(f"\n[INFO] Found {len(fixes_needed)} files with old (YYYY) format", file=sys.stderr)

    if dry_run:
        print("[DRY RUN] Would fix the following files:", file=sys.stderr)
        for old_path, new_name in fixes_needed:
            print(f"  {old_path.name}", file=sys.stderr)
            print(f"  -> {new_name}", file=sys.stderr)
        return 0

    success_count = 0
    for old_path, new_name in fixes_needed:
        new_path = video_dir / new_name

        if new_path.exists():
            print(f"[SKIP] Target already exists: {new_name}", file=sys.stderr)
            continue

        try:
            old_path.rename(new_path)
            print(f"[FIXED] {old_path.name}", file=sys.stderr)
            print(f"     -> {new_name}", file=sys.stderr)
            success_count += 1
        except Exception as e:
            print(f"[ERROR] Failed to fix {old_path.name}: {e}", file=sys.stderr)

    return success_count


def rename_files(video_dir: Path, rename_map: Dict[str, str], dry_run: bool = False) -> None:
    """Rename video files according to mapping."""
    if dry_run:
        print("\n[DRY RUN] No files will be renamed", file=sys.stderr)
        return

    print(f"\nRenaming {len(rename_map)} files...", file=sys.stderr)

    success_count = 0
    error_count = 0

    for old_name, new_name in rename_map.items():
        old_path = video_dir / old_name
        new_path = video_dir / new_name

        # Check if target already exists
        if new_path.exists():
            print(f"[SKIP] Target already exists: {new_name}", file=sys.stderr)
            continue

        try:
            old_path.rename(new_path)
            print(f"[OK] Renamed: {old_name}", file=sys.stderr)
            success_count += 1
        except Exception as e:
            print(f"[ERROR] Failed to rename {old_name}: {e}", file=sys.stderr)
            error_count += 1

    print(f"\nCompleted: {success_count} renamed, {error_count} errors", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description='Rename PyBay video files using token-based matching with JSON metadata',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Rename videos in default directory
  python src/file_renamer.py

  # Specify custom directory
  python src/file_renamer.py --video-dir /path/to/videos

  # Dry run (show what would be renamed)
  python src/file_renamer.py --dry-run

  # Use existing metadata JSON
  python src/file_renamer.py --metadata-json pybay_yt_video_download_dir/_pybay_2025_talk_data.json
        """
    )

    parser.add_argument(
        '--video-dir',
        type=str,
        default='pybay_yt_video_download_dir',
        help='Directory containing video files (default: pybay_yt_video_download_dir)'
    )

    parser.add_argument(
        '--url',
        type=str,
        default='https://pybay.org/speaking/talk-list-2025/',
        help='PyBay talks URL (default: 2025)'
    )

    parser.add_argument(
        '--year',
        type=int,
        help='PyBay year (auto-detected from URL if not specified)'
    )

    parser.add_argument(
        '--metadata-json',
        type=str,
        help='Path to existing metadata JSON (skips fetching if provided)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be renamed without actually renaming'
    )

    args = parser.parse_args()

    # Resolve paths
    video_dir = Path(args.video_dir).expanduser()

    if not video_dir.exists():
        print(f"[ERROR] Video directory does not exist: {video_dir}", file=sys.stderr)
        sys.exit(1)

    # Determine year
    if args.year:
        year = args.year
    else:
        year = extract_year_from_url(args.url)

    print(f"PyBay Year: {year}", file=sys.stderr)
    print(f"Video Directory: {video_dir}", file=sys.stderr)

    # Load or fetch metadata
    if args.metadata_json:
        json_path = Path(args.metadata_json)
        print(f"Using existing metadata: {json_path}", file=sys.stderr)
    else:
        json_path = fetch_talk_metadata(year, args.url, video_dir)

    if not json_path.exists():
        print(f"[ERROR] Metadata file not found: {json_path}", file=sys.stderr)
        sys.exit(1)

    talks = load_talk_metadata(json_path)

    # Create rename mapping using token-based matching
    # This automatically adds "PyBay YYYY" prefix in the new filenames
    print("\n=== Renaming videos to publication format ===", file=sys.stderr)
    rename_map, skipped_talks, unmatched_files = create_rename_mapping_from_json(
        talks, video_dir, year
    )

    if not rename_map:
        print("\n[WARNING] No files to rename", file=sys.stderr)
        sys.exit(0)

    # Rename files
    rename_files(video_dir, rename_map, args.dry_run)


if __name__ == '__main__':
    main()
