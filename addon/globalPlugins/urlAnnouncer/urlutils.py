# -*- coding: utf-8 -*-
# urlutils.py - helper functions for URL Announcer
# Tirupati Janardhan Gaikwad
# reads the browser URL using Windows UI Automation, no focus change, no keyboard tricks

import ctypes
import os
import re
import subprocess
import threading
import time
from urllib.parse import urlparse, parse_qs, quote, unquote

BROWSERS = frozenset({
    "chrome.exe", "msedge.exe", "firefox.exe", "opera.exe",
    "brave.exe", "vivaldi.exe", "iexplore.exe", "waterfox.exe",
    "seamonkey.exe", "palemoon.exe",
})

CF_UNICODETEXT = 13
GMEM_MOVEABLE  = 0x0002


def foreground_exe():
    """Return lowercase exe name of the foreground window process."""
    hwnd = ctypes.windll.user32.GetForegroundWindow()
    pid  = ctypes.c_ulong(0)
    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid.value)
    if not h:
        return ""
    buf  = ctypes.create_unicode_buffer(260)
    size = ctypes.c_ulong(260)
    ctypes.windll.kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size))
    ctypes.windll.kernel32.CloseHandle(h)
    return os.path.basename(buf.value).lower()


def clip_get():
    """Return current clipboard text, or empty string on failure."""
    if not ctypes.windll.user32.OpenClipboard(None):
        return ""
    try:
        h = ctypes.windll.user32.GetClipboardData(CF_UNICODETEXT)
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
        h = ctypes.windll.kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        if not h:
            return False
        p = ctypes.windll.kernel32.GlobalLock(h)
        ctypes.memmove(p, data, len(data))
        ctypes.windll.kernel32.GlobalUnlock(h)
        ctypes.windll.user32.SetClipboardData(CF_UNICODETEXT, h)
        return True
    except Exception:
        return False
    finally:
        try:
            ctypes.windll.user32.CloseClipboard()
        except Exception:
            pass


_URL_RE = re.compile(
    r'^(https?|ftp|file)://'
    r'[A-Za-z0-9\-._~:/?#\[\]@!$&\'()*+,;=%]+'
    r'$'
)


def validate_url(text):
    """Return True if text is a syntactically valid URL."""
    if not text or len(text) > 2048:
        return False
    return bool(_URL_RE.match(text.strip()))


_UIA_AutomationIdPropertyId = 30011
_UIA_ValueValuePropertyId   = 30045   # ValuePattern.Value (edit field text)
_UIA_NamePropertyId         = 30005   # Name property
_TreeScope_Descendants      = 4       # Search all descendants

# Address-bar AutomationIds by browser:
#   Chrome / Edge / Brave / Opera / Vivaldi  ->  "omnibox"
#   Firefox                                  ->  "urlbar-input"
#   Internet Explorer                        ->  "addressEditBox"
_ADDR_IDS = ("omnibox", "urlbar-input", "urlbar", "addressEditBox", "address", "url")



def _uia_query_on_main_thread():
    """
    Dispatch the UIA address-bar query to the wx/NVDA main thread.

    Called from a background worker thread.
    Blocks up to 300 ms for the main thread to complete the COM query.
    Returns URL string or "" if unavailable or timed out.

    WHY: UIAHandler.handler.clientObject lives in an STA created by NVDA's main
    thread. Calling COM methods from a background MTA thread causes cross-apartment
    marshaling that silently fails in NVDA 2025.3.3. Running on the main thread
    avoids all COM apartment issues entirely.
    """
    import wx

    result_holder = [""]           # mutable container so closure can write into it
    done_event    = threading.Event()

    def _do_query_on_main_thread():
        """Runs on the NVDA/wx main thread -- all COM calls are safe here."""
        try:
            result_holder[0] = _fetch_url_uia_safe()
        except Exception:
            result_holder[0] = ""
        finally:
            done_event.set()

    wx.CallAfter(_do_query_on_main_thread)

    # Wait up to 300 ms. Normal UIA traversal takes < 50 ms.
    # If the main thread is under load (event storm) we time out cleanly.
    done_event.wait(timeout=0.30)
    return result_holder[0]


def _fetch_url_uia_safe():
    """
    Read the current browser URL via UI Automation.

    MUST be called on the NVDA/wx main thread (STA).
    No keyboard simulation. No focus change. No sleep().
    All IUIAutomationElement references discarded immediately after use.

    Returns URL string or "" on any failure.
    """
    try:
        import UIAHandler
    except ImportError:
        return ""

    # Resolve UIA client -- attribute name varies across NVDA versions.
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
    Find address bar by AutomationId and read its value.
    Element reference is discarded immediately (no stale proxy accumulation).
    Returns URL string or "" on any failure.
    """
    try:
        cond = client.CreatePropertyCondition(_UIA_AutomationIdPropertyId, automation_id)
        el   = root.FindFirst(_TreeScope_Descendants, cond)
        if el is None:
            return ""
        # Try Value property first (most reliable for edit fields).
        try:
            val = el.GetCurrentPropertyValue(_UIA_ValueValuePropertyId)
            if isinstance(val, str) and validate_url(val.strip()):
                return val.strip()
        except Exception:
            pass
        # Try Name property (some browser versions expose URL here).
        try:
            val = el.GetCurrentPropertyValue(_UIA_NamePropertyId)
            if isinstance(val, str) and validate_url(val.strip()):
                return val.strip()
        except Exception:
            pass
        # el goes out of scope here -- COM reference released automatically.
        return ""
    except Exception:
        return ""



def fetch_url(restore_clipboard=True):
    """
    Get the current browser URL using UI Automation dispatched to the main thread.

    No keyboard simulation. No focus change. No Ctrl+L. Ever.
    If UIA cannot read the URL returns "" -- caller should report "URL not available".
    The restore_clipboard parameter is kept for API compatibility but is unused.
    """
    return _uia_query_on_main_thread()



def parse_url_readable(url):
    """
    Break a URL into labelled spoken parts.
    e.g. Protocol: HTTPS. Domain: google dot com. Path: search. Parameters: q equals nvda.
    """
    try:
        p     = urlparse(url)
        parts = []
        parts.append("Protocol: " + p.scheme.upper())
        domain = p.netloc
        if domain.lower().startswith("www."):
            domain = domain[4:]
        domain_clean  = domain.split(":")[0]
        domain_spoken = domain_clean.replace(".", " dot ").replace("-", " dash ")
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


def get_quick_security(url):
    """One-line instant security status (used by X command)."""
    try:
        p      = urlparse(url)
        scheme = p.scheme.lower()
        domain = p.netloc.replace("www.", "").split(":")[0]
        ds     = domain.replace(".", " dot ").replace("-", " dash ")
        if scheme == "https":
            return "Secure. HTTPS encryption. Domain: {d}.".format(d=ds)
        elif scheme == "http":
            return "Not secure. Plain HTTP -- data is not encrypted. Domain: {d}.".format(d=ds)
        elif scheme == "file":
            return "Local file on your computer."
        elif scheme == "ftp":
            return "FTP connection. Not encrypted."
        return "Protocol: {s}. Domain: {d}.".format(s=scheme, d=ds)
    except Exception:
        return "Could not read security status."


def get_security_info(url):
    """Deep domain safety analysis (used by D command)."""
    try:
        p      = urlparse(url)
        scheme = p.scheme.lower()
        domain = p.netloc.replace("www.", "").split(":")[0]
        path   = p.path.lower()
        query  = p.query.lower()
        lines  = []

        if scheme == "https":
            lines.append("Protocol: HTTPS -- encrypted and secure.")
        elif scheme == "http":
            lines.append("Warning: plain HTTP -- not encrypted. Do not enter passwords here.")
        elif scheme == "file":
            lines.append("Local file on your computer.")
        else:
            lines.append("Protocol: " + scheme + ".")

        ds = domain.replace(".", " dot ").replace("-", " dash ")
        lines.append("Domain: " + ds + ".")

        login_signals = ["/login", "/signin", "/sign-in", "/auth", "/account", "/session"]
        if any(s in path for s in login_signals):
            lines.append("Login page detected. Verify you trust this site before entering credentials.")

        sensitive = ["password", "passwd", "token", "secret", "ssn", "key", "apikey", "api_key"]
        if any(k in query for k in sensitive):
            lines.append("Security risk: URL contains sensitive data. Do not share this URL.")

        if re.match(r'^\d{1,3}(\.\d{1,3}){3}$', domain):
            lines.append("Suspicious: raw IP address domain. Legitimate sites rarely use this.")

        parts = domain.split(".")
        if len(parts) - 2 > 2:
            lines.append("Suspicious: many subdomains -- possible phishing address.")

        bad_tlds = [".tk", ".ml", ".ga", ".cf", ".gq", ".xyz", ".top", ".click"]
        if any(domain.endswith(t) for t in bad_tlds):
            lines.append("Caution: TLD commonly used by suspicious sites.")

        if len(domain) > 40:
            lines.append("Note: unusually long domain -- possible spoofed address.")

        warn_count = sum(
            1 for ln in lines
            if any(w in ln for w in ("Warning", "Suspicious", "risk", "Caution", "Login"))
        )
        if warn_count == 0:
            lines.append("Overall: no obvious safety concerns detected.")
        elif warn_count == 1:
            lines.append("Overall: one concern found. Exercise caution.")
        else:
            lines.append(
                "Overall: {n} concerns found. Be careful before entering personal information.".format(n=warn_count)
            )

        return " ".join(lines)
    except Exception:
        return "Could not analyse domain safety."


def youtube_short(url):
    """Convert a YouTube watch URL to a youtu.be short link."""
    m = re.search(r"[?&]v=([A-Za-z0-9_\-]{11})", url)
    if not m:
        return None
    vid = m.group(1)
    t   = re.search(r"[?&]t=([0-9]+)", url)
    return "https://youtu.be/" + vid + ("?t=" + t.group(1) if t else "")


def share_url(url):
    """Return share-ready URL (YouTube short link when applicable)."""
    if re.search(r"(youtube\.com/watch|youtu\.be/)", url, re.I):
        short = youtube_short(url)
        return short if short else url
    return url


def urlencode(text):
    """Percent-encode a string for use in a URL."""
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
    """Shorten URL using TinyURL (free, no API key). Returns short URL or None."""
    try:
        import urllib.request
        api = "https://tinyurl.com/api-create.php?url=" + urlencode(url)
        req = urllib.request.Request(api, headers={"User-Agent": "URLAnnouncer/3.2 (NVDA addon)"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            short = resp.read().decode("utf-8").strip()
        if short.startswith("https://tinyurl.com/") or short.startswith("http://tinyurl.com/"):
            return short
    except Exception:
        pass
    return None


def get_installed_browsers():
    """Return [(display_name, exe_path)] for browsers found in registry."""
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