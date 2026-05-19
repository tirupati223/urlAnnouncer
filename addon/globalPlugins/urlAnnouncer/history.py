# -*- coding: utf-8 -*-
# history.py - URL history for one session
# Tirupati Janardhan Gaikwad
import collections
import threading


class UrlHistory:
	"""
	Thread-safe in-memory URL history for one NVDA session.
	Uses a deque so oldest entries are automatically dropped when full.
	"""

	def __init__(self, maxlen=10):
		self._lock    = threading.Lock()
		self._history = collections.deque(maxlen=maxlen)


	def add(self, url):
		"""
		Append url to history.
		Consecutive duplicates are ignored so rapid refreshes don't flood the list.
		"""
		with self._lock:
			if not self._history or self._history[-1] != url:
				self._history.append(url)

	def get_recent(self, n=None):
		"""
		Return URLs as a list, most recent first.
		Pass n to limit the number returned.
		"""
		with self._lock:
			items = list(reversed(self._history))
			return items[:n] if n is not None else items

	def get_all(self):
		"""Return URLs as a list, oldest first."""
		with self._lock:
			return list(self._history)

	def clear(self):
		with self._lock:
			self._history.clear()

	def resize(self, maxlen):
		"""Change the maximum history size, keeping the most recent entries."""
		with self._lock:
			current = list(self._history)
			self._history = collections.deque(current, maxlen=maxlen)

	def __len__(self):
		with self._lock:
			return len(self._history)
