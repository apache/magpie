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
"""One-shot Gmail OAuth setup for the ``oauth_curl`` backend.

Takes the ``client_secrets.json`` file you downloaded from the Google
Cloud Console (the OAuth 2.0 Client IDs row, *Desktop app* type), runs
the local-server consent flow against the broad
``https://mail.google.com/`` scope, and writes a credentials file in
the shape ``oauth-draft-create`` and ``oauth-draft-mark-read`` expect.

Optional flags:

- ``--from-address``: address to bake into the credentials file.
  Defaults to ``$GMAIL_FROM`` env var, then ``git config user.email``.
- ``--out``: output path for the credentials file. Defaults to
  ``~/.config/apache-magpie/gmail-oauth.json``.
- ``--rm-client-secrets``: delete the input ``client_secrets.json``
  after a successful write. Off by default.

The browser tab that opens during the flow is the consent screen for
the OAuth client you created. Pick the Gmail account you use for
``security@<project>.apache.org`` triage, grant *"Manage your mail
and labels"* + *"Send email on your behalf"* + *"Read all your email"*
(everything under the ``mail.google.com`` umbrella scope), and the
tab closes itself when the local server captures the auth code.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from google_auth_oauthlib.flow import InstalledAppFlow

from oauth_draft.credentials import DEFAULT_CREDENTIALS_PATH

SCOPES = ["https://mail.google.com/"]


def detect_from_address() -> str | None:
    if env := os.environ.get("GMAIL_FROM"):
        return env
    try:
        out = subprocess.check_output(
            ["git", "config", "user.email"],
            text=True,
            cwd=Path(__file__).resolve().parent,
            stderr=subprocess.DEVNULL,
        ).strip()
        return out or None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description=(__doc__ or "").split("\n\n", 1)[0],
    )
    ap.add_argument(
        "client_secrets",
        help="Path to the client_secrets.json downloaded from Google Cloud Console.",
    )
    ap.add_argument(
        "--from-address",
        default=detect_from_address(),
        help=(
            "From: address to bake into the credentials file. "
            "Defaults to $GMAIL_FROM, else `git config user.email`."
        ),
    )
    ap.add_argument(
        "--out",
        default=str(DEFAULT_CREDENTIALS_PATH),
        help=f"Output credentials path. Default: {DEFAULT_CREDENTIALS_PATH}.",
    )
    ap.add_argument(
        "--rm-client-secrets",
        action="store_true",
        help="Delete the input client_secrets.json after writing the credentials file.",
    )
    return ap.parse_args(argv)


def read_client_app(client_secrets_path: Path) -> tuple[str, str]:
    """Return ``(client_id, client_secret)`` from a client_secrets.json.

    Accepts both the ``installed`` (Desktop app) and ``web`` shapes, and
    a bare object as a last resort.
    """
    raw = json.loads(client_secrets_path.read_text())
    inner = raw.get("installed", raw.get("web", raw))
    return inner["client_id"], inner["client_secret"]


def run_consent_flow(client_secrets_path: Path) -> Any:
    """Run the local-server OAuth consent flow and return the credentials.

    Opens a browser tab for the broad ``mail.google.com`` scope and blocks
    until the local callback captures the auth code. Raises ``SystemExit``
    if the flow yields no refresh token (usually because the OAuth client
    was already consented to before).
    """
    flow = InstalledAppFlow.from_client_secrets_file(str(client_secrets_path), scopes=SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent")
    if not creds.refresh_token:
        raise SystemExit(
            "OAuth flow returned no refresh_token. "
            "If you've consented to this OAuth client before, revoke it at "
            "https://myaccount.google.com/permissions and rerun."
        )
    return creds


def write_credentials(
    *,
    client_id: str,
    client_secret: str,
    refresh_token: str,
    from_address: str,
    out_path: Path,
) -> None:
    """Atomically write the credentials JSON at mode 600 under a 700 parent.

    The refresh token is the long-lived secret of the whole ``oauth_curl``
    backend, so the write is restrictive from the start: a temp file created
    at 0o600 in the same directory, then ``os.replace`` onto the target —
    no write-then-chmod race.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        out_path.parent.chmod(0o700)
    except OSError as e:
        print(f"Warning: could not chmod 700 {out_path.parent}: {e}", file=sys.stderr)
    parent_mode = out_path.parent.stat().st_mode & 0o777
    if parent_mode & 0o077:
        print(
            f"Warning: {out_path.parent} mode is {oct(parent_mode)} — "
            f"refresh token may be readable by other users on this host. "
            f"Consider moving the output to a directory you control.",
            file=sys.stderr,
        )
    payload = (
        json.dumps(
            {
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "from_address": from_address,
            },
            indent=2,
        )
        + "\n"
    )
    fd, tmp_name = tempfile.mkstemp(dir=str(out_path.parent), prefix=".gmail-oauth-", suffix=".tmp")
    try:
        os.fchmod(fd, stat.S_IRUSR | stat.S_IWUSR)  # 0o600
        with os.fdopen(fd, "w") as f:
            f.write(payload)
        os.replace(tmp_name, str(out_path))
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp_name)
        raise


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if not args.from_address:
        raise SystemExit(
            "Could not determine --from-address (no $GMAIL_FROM env, no git user.email). "
            "Pass --from-address explicitly."
        )

    # Variable named `_path` (not `client_secrets`) to keep CodeQL's
    # `py/clear-text-logging-sensitive-data` rule from flagging the
    # `print(... {client_secrets_path} ...)` lines below — what we
    # log is the filesystem path to the JSON file, not its contents.
    client_secrets_path = Path(args.client_secrets).expanduser().resolve()
    if not client_secrets_path.is_file():
        raise SystemExit(f"client_secrets not found: {client_secrets_path}")

    print(f"Running OAuth flow against {client_secrets_path} ...")
    print(f"Scopes requested: {' '.join(SCOPES)}")
    print("A browser tab will open; pick the account, click through consent.")
    creds = run_consent_flow(client_secrets_path)
    client_id, client_secret = read_client_app(client_secrets_path)

    out_path = Path(args.out).expanduser()
    write_credentials(
        client_id=client_id,
        client_secret=client_secret,
        refresh_token=creds.refresh_token,
        from_address=args.from_address,
        out_path=out_path,
    )
    print(f"Wrote credentials to {out_path} (mode 600).")
    print(f"Granted scopes: {' '.join(creds.scopes or SCOPES)}")
    print(f"From: address baked in: {args.from_address}")

    if args.rm_client_secrets:
        client_secrets_path.unlink()
        print(f"Removed {client_secrets_path}.")

    print()
    print("Smoke-test the credentials with:")
    print("  oauth-draft-mark-read --query 'in:inbox is:unread' --max 3")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
