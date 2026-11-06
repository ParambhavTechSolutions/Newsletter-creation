# Architecture

How the newsletter generator is put together, who checks what, and where it goes next.

## 1. The WAT framework

| Layer | What it is | In this project |
|---|---|---|
| **Workflows** | Plain-English SOPs: steps, rules, edge cases, learnings | [workflows/generate_newsletter.md](../workflows/generate_newsletter.md) |
| **Agent** | The decision-maker: runs tools in order, reads output, retries and fixes problems, asks for approval | Claude Code |
| **Tools** | Deterministic Python scripts, one job each | [tools/](../tools/) |

**Why it's split this way:** if every step were done by AI at 90% accuracy, five steps would succeed only 59% of the time. Handing execution to predictable scripts keeps the AI on judgment calls.

### What was built vs. what is borrowed

| Part of an agent | Here | Built by |
|---|---|---|
| Model and reasoning loop | Claude Code | Anthropic (borrowed) |
| Tools | `tools/*.py` | This project |
| Instructions and guardrails | workflow, `config/brand.json`, `check_content.py`, `brand_check.py`, approval rule | This project |

`research_topic.py` and `write_newsletter.py` call an AI model (Groq), but they're **fixed pipeline steps**, not agents: they make one call and return, with no decisions or retries. The agent is whoever reads their output and decides what happens next.

## 2. Data flow

Steps communicate only through files in `.tmp/<slug>/`, so each step can be rerun or replaced on its own:

```
research.json  →  content.json  →  img/*.png  →  newsletter.html  →  Gmail draft  →  Sheets row
 (Research          (Newsletter      (render_        (build_                (send_via_       (archive_
  schema)            schema)          infographics)   newsletter)            gmail)           to_sheets)
```

Schemas live in [tools/schemas.py](../tools/schemas.py) (Pydantic). Brand settings live in [config/brand.json](../config/brand.json).

## 3. Who picks sources and who checks quality

**Source selection**
- *Default:* Groq (`openai/gpt-oss-120b` with browser search) searches and opens pages.
- `research_topic.py` then tests every URL. Items from dead links, or from pages the model never opened, are marked `verified_source: false` and excluded from writing.
- *In practice:* for niche or India-specific topics, the agent researches in session: it opens every page and records only what the page says.

**Quality checks: three layers**

| Layer | Checks | On failure |
|---|---|---|
| `check_content.py` (automatic) | Schema; every `[n]` citation has a source and every source is cited; every chart or stat number appears in the research; hype words; subject and preview length; 3–5 infographics; closing section mentions India | Errors block the build; warnings must be fixed by hand |
| `brand_check.py` (automatic) | Brand colours only, text contrast, logo ≥160px, alt text on every image, under Gmail's 102KB clip limit | No draft is created |
| Agent review | Do claims match their sources? Is the premise supported? Do the infographics look right? | Agent fixes `content.json` and reruns |
| Human approval | Final read of the Gmail draft | Nothing is sent without approval |

**What the automatic checks can't catch:** whether a sentence is true. That depends on the agent reading sources and on human review.

## 4. Editorial angle

Readers are Indian business owners. Each issue:
1. explores the technology **across the globe**, naming the country of each example;
2. closes with **"What this means for Indian businesses"**.

India-specific claims need an Indian source, and currencies stay as the source states them. This is enforced in `config/brand.json` (`market`), in the research and writing prompts, and as a warning in `check_content.py`.

## 5. How the system improves

Nothing learns automatically. Improvements happen when a problem is spotted and fixed in one of three places:

| Where | Example |
|---|---|
| Code (`tools/`) | Removed the Cloudflare `seed` field; fixed chart series colours; made citations readable in the dark box |
| Rules (prompts, `brand.json`, checks) | Indian-market angle; number tracing |
| Workflow learnings | "Groq unreliable for India topics; research in session" |

Git history plus the workflow's **Learnings** section are the memory of the system.

## 6. LangGraph analysis

LangGraph is **not used**. The step-to-step logic currently lives in the agent and the workflow file.

**Where it would fit:** as the coordinator for unattended client runs:

```
research → verify_sources ──(too few verified)──→ research (retry ≤2)
              ↓ ok
           write → check_content ──(errors)──→ write (fix)
              ↓ ok
   render → build → brand_check ──(fail)──→ build
              ↓ ok
        create_draft → ⏸ human approval → send → archive
```

**What it adds:**
- automatic retry loops;
- a pause that waits for client approval and resumes later;
- restarting from the failed step after a crash;
- separate state for each client.

**Decision:** not worth it for one person running issues with an agent supervising. Worth it once runs are scheduled, approvals come from clients, or many clients run in parallel. The tools already have clean file inputs and outputs, so they would become graph nodes with no rewrite.

**Alternative:** the Claude Agent SDK. It reuses the workflow as instructions, so it's more flexible but less predictable than a fixed graph.

## 7. Turning it into a Claude Code skill

Package the workflow as `.claude/skills/newsletter/SKILL.md`:

```markdown
---
name: newsletter
description: Research a topic and produce the branded Parambhaav newsletter as a Gmail draft.
---
1. Run tools/research_topic.py "<topic>"; check every source …
(steps, quality rules and the approval gate from workflows/generate_newsletter.md)
```

You can then trigger it with `/newsletter <topic>`. It runs the same steps every time and can be shared across client repos. The tools stay where they are.

## 8. Roadmap

1. Make in-session research and writing the default; keep Groq for unattended runs, or replace it with the Claude API.
2. Send through an email service (Brevo, Mailchimp or Zoho) for client lists: unsubscribe links, tracking, SPF/DKIM.
3. A `/newsletter` skill.
4. Unattended client runs using the Claude Agent SDK or LangGraph, with an approval step.
5. Generate LinkedIn and X posts from each issue.
6. Turn reviewer feedback into new rules or checks.
