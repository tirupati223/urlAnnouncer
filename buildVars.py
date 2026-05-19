# -*- coding: utf-8 -*-
# buildVars.py — URL Announcer NVDA Add-on
# Used by the NVDA Add-on Store build pipeline (SCons / addonTemplate).
# Also used by build.py for consistent version info.

# Add-on information
addon_info = {
    # The add-on identifier — must match the name in manifest.ini exactly.
    "addon_name": "urlAnnouncer",

    # Human-readable name shown in NVDA's Add-on Manager.
    "addon_summary": "URL Announcer",

    # Shown in the add-on description in the Add-on Store.
    "addon_description": (
        "Gives blind and visually impaired users complete, fast control over "
        "the current browser URL. Press NVDA+Shift+U to open the command layer, "
        "then press one letter to announce, copy, share, bookmark, shorten, or "
        "analyse the URL. Features include: URL history, named bookmarks, YouTube "
        "short links, HTTPS security check, deep domain safety analysis, QR code "
        "generator, TinyURL shortener, share menu (WhatsApp, Telegram, Gmail, "
        "Twitter, Facebook, LinkedIn), open in chosen browser, email URL, "
        "clipboard URL reader, readable URL mode, auto-announce on page load, "
        "and background update notifications."
    ),

    # The version — must match manifest.ini.
    "addon_version": "3.0.0",

    # Minimum NVDA version this add-on supports.
    # Format: (year, minor[, patch])
    "addon_minimumNVDAVersion": (2021, 1),

    # Last NVDA version this add-on has been tested against.
    "addon_lastTestedNVDAVersion": (2025, 1),

    # Author name and email.
    "addon_author": u"Tirupati Janardhan Gaikwad <ytirupatiygaikwad@gmail.com>",

    # URL of the add-on repository on GitHub.
    "addon_url": "https://github.com/tirupati223/urlAnnouncer",

    # URL of the add-on source code (for the Add-on Store).
    "addon_sourceURL": "https://github.com/tirupati223/urlAnnouncer",

    # License identifier (SPDX).
    "addon_license": "GPL-2.0",

    # URL of the license text.
    "addon_licenseURL": "https://www.gnu.org/licenses/gpl-2.0.html",

    # Name of the help file (relative to addon/doc/<lang>/).
    "addon_docFileName": "readme.html",
}
