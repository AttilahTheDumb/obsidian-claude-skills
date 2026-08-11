# /resume — Load Context

Load relevant memory and recent session history before starting work — relevance-scored,
not "read the last N logs regardless of what today is about." That's the difference
between retrieval and replay: a user with six months of history should cost the same on
message one as a user with six days, because what gets loaded is what's *relevant*, not
everything that ever happened.

## Vault Paths
- CLAUDE.md: `VAULT_PATH/CLAUDE.md`
- Session logs: `VAULT_PATH/Areas/Work/Session-Logs/`
- Memory engine: `VAULT_PATH/System/Scripts/memory.py`

## Steps

1. If `Memory/` doesn't exist yet in this vault (first run, or an older install), run:
   ```
   python3 "VAULT_PATH/System/Scripts/memory.py" --vault "VAULT_PATH" init
   ```
   If `CLAUDE.md` exists but has never been migrated (no `Memory/Facts/*.md` files at all
   and the file has bullet-list sections like `## Conventions & Standards`), offer to run
   `migrate-claude-md` once, non-destructively, before continuing.

2. Read `CLAUDE.md` — the `## Pinned` block is permanent context, always relevant. Note it,
   but don't dump it verbatim into the briefing unless it's short.

3. **Build the retrieval query** from `$ARGUMENTS`:
   - If `$ARGUMENTS` is non-empty, use it directly as the query — it's either a task
     description ("continuing the auth refactor") or a search term, and the same text
     works for both.
   - If `$ARGUMENTS` is empty, you don't yet know what today's work is about, so a
     relevance query isn't possible yet. Read just the frontmatter (`outcome`, `topics`)
     of the single most recent file in `Areas/Work/Session-Logs/` and use that as a
     provisional query — it's a reasonable guess that today continues yesterday. Say
     explicitly in the briefing that this is a provisional/general load, not a targeted one.

4. Retrieve:
   ```
   python3 "VAULT_PATH/System/Scripts/memory.py" --vault "VAULT_PATH" retrieve --query "<query>"
   ```
   This returns active memories scored on relevance, confidence, freshness, and
   reinforcement, above a floor — it can legitimately return nothing if nothing active is
   relevant. That's correct behavior, not a bug: don't pad the briefing with unrelated
   memories just to have something to show.

5. Read the single most recent file in `Areas/Work/Session-Logs/` in full (for continuity —
   what was just being worked on). If `$ARGUMENTS` included a search term that the
   retrieval step didn't fully cover, also grep session log contents for it and pull in any
   additional matches — this is the "deep dive" path for when relevance scoring against the
   distilled memory store isn't enough and the user wants the raw history.

6. Check store health lightly:
   ```
   python3 "VAULT_PATH/System/Scripts/memory.py" --vault "VAULT_PATH" health
   ```
   Note `pending_conflicts` if nonzero — mention it in the briefing, don't act on it here.

7. Regenerate CLAUDE.md's memory section so it reflects current state (this also means
   anyone reading CLAUDE.md by hand in Obsidian between sessions sees fresh data):
   ```
   python3 "VAULT_PATH/System/Scripts/memory.py" --vault "VAULT_PATH" render-claude-md
   ```

## Output Format

**Active projects:** [from CLAUDE.md's Active Projects section]
**Relevant memory:** [bullet list from the retrieve results — content only, skip ids/scores;
  say "nothing specific surfaced" if retrieval returned empty rather than omitting the line]
**Recent work:** [1-2 sentences from the most recent session log]
**Pending tasks:** [bullet list of open items from that log]
**Relevant context:** [any additional session-log search results, if a search term was given]

If `pending_conflicts > 0`: one line — "N memory conflicts pending — run `/memory-conflicts`
when you have a moment."

Then ask: "What are we working on today?" — and if step 3 used the provisional-query path,
consider re-running `retrieve` with the actual answer before diving in, since a targeted
query will usually surface more than the provisional one did.
