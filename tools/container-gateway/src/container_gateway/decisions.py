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

from .labels import LABEL_KEY, merge_filters, with_label
from .policy import (
    NETWORK_MODE_KEYWORDS,
    PROXY_VARS,
    Deny,
    PolicyContext,
    apply_create_rewrites,
    check_create,
    check_exec_create,
    check_update,
    resource_create_spelling_violation,
)
from .routes import ACT_BY_NAME, LIST_LIKE, Family, Route
from .routes import route as _route

__all__ = ["Allow", "Request", "decide"]

_PROXY_VARS_CASEFOLD = frozenset(v.casefold() for v in PROXY_VARS)

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
    # When the resource the relay must label-check is named by a query
    # parameter rather than by a path segment (compat
    # ``POST /commit?container=<id>``), this is that parameter's name: the
    # relay splices the resolved id back into it instead of into the path.
    name_in_query: str | None = None


# Images are shared across every project on the host: reading one, pulling
# one, or tagging *from* one needs no label check. Only removing an image or
# retagging it (the ``tag`` verb's target, handled via ACT_BY_NAME below)
# touches what another project might still be using.
_IMAGE_READS = frozenset({"list", "pull", "inspect", "history", "save", "search", "load"})

# Endpoints that are reachable by name but do something the gateway cannot
# bound: checkpoint / restore name a host path to write the archive to
# (``?export=/Users/me/x.tar``, acted on by the daemon), and generate /
# play take a Kubernetes YAML the daemon reads and acts on wholesale. They
# stay in ``routes._VERBS`` so name parsing is unchanged, and are refused
# here before anything else looks at them.
_DENIED_ACTIONS: frozenset[tuple[Family, str]] = frozenset(
    {(f, a) for f in (Family.CONTAINERS, Family.PODS) for a in ("checkpoint", "restore", "generate", "play")}
)

# Query parameters that name a host path for the daemon to read or write,
# refused on every route as a backstop for a verb this module has not
# enumerated.
_DENIED_QUERY_PARAMS = frozenset({"export", "import"})

# --- Build-query policy (C2) -------------------------------------------
#
# `POST /build` is a create in disguise: its `RUN` steps execute with
# whatever the query asks for. The query is therefore an allow-list, like
# the create body: these parameters are forwarded, the table below is
# refused by name, and anything else is refused as unknown. The list
# covers what the docker CLI's classic builder and podman 6.x's remote
# client actually send, plus the flags that are bounded by construction.
_BUILD_ALLOWED_PARAMS = frozenset(
    name.casefold()
    for name in (
        "additionalbuildcontexts",
        "allplatforms",
        "annotations",
        "buildargs",
        "buildkit",
        "cachefrom",
        "cacheto",
        "cachettl",
        "compressionFormat",
        "createdannotation",
        "cpuperiod",
        "cpuquota",
        "cpusetcpus",
        "cpusetmems",
        "cpushares",
        "dnsoptions",
        "dnssearch",
        "dnsservers",
        "dockerfile",
        "dropcaps",
        "excludes",
        "forceCompressionFormat",
        "forcerm",
        "from",
        "httpproxy",
        "identitylabel",
        "idmappingoptions",
        "ignorefile",
        "inheritannotations",
        "isolation",
        "jobs",
        "labelannotations",
        "labels",
        "layerlabels",
        "layers",
        "manifest",
        "memory",
        "memswap",
        "nocache",
        "nohosts",
        "omithistory",
        "outputformat",
        "platform",
        "pull",
        "pullpolicy",
        "q",
        "quiet",
        "retry",
        "retry-delay",
        "rewritetimestamp",
        "rm",
        "shmsize",
        "skipunusedstages",
        "squash",
        "squashlayers",
        "t",
        "tag",
        "target",
        "timestamp",
        "unsetlabel",
        "version",
    )
)

# Refused by name, with the reason the client sees. Each is refused only
# when it carries a value: both CLIs send some of these empty on every
# build (`cgroupparent=`), and an empty one asks for nothing.
_BUILD_DENIED_PARAMS: dict[str, str] = {
    "addcaps": "added capabilities",
    "addhost": "extra hosts",
    "apparmor": "an apparmor profile",
    "cgroupparent": "a custom cgroup parent",
    "device": "host devices",
    "devices": "host devices",
    "extrahosts": "extra hosts",
    "labelopts": "selinux label options",
    "remote": "a remote build context",
    "runtime": "an alternative OCI runtime",
    "runtimeflags": "OCI runtime flags",
    "seccomp": "a seccomp profile",
    "secrets": "build secrets",
    "securityopt": "security options",
    "session": "a buildkit session",
    "sessionid": "a buildkit session",
    "ssh": "an ssh agent forward",
    "ulimits": "ulimits",
    "unmask": "unmasked kernel paths",
    "unsetenv": "unset environment variables",
    "volume": "a host bind mount",
    "volumes": "a host bind mount",
}

# Values that mean "this parameter asks for nothing", so a denied
# parameter carrying one is left alone rather than refused.
_EMPTY_QUERY_VALUES = frozenset({"", "0", "false", "null", "[]", "{}"})

# libpod's build `networkmode` is buildah's integer policy (0 default,
# 1 disabled, 2 enabled); compat's is the string NetworkMode. Host
# networking for a libpod build rides in `nsoptions`, not here.
_BUILD_NETWORKMODE_INTS = frozenset({"0", "1", "2"})
_BUILD_NETWORKMODE_KEYWORDS = frozenset(k for k in NETWORK_MODE_KEYWORDS if k != "host")

# The one `nsoptions` entry a rootless build legitimately carries: podman
# sends `{"Name": "user", "Host": true}` on every build. Any other
# host-joined namespace, and any namespace joined by path, is refused.
_NSOPTION_HOST_ALLOWED = frozenset({"user"})


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


def _is_empty_value(value: str) -> bool:
    return value.strip().casefold() in _EMPTY_QUERY_VALUES


def _nsoptions_deny(raw: str) -> Deny | None:
    """Refuse a libpod build that joins a host (or path-named) namespace."""
    try:
        parsed = _json.loads(raw)
    except _json.JSONDecodeError as exc:
        return Deny(f"malformed: build nsoptions is not valid JSON: {exc}")
    if not isinstance(parsed, list):
        return Deny("malformed: build nsoptions must be a JSON array")
    for entry in parsed:
        if not isinstance(entry, dict):
            return Deny("malformed: build nsoptions entries must be objects")
        name = str(entry.get("Name", "")).casefold()
        if entry.get("Host") and name not in _NSOPTION_HOST_ALLOWED:
            return Deny(f"denied-build-parameter: the host {name or 'unnamed'} namespace is refused")
        if entry.get("Path"):
            return Deny(
                f"denied-build-parameter: joining the {name or 'unnamed'} namespace by path is refused"
            )
    return None


def _build_query_deny(query: dict[str, list[str]]) -> Deny | None:
    """Allow-list the build query: anything not enumerated is refused."""
    for key, values in query.items():
        casefolded = key.casefold()
        what = _BUILD_DENIED_PARAMS.get(casefolded)
        if what is not None:
            if any(not _is_empty_value(v) for v in values):
                return Deny(f"denied-build-parameter: {what} ({key}) is refused")
            continue
        if casefolded == "networkmode":
            for value in values:
                if value.strip() in _BUILD_NETWORKMODE_INTS:
                    continue
                if value.strip().casefold() in _BUILD_NETWORKMODE_KEYWORDS:
                    continue
                return Deny(f"network: build networkmode={value} is refused")
            continue
        if casefolded == "nsoptions":
            for value in values:
                denial = _nsoptions_deny(value)
                if denial is not None:
                    return denial
            continue
        if casefolded in ("output", "outputs"):
            # buildah's `--output` and buildkit's `--output` both write to
            # a filesystem path when the value names a destination.
            for value in values:
                if "dest=" in value.casefold():
                    return Deny(f"denied-build-parameter: writing build output to {value} is refused")
            continue
        if casefolded not in _BUILD_ALLOWED_PARAMS:
            return Deny(f"denied-build-parameter: {key} is not accepted by the gateway")
    return None


def _label_build(req: Request, ctx: PolicyContext, *, libpod: bool) -> Deny | None:
    """Inject the project label into the build query, in the shape that API takes.

    The compat build takes ``labels`` as a JSON object; libpod's takes a
    JSON array of ``k=v`` strings. The shape the client sent wins when it
    sent one, so a client using the other spelling than its URL suggests
    still gets a body its daemon can parse.
    """
    raw_labels = _first(req.query, "labels")
    try:
        labels = _json.loads(raw_labels) if raw_labels else ([] if libpod else {})
    except _json.JSONDecodeError as exc:
        return Deny(f"malformed: build labels is not valid JSON: {exc}")
    if isinstance(labels, list):
        as_list = [str(item) for item in labels]
        as_list.append(f"{LABEL_KEY}={ctx.slug}")
        req.query["labels"] = [_json.dumps(as_list, separators=(",", ":"))]
        return None
    if not isinstance(labels, dict):
        return Deny("malformed: build labels must be a JSON object")
    req.query["labels"] = [_json.dumps(with_label(labels, ctx.slug), separators=(",", ":"))]
    return None


def _inject_build_proxy(query: dict[str, list[str]], ctx: PolicyContext) -> Deny | None:
    """Put the egress proxy into ``buildargs`` so ``RUN`` obeys it too.

    Client-supplied values for the same names are dropped first, exactly
    as the create rewrite does for ``Env``. podman's own ``httpproxy=1``
    (the daemon adding *its* proxy variables) is turned off for the same
    reason: the gateway decides the container's egress.
    """
    if not ctx.proxy_env or ctx.egress_mode == "off":
        return None
    raw = _first(query, "buildargs")
    try:
        args = _json.loads(raw) if raw else {}
    except _json.JSONDecodeError as exc:
        return Deny(f"malformed: build buildargs is not valid JSON: {exc}")
    if not isinstance(args, dict):
        return Deny("malformed: build buildargs must be a JSON object")
    merged = {k: v for k, v in args.items() if str(k).casefold() not in _PROXY_VARS_CASEFOLD}
    merged.update(ctx.proxy_env)
    query["buildargs"] = [_json.dumps(merged, separators=(",", ":"))]
    if "httpproxy" in query:
        query["httpproxy"] = ["0"]
    return None


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
    if key in _DENIED_ACTIONS:
        return Deny(f"denied-endpoint: {r.action} is not available through the gateway")
    for name in req.query:
        if name.casefold() in _DENIED_QUERY_PARAMS:
            return Deny(f"denied-query: {name} is not available through the gateway")
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
    if key in ((Family.CONTAINERS, "exec"), (Family.PODS, "exec")):
        exec_denied = check_exec_create(req.body)
        if exec_denied is not None:
            return exec_denied
    if key in ((Family.CONTAINERS, "update"), (Family.PODS, "update")):
        update_denied = check_update(req.body)
        if update_denied is not None:
            return update_denied
    if r.family is Family.BUILD:
        build_denied = _build_query_deny(req.query)
        if build_denied is not None:
            return build_denied
        label_denied = _label_build(req, ctx, libpod=r.libpod)
        if label_denied is not None:
            return label_denied
        proxy_denied = _inject_build_proxy(req.query, ctx)
        if proxy_denied is not None:
            return proxy_denied
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

    if key == (Family.CONTAINERS, "commit") and r.name is None:
        # The compat spelling: the container is in the query.
        container = _first(req.query, "container")
        if not container:
            return Deny("malformed: commit needs a container")
        return Allow(req, r, label_check=container, name_in_query="container")
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
