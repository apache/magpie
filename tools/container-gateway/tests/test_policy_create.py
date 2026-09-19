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
from container_gateway.policy import Deny, PolicyContext, apply_create_rewrites, check_create


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
