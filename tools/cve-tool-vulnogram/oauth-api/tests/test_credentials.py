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
import os
import stat

import pytest

from vulnogram_api.credentials import (
    Session,
    locate_session,
    write_session_atomic,
)


def write_session(path, **overrides):
    data = {
        "host": "cveprocess.apache.org",
        "session_cookie_name": "connect.sid",
        "session_cookie_value": "s%3Aabc.def",
        "from_address": "you@apache.org",
    }
    data.update(overrides)
    path.write_text(json.dumps(data))
    return path


def test_load_full_record(tmp_path):
    p = write_session(tmp_path / "s.json")
    s = Session.load(p)
    assert s.host == "cveprocess.apache.org"
    assert s.cookie_name == "connect.sid"
    assert s.cookie_value == "s%3Aabc.def"
    assert s.from_address == "you@apache.org"
    assert s.cookie_header() == "connect.sid=s%3Aabc.def"


def test_load_missing_cookie_value(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(
        json.dumps(
            {"host": "x", "session_cookie_name": "connect.sid"},
        )
    )
    with pytest.raises(SystemExit) as excinfo:
        Session.load(p)
    assert "session_cookie_value" in str(excinfo.value)


def test_load_missing_host(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(
        json.dumps(
            {"session_cookie_name": "connect.sid", "session_cookie_value": "x"},
        )
    )
    with pytest.raises(SystemExit) as excinfo:
        Session.load(p)
    assert "host" in str(excinfo.value)


def test_locate_explicit_arg_wins(tmp_path):
    a = write_session(tmp_path / "a.json")
    write_session(tmp_path / "b.json")
    assert locate_session(str(a)) == a


def test_locate_uses_env_var(tmp_path, monkeypatch):
    p = write_session(tmp_path / "via-env.json")
    monkeypatch.setenv("VULNOGRAM_SESSION", str(p))
    assert locate_session(None) == p


def test_locate_missing_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("VULNOGRAM_SESSION", raising=False)
    monkeypatch.setattr(
        "vulnogram_api.credentials.DEFAULT_CREDENTIALS_PATH",
        tmp_path / "does-not-exist.json",
    )
    with pytest.raises(SystemExit) as excinfo:
        locate_session(None)
    assert "vulnogram-api-setup" in str(excinfo.value)


def test_write_atomic_mode_600(tmp_path):
    out = tmp_path / "vulnogram-session.json"
    write_session_atomic(
        out,
        host="cveprocess.apache.org",
        cookie_name="connect.sid",
        cookie_value="s%3Aabc.def",
        from_address="you@apache.org",
    )
    assert out.is_file()
    mode = out.stat().st_mode & 0o777
    assert mode == stat.S_IRUSR | stat.S_IWUSR  # 0o600
    parent_mode = out.parent.stat().st_mode & 0o777
    assert parent_mode == 0o700
    payload = json.loads(out.read_text())
    assert payload["host"] == "cveprocess.apache.org"
    assert payload["session_cookie_value"] == "s%3Aabc.def"


def test_write_atomic_overwrite_replaces_atomically(tmp_path):
    out = tmp_path / "vulnogram-session.json"
    out.write_text("OLD")
    out.chmod(0o644)
    write_session_atomic(
        out,
        host="x",
        cookie_name="connect.sid",
        cookie_value="new-cookie",
        from_address=None,
    )
    # No leftover tempfiles in the same directory.
    siblings = [p.name for p in out.parent.iterdir()]
    assert siblings == [out.name], siblings
    payload = json.loads(out.read_text())
    assert payload["session_cookie_value"] == "new-cookie"
    # Mode locked back to 600 even though the existing file was 644.
    assert out.stat().st_mode & 0o777 == 0o600
    # And from_address wrote None as JSON null (not omitted).
    assert payload["from_address"] is None
    # Side-effect-free check: ensure os.path.dirname looks right.
    assert os.path.dirname(out) == str(tmp_path)
