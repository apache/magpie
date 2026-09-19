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
"""``decide()``: the single entry point the relay calls for every request.

Split out of ``policy.py`` to keep that module below its target size (Task
5 already left it at 645 lines before this module's ~90-line addition).
``decide()`` is the request-level counterpart to ``check_create`` /
``apply_create_rewrites``: it classifies a parsed request via
``routes.route``, applies the deny lists, injects the project label into
create bodies / list filters / build labels, and marks which act-by-name
requests still need the relay's backend label check.

Imports from ``policy.py`` at module load time, and is in turn imported
*from* ``policy.py`` (at the very bottom of that module, after every name
this module needs is already defined) so ``Allow``, ``Request`` and
``decide`` are re-exported as ``container_gateway.policy`` attributes.
That makes ``policy.py`` the load-bearing entry point for this module:
importing ``container_gateway.decisions`` directly, before anything has
imported ``container_gateway.policy``, would hit the same names mid
circular-import and fail. Always reach these three names through
``container_gateway.policy``.
"""

from __future__ import annotations

import json as _json
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from .labels import merge_filters, with_label
from .policy import Deny, PolicyContext, apply_create_rewrites, check_create
from .routes import ACT_BY_NAME, LIST_LIKE, Family, Route
from .routes import route as _route

__all__ = ["Allow", "Request", "decide"]


@dataclass
class Request:
    method: str
    path: str
    query: dict[str, list[str]]
    headers: dict[str, str]
    body: Any | None

    def raw_target(self) -> str:
        if not self.query:
            return self.path
        pairs = [f"{quote(k, safe='')}={quote(v, safe='')}" for k, vs in self.query.items() for v in vs]
        return f"{self.path}?{'&'.join(pairs)}"


@dataclass(frozen=True)
class Allow:
    request: Request
    route: Route
    label_check: str | None = None


# Images are shared across every project on the host: reading one, pulling
# one, or tagging *from* one needs no label check. Only removing an image or
# retagging it (the ``tag`` verb's target, handled via ACT_BY_NAME below)
# touches what another project might still be using.
_IMAGE_READS = frozenset({"list", "pull", "inspect", "history", "save", "search", "load"})


def decide(req: Request, ctx: PolicyContext) -> Allow | Deny:
    r = _route(req.method, req.path)
    if r.family is Family.DENIED:
        return Deny(f"denied-endpoint: {r.action} is not available through the gateway")
    if r.family is Family.UNKNOWN or r.action == "unknown":
        return Deny(f"unknown-endpoint: {req.method} {req.path} is not available through the gateway")

    key = (r.family, r.action)
    if key in ((Family.CONTAINERS, "create"), (Family.PODS, "create")):
        body = req.body if isinstance(req.body, dict) else {}
        denied = check_create(body, ctx, libpod=r.libpod)
        if denied:
            return denied
        req.body = apply_create_rewrites(body, ctx, libpod=r.libpod)
        return Allow(req, r)
    if key in ((Family.VOLUMES, "create"), (Family.NETWORKS, "create")):
        body = dict(req.body) if isinstance(req.body, dict) else {}
        k = "labels" if r.libpod or "labels" in body else "Labels"
        body[k] = with_label(body.get(k), ctx.slug)
        req.body = body
        return Allow(req, r)
    if r.family is Family.BUILD:
        query_labels = req.query.get("labels")
        raw: str | None = query_labels[0] if query_labels else None
        labels = _json.loads(raw) if raw else {}
        req.query["labels"] = [_json.dumps(with_label(labels, ctx.slug), separators=(",", ":"))]
        return Allow(req, r)

    if key in LIST_LIKE:
        query_filters = req.query.get("filters")
        raw = query_filters[0] if query_filters else None
        merged = merge_filters(raw, ctx.slug)
        if key == (Family.IMAGES, "prune"):
            f = _json.loads(merged)
            f["dangling"] = ["true"]
            merged = _json.dumps(f, separators=(",", ":"))
        req.query["filters"] = [merged]
        return Allow(req, r)

    if r.family is Family.IMAGES and r.action in _IMAGE_READS:
        return Allow(req, r)
    if key in ACT_BY_NAME:
        return Allow(req, r, label_check=r.name)
    return Allow(req, r)
