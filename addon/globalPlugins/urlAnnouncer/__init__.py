# -*- coding: utf-8 -*-
# URL Announcer - NVDA add-on
# Tirupati Janardhan Gaikwad <ytirupatiygaikwad@gmail.com>
# NVDA Certified Expert 2025
# License: GPL-2

import os
import time
import threading

import addonHandler
import globalPluginHandler
import ui
import gui
import wx
from gui import guiHelper
import gui.settingsDialogs as settingsDialogs
from scriptHandler import script
import logHandler
import keyboardHandler

# Safe import — disableInSecureMode was moved in some NVDA builds.
try:
	from globalPluginHandler import disableInSecureMode
except ImportError:
	def disableInSecureMode(cls):
		cls.disabledInSecureMode = True
		return cls

addonHandler.initTranslation()

from . import _cfg
from .history   import UrlHistory
from .bookmarks import BookmarkManager

_history   = UrlHistory(maxlen=_cfg.data.get("history_size", 10))
_bookmarks = BookmarkManager()

_PLATFORMS = [
	("WhatsApp",  "https://wa.me/?text={url}"),
	("Facebook",  "https://www.facebook.com/sharer/sharer.php?u={url}"),
	("Telegram",  "https://t.me/share/url?url={url}"),
	("Gmail",     "https://mail.google.com/mail/?view=cm&body={url}"),
	("Twitter",   "https://twitter.com/intent/tweet?url={url}"),
	("LinkedIn",  "https://www.linkedin.com/sharing/share-offsite/?url={url}"),
]


# ===========================================================================
# Accessible dialog classes
# ===========================================================================

class _ShareDialog(wx.Dialog):
	def __init__(self, parent, url):
		super().__init__(parent, title=_("Share URL"),
						 style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP)
		self._url = url
		panel = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)
		sizer.Add(wx.StaticText(panel, label=_("URL:")), flag=wx.ALL, border=6)
		txt = wx.TextCtrl(panel, value=url, style=wx.TE_READONLY | wx.TE_MULTILINE, size=(-1, 50))
		sizer.Add(txt, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=6)
		sizer.Add(wx.StaticText(panel, label=_("Share to:")), flag=wx.ALL, border=6)
		for label, tmpl in _PLATFORMS:
			btn = wx.Button(panel, label=label)
			btn.Bind(wx.EVT_BUTTON, lambda e, lbl=label, t=tmpl: self._on_platform(lbl, t))
			sizer.Add(btn, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=3)
		copy_btn = wx.Button(panel, label=_("Copy Link"))
		copy_btn.Bind(wx.EVT_BUTTON, lambda e: self._on_copy_link())
		sizer.Add(copy_btn, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=3)
		close = wx.Button(panel, wx.ID_CLOSE, label=_("Close"))
		close.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CLOSE))
		sizer.Add(close, flag=wx.ALL | wx.ALIGN_CENTER, border=8)
		panel.SetSizerAndFit(sizer)
		self.Fit()
		self.CentreOnScreen()

	def _on_platform(self, label, template):
		from .urlutils import open_url, urlencode
		open_url(template.replace("{url}", urlencode(self._url)))
		ui.message(_("Opening {platform}.").format(platform=label))
		self.EndModal(wx.ID_OK)

	def _on_copy_link(self):
		from .urlutils import clip_set
		clip_set(self._url)
		ui.message(_("Link copied to clipboard."))
		self.EndModal(wx.ID_OK)


class _HistoryDialog(wx.Dialog):
	def __init__(self, parent, items):
		super().__init__(parent, title=_("URL History"),
						 style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP)
		self._items = items
		panel = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)
		sizer.Add(
			wx.StaticText(panel, label=_("Recent URLs (most recent first):")),
			flag=wx.ALL, border=6,
		)
		self._list = wx.ListBox(panel, choices=items, style=wx.LB_SINGLE, size=(520, 180))
		if items:
			self._list.SetSelection(0)
		sizer.Add(self._list, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=6)
		btn_row = wx.BoxSizer(wx.HORIZONTAL)
		for label, handler in [
			(_("Announce"),        self._on_announce),
			(_("Copy URL"),        self._on_copy),
			(_("Open in Browser"), self._on_open),
			(_("Clear History"),   self._on_clear),
		]:
			btn = wx.Button(panel, label=label)
			btn.Bind(wx.EVT_BUTTON, handler)
			btn_row.Add(btn, flag=wx.ALL, border=4)
		close = wx.Button(panel, wx.ID_CLOSE, label=_("Close"))
		close.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CLOSE))
		btn_row.Add(close, flag=wx.ALL, border=4)
		sizer.Add(btn_row, flag=wx.ALL | wx.ALIGN_CENTER, border=4)
		panel.SetSizerAndFit(sizer)
		self.Fit()
		self.CentreOnScreen()

	def _selected(self):
		idx = self._list.GetSelection()
		return self._items[idx] if idx != wx.NOT_FOUND and idx < len(self._items) else None

	def _on_announce(self, _):
		url = self._selected()
		if url:
			ui.message(_("URL: ") + url)

	def _on_copy(self, _):
		url = self._selected()
		if url:
			from .urlutils import clip_set
			clip_set(url)
			ui.message(_("URL copied to clipboard."))

	def _on_open(self, _):
		url = self._selected()
		if url:
			from .urlutils import open_url
			open_url(url)
			ui.message(_("Opening URL in browser."))
			self.EndModal(wx.ID_OK)

	def _on_clear(self, _):
		_history.clear()
		self._list.Clear()
		self._items = []
		ui.message(_("URL history cleared."))


class _BookmarkNameDialog(wx.Dialog):
	def __init__(self, parent, default=""):
		super().__init__(parent, title=_("Save Bookmark"),
						 style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP)
		self.name = None
		panel = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)
		sizer.Add(wx.StaticText(panel, label=_("Bookmark name:")), flag=wx.ALL, border=6)
		self._text = wx.TextCtrl(panel, value=default, size=(340, -1))
		sizer.Add(self._text, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=6)
		btn_row = wx.BoxSizer(wx.HORIZONTAL)
		save = wx.Button(panel, wx.ID_OK, label=_("Save"))
		save.Bind(wx.EVT_BUTTON, self._on_save)
		cancel = wx.Button(panel, wx.ID_CANCEL, label=_("Cancel"))
		cancel.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CANCEL))
		btn_row.Add(save, flag=wx.ALL, border=4)
		btn_row.Add(cancel, flag=wx.ALL, border=4)
		sizer.Add(btn_row, flag=wx.ALL | wx.ALIGN_CENTER, border=4)
		panel.SetSizerAndFit(sizer)
		self.Fit()
		self.CentreOnScreen()
		self._text.SetFocus()

	def _on_save(self, _):
		name = self._text.GetValue().strip()
		if name:
			self.name = name
			self.EndModal(wx.ID_OK)
		else:
			ui.message(_("Please enter a name for this bookmark."))


class _BookmarkBrowseDialog(wx.Dialog):
	def __init__(self, parent):
		super().__init__(parent, title=_("Bookmarks"),
						 style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP)
		panel = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)
		sizer.Add(wx.StaticText(panel, label=_("Saved bookmarks:")), flag=wx.ALL, border=6)
		self._list = wx.ListBox(
			panel, choices=_bookmarks.get_names(), style=wx.LB_SINGLE, size=(520, 180),
		)
		if _bookmarks.get_names():
			self._list.SetSelection(0)
		sizer.Add(self._list, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=6)
		btn_row = wx.BoxSizer(wx.HORIZONTAL)
		for label, handler in [
			(_("Open"),     self._on_open),
			(_("Copy URL"), self._on_copy),
			(_("Announce"), self._on_announce),
			(_("Delete"),   self._on_delete),
		]:
			btn = wx.Button(panel, label=label)
			btn.Bind(wx.EVT_BUTTON, handler)
			btn_row.Add(btn, flag=wx.ALL, border=4)
		close = wx.Button(panel, wx.ID_CLOSE, label=_("Close"))
		close.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CLOSE))
		btn_row.Add(close, flag=wx.ALL, border=4)
		sizer.Add(btn_row, flag=wx.ALL | wx.ALIGN_CENTER, border=4)
		panel.SetSizerAndFit(sizer)
		self.Fit()
		self.CentreOnScreen()

	def _selected_name(self):
		idx = self._list.GetSelection()
		return self._list.GetString(idx) if idx != wx.NOT_FOUND else None

	def _on_open(self, _):
		name = self._selected_name()
		if name:
			url = _bookmarks.get_url(name)
			if url:
				from .urlutils import open_url
				open_url(url)
				ui.message(_("Opening bookmark: {name}.").format(name=name))
				self.EndModal(wx.ID_OK)

	def _on_copy(self, _):
		name = self._selected_name()
		if name:
			url = _bookmarks.get_url(name)
			if url:
				from .urlutils import clip_set
				clip_set(url)
				ui.message(_("Bookmark URL copied to clipboard."))

	def _on_announce(self, _):
		name = self._selected_name()
		if name:
			url = _bookmarks.get_url(name)
			if url:
				ui.message(_("Bookmark {name}: {url}").format(name=name, url=url))

	def _on_delete(self, _):
		name = self._selected_name()
		if name:
			idx = self._list.GetSelection()
			_bookmarks.remove(name)
			self._list.Delete(idx)
			ui.message(_("Bookmark deleted: {name}.").format(name=name))


class _BrowserChoiceDialog(wx.Dialog):
	def __init__(self, parent, browsers, url):
		super().__init__(parent, title=_("Open URL In Browser"),
						 style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP)
		self._browsers = browsers
		self._url      = url
		panel = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)
		sizer.Add(wx.StaticText(panel, label=_("Choose a browser:")), flag=wx.ALL, border=6)
		self._list = wx.ListBox(
			panel, choices=[b[0] for b in browsers], style=wx.LB_SINGLE, size=(360, 150),
		)
		if browsers:
			self._list.SetSelection(0)
		sizer.Add(self._list, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=6)
		btn_row = wx.BoxSizer(wx.HORIZONTAL)
		open_btn = wx.Button(panel, wx.ID_OK, label=_("Open"))
		open_btn.Bind(wx.EVT_BUTTON, self._on_open)
		cancel = wx.Button(panel, wx.ID_CANCEL, label=_("Cancel"))
		cancel.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CANCEL))
		btn_row.Add(open_btn, flag=wx.ALL, border=4)
		btn_row.Add(cancel, flag=wx.ALL, border=4)
		sizer.Add(btn_row, flag=wx.ALL | wx.ALIGN_CENTER, border=4)
		panel.SetSizerAndFit(sizer)
		self.Fit()
		self.CentreOnScreen()

	def _on_open(self, _):
		import subprocess
		idx = self._list.GetSelection()
		if idx != wx.NOT_FOUND:
			name, exe = self._browsers[idx]
			try:
				subprocess.Popen([exe, self._url])
				ui.message(_("Opening in {browser}.").format(browser=name))
			except Exception:
				ui.message(_("Could not launch {browser}.").format(browser=name))
			self.EndModal(wx.ID_OK)


# ===========================================================================
# Global Plugin
# ===========================================================================

@disableInSecureMode
class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	"""
	URL Announcer — NVDA+Shift+U opens the command layer; one letter acts.

	URL Fetching Strategy (two-path, guaranteed to work):
	  PATH 1 — UIA (instant, no focus change):
	    Tries Windows UI Automation on the main thread. Works when NVDA has
	    UIA enabled for the browser.
	  PATH 2 — Keyboard simulation (fallback, ~400ms delay):
	    Uses NVDA's own KeyboardInputGesture.send() so Ctrl+L / Ctrl+A /
	    Ctrl+C are invisible to NVDA's own processing. A wx.CallLater chain
	    keeps the main thread free. Works on every browser, every NVDA
	    version, every Windows version.
	"""

	scriptCategory     = _("URL Announcer")
	disabledInSecureMode = True

	_LAYER_GESTURES = {
		"kb:a":      "layer_a",
		"kb:c":      "layer_c",
		"kb:s":      "layer_s",
		"kb:x":      "layer_x",
		"kb:w":      "layer_w",
		"kb:r":      "layer_r",
		"kb:m":      "layer_m",
		"kb:b":      "layer_b",
		"kb:l":      "layer_l",
		"kb:t":      "layer_t",
		"kb:e":      "layer_e",
		"kb:o":      "layer_o",
		"kb:p":      "layer_p",
		"kb:d":      "layer_d",
		"kb:q":      "layer_q",
		"kb:h":      "layer_h",
		"kb:escape": "layer_esc",
	}

	# ---- Lifecycle ---------------------------------------------------------

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._layer       = False
		self._layer_timer = None
		# State for keyboard-simulation URL fetching
		self._kburl_cb       = None
		self._kburl_old_clip = ""
		self._kburl_restore  = True
		try:
			from .settings import UrlAnnouncerSettingsPanel
			if UrlAnnouncerSettingsPanel not in settingsDialogs.NVDASettingsDialog.categoryClasses:
				settingsDialogs.NVDASettingsDialog.categoryClasses.append(UrlAnnouncerSettingsPanel)
			if _cfg.data.get("update_check", True):
				from .updatecheck import check_for_updates
				check_for_updates(self._on_update_result)
		except Exception:
			logHandler.log.exception("URL Announcer: __init__")

	def terminate(self):
		try:
			from .settings import UrlAnnouncerSettingsPanel
			try:
				settingsDialogs.NVDASettingsDialog.categoryClasses.remove(UrlAnnouncerSettingsPanel)
			except ValueError:
				pass
			self._cancel_layer_timer()
			if self._layer:
				self._exit_layer()
		except Exception:
			logHandler.log.exception("URL Announcer: terminate")
		super().terminate()

	# ---- Auto-announce on page load ----------------------------------------

	def event_documentLoadComplete(self, obj, nextHandler):
		nextHandler()
		if _cfg.data.get("auto_announce", False):
			threading.Thread(
				target=self._auto_announce_delayed, daemon=True, name="UA-AutoAnnounce"
			).start()

	def _auto_announce_delayed(self):
		time.sleep(1.0)
		from .urlutils import foreground_exe, BROWSERS, fetch_url_uia, validate_url, parse_url_readable
		if foreground_exe() not in BROWSERS:
			return
		url = fetch_url_uia()
		if url and validate_url(url):
			_history.add(url)
			spoken = parse_url_readable(url) if _cfg.data.get("readable_mode", False) else url
			wx.CallAfter(ui.message, spoken)

	# ---- Update notification ------------------------------------------------

	def _on_update_result(self, new_version):
		if new_version:
			wx.CallAfter(
				ui.message,
				_("URL Announcer update available: version {v}. "
				  "Open the NVDA Add-on Store to update.").format(v=new_version),
			)

	# ---- Layer management --------------------------------------------------

	def _enter_layer(self):
		self._layer = True
		for gesture, name in self._LAYER_GESTURES.items():
			self.bindGesture(gesture, name)
		self._cancel_layer_timer()
		self._layer_timer = threading.Timer(30.0, self._layer_timeout)
		self._layer_timer.daemon = True
		self._layer_timer.start()
		if _cfg.data.get("announce_layer_commands", True):
			ui.message(_(
				"URL Announcer: "
				"A announce, C copy, S share link, X security, W share menu, "
				"R history, M bookmark, B bookmarks, L shorten, T title, "
				"E email, O open in browser, P clipboard URL, D domain check, "
				"Q QR code, H help, Escape cancel."
			))
		else:
			ui.message(_("URL Announcer ready."))

	def _exit_layer(self):
		self._layer = False
		self._cancel_layer_timer()
		for gesture in self._LAYER_GESTURES:
			try:
				self.removeGestureBinding(gesture)
			except Exception:
				pass

	def _cancel_layer_timer(self):
		if self._layer_timer is not None:
			try:
				self._layer_timer.cancel()
			except Exception:
				pass
			self._layer_timer = None

	def _layer_timeout(self):
		if self._layer:
			wx.CallAfter(self._exit_layer)

	# =========================================================================
	# URL FETCHING — Two-path architecture
	# =========================================================================
	# PATH 1: UIA (called on main thread, instant, no focus change)
	# PATH 2: Keyboard sim (wx.CallLater chain, NVDA-silent, ~400 ms total)
	#
	# Every script handler calls _get_url_then(callback, restore_clipboard).
	# The callback receives the URL string (or None on failure) and performs
	# the command-specific action.
	# =========================================================================

	def _get_url_then(self, callback, restore_clipboard=True):
		"""
		Fetch the current browser URL and call callback(url_or_None).
		Tries UIA first (instant). If that returns nothing, uses keyboard
		simulation (3-step wx.CallLater, non-blocking, ~400 ms).
		Must be called on the NVDA main thread.
		"""
		from .urlutils import foreground_exe, BROWSERS, fetch_url_uia, validate_url

		# Verify a browser is in the foreground.
		if foreground_exe() not in BROWSERS:
			callback(None, "no_browser")
			return

		# PATH 1 — try UIA (inline, instant).
		url = fetch_url_uia()
		if url and validate_url(url):
			callback(url, None)
			return

		# PATH 2 — keyboard simulation via NVDA-silent key injection.
		from .urlutils import clip_get
		self._kburl_cb       = callback
		self._kburl_restore  = restore_clipboard
		self._kburl_old_clip = clip_get() if restore_clipboard else ""

		# Ctrl+L focuses the address bar in every major browser.
		# KeyboardInputGesture.send() marks the keystroke as NVDA-injected
		# so NVDA's own processing ignores it — no duplicate announcements.
		try:
			keyboardHandler.KeyboardInputGesture.fromName("control+l").send()
		except Exception:
			logHandler.log.exception("URL Announcer: control+l send failed")
			callback(None, "error")
			return

		# Wait 230 ms for the address bar to receive focus and populate.
		wx.CallLater(230, self._kburl_step2)

	def _kburl_step2(self):
		"""Select-all then copy — runs after address bar is focused."""
		from .urlutils import foreground_exe, BROWSERS
		# Safety check: user may have switched windows during the 230 ms wait.
		if foreground_exe() not in BROWSERS:
			self._kburl_done(None, "no_browser")
			return
		try:
			keyboardHandler.KeyboardInputGesture.fromName("control+a").send()
			keyboardHandler.KeyboardInputGesture.fromName("control+c").send()
		except Exception:
			logHandler.log.exception("URL Announcer: ctrl+a/c send failed")
			self._kburl_done(None, "error")
			return
		# Wait 180 ms for the clipboard to be populated by the browser.
		wx.CallLater(180, self._kburl_step3)

	def _kburl_step3(self):
		"""Read clipboard, validate, restore, call callback."""
		from .urlutils import clip_get, validate_url, clip_set

		candidate = clip_get().strip()

		# Return focus to the page (Escape in address bar goes back to page).
		try:
			keyboardHandler.KeyboardInputGesture.fromName("escape").send()
		except Exception:
			pass

		# Restore the original clipboard content.
		if self._kburl_restore and self._kburl_old_clip:
			# Delay restoration slightly so the callback can read the URL first.
			wx.CallLater(80, clip_set, self._kburl_old_clip)

		url = candidate if validate_url(candidate) else None
		self._kburl_done(url, None if url else "bad_url")

	def _kburl_done(self, url, reason):
		"""Invoke the stored callback and clear state."""
		cb = self._kburl_cb
		self._kburl_cb       = None
		self._kburl_old_clip = ""
		if cb:
			cb(url, reason)

	# ---- Error message helper -----------------------------------------------

	def _url_error_msg(self, reason):
		if reason == "no_browser":
			return _(
				"No browser is active. "
				"Switch to Chrome, Firefox, Edge, or another supported browser and try again."
			)
		if reason == "bad_url":
			return _("The address bar contains text that is not a URL.")
		return _(
			"Could not read the URL. "
			"Make sure a webpage is fully loaded and try again."
		)

	# ---- Entry-point gesture ------------------------------------------------

	@script(
		gesture="kb:NVDA+shift+u",
		description=_(
			"URL Announcer command layer. Press A announce, C copy, S share link, "
			"X security, W share menu, R history, M bookmark, B bookmarks, "
			"L shorten, T title, E email, O open, P clipboard, "
			"D domain check, Q QR code, H help, Escape cancel."
		),
		category=_("URL Announcer"),
	)
	def script_activateLayer(self, gesture):
		if self._layer:
			self._exit_layer()
			ui.message(_("URL Announcer cancelled."))
		else:
			self._enter_layer()

	# ---- Layer command scripts ----------------------------------------------

	def script_layer_h(self, gesture):
		ui.message(_(
			"URL Announcer commands: "
			"A: announce URL. "
			"C: copy URL. "
			"S: copy share link, YouTube gives short youtu.be link. "
			"X: quick security status. "
			"W: share menu, WhatsApp, Facebook, Telegram, Gmail, Twitter, LinkedIn. "
			"R: browse URL history. "
			"M: save current URL as bookmark. "
			"B: browse saved bookmarks. "
			"L: shorten URL with TinyURL. "
			"T: announce page title and URL. "
			"E: open email with URL. "
			"O: open URL in chosen browser. "
			"P: read URL from clipboard. "
			"D: deep domain safety analysis. "
			"Q: generate QR code. "
			"Escape: cancel."
		))
	script_layer_h.__doc__ = _("Repeat URL Announcer help")

	def script_layer_esc(self, gesture):
		self._exit_layer()
		ui.message(_("Cancelled."))
	script_layer_esc.__doc__ = _("Cancel the URL Announcer layer")

	# ---- A: Announce URL ---------------------------------------------------

	def script_layer_a(self, gesture):
		self._exit_layer()
		self._get_url_then(self._cb_announce, restore_clipboard=True)
	script_layer_a.__doc__ = _("Announce current browser URL")

	def _cb_announce(self, url, reason):
		if not url:
			ui.message(self._url_error_msg(reason))
			return
		_history.add(url)
		from .urlutils import parse_url_readable, get_page_title
		spoken = parse_url_readable(url) if _cfg.data.get("readable_mode", False) else url
		if _cfg.data.get("announce_title", False):
			title = get_page_title()
			if title:
				spoken = _("Page: {title}. URL: {url}").format(title=title, url=spoken)
		mode = _cfg.data.get("url_action_mode", "announce")
		if mode == "copy":
			from .urlutils import clip_set
			clip_set(url)
		elif mode == "copy_announce":
			from .urlutils import clip_set
			clip_set(url)
			ui.message(_("URL: ") + spoken)
		else:
			ui.message(_("URL: ") + spoken)

	# ---- C: Copy URL -------------------------------------------------------

	def script_layer_c(self, gesture):
		self._exit_layer()
		# restore_clipboard=False: the URL stays in clipboard (that IS the goal).
		self._get_url_then(self._cb_copy, restore_clipboard=False)
	script_layer_c.__doc__ = _("Copy current browser URL to clipboard")

	def _cb_copy(self, url, reason):
		if not url:
			ui.message(self._url_error_msg(reason))
			return
		from .urlutils import clip_set
		_history.add(url)
		clip_set(url)
		ui.message(_("URL copied to clipboard."))

	# ---- S: Share link -----------------------------------------------------

	def script_layer_s(self, gesture):
		self._exit_layer()
		self._get_url_then(self._cb_share, restore_clipboard=False)
	script_layer_s.__doc__ = _("Copy share link (YouTube: youtu.be short link)")

	def _cb_share(self, url, reason):
		if not url:
			ui.message(self._url_error_msg(reason))
			return
		from .urlutils import share_url, clip_set
		_history.add(url)
		s = share_url(url)
		clip_set(s)
		if s != url:
			ui.message(_("YouTube share link copied: ") + s)
		else:
			ui.message(_("Share link copied: ") + s)

	# ---- X: Quick security -------------------------------------------------

	def script_layer_x(self, gesture):
		self._exit_layer()
		self._get_url_then(self._cb_security, restore_clipboard=True)
	script_layer_x.__doc__ = _("Quick website security status")

	def _cb_security(self, url, reason):
		if not url:
			ui.message(self._url_error_msg(reason))
			return
		from .urlutils import get_quick_security
		_history.add(url)
		ui.message(get_quick_security(url))

	# ---- W: Share menu dialog ----------------------------------------------

	def script_layer_w(self, gesture):
		self._exit_layer()
		self._get_url_then(self._cb_share_dialog, restore_clipboard=True)
	script_layer_w.__doc__ = _("Open share menu")

	def _cb_share_dialog(self, url, reason):
		if not url:
			ui.message(self._url_error_msg(reason))
			return
		_history.add(url)
		self._show_modal(_ShareDialog, url)

	# ---- R: History dialog -------------------------------------------------

	def script_layer_r(self, gesture):
		self._exit_layer()
		self._open_history_dialog()
	script_layer_r.__doc__ = _("Browse URL history")

	# ---- M: Save bookmark --------------------------------------------------

	def script_layer_m(self, gesture):
		self._exit_layer()
		self._get_url_then(self._cb_save_bookmark, restore_clipboard=True)
	script_layer_m.__doc__ = _("Save current URL as bookmark")

	def _cb_save_bookmark(self, url, reason):
		if not url:
			ui.message(self._url_error_msg(reason))
			return
		try:
			from urllib.parse import urlparse
			default = urlparse(url).netloc.replace("www.", "").split(":")[0]
		except Exception:
			default = ""
		self._open_bookmark_name_dialog(url, default)

	# ---- B: Browse bookmarks -----------------------------------------------

	def script_layer_b(self, gesture):
		self._exit_layer()
		self._open_bookmarks_dialog()
	script_layer_b.__doc__ = _("Browse saved bookmarks")

	# ---- L: Shorten URL ----------------------------------------------------

	def script_layer_l(self, gesture):
		self._exit_layer()
		self._get_url_then(self._cb_shorten, restore_clipboard=False)
	script_layer_l.__doc__ = _("Shorten URL with TinyURL")

	def _cb_shorten(self, url, reason):
		if not url:
			ui.message(self._url_error_msg(reason))
			return
		_history.add(url)
		ui.message(_("Shortening URL, please wait."))
		threading.Thread(
			target=self._do_shorten, args=(url,), daemon=True, name="UA-shorten"
		).start()

	def _do_shorten(self, url):
		from .urlutils import shorten_url, clip_set
		short = shorten_url(url)
		if short:
			clip_set(short)
			wx.CallAfter(ui.message, _("Short URL copied: ") + short)
		else:
			wx.CallAfter(ui.message, _("Could not shorten URL. Check your internet connection."))

	# ---- T: Page title + URL -----------------------------------------------

	def script_layer_t(self, gesture):
		self._exit_layer()
		self._get_url_then(self._cb_title_url, restore_clipboard=True)
	script_layer_t.__doc__ = _("Announce page title and URL")

	def _cb_title_url(self, url, reason):
		if not url:
			ui.message(self._url_error_msg(reason))
			return
		_history.add(url)
		from .urlutils import get_page_title
		title = get_page_title()
		if title:
			ui.message(_("Page: {title}. URL: {url}").format(title=title, url=url))
		else:
			ui.message(_("URL: ") + url)

	# ---- E: Email URL ------------------------------------------------------

	def script_layer_e(self, gesture):
		self._exit_layer()
		self._get_url_then(self._cb_email, restore_clipboard=True)
	script_layer_e.__doc__ = _("Open email client with URL")

	def _cb_email(self, url, reason):
		if not url:
			ui.message(self._url_error_msg(reason))
			return
		from .urlutils import urlencode
		_history.add(url)
		try:
			os.startfile("mailto:?subject=Sharing a link&body=" + urlencode(url))
			ui.message(_("Opening email client with the URL."))
		except Exception:
			ui.message(_("Could not open the email client."))

	# ---- O: Open in chosen browser -----------------------------------------

	def script_layer_o(self, gesture):
		self._exit_layer()
		self._get_url_then(self._cb_open_browser, restore_clipboard=True)
	script_layer_o.__doc__ = _("Open URL in chosen browser")

	def _cb_open_browser(self, url, reason):
		if not url:
			ui.message(self._url_error_msg(reason))
			return
		from .urlutils import get_installed_browsers
		_history.add(url)
		browsers = get_installed_browsers()
		if not browsers:
			ui.message(_("No supported browsers were found on this computer."))
			return
		self._show_modal(_BrowserChoiceDialog, browsers, url)

	# ---- P: Clipboard URL (no browser needed) ------------------------------

	def script_layer_p(self, gesture):
		self._exit_layer()
		from .urlutils import clip_get, validate_url, parse_url_readable
		text = clip_get().strip()
		if not text:
			ui.message(_("The clipboard is empty."))
			return
		if not validate_url(text):
			ui.message(_("The clipboard does not contain a valid URL."))
			return
		_history.add(text)
		spoken = parse_url_readable(text) if _cfg.data.get("readable_mode", False) else text
		ui.message(_("Clipboard URL: ") + spoken)
	script_layer_p.__doc__ = _("Read URL from clipboard")

	# ---- D: Deep domain safety analysis ------------------------------------

	def script_layer_d(self, gesture):
		self._exit_layer()
		self._get_url_then(self._cb_domain, restore_clipboard=True)
	script_layer_d.__doc__ = _("Deep domain safety analysis")

	def _cb_domain(self, url, reason):
		if not url:
			ui.message(self._url_error_msg(reason))
			return
		from .urlutils import get_security_info
		_history.add(url)
		ui.message(get_security_info(url))

	# ---- Q: QR code --------------------------------------------------------

	def script_layer_q(self, gesture):
		self._exit_layer()
		self._get_url_then(self._cb_qr, restore_clipboard=True)
	script_layer_q.__doc__ = _("Generate QR code for current URL")

	def _cb_qr(self, url, reason):
		if not url:
			ui.message(self._url_error_msg(reason))
			return
		from .urlutils import open_url, urlencode
		_history.add(url)
		qr_url = "https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=" + urlencode(url)
		ui.message(_("Generating QR code and opening in browser."))
		threading.Thread(target=open_url, args=(qr_url,), daemon=True, name="UA-qr").start()

	# ---- Dialog helpers ----------------------------------------------------

	def _show_modal(self, dialog_class, *args):
		dlg = dialog_class(gui.mainFrame, *args)
		gui.mainFrame.prePopup()
		try:
			dlg.ShowModal()
		finally:
			dlg.Destroy()
			gui.mainFrame.postPopup()

	def _open_history_dialog(self):
		items = _history.get_recent()
		if not items:
			ui.message(_("URL history is empty. Browse some pages and press NVDA+Shift+U then R."))
			return
		self._show_modal(_HistoryDialog, items)

	def _open_bookmark_name_dialog(self, url, default_name):
		dlg = _BookmarkNameDialog(gui.mainFrame, default_name)
		gui.mainFrame.prePopup()
		try:
			if dlg.ShowModal() == wx.ID_OK and dlg.name:
				is_new = _bookmarks.add(dlg.name, url)
				if is_new:
					ui.message(_("Bookmark saved: {name}.").format(name=dlg.name))
				else:
					ui.message(_("Bookmark updated: {name}.").format(name=dlg.name))
		finally:
			dlg.Destroy()
			gui.mainFrame.postPopup()

	def _open_bookmarks_dialog(self):
		if not len(_bookmarks):
			ui.message(_("No bookmarks saved. Press NVDA+Shift+U then M to save the current URL."))
			return
		self._show_modal(_BookmarkBrowseDialog)
