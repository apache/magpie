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
"""Connection + folder configuration, read from the adopter's shell environment.

The adapter does not read ``<project-config>/project.md`` itself — the calling
skill resolves the ``imap_*`` variables declared there and exports them into
the environment (see `AGENTS.md`, *Tool adapters declare their adopter-side
variables*).
"""

from __future__ import annotations

import ipaddress
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

FOLDERS_OFF = ("none", "off", "disabled", "")

DEFAULT_PORT_TLS = 993
DEFAULT_PORT_PLAIN = 143


class ConfigError(SystemExit):
    """Raised when the environment does not declare a usable connection."""


def is_loopback_host(host: str) -> bool:
    """
    True for ``localhost`` or a literal loopback address (``127.0.0.0/8``, ``::1``).

    The host is matched as written and never resolved: a DNS answer must not
    be able to make a remote name count as loopback. ``localhost`` itself is
    pinned to ``127.0.0.1`` when connecting (see ``plaintext_connect_host``).
    """
    name = host.strip().lower()
    if name == "localhost":
        return True
    try:
        return ipaddress.ip_address(name).is_loopback
    except ValueError:
        return False


def plaintext_connect_host(host: str) -> str:
    """
    The address to open a plain connection to: ``localhost`` becomes
    ``127.0.0.1`` so the system resolver cannot send it anywhere else.
    """
    return "127.0.0.1" if host.strip().lower() == "localhost" else host.strip()


PLAINTEXT_REFUSED = (
    "IMAP_SOURCE_SSL is off, which is allowed only for a loopback host "
    "(localhost, 127.0.0.0/8 or ::1); got {host!r}. Use TLS for any other server."
)


@dataclass(frozen=True)
class ImapConfig:
    host: str
    port: int
    use_tls: bool
    user: str
    password: str
    list_folder: str
    sent_folder: str | None
    drafts_folder: str | None
    archive_template: str | None

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> ImapConfig:
        source = os.environ if env is None else env
        host = source.get("IMAP_SOURCE_HOST", "").strip()
        if not host:
            raise ConfigError("IMAP_SOURCE_HOST is not set — see tools/mail-source/imap/README.md")
        user = source.get("IMAP_SOURCE_USER", "").strip()
        if not user:
            raise ConfigError("IMAP_SOURCE_USER is not set — see tools/mail-source/imap/README.md")
        password = _read_password(source)
        use_tls = source.get("IMAP_SOURCE_SSL", "1").strip().lower() not in ("0", "false", "no")
        if not use_tls and not is_loopback_host(host):
            raise ConfigError(PLAINTEXT_REFUSED.format(host=host))
        default_port = str(DEFAULT_PORT_TLS if use_tls else DEFAULT_PORT_PLAIN)
        try:
            port = int(source.get("IMAP_SOURCE_PORT", default_port).strip())
        except ValueError as exc:
            raise ConfigError(f"IMAP_SOURCE_PORT is not an integer: {exc}") from exc
        drafts = source.get("IMAP_SOURCE_DRAFTS_FOLDER", "Drafts").strip()
        sent = source.get("IMAP_SOURCE_SENT_FOLDER", "Sent").strip()
        archive = source.get("IMAP_SOURCE_ARCHIVE_TEMPLATE", "").strip()
        return cls(
            host=host,
            port=port,
            use_tls=use_tls,
            user=user,
            password=password,
            list_folder=source.get("IMAP_SOURCE_FOLDER", "INBOX").strip() or "INBOX",
            sent_folder=None if sent.lower() in FOLDERS_OFF else sent,
            drafts_folder=None if drafts.lower() in FOLDERS_OFF else drafts,
            archive_template=archive or None,
        )


def _read_password(env: Mapping[str, str]) -> str:
    direct = env.get("IMAP_SOURCE_PASSWORD", "")
    if direct:
        return direct
    password_file = env.get("IMAP_SOURCE_PASSWORD_FILE", "").strip()
    if password_file:
        path = Path(password_file)
        try:
            password = path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise ConfigError(f"cannot read IMAP_SOURCE_PASSWORD_FILE ({password_file}): {exc}") from exc
        if password:
            return password
        raise ConfigError(f"IMAP_SOURCE_PASSWORD_FILE ({password_file}) is empty")
    raise ConfigError(
        "neither IMAP_SOURCE_PASSWORD nor IMAP_SOURCE_PASSWORD_FILE is set — "
        "prefer the file form so the secret stays out of the process list"
    )
