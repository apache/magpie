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
"""Session-credential file handling for the ``vulnogram-api-*`` commands.

The Vulnogram API helpers operate on a single JSON file that records
the host, the session cookie name + value (typically ``connect.sid``
on cveprocess.apache.org), and the user's ``From:`` address (mostly
informational — used in CLI output so the operator can verify the
right account is wired up).

Schema::

    {
      "host": "cveprocess.apache.org",
      "session_cookie_name": "connect.sid",
      "session_cookie_value": "s%3A...long-cookie-value...",
      "from_address": "user@apache.org"
    }
"""

from __future__ import annotations

import contextlib
import dataclasses
import json
import os
import pathlib
import stat
import sys
import tempfile

DEFAULT_CREDENTIALS_DIR = pathlib.Path.home() / ".config" / "apache-steward"
DEFAULT_CREDENTIALS_PATH = DEFAULT_CREDENTIALS_DIR / "vulnogram-session.json"

DEFAULT_HOST = "cveprocess.apache.org"
DEFAULT_COOKIE_NAME = "connect.sid"


@dataclasses.dataclass
class Session:
    """Vulnogram session loaded from disk."""

    host: str
    cookie_name: str
    cookie_value: str
    from_address: str | None = None

    def cookie_header(self) -> str:
        """Render the ``Cookie:`` header value the HTTP client sends."""
        return f"{self.cookie_name}={self.cookie_value}"

    @classmethod
    def load(cls, path: pathlib.Path) -> Session:
        data = json.loads(path.read_text())
        missing = [k for k in ("host", "session_cookie_name", "session_cookie_value") if not data.get(k)]
        if missing:
            raise SystemExit(
                f"{path}: missing required fields: {', '.join(missing)}. "
                f"Re-run `vulnogram-api-setup` to regenerate."
            )
        return cls(
            host=data["host"],
            cookie_name=data["session_cookie_name"],
            cookie_value=data["session_cookie_value"],
            from_address=data.get("from_address"),
        )


def locate_session(explicit: str | None) -> pathlib.Path:
    """Resolve credentials path: ``--credentials`` → env → default."""
    candidates: list[str | None] = [
        explicit,
        os.environ.get("VULNOGRAM_SESSION"),
        str(DEFAULT_CREDENTIALS_PATH),
    ]
    for c in candidates:
        if not c:
            continue
        p = pathlib.Path(c).expanduser()
        if p.is_file():
            return p
    raise SystemExit(
        "No Vulnogram session file found. Tried: "
        + ", ".join(str(pathlib.Path(c).expanduser()) for c in candidates if c)
        + ". Run `vulnogram-api-setup` first; see "
        "tools/vulnogram/oauth-api/README.md."
    )


def write_session_atomic(
    out_path: pathlib.Path,
    *,
    host: str,
    cookie_name: str,
    cookie_value: str,
    from_address: str | None,
) -> None:
    """Atomically write the session JSON at mode 0600.

    Mirrors ``tools/gmail/oauth-draft/src/oauth_draft/setup_creds.py`` —
    the cookie value is the long-lived secret of the whole API path, so
    the parent directory is locked to 0700 and the file is written via
    a same-directory tempfile + ``os.replace`` so the secret never
    transiently sits at default-umask permissions.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        out_path.parent.chmod(0o700)
    except OSError as e:
        # chmod failed (NFS / AFS / unowned dir on macOS / Windows
        # ACLs). Emit a single warning that captures both the failure
        # and the resulting open mode, rather than the two-warning
        # cascade that the previous code produced.
        parent_mode = out_path.parent.stat().st_mode & 0o777
        if parent_mode & 0o077:
            print(
                f"Warning: could not chmod 700 {out_path.parent}: {e}. "
                f"Current mode is {oct(parent_mode)} — session cookie "
                f"may be readable by other users on this host. "
                f"Consider moving --out to a directory you control.",
                file=sys.stderr,
            )
    else:
        # chmod succeeded; sanity-check the resulting mode in case a
        # concurrent writer / umask race left it open anyway.
        parent_mode = out_path.parent.stat().st_mode & 0o777
        if parent_mode & 0o077:
            print(
                f"Warning: {out_path.parent} mode is {oct(parent_mode)} "
                f"after chmod 700 — possible race or filesystem "
                f"override. Session cookie may be readable by others.",
                file=sys.stderr,
            )

    payload = (
        json.dumps(
            {
                "host": host,
                "session_cookie_name": cookie_name,
                "session_cookie_value": cookie_value,
                "from_address": from_address,
            },
            indent=2,
        )
        + "\n"
    )
    fd, tmp_name = tempfile.mkstemp(dir=str(out_path.parent), prefix=".vulnogram-session-", suffix=".tmp")
    try:
        os.fchmod(fd, stat.S_IRUSR | stat.S_IWUSR)  # 0o600
        with os.fdopen(fd, "w") as f:
            f.write(payload)
        os.replace(tmp_name, str(out_path))
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp_name)
        raise
