# /preserve — Update Permanent Memory

Add standards, conventions, and structural knowledge to CLAUDE.md — the parts of project
memory that are hand-curated rather than distilled from conversation. For facts about
preferences, decisions, and context that should flow through the memory pipeline instead
(so they can be scored, consolidated, and eventually decay), use `/remember`.

## CLAUDE.md Location
`VAULT_PATH/CLAUDE.md`

## What belongs here vs. in the memory store

`/preserve` writes into the **`## Pinned`** section, between the `<!-- pinned:start -->`
and `<!-- pinned:end -->` markers. That block is the one part of CLAUDE.md the memory
pipeline (`memory.py render-claude-md`, run by `/resume`) never rewrites — content placed
there is permanent until a human edits or removes it. Use it for:
   - Project conventions or naming standards
   - Architecture or tooling decisions that should never expire or decay
   - Important file paths or locations
   - Recurring workflows or processes
   - Anything a future AI session should know upfront, unconditionally

If what's being preserved is closer to a personal preference, a fact about the user, or
something that could plausibly change later (and should decay if it stops being reinforced),
prefer `/remember` instead — that's what the `## Memory` section (also in CLAUDE.md) surfaces.

## Steps

1. Ask what to preserve (or identify from the conversation). If it sounds more like a
   decaying/personal fact than a standing rule, suggest `/remember` instead and stop here
   unless the user confirms they want it pinned permanently.

2. Read the current CLAUDE.md.

3. If `<!-- pinned:start -->` / `<!-- pinned:end -->` markers exist, add the new content
   inside that block, under a `###` sub-heading if it doesn't already have one for this
   topic. If the markers don't exist yet (an older vault), add them near the top of the
   file, right after `## About This Vault`.

4. **Auto-archive check:** If the pinned block exceeds 280 lines after the update:
   - Identify archivable content (completed projects, stale notes, done sections) within
     the pinned block only — never touch content outside it, since that's owned by
     `memory.py render-claude-md` and other sections of the file.
   - Move archivable content to `CLAUDE-Archive.md` in the vault root with a dated header.
   - Add a reference link in the pinned block pointing to the archive.

5. Confirm what was saved and where.
