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

Split out of ``policy.py`` to keep that module below its target size.
``decide()`` is the request-level counterpart to ``check_create`` /
``apply_create_rewrites``: it classifies a parsed request via
``routes.route``, applies the deny lists, injects the project label into
create bodies / list filters / build labels, and marks which act-by-name
requests still need the relay's backend label check.

Dependencies are strictly one-way: this module imports from ``policy.py``
(which imports from ``policy_shape.py``); neither of those two imports
anything back from here. Callers reach ``Allow``, ``Request`` and
``decide`` through ``container_gateway.decisions`` directly — there is no
re-export via ``container_gateway.policy``.

Like ``check_create``, ``decide`` is defensively layered against
attacker-controlled input it cannot fully type-check statically: every
JSON-parsing branch (``build`` labels, list-filters) denies on invalid JSON
or the wrong top-level type rather than letting the exception propagate,
and a total ``try/except`` backstop around the whole function denies with a
generic ``malformed`` reason rather than ever raising into the relay.
"""

from __future__ import annotations

import json as _json
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from .labels import merge_filters, with_label
from .policy import (
    Deny,
    PolicyContext,
    apply_create_rewrites,
    check_create,
    resource_create_spelling_violation,
)
from .routes import ACT_BY_NAME, LIST_LIKE, Family, Route
from .routes import route as _route

__all__ = ["Allow", "Request", "decide"]

# Control characters (C0 plus DEL) that make a path suspect regardless of
# where they appear.
_CONTROL_CHARS = frozenset(chr(c) for c in range(0x20)) | {"\x7f"}


@dataclass
class Request:
    """One parsed request, as the relay hands it to ``decide()``.

    ``path`` is the raw request-target path exactly as received on the
    wire — not percent-decoded, not otherwise normalised. ``decide()``
    refuses (rather than routes) anything that is not already normalised
    (see ``_path_is_malformed``); the relay must not percent-decode ``path``
    before calling ``decide()``, or a malicious `%2e%2e` segment would
    already look safe by the time this module ever sees it.

    ``decide()`` mutates ``query`` and ``body`` on this object in place (to
    inject the project label / proxy env / loopback host, or to merge a
    filter) rather than returning a copy; the ``request`` carried on the
    returned ``Allow`` is this same object, already rewritten.
    """

    method: str
    path: str
    query: dict[str, list[str]]
    headers: dict[str, str]
    body: Any | None

    def raw_target(self) -> str:
        # Guard on the built `pairs`, not on `self.query` being non-empty: a
        # query dict like {"a": []} is a non-empty dict with nothing to
        # render, and must still produce the bare path, not "path?".
        pairs = [f"{quote(k, safe='')}={quote(v, safe='')}" for k, vs in self.query.items() for v in vs]
        if not pairs:
            return self.path
        return f"{self.path}?{'&'.join(pairs)}"


@dataclass(frozen=True)
class Allow:
    """A request the policy admits, and what (if anything) the relay must still label-check.

    ``request`` is the same ``Request`` object passed to ``decide()`` — see
    ``Request``'s docstring on in-place mutation.
    """

    request: Request
    route: Route
    label_check: str | None = None


# Images are shared across every project on the host: reading one, pulling
# one, or tagging *from* one needs no label check. Only removing an image or
# retagging it (the ``tag`` verb's target, handled via ACT_BY_NAME below)
# touches what another project might still be using.
_IMAGE_READS = frozenset({"list", "pull", "inspect", "history", "save", "search", "load"})


def _first(query: dict[str, list[str]], key: str) -> str | None:
    """The first value of a (possibly absent, possibly empty) query parameter."""
    values = query.get(key)
    return values[0] if values else None


def _path_is_malformed(path: str) -> bool:
    """A path this module refuses to route rather than classify.

    Percent-encoding, backslashes, control characters, and doubled slashes
    are all ways a client (or a proxy ahead of this one) could smuggle a
    segment past the plain ``/``-split classifier in ``routes.route`` — a
    ``%2e%2e`` or a doubled slash can decode differently downstream than it
    parses here. A ``.``/``..`` path segment is refused outright rather than
    resolved, since resolving it would mean this module's classification and
    the backend's own path handling could disagree about what request is
    actually being made.
    """
    if "%" in path or "\\" in path or "//" in path:
        return True
    if any(c in _CONTROL_CHARS for c in path):
        return True
    return any(segment in (".", "..") for segment in path.split("/"))


def decide(req: Request, ctx: PolicyContext) -> Allow | Deny:
    try:
        return _decide(req, ctx)
    except (TypeError, AttributeError, ValueError, KeyError):
        return Deny("malformed: unexpected request shape")


def _decide(req: Request, ctx: PolicyContext) -> Allow | Deny:
    if _path_is_malformed(req.path):
        return Deny("malformed: path is not normalised")

    r = _route(req.method, req.path)
    if r.family is Family.DENIED:
        return Deny(f"denied-endpoint: {r.action} is not available through the gateway")
    if r.family is Family.UNKNOWN or r.action == "unknown":
        return Deny(f"unknown-endpoint: {req.method} {req.path} is not available through the gateway")

    key = (r.family, r.action)
    if key in ((Family.CONTAINERS, "create"), (Family.PODS, "create")):
        denied = check_create(req.body, ctx, libpod=r.libpod)
        if denied:
            return denied
        # check_create only returns None for a body that is already a dict
        # (see its docstring); this narrows the type for apply_create_rewrites
        # without pre-filtering req.body before check_create sees it (I4).
        assert isinstance(req.body, dict)
        req.body = apply_create_rewrites(req.body, ctx, libpod=r.libpod)
        return Allow(req, r)
    if key in ((Family.VOLUMES, "create"), (Family.NETWORKS, "create")):
        if not isinstance(req.body, dict):
            return Deny("malformed: request body must be a JSON object")
        spelling_violation = resource_create_spelling_violation(req.body, r.libpod)
        if spelling_violation is not None:
            return spelling_violation
        body = dict(req.body)
        k = "labels" if r.libpod else "Labels"
        body[k] = with_label(body.get(k), ctx.slug)
        req.body = body
        return Allow(req, r)
    if r.family is Family.BUILD:
        raw_labels = _first(req.query, "labels")
        try:
            labels = _json.loads(raw_labels) if raw_labels else {}
        except _json.JSONDecodeError as exc:
            return Deny(f"malformed: build labels is not valid JSON: {exc}")
        if not isinstance(labels, dict):
            return Deny("malformed: build labels must be a JSON object")
        req.query["labels"] = [_json.dumps(with_label(labels, ctx.slug), separators=(",", ":"))]
        return Allow(req, r)

    if key in LIST_LIKE:
        raw_filters = _first(req.query, "filters")
        try:
            merged = merge_filters(raw_filters, ctx.slug)
            if key == (Family.IMAGES, "prune"):
                f = _json.loads(merged)
                f["dangling"] = ["true"]
                merged = _json.dumps(f, separators=(",", ":"))
        except (ValueError, TypeError) as exc:
            return Deny(f"malformed: {exc}")
        req.query["filters"] = [merged]
        return Allow(req, r)

    if r.family is Family.IMAGES and r.action in _IMAGE_READS:
        return Allow(req, r)
    if key in ACT_BY_NAME:
        return Allow(req, r, label_check=r.name)
    if r.name is not None:
        # Fail closed: any other named route (a verb ``routes._VERBS`` knows
        # about but this module's tables do not yet enumerate) still gets
        # label-checked by name. The bare ``Allow`` below is reached only by
        # unnamed routes (system endpoints, bare-family list calls already
        # handled above).
        return Allow(req, r, label_check=r.name)
    return Allow(req, r)
