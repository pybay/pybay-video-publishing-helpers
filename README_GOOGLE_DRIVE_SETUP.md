# Google Drive API Setup

Authentication setup for downloading PyBay conference videos from Google Drive.

## Quick Start

**For volunteers (one-time use):** Use OAuth authentication (browser login) - follow steps below.

**For automation (already have creds in ENV vars):** Use Service Account authentication - skip to [Service Account Setup](#service-account-setup).

**Why two methods?** OAuth is simpler for personal use but requires browser access. Service accounts work headless but require sharing folders with a service account email.

---

## OAuth Setup (One-Time Volunteer Use)

### Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

**Prerequisites:** Google account with access to shared Drive folder, Python 3.10+

### Step 2: Create Google Cloud Project

1. Go to https://console.cloud.google.com/
2. Click project dropdown → "NEW PROJECT"
3. Name: `PyBay Video Downloader`
4. Click "CREATE" and select your new project

### Step 3: Enable Google Drive API

1. Go to "APIs & Services" → "Library"
2. Search for "Google Drive API"
3. Click "ENABLE"

### Step 4: Create OAuth 2.0 Credentials

1. **Configure OAuth Consent Screen**
   - Go to "APIs & Services" → "Credentials"
   - Click "CONFIGURE CONSENT SCREEN"
   - Select "External" → "CREATE"
   - Fill in: App name, your email (user support + developer contact)
   - Click "SAVE AND CONTINUE" through Scopes
   - Add your Gmail address as a test user
   - Click "BACK TO DASHBOARD"

2. **Create OAuth Client ID**
   - Go to "Credentials" → "+ CREATE CREDENTIALS" → "OAuth client ID"
   - Application type: "Desktop app"
   - Name: `PyBay Downloader`
   - Click "CREATE"

3. **Download Credentials**
   - Click "DOWNLOAD JSON"
   - Save as `credentials.json` in the project directory

### Step 5: Get Folder ID

1. Open shared folder in Google Drive
2. Copy the ID from the URL: `https://drive.google.com/drive/folders/YOUR_FOLDER_ID`
3. The long string after `/folders/` is your Folder ID

### Step 6: Run the Script

**First run:**

```bash
python src/google_drive_video_downloader.py \
  --gdrive-url "YOUR_FOLDER_ID" \
  --output-path "pybay_videos_destination" \
  --year 2025
```

**What happens:**
1. Browser opens for Google sign-in
2. Warning appears: "Google hasn't verified this app" (normal for personal projects)
   - Click "Advanced" → "Go to PyBay Downloader (unsafe)" (it's your own app!)
3. Click "Allow" to grant Drive access
4. `token.json` created automatically (reused on subsequent runs)
5. Videos download and rename automatically

**Subsequent runs:** No browser login needed - script reuses `token.json`.

---

## Troubleshooting OAuth

**"credentials.json not found"**
- Ensure file is in project root directory
- Check filename is exactly `credentials.json`

**"Could not access folder"**
- Verify folder ID is correct
- Ensure folder is shared with your Google account (Viewer permission minimum)

**"Access blocked: Invalid request"**
- Add your email as test user in OAuth consent screen
- Ensure app is in "Testing" mode

**"Token expired or revoked"**
- Delete `token.json` and re-run script to re-authenticate

**Security:** Never commit `credentials.json` or `token.json` to version control - they grant access to your Drive.

---

## Service Account Setup

**Why use service accounts?** If you're doing this, you probably need to work with Google Workspace projects regularly.  If you don't have this, don't feel like you need to add it - it's just a convenience and only worth it if you work with the Google Cloud assets regularly.  

**Trade-off:** Folders you are downloading from must be explicitly shared with the service account email (service accounts have no "My Drive").

### Step 1: Create Service Account

1. Go to https://console.cloud.google.com/
2. Create new project (or use existing)
3. Enable Google Drive API ("APIs & Services" → "Library")
4. Go to "Credentials" → "+ CREATE CREDENTIALS" → "Service account"
5. Name: `pybay-video-downloader` → "CREATE AND CONTINUE" → "DONE"
6. Click service account email → "KEYS" tab → "ADD KEY" → "Create new key" → "JSON"
7. Save the downloaded JSON file securely
8. **Copy the service account email** (format: `name@project-id.iam.gserviceaccount.com`)

### Step 2: Share Folder

1. Open Drive folder → "Share"
2. Add service account email
3. Permission: "Viewer"
4. Uncheck "Notify people" (it's a bot!)
5. Click "Share"

### Step 3: Set Environment Variable

**Linux/Mac/WSL:**
```bash
export GOOGLE_DRIVE_API_KEY_PYBAY=$(cat path/to/service-account-key.json)

# Make permanent (optional):
echo "export GOOGLE_DRIVE_API_KEY_PYBAY='$(cat path/to/key.json)'" >> ~/.bashrc
```

**Windows PowerShell:**
```powershell
$env:GOOGLE_DRIVE_API_KEY_PYBAY=$(Get-Content path\to\service-account-key.json -Raw)
```

### Step 4: Run Script

```bash
python src/google_drive_video_downloader.py \
  --gdrive-url YOUR_FOLDER_ID \
  --output-path pybay_videos \
  --year 2025 \
  --service-account
```

---

## Troubleshooting Service Accounts

**"Environment variable not found"**
- Check variable is set: `echo $GOOGLE_DRIVE_API_KEY_PYBAY`
- Verify JSON is valid: `echo $GOOGLE_DRIVE_API_KEY_PYBAY | python -m json.tool`

**"Could not access folder"**
- Ensure folder is shared with service account email
- Verify "Viewer" permission or higher

**Security:** Never commit service account JSON to version control. Rotate keys periodically.
