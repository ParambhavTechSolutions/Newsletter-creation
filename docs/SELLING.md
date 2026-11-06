# Selling the Newsletter Service

Sell it as a **done-for-you service**, not software. Clients want to stay in front of their customers without spending hours on it. Parambhaav runs the system, and the client gets a finished, branded newsletter to approve.

## Who to target first

| Sector | Why they'd pay | Example issue |
|---|---|---|
| 🏠 Real estate (builders, brokers) | Buyers take months to decide | Global smart-home trends and what they mean for Bengaluru buyers |
| 🎓 Coaching institutes / EdTech | Parents and students compare options for weeks | AI in UPSC coaching (sample in `docs/images/`) |
| 🏥 Clinics, diagnostics | Trust and repeat visits | Health-tech explained simply |
| 🏭 Manufacturers / B2B | Long sales cycles, few touchpoints | Industry trends for their buyers |
| 💼 CA firms, consultants | Need to look like experts | Monthly regulatory and tech updates |

Start with **one sector** so samples and case studies build on each other.

## The pitch

> "Every month your customers get a well-researched newsletter in your brand, with charts, sources and your name on it. You approve it in 5 minutes. We handle research, writing, design and delivery."

- Looks like a professional publication, not a WhatsApp forward
- Every fact is sourced, so nothing embarrassing goes out
- Nothing is sent without their approval
- Content can be reused for LinkedIn and WhatsApp

Lead with outcomes. Mention AI only if they ask how it's made so quickly.

## The demo: a free sample issue

1. Pick a prospect.
2. Set their logo and colours in `config/brand.json` and the logo files.
3. Run one issue on a topic from their industry and send them the preview or a test email.

It takes about an hour. A finished newsletter with their own brand on it does most of the persuading.

## Packages and pricing

These are starting points to test, not market data:

| Plan | Includes | Starting price |
|---|---|---|
| Starter | 1 issue/month, their branding, up to ~500 recipients | ₹8,000–15,000/month |
| Growth | 2 issues/month + 4 LinkedIn posts from the content | ₹20,000–35,000/month |
| Setup (one-time) | Brand setup, templates, list import, sending domain | ₹15,000–30,000 |

- Monthly billing with a 3-month minimum
- Price on time saved and leads gained, not on running cost
- Raise prices after 2–3 case studies

## Objections

| They say | Response |
|---|---|
| "AI content is generic" | Show the sources and the India section; every fact is checked and every issue is approved |
| "We don't have an email list" | Start with existing customers and enquiries; add a sign-up form to the website and WhatsApp |
| "Will people read it?" | Track opens and clicks from month 1 and adjust topics |
| "We can use ChatGPT ourselves" | You can, but research, checking, design and sending take hours every month |

## Before the first paying client

1. **Email service.** Use Brevo, Mailchimp or Zoho Campaigns for client sends. Gmail is for drafts only: about 500 recipients a day on a personal account, with no tracking or unsubscribe handling.
2. **Sending domain.** Send from the client's own domain with SPF/DKIM set up.
3. **Consent (DPDP Act).** Email only people who opted in, and put an unsubscribe link in every issue.
4. **Research quality.** Research in session, or move to a stronger paid model.
5. **Isolation.** Each client gets their own repo or folder, `brand.json`, recipients and keys.
6. **Service agreement.** Cover what's delivered, approval turnaround, content ownership (the client's), and the fact that nothing is sent without approval.

## First 30 days

| Week | Action |
|---|---|
| 1 | Pick a sector; make 2–3 sample issues |
| 2 | Make 10 prospect-branded samples; send them personally on LinkedIn or WhatsApp |
| 3 | Offer 2 pilot clients a lower price in exchange for a testimonial and shareable results |
| 4 | Set up their email service, send the first issues, track opens |

After 2–3 months of real numbers, the case study does most of the selling.
