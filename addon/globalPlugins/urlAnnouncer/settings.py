# -*- coding: utf-8 -*-
# URL Announcer — NVDA Settings Panel
# NVDA Menu → Preferences → Settings → URL Announcer

import wx
import gui
import gui.settingsDialogs as settingsDialogs
from gui import guiHelper
import addonHandler

from . import _cfg


class UrlAnnouncerSettingsPanel(settingsDialogs.SettingsPanel):
	title = _("URL Announcer")

	def makeSettings(self, settingsSizer):
		helper = guiHelper.BoxSizerHelper(self, sizer=settingsSizer)

		# ── Speech & Announce ──────────────────────────────────────────
		helper.addItem(wx.StaticText(self, label=_("Speech and announce options:")))

		self._readableMode = helper.addItem(wx.CheckBox(
			self,
			label=_("Speak URL in readable chunks (Protocol, Domain, Path, Parameters)"),
		))
		self._readableMode.SetValue(_cfg.data.get("readable_mode", False))

		self._announceTitle = helper.addItem(wx.CheckBox(
			self,
			label=_("Include page title when announcing URL"),
		))
		self._announceTitle.SetValue(_cfg.data.get("announce_title", False))

		self._autoAnnounce = helper.addItem(wx.CheckBox(
			self,
			label=_("Automatically announce URL each time a new page loads"),
		))
		self._autoAnnounce.SetValue(_cfg.data.get("auto_announce", False))

		# ── Command Layer ──────────────────────────────────────────────
		helper.addItem(wx.StaticText(self, label=_("Command layer options:")))

		self._announceLayerCmds = helper.addItem(wx.CheckBox(
			self,
			label=_(
				"Announce all commands when layer is activated "
				"(uncheck for silent / expert mode — just press the letter you want)"
			),
		))
		self._announceLayerCmds.SetValue(_cfg.data.get("announce_layer_commands", True))

		# ── URL Action Mode ────────────────────────────────────────────
		helper.addItem(wx.StaticText(self, label=_("URL action options:")))

		action_choices = [
			_("Announce URL only (speak the URL, do not copy)"),
			_("Copy to clipboard and announce URL"),
			_("Copy to clipboard silently (no speech)"),
		]
		self._urlActionMode = helper.addLabeledControl(
			_("When A is pressed, URL Announcer should:"),
			wx.Choice,
			choices=action_choices,
		)
		mode_map = {"announce": 0, "copy_announce": 1, "copy": 2}
		current   = _cfg.data.get("url_action_mode", "announce")
		self._urlActionMode.SetSelection(mode_map.get(current, 0))

		# ── Clipboard ──────────────────────────────────────────────────
		helper.addItem(wx.StaticText(self, label=_("Clipboard options:")))

		self._restoreClip = helper.addItem(wx.CheckBox(
			self,
			label=_("Restore clipboard content after reading the URL"),
		))
		self._restoreClip.SetValue(_cfg.data.get("restore_clipboard", True))

		# ── History ────────────────────────────────────────────────────
		helper.addItem(wx.StaticText(self, label=_("URL history options:")))

		history_sizes = ["5", "10", "20", "50"]
		self._historySize = helper.addLabeledControl(
			_("Maximum URLs to remember per session:"),
			wx.Choice,
			choices=history_sizes,
		)
		current_size = str(_cfg.data.get("history_size", 10))
		idx = history_sizes.index(current_size) if current_size in history_sizes else 1
		self._historySize.SetSelection(idx)

		# ── Security / Updates ─────────────────────────────────────────
		helper.addItem(wx.StaticText(self, label=_("Security and update options:")))

		self._safetyCheck = helper.addItem(wx.CheckBox(
			self,
			label=_("Enable extended domain safety analysis"),
		))
		self._safetyCheck.SetValue(_cfg.data.get("safety_check", False))

		self._updateCheck = helper.addItem(wx.CheckBox(
			self,
			label=_("Check for URL Announcer updates when NVDA starts"),
		))
		self._updateCheck.SetValue(_cfg.data.get("update_check", True))

	def onSave(self):
		sizes    = ["5", "10", "20", "50"]
		sel      = self._historySize.GetSelection()
		size     = int(sizes[sel]) if 0 <= sel < len(sizes) else 10

		action_map = {0: "announce", 1: "copy_announce", 2: "copy"}
		action_sel = self._urlActionMode.GetSelection()
		action     = action_map.get(action_sel, "announce")

		_cfg.data.update({
			"readable_mode":           self._readableMode.IsChecked(),
			"announce_title":          self._announceTitle.IsChecked(),
			"auto_announce":           self._autoAnnounce.IsChecked(),
			"announce_layer_commands": self._announceLayerCmds.IsChecked(),
			"url_action_mode":         action,
			"restore_clipboard":       self._restoreClip.IsChecked(),
			"history_size":            size,
			"safety_check":            self._safetyCheck.IsChecked(),
			"update_check":            self._updateCheck.IsChecked(),
		})
		_cfg.save()

		# Resize live history deque immediately (no restart needed)
		try:
			import sys
			pkg = sys.modules.get("globalPlugins.urlAnnouncer")
			if pkg is not None and hasattr(pkg, "_history"):
				pkg._history.resize(size)
		except Exception:
			pass
