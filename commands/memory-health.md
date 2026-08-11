# /memory-health — Store Health Check

Report on the memory store's health, and run decay if it's overdue. There's no background
daemon in a Claude Code setup — decay is deliberately idempotent and schedule-independent
(see `docs/memory-engineering-plan.md`, 4.5) precisely so that running it "whenever someone
happens to run `/memory-health`" gives identical results to running it on a strict cron.
This command is how a system with no scheduler stays maintained anyway.

## Engine
`VAULT_PATH/System/Scripts/memory.py` — run via Bash as
`python3 "VAULT_PATH/System/Scripts/memory.py" --vault "VAULT_PATH" <subcommand> ...`

## Steps

1. Run the health report:
   ```
   python3 "VAULT_PATH/System/Scripts/memory.py" --vault "VAULT_PATH" health
   ```

2. Present it as a short dashboard, not raw JSON:
   - **Store size:** counts by status (active / superseded / archived)
   - **Pending conflicts:** count, with a nudge to run `/memory-conflicts` if nonzero
   - **Nearing decay:** memories whose confidence is drifting toward the archive threshold —
     mention subjects/content, not just ids, so the user recognizes what's fading
   - **Never reinforced, 90+ days old:** candidates worth either reinforcing (if still true)
     or letting decay naturally
   - **Index drift:** if `index_in_sync` is false, run `reindex` to fix it before reporting
     further, then re-run `health`:
     ```
     python3 "VAULT_PATH/System/Scripts/memory.py" --vault "VAULT_PATH" reindex
     ```
   - **Decay status:** `last_decay_at`, `days_since_decay`, and whether it's `decay_overdue`

3. If `decay_overdue` is true, run it (do a dry run first so the user can see what would
   change, since archiving is the one operation here that changes a record's active/inactive
   status at scale):
   ```
   python3 "VAULT_PATH/System/Scripts/memory.py" --vault "VAULT_PATH" decay --dry-run
   ```
   Show what would be archived and why (expired vs. decayed below threshold). If it looks
   right — and it should, since nothing here is a judgment call, just threshold math — run
   it for real:
   ```
   python3 "VAULT_PATH/System/Scripts/memory.py" --vault "VAULT_PATH" decay
   ```
   Remind the user that archived memories aren't deleted — they're recoverable in
   `Memory/Archive/` if something turns out to still matter.

4. Regenerate CLAUDE.md's memory section if decay changed anything:
   ```
   python3 "VAULT_PATH/System/Scripts/memory.py" --vault "VAULT_PATH" render-claude-md
   ```

5. Close with one line: store is healthy / needs `/memory-conflicts` / needs a second look at
   [specific thing], so the user knows whether to act now or move on.
