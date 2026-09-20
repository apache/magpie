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
"""Every row of the spec's create-time table, in compat and libpod shape."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from container_gateway.labels import LABEL_KEY
from container_gateway.policy import (
    Deny,
    PolicyContext,
    apply_create_rewrites,
    check_create,
    named_networks,
    named_volumes,
)


@pytest.fixture
def ctx(tmp_path: Path) -> PolicyContext:
    root = tmp_path / "proj"
    root.mkdir()
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    return PolicyContext(
        slug="-proj",
        project_root=root,
        bind_roots=(root, scratch),
        proxy_env={"HTTP_PROXY": "http://host.containers.internal:8899"},
        egress_mode="inject-if-available",
    )


def compat(**host: Any) -> dict[str, Any]:
    return {"Image": "alpine", "HostConfig": host}


def libpod(**top: Any) -> dict[str, Any]:
    return {"image": "alpine", **top}


def compat_with_endpoints(endpoints: dict[str, Any]) -> dict[str, Any]:
    body = compat()
    body["NetworkingConfig"] = {"EndpointsConfig": endpoints}
    return body


@pytest.mark.parametrize(
    ("body", "rule"),
    [
        (compat(Privileged=True), "privileged"),
        (libpod(privileged=True), "privileged"),
        (compat(CapAdd=["SYS_ADMIN"]), "cap-add"),
        (libpod(cap_add=["NET_RAW"]), "cap-add"),
        (compat(Devices=[{"PathOnHost": "/dev/kvm"}]), "devices"),
        (compat(DeviceRequests=[{"Driver": "nvidia"}]), "devices"),
        (compat(DeviceCgroupRules=["c 1:3 rwm"]), "devices"),
        (libpod(devices=["/dev/kvm"]), "devices"),
        (compat(PidMode="host"), "namespace"),
        (compat(IpcMode="host"), "namespace"),
        (compat(UTSMode="host"), "namespace"),
        (compat(UsernsMode="host"), "namespace"),
        (compat(CgroupnsMode="host"), "namespace"),
        (compat(PidMode="container:deadbeef"), "namespace"),
        (libpod(pidns={"nsmode": "host"}), "namespace"),
        (libpod(userns={"nsmode": "host"}), "namespace"),
        (compat(NetworkMode="host"), "network"),
        (compat(NetworkMode="container:deadbeef"), "network"),
        (libpod(netns={"nsmode": "host"}), "network"),
        (compat(SecurityOpt=["seccomp=unconfined"]), "security-opt"),
        (compat(SecurityOpt=["apparmor=unconfined"]), "security-opt"),
        (compat(SecurityOpt=["label=disable"]), "security-opt"),
        (compat(SecurityOpt=["no-new-privileges=false"]), "security-opt"),
        (compat(SecurityOpt=["systempaths=unconfined"]), "security-opt"),
        (compat(Sysctls={"net.ipv4.ip_forward": "1"}), "sysctls"),
        (compat(CgroupParent="/x"), "cgroup-parent"),
        (compat(Runtime="nvidia"), "runtime"),
        (compat(Isolation="hyperv"), "isolation"),
        (compat(MaskedPaths=[]), "masked-paths"),
        (compat(ReadonlyPaths=[]), "readonly-paths"),
        (compat(Binds=["/etc:/etc:ro"]), "bind-mount"),
        (compat(Binds=["/Users/alice/.ssh:/root/.ssh"]), "bind-mount"),
        (compat(Mounts=[{"Type": "bind", "Source": "/", "Target": "/host"}]), "bind-mount"),
        (libpod(mounts=[{"type": "bind", "source": "/etc", "destination": "/etc"}]), "bind-mount"),
        (compat(VolumesFrom=["other"]), "volumes-from"),
        # --- Fix round 1 additions below ---
        # I3: namespace/network allow-list, not two literals
        (compat(PidMode="ns:/proc/1/ns/pid"), "namespace"),
        (libpod(pidns={"nsmode": "path"}), "namespace"),
        (compat(NetworkMode="ns:/proc/1/ns/net"), "network"),
        # I4: libpod spellings of the SecurityOpt / devices / masked-paths rules
        (libpod(selinux_opts=["disable"]), "security-opt"),
        (libpod(apparmor_profile="unconfined"), "security-opt"),
        (libpod(seccomp_policy="unsafe"), "security-opt"),
        (libpod(seccomp_profile_path="/tmp/x.json"), "security-opt"),
        (libpod(unmask=["ALL"]), "security-opt"),
        (libpod(device_cgroup_rule=["c 1:3 rwm"]), "devices"),
        (libpod(mask=[]), "masked-paths"),
        # I5: SecurityOpt parsing - both separators, per-key allow-list
        (compat(SecurityOpt=["seccomp:unconfined"]), "security-opt"),
        (compat(SecurityOpt=["seccomp=/tmp/allow-all.json"]), "security-opt"),
        (compat(SecurityOpt=["label:disable"]), "security-opt"),
        (compat(SecurityOpt=["unmask=all"]), "security-opt"),
        # I6: PublishAllPorts sidesteps the loopback rewrite
        (compat(PublishAllPorts=True), "publish-all"),
        (libpod(publish_image_ports=True), "publish-all"),
        # M1: type guards never raise, they deny
        ({"Image": "alpine", "HostConfig": "x"}, "malformed"),
        (compat(Mounts=["x"]), "malformed"),
        (compat(Binds="not-a-list"), "malformed"),
        (compat(SecurityOpt="not-a-list"), "malformed"),
        (compat(CapAdd="not-a-list"), "malformed"),
        (libpod(cap_add="not-a-list"), "malformed"),
        # M2: a Binds source with a path separator is a path, checked and denied
        (compat(Binds=["a/../../../../etc:/etc"]), "bind-mount"),
        # M3: MaskedPaths / ReadonlyPaths - any explicit value is denied, not just empty
        (compat(MaskedPaths=["/proc/foo"]), "masked-paths"),
        (compat(ReadonlyPaths=["/proc/foo"]), "readonly-paths"),
        # C2: mount entries with absent or non-canonical Type skip the bind check
        (compat(Mounts=[{"Source": "/", "Target": "/h"}]), "mount-type"),
        (libpod(mounts=[{"source": "/etc", "destination": "/etc"}]), "mount-type"),
        (compat(Mounts=[{"Type": "devpts", "Source": "/dev/pts", "Target": "/dev/pts"}]), "mount-type"),
        # --- Fix round 2 additions below ---
        # R2: libpod bare-word netns modes escape the prefix list; exact allow-list now
        (libpod(netns={"nsmode": "container", "value": "deadbeef"}), "network"),
        (libpod(netns={"nsmode": "ns", "value": "/proc/1/ns/net"}), "network"),
        (libpod(netns={"nsmode": "from-container", "value": "deadbeef"}), "network"),
        (libpod(netns={"nsmode": "from-pod"}), "network"),
        # --- Fix round 3 additions below ---
        # S1: the `_nsmode` malformed sentinel was not fail-closed for the network rule
        (libpod(netns={"nsmode": "host", "extra": 1}), "network"),
        (libpod(netns={"nsmode": "container", "value": "x", "extra": 1}), "network"),
        (libpod(netns={"nsmode": "host", "Extra": 1}), "network"),
        (compat(NetworkMode="<malformed>"), "network"),
        # S2: `host`/`none` attached through the endpoint maps
        (compat_with_endpoints({"host": {}}), "network"),
        (compat_with_endpoints({"HOST": {}}), "network"),
        (compat_with_endpoints({"none": {}}), "network"),
        (libpod(networks={"host": {}}), "network"),
        (libpod(networks={"HOST": {}}), "network"),
        (libpod(networks={"none": {}}), "network"),
    ],
)
def test_denied_shapes(ctx: PolicyContext, body: dict[str, Any], rule: str) -> None:
    d = check_create(body, ctx, libpod="HostConfig" not in body)
    assert isinstance(d, Deny), body
    assert d.reason.startswith(rule), d.reason
    assert d.message.startswith("container-gateway: ")
    assert "sandbox-troubleshooting.md#docker--podman-command-fails-with-a-socket-error" in d.message


def test_bind_under_project_root_is_allowed(ctx: PolicyContext) -> None:
    src = ctx.project_root / "data"
    src.mkdir()
    assert check_create(compat(Binds=[f"{src}:/data"]), ctx, libpod=False) is None
    assert (
        check_create(compat(Mounts=[{"Type": "bind", "Source": str(src), "Target": "/d"}]), ctx, libpod=False)
        is None
    )
    assert (
        check_create(
            libpod(mounts=[{"type": "bind", "source": str(src), "destination": "/d"}]), ctx, libpod=True
        )
        is None
    )


def test_bind_symlink_escaping_root_is_denied(ctx: PolicyContext, tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    link = ctx.project_root / "escape"
    link.symlink_to(outside)
    d = check_create(compat(Binds=[f"{link}:/x"]), ctx, libpod=False)
    assert isinstance(d, Deny) and d.reason.startswith("bind-mount")


def test_tmpfs_and_capdrop_and_named_volume_pass(ctx: PolicyContext) -> None:
    body = compat(CapDrop=["ALL"], Tmpfs={"/run": "rw"}, Mounts=[{"Type": "tmpfs", "Target": "/t"}])
    assert check_create(body, ctx, libpod=False) is None
    # Named volumes are label-checked by the relay (needs the backend), not here.
    assert check_create(compat(Binds=["myvol:/data"]), ctx, libpod=False) is None


def test_rewrites_label_hostip_and_proxy(ctx: PolicyContext) -> None:
    body = compat(PortBindings={"80/tcp": [{"HostPort": "8080"}]})
    body["Env"] = ["FOO=1", "HTTP_PROXY=http://evil:1"]
    out = apply_create_rewrites(body, ctx, libpod=False)
    assert out["Labels"][LABEL_KEY] == "-proj"
    assert out["HostConfig"]["PortBindings"]["80/tcp"][0]["HostIp"] == "127.0.0.1"
    assert "HTTP_PROXY=http://host.containers.internal:8899" in out["Env"]
    assert "HTTP_PROXY=http://evil:1" not in out["Env"]
    assert "FOO=1" in out["Env"]
    assert body.get("Labels") is None, "input must not be mutated"


def test_rewrites_libpod_shape(ctx: PolicyContext) -> None:
    body = libpod(portmappings=[{"container_port": 80, "host_port": 8080}], env={"HTTP_PROXY": "x"})
    out = apply_create_rewrites(body, ctx, libpod=True)
    assert out["labels"][LABEL_KEY] == "-proj"
    assert out["portmappings"][0]["host_ip"] == "127.0.0.1"
    assert out["env"]["HTTP_PROXY"] == "http://host.containers.internal:8899"


def test_explicit_hostip_is_kept(ctx: PolicyContext) -> None:
    body = compat(PortBindings={"80/tcp": [{"HostIp": "0.0.0.0", "HostPort": "8080"}]})
    out = apply_create_rewrites(body, ctx, libpod=False)
    assert out["HostConfig"]["PortBindings"]["80/tcp"][0]["HostIp"] == "0.0.0.0"


def test_egress_require_without_proxy_denies(ctx: PolicyContext) -> None:
    strict = PolicyContext(ctx.slug, ctx.project_root, ctx.bind_roots, None, "require")
    d = check_create(compat(), strict, libpod=False)
    assert isinstance(d, Deny) and d.reason.startswith("egress-required")


def test_egress_off_injects_nothing(ctx: PolicyContext) -> None:
    off = PolicyContext(ctx.slug, ctx.project_root, ctx.bind_roots, None, "off")
    out = apply_create_rewrites(compat(), off, libpod=False)
    assert "Env" not in out or not any(e.startswith("HTTP_PROXY=") for e in out["Env"])


# --- Fix round 1 additions below ---


@pytest.mark.parametrize(
    ("body", "libpod"),
    [
        # C1: a case-variant top-level key hides the real HostConfig from _host()
        ({"Image": "alpine", "hostconfig": {"Privileged": True}}, False),
        # C1: a case-variant HostConfig key hides Privileged from the check
        (compat(PRIVILEGED=True), False),
        # C1: Labels/labels both present - the daemon could take either
        ({"Image": "alpine", "HostConfig": {}, "Labels": {"a": "b"}, "labels": {"a": "b"}}, False),
        # C1: Env/env both present (Env must be a list, env must be a dict - each
        # individually well-typed, so only the spelling collision denies this)
        ({"Image": "alpine", "HostConfig": {}, "Env": ["A=1"], "env": {"A": "1"}}, False),
        # C1: libpod duplicate labels
        ({"image": "alpine", "labels": {"a": "b"}, "Labels": {"a": "b"}}, True),
        # C1: libpod duplicate env (Env list / env dict, each individually well-typed)
        ({"image": "alpine", "env": {"A": "1"}, "Env": ["A=1"]}, True),
        # C1: libpod case-variant top-level key
        ({"image": "alpine", "Privileged": True}, True),
        # C1/C2: type and Type collide inside one Mounts entry
        (
            {
                "Image": "alpine",
                "HostConfig": {"Mounts": [{"type": None, "Type": "bind", "Source": "/", "Target": "/h"}]},
            },
            False,
        ),
        # R1: the six libpod namespace objects were outside the spelling check
        (libpod(pidns={"NSMode": "host"}), True),
        (libpod(userns={"NSMode": "host"}), True),
        (libpod(netns={"NSMode": "host"}), True),
        (libpod(pidns={"nsmode": "private", "Value": "x"}), True),
    ],
)
def test_canonical_spelling_violation_is_denied(
    ctx: PolicyContext, body: dict[str, Any], libpod: bool
) -> None:
    d = check_create(body, ctx, libpod=libpod)
    assert isinstance(d, Deny), body
    assert d.reason.startswith("ambiguous-field"), d.reason


def test_security_opt_allowed_values_pass(ctx: PolicyContext) -> None:
    assert check_create(compat(SecurityOpt=["apparmor=docker-default"]), ctx, libpod=False) is None
    assert check_create(compat(SecurityOpt=["no-new-privileges"]), ctx, libpod=False) is None


def test_named_network_is_allowed_and_deferred_to_relay(ctx: PolicyContext) -> None:
    # A named network is not one of the fixed keywords and does not start with
    # host / container / ns / path / from-, so check_create allows it; the
    # relay label-checks the network by name (Task 9).
    assert check_create(compat(NetworkMode="mynet"), ctx, libpod=False) is None
    assert named_networks(compat(NetworkMode="mynet"), False) == ["mynet"]
    assert named_networks(compat(NetworkMode="host"), False) == []
    assert named_networks(compat(NetworkMode="container:deadbeef"), False) == []
    assert check_create(libpod(netns={"nsmode": "bridge"}), ctx, libpod=True) is None
    assert named_networks(libpod(netns={"nsmode": "bridge"}), True) == []


def test_named_volumes_helper(ctx: PolicyContext) -> None:
    assert named_volumes(compat(Binds=["myvol:/data"]), False) == ["myvol"]
    assert named_volumes(compat(Mounts=[{"Type": "volume", "Source": "myvol2", "Target": "/d"}]), False) == [
        "myvol2"
    ]
    assert named_volumes(
        libpod(mounts=[{"type": "volume", "source": "myvol3", "destination": "/d"}]), True
    ) == ["myvol3"]
    # An anonymous volume has no name for the relay to label-check.
    assert named_volumes(compat(Mounts=[{"Type": "volume", "Target": "/d"}]), False) == []
    assert named_volumes(libpod(mounts=[{"type": "volume", "destination": "/d"}]), True) == []


def test_proxy_env_filtered_case_insensitively(ctx: PolicyContext) -> None:
    body = compat()
    body["Env"] = ["Http_Proxy=http://evil:1", "FOO=1"]
    out = apply_create_rewrites(body, ctx, libpod=False)
    assert "Http_Proxy=http://evil:1" not in out["Env"]
    assert "HTTP_PROXY=http://host.containers.internal:8899" in out["Env"]
    assert "FOO=1" in out["Env"]


# --- Fix round 2 additions below ---


def test_masked_and_readonly_paths_null_passes(ctx: PolicyContext) -> None:
    # moby's HostConfig serialises MaskedPaths/ReadonlyPaths: null on every
    # create (no omitempty); the gateway must not refuse an ordinary create.
    body = compat(MaskedPaths=None, ReadonlyPaths=None)
    assert check_create(body, ctx, libpod=False) is None


def test_mask_and_unmask_null_passes(ctx: PolicyContext) -> None:
    assert check_create(libpod(mask=None, unmask=None), ctx, libpod=True) is None


def test_named_volumes_includes_libpod_top_level_volumes(ctx: PolicyContext) -> None:
    body = libpod(volumes=[{"Name": "myvol4", "Dest": "/d"}])
    assert check_create(body, ctx, libpod=True) is None
    assert named_volumes(body, True) == ["myvol4"]


def test_named_networks_from_endpoints_config_and_libpod_networks(ctx: PolicyContext) -> None:
    compat_body = compat()
    compat_body["NetworkingConfig"] = {"EndpointsConfig": {"other-net": {}}}
    assert check_create(compat_body, ctx, libpod=False) is None
    assert named_networks(compat_body, False) == ["other-net"]

    libpod_body = libpod(networks={"n1": {}})
    assert check_create(libpod_body, ctx, libpod=True) is None
    assert named_networks(libpod_body, True) == ["n1"]


def test_named_networks_excludes_builtin_names(ctx: PolicyContext) -> None:
    compat_body = compat()
    compat_body["NetworkingConfig"] = {"EndpointsConfig": {"bridge": {}, "podman": {}}}
    assert named_networks(compat_body, False) == []
    assert named_networks(compat(NetworkMode="host"), False) == []
    assert named_networks(compat(NetworkMode="none"), False) == []


@pytest.mark.parametrize(
    ("body", "libpod"),
    [
        # R3: TypeError in policy_shape.py before _malformed_shape ran
        (compat(Mounts=5), False),
        (libpod(mounts=5), True),
        (libpod(portmappings=5), True),
        (compat(PortBindings={"80/tcp": 5}), False),
        # R3: type-guarded in one shape only - the "wrong" shape's spelling slipped through
        (libpod(SecurityOpt=5), True),
        (compat(selinux_opts=5), False),
        # R3: a non-dict body (AttributeError)
        ("not-a-dict", False),
        # R3: apply_create_rewrites crashes downstream if check_create does not catch these first
        (libpod(env=["A=1"]), True),
        ({"Image": "alpine", "Labels": ["a"], "HostConfig": {}}, False),
    ],
)
def test_malformed_bodies_never_raise(ctx: PolicyContext, body: Any, libpod: bool) -> None:
    result = check_create(body, ctx, libpod=libpod)
    assert isinstance(result, Deny), body


@pytest.mark.parametrize(
    ("body", "libpod"),
    [
        (compat(), False),
        (compat(CapDrop=["ALL"], Tmpfs={"/run": "rw"}, Mounts=[{"Type": "tmpfs", "Target": "/t"}]), False),
        (compat(Binds=["myvol:/data"]), False),
        (compat(SecurityOpt=["apparmor=docker-default"]), False),
        (compat(NetworkMode="mynet"), False),
        (libpod(netns={"nsmode": "bridge"}), True),
        (libpod(portmappings=[{"container_port": 80, "host_port": 8080}], env={"HTTP_PROXY": "x"}), True),
        # S3: `"HostConfig": null` is a request check_create allows (see
        # _malformed_shape) but the old `out.setdefault("HostConfig", {})`
        # left it as None and crashed on `.get()`.
        ({"Image": "alpine", "HostConfig": None}, False),
    ],
)
def test_apply_create_rewrites_succeeds_on_every_allowed_body(
    ctx: PolicyContext, body: dict[str, Any], libpod: bool
) -> None:
    assert check_create(body, ctx, libpod=libpod) is None
    apply_create_rewrites(body, ctx, libpod=libpod)  # must not raise


# --- Fix round 3 additions below ---


def test_ipcns_shareable_is_allowed(ctx: PolicyContext) -> None:
    # podman's containers.conf default for the IPC namespace: private with
    # opt-in sharing, not host - must not be denied.
    assert check_create(libpod(ipcns={"nsmode": "shareable"}), ctx, libpod=True) is None
    d = check_create(libpod(ipcns={"nsmode": "host"}), ctx, libpod=True)
    assert isinstance(d, Deny) and d.reason.startswith("namespace")


def test_endpoints_config_and_networks_still_allow_real_names(ctx: PolicyContext) -> None:
    # S2 must not regress the R6 "a real named network is allowed and
    # returned" behaviour while closing the host/none escape.
    assert check_create(compat_with_endpoints({"mynet": {}}), ctx, libpod=False) is None
    assert named_networks(compat_with_endpoints({"mynet": {}}), False) == ["mynet"]
    assert check_create(libpod(networks={"mynet": {}}), ctx, libpod=True) is None
    assert named_networks(libpod(networks={"mynet": {}}), True) == ["mynet"]


# --- Fix round 4 additions below (Task 6 addendum carry-overs) ---


def test_network_name_grammar_rejects_trailing_newline(ctx: PolicyContext) -> None:
    # `$` in a non-MULTILINE regex matches just before a trailing newline, so
    # `.match()` let "mynet\n" through; the grammar check must fullmatch.
    d = check_create(compat(NetworkMode="mynet\n"), ctx, libpod=False)
    assert isinstance(d, Deny) and d.reason.startswith("network")
    d2 = check_create(compat_with_endpoints({"mynet\n": {}}), ctx, libpod=False)
    assert isinstance(d2, Deny) and d2.reason.startswith("network")


def test_default_named_network_reaches_label_check(ctx: PolicyContext) -> None:
    # A user-created network literally named "default" is not the built-in
    # default network; it must reach the relay's label check like any other
    # named network, not be silently treated as always-reachable.
    body = compat_with_endpoints({"default": {}})
    assert check_create(body, ctx, libpod=False) is None
    assert named_networks(body, False) == ["default"]


def test_endpoint_map_checked_regardless_of_libpod_flag(ctx: PolicyContext) -> None:
    # The endpoint-map classifier must read both NetworkingConfig.EndpointsConfig
    # and libpod networks unconditionally, like every other rule in this module.
    libpod_body_with_compat_field = libpod(NetworkingConfig={"EndpointsConfig": {"host": {}}})
    d = check_create(libpod_body_with_compat_field, ctx, libpod=True)
    assert isinstance(d, Deny) and d.reason.startswith("network")

    compat_body_with_libpod_field = compat()
    compat_body_with_libpod_field["networks"] = {"host": {}}
    d2 = check_create(compat_body_with_libpod_field, ctx, libpod=False)
    assert isinstance(d2, Deny) and d2.reason.startswith("network")


def test_network_deny_wording_per_position(ctx: PolicyContext) -> None:
    network_mode = check_create(compat(NetworkMode="host"), ctx, libpod=False)
    assert isinstance(network_mode, Deny)
    assert network_mode.reason == "network: NetworkMode=host is refused"

    endpoint_key = check_create(compat_with_endpoints({"host": {}}), ctx, libpod=False)
    assert isinstance(endpoint_key, Deny)
    assert endpoint_key.reason == "network: network name host is refused"

    netns_object = check_create(libpod(netns={"nsmode": "host", "extra": 1}), ctx, libpod=True)
    assert isinstance(netns_object, Deny)
    assert netns_object.reason == "network: netns netns object has unexpected keys"


# --- Fix round 1 additions below (review findings round 1) ---


def test_named_networks_reads_both_endpoint_shapes_regardless_of_libpod_flag(ctx: PolicyContext) -> None:
    # I7: named_networks must read both NetworkingConfig.EndpointsConfig and
    # libpod networks unconditionally, like check_create's own classifier
    # (fix round 4, I3/S2) already does.
    compat_body_with_libpod_field = compat()
    compat_body_with_libpod_field["networks"] = {"mynet": {}}
    assert named_networks(compat_body_with_libpod_field, False) == ["mynet"]

    libpod_body_with_compat_field = libpod(NetworkingConfig={"EndpointsConfig": {"othernet": {}}})
    assert named_networks(libpod_body_with_compat_field, True) == ["othernet"]
