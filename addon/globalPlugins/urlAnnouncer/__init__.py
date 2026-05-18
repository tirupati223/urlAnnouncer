# -*- coding: utf-8 -*-
# URL Announcer — NVDA Global Plugin  v3.0.0
# Author : Tirupati Gaikwad <ytirupatiygaikwad@gmail.com>
# License: GPL-2
#
# Follows the official NVDA Add-on Development Guide:
#   https://download.nvaccess.org/releases/2024.2/documentation/developerGuide.html
#
# Command layer — press NVDA+Shift+U, then:
#   A  Announce URL           C  Copy URL
#   S  Copy share link        X  Security + analysis
#   W  Share dialog           R  URL history
#   M  Save bookmark          B  Browse bookmarks
#   L  Shorten URL            T  Page title + URL
#   E  Email URL              O  Open in browser
#   P  Read clipboard URL     D  Domain safety check
#   Q  QR code                H  Help
#   Escape  Cancel

import os
import time
import threading

import addonHandler
import globalPluginHandler
from globalPluginHandler import disableInSecureMode
import ui
import gui
import wx
from gui import guiHelper, settingsDialogs
from scriptHandler import script

# Must be called once at module level — enables _() for all submodules too.
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
# Share platforms
# ---------------------------------------------------------------------------
_PLATFORMS = [
	("WhatsApp",  "https://wa.me/?text={url}"),
	("Facebook",  "https://www.facebook.com/sharer/sharer.php?u={url}"),
	("Telegram",  "https://t.me/share/url?url={url}"),
	("Gmail",     "https://mail.google.com/mail/?view=cm&body={url}"),
	("Twitter",   "https://twitter.com/intent/tweet?url={url}"),
	("LinkedIn",  "https://www.linkedin.com/sharing/share-offsite/?url={url}"),
	# Translators: Button label for copying the link
	(_("Copy Link"), None),
]

# ===========================================================================
# Accessible Dialogs
# ===========================================================================


class _ShareDialog(wx.Dialog):
	"""Fully accessible share dialog with platform buttons."""

	def __init__(self, parent, url):
		super().__init__(
			parent,
			# Translators: Title of the share dialog
			title=_("Share URL"),
			style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP,
		)
		self._url = url
		panel = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)

		# URL display (read-only)
		# Translators: Label above URL text field in share dialog
		sizer.Add(wx.StaticText(panel, label=_("URL:")), flag=wx.ALL, border=6)
		txt = wx.TextCtrl(
			panel, value=url,
			style=wx.TE_READONLY | wx.TE_MULTILINE,
			size=(-1, 50),
		)
		sizer.Add(txt, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=6)

		# Platform buttons
		# Translators: Label above share platform buttons
		sizer.Add(wx.StaticText(panel, label=_("Share to:")), flag=wx.ALL, border=6)
		for label, tmpl in _PLATFORMS:
			btn = wx.Button(panel, label=label)
			btn.Bind(wx.EVT_BUTTON, lambda e, lbl=label, t=tmpl: self._on_platform(lbl, t))
			sizer.Add(btn, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=3)

		# Close button
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
			# Translators: Spoken when link is copied via share dialog
			ui.message(_("Link copied to clipboard."))
		else:
			open_url(template.replace("{url}", urlencode(self._url)))
			# Translators: Spoken when a sharing platform is opened
			ui.message(_("Opening {platform}.").format(platform=label))
		self.EndModal(wx.ID_OK)


class _HistoryDialog(wx.Dialog):
	"""Browsable list of recently visited URLs."""

	def __init__(self, parent, items):
		super().__init__(
			parent,
			# Translators: Title of URL history dialog
			title=_("URL History"),
			style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP,
		)
		self._items = items
		panel = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)

		# Translators: Label above history list
		sizer.Add(wx.StaticText(panel, label=_("Recent URLs (most recent first):")), flag=wx.ALL, border=6)
		self._list = wx.ListBox(panel, choices=items, style=wx.LB_SINGLE, size=(520, 180))
		if items:
			self._list.SetSelection(0)
		sizer.Add(self._list, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=6)

		btn_row = wx.BoxSizer(wx.HORIZONTAL)
		for label, handler in [
			# Translators: Button in history dialog
			(_("Announce"), self._on_announce),
			# Translators: Button in history dialog
			(_("Copy URL"), self._on_copy),
			# Translators: Button in history dialog
			(_("Open in Browser"), self._on_open),
			# Translators: Button in history dialog
			(_("Clear History"), self._on_clear),
			(wx.ID_CLOSE, None),
		]:
			if label == wx.ID_CLOSE:
				btn = wx.Button(panel, wx.ID_CLOSE, label=_("Close"))
				btn.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CLOSE))
			else:
				btn = wx.Button(panel, label=label)
				btn.Bind(wx.EVT_BUTTON, handler)
			btn_row.Add(btn, flag=wx.ALL, border=4)
		sizer.Add(btn_row, flag=wx.ALL | wx.ALIGN_CENTER, border=4)

		panel.SetSizerAndFit(sizer)
		self.Fit()
		self.CentreOnScreen()

	def _selected(self):
		idx = self._list.GetSelection()
		if idx == wx.NOT_FOUND or idx >= len(self._items):
			return None
		return self._items[idx]

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
	"""Ask the user for a bookmark name."""

	def __init__(self, parent, default=""):
		super().__init__(
			parent,
			# Translators: Title of bookmark name dialog
			title=_("Save Bookmark"),
			style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP,
		)
		self.name = None
		panel = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)

		# Translators: Label for bookmark name text field
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
	"""Browse, open, copy, and delete saved bookmarks."""

	def __init__(self, parent):
		super().__init__(
			parent,
			# Translators: Title of bookmarks dialog
			title=_("Bookmarks"),
			style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP,
		)
		panel = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)

		# Translators: Label above bookmark list
		sizer.Add(wx.StaticText(panel, label=_("Saved bookmarks:")), flag=wx.ALL, border=6)
		self._list = wx.ListBox(panel, choices=_bookmarks.get_names(), style=wx.LB_SINGLE, size=(520, 180))
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
	"""Let the user choose which installed browser to open a URL in."""

	def __init__(self, parent, browsers, url):
		super().__init__(
			parent,
			# Translators: Title of browser choice dialog
			title=_("Open URL In Browser"),
			style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP,
		)
		self._browsers = browsers
		self._url      = url
		panel = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)

		# Translators: Label above browser list
		sizer.Add(wx.StaticText(panel, label=_("Choose a browser:")), flag=wx.ALL, border=6)
		self._list = wx.ListBox(
			panel,
			choices=[b[0] for b in browsers],
			style=wx.LB_SINGLE,
			size=(360, 150),
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
	URL Announcer — press NVDA+Shift+U to activate the command layer,
	then press one letter to act.  All network and keyboard operations
	run in daemon background threads so NVDA never freezes.
	"""

	# Shown in NVDA Input Gestures dialog
	scriptCategory = _("URL Announcer")

	# Layer state
	_layer = False

	# All keys active while the layer is open
	_LAYER_GESTURES = {
		"kb:a":       "layer_a",    # Announce URL
		"kb:c":       "layer_c",    # Copy URL
		"kb:s":       "layer_s",    # Share / short link
		"kb:x":       "layer_x",    # Security analysis
		"kb:w":       "layer_w",    # Share dialog
		"kb:r":       "layer_r",    # URL history
		"kb:m":       "layer_m",    # Save bookmark
		"kb:b":       "layer_b",    # Browse bookmarks
		"kb:l":       "layer_l",    # Shorten URL
		"kb:t":       "layer_t",    # Title + URL
		"kb:e":       "layer_e",    # Email URL
		"kb:o":       "layer_o",    # Open in browser
		"kb:p":       "layer_p",    # Read clipboard URL
		"kb:d":       "layer_d",    # Domain safety check
		"kb:q":       "layer_q",    # QR code
		"kb:h":       "layer_h",    # Help
		"kb:escape":  "layer_esc",  # Cancel
	}

	# ------------------------------------------------------------------
	# Lifecycle
	# ------------------------------------------------------------------

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

		# Register the settings panel in NVDA Preferences
		from .settings import UrlAnnouncerSettingsPanel
		if UrlAnnouncerSettingsPanel not in settingsDialogs.NVDASettingsDialog.categoryClasses:
			settingsDialogs.NVDASettingsDialog.categoryClasses.append(UrlAnnouncerSettingsPanel)

		# Start background update check (fails silently if no internet / repo)
		if _cfg.data.get("update_check", True):
			from .updatecheck import check_for_updates
			check_for_updates(self._on_update_result)

	def terminate(self):
		# Remove settings panel
		from .settings import UrlAnnouncerSettingsPanel
		try:
			settingsDialogs.NVDASettingsDialog.categoryClasses.remove(UrlAnnouncerSettingsPanel)
		except ValueError:
			pass

		# Clean up any active layer bindings
		if self._layer:
			self._exit_layer()

		super().terminate()

	# ------------------------------------------------------------------
	# Auto-announce on page load  (opt-in via settings)
	# ------------------------------------------------------------------

	def event_documentLoadComplete(self, obj, nextHandler):
		nextHandler()   # always pass event to next handler first
		if _cfg.data.get("auto_announce", False):
			threading.Thread(
				target=self._auto_announce_delayed,
				daemon=True,
				name="URLAnnouncer-AutoAnnounce",
			).start()

	def _auto_announce_delayed(self):
		time.sleep(1.2)   # wait for browser address bar to settle after load
		from .urlutils import foreground_exe, BROWSERS, fetch_url, validate_url, parse_url_readable
		if foreground_exe() not in BROWSERS:
			return
		url = fetch_url(restore_clipboard=_cfg.data.get("restore_clipboard", True))
		if url and validate_url(url):
			_history.add(url)
			if _cfg.data.get("readable_mode", False):
				wx.CallAfter(ui.message, parse_url_readable(url))
			else:
				wx.CallAfter(ui.message, url)

	# ------------------------------------------------------------------
	# Update notification callback
	# ------------------------------------------------------------------

	def _on_update_result(self, new_version):
		if new_version:
			wx.CallAfter(
				ui.message,
				_(
					"URL Announcer update available: version {v}. "
					"Open the NVDA Add-on Store to update."
				).format(v=new_version),
			)

	# ------------------------------------------------------------------
	# Layer management
	# ------------------------------------------------------------------

	def _enter_layer(self):
		self._layer = True
		for gesture, name in self._LAYER_GESTURES.items():
			self.bindGesture(gesture, name)
		ui.message(_(
			"URL Announcer layer active. "
			"A: announce URL. "
			"C: copy URL. "
			"S: share link. "
			"X: security. "
			"W: share menu. "
			"R: history. "
			"M: bookmark. "
			"B: browse bookmarks. "
			"L: shorten. "
			"T: title and URL. "
			"E: email. "
			"O: open in browser. "
			"P: clipboard URL. "
			"D: domain check. "
			"Q: QR code. "
			"H: help. "
			"Escape: cancel."
		))

	def _exit_layer(self):
		self._layer = False
		for gesture in self._LAYER_GESTURES:
			try:
				self.removeGestureBinding(gesture)
			except Exception:
				pass

	# ------------------------------------------------------------------
	# Entry-point script  (always active, shown in Input Gestures dialog)
	# ------------------------------------------------------------------

	@script(
		gesture="kb:NVDA+shift+u",
		# Translators: Description of the URL Announcer layer shortcut
		description=_(
			"URL Announcer command layer. "
			"After pressing, use: A announce, C copy, S share link, "
			"X security, W share menu, R history, M bookmark, B browse bookmarks, "
			"L shorten, T title, E email, O open in browser, P clipboard URL, "
			"D domain check, Q QR code, H help, Escape cancel."
		),
		category=_("URL Announcer"),
	)
	def script_activateLayer(self, gesture):
		if self._layer:
			self._exit_layer()
			# Translators: Spoken when layer is dismissed by pressing the entry key again
			ui.message(_("URL Announcer cancelled."))
		else:
			self._enter_layer()

	# ------------------------------------------------------------------
	# Layer scripts — each bound dynamically while the layer is open
	# ------------------------------------------------------------------

	# ---- Help ----

	def script_layer_h(self, gesture):
		ui.message(_(
			"URL Announcer commands: "
			"A: announce URL. "
			"C: copy URL to clipboard. "
			"S: copy share link (YouTube: short youtu.be link). "
			"X: website security and analysis. "
			"W: open share menu for WhatsApp, Facebook, Telegram, Gmail, Twitter, LinkedIn. "
			"R: browse URL history from this session. "
			"M: save current URL as a bookmark. "
			"B: browse your saved bookmarks. "
			"L: shorten URL using TinyURL. "
			"T: announce page title and URL together. "
			"E: open email client with URL pre-filled. "
			"O: open URL in a chosen browser. "
			"P: read and announce URL from clipboard. "
			"D: extended domain safety check. "
			"Q: generate QR code for current URL. "
			"Escape: cancel."
		))
	# Translators: Description of the help command
	script_layer_h.__doc__ = _("Repeat URL Announcer help")

	# ---- Cancel ----

	def script_layer_esc(self, gesture):
		self._exit_layer()
		# Translators: Spoken when layer is cancelled with Escape
		ui.message(_("Cancelled."))
	# Translators: Description of the cancel command
	script_layer_esc.__doc__ = _("Cancel the URL Announcer layer")

	# ---- Core commands ----

	def script_layer_a(self, gesture):
		self._exit_layer()
		threading.Thread(target=self._do_announce, daemon=True, name="UA-announce").start()
	# Translators: Description of the announce URL command
	script_layer_a.__doc__ = _("Announce current browser URL")

	def script_layer_c(self, gesture):
		self._exit_layer()
		threading.Thread(target=self._do_copy, daemon=True, name="UA-copy").start()
	# Translators: Description of the copy URL command
	script_layer_c.__doc__ = _("Copy current browser URL to clipboard")

	def script_layer_s(self, gesture):
		self._exit_layer()
		threading.Thread(target=self._do_share, daemon=True, name="UA-share").start()
	# Translators: Description of the share link command
	script_layer_s.__doc__ = _("Copy share link (YouTube: youtu.be short link)")

	def script_layer_x(self, gesture):
		self._exit_layer()
		threading.Thread(target=self._do_security, daemon=True, name="UA-security").start()
	# Translators: Description of the security command
	script_layer_x.__doc__ = _("Announce website security status and analysis")

	def script_layer_w(self, gesture):
		self._exit_layer()
		threading.Thread(target=self._do_share_dialog, daemon=True, name="UA-dialog").start()
	# Translators: Description of the share dialog command
	script_layer_w.__doc__ = _("Open share menu (WhatsApp, Facebook, Telegram, Gmail, Twitter, LinkedIn)")

	# ---- History & bookmarks ----

	def script_layer_r(self, gesture):
		self._exit_layer()
		wx.CallAfter(self._open_history_dialog)
	# Translators: Description of the history command
	script_layer_r.__doc__ = _("Browse URL history from this session")

	def script_layer_m(self, gesture):
		self._exit_layer()
		threading.Thread(target=self._do_save_bookmark, daemon=True, name="UA-bm-save").start()
	# Translators: Description of the bookmark save command
	script_layer_m.__doc__ = _("Save current URL as a bookmark")

	def script_layer_b(self, gesture):
		self._exit_layer()
		wx.CallAfter(self._open_bookmarks_dialog)
	# Translators: Description of the browse bookmarks command
	script_layer_b.__doc__ = _("Browse saved bookmarks")

	# ---- Power features ----

	def script_layer_l(self, gesture):
		self._exit_layer()
		threading.Thread(target=self._do_shorten, daemon=True, name="UA-shorten").start()
	# Translators: Description of the shorten URL command
	script_layer_l.__doc__ = _("Shorten current URL using TinyURL and copy to clipboard")

	def script_layer_t(self, gesture):
		self._exit_layer()
		threading.Thread(target=self._do_title_url, daemon=True, name="UA-title").start()
	# Translators: Description of the title+URL command
	script_layer_t.__doc__ = _("Announce page title and URL together")

	def script_layer_e(self, gesture):
		self._exit_layer()
		threading.Thread(target=self._do_email, daemon=True, name="UA-email").start()
	# Translators: Description of the email URL command
	script_layer_e.__doc__ = _("Open email client with current URL pre-filled")

	def script_layer_o(self, gesture):
		self._exit_layer()
		threading.Thread(target=self._do_open_in_browser, daemon=True, name="UA-browser").start()
	# Translators: Description of the open in browser command
	script_layer_o.__doc__ = _("Open current URL in a chosen browser")

	def script_layer_p(self, gesture):
		self._exit_layer()
		threading.Thread(target=self._do_clipboard_url, daemon=True, name="UA-clip").start()
	# Translators: Description of the clipboard URL command
	script_layer_p.__doc__ = _("Read and announce URL from the clipboard")

	def script_layer_d(self, gesture):
		self._exit_layer()
		threading.Thread(target=self._do_domain_check, daemon=True, name="UA-domain").start()
	# Translators: Description of the domain check command
	script_layer_d.__doc__ = _("Extended domain safety analysis")

	def script_layer_q(self, gesture):
		self._exit_layer()
		threading.Thread(target=self._do_qr_code, daemon=True, name="UA-qr").start()
	# Translators: Description of the QR code command
	script_layer_q.__doc__ = _("Generate QR code for current URL and open it in browser")

	# ------------------------------------------------------------------
	# Internal: browser check
	# ------------------------------------------------------------------

	def _check_browser(self):
		"""
		Verify a browser is active and fetch its current URL.
		Returns (url, None) on success or (None, error_message) on failure.
		All keyboard simulation happens here; safe to call from any thread.
		"""
		from .urlutils import foreground_exe, BROWSERS, fetch_url, validate_url
		if foreground_exe() not in BROWSERS:
			return None, _(
				"No browser is active. "
				"Please switch to Chrome, Firefox, or Edge and try again."
			)
		url = fetch_url(restore_clipboard=_cfg.data.get("restore_clipboard", True))
		if not url or not validate_url(url):
			return None, _(
				"Could not read the URL. "
				"Make sure a webpage is open and the browser is fully loaded."
			)
		return url, None

	# ------------------------------------------------------------------
	# Actions  (all run in background daemon threads)
	# ------------------------------------------------------------------

	def _do_announce(self):
		url, err = self._check_browser()
		if err:
			ui.message(err)
			return
		_history.add(url)
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
						title=obj.name, url=spoken
					)
			except Exception:
				pass
		# Translators: Spoken before the URL
		ui.message(_("URL: ") + spoken)

	def _do_copy(self):
		url, err = self._check_browser()
		if err:
			ui.message(err)
			return
		from .urlutils import clip_set
		_history.add(url)
		clip_set(url)
		# Translators: Spoken after copying URL to clipboard
		ui.message(_("URL copied to clipboard."))

	def _do_share(self):
		url, err = self._check_browser()
		if err:
			ui.message(err)
			return
		from .urlutils import share_url, clip_set
		_history.add(url)
		s = share_url(url)
		clip_set(s)
		if s != url:
			# Translators: Spoken after copying a YouTube short link
			ui.message(_("YouTube share link copied: ") + s)
		else:
			# Translators: Spoken after copying a share link
			ui.message(_("Share link copied: ") + s)

	def _do_security(self):
		url, err = self._check_browser()
		if err:
			ui.message(err)
			return
		from .urlutils import get_security_info
		_history.add(url)
		ui.message(get_security_info(url))

	def _do_share_dialog(self):
		url, err = self._check_browser()
		if err:
			ui.message(err)
			return
		from .urlutils import share_url
		_history.add(url)
		wx.CallAfter(self._show_modal, _ShareDialog, url)

	def _do_save_bookmark(self):
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

	def _do_shorten(self):
		url, err = self._check_browser()
		if err:
			ui.message(err)
			return
		from .urlutils import shorten_url, clip_set
		_history.add(url)
		# Translators: Spoken while waiting for TinyURL response
		ui.message(_("Shortening URL, please wait."))
		short = shorten_url(url)
		if short:
			clip_set(short)
			# Translators: Spoken after short URL is copied
			ui.message(_("Short URL copied to clipboard: ") + short)
		else:
			# Translators: Spoken when TinyURL request fails
			ui.message(_("Could not shorten URL. Check your internet connection and try again."))

	def _do_title_url(self):
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
			# Translators: Spoken when announcing title and URL together
			ui.message(_("Page: {title}. URL: {url}").format(title=title, url=url))
		else:
			ui.message(_("URL: ") + url)

	def _do_email(self):
		url, err = self._check_browser()
		if err:
			ui.message(err)
			return
		from .urlutils import urlencode
		_history.add(url)
		try:
			os.startfile(
				"mailto:?subject=Sharing a link&body=" + urlencode(url)
			)
			# Translators: Spoken after opening email client
			ui.message(_("Opening email client with the URL."))
		except Exception:
			# Translators: Spoken when email client cannot be opened
			ui.message(_("Could not open the email client."))

	def _do_open_in_browser(self):
		url, err = self._check_browser()
		if err:
			ui.message(err)
			return
		from .urlutils import get_installed_browsers
		_history.add(url)
		browsers = get_installed_browsers()
		if not browsers:
			# Translators: Spoken when no browsers are found
			ui.message(_("No supported browsers were found on this computer."))
			return
		wx.CallAfter(self._show_browser_dialog, browsers, url)

	def _do_clipboard_url(self):
		from .urlutils import clip_get, validate_url, parse_url_readable
		text = clip_get().strip()
		if not text:
			# Translators: Spoken when clipboard is empty
			ui.message(_("The clipboard is empty."))
			return
		if not validate_url(text):
			# Translators: Spoken when clipboard does not contain a URL
			ui.message(_("The clipboard does not contain a valid URL."))
			return
		_history.add(text)
		if _cfg.data.get("readable_mode", False):
			spoken = parse_url_readable(text)
		else:
			spoken = text
		# Translators: Spoken when reading URL from clipboard
		ui.message(_("Clipboard URL: ") + spoken)

	def _do_domain_check(self):
		url, err = self._check_browser()
		if err:
			ui.message(err)
			return
		from .urlutils import get_security_info
		_history.add(url)
		ui.message(get_security_info(url))

	def _do_qr_code(self):
		url, err = self._check_browser()
		if err:
			ui.message(err)
			return
		from .urlutils import open_url, urlencode
		_history.add(url)
		# Uses the free qrserver.com API — no API key, no installation required
		qr_url = "https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=" + urlencode(url)
		# Translators: Spoken when opening QR code
		ui.message(_("Generating QR code and opening in browser."))
		open_url(qr_url)

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
			ui.message(_(
				"URL history is empty. "
				"Browse some pages and press NVDA+Shift+U then R again."
			))
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
			ui.message(_(
				"No bookmarks saved. "
				"Press NVDA+Shift+U then M to save the current URL."
			))
			return
		self._show_modal(_BookmarkBrowseDialog)

	def _show_browser_dialog(self, browsers, url):
		self._show_modal(_BrowserChoiceDialog, browsers, url)
