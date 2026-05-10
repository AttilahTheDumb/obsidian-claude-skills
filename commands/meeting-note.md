# /meeting-note — Process a Meeting into a Structured Note

Turn a meeting transcript, voice note summary, or rough notes into a structured Obsidian note.

## Location
`VAULT_PATH/Areas/Work/Meetings/`

## Steps

1. Ask for the meeting input if not already provided:
   - Paste transcript, summary, or rough notes
   - Or describe the meeting verbally

2. Extract and confirm:
   - Date (default: today)
   - Attendees
   - Project it relates to (check CLAUDE.md Active Projects for options)
   - Meeting type (standup, client call, planning, review, 1:1)

3. Generate filename: `YYYY-MM-DD-[meeting-type]-[project-or-topic].md`

4. Create the file with this structure:

---
type: meeting
date: YYYY-MM-DD
project: project-name
attendees: [Person1, Person2]
status: completed
tags: [meeting-type]
---

# Meeting: [Topic] — YYYY-MM-DD

## Attendees
- Person1

## Summary
[2-3 sentence overview]

## Key Decisions
- Decision 1

## Action Items
- [ ] Task — Owner — Due date

## Notes
[Detailed notes]

5. Confirm the file was saved. The frontmatter ensures it surfaces automatically in any project query using `project:` metadata.
