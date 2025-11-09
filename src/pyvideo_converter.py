# Copyright Amethyst Reese
# Licensed under the MIT License

"""
Convert YouTube playlist metadata to PyVideo.org format.

This script converts YouTube video metadata (downloaded via yt-dlp) into the
standardized JSON format used by PyVideo.org for indexing conference talks.

To submit videos to PyVideo - the high-level process is to:
    1. Use this repo to download YT metadata and create the expected dir structure with all metadata files (JSON)
    2. Fork the PyVideo Data repository and create a new branch (e.g. `pybay-2025`)
    3. Copy the generated conference directory to your PyVideo fork
    4. In your PyVideo fork, run tests and fix any validation errors
    5. Submit a PR to PyVideo - a maintainer will merge when ready

References:
    - PyVideo Data Repository: https://github.com/pyvideo/data
    - Contributing Guide: https://github.com/pyvideo/data/blob/main/CONTRIBUTING.rst#contributing

Prerequisites:
    Install yt-dlp: pip install yt-dlp

Speaker Extraction:
    The script uses fuzzy matching to automatically extract speaker names from video titles
    by matching against the scraped PyBay metadata in `pybay_yt_video_download_dir/_pybay_2025_talk_data.json`.

    Typical results: ~90+% of videos automatically matched with 95%+ confidence.
    Videos that fail fuzzy matching are flagged in the terminal summary output so you can review them manually.

Usage:
    1. Complete video processing of original videos from the PyBay AV vendor
    2. On the PyBay YouTube Account, create a new playlist for the current PyBay year, upload videos, and publish
    3. Note the URL for the new YouTube playlist

    4. One-step: Download and convert (RECOMMENDED):
       $ python src/pyvideo_converter.py --url "https://www.youtube.com/playlist?list=PLAYLIST_ID"

       This will:
       - Clean old metadata files from pyvideo_data_dir/yt_metadata/ (preserves .gitkeep)
       - Check for yt-dlp installation
       - Download fresh YouTube metadata to pyvideo_data_dir/yt_metadata/
       - Convert to PyVideo format in pyvideo_data_dir/pybay-2025/
       - Print summary showing which videos need manual review

       Or two-step (manual yt-dlp):
       $ cd pyvideo_data_dir/yt_metadata/
       $ yt-dlp --skip-download --write-info-json <PLAYLIST-URL>
       $ cd ../..
       $ python src/pyvideo_converter.py

    5. **Review the summary output** at the end of the script run:
       The script will print a list of videos needing MANUAL REVIEW (missing speakers).
       Search for `"speakers": []` in the generated JSON files to find them.

    6. **CRITICAL: Manually review and fix the generated JSON files**
       Open pyvideo_data_dir/pybay-2025/videos/ and review each .json file:

       Common issues to fix:
       - Videos flagged with empty speakers array (typically 3-4 videos)
       - Speaker names not extracted correctly from titles (rare with fuzzy matching)
       - Talk titles containing speaker names or conference info (should be talk title only)
       - Descriptions needing conversion to valid reStructuredText (rST) format
       - Missing or incorrect metadata (tags, language, etc.)
       - Special characters that need escaping

       This is the most time-consuming step but critical for data quality.
       Do NOT skip this step - fix all issues before proceeding to PyVideo fork.

    7. Fork https://github.com/pyvideo/data and clone your fork

    8. Copy the reviewed and cleaned conference directory to your PyVideo fork:
       $ cp -r pyvideo_data_dir/pybay-2025/ /path/to/pyvideo-data-fork/

    9. In your PyVideo fork, set up the virtual environment and run tests:
       $ cd /path/to/pyvideo-data-fork/
       $ python3 -m venv .venv    # IMPORTANT -- pyvideo-data scripts REQUIRE your virtualenv to be named `.venv`
       $ source .venv/bin/activate
       $ make test

       The Makefile will automatically install test dependencies and run validation.

    10. Fix any remaining validation errors (should be minimal if step 5 was thorough)

    11. Submit a PR to https://github.com/pyvideo/data

Note: The --skip-download flag is critical - it downloads only metadata JSON files
(~5-20KB each) instead of the actual video files (potentially GBs). The resulting
PyVideo data references videos by their YouTube URLs, not local files.

Note: On re-runs, the script automatically cleans old metadata files to avoid confusion
from stale data (e.g., if YouTube titles were updated). This ensures you always work
with the latest YouTube metadata.

Known Limitations:
    - Descriptions are copied as-is from YouTube and may need manual conversion to valid
      reStructuredText (rST) format required by PyVideo
    - Recorded dates use simple date format; PyVideo prefers ISO 8601 with timezone
    - Videos with non-standard titles (e.g., "Welcome Remarks", "Lightning Talks") may
      not match fuzzy matching patterns and require manual speaker addition
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from pprint import pprint

from rapidfuzz import fuzz

SLUG_RE = re.compile(r"(\W+)")
# Match patterns like: "Talk Title — Speaker Name (PyBay 2025)"
# Also supports legacy patterns: "Title" - Speaker or "Title" by Speaker
QUOTED_TITLE_RE = re.compile(r'(?:"?(.+?)"?\s*(?:—|—|-|by)\s*(.+?)\s*\(PyBay \d{4}\)|"?(.+)"?\s*(?:-|by)\s*([\w\s"\',\-]+))')
TIMESTAMP_RE = re.compile(r"^\d+:\d\d - ")


def clamp[T](value: T, lower: T, upper: T) -> T:
    return min(max(value, lower), upper)


def parse_date(
    value: str, format: str = r"%Y-%m-%d", default: date = date.today()
) -> date:
    """
    Parse a date string into a date object.
    """
    return datetime.strptime(value, format).date() if value else default


class Sluggable:
    """Base class that generates URL-friendly slugs from titles.

    Converts titles to lowercase, replaces non-word chars with hyphens,
    and limits to first 10 words for readable filenames.
    """
    title: str

    @property
    def slug(self):
        slug = SLUG_RE.sub("-", self.title.lower()).strip("-")
        return "-".join(slug.split("-")[:10])


@dataclass
class Conference(Sluggable):
    """PyBay conference metadata for PyVideo submission.

    Contains conference-level information like playlist URLs, schedule links, and date range
    used to validate video upload dates.
    """
    title: str = "PyBay 2025"
    playlist_url: str = (
        "https://www.youtube.com/playlist?list=PL85KuAjbN_gseSuHZTUCgNAHLeKuMDBxI"
    )
    schedule_url: str = "https://pybay.org/speaking/schedule/"
    start: date = parse_date("2025-10-18")
    end: date = parse_date("2025-10-18")

    copyright_text: str = ""
    drop_first_lines: int = 0
    drop_last_lines: int = 0


@dataclass
class Talk(Sluggable):
    """Individual metadata files for each talk/video in required PyVideo format.

    Represents a single talk with all metadata required by PyVideo.org: speakers, description, video URLs, etc.
    """
    title: str = ""
    description: str = ""
    speakers: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    language: str = "eng"
    recorded: date = date.today()
    duration: int = 0
    copyright_text: str = ""
    related_urls: list[dict[str, str]] = field(default_factory=list)

    videos: list[dict[str, str]] = field(default_factory=list)
    thumbnail_url: str = ""


def check_yt_dlp() -> bool:
    """Check if yt-dlp is installed and available."""
    try:
        result = subprocess.run(
            ["yt-dlp", "--version"],
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode == 0:
            print(f"yt-dlp is installed: {result.stdout.strip()}")
            return True
        else:
            print("yt-dlp is not installed or not working. try `sudo apt install yt-dlp`")
            return False
    except FileNotFoundError:
        print("yt-dlp is not installed. try `sudo apt install yt-dlp`")
        return False


def download_youtube_metadata(playlist_url: str, output_dir: Path) -> bool:
    """
    Downloads YouTube playlist metadata using yt-dlp.
    """
    # Clean out old metadata files (keep .gitkeep)
    if output_dir.exists():
        for file in output_dir.glob("*.json"):
            if file.name != ".gitkeep":
                file.unlink()
        print(f"Cleaned old metadata files from {output_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nDownloading YouTube metadata to: {output_dir}")
    print(f"Playlist URL: {playlist_url}")
    print("\nRunning yt-dlp (this may take a few minutes)...\n")

    cmd = [
        "yt-dlp",
        "--skip-download",
        "--write-info-json",
        "--no-warnings",  # Suppress non-critical warnings
        "--output", str(output_dir / "%(title)s.%(ext)s"),
        playlist_url
    ]

    try:
        subprocess.run(cmd, check=True, cwd=output_dir)
        print("\nSuccessfully downloaded metadata for playlist.")

        # Count downloaded files
        json_files = list(output_dir.glob("*.info.json"))
        print(f"Found {len(json_files)} video metadata files.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\nFailed to download metadata: {e}")
        return False
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        return False


def load_talk_metadata(project_root: Path) -> dict[str, dict]:
    """
    Load talk metadata from the scraped PyBay data file.

    Returns a dict keyed by normalized talk title with speaker info.
    """
    metadata_file = project_root / "pybay_yt_video_download_dir" / "_pybay_2025_talk_data.json"

    if not metadata_file.exists():
        return log_talk_metadata_error(
            'Warning: Talk metadata file not found: ', metadata_file
        )
    try:
        with open(metadata_file) as f:
            talks_data = json.load(f)

        # Create lookup dict by normalized title
        lookup = {}
        for talk in talks_data:
            # Normalize title for matching (lowercase, no punctuation variations)
            normalized_title = talk["talk_title"].lower().strip()
            # Remove common variations
            normalized_title = normalized_title.replace(":", "").replace("—", "-").replace("–", "-")

            lookup[normalized_title] = {
                "title": talk["talk_title"],
                "speakers": [
                    f"{s['firstname']} {s['lastname']}".replace(" .", "").strip()  # Handle "Aastha ."
                    for s in talk.get("speakers", [])
                ],
                "description": talk.get("description", "")
            }

        print(f"Loaded metadata for {len(lookup)} talks from {metadata_file.name}")
        return lookup
    except Exception as e:
        return log_talk_metadata_error(
            'Warning: Failed to load talk metadata: ', e
        )


def log_talk_metadata_error(arg0, arg1):
    print(f"{arg0}{arg1}")
    print("Will fall back to parsing YouTube titles for speaker names")
    return {}


def create_talk_from_youtube_metadata(raw: dict, conf: Conference) -> Talk:
    """Convert YouTube metadata JSON to a Talk object.

    Args:
        raw: YouTube metadata dict from yt-dlp .info.json file
        conf: Conference object with settings for date validation and URLs

    Returns:
        Talk object with basic metadata populated from YouTube
    """
    return Talk(
        title=raw["title"],
        description="\n".join(
            line
            for line in raw["description"].splitlines()[
                conf.drop_first_lines : (
                    -conf.drop_last_lines if conf.drop_last_lines else None
                )
            ]
            if not TIMESTAMP_RE.match(line)
        ),
        recorded=str(
            clamp(
                parse_date(raw["upload_date"], r"%Y%m%d", conf.start),
                conf.start,
                conf.end,
            )
        ),
        duration=raw["duration"],
        videos=[
            {
                "type": "youtube",
                "url": raw["webpage_url"],
            }
        ],
        thumbnail_url=raw["thumbnail"],
        copyright_text=conf.copyright_text,
        related_urls=[
            {
                "label": "Conference schedule",
                "url": conf.schedule_url,
            },
            {
                "label": "Full playlist",
                "url": conf.playlist_url,
            },
        ],
    )


def match_speaker_with_fuzzy_matching(talk: Talk, talk_metadata: dict) -> tuple[Talk, bool]:
    """Match speaker names using fuzzy matching and regex fallback.

    Args:
        talk: Talk object with YouTube title
        talk_metadata: Dict of scraped PyBay metadata keyed by normalized title

    Returns:
        Tuple of (updated Talk object, needs_manual_review flag)
    """
    # Normalize YouTube title for matching
    normalized_yt_title = talk.title.lower().strip()
    # Remove "(PyBay 2025)" and speaker names for matching
    normalized_yt_title = re.sub(r'\s*\(pybay \d{4}\)', '', normalized_yt_title, flags=re.IGNORECASE)
    normalized_yt_title = re.sub(r'\s*[—–-]\s*.+$', '', normalized_yt_title)  # Remove "— Speaker Name"
    normalized_yt_title = normalized_yt_title.strip()

    metadata_match = None
    best_score = 0

    if talk_metadata:
        # Use fuzzy matching to find the best match
        # Using partial_ratio because it handles:
        # - YouTube's 100-char title truncation
        # - Minor punctuation differences (hyphen vs space, etc.)
        # - Substring matching (finds best match within longer strings)
        for key, metadata in talk_metadata.items():
            score = fuzz.partial_ratio(normalized_yt_title, key)
            if score > best_score:
                best_score = score
                metadata_match = metadata

        # Only use match if confidence is very high (>= 95%)
        if best_score >= 95:
            print(f"  Fuzzy matched ({best_score:.1f}%): {metadata_match['speakers']}")
        else:
            metadata_match = None
            print(f"  Low confidence ({best_score:.1f}%) - using regex fallback")

    if metadata_match:
        # Use clean data from scraped metadata
        talk.title = metadata_match["title"]
        talk.speakers = metadata_match["speakers"]
        print(f"  Matched with scraped metadata: {talk.speakers}")
        return talk, False
    elif match := QUOTED_TITLE_RE.search(talk.title):
        # Fall back to regex parsing
        groups = match.groups()
        # First two groups are for "Title — Speaker (PyBay YYYY)" format
        # Last two groups are for legacy "Title" - Speaker format
        if groups[0] and groups[1]:
            title, speaker = groups[0], groups[1]
        elif groups[2] and groups[3]:
            title, speaker = groups[2], groups[3]
        else:
            print(f"  MANUAL REVIEW NEEDED - No speaker found for: {talk.title}")
            return talk, True

        talk.title = title.strip()
        talk.speakers.extend(s.strip() for s in speaker.split(","))
        print(f"  Using regex fallback: {talk.speakers}")
        return talk, False
    else:
        # No match found
        print(f"  MANUAL REVIEW NEEDED - No speaker found for: {talk.title}")
        return talk, True


def write_pyvideo_files(talks: list[Talk], conf: Conference, pyvideo_data_dir: Path) -> None:
    """Write PyVideo JSON files for conference and all talks.

    Args:
        talks: List of Talk objects to write
        conf: Conference object with metadata
        pyvideo_data_dir: Root directory for PyVideo data
    """
    conf_dir = pyvideo_data_dir / conf.slug
    shutil.rmtree(conf_dir, ignore_errors=True)
    conf_dir.mkdir(parents=True, exist_ok=True)

    (conf_dir / "category.json").write_text(
        json.dumps(
            {"title": conf.title},
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    video_dir = conf_dir / "videos"
    video_dir.mkdir(parents=True, exist_ok=True)

    for talk in talks:
        path = (video_dir / talk.slug).with_suffix(".json")
        print(f"writing {path}")
        pprint(asdict(talk))
        path.write_text(
            json.dumps(
                asdict(talk),
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )


def print_summary(talks: list[Talk], needs_manual_review: list[str]) -> None:
    """Print summary of processed videos and manual review needs.

    Args:
        talks: List of all processed talks
        needs_manual_review: List of video titles needing manual review
    """
    print("\n" + "=" * 80)
    print(f"Processed {len(talks)} videos")

    if needs_manual_review:
        print(f"\n{len(needs_manual_review)} video(s) need MANUAL REVIEW (missing speakers):")
        for title in needs_manual_review:
            print(f"  - {title}")
        print("\nSearch for '\"speakers\": []' in the generated JSON files to find them.")
    else:
        print("\nAll videos successfully matched with speaker information!")

    print("=" * 80)


def main(yt_info_dir: Path, pyvideo_data_dir: Path, project_root: Path) -> None:
    """Main function to convert YouTube metadata to PyVideo format.

    Args:
        yt_info_dir: Directory containing yt-dlp .info.json files
        pyvideo_data_dir: Output directory for PyVideo formatted data
        project_root: Project root directory for locating scraped metadata
    """
    conf = Conference()
    talk_metadata = load_talk_metadata(project_root)

    talks: list[Talk] = []
    needs_manual_review: list[str] = []

    # Process each YouTube metadata file
    for path in sorted(yt_info_dir.glob("*.json")):
        print(f"loading {path}")
        raw = json.loads(path.read_text())
        if raw["_type"] != "video":
            print(f"skipping {raw['_type']}")
            continue

        # Convert YouTube metadata to Talk object
        talk = create_talk_from_youtube_metadata(raw, conf)

        # Match speakers using fuzzy matching and regex fallback
        talk, needs_review = match_speaker_with_fuzzy_matching(talk, talk_metadata)
        if needs_review:
            needs_manual_review.append(talk.title)

        talks.append(talk)

    # Write all PyVideo JSON files
    write_pyvideo_files(talks, conf, pyvideo_data_dir)

    # Print summary in terminal
    print_summary(talks, needs_manual_review)


if __name__ == "__main__":
    # Determine project root (parent of src/)
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent

    # Default paths relative to project root
    default_yt_dir = project_root / "pyvideo_data_dir" / "yt_metadata"
    default_data_dir = project_root / "pyvideo_data_dir"

    # Setup argument parser
    parser = argparse.ArgumentParser(
        description="Convert YouTube playlist metadata to PyVideo.org format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # One-step: Download from YouTube and convert (recommended)
  python src/pyvideo_converter.py --url "https://www.youtube.com/playlist?list=PLAYLIST_ID"

  # Two-step: Convert existing yt-dlp metadata
  python src/pyvideo_converter.py

  # Custom paths
  python src/pyvideo_converter.py /path/to/yt-dlp-output /path/to/pyvideo-data
        """
    )

    parser.add_argument(
        "--url",
        type=str,
        help="YouTube playlist URL to download metadata from (automates yt-dlp step)"
    )

    parser.add_argument(
        "yt_info_dir",
        nargs="?",
        type=Path,
        help=f"Directory containing yt-dlp .info.json files (default: {default_yt_dir})"
    )

    parser.add_argument(
        "pyvideo_data_dir",
        nargs="?",
        type=Path,
        help=f"Output directory for PyVideo data (default: {default_data_dir})"
    )

    args = parser.parse_args()

    # Determine input/output directories
    yt_info_dir = args.yt_info_dir.resolve() if args.yt_info_dir else default_yt_dir
    data_dir = args.pyvideo_data_dir.resolve() if args.pyvideo_data_dir else default_data_dir

    # If --url is provided, download metadata first
    if args.url:
        print("STEP 1: Downloading YouTube metadata with yt-dlp")

        if not check_yt_dlp():
            print("\nError: yt-dlp is not installed.")
            print("Install it with: pip install yt-dlp")
            sys.exit(1)

        if not download_youtube_metadata(args.url, yt_info_dir):
            print("\nError: Failed to download YouTube metadata")
            sys.exit(1)

        print("STEP 2: Converting metadata to PyVideo format")
    else:
        print("Using default paths:")
        print(f"  Input:  {yt_info_dir}")
        print(f"  Output: {data_dir}")

    # Run the conversion
    main(yt_info_dir, data_dir, project_root)

    print("PyVideo metadata conversion complete!")
    print("/n")
    print(f"\nGenerated PyVideo data in: {data_dir}")
    print("\nNEXT STEPS:")
    print("1. Manually review and fix JSON files in:")
    print(f"   {data_dir / Conference().slug / 'videos'}/")
    print("\n2. Common issues to check:")
    print("   - Speaker names extracted correctly")
    print("   - Talk titles (should not include speaker names)")
    print("   - Descriptions in valid reStructuredText format")
    print("\n3. After review, copy to PyVideo fork and run tests per their `Contributing Guidelines`.")
    