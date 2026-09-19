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
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .labels import with_label
from .policy_shape import CATALOG_ANCHOR, Deny, canonical_spelling_violation

__all__ = [
    "CATALOG_ANCHOR",
    "PROXY_VARS",
    "Deny",
    "PolicyContext",
    "apply_create_rewrites",
    "check_create",
    "named_network",
    "named_volumes",
    "resolve_bind_source",
]

PROXY_VARS = ("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "no_proxy")
_PROXY_VARS_CASEFOLD = frozenset(v.casefold() for v in PROXY_VARS)

# PidMode / IpcMode / UTSMode / UsernsMode / CgroupnsMode and their libpod
# equivalents (pidns / ipcns / utsns / userns / cgroupns): an allow-list, not
# a deny-list, so an unrecognised mode (a new backend feature, a typo, an
# attempt at obfuscation) is refused rather than silently passed through.
_NAMESPACE_ALLOWED_MODES = frozenset({"", "private", "pod", "auto", "keep-id", "nomap"})

# NetworkMode / netns: a fixed set of safe keywords is allowed outright; a
# named network (any other value) is allowed here and left to the relay's
# label check (Task 9); anything that looks like it targets a host or
# foreign namespace is refused regardless of spelling case.
_NETWORK_MODE_KEYWORDS = frozenset({"", "default", "bridge", "none", "private", "slirp4netns", "pasta"})
_NETWORK_HOST_LIKE_PREFIXES = ("host", "container:", "ns:", "path")

# SecurityOpt keys the policy recognises at all; every other key (including
# unmask, proc-opts) is refused outright.
_SECCOMP_ALLOWED_VALUES = frozenset({"", "default"})

_MOUNT_PASSTHROUGH_TYPES = frozenset({"tmpfs"})
_MOUNT_REFUSED_TYPES = frozenset({"image", "devpts", "npipe"})


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
    """Namespace mode as a string for both shapes: ``"host"`` or ``{"nsmode": "host"}``."""
    if isinstance(value, dict):
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


def _malformed_shape(body: dict[str, Any], libpod: bool) -> Deny | None:
    """Type-guard every field the rest of ``check_create`` iterates over.

    Never lets a wrongly-typed field reach an iteration or ``.get()`` call
    that would raise; every such shape is refused as ``malformed`` instead.
    """
    if not libpod:
        host_config = body.get("HostConfig")
        if host_config is not None and not isinstance(host_config, dict):
            return Deny("malformed: HostConfig has the wrong type")

    host = _host(body, libpod)

    list_fields: list[tuple[str, Any]] = []
    if libpod:
        list_fields.append(("cap_add", host.get("cap_add")))
        list_fields.append(("selinux_opts", host.get("selinux_opts")))
        mounts_field, mounts = "mounts", body.get("mounts")
        port_field, ports = "portmappings", body.get("portmappings")
    else:
        list_fields.append(("CapAdd", host.get("CapAdd")))
        list_fields.append(("SecurityOpt", host.get("SecurityOpt")))
        list_fields.append(("Binds", host.get("Binds")))
        mounts_field, mounts = "Mounts", host.get("Mounts")
        port_field, ports = None, None

    for name, value in list_fields:
        if value is not None and not isinstance(value, list):
            return Deny(f"malformed: {name} has the wrong type")

    if mounts is not None:
        if not isinstance(mounts, list):
            return Deny(f"malformed: {mounts_field} has the wrong type")
        for entry in mounts:
            if not isinstance(entry, dict):
                return Deny(f"malformed: {mounts_field} entries must be objects")

    if not libpod:
        port_bindings = host.get("PortBindings")
        if port_bindings is not None:
            if not isinstance(port_bindings, dict):
                return Deny("malformed: PortBindings has the wrong type")
            for bindings in port_bindings.values():
                if bindings is None:
                    continue
                if not isinstance(bindings, list):
                    return Deny("malformed: PortBindings has the wrong type")
                for entry in bindings:
                    if not isinstance(entry, dict):
                        return Deny("malformed: PortBindings entries must be objects")
    elif ports is not None:
        if not isinstance(ports, list):
            return Deny(f"malformed: {port_field} has the wrong type")
        for entry in ports:
            if not isinstance(entry, dict):
                return Deny(f"malformed: {port_field} entries must be objects")

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
    return names


def named_network(body: dict[str, Any], libpod: bool) -> str | None:
    """The named network this create body attaches to, if any (the relay label-checks it, Task 9).

    Returns ``None`` for the fixed keywords and for the host/foreign-namespace
    forms that ``check_create`` refuses outright — only an actual named
    network is returned.
    """
    host = _host(body, libpod)
    net = _nsmode(host.get("netns") if libpod else host.get("NetworkMode"))
    net_cf = net.casefold()
    if net_cf in _NETWORK_MODE_KEYWORDS or net_cf.startswith(_NETWORK_HOST_LIKE_PREFIXES):
        return None
    return net


def check_create(body: dict[str, Any], ctx: PolicyContext, *, libpod: bool) -> Deny | None:
    spelling_violation = canonical_spelling_violation(body, libpod)
    if spelling_violation is not None:
        return spelling_violation

    malformed = _malformed_shape(body, libpod)
    if malformed is not None:
        return malformed

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
                f"namespace: {key}={mode} is refused; only private, pod, auto, keep-id and nomap are allowed"
            )

    for key in ("NetworkMode", "netns"):
        net = _nsmode(host.get(key))
        net_cf = net.casefold()
        if net_cf not in _NETWORK_MODE_KEYWORDS and net_cf.startswith(_NETWORK_HOST_LIKE_PREFIXES):
            return Deny(f"network: {key}={net} is refused; use a bridge network created through the gateway")

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
    if "MaskedPaths" in host:
        return Deny("masked-paths: MaskedPaths is refused")
    if "mask" in host:
        return Deny("masked-paths: mask is refused")
    if "ReadonlyPaths" in host:
        return Deny("readonly-paths: ReadonlyPaths is refused")
    if host.get("unmask"):
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
        hc = out.setdefault("HostConfig", {})
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
