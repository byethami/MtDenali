TL;DR: Denali Connect (The "For Dummies" Guide)

> What does this project do in plain English?  
> Every night at midnight, this script visits TryHackMe, grabs your latest rank, streak, total points, and completed rooms, and pastes them neatly onto your GitHub profile. You don't have to touch anything ever again.

---

3-Minute Setup (Step-by-Step)

You only need two things:
1. Your TryHackMe username.
2. A GitHub repository** where this code lives.

---

Step 1: Push This Code to GitHub

If you haven't put this project on your GitHub account yet, run these commands in your terminal:

```bash
1. Create a new empty repository on github.com (e.g., named "tryhackme-tracker")
2. Link your local project to it and push:
git remote add origin https://github.com/YOUR_GITHUB_USERNAME/YOUR_REPOSITORY_NAME.git
git branch -M main
git push -u origin main
```

---

Step 2: Tell GitHub Your TryHackMe Username

1. On GitHub, open your repository.
2. Click Settings** (the gear icon on the top right).
3. In the left sidebar, click **Secrets and variables** ➔ click **Actions**.
4. Click the green button: **New repository secret**.
5. Fill in:
Name: `THM_USERNAME`
Secret: Type your exact TryHackMe username (e.g., `HackerOne` or `JohnDoeSec`).
6. Click Add secret.

(That's literally the only required setting!)

---

 Step 3: Enable Write Permissions (One-Time Setting)

GitHub needs permission to save updates to your repository:

1. In your repository on GitHub, go to **Settings** ➔ **Actions** ➔ **General**.
2. Scroll down to **Workflow permissions**.
3. Select **Read and write permissions**.
4. Click **Save**.

---
Step 4: Test It Right Now!

You don't need to wait until midnight to see it work:

1. Click the Actionstab at the top of your GitHub repository.
2. In the left sidebar, click Denali Connect - TryHackMe Activity Sync.
3. Click the Run workflow dropdown on the right ➔ click the green **Run workflow** button.
4. Wait ~30 seconds.
5. Go back to your repository's main page ([`README.md`](README.md)) — your real stats, rank, and badges are now live!

---

Optional: How to Show Private Rooms & Completed History

By default, TryHackMe only shows what is visible on your public profile. If you want the script to fetch **detailed completed rooms** and **private lab history**, give it your session cookie:

1. Log in to [tryhackme.com](https://tryhackme.com) in your web browser.
2. Press `F12` (or Right-Click anywhere ➔ click **Inspect**).
3. Go to the **Application** tab (Chrome/Edge/Brave) or **Storage** tab (Firefox).
4. On the left, expand **Cookies** and click `https://tryhackme.com`.
5. Look for the cookie named `connect.sid`.
6. Copy its long value.
7. Go back to GitHub ➔ Settings ➔ Secrets and variables ➔ Actions ➔ New repository secret:
   Name: `THM_SESSION_COOKIE`
   Secret: Paste the `connect.sid` value you copied.
8. Click Add secret.

---

How to Run It on Your Laptop (Without GitHub Actions)

Want to run the script manually on your computer right now?

```bash
1. Install requirements
pip install -r requirements.txt

2. Preview your stats in the terminal (does NOT modify files)
python3 main.py --username YOUR_TRYHACKME_USERNAME --dry-run

3. Update README.md and practice-log.md directly on your computer
python3 main.py --username YOUR_TRYHACKME_USERNAME --local
```

---
How It Works Behind the Scenes (ELI5 Diagram)

```text
[ TryHackMe Platform ]
        │
        │ 1. Script asks: "What is this user's rank, streak, and rooms?"
        ▼
[ Denali Connect (main.py) ]
        │
        │ 2. Takes the data and makes pretty badges and tables
        ▼
[ Your GitHub Repository ]
        │
        ├─► Updates README.md (between <!-- THM-STATS:START --> and <!-- THM-STATS:END -->)
        │
        └─► Updates practice-log.md (adds a timestamped history entry)
```

1. GitHub Actions wakes up** every night at 00:00 UTC.
2. It fetches your public profile from TryHackMe using `requests`.
3. It generates custom SVG badges (rank, points, streak, rooms) and formatted tables.
4. It finds the special markers `<!-- THM-STATS:START -->` and `<!-- THM-STATS:END -->` in your `README.md` and swaps the old stats with the new ones.
5. It adds a snapshot into `practice-log.md`.
6. It commits the changes back to your repository with the message `Auto-update TryHackMe stats [skip ci]`.

---

Common Questions & Troubleshooting

Q: Will this overwrite my own README text?
**No!** The script only touches the area between `<!-- THM-STATS:START -->` and `<!-- THM-STATS:END -->`. Everything else you write in `README.md` stays completely untouched.

Q: What if my TryHackMe username changes?
Just update the `THM_USERNAME` secret in your GitHub repository settings.

Q: Why did the GitHub Action fail with "Permission denied"?
You forgot Step 3! Go to Settings ➔ Actions ➔ **General** ➔ **Workflow permissions** ➔ select Read and write permissions ➔ click Save.

Q: How often does it run?
Automatically once a day at 00:00 UTC. You can also trigger it anytime manually by clicking Run workflow in the GitHub Actions tab.
