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

from vulnogram_api import check


def _write_session(path):
    path.write_text(
        json.dumps(
            {
                "host": "cveprocess.apache.org",
                "session_cookie_name": "connect.sid",
                "session_cookie_value": "s%3Atest",
                "from_address": None,
            }
        )
    )
    return path


def test_not_configured_returns_2(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("VULNOGRAM_SESSION", raising=False)
    monkeypatch.setattr(
        "vulnogram_api.credentials.DEFAULT_CREDENTIALS_PATH",
        tmp_path / "missing.json",
    )
    monkeypatch.setattr(
        "vulnogram_api.check.DEFAULT_CREDENTIALS_PATH",
        tmp_path / "missing.json",
    )
    rc = check.main([])
    assert rc == 2
    assert "not-configured" in capsys.readouterr().out


def test_quiet_suppresses_stdout(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("VULNOGRAM_SESSION", raising=False)
    monkeypatch.setattr(
        "vulnogram_api.check.DEFAULT_CREDENTIALS_PATH",
        tmp_path / "missing.json",
    )
    rc = check.main(["--quiet"])
    assert rc == 2
    assert capsys.readouterr().out == ""


def test_valid_session_returns_0(tmp_path, monkeypatch, capsys):
    creds = _write_session(tmp_path / "session.json")
    monkeypatch.setenv("VULNOGRAM_SESSION", str(creds))
    monkeypatch.setattr(check, "probe", lambda *a, **kw: "valid")
    rc = check.main([])
    assert rc == 0
    assert "valid" in capsys.readouterr().out


def test_expired_session_returns_1(tmp_path, monkeypatch, capsys):
    creds = _write_session(tmp_path / "session.json")
    monkeypatch.setenv("VULNOGRAM_SESSION", str(creds))
    monkeypatch.setattr(check, "probe", lambda *a, **kw: "expired")
    rc = check.main([])
    assert rc == 1
    assert "expired" in capsys.readouterr().out


def test_unknown_error_returns_3(tmp_path, monkeypatch, capsys):
    creds = _write_session(tmp_path / "session.json")
    monkeypatch.setenv("VULNOGRAM_SESSION", str(creds))
    monkeypatch.setattr(check, "probe", lambda *a, **kw: "error: connection refused")
    rc = check.main([])
    assert rc == 3


def test_unknown_error_writes_to_stderr_not_stdout(tmp_path, monkeypatch, capsys):
    """Error results must go to stderr so `2>/dev/null` gives a clean channel.

    Regression: the previous code printed every result to stdout in
    non-quiet mode and only emitted to stderr under ``--quiet`` (and
    only via a ternary that swallowed it the rest of the time).
    """
    creds = _write_session(tmp_path / "session.json")
    monkeypatch.setenv("VULNOGRAM_SESSION", str(creds))
    monkeypatch.setattr(check, "probe", lambda *a, **kw: "error: connection refused")
    rc = check.main([])
    captured = capsys.readouterr()
    assert rc == 3
    assert "error: connection refused" in captured.err
    assert "error: connection refused" not in captured.out


def test_unknown_error_quiet_still_writes_to_stderr(tmp_path, monkeypatch, capsys):
    """Under ``--quiet``, stdout stays empty but stderr still surfaces the reason."""
    creds = _write_session(tmp_path / "session.json")
    monkeypatch.setenv("VULNOGRAM_SESSION", str(creds))
    monkeypatch.setattr(check, "probe", lambda *a, **kw: "error: timeout")
    rc = check.main(["--quiet"])
    captured = capsys.readouterr()
    assert rc == 3
    assert captured.out == ""
    assert "error: timeout" in captured.err
