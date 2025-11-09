# PyBay Video Publishing Workflow

This document covers the complete end-to-end workflow for publishing PyBay conference videos:

1. **Download & Rename** - Process videos from AV vendor and prepare for YouTube
2. **Upload to YouTube** - Publish to SF Python YouTube channel
3. **Submit to PyVideo.org** - Make videos discoverable in the global Python video archive

---

## Step 1: Download & Rename Videos

### Quick Start (One Command)

**For volunteers:** Download and rename all videos automatically:

```bash
python src/google_drive_video_downloader.py \
  --gdrive-url "https://drive.google.com/drive/folders/YOUR_FOLDER_ID" \
  --output-path "pybay_videos_destination" \
  --year 2025
```

**What this does:**
1. Downloads all videos in parallel (preserves original Google Drive filenames)
2. Saves metadata → `_pybay_2025_gdrive_metadata.json`
3. Fetches talk data from pybay.org → `_pybay_2025_talk_data.json`
4. Renames to preferred filename format which is easier for YouTube viewers → `Title — Speaker (PyBay 2025).mp4`

---

## Design Decisions

### Why Keep Original Filenames During Download?

**Problem:** AV team uses inconsistent naming conventions that change every year.

**Solution:** Preserve original filenames, then do ALL transformation in one rename step.

**Benefits:**
- Simpler mental model (Download → Rename, not Download+Normalize → Rename)
- Less confusing to troubleshoot
- Renamer handles all time format variations anyway

### Why Use PyBay.org as Source of Truth?

**Problem:** We have three data sources with varying quality:
1. Speaker-provided data (Sessionize) - which in NOT publicly accessible but feeds PyBay website with API
2. PyBay website - public, system of record for what talks were done, easy to get data from
3. AV team filenames - actual videos of the talk, but loose naming standards (e.g. missing firstname, different timestamp formats each year), also - everything changes yearly
 
**Solution:** Use public pybay.org pages to avoid requiring volunteers to access complex/paid systems.

**Benefits:**
- No Sessionize API access needed
- No paid Google Drive account needed
- Public data anyone can verify
- Speaker Data already cleaned up by PyBay Organizers

### Why Token-Based Matching?

**Problem:** Can't rely on exact filename matching due to inconsistent naming.

**Solution:** Start from pybay.org metadata, then match room + time + lastname tokens

**Benefits:**
- Handles time format variations (`10:00 am`, `1000`, `10am`)
- Handles name variations (`van Rossum`, `Hatfield-Dodds`, single names)


---

## File Naming

**Original from Google Drive - for 2025 only:**
```
Robertson - 10am - Brousseau - Welcome Remarks.mp4
Fisher - 1030am - Hatfield-Dodds - Testing Tools.mp4
```

**Renamed to publication format - same format for 2024, 2025:**
```
Welcome & Opening Remarks — Chris Brousseau (PyBay 2025).mp4
No, seriously, why don't we use better testing tools? — Zac Hatfield-Dodds (PyBay 2025).mp4
```

**Multi-speaker talks:**
```
Next Level Python Applications with PyScript — Fabio Pliger & Chris Laffra (PyBay 2024).mp4
```

---

## Advanced Options - script flags

For users who want more control:

### Download Only

```bash
python src/google_drive_video_downloader.py \
  --gdrive-url "YOUR_FOLDER_ID" \
  --output-path "pybay_videos_destination" \
  --year 2025 \
  --download-only
```

### Rename Already Downloaded Files Separately

```bash
# Preview changes first (dry-run)
python src/file_renamer.py \
  --video-dir "pybay_videos_destination" \
  --year 2025 \
  --dry-run

# Actually rename
python src/file_renamer.py \
  --video-dir "pybay_videos_destination" \
  --year 2025
```

---

## Metadata Files Created

### `_pybay_2025_gdrive_metadata.json`
Original Google Drive filenames + checksums for audit trail.

### `_pybay_2025_talk_data.json`
Talk metadata from pybay.org (titles, speakers, rooms, times).

**Why keep both?**
- Google Drive metadata: Shows what AV team named files
- PyBay metadata: Authoritative talk information

---

## Handling Edge Cases

### Unmatched Videos
**Cause:** Alternate speakers, last-minute changes not on public schedule.

**Solution:** Renamer flags unmatched files. Manually rename or add to `_pybay_2025_talk_data.json`.

### Time Mismatches
**Cause:** Different time formats between sources.

**Solution:** Renamer normalizes all times to 24-hour format for matching.

### Multi-Speaker Talks
**Cause:** Panel discussions, co-presentations.

**Solution:** Renamer joins speakers with " & " separator.

### Special Characters
**Cause:** Colons, question marks in talk titles.

**Solution:** Renamer removes filesystem-unsafe characters (`< > : " / \ | ? *`).

---

## Troubleshooting

### Downloads fail with "name 'new_name' is not defined"
**Fixed** in latest version. Update your code.

### Renamer shows "No files to rename"
**Cause:** Files already renamed OR no videos downloaded.

**Solution:** Check directory contents. Re-run downloader if needed.

### Some talks show "[NO VIDEO]"
**Cause:** Video wasn't recorded or is in a different folder.

**Solution:** Normal - not all sessions are recorded. Flag for organizers if unexpected.

---

## File Organization

```
pybay_videos_destination/
├── _pybay_2025_gdrive_metadata.json    # Original Drive names
├── _pybay_2025_talk_data.json          # PyBay website metadata
└── *.mp4                               # Renamed videos
```

**Keep metadata files** - they provide audit trail and enable re-renaming if needed.  DO NOT upload to YouTube

---

## Step 2: Upload to YouTube

After videos are renamed, upload them to the SF Python YouTube channel:

1. **Create a new playlist** for the current year (e.g., "PyBay 2025")
2. **Upload all videos** to the playlist
3. **Publish the playlist** (make it public)
4. **Note the playlist URL** - you'll need this for PyVideo submission

**Example playlist URL:**
```
https://www.youtube.com/playlist?list=PLNl1VPnXL__XXXXXXXXXXXXXXXXX
```

---

## Step 3: Submit to PyVideo.org

PyVideo.org is the global archive for Python conference videos, making them discoverable and searchable across the entire Python community.

### Why Submit to PyVideo?

- **Discoverability** - Videos are indexed alongside PyCon, EuroPython, and other major conferences
- **Searchability** - Full-text search across talks, speakers, and descriptions
- **Preservation** - Long-term archival of Python conference content
- **Community** - Contributes to the global Python knowledge base

### Automated Workflow

The `pyvideo_converter.py` script automates the conversion of YouTube metadata to PyVideo format with fuzzy matching for speaker extraction.

**Quick Start:**

```bash
# From project root
python src/pyvideo_converter.py --url "https://www.youtube.com/playlist?list=PLAYLIST_ID"
```

**This will:**
1. Download YouTube metadata using yt-dlp
2. Fuzzy match video titles to scraped PyBay metadata (~89% success rate)
3. Generate PyVideo JSON files in `pyvideo_data_dir/pybay-2025/`
4. Flag videos needing manual review (typically 3-4 videos)

**Expected Output:**
```
================================================================================
Processed 27 videos

3 video(s) need MANUAL REVIEW (missing speakers):
  - Welcome & Opening Remarks (PyBay 2025)
  - Lightning Talks Session 1 (PyBay 2025)
  - Closing Remarks (PyBay 2025)

Search for '"speakers": []' in the generated JSON files to find them.
================================================================================
```

### Manual Review & Fixes

**CRITICAL:** Manually review all generated JSON files in `pyvideo_data_dir/pybay-2025/videos/`

Common issues to fix:
- Videos with empty `"speakers": []` array (flagged in output)
- Talk titles containing speaker names (should be title only)
- Descriptions needing reStructuredText (rST) formatting
- Special characters that need escaping

**Tip:** Use the summary output to quickly find videos needing attention.

### Submit to PyVideo Repository

1. **Fork and clone** the PyVideo data repository:
   ```bash
   # Fork on GitHub: https://github.com/pyvideo/data
   git clone https://github.com/YOUR_USERNAME/data.git pyvideo-data-fork
   ```

2. **Copy your reviewed data**:
   ```bash
   cp -r pyvideo_data_dir/pybay-2025/ pyvideo-data-fork/
   ```

3. **Create virtual environment and run tests**:
   ```bash
   cd pyvideo-data-fork
   python3 -m venv .venv    # Must be named .venv (required by Makefile)
   source .venv/bin/activate
   make test
   ```

4. **Fix any validation errors** (should be minimal if manual review was thorough)

5. **Create PR**:
   ```bash
   git checkout -b pybay-2025
   git add pybay-2025/
   git commit -m "Add PyBay 2025 videos"
   git push origin pybay-2025
   ```

6. **Submit PR** to https://github.com/pyvideo/data

### Detailed Instructions

For complete step-by-step instructions, see the docstring in `src/pyvideo_converter.py`:

```bash
python src/pyvideo_converter.py --help
# Or read the docstring directly in the file
```

### Directory Structure

After PyVideo conversion, your directory structure will be:

```
pybay-video-publishing-helpers/
├── pybay_yt_video_download_dir/
│   └── _pybay_2025_talk_data.json          # Scraped metadata (source of truth)
└── pyvideo_data_dir/
    ├── yt_metadata/                         # YouTube metadata from yt-dlp
    │   └── *.info.json                      # (cleaned on re-runs)
    └── pybay-2025/                          # PyVideo submission data
        ├── category.json                    # Conference metadata
        └── videos/                          # Video JSON files
            ├── welcome-opening-remarks.json
            ├── testing-tools.json
            └── ...
```

---

## Complete Workflow Summary

1. **Download & Rename** → `google_drive_video_downloader.py`
2. **Upload to YouTube** → Manual (SF Python YouTube channel)
3. **Convert to PyVideo** → `pyvideo_converter.py --url "PLAYLIST_URL"`
4. **Manual Review** → Fix videos flagged in summary output
5. **Test & Submit** → Fork PyVideo repo, run tests, create PR

---
