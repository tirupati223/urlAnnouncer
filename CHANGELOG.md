# Changelog

## v3.0.0 - May 2026

This is the first public release. I built this from scratch after personally struggling with getting the URL of the current page in NVDA without losing my place on the page.

What is included:

- NVDA+Shift+U opens a command layer with 16 commands
- A: speak the URL, C: copy it, S: copy a share link
- YouTube URLs are automatically converted to short youtu.be links when you press S
- W opens a share menu with WhatsApp, Facebook, Telegram, Gmail, Twitter and LinkedIn
- R shows your URL history for the session
- M saves the current URL as a named bookmark, B opens your bookmarks
- L shortens the URL with TinyURL
- T speaks the page title along with the URL
- E opens your email with the URL ready in the body
- O lets you pick which browser to open the URL in
- P reads a URL from the clipboard
- X gives a quick security check (HTTPS or plain HTTP)
- D runs a deeper check on the domain for phishing signs
- Q generates a QR code and opens it in the browser
- H repeats all commands, Escape closes the layer
- Settings panel in NVDA Preferences with options for readable URL mode, auto-announce, history size, action mode, and more
- Works with Chrome, Edge, Firefox, Opera, Brave, Vivaldi and others
- URL is read silently via Windows UI Automation - focus never moves to the address bar
- Layer closes automatically after 30 seconds if you forget to press Escape
- Tested on NVDA 2025.3, compatible back to 2019.3
