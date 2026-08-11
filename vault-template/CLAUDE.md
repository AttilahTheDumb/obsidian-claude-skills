# Project Memory — [Your Name]'s Vault

## About This Vault
Personal knowledge base and project workspace. Connected to Claude Code via obsidian-mcp,
with a memory pipeline (Capture → Consolidate → Retrieve → Reconcile → Decay) backing it —
see `Memory/` and `System/Scripts/memory.py`.

Use `/resume` to load relevant memory + recent session logs at the start of any session.
Use `/remember` to pin a durable fact right now, or `/preserve` for standards/conventions.
Use `/compress` to save a session log before ending — it also runs the capture pass.
Use `/memory-gc`, `/memory-conflicts`, and `/memory-health` to maintain the store.

## Key Paths
- **Vault root:** `VAULT_PATH`
- **Memory store:** `VAULT_PATH/Memory/` (`Facts/`, `Archive/`, `Conflicts/`, `index.json`)
- **Memory engine:** `VAULT_PATH/System/Scripts/memory.py`
- **Session logs:** `VAULT_PATH/Areas/Work/Session-Logs/`
- **Projects:** `VAULT_PATH/Areas/Work/Projects/`
- **Meetings:** `VAULT_PATH/Areas/Work/Meetings/`
- **Daily notes:** `VAULT_PATH/Calendar/Daily/`
- **Inbox:** `VAULT_PATH/+Inbox/`

## Pinned
<!-- pinned:start -->
*(Add anything here that should never be auto-generated or auto-archived — e.g. hard
constraints, standing instructions. `/preserve` and `render-claude-md` never touch this block.)*
<!-- pinned:end -->

## Memory
<!-- generated:start -->
*(This block is regenerated from `Memory/Facts/` by `memory.py render-claude-md`, run
automatically at the end of `/resume`. Don't hand-edit it — edit or add records instead,
via `/remember`, `/compress`, or directly in `Memory/Facts/`.)*
<!-- generated:end -->

## Active Projects
*(Projects will appear here as you create them)*

## Conventions & Standards
- Daily note filename: `YYYY-MM-DD.md` in `Calendar/Daily/`
- Meeting note frontmatter: `type: meeting`, `date`, `project`, `attendees`, `status`
- Session log frontmatter: `type: session`, `date`, `topics`, `projects`, `outcome`
- Project note frontmatter: `type: project`, `date`, `status: active|on-hold|completed`
- Memory record frontmatter: see `Memory/Facts/*.md` — `class: durable|expiring`,
  `subject`, `scope`, `base_confidence`, `status: active|superseded|archived`

## MCP Tools
- **obsidian-mcp**: Read, write, search, and create notes in the vault.

## Skills
- `/resume` — Load relevant memory + recent session logs for the task at hand
- `/compress` — Save the current session as a searchable log, and capture durable facts from it
- `/remember` — Pin a durable fact to memory immediately, mid-session
- `/preserve` — Add permanent conventions/standards to the pinned block of this file
- `/memory-gc` — Re-run consolidation across the whole memory store to clear duplicates
- `/memory-conflicts` — Review and resolve facts flagged as contradicting each other
- `/memory-health` — Report on the memory store's health (decay, drift, pending conflicts)
- `/daily-note` — Create or open today's note
- `/meeting-note` — Process a meeting into a structured note
- `/weekly-review` — Summarise the week from daily notes + session logs
