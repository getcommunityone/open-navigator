---
sidebar_position: 36
title: Data center companies and projects
description: How Open Navigator models data center companies (in the organization master) and projects, with a source for every figure (#531).
---

# Data center companies and projects

[#531](https://github.com/getcommunityone/open-navigator/issues/531) adds tables of data center companies and
projects, beyond the sites Epoch AI tracks. It is part of epic
[#530](https://github.com/getcommunityone/open-navigator/issues/530).

## Decisions

**Companies live in the organization master, not in a table of their own.** A data center company is an
organization, and the warehouse already has one master for organizations (`mdm_organization`). The seed
`data_center_companies.csv` is one more source for it (`stg_data_center_companies__org`, `org_type = 'company'`),
unioned in `int_organizations__unioned` like the IRS, NCCS and jurisdiction sources. Data center detail that the
master has no column for (roles, aliases, press-release feed, source) sits in the 1:1 satellite
`mdm_organization_data_center`, the same pattern as `mdm_organization_nonprofit`.

**A company reuses the master row that already names it.** A seed row has no city or state, so its cluster key is
the normalized name alone. A national mention already in the master with the same name, such as the AI-extracted
"Google" or "Microsoft", lands in the same cluster and keeps its `master_org_id`. A company the master didn't know
gets a new row. The curated source outranks AI-extracted mentions for the display name and the org type.

**Every figure keeps its own source.** A project's investment, IT load, acreage or square footage is one row per
(project, metric, source) in `data_center_project_figure`, with the URL and the verbatim excerpt that states it.
When sources disagree, each keeps its row and `data_center_project` shows no single figure for that metric
(`has_conflicting_figures`). Nothing is averaged or picked.

**What a source is.** `source_kind` says what the excerpt is: `company_announcement` (the company's own press
release), `news_article`, or `dataset_row` (a field of a published dataset, quoted as `<row> | <field>: <value>`;
Epoch AI's site list). Every Epoch site is folded in as a project credited to Epoch.

**Bridges are deterministic.** `data_center_project_jurisdiction` carries a curated project's stated city and
county, and an Epoch site's governments (#445). `data_center_project_mention` links decisions and meeting passages
to a project only when the text names the project in its state, or names one of the project's companies in a
record from one of the project's governments. A place alone, or a company named somewhere else, is not a match.

## Tables

| Table | Grain | Keys |
|---|---|---|
| `mdm_organization_data_center` | one row per data center company | PK and FK `master_org_id` → `mdm_organization` |
| `data_center_project` | one row per project | PK `project_id`; FK `data_center_site_id`, `jurisdiction_id` |
| `data_center_project_company` | one row per (project, company, role) | PK `project_company_id`; FK `project_id`, `master_org_id` |
| `data_center_project_jurisdiction` | one row per (project, government) | PK `project_jurisdiction_id`; FK `project_id`, `jurisdiction_id` |
| `data_center_project_figure` | one row per (project, metric, source, value) | PK `project_figure_id`; FK `project_id` |
| `data_center_project_mention` | one row per (project, decision or passage) | PK `project_mention_id`; FK `project_id`, `data_center_meeting_mention_id` |

All six are published to `public` and mirrored to Neon (`CIVIC_SERVING`). `mdm_organization` itself is not on
Neon, so the satellite carries `company_name` for the page.

## Adding a company or project

Add a row to `data_center_companies.csv` or `data_center_projects.csv` with the URL and a verbatim excerpt that
names it, and a row to `data_center_project_figures.csv` for each figure a source states. Never add a company,
project, date or number no source states. A new company needs `mdm_organization` rebuilt
(`dbt run --select stg_data_center_companies__org+ ` up to `mdm_organization`, then the data center models).
