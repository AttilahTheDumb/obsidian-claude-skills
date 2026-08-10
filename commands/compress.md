# /compress — Save Session

Save the current conversation as a searchable session log before ending, then run a
capture pass over it: pull out anything durable and check it into the memory store, so
`/resume` can retrieve it by relevance in future sessions instead of you having to re-read
this whole transcript.

The session log (below) is the **episodic** record — raw, complete, append-only, never
deduplicated or decayed. It's the audit trail. The capture pass writes to the **semantic**
store (`Memory/Facts/`) — distilled, deduplicated, and subject to decay. Retrieval in
`/resume` reads the semantic store, not this log, which is what keeps it fast regardless of
how much history has accumulated.

## Session Log Location
`VAULT_PATH/Areas/Work/Session-Logs/`

## Memory Engine
`VAULT_PATH/System/Scripts/memory.py` — run via Bash as
`python3 "VAULT_PATH/System/Scripts/memory.py" --vault "VAULT_PATH" <subcommand> ...`

## Part 1 — Session Log

1. Ask the user what to include (offer multi-select, default to all):
   - [ ] Key learnings
   - [ ] Solutions & fixes
   - [ ] Decisions made
   - [ ] Files modified
   - [ ] Setup & config
   - [ ] Pending tasks
   - [ ] Errors & workarounds

2. Generate a filename: `YYYY-MM-DD-HH-MM-[topic-slug].md`
   - topic-slug: 2-4 word kebab-case summary of the session (e.g. `auth-flow-fix`, `vault-setup`)

3. Create the session log file with this format:

---
type: session
date: YYYY-MM-DD
topics: [topic1, topic2]
projects: [project-name]
outcome: One-line summary of what was accomplished
---

# Session: YYYY-MM-DD HH:MM — [Topic]

## Quick Reference
**Topics:** topic1, topic2
**Projects:** project-name
**Outcome:** One-line summary

## Decisions Made
- Decision 1

## Key Learnings
- Learning 1

## Pending Tasks
- [ ] Task 1

## Files Modified
- path/to/file

---

## Session Summary
[2-4 paragraph narrative written for a future AI to pick up context quickly]

4. Confirm the file was saved and show the path.

## Part 2 — Capture Pass

Run this against the whole session, not turn-by-turn — classifying with the full
conversation visible catches things an in-the-moment read would miss, and it's the reason
this runs once here instead of on every turn.

5. If `Memory/` doesn't exist yet in this vault, run:
   ```
   python3 "VAULT_PATH/System/Scripts/memory.py" --vault "VAULT_PATH" init
   ```

6. **Propose candidates.** Re-scan the session for statements that pass the durability
   test — *would this still be true and useful in three months?* Look past explicit
   "remember this" phrasing; most durable facts aren't announced, they're just stated
   ("I use pnpm for this", "skip the preamble on reviews", "the client's compliance
   deadline is the 15th"). For each candidate, note: the fact in your own words, a short
   direct quote as provenance, `subject` (kebab-case), `scope` (optional), `class`
   (`durable` or `expiring`, with `expires_at` if expiring), and a confidence 0.6–0.9.

   Also explicitly list what you're **rejecting** and why (usually: true only in this
   session, or too vague to act on later). This list matters as much as the accepted one —
   it's what makes over- and under-capture visible to the user instead of silently
   happening in either direction.

7. **Consolidate each accepted candidate** against the existing store, same judgment as
   `/remember` step 3:
   ```
   python3 "VAULT_PATH/System/Scripts/memory.py" --vault "VAULT_PATH" candidates --subject <subject>
   ```
   - No related record, or genuinely new information → insert:
     ```
     python3 "VAULT_PATH/System/Scripts/memory.py" --vault "VAULT_PATH" new \
       --content "<fact>" --subject <subject> --class <durable|expiring> \
       [--scope <scope>] --confidence <0.0-1.0> [--expires-at <ISO8601>] \
       --quote "<short quote>" --session-source "<session log filename from step 2>" \
       --source "<session log filename from step 2>"
     ```
   - Duplicate of an existing record → skip it, note that in the summary.
   - Restates and confirms an existing record → reinforce instead of inserting:
     ```
     python3 "VAULT_PATH/System/Scripts/memory.py" --vault "VAULT_PATH" reinforce --id <candidate id>
     ```
   - Unambiguously supersedes an existing record → supersede:
     ```
     python3 "VAULT_PATH/System/Scripts/memory.py" --vault "VAULT_PATH" supersede \
       --old-id <candidate id> --content "<new fact>" [--scope <scope>] [--confidence <0.0-1.0>]
     ```
   - Ambiguously contradicts an existing record → flag it, don't guess:
     ```
     python3 "VAULT_PATH/System/Scripts/memory.py" --vault "VAULT_PATH" flag-conflict \
       --old-id <candidate id> --new-content "<new fact>" --subject <subject> \
       --reason "<why this is ambiguous>"
     ```

8. Regenerate the `## Memory` section of CLAUDE.md so it reflects what's active now:
   ```
   python3 "VAULT_PATH/System/Scripts/memory.py" --vault "VAULT_PATH" render-claude-md
   ```

9. Summarize the capture pass in a few lines: how many facts inserted / reinforced /
   superseded / flagged as conflicts, how many rejected (with a one-line reason for each),
   and a nudge to run `/memory-conflicts` if anything was flagged.

10. Ask if anything should also be preserved permanently (a standing rule, not a decaying
    fact) with `/preserve`.
