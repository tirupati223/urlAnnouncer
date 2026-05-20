# -*- coding: utf-8 -*-
# urlutils.py - URL utility functions for URL Announcer
# Tirupati Janardhan Gaikwad

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
# Win32 clipboard constants
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
# Windows UI Automation — address-bar reading (fast attempt, no focus change)
# ---------------------------------------------------------------------------
_UIA_AutomationIdPropertyId  = 30011
_UIA_ValueValuePropertyId    = 30045
_UIA_NamePropertyId          = 30005
_UIA_ControlTypePropertyId   = 30003
_UIA_ControlType_Edit        = 50004
_TreeScope_Descendants       = 4

_ADDR_IDS = ("omnibox", "urlbar-input", "urlbar", "addressEditBox", "address", "url",
             "addressBar", "urlBar", "location", "locationBar")


def fetch_url_uia():
    """
    Try to read the browser URL via Windows UI Automation.
    Returns URL string or '' if UIA is unavailable or returns nothing.
    Must be called on the NVDA main thread.
    """
    try:
        import UIAHandler
    except ImportError:
        return ""

    handler = getattr(UIAHandler, "handler", None)
    if handler is None:
        return ""

    client = None
    for attr in ("clientObject", "client", "IUIAutomationObject", "automation", "uiAutomation"):
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

    # Pass 1 — search by known AutomationIds.
    for aid in _ADDR_IDS:
        url = _try_by_id(client, root, aid)
        if url:
            return url

    # Pass 2 — scan ALL Edit controls; return the first one containing a valid URL.
    return _scan_edits_for_url(client, root)


def _try_by_id(client, root, automation_id):
    """Find an element by AutomationId and return its URL value."""
    try:
        cond = client.CreatePropertyCondition(_UIA_AutomationIdPropertyId, automation_id)
        el   = root.FindFirst(_TreeScope_Descendants, cond)
        if el is None:
            return ""
        for prop in (_UIA_ValueValuePropertyId, _UIA_NamePropertyId):
            try:
                val = el.GetCurrentPropertyValue(prop)
                if isinstance(val, str) and validate_url(val.strip()):
                    return val.strip()
            except Exception:
                pass
        return ""
    except Exception:
        return ""


def _scan_edits_for_url(client, root):
    """Scan all Edit controls in the window for a URL-valued one."""
    try:
        cond     = client.CreatePropertyCondition(_UIA_ControlTypePropertyId, _UIA_ControlType_Edit)
        elements = root.FindAll(_TreeScope_Descendants, cond)
        if elements is None:
            return ""
        count = getattr(elements, "Length", 0)
        for i in range(min(count, 30)):   # Cap at 30 to avoid slow scans
            try:
                el = elements.GetElement(i)
                for prop in (_UIA_ValueValuePropertyId, _UIA_NamePropertyId):
                    try:
                        val = el.GetCurrentPropertyValue(prop)
                        if isinstance(val, str) and validate_url(val.strip()):
                            return val.strip()
                    except Exception:
                        pass
            except Exception:
                continue
    except Exception:
        pass
    return ""


def get_page_title():
    """Return the foreground window name via NVDA api. Call from main thread."""
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
    """Break a URL into spoken labelled parts."""
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
    """One-line instant security status."""
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
    """Deep domain safety analysis."""
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
            lines.append("Security risk: URL contains sensitive data in query string.")
            warn += 1

        if re.match(r'^\d{1,3}(\.\d{1,3}){3}$', domain):
            lines.append("Suspicious: raw IP address domain.")
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
    """Convert a YouTube watch URL to a youtu.be short link."""
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
    """Shorten a URL via TinyURL. Returns short URL or None."""
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
