# -*- coding: utf-8 -*-
# _cfg.py - settings storage for URL Announcer
# Tirupati Janardhan Gaikwad

import json
import os

_PATH = os.path.join(
	os.environ.get("APPDATA", os.path.expanduser("~")),
	"nvda", "urlAnnouncer_config.json"
)

# Single mutable dict — never replaced, only updated in place.
# settings.py reads and writes this dict directly.
data = {
	# Speech
	"readable_mode":           False,   # Speak URL in labelled chunks
	"announce_title":          False,   # Include page title with URL announcement
	"auto_announce":           False,   # Announce URL on every page load (opt-in)

	# Layer behaviour
	"announce_layer_commands": True,    # Speak full command list when layer opens
	                                    # False = silent "ready" message (expert mode)

	# A-key action mode
	# "announce"      → speak URL
	# "copy_announce" → copy to clipboard and speak
	# "copy"          → copy silently
	"url_action_mode":         "announce",

	# History
	"history_size":            10,      # Maximum URLs kept per session

	# Safety / Updates
	"safety_check":            False,   # Extended domain safety analysis
	"update_check":            True,    # Check GitHub for newer version on startup
}


def load():
	"""Load persisted settings into data (mutates in place, ignores unknown keys)."""
	try:
		if os.path.exists(_PATH):
			with open(_PATH, "r", encoding="utf-8") as f:
				saved = json.load(f)
			if isinstance(saved, dict):
				# Only restore keys we know about — prevents stale keys accumulating.
				for k in data:
					if k in saved:
						data[k] = saved[k]
	except Exception:
		pass


def save():
	"""Persist the current data dict to disk."""
	try:
		os.makedirs(os.path.dirname(_PATH), exist_ok=True)
		with open(_PATH, "w", encoding="utf-8") as f:
			json.dump(data, f, ensure_ascii=False, indent=2)
	except Exception:
		pass


# Load saved settings on first import.
load()
