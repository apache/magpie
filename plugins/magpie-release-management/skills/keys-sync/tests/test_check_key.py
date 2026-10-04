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

from __future__ import annotations

import contextlib
import datetime as dt
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import check_key

FPR = "A1B2C3D4E5F6A1B2C3D4E5F6A1B2C3D4E5F6ABCD"
TODAY = dt.date(2026, 6, 19)
CREATED = "1647302400"  # 2022-03-15


def colons(algo: str, bits: str, curve: str = "", expires: str = "", fpr: str = FPR) -> str:
    pub = ["pub", "-", bits, algo, "KEYID", CREATED, expires] + [""] * 9 + [curve, "", "0", ""]
    return "\n".join(
        [
            "tru::1:1791072876:0:3:1:5",
            ":".join(pub),
            f"fpr:::::::::{fpr}:",
            "uid:-::::1647302400::HASH::Brendan Ngan <bngan@apache.org>::::::::::0:",
            "sub:-:4096:1:SUBID:1647302400::::::e::::::23:",
            "fpr:::::::::FFFF0000FFFF0000FFFF0000FFFF0000FFFF0000:",
        ]
    )


def check(text: str, fpr: str = FPR) -> dict:
    match = next((k for k in check_key.parse_colons(text) if k["fingerprint"] == fpr), None)
    return check_key.assess(match, fpr, TODAY)


def epoch(day: str) -> str:
    return str(int(dt.datetime.fromisoformat(day + "T00:00:00+00:00").timestamp()))


class AssessTest(unittest.TestCase):
    def test_rsa_4096_passes(self) -> None:
        out = check(colons("1", "4096"))
        self.assertEqual(out["verdict"], "proceed")
        self.assertEqual((out["algorithm"], out["bit_length"]), ("RSA", 4096))
        self.assertEqual(out["uid"], "Brendan Ngan <bngan@apache.org>")
        self.assertEqual(out["created"], "2022-03-15")
        self.assertIsNone(out["expiry"])
        self.assertIsNone(out["strength_note"])

    def test_rsa_1024_fails(self) -> None:
        out = check(colons("1", "1024"))
        self.assertEqual((out["verdict"], out["strength_check"]), ("blocked", "fail"))
        self.assertIn("1024", out["strength_note"])
        self.assertIn("2048", out["strength_note"])

    def test_dsa_2048_passes_with_advisory(self) -> None:
        out = check(colons("17", "2048"))
        self.assertEqual(out["strength_check"], "pass")
        self.assertIn("DSA", out["strength_note"])

    def test_ed25519_passes_without_bit_length(self) -> None:
        out = check(colons("22", "255", curve="ed25519"))
        self.assertEqual(
            (out["algorithm"], out["bit_length"], out["strength_check"]), ("EdDSA", None, "pass")
        )

    def test_ecdsa_p256_passes(self) -> None:
        out = check(colons("19", "256", curve="nistp256"))
        self.assertEqual((out["algorithm"], out["strength_check"]), ("ECDSA", "pass"))

    def test_other_algorithm_fails(self) -> None:
        out = check(colons("18", "256", curve="cv25519"))
        self.assertEqual(out["strength_check"], "fail")
        self.assertIsNone(out["algorithm"])

    def test_expiry_within_90_days_is_advisory(self) -> None:
        out = check(colons("1", "4096", expires=epoch("2026-08-01")))
        self.assertEqual(out["verdict"], "proceed")
        self.assertEqual(out["expiry"], "2026-08-01")
        self.assertIn("within 90 days", out["strength_note"])

    def test_expired_key_blocks(self) -> None:
        out = check(colons("1", "4096", expires=epoch("2026-06-01")))
        self.assertEqual((out["verdict"], out["strength_check"]), ("blocked", "fail"))
        self.assertIn("expired on 2026-06-01", out["strength_note"])

    def test_key_expiring_today_is_advisory_not_blocker(self) -> None:
        out = check(colons("1", "4096", expires=epoch("2026-06-19")))
        self.assertEqual(out["verdict"], "proceed")
        self.assertIn("within 90 days", out["strength_note"])

    def test_secp256k1_refused(self) -> None:
        out = check(colons("19", "256", curve="secp256k1"))
        self.assertEqual((out["verdict"], out["strength_check"]), ("blocked", "fail"))

    def test_expiry_far_away_no_note(self) -> None:
        out = check(colons("1", "4096", expires=epoch("2028-01-01")))
        self.assertIsNone(out["strength_note"])

    def test_wrong_fingerprint_is_not_found(self) -> None:
        out = check(colons("1", "4096", fpr="B" * 40))
        self.assertFalse(out["key_found"])
        self.assertIsNone(out["strength_check"])
        self.assertEqual(out["verdict"], "blocked")


class KeysDirTest(unittest.TestCase):
    def test_strip_keys(self) -> None:
        out = check_key.keys_dir("https://dist.apache.org/repos/dist/release/foo/KEYS")
        self.assertEqual(
            out, {"svn_keys_dir_url": "https://dist.apache.org/repos/dist/release/foo", "error": None}
        )

    def test_dist_dev_rejected(self) -> None:
        out = check_key.keys_dir("https://dist.apache.org/repos/dist/dev/foo/KEYS")
        self.assertIsNone(out["svn_keys_dir_url"])
        self.assertIn("dist/dev", out["error"])

    def test_url_not_ending_in_keys_rejected(self) -> None:
        out = check_key.keys_dir("https://dist.apache.org/repos/dist/release/foo/KEYS.txt")
        self.assertIsNone(out["svn_keys_dir_url"])
        self.assertIn("/KEYS", out["error"])


@unittest.skipUnless(shutil.which("gpg"), "gpg not installed")
class GpgTest(unittest.TestCase):
    def test_garbage_file_imports_nothing(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".asc") as handle:
            handle.write("not a key\n")
            handle.flush()
            self.assertNotIn("pub:", check_key.list_key_file(Path(handle.name)))


class AssessEdgeTest(unittest.TestCase):
    """Boundaries of the strength floor, the accepted curves and expiry."""

    def test_rsa_2048_is_the_floor(self) -> None:
        self.assertEqual(check(colons("1", "2048"))["verdict"], "proceed")
        out = check(colons("1", "2047"))
        self.assertEqual(out["verdict"], "blocked")
        self.assertIn("below the ASF floor", out["strength_note"])

    def test_accepted_curves(self) -> None:
        for algo, curve in (
            ("22", "ed448"),
            ("19", "nistp384"),
            ("19", "nistp521"),
            ("19", "brainpoolp512r1"),
        ):
            with self.subTest(curve=curve):
                self.assertEqual(check(colons(algo, "256", curve=curve))["verdict"], "proceed")

    def test_unknown_curve_refused(self) -> None:
        out = check(colons("22", "256", curve="curve25519x"))
        self.assertEqual(out["verdict"], "blocked")
        self.assertIn("not an accepted curve", out["strength_note"])

    def test_expired_and_weak_key_reports_both(self) -> None:
        out = check(colons("1", "1024", expires=epoch("2026-01-01")))
        self.assertEqual(out["verdict"], "blocked")
        self.assertIn("below the ASF floor", out["strength_note"])
        self.assertIn("expired on 2026-01-01", out["strength_note"])

    def test_missing_key_is_blocked_and_not_found(self) -> None:
        out = check_key.assess(None, FPR, TODAY)
        self.assertEqual((out["verdict"], out["key_found"]), ("blocked", False))


class FingerprintTest(unittest.TestCase):
    def test_spaced_lowercase_fingerprint_is_normalised(self) -> None:
        spaced = " ".join(FPR[i : i + 4] for i in range(0, 40, 4)).lower()
        self.assertEqual(check_key.normalise_fpr(spaced), FPR)
        self.assertEqual(check_key.normalise_fpr("0x" + FPR.lower()), FPR)

    def test_short_key_id_rejected(self) -> None:
        with self.assertRaises(check_key.InputError):
            check_key.normalise_fpr("E5F6ABCD")

    def test_non_hex_rejected(self) -> None:
        with self.assertRaises(check_key.InputError):
            check_key.normalise_fpr("Z" * 40)


class CheckKeyCliTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_cli(self, *args: str) -> tuple[int, dict]:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = check_key.main(list(args))
        return code, json.loads(buf.getvalue())

    def colons_file(self, text: str) -> str:
        path = self.tmp / "colons.txt"
        path.write_text(text, encoding="utf-8")
        return str(path)

    def test_cli_assesses_a_listing(self) -> None:
        code, out = self.run_cli(
            "--fingerprint",
            FPR.lower(),
            "--colons-file",
            self.colons_file(colons("1", "4096")),
            "--today",
            TODAY.isoformat(),
        )
        self.assertEqual(code, 0)
        self.assertEqual(out["verdict"], "proceed")
        self.assertEqual(out["fingerprint"], FPR)

    def test_cli_blocks_an_expired_key(self) -> None:
        code, out = self.run_cli(
            "--fingerprint",
            FPR,
            "--colons-file",
            self.colons_file(colons("1", "4096", expires=epoch("2026-06-18"))),
            "--today",
            TODAY.isoformat(),
        )
        self.assertEqual(code, 0)
        self.assertEqual(out["verdict"], "blocked")

    def test_cli_keys_url_mode(self) -> None:
        code, out = self.run_cli("--keys-url", "https://dist.apache.org/repos/dist/release/foo/KEYS")
        self.assertEqual(code, 0)
        self.assertEqual(out["svn_keys_dir_url"], "https://dist.apache.org/repos/dist/release/foo")

    def test_cli_key_mode_needs_a_fingerprint(self) -> None:
        code, out = self.run_cli("--colons-file", self.colons_file(colons("1", "4096")))
        self.assertEqual(code, 2)
        self.assertIn("--fingerprint", out["error"])

    def test_cli_rejects_a_bad_date(self) -> None:
        code, out = self.run_cli(
            "--fingerprint",
            FPR,
            "--colons-file",
            self.colons_file(colons("1", "4096")),
            "--today",
            "19-06-2026",
        )
        self.assertEqual(code, 2)
        self.assertIn("error", out)


class ValidityTest(unittest.TestCase):
    """gpg's validity field: revoked, invalid and disabled keys never pass."""

    def listing(self, validity: str) -> str:
        return colons("1", "4096").replace("pub:-:", f"pub:{validity}:", 1)

    def test_revoked_key_blocks(self) -> None:
        out = check(self.listing("r"))
        self.assertEqual(out["verdict"], "blocked")
        self.assertIn("revoked", out["strength_note"])

    def test_invalid_and_disabled_keys_block(self) -> None:
        for validity, word in (("i", "invalid"), ("d", "disabled")):
            with self.subTest(validity=validity):
                out = check(self.listing(validity))
                self.assertEqual(out["verdict"], "blocked")
                self.assertIn(word, out["strength_note"])

    def test_ordinary_validity_still_proceeds(self) -> None:
        for validity in ("-", "u", "f", "q"):
            with self.subTest(validity=validity):
                self.assertEqual(check(self.listing(validity))["verdict"], "proceed")


if __name__ == "__main__":
    unittest.main()
