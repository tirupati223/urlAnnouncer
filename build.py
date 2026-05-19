# Build script — URL Announcer NVDA addon v3.0.0
# Output: C:\Temp\urlAnnouncer-3.0.0.nvda-addon
#
# Run with:  python build.py
# The .nvda-addon file is a standard ZIP with this structure:
#   manifest.ini
#   globalPlugins/urlAnnouncer/__init__.py
#   globalPlugins/urlAnnouncer/_cfg.py
#   globalPlugins/urlAnnouncer/urlutils.py
#   globalPlugins/urlAnnouncer/history.py
#   globalPlugins/urlAnnouncer/bookmarks.py
#   globalPlugins/urlAnnouncer/settings.py
#   globalPlugins/urlAnnouncer/updatecheck.py
#   doc/en/readme.html

import os
import sys
import zipfile

BASE  = os.path.dirname(os.path.abspath(__file__))
ADDON = os.path.join(BASE, "addon")        # ZIP root: globalPlugins/ and doc/ live here
MANI  = os.path.join(BASE, "manifest.ini")
OUT   = os.path.join("C:\\Temp", "urlAnnouncer-3.0.0.nvda-addon")

SKIP_DIRS  = {"__pycache__"}
SKIP_EXTS  = {".pyc", ".pyo"}


def build():
	os.makedirs(os.path.dirname(OUT), exist_ok=True)
	if os.path.exists(OUT):
		os.remove(OUT)

	with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zf:
		# manifest.ini at ZIP root
		zf.write(MANI, "manifest.ini")
		print("  + manifest.ini")

		# Walk addon/ — all paths become relative to addon/
		for root, dirs, files in os.walk(ADDON):
			dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
			for fname in sorted(files):
				if os.path.splitext(fname)[1] in SKIP_EXTS:
					continue
				full = os.path.join(root, fname)
				arc  = os.path.relpath(full, ADDON).replace("\\", "/")
				zf.write(full, arc)
				print("  +", arc)

	print("\n=== ZIP contents ===")
	with zipfile.ZipFile(OUT) as zf:
		for info in zf.infolist():
			print("  {:50s}  {:>8,} bytes".format(info.filename, info.file_size))

	total = os.path.getsize(OUT)
	print("\nTotal size: {:,} bytes".format(total))
	print("Output:     ", OUT)
	return OUT


if __name__ == "__main__":
	out = build()
	print("\nDone. Install by double-clicking:", out)
