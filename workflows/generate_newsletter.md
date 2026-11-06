# Generate Newsletter

## Objective
Turn a topic from Prashanth into a researched, Parambhaav Tech–branded HTML newsletter with 3–5 infographics. It is delivered as a **Gmail draft** for review, can then be sent to the distribution list, and is logged to a Google Sheets archive.

**Running cost: free.**
- Research and writing: Groq free tier (`openai/gpt-oss-120b` with built-in browser search).
- Illustrations: Cloudflare Workers AI free plan.
- Delivery: Gmail and Sheets on Google's free APIs.
- Rendering: local.

## Files
| File | Purpose |
|---|---|
| [config/brand.json](../config/brand.json) | Brand spec: palette, contrast rules, fonts, logo sizes, voice rules, AI image style anchor |
| [config/recipients.json](../config/recipients.json) | Gmail recipients: `test` (drafts and test sends) and `list` (the distribution list, sent as BCC) |
| [tools/prepare_brand_assets.py](../tools/prepare_brand_assets.py) | One-time: trims the logo PNGs in `brand_assests/` into email-ready logos in `config/assets/` |
| [tools/research_topic.py](../tools/research_topic.py) | Groq browser search → sourced research brief → structured `research.json` |
| [tools/write_newsletter.py](../tools/write_newsletter.py) | Groq → `content.json` (article + infographics) in the brand voice, then runs the integrity checks |
| [tools/groq_client.py](../tools/groq_client.py) | Shared Groq client, strict JSON-schema conversion, free-tier rate-limit handling |
| [tools/schemas.py](../tools/schemas.py) | The exact structure of `research.json` and `content.json` |
| [tools/save_research.py](../tools/save_research.py) | Pings every source URL and marks items as verified or not. Also the manual fallback for in-session research |
| [tools/check_content.py](../tools/check_content.py) | Validates `content.json`: schema, citations, numbers traceable to research, brand-voice words |
| [tools/generate_ai_infographic.py](../tools/generate_ai_infographic.py) | Cloudflare Workers AI (FLUX.1 schnell, free) → on-brand illustration PNG, cached by prompt |
| [tools/render_infographics.py](../tools/render_infographics.py) | Branded infographic cards (stats, chart, timeline, comparison, quote, AI image) → PNGs via Playwright |
| [tools/build_newsletter.py](../tools/build_newsletter.py) | Email-safe HTML with logo and infographics embedded, plain-text version, desktop/mobile previews |
| [tools/brand_check.py](../tools/brand_check.py) | Blocks delivery if colours, contrast, logo size, alt text or email size break the brand rules |
| [tools/send_via_gmail.py](../tools/send_via_gmail.py) | Gmail API: draft (default), test send, or BCC send to the list |
| [tools/archive_to_sheets.py](../tools/archive_to_sheets.py) | Appends the issue's log row to the Google Sheets archive |
| [tools/google_auth.py](../tools/google_auth.py) | Shared Google OAuth (Gmail + Sheets) |
| [tools/templates/](../tools/templates/) | Email and infographic designs (Jinja2), bundled fonts, Chart.js |
| [workflows/generate_newsletter.md](generate_newsletter.md) | This SOP: step by step, with edge cases |

## Inputs
| Input | Required | Default |
|---|---|---|
| Topic | yes | — |
| Audience | no | owners and leaders of medium-sized, traditional businesses in India |
| Focus / angle | no | none (`--focus "cost savings for small brokerages"`) |
| AI illustration | no | on (at most 1 per issue). Use `--no-ai-images` on write_newsletter to skip |
| Delivery | no | Gmail draft to `recipients.json → test` |

If the topic is vague (e.g. "AI"), ask one clarifying question about angle or audience before researching.

## Steps (run from project root with `.venv/bin/python`)
1. **Research:** `tools/research_topic.py "<topic>" [--focus "..."]`
   - Groq searches and opens pages, then writes `research_brief.md`.
   - A second call structures the brief into findings.
   - URLs are then checked. `research.json` marks `verified_source: false` on items whose URL is dead, or that the search tool never actually opened.
   - **Skim `research_brief.md`** for relevance and source quality.
2. **Write:** `tools/write_newsletter.py .tmp/<slug>/research.json [--no-ai-images]`
   - Output: `content.json`. Only verified research items are given to the model. The checks run automatically.
   - **Read every `warn` line.** Fix numbers "not found in research" and uncited sources by editing content.json directly, then rerun `tools/check_content.py`.
   - **Read the content itself.** This is the editorial checkpoint: tone, accuracy, relevance to Parambhaav's readers.
3. **Infographics:** `tools/render_infographics.py .tmp/<slug>/content.json`
   - Use `--only <id>` to redo one card.
   - **Look at every PNG**, especially the AI image (check it's on-brand and has no stray text).
4. **Build:** `tools/build_newsletter.py .tmp/<slug>/content.json`
   - Runs the brand check and stops if it fails.
   - **Look at preview.png and preview_mobile.png.**
5. **Draft:** `tools/send_via_gmail.py .tmp/<slug>/content.json`
   - Creates a Gmail draft to the test recipients and prints its link. Share the link with Prashanth.
6. **Send (only after Prashanth explicitly approves in chat):** `tools/send_via_gmail.py .tmp/<slug>/content.json --send --yes`
   - Use `--send-test` first if Prashanth wants to see it in the inbox.
7. **Archive:** `tools/archive_to_sheets.py .tmp/<slug>/content.json`
   - Run after step 5, and again after step 6.

**Fallback: if Groq is down or out of quota,** the agent can do steps 1–2 in session instead:
- Research with its own web search and write `.tmp/<slug>/research_draft.json` in the `Research` schema (`tools/schemas.py`).
- Run `tools/save_research.py` on it.
- Write `content.json` following the rules below.
- Run `tools/check_content.py`.

**One-time setup** (`.env`):
- **Groq:** create a free key at console.groq.com/keys and set `GROQ_API_KEY`. Optionally set `GROQ_MODEL` (default `openai/gpt-oss-120b`).
- **Cloudflare:**
  1. Sign up at dash.cloudflare.com.
  2. Go to **Workers AI → Use REST API**.
  3. Copy the **Account ID** and create an **API token** with the Workers AI template.
  4. Set `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN`.
- **Google:**
  1. Google Cloud → enable the **Gmail API**, **Google Sheets API** and **Google Drive API**.
  2. Create an OAuth client of type "Desktop app".
  3. Save the downloaded file as `credentials.json` in the project root.

  The first Google run opens a browser for consent.
- **Sheet ID:** `NEWSLETTER_SHEET_ID` fills itself in on the first archive run.
- **Logos:** run `tools/prepare_brand_assets.py` (again only if the logos change).
- **Recipients:** fill `config/recipients.json → list` before the first list send.

## Writing rules for content.json
These are built into write_newsletter.py's prompts. Apply them to any manual edits too.

**Structure**
- `subject` ≤ 60 chars, specific, no clickbait or emoji. `preview_text` 60–120 chars that add to the subject.
- `headline`: clear and outcome-led. `dek`: one sentence. `intro`: 1–2 paragraphs. `key_takeaways`: 3–4 bullets.
- `sections`: 3–5, each with 1–3 short paragraphs.
- **Editorial angle (standing rule, set 2026-11-06):** Prashanth is based in Bengaluru and the clients are Indian businesses. Sections explore the technology **across the globe** (name the country of each example). The issue then closes with how **Indian businesses** can apply it.
- India-specific claims need an Indian source. If none exists, say so; never invent an Indian angle. Keep currencies as the source states them.
- `business_takeaway`: heading "What this means for Indian businesses" and practical next steps for Indian businesses. Add `focus_areas` only for Parambhaav areas that genuinely apply (Real Estate, EduTech, Digital Services).
- `sources`: numbered from 1 in order of first use. Every `[n]` must exist, and every source must be cited.

**Fact integrity (non-negotiable)**
- Use only research items with `verified_source: true`.
- Never round up, combine or extrapolate numbers.
- Only put numbers in one chart when they share a metric and method.

**Brand voice:** plain business language, outcomes first, no jargon, hype or guaranteed results.

**Infographics:** 3–5 per issue, one per section, alternating dark/light.
- `stats`, `chart` (bar, hbar, line or doughnut), `timeline`, `comparison`, `quote`.
- `ai` (at most one): the prompt describes a scene only, never text, numbers or charts. The brand style is appended automatically.
- Every card needs `id`, `type`, `theme`, `title`, `alt` (what it shows, including key numbers) and `source`.

## Edge cases & failure handling
- **Groq "rate limit – waiting Ns":** normal on the free tier (about 8K tokens/minute). The tool waits and retries on its own.
- **Groq "daily free-tier limit reached":** about 200K tokens/day. A full issue uses roughly 25–40K. Wait until tomorrow, or use the in-session fallback.
- **Groq "request is larger than the tokens-per-minute limit":** the research is too big for one call. Narrow the topic with `--focus`, or delete weaker items from research.json, then rerun write_newsletter.
- **Groq output cut off / schema mismatch:** the tool retries schema mismatches automatically. If it's still failing, rerun, or narrow the topic.
- **Groq 401:** the key is wrong. Check `GROQ_API_KEY`.
- **Many unverified items in research:** the search opened few pages. Rerun research_topic, which is free. If a source is good but its URL is "blocked" (it refuses bots), that's fine; only "dead" and "not-opened" are excluded.
- **Thin research (fewer than 4 statistics):** expect timeline, quote, comparison and AI cards rather than charts. Don't force a chart.
- **Cloudflare "daily limit reached":** resets at 00:00 UTC. Either wait, or remove the `ai` card and its section reference from content.json.
- **Cloudflare 401/403:** the token lacks Workers AI permission. Create a new token from the Workers AI template.
- **AI image off-brand or contains text:**
  - Rerun `tools/generate_ai_infographic.py "<prompt>" --out .tmp/<slug>/img/<id>_raw.png --force` for a new random image (free).
  - Or reword the prompt.
  - Then rerun `render_infographics.py --only <id>`.
- **Infographic FAIL "never signalled ready":** a JS error in the chart spec. check_content catches label/value count mismatches.
- **Brand check FAIL:**
  - Off-palette colour: a template has a non-brand hex.
  - Size over 102KB: shorten the copy.
- **Gmail/Sheets auth error:** delete `token.json` and rerun.
- **List send blocked:** the list is empty, `--yes` is missing, or there are more than 500 recipients (Gmail's daily limit).

## Learnings
- 2026-11-05: Muted grey (#727983) on white is only 4.39:1, below WCAG AA for normal text. It is used only for decorative lines and chart fills. All small text is Charcoal.
- 2026-11-05: WCAG "large text" means ≥24px, or ≥18.7px bold. Small uppercase labels count as normal text.
- 2026-11-05: Gmail drops SVG and web fonts. Logos are trimmed PNGs (`config/assets/`), and email text falls back to Arial. Infographic PNGs render the real Montserrat/Inter fonts.
- 2026-11-05: The brand PNG logos have large empty canvases. `prepare_brand_assets.py` trims them and keeps clear space and proportions.
- 2026-11-05: The `gmail.compose` scope covers both drafts and sending, so no separate `gmail.send` scope is needed.
- 2026-11-05: Kie.ai is pay-as-you-go only, and Google's Gemini image models have no free API tier.
  - Cloudflare Workers AI's free plan (10,000 neurons/day) covers FLUX.1 schnell at roughly 100 neurons per image.
  - FLUX.1 schnell outputs only 1024×1024 JPEG, which the tool center-crops to the card's aspect ratio. The prompt limit is 2,048 characters, including the brand style anchor.
  - FLUX.2 klein needs a multipart request body whose REST fields aren't documented, so it isn't used.
- 2026-11-05: Groq's `groq/compound` web-search models were shut down on 21 Sep 2026. Web search now uses `openai/gpt-oss-120b` with the built-in `browser_search` tool.
  - browser_search can't be combined with structured outputs, so research is two calls: search, then structure.
  - Groq's own docs recommend `reasoning_effort: "low"` with browser search to limit token use.
- 2026-11-05: Groq strict JSON schema requires every property in `required` (optional fields as nullable unions) and `additionalProperties: false`, and doesn't support streaming.
  - `groq_client.strict_schema()` converts the Pydantic models.
  - Bug found and fixed: removing the schema keyword `title` must not also delete fields that are *named* `title`.
- 2026-11-05: The free tier for gpt-oss-120b is about 8K tokens/min and 200K/day, so writing is split into two calls (article, then infographics), with automatic waits on 429.
- 2026-11-06: Workers AI `flux-1-schnell` rejects a `seed` field ("Additional or unevaluated properties '/seed'"), so the request sends only `prompt` and `steps`. Each call already produces a different image.
- 2026-11-06 (first issue, HYROX 2027): Groq output needed heavy editing at both checkpoints.
  - Research: it paraphrased "quotes", turned a date into a statistic, made up a sponsor count, and left out the event list the topic asked for. Re-reading the 2-3 main source URLs fixed this in minutes.
  - Writing: it added derived numbers ("up 33%", "an event every three days"), listed one source per citation (21 entries for 3 URLs), and attached infographics to the wrong sections. check_content didn't catch the derived numbers that appeared in takeaways without a citation.
  - Always skim the brief against the sources before writing, and read content.json in full.
- 2026-11-06: Citation links in the dark business-takeaway box used Charcoal and were invisible. The `rich` filter now takes a colour (`rich(c.silver)`) for dark backgrounds.
- 2026-11-06 (UPSC + AI agencies): Groq research had 10 of 32 items on dead or unopened URLs and invented two named quotes. It also reversed a vendor comparison, presenting the "traditional evaluation" price as the vendor's own price. Research was rebuilt in session from 7 verified sources via save_research.py.
  - For niche or India-specific topics, expect to do research in session.
  - When the evidence doesn't support the topic's premise, say so in the copy rather than stretching it.
- 2026-11-06: Multi-series bar/line charts drew series 1 and 2 in black and charcoal, which look identical. chart.html.j2 now spaces series colours apart (`seriesOrder`), and the legend uses the same order.

**2026-11-06: global-to-India angle**
- Prashanth's readers are Indian businesses. Every issue now covers global examples first and closes with "What this means for Indian businesses".
- Changed: `config/brand.json` (`market`, voice, closing heading), the research prompt (regional spread and an INDIA CONTEXT block), the writing prompt, the template eyebrow, and a check_content warning when the takeaway doesn't mention India.
