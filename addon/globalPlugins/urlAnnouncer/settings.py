# -*- coding: utf-8 -*-
# URL Announcer — NVDA Settings Panel
# Registered in NVDA Menu → Preferences → Settings → URL Announcer
#
# Uses gui.guiHelper.BoxSizerHelper per the official NVDA addon development guide.
# Imports _cfg (not __init__) to avoid circular imports.

import wx
import gui
from gui import guiHelper, settingsDialogs
import addonHandler

# _() is available because addonHandler.initTranslation() was called in __init__.py
# We do NOT call it again here.

from . import _cfg   # shared config dict — no circular import


class UrlAnnouncerSettingsPanel(settingsDialogs.SettingsPanel):
	# Translators: Title shown in the NVDA Settings category list
	title = _("URL Announcer")

	# ------------------------------------------------------------------
	# Build the panel
	# ------------------------------------------------------------------

	def makeSettings(self, settingsSizer):
		helper = guiHelper.BoxSizerHelper(self, sizer=settingsSizer)

		# --- Speech / Announce ---
		helper.addItem(wx.StaticText(self, label=_("Speech and announce options:")))

		# Readable URL chunks
		self._readableMode = helper.addItem(
			wx.CheckBox(
				self,
				# Translators: Settings checkbox label
				label=_("Speak URL in readable chunks (Protocol, Domain, Path, Parameters)"),
			)
		)
		self._readableMode.SetValue(_cfg.data.get("readable_mode", False))

		# Include page title
		self._announceTitle = helper.addItem(
			wx.CheckBox(
				self,
				# Translators: Settings checkbox label
				label=_("Include page title when announcing URL"),
			)
		)
		self._announceTitle.SetValue(_cfg.data.get("announce_title", False))

		# Auto-announce on page load
		self._autoAnnounce = helper.addItem(
			wx.CheckBox(
				self,
				# Translators: Settings checkbox label
				label=_("Automatically announce URL each time a new page loads (browsers only)"),
			)
		)
		self._autoAnnounce.SetValue(_cfg.data.get("auto_announce", False))

		# --- Clipboard ---
		helper.addItem(wx.StaticText(self, label=_("Clipboard options:")))

		# Restore clipboard after reading
		self._restoreClip = helper.addItem(
			wx.CheckBox(
				self,
				# Translators: Settings checkbox label
				label=_("Restore clipboard content after reading the URL"),
			)
		)
		self._restoreClip.SetValue(_cfg.data.get("restore_clipboard", True))

		# --- History ---
		helper.addItem(wx.StaticText(self, label=_("URL history options:")))

		history_sizes   = ["5", "10", "20", "50"]
		# Translators: Label for history size drop-down
		self._historySize = helper.addLabeledControl(
			_("Maximum URLs to remember per session:"),
			wx.Choice,
			choices=history_sizes,
		)
		current_size = str(_cfg.data.get("history_size", 10))
		idx = history_sizes.index(current_size) if current_size in history_sizes else 1
		self._historySize.SetSelection(idx)

		# --- Safety ---
		helper.addItem(wx.StaticText(self, label=_("Security options:")))

		# Extended safety analysis
		self._safetyCheck = helper.addItem(
			wx.CheckBox(
				self,
				# Translators: Settings checkbox label
				label=_("Enable extended domain safety analysis"),
			)
		)
		self._safetyCheck.SetValue(_cfg.data.get("safety_check", False))

		# --- Updates ---
		helper.addItem(wx.StaticText(self, label=_("Update options:")))

		# Update check on startup
		self._updateCheck = helper.addItem(
			wx.CheckBox(
				self,
				# Translators: Settings checkbox label
				label=_("Check for URL Announcer updates when NVDA starts"),
			)
		)
		self._updateCheck.SetValue(_cfg.data.get("update_check", True))

	# ------------------------------------------------------------------
	# Save
	# ------------------------------------------------------------------

	def onSave(self):
		sizes = ["5", "10", "20", "50"]
		sel   = self._historySize.GetSelection()
		size  = int(sizes[sel]) if 0 <= sel < len(sizes) else 10

		_cfg.data.update({
			"readable_mode":     self._readableMode.IsChecked(),
			"announce_title":    self._announceTitle.IsChecked(),
			"auto_announce":     self._autoAnnounce.IsChecked(),
			"restore_clipboard": self._restoreClip.IsChecked(),
			"history_size":      size,
			"safety_check":      self._safetyCheck.IsChecked(),
			"update_check":      self._updateCheck.IsChecked(),
		})
		_cfg.save()

		# Resize the in-memory history deque if the setting changed
		try:
			from . import _history
			_history.resize(size)
		except Exception:
			pass
