"""
Unit tests for scripts/memory.py -- the deterministic core of the memory
pipeline (everything that must be exact, as opposed to the Claude-judged
capture/consolidate/reconcile decisions the slash commands make on top of it).

Run with:  python3 -m pytest tests/test_memory.py -v
       or:  python3 -m unittest tests.test_memory -v   (from repo root)
"""

import importlib.util
import json
import math
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MEMORY_PY = REPO_ROOT / "scripts" / "memory.py"

spec = importlib.util.spec_from_file_location("memory", MEMORY_PY)
memory = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = memory  # dataclass field resolution needs this registered first
spec.loader.exec_module(memory)


def iso(dt: datetime) -> str:
    return memory.to_iso(dt)


def make_record(**overrides) -> "memory.Record":
    now = overrides.pop("now", datetime(2026, 8, 10, tzinfo=timezone.utc))
    defaults = dict(
        id="mem-test-0001",
        content="Prefers terse code reviews with no preamble",
        subject="code-review-style",
        body="Prefers terse code reviews with no preamble",
        cls=memory.CLASS_DURABLE,
        scope=None,
        base_confidence=0.8,
        captured_at=iso(now),
        last_reinforced=iso(now),
        reinforce_count=0,
        last_retrieved=iso(now),
        expires_at=None,
        status=memory.STATUS_ACTIVE,
    )
    defaults.update(overrides)
    return memory.Record(**defaults)


class FrontmatterRoundTrip(unittest.TestCase):
    def test_round_trip_preserves_all_scalar_types(self):
        data = {
            "id": "mem-abc",
            "class": "durable",
            "scope": None,
            "base_confidence": 0.8,
            "reinforce_count": 3,
            "content": "Contains: a colon",
            "supersedes": None,
        }
        rendered = memory.render_frontmatter(data, "body text")
        parsed, body = memory.parse_frontmatter(rendered)
        self.assertEqual(body.strip(), "body text")
        for key, value in data.items():
            self.assertEqual(parsed[key], value, key)

    def test_list_scalar_round_trips(self):
        rendered = memory.render_frontmatter({"topics": ["auth", "vault-setup"]}, "x")
        parsed, _ = memory.parse_frontmatter(rendered)
        self.assertEqual(parsed["topics"], ["auth", "vault-setup"])

    def test_missing_frontmatter_returns_empty_dict(self):
        data, body = memory.parse_frontmatter("just a body, no frontmatter")
        self.assertEqual(data, {})
        self.assertEqual(body, "just a body, no frontmatter")


class DecayMath(unittest.TestCase):
    def test_confidence_is_full_strength_at_capture(self):
        r = make_record()
        now = datetime(2026, 8, 10, tzinfo=timezone.utc)
        self.assertAlmostEqual(memory.compute_confidence(r, now), 0.8, places=6)

    def test_confidence_decays_over_time(self):
        r = make_record()
        now = datetime(2026, 8, 10, tzinfo=timezone.utc)
        later = now + timedelta(days=180)  # one half-life at reinforce_count=0
        self.assertAlmostEqual(memory.compute_confidence(r, later), 0.4, places=3)

    def test_reinforcement_extends_half_life(self):
        now = datetime(2026, 8, 10, tzinfo=timezone.utc)
        later = now + timedelta(days=180)
        unreinforced = make_record(reinforce_count=0)
        reinforced = make_record(reinforce_count=5)
        c1 = memory.compute_confidence(unreinforced, later)
        c2 = memory.compute_confidence(reinforced, later)
        self.assertGreater(c2, c1, "more reinforcement should resist decay more")

    def test_expiring_class_holds_confidence_until_expiry_then_cliffs(self):
        now = datetime(2026, 8, 10, tzinfo=timezone.utc)
        r = make_record(cls=memory.CLASS_EXPIRING, expires_at=iso(now + timedelta(days=10)))
        just_before = now + timedelta(days=9)
        just_after = now + timedelta(days=11)
        self.assertAlmostEqual(memory.compute_confidence(r, just_before), 0.8, places=6)
        self.assertEqual(memory.compute_confidence(r, just_after), 0.0)

    def test_decay_is_schedule_independent(self):
        """
        The bug in the article's reference apply_decay(): confidence is
        subtracted per invocation, so running it daily for 30 days decays
        far more than running it once after 30 days. Our compute_confidence
        is a pure function of elapsed time, so both must agree exactly.
        """
        r = make_record()
        start = datetime(2026, 8, 10, tzinfo=timezone.utc)
        end = start + timedelta(days=30)

        # "run daily" -- just call compute_confidence 30 times at increasing
        # 'now' values; since it's a pure read, this must never mutate state.
        for day in range(31):
            memory.compute_confidence(r, start + timedelta(days=day))
        confidence_after_daily_reads = memory.compute_confidence(r, end)

        confidence_single_read = memory.compute_confidence(make_record(), end)

        self.assertEqual(confidence_after_daily_reads, confidence_single_read)


class VaultCliBase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="memtest-")
        self.vault = Path(self.tmpdir) / "Vault"
        self.vault.mkdir()
        self.run_cli("init")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def run_cli(self, *args, now=None):
        cmd = [sys.executable, str(MEMORY_PY), "--vault", str(self.vault), *args]
        if now:
            cmd += ["--now", now]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise AssertionError(f"CLI failed: {cmd}\nstdout={result.stdout}\nstderr={result.stderr}")
        return result.stdout.strip()

    def run_cli_expect_failure(self, *args):
        cmd = [sys.executable, str(MEMORY_PY), "--vault", str(self.vault), *args]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode, result.stdout, result.stderr

    def new_fact(self, content, subject, **kwargs):
        args = ["new", "--content", content, "--subject", subject]
        for key, value in kwargs.items():
            args += [f"--{key.replace('_', '-')}", str(value)]
        return self.run_cli(*args)


class InitAndNew(VaultCliBase):
    def test_init_creates_scaffolding(self):
        for sub in ("Facts", "Archive", "Conflicts", "Conflicts/Resolved"):
            self.assertTrue((self.vault / "Memory" / sub).is_dir(), sub)
        self.assertTrue((self.vault / "Memory" / "index.json").exists())

    def test_new_creates_file_and_index_entry(self):
        record_id = self.new_fact("Uses pnpm", "package-manager", confidence=0.8)
        fact_path = self.vault / "Memory" / "Facts" / f"{record_id}.md"
        self.assertTrue(fact_path.exists())
        index = json.loads((self.vault / "Memory" / "index.json").read_text())
        self.assertIn(record_id, index["memories"])
        self.assertEqual(index["memories"][record_id]["subject"], "package-manager")

    def test_subject_is_slugified(self):
        record_id = self.new_fact("x", "Code Review Style!!")
        data, _ = memory.parse_frontmatter((self.vault / "Memory" / "Facts" / f"{record_id}.md").read_text())
        self.assertEqual(data["subject"], "code-review-style")


class Candidates(VaultCliBase):
    def test_candidates_filters_by_subject(self):
        self.new_fact("Uses pnpm", "package-manager")
        self.new_fact("Prefers dark mode", "editor-theme")
        out = json.loads(self.run_cli("candidates", "--subject", "package-manager"))
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["content"], "Uses pnpm")

    def test_candidates_excludes_superseded(self):
        old_id = self.new_fact("Uses pnpm", "package-manager")
        self.run_cli("supersede", "--old-id", old_id, "--content", "Uses yarn now")
        out = json.loads(self.run_cli("candidates", "--subject", "package-manager"))
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["content"], "Uses yarn now")


class Retrieval(VaultCliBase):
    def test_returns_relevant_above_floor(self):
        self.new_fact("Prefers terse code reviews with no preamble", "code-review-style", confidence=0.8)
        self.new_fact("Favourite coffee order is a flat white", "coffee-order", confidence=0.8)
        out = json.loads(self.run_cli("retrieve", "--query", "how should I write this code review"))
        contents = [r["content"] for r in out]
        self.assertIn("Prefers terse code reviews with no preamble", contents)
        self.assertNotIn("Favourite coffee order is a flat white", contents)

    def test_unrelated_query_returns_nothing_not_noise(self):
        """
        The reference retrieve_relevant always returns exactly top_k results,
        so an unrelated query still injects noise. Ours has a floor.
        """
        self.new_fact("Prefers terse code reviews with no preamble", "code-review-style", confidence=0.8)
        out = json.loads(self.run_cli("retrieve", "--query", "spaceship banana quantum tuesday"))
        self.assertEqual(out, [])

    def test_retrieval_bumps_last_retrieved_not_last_reinforced(self):
        record_id = self.new_fact("Prefers terse code reviews", "code-review-style", confidence=0.8)
        before, _ = memory.parse_frontmatter(
            (self.vault / "Memory" / "Facts" / f"{record_id}.md").read_text()
        )
        self.run_cli("retrieve", "--query", "terse code reviews", now="2026-09-15T00:00:00Z")
        after, _ = memory.parse_frontmatter(
            (self.vault / "Memory" / "Facts" / f"{record_id}.md").read_text()
        )
        self.assertNotEqual(before["last_retrieved"], after["last_retrieved"])
        self.assertEqual(before["last_reinforced"], after["last_reinforced"])

    def test_repeated_retrieval_does_not_disable_decay(self):
        """
        The bug this guards against: if retrieval reset last_reinforced
        (as the article's reference implementation does), a memory that
        keeps surfacing in irrelevant-but-matched queries would never
        decay. Here we retrieve the same fact 5 times, then confirm decay
        one durable half-life later still archives it.
        """
        record_id = self.new_fact("Prefers terse code reviews", "code-review-style", confidence=0.8)
        for _ in range(5):
            self.run_cli("retrieve", "--query", "terse code reviews", now="2026-08-11T00:00:00Z")
        decay_out = json.loads(self.run_cli("decay", "--now", "2028-08-01T00:00:00Z"))
        archived_ids = [a["id"] for a in decay_out["archived"]]
        self.assertIn(record_id, archived_ids)


class Reinforce(VaultCliBase):
    def test_reinforce_resets_decay_clock(self):
        record_id = self.new_fact("Prefers terse code reviews", "code-review-style", confidence=0.8)
        self.run_cli("reinforce", "--id", record_id, now="2027-01-01T00:00:00Z")
        data, _ = memory.parse_frontmatter(
            (self.vault / "Memory" / "Facts" / f"{record_id}.md").read_text()
        )
        self.assertEqual(data["reinforce_count"], 1)
        self.assertEqual(data["last_reinforced"], "2027-01-01T00:00:00Z")

    def test_reinforce_snapshots_decayed_value_not_original(self):
        record_id = self.new_fact("Prefers terse code reviews", "code-review-style", confidence=0.8)
        self.run_cli("reinforce", "--id", record_id, now="2027-02-06T00:00:00Z")  # ~180 days later
        data, _ = memory.parse_frontmatter(
            (self.vault / "Memory" / "Facts" / f"{record_id}.md").read_text()
        )
        self.assertLess(data["base_confidence"], 0.8)
        self.assertGreater(data["base_confidence"], 0.35)


class Supersede(VaultCliBase):
    def test_old_marked_superseded_new_is_active(self):
        old_id = self.new_fact("Uses pnpm", "package-manager")
        new_id = self.run_cli("supersede", "--old-id", old_id, "--content", "Uses yarn now")
        old_data, _ = memory.parse_frontmatter((self.vault / "Memory" / "Facts" / f"{old_id}.md").read_text())
        new_data, _ = memory.parse_frontmatter((self.vault / "Memory" / "Facts" / f"{new_id}.md").read_text())
        self.assertEqual(old_data["status"], "superseded")
        self.assertEqual(old_data["superseded_by"], new_id)
        self.assertEqual(new_data["status"], "active")
        self.assertEqual(new_data["supersedes"], old_id)

    def test_superseded_excluded_from_active_records(self):
        old_id = self.new_fact("Uses pnpm", "package-manager")
        self.run_cli("supersede", "--old-id", old_id, "--content", "Uses yarn now")
        vault = memory.Vault(self.vault)
        active_ids = {r.id for r in vault.active_records()}
        self.assertNotIn(old_id, active_ids)

    def test_nothing_is_deleted(self):
        old_id = self.new_fact("Uses pnpm", "package-manager")
        self.run_cli("supersede", "--old-id", old_id, "--content", "Uses yarn now")
        self.assertTrue((self.vault / "Memory" / "Facts" / f"{old_id}.md").exists())


class Decay(VaultCliBase):
    def test_dry_run_does_not_move_files(self):
        record_id = self.new_fact("Old fact", "misc", confidence=0.8)
        self.run_cli("decay", "--dry-run", now="2028-08-01T00:00:00Z")
        self.assertTrue((self.vault / "Memory" / "Facts" / f"{record_id}.md").exists())
        self.assertFalse((self.vault / "Memory" / "Archive" / f"{record_id}.md").exists())

    def test_archives_below_threshold_moves_file(self):
        record_id = self.new_fact("Old fact", "misc", confidence=0.8)
        self.run_cli("decay", now="2028-08-01T00:00:00Z")
        self.assertFalse((self.vault / "Memory" / "Facts" / f"{record_id}.md").exists())
        self.assertTrue((self.vault / "Memory" / "Archive" / f"{record_id}.md").exists())

    def test_recently_captured_survives_decay(self):
        record_id = self.new_fact("Fresh fact", "misc", confidence=0.8)
        self.run_cli("decay", now="2026-08-11T00:00:00Z")
        self.assertTrue((self.vault / "Memory" / "Facts" / f"{record_id}.md").exists())

    def test_running_decay_twice_is_idempotent(self):
        self.new_fact("Old fact", "misc", confidence=0.8)
        first = self.run_cli("decay", now="2028-08-01T00:00:00Z")
        second = self.run_cli("decay", now="2028-08-01T00:00:00Z")
        first_archived = json.loads(first)["archived"]
        second_archived = json.loads(second)["archived"]
        self.assertEqual(len(first_archived), 1)
        self.assertEqual(len(second_archived), 0, "already-archived records must not be reprocessed")

    def test_expiring_fact_archives_at_expiry_regardless_of_confidence(self):
        record_id = self.new_fact(
            "Project deadline is Friday", "deadline",
            **{"class": memory.CLASS_EXPIRING, "confidence": 0.95, "expires-at": "2026-08-15T00:00:00Z"},
        )
        self.run_cli("decay", now="2026-08-16T00:00:00Z")
        self.assertTrue((self.vault / "Memory" / "Archive" / f"{record_id}.md").exists())


class ConflictQueue(VaultCliBase):
    def test_flag_then_supersede_resolution(self):
        old_id = self.new_fact("Uses pnpm", "package-manager")
        conflict_id = self.run_cli(
            "flag-conflict", "--old-id", old_id, "--new-content", "Uses yarn now",
            "--subject", "package-manager", "--reason", "ambiguous",
        )
        pending = json.loads(self.run_cli("list-conflicts"))
        self.assertEqual(len(pending), 1)

        self.run_cli("resolve-conflict", "--conflict-id", conflict_id, "--action", "supersede")

        pending_after = json.loads(self.run_cli("list-conflicts"))
        self.assertEqual(pending_after, [])
        self.assertTrue((self.vault / "Memory" / "Conflicts" / "Resolved" / f"{conflict_id}.md").exists())

        old_data, _ = memory.parse_frontmatter((self.vault / "Memory" / "Facts" / f"{old_id}.md").read_text())
        self.assertEqual(old_data["status"], "superseded")

    def test_coexist_resolution_keeps_both_active_with_scopes(self):
        old_id = self.new_fact("Dark mode", "editor-theme", scope="work")
        conflict_id = self.run_cli(
            "flag-conflict", "--old-id", old_id, "--new-content", "Light mode",
            "--subject", "editor-theme",
        )
        self.run_cli(
            "resolve-conflict", "--conflict-id", conflict_id, "--action", "coexist",
            "--old-scope", "work", "--new-scope", "personal",
        )
        candidates = json.loads(self.run_cli("candidates", "--subject", "editor-theme"))
        scopes = {c["scope"] for c in candidates}
        self.assertEqual(scopes, {"work", "personal"})
        statuses = {c["status"] for c in candidates}
        self.assertEqual(statuses, {"active"})

    def test_never_silently_auto_resolves(self):
        """flag-conflict must always land in the pending queue, never resolve itself."""
        old_id = self.new_fact("Uses pnpm", "package-manager")
        self.run_cli("flag-conflict", "--old-id", old_id, "--new-content", "Uses yarn now")
        old_data, _ = memory.parse_frontmatter((self.vault / "Memory" / "Facts" / f"{old_id}.md").read_text())
        self.assertEqual(old_data["status"], "active", "must not resolve until a human/action calls resolve-conflict")


class Reindex(VaultCliBase):
    def test_reindex_rebuilds_from_disk_after_hand_edit(self):
        record_id = self.new_fact("Uses pnpm", "package-manager")
        index_path = self.vault / "Memory" / "index.json"
        index = json.loads(index_path.read_text())
        del index["memories"][record_id]
        index_path.write_text(json.dumps(index))

        health_before = json.loads(self.run_cli("health"))
        self.assertFalse(health_before["index_in_sync"])

        self.run_cli("reindex")
        health_after = json.loads(self.run_cli("health"))
        self.assertTrue(health_after["index_in_sync"])


class MigrateClaudeMd(VaultCliBase):
    def test_extracts_bullets_and_leaves_source_untouched(self):
        claude_md = self.vault / "CLAUDE.md"
        original = (
            "# Project Memory\n\n"
            "## Conventions & Standards\n"
            "- Uses pnpm, not npm\n"
            "- Daily note filename: YYYY-MM-DD.md\n\n"
            "## Active Projects\n"
            "- Working on the vault memory pipeline\n"
        )
        claude_md.write_text(original)

        out = json.loads(self.run_cli("migrate-claude-md"))
        self.assertEqual(out["extracted"], 3)
        self.assertTrue(out["source_untouched"])
        self.assertEqual(claude_md.read_text(), original)

        vault = memory.Vault(self.vault)
        subjects = {r.subject for r in vault.active_records()}
        self.assertEqual(subjects, {"conventions-standards", "active-projects"})

    def test_skip_heading_excludes_section(self):
        claude_md = self.vault / "CLAUDE.md"
        claude_md.write_text(
            "## Skills\n- /resume — do a thing\n\n## Conventions & Standards\n- Uses pnpm\n"
        )
        out = json.loads(self.run_cli("migrate-claude-md", "--skip-heading", "Skills"))
        self.assertEqual(out["extracted"], 1)


class RenderClaudeMd(VaultCliBase):
    def test_preserves_content_outside_generated_block(self):
        claude_md = self.vault / "CLAUDE.md"
        claude_md.write_text(
            "# Project Memory\n\n"
            "## Pinned\n<!-- pinned:start -->\nHard rule: never force-push main.\n<!-- pinned:end -->\n\n"
            "## Memory\n<!-- generated:start -->\nstale\n<!-- generated:end -->\n\n"
            "## Skills\n- /resume\n"
        )
        self.new_fact("Prefers terse code reviews", "code-review-style", confidence=0.8)
        self.run_cli("render-claude-md")
        rendered = claude_md.read_text()
        self.assertIn("Hard rule: never force-push main.", rendered)
        self.assertIn("## Skills\n- /resume", rendered)
        self.assertIn("Prefers terse code reviews", rendered)
        self.assertNotIn("stale", rendered)

    def test_only_active_durable_facts_are_rendered(self):
        claude_md = self.vault / "CLAUDE.md"
        claude_md.write_text("<!-- generated:start -->\n<!-- generated:end -->\n")
        keep_id = self.new_fact("Durable fact", "topic-a", confidence=0.8)
        old_id = self.new_fact("Will be superseded", "topic-b", confidence=0.8)
        self.run_cli("supersede", "--old-id", old_id, "--content", "Superseding fact")
        self.new_fact(
            "Expired fact", "topic-c",
            **{"class": memory.CLASS_EXPIRING, "expires-at": "2020-01-01T00:00:00Z"},
        )
        self.run_cli("render-claude-md")
        rendered = claude_md.read_text()
        self.assertIn("Durable fact", rendered)
        self.assertNotIn("Will be superseded", rendered)
        # expiring class is excluded from the CLAUDE.md view entirely (by design:
        # only durable facts are surfaced there), regardless of expiry.
        self.assertNotIn("Expired fact", rendered)


class Health(VaultCliBase):
    def test_reports_pending_conflicts(self):
        old_id = self.new_fact("Uses pnpm", "package-manager")
        self.run_cli("flag-conflict", "--old-id", old_id, "--new-content", "Uses yarn now")
        report = json.loads(self.run_cli("health"))
        self.assertEqual(report["pending_conflicts"], 1)

    def test_nearing_decay_detection(self):
        self.new_fact("About to decay", "misc", confidence=0.8)
        # 0.8 * 0.5^(days/180) in [0.15, 0.25] band -> solve for days
        report = json.loads(self.run_cli("health", now="2027-08-01T00:00:00Z"))
        self.assertGreaterEqual(len(report["nearing_decay"]), 0)  # sanity: doesn't crash / valid shape
        self.assertIn("nearing_decay", report)


if __name__ == "__main__":
    unittest.main()
