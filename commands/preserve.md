# /preserve — Update Permanent Memory

Add key insights, decisions, or context to CLAUDE.md for permanent project memory.

## CLAUDE.md Location
`VAULT_PATH/CLAUDE.md`

## Steps

1. Ask what to preserve (or identify from the conversation):
   - Project conventions or naming standards
   - Architecture or tooling decisions
   - Important file paths or locations
   - Recurring workflows or processes
   - Anything a future AI session should know upfront

2. Read the current CLAUDE.md

3. Add content to the most appropriate section:
   - New project → `## Active Projects`
   - Convention or standard → `## Conventions & Standards`
   - New tool or integration → `## MCP Tools` or `## Skills`
   - General vault knowledge → `## About This Vault`

4. **Auto-archive check:** If CLAUDE.md exceeds 280 lines after the update:
   - Identify archivable content (completed projects, old notes, done sections)
   - Protect these sections — never move: `## About This Vault`, `## Key Paths`, `## MCP Tools`, `## Skills`, `## Conventions & Standards`
   - Move archivable content to `CLAUDE-Archive.md` in the vault root with a dated header
   - Add a reference link in CLAUDE.md pointing to the archive

5. Confirm what was saved and where.
