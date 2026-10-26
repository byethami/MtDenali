# 🏔️ Denali Connect: TryHackMe to GitHub Activity Automator

[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg?logo=python&logoColor=white)](https://python.org)
[![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-Automation-2088FF.svg?logo=githubactions&logoColor=white)](https://github.com/features/actions)
[![TryHackMe](https://img.shields.io/badge/Platform-TryHackMe-red.svg?logo=tryhackme&logoColor=white)](https://tryhackme.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Maintenance](https://img.shields.io/badge/Maintained%3F-yes-brightgreen.svg)]()

> **Denali Connect** is a production-grade automation system that bridges your [TryHackMe](https://tryhackme.com) cybersecurity journey with your GitHub profile and repositories. It automatically fetches your latest rank, streak, total score, badges, and completed walkthroughs/CTF rooms, keeping your GitHub profile and activity logs dynamically synchronized.

---

## 📈 TryHackMe Live Statistics

<!-- THM-STATS:START -->
<!-- Do not edit this section directly; automatically synced by Denali Connect -->
### 🛡️ Live TryHackMe Profile Statistics

<div align="center">
  <a href="https://tryhackme.com" target="_blank">
    <img src="https://tryhackme-badges.s3.amazonaws.com/example.png" alt="TryHackMe Profile Badge" width="400" />
  </a>
</div>

<div align="center">
  <img src="https://img.shields.io/badge/Rank-Syncing...-00b4d8?style=for-the-badge&logo=tryhackme&logoColor=white" alt="THM Rank" />
  <img src="https://img.shields.io/badge/Rooms%20Completed-0-e63946?style=for-the-badge&logo=target&logoColor=white" alt="Rooms Completed" />
  <img src="https://img.shields.io/badge/Streak-0%20Days-ffb703?style=for-the-badge&logo=fire&logoColor=white" alt="Current Streak" />
  <img src="https://img.shields.io/badge/Points-0-2a9d8f?style=for-the-badge&logo=counter-strike&logoColor=white" alt="Total Points" />
</div>

#### 📊 Performance Overview

| Platform Metric | Value |
| :--- | :--- |
| 👤 **Hacker Profile** | [**`Pending Sync`**](https://tryhackme.com) |
| 🏆 **Global Rank** | **Unranked** |
| 🔥 **Current Streak** | **0 days** |
| 📦 **Rooms Completed** | **0 rooms** |
| 🎖️ **Badges Earned** | **0 badges** |
| ⭐ **Total Score** | **0 pts** |
| ⚡ **Platform Rank / Tier** | **Active Learner** |
| 🕒 **Last Synchronized** | `Awaiting initial workflow execution` |

*Automated with [Denali Connect](https://github.com) • Updates daily at 00:00 UTC*
<!-- THM-STATS:END -->

---

## 🚀 Key Features

- 🔄 **Fully Automated Synchronization:** Runs on a scheduled GitHub Actions cron (e.g. daily at 00:00 UTC) or triggers on-demand via `workflow_dispatch`.
- 🔐 **Flexible Authentication:**
  - **Public Profiles:** Operates with just your TryHackMe username (no login required for public metrics).
  - **Session Support:** Optionally handles `connect.sid` session cookies to retrieve private activity and comprehensive completed room lists.
- 🎯 **Rich Metrics Extraction:**
  - Global user rank & rank percentiles.
  - Overall points and current consecutive day streak.
  - Total room completions and recent lab breakdown (title, difficulty, completion date).
  - Earned achievement badges and platform tier.
- 🎨 **Visual Presentation:** Dynamically renders official TryHackMe badge cards, Shields.io badges, and Markdown tables.
- 📜 **Historical Practice Log:** Appends timestamped audit entries to [`practice-log.md`](practice-log.md) to track cybersecurity milestones over time.
- ⚡ **Idempotent Updates:** Compares existing repository content and skips unnecessary commits if stats have not changed.
- 🧪 **Offline & Mock Support:** Built-in `--mock` and `--dry-run` modes for testing and validation without network access or active credentials.

---

## 🏗️ Architecture & Modules

```
                    ┌───────────────────────────┐
                    │       TryHackMe API       │
                    │   (/api/v2/public-profile)│
                    │   (/api/user/completed)   │
                    └─────────────┬─────────────┘
                                  │  JSON Response
                                  ▼
                    ┌───────────────────────────┐
                    │   TryHackMeClient         │
                    │  (Session, Retry, Parse)  │
                    └─────────────┬─────────────┘
                                  │  THMStats Dataclass
                                  ▼
                    ┌───────────────────────────┐
                    │   ContentFormatter        │
                    │ (Badges, Tables, Regex)   │
                    └─────────────┬─────────────┘
                                  │
         ┌────────────────────────┴────────────────────────┐
         ▼                                                 ▼
┌───────────────────────────┐                     ┌───────────────────────────┐
│     README.md Updates     │                     │    practice-log.md Logs   │
│  <!-- THM-STATS:START --> │                     │  <!-- THM-LOG:START -->   │
└─────────────┬─────────────┘                     └─────────────┬─────────────┘
              │                                                 │
              └────────────────────────┬────────────────────────┘
                                       │
                                       ▼
                    ┌───────────────────────────┐
                    │      GitHubUpdater        │
                    │   (PyGithub / Git CLI)    │
                    └─────────────┬─────────────┘
                                  │  Push Commit [skip ci]
                                  ▼
                    ┌───────────────────────────┐
                    │   GitHub Repository Main  │
                    └───────────────────────────┘
```

1. **TryHackMe Data Retrieval Module (`TryHackMeClient`)**:
   Interfaces with TryHackMe's public endpoints (`/api/v2/public-profile`, `/api/users/rank/`, `/api/v2/public-profile/completed-rooms`) and session-authenticated endpoints (`/api/user/completed-rooms`). Parses and normalizes diverse JSON schemas with robust multi-field fallbacks.

2. **Content Formatter Module (`ContentFormatter`)**:
   Transforms raw numeric and categorical data into visual badges, markdown tables, recent room matrices, and practice logs. Preserves surrounding text in the README and log files by isolating updates between specific HTML comment tokens.

3. **GitHub Integration Module (`GitHubUpdater`)**:
   Uses `PyGithub` to inspect existing file states, compare changes, and commit updates directly via the GitHub REST API or local disk operations with custom commit messages.

4. **Automation & CI/CD (`.github/workflows/update_stats.yml`)**:
   Scheduled cron runner ensuring your public profile stays fresh without manual intervention.

---

## 📁 File Structure

```
.
├── .github/
│   └── workflows/
│       ├── update_stats.yml    # Primary GitHub Actions scheduled workflow
│       └── thm-tracker.yml     # Alternative workflow trigger
├── main.py                     # Core Python automation script & CLI
├── requirements.txt            # Python dependencies (requests, PyGithub)
├── README.md                   # Project documentation & live stats container
├── practice-log.md             # Chronological cybersecurity training log
├── .env.example                # Template for local environment configuration
└── .gitignore                  # Git ignore patterns
```

---

## ⚙️ Setup & Configuration Guide

### 1. Fork or Clone the Repository
Clone this repository to your local machine or fork it directly on GitHub:
```bash
git clone https://github.com/your-username/denali-connect.git
cd denali-connect
```

### 2. Obtain Your TryHackMe Credentials
- **Username:** Your public TryHackMe username (e.g. `https://tryhackme.com/p/<USERNAME>`).
- *(Optional)* **Session Cookie (`connect.sid`):**
  1. Open your browser and navigate to [tryhackme.com](https://tryhackme.com).
  2. Open Developer Tools (`F12` or `Ctrl+Shift+I` / `Cmd+Option+I`).
  3. Navigate to **Application** (Chrome/Brave) or **Storage** (Firefox) -> **Cookies** -> `https://tryhackme.com`.
  4. Locate the cookie named `connect.sid` and copy its value.

### 3. Generate a GitHub Personal Access Token (PAT)
If using GitHub Actions on your own repository, the built-in `${{ secrets.GITHUB_TOKEN }}` works automatically!
If writing to another repository or running from an external environment:
1. Navigate to GitHub **Settings** -> **Developer Settings** -> **Personal Access Tokens** -> **Tokens (classic)**.
2. Generate a token with the `repo` scope.
3. Save the token securely.

### 4. Configure GitHub Actions Secrets
In your repository on GitHub:
1. Go to **Settings** -> **Secrets and variables** -> **Actions**.
2. Click **New repository secret** and add:

| Secret Name | Required | Description |
| :--- | :---: | :--- |
| `THM_USERNAME` | **Yes** | Your TryHackMe username (e.g., `CyberHacker42`) |
| `THM_SESSION_COOKIE` | *Optional* | Your `connect.sid` cookie value for private rooms |
| `GH_TOKEN` | *Optional* | Custom GitHub PAT (defaults to `${{ secrets.GITHUB_TOKEN }}`) |

> [!IMPORTANT]
> Ensure GitHub Actions has write permissions:  
> Go to **Settings** -> **Actions** -> **General** -> **Workflow permissions** -> Select **Read and write permissions** -> Click **Save**.

### 5. Trigger the Workflow
- **Automatic:** The workflow will execute automatically every day at 00:00 UTC.
- **Manual:** Navigate to the **Actions** tab -> Select **Denali Connect - TryHackMe Activity Sync** -> Click **Run workflow**.

---

## 💻 Local Usage & CLI Options

You can also run Denali Connect directly on your local workstation.

### Installation
```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration
Copy the template and edit your `.env`:
```bash
cp .env.example .env
```

### Running Commands
```bash
# 1. Preview changes without committing (Dry Run)
python3 main.py --username your_thm_username --dry-run

# 2. Test formatting and workflow offline with Mock Data
python3 main.py --mock --dry-run

# 3. Update local files on disk only
python3 main.py --username your_thm_username --local

# 4. Update repository via GitHub API
python3 main.py --username your_thm_username --token ghp_yourToken --repo yourname/yourrepo
```

### Command Line Arguments Reference
| Argument | Flag | Default | Description |
| :--- | :---: | :---: | :--- |
| `--username` | `-u` | `$THM_USERNAME` | TryHackMe username |
| `--cookie` | `-c` | `$THM_SESSION_COOKIE` | TryHackMe `connect.sid` cookie |
| `--token` | `-t` | `$GITHUB_TOKEN` | GitHub Personal Access Token |
| `--repo` | `-r` | `$GITHUB_REPOSITORY` | Target repository (`owner/repo`) |
| `--readme` | | `README.md` | Path to target README file |
| `--log` | | `practice-log.md` | Path to practice log file |
| `--branch` | `-b` | `main` | Target Git branch |
| `--dry-run` | | `False` | Display preview without writing/committing |
| `--mock` | | `False` | Use built-in mock data for testing |
| `--local` | | `False` | Modify local disk files without calling GitHub API |

---

## 🔒 Security Best Practices

1. **Keep Secrets Protected:** Never hardcode your TryHackMe `connect.sid` cookie or GitHub PAT into repository files. Always use GitHub Actions Secrets or a local `.env` (which is included in `.gitignore`).
2. **Token Scoping:** Grant only the minimum permissions necessary (`contents: write` for updating repository files).
3. **Session Expiration:** TryHackMe `connect.sid` cookies expire periodically when logging out. If detailed private room fetching ceases, update the `THM_SESSION_COOKIE` secret with a fresh session cookie.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
