"""Validate a version tag and ensure it belongs to the main branch history."""

import argparse
import subprocess

from anna import __version__

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("tag")
args = parser.parse_args()
if args.tag != f"v{__version__}":
    raise SystemExit(f"Tag must be v{__version__}")
subprocess.run(["git", "merge-base", "--is-ancestor", "HEAD", "origin/main"], check=True)
print(f"Validated {args.tag}")
