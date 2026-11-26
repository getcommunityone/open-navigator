---
title: Companies named for each topic
description: How the home page lists, for any topic, the companies meetings and decisions name, with real counts and a quoted passage.
---

# Companies named for each topic

Issue: [#1052](https://github.com/getcommunityone/open-navigator/issues/1052). Added 2026-11-26. It generalises the
short-term rental platforms ([#1015](./short-term-rental-companies.md)) to every curated topic.

## In short

- Under **Browse topics** on the home page, the selected topic shows **Companies named · topic · place**. Each company
  shows the meetings and decisions in that place that name it, and its newest mention quoted with the matched words
  highlighted.
- Coming-soon topics with tracked companies (Flock, License plate readers, Guns, Pickleball) can be picked for their companies.
  The story above stays the same.
- A company named in no meeting in scope is listed once, plainly, after the others. No count is ever estimated.
- A company in the organization master (data center operators, rental platforms) links to its organization page.
  Every company's meeting count links to a search for the name actually said.

## Where the companies come from

| Topic | Companies | How a mention is found |
|---|---|---|
| Data centers | `mdm_organization_data_center`, plus `data_center_operators` operators not in it | Meetings: the company named (whole word, any case) **inside a passage that already talks about a data center** (`int_data_center_transcript__passage`), so "Google" said in passing doesn't count. Decisions: `decision_company_mention` |
| Short-term rentals | `mdm_organization_short_term_rental` | `short_term_rental_company_mention`, as is |
| Flock and license plate readers | `topic_companies` seed: Flock Safety, Motorola Solutions (Vigilant), Axon, Genetec, Rekor | The company's phrases in the transcript or in the decision's headline and statement (English full text) |
| Pickleball | `topic_companies` seed: venue chains (Chicken N Pickle, The Picklr, Pickleball Kingdom, Dill Dinkers, Ace Pickleball Club) and paddle makers (Selkirk Sport, JOOLA, Franklin Sports) | As above |
| Guns | `topic_companies` seed: SoundThinking (ShotSpotter), Smith & Wesson, Sturm Ruger, SIG Sauer, Glock, Beretta, Daniel Defense, Remington | As above |

Seed phrases avoid ordinary words. Flock is matched as "flock safety" or "flock camera", never as "flock" alone.
Remington is matched only as "Remington Arms" or "RemArms", and Selkirk only as "Selkirk Sport" or "Selkirk paddle", because both are also place names.

Glock, Ruger, Beretta and Axon are also surnames or caption garbles, so they count only in a product phrase ("Glock 19",
"Ruger pistol", "Beretta M9", "Axon body camera").

For Flock and license plate readers, Guns and Pickleball, a company counts only in a meeting or decision already tagged
with that topic. Motorola's radio contracts or Axon's body cameras don't count toward license plate readers unless that
meeting discusses plate readers. Gating cut Axon from 743 meetings to 89, and the product-phrase rule then took it to
28. For data centers, the name must also be within about 250 characters of a data center phrase. A remaining false
match ("Google them", Amazon's warehouse near a data center site) shows as such in the quote.

First local build (national meetings): Google 92, Meta 82, Microsoft 81, Amazon 73, QTS 23; Flock Safety 472, Axon 28,
Motorola Solutions 24; SoundThinking (ShotSpotter) 200, Glock 46, Smith & Wesson 17; Chicken N Pickle 7; Airbnb 2,207,
Expedia Group 439.

## The tables

| Table | Grain | Keys |
|---|---|---|
| `topic_company` | one row per (topic, company) | PK `topic_company_id` = md5(`topic_query_id`\|`company_key`); FK `topic_id` → `civicsearch_topic`; `master_org_id` when the company is in MDM |
| `topic_company_mention` | one row per (topic company, meeting video) or (topic company, decision) | PK `topic_company_mention_id`; FK `topic_company_id` → `topic_company`. `evidence` is a verbatim excerpt with `<mark>`; a row without one is dropped |

Both are serving tables, on the Neon allow-list.

## The endpoint

`GET /api/topics/{query_id}/companies?state=&city=` returns `topic_query_id`, `scope` (national, state or city) and
`companies`. Each company has `company_key`, `company_name`, `aliases`, `website_url`, `master_org_id`, `meetings`,
`decisions` and `newest` (`mention_kind`, `title`, `date`, `jurisdiction_name`, `state_code`, `url`, `evidence`). The
busiest company comes first. An unknown topic, or a serving copy without the tables, returns an empty list.

## Build it

```bash
cd dbt_project
dbt seed --select topic_companies
dbt build --select topic_company topic_company_mention
dbt run-operation publish_public_serving
```
