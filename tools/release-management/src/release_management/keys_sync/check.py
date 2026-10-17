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
an expiry within 90 days. The verdict also needs a usable signing-capable
key: a primary key without the sign capability (certify only) needs a
compliant signing subkey, and a signing subkey only counts when it meets the
same floor, validity and expiry rules on its own; the compliant ones are
listed under ``signers``. A listing without capabilities (``caps``) keeps the
primary key as the signer. ``keys_dir`` strips ``/KEYS`` from
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


def _meets_strength(key: dict[str, Any]) -> tuple[bool, str | None]:
    """The per-key rules: the algorithm / size floor and the accepted curves."""
    algorithm = ALGORITHMS.get(str(key.get("algo_id")))
    if algorithm in ("RSA", "DSA"):
        bits = key.get("bits")
        if bits is None or bits < FLOOR_BITS:
            return False, (
                f"{algorithm} {bits}-bit key is below the ASF floor of {FLOOR_BITS} bits; "
                "generate a new key that meets the floor"
            )
        return True, None
    curve = key.get("curve") or ""
    if algorithm == "EdDSA":
        if curve in EDDSA_CURVES:
            return True, None
        return False, f"EdDSA curve {curve or 'unknown'!r} is not an accepted curve"
    if algorithm == "ECDSA":
        if curve in ECDSA_CURVES:
            return True, None
        return False, f"ECDSA curve {curve or 'unknown'!r} is not P-256 or stronger"
    return False, f"public-key algorithm id {key.get('algo_id')} is not accepted for release signing"


def _usable_for_signing(key: dict[str, Any], today: dt.date) -> bool:
    if UNUSABLE_VALIDITY.get(key.get("validity") or ""):
        return False
    if key.get("expiry"):
        return dt.date.fromisoformat(key["expiry"]) >= today
    return True


def _signer_summary(key: dict[str, Any], source: str) -> dict[str, Any]:
    return {
        "source": source,
        "algorithm": ALGORITHMS.get(str(key.get("algo_id"))),
        "bit_length": key.get("bits"),
        "curve": key.get("curve") or None,
        "expiry": key.get("expiry"),
    }


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
        "signers": [],
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
    passed, primary_note = _meets_strength(key)
    if algorithm in ("RSA", "DSA"):
        out["bit_length"] = key["bits"]
    if algorithm == "DSA":
        notes.append("DSA keys are discouraged by ASF release-signing guidance")
    if primary_note:
        notes.append(primary_note)
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
    # A release needs a usable, strength-compliant SIGNER. gpg's capability field
    # (`caps`): lowercase letters are the key's own usage, uppercase the whole key's,
    # so a certify-only primary reads e.g. `cSC` and must not count as a signer.
    # A listing without `caps` keeps the primary as the signer.
    caps = str(key.get("caps") or "")
    if caps and "s" not in caps:
        notes.append("primary key has no signing capability (certify only)")
    elif passed:
        out["signers"].append(_signer_summary(key, "primary"))
    for sub in key.get("subkeys") or []:
        if not isinstance(sub, dict) or "s" not in str(sub.get("caps") or ""):
            continue
        sub_ok, sub_note = _meets_strength(sub)
        if sub_note:
            notes.append(f"signing subkey: {sub_note}")
        if not (sub_ok and _usable_for_signing(sub, today)):
            continue
        out["signers"].append(_signer_summary(sub, "subkey"))
        if ALGORITHMS.get(str(sub.get("algo_id"))) == "DSA":
            notes.append("signing subkey: DSA keys are discouraged by ASF release-signing guidance")
        if sub.get("expiry"):
            sub_days = (dt.date.fromisoformat(sub["expiry"]) - today).days
            if sub_days <= EXPIRY_ADVISORY_DAYS:
                notes.append(
                    f"signing subkey expires on {sub['expiry']}, within {EXPIRY_ADVISORY_DAYS} days; "
                    "consider extending it"
                )
    if not out["signers"]:
        passed = False
        notes.append(
            "no signing-capable key meets the admission rules; "
            "a release signature from this key group would not be a checked signer"
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
