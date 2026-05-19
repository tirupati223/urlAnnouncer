# -*- coding: utf-8 -*-
# URL Announcer — Configuration Module
# Isolated to avoid circular imports between __init__.py and settings.py
import json
import os

_PATH = os.path.join(
	os.environ.get("APPDATA", os.path.expanduser("~")),
	"nvda", "urlAnnouncer_config.json"
)

# Single mutable dict — never replaced, only updated in place
data = {
	# --- Speech / Announce ---
	"readable_mode":           False,  # Speak URL in readable chunks
	"announce_title":          False,  # Include page title with URL
	"auto_announce":           False,  # Announce URL on every page load

	# --- Layer behaviour ---
	"announce_layer_commands": True,   # Speak command list when layer opens
	                                   # Set False: layer opens silently (expert mode)

	# --- URL action mode (for A command) ---
	# "announce"       → speak URL only  (default)
	# "copy_announce"  → copy to clipboard AND speak
	# "copy"           → copy silently, no speech
	"url_action_mode":         "announce",

	# --- Clipboard ---
	"restore_clipboard":       True,   # Restore clipboard after keyboard fallback

	# --- History ---
	"history_size":            10,     # Max URLs remembered per session

	# --- Safety / Updates ---
	"safety_check":            False,  # Extended domain safety analysis
	"update_check":            True,   # Check for updates on startup
}


def load():
	"""Load saved settings into data dict (mutates in place)."""
	try:
		if os.path.exists(_PATH):
			with open(_PATH, "r", encoding="utf-8") as f:
				saved = json.load(f)
				if isinstance(saved, dict):
					data.update(saved)
	except Exception:
		pass


def save():
	"""Persist current data dict to disk."""
	try:
		os.makedirs(os.path.dirname(_PATH), exist_ok=True)
		with open(_PATH, "w", encoding="utf-8") as f:
			json.dump(data, f, ensure_ascii=False, indent=2)
	except Exception:
		pass


# Load on first import
load()
