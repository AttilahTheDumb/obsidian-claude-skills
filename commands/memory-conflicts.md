# /memory-conflicts — Review the Conflict Queue

Resolve facts that `/remember`, `/compress`, or `/memory-gc` flagged as contradicting an
existing memory without a clear enough signal to resolve automatically. This command is
where that ambiguity finally gets a human decision instead of a guess — nothing in this
pipeline auto-resolves a flagged conflict; that's the whole point of the queue existing.

## Engine
`VAULT_PATH/System/Scripts/memory.py` — run via Bash as
`python3 "VAULT_PATH/System/Scripts/memory.py" --vault "VAULT_PATH" <subcommand> ...`

## Steps

1. List pending conflicts:
   ```
   python3 "VAULT_PATH/System/Scripts/memory.py" --vault "VAULT_PATH" list-conflicts
   ```
   If empty, say so and stop — there's nothing to review.

2. For each pending conflict, show the user both sides plainly:
   - The existing (`old_id`) record's current content — look it up if useful context (when
     it was captured, how many times it's been reinforced).
   - The proposed new content that triggered the flag.
   - The reason it was flagged (from the conflict record's body).

3. Ask the user to choose, per conflict:
   - **The new one is right** → `--action supersede` (old is marked superseded, new becomes
     the active record).
   - **The old one is still right, discard the new claim** → `--action discard-new` (nothing
     changes except the conflict is closed).
   - **The old one is wrong and should go away, but the new one isn't a replacement either**
     → `--action discard-old` (old is archived, nothing new is written).
   - **Both are true, just in different contexts** → `--action coexist`, and ask what scope
     distinguishes them (e.g. `work` vs `personal`) so both can stay active without
     re-triggering this same conflict:
     ```
     python3 "VAULT_PATH/System/Scripts/memory.py" --vault "VAULT_PATH" resolve-conflict \
       --conflict-id <id> --action coexist --old-scope <scope> --new-scope <scope>
     ```
   - **Still genuinely unclear even with the user looking at it** → leave it pending, move
     on to the next one. Don't force a resolution just to clear the queue.

4. Apply each resolution:
   ```
   python3 "VAULT_PATH/System/Scripts/memory.py" --vault "VAULT_PATH" resolve-conflict \
     --conflict-id <id> --action <supersede|discard-new|discard-old|coexist> [--old-scope <s>] [--new-scope <s>]
   ```

5. Regenerate CLAUDE.md's memory section if anything changed:
   ```
   python3 "VAULT_PATH/System/Scripts/memory.py" --vault "VAULT_PATH" render-claude-md
   ```

6. Summarize: how many resolved, how many left pending and why.
