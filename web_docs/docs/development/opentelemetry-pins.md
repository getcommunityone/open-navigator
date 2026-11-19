---
sidebar_position: 39
title: OpenTelemetry pins and Dependabot
description: Why one OpenTelemetry security bump broke the install three times, what we chose (group the family in dependabot.yml), what that does not yet prove, and the manual bump that always works (#378).
---

# OpenTelemetry pins and Dependabot

Decision for [#378](https://github.com/getcommunityone/open-navigator/issues/378), recorded 2026-11-18.

## What went wrong

`requirements.txt`, `requirements-cpu.txt` and `apps/open-navigator-web/requirements.txt` pin the OpenTelemetry family
with `==`. The packages in it need each other at matching versions. From the installed metadata (1.42.0 / 0.63b0; the
shape is the same on every release train):

| Package | Requires exactly |
|---|---|
| `opentelemetry-sdk` | `opentelemetry-api` (same version) and `opentelemetry-semantic-conventions` (the `0.xb` twin) |
| `opentelemetry-instrumentation-fastapi` (and the asyncpg, psycopg2 and sqlalchemy ones) | `opentelemetry-semantic-conventions`, `opentelemetry-instrumentation` and `opentelemetry-util-http` at the twin version |
| `opentelemetry-exporter-otlp-proto-http` | `opentelemetry-exporter-otlp-proto-common` and `opentelemetry-proto` (same version), `opentelemetry-sdk~=` the same minor |

A Dependabot security update moves only the package named in the advisory. A bump of `opentelemetry-api` alone leaves
`opentelemetry-sdk==1.45.2` asking for the old api, so pip cannot install and Backend Tests and API Types fail. That
happened on November 15, 2026 in #364, #375 and #376, and each time the whole family was moved by hand.

## What we chose

Group the family so Dependabot opens one pull request for it: `.github/dependabot.yml` has a group `opentelemetry`
(`applies-to: security-updates`, pattern `opentelemetry-*`) for the two directories that hold the pins, `/` and
`/apps/open-navigator-web`. `open-pull-requests-limit: 0` keeps version updates off, so the file adds no routine
update pull requests. GitHub documents both settings in its
[security updates guide](https://docs.github.com/en/code-security/dependabot/dependabot-security-updates/configuring-dependabot-security-updates).

The issue's second option said version-update groups were the only kind; `applies-to: security-updates` now exists and
is what this uses.

Not chosen:

- **Dropping the `opentelemetry-api` pin.** It fixes only an advisory on `api` alone, and `sdk` and the instrumentation
  packages still need each other.
- **Only documenting the manual bump.** It is kept below as the fallback, but the failing pull request would still be
  opened each time.

## What is not proven

I can't run Dependabot, so none of this has been seen working:

- Whether the group also moves family members that have **no advisory of their own**. GitHub's text says the group
  updates "multiple dependencies" at once; if it includes only vulnerable ones, an advisory on a single package
  still produces a one-line pull request. The next OpenTelemetry advisory is the test.
- Whether Dependabot reads `requirements-cpu.txt`; it names `requirements*.txt` files only by its own rules.
- `uv.lock` also lists the family. This file does not cover the `uv` ecosystem.

If the next advisory still opens a broken pull request, close it and do the manual bump below, then reopen #378 with
what the pull request contained.

## The manual bump (always works)

1. Pick one release train from PyPI: the `opentelemetry-sdk` version `X` and the `0.yb` version `Y` its release notes
   name (for 1.45.2 it is 0.66b2).
2. In all three requirements files set `opentelemetry-api`, `-sdk` and `-exporter-otlp-proto-http` to `X`, and every
   `opentelemetry-instrumentation-*` to `Y`.
3. `pip install --dry-run -r requirements.txt` (or the file you changed) must resolve before you push.
4. Run the Backend Tests and API Types checks.
