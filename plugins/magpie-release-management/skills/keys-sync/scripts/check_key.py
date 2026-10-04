#!/usr/bin/env python3
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
"""Validate a fetched PUBLIC key against the ASF strength floor.

Key mode (Step 1)::

    check_key.py --key-file <fetched.asc> --fingerprint <FPR> [--today YYYY-MM-DD]

The key file is imported into a throw-away ``GNUPGHOME`` created for this
run and deleted afterwards — never the user's keyring — and read back with
``gpg --with-colons``. An empty file, a file with no key, or a key whose
fingerprint differs from ``--fingerprint`` means ``key_found: false``.
Prints the Step 1 JSON: algorithm / size floor (RSA and DSA >= 2048 bits,
EdDSA and ECDSA on an accepted curve; secp256k1 is refused), the DSA
advisory, and the advisory for an expiry within 90 days. A key that has
already expired is a blocker, like a sub-floor key.

KEYS-directory mode (Step 2)::

    check_key.py --keys-url <keys_file_url>

Derives the svn directory to check out by stripping ``/KEYS``; rejects a
URL under ``dist/dev`` and one that does not end in ``/KEYS``. Commands stay with the Release Manager; this script
never contacts a keyserver or a repository.

Exit 0 on success, 2 on bad input or when gpg is unavailable.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ALGORITHMS = {"1": "RSA", "2": "RSA", "3": "RSA", "17": "DSA", "19": "ECDSA", "22": "EdDSA"}
EDDSA_CURVES = {"ed25519", "ed448"}
ECDSA_CURVES = {"nistp256", "nistp384", "nistp521", "brainpoolp256r1", "brainpoolp384r1", "brainpoolp512r1"}
FLOOR_BITS = 2048
EXPIRY_ADVISORY_DAYS = 90


class InputError(Exception):
    pass


def _date(epoch: str) -> str | None:
    if not epoch:
        return None
    if "T" in epoch:  # ISO form some gpg builds print
        return f"{epoch[0:4]}-{epoch[4:6]}-{epoch[6:8]}"
    return dt.datetime.fromtimestamp(int(epoch), dt.timezone.utc).date().isoformat()


def parse_colons(text: str) -> list[dict[str, Any]]:
    """Primary keys from ``gpg --with-colons --fixed-list-mode`` output."""
    keys: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    want_fpr = False
    for line in text.splitlines():
        f = line.split(":") + [""] * 20
        kind = f[0]
        if kind == "pub":
            current = {
                "algo_id": f[3],
                "bits": int(f[2]) if f[2].isdigit() else None,
                "created": _date(f[5]),
                "expiry": _date(f[6]),
                "curve": f[16].lower(),
                "fingerprint": None,
                "uids": [],
            }
            keys.append(current)
            want_fpr = True
        elif kind == "fpr" and current is not None and want_fpr:
            current["fingerprint"] = f[9].upper()
            want_fpr = False
        elif kind == "sub":
            want_fpr = False
        elif kind == "uid" and current is not None and f[1] not in ("r", "e"):
            current["uids"].append(f[9])
    return keys


def assess(key: dict[str, Any] | None, fingerprint: str, today: dt.date) -> dict[str, Any]:
    out: dict[str, Any] = {
        "verdict": "blocked",
        "key_found": key is not None,
        "fingerprint": fingerprint,
        "uid": None,
        "algorithm": None,
        "bit_length": None,
        "created": None,
        "expiry": None,
        "strength_check": None,
        "strength_note": None,
    }
    if key is None:
        return out
    algorithm = ALGORITHMS.get(key["algo_id"])
    out.update(
        uid=key["uids"][0] if key["uids"] else None,
        algorithm=algorithm,
        created=key["created"],
        expiry=key["expiry"],
    )
    notes: list[str] = []
    passed = False
    if algorithm in ("RSA", "DSA"):
        bits = key["bits"]
        out["bit_length"] = bits
        passed = bits is not None and bits >= FLOOR_BITS
        if not passed:
            notes.append(
                f"{algorithm} {bits}-bit key is below the ASF floor of {FLOOR_BITS} bits; "
                "generate a new key that meets the floor"
            )
        if algorithm == "DSA":
            notes.append("DSA keys are discouraged by ASF release-signing guidance")
    elif algorithm == "EdDSA":
        passed = key["curve"] in EDDSA_CURVES
        if not passed:
            notes.append(f"EdDSA curve {key['curve'] or 'unknown'!r} is not an accepted curve")
    elif algorithm == "ECDSA":
        passed = key["curve"] in ECDSA_CURVES
        if not passed:
            notes.append(f"ECDSA curve {key['curve'] or 'unknown'!r} is not P-256 or stronger")
    else:
        notes.append(f"public-key algorithm id {key['algo_id']} is not accepted for release signing")
    if key["expiry"]:
        days = (dt.date.fromisoformat(key["expiry"]) - today).days
        if days < 0:
            passed = False
            notes.append(f"key expired on {key['expiry']}; extend its expiry or generate a new key")
        elif days <= EXPIRY_ADVISORY_DAYS:
            notes.append(f"key expires on {key['expiry']}, within {EXPIRY_ADVISORY_DAYS} days; consider extending it")
    out["strength_check"] = "pass" if passed else "fail"
    out["strength_note"] = "; ".join(notes) if notes else None
    out["verdict"] = "proceed" if passed else "blocked"
    return out


def list_key_file(path: Path) -> str:
    gpg = shutil.which("gpg")
    if not gpg:
        raise InputError("gpg not found on PATH")
    home = tempfile.mkdtemp(prefix="keys-sync-")
    try:
        os.chmod(home, 0o700)
        base = [gpg, "--homedir", home, "--batch", "--no-autostart", "--no-tty"]
        subprocess.run([*base, "--import", str(path)], capture_output=True, check=False)
        listing = subprocess.run(
            [*base, "--with-colons", "--fixed-list-mode", "--list-keys"],
            capture_output=True,
            text=True,
            check=False,
        )
        return listing.stdout
    finally:
        shutil.rmtree(home, ignore_errors=True)


def keys_dir(url: str) -> dict[str, Any]:
    url = url.strip()
    if "/dist/dev/" in url or url.rstrip("/").endswith("/dist/dev"):
        return {"svn_keys_dir_url": None, "error": "keys_file_url points at dist/dev; KEYS belongs in dist/release"}
    if not url.endswith("/KEYS"):
        return {"svn_keys_dir_url": None, "error": "keys_file_url does not end in /KEYS"}
    return {"svn_keys_dir_url": url[: -len("/KEYS")], "error": None}


def normalise_fpr(fpr: str) -> str:
    cleaned = "".join(fpr.split()).upper().removeprefix("0X")
    if len(cleaned) not in (40, 64) or any(c not in "0123456789ABCDEF" for c in cleaned):
        raise InputError(f"fingerprint {fpr!r} is not a 40- or 64-hex-character fingerprint")
    return cleaned


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--key-file", help="fetched public key (armoured or binary); may be empty")
    parser.add_argument("--fingerprint")
    parser.add_argument("--today", help="YYYY-MM-DD; defaults to the current UTC date")
    parser.add_argument("--keys-url", help="keys_file_url, for the KEYS-directory mode")
    parser.add_argument("--colons-file", help=argparse.SUPPRESS)  # tests: pre-captured gpg listing
    args = parser.parse_args(argv)
    try:
        if args.keys_url and not (args.key_file or args.colons_file):
            print(json.dumps(keys_dir(args.keys_url), indent=2))
            return 0
        if not args.fingerprint or not (args.key_file or args.colons_file):
            raise InputError("key mode needs --fingerprint and --key-file")
        fpr = normalise_fpr(args.fingerprint)
        today = dt.date.fromisoformat(args.today) if args.today else dt.datetime.now(dt.timezone.utc).date()
        if args.colons_file:
            colons = Path(args.colons_file).read_text(encoding="utf-8")
        else:
            path = Path(args.key_file)
            colons = list_key_file(path) if path.stat().st_size else ""
        match = next((k for k in parse_colons(colons) if k["fingerprint"] == fpr), None)
        out = assess(match, fpr, today)
    except (InputError, OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}))
        return 2
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
