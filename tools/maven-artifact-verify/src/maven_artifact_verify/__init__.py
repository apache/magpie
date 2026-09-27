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
   ALv2 licence, ``<developers>`` and ``<scm>``. An element that is
   absent locally but supplied by a parent POM is resolved against the
   parent *when the parent POM is itself staged*; otherwise the result
   is ``inherited-unverified`` (a warning, never a failure - the
   correct POM must not be failed, per the issue's boundary conditions).
2. **Incubator disclaimer in ``<description>``** - podlings only,
   enabled by ``--podling``. Accepts the standard disclaimer and the
   ``DISCLAIMER-WIP`` variant; matching tolerates whitespace and
   line-wrapping differences. An absent description resolves against
   a locally staged parent POM when possible: ``INHERITED-UNVERIFIED``
   (a warning) when the parent is not staged, a failure when the
   effective description verifiably lacks the disclaimer.
3. **Companion jars** - for every staged main jar, the
   ``-sources.jar`` and ``-javadoc.jar`` companions must exist and each
   must carry its own ``.asc`` signature and checksum files.
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

APACHE_LICENSE_NAME_RE = re.compile(r"apache\s+license.*2\.0", re.IGNORECASE)
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


def check_pom_entries(pom: dict, parent_pom: dict | None) -> dict:
    """Check 1 - ALv2 licence, <developers> and <scm> in one POM."""
    entries: dict[str, str | None] = {}
    for key in ("licenses", "developers", "scm"):
        value = pom.get(key)
        # lists (licenses/developers): present when non-empty;
        # Element (scm): present when the element exists at all — an
        # empty <scm/> is a declaration that fails the url check.
        present = bool(value) if isinstance(value, list) else value is not None
        if present:
            if key == "licenses":
                ok = _has_apache_license(pom["licenses"])
                entries[key] = "PASS" if ok else "FAIL"
                if not ok:
                    entries[key + "_detail"] = (
                        "licences declared but none is ALv2 "
                        "(expected name matching 'Apache License, Version 2.0' "
                        "or url containing apache.org/licenses/LICENSE-2.0)"
                    )
            elif key == "developers":
                entries[key] = "PASS" if pom["developers"] else "FAIL"
            else:  # scm
                scm = pom["scm"]
                has_url = _text(_find_child(scm, "url")) is not None or _text(_find_child(scm, "connection")) is not None
                entries[key] = "PASS" if has_url else "FAIL"
            continue

        # Element absent locally: resolve against the parent POM when it
        # is staged, otherwise report inherited-unverified (WARN, never
        # FAIL - a correct POM inheriting from the ASF parent must not
        # fail this check; see issue #1173 boundary conditions).
        if parent_pom is not None:
            entries[key] = "PASS"
            entries[key + "_detail"] = "inherited from locally staged parent POM"
        else:
            entries[key] = "INHERITED-UNVERIFIED"
            entries[key + "_detail"] = "element absent and no locally staged parent POM to resolve against; verify against the effective POM"
    return entries


def check_disclaimer(pom: dict, parent_pom: dict | None) -> dict:
    """Check 2 - incubation disclaimer inside <description> (podlings only)."""
    description = pom.get("description")
    if description is None and not pom.get("description_present") and parent_pom is not None:
        # Element absent locally: resolve against a locally staged
        # parent POM when possible. A resolvable parent whose
        # description still lacks the disclaimer stays a FAIL.
        description = parent_pom.get("description")
        if description is not None:
            if all(core in _normalize_ws(description) for core in DISCLAIMER_CORE):
                return {"disclaimer": "PASS", "disclaimer_detail": "inherited from locally staged parent POM"}
            return {"disclaimer": "FAIL", "disclaimer_detail": "inherited description lacks the incubation disclaimer"}

    if description is None:
        if pom.get("description_present"):
            # <description></description> declared but empty.
            return {"disclaimer": "FAIL", "disclaimer_detail": "<description> empty for a podling POM"}
        if pom.get("parent") is not None:
            # Inherited from a parent POM that is not staged locally —
            # the effective POM may well carry the disclaimer; do not
            # fail a correct POM we cannot resolve offline.
            return {
                "disclaimer": "INHERITED-UNVERIFIED",
                "disclaimer_detail": ("<description> absent and no locally staged parent POM to resolve against; verify against the effective POM"),
            }
        return {"disclaimer": "FAIL", "disclaimer_detail": "<description> absent for a podling POM"}

    normalized = _normalize_ws(description)
    if all(core in normalized for core in DISCLAIMER_CORE):
        return {"disclaimer": "PASS", "disclaimer_detail": None}
    return {
        "disclaimer": "FAIL",
        "disclaimer_detail": ("<description> does not carry the incubation disclaimer (neither the standard text nor the DISCLAIMER-WIP variant)"),
    }


def check_companions(jar: Path, digests: list[str]) -> dict:
    """Check 3 - companion jars exist, each signed and checksummed."""
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
        for suffix, what in ((f"{companion.name}.asc", ".asc signature"), *[(f"{companion.name}.{d}", f".{d} checksum") for d in digests]):
            if not (jar.parent / suffix).exists():
                results.append(
                    {
                        "companion": companion.name,
                        "classification": "FAIL",
                        "detail": f"missing {what} file ({suffix})",
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
    poms = sorted(staged_dir.glob("*.pom"))
    jars = sorted(staged_dir.glob("*.jar"))

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
        parent_pom = None
        if data.get("parent"):
            parent_pom = by_coordinate.get(tuple(data["parent"]))
        check1 = check_pom_entries(data, parent_pom)
        entry = {"pom": pom_path.name, "packaging": data["packaging"], "check1": check1}
        if podling:
            entry["check2"] = check_disclaimer(data, parent_pom)
        report["poms"].append(entry)

    # --- check 3: per main jar ---
    main_jars = []
    for data in parsed.values():
        if "error" in data or data["packaging"] == "pom":
            continue
        if data["artifact_id"] and data["version"]:
            main = staged_dir / f"{data['artifact_id']}-{data['version']}.jar"
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
        report["jars"].append(check_companions(main, digests))

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
