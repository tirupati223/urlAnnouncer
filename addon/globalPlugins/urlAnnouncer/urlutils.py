# -*- coding: utf-8 -*-
# URL Announcer — URL Utility Functions
# All Win32, clipboard, keyboard, and URL operations live here.

import ctypes
import os
import re
import subprocess
import time
from urllib.parse import urlparse, parse_qs, quote, unquote

# ---------------------------------------------------------------------------
# Win32 constants
# ---------------------------------------------------------------------------
VK_CONTROL      = 0x11
VK_L            = 0x4C
VK_A            = 0x41
VK_C            = 0x43
VK_ESCAPE       = 0x1B
KEYEVENTF_KEYUP = 0x0002
CF_UNICODETEXT  = 13
GMEM_MOVEABLE   = 0x0002

# ---------------------------------------------------------------------------
# Supported browser executables
# ---------------------------------------------------------------------------
BROWSERS = frozenset({
	"chrome.exe", "msedge.exe", "firefox.exe", "opera.exe",
	"brave.exe", "vivaldi.exe", "iexplore.exe", "waterfox.exe",
	"seamonkey.exe", "palemoon.exe",
})

# ---------------------------------------------------------------------------
# Win32 low-level helpers
# ---------------------------------------------------------------------------

def _kdn(vk):
	ctypes.windll.user32.keybd_event(vk, 0, 0, 0)


def _kup(vk):
	ctypes.windll.user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)


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


# ---------------------------------------------------------------------------
# Clipboard helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# URL fetch via keyboard simulation  (works across all browsers)
# ---------------------------------------------------------------------------

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


def fetch_url(restore_clipboard=True):
	"""
	Focus the browser address bar, copy the URL, and return it.
	Retries up to 3 times to handle Firefox's slower address-bar focus.
	Always restores the original clipboard content when restore_clipboard=True.
	Returns the URL string or empty string on failure.
	"""
	saved = clip_get()
	result = ""
	try:
		for attempt in range(3):
			delay = 0.25 + (attempt * 0.15)   # 0.25, 0.40, 0.55 seconds
			# Ctrl+L — focus address bar
			_kdn(VK_CONTROL); _kdn(VK_L); _kup(VK_L); _kup(VK_CONTROL)
			time.sleep(delay)
			# Ctrl+A — select all text in address bar
			_kdn(VK_CONTROL); _kdn(VK_A); _kup(VK_A); _kup(VK_CONTROL)
			time.sleep(0.1)
			# Ctrl+C — copy
			_kdn(VK_CONTROL); _kdn(VK_C); _kup(VK_C); _kup(VK_CONTROL)
			time.sleep(0.3)
			candidate = clip_get().strip()
			if validate_url(candidate):
				result = candidate
				break
		return result
	finally:
		# Restore clipboard
		time.sleep(0.08)
		if restore_clipboard and saved:
			clip_set(saved)
		# Return keyboard focus to the page
		_kdn(VK_ESCAPE); _kup(VK_ESCAPE)


# ---------------------------------------------------------------------------
# URL analysis helpers
# ---------------------------------------------------------------------------

def parse_url_readable(url):
	"""
	Break a URL into labelled, human-readable spoken parts.
	e.g. "Protocol: HTTPS. Domain: google dot com. Path: search. Parameters: q equals nvda"
	"""
	try:
		p = urlparse(url)
		parts = []

		# Protocol
		parts.append("Protocol: " + p.scheme.upper())

		# Domain — remove www., replace dots and hyphens
		domain = p.netloc
		if domain.lower().startswith("www."):
			domain = domain[4:]
		# Port stripping
		domain_clean = domain.split(":")[0]
		domain_spoken = domain_clean.replace(".", " dot ").replace("-", " dash ")
		parts.append("Domain: " + domain_spoken)

		# Path
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

		# Query parameters (max 5 to keep it concise)
		if p.query:
			params = parse_qs(p.query)
			param_strs = []
			for k, v in list(params.items())[:5]:
				param_strs.append("{k} equals {v}".format(k=k, v=", ".join(v)))
			if param_strs:
				parts.append("Parameters: " + "; ".join(param_strs))

		# Fragment / anchor
		if p.fragment:
			frag = p.fragment.replace("-", " dash ").replace("_", " ")
			parts.append("Section: " + frag)

		return ". ".join(parts) + "."
	except Exception:
		return url


def get_security_info(url):
	"""
	Return a detailed, spoken security analysis of a URL.
	Covers: protocol, login-page detection, suspicious query params, domain.
	"""
	try:
		p      = urlparse(url)
		scheme = p.scheme.lower()
		domain = p.netloc.replace("www.", "").split(":")[0]
		path   = p.path.lower()
		query  = p.query.lower()

		lines = []

		# 1 — Protocol
		if scheme == "https":
			lines.append(
				"Secure connection. "
				"This website uses HTTPS encryption. Your data is protected."
			)
		elif scheme == "http":
			lines.append(
				"Warning: Not secure. "
				"This website uses plain HTTP. "
				"Do not enter passwords or personal data."
			)
		elif scheme == "file":
			lines.append("Local file. This page is stored on your computer.")
		elif scheme == "ftp":
			lines.append("FTP connection. File transfer protocol — not encrypted.")
		else:
			lines.append("Unknown connection type: " + scheme)

		# 2 — Domain
		domain_spoken = domain.replace(".", " dot ").replace("-", " dash ")
		lines.append("Domain: " + domain_spoken + ".")

		# 3 — Login / auth page detection
		login_signals = ["/login", "/signin", "/sign-in", "/auth", "/account", "/session"]
		if any(sig in path for sig in login_signals):
			lines.append(
				"This appears to be a login or account page. "
				"Make sure you trust this website before entering credentials."
			)

		# 4 — Sensitive data in query string
		sensitive_keys = ["password", "passwd", "token", "secret", "ssn", "key", "apikey"]
		found = [k for k in sensitive_keys if k in query]
		if found:
			lines.append(
				"Warning: the URL contains what may be sensitive data in the address. "
				"Avoid sharing this URL with others."
			)

		# 5 — IP address in domain (suspicious)
		if re.match(r'^\d{1,3}(\.\d{1,3}){3}$', domain):
			lines.append(
				"Caution: this URL uses an IP address instead of a domain name, "
				"which is unusual for legitimate websites."
			)

		# 6 — Excessive subdomains (phishing signal)
		subdomain_count = len(domain.split(".")) - 2
		if subdomain_count > 3:
			lines.append(
				"Caution: this URL has many subdomains, "
				"which can be a sign of a phishing site."
			)

		return " ".join(lines)
	except Exception:
		return "Could not analyse security status."


def youtube_short(url):
	"""Convert a YouTube watch URL to a youtu.be short link, preserving timestamp."""
	m = re.search(r"[?&]v=([A-Za-z0-9_\-]{11})", url)
	if not m:
		return None
	vid = m.group(1)
	t   = re.search(r"[?&]t=([0-9]+)", url)
	return "https://youtu.be/" + vid + ("?t=" + t.group(1) if t else "")


def share_url(url):
	"""Return a share-ready URL (YouTube short link when applicable)."""
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
	"""
	Shorten a URL using the TinyURL API (free, no API key required).
	Returns the short URL string, or None if the request fails.
	"""
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
	Return a list of (display_name, exe_path) for browsers found in the registry.
	"""
	results = []
	try:
		import winreg
		candidates = [
			("Google Chrome",    r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"),
			("Microsoft Edge",   r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe"),
			("Mozilla Firefox",  r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\firefox.exe"),
			("Opera",            r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\opera.exe"),
			("Brave",            r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\brave.exe"),
			("Vivaldi",          r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\vivaldi.exe"),
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
