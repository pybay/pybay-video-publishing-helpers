"""
Progress tracking utilities for parallel downloads.

Provides thread-safe progress tracking with tqdm for monitoring
multiple concurrent download operations.
TODO: Currently not used, started but removed when we revised our parallel download model.  Would be nice addition.
"""

import threading
import time
from tqdm import tqdm


class ProgressTracker:
    """
    Thread-safe progress tracker for parallel downloads.
    Displays minimalist single-line stats: files, size, percentage, active count, speed.
    Updates at most every 2 seconds to avoid overwhelming the display.
    """

    def __init__(self, total_files: int, total_bytes: int):
        self.total_files = total_files
        self.total_bytes = total_bytes
        self.completed_files = 0
        self.completed_bytes = 0
        self.failed_files = 0

        # Active downloads: {filename: (current_bytes, total_bytes)}
        self.active_downloads = {}

        # Speed tracking (exponential moving average)
        self.speed_samples = []  # List of (timestamp, bytes_completed)
        self.avg_speed = 0  # Bytes per second
        self.last_update = time.time()

        # Thread safety - use RLock (reentrant) since _update_description is called while holding lock
        self.lock = threading.RLock()

        # Create tqdm progress bar (minimalist single-line display)
        self.pbar = tqdm(
            total=total_bytes,
            unit='B',
            unit_scale=True,
            unit_divisor=1024,
            bar_format='{desc}',  # Single line, stats only
            dynamic_ncols=True,
            mininterval=2.0  # Update display at most every 2 seconds
        )
        self._update_description()

    def _update_description(self):
        """Update the progress bar description with current status (minimalist stats only)."""
        with self.lock:
            # Calculate stats
            completed_gb = self.completed_bytes / (1024**3)
            total_gb = self.total_bytes / (1024**3)
            pct = int((self.completed_bytes / self.total_bytes * 100)) if self.total_bytes > 0 else 0
            active_count = len(self.active_downloads)

            # Format speed
            if self.avg_speed > 0:
                speed_mb = self.avg_speed / (1024**2)
                speed_str = f"{speed_mb:.1f} MB/s"
            else:
                speed_str = "calculating..."

            # Minimalist format: "2/26 files (7.3/58.3 GB) - 12% | 4 active | 2.3 MB/s"
            desc = f"{self.completed_files}/{self.total_files} files ({completed_gb:.1f}/{total_gb:.1f} GB) - {pct}% | {active_count} active | {speed_str}"
            self.pbar.set_description(desc)

    def _calculate_speed(self):
        """Calculate exponential moving average speed over last 60 seconds."""
        now = time.time()
        cutoff = now - 60  # 60-second window

        # Remove old samples
        self.speed_samples = [(t, b) for t, b in self.speed_samples if t > cutoff]

        # Add current sample
        self.speed_samples.append((now, self.completed_bytes))

        # Calculate speed if we have at least 2 samples
        if len(self.speed_samples) >= 2:
            time_diff = self.speed_samples[-1][0] - self.speed_samples[0][0]
            bytes_diff = self.speed_samples[-1][1] - self.speed_samples[0][1]
            if time_diff > 0:
                self.avg_speed = bytes_diff / time_diff

    def start_download(self, filename: str, total_bytes: int):
        """Mark a file as starting download."""
        with self.lock:
            self.active_downloads[filename] = (0, total_bytes)
            self._update_description()

    def update_download(self, filename: str, current_bytes: int, total_bytes: int):
        """Update progress for an active download."""
        with self.lock:
            if filename in self.active_downloads:
                self.active_downloads[filename] = (current_bytes, total_bytes)
                self._calculate_speed()
                self._update_description()

    def complete_download(self, filename: str, success: bool, file_bytes: int):
        """Mark a file as completed (success or failure)."""
        # Update state inside lock, but do I/O outside lock to avoid threading issues
        with self.lock:
            if filename in self.active_downloads:
                del self.active_downloads[filename]

            if success:
                self.completed_files += 1
                self.completed_bytes += file_bytes
                self.pbar.update(file_bytes)
            else:
                self.failed_files += 1

            self._calculate_speed()
            self._update_description()

        # Print OUTSIDE lock to avoid race conditions with tqdm and terminal I/O
        # Only print successes - failures are shown in final summary
        if success:
            print(f"\n[OK] {filename} ({self._format_bytes_human_readable(file_bytes)})")

    def skip_file(self, filename: str, file_bytes: int):
        """Mark a file as skipped (already exists)."""
        with self.lock:
            self.completed_files += 1
            self.completed_bytes += file_bytes
            self.pbar.update(file_bytes)
            self._update_description()

    def close(self):
        """Close the progress bar."""
        self.pbar.close()

    @staticmethod
    def _format_bytes_human_readable(bytes_val: int) -> str:
        """Format bytes into human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_val < 1024.0:
                return f"{bytes_val:.1f} {unit}"
            bytes_val /= 1024.0
        return f"{bytes_val:.1f} TB"
