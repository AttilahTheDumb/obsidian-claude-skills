# Obsidian + Claude Code Skills

Claude Code slash commands — Obsidian integration for persistent AI memory, plus developer productivity skills.

## What this does

### Developer skills
- **`/test-gen`** — Behaviour-first test generation. Analyses what your code *promises* to do, writes tests that catch real bugs, matches your existing test style, and runs them to verify they pass. Works with pytest, Jest, Vitest, Go testing, RSpec, and more.

### Obsidian memory skills
- **`/resume`** — Loads your vault memory + recent session logs at the start of every session. Claude knows what you were working on, what decisions you made, what's pending.
- **`/compress`** — Saves the current conversation as a searchable session log before you close. Nothing gets lost.
- **`/preserve`** — Writes permanent learnings into your vault's `CLAUDE.md`. Auto-archives when it gets too long.
- **`/daily-note`** — Creates today's note with a priorities prompt.
- **`/meeting-note`** — Processes a transcript or rough notes into a structured meeting note with proper frontmatter.
- **`/weekly-review`** — Summarises the week from your daily notes and session logs.

## Requirements

- [Claude Code](https://claude.ai/code)
- [Obsidian](https://obsidian.md)
- [Local REST API](https://github.com/coddingtonbear/obsidian-local-rest-api) plugin for Obsidian (free, community plugin)
- Node.js (for `npx`)

## Install

```bash
git clone https://github.com/joesephm/obsidian-claude-skills
cd obsidian-claude-skills
chmod +x install.sh
./install.sh
```

The script will:
1. Detect your Obsidian vault (or ask for the path)
2. Ask for your Local REST API key and port
3. Create the vault folder structure
4. Install the skills to `~/.claude/commands/`
5. Register the `obsidian-mcp` server

Then restart Claude Code and run `/daily-note` to try it.

## Vault structure created

```
YourVault/
├── +Inbox/
├── Areas/
│   ├── Work/
│   │   ├── Projects/
│   │   ├── Meetings/
│   │   └── Session-Logs/      ← session memory lives here
│   ├── Personal/
│   └── Health/
├── Calendar/
│   ├── Daily/                 ← YYYY-MM-DD.md
│   ├── Weekly/
│   └── Monthly/
├── System/
│   ├── Templates/
│   └── Dashboards/
└── CLAUDE.md                  ← permanent AI memory file
```

## Getting the Local REST API key

1. Obsidian → Settings → Community plugins → search "Local REST API" → Install → Enable
2. In plugin settings, click **Generate** to create an API key
3. Note the port (default: 27124 for HTTPS)

## The philosophy

Write once, surface everywhere. You add frontmatter once when you create a note (`type`, `date`, `project`). From that point, the note automatically appears in project queries, daily notes, and search results without any manual linking.

Full writeup: [Claude Code + Obsidian](https://www.reddit.com/r/ClaudeAI/comments/1j6wy7k/claude_code_obsidian_how_i_use_it_short_guide/) by the original author.

## Related

- [CPR Skills](https://github.com/EliaAlberti/cpr-compress-preserve-resume) — the original `/compress`, `/preserve`, `/resume` skills this builds on
