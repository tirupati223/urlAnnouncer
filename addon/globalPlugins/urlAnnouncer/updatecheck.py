# -*- coding: utf-8 -*-
# URL Announcer — Background Update Checker
#
# Checks a version.json file on GitHub. If the addon author has not yet
# created the GitHub repository, the request simply fails silently.
# No crash, no NVDA hang — the check runs in a daemon thread.

import json
import threading
import urllib.request

CURRENT_VERSION = "3.0.0"
VERSION_URL = (
	"https://raw.githubusercontent.com/tirupati223/"
	"urlAnnouncer/main/version.json"
)


def _parse_version(v):
	"""Convert '3.0.0' to (3, 0, 0) for comparison. Returns (0,) on error."""
	try:
		return tuple(int(x) for x in str(v).split("."))
	except Exception:
		return (0,)


def check_for_updates(callback):
	"""
	Start a background daemon thread that checks for a newer version.

	callback(new_version_str) is called on the same background thread:
	  - new_version_str is a string like "3.1.0" if an update exists
	  - new_version_str is None if the addon is up to date or the check failed

	The caller should wrap any UI operations in wx.CallAfter.
	"""
	def _check():
		try:
			req = urllib.request.Request(
				VERSION_URL,
				headers={"User-Agent": "URLAnnouncer/{v} (NVDA addon)".format(v=CURRENT_VERSION)},
			)
			with urllib.request.urlopen(req, timeout=10) as resp:
				payload = json.loads(resp.read().decode("utf-8"))
			latest = payload.get("version", "")
			if latest and _parse_version(latest) > _parse_version(CURRENT_VERSION):
				callback(latest)
			else:
				callback(None)
		except Exception:
			callback(None)   # Silently swallow all errors

	t = threading.Thread(target=_check, daemon=True, name="URLAnnouncer-UpdateCheck")
	t.start()
