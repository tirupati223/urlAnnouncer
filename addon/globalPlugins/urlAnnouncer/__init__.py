# -*- coding: utf-8 -*-
# URL Announcer — NVDA Global Plugin  v3.1
# Author : Tirupati Janardhan Gaikwad <ytirupatiygaikwad@gmail.com>
# NVDA Certified Expert 2025
# License: GPL-2
#
# KEY DESIGN RULES:
#  1. URL is read via UI Automation — NO Ctrl+L, NO focus change, EVER.
#  2. Every network / file operation runs in a daemon thread — NVDA never freezes.
#  3. Every UI dialog uses wx.CallAfter — thread-safe.
#  4. Layer auto-exits after 30 seconds to prevent stuck state.

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

# Safe import — disableInSecureMode was moved/removed in some NVDA builds.
try:
	from globalPluginHandler import disableInSecureMode
except ImportError:
	def disableInSecureMode(cls):
		cls.disabledInSecureMode = True
		return cls

# Must be called once at module level — makes _() available everywhere.
addonHandler.initTranslation()

# ---------------------------------------------------------------------------
# Submodule imports  (after initTranslation so _() is available)
# ---------------------------------------------------------------------------
from . import _cfg
from .history   import UrlHistory
from .bookmarks import BookmarkManager

# Module-level singletons shared with settings.py
_history   = UrlHistory(maxlen=_cfg.data.get("history_size", 10))
_bookmarks = BookmarkManager()

# ---------------------------------------------------------------------------
# Share platform definitions
# ---------------------------------------------------------------------------
_PLATFORMS = [
	("WhatsApp",  "https://wa.me/?text={url}"),
	("Facebook",  "https://www.facebook.com/sharer/sharer.php?u={url}"),
	("Telegram",  "https://t.me/share/url?url={url}"),
	("Gmail",     "https://mail.google.com/mail/?view=cm&body={url}"),
	("Twitter",   "https://twitter.com/intent/tweet?url={url}"),
	("LinkedIn",  "https://www.linkedin.com/sharing/share-offsite/?url={url}"),
	(_("Copy Link"), None),
]

# ===========================================================================
# Accessible Dialogs
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
		close = wx.Button(panel, wx.ID_CLOSE, label=_("Close"))
		close.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CLOSE))
		sizer.Add(close, flag=wx.ALL | wx.ALIGN_CENTER, border=8)
		panel.SetSizerAndFit(sizer)
		self.Fit()
		self.CentreOnScreen()

	def _on_platform(self, label, template):
		from .urlutils import clip_set, open_url, urlencode
		if template is None:
			clip_set(self._url)
			ui.message(_("Link copied to clipboard."))
		else:
			open_url(template.replace("{url}", urlencode(self._url)))
			ui.message(_("Opening {platform}.").format(platform=label))
		self.EndModal(wx.ID_OK)


class _HistoryDialog(wx.Dialog):
	def __init__(self, parent, items):
		super().__init__(parent, title=_("URL History"),
						 style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP)
		self._items = items
		panel = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)
		sizer.Add(wx.StaticText(panel, label=_("Recent URLs (most recent first):")), flag=wx.ALL, border=6)
		self._list = wx.ListBox(panel, choices=items, style=wx.LB_SINGLE, size=(520, 180))
		if items:
			self._list.SetSelection(0)
		sizer.Add(self._list, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=6)
		btn_row = wx.BoxSizer(wx.HORIZONTAL)
		for label, handler in [
			(_("Announce"),       self._on_announce),
			(_("Copy URL"),       self._on_copy),
			(_("Open in Browser"),self._on_open),
			(_("Clear History"),  self._on_clear),
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
		self._list = wx.ListBox(panel, choices=_bookmarks.get_names(),
								style=wx.LB_SINGLE, size=(520, 180))
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
		self._list = wx.ListBox(panel, choices=[b[0] for b in browsers],
								style=wx.LB_SINGLE, size=(360, 150))
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
	URL Announcer — press NVDA+Shift+U to open the command layer,
	then press one letter.  URL is read via UI Automation — focus never moves.
	All network / file I/O runs in daemon threads — NVDA never freezes.
	"""

	scriptCategory     = _("URL Announcer")
	disabledInSecureMode = True

	# Layer state
	_layer       = False
	_layer_timer = None   # threading.Timer for auto-exit after 30 s

	# All letter keys active while layer is open
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

	# ------------------------------------------------------------------
	# Lifecycle
	# ------------------------------------------------------------------

	def __init__(self, *args, **kwargs):
		try:
			super().__init__(*args, **kwargs)
			from .settings import UrlAnnouncerSettingsPanel
			if UrlAnnouncerSettingsPanel not in settingsDialogs.NVDASettingsDialog.categoryClasses:
				settingsDialogs.NVDASettingsDialog.categoryClasses.append(UrlAnnouncerSettingsPanel)
			if _cfg.data.get("update_check", True):
				from .updatecheck import check_for_updates
				check_for_updates(self._on_update_result)
		except Exception:
			logHandler.log.exception("URL Announcer: error in __init__")

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
			logHandler.log.exception("URL Announcer: error in terminate")
		super().terminate()

	# ------------------------------------------------------------------
	# Auto-announce on page load  (opt-in via settings)
	# ------------------------------------------------------------------

	def event_documentLoadComplete(self, obj, nextHandler):
		nextHandler()
		if _cfg.data.get("auto_announce", False):
			threading.Thread(
				target=self._auto_announce_delayed,
				daemon=True,
				name="UA-AutoAnnounce",
			).start()

	def _auto_announce_delayed(self):
		time.sleep(1.0)
		from .urlutils import foreground_exe, BROWSERS, fetch_url, validate_url, parse_url_readable
		if foreground_exe() not in BROWSERS:
			return
		url = fetch_url(restore_clipboard=_cfg.data.get("restore_clipboard", True))
		if url and validate_url(url):
			_history.add(url)
			spoken = parse_url_readable(url) if _cfg.data.get("readable_mode", False) else url
			wx.CallAfter(ui.message, spoken)

	# ------------------------------------------------------------------
	# Update notification
	# ------------------------------------------------------------------

	def _on_update_result(self, new_version):
		if new_version:
			wx.CallAfter(
				ui.message,
				_("URL Announcer update available: version {v}. "
				  "Open the NVDA Add-on Store to update.").format(v=new_version),
			)

	# ------------------------------------------------------------------
	# Layer management
	# ------------------------------------------------------------------

	def _enter_layer(self):
		self._layer = True
		for gesture, name in self._LAYER_GESTURES.items():
			self.bindGesture(gesture, name)

		# Auto-exit timer — prevents stuck layer state
		self._cancel_layer_timer()
		self._layer_timer = threading.Timer(30.0, self._layer_timeout)
		self._layer_timer.daemon = True
		self._layer_timer.start()

		# Announce commands (optional — can be silenced in settings)
		if _cfg.data.get("announce_layer_commands", True):
			ui.message(_(
				"URL Announcer: "
				"A announce, "
				"C copy, "
				"S share link, "
				"X security, "
				"W share menu, "
				"R history, "
				"M bookmark, "
				"B browse bookmarks, "
				"L shorten, "
				"T title, "
				"E email, "
				"O open in browser, "
				"P clipboard URL, "
				"D domain check, "
				"Q QR code, "
				"H help, "
				"Escape cancel."
			))
		else:
			# Expert / silent mode — just a short confirmation
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
		"""Auto-exit the layer after 30 seconds of inactivity."""
		if self._layer:
			wx.CallAfter(self._exit_layer)

	# ------------------------------------------------------------------
	# Entry-point gesture  (always active)
	# ------------------------------------------------------------------

	@script(
		gesture="kb:NVDA+shift+u",
		description=_("URL Announcer command layer. Press then A announce, C copy, "
					   "S share, X security, W share menu, R history, M bookmark, "
					   "B bookmarks, L shorten, T title, E email, O open, P clipboard, "
					   "D domain, Q QR code, H help, Escape cancel."),
		category=_("URL Announcer"),
	)
	def script_activateLayer(self, gesture):
		if self._layer:
			self._exit_layer()
			ui.message(_("URL Announcer cancelled."))
		else:
			self._enter_layer()

	# ------------------------------------------------------------------
	# Layer scripts — bound dynamically while layer is open
	# ------------------------------------------------------------------

	def script_layer_h(self, gesture):
		ui.message(_(
			"URL Announcer commands: "
			"A: announce URL. "
			"C: copy URL. "
			"S: copy share link — YouTube gives short youtu.be link. "
			"X: quick security status. "
			"W: share menu — WhatsApp, Facebook, Telegram, Gmail, Twitter, LinkedIn. "
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

	# ---- Action scripts ----

	def script_layer_a(self, gesture):
		self._exit_layer()
		threading.Thread(target=self._do_announce, daemon=True, name="UA-announce").start()
	script_layer_a.__doc__ = _("Announce current browser URL")

	def script_layer_c(self, gesture):
		self._exit_layer()
		threading.Thread(target=self._do_copy, daemon=True, name="UA-copy").start()
	script_layer_c.__doc__ = _("Copy current browser URL to clipboard")

	def script_layer_s(self, gesture):
		self._exit_layer()
		threading.Thread(target=self._do_share, daemon=True, name="UA-share").start()
	script_layer_s.__doc__ = _("Copy share link (YouTube: youtu.be short link)")

	def script_layer_x(self, gesture):
		self._exit_layer()
		threading.Thread(target=self._do_security, daemon=True, name="UA-security").start()
	script_layer_x.__doc__ = _("Quick website security status")

	def script_layer_w(self, gesture):
		self._exit_layer()
		threading.Thread(target=self._do_share_dialog, daemon=True, name="UA-dialog").start()
	script_layer_w.__doc__ = _("Open share menu")

	def script_layer_r(self, gesture):
		self._exit_layer()
		wx.CallAfter(self._open_history_dialog)
	script_layer_r.__doc__ = _("Browse URL history")

	def script_layer_m(self, gesture):
		self._exit_layer()
		threading.Thread(target=self._do_save_bookmark, daemon=True, name="UA-bm-save").start()
	script_layer_m.__doc__ = _("Save current URL as bookmark")

	def script_layer_b(self, gesture):
		self._exit_layer()
		wx.CallAfter(self._open_bookmarks_dialog)
	script_layer_b.__doc__ = _("Browse saved bookmarks")

	def script_layer_l(self, gesture):
		self._exit_layer()
		threading.Thread(target=self._do_shorten, daemon=True, name="UA-shorten").start()
	script_layer_l.__doc__ = _("Shorten URL with TinyURL")

	def script_layer_t(self, gesture):
		self._exit_layer()
		threading.Thread(target=self._do_title_url, daemon=True, name="UA-title").start()
	script_layer_t.__doc__ = _("Announce page title and URL")

	def script_layer_e(self, gesture):
		self._exit_layer()
		threading.Thread(target=self._do_email, daemon=True, name="UA-email").start()
	script_layer_e.__doc__ = _("Open email client with URL")

	def script_layer_o(self, gesture):
		self._exit_layer()
		threading.Thread(target=self._do_open_in_browser, daemon=True, name="UA-browser").start()
	script_layer_o.__doc__ = _("Open URL in chosen browser")

	def script_layer_p(self, gesture):
		self._exit_layer()
		threading.Thread(target=self._do_clipboard_url, daemon=True, name="UA-clip").start()
	script_layer_p.__doc__ = _("Read URL from clipboard")

	def script_layer_d(self, gesture):
		self._exit_layer()
		threading.Thread(target=self._do_domain_check, daemon=True, name="UA-domain").start()
	script_layer_d.__doc__ = _("Deep domain safety analysis")

	def script_layer_q(self, gesture):
		self._exit_layer()
		threading.Thread(target=self._do_qr_code, daemon=True, name="UA-qr").start()
	script_layer_q.__doc__ = _("Generate QR code for current URL")

	# ------------------------------------------------------------------
	# Browser / URL check  (called from every action method)
	# ------------------------------------------------------------------

	def _check_browser(self):
		"""
		Verify a browser is active and fetch its URL via UI Automation.
		Returns (url, None) on success or (None, error_message).
		Safe to call from any background thread.
		"""
		from .urlutils import foreground_exe, BROWSERS, fetch_url, validate_url
		if foreground_exe() not in BROWSERS:
			return None, _(
				"No browser is active. "
				"Please switch to Chrome, Firefox, Edge, or another browser and try again."
			)
		url = fetch_url(restore_clipboard=_cfg.data.get("restore_clipboard", True))
		if not url or not validate_url(url):
			return None, _(
				"Could not read the URL. "
				"Make sure a webpage is open and fully loaded."
			)
		return url, None

	# ------------------------------------------------------------------
	# Actions  (all run in daemon background threads)
	# ------------------------------------------------------------------

	def _do_announce(self):
		try:
			url, err = self._check_browser()
			if err:
				ui.message(err)
				return
			_history.add(url)

			# Build spoken text
			if _cfg.data.get("readable_mode", False):
				from .urlutils import parse_url_readable
				spoken = parse_url_readable(url)
			else:
				spoken = url

			if _cfg.data.get("announce_title", False):
				try:
					import api
					obj = api.getForegroundObject()
					if obj and getattr(obj, "name", None):
						spoken = _("Page: {title}. URL: {url}").format(
							title=obj.name, url=spoken)
				except Exception:
					pass

			# Respect url_action_mode setting
			mode = _cfg.data.get("url_action_mode", "announce")
			if mode == "copy":
				from .urlutils import clip_set
				clip_set(url)
				# Silent copy — no speech
			elif mode == "copy_announce":
				from .urlutils import clip_set
				clip_set(url)
				ui.message(_("URL: ") + spoken)
			else:
				# Default: announce only
				ui.message(_("URL: ") + spoken)
		except Exception:
			logHandler.log.exception("URL Announcer: error in _do_announce")
			ui.message(_("An error occurred while reading the URL."))

	def _do_copy(self):
		try:
			url, err = self._check_browser()
			if err:
				ui.message(err)
				return
			from .urlutils import clip_set
			_history.add(url)
			clip_set(url)
			ui.message(_("URL copied to clipboard."))
		except Exception:
			logHandler.log.exception("URL Announcer: error in _do_copy")

	def _do_share(self):
		try:
			url, err = self._check_browser()
			if err:
				ui.message(err)
				return
			from .urlutils import share_url, clip_set
			_history.add(url)
			s = share_url(url)
			clip_set(s)
			if s != url:
				ui.message(_("YouTube share link copied: ") + s)
			else:
				ui.message(_("Share link copied: ") + s)
		except Exception:
			logHandler.log.exception("URL Announcer: error in _do_share")

	def _do_security(self):
		try:
			url, err = self._check_browser()
			if err:
				ui.message(err)
				return
			from .urlutils import get_quick_security
			_history.add(url)
			ui.message(get_quick_security(url))
		except Exception:
			logHandler.log.exception("URL Announcer: error in _do_security")

	def _do_share_dialog(self):
		try:
			url, err = self._check_browser()
			if err:
				ui.message(err)
				return
			from .urlutils import share_url
			_history.add(url)
			wx.CallAfter(self._show_modal, _ShareDialog, url)
		except Exception:
			logHandler.log.exception("URL Announcer: error in _do_share_dialog")

	def _do_save_bookmark(self):
		try:
			url, err = self._check_browser()
			if err:
				ui.message(err)
				return
			try:
				from urllib.parse import urlparse
				default = urlparse(url).netloc.replace("www.", "").split(":")[0]
			except Exception:
				default = ""
			wx.CallAfter(self._open_bookmark_name_dialog, url, default)
		except Exception:
			logHandler.log.exception("URL Announcer: error in _do_save_bookmark")

	def _do_shorten(self):
		try:
			url, err = self._check_browser()
			if err:
				ui.message(err)
				return
			from .urlutils import shorten_url, clip_set
			_history.add(url)
			ui.message(_("Shortening URL, please wait."))
			short = shorten_url(url)
			if short:
				clip_set(short)
				ui.message(_("Short URL copied: ") + short)
			else:
				ui.message(_("Could not shorten URL. Check your internet connection."))
		except Exception:
			logHandler.log.exception("URL Announcer: error in _do_shorten")

	def _do_title_url(self):
		try:
			url, err = self._check_browser()
			if err:
				ui.message(err)
				return
			_history.add(url)
			title = ""
			try:
				import api
				obj = api.getForegroundObject()
				if obj and getattr(obj, "name", None):
					title = obj.name
			except Exception:
				pass
			if title:
				ui.message(_("Page: {title}. URL: {url}").format(title=title, url=url))
			else:
				ui.message(_("URL: ") + url)
		except Exception:
			logHandler.log.exception("URL Announcer: error in _do_title_url")

	def _do_email(self):
		try:
			url, err = self._check_browser()
			if err:
				ui.message(err)
				return
			from .urlutils import urlencode
			_history.add(url)
			try:
				os.startfile("mailto:?subject=Sharing a link&body=" + urlencode(url))
				ui.message(_("Opening email client with the URL."))
			except Exception:
				ui.message(_("Could not open the email client."))
		except Exception:
			logHandler.log.exception("URL Announcer: error in _do_email")

	def _do_open_in_browser(self):
		try:
			url, err = self._check_browser()
			if err:
				ui.message(err)
				return
			from .urlutils import get_installed_browsers
			_history.add(url)
			browsers = get_installed_browsers()
			if not browsers:
				ui.message(_("No supported browsers were found on this computer."))
				return
			wx.CallAfter(self._show_browser_dialog, browsers, url)
		except Exception:
			logHandler.log.exception("URL Announcer: error in _do_open_in_browser")

	def _do_clipboard_url(self):
		try:
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
		except Exception:
			logHandler.log.exception("URL Announcer: error in _do_clipboard_url")

	def _do_domain_check(self):
		try:
			url, err = self._check_browser()
			if err:
				ui.message(err)
				return
			from .urlutils import get_security_info
			_history.add(url)
			ui.message(get_security_info(url))
		except Exception:
			logHandler.log.exception("URL Announcer: error in _do_domain_check")

	def _do_qr_code(self):
		try:
			url, err = self._check_browser()
			if err:
				ui.message(err)
				return
			from .urlutils import open_url, urlencode
			_history.add(url)
			qr_url = "https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=" + urlencode(url)
			ui.message(_("Generating QR code and opening in browser."))
			open_url(qr_url)
		except Exception:
			logHandler.log.exception("URL Announcer: error in _do_qr_code")

	# ------------------------------------------------------------------
	# Dialog helpers  (called via wx.CallAfter from background threads)
	# ------------------------------------------------------------------

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
			ui.message(_("URL history is empty. "
						  "Browse some pages and press NVDA+Shift+U then R again."))
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
			ui.message(_("No bookmarks saved. "
						  "Press NVDA+Shift+U then M to save the current URL."))
			return
		self._show_modal(_BookmarkBrowseDialog)

	def _show_browser_dialog(self, browsers, url):
		self._show_modal(_BrowserChoiceDialog, browsers, url)
