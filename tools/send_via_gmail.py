"""Deliver a built newsletter through Gmail, with infographics embedded inline (CID).

Usage:
  .venv/bin/python tools/send_via_gmail.py .tmp/<slug>/content.json                 # draft to test recipients (default)
  .venv/bin/python tools/send_via_gmail.py .tmp/<slug>/content.json --send-test     # send to test recipients
  .venv/bin/python tools/send_via_gmail.py .tmp/<slug>/content.json --send --yes    # send to the distribution list
  .venv/bin/python tools/send_via_gmail.py .tmp/<slug>/content.json --dry-run       # write newsletter.eml only

Recipients come from config/recipients.json ("test" and "list"). List sends go out as BCC in batches
(To: the sender) so subscribers never see each other's addresses. --send requires --yes, and the
agent must get Prashanth's explicit OK in chat before running it.

Writes .tmp/<slug>/delivery.json and appends to issues_log.json. Run archive_to_sheets.py afterwards.
"""
import argparse
import base64
import json
from datetime import datetime
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path

from common import ROOT, fail, load_brand, load_json, write_json

LOG = ROOT / "issues_log.json"
RECIPIENTS = ROOT / "config" / "recipients.json"
BCC_BATCH = 50          # keep each message well under Gmail's per-message recipient limits
DAILY_LIMIT = 500       # consumer Gmail sending limit per rolling 24h


def build_message(d: Path, content: dict, brand: dict, sender: str, to: list, bcc: list = None) -> EmailMessage:
    html_path, txt_path, img_map_path = d / "newsletter.html", d / "newsletter.txt", d / "images.json"
    for p in (html_path, txt_path, img_map_path):
        if not p.exists():
            fail(f"Missing {p.relative_to(ROOT)} - run build_newsletter.py first")
    images = json.loads(img_map_path.read_text())

    msg = EmailMessage()
    msg["Subject"] = content["subject"]
    msg["From"] = formataddr((brand["email"]["from_name"], sender))
    msg["To"] = ", ".join(to)
    if bcc:
        msg["Bcc"] = ", ".join(bcc)
    msg.set_content(txt_path.read_text())
    msg.add_alternative(html_path.read_text(), subtype="html")
    html_part = msg.get_payload()[1]
    for cid, path in images.items():
        html_part.add_related(Path(path).read_bytes(), maintype="image", subtype="png",
                              cid=f"<{cid}>", filename=f"{cid}.png", disposition="inline")
    return msg


def raw(msg):
    return base64.urlsafe_b64encode(msg.as_bytes()).decode()


def gmail():
    from googleapiclient.discovery import build
    from google_auth import get_credentials
    return build("gmail", "v1", credentials=get_credentials(), cache_discovery=False)


def record(d, content, mode, recipients, ids):
    entry = {"date": datetime.now().isoformat(timespec="minutes"), "slug": d.name, "topic": content.get("topic"),
             "subject": content["subject"], "status": mode, "recipient_count": len(recipients),
             "ids": ids, "sources": len(content.get("sources", [])),
             "infographics": len(content.get("infographics", []))}
    write_json(d / "delivery.json", entry)
    log = json.loads(LOG.read_text()) if LOG.exists() else []
    log.append(entry)
    write_json(LOG, log)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("content_json")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--send-test", action="store_true", help="send to test recipients")
    mode.add_argument("--send", action="store_true", help="send to the distribution list (needs --yes)")
    mode.add_argument("--dry-run", action="store_true", help="write newsletter.eml instead of calling Gmail")
    ap.add_argument("--yes", action="store_true", help="confirm a --send to the full list")
    args = ap.parse_args()

    d = Path(args.content_json).resolve().parent
    content = load_json(Path(args.content_json).resolve())
    brand = load_brand()
    rcpt = load_json(RECIPIENTS)
    test, subscribers = rcpt.get("test", []), rcpt.get("list", [])
    if not test:
        fail("config/recipients.json has no 'test' addresses")
    sender = test[0]

    if args.dry_run:
        msg = build_message(d, content, brand, sender, test)
        (d / "newsletter.eml").write_bytes(msg.as_bytes())
        print(f"OK  dry run: {(d / 'newsletter.eml').relative_to(ROOT)} ({len(msg.as_bytes()) / 1048576:.2f}MB)")
        return

    if args.send:
        if not subscribers:
            fail("config/recipients.json 'list' is empty - add subscriber addresses first")
        if not args.yes:
            fail(f"--send would email {len(subscribers)} people. Re-run with --yes once Prashanth has approved.")
        if len(subscribers) > DAILY_LIMIT:
            fail(f"{len(subscribers)} recipients exceeds Gmail's ~{DAILY_LIMIT}/day limit - use a newsletter platform")

    probe = build_message(d, content, brand, sender, test)
    size_mb = len(probe.as_bytes()) / 1048576
    if size_mb > 20:
        fail(f"Email is {size_mb:.1f}MB - reduce infographic count/size")

    svc = gmail()
    try:
        if args.send:
            ids = []
            for i in range(0, len(subscribers), BCC_BATCH):
                batch = subscribers[i:i + BCC_BATCH]
                m = build_message(d, content, brand, sender, [sender], bcc=batch)
                ids.append(svc.users().messages().send(userId="me", body={"raw": raw(m)}).execute()["id"])
                print(f"  sent batch {i // BCC_BATCH + 1}: {len(batch)} recipients")
            record(d, content, "sent", subscribers, ids)
            print(f"OK  sent to {len(subscribers)} subscribers in {len(ids)} message(s)")
        elif args.send_test:
            sent = svc.users().messages().send(userId="me", body={"raw": raw(probe)}).execute()
            record(d, content, "test-sent", test, [sent["id"]])
            print(f"OK  test send to {', '.join(test)}")
        else:
            draft = svc.users().drafts().create(userId="me", body={"message": {"raw": raw(probe)}}).execute()
            record(d, content, "draft", test, [draft["id"]])
            print(f"OK  Gmail draft created ({size_mb:.2f}MB) to {', '.join(test)}")
            print(f"    https://mail.google.com/mail/u/0/#drafts?compose={draft['message']['id']}")
    except Exception as e:
        fail(f"Gmail API error: {e}")


if __name__ == "__main__":
    main()
