# Workflow SOP Conventions

Each workflow is a Markdown file named `snake_case.md` (e.g. `generate_newsletter_issue.md`).

Every workflow should have these sections:

1. **Objective** — what this workflow achieves, in one or two sentences.
2. **Inputs** — what's required to run it (topics, URLs, dates, IDs) and where it comes from.
3. **Tools** — which scripts in `tools/` to run, in order, with example commands.
4. **Outputs** — what gets produced and where it lands (cloud deliverable vs `.tmp/` intermediate).
5. **Edge cases & failure handling** — what to do when a step fails, returns nothing, or hits limits.
6. **Learnings** — running log of quirks discovered (rate limits, API behavior, fixes). Append, don't overwrite.
