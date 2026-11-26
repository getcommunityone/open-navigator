---
title: Privacy and data ethics
description: The privacy rules every agent and contributor follows (public roles vs private people, sensitive data, minors, scraping, AI tagging, contact, users' data) and the laws behind them.
---

# Privacy and data ethics

Issue: [#1080](https://github.com/getcommunityone/open-navigator/issues/1080). Decided 2026-11-26 at the owner's
request: be legally compliant at a minimum, be ethical by default, and treat citizens' privacy as a top priority. The
binding rules are in `AGENTS.md` under "Privacy and data ethics", and the review scan is in `.claude/review-rubric.md`.
This page gives the reasons.

## What we hold, and about whom

| Who | Examples | What we may hold and show |
|---|---|---|
| Public roles | elected officials, appointed board members, staff acting in their role | Name, office, official email and phone, official photo and biography, votes, statements at meetings, terms of office. Each item comes with its source |
| Organizations | companies, nonprofits, churches and schools as institutions, developers | Names, public filings (990s, registrations), mentions in meetings and decisions, grants |
| Private residents | people who spoke at public comment, applicants named in a case | Only what the record says. Names are shortened to "First L." in served data. Nothing is added from elsewhere |
| Our users | people who sign in | Their sign-in identity and what they choose to save. See "Our users' data" below |

A public meeting is a public record, but that doesn't make a resident a public figure. Someone who spoke for three
minutes about a rezoning is shown with the quote and where it was said, and nothing more.

## Sensitive data

Health, religion, race or ethnicity, immigration status, sexual orientation, disability, criminal history, personal
finances and precise home location are never tied to an identifiable private person.

- **Health.** We aren't a HIPAA covered entity or business associate, so HIPAA doesn't bind us. We treat health
  details as if it did. A resident who mentions their cancer in public comment isn't tagged with it, and no table
  links a person to a condition. Counts with no one identifiable, such as "12 speakers raised water quality", are fine.
- **Religion, schools, family.** A church or school may appear as an organization. We never record that a private
  person attends one.

## Minors and students

We never name, quote or tag a child or student identified in a meeting or document. School board meetings often
discuss individual students; FERPA protects education records, and we don't republish what a meeting let slip. We
don't create accounts for users under 13 (COPPA).

## Scraping

We collect public information the way a careful person would, only faster:

- **Public pages only.** We never log in, bypass a paywall or solve a CAPTCHA to reach content.
- **Who we are.** Requests identify as `open-navigator`. We don't spoof a browser or rotate proxies to get past a
  block. Retrying outside our VPN (see [Scraping with the VPN on](./scrape-vpn-direct-egress.md)) sends the request
  from our ordinary address, which is not disguise. A 403 that still fails outside the VPN is final.
- **Slow down when asked.** A 429 ("too many requests") means back off, honouring `Retry-After` when sent. It is not
  a reason to retry from elsewhere.
- **Terms and robots.txt.** Where a site's terms forbid automated collection, we cite or link instead. Job boards are
  an example (#1019), and CivicSearch's terms are respected as noted in its pipeline docs.
- **Keep the source.** Every scraped record keeps its URL and the date fetched.

## AI tagging and extraction

Models (Gemini meeting analysis, the Jev classifier, Claude) tag what was said: topic, stance, outcome, the bill or
company named. They don't infer who a person is beyond the record, or their health, religion, ethnicity, motives or
politics beyond the stance they stated. Prompts that would ask for such inferences don't pass review. Speaker names
in served data stay "First L." unless the person claims their comment and chooses otherwise.

## Contact

- **Private people** are never emailed, texted or called unless they asked us to. A resident reaches us through
  "Is this you?" on their quote ([People in meetings](./people-claim-and-privacy.md)).
- **Officials** are contacted only at the official address on their government's page, by the owner. Nothing is sent
  automatically.
- **Bulk email** follows CAN-SPAM: an honest sender and subject, a postal address, and a working opt-out honoured
  within 10 business days.

## Our users' data

- **Minimize.** We collect only what a feature needs and say why. An address typed to look up local taxes is used for
  the lookup and not stored ([Contact form privacy](./contact-form-privacy.md) is the model).
- **Keep it short.** Data is kept only as long as the feature needs it, then deleted.
- **Never sell or share** users' data.
- **Delete on request.** A user can delete their account and what they saved. State privacy laws (California's
  CCPA/CPRA, Virginia, Colorado, Connecticut and others) give these rights to their residents; we give them to everyone.
- **Logs.** We don't log emails, tokens, exact locations or chat text next to a user's identity. Telemetry records
  kinds and counts, not people.

## Correction and removal

Anyone shown on the site can ask us to correct, hide or remove how we show them (#1064). We honour a removal request
even without full verification when the risk to the person is plausible. A public "Corrections and removals" page
explains how.

## How it's enforced

- `AGENTS.md` makes these rules binding on every coding agent. Where a task conflicts with them, the agent stops and
  asks the owner.
- The review rubric blocks a PR that breaks them.
- Known gaps are filed as issues rather than left in notes. The first is that site scrapers retry a 429 outside the
  VPN rather than backing off ([#1081](https://github.com/getcommunityone/open-navigator/issues/1081)).
