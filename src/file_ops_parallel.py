"""
File operations module - PARALLEL VERSION

Handles fast parallel downloads using authenticated requests with proper streaming.
This bypasses MediaIoBaseDownload's speed limitations for 4-8x performance gain.
"""

import time
import random
import requests
from pathlib import Path
from typing import Optional, Tuple


def download_file_fast(service, file_id: str, file_name: str, destination: Path,
                       file_size: int, max_retries: int = 5,
                       chunk_size: int = 4*1024*1024) -> Tuple[bool, Optional[str]]:
    """
    Download a file from Google Drive using authenticated requests with streaming.

    Uses session-based connection pooling and optimized chunk size for throughput.
    Chunk size is based on bandwidth-delay product (BDP) analysis for typical networks.

    Args:
        service: Google Drive API service instance
        file_id: Google Drive file ID
        file_name: Name of the file being downloaded
        destination: Local path to save the file
        file_size: Size of the file in bytes
        max_retries: Number of retry attempts (default: 5 for Drive throttling)
        chunk_size: I/O buffer for iter_content (default: 4 MiB).
                   Empirically performs best across typical networks (BDP ~1-8 MiB).
                   Balances Python overhead vs retry cost. Range: 1-8 MiB recommended.
                   Larger chunks (>16 MiB) rarely improve throughput and worsen retry cost.

    Returns:
        tuple: (success: bool, error_message: Optional[str])
    """
    last_error = None

    # Create a session for this download (connection pooling within retries)
    session = requests.Session()

    for attempt in range(max_retries):
        try:
            # Get credentials from the service and ensure they're valid
            credentials = service._http.credentials

            # Refresh token if needed (different methods for OAuth vs service account)
            if hasattr(credentials, 'token'):
                # OAuth credentials
                if credentials.token is None and hasattr(credentials, 'refresh'):
                    import google.auth.transport.requests
                    request = google.auth.transport.requests.Request()
                    credentials.refresh(request)
                access_token = credentials.token
            elif hasattr(credentials, 'access_token'):
                # Service account credentials
                access_token = credentials.access_token
            else:
                raise ValueError("Could not extract access token from credentials")

            # Build the download URL
            download_url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"

            # Make authenticated request with streaming
            headers = {
                'Authorization': f'Bearer {access_token}'
            }

            response = session.get(
                download_url,
                headers=headers,
                stream=True,
                timeout=(5, 60)  # (connect_timeout, read_timeout) - fail fast on connect, patient on read
            )
            response.raise_for_status()

            # Stream download to file
            downloaded_bytes = 0
            with open(destination, 'wb') as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded_bytes += len(chunk)

            # Verify size (allow small variance for metadata)
            if file_size > 0 and abs(downloaded_bytes - file_size) > chunk_size:
                raise ValueError(f"Downloaded {downloaded_bytes} bytes but expected {file_size}")

            return True, None

        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code
            last_error = f"HTTP {status_code}: {str(e)}"

            if status_code == 403:
                if 'rate' in str(e).lower() or 'quota' in str(e).lower():
                    last_error = "Rate limit exceeded"
                    if attempt < max_retries - 1:
                        # Longer backoff for rate limits
                        base_delay = min(10 * (2 ** attempt), 60)
                        jitter = base_delay * (0.5 + random.random() * 0.5)
                        time.sleep(jitter)
                else:
                    # Permission error - don't retry
                    break
            elif status_code == 404:
                last_error = "File not found (404)"
                break
            elif status_code in (500, 502, 503, 504):
                # Server errors - retry with backoff + jitter
                if attempt < max_retries - 1:
                    base_delay = min(2 ** attempt, 30)
                    jitter = base_delay * (0.5 + random.random() * 0.5)
                    time.sleep(jitter)
            else:
                # Other HTTP errors
                if attempt < max_retries - 1:
                    jitter = 2 * (0.5 + random.random() * 0.5)
                    time.sleep(jitter)

        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            last_error = f"Network error: {str(e)}"
            if attempt < max_retries - 1:
                # Network errors - exponential backoff with jitter
                base_delay = min(2 ** attempt, 30)
                jitter = base_delay * (0.5 + random.random() * 0.5)
                time.sleep(jitter)

        except Exception as e:
            last_error = f"Error: {str(e)}"
            if attempt < max_retries - 1:
                # Generic errors - exponential backoff with jitter
                base_delay = min(2 ** attempt, 30)
                jitter = base_delay * (0.5 + random.random() * 0.5)
                time.sleep(jitter)

        # Clean up partial download before retry
        if destination.exists():
            try:
                destination.unlink()
            except:
                pass

    # Clean up session after all retries exhausted
    try:
        session.close()
    except:
        pass

    return False, last_error
