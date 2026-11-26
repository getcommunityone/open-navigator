---
title: Company funding
description: How companies we track are linked to the nonprofits their foundations fund (IRS 990 grants), and the options for linking companies to contributions to leaders.
---

# Company funding

Issue: [#1073](https://github.com/getcommunityone/open-navigator/issues/1073).

The question: which nonprofits and which leaders does a company support with money? This page records what is
linked today (company foundations → nonprofits, from IRS 990 grants we already hold) and compares the sources that
could link companies to leaders (campaign contributions and lobbying). None of the leader sources is loaded yet.

## What is linked: company → foundation → grantee

Companies mostly give to nonprofits through a foundation, which files its own IRS return. We already load 990
Schedule I grant lines into the `grant` mart (grantor EIN → grantee, cash amount, purpose, tax year, filing URL).
What was missing was the step from a company to its foundation.

| Layer | Object | Grain | Keys |
|---|---|---|---|
| Seed | `company_foundation` | one row per (company, foundation) | (`company_key`, `foundation_ein`) unique; `foundation_ein` unique |
| Mart | `company_grant` | one row per 990 grant line from a linked foundation | PK `grant_id`; FKs `grant_id` → `grant`, `master_org_id` → `mdm_organization`, `foundation_master_org_id` → `mdm_organization`, `grantee_master_org_id` → `mdm_organization` (nullable) |
| API | `GET /api/organizations/{id}/funding` | `funds[]` (grantees), `funded_by[]` (companies) | — |
| UI | `/organizations/:masterOrgId` | **Funds** and **Funded by** sections | — |

### Rules for a seed row

A foundation is added to `company_foundation` only when both hold:

1. its EIN is a `grantor_ein` in the `grant` mart, and
2. a public page ties it to the company. The row keeps that page (`source_url`), the verbatim sentence
   (`source_excerpt`) and the date it was read (`verified_on`).

EINs are never guessed. `relationship` says how the two are tied:

- `founded_by_company`: the company started it, and it is a separate 501(c)(3).
- `governed_by_company`: its board is made up of the company's executives.
- `controls_company`: the nonprofit controls the company.

The company's `master_org_id` is not stored in the seed. `company_grant` looks it up by `company_key` in
`topic_company` (data center companies, short-term rental platforms and the topic companies from #1052). That way the
link survives an MDM rebuild that changes the hash. A company without a `master_org_id` can't be linked: the
mart's FK to `mdm_organization` needs one.

### Linked today (local warehouse, 2026-11-26)

| Company | Foundation (EIN) | Relationship | Grant lines | Total reported | Tax years |
|---|---|---|---|---|---|
| Airbnb | Airbnb.org (83-3135259) | founded by Airbnb; a separate 501(c)(3) (kept as its own org in MDM, #1015) | 56 | $18,528,372 | 2020–2023 |
| Oracle | Oracle Health Foundation, formerly First Hand Foundation (43-1725294) | governed by Oracle executives | 86 | $18,385,477 | 2021–2023 |
| OpenAI | OpenAI Foundation, formerly OpenAI Inc (81-0861541) | the nonprofit that controls OpenAI Group | 25 | $12,683,542 | 2019–2023 |

Totals are SQL sums of the amounts on the 990s. Some caveats:

- **Oracle Health Foundation** was Cerner's foundation before Oracle bought Cerner (2022). Its 2021 lines were filed
  as "First Hand Foundation". `company_grant.grantor_name_on_filing` keeps the name used on each filing. The page shows
  every grant under the foundation's EIN, including those from before Oracle owned it.
- The OpenAI Foundation is not a corporate giving arm. It is the nonprofit parent that controls the company. It is
  linked because its grants are money that comes from the OpenAI organization, and `relationship` says which kind of
  tie it is.
- A grant to a donor-advised fund (for example Oracle Health Foundation's 2023 transfer to National Philanthropic
  Trust) is shown as the 990 reports it. Where the money went after that is not in the 990.

### Why the big names are missing

The `grant` mart is built from **990 Schedule I** (public charities). Private foundations file a **990-PF**, and
990-PF grant lists aren't loaded. So most corporate foundations can't be linked yet, even ones that clearly
exist (Google's, Motorola Solutions', Expedia's and others). We searched the grant mart by name for the tracked companies,
and the only grantors found were the three above. Smith & Wesson, Axon, Motorola Solutions and the other
topic companies from the `topic_companies` seed also have no `master_org_id` in `topic_company`, so they couldn't be
linked even with a 990-PF source. Loading 990-PF Part XV grants (from the same GivingTuesday 990 data lake) is the
next step that would add them.

### Serving

`company_grant` is in the public serving list (`publish_public_serving.sql`) and in the Neon mirror list
(`sync_public_to_neon.py`). It is about 0.2 MB (167 rows), and it carries the grantee's name and location itself, so it
doesn't need `grant` or `mdm_organization` on Neon. The organization page itself
404s on Neon for an organization that is only in `mdm_organization` (not served there). So **Funded by**
shows on the hosted site only for grantees that have a served company or nonprofit record.

## Contributions to leaders: options

Nothing below is loaded. Loading is a follow-up issue. For each source the table says who it covers, what it would tell
us about the companies we track, and what it would tell us about Tuscaloosa officials.

| | FEC (OpenFEC API) | Alabama FCPA (Secretary of State) | Federal lobbying (Senate LDA API) |
|---|---|---|---|
| Covers | Federal candidates (President, Senate, House), party committees and PACs | State and county candidates and political committees in Alabama | Registered federal lobbyists and the clients they lobby for |
| Access | Free REST API (`api.open.fec.gov`) with a free key from api.data.gov; bulk files on fec.gov | Electronic filing search and data download on the Alabama FCPA reporting site; terms to be checked before loading | Free REST API (`lda.senate.gov/api`); registering for a key raises the rate limit |
| Company link | A corporation can't give to a federal candidate directly. Its PAC (separate segregated fund) can, and that PAC is a committee in the FEC data. Individual contributions over $200 are itemized with employer and occupation, so "employees of X" can be grouped by the employer text (messy, not an org link) | Contributions are reported by contributor name. Corporate contributors appear by name and would need matching to `mdm_organization` | LD-1/LD-2 reports name the client company, the issues lobbied and the quarterly spend. LD-203 reports list the contributions that lobbyists and registrants made to federal candidates |
| Tuscaloosa officials | Only officials who run for federal office, or who give to federal candidates themselves. Useful for the members of Congress who represent Tuscaloosa and the company PACs that give to them | State legislators and county officials for Tuscaloosa; any city official who has run for state office. **Municipal candidates (mayor, city council) file with the city clerk under the FCPA, mostly on paper**, so the council members' campaign reports are not in the state system | No local officials. It shows which tracked companies lobby Congress, on what issues, and how much they spend |
| Effort | Low: clean API, stable IDs (candidate_id, committee_id) | Medium: name matching. City-level data would need records requests or scanning paper filings from the clerk | Low to medium: clean API; client names need matching to `mdm_organization` |

### Recommendation

1. **FEC first** for the company → federal leader link: load the tracked companies' PACs (by committee name and
   connected organization) and their Schedule B contributions to candidates. This connects money to people with
   stable IDs.
2. **Senate LDA second**: the client name of each tracked company → lobbying spend and issues. This answers "what does
   this company want from government", and the issue codes match our topics (for example data centers and energy).
3. **Alabama FCPA third**, for the state legislators and county officials who represent Tuscaloosa. For the city
   council, ask the Tuscaloosa city clerk for the municipal campaign finance reports. Don't scrape scanned filings
   without a decision on OCR quality and privacy (contributor home addresses are on the forms).

All three show money given, not influence. A page that shows a contribution must show the filing it came from and
must not suggest a contribution caused a vote.
