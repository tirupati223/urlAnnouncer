# URL Announcer - NVDA Add-on

I made this add-on because I personally faced difficulty knowing what URL was open in the browser while using NVDA. Switching to the address bar, reading it, and coming back broke my workflow every time. So I built URL Announcer - press one shortcut, hear the URL instantly, and stay exactly where you were.

---

## About Me

<table>
<tr>
<td><img src="assets/tirupati_photo.png" alt="Tirupati Janardhan Gaikwad" width="110" style="border-radius:8px;"/></td>
<td>

**Tirupati Janardhan Gaikwad**
Email: ytirupatiygaikwad@gmail.com
Phone: +91 99757 32046

</td>
<td>

<a href="https://certification.nvaccess.org/?query=tirupati&country=IN&submit=Search">
<img src="assets/nvda-certified-expert-2025.svg" alt="NVDA Certified Expert 2025" width="180"/>
</a>

[Verify my NVDA Certification](https://certification.nvaccess.org/?query=tirupati&country=IN&submit=Search)

</td>
</tr>
</table>

---

## Download

Get it from the [Releases page](https://github.com/tirupati223/urlAnnouncer/releases).

---

## How it works

Press **NVDA+Shift+U** to open the command layer. NVDA speaks the available commands. Then press one letter:

| Key | What it does |
|-----|-------------|
| A | Speak the current URL |
| C | Copy URL to clipboard |
| S | Copy share link (YouTube links become short youtu.be links) |
| X | Quick security check - HTTPS or not |
| W | Share menu - WhatsApp, Facebook, Telegram, Gmail, Twitter, LinkedIn |
| R | Browse URL history for this session |
| M | Save the current URL as a bookmark |
| B | Browse saved bookmarks |
| L | Shorten URL using TinyURL |
| T | Hear the page title and URL together |
| E | Open email client with URL in the body |
| O | Choose which browser to open the URL in |
| P | Read URL from clipboard |
| D | Full domain safety check |
| Q | Generate QR code for the URL |
| H | Hear all commands again |
| Escape | Cancel |

The add-on reads the URL using Windows UI Automation so your focus never moves to the address bar, no keys are pressed in the browser, and your clipboard is never touched unless you ask.

---

## Settings

Go to **NVDA Menu > Preferences > Settings > URL Announcer**

Options include readable URL mode, auto-announce on page load, history size, what A does (announce only, copy and announce, or copy silently), and more.

---

## Supported Browsers

Chrome, Edge, Firefox, Opera, Brave, Vivaldi, Internet Explorer, Waterfox, SeaMonkey, Pale Moon.

---

## Installing

1. Download the .nvda-addon file from [Releases](https://github.com/tirupati223/urlAnnouncer/releases)
2. Double-click it
3. Click Yes when NVDA asks
4. Restart NVDA
5. Open any browser and press NVDA+Shift+U

---

## Requirements

NVDA 2019.3 or later. Tested on NVDA 2025.3.

---

## License

GPL-2.0
