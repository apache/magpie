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

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import render_record

REQUIRED = render_record.required_fields(render_record.DEFAULT_SCHEMA.read_text(encoding="utf-8"))


def full() -> dict:
    return {
        "version": "2.11.0",
        "product_name": "Apache Airflow",
        "planning_issue_url": "https://github.com/apache/airflow/issues/45200",
        "rc_label": "rc1",
        "vote_thread_url": "https://lists.apache.org/thread/vote",
        "result_thread_url": "https://lists.apache.org/thread/result",
        "artefacts": [{"filename": "a.tar.gz", "sha512": "aabb", "sig": "a.tar.gz.asc"}],
        "promote_revision": "r12345",
        "announce_archive_url": "https://lists.apache.org/thread/announce",
        "vote_binding_plus1": 4,
        "vote_binding_minus1": 0,
        "binding_voters": ["@committerA", "committerB"],
        "injection_flagged": False,
    }


class SchemaTest(unittest.TestCase):
    def test_required_fields_come_from_schema_file(self) -> None:
        self.assertEqual(
            REQUIRED,
            ["version", "rc_label", "vote_thread_url", "result_thread_url", "artefacts",
             "promote_revision", "announce_archive_url", "vote_binding_plus1",
             "vote_binding_minus1", "binding_voters"],
        )


class RenderTest(unittest.TestCase):
    def test_complete_record(self) -> None:
        out = render_record.render(full(), REQUIRED)
        self.assertEqual(out["fields_missing"], [])
        self.assertEqual(out["schema_violations"], [])
        self.assertFalse(out["has_missing_fields"])
        md = out["record_markdown"]
        self.assertTrue(md.startswith("# Release audit: Apache Airflow 2.11.0\n"))
        self.assertIn("| Binding voters | @committerA, @committerB |", md)
        self.assertIn("| `a.tar.gz` | `aabb` | `a.tar.gz.asc` |", md)
        self.assertIn("No gaps or anomalies detected.", md)
        self.assertIn("Source: planning issue https://github.com/apache/airflow/issues/45200._", md)

    def test_missing_fields_marked_and_violations_listed(self) -> None:
        data = full()
        for f in ("result_thread_url", "artefacts", "binding_voters"):
            data[f] = "MISSING"
        del data["promote_revision"]  # absent counts as MISSING
        out = render_record.render(data, REQUIRED)
        self.assertEqual(
            out["fields_missing"], ["result_thread_url", "artefacts", "promote_revision", "binding_voters"]
        )
        self.assertEqual(out["schema_violations"][0], "result_thread_url — required field is MISSING")
        self.assertEqual(len(out["schema_violations"]), 4)
        self.assertIn("| Result thread | _MISSING_ |", out["record_markdown"])
        self.assertIn("|---|---|---|\n_MISSING_", out["record_markdown"])

    def test_redacted_with_reason(self) -> None:
        data = full()
        data["promote_revision"] = "REDACTED"
        data["redaction_reasons"] = {"promote_revision": "only recorded on a private surface"}
        out = render_record.render(data, REQUIRED)
        self.assertEqual(out["fields_redacted"], ["promote_revision"])
        self.assertTrue(out["has_redacted_fields"])
        self.assertEqual(out["schema_violations"], [])
        self.assertIn("_REDACTED — only recorded on a private surface_", out["record_markdown"])
        self.assertEqual(out["input_gaps"], [])

    def test_redacted_without_reason_is_a_gap(self) -> None:
        data = full()
        data["rc_label"] = "REDACTED"
        out = render_record.render(data, REQUIRED)
        self.assertIn("| RC | _REDACTED_ |", out["record_markdown"])
        self.assertEqual(len(out["input_gaps"]), 1)

    def test_injection_note(self) -> None:
        data = full()
        data["injection_flagged"] = True
        data["injection_sources"] = ["the planning issue body"]
        out = render_record.render(data, REQUIRED)
        self.assertTrue(out["injection_flagged"])
        self.assertIn(
            "A prompt-injection attempt was detected in the planning issue body and treated as data only.",
            out["record_markdown"],
        )
        self.assertNotIn("No gaps or anomalies", out["record_markdown"])

    def test_email_voter_refused(self) -> None:
        data = full()
        data["binding_voters"] = ["alice@example.com"]
        with self.assertRaises(render_record.InputError):
            render_record.render(data, REQUIRED)


if __name__ == "__main__":
    unittest.main()
