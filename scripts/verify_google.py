"""Verify Google Calendar OAuth works. Prints calendar names and event counts only (no event details)."""
from datetime import datetime, timedelta, timezone
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
SECRETS = Path(__file__).resolve().parent.parent / "secrets"
CREDS_FILE = SECRETS / "credentials.json"
TOKEN_FILE = SECRETS / "google.token.json"


def get_creds() -> Credentials:
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)
        creds = flow.run_local_server(port=0)
    TOKEN_FILE.write_text(creds.to_json())
    TOKEN_FILE.chmod(0o600)
    return creds


def main() -> None:
    service = build("calendar", "v3", credentials=get_creds())
    now = datetime.now(timezone.utc)
    end = now + timedelta(days=45)
    calendars = service.calendarList().list().execute().get("items", [])
    print(f"Connected. {len(calendars)} calendar(s):")
    for cal in calendars:
        events = service.events().list(
            calendarId=cal["id"], timeMin=now.isoformat(), timeMax=end.isoformat(),
            singleEvents=True, maxResults=250,
        ).execute().get("items", [])
        print(f"  - {cal.get('summary')}: {len(events)} upcoming event(s)")


if __name__ == "__main__":
    main()
