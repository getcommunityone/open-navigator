---
sidebar_position: 37
title: Businesses in search
description: How Open Navigator finds, types and places the businesses that meetings, decisions, bills and ballot measures name, and serves them within the Neon budget (#1088).
---

# Businesses in search

[#1088](https://github.com/getcommunityone/open-navigator/issues/1088) adds a **Businesses** search type in place of
Nonprofits. This page records what the owner decided on 2026-11-26, the tables, and the order of work.

## Why Nonprofits shows 0 today

`search_organizations_pg` (`api/routes/search_postgres.py`) reads `mdm_organization` joined to
`mdm_organization_nonprofit`. Neither is published to Neon: about 4.2 million organizations, roughly 1.7 GB, are on
the `NON_SERVING` list in `packages/hosting/src/hosting/neon/sync_public_to_neon.py`
([what Neon serves](neon-serving-scope.md), #284). On the hosted site the query fails, the error is swallowed, and the
count shows 0.

## Decisions

| Decision | Choice | Why |
|---|---|---|
| Which businesses | Only those named in a meeting, a decision, a bill or a ballot measure | Residents care about the businesses their government deals with; it keeps the served tables to a few MB of the 480 MB budget |
| Subtypes | `nonprofit`, `corporation`, `local_business` | The owner's three; government bodies and political committees aren't businesses and are left out |
| A company with many sites (for example a data-center operator) | Listed under **All locations**, and under each city or state whose records name it | A national company belongs to the national view; a city view shows only what that city's records say |
| The menu | **Businesses** replaces Nonprofits; nonprofit becomes a subtype | One type, one count, no empty entry |
| Release | After bills and ballot measures feed it too, not only meetings and decisions | The owner's choice: the type should cover all three kinds of record from the start |

## Tables

Both are served on Neon (added to `CIVIC_SERVING`), with keys declared in `schema.yml` as `CLAUDE.md` requires.

**`business`: one row per business.**

| Column | Meaning |
|---|---|
| `business_id` (PK) | `master_org_id` where the name matched the organization master, else the md5 of the normalized name plus state |
| `business_name` | the name as the records give it |
| `business_type_code` | `nonprofit`, `corporation` or `local_business` (rules below) |
| `master_org_id` | FK to `mdm_organization`, null when unmatched |
| `state_code`, `state`, `city` | where the business is based, when known |
| `is_all_locations` | true for a company listed under All locations |
| `ein`, `website_url` | when known |
| `mention_count`, `first_mentioned_date`, `last_mentioned_date` | over its mentions |

**`business_mention`: one row per business per record that names it.**

| Column | Meaning |
|---|---|
| `business_mention_id` (PK) | |
| `business_id` | FK to `business` |
| `source_kind_code` | `meeting`, `decision`, `bill` or `ballot_measure` |
| `source_record_id`, `source_url` | the record and its link |
| `mention_date` | the meeting date, decision date, bill action date or election date |
| `state_code`, `jurisdiction_name`, `city` | the place of the record, which decides where the business shows |
| `quote_text` | the verbatim text that names the business, which search shows as the match evidence |

## How a business is typed

Rules, applied in order, with no model guessing:

1. **nonprofit:** its EIN is in `mdm_organization_nonprofit` (IRS exempt organizations), or the extraction typed it as
   a nonprofit or a church.
2. **corporation:** it is in the data-center, short-term-rental or topic company tables, or records from two or
   more states name it.
3. **local_business:** any other business.

## How a business is placed

- **No place picked:** every business.
- **A state or a city:** the businesses with at least one mention in that place. A national company doesn't show in a
  city unless that city's records name it.
- **All locations:** `is_all_locations` is true for every company in the data-center company table, and for a
  corporation named in two or more states. These companies are stored with no single city, as
  `mdm_organization_data_center` already does.

## Where the mentions come from

| Source | Today | Work |
|---|---|---|
| Meetings | Organizations the meeting analysis extracts (`bronze_organizations_from_ai`) | [#1089](https://github.com/getcommunityone/open-navigator/issues/1089) builds the marts |
| Decisions | `decision_company_mention` and the topic company mentions | #1089 |
| Bills | Nothing: `bills` has a title, subject and latest action, no text | [#1090](https://github.com/getcommunityone/open-navigator/issues/1090) extracts names from bills that meetings reference and from current sessions in states with live cities |
| Ballot measures | Nothing: Ballotpedia titles and summaries are loaded; `bronze_ballot_measures_from_ai` is an empty placeholder | #1090 extracts names from the 2025–2026 measures |

Extraction over the real bills and measures uses LLM calls, so it runs on the warehouse machine after the owner's
yes ([AGENTS.md, "GPU and paid compute"](https://github.com/getcommunityone/open-navigator/blob/main/AGENTS.md)).

## Order of work

1. This page (#1088).
2. [#1089](https://github.com/getcommunityone/open-navigator/issues/1089): `business` and `business_mention` from
   meetings and decisions, published, with their size from the publish dry run.
3. [#1090](https://github.com/getcommunityone/open-navigator/issues/1090): bills and ballot measures feed
   `business_mention`.
4. [#1091](https://github.com/getcommunityone/open-navigator/issues/1091): Businesses in the API and on the site,
   merged last.

## Related

- [#1063](https://github.com/getcommunityone/open-navigator/issues/1063): applicants and petitioners linked to the
  organization master (`organization_meeting_mention`). Its mentions can feed `business_mention` once built.
- [#1076](https://github.com/getcommunityone/open-navigator/issues/1076): organization pages 404 on the hosted site.
  `business` is a served projection of the organizations search links to, so it covers those pages for businesses.
- [Data center companies and projects](data-center-companies-projects.md),
  [decision place and company](decision-place-and-company.md), [topic companies](topic-companies.md).
