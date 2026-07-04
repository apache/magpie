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
"""Egress host-allowlist policy + the proxy.py plugin that enforces it.

The host-matching policy (:func:`host_allowed`) is a pure function with no
third-party imports, so it is cheap to unit-test in isolation. The
:class:`EgressAllowlistPlugin` wires that policy into proxy.py's
``before_upstream_connection`` hook: any CONNECT / request whose target host
is not on the allowlist is rejected with a 403 before any upstream socket is
opened. The gateway — not the sandbox — becomes the egress-control point.

The default allowlist mirrors the curated host set the framework's secure
sandbox already trusts (`sandbox.network.allowedDomains`): ASF infra, GitHub,
Google APIs, PyPI. Adopters extend it without editing code via the
``EGRESS_ALLOW_EXTRA`` environment variable (comma-separated hosts; a leading
dot means "this suffix and all sub-hosts").
"""

from __future__ import annotations

import os

# Exact hostnames that do not fall under an allowed suffix.
ALLOW_EXACT: frozenset[str] = frozenset(
    {
        "github.com",
        "api.github.com",
        "api.bitbucket.org",
        "pypi.org",
        "docs.google.com",
        "nvd.nist.gov",
        "cve.org",
        "www.cve.org",
        "cveawg.mitre.org",
        "issues.apache.org",
    }
)

# Any host ending in one of these suffixes is allowed.
ALLOW_SUFFIXES: tuple[str, ...] = (
    ".apache.org",  # whimsy, lists, projects, issues, every project site
    ".googleapis.com",  # sheets / gmail / oauth2
    ".githubusercontent.com",  # raw / objects / codeload
    ".pythonhosted.org",  # uv / pip wheel downloads
)

# Loopback is always allowed — local inference endpoints (Ollama/vLLM) and
# local fixtures never leave the host.
ALLOW_LOOPBACK: frozenset[str] = frozenset({"localhost", "127.0.0.1", "::1"})

_ENV_EXTRA = "EGRESS_ALLOW_EXTRA"


def _parse_extra(raw: str | None) -> tuple[frozenset[str], tuple[str, ...]]:
    """Split EGRESS_ALLOW_EXTRA into (exact-hosts, suffixes).

    Entries starting with '.' are treated as suffixes; everything else is an
    exact host. Whitespace and empty entries are ignored.
    """
    exact: set[str] = set()
    suffixes: list[str] = []
    for entry in (raw or "").split(","):
        token = entry.strip().lower()
        if token.startswith("."):
            host = token.strip(".")
            if host:
                suffixes.append("." + host)
        else:
            host = token.rstrip(".")
            if host:
                exact.add(host)
    return frozenset(exact), tuple(suffixes)


def host_allowed(
    host: str,
    *,
    extra_exact: frozenset[str] | None = None,
    extra_suffixes: tuple[str, ...] | None = None,
) -> bool:
    """Return True if *host* is permitted egress.

    *host* may include a ``:port`` suffix and trailing dot; both are
    normalised away. Bare and bracketed IPv6 literals (``::1``, ``[::1]:443``)
    are handled without mangling. Matching is case-insensitive.
    """
    norm = host.strip().lower().rstrip(".")
    if norm.startswith("["):  # bracketed IPv6, optionally [::1]:port
        end = norm.find("]")
        if end != -1:
            norm = norm[1:end]
    elif norm.count(":") == 1:  # host:port (a bare IPv6 has >1 colon)
        norm = norm.split(":", 1)[0]
    if not norm:
        return False
    if norm in ALLOW_LOOPBACK or norm in ALLOW_EXACT:
        return True
    if extra_exact and norm in extra_exact:
        return True
    if norm.endswith(ALLOW_SUFFIXES):
        return True
    return bool(extra_suffixes) and norm.endswith(extra_suffixes)


# --- proxy.py plugin -------------------------------------------------------

from proxy.common.utils import text_  # noqa: E402  (kept below the pure policy)
from proxy.http.exception import HttpRequestRejected  # noqa: E402
from proxy.http.parser import HttpParser  # noqa: E402
from proxy.http.proxy import HttpProxyBasePlugin  # noqa: E402


class EgressAllowlistPlugin(HttpProxyBasePlugin):
    """Reject any upstream host not on the allowlist (default-deny)."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self._extra_exact, self._extra_suffixes = _parse_extra(os.environ.get(_ENV_EXTRA))

    def before_upstream_connection(self, request: HttpParser) -> HttpParser | None:
        host = text_(request.host) if request.host else ""
        if not host_allowed(
            host,
            extra_exact=self._extra_exact,
            extra_suffixes=self._extra_suffixes,
        ):
            raise HttpRequestRejected(
                status_code=403,
                reason=b"Forbidden",
                body=b"egress-gateway: host not on allowlist\n",
            )
        return request

    def handle_client_request(self, request: HttpParser) -> HttpParser | None:
        return request

    def handle_upstream_chunk(self, chunk: memoryview) -> memoryview:
        return chunk

    def on_upstream_connection_close(self) -> None:
        pass
