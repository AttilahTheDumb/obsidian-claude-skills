# /compress — Save Session

Save the current conversation as a searchable session log before ending.

## Session Log Location
`VAULT_PATH/Areas/Work/Session-Logs/`

## Steps

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
5. Ask if anything should be preserved permanently with `/preserve`.
