# Obsidian + Claude Code Skills

Ten Claude Code slash commands that turn your Obsidian vault into a persistent AI brain — with
a real memory pipeline (not just transcript replay), automatic relevance-scored context
loading, and structured note creation.

## What this does

### Memory pipeline
Five stages — Capture, Consolidate, Retrieve, Reconcile, Decay — backed by
`scripts/memory.py` and a `Memory/` store in your vault. See
[`docs/memory-engineering-plan.md`](docs/memory-engineering-plan.md) for the design and why
it's built this way rather than as "read the whole history every time."

- **`/resume`** — Loads memory *relevant to what you're doing*, not just the last N logs, plus recent session-log continuity. Claude knows what you were working on, what decisions you made, what's pending — without re-reading everything you've ever discussed.
- **`/remember`** — Pins a durable fact to memory right now, mid-session.
- **`/compress`** — Saves the session as a searchable log, then runs a capture pass that distills durable facts into memory (with a rejected-list shown, so over- and under-capture are both visible).
- **`/memory-gc`** — Retroactively consolidates the store — collapses duplicates, resolves obvious contradictions, flags ambiguous ones.
- **`/memory-conflicts`** — Reviews facts flagged as contradicting each other and resolves them with your input; nothing auto-resolves silently.
- **`/memory-health`** — Reports store health (decay status, drift, pending conflicts) and runs decay when it's due.

### Notes
- **`/preserve`** — Writes standing conventions/decisions into CLAUDE.md's pinned block (permanent, never auto-generated or auto-archived by the memory pipeline).
- **`/daily-note`** — Creates today's note with a priorities prompt.
- **`/meeting-note`** — Processes a transcript or rough notes into a structured meeting note with proper frontmatter.
- **`/weekly-review`** — Summarises the week from your daily notes and session logs.

## Requirements

- [Claude Code](https://claude.ai/code)
- [Obsidian](https://obsidian.md)
- [Local REST API](https://github.com/coddingtonbear/obsidian-local-rest-api) plugin for Obsidian (free, community plugin)
- Node.js (for `npx`)
- Python 3 (for the memory engine — stdlib only, no pip installs needed)

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
3. Create the vault folder structure, including `Memory/`
4. Install the memory engine to `System/Scripts/memory.py` and initialise the store
5. Install the skills to `~/.claude/commands/`
6. Register the `obsidian-mcp` server

Then restart Claude Code and run `/daily-note` to try it.

If you already have a `CLAUDE.md` from before this pipeline existed, the installer leaves it
untouched and tells you how to run `memory.py migrate-claude-md` — a non-destructive,
one-time extraction of its bullet points into the memory store.

## Vault structure created

```
YourVault/
├── +Inbox/
├── Areas/
│   ├── Work/
│   │   ├── Projects/
│   │   ├── Meetings/
│   │   └── Session-Logs/      ← episodic record: raw, append-only, never decayed
│   ├── Personal/
│   └── Health/
├── Calendar/
│   ├── Daily/                 ← YYYY-MM-DD.md
│   ├── Weekly/
│   └── Monthly/
├── Memory/
│   ├── Facts/                 ← semantic store: distilled, deduplicated, decaying
│   ├── Archive/                   (decayed/superseded — never deleted, always recoverable)
│   ├── Conflicts/              ← ambiguous contradictions awaiting review
│   └── index.json             ← derived cache, rebuildable from Facts/ + Archive/ at any time
├── System/
│   ├── Templates/
│   ├── Dashboards/
│   └── Scripts/memory.py      ← the memory engine (stdlib-only Python)
└── CLAUDE.md                  ← pinned block (permanent) + generated memory view
```

## Getting the Local REST API key

1. Obsidian → Settings → Community plugins → search "Local REST API" → Install → Enable
2. In plugin settings, click **Generate** to create an API key
3. Note the port (default: 27124 for HTTPS)

## Development

The memory engine's deterministic core (decay math, retrieval scoring, record I/O) has a
test suite — the parts of the pipeline that require semantic judgment (is this durable? do
these two facts contradict?) are deliberately left to Claude at runtime and aren't unit
tested, since that judgment lives in the slash commands under `commands/`, not in Python.

```bash
python3 -m unittest tests.test_memory -v
```

## The philosophy

Write once, surface everywhere. You add frontmatter once when you create a note (`type`, `date`, `project`). From that point, the note automatically appears in project queries, daily notes, and search results without any manual linking.

Full writeup: [Claude Code + Obsidian](https://www.reddit.com/r/ClaudeAI/comments/1j6wy7k/claude_code_obsidian_how_i_use_it_short_guide/) by the original author.

## Related

- [CPR Skills](https://github.com/EliaAlberti/cpr-compress-preserve-resume) — the original `/compress`, `/preserve`, `/resume` skills this builds on
