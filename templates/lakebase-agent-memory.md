# About DevHub

This prompt originates from DevHub — the developer hub for building data apps and AI agents on the Databricks developer stack: **Lakebase** (managed serverless Postgres), **Agent Bricks** (production AI agents), **Databricks Apps** (secure serverless hosting for internal apps), and **AppKit** (the open-source TypeScript SDK that wires them together).

- Website: https://developers.databricks.com
- GitHub: https://github.com/databricks/devhub
- Report issues: https://github.com/databricks/devhub/issues

A complete index of every DevHub doc and template is at https://developers.databricks.com/llms.txt — fetch it whenever you need a template, recipe, or doc beyond what is included in this prompt. If a step in this prompt is unclear, the matching DevHub page almost certainly clarifies it.

---

# Working with DevHub prompts

Follow these rules every time you act on a DevHub prompt.

## Read first, then act

- Read the entire prompt before executing any steps. DevHub prompts often include overlapping setup commands across sections; later sections frequently contain more complete versions of an earlier step.
- Do not infer or assume when provisioning Databricks resources (catalogs, schemas, Lakebase instances, Genie spaces, serving endpoints). Ask the user whether to create new resources or reuse existing ones.
- If you run into trouble, fetch additional templates and docs from https://developers.databricks.com (the index lives at https://developers.databricks.com/llms.txt). For example, if Genie setup fails, fetch the Genie docs and templates instead of guessing.

## Implementation guidance

The template below describes **what to build**, not how to build it. Your installed Databricks agent skills contain all implementation patterns, code examples, CLI commands, and configuration needed. Use them to implement the template. Before continuing, always run `databricks aitools version`. **If skills are missing or it reports a newer release: STOP. Install skills if missing or update if outdated before proceeding — do not work around a missing or stale install.** A stale `.agents/skills/` copy silently shadows a fresh global install, so always check both scopes.

## Engage the user in a conversation

Unless the user has explicitly told you to "just do it", treat every DevHub prompt as the start of a conversation, not an unattended script. The user knows their domain best; DevHub knows the Databricks stack. Both are required to build a successful system.

Follow these rules every time you ask a question:

1. **One question at a time.** Never ask multiple questions in a single message.
2. **Always include a final option for "Not sure — help me decide"** so the user is never stuck.
3. **Prefer interactive multiple-choice UI when available.** Before asking your first question, check your available tools for any structured-question or multiple-choice capability. If one exists, **always** use it instead of plain text. Known tools by environment:
   - **Cursor**: use the `AskQuestion` tool.
   - **Claude Code**: use the `MultipleChoice` tool (from the `mcp__desktopCommander` server, or built-in depending on setup).
   - **Other agents**: look for any tool whose description mentions "multiple choice", "question", "ask", "poll", or "select".
4. **Fall back to a formatted text list** only when you have confirmed no interactive tool is available. Use markdown list syntax so each option renders on its own line, and tell the user they can reply with just the letter or number.

### Example: Cursor (`AskQuestion` tool)

```
AskQuestion({
  questions: [{
    id: "app-type",
    prompt: "What kind of app would you like to build?",
    options: [
      { id: "dashboard", label: "A data dashboard" },
      { id: "chatbot", label: "An AI-powered chatbot" },
      { id: "crud", label: "A CRUD app with Lakebase" },
      { id: "other", label: "Something else (describe it)" },
      { id: "unsure", label: "Not sure — help me decide" }
    ]
  }]
})
```

### Example: plain text fallback

Only use this when no interactive tool is available:

What kind of app would you like to build? Reply with the letter to choose:

- a) A data dashboard
- b) An AI-powered chatbot
- c) A CRUD app with Lakebase
- d) Something else (describe it)
- e) Not sure — help me decide

## Default workflow

Unless instructed otherwise, follow this workflow:

1. Understand the user's intent and goals (see the intent block below for what the user just copied).
2. Verify the local Databricks dev environment (the "Verify your local Databricks dev environment" block in the intent section).
3. Ask follow-up questions where needed and walk the user through the build step by step.
4. Build the app or agent.
5. Make it look great (see "Make it look great" below).
6. Run and test locally.
7. Deploy to production. **Ask the user for confirmation first, unless they have already given an explicit go-ahead.**
8. If deployed, run and test deployed app (see "Run and test deployed app" below).

## Make it look great

The default templates that AppKit provides are intentionally minimal — a starting point, not a finished product. **Do not stop there.** Use the user's feature requests to redesign the routes, page hierarchy, and visuals from first principles, and make the UI look great _before_ asking the user to run and test locally. Showing the user something polished early changes the conversation.

Unless the user has specified a design preference, use these defaults:

- shadcn/ui components on top of Tailwind CSS.
- Clean hierarchy with modern spacing — not too many stacked cards.
- Modern, minimal design language.
- Databricks brand palette: `#FF3621`, `#0B2026`, `#EEEDE9`, `#F9F7F4`.

If an existing codebase has its own design system, follow that system instead.

## Run and test deployed app

- If the `databricks-apps` skill is available, follow its `agent-browser` reference to load the deployed app and test it; otherwise install `agent-browser` (`npm install -g agent-browser`) and drive the deployed URL with it directly.
- If anything is off, fix it.
- Inspect the app logs via the Databricks CLI and fix any errors.
- Redeploy and repeat until all issues are resolved.
- Report back to the user once the deployed app is verified.

## When you run into issues

Use the GitHub CLI (if available) or generate a copy-pastable error report for the user to file at https://github.com/databricks/devhub/issues. Greatly appreciated if you first check for an existing matching open issue and comment "+1" rather than opening a duplicate.

---

# What the user just did

The user copied the prompt for a DevHub **recipe** — **Lakebase Agent Memory** (https://developers.databricks.com/templates/lakebase-agent-memory).

A recipe is a focused, opinionated how-to for a single Databricks pattern (e.g. wiring Lakebase Change Data Feed, creating a Model Serving endpoint, persisting chat history). Recipes are designed to be dropped into an existing project or composed into a larger build. They are deliberately narrow — they solve one thing well.

The recipe goal below describes **what** the user wants to build — the outcome and key decisions. Your installed Databricks agent skills contain the **how** — the implementation patterns, CLI commands, and code. Use the goal for scope and context; use the skills for implementation.

Your job in this conversation is to:

1. Clarify whether the user is **integrating this recipe into an existing project** or **starting fresh from scratch**, and adapt accordingly.
2. Verify the local Databricks dev environment is ready (block below).
3. Use the recipe goal to understand scope, then **use your installed Databricks agent skills** to implement it step by step.

## Step 1 — Clarify intent before touching code

Ask **one** question, ideally with a multiple-choice tool (see guidelines):

- **Existing project**: the user already has a Databricks app / repo and wants to add this pattern to it. → Read the user's existing project structure first; apply the pattern surgically.
- **New project from this recipe**: the user wants this recipe as the starting point of a new app. → Run the local-bootstrap below first, then implement.
- **Just learning**: the user wants to understand the pattern without building anything yet. → Walk through the goal and explain what each piece does.
- **Not sure — help me decide**: ask the user what they're trying to accomplish at the project level, then map back to one of the above.

## Step 2 — Pin down recipe-specific decisions

Once the integration mode is clear, ask any follow-ups — typically about which Databricks resources to use:

- Should we **create new resources** (catalog, schema, Lakebase instance, serving endpoint) or **reuse existing ones** the user already has? Never assume; always ask.
- Which **Databricks profile** should the CLI commands target? (`databricks auth profiles` to list valid profiles.)
- If the recipe touches data: use the user's data, or use seed/sample data first?

## Step 3 — Verify the local Databricks dev environment

Whether integrating or starting fresh, your skills' commands assume a working Databricks CLI profile and (for app-related recipes) an AppKit project. **Walk the user through the local-bootstrap block below before running any commands** — even if they think the environment is already set up.

The recipe goal the user is focused on is attached after the local-bootstrap block.

---

# Verify your local Databricks dev environment

A working Databricks CLI profile is the prerequisite for every step that follows. The goal below describes what a ready environment looks like. Use your installed Databricks agent skills to verify and set up the environment — _even if the user says their environment is already set up_.

When done, you will have:

- Databricks CLI `1.0.0+` installed and on `PATH`
- An authenticated CLI profile (`databricks auth profiles` shows `Valid: YES`)
- A successful smoke test (`databricks current-user me` returns your identity)

---

# The recipe the user copied

The recipe goal is below — it describes what the user wants to build. Once the local-bootstrap above passes and the intent questions are answered, use your installed Databricks agent skills to implement it.

When done, you will have:

- A relational schema (chats and messages tables) in Lakebase for storing conversations
- Durable persistence of every chat turn: user input, assistant replies, and tool calls
- An app where users can return to previous chat sessions and continue where they left off
- Agent memory that survives restarts, deploys, and machine changes