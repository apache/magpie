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
"""release-keys-sync: the Step 0 KEYS lookup, the Step 1 strength floor and the Step 2 render.

The strength-floor cases moved here from `keys-sync/tests/test_check_key.py`
(the gpg listing they exercised is now `release-verify list-keys`, tested in
tools/release-verify). The scripted cases of the retired model-graded suites
`step-0-preflight` (cases 2-3), `step-1-key-fetch` (cases 1-3) and
`step-2-svn-commands` (cases 1 and 3) live here, named after each former case,
with the same scenario and the same assertions.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import Any

import pytest

from release_management.cli import main
from release_management.keys_sync import check, render

FPR = "A1B2C3D4E5F6A1B2C3D4E5F6A1B2C3D4E5F6ABCD"
TODAY = dt.date(2026, 6, 19)
UID = "Brendan Ngan <bngan@apache.org>"
KEYS_URL = "https://dist.apache.org/repos/dist/release/airflow/KEYS"
BLOCK = "-----BEGIN PGP PUBLIC KEY BLOCK-----\n\nmQINBGIx...ABCD\n=xYzW\n-----END PGP PUBLIC KEY BLOCK-----"

# The step-2-svn-commands assertions, verbatim.
ASSERT = {
    "has_pgp_begin_header": ("keys_block_to_append", "-----BEGIN PGP PUBLIC KEY BLOCK-----", 0),
    "has_pgp_end_footer": ("keys_block_to_append", "-----END PGP PUBLIC KEY BLOCK-----", 0),
    "has_uid_comment": ("keys_block_to_append", "^# .+@", re.M),
    "has_checkout_command": ("svn_command_sequence", "svn checkout|git checkout|git clone", re.I),
    "has_commit_command": ("svn_command_sequence", "svn commit|git commit|git push", re.I),
    "has_expiry_warning": (
        "keyserver_upload_reminder",
        r"expir\w*\s+(on|in|within|by)|in\s+\d+\s+days?|extend\w*\s+the\s+key|renew\w*\s+the\s+key|before\s+\w+\s+expir",
        re.I,
    ),
}


def holds(out: dict[str, Any], name: str) -> bool:
    field, pattern, flags = ASSERT[name]
    return re.search(pattern, out[field], flags) is not None


def key(
    algo: str = "1",
    bits: int | None = 4096,
    curve: str = "",
    expiry: str | None = None,
    fpr: str = FPR,
    validity: str = "-",
    uids: list[str] | None = None,
    created: str = "2022-03-15",
) -> dict[str, Any]:
    """One key as `release-verify list-keys` prints it."""
    return {
        "fingerprint": fpr,
        "validity": validity,
        "algo_id": algo,
        "algorithm": check.ALGORITHMS.get(algo),
        "bits": bits,
        "curve": curve,
        "created": created,
        "expiry": expiry,
        "uids": [UID] if uids is None else uids,
        "subkey_fingerprints": ["FFFF0000FFFF0000FFFF0000FFFF0000FFFF0000"],
    }


def listing(*keys: dict[str, Any], file: str = "fetched.asc") -> dict[str, Any]:
    return {"step": "list-keys", "file": file, "keys": list(keys)}


FETCHED = listing(key())  # `release-verify list-keys` of the fetched key file


def assess(k: dict[str, Any], fpr: str = FPR) -> dict[str, Any]:
    return check.assess(check.find_key([k], fpr), fpr, TODAY)


def preflight(blockers: list[str] | None = None, keys_url: str = KEYS_URL) -> dict[str, Any]:
    return {
        "ok": not blockers,
        "skill": "keys-sync",
        "blockers": blockers or [],
        "warnings": [],
        "values": {
            "fingerprint": FPR,
            "fingerprint_source": "release-management-config.md rm_key_fingerprint",
            "keys_file_url": keys_url,
            "keyserver": "keys.openpgp.org",
        },
    }


def loaded(name: str = "airflow", backend: str = "svnpubsub") -> dict[str, Any]:
    return {"config": {"project_dist_name": name, "release_dist_backend": backend}}


def step1(**over: Any) -> dict[str, Any]:
    return assess(key(**over))


def run(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, dict[str, Any]]:
    code = main(["keys-sync", *argv])
    return code, json.loads(capsys.readouterr().out)


def save(tmp_path: Path, name: str, data: Any) -> str:
    path = tmp_path / name
    path.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
    return str(path)


# --------------------------------------------------------------------------- Step 1 strength floor


class TestAssess:
    def test_rsa_4096_passes(self) -> None:
        out = assess(key())
        assert out["verdict"] == "proceed"
        assert (out["algorithm"], out["bit_length"]) == ("RSA", 4096)
        assert out["uid"] == UID and out["created"] == "2022-03-15"
        assert out["expiry"] is None and out["strength_note"] is None

    def test_rsa_1024_fails(self) -> None:
        out = assess(key(bits=1024))
        assert (out["verdict"], out["strength_check"]) == ("blocked", "fail")
        assert "1024" in out["strength_note"] and "2048" in out["strength_note"]

    def test_dsa_2048_passes_with_advisory(self) -> None:
        out = assess(key("17", 2048))
        assert out["strength_check"] == "pass" and "DSA" in out["strength_note"]

    def test_ed25519_passes_without_bit_length(self) -> None:
        out = assess(key("22", 255, "ed25519"))
        assert (out["algorithm"], out["bit_length"], out["strength_check"]) == ("EdDSA", None, "pass")

    def test_ecdsa_p256_passes(self) -> None:
        out = assess(key("19", 256, "nistp256"))
        assert (out["algorithm"], out["strength_check"]) == ("ECDSA", "pass")

    def test_other_algorithm_fails(self) -> None:
        out = assess(key("18", 256, "cv25519"))
        assert out["strength_check"] == "fail" and out["algorithm"] is None

    def test_expiry_within_90_days_is_advisory(self) -> None:
        out = assess(key(expiry="2026-08-01"))
        assert out["verdict"] == "proceed" and out["expiry"] == "2026-08-01"
        assert "within 90 days" in out["strength_note"]

    def test_expired_key_blocks(self) -> None:
        out = assess(key(expiry="2026-06-01"))
        assert (out["verdict"], out["strength_check"]) == ("blocked", "fail")
        assert "expired on 2026-06-01" in out["strength_note"]

    def test_key_expiring_today_is_advisory_not_blocker(self) -> None:
        out = assess(key(expiry="2026-06-19"))
        assert out["verdict"] == "proceed" and "within 90 days" in out["strength_note"]

    def test_secp256k1_refused(self) -> None:
        out = assess(key("19", 256, "secp256k1"))
        assert (out["verdict"], out["strength_check"]) == ("blocked", "fail")

    def test_expiry_far_away_no_note(self) -> None:
        assert assess(key(expiry="2028-01-01"))["strength_note"] is None

    def test_wrong_fingerprint_is_not_found(self) -> None:
        out = assess(key(fpr="B" * 40))
        assert out["key_found"] is False and out["strength_check"] is None and out["verdict"] == "blocked"

    def test_rsa_2048_is_the_floor(self) -> None:
        assert assess(key(bits=2048))["verdict"] == "proceed"
        out = assess(key(bits=2047))
        assert out["verdict"] == "blocked" and "below the ASF floor" in out["strength_note"]

    @pytest.mark.parametrize(
        ("algo", "curve"),
        [("22", "ed448"), ("19", "nistp384"), ("19", "nistp521"), ("19", "brainpoolp512r1")],
    )
    def test_accepted_curves(self, algo: str, curve: str) -> None:
        assert assess(key(algo, 256, curve))["verdict"] == "proceed"

    def test_unknown_curve_refused(self) -> None:
        out = assess(key("22", 256, "curve25519x"))
        assert out["verdict"] == "blocked" and "not an accepted curve" in out["strength_note"]

    def test_expired_and_weak_key_reports_both(self) -> None:
        out = assess(key(bits=1024, expiry="2026-01-01"))
        assert out["verdict"] == "blocked"
        assert (
            "below the ASF floor" in out["strength_note"] and "expired on 2026-01-01" in out["strength_note"]
        )

    def test_missing_key_is_blocked_and_not_found(self) -> None:
        out = check.assess(None, FPR, TODAY)
        assert (out["verdict"], out["key_found"]) == ("blocked", False)

    def test_subkey_fingerprint_is_not_the_key_for_step_1(self) -> None:
        assert check.find_key([key()], "FFFF0000FFFF0000FFFF0000FFFF0000FFFF0000") is None


SUB_FPR = "FFFF0000FFFF0000FFFF0000FFFF0000FFFF0000"


def signing_key(
    primary_caps: str = "cSC",
    sub_algo: str = "1",
    sub_bits: int | None = 1024,
    sub_caps: str = "s",
    sub_expiry: str | None = None,
) -> dict[str, Any]:
    """The issue #1628 shape: an Ed25519 certify-only primary plus one subkey, as list-keys prints it."""
    primary = key("22", 255, "ed25519")
    primary["caps"] = primary_caps
    primary["subkeys"] = [
        {
            "fingerprint": SUB_FPR,
            "validity": "-",
            "algo_id": sub_algo,
            "algorithm": check.ALGORITHMS.get(sub_algo),
            "bits": sub_bits,
            "curve": "",
            "created": "2022-03-15",
            "expiry": sub_expiry,
            "caps": sub_caps,
        }
    ]
    return primary


class TestSignerAdmission:
    """Ported from #1635: the verdict needs a usable signing-capable key, not just a strong primary."""

    def test_certify_only_primary_with_weak_sign_subkey_blocks(self) -> None:
        out = assess(signing_key(primary_caps="c"))
        assert (out["verdict"], out["strength_check"], out["signers"]) == ("blocked", "fail", [])
        assert "no signing-capable key" in out["strength_note"]
        assert "below the ASF floor" in out["strength_note"]

    def test_aggregate_uppercase_sign_capability_does_not_make_primary_a_signer(self) -> None:
        out = assess(signing_key(primary_caps="cSC"))
        assert (out["verdict"], out["strength_check"], out["signers"]) == ("blocked", "fail", [])
        assert "primary key has no signing capability" in out["strength_note"]

    def test_admitted_dsa_signing_subkey_keeps_the_dsa_advisory(self) -> None:
        out = assess(signing_key(sub_algo="17", sub_bits=2048))
        assert out["verdict"] == "proceed" and "DSA keys are discouraged" in out["strength_note"]

    def test_admitted_signing_subkey_near_expiry_keeps_the_expiry_advisory(self) -> None:
        soon = (TODAY + dt.timedelta(days=30)).isoformat()
        out = assess(signing_key(sub_bits=4096, sub_expiry=soon))
        assert out["verdict"] == "proceed" and f"signing subkey expires on {soon}" in out["strength_note"]

    def test_certify_only_primary_without_any_sign_key_blocks(self) -> None:
        out = assess(signing_key(sub_caps="e"))
        assert (out["verdict"], out["strength_check"]) == ("blocked", "fail")
        assert "primary key has no signing capability" in out["strength_note"]
        assert "no signing-capable key" in out["strength_note"]

    def test_certify_only_primary_with_compliant_sign_subkey_proceeds(self) -> None:
        out = assess(signing_key(sub_bits=4096))
        assert out["verdict"] == "proceed"
        assert [(s["source"], s["algorithm"], s["bit_length"]) for s in out["signers"]] == [
            ("subkey", "RSA", 4096)
        ]

    def test_sign_capable_primary_alone_proceeds(self) -> None:
        out = assess(signing_key(primary_caps="scSC", sub_caps="e"))
        assert out["verdict"] == "proceed" and [s["source"] for s in out["signers"]] == ["primary"]

    def test_expired_signing_subkey_does_not_rescue(self) -> None:
        out = assess(signing_key(sub_bits=4096, sub_expiry="2026-06-01"))
        assert (out["verdict"], out["signers"]) == ("blocked", [])

    def test_revoked_signing_subkey_does_not_rescue(self) -> None:
        k = signing_key(sub_bits=4096)
        k["subkeys"][0]["validity"] = "r"
        assert assess(k)["verdict"] == "blocked"

    def test_compliant_subkey_does_not_rescue_a_weak_primary(self) -> None:
        k = signing_key(sub_bits=4096)
        k.update(algo_id="1", bits=1024, curve="")
        out = assess(k)
        assert out["verdict"] == "blocked" and "below the ASF floor" in out["strength_note"]

    def test_listings_without_caps_keep_the_primary_as_signer(self) -> None:
        out = assess(key())
        assert out["verdict"] == "proceed" and [s["source"] for s in out["signers"]] == ["primary"]

    def test_dsa_1024_reports_floor_and_advisory(self) -> None:
        out = assess(key("17", 1024))
        assert out["verdict"] == "blocked"
        assert "below the ASF floor" in out["strength_note"] and "DSA" in out["strength_note"]

    def test_check_cli_blocks_a_certify_only_key(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        f = save(tmp_path, "l.json", listing(signing_key()))
        code, out = run(capsys, "check", "--fingerprint", FPR, "--key-listing", f, "--today", "2026-06-19")
        assert code == 0 and out["verdict"] == "blocked" and out["signers"] == []
        f = save(tmp_path, "l.json", listing(signing_key(sub_bits=4096)))
        code, out = run(capsys, "check", "--fingerprint", FPR, "--key-listing", f, "--today", "2026-06-19")
        assert code == 0 and out["verdict"] == "proceed"

    def test_step_2_refuses_a_key_blocked_for_want_of_a_signer(self) -> None:
        with pytest.raises(render.RenderError, match="Step 1 did not proceed"):
            render.step2(preflight(), loaded(), assess(signing_key()), BLOCK, listing(signing_key()))


class TestValidity:
    """gpg's validity field: revoked, invalid and disabled keys never pass."""

    def test_revoked_key_blocks(self) -> None:
        out = assess(key(validity="r"))
        assert out["verdict"] == "blocked" and "revoked" in out["strength_note"]

    @pytest.mark.parametrize(("validity", "word"), [("i", "invalid"), ("d", "disabled")])
    def test_invalid_and_disabled_keys_block(self, validity: str, word: str) -> None:
        out = assess(key(validity=validity))
        assert out["verdict"] == "blocked" and word in out["strength_note"]

    @pytest.mark.parametrize("validity", ["-", "u", "f", "q"])
    def test_ordinary_validity_still_proceeds(self, validity: str) -> None:
        assert assess(key(validity=validity))["verdict"] == "proceed"


class TestKeysDirAndFingerprint:
    def test_strip_keys(self) -> None:
        out = check.keys_dir("https://dist.apache.org/repos/dist/release/foo/KEYS")
        assert out == {"svn_keys_dir_url": "https://dist.apache.org/repos/dist/release/foo", "error": None}

    def test_dist_dev_rejected(self) -> None:
        out = check.keys_dir("https://dist.apache.org/repos/dist/dev/foo/KEYS")
        assert out["svn_keys_dir_url"] is None and "dist/dev" in out["error"]

    def test_url_not_ending_in_keys_rejected(self) -> None:
        out = check.keys_dir("https://dist.apache.org/repos/dist/release/foo/KEYS.txt")
        assert out["svn_keys_dir_url"] is None and "/KEYS" in out["error"]

    def test_spaced_lowercase_fingerprint_is_normalised(self) -> None:
        spaced = " ".join(FPR[i : i + 4] for i in range(0, 40, 4)).lower()
        assert check.normalise_fpr(spaced) == FPR
        assert check.normalise_fpr("0x" + FPR.lower()) == FPR

    @pytest.mark.parametrize("bad", ["E5F6ABCD", "Z" * 40])
    def test_short_or_non_hex_rejected(self, bad: str) -> None:
        with pytest.raises(check.InputError):
            check.normalise_fpr(bad)


class TestCheckCli:
    def test_cli_assesses_a_listing(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        f = save(tmp_path, "l.json", listing(key()))
        code, out = run(
            capsys, "check", "--fingerprint", FPR.lower(), "--key-listing", f, "--today", "2026-06-19"
        )
        assert code == 0 and out["verdict"] == "proceed" and out["fingerprint"] == FPR

    def test_cli_blocks_an_expired_key(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        f = save(tmp_path, "l.json", listing(key(expiry="2026-06-18")))
        code, out = run(capsys, "check", "--fingerprint", FPR, "--key-listing", f, "--today", "2026-06-19")
        assert code == 0 and out["verdict"] == "blocked"

    def test_cli_keys_dir(self, capsys: pytest.CaptureFixture[str]) -> None:
        code, out = run(
            capsys, "keys-dir", "--keys-url", "https://dist.apache.org/repos/dist/release/foo/KEYS"
        )
        assert code == 0 and out["svn_keys_dir_url"] == "https://dist.apache.org/repos/dist/release/foo"

    def test_cli_rejects_a_bad_date_and_fingerprint(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        f = save(tmp_path, "l.json", listing(key()))
        code, out = run(capsys, "check", "--fingerprint", FPR, "--key-listing", f, "--today", "19-06-2026")
        assert code == 2 and "error" in out
        code, out = run(capsys, "check", "--fingerprint", "E5F6ABCD", "--key-listing", f)
        assert code == 2 and "fingerprint" in out["error"]

    def test_cli_surfaces_a_release_verify_error(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        f = save(tmp_path, "l.json", {"error": "gpg not found on PATH"})
        code, out = run(capsys, "check", "--fingerprint", FPR, "--key-listing", f)
        assert code == 2 and "gpg not found" in out["error"]

    def test_cli_surfaces_a_gpg_import_failure_not_a_missing_key(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Ported from #1634: release-verify reports a failed import as an error; it is never key_found false."""
        failed = {"error": "gpg --import failed (exit 2): gpg: invalid armor header"}
        f = save(tmp_path, "l.json", failed)
        code, out = run(capsys, "check", "--fingerprint", FPR, "--key-listing", f)
        assert code == 2 and set(out) == {"error"} and "gpg --import failed (exit 2)" in out["error"]
        code, out = run(
            capsys, "verdict", "--preflight", save(tmp_path, "p.json", preflight()), "--keys-listing", f
        )
        assert code == 2 and "gpg --import failed" in out["error"]


# --------------------------------------------------------------------------- former step-1-key-fetch cases


def test_step_1_key_fetch_case_1_rsa_4096_pass() -> None:
    assert assess(key()) == {
        "verdict": "proceed",
        "key_found": True,
        "fingerprint": FPR,
        "uid": UID,
        "algorithm": "RSA",
        "bit_length": 4096,
        "created": "2022-03-15",
        "expiry": None,
        "strength_check": "pass",
        "strength_note": None,
        "signers": [
            {"source": "primary", "algorithm": "RSA", "bit_length": 4096, "curve": None, "expiry": None}
        ],
    }


def test_step_1_key_fetch_case_2_not_on_keyserver(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # The keyserver returned 404, so the saved file is empty and list-keys lists nothing.
    f = save(tmp_path, "l.json", {**listing(), "detail": "file is empty"})
    code, out = run(capsys, "check", "--fingerprint", FPR, "--key-listing", f, "--today", "2026-06-19")
    assert code == 0
    assert out == {
        "verdict": "blocked",
        "key_found": False,
        "fingerprint": FPR,
        "uid": None,
        "algorithm": None,
        "bit_length": None,
        "created": None,
        "expiry": None,
        "strength_check": None,
        "strength_note": None,
        "signers": [],
    }


def test_step_1_key_fetch_case_3_weak_key() -> None:
    out = assess(key(bits=1024, created="2008-07-10"))
    assert {
        k: out[k] for k in ("verdict", "key_found", "uid", "algorithm", "bit_length", "created", "expiry")
    } == {
        "verdict": "blocked",
        "key_found": True,
        "uid": UID,
        "algorithm": "RSA",
        "bit_length": 1024,
        "created": "2008-07-10",
        "expiry": None,
    }
    assert out["strength_check"] == "fail"
    assert "1024" in out["strength_note"] and "2048" in out["strength_note"]  # has_weak_key_note


# --------------------------------------------------------------------------- Step 0 verdict


def test_step_0_preflight_case_1_fingerprint_absent_proceeds() -> None:
    out = render.verdict(preflight(), listing(key(fpr="C" * 40), file="KEYS"))
    assert (out["verdict"], out["blockers"], out["noop_reason"]) == ("proceed", [], None)
    assert (out["fingerprint"], out["keys_file_url"], out["keyserver"]) == (FPR, KEYS_URL, "keys.openpgp.org")


def test_step_0_preflight_case_2_already_in_keys() -> None:
    out = render.verdict(preflight(), listing(key(fpr="C" * 40), key(), file="KEYS"), listing(key()))
    assert out["verdict"] == "noop" and out["blockers"] == []
    assert out["noop_reason"] == f"fingerprint {FPR} already present in KEYS for uid: {UID}"
    assert out["read"] == ["outcomes/noop.md"]


def test_step_0_preflight_case_3_key_rolled() -> None:
    old = "Brendan Ngan <bngan@oldcompany.example.com>"
    out = render.verdict(preflight(), listing(key(uids=[old]), file="KEYS"), listing(key()))
    assert out["verdict"] == "blocked" and out["noop_reason"] is None
    assert out["blockers"] == [
        f"fingerprint {FPR} is already in KEYS for uid '{old}' but the keyserver reports uid "
        f"'{UID}'; the RM must decide whether to append the updated key block or replace the existing one, "
        "then update rm_key_fingerprint if the key itself changed"
    ]
    assert out["read"] == ["outcomes/key-rolled.md"]


def test_verdict_noop_when_the_keyserver_uid_is_any_keys_uid() -> None:
    keys_entry = key(uids=["Brendan Ngan <old@example.com>", UID])
    assert render.verdict(preflight(), listing(keys_entry), listing(key()))["verdict"] == "noop"


def test_verdict_matches_a_subkey_fingerprint_in_keys() -> None:
    entry = key(fpr="C" * 40)
    entry["subkey_fingerprints"] = [FPR]
    served = key(fpr="C" * 40)
    served["subkey_fingerprints"] = [FPR]
    assert render.verdict(preflight(), listing(entry), listing(served))["verdict"] == "noop"


def test_verdict_cannot_compare_without_a_keyserver_uid() -> None:
    out = render.verdict(preflight(), listing(key()), listing())
    assert out["verdict"] == "blocked" and "cannot be compared" in out["blockers"][0]
    assert "returned no key" in out["blockers"][0]
    out = render.verdict(preflight(), listing(key()), listing(key(uids=[])))
    assert "returned no user ID" in out["blockers"][0]


def test_verdict_normalises_a_0x_prefixed_fingerprint() -> None:
    """`check` strips 0x and spaces; `verdict` matches the same fingerprint the same way."""
    pre = preflight()
    pre["values"]["fingerprint"] = "0x" + FPR.lower()
    out = render.verdict(pre, listing(key(), file="KEYS"), listing(key()))
    assert out["verdict"] == "noop" and out["fingerprint"] == FPR
    assert out["blockers"] == []


def test_verdict_blocks_a_malformed_fingerprint() -> None:
    pre = preflight()
    pre["values"]["fingerprint"] = "0xDEADBEEF"
    out = render.verdict(pre, listing(key(), file="KEYS"), listing(key()))
    assert out["verdict"] == "blocked" and out["fingerprint"] is None
    assert any("40- or 64-hex-character" in b for b in out["blockers"])


def test_verdict_pending_until_the_listings_are_given() -> None:
    out = render.verdict(preflight(), None)
    assert out["verdict"] is None and "--keys-listing" in out["pending"][0]
    out = render.verdict(preflight(), listing(key()))
    assert out["verdict"] is None and "--key-listing" in out["pending"][0]


def test_verdict_carries_preflight_blockers_as_written() -> None:
    blocker = (
        "keys_file_url not resolvable: set it in release-management-config.md § Signing or pass --keys-url"
    )
    out = render.verdict(preflight([blocker]), None)
    assert (out["verdict"], out["blockers"]) == ("blocked", [blocker])


def test_verdict_blocks_an_empty_keys_file() -> None:
    out = render.verdict(preflight(), listing(file="KEYS"))
    assert out["verdict"] == "blocked" and "lists no public key" in out["blockers"][0]


def test_verdict_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, out = run(
        capsys,
        "verdict",
        "--preflight",
        save(tmp_path, "p.json", preflight()),
        "--keys-listing",
        save(tmp_path, "k.json", listing(key(fpr="C" * 40), file="KEYS")),
    )
    assert code == 0 and out["verdict"] == "proceed"


# --------------------------------------------------------------------------- former step-2-svn-commands cases


def test_step_2_svn_commands_case_1_standard_asf() -> None:
    out = render.step2(preflight(), loaded(), step1(), f"{BLOCK}\n", FETCHED)
    assert out["proposed"] is True and out["backend"] == "svnpubsub"
    for name in ("has_pgp_begin_header", "has_pgp_end_footer", "has_uid_comment", "has_checkout_command"):
        assert holds(out, name), name
    assert holds(out, "has_commit_command")
    assert out["keyserver_upload_reminder"]  # has_keyserver_reminder
    assert not holds(out, "has_expiry_warning")
    assert out["keys_block_to_append"] == f"# {UID}\n{BLOCK}"
    assert out["svn_command_sequence"] == (
        "# 1. Check out only the KEYS-file directory (release_dist_backend=svnpubsub)\n"
        "svn checkout https://dist.apache.org/repos/dist/release/airflow /tmp/airflow-keys --depth immediates\n"
        "\n"
        "# 2. Append the key block below to /tmp/airflow-keys/KEYS\n"
        "\n"
        "# 3. Commit (release_dist_backend=svnpubsub)\n"
        f'svn commit /tmp/airflow-keys/KEYS -m "Add {UID} to KEYS (fingerprint: {FPR})"'
    )
    assert "https://keys.openpgp.org/upload" in out["keyserver_upload_reminder"]


def test_step_2_svn_commands_case_3_expiring_key() -> None:
    out = render.step2(preflight(), loaded(), step1(expiry="2026-07-15"), BLOCK, FETCHED)
    for name in ASSERT:
        assert holds(out, name), name
    assert "2026-07-15" in out["keyserver_upload_reminder"]


def test_step_2_git_backend_for_a_github_keys_url() -> None:
    url = "https://github.com/example-org/example-project/blob/main/KEYS"
    out = render.step2(
        preflight(keys_url=url), loaded("example-project", "github-releases"), step1(), BLOCK, FETCHED
    )
    assert out["backend"] == "git" and out["read"] == ["backends/git.md"]
    for name in ("has_uid_comment", "has_checkout_command", "has_commit_command"):
        assert holds(out, name), name
    assert (
        "git clone https://github.com/example-org/example-project.git /tmp/example-project-keys"
        in out["svn_command_sequence"]
    )
    assert "gh pr create --web --repo example-org/example-project --base main" in out["svn_command_sequence"]


def test_step_2_atr_offers_atr_and_keeps_the_svn_sequence() -> None:
    out = render.step2(preflight(), loaded(backend="atr"), step1(), BLOCK, FETCHED)
    assert out["atr_offer"] is True and "svn commit" in out["svn_command_sequence"]
    assert out["read"] == ["backends/atr.md", "backends/svnpubsub.md"]


def test_step_2_generic_url_gets_instructions() -> None:
    out = render.step2(preflight(keys_url="https://example.org/KEYS"), loaded(), step1(), BLOCK, FETCHED)
    assert out["backend"] == "generic" and "svn" not in out["svn_command_sequence"]


def test_step_2_refuses_dist_dev_and_a_blocked_key() -> None:
    with pytest.raises(render.RenderError, match="dist/dev"):
        render.step2(
            preflight(keys_url="https://dist.apache.org/repos/dist/dev/airflow/KEYS"),
            loaded(),
            step1(),
            BLOCK,
            FETCHED,
        )
    with pytest.raises(render.RenderError, match="Step 1 did not proceed"):
        render.step2(preflight(), loaded(), step1(bits=1024), BLOCK, FETCHED)


def test_step_2_refuses_private_key_material_and_a_missing_block() -> None:
    marker = "PGP " + "PRIVATE KEY BLOCK"  # built at runtime so the secret scanner stays quiet
    with pytest.raises(render.RenderError, match="private-key"):
        render.step2(preflight(), loaded(), step1(), f"{BLOCK}\n-----BEGIN {marker}-----\nx\n", FETCHED)
    with pytest.raises(render.RenderError, match="0 armoured"):
        render.step2(preflight(), loaded(), step1(), "", FETCHED)


def test_step_2_refuses_a_key_file_that_is_not_the_checked_key() -> None:
    """The appended block must be the Step 1 key: a multi-key armour or another key is refused."""
    other = key(fpr="C" * 40, uids=["Eve <eve@example.org>"])
    with pytest.raises(render.RenderError, match=r"lists 2 primary key\(s\)"):
        render.step2(preflight(), loaded(), step1(), BLOCK, listing(key(), other))
    with pytest.raises(render.RenderError, match="expected exactly the Step 1 key"):
        render.step2(preflight(), loaded(), step1(), BLOCK, listing(other))
    with pytest.raises(render.RenderError, match=r"lists 0 primary key\(s\)"):
        render.step2(preflight(), loaded(), step1(), BLOCK, listing())
    with pytest.raises(render.RenderError, match="lists 0"):
        render.step2(preflight(), loaded(), step1(), BLOCK, None)
    with pytest.raises(render.RenderError, match="release-verify list-keys failed"):
        render.step2(preflight(), loaded(), step1(), BLOCK, {"error": "gpg missing"})


def test_step_2_render_cli_refuses_a_multi_key_listing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out = run(
        capsys,
        "render",
        "--step",
        "2",
        "--preflight",
        save(tmp_path, "p.json", preflight()),
        "--load",
        save(tmp_path, "l.json", loaded()),
        "--check",
        save(tmp_path, "c.json", step1()),
        "--key-file",
        save(tmp_path, "k.asc", BLOCK),
        "--key-listing",
        save(tmp_path, "kl.json", listing(key(), key(fpr="C" * 40))),
    )
    assert code == 2 and out["ok"] is False and "2 primary key" in out["refused"]


def test_step_2_external_uid_cannot_break_out() -> None:
    hostile = 'Eve $(touch /tmp/x) "q" <eve@example.org>\n-----BEGIN PGP PUBLIC KEY BLOCK-----'
    out = render.step2(preflight(), loaded(), step1(uids=[hostile]), BLOCK, FETCHED)
    first, rest = out["keys_block_to_append"].split("\n", 1)
    assert first.startswith("# Eve") and rest == BLOCK
    commit = out["svn_command_sequence"].splitlines()[-1]
    assert '\\$(touch /tmp/x) \\"q\\"' in commit


def test_step_2_render_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, out = run(
        capsys,
        "render",
        "--step",
        "2",
        "--preflight",
        save(tmp_path, "p.json", preflight()),
        "--load",
        save(tmp_path, "l.json", loaded()),
        "--check",
        save(tmp_path, "c.json", step1()),
        "--key-file",
        save(tmp_path, "k.asc", BLOCK + "\n"),
        "--key-listing",
        save(tmp_path, "kl.json", FETCHED),
    )
    assert code == 0 and out["proposed"] is True
    code, out = run(
        capsys,
        "render",
        "--step",
        "2",
        "--preflight",
        save(tmp_path, "p.json", preflight()),
        "--load",
        save(tmp_path, "l.json", loaded()),
        "--check",
        save(tmp_path, "c.json", step1(bits=1024)),
        "--key-file",
        save(tmp_path, "k.asc", BLOCK),
        "--key-listing",
        save(tmp_path, "kl.json", FETCHED),
    )
    assert code == 2 and out["ok"] is False and "refused" in out


# --------------------------------------------------------------------------- ported from test_check_key.py

STEP_1_FIELDS = {
    "verdict",
    "key_found",
    "fingerprint",
    "uid",
    "algorithm",
    "bit_length",
    "created",
    "expiry",
    "strength_check",
    "strength_note",
    "signers",
}


@pytest.mark.parametrize(("listed", "found"), [(FPR, True), ("B" * 40, False)])
def test_check_cli_completed_assessments_keep_the_field_contract(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], listed: str, found: bool
) -> None:
    """A listing holding another key's fingerprint is `key_found: false`, exit 0, same fields."""
    f = save(tmp_path, "l.json", listing(key(fpr=listed)))
    code, out = run(capsys, "check", "--fingerprint", FPR, "--key-listing", f, "--today", "2026-06-19")
    assert (code, out["key_found"], set(out)) == (0, found, STEP_1_FIELDS)


def test_check_cli_needs_a_fingerprint(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    f = save(tmp_path, "l.json", listing(key()))
    with pytest.raises(SystemExit) as exc:
        main(["keys-sync", "check", "--key-listing", f])
    assert exc.value.code == 2 and "--fingerprint" in capsys.readouterr().err


def test_verdict_compares_uid_sets_not_the_keyserver_order() -> None:
    """The keyserver may list a UID KEYS lacks first; a UID both share keeps the verdict `noop`."""
    added = "Brendan Ngan <brendan@example.org>"
    out = render.verdict(preflight(), listing(key(), file="KEYS"), listing(key(uids=[added, UID])))
    assert out["verdict"] == "noop" and out["blockers"] == []
    assert out["noop_reason"] == f"fingerprint {FPR} already present in KEYS for uid: {UID}"


def test_verdict_blocks_when_no_keyserver_uid_is_in_keys() -> None:
    old = "Brendan Ngan <bngan@oldcompany.example.com>"
    served = ["Brendan Ngan <one@example.org>", "Brendan Ngan <two@example.org>"]
    out = render.verdict(preflight(), listing(key(uids=[old]), file="KEYS"), listing(key(uids=served)))
    assert out["verdict"] == "blocked" and out["read"] == ["outcomes/key-rolled.md"]
    assert f"the keyserver reports uids {served!r}" in out["blockers"][0]


# --------------------------------------------------------------------------- git backend: branch and KEYS path


def git_step2(url: str, keys_branch: str | None = None, *, in_config: bool = False) -> dict[str, Any]:
    pre = preflight(keys_url=url)
    load = loaded("r", "github-releases")
    if keys_branch is not None:
        (load["config"] if in_config else pre["values"])["keys_file_branch"] = keys_branch
    return render.step2(pre, load, step1(), BLOCK, FETCHED)


@pytest.mark.parametrize(
    ("url", "branch", "path", "warned"),
    [
        ("https://github.com/o/r/blob/main/KEYS", "main", "KEYS", False),
        ("https://github.com/o/r/blob/main/dist/KEYS", "main", "dist/KEYS", True),
        ("https://github.com/o/r.git/raw/main/release/keys/KEYS", "main", "release/keys/KEYS", True),
        ("https://raw.githubusercontent.com/o/r/main/KEYS", "main", "KEYS", False),
        ("https://raw.githubusercontent.com/o/r/main/dist/KEYS", "main", "dist/KEYS", True),
        ("https://raw.githubusercontent.com/o/r/refs/heads/main/dist/KEYS", "main", "dist/KEYS", True),
        ("https://github.com/o/r", "main", "KEYS", False),
    ],
)
def test_step_2_git_branch_is_the_first_segment_and_keys_may_sit_in_a_subdir(
    url: str, branch: str, path: str, warned: bool
) -> None:
    out = git_step2(url)
    commands = out["svn_command_sequence"]
    assert f"git checkout -b keys-sync-{FPR[-16:].lower()} origin/{branch}\n" in commands
    assert f"# 2. Append the key block below to {path}\n" in commands
    assert f"git add {path}\n" in commands and f"--base {branch} " in commands
    assert "git clone https://github.com/o/r.git " in commands
    warnings = [w for w in out["warnings"] if "keys_file_branch" in w]
    assert bool(warnings) is warned
    if warned:
        assert f"read as branch {branch!r} and file {path!r}" in warnings[0]


@pytest.mark.parametrize("in_config", [False, True])
def test_step_2_keys_file_branch_names_a_branch_holding_a_slash(in_config: bool) -> None:
    out = git_step2("https://github.com/o/r/blob/release/1.x/dist/KEYS", "release/1.x", in_config=in_config)
    commands = out["svn_command_sequence"]
    assert "origin/release/1.x\n" in commands and "--base release/1.x " in commands
    assert "git add dist/KEYS\n" in commands
    assert not [w for w in out["warnings"] if "keys_file_branch" in w]


def test_step_2_keys_file_branch_quotes_a_hostile_branch() -> None:
    commands = git_step2("https://github.com/o/r/blob/a$(id)/KEYS", "a$(id)")["svn_command_sequence"]
    assert " 'origin/a$(id)'\n" in commands and "--base 'a$(id)' " in commands


@pytest.mark.parametrize(
    "url",
    ["https://github.com/o/r/blob/release/2.x/dist/KEYS", "https://github.com/o/r/blob/release/1.x/KEYS2"],
)
def test_step_2_keys_file_branch_mismatch_is_refused(url: str) -> None:
    with pytest.raises(render.RenderError) as exc:
        git_step2(url, "release/1.x/KEYS2" if url.endswith("KEYS2") else "release/1.x")
    message = str(exc.value)
    assert ("does not match" in message or "called KEYS" in message) and url in message


def test_step_2_keys_file_branch_naming_the_whole_path_is_refused() -> None:
    with pytest.raises(render.RenderError, match=r"keys_file_branch 'main/KEYS' does not match"):
        git_step2("https://github.com/o/r/blob/main/KEYS", "main/KEYS")


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/o/r/blob/main/KEYS.txt",
        "https://github.com/o/r/blob/main/docs/keys",
        "https://raw.githubusercontent.com/o/r/main/dist/KEYS.asc",
    ],
)
def test_step_2_git_refuses_a_file_not_named_keys(url: str) -> None:
    with pytest.raises(render.RenderError, match="does not name a file called KEYS"):
        git_step2(url)


@pytest.mark.parametrize(
    "url", ["https://github.com/o/r/tree/main", "https://raw.githubusercontent.com/o/r/KEYS"]
)
def test_step_2_git_refuses_a_url_without_branch_and_keys(url: str) -> None:
    with pytest.raises(
        render.RenderError, match=re.escape("expected https://github.com/<owner>/<repo>/blob/<branch>")
    ):
        git_step2(url)
