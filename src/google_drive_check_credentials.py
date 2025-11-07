"""
Test Google Drive credentials from environment variable
"""
import os
import sys
import json

# Check for required dependencies
try:
    from google.oauth2 import service_account  # noqa
    from googleapiclient.discovery import build  # noqa
except ImportError as e:
    print("ERROR: Required Google API libraries not installed.")
    print("Please run: pip install -r requirements.txt")
    print(f"\nMissing module: {e.name}")
    sys.exit(1)

# If we get here, imports succeeded - re-import for clean scope
from google.oauth2 import service_account
from googleapiclient.discovery import build

def test_service_account_credentials():
    """Test service account credentials from environment variable."""

    # Get credentials from environment
    creds_json = os.environ.get('GOOGLE_DRIVE_API_KEY_PYBAY')

    if not creds_json:
        print("[ERROR] GOOGLE_DRIVE_API_KEY_PYBAY environment variable not found")
        return False

    print("[OK] Found GOOGLE_DRIVE_API_KEY_PYBAY environment variable")

    try:
        return verify_service_account_auth(creds_json)
    except json.JSONDecodeError as e:
        print(f"[ERROR] Failed to parse credentials JSON: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] {e}")
        return False


def verify_service_account_auth(creds_json):
    """Authenticate with service account and verify access to Google Drive."""
    # Parse JSON credentials
    creds_dict = json.loads(creds_json)
    print("[OK] Successfully parsed credentials JSON")
    print(f"  Project ID: {creds_dict.get('project_id')}")
    print(f"  Client Email: {creds_dict.get('client_email')}")

    # Create credentials object
    scopes = ['https://www.googleapis.com/auth/drive.readonly']
    credentials = service_account.Credentials.from_service_account_info(
        creds_dict, scopes=scopes
    )
    print("[OK] Created service account credentials object")

    # Build Drive service
    service = build('drive', 'v3', credentials=credentials)
    print("[OK] Built Google Drive service")

    # Test API call - list files in root (just to verify authentication works)
    print("\nTesting API access...")
    results = service.files().list(
        pageSize=10,
        fields="files(id, name)"
    ).execute()

    files = results.get('files', [])
    print("[OK] Successfully authenticated and accessed Google Drive")
    print(f"  Found at least {len(files)} file(s) accessible to this service account")

    if files:
        print("\n  Sample files:")
        for item in files[:5]:
            print(f"    - {item['name']}")
    else:
        print("\n  [NOTE] Service account has no files in 'My Drive'")
        print("    This is normal - service accounts need folder IDs shared with them")

    return True

if __name__ == '__main__':
    print("="*80)
    print("Testing Google Drive Service Account Credentials")
    print("="*80 + "\n")

    success = test_service_account_credentials()

    print("\n" + "="*80)
    if success:
        print("[OK] Credentials are valid and working!")
        print("\nNext steps:")
        print("  1. Ensure target folders are shared with the service account")
        print("  2. Use --service-account flag with google_drive_video_downloader.py")
    else:
        print("[ERROR] Credential test failed")
        print("\nPlease check:")
        print("  1. GOOGLE_DRIVE_API_KEY_PYBAY is set correctly")
        print("  2. Service account has necessary permissions")
    print("="*80)
