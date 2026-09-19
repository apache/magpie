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

Everything here is a pure function over parsed requests. Nothing talks to
the backend; the label pre-check that needs backend I/O lives in relay.py.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .labels import with_label

CATALOG_ANCHOR = "docs/setup/sandbox-troubleshooting.md#docker--podman-command-fails-with-a-socket-error"
PROXY_VARS = ("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "no_proxy")


@dataclass(frozen=True)
class Deny:
    reason: str
    status: int = 403

    @property
    def message(self) -> str:
        return f"container-gateway: {self.reason}; see {CATALOG_ANCHOR}"


@dataclass(frozen=True)
class PolicyContext:
    slug: str
    project_root: Path
    bind_roots: tuple[Path, ...]
    proxy_env: dict[str, str] | None
    egress_mode: str = "inject-if-available"
    extra: dict[str, Any] = field(default_factory=dict)


def _host(body: dict[str, Any], libpod: bool) -> dict[str, Any]:
    return body if libpod else body.get("HostConfig") or {}


def _nsmode(value: Any) -> str:
    """Namespace mode as a string for both shapes: ``"host"`` or ``{"nsmode": "host"}``."""
    if isinstance(value, dict):
        return str(value.get("nsmode", ""))
    return str(value or "")


def resolve_bind_source(src: str, ctx: PolicyContext) -> bool:
    try:
        real = Path(src).resolve(strict=False)
    except (OSError, RuntimeError):
        return False
    return any(real == root.resolve() or root.resolve() in real.parents for root in ctx.bind_roots)


def _bind_sources(host: dict[str, Any], body: dict[str, Any], libpod: bool) -> list[str]:
    sources: list[str] = []
    for spec in host.get("Binds") or []:
        src = str(spec).split(":", 1)[0]
        # A bare name (no slash) is a named volume, label-checked by the relay.
        if src.startswith(("/", ".", "~")):
            sources.append(src)
    mounts = body.get("mounts") if libpod else host.get("Mounts")
    for m in mounts or []:
        if str(m.get("type", m.get("Type", ""))).lower() == "bind":
            sources.append(str(m.get("source", m.get("Source", ""))))
    return sources


_BAD_SECURITY_OPTS = (
    "seccomp=unconfined",
    "apparmor=unconfined",
    "label=disable",
    "no-new-privileges=false",
    "systempaths=unconfined",
)


def check_create(body: dict[str, Any], ctx: PolicyContext, *, libpod: bool) -> Deny | None:
    host = _host(body, libpod)

    if host.get("Privileged") or host.get("privileged"):
        return Deny("privileged: drop --privileged; the gateway never grants it")
    if host.get("CapAdd") or host.get("cap_add"):
        return Deny("cap-add: added capabilities are refused; run without --cap-add")
    if any(host.get(k) for k in ("Devices", "DeviceRequests", "DeviceCgroupRules", "devices")):
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
        if mode == "host" or mode.startswith("container:"):
            return Deny(
                f"namespace: {key}={mode} is refused; joining host or foreign namespaces is not allowed"
            )

    net = _nsmode(host.get("NetworkMode") or host.get("netns"))
    if net == "host" or net.startswith("container:"):
        return Deny(
            f"network: NetworkMode={net} is refused; use a bridge network created through the gateway"
        )

    for opt in host.get("SecurityOpt") or host.get("security_opt") or []:
        if str(opt).replace(" ", "").lower() in _BAD_SECURITY_OPTS:
            return Deny(f"security-opt: {opt} is refused")
    if host.get("Sysctls") or host.get("sysctl"):
        return Deny("sysctls: kernel parameters are refused")
    if host.get("CgroupParent") or host.get("cgroup_parent"):
        return Deny("cgroup-parent: custom cgroup parents are refused")
    if host.get("Runtime") or host.get("oci_runtime"):
        return Deny("runtime: alternative OCI runtimes are refused")
    if host.get("Isolation"):
        return Deny("isolation: the Isolation field is refused")
    if "MaskedPaths" in host and host["MaskedPaths"] == []:
        return Deny("masked-paths: emptying MaskedPaths is refused")
    if "ReadonlyPaths" in host and host["ReadonlyPaths"] == []:
        return Deny("readonly-paths: emptying ReadonlyPaths is refused")

    for src in _bind_sources(host, body, libpod):
        if not resolve_bind_source(src, ctx):
            roots = ", ".join(str(r) for r in ctx.bind_roots)
            return Deny(f"bind-mount: {src} is outside the allowed roots ({roots})")

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
            env = dict(out.get("env") or {})
            for k in PROXY_VARS:
                env.pop(k, None)
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
            env_list: list[str] = [e for e in out.get("Env") or [] if e.split("=", 1)[0] not in PROXY_VARS]
            env_list.extend(f"{k}={v}" for k, v in ctx.proxy_env.items())
            out["Env"] = env_list
    return out
