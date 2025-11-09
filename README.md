# PyBay Video Publishing Helpers

Utilities to automate processing of PyBay conference videos for publication on YouTube and PyVideo.

## Overview

This toolkit helps volunteers prepare PyBay conference videos for publication by:
- Downloading videos from Google Drive
- Fetching talk metadata from the PyBay website
- Renaming videos to a consistent, publication-ready format
- Converting YouTube metadata to PyVideo.org format for global archival

**Key Design Principles:**
- **Use public information** - Relies on publicly accessible pybay.org pages to avoid requiring volunteers to access complex/paid systems (Sessionize, paid Google Drive accounts, etc.)
- **Handle variability** - Works with inconsistent input from multiple sources that change year-to-year
- **Minimize friction** - Designed for volunteers who perform this task once per year

## The Challenge

Publishing PyBay videos involves reconciling data from multiple sources with varying quality:

1. **Speaker-provided data** (via Sessionize):
   - Talk titles, descriptions, speaker names
   - We don't control this input - speakers can format names inconsistently
   - Changes format/structure year-to-year

2. **AV team video filenames**:
   - VERY LOOSE file naming standards that changes slightly every year
   - Examples from 2025: `Robertson - 1000 - Brousseau - Welcome Remarks.mp4`
   - May use different time formats (12hr vs 24hr), varying separators, etc.
   - Different person may handle this each year → different conventions

3. **Google Drive organization**:
   - Videos uploaded by AV team
   - Requires authentication to access
   - Original filenames preserved in metadata

**Our solution:** Use the official schedule published on the public PyBay website as the authoritative source of truth, then match videos using intelligent token-based matching (room + time + speaker name).

## Installation

```bash
# Clone the repo
git clone https://github.com/pybay/pybay-video-publishing-helpers.git
cd pybay-video-publishing-helpers

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Quick Start

### Simple One-Command Workflow (Recommended for Volunteers)

Download and rename all videos in one command:

```bash
python src/google_drive_video_downloader.py \
  --gdrive-url "https://drive.google.com/drive/folders/YOUR_FOLDER_ID" \
  --output-path "pybay_videos_destination" \
  --year 2025
```

**This single command automatically:**
1. Downloads all videos in parallel (4-8x faster)
2. Saves metadata → `_pybay_2025_gdrive_metadata.json`
3. Fetches talk data → `_pybay_2025_talk_data.json`
4. Renames to publication format → `Title — Speaker (PyBay 2025).mp4`
5. Flags unmatched files for review → `![REVIEW_NEEDED]_filename.mp4`
6. Verifies downloads with MD5 checksums
7. Skips already-downloaded files (resumable)

**Using service account authentication:**
```bash
export GOOGLE_DRIVE_API_KEY_PYBAY='{"type":"service_account",...}'
python src/google_drive_video_downloader.py \
  --gdrive-url "YOUR_FOLDER_ID" \
  --output-path "pybay_videos_destination" \
  --year 2025 \
  --service-account
```

### Advanced: Two-Step Workflow

For volunteers who want more control, or want to rename videos with a different pattern after downloading:

```bash
# Step 1: Download only (skip renaming)
python src/google_drive_video_downloader.py \
  --gdrive-url "YOUR_FOLDER_ID" \
  --output-path "pybay_videos_destination" \
  --year 2025 \
  --download-only

# Step 2: Rename separately (with dry-run preview first)
python src/file_renamer.py \
  --video-dir "pybay_videos_destination" \
  --year 2025 \
  --dry-run

# Then actually rename
python src/file_renamer.py \
  --video-dir "pybay_videos_destination" \
  --year 2025
```

**File naming:**
```
Downloaded from GDrive: Robertson - 1000 - Brousseau - Welcome Remarks.mp4
Renamed to:            Welcome & Opening Remarks — Chris Brousseau (PyBay 2025).mp4

Downloaded from GDrive: Robertson - 1000 - Pliger - PyScript Talk.mp4
Renamed to:            Next Level Python Applications with PyScript — Fabio Pliger & Chris Laffra (PyBay 2024).mp4
```

## Features

### Multi-Speaker Support ✨

Handles talks with multiple speakers (panels, co-presentations):

**JSON Format:**
```json
{
  "talk_title": "Next Level Python Applications with PyScript",
  "speakers": [
    {"firstname": "Fabio", "lastname": "Pliger"},
    {"firstname": "Chris", "lastname": "Laffra"}
  ]
}
```

**Filename Output:**
```
Next Level Python Applications with PyScript — Fabio Pliger & Chris Laffra (PyBay 2024).mp4
```

### Intelligent Matching

Matches videos to talk metadata with three data elements:
- **Room** - Case-insensitive (e.g., Robertson, Fisher.)
- **Time** - Normalized to 24-hour format (handles "10:00 am", "1000", "2:30 pm", "1430")
- **Name** - Partial matching (handles "van Rossum", "Hatfield-Dodds", single names)

For multi-speaker talks, matches if **ANY** speaker name appears in the filename.

### Special Cases Handled

- Multiple speakers joined with " & " (we often have 1-2 every year, last one in 2024)
- Hyphenated last names (e.g., Hatfield-Dodds)
- Single names (e.g., no last name, which comes from incomplete Sessionize profiels)
- Multi-part surnames (e.g., van Rossum)
- Missing name data (uses whatever is available)
- Files without metadata flagged for manual review by adding prefix to final filename

### Parallel Downloads w/auto retry


## Related Docs

- **[README_VIDEO_PUBLISHING_WORKFLOW.md](README_VIDEO_PUBLISHING_WORKFLOW.md)** - Complete workflows with diagrams
- **[README_GOOGLE_DRIVE_SETUP.md](README_GOOGLE_DRIVE_SETUP.md)** - Google Drive auth setup

## Testing

Some tests written - could use more for sure

**Test Coverage:**
- Multi-speaker handling (22 tests)
- Web scraping and parsing (13 tests)
- Time normalization (15 tests)

## Complete Publishing Workflow

The full PyBay video publishing process has three steps:

1. **Download & Rename** (this repo) - Process videos from AV vendor
2. **Upload to YouTube** - Publish to SF Python YouTube channel
3. **Submit to PyVideo.org** (this repo) - Archive in global Python video database

### Step 1 & 2: Download, Rename, and Upload to YouTube

```bash
# Download and rename videos from AV vendor Google Drive
python src/google_drive_video_downloader.py \
  --gdrive-url "YOUR_FOLDER_ID" \
  --output-path "pybay_videos_destination" \
  --year 2025

# Then manually upload to YouTube and create playlist
```

### Step 3: Submit to PyVideo.org

```bash
# Convert YouTube metadata to PyVideo format (with fuzzy matching)
python src/pyvideo_converter.py --url "https://www.youtube.com/playlist?list=PLAYLIST_ID"

# Review flagged videos, fix any issues, then submit PR to pyvideo/data
```

**See [README_VIDEO_PUBLISHING_WORKFLOW.md](README_VIDEO_PUBLISHING_WORKFLOW.md) for complete details.**

---

## Project Structure

```
pybay-video-publishing-helpers/
├── src/
│   ├── google_drive_video_downloader.py  # Main download script (parallel)
│   ├── file_renamer.py                   # Token-based renamer
│   ├── pyvideo_converter.py              # YouTube → PyVideo converter (fuzzy matching)
│   ├── scraper_pybayorg_talk_metadata.py # Scrapes pybay.org for talk data
│   ├── google_drive_fetch_metadata.py    # Standalone metadata fetcher
│   ├── google_drive_ops.py               # Google Drive API operations
│   ├── file_ops.py                       # File verification utilities
│   └── file_ops_parallel.py              # Fast parallel download functions
├── tests/
│   ├── test_multi_speaker.py             # Multi-speaker functionality tests
│   ├── test_scraper.py                   # Scraper function tests
│   └── test_time_normalization.py        # Time parsing tests
├── pybay_yt_video_download_dir/          # Renamed videos + metadata (for YouTube upload)
├── pyvideo_data_dir/                     # PyVideo formatted data (for PyVideo submission)
├── README_VIDEO_PUBLISHING_WORKFLOW.md   # Complete workflow documentation
├── README_GOOGLE_DRIVE_SETUP.md          # Authentication setup guide
└── requirements.txt                      # Python dependencies
```

## Data Sources

### 1. PyBay Website (pybay.org)
- **Source:** `https://pybay.org/speaking/talk-list-YYYY/`
- **Format:** Sessionize API HTML
- **Contains:** Talk titles, speaker names, rooms, times, descriptions
- **Saved to:** `_pybay_YYYY_talk_data.json`
- **Why:** Publicly accessible, authoritative source of truth

### 2. Google Drive Metadata
- **Source:** Google Drive API
- **Contains:** Original filenames from AV provider, file sizes, MD5 checksums
- **Saved to:** `_pybay_YYYY_gdrive_metadata.json`
- **Why:** Preserves audit trail of original AV team filenames

### 3. Downloaded Video Files
- **Current format:** `{Room} - {Time} - {LastName} - {Title}.mp4`
- **Final format:** `{Title} — {FirstName} {LastName} ({Year}).mp4`
- **Note:** AV Team's Naming conventions vary year-to-year

## Common Issues

### Videos don't match metadata
**Cause:** Last-minute speaker changes, Alternate Speakers not added to official schedule in Sessionize, uAV team filename variations

**Solution:**
- Renamer flags unmatched files for manual review
- Manually rename these files, or
- Add missing entries to `_pybay_YYYY_talk_data.json`

### Time formats don't match
**Cause:** Inconsistent time formats between AV team and website

**Solution:**
- Renamer normalizes all times to 24-hour format automatically
- Handles: `10am`, `10:00 am`, `1000`, `1430`, `2:30 pm`, etc.

### Missing metadata files
**Cause:** Fresh download didn't create metadata, or files were deleted

**Solution:**
```bash
# Re-fetch Google Drive metadata (doesn't re-download videos)
python src/google_drive_fetch_metadata.py \
  --folder "YOUR_DRIVE_URL" \
  --year 2025

# Fetch PyBay website metadata
python src/scraper_pybayorg_talk_metadata.py \
  --url "https://pybay.org/speaking/talk-list-2025/" \
  --output "pybay_videos_destination/_pybay_2025_talk_data.json"
```

## Contributing

This is a volunteer-driven project. Contributions welcome!

### Good Future Improvements

**New Features:**
- Upload to SF Python YouTube channel and playlist (needed!)
- Improve fuzzy matching for edge cases (currently ~89% success rate)
- Integrate tqdm progress tracker for better download visibility
- Automated reStructuredText validation for PyVideo descriptions

**Test Coverage Gaps:**

Areas without tests:
- Google Drive operations (`google_drive_ops.py`, `google_drive_video_downloader.py`)
- File operations (`file_ops.py`, `file_ops_parallel.py`)
- Credential checking (`google_drive_check_credentials.py`)
- Metadata fetching (`google_drive_fetch_metadata.py`)

**Note for Future Volunteers:** This repo was designed to be a little resilient to changes we have seen in past few years, but if something breaks, check:
1. Has the AV team changed their filename format?
2. Has pybay.org changed its URL structure?
3. Has Sessionize changed its HTML structure?
