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

## Names and addresses in quoted meeting text

Issue: [#1468](https://github.com/getcommunityone/open-navigator/issues/1468). The site quotes meetings word for word:
transcript excerpts, public-comment quotes, search snippets, decision statements and agenda passages. A verbatim
quote can carry a resident's full name even when the speaker label beside it says "First L.": the chair calls "Next,
John Smith of 412 Elm Street", a speaker says "my name is Mary Ann Smith", or someone names a neighbour.

**The rule.** Before any meeting text leaves the API, one shared step rewrites it:

| In the text | Served as |
|---|---|
| A private person's name ("John Smith", "Mary Ann Smith", "my neighbor Bob Jones") | "First L." ("John S.", "Mary S.", "Bob J.") |
| A surname after a courtesy title ("Mr. Smith") | Its initial ("Mr. S.") |
| A street address after "I live at", "my address is", or "of / at / from &lt;number&gt; &lt;street&gt;" | `[address]` |
| Any private name in a school board's meeting (a resident there may be a student) | `[name]`, a lone first name included |
| A roster official of that government (`person_government`, `body_membership`), or a state-level official of that state | Kept as said |
| A name right after an office title ("Councilman Joe Roe", "Superintendent Dana Whitley") | Kept: a public role |
| A widely known public figure on the reviewed allow-list (`trending_term_public_figure` seed) | Kept |

**How a name is found.** No model, no network and no lookup about anyone. A name is the words after a cue ("my name
is", "next speaker is", "I'm", "this is", "thank you", "Mr./Ms./Dr.", "my neighbor"), or a known given name followed
by capitalised words that aren't ordinary words, places or roles. The given names are the aggregate list speaker
introductions already use (#1231, #1245): first names carried by at least 4 people in the person master or shared by
at least 2 officials, with no surname or person attached. The step is conservative: when a pair might be a name, it is
shortened. A name followed by an organisation or place word ("John Smith Park", "Jones Construction") is an entity's
name and is kept. `<mark>` highlighting from `ts_headline` survives the rewrite.

**Where it runs.**

- `core_lib.privacy` (`packages/core-lib/src/core_lib/privacy/names.py`) holds the redactor. `api/privacy_redaction.py`
  applies it to every endpoint that serves meeting text (`redact_response`), with the officials of each row's own
  place. The officials index is read from the served tables once an hour; if it can't be read, every name is shortened.
- Every served excerpt endpoint goes through it: `/api/search` (meeting, transcript, agenda/minutes, decision and topic
  results), `/api/trends/terms/{id}/evidence`, the topic routes (`/meetings`, `/states`, `/decisions`, `/outcomes`,
  `/upcoming`, `/companies`, `/organizations`), the data-center routes (`/meeting-mentions`, `/positions`,
  `/speakers`, `/comments`, `/agenda-items`, `/job-claims`, `/projects`, `/decisions`, `/vote-decisions`,
  `/hearings`), the policy-question routes, `/api/meetings`, `/api/meeting/{id}`, `/api/meeting/{video_id}/transcript`,
  the meeting comparison and document gaps, `/api/decision/*`, `/api/decisions`, `/api/lenses`, `/api/chat/meetings`,
  `/api/organizations/{id}` and `/api/short-term-rentals/companies`. `tests/test_privacy_redaction_api.py` fails when
  one of these returns without it, or when its response model has a text field the step doesn't cover.
- The dbt macro `redact_person_names` is the SQL twin for stored excerpts (cues, courtesy titles and addresses only);
  `trending_term_evidence` applies it before `ts_headline`. Other marts store the raw passage in the private warehouse
  and rely on the API step.

**Limits.** A name with no cue and no known given name ("Tatum Okafor said") can pass, and so can a single surname.
Property addresses in land-use decisions ("rezoning of 1234 Main Street") are masked as well, which loses a public
detail; we accept that for now rather than risk a home address. The full recording stays linked: it is the
government's record.

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
