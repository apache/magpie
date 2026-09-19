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
"""Project identity for the gateway: one label, one slug, one filter."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

LABEL_KEY = "org.apache.magpie.project"


def project_slug(root: Path) -> str:
    """The project root as Claude Code's scratch-tree slug: resolved path, ``/`` -> ``-``."""
    return str(Path(root).resolve()).replace("/", "-")


def label_filter_value(slug: str) -> str:
    return f"{LABEL_KEY}={slug}"


def has_label(labels: Mapping[str, str] | None, slug: str) -> bool:
    if not labels:
        return False
    return labels.get(LABEL_KEY) == slug


def with_label(labels: Mapping[str, str] | None, slug: str) -> dict[str, str]:
    out = dict(labels or {})
    out[LABEL_KEY] = slug
    return out


def merge_filters(raw: str | None, slug: str) -> str:
    """Add the project label to a Docker ``filters`` query value.

    Accepts the list form ``{"label": ["k=v"]}`` and the legacy map form
    ``{"label": {"k=v": true}}``; always emits the list form. Filters use
    AND logic by the daemon, so a client-supplied label for another project
    simply matches nothing.
    """
    filters: dict[str, object] = {}
    if raw:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"filters is not valid JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise ValueError("filters must be a JSON object")
        filters = parsed
    existing = filters.get("label", [])
    if isinstance(existing, dict):
        labels = [k for k, v in existing.items() if v]
    elif isinstance(existing, list):
        labels = [str(x) for x in existing]
    else:
        raise ValueError("filters.label must be a list or an object")
    wanted = label_filter_value(slug)
    if wanted not in labels:
        labels.append(wanted)
    filters["label"] = labels
    return json.dumps(filters, separators=(",", ":"))
