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
"""Step 3 and the verdict: the detector output mapped to stack-level findings.

What the detectors prove is mapped here, once, by the table in the skill's
classification documents. What needs a human read comes back as a
*candidate*: a seam hit at a later head (is the definition absent there?), a
floor move (does a lower layer use a construct above its floor?), a
wrong-layer outlier (does the hunk belong to another layer?), and the
narrative and residue checks. The agent confirms, drops or re-grades
candidates; `verdict` then decides from the confirmed list alone.
"""

from __future__ import annotations

from typing import Any

SEVERITY_ORDER = {"blocking": 0, "major": 1, "minor": 2}

#: Classification document per finding class (paths relative to the skill).
CLASS_DOCS = {
    "chain": "classifications/chain.md",
    "ordering": "classifications/ordering.md",
    "trunk-drift": "classifications/trunk-drift.md",
    "wrong-layer": "classifications/wrong-layer.md",
    "duplicate": "classifications/duplicate.md",
    "narrative": "classifications/narrative.md",
    "residue": "classifications/residue.md",
}

VERDICT_DOCS = {
    "coherent": "classifications/verdict-coherent.md",
    "merge-unit": "classifications/verdict-merge-unit.md",
    "needs-attention": "classifications/verdict-needs-attention.md",
    "not-mergeable": "classifications/verdict-not-mergeable.md",
}

VERDICT_LABELS = {
    "coherent": "coherent",
    "merge-unit": "mergeable bottom-up; merge layers {unit} together",
    "needs-attention": "needs attention before the bottom merges",
    "not-mergeable": "not mergeable as a stack",
}


def _finding(
    cls: str, severity: str, layers: list[int], evidence: str, *, verify: str | None = None
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "class": cls,
        "severity": severity,
        "layers": sorted(set(layers)),
        "evidence": evidence,
    }
    if verify:
        out["verify"] = verify
    return out


def from_chain(chain: dict[str, Any] | None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    findings: list[dict[str, Any]] = []
    info: list[dict[str, Any]] = []
    if not chain:
        return findings, info
    layers = chain.get("layers") or []
    first = min((int(x["position"]) for x in layers), default=1)
    for layer in layers:
        k = int(layer["position"])
        if k > first and layer.get("contains_below") is False:
            findings.append(
                _finding(
                    "chain",
                    "blocking",
                    [k],
                    f"layer {k} does not contain layer {k - 1}'s head — cascade rebase needed "
                    "(`gh stack rebase`, then `gh stack push`; quoted, never run)",
                )
            )
        if int(layer.get("merge_commits") or 0) > 0:
            findings.append(
                _finding(
                    "chain", "blocking", [k], f"layer {k} carries {layer['merge_commits']} merge commit(s)"
                )
            )
        if int(layer.get("own_commits") or 0) == 0:
            findings.append(_finding("narrative", "minor", [k], f"layer {k} is empty: no commits of its own"))
    touched = chain.get("trunk_touches_stack_files") or []
    if touched:
        findings.append(
            _finding(
                "trunk-drift",
                "major",
                [first],
                f"the trunk changed {len(touched)} file(s) the stack edits ({', '.join(touched[:5])}"
                f"{'…' if len(touched) > 5 else ''}); the next rebase conflicts or compiles differently",
            )
        )
    behind = int(chain.get("behind_trunk_commits") or 0)
    if behind:
        info.append({"kind": "behind-trunk", "commits": behind})
    return findings, info


def from_seams(seams: dict[str, Any] | None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    findings: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    for layer in (seams or {}).get("layers") or []:
        k = int(layer["position"])
        for name, hit in sorted((layer.get("hits") or {}).items()):
            if hit.get("at_own_head"):
                findings.append(
                    _finding(
                        "ordering",
                        "blocking",
                        [k],
                        f"layer {k} removes `{name}` (from {hit.get('removed_in')}) and its own head still "
                        f"references it: {hit['at_own_head'][0]}",
                        verify="confirm the quoted lines are real references (import, call, attribute), not a "
                        "string or a doc; drop the finding otherwise",
                    )
                )
            for j, hits in sorted((hit.get("at_later_heads") or {}).items(), key=lambda kv: int(kv[0])):
                candidates.append(
                    {
                        "class": "ordering",
                        "layers": sorted({k, int(j)}),
                        "if_confirmed": "blocking",
                        "evidence": f"`{name}` removed in layer {k} is referenced at layer {j}'s head: {hits[0]}",
                        "question": f"is `{name}`'s definition absent at layer {j}'s head (a use reintroduced after "
                        "the removal → blocking ordering for that layer), or does layer {j} re-add it (an "
                        "observation)?".replace("{j}", str(j)),
                    }
                )
            if hit.get("new_on_trunk"):
                findings.append(
                    _finding(
                        "trunk-drift",
                        "major",
                        [k],
                        f"a reference to `{name}`, removed in layer {k}, appeared on the trunk after the stack was "
                        f"cut: {hit['new_on_trunk'][0]}",
                    )
                )
    return findings, candidates


def from_floors(floors: dict[str, Any] | None) -> list[dict[str, Any]]:
    candidates = []
    for change in (floors or {}).get("floor_changes") or []:
        if not change.get("moved"):
            continue
        k = int(change["position"])
        moves = ", ".join(f"{p}: {m['from']} → {m['to']}" for p, m in sorted(change["moved"].items()))
        candidates.append(
            {
                "class": "ordering",
                "layers_below": k,
                "if_confirmed": "major",
                "evidence": f"layer {k} moves the declared floor ({moves})",
                "question": f"does any layer below {k} use, at its own head, a construct the old floor lacks? Verify "
                f"with `git grep` at that head, quote the line, and name the merge unit (layers <a>\u2013{k}).",
            }
        )
    return candidates


def from_ledger(ledger: dict[str, Any] | None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    findings: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    if not ledger:
        return findings, candidates
    detectors = ledger.get("detectors") or {}
    for entry in detectors.get("release_note_in_several_layers") or []:
        findings.append(
            _finding(
                "duplicate",
                "major",
                list(entry["layers"]),
                f"release note {entry['path']} edited in layers {', '.join(map(str, entry['layers']))}",
            )
        )
    for entry in detectors.get("generated_in_several_layers") or []:
        findings.append(
            _finding(
                "duplicate",
                "major",
                list(entry["layers"]),
                f"generated file {entry['path']} regenerated in "
                f"layers {', '.join(map(str, entry['layers']))} — regenerate once, where its source changes",
            )
        )
    for entry in detectors.get("lock_without_manifest") or []:
        findings.append(
            _finding(
                "duplicate",
                "major",
                [int(entry["layer"]), *map(int, entry.get("manifest_layers") or [])],
                f"lock file {entry['path']} changes in layer {entry['layer']} while its manifest changes only in "
                f"layer(s) {', '.join(map(str, entry.get('manifest_layers') or [])) or 'none'}",
            )
        )
    for path, layers in sorted((ledger.get("overlap") or {}).items()):
        candidates.append(
            {
                "class": "wrong-layer",
                "layers": sorted(layers),
                "if_confirmed": "minor",
                "evidence": f"{path} is changed in layers {', '.join(map(str, layers))}",
                "question": "does a hunk in one layer belong to another layer's stated purpose? Check the commit "
                "bodies first: a placement a commit explains is narrative at most",
            }
        )
    for layer in ledger.get("layers") or []:
        k = int(layer["position"])
        for path in layer.get("dir_outliers") or []:
            candidates.append(
                {
                    "class": "wrong-layer",
                    "layers": [k],
                    "if_confirmed": "minor",
                    "evidence": f"layer {k} touches the off-theme file {path}",
                    "question": "does it belong to another layer? Name the layer it belongs to",
                }
            )
    return findings, candidates


def collect(
    chain: dict[str, Any] | None,
    seams: dict[str, Any] | None,
    floors: dict[str, Any] | None,
    ledger: dict[str, Any] | None,
    *,
    no_fetch: bool = False,
) -> dict[str, Any]:
    chain_f, info = from_chain(chain)
    seams_f, seam_c = from_seams(seams)
    ledger_f, ledger_c = from_ledger(ledger)
    findings = sort_findings([*chain_f, *seams_f, *ledger_f])
    candidates = [*seam_c, *from_floors(floors), *ledger_c]
    always = [
        {
            "class": "narrative",
            "question": "compare every layer's title and body with its commit messages, class "
            "histogram and read hunks; check stack maps across bodies",
        },
        {
            "class": "residue",
            "question": "collect the tokens the stack retires and build the residue grep with "
            "`stack-review residue-command`",
        },
    ]
    classes = {f["class"] for f in findings} | {c["class"] for c in candidates} | {"narrative", "residue"}
    return {
        "findings": findings,
        "candidates": candidates,
        "judgement": always,
        "informational": info,
        "skipped": ["chain", "seams", "floors", "residue"] if no_fetch else [],
        "docs": [CLASS_DOCS[c] for c in CLASS_DOCS if c in classes],
    }


def sort_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """`blocking` → `major` → `minor`; inside a severity, bottom layer first."""
    return sorted(
        findings,
        key=lambda f: (
            SEVERITY_ORDER.get(f.get("severity", "minor"), 3),
            min(f.get("layers") or [0]),
            f.get("class", ""),
        ),
    )


def coverage_qualifier(ledger: dict[str, Any] | None) -> str | None:
    """The clause every verdict line carries when a layer was read by exemplar."""
    layers = (ledger or {}).get("layers") or []
    if not any(layer.get("plan") == "exemplar" for layer in layers):
        return None
    read_hunks = sum(int(layer.get("planned_hunks") or 0) for layer in layers)
    all_hunks = sum(int(layer.get("hunks") or 0) for layer in layers)
    read_lines = sum(int(layer.get("planned_lines") or 0) for layer in layers)
    all_lines = sum(int(layer.get("changed_lines") or 0) for layer in layers)
    return (
        f"(structure checked in full; code read {read_hunks:,} of {all_hunks:,} hand-written hunks, "
        f"{read_lines:,} of {all_lines:,} lines)"
    )


def verdict(
    findings: list[dict[str, Any]], *, no_fetch: bool = False, ledger: dict[str, Any] | None = None
) -> dict[str, Any]:
    """The verdict from the confirmed stack-level findings alone (gate rows never count)."""
    ordered = sort_findings([f for f in findings if f.get("severity") in SEVERITY_ORDER])
    blocking = [f for f in ordered if f["severity"] == "blocking"]
    majors = [f for f in ordered if f["severity"] == "major"]
    unit = None
    if blocking:
        key = "not-mergeable"
    elif majors and all(f["class"] == "ordering" and len(f.get("layers") or []) > 1 for f in majors):
        key = "merge-unit"
        layers = sorted({k for f in majors for k in f["layers"]})
        unit = f"{layers[0]}\u2013{layers[-1]}"
    elif majors:
        key = "needs-attention"
    else:
        key = "coherent"
    label = VERDICT_LABELS[key].format(unit=unit or "")
    qualifier = coverage_qualifier(ledger)
    out: dict[str, Any] = {
        "verdict": key,
        "label": label,
        "line": f"{label} {qualifier}" if qualifier else label,
        "findings": ordered,
        "doc": VERDICT_DOCS[key],
        "demoted_layers": [
            int(x["position"]) for x in (ledger or {}).get("layers") or [] if x.get("plan") == "exemplar"
        ],
    }
    if unit:
        out["merge_unit"] = unit
    if no_fetch and key == "coherent":
        out["note"] = "chain and ordering are unknown under no-fetch; the verdict is from the ledger alone"
    return out
