# /memory-gc — Retroactive Consolidation

Run the same consolidation judgment `/remember` and `/compress` apply on write, but
retroactively across the whole store — for cleaning up duplicates and near-duplicates that
piled up before this pipeline existed (e.g. right after `migrate-claude-md`, which
extracts one record per bullet with no dedup), or that slipped through despite it.

## Engine
`VAULT_PATH/System/Scripts/memory.py` — run via Bash as
`python3 "VAULT_PATH/System/Scripts/memory.py" --vault "VAULT_PATH" <subcommand> ...`

## Steps

1. Get every active subject in the store. There's no dedicated subcommand for this — list
   `Memory/Facts/*.md`, or read `Memory/index.json`, and collect the distinct `subject`
   values from `active` records.

2. For each subject with more than one active record, pull the shortlist:
   ```
   python3 "VAULT_PATH/System/Scripts/memory.py" --vault "VAULT_PATH" candidates --subject <subject>
   ```

3. For each pair within a subject's shortlist, judge the relationship — this is the same
   call `/remember` step 3 makes for a single new fact, applied pairwise here:
   - **Near-identical restatements** (including ones that only differ because they were
     extracted from different bullets in an old `CLAUDE.md`) → keep the one with the
     stronger current confidence (or the more specific wording if confidence ties), and
     merge the other into it — this points the duplicate's `superseded_by` at the kept
     record without minting a redundant new one, and counts as a reinforcement of the kept
     record:
     ```
     python3 "VAULT_PATH/System/Scripts/memory.py" --vault "VAULT_PATH" merge \
       --keep-id <stronger id> --drop-id <weaker id>
     ```
   - **Related but covering different aspects of the same subject** (e.g. "uses pnpm" and
     "pnpm workspace is at repo root") → leave both active, no action.
   - **Genuinely contradictory and the resolution is obvious from timestamps/content**
     (a later record is a clear correction) → supersede the older one:
     ```
     python3 "VAULT_PATH/System/Scripts/memory.py" --vault "VAULT_PATH" supersede \
       --old-id <older id> --content "<current content>" --subject <subject>
     ```
   - **Genuinely contradictory and unclear which is current** → don't guess, file it:
     ```
     python3 "VAULT_PATH/System/Scripts/memory.py" --vault "VAULT_PATH" flag-conflict \
       --old-id <one id> --new-content "<the other record's content>" --subject <subject> \
       --reason "found during /memory-gc, ambiguous which is current"
     ```

4. Regenerate CLAUDE.md's memory section:
   ```
   python3 "VAULT_PATH/System/Scripts/memory.py" --vault "VAULT_PATH" render-claude-md
   ```

5. Summarize: how many subjects reviewed, how many duplicates merged, how many
   contradictions superseded, how many flagged. If anything was flagged, point at
   `/memory-conflicts`.

## Note

This command only ever *acts* on pairs where the relationship is clear. When in doubt
between two plausible readings of a pair, flag it rather than picking — the conflict queue
existing is what makes it safe to be conservative here instead of forcing every ambiguous
case to fit `insert`/`merge`/`skip`.
