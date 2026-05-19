# Changelog — URL Announcer

All notable changes to URL Announcer are documented here.

## Version 3.0.0 — 2026-05-19

### Added
- Command layer (NVDA+Shift+U) with 16 sub-commands: A C S X W R M B L T E O P D Q H
- URL history browser (R) — remembers last 5 / 10 / 20 / 50 URLs per session
- Bookmark manager — save (M) and browse (B) named bookmarks
- URL shortener (L) — shortens via TinyURL, copies result to clipboard
- Share menu (W) — WhatsApp, Facebook, Telegram, Gmail, Twitter, LinkedIn
- YouTube short link (S) — converts youtube.com/watch URLs to youtu.be format
- QR code generator (Q) — opens QR code in browser
- Email client (E) — opens mailto with current URL in body
- Open in browser chooser (O) — pick from installed browsers
- Clipboard URL reader (P) — reads and announces URL stored in clipboard
- Quick security status (X) — one-line HTTPS / HTTP / file / FTP check
- Deep domain safety analysis (D) — 9-point check for phishing indicators
- Page title + URL announcement (T)
- Readable URL mode — speaks URL in labelled parts (Protocol, Domain, Path, Parameters)
- Auto-announce on page load (optional)
- Include page title when announcing URL (optional)
- Settings panel under NVDA Menu → Preferences → Settings → URL Announcer
- Announce layer commands on/off (silent / expert mode)
- URL action mode: announce only / copy and announce / copy silently
- Restore clipboard after use (optional)
- Update checker on startup (optional)
- UI Automation URL fetch — no focus change, no keyboard simulation, ever
- Layer auto-exit after 30 seconds — prevents stuck layer state
- Full NVDA Addon Store compliance: locale, buildVars, manifest
- Compatible with NVDA 2019.3 and later, tested on NVDA 2025.3

### Browsers Supported
Google Chrome, Microsoft Edge, Mozilla Firefox, Opera, Brave, Vivaldi,
Internet Explorer, Waterfox, SeaMonkey, Pale Moon

### Author
Tirupati Janardhan Gaikwad — NVDA Certified Expert 2025
