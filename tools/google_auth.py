"""Shared Google OAuth for Gmail + Sheets tools.

credentials.json (OAuth Desktop client) lives in the project root; token.json is saved there after
the first consent. If token.json was created with fewer scopes than SCOPES, it is discarded and the
browser consent runs again.
"""
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from common import ROOT, fail

SCOPES = [
    "https://www.googleapis.com/auth/gmail.compose",   # create drafts + send (no inbox read access)
    "https://www.googleapis.com/auth/spreadsheets",    # archive log sheet
    "https://www.googleapis.com/auth/drive.file",      # create the archive sheet (only files this app creates)
]
TOKEN = ROOT / "token.json"
CREDS = ROOT / "credentials.json"


def get_credentials() -> Credentials:
    creds = None
    if TOKEN.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN))
        if not set(SCOPES).issubset(set(creds.scopes or [])):
            print("  token.json is missing newer scopes - re-running Google consent")
            creds = None
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception:
            creds = None
    if not creds or not creds.valid:
        if not CREDS.exists():
            fail("credentials.json not found in project root. In Google Cloud Console: enable the Gmail API "
                 "and Google Sheets API, create an OAuth client of type 'Desktop app', download it as credentials.json.")
        creds = InstalledAppFlow.from_client_secrets_file(str(CREDS), SCOPES).run_local_server(port=0)
    TOKEN.write_text(creds.to_json())
    return creds
