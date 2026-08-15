---
title: "Trading Journal System AI Router"
type: ai-instruction
status: active
owner: "Trading Journal"
created: 2026-08-13
updated: 2026-08-13
ai_access: internal
ai_generated: true
review_status: draft
canonical: true
---

# Trading Journal System AI Router

`AGENTS.md` is the canonical shared AI router for this project.

## Bootstrap

1. Confirm the root by locating this file and `README.md`.
2. Read `README.md`.
3. Read `handoff.md` to know the current state and next action.
4. Classify the task.
5. Load only the matching context bundle.
6. Stop loading when enough verified context exists.

## Task Bundles

- **Quick task**: `AGENTS.md`, `README.md`.
- **Normal active work**: add `memory.md` and `handoff.md`.
- **Active project design**: add `PROJECT-CONTEXT.md`, `requirements.md`, and `architecture.md`.
- **Implementation**: add the relevant module README or inline comments; do not broadly load the entire codebase.

## Local Skills

Project-specific skill guides in `skills/` — load the relevant one when doing deep work in that area:

- **UI/UX work**: `skills/ui-ux-pro-max.md` + `skills/frontend-design.md`
- **Backend/API work**: `skills/fastapi-python.md`
- **Trading logic/journal features**: `skills/trade-journal.md`
- **Refactoring/architecture**: `skills/solid-principles.md`

## Default Exclusions

Never broadly load:
- `media/`, `uploads/`, attachments, screenshots
- `.env`, credentials, secrets
- `logs/`, runtime state, generated reports
- The entire Excel file unless importing data
- Full database dumps or raw trade history unless doing data analysis

## Write Rules

- Preserve existing content and use reversible edits.
- Never store credentials, secrets, or database passwords in Markdown or code comments.
- Use `.env` and `.env.example` for configuration.
- Treat missing `ai_access` as restricted.
- AI-generated operational knowledge starts as draft.
- `memory.md` is durable and approved; `handoff.md` is current and replace-and-refresh.
- Do not commit, publish, configure remotes, or push without explicit authorization.
