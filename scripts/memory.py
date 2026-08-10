#!/usr/bin/env python3
"""
Deterministic core of the vault memory pipeline (Capture -> Consolidate ->
Retrieve -> Reconcile -> Decay). See docs/memory-engineering-plan.md.

Design rule: this file does everything that must be exact and testable
(decay math, scoring, id generation, file/index bookkeeping). It never
judges whether a statement is durable, whether two facts contradict, or
how they should merge -- that judgment belongs to the calling Claude Code
skill, which shells out to the subcommands below to read and write state.

No third-party dependencies (this file is copied into the user's vault by
install.sh and must run with a bare `python3`).
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

# ── Tunables ──────────────────────────────────────────────────────────────

DURABLE_HALF_LIFE_DAYS = 180.0
ARCHIVE_THRESHOLD = 0.15
RETRIEVE_FLOOR = 0.35
RETRIEVE_TOP_K = 5
FRESHNESS_WINDOW_DAYS = 60.0
REINFORCEMENT_SATURATION = 10

STATUS_ACTIVE = "active"
STATUS_SUPERSEDED = "superseded"
STATUS_ARCHIVED = "archived"

CLASS_DURABLE = "durable"
CLASS_EXPIRING = "expiring"

FACTS_DIR = "Memory/Facts"
ARCHIVE_DIR = "Memory/Archive"
CONFLICTS_DIR = "Memory/Conflicts"
CONFLICTS_RESOLVED_DIR = "Memory/Conflicts/Resolved"
INDEX_PATH = "Memory/index.json"


# ── Time helpers ─────────────────────────────────────────────────────────

def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def to_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def from_iso(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)


def days_between(earlier: datetime, later: datetime) -> float:
    return max(0.0, (later - earlier).total_seconds() / 86400.0)


# ── Minimal frontmatter parser/renderer ─────────────────────────────────
#
# Deliberately not a general YAML parser -- the memory record schema only
# ever needs scalars, null, and flat lists, so a hand-rolled parser avoids
# requiring PyYAML on a bare `python3` in the user's environment.

def _parse_scalar(raw: str):
    raw = raw.strip()
    if raw == "" or raw == "null" or raw == "~":
        return None
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if not inner:
            return []
        return [item.strip().strip('"').strip("'") for item in inner.split(",")]
    if raw.startswith('"') and raw.endswith('"') and len(raw) >= 2:
        return raw[1:-1]
    if raw.startswith("'") and raw.endswith("'") and len(raw) >= 2:
        return raw[1:-1]
    if re.fullmatch(r"-?\d+", raw):
        return int(raw)
    if re.fullmatch(r"-?\d+\.\d+", raw):
        return float(raw)
    return raw


def _render_scalar(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(str(v) for v in value) + "]"
    text = str(value)
    if any(ch in text for ch in [":", "#"]) or text != text.strip():
        return json.dumps(text)
    return text


def parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    _, fm_raw, body = parts
    data = {}
    for line in fm_raw.strip("\n").split("\n"):
        if not line.strip() or line.strip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, raw_value = line.partition(":")
        data[key.strip()] = _parse_scalar(raw_value)
    return data, body.lstrip("\n")


def render_frontmatter(data: dict, body: str) -> str:
    lines = ["---"]
    for key, value in data.items():
        lines.append(f"{key}: {_render_scalar(value)}")
    lines.append("---")
    header = "\n".join(lines)
    body = body.strip("\n")
    return f"{header}\n\n{body}\n" if body else f"{header}\n"


# ── Record model ─────────────────────────────────────────────────────────

RECORD_FIELDS = [
    "id", "type", "class", "content", "subject", "scope", "base_confidence",
    "captured_at", "last_reinforced", "reinforce_count", "last_retrieved",
    "expires_at", "status", "supersedes", "superseded_by", "source",
]


@dataclass
class Record:
    id: str
    content: str
    subject: str
    body: str = ""
    type: str = "memory"
    cls: str = CLASS_DURABLE  # 'class' shadows a builtin, keep it out of kwargs
    scope: Optional[str] = None
    base_confidence: float = 0.8
    captured_at: str = ""
    last_reinforced: str = ""
    reinforce_count: int = 0
    last_retrieved: str = ""
    expires_at: Optional[str] = None
    status: str = STATUS_ACTIVE
    supersedes: Optional[str] = None
    superseded_by: Optional[str] = None
    source: Optional[str] = None
    path: Optional[Path] = None

    def to_frontmatter(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "class": self.cls,
            "content": self.content,
            "subject": self.subject,
            "scope": self.scope,
            "base_confidence": round(self.base_confidence, 4),
            "captured_at": self.captured_at,
            "last_reinforced": self.last_reinforced,
            "reinforce_count": self.reinforce_count,
            "last_retrieved": self.last_retrieved,
            "expires_at": self.expires_at,
            "status": self.status,
            "supersedes": self.supersedes,
            "superseded_by": self.superseded_by,
            "source": self.source,
        }

    def render(self) -> str:
        return render_frontmatter(self.to_frontmatter(), self.body)

    def to_index_entry(self) -> dict:
        entry = self.to_frontmatter()
        entry["path"] = str(self.path) if self.path else None
        return entry

    @staticmethod
    def from_file(path: Path) -> "Record":
        text = path.read_text(encoding="utf-8")
        data, body = parse_frontmatter(text)
        return Record(
            id=data.get("id", path.stem),
            content=data.get("content", ""),
            subject=data.get("subject", ""),
            body=body,
            type=data.get("type", "memory"),
            cls=data.get("class", CLASS_DURABLE),
            scope=data.get("scope"),
            base_confidence=float(data.get("base_confidence", 0.8) or 0.8),
            captured_at=data.get("captured_at", ""),
            last_reinforced=data.get("last_reinforced", data.get("captured_at", "")),
            reinforce_count=int(data.get("reinforce_count", 0) or 0),
            last_retrieved=data.get("last_retrieved", ""),
            expires_at=data.get("expires_at"),
            status=data.get("status", STATUS_ACTIVE),
            supersedes=data.get("supersedes"),
            superseded_by=data.get("superseded_by"),
            source=data.get("source"),
            path=path,
        )


# ── Confidence / decay math ─────────────────────────────────────────────

def compute_confidence(record: Record, now: datetime) -> float:
    """
    Pure function of stored timestamps -- never mutates state, so calling
    it once after 30 days gives the same answer as calling it daily for
    30 days. That is what makes the decay command idempotent and
    schedule-independent (see docs/memory-engineering-plan.md, 4.5).
    """
    if record.cls == CLASS_EXPIRING:
        expires = from_iso(record.expires_at)
        if expires is not None and now >= expires:
            return 0.0
        return record.base_confidence

    last_reinforced = from_iso(record.last_reinforced) or from_iso(record.captured_at) or now
    half_life = DURABLE_HALF_LIFE_DAYS * (1 + math.log1p(record.reinforce_count))
    idle_days = days_between(last_reinforced, now)
    return record.base_confidence * (0.5 ** (idle_days / half_life))


def reinforcement_score(reinforce_count: int) -> float:
    return min(math.log1p(reinforce_count) / math.log1p(REINFORCEMENT_SATURATION), 1.0)


def freshness_score(record: Record, now: datetime) -> float:
    last_reinforced = from_iso(record.last_reinforced) or from_iso(record.captured_at) or now
    idle_days = days_between(last_reinforced, now)
    return 1.0 / (1.0 + idle_days / FRESHNESS_WINDOW_DAYS)


def tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def relevance_score(query_tokens: set[str], record: Record) -> float:
    fact_tokens = tokenize(record.content) | tokenize(record.subject)
    if not query_tokens or not fact_tokens:
        return 0.0
    overlap = query_tokens & fact_tokens
    union = query_tokens | fact_tokens
    return len(overlap) / len(union) if union else 0.0


def retrieval_score(record: Record, query_tokens: set[str], now: datetime) -> dict:
    relevance = relevance_score(query_tokens, record)
    confidence = compute_confidence(record, now)
    freshness = freshness_score(record, now)
    reinforcement = reinforcement_score(record.reinforce_count)
    total = (
        0.55 * relevance
        + 0.20 * confidence
        + 0.15 * freshness
        + 0.10 * reinforcement
    )
    return {
        "score": total,
        "relevance": relevance,
        "confidence": confidence,
        "freshness": freshness,
        "reinforcement": reinforcement,
    }


# ── Vault / filesystem plumbing ─────────────────────────────────────────

class Vault:
    def __init__(self, root: Path):
        self.root = root
        self.facts_dir = root / FACTS_DIR
        self.archive_dir = root / ARCHIVE_DIR
        self.conflicts_dir = root / CONFLICTS_DIR
        self.conflicts_resolved_dir = root / CONFLICTS_RESOLVED_DIR
        self.index_path = root / INDEX_PATH

    def init(self) -> None:
        for d in (self.facts_dir, self.archive_dir, self.conflicts_dir, self.conflicts_resolved_dir):
            d.mkdir(parents=True, exist_ok=True)
        if not self.index_path.exists():
            self.write_index({"version": 1, "updated_at": to_iso(now_utc()), "memories": {}})

    def read_index(self) -> dict:
        if not self.index_path.exists():
            return {"version": 1, "updated_at": None, "memories": {}}
        return json.loads(self.index_path.read_text(encoding="utf-8"))

    def write_index(self, index: dict) -> None:
        index["updated_at"] = to_iso(now_utc())
        self.index_path.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def upsert_index_entry(self, record: Record) -> None:
        index = self.read_index()
        index["memories"][record.id] = record.to_index_entry()
        self.write_index(index)

    def all_records(self, include_archived: bool = True) -> list[Record]:
        records = [Record.from_file(p) for p in sorted(self.facts_dir.glob("*.md"))]
        if include_archived:
            records += [Record.from_file(p) for p in sorted(self.archive_dir.glob("*.md"))]
        return records

    def active_records(self) -> list[Record]:
        return [r for r in self.all_records(include_archived=False) if r.status == STATUS_ACTIVE]

    def find(self, memory_id: str) -> Optional[Record]:
        for d in (self.facts_dir, self.archive_dir):
            p = d / f"{memory_id}.md"
            if p.exists():
                return Record.from_file(p)
        return None

    def save(self, record: Record) -> None:
        assert record.path is not None
        record.path.write_text(record.render(), encoding="utf-8")
        self.upsert_index_entry(record)

    def reindex(self) -> int:
        index = {"version": 1, "updated_at": None, "memories": {}}
        count = 0
        for record in self.all_records(include_archived=True):
            index["memories"][record.id] = record.to_index_entry()
            count += 1
        self.write_index(index)
        return count


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "misc"


def new_id(now: datetime) -> str:
    return f"mem-{now.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4]}"


# ── Subcommand implementations ──────────────────────────────────────────

def cmd_init(args):
    vault = Vault(Path(args.vault))
    vault.init()
    print(f"Initialized memory store at {vault.root / 'Memory'}")


def cmd_new(args):
    vault = Vault(Path(args.vault))
    vault.init()
    now = from_iso(args.now) if args.now else now_utc()
    subject = slugify(args.subject)
    record_id = new_id(now)
    body_parts = [args.content.strip()]
    if args.quote:
        prov = f'> "{args.quote}"'
        if args.session_source:
            prov += f"\n— {args.session_source}"
        body_parts.append(f"## Provenance\n{prov}")
    record = Record(
        id=record_id,
        content=args.content.strip(),
        subject=subject,
        body="\n\n".join(body_parts),
        cls=args.klass,
        scope=args.scope,
        base_confidence=args.confidence,
        captured_at=to_iso(now),
        last_reinforced=to_iso(now),
        reinforce_count=0,
        last_retrieved=to_iso(now),
        expires_at=args.expires_at,
        status=STATUS_ACTIVE,
        source=args.source,
        path=vault.facts_dir / f"{record_id}.md",
    )
    vault.save(record)
    print(record_id)


def cmd_candidates(args):
    vault = Vault(Path(args.vault))
    subject = slugify(args.subject)
    out = []
    for record in vault.active_records():
        if record.subject != subject:
            continue
        if args.scope and record.scope and record.scope != args.scope:
            continue
        out.append(record.to_frontmatter() | {"body": record.body})
    print(json.dumps(out, indent=2))


def cmd_search(args):
    vault = Vault(Path(args.vault))
    query_tokens = tokenize(args.query)
    now = now_utc()
    scored = []
    for record in vault.active_records():
        s = relevance_score(query_tokens, record)
        if s > 0:
            scored.append((s, record))
    scored.sort(key=lambda t: t[0], reverse=True)
    out = [
        {"id": r.id, "content": r.content, "subject": r.subject, "relevance": round(s, 3)}
        for s, r in scored[: args.limit]
    ]
    print(json.dumps(out, indent=2))


def cmd_retrieve(args):
    vault = Vault(Path(args.vault))
    now = from_iso(args.now) if args.now else now_utc()
    query_tokens = tokenize(args.query)
    scored = []
    for record in vault.active_records():
        s = retrieval_score(record, query_tokens, now)
        if s["score"] >= args.floor:
            scored.append((s, record))
    scored.sort(key=lambda t: t[0]["score"], reverse=True)
    top = scored[: args.top_k]

    for _, record in top:
        record.last_retrieved = to_iso(now)
        vault.save(record)

    out = [
        {
            "id": record.id,
            "content": record.content,
            "subject": record.subject,
            "class": record.cls,
            "scope": record.scope,
            "score": round(s["score"], 4),
            "relevance": round(s["relevance"], 4),
            "confidence": round(s["confidence"], 4),
        }
        for s, record in top
    ]
    print(json.dumps(out, indent=2))


def cmd_reinforce(args):
    vault = Vault(Path(args.vault))
    now = from_iso(args.now) if args.now else now_utc()
    record = vault.find(args.id)
    if record is None:
        print(f"error: no memory {args.id}", file=sys.stderr)
        sys.exit(1)
    # Snapshot the currently-decayed confidence rather than resetting to the
    # original capture strength -- reinforcement resets the decay clock and
    # lengthens the effective half-life, it doesn't retroactively undo decay.
    record.base_confidence = compute_confidence(record, now)
    record.last_reinforced = to_iso(now)
    record.reinforce_count += 1
    vault.save(record)
    print(json.dumps(record.to_frontmatter(), indent=2))


def cmd_supersede(args):
    vault = Vault(Path(args.vault))
    now = from_iso(args.now) if args.now else now_utc()
    old = vault.find(args.old_id)
    if old is None:
        print(f"error: no memory {args.old_id}", file=sys.stderr)
        sys.exit(1)
    subject = args.subject or old.subject
    new_record_id = new_id(now)
    new_record = Record(
        id=new_record_id,
        content=args.content.strip(),
        subject=slugify(subject),
        body=args.content.strip(),
        cls=args.klass or old.cls,
        scope=args.scope if args.scope is not None else old.scope,
        base_confidence=args.confidence if args.confidence is not None else old.base_confidence,
        captured_at=to_iso(now),
        last_reinforced=to_iso(now),
        reinforce_count=0,
        last_retrieved=to_iso(now),
        expires_at=args.expires_at,
        status=STATUS_ACTIVE,
        supersedes=old.id,
        source=args.source,
        path=vault.facts_dir / f"{new_record_id}.md",
    )
    old.status = STATUS_SUPERSEDED
    old.superseded_by = new_record_id
    vault.save(old)
    vault.save(new_record)
    print(new_record_id)


def cmd_decay(args):
    vault = Vault(Path(args.vault))
    now = from_iso(args.now) if args.now else now_utc()
    archived, kept = [], []
    for record in vault.active_records():
        confidence = compute_confidence(record, now)
        expired = record.cls == CLASS_EXPIRING and record.expires_at and now >= from_iso(record.expires_at)
        if expired or confidence <= args.threshold:
            archived.append((record, "expired" if expired else "decayed", confidence))
        else:
            kept.append((record, confidence))

    for record, reason, confidence in archived:
        record.status = STATUS_ARCHIVED
        if not args.dry_run:
            old_path = record.path
            new_path = vault.archive_dir / old_path.name
            record.path = new_path
            new_path.write_text(record.render(), encoding="utf-8")
            old_path.unlink()
            vault.upsert_index_entry(record)

    print(json.dumps({
        "archived": [{"id": r.id, "reason": reason, "confidence": round(c, 4)} for r, reason, c in archived],
        "kept": len(kept),
        "dry_run": args.dry_run,
    }, indent=2))


def cmd_flag_conflict(args):
    vault = Vault(Path(args.vault))
    vault.init()
    now = from_iso(args.now) if args.now else now_utc()
    conflict_id = f"conflict-{now.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4]}"
    data = {
        "id": conflict_id,
        "type": "conflict",
        "status": "pending",
        "old_id": args.old_id,
        "new_content": args.new_content,
        "subject": slugify(args.subject) if args.subject else None,
        "new_source": args.source,
        "flagged_at": to_iso(now),
    }
    body = args.reason or "Ambiguous relationship between existing and new fact -- needs human review."
    path = vault.conflicts_dir / f"{conflict_id}.md"
    path.write_text(render_frontmatter(data, body), encoding="utf-8")
    print(conflict_id)


def cmd_list_conflicts(args):
    vault = Vault(Path(args.vault))
    out = []
    for p in sorted(vault.conflicts_dir.glob("*.md")):
        data, body = parse_frontmatter(p.read_text(encoding="utf-8"))
        if data.get("status") == "pending":
            out.append(data | {"body": body})
    print(json.dumps(out, indent=2))


def cmd_resolve_conflict(args):
    vault = Vault(Path(args.vault))
    now = from_iso(args.now) if args.now else now_utc()
    path = vault.conflicts_dir / f"{args.conflict_id}.md"
    if not path.exists():
        print(f"error: no conflict {args.conflict_id}", file=sys.stderr)
        sys.exit(1)
    data, body = parse_frontmatter(path.read_text(encoding="utf-8"))

    result = {"action": args.action}
    if args.action == "supersede":
        old = vault.find(data["old_id"])
        if old is None:
            print(f"error: no memory {data['old_id']}", file=sys.stderr)
            sys.exit(1)
        new_record_id = new_id(now)
        new_record = Record(
            id=new_record_id,
            content=data["new_content"],
            subject=data.get("subject") or old.subject,
            body=data["new_content"],
            cls=old.cls,
            scope=old.scope,
            base_confidence=old.base_confidence,
            captured_at=to_iso(now),
            last_reinforced=to_iso(now),
            reinforce_count=0,
            last_retrieved=to_iso(now),
            status=STATUS_ACTIVE,
            supersedes=old.id,
            source=data.get("new_source"),
            path=vault.facts_dir / f"{new_record_id}.md",
        )
        old.status = STATUS_SUPERSEDED
        old.superseded_by = new_record_id
        vault.save(old)
        vault.save(new_record)
        result["new_id"] = new_record_id
    elif args.action == "coexist":
        new_record_id = new_id(now)
        new_record = Record(
            id=new_record_id,
            content=data["new_content"],
            subject=data.get("subject") or "misc",
            body=data["new_content"],
            cls=CLASS_DURABLE,
            scope=args.new_scope,
            base_confidence=0.8,
            captured_at=to_iso(now),
            last_reinforced=to_iso(now),
            reinforce_count=0,
            last_retrieved=to_iso(now),
            status=STATUS_ACTIVE,
            source=data.get("new_source"),
            path=vault.facts_dir / f"{new_record_id}.md",
        )
        vault.save(new_record)
        result["new_id"] = new_record_id
        if args.old_scope:
            old = vault.find(data["old_id"])
            if old:
                old.scope = args.old_scope
                vault.save(old)
    elif args.action == "discard-new":
        pass
    elif args.action == "discard-old":
        old = vault.find(data["old_id"])
        if old:
            old.status = STATUS_ARCHIVED
            old_path = old.path
            new_path = vault.archive_dir / old_path.name
            old.path = new_path
            new_path.write_text(old.render(), encoding="utf-8")
            old_path.unlink()
            vault.upsert_index_entry(old)

    data["status"] = "resolved"
    data["resolved_action"] = args.action
    data["resolved_at"] = to_iso(now)
    resolved_path = vault.conflicts_resolved_dir / path.name
    vault.conflicts_resolved_dir.mkdir(parents=True, exist_ok=True)
    resolved_path.write_text(render_frontmatter(data, body), encoding="utf-8")
    path.unlink()

    print(json.dumps(result, indent=2))


def cmd_reindex(args):
    vault = Vault(Path(args.vault))
    vault.init()
    count = vault.reindex()
    print(f"Reindexed {count} records")


def cmd_health(args):
    vault = Vault(Path(args.vault))
    now = from_iso(args.now) if args.now else now_utc()
    records = vault.all_records(include_archived=True)
    by_status = {}
    nearing_decay = []
    never_reinforced_stale = []
    for record in records:
        by_status[record.status] = by_status.get(record.status, 0) + 1
        if record.status == STATUS_ACTIVE:
            confidence = compute_confidence(record, now)
            if args.threshold < confidence <= args.threshold + 0.10:
                nearing_decay.append({"id": record.id, "confidence": round(confidence, 4)})
            if record.reinforce_count == 0 and days_between(from_iso(record.captured_at) or now, now) > 90:
                never_reinforced_stale.append(record.id)

    pending_conflicts = len(list(vault.conflicts_dir.glob("*.md")))

    index = vault.read_index()
    indexed_ids = set(index.get("memories", {}).keys())
    disk_ids = {r.id for r in records}
    orphaned_index_entries = sorted(indexed_ids - disk_ids)
    unindexed_files = sorted(disk_ids - indexed_ids)

    report = {
        "generated_at": to_iso(now),
        "counts_by_status": by_status,
        "pending_conflicts": pending_conflicts,
        "nearing_decay": nearing_decay,
        "never_reinforced_over_90d": never_reinforced_stale,
        "orphaned_index_entries": orphaned_index_entries,
        "unindexed_files": unindexed_files,
        "index_in_sync": not orphaned_index_entries and not unindexed_files,
    }
    print(json.dumps(report, indent=2))


CLAUDE_MD_BULLET_RE = re.compile(r"^- (.+)$")
CLAUDE_MD_HEADING_RE = re.compile(r"^##\s+(.+)$")


def cmd_migrate_claude_md(args):
    vault = Vault(Path(args.vault))
    vault.init()
    claude_md = Path(args.claude_md) if args.claude_md else vault.root / "CLAUDE.md"
    if not claude_md.exists():
        print(f"error: {claude_md} not found", file=sys.stderr)
        sys.exit(1)

    now = from_iso(args.now) if args.now else now_utc()
    skip_headings = {h.strip().lower() for h in (args.skip_heading or [])}
    current_heading = None
    extracted = []

    for raw_line in claude_md.read_text(encoding="utf-8").split("\n"):
        heading_match = CLAUDE_MD_HEADING_RE.match(raw_line)
        if heading_match:
            current_heading = heading_match.group(1).strip()
            continue
        if current_heading is None or current_heading.lower() in skip_headings:
            continue
        bullet_match = CLAUDE_MD_BULLET_RE.match(raw_line.strip())
        if not bullet_match:
            continue
        content = bullet_match.group(1).strip()
        if not content or content.startswith("*("):
            continue
        record_id = new_id(now)
        record = Record(
            id=record_id,
            content=content,
            subject=slugify(current_heading),
            body=content,
            cls=CLASS_DURABLE,
            base_confidence=0.7,  # migrated facts start below fresh-capture default
            captured_at=to_iso(now),
            last_reinforced=to_iso(now),
            last_retrieved=to_iso(now),
            source=f"migrated from {claude_md.name} :: {current_heading}",
            path=vault.facts_dir / f"{record_id}.md",
        )
        vault.save(record)
        extracted.append(record_id)

    print(json.dumps({"extracted": len(extracted), "ids": extracted, "source_untouched": True}, indent=2))


GENERATED_START = "<!-- generated:start -->"
GENERATED_END = "<!-- generated:end -->"


def cmd_render_claude_md(args):
    """
    Regenerates ONLY the block between GENERATED_START/GENERATED_END. Every
    other line in CLAUDE.md -- including the pinned block, which is owned
    by /preserve and the user, not by this command -- is passed through
    byte-for-byte. This is the fix for the plan's open question 2: the
    generator must never be able to clobber hand-owned content.
    """
    vault = Vault(Path(args.vault))
    claude_md = Path(args.claude_md) if args.claude_md else vault.root / "CLAUDE.md"
    now = from_iso(args.now) if args.now else now_utc()

    records = [r for r in vault.active_records() if r.cls == CLASS_DURABLE]
    by_subject: dict[str, list[Record]] = {}
    for r in records:
        by_subject.setdefault(r.subject, []).append(r)

    lines = [
        f"_Regenerated {to_iso(now)} from {len(records)} active memories. "
        f"Do not hand-edit this block — edit the source records in Memory/Facts/ instead._",
        "",
    ]
    if not by_subject:
        lines.append("*(No durable memories captured yet.)*")
    for subject in sorted(by_subject):
        lines.append(f"### {subject}")
        subj_records = sorted(by_subject[subject], key=lambda r: compute_confidence(r, now), reverse=True)
        for r in subj_records:
            confidence = compute_confidence(r, now)
            lines.append(f"- {r.content} _(confidence {confidence:.2f})_")
        lines.append("")
    generated_body = "\n".join(lines).rstrip()

    existing = claude_md.read_text(encoding="utf-8") if claude_md.exists() else ""
    new_block = f"{GENERATED_START}\n{generated_body}\n{GENERATED_END}"

    if GENERATED_START in existing and GENERATED_END in existing:
        start = existing.index(GENERATED_START)
        end = existing.index(GENERATED_END) + len(GENERATED_END)
        updated = existing[:start] + new_block + existing[end:]
    elif existing:
        # No markers yet (older CLAUDE.md) -- append a Memory section rather
        # than guessing where to splice one in.
        updated = existing.rstrip("\n") + f"\n\n## Memory\n{new_block}\n"
    else:
        updated = f"# Project Memory\n\n## Memory\n{new_block}\n"

    claude_md.write_text(updated, encoding="utf-8")
    print(f"Rendered {claude_md} from {len(records)} active durable memories")


# ── CLI wiring ───────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="memory.py", description="Vault memory pipeline CLI")
    p.add_argument("--vault", required=True, help="Path to the Obsidian vault root")
    sub = p.add_subparsers(dest="command", required=True)

    def add(name, help_, fn):
        sp = sub.add_parser(name, help=help_)
        sp.add_argument("--now", help=argparse.SUPPRESS)  # testing/debug override
        sp.set_defaults(func=fn)
        return sp

    add("init", "Create Memory/ scaffolding", cmd_init)

    sp = add("new", "Write a new memory record", cmd_new)
    sp.add_argument("--content", required=True)
    sp.add_argument("--subject", required=True)
    sp.add_argument("--class", dest="klass", choices=[CLASS_DURABLE, CLASS_EXPIRING], default=CLASS_DURABLE)
    sp.add_argument("--scope", default=None)
    sp.add_argument("--confidence", type=float, default=0.8)
    sp.add_argument("--expires-at", default=None)
    sp.add_argument("--source", default=None)
    sp.add_argument("--quote", default=None)
    sp.add_argument("--session-source", default=None)

    sp = add("candidates", "List active memories sharing a subject (consolidation shortlist)", cmd_candidates)
    sp.add_argument("--subject", required=True)
    sp.add_argument("--scope", default=None)

    sp = add("search", "Lexical search over active memories", cmd_search)
    sp.add_argument("--query", required=True)
    sp.add_argument("--limit", type=int, default=10)

    sp = add("retrieve", "Score and return the most relevant active memories", cmd_retrieve)
    sp.add_argument("--query", required=True)
    sp.add_argument("--top-k", type=int, default=RETRIEVE_TOP_K)
    sp.add_argument("--floor", type=float, default=RETRIEVE_FLOOR)

    sp = add("reinforce", "Reset a memory's decay clock and record reinforcement", cmd_reinforce)
    sp.add_argument("--id", required=True)

    sp = add("supersede", "Replace an existing memory with a new one", cmd_supersede)
    sp.add_argument("--old-id", required=True)
    sp.add_argument("--content", required=True)
    sp.add_argument("--subject", default=None)
    sp.add_argument("--class", dest="klass", choices=[CLASS_DURABLE, CLASS_EXPIRING], default=None)
    sp.add_argument("--scope", default=None)
    sp.add_argument("--confidence", type=float, default=None)
    sp.add_argument("--expires-at", default=None)
    sp.add_argument("--source", default=None)

    sp = add("decay", "Recompute confidence and archive anything below threshold", cmd_decay)
    sp.add_argument("--threshold", type=float, default=ARCHIVE_THRESHOLD)
    sp.add_argument("--dry-run", action="store_true")

    sp = add("flag-conflict", "File an ambiguous contradiction for human review", cmd_flag_conflict)
    sp.add_argument("--old-id", required=True)
    sp.add_argument("--new-content", required=True)
    sp.add_argument("--subject", default=None)
    sp.add_argument("--source", default=None)
    sp.add_argument("--reason", default=None)

    add("list-conflicts", "List pending conflicts", cmd_list_conflicts)

    sp = add("resolve-conflict", "Resolve a pending conflict", cmd_resolve_conflict)
    sp.add_argument("--conflict-id", required=True)
    sp.add_argument("--action", required=True, choices=["supersede", "coexist", "discard-new", "discard-old"])
    sp.add_argument("--old-scope", default=None)
    sp.add_argument("--new-scope", default=None)

    add("reindex", "Rebuild index.json from the markdown files on disk", cmd_reindex)

    sp = add("health", "Report store health / drift", cmd_health)
    sp.add_argument("--threshold", type=float, default=ARCHIVE_THRESHOLD)

    sp = add("migrate-claude-md", "Extract bullet facts from an existing CLAUDE.md (non-destructive)", cmd_migrate_claude_md)
    sp.add_argument("--claude-md", default=None)
    sp.add_argument("--skip-heading", action="append", default=None)

    sp = add("render-claude-md", "Regenerate CLAUDE.md's memory section from active records", cmd_render_claude_md)
    sp.add_argument("--claude-md", default=None)

    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
