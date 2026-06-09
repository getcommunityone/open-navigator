---
sidebar_label: release history
title: Release History
description: Project-wide release log for Open Navigator, with each version tied to a Postgres backup.
---

# Release History

Project-wide release log for Open Navigator. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project adheres to
[Semantic Versioning](https://semver.org/) (`MAJOR.MINOR.PATCH`).

**Each tagged release is paired with a Postgres backup** of the warehouse
(`open_navigator` + `openstates`) so the code at a tag can be reproduced against the
exact data it shipped with. See
[Releases & Data Versioning](../quickstart.md#releases--data-versioning) in the Quick
Start guide for the `make backup` / `make restore` workflow.

> This is the **project-level** release log. For the jurisdiction-discovery
> component history see [its changelog](./changelog.md).

| Bump      | Meaning                                                                 |
| --------- | ---------------------------------------------------------------------- |
| **MAJOR** | Breaking API/schema change, dropped table or endpoint, incompatible dbt |
| **MINOR** | New data source, endpoint, or dbt mart — backward compatible            |
| **PATCH** | Bug fix, data backfill, or docs — no schema or contract change          |

## [Unreleased]

### Added
- Semantic-versioning + data-backup workflow: `make backup` / `make restore` targets
  and the **Releases & Data Versioning** section of the Quick Start guide. Each release
  tag is paired with version-stamped `pg_dump` snapshots (`<db>_<version>_<date>_<sha>.dump`)
  written to a Google Drive for Desktop folder via a WSL symlink
  (`open-navigator-backups` → `H:\My Drive\open-navigator-backups`), which Drive syncs
  off-machine automatically.

## [1.0.0]

Initial baseline version (as recorded in `web_app/package.json`). Establishes the
FastAPI backend, dbt medallion warehouse, React app, and Docusaurus docs.

> **Backup:** _to be provisioned_ — the first versioned warehouse snapshot will be
> written once the Google Drive for Desktop folder + WSL symlink are set up (see the
> Quick Start one-time setup) and `H:` is mounted in WSL.

[Unreleased]: https://github.com/getcommunityone/open-navigator/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/getcommunityone/open-navigator/releases/tag/v1.0.0
