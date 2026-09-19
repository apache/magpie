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
"""The gateway's policy: what a request may ask for, and what it gets rewritten to.

Everything here is a pure function over parsed requests, with one
exception: ``resolve_bind_source`` stats the host filesystem (it follows
symlinks to decide whether a bind source resolves under a bind root).
Nothing here talks to the backend; the label pre-check that needs
backend I/O lives in relay.py. Canonical-spelling enforcement (case and
duplicate-key ambiguity) lives in ``policy_shape.py``, imported below.

``check_create`` is defensively layered: a total shape guard denies a
non-dict body outright, ``_malformed_shape`` type-guards every field the
rest of the checks read (in both shapes, regardless of which one the URL
says — several checks below read both spellings unconditionally, so the
guard must too), the spelling check then runs, and a final
``try/except`` backstop denies with a generic reason rather than letting
any residual exception cross this function. ``apply_create_rewrites`` is
not similarly hardened: its contract is that the relay calls it only
after ``check_create`` returned ``None`` for the same body and ``libpod``
flag, and it does not re-validate what ``check_create`` already accepted.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .labels import with_label
from .policy_shape import (
    CATALOG_ANCHOR,
    Deny,
    canonical_spelling_violation,
    resource_create_spelling_violation,
)

__all__ = [
    "CATALOG_ANCHOR",
    "PROXY_VARS",
    "Deny",
    "PolicyContext",
    "apply_create_rewrites",
    "check_create",
    "named_networks",
    "named_volumes",
    "resolve_bind_source",
    "resource_create_spelling_violation",
]

PROXY_VARS = ("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "no_proxy")
_PROXY_VARS_CASEFOLD = frozenset(v.casefold() for v in PROXY_VARS)

# PidMode / IpcMode / UTSMode / UsernsMode / CgroupnsMode and their libpod
# equivalents (pidns / ipcns / utsns / userns / cgroupns): an allow-list, not
# a deny-list, so an unrecognised mode (a new backend feature, a typo, an
# attempt at obfuscation) is refused rather than silently passed through.
_NAMESPACE_ALLOWED_MODES = frozenset({"", "private", "pod", "auto", "keep-id", "nomap", "shareable"})

# A dict-shaped namespace mode (``{"nsmode": ..., "value": ...}``) whose keys
# are not a subset of this set is not a namespace object the policy
# recognises; `_nsmode()` maps it to a sentinel that is in no allow-list, so
# the namespace/network rule denies it even if the spelling check (which
# would normally catch a case-variant or extra key first) were skipped.
_NSMODE_OBJECT_KEYS = frozenset({"nsmode", "value"})
_NSMODE_MALFORMED_SENTINEL = "<malformed>"

# NetworkMode / netns: a fixed set of safe keywords is allowed outright
# (exact match, casefolded); anything that casefold-starts with one of these
# prefixes targets a host, foreign, or otherwise unsafe namespace and is
# refused regardless of spelling case; everything else must look like a
# real network name (see ``_NETWORK_NAME_RE``) to be treated as a named
# network, allowed here and left to the relay's label check (Task 9).
_NETWORK_MODE_KEYWORDS = frozenset(
    {"", "default", "bridge", "none", "private", "slirp4netns", "pasta", "pod"}
)
_NETWORK_DENIED_PREFIXES = ("host", "container", "ns", "path", "from-")

# The docker/podman network-name grammar: an unrecognised value that does not
# even look like a network name is refused rather than treated as one. Always
# matched with `.fullmatch()` (never `.match()`): in a non-MULTILINE regex `$`
# matches just before a trailing newline, so `.match()` would let a value like
# "mynet\n" through.
_NETWORK_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")

# NetworkingConfig.EndpointsConfig / libpod networks keys: `host`/`none` (any
# case) are not real networks a project could create — moby promotes a lone
# EndpointsConfig entry to the effective network mode, so attaching to a
# network literally named `host`/`none` is the same host/no-network escape
# NetworkMode itself refuses. `bridge`/`podman` are real built-in networks
# every project can already reach without a label check; a project-created
# network literally named `default` is not the built-in default network and
# must reach the relay's label check like any other named network, so it is
# deliberately absent from this allow-list (unlike `_NETWORK_MODE_KEYWORDS`,
# where a bare `NetworkMode: "default"` genuinely means the built-in one).
_NETWORK_HOST_LIKE_KEY_NAMES = frozenset({"host", "none"})
_ENDPOINT_KEY_ALLOWED_KEYWORDS = frozenset({"bridge", "podman"})

# Built-in network names every project can already reach; never treated as a
# *named* (foreign) network the relay needs to label-check. `default` is
# deliberately absent — see `_ENDPOINT_KEY_ALLOWED_KEYWORDS` above.
_BUILTIN_NETWORK_NAMES = frozenset({"bridge", "podman", "host", "none"})

# SecurityOpt keys the policy recognises at all; every other key (including
# unmask, proc-opts) is refused outright.
_SECCOMP_ALLOWED_VALUES = frozenset({"", "default"})

_MOUNT_PASSTHROUGH_TYPES = frozenset({"tmpfs"})
_MOUNT_REFUSED_TYPES = frozenset({"image", "devpts", "npipe"})

# --- _malformed_shape's field tables -----------------------------------
# Checked via `host.get(name)`: for compat this is HostConfig, for libpod
# this is the body itself, so a single unconditional check per name covers
# both shapes' real location for that field (and harmlessly looks in the
# "wrong" object for the other shape's spelling, which is never read from
# there anyway).
_LIST_OR_NONE_HOST_FIELDS = (
    "Binds",
    "CapAdd",
    "cap_add",
    "CapDrop",
    "cap_drop",
    "SecurityOpt",
    "selinux_opts",
    "Devices",
    "DeviceRequests",
    "DeviceCgroupRules",
    "device_cgroup_rule",
    "MaskedPaths",
    "ReadonlyPaths",
    "mask",
    "unmask",
    "VolumesFrom",
    "volumes_from",
)
_MOUNT_LIST_HOST_FIELDS = ("Mounts", "mounts", "portmappings", "volumes")
_DICT_OR_NONE_HOST_FIELDS = ("Sysctls", "sysctl")
_NAMESPACE_HOST_FIELDS = (
    "PidMode",
    "IpcMode",
    "UTSMode",
    "UsernsMode",
    "CgroupnsMode",
    "pidns",
    "ipcns",
    "utsns",
    "userns",
    "cgroupns",
    "NetworkMode",
    "netns",
)
# Checked via `body.get(name)`: these are always at the top of the body
# (Env/Labels/NetworkingConfig for compat, env/labels/networks for libpod —
# and for libpod the body *is* `host`, so this is equivalent to host.get()
# there too).
_DICT_OR_NONE_BODY_FIELDS = ("NetworkingConfig", "networks")
_STR_LIST_BODY_FIELDS = ("Env",)
_STR_DICT_BODY_FIELDS = ("env", "Labels", "labels")


@dataclass(frozen=True)
class PolicyContext:
    slug: str
    project_root: Path
    bind_roots: tuple[Path, ...]
    proxy_env: dict[str, str] | None
    egress_mode: str = "inject-if-available"


def _host(body: dict[str, Any], libpod: bool) -> dict[str, Any]:
    if libpod:
        return body
    host_config = body.get("HostConfig")
    return host_config if isinstance(host_config, dict) else {}


def _nsmode(value: Any) -> str:
    """Namespace mode as a string for both shapes: ``"host"`` or ``{"nsmode": "host"}``.

    A dict whose keys are not a subset of ``{"nsmode", "value"}`` is not a
    namespace object the policy recognises and fails closed to a sentinel
    (see ``_NSMODE_MALFORMED_SENTINEL``) rather than reading ``nsmode`` out
    of it anyway.
    """
    if isinstance(value, dict):
        if not set(value).issubset(_NSMODE_OBJECT_KEYS):
            return _NSMODE_MALFORMED_SENTINEL
        return str(value.get("nsmode", ""))
    return str(value or "")


def _is_path_like(spec: str) -> bool:
    """A ``Binds`` source containing a path separator is a path; otherwise a named volume."""
    return "/" in spec or "\\" in spec


def resolve_bind_source(src: str, ctx: PolicyContext) -> bool:
    try:
        real = Path(src).resolve(strict=False)
    except (OSError, RuntimeError):
        return False
    return any(real == root.resolve() or root.resolve() in real.parents for root in ctx.bind_roots)


def _list_of_dicts_deny(name: str, value: Any) -> Deny | None:
    if value is None:
        return None
    if not isinstance(value, list):
        return Deny(f"malformed: {name} has the wrong type")
    for entry in value:
        if not isinstance(entry, dict):
            return Deny(f"malformed: {name} entries must be objects")
    return None


def _malformed_shape(body: dict[str, Any], libpod: bool) -> Deny | None:
    """Type-guard every field the rest of ``check_create`` reads, in both shapes.

    Never lets a wrongly-typed field reach an iteration, ``.items()``, or
    ``.get()`` call that would raise; every such shape is refused as
    ``malformed`` instead. Runs before the spelling check, which itself
    assumes these types are already sound.
    """
    host_config = body.get("HostConfig")
    if host_config is not None and not isinstance(host_config, dict):
        return Deny("malformed: HostConfig has the wrong type")

    host = _host(body, libpod)

    for name in _LIST_OR_NONE_HOST_FIELDS:
        value = host.get(name)
        if value is not None and not isinstance(value, list):
            return Deny(f"malformed: {name} has the wrong type")

    for name in _NAMESPACE_HOST_FIELDS:
        value = host.get(name)
        if value is not None and not isinstance(value, dict | str):
            return Deny(f"malformed: {name} has the wrong type")

    for name in _DICT_OR_NONE_HOST_FIELDS:
        value = host.get(name)
        if value is not None and not isinstance(value, dict):
            return Deny(f"malformed: {name} has the wrong type")

    for name in _DICT_OR_NONE_BODY_FIELDS:
        value = body.get(name)
        if value is not None and not isinstance(value, dict):
            return Deny(f"malformed: {name} has the wrong type")

    for name in _MOUNT_LIST_HOST_FIELDS:
        denial = _list_of_dicts_deny(name, host.get(name))
        if denial is not None:
            return denial

    port_bindings = host.get("PortBindings")
    if port_bindings is not None:
        if not isinstance(port_bindings, dict):
            return Deny("malformed: PortBindings has the wrong type")
        for bindings in port_bindings.values():
            denial = _list_of_dicts_deny("PortBindings", bindings)
            if denial is not None:
                return denial

    for name in _STR_LIST_BODY_FIELDS:
        value = body.get(name)
        if value is not None and (
            not isinstance(value, list) or not all(isinstance(item, str) for item in value)
        ):
            return Deny(f"malformed: {name} has the wrong type")

    for name in _STR_DICT_BODY_FIELDS:
        value = body.get(name)
        if value is not None and (
            not isinstance(value, dict)
            or not all(isinstance(k, str) and isinstance(v, str) for k, v in value.items())
        ):
            return Deny(f"malformed: {name} has the wrong type")

    return None


def _split_security_opt(opt: str) -> tuple[str, str]:
    """Split on the first ``=`` or ``:``, whichever comes first (both separators are legal)."""
    indices = [i for i in (opt.find("="), opt.find(":")) if i != -1]
    if not indices:
        return opt, ""
    idx = min(indices)
    return opt[:idx], opt[idx + 1 :]


def _security_opt_denied(opt: str) -> bool:
    raw_key, raw_value = _split_security_opt(opt)
    key = raw_key.casefold().strip()
    value = raw_value.casefold().strip()
    if key == "seccomp":
        return value not in _SECCOMP_ALLOWED_VALUES
    if key == "apparmor":
        return value == "unconfined"
    if key == "label":
        return value == "disable"
    if key == "no-new-privileges":
        return value not in ("", "true")
    if key == "systempaths":
        return value != ""
    # unmask, proc-opts, and any key the policy does not explicitly allow.
    return True


def _security_opt_deny(host: dict[str, Any]) -> Deny | None:
    for opt in host.get("SecurityOpt") or []:
        opt_str = str(opt)
        if _security_opt_denied(opt_str):
            return Deny(f"security-opt: {opt_str} is refused")

    for opt in host.get("selinux_opts") or []:
        if str(opt).casefold().strip() == "disable":
            return Deny(f"security-opt: selinux_opts={opt} is refused")
    apparmor_profile = host.get("apparmor_profile")
    if apparmor_profile is not None and str(apparmor_profile).casefold() == "unconfined":
        return Deny(f"security-opt: apparmor_profile={apparmor_profile} is refused")
    seccomp_policy = host.get("seccomp_policy")
    if seccomp_policy is not None and str(seccomp_policy).casefold() not in _SECCOMP_ALLOWED_VALUES:
        return Deny(f"security-opt: seccomp_policy={seccomp_policy} is refused")
    if host.get("seccomp_profile_path"):
        return Deny(f"security-opt: seccomp_profile_path={host['seccomp_profile_path']} is refused")
    return None


def _mount_type_deny(
    entry: dict[str, Any], type_key: str, source_key: str, ctx: PolicyContext
) -> Deny | None:
    raw_type = entry.get(type_key)
    mtype = str(raw_type).casefold() if raw_type else ""
    if mtype == "bind":
        source = str(entry.get(source_key, ""))
        if not resolve_bind_source(source, ctx):
            roots = ", ".join(str(r) for r in ctx.bind_roots)
            return Deny(f"bind-mount: {source} is outside the allowed roots ({roots})")
        return None
    if mtype == "volume":
        return None  # a named volume; the relay label-checks it (Task 9)
    if mtype in _MOUNT_PASSTHROUGH_TYPES:
        return None
    if mtype in _MOUNT_REFUSED_TYPES:
        return Deny(f"mount-type: {raw_type} is refused")
    return Deny("mount-type: every mount needs an explicit type of bind, volume or tmpfs")


def _mounts_deny(
    body: dict[str, Any], host: dict[str, Any], ctx: PolicyContext, *, libpod: bool
) -> Deny | None:
    if not libpod:
        for spec in host.get("Binds") or []:
            src = str(spec).split(":", 1)[0]
            if src and _is_path_like(src) and not resolve_bind_source(src, ctx):
                roots = ", ".join(str(r) for r in ctx.bind_roots)
                return Deny(f"bind-mount: {src} is outside the allowed roots ({roots})")

    type_key, source_key = ("type", "source") if libpod else ("Type", "Source")
    mounts = body.get("mounts") if libpod else host.get("Mounts")
    for entry in mounts or []:
        # _malformed_shape has already rejected non-dict entries by this point.
        denial = _mount_type_deny(entry, type_key, source_key, ctx)
        if denial is not None:
            return denial
    return None


def _network_mode_deny(key: str, net: str) -> Deny | None:
    """Exact classifier for a ``NetworkMode``/``netns`` value.

    keyword -> allow; the ``_nsmode`` malformed sentinel -> deny (the netns
    object itself is malformed, not merely a bad name, so this message names
    the object rather than a value); a host/foreign-namespace prefix -> deny;
    otherwise the value must look like a real network name (see
    ``_NETWORK_NAME_RE``) to be treated as a named network, allowed here and
    left to the relay's label check (Task 9) — anything else is refused
    rather than passed through.
    """
    net_cf = net.casefold()
    if net_cf in _NETWORK_MODE_KEYWORDS:
        return None
    if net == _NSMODE_MALFORMED_SENTINEL:
        return Deny(f"network: {key} netns object has unexpected keys")
    if net_cf.startswith(_NETWORK_DENIED_PREFIXES):
        return Deny(f"network: {key}={net} is refused")
    if not _NETWORK_NAME_RE.fullmatch(net):
        return Deny(f"network: {net} is not a valid network name")
    return None


def _network_key_deny(name: str) -> Deny | None:
    """Exact classifier for one ``NetworkingConfig.EndpointsConfig`` / libpod ``networks`` key.

    Mirrors ``_network_mode_deny`` but with a key-shaped allow-list: real
    built-in networks (``bridge``/``podman``) allow, ``host``/``none`` deny
    (moby promotes a lone ``EndpointsConfig`` entry to the effective network
    mode, so this is the same escape ``NetworkMode`` itself refuses), and the
    same denied-prefix / name-grammar checks apply to everything else. Unlike
    ``_network_mode_deny``, a key is always a plain string (a JSON object
    key), never a netns object, so there is no malformed-sentinel branch here
    — a key that happened to equal the sentinel text would fail the grammar
    check below anyway.
    """
    name_cf = name.casefold()
    if name_cf in _ENDPOINT_KEY_ALLOWED_KEYWORDS:
        return None
    if name_cf in _NETWORK_HOST_LIKE_KEY_NAMES or name_cf.startswith(_NETWORK_DENIED_PREFIXES):
        return Deny(f"network: network name {name} is refused")
    if not _NETWORK_NAME_RE.fullmatch(name):
        return Deny(f"network: {name} is not a valid network name")
    return None


def _named_network_candidate(host: dict[str, Any], libpod: bool) -> str | None:
    """The named-network value of ``NetworkMode``/``netns``, if any.

    Deliberately distinct from ``_network_mode_deny`` returning ``None``: a
    fixed keyword (``""``, ``bridge``, ...) is *allowed* by the policy but is
    not a *named* network to report — only a value that clears every check
    and matches the network-name grammar is a genuine candidate.
    """
    net = _nsmode(host.get("netns") if libpod else host.get("NetworkMode"))
    net_cf = net.casefold()
    if net_cf in _NETWORK_MODE_KEYWORDS or net == _NSMODE_MALFORMED_SENTINEL:
        return None
    if net_cf.startswith(_NETWORK_DENIED_PREFIXES):
        return None
    if not _NETWORK_NAME_RE.fullmatch(net):
        return None
    return net


def named_volumes(body: dict[str, Any], libpod: bool) -> list[str]:
    """Named volumes this create body references: the relay label-checks each one (Task 9)."""
    host = _host(body, libpod)
    names: list[str] = []
    if not libpod:
        for spec in host.get("Binds") or []:
            src = str(spec).split(":", 1)[0]
            if src and not _is_path_like(src):
                names.append(src)
    type_key, source_key = ("type", "source") if libpod else ("Type", "Source")
    mounts = body.get("mounts") if libpod else host.get("Mounts")
    for entry in mounts or []:
        if isinstance(entry, dict) and str(entry.get(type_key, "")).casefold() == "volume":
            names.append(str(entry.get(source_key, "")))
    if libpod:
        for entry in body.get("volumes") or []:
            if isinstance(entry, dict) and entry.get("Name"):
                names.append(str(entry["Name"]))
    return names


def named_networks(body: dict[str, Any], libpod: bool) -> list[str]:
    """Named (foreign) networks this create body attaches to: the relay label-checks each one (Task 9).

    Covers the ``NetworkMode``/``netns`` named-network value, compat
    ``NetworkingConfig.EndpointsConfig`` keys, and libpod top-level
    ``networks`` keys — reading both endpoint-map shapes unconditionally,
    regardless of which URL flavour this request came in on, exactly like
    ``check_create``'s equivalent check. Built-in network names (``bridge``,
    ``podman``, ``host``, ``none``) are excluded — ``check_create`` already
    refuses ``host``/``none`` outright, whether as a ``NetworkMode``/``netns``
    value or as an ``EndpointsConfig``/``networks`` key (moby promotes a lone
    ``EndpointsConfig`` entry to the effective network mode, so a `host`/
    `none` key is the same escape), and ``bridge``/``podman`` are real
    built-in networks every project can already reach without a label check.
    A network literally named ``default`` is a normal named (foreign) network
    like any other — not a built-in — so it is deliberately not excluded here
    and does get a label check; see ``_ENDPOINT_KEY_ALLOWED_KEYWORDS``. This
    helper assumes the same precondition as ``apply_create_rewrites``: it is
    only meaningful on a body ``check_create`` already accepted. Deduplicated,
    first-seen order.
    """
    host = _host(body, libpod)
    candidates: list[str] = []

    network_mode = _named_network_candidate(host, libpod)
    if network_mode is not None:
        candidates.append(network_mode)

    networks = body.get("networks")
    if isinstance(networks, dict):
        candidates.extend(str(k) for k in networks)

    networking_config = body.get("NetworkingConfig")
    if isinstance(networking_config, dict):
        endpoints_config = networking_config.get("EndpointsConfig")
        if isinstance(endpoints_config, dict):
            candidates.extend(str(k) for k in endpoints_config)

    seen: set[str] = set()
    result: list[str] = []
    for name in candidates:
        if name.casefold() in _BUILTIN_NETWORK_NAMES or name in seen:
            continue
        seen.add(name)
        result.append(name)
    return result


def check_create(body: Any, ctx: PolicyContext, *, libpod: bool) -> Deny | None:
    """Entry point: accepts whatever the client sent, unnarrowed.

    ``body`` is typed ``Any`` (not ``dict[str, Any]``) deliberately: callers
    (``decide()`` in ``decisions.py``) pass the request body through exactly
    as received, including a non-dict JSON value, and rely on the
    ``isinstance`` guard below to deny it rather than pre-filtering it
    themselves. ``_check_create`` below is the narrowed, dict-only worker.
    """
    if not isinstance(body, dict):
        return Deny("malformed: request body must be a JSON object")
    try:
        return _check_create(body, ctx, libpod=libpod)
    except (TypeError, AttributeError, ValueError, KeyError):
        return Deny("malformed: unexpected request shape")


def _check_create(body: dict[str, Any], ctx: PolicyContext, *, libpod: bool) -> Deny | None:
    malformed = _malformed_shape(body, libpod)
    if malformed is not None:
        return malformed

    spelling_violation = canonical_spelling_violation(body, libpod)
    if spelling_violation is not None:
        return spelling_violation

    host = _host(body, libpod)

    if host.get("Privileged") or host.get("privileged"):
        return Deny("privileged: drop --privileged; the gateway never grants it")
    if host.get("CapAdd") or host.get("cap_add"):
        return Deny("cap-add: added capabilities are refused; run without --cap-add")
    if any(
        host.get(k)
        for k in ("Devices", "DeviceRequests", "DeviceCgroupRules", "devices", "device_cgroup_rule")
    ):
        return Deny("devices: host devices are refused; run without --device / --gpus")

    for key in (
        "PidMode",
        "IpcMode",
        "UTSMode",
        "UsernsMode",
        "CgroupnsMode",
        "pidns",
        "ipcns",
        "utsns",
        "userns",
        "cgroupns",
    ):
        mode = _nsmode(host.get(key))
        if mode.casefold() not in _NAMESPACE_ALLOWED_MODES:
            return Deny(
                f"namespace: {key}={mode} is refused; "
                "only private, pod, auto, keep-id, nomap and shareable are allowed"
            )

    for key in ("NetworkMode", "netns"):
        net_deny = _network_mode_deny(key, _nsmode(host.get(key)))
        if net_deny is not None:
            return net_deny

    # Read both the libpod and compat endpoint-map shapes unconditionally,
    # regardless of which URL flavour this request came in on — like every
    # other rule in this function (see the module docstring): a client could
    # smuggle the "other" shape's field past a check gated on `libpod`.
    networks = body.get("networks")
    if isinstance(networks, dict):
        for network_key in networks:
            key_deny = _network_key_deny(str(network_key))
            if key_deny is not None:
                return key_deny

    networking_config = body.get("NetworkingConfig")
    if isinstance(networking_config, dict):
        endpoints_config = networking_config.get("EndpointsConfig")
        if isinstance(endpoints_config, dict):
            for network_key in endpoints_config:
                key_deny = _network_key_deny(str(network_key))
                if key_deny is not None:
                    return key_deny

    security_opt_deny = _security_opt_deny(host)
    if security_opt_deny is not None:
        return security_opt_deny

    if host.get("Sysctls") or host.get("sysctl"):
        return Deny("sysctls: kernel parameters are refused")
    if host.get("CgroupParent") or host.get("cgroup_parent"):
        return Deny("cgroup-parent: custom cgroup parents are refused")
    if host.get("Runtime") or host.get("oci_runtime"):
        return Deny("runtime: alternative OCI runtimes are refused")
    if host.get("Isolation"):
        return Deny("isolation: the Isolation field is refused")
    if host.get("MaskedPaths") is not None:
        return Deny("masked-paths: MaskedPaths is refused")
    if host.get("mask") is not None:
        return Deny("masked-paths: mask is refused")
    if host.get("ReadonlyPaths") is not None:
        return Deny("readonly-paths: ReadonlyPaths is refused")
    if host.get("unmask") is not None:
        return Deny("security-opt: unmask is refused")

    if host.get("PublishAllPorts") or host.get("publish_image_ports"):
        return Deny("publish-all: publishing every exposed port binds 0.0.0.0; publish ports explicitly")

    mounts_deny = _mounts_deny(body, host, ctx, libpod=libpod)
    if mounts_deny is not None:
        return mounts_deny

    if host.get("VolumesFrom") or host.get("volumes_from"):
        # The relay would have to label-check every listed container; refuse
        # outright until that is needed — named volumes cover the common case.
        return Deny("volumes-from: --volumes-from is refused; share a named volume instead")

    if ctx.egress_mode == "require" and not ctx.proxy_env:
        return Deny("egress-required: the egress gateway is unreachable and --egress require is set")
    return None


def apply_create_rewrites(body: dict[str, Any], ctx: PolicyContext, *, libpod: bool) -> dict[str, Any]:
    """Apply the label / HostIp / proxy-env rewrites.

    Precondition: ``check_create(body, ctx, libpod=libpod)`` must already
    have returned ``None`` for this exact body — the relay always calls the
    two in that order. This function does not re-validate shapes
    ``check_create`` already rejected (e.g. a non-dict ``Env``/``Labels``).
    """
    out = copy.deepcopy(body)
    if libpod:
        out["labels"] = with_label(out.get("labels"), ctx.slug)
        for pm in out.get("portmappings") or []:
            if not pm.get("host_ip"):
                pm["host_ip"] = "127.0.0.1"
        if ctx.proxy_env and ctx.egress_mode != "off":
            env = {
                k: v for k, v in (out.get("env") or {}).items() if k.casefold() not in _PROXY_VARS_CASEFOLD
            }
            env.update(ctx.proxy_env)
            out["env"] = env
    else:
        out["Labels"] = with_label(out.get("Labels"), ctx.slug)
        # `out.setdefault` only fills in an *absent* key; an explicit
        # `"HostConfig": null` (which check_create allows - see
        # `_malformed_shape`) leaves `hc` as `None` and the `.get()` below
        # raises. `or {}` normalises both "absent" and "explicit null".
        hc = out.get("HostConfig") or {}
        out["HostConfig"] = hc
        for bindings in (hc.get("PortBindings") or {}).values():
            for b in bindings or []:
                if not b.get("HostIp"):
                    b["HostIp"] = "127.0.0.1"
        if ctx.proxy_env and ctx.egress_mode != "off":
            env_list: list[str] = [
                e for e in out.get("Env") or [] if e.split("=", 1)[0].casefold() not in _PROXY_VARS_CASEFOLD
            ]
            env_list.extend(f"{k}={v}" for k, v in ctx.proxy_env.items())
            out["Env"] = env_list
    return out
