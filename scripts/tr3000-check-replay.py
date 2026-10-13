#!/usr/bin/env python3
"""Replay the complete local adaptation series onto the immutable release tag."""
import json
import pathlib
import subprocess
import sys

source = pathlib.Path(sys.argv[1]).resolve()
destination = pathlib.Path(sys.argv[2]).resolve()
report = pathlib.Path(sys.argv[3]).resolve()
if destination.exists():
    sys.exit("Replay destination must not exist; existing checkouts are never overwritten")
report.parent.mkdir(parents=True, exist_ok=True)
git = ["git", "-c", f"safe.directory={source}", "-C", str(source)]


def read(args):
    return subprocess.check_output(args, text=True).strip()


base = read(git + ["rev-parse", "v25.12.2^{commit}"])
if base != "4fc16f2985a358bd43bb522e43f05395fcbd6ed5":
    sys.exit("Unexpected release base")
tip = read(git + ["rev-parse", "HEAD"])
subprocess.run(git + ["merge-base", "--is-ancestor", base, tip], check=True)
if read(git + ["rev-list", "--min-parents=2", f"{base}..{tip}"]):
    sys.exit("Adaptation series contains merges; explicit replay review required")
commits = read(git + ["rev-list", "--reverse", f"{base}..{tip}"]).splitlines()
if not commits:
    sys.exit("No adaptation commits to replay")
with report.with_suffix(".log").open("w") as log:
    def run(args, **kwargs):
        subprocess.run(args, stdout=log, stderr=subprocess.STDOUT, check=True, **kwargs)

    run(["git", "-c", f"safe.directory={source}", "clone", "--no-checkout",
         "--no-hardlinks", str(source), str(destination)])
    replay = ["git", "-C", str(destination)]
    run(replay + ["config", "core.autocrlf", "false"])
    run(replay + ["config", "core.eol", "lf"])
    run(replay + ["config", "user.name", "TR3000 replay validation"])
    run(replay + ["config", "user.email", "replay@localhost"])
    run(replay + ["checkout", "--detach", base])
    run(replay + ["cherry-pick", "--stdin"], input="\n".join(commits) + "\n", text=True)
    expected_tree = read(git + ["rev-parse", f"{tip}^{{tree}}"])
    actual_tree = read(replay + ["rev-parse", "HEAD^{tree}"])
    if actual_tree != expected_tree:
        sys.exit("Replayed tree differs from maintained source")
    if read(replay + ["status", "--porcelain"]):
        sys.exit("Replay checkout is not clean")
    result = {"status": "passed", "base": base, "source_commit": tip,
              "replayed_commit": read(replay + ["rev-parse", "HEAD"]),
              "tree": actual_tree, "commit_count": len(commits), "commits": commits}
    report.write_text(json.dumps(result, indent=2) + "\n")
    print(f"Replayed {len(commits)} commits; tree identity and clean checkout verified: {report}")
