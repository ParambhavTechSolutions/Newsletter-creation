# Tools Conventions

- One script, one job. Name scripts `verb_noun.py` (e.g. `scrape_rss_feeds.py`, `send_newsletter.py`).
- Load secrets with `python-dotenv` from the project `.env` — never hardcode keys.
- Take inputs as CLI arguments; write intermediate files to `.tmp/`.
- Print a clear success/failure summary and exit non-zero on failure.
- Run with the project venv: `.venv/bin/python tools/<script>.py ...`

## Newsletter generator tools
The full file list and run order are in `workflows/generate_newsletter.md`.

Order: `research_topic` (Groq, + `save_research`) → `write_newsletter` (Groq, + `check_content`) → `render_infographics` (+ `generate_ai_infographic`) → `build_newsletter` (+ `brand_check`) → `send_via_gmail` → `archive_to_sheets`.
