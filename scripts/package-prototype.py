#!/usr/bin/env python3
"""Compose a loopback-only PHP storage prototype from a fixed local Git object.

Does not fetch, execute upstream build scripts, issue sessions, or deploy anything.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def package(source: Path, output: Path, origin: str) -> Path:
    match = re.fullmatch(r"http://127\.0\.0\.1:([1-9][0-9]{0,4})", origin)
    if not match or not 1 <= int(match[1]) <= 65535:
        raise ValueError("Prototype requires an explicit http://127.0.0.1:PORT origin")
    lock = json.loads((ROOT / "upstream.lock.json").read_text())
    if not re.fullmatch(r"[a-f0-9]{40}", lock["commit"]) or lock["path"] != "apps/web/public/store.php":
        raise ValueError("Invalid upstream lock")
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    upstream = subprocess.run(
        ["git", "--no-optional-locks", "-C", str(source), "show", f"{lock['commit']}:{lock['path']}"],
        env=env, check=True, capture_output=True,
    ).stdout
    if hashlib.sha256(upstream).hexdigest() != lock["sha256"]:
        raise ValueError("Upstream hash differs from the reviewed lock")
    # Resolve ancestors but never follow/overwrite an existing destination.
    if output.exists() or output.is_symlink():
        raise ValueError("Output must not exist; existing runtime/data are never overwritten")
    output = output.parent.resolve(strict=True) / output.name
    output.mkdir(mode=0o700)
    private = output / "private"
    public = output / "public"
    for directory in [private, private / "src", private / "upstream", private / "projects", private / "sessions", public]:
        directory.mkdir(mode=0o700)
    for file in (ROOT / "src").glob("*.php"):
        shutil.copyfile(file, private / "src" / file.name)
    for name in ["store.php", "session.php"]:
        shutil.copyfile(ROOT / "public" / name, public / name)
    (private / "upstream" / "store.php").write_bytes(upstream)
    shutil.copyfile(ROOT / "upstream.lock.json", private / "upstream.lock.json")
    (private / "principals.json").write_text("{}\n")
    (private / "authorization.lock").touch(mode=0o600)
    (private / "audit.jsonl").touch(mode=0o600)
    (private / "config.json").write_text(json.dumps({
        "mode": "local-storage-prototype", "origin": origin,
        "authorizationModel": "prototype-fresh-evidence",
        "absoluteSeconds": 3600, "idleSeconds": 900,
        "privilegeEvidenceSeconds": 300,
        "groupIds": {"makerspace": None, "admins": None},
    }, indent=2) + "\n")
    manifest = {str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(output.rglob("*")) if p.is_file()}
    (private / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    for p in output.rglob("*"):
        if p.is_file():
            p.chmod(0o600)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--layerling", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--origin", default="http://127.0.0.1:8080")
    args = parser.parse_args()
    try:
        result = package(args.layerling, args.output, args.origin)
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"Packaging failed ({type(exc).__name__}); no deployment performed.\n")
    print(f"Local prototype: {result}")
    print("No sessions issued. Only public/ may be a document root. Not a deployable SSO release.")
