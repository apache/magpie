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

"""Tests for maven-artifact-verify.

Fixtures are synthetic POMs (string templates) and jars (zipfile
output) built at test time, so the repository carries no binary test
blobs.
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import maven_artifact_verify as mav

DISCLAIMER = (
    "Apache Foo is an effort undergoing incubation at The Apache Software "
    "Foundation (ASF), sponsored by the Apache Incubator. Incubation is "
    "required of all newly accepted projects until a further review "
    "indicates that the infrastructure, communications, and decision making "
    "process have stabilized in a manner consistent with other successful "
    "ASF projects. While incubation status is not necessarily a reflection "
    "of the completeness or stability of the code, it does indicate that "
    "the project has yet to be fully endorsed by the ASF."
)

DISCLAIMER_WIP = DISCLAIMER + (
    " Some of the incubating project's releases may not be fully compliant "
    "with ASF policy. For example, releases may have incomplete or "
    "un-reviewed licensing conditions."
)


def pom_xml(
    artifact_id: str = "foo-core",
    version: str = "1.0.0",
    packaging: str | None = None,
    licenses: str | None = None,
    developers: str | None = None,
    scm: str | None = None,
    description: str | None = None,
    parent: str | None = None,
    group_id: str = "org.apache.foo",
) -> str:
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<project xmlns="http://maven.apache.org/POM/4.0.0"'
        + ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
        + ' xsi:schemaLocation="http://maven.apache.org/POM/4.0.0'
        + ' http://maven.apache.org/xsd/maven-4.0.0.xsd">',
        "  <modelVersion>4.0.0</modelVersion>",
    ]
    if parent:
        parts.append(parent)
    parts.append(f"  <groupId>{group_id}</groupId>")
    parts.append(f"  <artifactId>{artifact_id}</artifactId>")
    if version:
        parts.append(f"  <version>{version}</version>")
    if packaging:
        parts.append(f"  <packaging>{packaging}</packaging>")
    if licenses:
        parts.append(licenses)
    if description:
        parts.append(f"  <description>{description}</description>")
    if developers:
        parts.append(developers)
    if scm:
        parts.append(scm)
    parts.append("</project>")
    return "\n".join(parts)


APACHE_LICENSES = (
    "  <licenses>"
    "    <license>"
    "      <name>Apache License, Version 2.0</name>"
    "      <url>https://www.apache.org/licenses/LICENSE-2.0.txt</url>"
    "    </license>"
    "  </licenses>"
)
MIT_LICENSES = "  <licenses>    <license><name>MIT License</name><url>https://opensource.org/licenses/MIT</url></license>  </licenses>"
DEVELOPERS = (
    "  <developers>"
    "    <developer><name>Apache Foo developers</name>"
    "      <organization>Apache Software Foundation</organization>"
    "    </developer>"
    "  </developers>"
)
SCM = "  <scm>    <connection>scm:git:https://gitbox.apache.org/repos/asf/foo.git</connection>    <url>https://github.com/apache/foo</url>  </scm>"
TAG_ONLY_SCM = "  <scm>    <tag>v1.0.0</tag>  </scm>"
EMPTY_SCM = "  <scm/>"
ASF_PARENT = "  <parent>    <groupId>org.apache</groupId>    <artifactId>apache</artifactId>    <version>33</version>  </parent>"
FOO_PARENT = "  <parent>    <groupId>org.apache.foo</groupId>    <artifactId>foo-parent</artifactId>    <version>1.0.0</version>  </parent>"


def write_pom(directory: Path, name: str, xml: str) -> Path:
    path = directory / name
    path.write_text(xml, encoding="utf-8", newline="")
    return path


def write_jar(directory: Path, name: str, entry: str = "org/apache/foo/Main.class") -> Path:
    path = directory / name
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(entry, b"class-bytes-here")
    return path


def write_checksum(jar_path: Path, digest: str) -> Path:
    """Write a checksum file holding the jar's real digest."""
    hasher = hashlib.new(digest)
    hasher.update(jar_path.read_bytes())
    path = jar_path.with_name(f"{jar_path.name}.{digest}")
    path.write_text(hasher.hexdigest() + "\n", encoding="utf-8")
    return path


def write_staged(
    directory: Path,
    artifact: str = "foo-core",
    version: str = "1.0.0",
    companions: bool = True,
    companion_signatures: bool = True,
    companion_digests: tuple[str, ...] = ("sha512",),
) -> None:
    """Write one main jar plus its signed, checksummed companions."""
    stem = f"{artifact}-{version}"
    write_jar(directory, f"{stem}.jar")
    if companions:
        for classifier in ("sources", "javadoc"):
            companion = write_jar(directory, f"{stem}-{classifier}.jar")
            if companion_signatures:
                (directory / f"{stem}-{classifier}.jar.asc").write_bytes(b"sig")
            for digest in companion_digests:
                write_checksum(companion, digest)


def mav_json(directory: Path, extra: tuple[str, ...]) -> str:
    import contextlib
    import io

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        mav.main([str(directory), *extra])
    return buffer.getvalue()


# --- full good set -------------------------------------------------------


def test_good_podling_set_passes(tmp_path: Path) -> None:
    write_pom(tmp_path, "foo-core-1.0.0.pom", pom_xml(licenses=APACHE_LICENSES, developers=DEVELOPERS, scm=SCM, description=DISCLAIMER))
    write_staged(tmp_path)
    report = json.loads(mav_json(tmp_path, ("--podling",)))
    assert report["status"] == "PASS"
    assert report["poms"][0]["check1"]["licenses"] == "PASS"
    assert report["poms"][0]["check2"]["disclaimer"] == "PASS"
    assert report["jars"] and all(c["classification"] == "PASS" for c in report["jars"][0]["companions"])


def test_top_level_project_without_podling_flag_passes(tmp_path: Path) -> None:
    write_pom(tmp_path, "foo-core-1.0.0.pom", pom_xml(licenses=APACHE_LICENSES, developers=DEVELOPERS, scm=SCM, description=None))
    write_staged(tmp_path)
    report = json.loads(mav_json(tmp_path, ()))
    assert report["status"] == "PASS"
    assert "check2" not in report["poms"][0]


# --- check 1: POM licence / developers / scm ------------------------------


def test_non_alv2_license_fails(tmp_path: Path) -> None:
    write_pom(tmp_path, "foo-core-1.0.0.pom", pom_xml(licenses=MIT_LICENSES, developers=DEVELOPERS, scm=SCM))
    report = json.loads(mav_json(tmp_path, ()))
    assert report["status"] == "FAIL"
    assert report["poms"][0]["check1"]["licenses"] == "FAIL"


def test_licence_name_variants_without_url_pass(tmp_path: Path) -> None:
    # The SPDX id and the legacy ASF wording identify ALv2 on their own;
    # without this, <name>Apache-2.0</name> with no <url> failed.
    for index, name in enumerate(("Apache-2.0", "The Apache Software License, Version 2.0")):
        directory = tmp_path / str(index)
        directory.mkdir()
        licenses = f"  <licenses>    <license><name>{name}</name></license>  </licenses>"
        write_pom(directory, "foo-core-1.0.0.pom", pom_xml(licenses=licenses, developers=DEVELOPERS, scm=SCM))
        report = json.loads(mav_json(directory, ()))
        assert report["status"] == "PASS", name
        assert report["poms"][0]["check1"]["licenses"] == "PASS", name


def test_inherited_licence_resolved_from_staged_parent(tmp_path: Path) -> None:
    write_pom(
        tmp_path,
        "apache-33.pom",
        pom_xml(artifact_id="apache", version="33", packaging="pom", group_id="org.apache", licenses=APACHE_LICENSES, developers=DEVELOPERS, scm=SCM),
    )
    write_pom(tmp_path, "foo-core-1.0.0.pom", pom_xml(parent=ASF_PARENT, developers=DEVELOPERS, scm=SCM))
    report = json.loads(mav_json(tmp_path, ()))
    assert report["status"] == "PASS"
    check1 = next(e["check1"] for e in report["poms"] if e["pom"] == "foo-core-1.0.0.pom")
    assert check1["licenses"] == "PASS"
    assert "inherited" in check1["licenses_detail"]


def test_inherited_licence_without_staged_parent_warns(tmp_path: Path) -> None:
    write_pom(tmp_path, "foo-core-1.0.0.pom", pom_xml(parent=ASF_PARENT, developers=DEVELOPERS, scm=SCM))
    report = json.loads(mav_json(tmp_path, ()))
    assert report["status"] == "WARN"
    assert report["poms"][0]["check1"]["licenses"] == "INHERITED-UNVERIFIED"


def test_staged_parent_with_non_alv2_licence_fails(tmp_path: Path) -> None:
    # Regression: a staged parent used to report a blind PASS without its
    # own <licenses> ever being read. A child of a staged parent that
    # declares MIT must fail the blocking check.
    write_pom(
        tmp_path,
        "foo-parent-1.0.0.pom",
        pom_xml(artifact_id="foo-parent", packaging="pom", licenses=MIT_LICENSES, developers=DEVELOPERS, scm=SCM),
    )
    write_pom(
        tmp_path,
        "foo-core-1.0.0.pom",
        pom_xml(
            parent="  <parent>    <groupId>org.apache.foo</groupId>    <artifactId>foo-parent</artifactId>    <version>1.0.0</version>  </parent>",
            developers=DEVELOPERS,
            scm=SCM,
        ),
    )
    report = json.loads(mav_json(tmp_path, ()))
    assert report["status"] == "FAIL"
    check1 = next(e["check1"] for e in report["poms"] if e["pom"] == "foo-core-1.0.0.pom")
    assert check1["licenses"] == "FAIL"
    assert "foo-parent" in check1["licenses_detail"]


def test_staged_parent_without_scm_fails(tmp_path: Path) -> None:
    # The staged parent declares no <scm> and has no parent of its own,
    # so nothing can supply the element: a hard FAIL, not a warning.
    write_pom(
        tmp_path,
        "foo-parent-1.0.0.pom",
        pom_xml(artifact_id="foo-parent", packaging="pom", licenses=APACHE_LICENSES, developers=DEVELOPERS),
    )
    write_pom(
        tmp_path,
        "foo-core-1.0.0.pom",
        pom_xml(
            parent="  <parent>    <groupId>org.apache.foo</groupId>    <artifactId>foo-parent</artifactId>    <version>1.0.0</version>  </parent>",
            developers=DEVELOPERS,
        ),
    )
    report = json.loads(mav_json(tmp_path, ()))
    assert report["status"] == "FAIL"
    check1 = next(e["check1"] for e in report["poms"] if e["pom"] == "foo-core-1.0.0.pom")
    assert check1["licenses"] == "PASS"  # resolved through the parent
    assert check1["scm"] == "FAIL"


def test_parentless_pom_with_missing_licence_fails(tmp_path: Path) -> None:
    # Regression: a POM with no <parent> at all used to get the
    # INHERITED-UNVERIFIED warning, but nothing can be inherited —
    # Maven Central rejects such a POM, so it is a hard FAIL.
    write_pom(tmp_path, "foo-core-1.0.0.pom", pom_xml(developers=DEVELOPERS, scm=SCM))
    report = json.loads(mav_json(tmp_path, ()))
    assert report["status"] == "FAIL"
    check1 = report["poms"][0]["check1"]
    assert check1["licenses"] == "FAIL"
    assert "no <parent>" in check1["licenses_detail"]


def test_licence_resolved_from_staged_grandparent(tmp_path: Path) -> None:
    # The ASF parent chain is two levels deep (project parent -> apache
    # parent); an element may only be declared at the grandparent.
    write_pom(
        tmp_path,
        "apache-33.pom",
        pom_xml(artifact_id="apache", version="33", packaging="pom", group_id="org.apache", licenses=APACHE_LICENSES, developers=DEVELOPERS, scm=SCM),
    )
    write_pom(
        tmp_path,
        "foo-parent-1.0.0.pom",
        pom_xml(
            artifact_id="foo-parent",
            packaging="pom",
            parent=ASF_PARENT,
            developers=DEVELOPERS,
            scm=SCM,
        ),
    )
    write_pom(
        tmp_path,
        "foo-core-1.0.0.pom",
        pom_xml(
            parent="  <parent>    <groupId>org.apache.foo</groupId>    <artifactId>foo-parent</artifactId>    <version>1.0.0</version>  </parent>",
            developers=DEVELOPERS,
            scm=SCM,
        ),
    )
    report = json.loads(mav_json(tmp_path, ()))
    assert report["status"] == "PASS"
    check1 = next(e["check1"] for e in report["poms"] if e["pom"] == "foo-core-1.0.0.pom")
    assert check1["licenses"] == "PASS"
    assert "org.apache:apache:33" in check1["licenses_detail"]


def test_parent_chain_cycle_fails_without_hanging(tmp_path: Path) -> None:
    # Two staged POMs naming each other as parent: the walk must stop
    # and never hang. A cyclic chain is a broken staged set (Maven
    # refuses to build it), so the elements that cannot be resolved
    # FAIL instead of warning.
    foo_parent = "  <parent>    <groupId>org.apache.foo</groupId>    <artifactId>foo-b</artifactId>    <version>1.0.0</version>  </parent>"
    bar_parent = "  <parent>    <groupId>org.apache.foo</groupId>    <artifactId>foo-a</artifactId>    <version>1.0.0</version>  </parent>"
    write_pom(tmp_path, "foo-a-1.0.0.pom", pom_xml(artifact_id="foo-a", parent=foo_parent, developers=DEVELOPERS, scm=SCM))
    write_pom(tmp_path, "foo-b-1.0.0.pom", pom_xml(artifact_id="foo-b", parent=bar_parent, developers=DEVELOPERS, scm=SCM))
    report = json.loads(mav_json(tmp_path, ()))
    assert report["status"] == "FAIL"
    check1 = next(e["check1"] for e in report["poms"] if e["pom"] == "foo-a-1.0.0.pom")
    assert check1["licenses"] == "FAIL"
    assert "cyclic" in check1["licenses_detail"]


def test_tag_only_scm_inherits_from_staged_parent(tmp_path: Path) -> None:
    # Regression: Maven merges <scm> per field, so a child declaring
    # only <tag> still inherits url/connection from its parent. Judging
    # the child's <scm> in isolation used to make this a hard FAIL.
    write_pom(
        tmp_path,
        "foo-parent-1.0.0.pom",
        pom_xml(artifact_id="foo-parent", packaging="pom", licenses=APACHE_LICENSES, developers=DEVELOPERS, scm=SCM),
    )
    write_pom(tmp_path, "foo-core-1.0.0.pom", pom_xml(parent=FOO_PARENT, licenses=APACHE_LICENSES, developers=DEVELOPERS, scm=TAG_ONLY_SCM))
    report = json.loads(mav_json(tmp_path, ()))
    assert report["status"] == "PASS"
    check1 = next(e["check1"] for e in report["poms"] if e["pom"] == "foo-core-1.0.0.pom")
    assert check1["scm"] == "PASS"
    assert "inherited" in check1["scm_detail"]


def test_tag_only_scm_with_unstaged_parent_warns(tmp_path: Path) -> None:
    # An unstaged parent may carry url/connection, so the child's
    # tag-only <scm> is INHERITED-UNVERIFIED, never a hard FAIL.
    write_pom(tmp_path, "foo-core-1.0.0.pom", pom_xml(parent=ASF_PARENT, licenses=APACHE_LICENSES, developers=DEVELOPERS, scm=TAG_ONLY_SCM))
    report = json.loads(mav_json(tmp_path, ()))
    assert report["status"] == "WARN"
    check1 = report["poms"][0]["check1"]
    assert check1["scm"] == "INHERITED-UNVERIFIED"
    assert "not fully staged" in check1["scm_detail"]


def test_scm_without_url_anywhere_in_complete_chain_fails(tmp_path: Path) -> None:
    # The staged parent declares a tag-only <scm> too and has no parent
    # of its own: nothing in the chain supplies url or connection —
    # a hard FAIL, the POM Maven Central would reject.
    write_pom(
        tmp_path,
        "foo-parent-1.0.0.pom",
        pom_xml(artifact_id="foo-parent", packaging="pom", licenses=APACHE_LICENSES, developers=DEVELOPERS, scm=TAG_ONLY_SCM),
    )
    write_pom(tmp_path, "foo-core-1.0.0.pom", pom_xml(parent=FOO_PARENT, licenses=APACHE_LICENSES, developers=DEVELOPERS, scm=TAG_ONLY_SCM))
    report = json.loads(mav_json(tmp_path, ()))
    assert report["status"] == "FAIL"
    check1 = next(e["check1"] for e in report["poms"] if e["pom"] == "foo-core-1.0.0.pom")
    assert check1["scm"] == "FAIL"
    assert "no parent POM in the staged chain" in check1["scm_detail"]


def test_empty_child_scm_resolves_from_staged_grandparent(tmp_path: Path) -> None:
    # Empty and tag-only declarations don't win: the per-field walk
    # continues past them to the grandparent that declares url.
    write_pom(
        tmp_path,
        "apache-33.pom",
        pom_xml(artifact_id="apache", version="33", packaging="pom", group_id="org.apache", licenses=APACHE_LICENSES, developers=DEVELOPERS, scm=SCM),
    )
    write_pom(tmp_path, "foo-parent-1.0.0.pom", pom_xml(artifact_id="foo-parent", packaging="pom", parent=ASF_PARENT, developers=DEVELOPERS, scm=TAG_ONLY_SCM))
    write_pom(tmp_path, "foo-core-1.0.0.pom", pom_xml(parent=FOO_PARENT, licenses=APACHE_LICENSES, developers=DEVELOPERS, scm=EMPTY_SCM))
    report = json.loads(mav_json(tmp_path, ()))
    assert report["status"] == "PASS"
    check1 = next(e["check1"] for e in report["poms"] if e["pom"] == "foo-core-1.0.0.pom")
    assert check1["scm"] == "PASS"
    assert "org.apache:apache:33" in check1["scm_detail"]


def test_empty_scm_element_fails(tmp_path: Path) -> None:
    # No <parent> at all, so the empty <scm> cannot inherit url or
    # connection from anywhere: a hard FAIL.
    write_pom(tmp_path, "foo-core-1.0.0.pom", pom_xml(licenses=APACHE_LICENSES, developers=DEVELOPERS, scm=EMPTY_SCM))
    report = json.loads(mav_json(tmp_path, ()))
    assert report["status"] == "FAIL"
    assert report["poms"][0]["check1"]["scm"] == "FAIL"


def test_malformed_pom_fails(tmp_path: Path) -> None:
    (tmp_path / "broken-1.0.0.pom").write_text("<project><unclosed>", encoding="utf-8")
    report = json.loads(mav_json(tmp_path, ()))
    assert report["status"] == "FAIL"


# --- check 2: podling disclaimer ------------------------------------------


def test_podling_without_description_fails(tmp_path: Path) -> None:
    write_pom(tmp_path, "foo-core-1.0.0.pom", pom_xml(licenses=APACHE_LICENSES, developers=DEVELOPERS, scm=SCM))
    write_staged(tmp_path)
    report = json.loads(mav_json(tmp_path, ("--podling",)))
    assert report["status"] == "FAIL"
    assert report["poms"][0]["check2"]["disclaimer"] == "FAIL"


def test_podling_inherited_description_without_staged_parent_warns(tmp_path: Path) -> None:
    # <description> may be inherited from the project parent POM; when
    # that parent is not staged the effective POM cannot be resolved
    # offline, so the result is a warning, never a failure.
    write_pom(
        tmp_path,
        "foo-core-1.0.0.pom",
        pom_xml(parent=ASF_PARENT, licenses=APACHE_LICENSES, developers=DEVELOPERS, scm=SCM),
    )
    write_staged(tmp_path)
    report = json.loads(mav_json(tmp_path, ("--podling",)))
    assert report["status"] == "WARN"
    assert report["poms"][0]["check2"]["disclaimer"] == "INHERITED-UNVERIFIED"


def test_podling_cycle_fails_disclaimer_without_hanging(tmp_path: Path) -> None:
    # The same cycle rule under check 2: a cyclic chain is a broken
    # staged set, so the unresolved <description> is a FAIL, not a
    # warning.
    foo_parent = "  <parent>    <groupId>org.apache.foo</groupId>    <artifactId>foo-b</artifactId>    <version>1.0.0</version>  </parent>"
    bar_parent = "  <parent>    <groupId>org.apache.foo</groupId>    <artifactId>foo-a</artifactId>    <version>1.0.0</version>  </parent>"
    write_pom(tmp_path, "foo-a-1.0.0.pom", pom_xml(artifact_id="foo-a", parent=foo_parent, developers=DEVELOPERS, scm=SCM))
    write_pom(tmp_path, "foo-b-1.0.0.pom", pom_xml(artifact_id="foo-b", parent=bar_parent, developers=DEVELOPERS, scm=SCM))
    report = json.loads(mav_json(tmp_path, ("--podling",)))
    assert report["status"] == "FAIL"
    check2 = next(e["check2"] for e in report["poms"] if e["pom"] == "foo-a-1.0.0.pom")
    assert check2["disclaimer"] == "FAIL"
    assert "cyclic" in check2["disclaimer_detail"]


def test_podling_inherited_description_without_disclaimer_fails(tmp_path: Path) -> None:
    # A resolvable parent whose description lacks the disclaimer stays
    # a FAIL: the effective POM verifiably does not carry it.
    write_pom(tmp_path, "foo-parent-1.0.0.pom", pom_xml(artifact_id="foo-parent", packaging="pom", description="Just a parent."))
    write_pom(
        tmp_path,
        "foo-core-1.0.0.pom",
        pom_xml(
            parent=("  <parent>    <groupId>org.apache.foo</groupId>    <artifactId>foo-parent</artifactId>    <version>1.0.0</version>  </parent>"),
            licenses=APACHE_LICENSES,
            developers=DEVELOPERS,
            scm=SCM,
        ),
    )
    report = json.loads(mav_json(tmp_path, ("--podling",)))
    assert report["status"] == "FAIL"
    check2 = next(e["check2"] for e in report["poms"] if e["pom"] == "foo-core-1.0.0.pom")
    assert check2["disclaimer"] == "FAIL"


def test_podling_disclaimer_without_podling_flag_not_checked(tmp_path: Path) -> None:
    write_pom(
        tmp_path,
        "foo-core-1.0.0.pom",
        pom_xml(licenses=APACHE_LICENSES, developers=DEVELOPERS, scm=SCM, description="A plain description without the disclaimer."),
    )
    write_staged(tmp_path)
    report = json.loads(mav_json(tmp_path, ()))
    assert report["status"] == "PASS"


def test_whitespace_wrapped_disclaimer_passes(tmp_path: Path) -> None:
    wrapped = DISCLAIMER.replace(". ", ".\n    ")
    write_pom(tmp_path, "foo-core-1.0.0.pom", pom_xml(licenses=APACHE_LICENSES, developers=DEVELOPERS, scm=SCM, description=wrapped))
    write_staged(tmp_path)
    report = json.loads(mav_json(tmp_path, ("--podling",)))
    assert report["status"] == "PASS"


def test_wip_variant_passes(tmp_path: Path) -> None:
    write_pom(tmp_path, "foo-core-1.0.0.pom", pom_xml(licenses=APACHE_LICENSES, developers=DEVELOPERS, scm=SCM, description=DISCLAIMER_WIP))
    write_staged(tmp_path)
    report = json.loads(mav_json(tmp_path, ("--podling",)))
    assert report["status"] == "PASS"


def test_non_disclaimer_description_fails_for_podling(tmp_path: Path) -> None:
    write_pom(tmp_path, "foo-core-1.0.0.pom", pom_xml(licenses=APACHE_LICENSES, developers=DEVELOPERS, scm=SCM, description="Foo is a fast thing."))
    report = json.loads(mav_json(tmp_path, ("--podling",)))
    assert report["status"] == "FAIL"


# --- check 3: companion jars ----------------------------------------------


def test_missing_companion_fails(tmp_path: Path) -> None:
    write_pom(tmp_path, "foo-core-1.0.0.pom", pom_xml(licenses=APACHE_LICENSES, developers=DEVELOPERS, scm=SCM))
    write_staged(tmp_path, companions=False)
    report = json.loads(mav_json(tmp_path, ()))
    assert report["status"] == "FAIL"
    classes = [c["classification"] for c in report["jars"][0]["companions"]]
    assert classes.count("FAIL") == 2


def test_companion_missing_signature_fails(tmp_path: Path) -> None:
    write_pom(tmp_path, "foo-core-1.0.0.pom", pom_xml(licenses=APACHE_LICENSES, developers=DEVELOPERS, scm=SCM))
    write_staged(tmp_path, companion_signatures=False)
    report = json.loads(mav_json(tmp_path, ()))
    assert report["status"] == "FAIL"
    fails = [c for c in report["jars"][0]["companions"] if c["classification"] == "FAIL"]
    assert len(fails) == 2  # one .asc missing per companion
    assert all(".asc" in c["detail"] for c in fails)
    # a companion with a missing file must not also carry a PASS record
    # (regression: a loop-else used to append PASS unconditionally)
    companions = {c["companion"] for c in report["jars"][0]["companions"]}
    for name in companions:
        classifications = [c["classification"] for c in report["jars"][0]["companions"] if c["companion"] == name]
        assert classifications == ["FAIL"], f"{name}: {classifications}"


def test_companion_missing_digest_fails(tmp_path: Path) -> None:
    write_pom(tmp_path, "foo-core-1.0.0.pom", pom_xml(licenses=APACHE_LICENSES, developers=DEVELOPERS, scm=SCM))
    write_staged(tmp_path)
    (tmp_path / "foo-core-1.0.0-sources.jar.sha512").unlink()
    report = json.loads(mav_json(tmp_path, ()))
    assert report["status"] == "FAIL"
    fails = [c for c in report["jars"][0]["companions"] if c["classification"] == "FAIL"]
    assert len(fails) == 1 and "sha512" in fails[0]["detail"]


def test_sha256_digest_set(tmp_path: Path) -> None:
    write_pom(tmp_path, "foo-core-1.0.0.pom", pom_xml(licenses=APACHE_LICENSES, developers=DEVELOPERS, scm=SCM))
    write_staged(tmp_path, companion_digests=("sha512", "sha256"))
    report = json.loads(mav_json(tmp_path, ("--digests", "sha512,sha256")))
    assert report["status"] == "PASS"


def test_checksum_mismatch_fails(tmp_path: Path) -> None:
    # Regression: the checksum file used to be an existence check only —
    # any bytes passed. A recorded digest that does not match the
    # companion jar's actual bytes must fail.
    write_pom(tmp_path, "foo-core-1.0.0.pom", pom_xml(licenses=APACHE_LICENSES, developers=DEVELOPERS, scm=SCM))
    write_staged(tmp_path)
    (tmp_path / "foo-core-1.0.0-sources.jar.sha512").write_text("0" * 128 + "\n", encoding="utf-8")
    report = json.loads(mav_json(tmp_path, ()))
    assert report["status"] == "FAIL"
    fails = [c for c in report["jars"][0]["companions"] if c["classification"] == "FAIL"]
    assert len(fails) == 1 and "checksum mismatch" in fails[0]["detail"]


def test_checksum_file_with_gnu_coreutils_line_passes(tmp_path: Path) -> None:
    # The GNU coreutils layout "<digest>  <filename>".
    write_pom(tmp_path, "foo-core-1.0.0.pom", pom_xml(licenses=APACHE_LICENSES, developers=DEVELOPERS, scm=SCM))
    write_staged(tmp_path)
    companion = tmp_path / "foo-core-1.0.0-sources.jar"
    hasher = hashlib.sha512()
    hasher.update(companion.read_bytes())
    (tmp_path / "foo-core-1.0.0-sources.jar.sha512").write_text(f"{hasher.hexdigest()}  {companion.name}\n", encoding="utf-8")
    report = json.loads(mav_json(tmp_path, ()))
    assert report["status"] == "PASS"


def test_checksum_file_with_bsd_tagged_line_passes(tmp_path: Path) -> None:
    # The real BSD/tagged layout "ALGO (filename) = <digest>" as written
    # by `shasum --tag` used to report a false checksum mismatch.
    write_pom(tmp_path, "foo-core-1.0.0.pom", pom_xml(licenses=APACHE_LICENSES, developers=DEVELOPERS, scm=SCM))
    write_staged(tmp_path)
    companion = tmp_path / "foo-core-1.0.0-sources.jar"
    hasher = hashlib.sha512()
    hasher.update(companion.read_bytes())
    (tmp_path / "foo-core-1.0.0-sources.jar.sha512").write_text(f"SHA512 ({companion.name}) = {hasher.hexdigest()}\n", encoding="utf-8")
    report = json.loads(mav_json(tmp_path, ()))
    assert report["status"] == "PASS"


def test_checksum_file_with_gpg_print_md_line_passes(tmp_path: Path) -> None:
    # `gpg --print-md` writes "<filename>: <DIGEST>" in upper case, and
    # some ASF projects still publish that layout.
    write_pom(tmp_path, "foo-core-1.0.0.pom", pom_xml(licenses=APACHE_LICENSES, developers=DEVELOPERS, scm=SCM))
    write_staged(tmp_path)
    companion = tmp_path / "foo-core-1.0.0-sources.jar"
    hasher = hashlib.sha512()
    hasher.update(companion.read_bytes())
    (tmp_path / "foo-core-1.0.0-sources.jar.sha512").write_text(f"{companion.name}: {hasher.hexdigest().upper()}\n", encoding="utf-8")
    report = json.loads(mav_json(tmp_path, ()))
    assert report["status"] == "PASS"


def test_checksum_file_with_wrong_digest_still_fails(tmp_path: Path) -> None:
    # Lenient extraction must not start accepting any 128-hex-char
    # looking string: a recorded digest that does not match the bytes
    # stays a FAIL.
    write_pom(tmp_path, "foo-core-1.0.0.pom", pom_xml(licenses=APACHE_LICENSES, developers=DEVELOPERS, scm=SCM))
    write_staged(tmp_path)
    (tmp_path / "foo-core-1.0.0-sources.jar.sha512").write_text("SHA512 (foo-core-1.0.0-sources.jar) = " + "0" * 128 + "\n", encoding="utf-8")
    report = json.loads(mav_json(tmp_path, ()))
    assert report["status"] == "FAIL"
    assert any("checksum mismatch" in str(c.get("detail")) for e in report["jars"] for c in e["companions"])


def test_unknown_digest_algorithm_is_presence_only(tmp_path: Path) -> None:
    # An algorithm this Python's hashlib does not provide cannot be
    # checked offline: the file is still required, but the tool must say
    # plainly that it verified presence only, never a fake PASS.
    write_pom(tmp_path, "foo-core-1.0.0.pom", pom_xml(licenses=APACHE_LICENSES, developers=DEVELOPERS, scm=SCM))
    write_staged(tmp_path)
    (tmp_path / "foo-core-1.0.0-sources.jar.sha999").write_bytes(b"hash")
    (tmp_path / "foo-core-1.0.0-javadoc.jar.sha999").write_bytes(b"hash")
    report = json.loads(mav_json(tmp_path, ("--digests", "sha999")))
    assert report["status"] == "PASS"
    assert any("not verified" in f for f in report["findings"])


def test_maven_repository_layout_is_verified(tmp_path: Path) -> None:
    # Regression: a top-level-only scan misreported a staging directory
    # in Maven-repository layout as a non-JVM artefact set and skipped.
    nested = tmp_path / "org" / "apache" / "foo" / "foo-core" / "1.0.0"
    nested.mkdir(parents=True)
    write_pom(nested, "foo-core-1.0.0.pom", pom_xml(licenses=APACHE_LICENSES, developers=DEVELOPERS, scm=SCM))
    write_staged(nested)
    report = json.loads(mav_json(tmp_path, ()))
    assert report["status"] == "PASS"
    assert report["poms"][0]["pom"] == "foo-core-1.0.0.pom"
    assert all(c["classification"] == "PASS" for c in report["jars"][0]["companions"])


def test_main_jar_absent_is_an_observation_not_a_failure(tmp_path: Path) -> None:
    # The common ASF workflow publishes jars via the Nexus staging
    # repository and stages only the POM locally — absence of the main
    # jar must not fail the local check set.
    write_pom(tmp_path, "foo-core-1.0.0.pom", pom_xml(licenses=APACHE_LICENSES, developers=DEVELOPERS, scm=SCM))
    report = json.loads(mav_json(tmp_path, ()))
    assert report["status"] == "PASS"
    assert report["jars"][0]["companions"][0]["classification"] == "ABSENT"
    assert any("not staged locally" in f for f in report["findings"])


def test_invalid_coordinates_are_rejected_before_path_build(tmp_path: Path) -> None:
    # artifactId/version go straight into a path when the main jar is
    # located; a POM with <artifactId>../../evil</artifactId> must not
    # make the tool stat or hash files outside the staging directory.
    staged = tmp_path / "staged"
    staged.mkdir()
    outside = tmp_path / "evil-1.0.0.jar"
    outside.write_bytes(b"outside the staging directory")
    write_pom(staged, "foo-core-1.0.0.pom", pom_xml(artifact_id="../../evil", licenses=APACHE_LICENSES, developers=DEVELOPERS, scm=SCM))
    report = json.loads(mav_json(staged, ()))
    assert report["status"] == "PASS"  # checks 1-2 still ran; the jar checks are what is skipped
    assert any("not a valid Maven coordinate" in f for f in report["findings"])
    assert not any(entry["jar"].startswith("evil") for entry in report["jars"])
    assert outside.read_bytes() == b"outside the staging directory"


def test_pom_packaging_exempt_from_companions(tmp_path: Path) -> None:
    write_pom(tmp_path, "foo-parent-1.0.0.pom", pom_xml(artifact_id="foo-parent", packaging="pom", licenses=APACHE_LICENSES, developers=DEVELOPERS, scm=SCM))
    report = json.loads(mav_json(tmp_path, ()))
    assert report["status"] == "PASS"
    assert report["jars"] == []


def test_classified_jar_is_unmatched_never_failed(tmp_path: Path) -> None:
    write_pom(tmp_path, "foo-core-1.0.0.pom", pom_xml(licenses=APACHE_LICENSES, developers=DEVELOPERS, scm=SCM))
    write_staged(tmp_path)
    write_jar(tmp_path, "foo-core-1.0.0-tests.jar")
    write_jar(tmp_path, "foo-core-1.0.0-linux-x86_64.jar")
    report = json.loads(mav_json(tmp_path, ()))
    assert report["status"] == "PASS"
    assert set(report["unmatched_jars"]) == {"foo-core-1.0.0-tests.jar", "foo-core-1.0.0-linux-x86_64.jar"}


def test_jars_without_poms_warn(tmp_path: Path) -> None:
    # Jars present but no POM staged at all: the companions are skipped
    # (no POM-declared main) and the main jar itself is unmatched — an
    # observation, not a failure, but the report must say the POM
    # checks could not run.
    write_jar(tmp_path, "foo-core-1.0.0.jar")
    write_jar(tmp_path, "foo-core-1.0.0-sources.jar")
    report = json.loads(mav_json(tmp_path, ()))
    assert report["status"] == "WARN"
    assert "foo-core-1.0.0.jar" in report["unmatched_jars"]
    assert any("no .pom" in f for f in report["findings"])


# --- aggregation -----------------------------------------------------------


def test_no_jvm_artefacts_skips(tmp_path: Path) -> None:
    (tmp_path / "apache-foo-1.0.0-src.tar.gz").write_bytes(b"not a jar")
    report = json.loads(mav_json(tmp_path, ("--podling",)))
    assert report["status"] == "SKIP"


def test_missing_directory_fails(tmp_path: Path) -> None:
    import contextlib
    import io

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = mav.main([str(tmp_path / "nope")])
    report = json.loads(buffer.getvalue())
    assert code == 2
    assert report["status"] == "FAIL"
