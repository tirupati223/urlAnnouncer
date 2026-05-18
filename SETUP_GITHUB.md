# How to Set Up GitHub for URL Announcer

This guide explains how to connect your URL Announcer project to GitHub
so that your changes automatically appear online.

---

## Step 1 — Create a GitHub Account (if you don't have one)

1. Go to **https://github.com/signup**
2. Enter your email: `ytirupatiygaikwad@gmail.com`
3. Choose a username — use: **tirupatiygaikwad**
4. Set a password
5. Verify your email address

---

## Step 2 — Create the Repository on GitHub

1. Go to **https://github.com/new**
2. Fill in:
   - **Repository name:** `urlAnnouncer`
   - **Description:** `NVDA addon to announce, copy, and share browser URLs - by Tirupati Janardhan Gaikwad, NVDA Certified 2025`
   - **Visibility:** ✅ Public
   - ❌ Do NOT tick "Add a README file"
   - ❌ Do NOT tick "Add .gitignore"
   - ❌ Do NOT tick "Choose a license"
3. Click **Create repository**

---

## Step 3 — Create a Personal Access Token (for password)

GitHub no longer accepts your account password for git push.
You need a **Personal Access Token (PAT)** instead.

1. Go to **https://github.com/settings/tokens/new**
2. Fill in:
   - **Note:** `urlAnnouncer push token`
   - **Expiration:** 1 year
   - **Scopes:** tick ✅ **repo** (the top-level checkbox)
3. Click **Generate token**
4. **COPY the token NOW** — you will not see it again!
   It looks like: `ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
5. Save it somewhere safe (like Notepad)

---

## Step 4 — Push Your Files to GitHub

Open **Command Prompt** (press Win+R, type `cmd`, press Enter) and run:

```
cd "C:\URL announcer"
git push -u origin main
```

When asked:
- **Username:** your GitHub username (e.g. `tirupatiygaikwad`)
- **Password:** paste your Personal Access Token from Step 3

Windows will save your credentials automatically — you will never be asked again.

---

## Step 5 — Create a Release (so users can download the addon)

1. Go to: **https://github.com/tirupatiygaikwad/urlAnnouncer/releases/new**
2. Fill in:
   - **Tag:** `v3.0.0`
   - **Release title:** `URL Announcer v3.0.0`
   - **Description:** `Complete professional NVDA addon with URL history, bookmarks, QR code, URL shortener, share menu, and more.`
3. Click **Attach binaries** and upload: `C:\Temp\urlAnnouncer-3.0.0.nvda-addon`
4. Click **Publish release**

---

## After Setup — Automatic Push

After Step 4, every time you make changes:

### Option A — Double-click the batch file
Double-click `push_to_github.bat` in the `C:\URL announcer` folder.
It will add, commit, and push everything automatically.

### Option B — Use git commit (auto-push hook is active)
Open Command Prompt in `C:\URL announcer` and run:
```
git add -A
git commit -m "Your message here"
```
The post-commit hook will automatically push to GitHub!

---

## Verify Your Repository

After pushing, visit:
**https://github.com/tirupatiygaikwad/urlAnnouncer**

You should see all your files online.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `Authentication failed` | Re-do Step 3 and create a new token |
| `Repository not found` | Make sure you created the repo in Step 2 |
| `not a git repository` | Run `cd "C:\URL announcer"` first |
| Push works but files missing | Run `git add -A` then `git commit -m "add files"` |

---

## Your GitHub Links (after setup)

- **Repository:** https://github.com/tirupatiygaikwad/urlAnnouncer
- **Releases:** https://github.com/tirupatiygaikwad/urlAnnouncer/releases
- **Help file:** https://github.com/tirupatiygaikwad/urlAnnouncer/blob/main/addon/doc/en/readme.html
- **Source code:** https://github.com/tirupatiygaikwad/urlAnnouncer/blob/main/addon/globalPlugins/urlAnnouncer/__init__.py
