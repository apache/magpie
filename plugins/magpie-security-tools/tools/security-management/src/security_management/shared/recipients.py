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
"""The security CC of every security draft, per `tools/mail-source/contract.md` § *Security draft CC resolution*.

Each key resolves through the layers (project, organization, framework
defaults) to the **first layer that declares it**, even as null or blank;
a lower layer is consulted only when the key is absent. `security_list`,
trimmed, is the CC when configured (and clears a previous run's
fallback); missing, blank, `TODO…` or a `<placeholder>` is unconfigured.
Otherwise `security_inbox.foundation_security_address` is the fallback,
with a warning; when the project declares that key null or blank, the
fallback is disabled. With neither, the draft is blocked. The CC array
keeps the other recipients and drops duplicates.

A flat input (keys already resolved, dotted) is read as one layer.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

FALLBACK_KEY = ("security_inbox", "foundation_security_address")
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


def security_cc(data: Mapping[str, Any]) -> dict[str, Any]:
    if any(k in data for k in ("project", "organization", "framework_defaults")):
        layers = [data.get(k) or {} for k in ("project", "organization", "framework_defaults")]
    else:
        layers = [data]
    listed = configured(_resolve(layers, ("security_list",)))
    existing = [str(c).strip() for c in data.get("existing_cc") or [] if str(c).strip()]
    cc: str | None
    fallback: str | None
    warning: str | None
    if listed:
        cc, fallback, warning = listed, None, None
    else:
        fallback = configured(_resolve(layers, FALLBACK_KEY))
        cc = fallback
        warning = (
            f"security_list is not configured: CC falls back to {fallback}"
            if fallback
            else "no security CC can be resolved: set security_list (or the organization fallback) before drafting"
        )
    if cc is None:
        return {
            "security_cc": None,
            "cc_fallback": None,
            "warning": True,
            "warning_text": warning,
            "draft_blocked": True,
            "cc": [],
            "search_list": None,
        }
    merged: list[str] = []
    for address in [*existing, cc]:
        if address.lower() not in (m.lower() for m in merged):
            merged.append(address)
    return {
        "security_cc": cc,
        "cc_fallback": fallback,
        "warning": warning is not None,
        "warning_text": warning,
        "draft_blocked": False,
        "cc": merged,
        "search_list": listed,
    }
