# URL Announcer — NVDA Add-on

[![License: GPL-2](https://img.shields.io/badge/License-GPL%20v2-blue.svg)](https://www.gnu.org/licenses/gpl-2.0.html)
[![NVDA: 2021.1+](https://img.shields.io/badge/NVDA-2021.1%2B-green.svg)](https://www.nvaccess.org/)
[![Version: 3.0.0](https://img.shields.io/badge/Version-3.0.0-orange.svg)](https://github.com/tirupatiygaikwad/urlAnnouncer/releases)

**Author:** Tirupati Janardhan Gaikwad — *NVDA Certified Professional 2025*  
**Email:** ytirupatiygaikwad@gmail.com  
**Mobile:** +91 99757 32046  
**Certification:** [NV Access Certification Registry](https://certification.nvaccess.org/?query=tirupati&country=IN&submit=Search)

---

## Overview

URL Announcer is a professional NVDA screen reader add-on that gives blind and visually impaired users complete, accessible control over the current browser URL.

Press **NVDA+Shift+U** to open the command layer, then press one letter key to act — no complex key combinations to memorize.

---

## Features

| Key | Action |
|-----|--------|
| `A` | Announce current URL (raw or readable mode) |
| `C` | Copy URL to clipboard |
| `S` | Copy share link (YouTube → short youtu.be link with timestamp) |
| `X` | Security & analysis (HTTPS, login-page, sensitive data, IP detection) |
| `W` | Share menu — WhatsApp, Facebook, Telegram, Gmail, Twitter, LinkedIn |
| `R` | Browse URL history from this session |
| `M` | Save current URL as a named bookmark |
| `B` | Browse, open, copy, or delete saved bookmarks |
| `L` | Shorten URL using TinyURL (free, no API key) |
| `T` | Announce page title and URL together |
| `E` | Open email client with URL pre-filled |
| `O` | Open URL in a chosen installed browser |
| `P` | Read and announce URL from the clipboard |
| `D` | Extended domain safety check |
| `Q` | Generate QR code (opens in browser via qrserver.com) |
| `H` | Repeat all commands |
| `Escape` | Cancel the command layer |

---

## Why NVDA+Shift+U?

`NVDA+U` (without Shift) is a **built-in NVDA browse-mode command** that navigates to the next unvisited link. This add-on uses `NVDA+Shift+U` instead — a gesture that is free of all conflicts with NVDA's defaults and popular add-ons.

---

## Settings

Go to **NVDA Menu → Preferences → Settings → URL Announcer** to configure:

- **Readable URL mode** — speaks Protocol / Domain / Path / Parameters separately
- **Auto-announce on page load** — URL is spoken every time a browser page loads (opt-in)
- **Include page title when announcing URL**
- **Restore clipboard after reading URL** (on by default)
- **URL history size** — 5, 10, 20, or 50 URLs
- **Extended domain safety analysis**
- **Update notifications on NVDA startup**

---

## Supported Browsers

Chrome · Edge · Firefox · Opera · Brave · Vivaldi · Internet Explorer · Waterfox · SeaMonkey · Pale Moon

---

## Installation

1. Download `urlAnnouncer-3.0.0.nvda-addon` from [Releases](https://github.com/tirupatiygaikwad/urlAnnouncer/releases)
2. Double-click the file — NVDA will ask to install it
3. Click **Yes** and restart NVDA
4. Open any browser and press **NVDA+Shift+U**

---

## Building from Source

```bash
git clone https://github.com/tirupatiygaikwad/urlAnnouncer.git
cd urlAnnouncer
python build.py
# Output: C:\Temp\urlAnnouncer-3.0.0.nvda-addon
```

Requirements: Python 3.8+, no external packages needed.

---

## File Structure

```
urlAnnouncer/
├── manifest.ini                          # NVDA addon metadata
├── build.py                              # Build script
├── README.md                             # This file
├── LICENSE                               # GPL-2
└── addon/
    ├── globalPlugins/
    │   └── urlAnnouncer/
    │       ├── __init__.py               # Main plugin & all layer scripts
    │       ├── _cfg.py                   # Settings config module
    │       ├── urlutils.py               # URL fetch, parse, share utilities
    │       ├── history.py                # Session URL history
    │       ├── bookmarks.py              # Persistent bookmarks
    │       ├── settings.py               # NVDA settings panel
    │       └── updatecheck.py            # Background update checker
    └── doc/
        └── en/
            └── readme.html               # In-addon help file
```

---

## Technical Design

- **No NVDA freezes** — all URL fetching, network calls, and file I/O run in `daemon=True` background threads
- **No clipboard data loss** — original clipboard is always saved and restored
- **Firefox compatible** — retries up to 3× with increasing delays
- **Thread-safe** — `UrlHistory` and `BookmarkManager` use `threading.Lock`
- **No circular imports** — config isolated in `_cfg.py`
- **NVDA best practices** — `addonHandler.initTranslation()`, `@disableInSecureMode`, `@script(gesture=...)`, `super().terminate()`, `wx.CallAfter` for all UI operations from threads

---

## Changelog

### v3.0.0
- URL history (R), bookmarks save/browse (M/B), URL shortener (L)
- Page title + URL (T), email URL (E), open in browser (O)
- Read clipboard URL (P), domain safety check (D), QR code (Q)
- Full settings panel, readable URL mode, auto-announce on page load
- Firefox retry loop, modular 7-file architecture

### v2.0.0
- Command layer (NVDA+Shift+U)
- Announce (A), copy (C), share link (S), security (X), share dialog (W)
- YouTube short links, HTTPS/HTTP detection
- Help (H), cancel (Escape)

---

## License

GNU General Public License version 2.  
See [LICENSE](LICENSE) or [https://www.gnu.org/licenses/gpl-2.0.html](https://www.gnu.org/licenses/gpl-2.0.html)

---

## Contributing

Pull requests and issues are welcome. Please test against NVDA 2024.x or later before submitting.
