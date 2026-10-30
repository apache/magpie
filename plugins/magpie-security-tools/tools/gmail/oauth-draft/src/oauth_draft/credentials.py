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
"""Shared OAuth credential handling for the ``oauth-draft-*`` commands.

The three commands (``oauth-draft-setup``, ``oauth-draft-create``,
``oauth-draft-mark-read``) all need to:

- locate a credentials JSON on disk (CLI flag → env var → default path);
- parse it into a typed ``Credentials`` record;
- exchange the long-lived refresh token for a short-lived access token.

This module owns those primitives so the command modules can stay thin.
"""

from __future__ import annotations

import dataclasses
import json
import os
import pathlib
import urllib.error
import urllib.parse
import urllib.request

TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_API = "https://gmail.googleapis.com/gmail/v1/users/me"

# Default location of the credentials file. Was historically
# ``~/.config/airflow-s/gmail-oauth.json`` when this tool lived in the
# Apache Airflow security tracker repo; renamed to
# ``apache-magpie`` here as the framework was generalised. Existing
# adopters who still have the file at the old path can either move it
# or set ``$GMAIL_OAUTH_CREDENTIALS`` (or pass ``--credentials``).
DEFAULT_CREDENTIALS_DIR = pathlib.Path.home() / ".config" / "apache-magpie"
DEFAULT_CREDENTIALS_PATH = DEFAULT_CREDENTIALS_DIR / "gmail-oauth.json"


@dataclasses.dataclass
class Credentials:
    """OAuth credentials loaded from disk.

    ``from_address`` is required by ``oauth-draft-create`` (it is the
    ``From:`` header baked into outgoing drafts) but not by
    ``oauth-draft-mark-read``. Loaders that do not need it pass
    ``require_from_address=False`` to :meth:`load`.
    """

    client_id: str
    client_secret: str
    refresh_token: str
    from_address: str | None = None

    @classmethod
    def load(cls, path: pathlib.Path, *, require_from_address: bool = True) -> Credentials:
        data = json.loads(path.read_text())
        required = ["client_id", "client_secret", "refresh_token"]
        if require_from_address:
            required.append("from_address")
        missing = [k for k in required if not data.get(k)]
        if missing:
            raise SystemExit(
                f"{path}: missing required fields: {', '.join(missing)}. "
                f"See tools/gmail/oauth-draft/README.md for the expected shape."
            )
        return cls(
            client_id=data["client_id"],
            client_secret=data["client_secret"],
            refresh_token=data["refresh_token"],
            from_address=data.get("from_address"),
        )


def locate_credentials(explicit: str | None) -> pathlib.Path:
    """Resolve the credentials path: ``--credentials`` → env → default.

    Raises ``SystemExit`` with a helpful list of paths tried if none
    of the candidates exists.
    """
    candidates: list[str | None] = [
        explicit,
        os.environ.get("GMAIL_OAUTH_CREDENTIALS"),
        str(DEFAULT_CREDENTIALS_PATH),
    ]
    for c in candidates:
        if not c:
            continue
        p = pathlib.Path(c).expanduser()
        if p.is_file():
            return p
    raise SystemExit(
        "No Gmail OAuth credentials found. Tried: "
        + ", ".join(str(pathlib.Path(c).expanduser()) for c in candidates if c)
        + ". See tools/gmail/oauth-draft/README.md."
    )


def refresh_access_token(creds: Credentials) -> str:
    """Trade the long-lived refresh token for a ~1h access token."""
    body = urllib.parse.urlencode(
        {
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "refresh_token": creds.refresh_token,
            "grant_type": "refresh_token",
        }
    ).encode()
    req = urllib.request.Request(TOKEN_URL, data=body, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            payload = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise SystemExit(f"OAuth token refresh failed ({e.code}): {e.read().decode(errors='replace')}") from e
    token = payload.get("access_token")
    if not token:
        raise SystemExit(f"OAuth token refresh returned no access_token: {payload}")
    return str(token)
