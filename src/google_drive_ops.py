"""
Google Drive operations module.

Handles authentication and Google Drive API interactions including
file listing, connection testing, URL parsing, and metadata saving.
"""

import os
import sys
import json
import re
from datetime import datetime
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Google Drive API scopes - read-only access
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']


def authenticate_with_oauth():
    """Authenticate with OAuth 2.0 and return Google Drive service instance."""
    creds = None
    token_file = 'token.json'
    credentials_file = 'credentials.json'

    # Check if credentials.json exists
    if not os.path.exists(credentials_file):
        print("\nERROR: 'credentials.json' file not found!")
        print("\nOptions:")
        print("  1. Set up OAuth credentials - See README_GOOGLE_DRIVE_SETUP.md for instructions")

        # Check if service account credentials might be available
        if os.environ.get('GOOGLE_DRIVE_API_KEY_PYBAY'):
            print("  2. Use service account - Add --service-account flag to your command")
            print("     (Detected GOOGLE_DRIVE_API_KEY_PYBAY environment variable)")

        sys.exit(1)

    # Load existing token if available
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)

    # If no valid credentials, authenticate
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing expired credentials...")
            creds.refresh(Request())
        else:
            print("\nOpening browser for Google authentication...")
            print("Please log in and authorize access to Google Drive.")
            flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save credentials for next run
        with open(token_file, 'w') as token:
            token.write(creds.to_json())
        print("[OK] Authentication successful! Token saved for future use.\n")

    return build('drive', 'v3', credentials=creds, cache_discovery=False)


def authenticate_with_service_account(env_var: str = 'GOOGLE_DRIVE_API_KEY_PYBAY', silent: bool = False):
    """
    Authenticate with service account and return Google Drive service instance.

    Args:
        env_var: Name of environment variable containing service account JSON
        silent: If True, suppress informational messages (for worker processes)

    Returns:
        Google Drive service instance
    """
    # Get credentials from environment
    creds_json = os.environ.get(env_var)

    if not creds_json:
        if not silent:
            print(f"\nERROR: '{env_var}' environment variable not found!")
            print("\nTo use service account authentication:")
            print(f"  export {env_var}='{{...service account JSON...}}'")
            print("\nOr switch to OAuth authentication by removing the --service-account flag")
        sys.exit(1)

    try:
        # Parse JSON credentials
        creds_dict = json.loads(creds_json)
        if not silent:
            print(f"[OK] Found service account credentials")
            print(f"  Project ID: {creds_dict.get('project_id')}")
            print(f"  Client Email: {creds_dict.get('client_email')}")

        # Create credentials object
        credentials = service_account.Credentials.from_service_account_info(
            creds_dict, scopes=SCOPES
        )
        if not silent:
            print(f"[OK] Service account authentication successful!\n")

        return build('drive', 'v3', credentials=credentials, cache_discovery=False)

    except json.JSONDecodeError as e:
        if not silent:
            print(f"\nERROR: Failed to parse service account JSON: {e}")
            print(f"Please check that {env_var} contains valid JSON")
        sys.exit(1)
    except Exception as e:
        if not silent:
            print(f"\nERROR: Failed to authenticate with service account: {e}")
        sys.exit(1)


def get_drive_service(use_service_account: bool = False, env_var: str = 'GOOGLE_DRIVE_API_KEY_PYBAY', silent: bool = False):
    """
    Authenticate and return Google Drive service instance.

    Args:
        use_service_account: If True, use service account auth. If False, auto-detect or use OAuth
        env_var: Environment variable name for service account credentials
        silent: If True, suppress informational messages (for worker processes)

    Returns:
        Google Drive service instance
    """
    # Auto-detect: If service account env var exists and --service-account not explicitly set,
    # default to service account mode
    if not use_service_account and os.environ.get(env_var):
        if not silent:
            print(f"[INFO] Detected {env_var} environment variable")
            print("[INFO] Using service account authentication (auto-detected)")
            print("[INFO] To use OAuth instead, ensure credentials.json exists\n")
        use_service_account = True

    if use_service_account:
        return authenticate_with_service_account(env_var, silent=silent)
    else:
        return authenticate_with_oauth()


def list_video_files(service, folder_id: str):
    """List all video files in the specified folder."""
    print(f"Fetching file list from folder ID: {folder_id}...")

    try:
        results = service.files().list(
            q=f"'{folder_id}' in parents and mimeType contains 'video/'",
            fields="files(id, name, size, md5Checksum)",
            pageSize=1000
        ).execute()

        files = results.get('files', [])
        print(f"[OK] Found {len(files)} video file(s)\n")
        return files

    except Exception as e:
        handle_list_videos_error(e)


def handle_list_videos_error(e):
    """Print error message for list_video_files failures."""
    print(f"ERROR: Could not access folder: {e}")
    print("\nMake sure:")
    print("  1. The folder ID is correct")
    print("  2. The folder is shared with your Google account")
    print("  3. You have at least 'Viewer' permissions")
    sys.exit(1)


def test_connection(service, folder_id: str, using_service_account: bool = False) -> bool:
    """
    Test connection to Google Drive by attempting to access the folder.

    Args:
        service: Google Drive API service instance
        folder_id: Folder ID to test access
        using_service_account: Whether service account authentication is being used

    Returns:
        True if connection successful, False otherwise
    """
    try:
        print("Testing connection to Google Drive...")
        # Attempt to list files in the folder (just get count)
        service.files().list(
            q=f"'{folder_id}' in parents",
            fields="files(id)",
            pageSize=1
        ).execute()
        print("[OK] Connection test successful!")
        return True
    except Exception as e:
        return handle_connection_error(e, folder_id, using_service_account)


def handle_connection_error(e, folder_id: str, using_service_account: bool):
    """
    Print helpful error message based on the exception type and authentication method.
    """
    error_str = str(e)
    print(f"\n[ERROR] Connection test failed: {e}\n")

    # Detect specific error types
    is_permission_error = '403' in error_str or 'insufficient' in error_str.lower() or 'permission' in error_str.lower()
    is_not_found = '404' in error_str or 'not found' in error_str.lower()

    if is_permission_error or is_not_found:
        print("PERMISSION OR ACCESS ISSUE DETECTED\n")
        print("Common causes:")
        print(f"  1. Folder ID '{folder_id}' may be incorrect")
        print("  2. Folder is not shared with your account")

        if using_service_account:
            print("\n[INFO] You are using SERVICE ACCOUNT authentication")
            print("Service accounts require explicit folder sharing:")
            print("  • Open the folder in Google Drive web interface")
            print("  • Click 'Share' button")
            print("  • Add the service account email (ends with @*.iam.gserviceaccount.com)")
            print("  • Grant at least 'Viewer' permission")
            print("  • IMPORTANT: Service accounts don't have access to 'My Drive' - folders must be explicitly shared")
        else:
            print("\n[INFO] You are using OAUTH authentication")
            print("  • Make sure you're logged in with the correct Google account")
            print("  • Ensure the folder is accessible to that account")
            print("  • Try opening the folder in your browser while logged in")
    else:
        print("Please check:")
        print("  1. Your internet connection is working")
        print("  2. Google Drive API is enabled in your project")
        print("  3. You have valid authentication credentials")
    return False


def extract_folder_id(folder_input: str) -> str:
    """
    Extract Google Drive folder ID from URL or return as-is if already an ID.

    Supports various Google Drive URL formats:
        - https://drive.google.com/drive/folders/FOLDER_ID
        - https://drive.google.com/drive/u/0/folders/FOLDER_ID
        - https://drive.google.com/drive/u/1/folders/FOLDER_ID?...
        - FOLDER_ID (direct ID, returned as-is)

    Args:
        folder_input: Google Drive folder URL or folder ID

    Returns:
        Extracted folder ID
    """
    # If it's already just an ID (no slashes or URL components), return it
    if '/' not in folder_input and 'drive.google.com' not in folder_input:
        return folder_input.strip()

    # Try to extract from URL patterns
    patterns = [
        r'/folders/([a-zA-Z0-9_-]+)',  # Match /folders/ID
        r'id=([a-zA-Z0-9_-]+)',        # Match id=ID (alternative format)
    ]

    for pattern in patterns:
        match = re.search(pattern, folder_input)
        if match:
            folder_id = match.group(1)
            print(f"[INFO] Extracted folder ID from URL: {folder_id}")
            return folder_id

    # If no pattern matched, return original (might be a valid ID)
    return folder_input.strip()


def save_folder_metadata(service, folder_id: str, destination_dir: Path, pybay_year: int) -> Path:
    """
    Fetch and save Google Drive folder metadata to JSON file.

    Creates a metadata file before downloading to preserve original filenames
    and file properties for future reference.

    Args:
        service: Authenticated Google Drive service
        folder_id: Google Drive folder ID
        destination_dir: Directory where metadata JSON will be saved
        pybay_year: PyBay year (e.g., 2025) for filename

    Returns:
        Path to saved metadata JSON file
    """
    print(f"[INFO] Fetching folder metadata...")

    # List files in folder
    files = list_video_files(service, folder_id)

    # Build metadata structure
    metadata = {
        'pybay_year': pybay_year,
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

    # Generate metadata filename with PyBay year
    metadata_filename = f"_pybay_{pybay_year}_gdrive_metadata.json"
    metadata_path = destination_dir / metadata_filename

    # Save metadata
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    print(f"[OK] Saved folder metadata: {metadata_filename}")
    print(f"     Files: {metadata['file_count']}")
    print(f"     Folder ID: {folder_id}")

    return metadata_path
