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

"""Verify locally staged JVM release-candidate artefacts.

Implements the blocking checks 1-3 of apache/magpie issue #1173
(`release-verify-rc: validate rc jars`), local artefacts only:

1. **POM licence entry** - every staged ``.pom`` must declare the
   ALv2 licence, ``<developers>`` and ``<scm>``. An element absent
   from the POM itself is resolved against the chain of locally
   staged parent POMs: the first ancestor declaring the element
   decides PASS or FAIL. When the staged chain proves that nothing
   could supply the element - including a POM with no ``<parent>``
   at all - the result is a failure, the same judgement Maven
   Central applies. When the chain cannot be fully resolved offline
   the result is ``inherited-unverified`` (a warning, never a
   failure - the correct POM must not be failed, per the issue's
   boundary conditions).
2. **Incubator disclaimer in ``<description>``** - podlings only,
   enabled by ``--podling``. Accepts the standard disclaimer and the
   ``DISCLAIMER-WIP`` variant; matching tolerates whitespace and
   line-wrapping differences. An absent description resolves against
   the locally staged parent chain the same way: a failure when the
   effective description verifiably lacks the disclaimer, a failure
   when nothing could supply it, ``INHERITED-UNVERIFIED`` (a
   warning) when the chain is not fully staged.
3. **Companion jars** - for every staged main jar, the
   ``-sources.jar`` and ``-javadoc.jar`` companions must exist and
   each must carry its own ``.asc`` signature and checksum files.
   Checksum files are verified against the companion jar's actual
   bytes (``hashlib``, still offline); ``.asc`` signatures are
   presence-only here - verifying a signature needs GPG and the
   release key, which `release-verify-rc` Step 2 does.
   ``packaging=pom`` modules are exempt (no jar), classified jars
   (``-tests``, ``-shaded``, ...) are neither mains nor companions.

The tool is stdlib-only and fully offline: it reads the staged
directory, never the network. Nexus staging-repository checks are out
of scope here (issue #1173, PR 2).

Output is a single JSON document on stdout, in the shape
`release-verify-rc` Step 6b consumes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

MAVEN_NS = "http://maven.apache.org/POM/4.0.0"

# The distinctive core shared by the standard incubation disclaimer and
# the DISCLAIMER-WIP variant (https://incubator.apache.org/policy/incubation.html#disclaimers).
# Matching this core (case-insensitively, whitespace-normalised) accepts
# either text and tolerates wrapping inside the XML element.
DISCLAIMER_CORE = [
    "is an effort undergoing incubation at the apache software foundation",
    "has yet to be fully endorsed by the asf",
]

# The licence <name> may carry the canonical ASF wording, the legacy
# "The Apache Software License, Version 2.0" phrasing, or the SPDX id
# "Apache-2.0" — all three identify ALv2.
APACHE_LICENSE_NAME_RE = re.compile(r"apache(?:\s+software)?\s+license.*2\.0|apache\s*-\s*2\.0", re.IGNORECASE)
APACHE_LICENSE_URL_RE = re.compile(r"apache\.org/licenses/LICENSE-2\.0", re.IGNORECASE)

# Classifiers that mark a jar as a companion of another artefact rather
# than a main artefact. Anything else (-tests, -shaded, -linux-x86_64,
# ...) is neither a main nor a companion: it is reported as unmatched.
COMPANION_CLASSIFIERS = ("sources", "javadoc")

# A Maven version segment as it appears in filenames:
# <artifactId>-<version>[-<classifier>].jar, where the version starts
# with a digit and may carry a qualifier (rc1, alpha, SNAPSHOT, ...).
VERSION_SPLIT_RE = re.compile(
    r"^(?P<stem>.+?)-(?P<version>\d[\w.]*(?:-[A-Za-z]+)*)"
    r"(?:-(?P<classifier>[a-zA-Z][\w-]*))?$"
)

# Maven coordinates as they may appear in <artifactId>/<version>: the
# characters Central accepts. Coordinates go straight into paths when
# the main jar is located, so anything else (e.g. "../..") is rejected
# before the filesystem is touched.
MAVEN_COORDINATE_RE = re.compile(r"[A-Za-z0-9_.-]+")


def _local(tag: str) -> str:
    """Strip the Maven XML namespace from an ElementTree tag."""
    return tag.rsplit("}", 1)[-1]


def _find_child(elem: ET.Element | None, name: str) -> ET.Element | None:
    if elem is None:
        return None
    for child in elem:
        if _local(child.tag) == name:
            return child
    return None


def _find_children(elem: ET.Element | None, name: str) -> list[ET.Element]:
    if elem is None:
        return []
    return [child for child in elem if _local(child.tag) == name]


def _text(elem: ET.Element | None) -> str | None:
    if elem is None or elem.text is None:
        return None
    value = elem.text.strip()
    return value or None


def _normalize_ws(text: str) -> str:
    return " ".join(text.split()).lower()


def parse_pom(path: Path) -> dict:
    """Parse one POM into a plain dict of the fields the checks need."""
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        return {"path": path, "error": f"XML parse error: {exc}"}

    parent = _find_child(root, "parent")
    return {
        "path": path,
        "group_id": _text(_find_child(root, "groupId")) or (_text(_find_child(parent, "groupId")) if parent is not None else None),
        "artifact_id": _text(_find_child(root, "artifactId")),
        "version": _text(_find_child(root, "version")) or (_text(_find_child(parent, "version")) if parent is not None else None),
        "packaging": (_text(_find_child(root, "packaging")) or "jar"),
        "parent": (
            parent is not None and (_text(_find_child(parent, "groupId")), _text(_find_child(parent, "artifactId")), _text(_find_child(parent, "version")))
        )
        or None,
        "licenses": _find_children(_find_child(root, "licenses"), "license"),
        "developers": _find_children(_find_child(root, "developers"), "developer"),
        "scm": _find_child(root, "scm"),
        "description": _text(_find_child(root, "description")),
        "description_present": _find_child(root, "description") is not None,
    }


def _has_apache_license(licenses: list[ET.Element]) -> bool:
    for lic in licenses:
        name = _text(_find_child(lic, "name")) or ""
        url = _text(_find_child(lic, "url")) or ""
        if APACHE_LICENSE_NAME_RE.search(name) or APACHE_LICENSE_URL_RE.search(url):
            return True
    return False


def _pom_label(pom: dict) -> str:
    """Human-readable GAV coordinate for report details."""
    return ":".join(str(pom.get(key) or "?") for key in ("group_id", "artifact_id", "version"))


def _element_present(pom: dict, key: str) -> bool:
    # lists (licenses/developers): present when non-empty. <scm> is not
    # judged here: Maven merges it per field, see _check_scm.
    value = pom.get(key)
    return bool(value) if isinstance(value, list) else value is not None


def _evaluate_element(pom: dict, key: str) -> tuple[bool, str | None]:
    """Judge one POM's own declaration of ``key``.

    The same judgement whether the element is declared by the POM
    itself or inherited from a staged ancestor.
    """
    if key == "licenses":
        if _has_apache_license(pom["licenses"]):
            return True, None
        return False, (
            "licences declared but none is ALv2 (expected name matching 'Apache License, Version 2.0' or url containing apache.org/licenses/LICENSE-2.0)"
        )
    if pom["developers"]:
        return True, None
    return False, "<developers> declared but empty"


def _scm_field(pom: dict, field: str) -> str | None:
    """One ``<scm>`` field, or None when this POM declares no non-empty value."""
    scm = pom.get("scm")
    if scm is None:
        return None
    return _text(_find_child(scm, field))


def _check_scm(pom: dict, chain: list[dict], chain_reason: str) -> dict:
    """Check 1, the ``<scm>`` part - resolved per field along the chain.

    Maven merges ``<scm>`` per field: a child declaring only
    ``<scm><tag>`` still inherits ``url`` / ``connection`` from an
    ancestor, so a local ``<scm>`` is never judged in isolation. For
    each field, the nearest POM in the staged chain declaring it
    non-emptily wins (empty declarations are skipped, the walk
    continues). Either field resolvable — from the POM itself or
    inherited — is a PASS; neither field resolvable anywhere in a
    complete chain is a hard FAIL, and so is a cyclic chain (Maven
    refuses to build one); an unstaged chain reports
    ``INHERITED-UNVERIFIED``.
    """
    source: dict[str, tuple[int, str]] = {}
    for field in ("url", "connection"):
        for index, chain_pom in enumerate(chain):
            if _scm_field(chain_pom, field) is not None:
                source[field] = (index, _pom_label(chain_pom))
                break

    if source:
        inherited: dict[str, list[str]] = {}
        for field, (index, label) in source.items():
            if index > 0:
                inherited.setdefault(label, []).append(field)
        if inherited:
            detail = "; ".join(f"{', '.join(fields)} inherited from locally staged parent POM {label}" for label, fields in inherited.items())
            return {"scm": "PASS", "scm_detail": detail}
        return {"scm": "PASS"}

    if chain_reason == "cycle":
        return {
            "scm": "FAIL",
            "scm_detail": f"<scm> declares no url or connection and the parent chain is cyclic ({_pom_label(pom)}); Maven refuses to build a cyclic parent chain",
        }
    if chain_reason == "complete":
        if len(chain) == 1:
            return {
                "scm": "FAIL",
                "scm_detail": "<scm> declares no url or connection and the POM declares no <parent>: nothing to inherit from",
            }
        return {
            "scm": "FAIL",
            "scm_detail": "<scm> declares no url or connection and no parent POM in the staged chain declares one",
        }
    return {
        "scm": "INHERITED-UNVERIFIED",
        "scm_detail": "<scm> declares no url or connection and the parent chain is not fully staged locally; verify against the effective POM",
    }


def _resolve_chain(pom: dict, by_coordinate: dict) -> tuple[list[dict], str]:
    """Walk the parent chain through locally staged POMs.

    Returns ``(chain, reason)`` where ``chain`` is ``[pom, parent,
    grandparent, ...]`` as far as staged POMs resolve it, and ``reason``
    is ``"complete"`` when the walk ends at a POM with no ``<parent>``
    (so nothing outside the staged set could supply an inherited
    element), ``"unstaged"`` when it stops at a parent reference whose
    POM is not staged, or ``"cycle"`` when a parent coordinate repeats
    (including a POM naming itself as its own parent).
    """
    chain = [pom]
    visited = {(pom.get("group_id"), pom.get("artifact_id"), pom.get("version"))}
    current = pom
    while current.get("parent"):
        coordinate = tuple(current["parent"])
        if coordinate in visited:
            return chain, "cycle"
        parent = by_coordinate.get(coordinate)
        if parent is None:
            return chain, "unstaged"
        visited.add(coordinate)
        chain.append(parent)
        current = parent
    return chain, "complete"


def check_pom_entries(pom: dict, chain: list[dict], chain_reason: str) -> dict:
    """Check 1 - ALv2 licence, <developers> and <scm> in one POM.

    ``<licenses>`` and ``<developers>`` are judged at element level: an
    element absent from the POM itself is resolved against the locally
    staged parent chain, and the first ancestor that declares the
    element is judged as-is, so a staged parent carrying a non-ALv2
    licence fails the child too. ``<scm>`` is judged per field (Maven
    merges ``url`` / ``connection`` / ``tag`` independently) — see
    ``_check_scm``. When the chain is complete and nothing resolves an
    element — including a POM with no ``<parent>`` at all, where
    nothing can be inherited — the result is a hard FAIL; Maven Central
    rejects such a POM. A cyclic chain is a FAIL too: Maven refuses to
    build one, so it cannot be a correct POM inheriting from the ASF
    parent. An unstaged chain — the one case where a correct POM may
    inherit from the un-staged ASF parent — reports
    ``INHERITED-UNVERIFIED`` (see issue #1173 boundary conditions).
    """
    entries: dict[str, str | None] = {}
    for key in ("licenses", "developers"):
        if _element_present(pom, key):
            ok, fail_detail = _evaluate_element(pom, key)
            entries[key] = "PASS" if ok else "FAIL"
            if fail_detail is not None:
                entries[key + "_detail"] = fail_detail
            continue

        inherited = next((ancestor for ancestor in chain[1:] if _element_present(ancestor, key)), None)
        if inherited is not None:
            ok, fail_detail = _evaluate_element(inherited, key)
            label = _pom_label(inherited)
            entries[key] = "PASS" if ok else "FAIL"
            entries[key + "_detail"] = (
                f"inherited from locally staged parent POM {label}" if ok else f"{fail_detail} (inherited from locally staged parent POM {label})"
            )
        elif chain_reason == "complete":
            entries[key] = "FAIL"
            if len(chain) == 1:
                entries[key + "_detail"] = "element absent and the POM declares no <parent>: nothing to inherit from"
            else:
                entries[key + "_detail"] = "element absent and no parent POM in the staged chain declares it"
        elif chain_reason == "cycle":
            entries[key] = "FAIL"
            entries[key + "_detail"] = f"element absent and the parent chain is cyclic ({_pom_label(pom)}); Maven refuses to build a cyclic parent chain"
        else:
            entries[key] = "INHERITED-UNVERIFIED"
            entries[key + "_detail"] = "element absent and the parent chain is not fully staged locally; verify against the effective POM"
    entries.update(_check_scm(pom, chain, chain_reason))
    return entries


def check_disclaimer(pom: dict, chain: list[dict], chain_reason: str) -> dict:
    """Check 2 - incubation disclaimer inside <description> (podlings only).

    Resolution mirrors check 1: a ``<description>`` declared by a
    staged ancestor is judged as-is (an inherited description without
    the disclaimer stays a FAIL), an element no staged ancestor
    declares when the chain is complete is a FAIL, a cyclic chain is a
    FAIL, and an unstaged chain reports ``INHERITED-UNVERIFIED``.
    """
    if pom.get("description_present"):
        description = pom.get("description")
        if description is None:
            # <description></description> declared but empty.
            return {"disclaimer": "FAIL", "disclaimer_detail": "<description> empty for a podling POM"}
        if all(core in _normalize_ws(description) for core in DISCLAIMER_CORE):
            return {"disclaimer": "PASS", "disclaimer_detail": None}
        return {
            "disclaimer": "FAIL",
            "disclaimer_detail": ("<description> does not carry the incubation disclaimer (neither the standard text nor the DISCLAIMER-WIP variant)"),
        }

    # Element absent locally: resolve against the staged parent chain.
    for ancestor in chain[1:]:
        if not ancestor.get("description_present"):
            continue
        description = ancestor.get("description")
        label = _pom_label(ancestor)
        if description is None:
            return {"disclaimer": "FAIL", "disclaimer_detail": f"inherited <description> is empty (from locally staged parent POM {label})"}
        if all(core in _normalize_ws(description) for core in DISCLAIMER_CORE):
            return {"disclaimer": "PASS", "disclaimer_detail": f"inherited from locally staged parent POM {label}"}
        return {"disclaimer": "FAIL", "disclaimer_detail": f"inherited description lacks the incubation disclaimer (from locally staged parent POM {label})"}

    if chain_reason == "complete":
        if len(chain) == 1:
            return {"disclaimer": "FAIL", "disclaimer_detail": "<description> absent for a podling POM with no <parent> to inherit from"}
        return {"disclaimer": "FAIL", "disclaimer_detail": "<description> absent and no parent POM in the staged chain declares it"}
    if chain_reason == "cycle":
        return {
            "disclaimer": "FAIL",
            "disclaimer_detail": f"<description> absent and the parent chain is cyclic ({_pom_label(pom)}); Maven refuses to build a cyclic parent chain",
        }
    return {
        "disclaimer": "INHERITED-UNVERIFIED",
        "disclaimer_detail": "<description> absent and the parent chain is not fully staged locally; verify against the effective POM",
    }


def _checksum_status(companion: Path, digest_file: Path, digest: str) -> str | None:
    """Compare a checksum file's recorded digest with the companion's bytes.

    Returns ``None`` when the recorded digest matches, an error message
    when it does not, or ``"unverified"`` when ``digest`` names an
    algorithm this Python's ``hashlib`` does not provide (the file is
    still required, but its content cannot be checked offline). The hex
    digest is extracted leniently, so every layout published in
    practice is accepted: a bare digest, the GNU coreutils
    ``<digest>  <filename>``, the BSD/tagged ``ALGO (filename) =
    <digest>`` (``shasum --tag``), and ``gpg --print-md``'s
    ``filename: <DIGEST>`` — any case.
    """
    try:
        hasher = hashlib.new(digest)
    except ValueError:
        return "unverified"
    hasher.update(companion.read_bytes())
    actual = hasher.hexdigest()
    text = digest_file.read_text(encoding="utf-8", errors="replace")
    hex_length = len(actual)
    match = re.search(rf"(?<![0-9a-fA-F])[0-9a-fA-F]{{{hex_length}}}(?![0-9a-fA-F])", text)
    recorded = match.group(0) if match is not None else None
    if recorded is None:
        # `gpg --print-md` splits the digest into space-separated groups
        # and wraps it across lines, so there is no contiguous hex run;
        # rejoin everything after the last ':' and compare that.
        tail = re.sub(r"\s+", "", text.rsplit(":", 1)[-1])
        if re.fullmatch(rf"[0-9a-fA-F]{{{hex_length}}}", tail):
            recorded = tail
    if recorded is None or recorded.lower() != actual:
        return f"checksum mismatch: {digest_file.name} does not match {companion.name}"
    return None


def check_companions(jar: Path, digests: list[str], findings: list[str]) -> dict:
    """Check 3 - companion jars exist, each signed and checksummed.

    Checksum files are verified against the companion jar's actual
    bytes (``hashlib``, still offline). ``.asc`` signatures are checked
    for presence only: verifying a signature needs GPG and the release
    key, which `release-verify-rc` Step 2 runs against the main
    artefacts — the Step 6b recipe extends that verification to the
    companions when it emits the paste-ready commands.
    """
    results: list[dict[str, str | None]] = []
    for classifier in COMPANION_CLASSIFIERS:
        companion = jar.with_name(jar.name[: -len(".jar")] + f"-{classifier}.jar")
        if not companion.exists():
            results.append(
                {
                    "companion": companion.name,
                    "classification": "FAIL",
                    "detail": "missing companion jar (Maven Central requirement)",
                }
            )
            continue
        problems: list[str] = []
        if not (jar.parent / f"{companion.name}.asc").exists():
            problems.append(f"missing .asc signature file ({companion.name}.asc)")
        for digest in digests:
            digest_file = jar.parent / f"{companion.name}.{digest}"
            if not digest_file.exists():
                problems.append(f"missing .{digest} checksum file ({digest_file.name})")
                continue
            status = _checksum_status(companion, digest_file, digest)
            if status == "unverified":
                findings.append(f"{digest_file.name}: '{digest}' is not a digest algorithm this Python provides; checksum content not verified (presence only)")
            elif status is not None:
                problems.append(status)
        if problems:
            for problem in problems:
                results.append(
                    {
                        "companion": companion.name,
                        "classification": "FAIL",
                        "detail": problem,
                    }
                )
        else:
            results.append(
                {
                    "companion": companion.name,
                    "classification": "PASS",
                    "detail": None,
                }
            )
    return {"jar": jar.name, "companions": results}


def split_jar_name(name: str) -> tuple[str, str | None, str | None]:
    """Split ``<artifactId>-<version>[-<classifier>].jar`` into parts.

    Companion classifiers are detected by suffix first: a version's
    ``-[A-Za-z]+`` qualifier would otherwise greedily absorb
    ``-sources`` / ``-javadoc`` and hide the classifier.
    """
    base = name[: -len(".jar")]
    classifier: str | None = None
    for known in COMPANION_CLASSIFIERS:
        if base.endswith(f"-{known}"):
            classifier = known
            base = base[: -len(known) - 1]
            break
    m = VERSION_SPLIT_RE.match(base)
    if m is None:
        return base, None, classifier
    return m.group("stem"), m.group("version"), classifier


def verify_staged_dir(staged_dir: Path, digests: list[str], podling: bool) -> dict:
    # rglob, not glob: a staging directory in Maven-repository layout
    # (org/apache/foo/foo-core/1.0.0/...) is a JVM artefact set too — a
    # top-level-only scan would misreport it as non-JVM and skip.
    poms = sorted(staged_dir.rglob("*.pom"))
    jars = sorted(staged_dir.rglob("*.jar"))

    report: dict = {
        "tool": "maven-artifact-verify",
        "status": "SKIP",
        "artefact_dir": str(staged_dir),
        "podling": podling,
        "digests": digests,
        "poms": [],
        "jars": [],
        "unmatched_jars": [],
        "findings": [],
    }

    if not poms and not jars:
        report["findings"].append("no .pom or .jar files staged - non-JVM artefact set, JVM checks skip cleanly")
        return report

    parsed = {}
    for pom_path in poms:
        data = parse_pom(pom_path)
        parsed[pom_path] = data
        if "error" in data:
            report["poms"].append({"pom": pom_path.name, "check1": "FAIL", "detail": data["error"]})

    # Index the staged POMs by (groupId, artifactId, version) so a
    # <parent> reference can be resolved locally when possible.
    by_coordinate = {}
    for data in parsed.values():
        if "error" in data:
            continue
        by_coordinate[(data["group_id"], data["artifact_id"], data["version"])] = data

    # --- checks 1 and 2: per POM ---
    for pom_path, data in parsed.items():
        if "error" in data:
            continue
        chain, chain_reason = _resolve_chain(data, by_coordinate)
        check1 = check_pom_entries(data, chain, chain_reason)
        entry = {"pom": pom_path.name, "packaging": data["packaging"], "check1": check1}
        if podling:
            entry["check2"] = check_disclaimer(data, chain, chain_reason)
        report["poms"].append(entry)

    # --- check 3: per main jar ---
    main_jars = []
    for pom_path, data in parsed.items():
        if "error" in data or data["packaging"] == "pom":
            continue
        if data["artifact_id"] and data["version"]:
            if MAVEN_COORDINATE_RE.fullmatch(data["artifact_id"]) is None or MAVEN_COORDINATE_RE.fullmatch(data["version"]) is None:
                # The coordinates go straight into a path below; reject
                # anything Maven itself would not accept (e.g. "../..")
                # before touching the filesystem.
                report["findings"].append(
                    f"{pom_path.name}: artifactId {data['artifact_id']!r} / version {data['version']!r} is not a valid Maven coordinate "
                    "([A-Za-z0-9_.-] only); jar and companion checks skipped"
                )
                continue
            # The main jar lives in the POM's own directory (in Maven
            # repository layout that is the versioned subdirectory, not
            # the staged root).
            main = pom_path.parent / f"{data['artifact_id']}-{data['version']}.jar"
            if main.exists():
                main_jars.append(main)
            else:
                # The jar is published via the Nexus staging repository
                # in the common ASF workflow and is not staged locally
                # in dist/dev at all. That is an observation, not a
                # failure: companion coverage is only checkable for
                # jars that ARE staged locally. release-verify-rc
                # classifies an unexpected absence against
                # release-build.md § JVM artefact checks.
                report["jars"].append(
                    {
                        "jar": main.name,
                        "companions": [
                            {
                                "companion": main.name,
                                "classification": "ABSENT",
                                "detail": "main jar not staged locally; companion "
                                "checks skipped (verify via the Nexus "
                                "staging repository when it is the vote "
                                "target)",
                            }
                        ],
                    }
                )
                report["findings"].append(f"{main.name} is declared by a staged POM but not staged locally")

    matched = set(main_jars)
    for jar in jars:
        if jar in matched:
            continue
        _stem, _version, classifier = split_jar_name(jar.name)
        if classifier in COMPANION_CLASSIFIERS:
            # A companion of some main jar; check 3 runs against the
            # main jar (declared by its POM) and covers it there.
            continue
        # Not a POM-declared main jar and not a known companion
        # classifier (-tests, -shaded, platform classifiers, ...).
        # Report as unmatched: neither a main nor a companion, never a
        # failure in either direction (issue #1173 boundary conditions).
        report["unmatched_jars"].append(jar.name)

    for main in main_jars:
        report["jars"].append(check_companions(main, digests, report["findings"]))

    # --- aggregate ---
    statuses = []
    for entry in report["poms"]:
        for key in ("check1", "check2"):
            check = entry.get(key)
            if isinstance(check, str):
                statuses.append(check)
            elif isinstance(check, dict):
                statuses.extend(v for k, v in check.items() if not k.endswith("_detail"))
    for jar_entry in report["jars"]:
        for comp in jar_entry["companions"]:
            statuses.append(comp["classification"])

    if not statuses:
        if jars:
            # Jars staged but no POM anywhere: checks 1-2 cannot run,
            # and no main jar was POM-declared for check 3. Never a
            # silent skip — surface what could not be verified.
            report["status"] = "WARN"
            report["findings"].append(
                "jars staged but no .pom found: POM and companion checks could not run; verify against the Nexus staging repository (issue #1173, check 4)"
            )
        else:
            report["status"] = "SKIP"
    elif "FAIL" in statuses:
        report["status"] = "FAIL"
    elif "INHERITED-UNVERIFIED" in statuses:
        report["status"] = "WARN"
    else:
        report["status"] = "PASS"
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="maven-artifact-verify",
        description="Verify locally staged JVM release-candidate artefacts "
        "(POM licence set, podling disclaimer, companion jars). "
        "Stdlib-only and offline; prints one JSON report.",
    )
    parser.add_argument("staged_dir", type=Path, help="directory holding the staged .pom / .jar artefacts")
    parser.add_argument("--digests", default="sha512", help="comma-separated digest types companions must carry (default: sha512)")
    parser.add_argument("--podling", action="store_true", help="project is incubating: check 2 requires the incubation disclaimer in every <description>")
    args = parser.parse_args(argv)

    if not args.staged_dir.is_dir():
        print(
            json.dumps(
                {
                    "tool": "maven-artifact-verify",
                    "status": "FAIL",
                    "artefact_dir": str(args.staged_dir),
                    "findings": [f"staged directory does not exist: {args.staged_dir}"],
                }
            )
        )
        return 2

    digests = [d.strip() for d in args.digests.split(",") if d.strip()]
    report = verify_staged_dir(args.staged_dir, digests, args.podling)
    print(json.dumps(report, indent=2))
    return 0 if report["status"] != "FAIL" else 1


if __name__ == "__main__":
    sys.exit(main())
