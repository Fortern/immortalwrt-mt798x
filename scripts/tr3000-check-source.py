#!/usr/bin/env python3
"""Check the tracked TR3000 changes without rewriting files."""
import pathlib
import hashlib
import json
import os
import subprocess
import sys

root = pathlib.Path(__file__).resolve().parents[1]
os.environ["GIT_OPTIONAL_LOCKS"] = "0"
git = ["git", "-c", f"safe.directory={root}", "-C", str(root)]
base = subprocess.check_output(git + ["rev-parse", "v25.12.2^{commit}"], text=True).strip()
if base != "4fc16f2985a358bd43bb522e43f05395fcbd6ed5":
    sys.exit(f"Unexpected release commit: {base}")
subprocess.run(git + ["merge-base", "--is-ancestor", base, "HEAD"], check=True)
names = subprocess.check_output(git + ["diff", "--no-renames", "--name-only", "--diff-filter=ACMR", "-z", base])
attr_result = subprocess.run(git + ["check-attr", "-z", "--stdin", "text"], input=names,
                             stdout=subprocess.PIPE, check=True).stdout.split(b"\0")
text_attrs = {attr_result[i].decode(): attr_result[i + 2] for i in range(0, len(attr_result) - 1, 3)}
errors = []
for raw_name in names.split(b"\0"):
    if not raw_name:
        continue
    name = raw_name.decode()
    path = root / name
    if path.is_symlink():
        continue
    data = path.read_bytes()
    if text_attrs.get(name) == b"unset" or b"\0" in data:
        continue
    if b"\r\n" in data:
        errors.append(f"CRLF in text file: {name}")
for script in ("scripts/tr3000-build.sh",):
    mode = subprocess.check_output(git + ["ls-files", "-s", "--", script], text=True)
    if not mode.startswith("100755 "):
        errors.append(f"Executable bit missing: {script}")
expected_feeds = subprocess.check_output(git + ["show", f"{base}:feeds.conf.default"])
if (root / "feeds.conf.default").read_bytes() != expected_feeds:
    errors.append("Release feed locks changed")
manifest = json.loads((root / "docs/tr3000/vendor-import.json").read_text())
for entry in manifest["files"]:
    if entry["binary"]:
        path = root / entry["path"]
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != entry["source_sha256"]:
            errors.append(f"Imported binary changed: {entry['path']}")
datconf = root / "package/mtk/applications/datconf/datconf-6bb733f7.tar.bz2"
if hashlib.sha256(datconf.read_bytes()).hexdigest() != "c1632b1950407e731c8a36b14d50d6e04bed7e7218938283e06e16ac9050d20b":
    errors.append("Bundled datconf archive changed")
if errors:
    sys.exit("\n".join(errors))
print("Release ancestry, changed text LF, script mode, feed locks and imported binary hashes verified.")
