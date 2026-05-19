# -*- coding: utf-8 -*-
# urlutils.py - URL utility functions for URL Announcer
# Tirupati Janardhan Gaikwad
# All browser URL reading is done via Windows UI Automation.
# No keyboard simulation. No focus change. No clipboard tricks.

import ctypes
import os
import re
import subprocess
import threading
from urllib.parse import urlparse, parse_qs, quote, unquote

# ---------------------------------------------------------------------------
# Supported browser process names
# ---------------------------------------------------------------------------
BROWSERS = frozenset({
    "chrome.exe", "msedge.exe", "firefox.exe", "opera.exe",
    "brave.exe", "vivaldi.exe", "iexplore.exe", "waterfox.exe",
    "seamonkey.exe", "palemoon.exe",
})

# ---------------------------------------------------------------------------
# Win32 clipboard constants (used only for clip_get / clip_set)
# ---------------------------------------------------------------------------
_CF_UNICODETEXT = 13
_GMEM_MOVEABLE  = 0x0002


# ---------------------------------------------------------------------------
# Process / window helpers
# ---------------------------------------------------------------------------

def foreground_exe():
    """Return the lowercase exe name of the foreground window's process, or ''."""
    hwnd = ctypes.windll.user32.GetForegroundWindow()
    if not hwnd:
        return ""
    pid = ctypes.c_ulong(0)
    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return ""
    h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid.value)
    if not h:
        return ""
    buf  = ctypes.create_unicode_buffer(260)
    size = ctypes.c_ulong(260)
    ctypes.windll.kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size))
    ctypes.windll.kernel32.CloseHandle(h)
    return os.path.basename(buf.value).lower()


# ---------------------------------------------------------------------------
# Clipboard helpers
# ---------------------------------------------------------------------------

def clip_get():
    """Return current clipboard text, or '' on any failure."""
    if not ctypes.windll.user32.OpenClipboard(None):
        return ""
    try:
        h = ctypes.windll.user32.GetClipboardData(_CF_UNICODETEXT)
        if not h:
            return ""
        p = ctypes.windll.kernel32.GlobalLock(h)
        if not p:
            return ""
        text = ctypes.wstring_at(p)
        ctypes.windll.kernel32.GlobalUnlock(h)
        return text
    except Exception:
        return ""
    finally:
        try:
            ctypes.windll.user32.CloseClipboard()
        except Exception:
            pass


def clip_set(text):
    """Write text to the clipboard. Returns True on success."""
    if not ctypes.windll.user32.OpenClipboard(None):
        return False
    try:
        ctypes.windll.user32.EmptyClipboard()
        data = (text + "\x00").encode("utf-16-le")
        h = ctypes.windll.kernel32.GlobalAlloc(_GMEM_MOVEABLE, len(data))
        if not h:
            return False
        p = ctypes.windll.kernel32.GlobalLock(h)
        ctypes.memmove(p, data, len(data))
        ctypes.windll.kernel32.GlobalUnlock(h)
        ctypes.windll.user32.SetClipboardData(_CF_UNICODETEXT, h)
        return True
    except Exception:
        return False
    finally:
        try:
            ctypes.windll.user32.CloseClipboard()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# URL validation
# ---------------------------------------------------------------------------

_URL_RE = re.compile(
    r'^(https?|ftp|file)://'
    r'[A-Za-z0-9\-._~:/?#\[\]@!$&\'()*+,;=%]+'
    r'$'
)


def validate_url(text):
    """Return True if text looks like a syntactically valid URL."""
    if not text or len(text) > 2048:
        return False
    return bool(_URL_RE.match(text.strip()))


# ---------------------------------------------------------------------------
# Windows UI Automation — address-bar reading
# ---------------------------------------------------------------------------
# Property IDs from the Windows SDK UIA header (uiautomationclient.h).
# These are stable across all Windows 10 / 11 versions.
_UIA_AutomationIdPropertyId = 30011   # AutomationId property
_UIA_ValueValuePropertyId   = 30045   # ValuePattern.Value (edit text)
_UIA_NamePropertyId         = 30005   # Name property
_TreeScope_Descendants      = 4       # Search all descendants

# Address-bar AutomationIds per browser family:
#   Chrome / Edge / Brave / Opera / Vivaldi  →  "omnibox"
#   Firefox                                  →  "urlbar-input" (or "urlbar")
#   Internet Explorer                        →  "addressEditBox"
_ADDR_IDS = ("omnibox", "urlbar-input", "urlbar", "addressEditBox", "address", "url")


def _fetch_url_uia_safe():
    """
    Read the current browser URL using Windows UI Automation.

    MUST be called on the NVDA/wx main thread (STA) to avoid COM
    cross-apartment failures.  Returns URL string or '' on any error.
    """
    try:
        import UIAHandler
    except ImportError:
        return ""

    # Resolve the UIA client object — attribute name varies across NVDA versions.
    client  = None
    handler = getattr(UIAHandler, "handler", None)
    if handler is not None:
        for attr in ("clientObject", "client", "IUIAutomationObject", "automation"):
            client = getattr(handler, attr, None)
            if client is not None:
                break

    if client is None:
        return ""

    hwnd = ctypes.windll.user32.GetForegroundWindow()
    if not hwnd:
        return ""

    try:
        root = client.ElementFromHandle(hwnd)
    except Exception:
        return ""

    if root is None:
        return ""

    for aid in _ADDR_IDS:
        url = _try_read_addr_bar(client, root, aid)
        if url:
            return url

    return ""


def _try_read_addr_bar(client, root, automation_id):
    """
    Find an element by AutomationId and return its text value.
    Returns URL string or '' on any failure.
    Element reference goes out of scope immediately — no stale proxy accumulation.
    """
    try:
        cond = client.CreatePropertyCondition(_UIA_AutomationIdPropertyId, automation_id)
        el   = root.FindFirst(_TreeScope_Descendants, cond)
        if el is None:
            return ""
        # Value property is most reliable for edit/combo fields.
        try:
            val = el.GetCurrentPropertyValue(_UIA_ValueValuePropertyId)
            if isinstance(val, str) and validate_url(val.strip()):
                return val.strip()
        except Exception:
            pass
        # Some browser versions expose the URL via the Name property instead.
        try:
            val = el.GetCurrentPropertyValue(_UIA_NamePropertyId)
            if isinstance(val, str) and validate_url(val.strip()):
                return val.strip()
        except Exception:
            pass
        return ""
    except Exception:
        return ""


def _is_main_thread():
    """Return True if the caller is running on the wx/NVDA main thread."""
    try:
        import wx
        return wx.IsMainThread()
    except Exception:
        return threading.current_thread() is threading.main_thread()


def fetch_url():
    """
    Return the current browser URL via UI Automation.

    Safe to call from any thread.  If called from a background thread the
    query is dispatched to the main thread (where COM lives) and we wait up
    to 500 ms for the result.  If called directly on the main thread the
    query runs inline with no threading overhead.

    Returns URL string, or '' if unavailable.
    """
    if _is_main_thread():
        # Direct call — no threading, no timeout risk.
        return _fetch_url_uia_safe()

    # Background thread — dispatch to main thread via wx event loop.
    import wx

    result   = [""]
    done_evt = threading.Event()

    def _on_main():
        try:
            result[0] = _fetch_url_uia_safe()
        except Exception:
            result[0] = ""
        finally:
            done_evt.set()

    wx.CallAfter(_on_main)
    # 500 ms gives the main thread comfortable time even on loaded systems.
    done_evt.wait(timeout=0.50)
    return result[0]


def get_page_title():
    """
    Return the foreground window title via NVDA's api module.

    Safe to call from any thread — dispatches to main thread when needed.
    Returns string or ''.
    """
    if _is_main_thread():
        return _fetch_title_safe()

    import wx

    result   = [""]
    done_evt = threading.Event()

    def _on_main():
        try:
            result[0] = _fetch_title_safe()
        except Exception:
            result[0] = ""
        finally:
            done_evt.set()

    wx.CallAfter(_on_main)
    done_evt.wait(timeout=0.30)
    return result[0]


def _fetch_title_safe():
    """Read the foreground object name via NVDA api. Must run on main thread."""
    try:
        import api
        obj = api.getForegroundObject()
        if obj is not None:
            name = getattr(obj, "name", None)
            return (name or "").strip()
    except Exception:
        pass
    return ""


# ---------------------------------------------------------------------------
# URL formatting helpers
# ---------------------------------------------------------------------------

def parse_url_readable(url):
    """
    Break a URL into spoken labelled parts.
    Example: Protocol: HTTPS. Domain: google dot com. Path: search.
    """
    try:
        p     = urlparse(url)
        parts = []

        parts.append("Protocol: " + p.scheme.upper())

        domain = p.netloc
        if domain.lower().startswith("www."):
            domain = domain[4:]
        domain = domain.split(":")[0]
        domain_spoken = domain.replace(".", " dot ").replace("-", " dash ")
        parts.append("Domain: " + domain_spoken)

        path = unquote(p.path).strip("/")
        if path:
            path_spoken = (
                path
                .replace("/", " slash ")
                .replace("-", " dash ")
                .replace("_", " ")
                .replace(".", " dot ")
            )
            parts.append("Path: " + path_spoken)

        if p.query:
            params = parse_qs(p.query)
            strs   = []
            for k, v in list(params.items())[:5]:
                strs.append("{k} equals {v}".format(k=k, v=", ".join(v)))
            if strs:
                parts.append("Parameters: " + "; ".join(strs))

        if p.fragment:
            frag = p.fragment.replace("-", " dash ").replace("_", " ")
            parts.append("Section: " + frag)

        return ". ".join(parts) + "."
    except Exception:
        return url


# ---------------------------------------------------------------------------
# Security helpers
# ---------------------------------------------------------------------------

def get_quick_security(url):
    """One-line instant security status for the X command."""
    try:
        p      = urlparse(url)
        scheme = p.scheme.lower()
        domain = p.netloc.replace("www.", "").split(":")[0]
        ds     = domain.replace(".", " dot ").replace("-", " dash ")
        if scheme == "https":
            return "Secure. HTTPS. Domain: {d}.".format(d=ds)
        elif scheme == "http":
            return "Not secure. Plain HTTP. Domain: {d}.".format(d=ds)
        elif scheme == "file":
            return "Local file on your computer."
        elif scheme == "ftp":
            return "FTP connection. Not encrypted."
        return "Protocol: {s}. Domain: {d}.".format(s=scheme, d=ds)
    except Exception:
        return "Could not read security status."


def get_security_info(url):
    """Deep domain safety analysis for the D command."""
    try:
        p      = urlparse(url)
        scheme = p.scheme.lower()
        domain = p.netloc.replace("www.", "").split(":")[0]
        path   = p.path.lower()
        query  = p.query.lower()
        lines  = []
        warn   = 0

        if scheme == "https":
            lines.append("Protocol: HTTPS, encrypted and secure.")
        elif scheme == "http":
            lines.append("Warning: plain HTTP, not encrypted. Do not enter passwords here.")
            warn += 1
        elif scheme == "file":
            lines.append("Local file on your computer.")
        else:
            lines.append("Protocol: {s}.".format(s=scheme))

        ds = domain.replace(".", " dot ").replace("-", " dash ")
        lines.append("Domain: {d}.".format(d=ds))

        login_signals = ["/login", "/signin", "/sign-in", "/auth", "/account", "/session"]
        if any(s in path for s in login_signals):
            lines.append("Login page detected. Verify you trust this site before entering credentials.")
            warn += 1

        sensitive = ["password", "passwd", "token", "secret", "ssn", "key", "apikey", "api_key"]
        if any(k in query for k in sensitive):
            lines.append("Security risk: URL contains sensitive data in query string. Do not share this URL.")
            warn += 1

        if re.match(r'^\d{1,3}(\.\d{1,3}){3}$', domain):
            lines.append("Suspicious: raw IP address domain. Legitimate sites rarely use this.")
            warn += 1

        parts = domain.split(".")
        if len(parts) - 2 > 2:
            lines.append("Suspicious: many subdomains present, possible phishing address.")
            warn += 1

        bad_tlds = [".tk", ".ml", ".ga", ".cf", ".gq", ".xyz", ".top", ".click"]
        if any(domain.endswith(t) for t in bad_tlds):
            lines.append("Caution: TLD commonly associated with suspicious sites.")
            warn += 1

        if len(domain) > 40:
            lines.append("Note: unusually long domain name, possible spoofed address.")
            warn += 1

        if warn == 0:
            lines.append("Overall: no obvious safety concerns detected.")
        elif warn == 1:
            lines.append("Overall: one concern found. Exercise caution.")
        else:
            lines.append(
                "Overall: {n} concerns found. Be careful before entering personal information.".format(n=warn)
            )

        return " ".join(lines)
    except Exception:
        return "Could not analyse domain safety."


# ---------------------------------------------------------------------------
# YouTube / sharing
# ---------------------------------------------------------------------------

def youtube_short(url):
    """Convert a YouTube watch URL to a youtu.be short link, preserving timestamp."""
    m = re.search(r"[?&]v=([A-Za-z0-9_\-]{11})", url)
    if not m:
        return None
    vid = m.group(1)
    t   = re.search(r"[?&]t=([0-9]+)", url)
    return "https://youtu.be/" + vid + ("?t=" + t.group(1) if t else "")


def share_url(url):
    """Return a share-ready URL. YouTube watch URLs become youtu.be short links."""
    if re.search(r"(youtube\.com/watch|youtu\.be/)", url, re.I):
        short = youtube_short(url)
        return short if short else url
    return url


# ---------------------------------------------------------------------------
# Miscellaneous utilities
# ---------------------------------------------------------------------------

def urlencode(text):
    """Percent-encode a string for safe use inside a URL."""
    try:
        return quote(str(text), safe="")
    except Exception:
        return text.replace(" ", "%20")


def open_url(url):
    """Open a URL in the system default browser."""
    try:
        os.startfile(url)
    except Exception:
        try:
            subprocess.Popen(["cmd", "/c", "start", "", url])
        except Exception:
            pass


def shorten_url(url):
    """Shorten a URL via TinyURL (free, no API key required). Returns short URL or None."""
    try:
        import urllib.request
        api_url = "https://tinyurl.com/api-create.php?url=" + urlencode(url)
        req = urllib.request.Request(
            api_url,
            headers={"User-Agent": "URLAnnouncer/3.0 (NVDA addon)"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            short = resp.read().decode("utf-8").strip()
        if short.startswith("https://tinyurl.com/") or short.startswith("http://tinyurl.com/"):
            return short
    except Exception:
        pass
    return None


def get_installed_browsers():
    """
    Return a list of (display_name, exe_path) for browsers found in the Windows registry.
    Checks both HKLM and HKCU so per-user installs are found too.
    """
    results = []
    try:
        import winreg
        candidates = [
            ("Google Chrome",   r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"),
            ("Microsoft Edge",  r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe"),
            ("Mozilla Firefox", r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\firefox.exe"),
            ("Opera",           r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\opera.exe"),
            ("Brave",           r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\brave.exe"),
            ("Vivaldi",         r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\vivaldi.exe"),
        ]
        seen = set()
        for name, reg_path in candidates:
            for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                try:
                    with winreg.OpenKey(hive, reg_path) as key:
                        exe = winreg.QueryValue(key, None)
                        if exe and os.path.isfile(exe) and exe not in seen:
                            results.append((name, exe))
                            seen.add(exe)
                            break
                except OSError:
                    continue
    except Exception:
        pass
    return results
