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
        ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
        ' xsi:schemaLocation="http://maven.apache.org/POM/4.0.0'
        ' http://maven.apache.org/xsd/maven-4.0.0.xsd">',
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
EMPTY_SCM = "  <scm/>"
ASF_PARENT = "  <parent>    <groupId>org.apache</groupId>    <artifactId>apache</artifactId>    <version>33</version>  </parent>"


def write_pom(directory: Path, name: str, xml: str) -> Path:
    path = directory / name
    path.write_text(xml, encoding="utf-8", newline="")
    return path


def write_jar(directory: Path, name: str, entry: str = "org/apache/foo/Main.class") -> Path:
    path = directory / name
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(entry, b"class-bytes-here")
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
            write_jar(directory, f"{stem}-{classifier}.jar")
            if companion_signatures:
                (directory / f"{stem}-{classifier}.jar.asc").write_bytes(b"sig")
            for digest in companion_digests:
                (directory / f"{stem}-{classifier}.jar.{digest}").write_bytes(b"hash")


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


def test_empty_scm_element_fails(tmp_path: Path) -> None:
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


def test_main_jar_absent_is_an_observation_not_a_failure(tmp_path: Path) -> None:
    # The common ASF workflow publishes jars via the Nexus staging
    # repository and stages only the POM locally — absence of the main
    # jar must not fail the local check set.
    write_pom(tmp_path, "foo-core-1.0.0.pom", pom_xml(licenses=APACHE_LICENSES, developers=DEVELOPERS, scm=SCM))
    report = json.loads(mav_json(tmp_path, ()))
    assert report["status"] == "PASS"
    assert report["jars"][0]["companions"][0]["classification"] == "ABSENT"
    assert any("not staged locally" in f for f in report["findings"])


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
