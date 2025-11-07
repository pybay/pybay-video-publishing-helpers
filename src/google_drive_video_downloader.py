"""
Google Drive Video Downloader and Renamer - PARALLEL VERSION

Downloads videos from a shared Google Drive folder using parallel downloads
with direct HTTP requests for maximum speed (4-8x faster than sequential).

Key differences from original:
    - Uses requests library with direct HTTP downloads (bypasses MediaIoBaseDownload)
    - Parallel downloads with ProcessPoolExecutor (4-8 concurrent workers)
    - Expected performance: 58.3 GB in 30-60 minutes vs 4+ hours sequential

Cross-Platform Support:
    - Uses pathlib.Path for cross-platform path handling (Linux, macOS, Windows)
    - Automatically converts Windows paths to WSL format when running in WSL
    - Streams large files directly to disk (memory-efficient for multi-GB files)
"""

import os
import sys
import argparse
import time
import subprocess
from pathlib import Path
from typing import Optional, Tuple, Dict
from concurrent.futures import ProcessPoolExecutor, as_completed

# Import from our utility modules
from utils_job_progress import ProgressTracker
from google_drive_ops import (
    get_drive_service,
    list_video_files,
    test_connection,
    extract_folder_id,
    save_folder_metadata
)
from file_ops import verify_file
from file_ops_parallel import download_file_fast  # New fast download function
from utils_path import get_download_path


def parse_arguments():
    """Parse and return command-line arguments."""
    # Calculate default workers: CPU count - 1 (min 1, max 12)
    cpu_count = os.cpu_count() or 4
    default_workers = max(1, min(cpu_count - 1, 12))

    parser = argparse.ArgumentParser(
        description='Download videos from Google Drive in parallel (FAST)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Examples:
  # Download with OAuth (default) - uses {default_workers} parallel workers (CPU-1)
  python google_drive_video_downloader.py --gdrive-url YOUR_FOLDER_ID --output-path "/mnt/c/Users/chris/Downloads/PyBay 2025 Videos"

  # Download with custom worker count
  python google_drive_video_downloader.py --gdrive-url YOUR_FOLDER_ID --output-path ~/Videos --workers 8

  # Download using service account authentication
  export GOOGLE_DRIVE_API_KEY_PYBAY='{{"type":"service_account",...}}'
  python google_drive_video_downloader.py --gdrive-url YOUR_FOLDER_ID --output-path ~/Videos --service-account
        """
    )

    parser.add_argument('--gdrive-url', required=True, help='Google Drive folder ID or URL')
    parser.add_argument('--output-path', help='Local destination directory (will prompt if not provided)')
    parser.add_argument('--workers', type=int, default=default_workers,
                       help=f'Number of parallel download workers (default: {default_workers} = CPU-1, max recommended: 12)')
    parser.add_argument('--year', type=int,
                       help='PyBay year (e.g., 2025) for metadata filename (default: current year)')
    parser.add_argument('--talks-url',
                       help='PyBay talks page URL (default: auto-generated from --year as https://pybay.org/speaking/talk-list-YYYY/)')
    parser.add_argument('--download-only', action='store_true',
                       help='Download only, skip renaming to publication format (advanced users)')
    parser.add_argument('--service-account', action='store_true',
                       help='Use service account authentication instead of OAuth (requires GOOGLE_DRIVE_API_KEY_PYBAY env var)')
    parser.add_argument('--service-account-env', default='GOOGLE_DRIVE_API_KEY_PYBAY',
                       help='Environment variable name for service account credentials (default: GOOGLE_DRIVE_API_KEY_PYBAY)')

    args = parser.parse_args()

    # Validate worker count
    if args.workers < 1:
        print("[ERROR] --workers must be at least 1")
        sys.exit(1)
    elif args.workers > 12:
        print(f"[WARNING] --workers={args.workers} is quite high. Recommended: 4-8")
        print("High worker counts may hit API rate limits or saturate your connection.")
        response = input("Continue anyway? (y/n): ").strip().lower()
        if response != 'y':
            sys.exit(0)

    return args


def process_single_file_parallel(file_info: dict, download_path: Path,
                                 service_account: bool,
                                 service_account_env: str) -> Tuple[Dict, Optional[str], Optional[str]]:
    """
    Process a single video file: check, download, and verify.
    Designed for multiprocessing - creates its own service instance.

    Args:
        file_info: File metadata dictionary from Google Drive
        download_path: Path object for download destination
        service_account: Whether to use service account auth
        service_account_env: Environment variable for service account credentials

    Returns:
        tuple: (stats dict, failed_filename or None, error_message or None)
    """
    # Import here to avoid pickling issues
    from google_drive_ops import get_drive_service

    file_id = file_info['id']
    original_name = file_info['name']
    file_size = int(file_info.get('size', 0))
    file_md5 = file_info.get('md5Checksum')

    stats = {'downloaded': 0, 'skipped': 0, 'failed': 0}
    failed_file = None
    error_msg = None

    # Use original filename (no renaming during download)
    destination = download_path / original_name

    # Check if file already exists - silently clean up corrupted/0-byte files
    if destination.exists():
        if verify_file(destination, file_size, file_md5, silent=True):
            stats['skipped'] = 1
            return stats, None, None
        else:
            # Verification failed (corrupted or 0-byte), silently delete and re-download
            destination.unlink()

    # Create service instance for this process (with silent auth)
    try:
        service = get_drive_service(service_account, service_account_env, silent=True)
    except Exception as e:
        stats['failed'] = 1
        return stats, original_name, f"Authentication failed: {e}"

    # Download file using fast method (with automatic retries)
    download_success, download_error = download_file_fast(
        service, file_id, original_name, destination, file_size
    )

    if download_success:
        if verify_file(destination, file_size, file_md5, silent=True):
            stats['downloaded'] = 1
            # Print success immediately for visibility
            print(f"[OK] {original_name} ({file_size / (1024**2):.1f} MB)")
        else:
            # Verification failed after download - silently clean up
            destination.unlink()
            stats['failed'] = 1
            failed_file = original_name
            error_msg = "Verification failed after download"
    else:
        stats['failed'] = 1
        failed_file = original_name
        error_msg = download_error or "Unknown error"

    return stats, failed_file, error_msg


def print_summary(stats: dict, total_files: int,
                 failed_files: list = None, elapsed_time: float = None):
    """
    Print download statistics summary.

    Args:
        stats: Dictionary with download statistics
        total_files: Total number of files processed
        failed_files: Optional list of failed filenames
        elapsed_time: Optional elapsed time in seconds
    """
    print(f"\n{'='*80}")
    print("Download Summary")
    print(f"{'='*80}")
    print(f"Files downloaded:    {stats['downloaded']}")
    print(f"Files skipped:       {stats['skipped']}  (already existed and verified)")
    print(f"Files failed:        {stats['failed']}")
    print(f"Total files:         {total_files}")

    if elapsed_time:
        minutes = int(elapsed_time // 60)
        seconds = int(elapsed_time % 60)
        print(f"Time elapsed:        {minutes}m {seconds}s")

    if stats['failed'] > 0:
        print(f"\n{'='*80}")
        print("FAILED FILES - Action Required")
        print(f"{'='*80}")

        if failed_files:
            print("\nThe following files failed to download:")
            for filename in failed_files:
                print(f"  [FAILED] {filename}")

        print("\nWhat to do next:")
        print("  1. CHECK YOUR CONNECTION - Ensure you have stable internet")
        print("  2. RE-RUN THE SCRIPT - It will automatically:")
        print("     • Skip files that were successfully downloaded")
        print("     • Retry only the failed files")
        print("     • Resume where it left off")
        print("\n  Command to retry:")
        print("     python src/google_drive_video_downloader.py --folder <YOUR_FOLDER> --path <YOUR_PATH>")
        print("\n  3. If failures persist:")
        print("     • Check disk space (may be full)")
        print("     • Verify Google Drive API quotas (unlikely with moderate file counts)")
        print("     • Try reducing --workers (e.g., --workers 2)")
        print("     • Contact folder owner if files appear corrupted on Drive")
    else:
        print("\n" + "="*80)
        print("All downloads complete!")
        print("="*80)


def main():
    """Main entry point for the parallel video downloader script."""
    start_time = time.time()

    # Parse command-line arguments
    args = parse_arguments()

    # Extract folder ID from URL if needed
    folder_id = extract_folder_id(args.gdrive_url)

    # Get and validate download path
    download_path = get_download_path(args.output_path)

    # Authenticate with Google Drive
    if args.service_account:
        print("Authenticating with Google Drive (Service Account)...")
    else:
        print("Authenticating with Google Drive (OAuth)...")
    service = get_drive_service(args.service_account, args.service_account_env)

    # Test connection early (fail fast approach)
    using_service_account = args.service_account or os.environ.get(args.service_account_env) is not None
    if not test_connection(service, folder_id, using_service_account):
        print("\nExiting due to connection failure.")
        sys.exit(1)

    # Determine PyBay year for metadata
    if args.year:
        pybay_year = args.year
    else:
        from datetime import datetime
        pybay_year = datetime.now().year

    # Auto-generate talks URL if not provided
    if args.talks_url:
        talks_url = args.talks_url
    else:
        talks_url = f"https://pybay.org/speaking/talk-list-{pybay_year}/"
        print(f"[INFO] Using auto-generated talks URL: {talks_url}")

    # Save Google Drive folder metadata BEFORE downloading
    # This preserves original filenames for future reference
    save_folder_metadata(service, folder_id, download_path, pybay_year)

    # List files in folder
    files = list_video_files(service, folder_id)

    if not files:
        print("No video files found in the specified folder.")
        return

    # Calculate total size of all files
    total_bytes = sum(int(f.get('size', 0)) for f in files)
    total_gb = total_bytes / (1024**3)

    print(f"\nFound {len(files)} video files (Total: {total_gb:.1f} GB)")

    # Pre-scan: Check which files already exist locally
    existing_count = 0
    existing_bytes = 0
    corrupted_count = 0
    files_to_download = []

    for file_info in files:
        original_name = file_info['name']
        file_size = int(file_info.get('size', 0))
        file_md5 = file_info.get('md5Checksum')

        # Use original filename (no renaming during download)
        destination = download_path / original_name

        # Check if file exists and is valid (silent pre-scan)
        if destination.exists():
            if verify_file(destination, file_size, file_md5, silent=True):
                existing_count += 1
                existing_bytes += file_size
            else:
                # File exists but is corrupted (will re-download)
                corrupted_count += 1
                files_to_download.append(file_info)
        else:
            files_to_download.append(file_info)

    # Show pre-scan summary
    bytes_to_download = total_bytes - existing_bytes
    if existing_count > 0:
        existing_gb = existing_bytes / (1024**3)
        to_download_gb = bytes_to_download / (1024**3)
        print(f"  → {existing_count} files already downloaded ({existing_gb:.1f} GB)")
        print(f"  → {len(files_to_download)} files to download ({to_download_gb:.1f} GB)")
    else:
        print(f"  → All {len(files)} files need to be downloaded")

    if not files_to_download:
        print("\nAll files already exist and are verified. Nothing to download!")
        return

    # Check disk space before starting
    disk_stats = os.statvfs(download_path)
    available_bytes = disk_stats.f_bavail * disk_stats.f_frsize
    available_gb = available_bytes / (1024**3)

    if bytes_to_download > available_bytes:
        # Not enough space
        needed_gb = bytes_to_download / (1024**3)
        print(f"\n[ERROR] Insufficient disk space!")
        print(f"  Required: {needed_gb:.1f} GB")
        print(f"  Available: {available_gb:.1f} GB")
        print(f"  Shortfall: {(needed_gb - available_gb):.1f} GB")
        print("\nPlease free up disk space and try again.")
        sys.exit(1)
    elif bytes_to_download > (available_bytes * 0.9):
        # Would use > 90% of available space - warn but allow
        usage_pct = (bytes_to_download / available_bytes) * 100
        print(f"\n[WARNING] Downloads will use {usage_pct:.0f}% of available disk space")
        print(f"  Available: {available_gb:.1f} GB")
        print(f"  To download: {bytes_to_download / (1024**3):.1f} GB")
        print(f"  Remaining after: {(available_bytes - bytes_to_download) / (1024**3):.1f} GB")
        response = input("\nContinue anyway? (y/n): ").strip().lower()
        if response != 'y':
            print("Download cancelled by user.")
            sys.exit(0)

    # Test write access before starting downloads
    test_file = download_path / ".write_test_temp"
    try:
        with open(test_file, 'w') as f:
            f.write("test")
        test_file.unlink()
    except Exception as e:
        print(f"\n[ERROR] Cannot write to download path: {e}")
        print(f"Path: {download_path}")
        print("\nThis may be a permissions issue or the path may not be accessible.")
        sys.exit(1)

    print(f"\nDownloading with {args.workers} parallel workers...\n")
    print("NOTE: Progress updates appear as each file completes (not during download)")
    print("This is faster but provides less granular progress than sequential mode.\n")

    # Process files in parallel with ProcessPoolExecutor
    total_stats = {'downloaded': 0, 'skipped': existing_count, 'failed': 0}
    failed_files = []  # Track failed files with error messages

    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        # Submit all download tasks
        future_to_file = {}
        for file_info in files_to_download:
            future = executor.submit(
                process_single_file_parallel,
                file_info,
                download_path,
                args.service_account,
                args.service_account_env
            )
            future_to_file[future] = file_info['name']

        # Process completed downloads as they finish
        completed = 0
        total_to_download = len(files_to_download)

        for future in as_completed(future_to_file):
            completed += 1
            filename = future_to_file[future]

            try:
                file_stats, failed_filename, error_msg = future.result()

                # Accumulate stats
                for key in total_stats:
                    total_stats[key] += file_stats[key]

                # Track failures
                if failed_filename:
                    failed_files.append(f"{failed_filename} - {error_msg}")
                    print(f"[FAILED] {failed_filename}: {error_msg}")

                # Show overall progress
                print(f"Progress: {completed}/{total_to_download} files completed")

            except Exception as e:
                # Handle unexpected errors
                total_stats['failed'] += 1
                error_message = f"{filename} - Exception: {str(e)}"
                failed_files.append(error_message)
                print(f"[ERROR] {error_message}")

    elapsed_time = time.time() - start_time

    # Print download summary
    print("\n" + "="*80)
    print_summary(total_stats, len(files), failed_files, elapsed_time)

    # Step 2: Rename to publication format (unless --download-only)
    if not args.download_only:
        print("\n" + "="*80)
        print("Step 2: Renaming videos to publication format")
        print("="*80)

        try:
            # Import and run the renamer
            result = subprocess.run([
                sys.executable,
                'src/file_renamer.py',
                '--video-dir', str(download_path),
                '--year', str(pybay_year),
                '--url', talks_url
            ], capture_output=True, text=True)

            # Show renamer output
            if result.stdout:
                print(result.stdout)
            if result.stderr:
                print(result.stderr, file=sys.stderr)

            if result.returncode != 0:
                print(f"\n[WARNING] Renaming step failed with return code {result.returncode}")
                print("You can manually run the renamer later:")
                print(f"  python src/file_renamer.py --video-dir {download_path} --year {pybay_year}")
            else:
                print("\n" + "="*80)
                print("SUCCESS! All videos downloaded and renamed to publication format.")
                print("="*80)
        except Exception as e:
            print(f"\n[ERROR] Failed to run renamer: {e}")
            print("You can manually run the renamer:")
            print(f"  python src/file_renamer.py --video-dir {download_path} --year {pybay_year}")
    else:
        print("\n[INFO] --download-only specified, skipping rename step")
        print("To rename later, run:")
        print(f"  python src/file_renamer.py --video-dir {download_path} --year {pybay_year}")


if __name__ == '__main__':
    main()
