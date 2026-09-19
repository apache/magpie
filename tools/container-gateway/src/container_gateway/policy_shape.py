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
"""Canonical-spelling enforcement for create-request bodies.

Both dockerd and podman decode JSON with Go's ``encoding/json``: object
keys match struct fields case-insensitively, and when two keys collide
under that comparison the last one wins. A client can therefore smuggle
a policy-relevant field past every check in ``policy.py`` by spelling it
differently than the checks look for (``hostconfig`` instead of
``HostConfig``, ``PRIVILEGED`` instead of ``Privileged``), or can make
the gateway rewrite one spelling of a field while the daemon honours a
second, client-supplied spelling of the same field (``Labels`` and
``labels`` both present).

This module is pure and stateless: it only inspects key spellings, never
values. It is split out of ``policy.py`` to keep that module below the
file's target size.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

CATALOG_ANCHOR = "docs/setup/sandbox-troubleshooting.md#docker--podman-command-fails-with-a-socket-error"


@dataclass(frozen=True)
class Deny:
    """A create/act request the policy refuses, and why.

    Defined here (not in ``policy.py``) so this module and ``policy.py``
    can each import it without a circular import between the two.
    """

    reason: str
    status: int = 403

    @property
    def message(self) -> str:
        return f"container-gateway: {self.reason}; see {CATALOG_ANCHOR}"


# Every key the policy in policy.py reads or rewrites, by shape. A client
# key that casefold-matches one of these but is not spelled exactly like
# this is ambiguous: the daemon's case-insensitive decoder might bind it
# to the same struct field, or might not, depending on decode order.
COMPAT_TOP_KEYS = frozenset(
    {
        "Image",
        "Labels",
        "Env",
        "HostConfig",
        "NetworkingConfig",
        "Volumes",
        "User",
        "Entrypoint",
        "Cmd",
        "ExposedPorts",
    }
)

COMPAT_HOSTCONFIG_KEYS = frozenset(
    {
        "Privileged",
        "CapAdd",
        "CapDrop",
        "Devices",
        "DeviceRequests",
        "DeviceCgroupRules",
        "PidMode",
        "IpcMode",
        "UTSMode",
        "UsernsMode",
        "CgroupnsMode",
        "NetworkMode",
        "SecurityOpt",
        "Sysctls",
        "CgroupParent",
        "Runtime",
        "Isolation",
        "MaskedPaths",
        "ReadonlyPaths",
        "Binds",
        "Mounts",
        "VolumesFrom",
        "PortBindings",
        "PublishAllPorts",
        "Tmpfs",
    }
)

COMPAT_MOUNT_KEYS = frozenset(
    {"Type", "Source", "Target", "ReadOnly", "BindOptions", "VolumeOptions", "TmpfsOptions"}
)

COMPAT_PORT_BINDING_KEYS = frozenset({"HostIp", "HostPort"})

LIBPOD_TOP_KEYS = frozenset(
    {
        "image",
        "labels",
        "env",
        "privileged",
        "cap_add",
        "cap_drop",
        "devices",
        "device_cgroup_rule",
        "pidns",
        "ipcns",
        "utsns",
        "userns",
        "cgroupns",
        "netns",
        "selinux_opts",
        "apparmor_profile",
        "seccomp_policy",
        "seccomp_profile_path",
        "no_new_privileges",
        "mask",
        "unmask",
        "sysctl",
        "cgroup_parent",
        "oci_runtime",
        "mounts",
        "volumes",
        "volumes_from",
        "portmappings",
        "publish_image_ports",
    }
)

LIBPOD_MOUNT_KEYS = frozenset({"type", "source", "destination", "options"})

LIBPOD_PORTMAPPING_KEYS = frozenset({"host_ip", "host_port", "container_port", "protocol", "range"})


def _spelling_violation_in(obj: dict[str, Any], known: frozenset[str]) -> Deny | None:
    """Ambiguous-spelling check for one object's own keys.

    Two rules, checked in order so a duplicate is reported as a duplicate
    even when one of the two spellings happens to be canonical:

    1. Two present keys casefold to the same value (a duplicate the
       daemon's decoder would silently resolve one way or the other).
    2. A present key casefolds to a key in ``known`` but is not spelled
       exactly like it (an aliased field the policy would not recognise).
    """
    by_casefold: dict[str, list[str]] = {}
    for key in obj:
        if isinstance(key, str):
            by_casefold.setdefault(key.casefold(), []).append(key)

    for keys in by_casefold.values():
        if len(keys) > 1:
            a, b = sorted(keys)[:2]
            return Deny(f"ambiguous-field: {a} and {b} name the same field")

    known_by_casefold = {k.casefold(): k for k in known}
    for cf, keys in by_casefold.items():
        canonical = known_by_casefold.get(cf)
        if canonical is not None and keys[0] != canonical:
            return Deny(f"ambiguous-field: {keys[0]} is not the canonical spelling of {canonical}")
    return None


def canonical_spelling_violation(body: dict[str, Any], libpod: bool) -> Deny | None:
    """Deny a body carrying a case-variant or duplicate spelling of a known field.

    Inspected objects: the top-level body, ``HostConfig`` (compat only),
    every entry of ``Mounts`` / ``mounts``, every entry of the
    ``PortBindings`` value lists / ``portmappings``, and ``NetworkingConfig``
    if present (collision-only there; the API does not fix its own key set).
    """
    if libpod:
        violation = _spelling_violation_in(body, LIBPOD_TOP_KEYS)
        if violation is not None:
            return violation
        for mount in body.get("mounts") or []:
            if isinstance(mount, dict):
                violation = _spelling_violation_in(mount, LIBPOD_MOUNT_KEYS)
                if violation is not None:
                    return violation
        for mapping in body.get("portmappings") or []:
            if isinstance(mapping, dict):
                violation = _spelling_violation_in(mapping, LIBPOD_PORTMAPPING_KEYS)
                if violation is not None:
                    return violation
        return None

    violation = _spelling_violation_in(body, COMPAT_TOP_KEYS)
    if violation is not None:
        return violation

    host_config = body.get("HostConfig")
    if isinstance(host_config, dict):
        violation = _spelling_violation_in(host_config, COMPAT_HOSTCONFIG_KEYS)
        if violation is not None:
            return violation
        for mount in host_config.get("Mounts") or []:
            if isinstance(mount, dict):
                violation = _spelling_violation_in(mount, COMPAT_MOUNT_KEYS)
                if violation is not None:
                    return violation
        port_bindings = host_config.get("PortBindings")
        if isinstance(port_bindings, dict):
            for bindings in port_bindings.values():
                for binding in bindings or []:
                    if isinstance(binding, dict):
                        violation = _spelling_violation_in(binding, COMPAT_PORT_BINDING_KEYS)
                        if violation is not None:
                            return violation

    networking_config = body.get("NetworkingConfig")
    if isinstance(networking_config, dict):
        violation = _spelling_violation_in(networking_config, frozenset())
        if violation is not None:
            return violation

    return None
