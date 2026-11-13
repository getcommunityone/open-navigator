---
name: Work item
about: A change to make (feature, fix, chore or docs). Fill in all four parts before the first commit.
title: "<type>(<scope>): <what changes>"
labels: ""
---

<!-- Planned work (a PI epic or one of its stories, or a task under them): keep this table and fill in the links.
Otherwise delete it. A story says "this issue" for itself; anything under a story links both. -->

| Attribute | Value |
|---|---|
| Epic | [<key> · <epic name>](https://github.com/getcommunityone/open-navigator/issues/<epic>) |
| User story | [<key> · <story title>](https://github.com/getcommunityone/open-navigator/issues/<story>) |
| PI · Sprint | <PI> · <sprint> |
| Points | <points> |

## Problem

<!-- What is wrong or missing, and who it affects. Link the evidence: a failing test, a log line, a screenshot, a
user's feedback issue. -->

## Done when

<!-- One line per check a test or reviewer will make, for example:
- `GET /api/jurisdictions?state=AL` returns `state_code` and `state` for every row -->

## Contract

<!-- Every name the work adds or changes that a test or another layer will use:
- API: path, parameters, response fields and their types.
- Data: the dbt model or table, its grain (one row per what), its typed columns, its primary key and foreign keys.
- UI: the route and the URL parameters it reads (?state=&city=). -->

## Read first

<!-- The files to change and the rules that govern them (sections of CLAUDE.md / AGENTS.md, docs under
web_docs/docs/). -->
