# /resume — Load Context

Load context from vault memory and recent session logs before starting work.

## Vault Paths
- CLAUDE.md: `VAULT_PATH/CLAUDE.md`
- Session logs: `VAULT_PATH/Areas/Work/Session-Logs/`

## Steps

1. Read CLAUDE.md — this is the permanent project memory
2. List all files in `Areas/Work/Session-Logs/` sorted by date, newest first
3. Parse arguments from `$ARGUMENTS`:
   - If a number is provided (e.g. `10`), read that many recent logs (default: 3)
   - If a search term is provided (e.g. `auth`), also search session log contents for that term
   - Both can be combined: `5 auth` means last 5 logs + search for "auth"
4. Read the selected session logs, focusing on `## Quick Reference` and `## Pending Tasks` first for speed
5. If a search term was given, scan raw session text for matching context

## Output Format

After loading, give a concise briefing:

**Active projects:** [list from CLAUDE.md]
**Recent work:** [1-2 sentences from session logs]
**Pending tasks:** [bullet list of open items]
**Relevant context:** [any search results if a term was given]

Then ask: "What are we working on today?"
