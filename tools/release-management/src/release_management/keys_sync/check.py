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
"""Judge a fetched PUBLIC key against the ASF strength floor, and the KEYS directory.

Moved from ``keys-sync/scripts/check_key.py``. The key is no longer read here:
``release-verify list-keys --file <fetched.asc>`` lists it in a throwaway
GNUPGHOME and this module reads that JSON, so release-management still runs
nothing. ``assess`` is unchanged: RSA and DSA >= 2048 bits, EdDSA and ECDSA
on an accepted curve (secp256k1 refused), the DSA advisory, a revoked,
invalid or disabled key blocked, an expired key blocked, and an advisory for
an expiry within 90 days. ``keys_dir`` strips ``/KEYS`` from
``keys_file_url`` and rejects a ``dist/dev`` URL or one not ending in ``/KEYS``.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

ALGORITHMS = {"1": "RSA", "2": "RSA", "3": "RSA", "17": "DSA", "19": "ECDSA", "22": "EdDSA"}
EDDSA_CURVES = {"ed25519", "ed448"}
ECDSA_CURVES = {"nistp256", "nistp384", "nistp521", "brainpoolp256r1", "brainpoolp384r1", "brainpoolp512r1"}
FLOOR_BITS = 2048
UNUSABLE_VALIDITY = {
    "r": "key is revoked; generate a new key",
    "i": "key is invalid (gpg could not validate it); fix or replace the key",
    "d": "key is disabled",
}
EXPIRY_ADVISORY_DAYS = 90


class InputError(Exception):
    pass


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
    # gpg's validity field: a revoked, invalid or disabled key never signs a release,
    # whatever its strength or expiry date says.
    unusable = UNUSABLE_VALIDITY.get(key.get("validity", ""))
    if unusable:
        passed = False
        notes.append(unusable)
    if key["expiry"]:
        days = (dt.date.fromisoformat(key["expiry"]) - today).days
        if days < 0:
            passed = False
            notes.append(f"key expired on {key['expiry']}; extend its expiry or generate a new key")
        elif days <= EXPIRY_ADVISORY_DAYS:
            notes.append(
                f"key expires on {key['expiry']}, within {EXPIRY_ADVISORY_DAYS} days; consider extending it"
            )
    out["strength_check"] = "pass" if passed else "fail"
    out["strength_note"] = "; ".join(notes) if notes else None
    out["verdict"] = "proceed" if passed else "blocked"
    return out


def keys_dir(url: str) -> dict[str, Any]:
    url = url.strip()
    if "/dist/dev/" in url or url.rstrip("/").endswith("/dist/dev"):
        return {
            "svn_keys_dir_url": None,
            "error": "keys_file_url points at dist/dev; KEYS belongs in dist/release",
        }
    if not url.endswith("/KEYS"):
        return {"svn_keys_dir_url": None, "error": "keys_file_url does not end in /KEYS"}
    return {"svn_keys_dir_url": url[: -len("/KEYS")], "error": None}


def normalise_fpr(fpr: str) -> str:
    cleaned = "".join(fpr.split()).upper().removeprefix("0X")
    if len(cleaned) not in (40, 64) or any(c not in "0123456789ABCDEF" for c in cleaned):
        raise InputError(f"fingerprint {fpr!r} is not a 40- or 64-hex-character fingerprint")
    return cleaned


def listed_keys(listing: dict[str, Any] | None, what: str) -> list[dict[str, Any]]:
    """The `keys` of what `release-verify list-keys` printed; its `error` is surfaced, never read as no key."""
    if listing is None:
        return []
    if not isinstance(listing, dict) or "error" in listing:
        detail = listing.get("error") if isinstance(listing, dict) else listing
        raise InputError(f"{what}: release-verify list-keys failed: {detail}")
    keys = listing.get("keys")
    if listing.get("step") != "list-keys" or not isinstance(keys, list):
        raise InputError(f"{what} is not what `release-verify list-keys` prints")
    return [k for k in keys if isinstance(k, dict)]


def find_key(keys: list[dict[str, Any]], fingerprint: str, *, subkeys: bool = False) -> dict[str, Any] | None:
    """The key whose primary fingerprint is `fingerprint` (or, with `subkeys`, one of its subkeys')."""
    for key in keys:
        if str(key.get("fingerprint") or "").upper() == fingerprint:
            return key
    if subkeys:
        for key in keys:
            if fingerprint in [str(s).upper() for s in key.get("subkey_fingerprints") or []]:
                return key
    return None
