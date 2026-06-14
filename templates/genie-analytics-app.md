# About DevHub

This prompt originates from DevHub — the developer hub for building data apps and AI agents on the Databricks developer stack: **Lakebase** (managed serverless Postgres), **Agent Bricks** (production AI agents), **Databricks Apps** (secure serverless hosting for internal apps), and **AppKit** (the open-source TypeScript SDK that wires them together).

- Website: https://developers.databricks.com
- GitHub: https://github.com/databricks/devhub
- Report issues: https://github.com/databricks/devhub/issues

A complete index of every DevHub doc and template is at https://developers.databricks.com/llms.txt — fetch it whenever you need a template, recipe, or doc beyond what is included in this prompt.

---

# What the user copied

The DevHub **cookbook** — **Genie Analytics App** (https://developers.databricks.com/templates/genie-analytics-app).

A cookbook is a composed pattern that builds an **archetype application** end-to-end on Databricks from multiple recipe goals. Use the cookbook goal for scope and architecture; use the installed Databricks agent skills for implementation.

## Default workflow

1. Understand the user's intent and goals.
2. Verify the local Databricks dev environment (CLI `1.0.0+`, authenticated profile, `databricks current-user me` smoke test).
3. Ask follow-up questions one at a time (always offer "Not sure — help me decide"); prefer a multiple-choice tool.
4. Build the app or agent (use the agent skills for implementation).
5. Make it look great (shadcn/ui + Tailwind; Databricks palette `#FF3621`, `#0B2026`, `#EEEDE9`, `#F9F7F4`; or follow the existing codebase's design system).
6. Run and test locally.
7. Deploy to production (confirm first unless given a go-ahead).
8. Run and test the deployed app (`agent-browser`; inspect `databricks apps logs`; fix + redeploy until clean).

## Before building

- Always run `databricks aitools version`. If skills are missing or stale: STOP and install/update first (a stale `.agents/skills/` shadows a fresh global install — check both scopes).
- Do NOT assume when provisioning Databricks resources (Lakebase, Model Serving, **Genie spaces**, **SQL warehouses**, catalogs/schemas) — they cost money and take minutes. Ask create-new vs reuse-existing.

## Intent (ask one, multiple-choice)

- **New project from scratch** following this archetype end-to-end.
- **Add this archetype to an existing Databricks app** (read the existing project first; introduce incrementally).
- **Just learning the pattern** (guided tour; no commands).
- **Not sure — help me decide.**

## Archetype-specific decisions (Step 2)

- For each primitive (Genie space, SQL warehouse, Model Serving, Lakebase): create new or reuse?
- Which Databricks profile? (`databricks auth profiles`.)
- Data: real Unity Catalog tables, or seed data to start and swap later?
- Scope today: full archetype, or a working slice first?

---

# Cookbook goal — Genie Analytics App

> title: "Genie Analytics App"
> url: https://developers.databricks.com/templates/genie-analytics-app
> summary: "Build a minimal Databricks App with AI/BI Genie conversational analytics. Covers Genie space configuration, plugin wiring, and deploy."

A minimal Databricks App with AI/BI Genie conversational analytics. Users ask natural-language questions about their data and get SQL-powered answers through an embedded Genie chat interface.

## Components

1. **Genie Conversational Analytics** — configure a Genie space, wire up the server and client plugins, declare app resources, and deploy.

## Component: Genie Conversational Analytics

When done, you will have:

- A configured AI/BI Genie space connected to your data tables
- A Databricks App with an embedded Genie chat interface
- Server and client plugins wired together with proper app resource declarations
- A deployed app where users can ask questions about their data in plain language

## User's added requirement

Integrate it in an intuitive way and **make it easy for the user to understand the original data source used** (surface the underlying catalog/schema/tables and show provenance for each answer).
