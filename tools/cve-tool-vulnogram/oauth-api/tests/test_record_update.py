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

import json

import pytest

from vulnogram_api import record_update


def _write_session(path):
    path.write_text(
        json.dumps(
            {
                "host": "cveprocess.apache.org",
                "session_cookie_name": "connect.sid",
                "session_cookie_value": "s%3Atest",
                "from_address": "you@apache.org",
            }
        )
    )
    return path


def _no_current_record(monkeypatch):
    """Make _fetch_current_or_none return None so merge-mode guards
    behave as no-ops (the "first push, nothing to merge against" path).
    """
    monkeypatch.setattr(
        record_update,
        "_fetch_current_or_none",
        lambda *a, **kw: None,
    )


def test_invalid_cve_id_rejected(tmp_path, monkeypatch, capsys):
    creds = _write_session(tmp_path / "session.json")
    body = tmp_path / "body.json"
    body.write_text("{}")
    monkeypatch.setenv("VULNOGRAM_SESSION", str(creds))
    with pytest.raises(SystemExit) as excinfo:
        record_update.main(
            ["--cve-id", "not-a-cve", "--json-file", str(body)],
        )
    assert "CVE-YYYY-NNNN" in str(excinfo.value)


def test_missing_json_file_errors(tmp_path, monkeypatch):
    _write_session(tmp_path / "session.json")
    monkeypatch.setenv("VULNOGRAM_SESSION", str(tmp_path / "session.json"))
    with pytest.raises(SystemExit) as excinfo:
        record_update.main(
            ["--cve-id", "CVE-2026-12345", "--json-file", str(tmp_path / "missing.json")],
        )
    assert "not found" in str(excinfo.value)


def test_non_object_json_rejected(tmp_path, monkeypatch):
    _write_session(tmp_path / "session.json")
    body = tmp_path / "body.json"
    body.write_text(json.dumps([1, 2, 3]))
    monkeypatch.setenv("VULNOGRAM_SESSION", str(tmp_path / "session.json"))
    with pytest.raises(SystemExit) as excinfo:
        record_update.main(
            ["--cve-id", "CVE-2026-12345", "--json-file", str(body)],
        )
    assert "not a JSON object" in str(excinfo.value)


def test_session_expired_returns_2(tmp_path, monkeypatch, capsys):
    _write_session(tmp_path / "session.json")
    body = tmp_path / "body.json"
    body.write_text(json.dumps({"x": 1}))
    monkeypatch.setenv("VULNOGRAM_SESSION", str(tmp_path / "session.json"))
    _no_current_record(monkeypatch)

    def _raise_expired(*a, **kw):
        from vulnogram_api.client import SessionExpired

        raise SessionExpired("session expired")

    monkeypatch.setattr(record_update, "update_record", _raise_expired)
    rc = record_update.main(["--cve-id", "CVE-2026-12345", "--json-file", str(body)])
    assert rc == 2
    err = capsys.readouterr().err
    assert "session expired" in err


def test_save_failed_returns_5(tmp_path, monkeypatch, capsys):
    _write_session(tmp_path / "session.json")
    body = tmp_path / "body.json"
    body.write_text(json.dumps({"x": 1}))
    monkeypatch.setenv("VULNOGRAM_SESSION", str(tmp_path / "session.json"))
    _no_current_record(monkeypatch)

    def _raise_save_failed(*a, **kw):
        from vulnogram_api.client import RecordSaveFailed

        raise RecordSaveFailed("validation: missing field")

    monkeypatch.setattr(record_update, "update_record", _raise_save_failed)
    rc = record_update.main(["--cve-id", "CVE-2026-12345", "--json-file", str(body)])
    assert rc == 5
    err = capsys.readouterr().err
    assert "missing field" in err


def test_happy_path_returns_0(tmp_path, monkeypatch, capsys):
    _write_session(tmp_path / "session.json")
    body = tmp_path / "body.json"
    body.write_text(json.dumps({"x": 1}))
    monkeypatch.setenv("VULNOGRAM_SESSION", str(tmp_path / "session.json"))
    _no_current_record(monkeypatch)
    monkeypatch.setattr(
        record_update,
        "update_record",
        lambda *a, **kw: {"type": "saved"},
    )
    rc = record_update.main(["--cve-id", "CVE-2026-12345", "--json-file", str(body)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "saved" in out
    assert "CVE-2026-12345" in out


# ---------------------------------------------------------------------------
# Merge-mode integration tests (the new behaviour)
# ---------------------------------------------------------------------------


def _public_record() -> dict:
    """A current-record snapshot with `PUBLIC` state and one
    advisory reference. Models the canonical post-publication shape
    that the merge-mode guards exist to protect.
    """
    return {
        "comments": [],
        "files": [],
        "body": {
            "cveMetadata": {"cveId": "CVE-2026-12345", "state": "PUBLISHED"},
            "CNA_private": {"state": "PUBLIC"},
            "containers": {
                "cna": {
                    "affected": [
                        {
                            "packageName": "apache-foo-providers-bar",
                            "product": "Apache Foo Providers Bar",
                        }
                    ],
                    "references": [
                        {"url": "https://github.com/apache/foo/pull/100", "tags": ["patch"]},
                        {
                            "url": "https://lists.apache.org/thread/abc",
                            "tags": ["vendor-advisory"],
                        },
                    ],
                },
            },
        },
    }


def _new_doc_review_state_with_provider() -> dict:
    """A regenerated body that walks state back to REVIEW. Mirrors
    the CVE-2026-41016 regression class.
    """
    return {
        "cveMetadata": {"cveId": "CVE-2026-12345", "state": "PUBLISHED"},
        "CNA_private": {"state": "REVIEW"},
        "containers": {
            "cna": {
                "affected": [
                    {
                        "packageName": "apache-foo-providers-bar",
                        "product": "Apache Foo Providers Bar",
                    }
                ],
                "references": [
                    {"url": "https://github.com/apache/foo/pull/100", "tags": ["patch"]},
                ],
            },
        },
    }


def test_state_downgrade_refused_by_default(tmp_path, monkeypatch, capsys):
    _write_session(tmp_path / "session.json")
    body = tmp_path / "body.json"
    body.write_text(json.dumps(_new_doc_review_state_with_provider()))
    monkeypatch.setenv("VULNOGRAM_SESSION", str(tmp_path / "session.json"))
    monkeypatch.setattr(
        record_update,
        "_fetch_current_or_none",
        lambda *a, **kw: _public_record(),
    )
    push_called: list = []

    def _record_call(*a, **kw):
        push_called.append(a)
        return {"type": "saved"}

    monkeypatch.setattr(record_update, "update_record", _record_call)

    rc = record_update.main(["--cve-id", "CVE-2026-12345", "--json-file", str(body)])

    assert rc == 3
    err = capsys.readouterr().err
    assert "state downgrade" in err
    assert "PUBLIC" in err
    assert "REVIEW" in err
    assert push_called == [], "push must not fire when a guard refuses"


def test_state_downgrade_allowed_with_flag(tmp_path, monkeypatch, capsys):
    _write_session(tmp_path / "session.json")
    body = tmp_path / "body.json"
    body.write_text(json.dumps(_new_doc_review_state_with_provider()))
    monkeypatch.setenv("VULNOGRAM_SESSION", str(tmp_path / "session.json"))
    monkeypatch.setattr(
        record_update,
        "_fetch_current_or_none",
        lambda *a, **kw: _public_record(),
    )
    monkeypatch.setattr(
        record_update,
        "update_record",
        lambda *a, **kw: {"type": "saved"},
    )

    rc = record_update.main(
        [
            "--cve-id",
            "CVE-2026-12345",
            "--json-file",
            str(body),
            "--allow-state-downgrade",
        ]
    )

    assert rc == 0


def test_references_merged_by_default(tmp_path, monkeypatch):
    """The new emission carries only the patch reference; the current
    record's advisory URL must be preserved on the merged push.
    """
    _write_session(tmp_path / "session.json")
    new_body = _new_doc_review_state_with_provider()
    new_body["CNA_private"]["state"] = "PUBLIC"  # bypass state guard
    body = tmp_path / "body.json"
    body.write_text(json.dumps(new_body))
    monkeypatch.setenv("VULNOGRAM_SESSION", str(tmp_path / "session.json"))
    monkeypatch.setattr(
        record_update,
        "_fetch_current_or_none",
        lambda *a, **kw: _public_record(),
    )
    captured = {}

    def _capture(session, cve_id, document, **kw):
        captured["document"] = document
        return {"type": "saved"}

    monkeypatch.setattr(record_update, "update_record", _capture)

    rc = record_update.main(["--cve-id", "CVE-2026-12345", "--json-file", str(body)])

    assert rc == 0
    refs = captured["document"]["containers"]["cna"]["references"]
    urls = {ref["url"] for ref in refs}
    assert "https://github.com/apache/foo/pull/100" in urls
    assert "https://lists.apache.org/thread/abc" in urls


def test_references_wholesale_replace_with_flag(tmp_path, monkeypatch):
    _write_session(tmp_path / "session.json")
    new_body = _new_doc_review_state_with_provider()
    body = tmp_path / "body.json"
    body.write_text(json.dumps(new_body))
    monkeypatch.setenv("VULNOGRAM_SESSION", str(tmp_path / "session.json"))

    # Use a current record in REVIEW state so neither the
    # state-downgrade guard (PUBLIC → REVIEW) nor the new state-
    # upgrade-to-PUBLIC guard fires. The references-merge guard is
    # the only behaviour under test here.
    review_record = _public_record()
    review_record["body"]["CNA_private"]["state"] = "REVIEW"
    monkeypatch.setattr(
        record_update,
        "_fetch_current_or_none",
        lambda *a, **kw: review_record,
    )
    captured = {}

    def _capture(session, cve_id, document, **kw):
        captured["document"] = document
        return {"type": "saved"}

    monkeypatch.setattr(record_update, "update_record", _capture)

    rc = record_update.main(
        [
            "--cve-id",
            "CVE-2026-12345",
            "--json-file",
            str(body),
            "--replace-references",
        ]
    )

    assert rc == 0
    refs = captured["document"]["containers"]["cna"]["references"]
    urls = {ref["url"] for ref in refs}
    assert urls == {"https://github.com/apache/foo/pull/100"}


def test_product_change_refused_by_default(tmp_path, monkeypatch, capsys):
    """The regenerated body changes packageName from the providers
    package to the core package — the CVE-2026-41016 regression.
    """
    _write_session(tmp_path / "session.json")
    new_body = {
        "cveMetadata": {"cveId": "CVE-2026-12345", "state": "PUBLISHED"},
        "CNA_private": {"state": "PUBLIC"},  # keep state to isolate this guard
        "containers": {
            "cna": {
                "affected": [
                    {
                        "packageName": "apache-foo",
                        "product": "Apache Foo",
                    }
                ],
                "references": [
                    {"url": "https://github.com/apache/foo/pull/100", "tags": ["patch"]},
                    {"url": "https://lists.apache.org/thread/abc", "tags": ["vendor-advisory"]},
                ],
            },
        },
    }
    body = tmp_path / "body.json"
    body.write_text(json.dumps(new_body))
    monkeypatch.setenv("VULNOGRAM_SESSION", str(tmp_path / "session.json"))
    monkeypatch.setattr(
        record_update,
        "_fetch_current_or_none",
        lambda *a, **kw: _public_record(),
    )
    push_called: list = []

    def _record_call(*a, **kw):
        push_called.append(a)
        return {"type": "saved"}

    monkeypatch.setattr(record_update, "update_record", _record_call)

    rc = record_update.main(["--cve-id", "CVE-2026-12345", "--json-file", str(body)])

    assert rc == 3
    err = capsys.readouterr().err
    assert "product" in err.lower() or "packagename" in err.lower()
    assert "apache-foo-providers-bar" in err
    assert "apache-foo" in err
    assert push_called == []


def test_product_change_allowed_with_flag(tmp_path, monkeypatch):
    _write_session(tmp_path / "session.json")
    new_body = {
        "cveMetadata": {"cveId": "CVE-2026-12345", "state": "PUBLISHED"},
        "CNA_private": {"state": "PUBLIC"},
        "containers": {
            "cna": {
                "affected": [
                    {
                        "packageName": "apache-foo",
                        "product": "Apache Foo",
                    }
                ],
                "references": [
                    {"url": "https://github.com/apache/foo/pull/100", "tags": ["patch"]},
                    {"url": "https://lists.apache.org/thread/abc", "tags": ["vendor-advisory"]},
                ],
            },
        },
    }
    body = tmp_path / "body.json"
    body.write_text(json.dumps(new_body))
    monkeypatch.setenv("VULNOGRAM_SESSION", str(tmp_path / "session.json"))
    monkeypatch.setattr(
        record_update,
        "_fetch_current_or_none",
        lambda *a, **kw: _public_record(),
    )
    monkeypatch.setattr(record_update, "update_record", lambda *a, **kw: {"type": "saved"})

    rc = record_update.main(
        [
            "--cve-id",
            "CVE-2026-12345",
            "--json-file",
            str(body),
            "--allow-product-change",
        ]
    )

    assert rc == 0


def test_full_replace_overrides_all_three(tmp_path, monkeypatch, capsys):
    """`--full-replace` is the umbrella: it should allow a record
    that combines all three regressions (state downgrade + reference
    drop + product change) without firing any guard.
    """
    _write_session(tmp_path / "session.json")
    new_body = _new_doc_review_state_with_provider()  # REVIEW state
    new_body["containers"]["cna"]["affected"][0] = {
        "packageName": "apache-foo",
        "product": "Apache Foo",
    }  # changed product
    body = tmp_path / "body.json"
    body.write_text(json.dumps(new_body))
    monkeypatch.setenv("VULNOGRAM_SESSION", str(tmp_path / "session.json"))
    monkeypatch.setattr(
        record_update,
        "_fetch_current_or_none",
        lambda *a, **kw: _public_record(),
    )
    captured = {}

    def _capture(session, cve_id, document, **kw):
        captured["document"] = document
        return {"type": "saved"}

    monkeypatch.setattr(record_update, "update_record", _capture)

    rc = record_update.main(
        [
            "--cve-id",
            "CVE-2026-12345",
            "--json-file",
            str(body),
            "--full-replace",
        ]
    )

    assert rc == 0
    # References were replaced wholesale — the advisory URL is gone.
    refs = captured["document"]["containers"]["cna"]["references"]
    urls = {ref["url"] for ref in refs}
    assert "https://lists.apache.org/thread/abc" not in urls


def test_new_record_skips_all_guards(tmp_path, monkeypatch):
    """First push for a CVE ID: get_record returns None and the
    merge-mode guards are no-ops. The original document is pushed
    verbatim with no state-downgrade / product-change refusal.
    """
    _write_session(tmp_path / "session.json")
    new_body = _new_doc_review_state_with_provider()  # REVIEW state, fewer refs
    body = tmp_path / "body.json"
    body.write_text(json.dumps(new_body))
    monkeypatch.setenv("VULNOGRAM_SESSION", str(tmp_path / "session.json"))
    monkeypatch.setattr(
        record_update,
        "_fetch_current_or_none",
        lambda *a, **kw: None,  # record doesn't exist yet
    )
    captured = {}

    def _capture(session, cve_id, document, **kw):
        captured["document"] = document
        return {"type": "saved"}

    monkeypatch.setattr(record_update, "update_record", _capture)

    rc = record_update.main(["--cve-id", "CVE-2026-12345", "--json-file", str(body)])

    assert rc == 0
    # The pushed body matches the input verbatim (modulo a deep copy
    # that the guards make but skip mutating).
    assert captured["document"]["CNA_private"]["state"] == "REVIEW"
    refs = captured["document"]["containers"]["cna"]["references"]
    urls = {ref["url"] for ref in refs}
    assert urls == {"https://github.com/apache/foo/pull/100"}
