#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
URL Announcer — One-time GitHub Setup Script
Run this once to create the GitHub repo and push all files.
After this, changes push automatically via the git post-commit hook.
"""

import os
import sys
import subprocess
import urllib.request
import urllib.error
import json
import webbrowser
import time

REPO_NAME  = "urlAnnouncer"
REPO_DESC  = "NVDA addon to announce, copy and share browser URLs. By Tirupati Gaikwad."
PROJECT    = r"C:\URL announcer"

LINE = "=" * 55

def banner(text):
    print()
    print(LINE)
    print("  " + text)
    print(LINE)

def run(cmd, cwd=PROJECT):
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.returncode != 0 and result.stderr.strip():
        print("STDERR:", result.stderr.strip())
    return result.returncode == 0

def github_api(method, endpoint, token, data=None):
    url = "https://api.github.com" + endpoint
    body = json.dumps(data).encode() if data else None
    req  = urllib.request.Request(
        url, data=body, method=method,
        headers={
            "Authorization": "token " + token,
            "Accept":        "application/vnd.github.v3+json",
            "Content-Type":  "application/json",
            "User-Agent":    "URLAnnouncer-Setup/1.0",
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())
    except Exception as e:
        return 0, {"message": str(e)}

def main():
    banner("URL Announcer — GitHub Setup")
    print()
    print("This script will:")
    print("  1. Create the GitHub repository (if it doesn't exist)")
    print("  2. Push all addon files to GitHub")
    print("  3. Set up automatic future pushes")
    print()

    # ── Get GitHub username ──────────────────────────────────────────────
    print("Enter your GitHub username.")
    print("(If you don't have a GitHub account, go to https://github.com/signup)")
    print()
    username = input("GitHub username: ").strip()
    if not username:
        print("Username cannot be empty. Exiting.")
        sys.exit(1)

    # ── Get GitHub token ─────────────────────────────────────────────────
    print()
    print("You need a Personal Access Token (PAT) from GitHub.")
    print("Opening the token creation page in your browser...")
    time.sleep(1)
    token_url = (
        "https://github.com/settings/tokens/new"
        "?description=urlAnnouncer&scopes=repo"
    )
    webbrowser.open(token_url)
    print()
    print("In the browser page that just opened:")
    print("  1. Make sure you are signed in to GitHub")
    print("  2. Scroll down and tick the checkbox next to 'repo'")
    print("  3. Scroll to bottom, click 'Generate token'")
    print("  4. COPY the token that appears (starts with ghp_)")
    print("  5. Come back here and paste it below")
    print()
    token = input("Paste your GitHub token: ").strip()
    if not token:
        print("Token cannot be empty. Exiting.")
        sys.exit(1)

    # ── Verify token ─────────────────────────────────────────────────────
    banner("Step 1 of 3 — Verifying GitHub credentials")
    status, data = github_api("GET", "/user", token)
    if status != 200:
        print(f"ERROR: Token verification failed ({status}): {data.get('message','')}")
        print("Please check your token and try again.")
        sys.exit(1)
    login = data.get("login", username)
    print(f"Logged in as: {login}")

    # ── Create repository ────────────────────────────────────────────────
    banner("Step 2 of 3 — Creating GitHub repository")
    status, data = github_api("POST", "/user/repos", token, {
        "name":        REPO_NAME,
        "description": REPO_DESC,
        "private":     False,
        "has_issues":  True,
        "has_wiki":    False,
        "auto_init":   False,
    })
    if status == 201:
        print(f"Repository created: https://github.com/{login}/{REPO_NAME}")
    elif status == 422:
        print(f"Repository already exists — continuing with push.")
    else:
        print(f"WARNING: Repo creation returned {status}: {data.get('message','')}")

    # ── Push files ───────────────────────────────────────────────────────
    banner("Step 3 of 3 — Pushing files to GitHub")
    os.chdir(PROJECT)

    # Set remote URL with token embedded (for this push)
    token_url = f"https://{login}:{token}@github.com/{login}/{REPO_NAME}.git"
    run(["git", "remote", "set-url", "origin", token_url])

    print("Pushing 2 commits and all 14 files...")
    ok = run(["git", "push", "-u", "origin", "main"])

    # Reset remote URL to plain HTTPS (token saved by credential manager)
    plain_url = f"https://github.com/{login}/{REPO_NAME}.git"
    run(["git", "remote", "set-url", "origin", plain_url])

    # Save credentials via Windows Credential Manager
    run(["git", "config", "credential.helper", "manager"])

    if ok:
        banner("SUCCESS — All files are on GitHub!")
        print()
        print(f"  Repository : https://github.com/{login}/{REPO_NAME}")
        print(f"  Source code: https://github.com/{login}/{REPO_NAME}/tree/main/addon")
        print(f"  Help file  : https://github.com/{login}/{REPO_NAME}/blob/main/addon/doc/en/readme.html")
        print()
        print("Opening your repository in the browser...")
        webbrowser.open(f"https://github.com/{login}/{REPO_NAME}")
        print()
        print("AUTOMATIC FUTURE PUSHES:")
        print("  Every time you do 'git commit', files push to GitHub automatically.")
        print("  Or double-click 'push_to_github.bat' to push manually.")
    else:
        print()
        print("Push failed. Common causes:")
        print("  - Token does not have 'repo' scope — generate a new one")
        print("  - Repository was not created — check https://github.com/" + login)
        print()
        print("Try running this script again.")
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled.")
