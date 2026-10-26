#!/usr/bin/env python3
"""
Unit tests for Denali Connect: TryHackMe to GitHub Activity Automator
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# Provide mock requests in sys.modules if not installed globally
if "requests" not in sys.modules:
    mock_requests = MagicMock()
    sys.modules["requests"] = mock_requests
    sys.modules["requests.adapters"] = MagicMock()
    sys.modules["urllib3"] = MagicMock()
    sys.modules["urllib3.util"] = MagicMock()
    sys.modules["urllib3.util.retry"] = MagicMock()

import main
main.HAS_REQUESTS = True
main.requests = sys.modules["requests"]

from main import (
    LOG_MARKER_END,
    LOG_MARKER_START,
    README_MARKER_END,
    README_MARKER_START,
    ContentFormatter,
    GitHubUpdater,
    THMBadge,
    THMRoom,
    THMStats,
    TryHackMeClient,
    get_mock_stats,
    run_sync,
)


class TestContentFormatter(unittest.TestCase):
    def setUp(self) -> None:
        self.stats = THMStats(
            username="test_hacker",
            name="Alice Sec",
            rank=1337,
            points=25000,
            streak=14,
            completed_rooms_count=42,
            badges_count=10,
            level=5,
            level_title="Specialist",
            badges=[
                THMBadge(name="Web Fundamentals", description="OWASP skills"),
                THMBadge(name="Burp Suite Basics", description="Interception proxy"),
            ],
            recent_rooms=[
                THMRoom(code="pickle_rick", title="Pickle Rick", difficulty="Easy", completed_at="2026-10-25"),
                THMRoom(code="blue", title="Blue", difficulty="Easy", completed_at="2026-10-24"),
            ],
            synced_at="2026-10-26 00:00:00 UTC",
        )

    def test_generate_readme_section_contains_markers_and_metrics(self) -> None:
        section = ContentFormatter.generate_readme_section(self.stats)
        self.assertIn(README_MARKER_START, section)
        self.assertIn(README_MARKER_END, section)
        self.assertIn("test_hacker", section)
        self.assertIn("#1,337", section)
        self.assertIn("25,000 pts", section)
        self.assertIn("14 days", section)
        self.assertIn("42 rooms", section)
        self.assertIn("Pickle Rick", section)
        self.assertIn("Web Fundamentals", section)

    def test_update_readme_content_replacement(self) -> None:
        initial = (
            "# My Repo\n\n"
            f"{README_MARKER_START}\nOld content to be replaced\n{README_MARKER_END}\n\n"
            "## Footer info\n"
        )
        new_section = f"{README_MARKER_START}\nBrand new stats\n{README_MARKER_END}"
        updated = ContentFormatter.update_readme_content(initial, new_section)

        self.assertIn("Brand new stats", updated)
        self.assertNotIn("Old content to be replaced", updated)
        self.assertIn("# My Repo", updated)
        self.assertIn("## Footer info", updated)

    def test_update_readme_content_append_when_missing(self) -> None:
        initial = "# Existing Readme Without Markers\n"
        new_section = f"{README_MARKER_START}\nAppended Stats\n{README_MARKER_END}"
        updated = ContentFormatter.update_readme_content(initial, new_section)

        self.assertTrue(updated.startswith("# Existing Readme Without Markers"))
        self.assertTrue(updated.endswith(f"{new_section}\n"))

    def test_generate_log_entry(self) -> None:
        entry = ContentFormatter.generate_log_entry(self.stats)
        self.assertIn("Snapshot", entry)
        self.assertIn("#1,337", entry)
        self.assertIn("42", entry)
        self.assertIn("Pickle Rick", entry)

    def test_update_log_content_prepending(self) -> None:
        initial = (
            "# Practice Log\n\n"
            f"{LOG_MARKER_START}\n"
            "*No activity has been logged yet. The automated tracking workflow will populate practice sessions here.*\n"
            f"{LOG_MARKER_END}\n"
        )
        new_entry = "### 📅 2026-10-26 Snapshot\n- **Rooms Completed:** 42"
        updated = ContentFormatter.update_log_content(initial, new_entry)

        self.assertIn("2026-10-26 Snapshot", updated)
        self.assertNotIn("*No activity has been logged yet.", updated)
        self.assertIn(LOG_MARKER_START, updated)
        self.assertIn(LOG_MARKER_END, updated)


class TestTryHackMeClientParsing(unittest.TestCase):
    def test_get_stats_multi_schema_parsing(self) -> None:
        mock_session = MagicMock()
        client = TryHackMeClient()
        client.session = mock_session

        # Mock public-profile response
        mock_profile_resp = MagicMock()
        mock_profile_resp.status_code = 200
        mock_profile_resp.json.return_value = {
            "status": "success",
            "data": {
                "username": "pentest_pro",
                "name": "Pro Hacker",
                "userRank": 500,
                "score": 32000,
                "streak": 21,
                "completedRoomsCount": 65,
                "badgesCount": 12,
                "currentLevel": {"level": 8, "title": "Master"},
                "userPublicId": "user_hash_xyz",
            },
        }

        # Mock completed rooms response
        mock_rooms_resp = MagicMock()
        mock_rooms_resp.status_code = 200
        mock_rooms_resp.json.return_value = {
            "data": [
                {"code": "metasploit", "title": "Metasploit Intro", "difficulty": "easy", "completed": "2026-10-20"},
                {"code": "nmap", "title": "Nmap Scanning", "difficulty": "medium", "completed": "2026-10-18"},
            ]
        }

        # Configure get responses based on URL
        def get_side_effect(url: str, *args, **kwargs):
            if "public-profile/completed-rooms" in url:
                return mock_rooms_resp
            return mock_profile_resp

        mock_session.get.side_effect = get_side_effect

        stats = client.get_stats("pentest_pro")

        self.assertEqual(stats.username, "pentest_pro")
        self.assertEqual(stats.rank, 500)
        self.assertEqual(stats.points, 32000)
        self.assertEqual(stats.streak, 21)
        self.assertEqual(stats.completed_rooms_count, 65)
        self.assertEqual(stats.badges_count, 12)
        self.assertEqual(stats.level, 8)
        self.assertEqual(stats.level_title, "Master")
        self.assertEqual(len(stats.recent_rooms), 2)
        self.assertEqual(stats.recent_rooms[0].title, "Metasploit Intro")


class TestGitHubUpdaterLocal(unittest.TestCase):
    def test_local_file_commit_and_idempotency(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "test_readme.md")
            initial_text = f"# Header\n{README_MARKER_START}\n{README_MARKER_END}\n"

            updater = GitHubUpdater()

            # 1. Commit initial text
            success = updater.commit_file(file_path, initial_text, "Initial commit")
            self.assertTrue(success)
            self.assertTrue(os.path.exists(file_path))

            # 2. Read back
            content, sha = updater.get_file_content(file_path)
            self.assertEqual(content, initial_text)
            self.assertIsNone(sha)


class TestFullSyncMock(unittest.TestCase):
    def test_run_sync_with_mock_and_local(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            readme_path = os.path.join(tmpdir, "README.md")
            log_path = os.path.join(tmpdir, "practice-log.md")

            with open(readme_path, "w") as f:
                f.write(f"# Project\n\n{README_MARKER_START}\nold\n{README_MARKER_END}\n")

            with open(log_path, "w") as f:
                f.write(f"# Log\n\n{LOG_MARKER_START}\ninitial\n{LOG_MARKER_END}\n")

            exit_code = run_sync(
                username="mock_user",
                target_readme=readme_path,
                target_log=log_path,
                use_mock=True,
                local_only=True,
            )
            self.assertEqual(exit_code, 0)

            with open(readme_path, "r") as f:
                updated_readme = f.read()
            self.assertIn("mock_user", updated_readme)
            self.assertIn("Kenobi", updated_readme)

            with open(log_path, "r") as f:
                updated_log = f.read()
            self.assertIn("Snapshot", updated_log)


if __name__ == "__main__":
    unittest.main()
