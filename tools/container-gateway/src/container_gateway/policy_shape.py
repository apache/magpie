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
        "networks",
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
        "security_opt",
        # podman's SpecGenerator spells the per-network map ``Networks``
        # (capital N, the Go field name); older clients send ``networks``.
        # Both are canonical -- see ``_spelling_violation_in``.
        "Networks",
    }
)

LIBPOD_MOUNT_KEYS = frozenset({"type", "source", "destination", "options"})

LIBPOD_PORTMAPPING_KEYS = frozenset({"host_ip", "host_port", "container_port", "protocol", "range"})

# The six libpod namespace objects (``{"nsmode": "...", "value": "..."}``):
# NetworkMode's libpod sibling ``netns`` is namespace-shaped too, so it is
# inspected the same way even though the network check itself lives in
# policy.py.
NAMESPACE_OBJECT_FIELDS = ("pidns", "ipcns", "utsns", "userns", "cgroupns", "netns")
NAMESPACE_OBJECT_KEYS = frozenset({"nsmode", "value"})

# libpod's top-level named-volume list: ``volumes: [{"Name": ..., "Dest": ...}]``.
# Mixed-case keys inside an otherwise snake_case body — that is podman's own
# SpecGenerator shape, not a spelling choice made here.
LIBPOD_VOLUME_KEYS = frozenset({"Name", "Dest", "Options"})

# The (much smaller) volume/network create body shape: every key the gateway
# reads or rewrites there, by shape.
VOLUME_NETWORK_COMPAT_KEYS = frozenset({"Name", "Labels", "Driver", "DriverOpts"})
VOLUME_NETWORK_LIBPOD_KEYS = frozenset({"name", "labels", "driver", "options"})


def _spelling_violation_in(obj: dict[str, Any], known: frozenset[str]) -> Deny | None:
    """Ambiguous-spelling check for one object's own keys.

    Two rules, checked in order so a duplicate is reported as a duplicate
    even when one of the two spellings happens to be canonical:

    1. Two present keys casefold to the same value (a duplicate the
       daemon's decoder would silently resolve one way or the other).
    2. A present key casefolds to a key in ``known`` but is not spelled
       exactly like one of the accepted spellings for it (an aliased field
       the policy would not recognise).

    ``known`` may carry more than one accepted spelling for the same
    casefolded name (``networks`` and ``Networks``): podman's own
    SpecGenerator renamed that field's JSON tag between releases, so both
    spellings are canonical for some client the gateway must serve. Rule 1
    still refuses a body carrying *both* at once.
    """
    by_casefold: dict[str, list[str]] = {}
    for key in obj:
        if isinstance(key, str):
            by_casefold.setdefault(key.casefold(), []).append(key)

    for keys in by_casefold.values():
        if len(keys) > 1:
            a, b = sorted(keys)[:2]
            return Deny(f"ambiguous-field: {a} and {b} name the same field")

    known_by_casefold: dict[str, set[str]] = {}
    for k in known:
        known_by_casefold.setdefault(k.casefold(), set()).add(k)
    for cf, keys in by_casefold.items():
        accepted = known_by_casefold.get(cf)
        if accepted is not None and keys[0] not in accepted:
            canonical = "/".join(sorted(accepted))
            return Deny(f"ambiguous-field: {keys[0]} is not the canonical spelling of {canonical}")
    return None


def object_spelling_violation(obj: dict[str, Any], known: frozenset[str]) -> Deny | None:
    """``_spelling_violation_in`` for callers outside this module.

    Used by the exec / update body checks in ``policy.py``, whose bodies
    are a single flat object rather than the nested create shape
    ``canonical_spelling_violation`` walks.
    """
    return _spelling_violation_in(obj, known)


def canonical_spelling_violation(body: dict[str, Any], libpod: bool) -> Deny | None:
    """Deny a body carrying a case-variant or duplicate spelling of a known field.

    Inspected objects: the top-level body, ``HostConfig`` (compat only),
    every entry of ``Mounts`` / ``mounts``, every entry of the
    ``PortBindings`` value lists / ``portmappings``, every libpod namespace
    object (``pidns``/``ipcns``/``utsns``/``userns``/``cgroupns``/``netns``),
    every entry of libpod ``volumes``, libpod ``networks``, and
    ``NetworkingConfig`` / its ``EndpointsConfig`` if present
    (collision-only for both of those — the API does not fix their key set).
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
        for volume in body.get("volumes") or []:
            if isinstance(volume, dict):
                violation = _spelling_violation_in(volume, LIBPOD_VOLUME_KEYS)
                if violation is not None:
                    return violation
        for field in NAMESPACE_OBJECT_FIELDS:
            namespace_obj = body.get(field)
            if isinstance(namespace_obj, dict):
                violation = _spelling_violation_in(namespace_obj, NAMESPACE_OBJECT_KEYS)
                if violation is not None:
                    return violation
        for key in ("networks", "Networks"):
            networks = body.get(key)
            if isinstance(networks, dict):
                violation = _spelling_violation_in(networks, frozenset())
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
        endpoints_config = networking_config.get("EndpointsConfig")
        if isinstance(endpoints_config, dict):
            violation = _spelling_violation_in(endpoints_config, frozenset())
            if violation is not None:
                return violation

    return None


def resource_create_spelling_violation(body: dict[str, Any], libpod: bool) -> Deny | None:
    """Ambiguous-spelling check for a volume/network create body.

    Mirrors ``canonical_spelling_violation`` for containers/pods, but for the
    much smaller volume/network create shape (``Name``/``Labels``/``Driver``/
    ``DriverOpts`` compat, ``name``/``labels``/``driver``/``options`` libpod).
    Without this, a second spelling of the label field (``labels`` *and*
    ``Labels`` both present, or ``LABELS``) would let a client's value
    collide with the gateway's injected project label under the daemon's
    case-insensitive JSON decode — the same escape
    ``canonical_spelling_violation`` already closes for container/pod create.
    """
    known = VOLUME_NETWORK_LIBPOD_KEYS if libpod else VOLUME_NETWORK_COMPAT_KEYS
    return _spelling_violation_in(body, known)


# --- The create-body allow-list ----------------------------------------
#
# The posture is an allow-list, not a deny-list: a create body may carry
# only the fields enumerated here, and every other key is refused as
# ``unknown-field``. A deny-list over an unbounded JSON body cannot be
# right by construction -- both daemons grow fields faster than this
# policy can learn them, and several of the ones already shipped (libpod
# ``rootfs``, ``overlay_volumes``, ``env_host``, ``log_configuration``)
# turn a container into host access on their own.
#
# The cost of the posture is that a field the gateway has not learned is
# unavailable through it until it is added here; that is deliberate and
# documented in the tool's "Limits and residual risks" section.
#
# The three sets below are merged into one casefolded allow-list applied
# to the top level of both shapes and to compat's ``HostConfig``. They are
# not kept apart per position because the policy already reads both
# shapes' spellings out of both positions unconditionally (see the module
# docstring in policy.py): a field in the "wrong" position is inert for
# the daemon, which decodes into one struct or the other, and splitting
# the tables would only add a way for the two halves to disagree.

# moby's container.Config plus the create request's own keys. Every one of
# these is sent (at its Go zero value) by a plain ``docker run``.
COMPAT_TOP_ALLOWED = frozenset(
    {
        "ArgsEscaped",
        "AttachStderr",
        "AttachStdin",
        "AttachStdout",
        "Cmd",
        "Domainname",
        "Entrypoint",
        "Env",
        "ExposedPorts",
        "Healthcheck",
        "HostConfig",
        "Hostname",
        "Image",
        "Labels",
        "MacAddress",
        "NetworkDisabled",
        "NetworkingConfig",
        "OnBuild",
        "OpenStdin",
        "Platform",
        "Shell",
        "StdinOnce",
        "StopSignal",
        "StopTimeout",
        "Tty",
        "User",
        "Volumes",
        "WorkingDir",
        "name",
    }
)

# moby's container.HostConfig. The dangerous members are in the table
# above's company only by name: they stay in this set because a real
# ``docker run`` sends every one of them at its zero value, and the
# value-level rules in policy.py are what actually refuse them.
COMPAT_HOSTCONFIG_ALLOWED = frozenset(
    {
        "Annotations",
        "AutoRemove",
        "Binds",
        "BlkioDeviceReadBps",
        "BlkioDeviceReadIOps",
        "BlkioDeviceWriteBps",
        "BlkioDeviceWriteIOps",
        "BlkioWeight",
        "BlkioWeightDevice",
        "CapAdd",
        "CapDrop",
        "Capabilities",
        "Cgroup",
        "CgroupParent",
        "CgroupnsMode",
        "ConsoleSize",
        "ContainerIDFile",
        "CpuCount",
        "CpuPercent",
        "CpuPeriod",
        "CpuQuota",
        "CpuRealtimePeriod",
        "CpuRealtimeRuntime",
        "CpuShares",
        "CpusetCpus",
        "CpusetMems",
        "DeviceCgroupRules",
        "DeviceRequests",
        "Devices",
        "Dns",
        "DnsOptions",
        "DnsSearch",
        "ExtraHosts",
        "GroupAdd",
        "IOMaximumBandwidth",
        "IOMaximumIOps",
        "Init",
        "IpcMode",
        "Isolation",
        "KernelMemory",
        "KernelMemoryTCP",
        "Links",
        "LogConfig",
        "MaskedPaths",
        "Memory",
        "MemoryReservation",
        "MemorySwap",
        "MemorySwappiness",
        "Mounts",
        "NanoCpus",
        "NetworkMode",
        "OomKillDisable",
        "OomScoreAdj",
        "PidMode",
        "PidsLimit",
        "PortBindings",
        "Privileged",
        "PublishAllPorts",
        "ReadonlyPaths",
        "ReadonlyRootfs",
        "RestartPolicy",
        "Runtime",
        "SecurityOpt",
        "ShmSize",
        "StorageOpt",
        "Sysctls",
        "Tmpfs",
        "UTSMode",
        "Ulimits",
        "UsernsMode",
        "VolumeDriver",
        "VolumesFrom",
    }
)

# podman's SpecGenerator (container create) and PodSpecGenerator (pod
# create). Taken from the bodies podman 6.1's remote client actually
# sends, plus the SpecGenerator members a flag can set.
LIBPOD_TOP_ALLOWED = frozenset(
    {
        "Networks",
        "annotations",
        "apparmor_profile",
        "cap_add",
        "cap_drop",
        "cgroup_parent",
        "cgroupns",
        "cgroups_mode",
        "command",
        "conmon_pid_file",
        "containerCreateCommand",
        "dependencyContainers",
        "device_cgroup_rule",
        "devices",
        "dns_option",
        "dns_search",
        "dns_server",
        "entrypoint",
        "env",
        "env_merge",
        "expose",
        "groups",
        "healthLogDestination",
        "healthMaxLogCount",
        "healthMaxLogSize",
        "health_check_on_failure_action",
        "health_config",
        "healthconfig",
        "startupHealthConfig",
        "base_hosts_file",
        "hostadd",
        "hostname",
        "hostusers",
        "httpproxy",
        "idmappings",
        "image",
        "image_arch",
        "image_os",
        "image_variant",
        "image_volume_mode",
        "image_volumes",
        "init",
        "init_container_type",
        "ipcns",
        "labels",
        "manage_password",
        "mask",
        "mounts",
        "name",
        "netns",
        "networkOrder",
        "networks",
        "no_hosts",
        "no_new_privileges",
        "oci_runtime",
        "oom_score_adj",
        "passwd_entry",
        "pidns",
        "pod",
        "portmappings",
        "privileged",
        "publish_image_ports",
        "raw_image_name",
        "read_only_filesystem",
        "read_write_tmpfs",
        "remove",
        "remove_image",
        "resource_limits",
        "restart_policy",
        "restart_tries",
        "sdnotifyMode",
        "seccomp_policy",
        "seccomp_profile_path",
        "security_opt",
        "selinux_opts",
        "shm_size",
        "shm_size_systemd",
        "static_ip",
        "static_ipv6",
        "static_mac",
        "stdin",
        "stop_signal",
        "stop_timeout",
        "sysctl",
        "systemd",
        "terminal",
        "timeout",
        "timezone",
        "umask",
        "unified",
        "unmask",
        "unsetenv",
        "unsetenvall",
        "use_image_hostname",
        "use_image_hosts",
        "use_image_resolve_conf",
        "user",
        "userns",
        "utsns",
        "volatile",
        "volumes",
        "volumes_from",
        "weight_device",
        "work_dir",
        # PodSpecGenerator's own members (pod create shares this policy).
        "exit_policy",
        "infra_command",
        "infra_image",
        "infra_name",
        "no_infra",
        "no_manage_hostname",
        "no_manage_hosts",
        "no_manage_resolv_conf",
        "pid",
        "pod_create_command",
        "serviceContainerID",
        "share_parent",
        "shared_namespaces",
    }
)

# Fields refused with a reason of their own rather than a bare
# ``unknown-field``. Each is refused only when it carries a *set* value:
# both CLIs serialise the zero value of every member of their create
# struct on every request (``"env_host": false``, ``"log_configuration":
# {}``), so refusing on mere presence would refuse every create.
DENIED_CREATE_FIELDS: dict[str, str] = {
    "rootfs": "rootfs: a host path as the container root filesystem is refused",
    "rootfs_overlay": "rootfs: an overlay over a host root filesystem is refused",
    "overlay_volumes": "overlay-volumes: overlay mounts of host paths are refused",
    "env_host": "env-host: exporting the host environment into the container is refused",
    "log_configuration": "log-configuration: a custom log driver can write to a host path and is refused",
    "secret_env": "secrets: daemon secrets are refused",
    "secrets": "secrets: daemon secrets are refused",
    "cni_networks": "network: cni_networks is refused; attach networks through networks",
    "chroot_directories": "chroot-directories: host directories to chroot into are refused",
    "init_path": "init-path: a host path as the container init binary is refused",
    "conmon_pid_file": "pid-file: writing a pid file on the host is refused",
    "infra_conmon_pid_file": "pid-file: writing a pid file on the host is refused",
    "ContainerIDFile": "container-id-file: writing a container id file on the host is refused",
    "Links": "links: --link reaches another project's container and is refused",
    "Cgroup": "cgroup-parent: joining another container's cgroup is refused",
    "VolumeDriver": "volume-driver: a custom volume driver is refused",
}

CREATE_ALLOWED_FIELDS = frozenset(
    name.casefold()
    for name in (
        COMPAT_TOP_ALLOWED | COMPAT_HOSTCONFIG_ALLOWED | LIBPOD_TOP_ALLOWED | frozenset(DENIED_CREATE_FIELDS)
    )
)

# ``POST /containers/<id>/exec``: the whole body, in the one shape both
# APIs use (libpod's exec endpoint takes moby's spelling).
EXEC_KNOWN_KEYS = frozenset(
    {
        "AttachStderr",
        "AttachStdin",
        "AttachStdout",
        "Cmd",
        "ConsoleSize",
        "DetachKeys",
        "Env",
        "Privileged",
        "Tty",
        "User",
        "WorkingDir",
    }
)
EXEC_ALLOWED_FIELDS = frozenset(name.casefold() for name in EXEC_KNOWN_KEYS)

# ``POST /containers/<id>/update``: moby's UpdateConfig, which is
# container.Resources plus RestartPolicy. Nothing here can reach the host;
# everything else in an update body can.
UPDATE_KNOWN_KEYS = frozenset(
    {
        "BlkioDeviceReadBps",
        "BlkioDeviceReadIOps",
        "BlkioDeviceWriteBps",
        "BlkioDeviceWriteIOps",
        "BlkioWeight",
        "BlkioWeightDevice",
        "CpuCount",
        "CpuPercent",
        "CpuPeriod",
        "CpuQuota",
        "CpuRealtimePeriod",
        "CpuRealtimeRuntime",
        "CpuShares",
        "CpusetCpus",
        "CpusetMems",
        "IOMaximumBandwidth",
        "IOMaximumIOps",
        "KernelMemory",
        "KernelMemoryTCP",
        "Memory",
        "MemoryReservation",
        "MemorySwap",
        "MemorySwappiness",
        "NanoCpus",
        "OomKillDisable",
        "PidsLimit",
        "RestartPolicy",
        "Ulimits",
    }
)
UPDATE_ALLOWED_FIELDS = frozenset(name.casefold() for name in UPDATE_KNOWN_KEYS)


def allow_list_violation(
    obj: dict[str, Any], allowed: frozenset[str], *, denied: dict[str, str] | None = None
) -> Deny | None:
    """Refuse a key that is not in ``allowed``, or a ``denied`` one that is set.

    Keys are compared casefolded, because that is how both daemons' JSON
    decoders bind an object key to a struct field: a deny keyed on the
    exact spelling would be sidestepped by ``ROOTFS``. The canonical-
    spelling check runs first and refuses a case variant of a field the
    policy reasons about; this check is what refuses everything the policy
    has never heard of.
    """
    denied_fields = DENIED_CREATE_FIELDS if denied is None else denied
    for key, value in obj.items():
        if not isinstance(key, str):
            return Deny("malformed: object keys must be strings")
        casefolded = key.casefold()
        reason = denied_fields.get(casefolded) or denied_fields.get(key)
        if reason is not None and value:
            return Deny(reason)
        if casefolded not in allowed:
            return Deny(f"unknown-field: {key} is not accepted by the gateway")
    return None
