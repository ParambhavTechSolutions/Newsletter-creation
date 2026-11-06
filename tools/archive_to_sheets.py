"""Append a newsletter delivery record to the Google Sheets archive.

Usage: .venv/bin/python tools/archive_to_sheets.py .tmp/<slug>/content.json

Reads .tmp/<slug>/delivery.json (written by send_via_gmail.py). If NEWSLETTER_SHEET_ID is empty in .env,
creates a "Parambhaav Newsletter Archive" sheet in Prashanth's Drive and saves its ID to .env.
"""
import argparse
import os
import re
from pathlib import Path

from dotenv import load_dotenv, set_key

from common import ROOT, fail, load_json

HEADER = ["Date", "Slug", "Topic", "Subject", "Status", "Recipients", "Sources", "Infographics", "Gmail IDs"]
SHEET_TITLE = "Parambhaav Newsletter Archive"


def add_header(ws):
    ws.update(range_name="A1", values=[HEADER])
    # Header row in brand Primary black (#090A0C) with white bold text
    ws.format("A1:I1", {"backgroundColor": {"red": 0.035, "green": 0.039, "blue": 0.047},
                        "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}}})
    ws.freeze(rows=1)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("content_json")
    args = ap.parse_args()

    d = Path(args.content_json).resolve().parent
    delivery = d / "delivery.json"
    if not delivery.exists():
        fail(f"Missing {delivery.relative_to(ROOT)} - run send_via_gmail.py first")
    rec = load_json(delivery)

    import gspread
    from google_auth import get_credentials
    gc = gspread.authorize(get_credentials())

    load_dotenv(ROOT / ".env")
    sheet_id = (os.getenv("NEWSLETTER_SHEET_ID") or "").strip()
    # Accept a bare ID or a pasted sheet URL / partial URL (".../d/<ID>/edit#gid=0")
    m = re.search(r"/d/([A-Za-z0-9_-]{25,})", sheet_id) or re.search(r"([A-Za-z0-9_-]{25,})", sheet_id)
    sheet_id = m.group(1) if m else ""
    if sheet_id:
        try:
            sh = gc.open_by_key(sheet_id)
        except Exception as e:
            fail(f"Could not open sheet {sheet_id}: {e}")
        ws = sh.sheet1
        if not ws.row_values(1):            # blank sheet made by hand: give it the archive header
            add_header(ws)
            if sh.title == "Untitled spreadsheet":
                sh.update_title(SHEET_TITLE)
            print("  added header row to the archive sheet")
    else:
        sh = gc.create(SHEET_TITLE)
        ws = sh.sheet1
        add_header(ws)
        set_key(str(ROOT / ".env"), "NEWSLETTER_SHEET_ID", sh.id, quote_mode="never")
        print(f"  created sheet '{SHEET_TITLE}' and saved its ID to .env")
        sheet_id = sh.id

    row = [rec["date"], rec["slug"], rec.get("topic") or "", rec["subject"], rec["status"],
           rec["recipient_count"], rec.get("sources", 0), rec.get("infographics", 0), ", ".join(rec.get("ids", []))]
    ws.append_row(row, value_input_option="USER_ENTERED")
    print(f"OK  archived to https://docs.google.com/spreadsheets/d/{sheet_id}")


if __name__ == "__main__":
    main()
