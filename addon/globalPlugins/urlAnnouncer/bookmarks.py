# -*- coding: utf-8 -*-
# bookmarks.py - saves and loads named URL bookmarks
# Tirupati Janardhan Gaikwad
import json
import os
import threading


def _default_path():
	appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
	return os.path.join(appdata, "nvda", "urlAnnouncer_bookmarks.json")


class BookmarkManager:
	"""
	Thread-safe manager for named URL bookmarks.
	Bookmarks are persisted as a JSON array in the NVDA AppData folder.
	Each entry is {"name": str, "url": str}.
	"""

	def __init__(self, path=None):
		self._path      = path or _default_path()
		self._lock      = threading.Lock()
		self._bookmarks = []   # list of {"name": str, "url": str}
		self._load()

	def _load(self):
		try:
			if os.path.exists(self._path):
				with open(self._path, "r", encoding="utf-8") as f:
					data = json.load(f)
					if isinstance(data, list):
						self._bookmarks = data
		except Exception:
			self._bookmarks = []

	def _save(self):
		try:
			os.makedirs(os.path.dirname(self._path), exist_ok=True)
			with open(self._path, "w", encoding="utf-8") as f:
				json.dump(self._bookmarks, f, ensure_ascii=False, indent=2)
		except Exception:
			pass

	def add(self, name, url):
		"""
		Save or update a bookmark.
		Returns True if a new bookmark was created, False if an existing one was updated.
		"""
		with self._lock:
			for bm in self._bookmarks:
				if bm.get("name") == name:
					bm["url"] = url
					self._save()
					return False   # updated existing
			self._bookmarks.append({"name": name, "url": url})
			self._save()
			return True   # added new

	def remove(self, name):
		"""Delete a bookmark by name. Returns True if it existed."""
		with self._lock:
			before = len(self._bookmarks)
			self._bookmarks = [b for b in self._bookmarks if b.get("name") != name]
			if len(self._bookmarks) < before:
				self._save()
				return True
			return False

	def get_url(self, name):
		"""Return the URL for a bookmark name, or None if not found."""
		with self._lock:
			for b in self._bookmarks:
				if b.get("name") == name:
					return b.get("url")
			return None

	def get_names(self):
		"""Return a list of all bookmark names."""
		with self._lock:
			return [b.get("name", "") for b in self._bookmarks]

	def get_all(self):
		"""Return a copy of the full bookmarks list."""
		with self._lock:
			return list(self._bookmarks)

	def __len__(self):
		with self._lock:
			return len(self._bookmarks)
