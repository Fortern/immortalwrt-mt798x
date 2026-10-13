#!/usr/bin/env python3
"""Fetch release-pinned feeds directly, preserving feeds.conf.default."""
import concurrent.futures
import pathlib
import re
import subprocess


def prepare(entry):
    name, url, commit = entry
    directory = pathlib.Path("feeds") / name
    if not (directory / ".git").is_dir():
        if directory.exists() and any(directory.iterdir()):
            raise RuntimeError(f"Refusing to replace non-Git feed {directory}")
        directory.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init", str(directory)], check=True)
        subprocess.run(["git", "-C", str(directory), "remote", "add", "origin", url], check=True)
    git = ["git", "-C", str(directory)]
    if subprocess.check_output(git + ["status", "--porcelain"]).strip():
        raise RuntimeError(f"Feed {name} contains local changes")
    available = subprocess.run(git + ["cat-file", "-e", f"{commit}^{{commit}}"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if available.returncode:
        for attempt in range(3):
            result = subprocess.run(git + ["-c", "http.version=HTTP/1.1", "fetch",
                                           "--depth=1", "--filter=blob:none", "--no-tags", url, commit])
            if result.returncode == 0:
                break
        result.check_returncode()
    if name == "luci":
        # Third-party applications embed large databases unrelated to this image.
        # Keep the release commit unchanged and materialize the official UI set.
        subprocess.run(git + ["sparse-checkout", "init", "--cone"], check=True)
        subprocess.run(git + ["sparse-checkout", "set", "build", "collections", "contrib/package", "libs",
                              "modules", "protocols", "themes", "applications/luci-app-firewall",
                              "applications/luci-app-package-manager", "applications/luci-app-opkg"],
                       check=True)
    subprocess.run(git + ["-c", "advice.detachedHead=false", "checkout", "--detach", commit], check=True)
    actual = subprocess.check_output(git + ["rev-parse", "HEAD"], text=True).strip()
    if actual != commit:
        raise RuntimeError(f"Unexpected revision for {name}: {actual}")
    subprocess.run(git + ["submodule", "update", "--init", "--recursive", "--depth=1"], check=True)
    print(f"Verified feed {name}: {actual}", flush=True)


entries = []
for line in pathlib.Path("feeds.conf.default").read_text().splitlines():
    if not line.strip() or line.lstrip().startswith("#"):
        continue
    match = re.fullmatch(r"src-git\s+([\w-]+)\s+(https://[^\s^]+)\^([0-9a-f]{40})", line)
    if not match:
        raise RuntimeError(f"Expected an immutable release feed: {line}")
    entries.append(match.groups())
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
    list(executor.map(prepare, entries))
