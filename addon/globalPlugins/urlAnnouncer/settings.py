# -*- coding: utf-8 -*-
# settings.py - NVDA settings panel for URL Announcer
# Tirupati Janardhan Gaikwad
# Accessible via NVDA Menu > Preferences > Settings > URL Announcer

import wx
import gui.settingsDialogs as settingsDialogs
from gui import guiHelper

from . import _cfg


class UrlAnnouncerSettingsPanel(settingsDialogs.SettingsPanel):
	title = _("URL Announcer")

	def makeSettings(self, settingsSizer):
		helper = guiHelper.BoxSizerHelper(self, sizer=settingsSizer)

		# Speech and announce
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

		# Command layer
		helper.addItem(wx.StaticText(self, label=_("Command layer options:")))

		self._announceLayerCmds = helper.addItem(wx.CheckBox(
			self,
			label=_(
				"Announce all commands when the layer is activated "
				"(uncheck for silent expert mode)"
			),
		))
		self._announceLayerCmds.SetValue(_cfg.data.get("announce_layer_commands", True))

		# URL action mode
		helper.addItem(wx.StaticText(self, label=_("URL action options:")))

		action_choices = [
			_("Announce URL only (speak the URL, do not copy)"),
			_("Copy to clipboard and announce URL"),
			_("Copy to clipboard silently, no speech"),
		]
		self._urlActionMode = helper.addLabeledControl(
			_("When A is pressed, URL Announcer should:"),
			wx.Choice,
			choices=action_choices,
		)
		mode_map = {"announce": 0, "copy_announce": 1, "copy": 2}
		self._urlActionMode.SetSelection(mode_map.get(_cfg.data.get("url_action_mode", "announce"), 0))

		# History
		helper.addItem(wx.StaticText(self, label=_("URL history options:")))

		history_sizes = ["5", "10", "20", "50"]
		self._historySize = helper.addLabeledControl(
			_("Maximum URLs to remember per session:"),
			wx.Choice,
			choices=history_sizes,
		)
		current_size = str(_cfg.data.get("history_size", 10))
		self._historySize.SetSelection(
			history_sizes.index(current_size) if current_size in history_sizes else 1
		)

		# Security and updates
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
		sizes      = ["5", "10", "20", "50"]
		sel        = self._historySize.GetSelection()
		size       = int(sizes[sel]) if 0 <= sel < len(sizes) else 10
		action_map = {0: "announce", 1: "copy_announce", 2: "copy"}
		action     = action_map.get(self._urlActionMode.GetSelection(), "announce")

		_cfg.data.update({
			"readable_mode":           self._readableMode.IsChecked(),
			"announce_title":          self._announceTitle.IsChecked(),
			"auto_announce":           self._autoAnnounce.IsChecked(),
			"announce_layer_commands": self._announceLayerCmds.IsChecked(),
			"url_action_mode":         action,
			"history_size":            size,
			"safety_check":            self._safetyCheck.IsChecked(),
			"update_check":            self._updateCheck.IsChecked(),
		})
		_cfg.save()

		# Apply new history size immediately without restarting NVDA.
		try:
			import sys
			pkg = sys.modules.get("globalPlugins.urlAnnouncer")
			if pkg is not None and hasattr(pkg, "_history"):
				pkg._history.resize(size)
		except Exception:
			pass
