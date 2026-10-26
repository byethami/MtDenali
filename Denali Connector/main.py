#!/usr/bin/env python3
"""
Denali Connect: TryHackMe to GitHub Activity Automator
======================================================
Fetches a user's progress, completed rooms, badges, and statistics from
TryHackMe and automatically updates a GitHub repository (README and practice log)
to showcase cyber defense and penetration testing practice history.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import logging
import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    HAS_REQUESTS = True
except ImportError:
    requests = None  # type: ignore
    HTTPAdapter = None  # type: ignore
    Retry = None  # type: ignore
    HAS_REQUESTS = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("denali-connect")

# Constant Markers for Dynamic Content Injection
README_MARKER_START = "<!-- THM-STATS:START -->"
README_MARKER_END = "<!-- THM-STATS:END -->"

LOG_MARKER_START = "<!-- THM-LOG:START -->"
LOG_MARKER_END = "<!-- THM-LOG:END -->"


# ==============================================================================
# Data Models
# ==============================================================================

@dataclass
class THMBadge:
    name: str
    title: str = ""
    description: str = ""
    earned_at: Optional[str] = None
    image_url: Optional[str] = None


@dataclass
class THMRoom:
    code: str
    title: str
    difficulty: str = "Unknown"
    completed_at: Optional[str] = None
    room_type: str = "Walkthrough/Challenge"


@dataclass
class THMStats:
    username: str
    name: str = ""
    rank: Optional[int] = None
    points: int = 0
    streak: int = 0
    completed_rooms_count: int = 0
    badges_count: int = 0
    level: Optional[int] = None
    level_title: Optional[str] = None
    avatar_url: Optional[str] = None
    user_id: Optional[str] = None
    profile_url: str = ""
    badges: List[THMBadge] = field(default_factory=list)
    recent_rooms: List[THMRoom] = field(default_factory=list)
    synced_at: str = ""

    def __post_init__(self) -> None:
        if not self.profile_url:
            self.profile_url = f"https://tryhackme.com/p/{self.username}"
        if not self.synced_at:
            self.synced_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


# ==============================================================================
# TryHackMe Data Retrieval Module
# ==============================================================================

class TryHackMeClient:
    """Handles communication and data extraction from TryHackMe endpoints."""

    BASE_URL = "https://tryhackme.com"

    def __init__(self, session_cookie: Optional[str] = None, timeout: int = 15) -> None:
        if not HAS_REQUESTS:
            raise ImportError(
                "The 'requests' library is required for live TryHackMe queries. "
                "Install dependencies via: pip install -r requirements.txt"
            )
        self.session_cookie = session_cookie.strip() if session_cookie else None
        self.timeout = timeout
        self.session = self._init_session()

    def _init_session(self) -> requests.Session:
        session = requests.Session()
        session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://tryhackme.com/",
            "Origin": "https://tryhackme.com",
        })

        # Inject session cookie if provided (connect.sid)
        if self.session_cookie:
            session.cookies.set(
                "connect.sid",
                self.session_cookie,
                domain=".tryhackme.com",
                path="/",
            )
            session.cookies.set(
                "connect.sid",
                self.session_cookie,
                domain="tryhackme.com",
                path="/",
            )
            logger.info("Configured TryHackMe session cookie (connect.sid) for authenticated requests.")

        # Resilient retry strategy for transient network hiccups or rate limits
        retries = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retries)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def fetch_public_profile(self, username: str) -> Dict[str, Any]:
        """Fetch raw public profile information."""
        url = f"{self.BASE_URL}/api/v2/public-profile"
        params = {"username": username}
        try:
            logger.info(f"Querying TryHackMe public profile for '{username}'...")
            resp = self.session.get(url, params=params, timeout=self.timeout)
            if resp.status_code == 404:
                raise ValueError(f"TryHackMe user '{username}' was not found (HTTP 404).")
            resp.raise_for_status()
            data = resp.json()
            return data
        except requests.RequestException as e:
            logger.warning(f"Failed to fetch public profile endpoint: {e}")
            return {}

    def fetch_user_rank(self, username: str) -> Optional[int]:
        """Fallback to retrieve user rank if missing from main endpoint."""
        url = f"{self.BASE_URL}/api/users/rank/{username}"
        try:
            resp = self.session.get(url, timeout=self.timeout)
            if resp.status_code == 200:
                payload = resp.json()
                if isinstance(payload, dict):
                    rank_val = payload.get("userOrder") or payload.get("rank")
                    if rank_val:
                        return int(rank_val)
                elif isinstance(payload, (int, str)) and str(payload).isdigit():
                    return int(payload)
        except Exception as e:
            logger.debug(f"Rank fallback query skipped: {e}")
        return None

    def fetch_completed_rooms(self, user_id_or_name: str, limit: int = 10) -> List[THMRoom]:
        """
        Fetch completed rooms list using public-profile or authenticated endpoint.
        """
        rooms: List[THMRoom] = []

        # 1. Try public-profile/completed-rooms endpoint
        url = f"{self.BASE_URL}/api/v2/public-profile/completed-rooms"
        params = {"user": user_id_or_name, "limit": limit, "page": 1}
        try:
            resp = self.session.get(url, params=params, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                raw_rooms = []
                if isinstance(data, dict):
                    raw_rooms = data.get("data") or data.get("rooms") or data.get("docs") or []
                elif isinstance(data, list):
                    raw_rooms = data

                for item in raw_rooms:
                    if isinstance(item, dict):
                        code = item.get("code") or item.get("roomCode") or item.get("roomId") or item.get("title", "")
                        title = item.get("title") or item.get("name") or code
                        difficulty = item.get("difficulty") or item.get("level") or "Standard"
                        completed_at = item.get("completed") or item.get("completedAt") or item.get("date")
                        room_type = item.get("type") or item.get("category") or "Room"
                        rooms.append(THMRoom(
                            code=str(code),
                            title=str(title),
                            difficulty=str(difficulty).capitalize(),
                            completed_at=str(completed_at) if completed_at else None,
                            room_type=str(room_type).capitalize(),
                        ))
                if rooms:
                    return rooms[:limit]
        except Exception as e:
            logger.debug(f"Public completed rooms endpoint skipped: {e}")

        # 2. Try authenticated endpoint if session cookie is available
        if self.session_cookie:
            auth_url = f"{self.BASE_URL}/api/user/completed-rooms"
            try:
                resp = self.session.get(auth_url, timeout=self.timeout)
                if resp.status_code == 200:
                    data = resp.json()
                    raw_rooms = data if isinstance(data, list) else data.get("rooms", [])
                    for item in raw_rooms:
                        if isinstance(item, dict):
                            title = item.get("title") or item.get("name") or item.get("code", "Untitled")
                            code = item.get("code") or title
                            difficulty = item.get("difficulty", "Standard")
                            completed_at = item.get("completed") or item.get("date")
                            rooms.append(THMRoom(
                                code=str(code),
                                title=str(title),
                                difficulty=str(difficulty).capitalize(),
                                completed_at=str(completed_at) if completed_at else None,
                            ))
                    if rooms:
                        return rooms[:limit]
            except Exception as e:
                logger.debug(f"Authenticated completed rooms endpoint skipped: {e}")

        return rooms

    def fetch_user_badges(self, username: str) -> List[THMBadge]:
        """Fetch detailed badges list."""
        badges: List[THMBadge] = []
        url = f"{self.BASE_URL}/api/v2/badges/public-profile"
        try:
            resp = self.session.get(url, params={"username": username}, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                raw_badges = []
                if isinstance(data, dict):
                    raw_badges = data.get("data") or data.get("badges") or []
                elif isinstance(data, list):
                    raw_badges = data
                for b in raw_badges:
                    if isinstance(b, dict):
                        name = b.get("name") or b.get("title") or "Achievement"
                        desc = b.get("description") or b.get("desc") or ""
                        earned = b.get("earnedAt") or b.get("earned") or b.get("date")
                        img = b.get("image") or b.get("badgeUrl")
                        badges.append(THMBadge(
                            name=str(name),
                            title=str(name),
                            description=str(desc),
                            earned_at=str(earned) if earned else None,
                            image_url=str(img) if img else None,
                        ))
        except Exception as e:
            logger.debug(f"Badges fetch skipped: {e}")
        return badges

    def get_stats(self, username: str) -> THMStats:
        """Fetch all stats and return a normalized THMStats object."""
        raw_profile = self.fetch_public_profile(username)

        # Handle nested data structure: { "status": "success", "data": { ... } }
        data = raw_profile.get("data", raw_profile) if isinstance(raw_profile, dict) else {}

        # 1. User Name & Avatar
        display_name = data.get("name") or data.get("username") or username
        avatar_url = data.get("avatar") or data.get("gravatar") or data.get("avatarUrl")
        user_id = data.get("userPublicId") or data.get("userId") or data.get("_id") or data.get("id")

        # 2. Rank
        rank_val = data.get("rank") or data.get("userRank") or data.get("globalRank")
        rank: Optional[int] = None
        if rank_val is not None and str(rank_val).isdigit():
            rank = int(rank_val)
        else:
            rank = self.fetch_user_rank(username)

        # 3. Points / Score
        points_val = data.get("points") or data.get("score") or data.get("totalPoints") or 0
        points = int(points_val) if str(points_val).isdigit() else 0

        # 4. Streak
        streak_val = data.get("streak") or data.get("currentStreak") or 0
        streak = int(streak_val) if str(streak_val).isdigit() else 0

        # 5. Completed Rooms Count
        rooms_count_val = (
            data.get("completedRoomsCount")
            or data.get("completedRooms")
            or data.get("roomsCompleted")
            or 0
        )
        completed_rooms_count = int(rooms_count_val) if str(rooms_count_val).isdigit() else 0

        # 6. Badges Count & Badges List
        badges_count_val = (
            data.get("badgesCount")
            or data.get("totalBadges")
            or (len(data.get("badges", [])) if isinstance(data.get("badges"), list) else 0)
        )
        badges_count = int(badges_count_val) if str(badges_count_val).isdigit() else 0

        badges: List[THMBadge] = []
        if isinstance(data.get("badges"), list):
            for b in data["badges"]:
                if isinstance(b, dict):
                    badges.append(THMBadge(
                        name=b.get("name") or b.get("title", "Badge"),
                        title=b.get("title", ""),
                        description=b.get("description", ""),
                        earned_at=b.get("earned") or b.get("earnedAt"),
                        image_url=b.get("image") or b.get("badge"),
                    ))
        if not badges:
            badges = self.fetch_user_badges(username)
        if badges and badges_count == 0:
            badges_count = len(badges)

        # 7. Level
        level: Optional[int] = None
        level_title: Optional[str] = None
        lvl_data = data.get("currentLevel") or data.get("level")
        if isinstance(lvl_data, dict):
            lvl_val = lvl_data.get("level")
            if lvl_val and str(lvl_val).isdigit():
                level = int(lvl_val)
            level_title = lvl_data.get("title")
        elif isinstance(lvl_data, (int, str)) and str(lvl_data).isdigit():
            level = int(lvl_data)

        # 8. Completed Rooms list
        target_id_for_rooms = user_id or username
        recent_rooms = self.fetch_completed_rooms(str(target_id_for_rooms), limit=10)

        # If completed_rooms_count was 0 but rooms list exists, infer count
        if completed_rooms_count == 0 and recent_rooms:
            completed_rooms_count = len(recent_rooms)

        stats = THMStats(
            username=username,
            name=display_name,
            rank=rank,
            points=points,
            streak=streak,
            completed_rooms_count=completed_rooms_count,
            badges_count=badges_count,
            level=level,
            level_title=level_title,
            avatar_url=avatar_url,
            user_id=str(user_id) if user_id else None,
            badges=badges,
            recent_rooms=recent_rooms,
        )

        logger.info(
            f"Successfully retrieved stats for {username}: "
            f"Rank={stats.rank or 'N/A'}, Points={stats.points}, "
            f"Streak={stats.streak}d, Rooms={stats.completed_rooms_count}, "
            f"Badges={stats.badges_count}"
        )
        return stats


# ==============================================================================
# Content Formatter Module
# ==============================================================================

class ContentFormatter:
    """Formats retrieved TryHackMe metrics into Markdown widgets and logs."""

    @staticmethod
    def generate_readme_section(stats: THMStats) -> str:
        """Generates dynamic Markdown snippet for insertion into README.md."""
        rank_display = f"#{stats.rank:,}" if stats.rank else "Unranked"
        level_display = f"Level {stats.level}" if stats.level else "Active Learner"
        if stats.level_title:
            level_display += f" ({stats.level_title})"

        # Shields.io badges
        rank_badge_text = f"Rank-%23{stats.rank if stats.rank else 'N/A'}"
        rank_badge_url = f"https://img.shields.io/badge/{rank_badge_text}-00b4d8?style=for-the-badge&logo=tryhackme&logoColor=white"
        rooms_badge_url = f"https://img.shields.io/badge/Rooms%20Completed-{stats.completed_rooms_count}-e63946?style=for-the-badge&logo=target&logoColor=white"
        streak_badge_url = f"https://img.shields.io/badge/Streak-{stats.streak}%20Days-ffb703?style=for-the-badge&logo=fire&logoColor=white"
        points_badge_url = f"https://img.shields.io/badge/Points-{stats.points:,}-2a9d8f?style=for-the-badge&logo=counter-strike&logoColor=white"

        # TryHackMe official badge card
        thm_badge_img = f"https://tryhackme-badges.s3.amazonaws.com/{stats.username}.png"

        lines: List[str] = [
            README_MARKER_START,
            "<!-- Do not edit this section directly; automatically synced by Denali Connect -->",
            "### 🛡️ Live TryHackMe Profile Statistics",
            "",
            f'<div align="center">',
            f'  <a href="{stats.profile_url}" target="_blank">',
            f'    <img src="{thm_badge_img}" alt="TryHackMe Profile Badge" width="400" />',
            f"  </a>",
            f"</div>",
            "",
            f'<div align="center">',
            f'  <img src="{rank_badge_url}" alt="THM Rank" />',
            f'  <img src="{rooms_badge_url}" alt="Rooms Completed" />',
            f'  <img src="{streak_badge_url}" alt="Current Streak" />',
            f'  <img src="{points_badge_url}" alt="Total Points" />',
            f"</div>",
            "",
            "#### 📊 Performance Overview",
            "",
            "| Platform Metric | Value |",
            "| :--- | :--- |",
            f"| 👤 **Hacker Profile** | [**`{stats.username}`**]({stats.profile_url}) |",
            f"| 🏆 **Global Rank** | **{rank_display}** |",
            f"| 🔥 **Current Streak** | **{stats.streak} day{'s' if stats.streak != 1 else ''}** |",
            f"| 📦 **Rooms Completed** | **{stats.completed_rooms_count} rooms** |",
            f"| 🎖️ **Badges Earned** | **{stats.badges_count} badges** |",
            f"| ⭐ **Total Score** | **{stats.points:,} pts** |",
            f"| ⚡ **Platform Rank / Tier** | **{level_display}** |",
            f"| 🕒 **Last Synchronized** | `{stats.synced_at}` |",
            "",
        ]

        # Recent completed rooms table
        if stats.recent_rooms:
            lines.extend([
                "#### 🚀 Recent Completed Rooms",
                "",
                "| Room Name | Difficulty | Category | Date Completed |",
                "| :--- | :---: | :---: | :---: |",
            ])
            for r in stats.recent_rooms[:5]:
                room_link = f"[{r.title}](https://tryhackme.com/room/{r.code})"
                date_str = r.completed_at[:10] if (r.completed_at and len(r.completed_at) >= 10) else "Recently"
                diff_badge = f"`{r.difficulty}`"
                lines.append(f"| {room_link} | {diff_badge} | {r.room_type} | {date_str} |")
            lines.append("")

        # Badges highlight
        if stats.badges:
            lines.extend([
                "#### 🏅 Featured Achievements & Badges",
                "",
            ])
            for b in stats.badges[:6]:
                badge_title = b.title or b.name
                desc = f" - *{b.description}*" if b.description else ""
                lines.append(f"- 🎖️ **{badge_title}**{desc}")
            lines.append("")

        lines.extend([
            f"*Automated with [Denali Connect](https://github.com) • Updates daily at 00:00 UTC*",
            README_MARKER_END,
        ])

        return "\n".join(lines)

    @staticmethod
    def update_readme_content(original_content: str, new_section: str) -> str:
        """Substitutes or appends the statistics section into the README text."""
        pattern = re.compile(
            rf"{re.escape(README_MARKER_START)}.*?{re.escape(README_MARKER_END)}",
            re.DOTALL,
        )

        if pattern.search(original_content):
            return pattern.sub(new_section, original_content)

        # Fallback: append cleanly to existing content
        logger.info("README dynamic markers not found. Appending section to file end.")
        cleaned = original_content.rstrip()
        return f"{cleaned}\n\n{new_section}\n" if cleaned else f"{new_section}\n"

    @staticmethod
    def generate_log_entry(stats: THMStats) -> str:
        """Creates a timestamped entry for practice-log.md."""
        rank_str = f"#{stats.rank:,}" if stats.rank else "N/A"
        entry_lines = [
            f"### 📅 {stats.synced_at[:10]} Snapshot",
            f"- **Rank:** {rank_str}",
            f"- **Rooms Completed:** {stats.completed_rooms_count}",
            f"- **Points:** {stats.points:,}",
            f"- **Streak:** {stats.streak} days",
            f"- **Badges:** {stats.badges_count}",
        ]

        if stats.recent_rooms:
            entry_lines.append("- **Latest Activity:**")
            for room in stats.recent_rooms[:3]:
                entry_lines.append(f"  - Completed `{room.title}` ({room.difficulty})")

        entry_lines.append("")
        return "\n".join(entry_lines)

    @staticmethod
    def update_log_content(original_content: str, new_entry: str) -> str:
        """Prepends the new log entry right after the start marker in practice-log.md."""
        pattern = re.compile(
            rf"({re.escape(LOG_MARKER_START)})(.*?)({re.escape(LOG_MARKER_END)})",
            re.DOTALL,
        )

        match = pattern.search(original_content)
        if match:
            existing_body = match.group(2).strip()
            # If initial placeholder text exists, replace it; otherwise prepend entry
            if "*No activity has been logged yet." in existing_body:
                updated_body = f"\n\n{new_entry.strip()}\n\n"
            else:
                updated_body = f"\n\n{new_entry.strip()}\n\n{existing_body}\n\n"
            return pattern.sub(rf"\1{updated_body}\3", original_content)

        # Fallback: append
        return f"{original_content.rstrip()}\n\n{new_entry}\n"


# ==============================================================================
# GitHub Integration Module
# ==============================================================================

class GitHubUpdater:
    """Manages reading and pushing file changes to GitHub via PyGithub or local filesystem."""

    def __init__(
        self,
        token: Optional[str] = None,
        repository: Optional[str] = None,
        branch: str = "main",
    ) -> None:
        self.token = token.strip() if token else None
        self.repository_name = repository.strip() if repository else None
        self.branch = branch

        self._github_client: Optional[Any] = None
        self._repo_obj: Optional[Any] = None

        if self.token and self.repository_name:
            try:
                from github import Github, Auth
                auth = Auth.Token(self.token)
                self._github_client = Github(auth=auth)
                self._repo_obj = self._github_client.get_repo(self.repository_name)
                logger.info(f"Initialized PyGithub client for repository '{self.repository_name}'.")
            except Exception as e:
                logger.warning(f"Could not connect via PyGithub: {e}. Will fall back to local file updates.")

    @property
    def has_remote_access(self) -> bool:
        return self._repo_obj is not None

    def get_file_content(self, file_path: str) -> Tuple[str, Optional[str]]:
        """
        Reads content of a file.
        Returns: (file_content_str, file_sha_if_remote)
        """
        # Try remote PyGithub first if available
        if self._repo_obj:
            try:
                content_file = self._repo_obj.get_contents(file_path, ref=self.branch)
                decoded = content_file.decoded_content.decode("utf-8")
                return decoded, content_file.sha
            except Exception as e:
                logger.debug(f"Remote file '{file_path}' not retrieved via API ({e}). Reading locally.")

        # Local filesystem fallback
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read(), None

        return "", None

    def commit_file(
        self,
        file_path: str,
        new_content: str,
        commit_message: str,
        existing_sha: Optional[str] = None,
    ) -> bool:
        """
        Commits file to GitHub or writes to local filesystem.
        Returns True if changes were written, False if identical or failed.
        """
        # Always write to local disk first if directory exists or file exists
        try:
            os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            logger.info(f"Updated local file '{file_path}'.")
        except Exception as e:
            logger.warning(f"Local file write warning for '{file_path}': {e}")

        # If remote access is configured, commit via PyGithub
        if self._repo_obj:
            try:
                if existing_sha:
                    self._repo_obj.update_file(
                        path=file_path,
                        message=commit_message,
                        content=new_content,
                        sha=existing_sha,
                        branch=self.branch,
                    )
                    logger.info(f"Committed updates to '{file_path}' on branch '{self.branch}'.")
                else:
                    self._repo_obj.create_file(
                        path=file_path,
                        message=commit_message,
                        content=new_content,
                        branch=self.branch,
                    )
                    logger.info(f"Created file '{file_path}' on branch '{self.branch}'.")
                return True
            except Exception as e:
                logger.error(f"Failed to commit '{file_path}' via GitHub API: {e}")
                return False

        return True


# ==============================================================================
# Mock Data Provider (For testing & offline validation)
# ==============================================================================

def get_mock_stats(username: str) -> THMStats:
    """Returns sample TryHackMe data for offline testing and verification."""
    return THMStats(
        username=username,
        name="Security Explorer",
        rank=3842,
        points=14250,
        streak=19,
        completed_rooms_count=87,
        badges_count=16,
        level=7,
        level_title="Hacker",
        avatar_url="https://tryhackme-images.s3.amazonaws.com/user-avatars/mock.png",
        user_id="mock_user_hash_123",
        badges=[
            THMBadge(name="Linux PrivEsc", description="Mastered privilege escalation on Linux systems"),
            THMBadge(name="Network Fundamentals", description="Understands networking protocols and subnets"),
            THMBadge(name="Web Fundamentals", description="Completed OWASP top 10 challenge set"),
            THMBadge(name="7 Day Streak", description="Maintained continuous learning streak for 7 days"),
        ],
        recent_rooms=[
            THMRoom(code="kenobi", title="Kenobi", difficulty="Easy", completed_at="2026-10-24", room_type="Walkthrough"),
            THMRoom(code="steelmountain", title="Steel Mountain", difficulty="Easy", completed_at="2026-10-22", room_type="Challenge"),
            THMRoom(code="blue", title="Blue (EternalBlue)", difficulty="Easy", completed_at="2026-10-20", room_type="Walkthrough"),
            THMRoom(code="mrrobot", title="Mr Robot CTF", difficulty="Medium", completed_at="2026-10-18", room_type="CTF"),
        ],
    )


# ==============================================================================
# Main Orchestrator
# ==============================================================================

def run_sync(
    username: str,
    session_cookie: Optional[str] = None,
    github_token: Optional[str] = None,
    github_repo: Optional[str] = None,
    target_readme: str = "README.md",
    target_log: str = "practice-log.md",
    branch: str = "main",
    dry_run: bool = False,
    use_mock: bool = False,
    local_only: bool = False,
) -> int:
    """Coordinates fetching data and updating GitHub target files."""
    logger.info("=" * 60)
    logger.info("Starting Denali Connect TryHackMe to GitHub Activity Sync")
    logger.info("=" * 60)

    # 1. Fetch Stats
    if use_mock:
        logger.info(f"Using mock data for TryHackMe user: '{username}'")
        stats = get_mock_stats(username)
    else:
        client = TryHackMeClient(session_cookie=session_cookie)
        try:
            stats = client.get_stats(username)
        except Exception as e:
            logger.error(f"Error fetching data from TryHackMe: {e}")
            return 1

    # 2. Format Content
    new_readme_section = ContentFormatter.generate_readme_section(stats)
    new_log_entry = ContentFormatter.generate_log_entry(stats)

    if dry_run:
        logger.info("[DRY RUN MODE] Showing generated README section preview:")
        print("\n" + "-" * 40 + " README PREVIEW " + "-" * 40)
        print(new_readme_section)
        print("-" * 40 + " LOG ENTRY PREVIEW " + "-" * 40)
        print(new_log_entry)
        print("-" * 90)
        logger.info("[DRY RUN MODE] No changes were committed.")
        return 0

    # 3. Initialize GitHub Updater
    updater = GitHubUpdater(
        token=None if local_only else github_token,
        repository=None if local_only else github_repo,
        branch=branch,
    )

    # 4. Update README.md
    readme_content, readme_sha = updater.get_file_content(target_readme)
    updated_readme = ContentFormatter.update_readme_content(readme_content, new_readme_section)

    if updated_readme == readme_content:
        logger.info(f"No changes detected in '{target_readme}'. Stats are already up to date.")
    else:
        commit_msg = f"Auto-update TryHackMe stats: {stats.completed_rooms_count} rooms completed [skip ci]"
        updater.commit_file(target_readme, updated_readme, commit_msg, readme_sha)

    # 5. Update practice-log.md
    log_content, log_sha = updater.get_file_content(target_log)
    if log_content or os.path.exists(target_log) or updater.has_remote_access:
        updated_log = ContentFormatter.update_log_content(log_content, new_log_entry)
        if updated_log == log_content:
            logger.info(f"No changes detected in '{target_log}'.")
        else:
            log_commit_msg = f"Log TryHackMe activity for {stats.synced_at[:10]} [skip ci]"
            updater.commit_file(target_log, updated_log, log_commit_msg, log_sha)

    logger.info("Denali Connect sync completed successfully!")
    return 0


# ==============================================================================
# CLI Entry Point
# ==============================================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Denali Connect: Automated TryHackMe to GitHub Activity Sync",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--username",
        "-u",
        default=os.getenv("THM_USERNAME", ""),
        help="TryHackMe username (or set THM_USERNAME env var)",
    )
    parser.add_argument(
        "--cookie",
        "-c",
        default=os.getenv("THM_SESSION_COOKIE", ""),
        help="TryHackMe connect.sid cookie for private rooms (or set THM_SESSION_COOKIE env var)",
    )
    parser.add_argument(
        "--token",
        "-t",
        default=os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN", ""),
        help="GitHub Personal Access Token (or set GITHUB_TOKEN / GH_TOKEN env var)",
    )
    parser.add_argument(
        "--repo",
        "-r",
        default=os.getenv("GITHUB_REPOSITORY", ""),
        help="GitHub repository in format 'owner/repo' (or set GITHUB_REPOSITORY env var)",
    )
    parser.add_argument(
        "--readme",
        default=os.getenv("TARGET_README_PATH", "README.md"),
        help="Path to the target README file to update",
    )
    parser.add_argument(
        "--log",
        default=os.getenv("TARGET_LOG_PATH", "practice-log.md"),
        help="Path to practice log markdown file",
    )
    parser.add_argument(
        "--branch",
        "-b",
        default=os.getenv("TARGET_BRANCH", "main"),
        help="Target Git branch to commit updates to",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch data and preview output without writing or committing files",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use realistic mock data to test formatting and updates offline",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        default=os.getenv("LOCAL_MODE", "false").lower() == "true",
        help="Update files on local disk only without calling PyGithub API",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Determine username
    username = args.username.strip()
    if not username and not args.mock:
        logger.error(
            "TryHackMe username is required! Provide it via --username argument "
            "or set the THM_USERNAME environment variable."
        )
        sys.exit(1)

    target_user = username or "Hacker"

    exit_code = run_sync(
        username=target_user,
        session_cookie=args.cookie,
        github_token=args.token,
        github_repo=args.repo,
        target_readme=args.readme,
        target_log=args.log,
        branch=args.branch,
        dry_run=args.dry_run,
        use_mock=args.mock,
        local_only=args.local,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
