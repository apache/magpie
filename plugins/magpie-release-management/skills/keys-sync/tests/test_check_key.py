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

import base64
import contextlib
import datetime as dt
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import check_key

FPR = "A1B2C3D4E5F6A1B2C3D4E5F6A1B2C3D4E5F6ABCD"
TODAY = dt.date(2026, 6, 19)
CREATED = "1647302400"  # 2022-03-15
GPG = shutil.which("gpg")
MSYS_GPG = sys.platform == "win32" and GPG is not None and Path(GPG).with_name("msys-2.0.dll").is_file()
NO_DATA = "[GNUPG:] NODATA 1\n[GNUPG:] IMPORT_RES " + " ".join(["0"] * 15) + "\n"
PUBLIC_FPR = "038B5CD314A54039993E7625DA31D2B4B27784E4"
PUBLIC_KEY = """-----BEGIN PGP PUBLIC KEY BLOCK-----

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
+P8JcWgqidc2b1O/jl++tHgTt8SqqtM=
=cHCJ
-----END PGP PUBLIC KEY BLOCK-----
"""


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

    def test_dsa_1024_reports_floor_and_advisory(self) -> None:
        out = check(colons("17", "1024"))
        self.assertEqual(out["verdict"], "blocked")
        self.assertIn("below the ASF floor", out["strength_note"])
        self.assertIn("DSA", out["strength_note"])

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


@unittest.skipUnless(GPG and not MSYS_GPG, "requires gpg accepting native --homedir paths")
class GpgTest(unittest.TestCase):
    def run_cli(self, path: Path, fingerprint: str = PUBLIC_FPR) -> tuple[int, dict]:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = check_key.main(["--key-file", str(path), "--fingerprint", fingerprint])
        return code, json.loads(buf.getvalue())

    def test_garbage_file_imports_nothing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="keys sync ") as directory:
            path = Path(directory) / "not a key.asc"
            path.write_text("not a key\n", encoding="utf-8")
            self.assertNotIn("pub:", check_key.list_key_file(path))

    def test_unicode_text_imports_nothing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="keys sync ") as directory:
            path = Path(directory) / "not a key.asc"
            path.write_text("这不是公钥\n", encoding="utf-8")
            self.assertNotIn("pub:", check_key.list_key_file(path))

    def test_directory_input_is_an_error(self) -> None:
        with tempfile.TemporaryDirectory(prefix="keys sync ") as directory:
            code, out = self.run_cli(Path(directory))
            self.assertEqual((code, set(out)), (2, {"error"}))
            self.assertIn("--key-file", out["error"])
            self.assertIn("regular file", out["error"])

    def test_truncated_armored_public_key_is_an_error(self) -> None:
        with tempfile.TemporaryDirectory(prefix="keys sync ") as directory:
            path = Path(directory) / "truncated key.asc"
            path.write_text(PUBLIC_KEY[:160], encoding="ascii")
            code, out = self.run_cli(path)
            self.assertEqual((code, set(out)), (2, {"error"}))
            self.assertIn("gpg --import failed (exit 2)", out["error"])

    def test_other_malformed_armored_inputs_are_errors(self) -> None:
        for public in (
            PUBLIC_KEY.split("\n\n", 1)[0] + "\n",
            PUBLIC_KEY.replace("=cHCJ", "=AAAA"),
            PUBLIC_KEY + PUBLIC_KEY[:160],
        ):
            with (
                self.subTest(public=public[:40]),
                tempfile.TemporaryDirectory(prefix="keys sync ") as directory,
            ):
                path = Path(directory) / "malformed key.asc"
                path.write_text(public, encoding="ascii")
                code, out = self.run_cli(path)
                self.assertEqual((code, set(out)), (2, {"error"}))
                self.assertIn("gpg --import failed (exit 2)", out["error"])

    def test_valid_public_key_is_listed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="keys sync ") as directory:
            path = Path(directory) / "public key.asc"
            path.write_text(PUBLIC_KEY, encoding="ascii")
            keys = check_key.parse_colons(check_key.list_key_file(path))
            self.assertEqual([key["fingerprint"] for key in keys], [PUBLIC_FPR])

    def test_valid_binary_public_key_is_listed(self) -> None:
        body = PUBLIC_KEY.split("\n\n", 1)[1].split("\n=", 1)[0]
        with tempfile.TemporaryDirectory(prefix="keys sync ") as directory:
            path = Path(directory) / "public key.gpg"
            path.write_bytes(base64.b64decode(body))
            keys = check_key.parse_colons(check_key.list_key_file(path))
            self.assertEqual([key["fingerprint"] for key in keys], [PUBLIC_FPR])

    def test_valid_public_key_with_another_fingerprint_is_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="keys sync ") as directory:
            path = Path(directory) / "public key.asc"
            path.write_text(PUBLIC_KEY, encoding="ascii")
            code, out = self.run_cli(path, "A" * 40)
            self.assertEqual((code, out["verdict"], out["key_found"]), (0, "blocked", False))

    def test_import_uses_the_bytes_read_before_the_file_changes(self) -> None:
        original_run = check_key.subprocess.run
        with tempfile.TemporaryDirectory(prefix="keys sync ") as directory:
            path = Path(directory) / "public key.asc"
            path.write_text(PUBLIC_KEY, encoding="ascii")

            def replace_input(command, **kwargs):
                if "--import" in command:
                    path.write_text("not a key\n", encoding="utf-8")
                return original_run(command, **kwargs)

            with mock.patch.object(check_key.subprocess, "run", side_effect=replace_input):
                keys = check_key.parse_colons(check_key.list_key_file(path))
            self.assertEqual([key["fingerprint"] for key in keys], [PUBLIC_FPR])


@unittest.skipUnless(MSYS_GPG, "requires Windows and Git/MSYS gpg")
class MsysGpgTest(unittest.TestCase):
    def test_incompatible_homedir_is_an_error_not_a_missing_key(self) -> None:
        with tempfile.TemporaryDirectory(prefix="keys sync ") as directory:
            path = Path(directory) / "public key.asc"
            path.write_text(PUBLIC_KEY, encoding="ascii")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = check_key.main(["--key-file", str(path), "--fingerprint", PUBLIC_FPR])
            out = json.loads(buf.getvalue())
            self.assertEqual(code, 2)
            self.assertEqual(set(out), {"error"})
            self.assertIn("gpg --import failed (exit 2)", out["error"])


class GpgFailureTest(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory(prefix="keys sync ")
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "public key.asc"
        self.path.write_text("not a key\n", encoding="utf-8")

    def result(self, code: int, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess([], code, stdout.encode("utf-8"), stderr.encode("utf-8"))

    def invoke(self, *results: subprocess.CompletedProcess[bytes] | OSError) -> tuple[int, dict, int]:
        buf = io.StringIO()
        with (
            mock.patch.object(check_key.shutil, "which", return_value="test-gpg"),
            mock.patch.object(check_key.subprocess, "run", side_effect=results) as run,
            contextlib.redirect_stdout(buf),
        ):
            code = check_key.main(["--key-file", str(self.path), "--fingerprint", FPR])
        for call in run.call_args_list:
            command = call.args[0]
            home = Path(command[command.index("--homedir") + 1])
            self.assertFalse(home.exists(), f"temporary keyring survived: {home}")
        return code, json.loads(buf.getvalue()), run.call_count

    def assert_error(self, code: int, out: dict, stage: str) -> None:
        self.assertEqual(code, 2)
        self.assertEqual(set(out), {"error"})
        self.assertIn(f"gpg {stage}", out["error"])

    def test_import_failure_is_not_hidden_by_a_readable_empty_keyring(self) -> None:
        code, out, calls = self.invoke(self.result(2, stderr="permission denied"), self.result(0))
        self.assert_error(code, out, "--import")
        self.assertIn("exit 2", out["error"])
        self.assertIn("permission denied", out["error"])
        self.assertEqual(calls, 1)

    def test_listing_failure_discards_partial_output(self) -> None:
        code, out, _ = self.invoke(self.result(0), self.result(2, colons("1", "4096"), "cannot read keyring"))
        self.assert_error(code, out, "--list-keys")
        self.assertIn("cannot read keyring", out["error"])

    def test_only_no_data_preserves_the_missing_key_result(self) -> None:
        for suffix in ("", "[GNUPG:] FAILURE gpg-exit 33554433\n"):
            with self.subTest(suffix=suffix):
                code, out, calls = self.invoke(
                    self.result(2, NO_DATA + suffix), self.result(0, "tru::1:0:0:\n")
                )
                self.assertEqual((code, out["verdict"], out["key_found"]), (0, "blocked", False))
                self.assertEqual(calls, 2)

    def test_no_data_never_overrides_another_failure_or_partial_import(self) -> None:
        for status in (
            "ERROR add_keyblock_resource 33587281",
            "IMPORT_PROBLEM 4",
            f"IMPORT_OK 1 {FPR}",
            "IMPORTED KEYID Test key",
            "FAILURE import 33554433",
            "FAILURE gpg-exit 33554445",
        ):
            with self.subTest(status=status):
                code, out, calls = self.invoke(self.result(2, NO_DATA + f"[GNUPG:] {status}\n"))
                self.assert_error(code, out, "--import")
                self.assertEqual(calls, 1)

    def test_no_data_needs_a_complete_zero_import_summary(self) -> None:
        for summary in (
            "",
            "[GNUPG:] IMPORT_RES 0 0\n",
            "[GNUPG:] IMPORT_RES " + " ".join(["0"] * 14 + ["1"]) + "\n",
            "[GNUPG:] IMPORT_RES " + " ".join(["0"] * 14 + ["unknown"]) + "\n",
        ):
            with self.subTest(summary=summary):
                code, out, _ = self.invoke(self.result(2, "[GNUPG:] NODATA 1\n" + summary))
                self.assert_error(code, out, "--import")

    def test_no_data_still_requires_successful_listing(self) -> None:
        code, out, _ = self.invoke(self.result(2, NO_DATA), self.result(2, stderr="keyring unavailable"))
        self.assert_error(code, out, "--list-keys")

    def test_no_data_with_a_listed_public_key_is_an_import_error(self) -> None:
        code, out, _ = self.invoke(self.result(2, NO_DATA), self.result(0, colons("1", "4096")))
        self.assert_error(code, out, "--import")

    def test_unrecognised_or_missing_no_data_status_is_an_error(self) -> None:
        for status in ("", "[GNUPG:] IMPORT_RES " + " ".join(["0"] * 15), "[GNUPG:] NODATA 99\n" + NO_DATA):
            with self.subTest(status=status):
                code, out, _ = self.invoke(self.result(2, status))
                self.assert_error(code, out, "--import")

    def test_other_exit_codes_are_never_no_data_exceptions(self) -> None:
        for exit_code in (1, -9, 127):
            with self.subTest(exit_code=exit_code):
                code, out, _ = self.invoke(self.result(exit_code, NO_DATA))
                self.assert_error(code, out, "--import")
                self.assertIn(f"exit {exit_code}", out["error"])

    def test_error_uses_status_output_when_stderr_is_empty(self) -> None:
        code, out, _ = self.invoke(self.result(2, "[GNUPG:] ERROR keydb_search 33554445\n"))
        self.assert_error(code, out, "--import")
        self.assertIn("ERROR keydb_search 33554445", out["error"])

    def test_no_diagnostics_still_reports_the_stage_and_return_code(self) -> None:
        code, out, _ = self.invoke(self.result(2))
        self.assert_error(code, out, "--import")
        self.assertIn("exit 2", out["error"])
        self.assertIn("no diagnostic output", out["error"])

    def test_spawn_errors_report_the_stage_and_clean_the_keyring(self) -> None:
        for results, stage in (
            ((OSError("could not start"),), "--import"),
            ((self.result(0), OSError("could not start")), "--list-keys"),
        ):
            with self.subTest(stage=stage):
                code, out, _ = self.invoke(*results)
                self.assert_error(code, out, stage)
                self.assertIn("could not start", out["error"])

    def test_completed_assessments_preserve_the_field_contract(self) -> None:
        for fingerprint, expected_found in ((FPR, True), ("B" * 40, False)):
            with self.subTest(fingerprint=fingerprint):
                code, out, _ = self.invoke(
                    self.result(0), self.result(0, colons("1", "4096", fpr=fingerprint))
                )
                self.assertEqual((code, out["key_found"]), (0, expected_found))
                self.assertEqual(
                    set(out),
                    {
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
                    },
                )

    def test_empty_input_does_not_need_gpg(self) -> None:
        self.path.write_bytes(b"")
        code, out, calls = self.invoke()
        self.assertEqual((code, out["key_found"], calls), (0, False, 0))

    def test_directory_is_rejected_before_the_empty_input_shortcut(self) -> None:
        self.path.unlink()
        self.path.mkdir()
        code, out, calls = self.invoke(self.result(2, NO_DATA), self.result(0))
        self.assert_error_input(code, out)
        self.assertIn("regular file", out["error"])
        self.assertEqual(calls, 0)

    def test_read_error_is_reported_before_calling_gpg(self) -> None:
        with mock.patch.object(Path, "read_bytes", side_effect=PermissionError("permission denied")):
            code, out, calls = self.invoke(self.result(0), self.result(0, colons("1", "4096")))
        self.assert_error_input(code, out)
        self.assertIn("--key-file", out["error"])
        self.assertIn("permission denied", out["error"])
        self.assertEqual(calls, 0)

    def test_no_data_does_not_hide_a_declared_public_key(self) -> None:
        self.path.write_text(PUBLIC_KEY[:160], encoding="ascii")
        code, out, calls = self.invoke(self.result(2, NO_DATA), self.result(0))
        self.assert_error(code, out, "--import")
        self.assertEqual(calls, 1)

    def test_bad_fingerprint_does_not_call_gpg(self) -> None:
        buf = io.StringIO()
        with mock.patch.object(check_key.subprocess, "run") as run, contextlib.redirect_stdout(buf):
            code = check_key.main(["--key-file", str(self.path), "--fingerprint", "bad"])
        self.assert_error_input(code, json.loads(buf.getvalue()))
        run.assert_not_called()

    def assert_error_input(self, code: int, out: dict) -> None:
        self.assertEqual((code, set(out)), (2, {"error"}))

    def test_gpg_unavailable_is_still_an_error(self) -> None:
        buf = io.StringIO()
        with mock.patch.object(check_key.shutil, "which", return_value=None), contextlib.redirect_stdout(buf):
            code = check_key.main(["--key-file", str(self.path), "--fingerprint", FPR])
        out = json.loads(buf.getvalue())
        self.assert_error_input(code, out)
        self.assertIn("gpg not found", out["error"])

    def test_non_utf8_diagnostics_do_not_hide_the_gpg_failure(self) -> None:
        result = check_key._run_gpg(
            [sys.executable, "-c", "import sys; sys.stderr.buffer.write(b'failure: \\xff'); sys.exit(2)"],
            "--import",
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("failure:", str(check_key._gpg_error("--import", result)))
        self.assertIn("\ufffd", result.stderr)


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


def signing_listing(
    primary_caps: str = "c",
    sub_algo: str = "1",
    sub_bits: str = "1024",
    sub_caps: str = "s",
    sub_expires: str = "",
) -> str:
    """The issue #1628 shape: an Ed25519 certify-only primary plus a signing subkey."""

    def key_line(
        kind: str, algo: str, bits: str, key_id: str, caps: str, curve: str = "", expires: str = ""
    ) -> str:
        # Real gpg colons layout, 0-based indexes: type:0 validity:1 bits:2
        # algo:3 keyid:4 created:5 expiry:6 ... capabilities:11 ... curve:16.
        fields = [""] * 17
        fields[0], fields[1], fields[2], fields[3], fields[4] = kind, "-", bits, algo, key_id
        fields[5], fields[6], fields[11], fields[16] = CREATED, expires, caps, curve
        return ":".join(fields)

    return "\n".join(
        [
            "tru::1:1791072876:0:3:1:5",
            key_line("pub", "22", "255", "KEYID", primary_caps, curve="ed25519"),
            f"fpr:::::::::{FPR}:",
            "uid:-::::1647302400::HASH::Example RM <rm@example.invalid>::::::::::0:",
            key_line("sub", sub_algo, sub_bits, "SUBID", sub_caps, expires=sub_expires),
            "fpr:::::::::FFFF0000FFFF0000FFFF0000FFFF0000FFFF0000:",
        ]
    )


class SignerAdmissionTest(unittest.TestCase):
    """A verdict needs a usable signing-capable key, not just a strong primary (#1628)."""

    def test_certify_only_primary_with_weak_sign_subkey_blocks(self) -> None:
        out = check(signing_listing())
        self.assertEqual((out["verdict"], out["strength_check"]), ("blocked", "fail"))
        self.assertEqual(out["signers"], [])
        self.assertIn("no signing-capable key", out["strength_note"])
        self.assertIn("below the ASF floor", out["strength_note"])

    def test_aggregate_uppercase_sign_capability_does_not_make_primary_a_signer(self) -> None:
        # gpg reports "cSC" for a certify-only primary whose subkey signs.
        out = check(signing_listing(primary_caps="cSC"))
        self.assertEqual((out["verdict"], out["strength_check"]), ("blocked", "fail"))
        self.assertEqual(out["signers"], [])
        self.assertIn("primary key has no signing capability", out["strength_note"])

    def test_admitted_dsa_signing_subkey_keeps_the_dsa_advisory(self) -> None:
        out = check(signing_listing(sub_algo="17", sub_bits="2048"))
        self.assertEqual(out["verdict"], "proceed")
        self.assertIn("DSA keys are discouraged", out["strength_note"])

    def test_admitted_signing_subkey_near_expiry_keeps_the_expiry_advisory(self) -> None:
        soon_date = TODAY + dt.timedelta(days=30)
        soon = soon_date.isoformat()
        noon = dt.datetime.combine(soon_date, dt.time(12), tzinfo=dt.UTC)
        epoch = str(int(noon.timestamp()))
        out = check(signing_listing(sub_bits="4096", sub_expires=epoch))
        self.assertEqual(out["verdict"], "proceed")
        self.assertIn(f"signing subkey expires on {soon}", out["strength_note"])

    def test_certify_only_primary_without_any_sign_key_blocks(self) -> None:
        out = check(signing_listing(sub_caps="e"))
        self.assertEqual((out["verdict"], out["strength_check"]), ("blocked", "fail"))
        self.assertIn("primary key has no signing capability", out["strength_note"])
        self.assertIn("no signing-capable key", out["strength_note"])

    def test_certify_only_primary_with_compliant_sign_subkey_proceeds(self) -> None:
        out = check(signing_listing(sub_bits="4096"))
        self.assertEqual(out["verdict"], "proceed")
        self.assertEqual(
            [(s["source"], s["algorithm"], s["bit_length"]) for s in out["signers"]],
            [("subkey", "RSA", 4096)],
        )

    def test_sign_capable_primary_alone_proceeds(self) -> None:
        out = check(signing_listing(primary_caps="sc", sub_caps="e"))
        self.assertEqual(out["verdict"], "proceed")
        self.assertEqual([s["source"] for s in out["signers"]], ["primary"])

    def test_expired_signing_subkey_does_not_rescue(self) -> None:
        out = check(signing_listing(sub_bits="4096", sub_expires=epoch("2026-06-01")))
        self.assertEqual((out["verdict"], out["signers"]), ("blocked", []))

    def test_synthetic_listings_without_caps_keep_legacy_behaviour(self) -> None:
        # The older fixture has no capability fields; the primary is still
        # treated as an eligible signer so existing integrations keep working.
        out = check(colons("1", "4096"))
        self.assertEqual(out["verdict"], "proceed")
        self.assertEqual([s["source"] for s in out["signers"]], ["primary"])

    def test_parse_colons_attaches_subkey_fingerprints(self) -> None:
        keys = check_key.parse_colons(signing_listing())
        self.assertEqual(keys[0]["fingerprint"], FPR)
        self.assertEqual(keys[0]["subs"][0]["fingerprint"], "FFFF0000FFFF0000FFFF0000FFFF0000FFFF0000")
        self.assertEqual(keys[0]["subs"][0]["caps"], "s")


if __name__ == "__main__":
    unittest.main()
