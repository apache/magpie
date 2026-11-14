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
"""Unit tests for the egress allowlist host-matching policy."""

from __future__ import annotations

import pytest

from egress_gateway.allowlist import _parse_extra, host_allowed


@pytest.mark.parametrize(
    "host",
    [
        "github.com",
        "api.github.com",
        "raw.githubusercontent.com",
        "objects.githubusercontent.com",
        "sheets.googleapis.com",
        "oauth2.googleapis.com",
        "docs.google.com",
        "pypi.org",
        "files.pythonhosted.org",
        "nvd.nist.gov",
        "cveawg.mitre.org",
        "api.osv.dev",
    ],
)
def test_allowed_hosts(host: str) -> None:
    assert host_allowed(host) is True


@pytest.mark.parametrize(
    "host",
    [
        "example.com",
        "api.openai.com",
        "evil.example.net",
        "apache.org.evil.com",  # suffix spoof — must NOT match ".apache.org"
        "notgithub.com",
        "githubusercontent.com.evil.io",
        "",
    ],
)
def test_denied_hosts(host: str) -> None:
    assert host_allowed(host) is False


def test_loopback_always_allowed() -> None:
    for host in ("localhost", "127.0.0.1", "::1"):
        assert host_allowed(host) is True


def test_port_and_trailing_dot_normalised() -> None:
    assert host_allowed("github.com:443") is True
    assert host_allowed("github.com.") is True
    assert host_allowed("GITHUB.COM") is True


def test_suffix_match_requires_dot_boundary() -> None:
    # "myapache.org" must not match the ".apache.org" suffix.
    assert host_allowed("myapache.org") is False


def test_extra_exact_and_suffix() -> None:
    extra_exact, extra_suffixes = _parse_extra("bedrock.example.com, .internal.corp")
    assert host_allowed("bedrock.example.com", extra_exact=extra_exact, extra_suffixes=extra_suffixes) is True
    assert host_allowed("svc.internal.corp", extra_exact=extra_exact, extra_suffixes=extra_suffixes) is True
    # Not granted without the extras.
    assert host_allowed("bedrock.example.com") is False


def test_parse_extra_ignores_blanks() -> None:
    exact, suffixes = _parse_extra("  , host.example , , .suf.example ,")
    assert exact == frozenset({"host.example"})
    assert suffixes == (".suf.example",)


def test_parse_extra_empty() -> None:
    assert _parse_extra(None) == (frozenset(), ())
    assert _parse_extra("") == (frozenset(), ())


@pytest.mark.parametrize(
    "host",
    [
        "whimsy.apache.org",
        "lists.apache.org",
        "issues.apache.org",
        "projects.apache.org",
        "cveprocess.apache.org",
        "dist.apache.org",
    ],
)
def test_asf_hosts_denied_by_default(host: str) -> None:
    assert host_allowed(host) is False


@pytest.mark.parametrize(
    "host",
    [
        "whimsy.apache.org:443",
        "whimsy.apache.org.",
        "WHIMSY.Apache.ORG",
    ],
)
def test_asf_host_normalization_does_not_bypass_policy(host: str) -> None:
    assert host_allowed(host) is False


def test_asf_hosts_require_explicit_gateway_override() -> None:
    exact, suffixes = _parse_extra("issues.apache.org,.apache.org")

    assert host_allowed("issues.apache.org", extra_exact=exact, extra_suffixes=suffixes)
    assert host_allowed("whimsy.apache.org", extra_exact=exact, extra_suffixes=suffixes)
    assert not host_allowed("apache.org.evil.com", extra_exact=exact, extra_suffixes=suffixes)
