"""Provenance stamp for every result JSON: git hash + input file hashes (detects stale outputs)."""

import datetime
import hashlib
import json
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:16]


def stamp(inputs):
    git = subprocess.run(["git", "-C", ROOT, "rev-parse", "--short", "HEAD"], capture_output=True, text=True)
    return {"git": git.stdout.strip() or "uncommitted", "generated": datetime.datetime.now().isoformat(timespec="seconds"),
            "inputs": {os.path.relpath(p, ROOT): _sha(p) for p in inputs}}


def write(name, payload, inputs):
    out = os.path.join(ROOT, "data", f"{name}.json")
    with open(out, "w") as f:
        json.dump({"_provenance": stamp(inputs), **payload}, f, indent=1)
    return out


def load_fresh(name):
    """Load data/<name>.json and raise if any input changed since it was written."""
    with open(os.path.join(ROOT, "data", f"{name}.json")) as f:
        d = json.load(f)
    for rel, h in d["_provenance"]["inputs"].items():
        if _sha(os.path.join(ROOT, rel)) != h:
            raise RuntimeError(f"data/{name}.json is stale: {rel} changed - rerun its generator")
    return d
