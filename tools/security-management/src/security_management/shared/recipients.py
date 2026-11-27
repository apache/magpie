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
"""The security CC and Bcc of every security draft, per `tools/mail-source/contract.md` § *Security draft CC resolution*.

Each key resolves through the layers (project, organization, framework
defaults) to the **first layer that declares it**, even as null or blank;
a lower layer is consulted only when the key is absent. `security_list`,
trimmed, is the CC when configured (and clears a previous run's
fallback); missing, blank, `TODO…` or a `<placeholder>` is unconfigured.
Otherwise `security_inbox.foundation_security_address` is the fallback,
with a warning; when the project declares that key null or blank, the
fallback is disabled. With neither, the draft is blocked. The CC array
keeps the other recipients and drops duplicates.

The Bcc: when the project has no dedicated security list (`security_list`
unconfigured, or equal to the foundation address) and
`security_inbox.bcc_private_list` resolves true, the project's
`private_list` goes in `bcc`, so the governance body sees what reporters
are told. The private list is never a To or Cc recipient: it is dropped
from `cc`, and a `security_list` naming it counts as no dedicated list (the
CC falls back to the foundation address, with a warning; `search_list`
still names it, since reports arrive there).

A flat input (keys already resolved, dotted) is read as one layer.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from email.utils import getaddresses
from typing import Any

FALLBACK_KEY = ("security_inbox", "foundation_security_address")
BCC_FLAG_KEY = ("security_inbox", "bcc_private_list")
_ADDRESS = re.compile(r"^[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+$")
_MISSING = object()


def _lookup(layer: Mapping[str, Any], path: Sequence[str]) -> object:
    dotted = ".".join(path)
    if dotted in layer:
        return layer[dotted]
    node: object = layer
    for part in path:
        if not isinstance(node, Mapping) or part not in node:
            return _MISSING
        node = node[part]
    return node


def _resolve(layers: Sequence[Mapping[str, Any]], path: Sequence[str]) -> object:
    for layer in layers:
        value = _lookup(layer, path)
        if value is not _MISSING:
            return value
    return None


def configured(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    if not text or text.upper().startswith("TODO") or "<" in text or not _ADDRESS.match(text):
        return None
    return text


def _flag(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return value is not None and str(value).strip().lower() in ("true", "yes", "1", "on")


def _blocked(warning: str) -> dict[str, Any]:
    return {
        "security_cc": None,
        "cc_fallback": None,
        "warning": True,
        "warning_text": warning,
        "draft_blocked": True,
        "cc": [],
        "bcc": [],
        "private_list": None,
        "search_list": None,
    }


def _addresses(value: object) -> list[str]:
    if value is None:
        return []
    items: Iterable[object] = value if isinstance(value, (list, tuple)) else [value]
    return [addr.strip() for _, addr in getaddresses([str(i) for i in items]) if addr.strip()]


def private_in_recipients(private_list: object, to: object = None, cc: object = None) -> list[str]:
    """The To / Cc addresses that are the private list (case-insensitive); it belongs in Bcc only."""
    private = configured(private_list)
    if private is None:
        return []
    return [a for a in [*_addresses(to), *_addresses(cc)] if a.lower() == private.lower()]


def security_cc(data: Mapping[str, Any]) -> dict[str, Any]:
    if any(k in data for k in ("project", "organization", "framework_defaults")):
        layers = [data.get(k) or {} for k in ("project", "organization", "framework_defaults")]
    else:
        layers = [data]
    listed = configured(_resolve(layers, ("security_list",)))
    foundation = configured(_resolve(layers, FALLBACK_KEY))
    private = configured(_resolve(layers, ("private_list",)))
    existing = [str(c).strip() for c in data.get("existing_cc") or [] if str(c).strip()]
    # A security_list that is the private list is not a dedicated security list, and never a CC.
    names_private = bool(private and listed and listed.lower() == private.lower())
    cc_list = None if names_private else listed
    cc: str | None
    fallback: str | None
    warning: str | None
    if cc_list:
        cc, fallback, warning = cc_list, None, None
    else:
        fallback = foundation
        cc = fallback
        missing = (
            f"security_list names the private list {private}, which is never a To or Cc recipient"
            if names_private
            else "security_list is not configured"
        )
        unresolved = (
            "no security CC can be resolved: set security_list (or the organization fallback) before drafting"
        )
        warning = (
            f"{missing}: CC falls back to {fallback}"
            if fallback
            else f"{missing}: {unresolved}"
            if names_private
            else unresolved
        )
    if cc is None:
        return _blocked(str(warning))
    dedicated = cc_list is not None and (foundation is None or cc_list.lower() != foundation.lower())
    bcc = [private] if private and not dedicated and _flag(_resolve(layers, BCC_FLAG_KEY)) else []
    merged: list[str] = []
    for address in [*existing, cc]:
        if private_in_recipients(private, cc=address):
            continue
        if address.lower() not in (m.lower() for m in merged):
            merged.append(address)
    return {
        "security_cc": cc,
        "cc_fallback": fallback,
        "warning": warning is not None,
        "warning_text": warning,
        "draft_blocked": False,
        "cc": merged,
        "bcc": bcc,
        "private_list": private,
        "search_list": listed,
    }
