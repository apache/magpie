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
"""`release-management prepare …` — every command prints JSON and runs nothing.

`--preflight` is what `release-config preflight --skill prepare …` printed and
`--load` what `release-config load --skill prepare …` printed, each saved to a
file; `--prs` is what `gh pr list --json number,title,url,labels,mergedAt`
printed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from release_management.cli import emit
from release_management.prepare import archive, category_x, next_dev_version, plan, prep, prev_tag, signing

FAMILY = "prepare"


def _json(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _text(path: str | None, *, missing_ok: bool = False) -> str | None:
    """The file's text; a path passed on the command line must exist, unless `missing_ok`."""
    if path is None:
        return None
    file = Path(path)
    if not file.is_file():
        if missing_ok and not file.exists():
            return None
        raise prep.RenderError(f"{path}: no such file")
    return file.read_text(encoding="utf-8", errors="replace")


def _prs(path: str) -> list[dict[str, Any]]:
    data = _json(path)
    if not isinstance(data, list):
        raise prep.RenderError("--prs must hold the JSON list `gh pr list --json` printed")
    return [d for d in data if isinstance(d, dict)]


def _pair(value: str) -> tuple[str, str]:
    key, sep, rest = value.partition("=")
    if not sep or not key.strip() or not rest.strip():
        raise argparse.ArgumentTypeError(f"expected KEY=VALUE, got {value!r}")
    return key.strip(), rest.strip()


def _files(values: list[str]) -> list[tuple[str, str]]:
    return [(f.split("=", 1)[0], f.split("=", 1)[1]) if "=" in f else (f, f) for f in values]


def _manifests(load: dict[str, Any]) -> list[str]:
    raw = (load.get("config") or {}).get("version_manifest_files") or []
    return (
        [str(m) for m in raw]
        if isinstance(raw, list)
        else [m.strip() for m in str(raw).split(",") if m.strip()]
    )


def add_parsers(sub: Any) -> None:
    parser = sub.add_parser(
        FAMILY,
        help="release-prepare: Step 0 verdict, planning issue, prep and post-release PRs, archive review, automated signing",
    )
    c = parser.add_subparsers(dest="command", required=True)

    v = c.add_parser(
        "verdict", help="Step 0: the preflight blockers plus train coverage, planning issue and gh access"
    )
    v.add_argument("--preflight", required=True)
    v.add_argument("--planning-issue", help="the planning issue URL, when one was found (prep, post)")
    v.add_argument("--planning-label", action="append", default=[], help="a label the planning issue carries")
    v.add_argument("--gh-access", action="store_true", help="`gh pr list --repo <upstream>` succeeded")
    v.add_argument("--previous-tag", help="the previous release tag, when detectable at pre-flight")
    v.add_argument(
        "--train-confirmed",
        action="store_true",
        help="the agent read release_lines and found the train record",
    )

    t = c.add_parser("prev-tag", help="1a: the previous final release tag of the train")
    t.add_argument(
        "--tags", required=True, help="file of tag names or `git ls-remote --tags` output ('-' for stdin)"
    )
    t.add_argument("--version", required=True)
    t.add_argument("--train", help="train pattern, e.g. 2.x or 2.11.x")
    t.add_argument("--tag-prefix", default="", help="namespace to strip, e.g. rel/")

    q = c.add_parser("plan-query", help="1a: the read that dates the previous tag, and the merged-PR query")
    q.add_argument("--upstream", required=True)
    q.add_argument("--base", required=True, help="release_branch_base")
    q.add_argument("--previous-tag")
    q.add_argument("--tag-date", help="what the date read printed")

    p = c.add_parser(
        "plan", help="1a/1b: the empty-set hand-off, or the planning issue title, body and create line"
    )
    p.add_argument("--prs", required=True)
    p.add_argument("--version", required=True)
    p.add_argument("--product-name", required=True)
    p.add_argument("--previous-tag")
    p.add_argument("--base", required=True)
    p.add_argument("--upstream", default="<upstream>")
    p.add_argument("--train", help="the release train name from release-trains.md")
    p.add_argument("--rm", help="the Release Manager from release-trains.md or user.md")
    p.add_argument("--template", help="file at release_planning_issue_template, when set")
    p.add_argument("--skip-empty-check", metavar="REASON", nargs="?", const="")
    p.add_argument("--opened-at", help="ISO-8601 time for the Timestamps section (default: now, UTC)")
    p.add_argument(
        "--body-file",
        help="where the approved body is written (default <scratch>/planning-issue-body-<version>.md)",
    )

    vs = c.add_parser("versions", help="2a: the current version string in each manifest")
    vs.add_argument("--target", required=True, help="the release version")
    vs.add_argument("files", nargs="+", help="<repo-path>=<local-copy>")

    x = c.add_parser("category-x", help="2b: scan manifest and lock files for Category-X identifiers")
    x.add_argument("--deny", action="append", default=[], help="a category_x_dependencies identifier")
    x.add_argument("files", nargs="+", help="<repo-path>=<local-copy> or a local path")

    n = c.add_parser("notice", help="2c: the attribution paragraphs a NOTICE diff removes and adds")
    n.add_argument("--diff", help="a unified NOTICE diff, instead of --old / --new")
    n.add_argument("--old", help="NOTICE at the previous release tag (omit when it had none)")
    n.add_argument("--new", help="NOTICE at the release branch base")

    cl = c.add_parser("changelog", help="2d: the changelog entry by section, and the ≥ 90%% coverage check")
    cl.add_argument("--prs", required=True)
    cl.add_argument("--version", required=True)
    cl.add_argument("--date", help="the entry date (default: today, UTC)")
    cl.add_argument("--load", help="release-config load output, for changelog_label_categories")
    cl.add_argument("--category", action="append", default=[], type=_pair, metavar="LABEL=SECTION")
    cl.add_argument(
        "--assign",
        action="append",
        default=[],
        type=_pair,
        metavar="N=SECTION",
        help="the RM's call for one PR",
    )

    m = c.add_parser("archive-mode", help="2e: full review, drift check or skipped, and the listings to save")
    m.add_argument("--load", required=True)
    m.add_argument("--review-archive", action="store_true")
    m.add_argument("--previous-tag")

    r = c.add_parser("archive-review", help="2e: bucket table, proposed entries, references and symlinks")
    r.add_argument("--tracked", required=True, help="`git ls-files` output")
    r.add_argument("--gitattributes", help="the clone's .gitattributes (absent is fine)")
    r.add_argument("--symlinks", help="`path -> target` lines")
    r.add_argument("--refs", help="what the rendered `git grep` loop printed")
    r.add_argument("--changed", help="drift check: `git diff --name-only <previous-tag> HEAD` output")
    r.add_argument("--exclude", action="append", default=[], help="an entry the RM chose to exclude")
    r.add_argument("--keep", action="append", default=[], help="a proposed entry the RM dropped")
    r.add_argument("--reason", action="append", default=[], type=_pair, metavar="PATH=WHY")
    r.add_argument("--load", help="release-config load output: RAT excludes, validators, manifests")
    r.add_argument(
        "--voter-input",
        action="append",
        default=[],
        help="a path the voters' checks read (RAT excludes, a validator)",
    )
    r.add_argument("--previous-tag")
    r.add_argument("--framework", default="<framework>")

    pr = c.add_parser("prep-pr", help="2f: the prep PR title, body and scope")
    pr.add_argument("--load", required=True)
    pr.add_argument("--version", required=True)
    pr.add_argument("--product-name", required=True)
    pr.add_argument("--changelog", required=True, help="what `prepare changelog` printed")
    pr.add_argument("--versions", help="what `prepare versions` printed")
    pr.add_argument("--current-version", help="the current dev version, when --versions cannot tell")
    pr.add_argument("--previous-tag")
    pr.add_argument("--notice-summary")
    pr.add_argument("--archive-mode", required=True, help="what `prepare archive-mode` printed")
    pr.add_argument("--archive-review", choices=prep.ARCHIVE_REVIEW, default="skipped")
    pr.add_argument("--archive-entry", action="append", default=[], type=_pair, metavar="ENTRY=REASON")
    pr.add_argument("--release-build", default=prep.DEFAULT_RELEASE_BUILD)
    pr.add_argument("--files", nargs="+", required=True, help="every file the diff touches")
    pr.add_argument("--confirm-extra", action="append", default=[])

    nd = c.add_parser("next-dev-version", help="14a: the next development version per configured file")
    nd.add_argument("--version", required=True, help="the version just released")
    src = nd.add_mutually_exclusive_group(required=True)
    src.add_argument("--config", help="resolved release-management-config.md carrying version_manifest_files")
    src.add_argument("--version-files", help="comma-separated version_manifest_files, instead of --config")
    nd.add_argument("files", nargs="*", help="files to report on; defaults to version_manifest_files")

    po = c.add_parser("post-pr", help="14b: the post-release bump PR title, body and scope")
    po.add_argument("--next", required=True, help="what `prepare next-dev-version` printed")
    po.add_argument("--product-name", required=True)
    po.add_argument("--load", required=True, help="release-config load output, for changelog_file")
    po.add_argument("--next-version", help="the RM's confirmed next version")
    po.add_argument("--files", nargs="+", required=True, help="every file the diff touches")
    po.add_argument("--confirm-extra", action="append", default=[])

    se = c.add_parser("signing-eligibility", help="A1: the automated-signing eligibility gate (ASF only)")
    se.add_argument("--load", required=True)
    se.add_argument(
        "--verify-rc-identical",
        action="store_true",
        help="the latest RC's release-verify-rc report shows Step 9 PASS, every artefact identical",
    )

    sw = c.add_parser("signing-render", help="A4/A5: the workflow file and the config diff")
    sw.add_argument("--load", required=True)
    sw.add_argument(
        "--template",
        required=True,
        help="<framework>/plugins/magpie-setup/templates/workflows/release-candidate.yml",
    )
    sw.add_argument("--project", required=True, help="the ASF project slug")
    sw.add_argument("--infra-ticket")


def _legacy(args: argparse.Namespace) -> int:
    """The three former skill scripts: same output, exit 2 on bad input."""
    try:
        if args.command == "prev-tag":
            text = sys.stdin.read() if args.tags == "-" else Path(args.tags).read_text(encoding="utf-8")
            out = prev_tag.find_previous(prev_tag.tag_names(text), args.version, args.train, args.tag_prefix)
        elif args.command == "category-x":
            deny = [d.strip() for d in args.deny if d.strip()]
            if not deny:
                out = {"category_x_hit": False, "category_x_violations": [], "files_scanned": []}
            else:
                out = category_x.scan(deny, _files(args.files))
            if out["category_x_hit"]:
                out["read"] = ["classifications/category-x-hit.md"]
        else:
            if args.config:
                configured = next_dev_version.configured_files(Path(args.config).read_text(encoding="utf-8"))
            else:
                configured = next_dev_version._split_values(args.version_files)
            out = next_dev_version.next_versions(args.version, configured, args.files)
    except (prev_tag.InputError, OSError, ValueError) as exc:
        emit({"error": str(exc)})
        return 2
    emit(out)
    return 0


def dispatch(args: argparse.Namespace) -> int:
    if args.command in ("prev-tag", "category-x", "next-dev-version"):
        return _legacy(args)
    try:
        out = _run(args)
    except (plan.RenderError, prep.RenderError, signing.RenderError, OSError) as exc:
        emit({"ok": False, "refused": str(exc)})
        return 2
    emit(out)
    return 0


def _run(args: argparse.Namespace) -> dict[str, Any]:
    cmd = args.command
    if cmd == "verdict":
        return plan.verdict(
            _json(args.preflight),
            planning_issue=args.planning_issue,
            planning_labels=args.planning_label,
            gh_access=args.gh_access,
            previous_tag=args.previous_tag,
            train_confirmed=args.train_confirmed,
        )
    if cmd == "plan-query":
        return plan.query(
            upstream=args.upstream, base=args.base, previous_tag=args.previous_tag, tag_date=args.tag_date
        )
    if cmd == "plan":
        return plan.render(
            _prs(args.prs),
            version=args.version,
            product_name=args.product_name,
            previous_tag=args.previous_tag,
            base=args.base,
            upstream=args.upstream,
            train=args.train,
            rm=args.rm,
            template=_text(args.template),
            skip_empty_check=args.skip_empty_check,
            opened_at=args.opened_at,
            body_file=args.body_file,
        )
    if cmd == "versions":
        return prep.versions(args.target, _files(args.files))
    if cmd == "notice":
        if args.diff:
            if args.old or args.new:
                raise prep.RenderError("pass --diff, or --old / --new, not both")
            return prep.notice_changes(_text(args.diff) or "")
        if not args.new:
            raise prep.RenderError("pass --diff, or --new (and --old unless the previous tag had no NOTICE)")
        return prep.notice_diff(_text(args.old), _text(args.new) or "")
    if cmd == "changelog":
        cats = prep.parse_categories(
            ((_json(args.load) if args.load else {}).get("config") or {}).get("changelog_label_categories")
        )
        cats.update(dict(args.category))
        assigned = {int(k.lstrip("#")): v for k, v in args.assign}
        return prep.changelog(
            _prs(args.prs), version=args.version, date=args.date, categories=cats, assigned=assigned
        )
    if cmd == "archive-mode":
        return archive.mode(
            _json(args.load), review_archive=args.review_archive, previous_tag=args.previous_tag
        )
    if cmd == "archive-review":
        load = _json(args.load) if args.load else {}
        build = load.get("build") or {}
        voters = {p for p in [build.get("rat_excludes_path"), build.get("rat_config_path")] if p}
        voters |= {str(v).split()[0] for v in build.get("source_tree_validators") or [] if str(v).strip()}
        return archive.review(
            archive.lines(_text(args.tracked)),
            gitattributes=_text(args.gitattributes, missing_ok=True),
            links=archive.parse_symlinks(_text(args.symlinks)),
            refs=archive.parse_refs(_text(args.refs)) if args.refs else None,
            changed=archive.lines(_text(args.changed)) if args.changed else None,
            exclude=args.exclude,
            keep=args.keep,
            reasons=dict(args.reason),
            voter_inputs=voters | set(args.voter_input) | {".rat-excludes"},
            manifests=set(_manifests(load)),
            previous_tag=args.previous_tag,
            framework=args.framework,
        )
    if cmd == "prep-pr":
        load = _json(args.load)
        current = args.current_version
        if current is None and args.versions:
            current = _json(args.versions).get("current_dev_version")
        return prep.prep_pr(
            version=args.version,
            product_name=args.product_name,
            manifests=_manifests(load),
            current_version=current,
            log=_json(args.changelog),
            previous_tag=args.previous_tag,
            changelog_file=(load.get("config") or {}).get("changelog_file"),
            notice_summary=args.notice_summary,
            archive_mode=str(_json(args.archive_mode).get("mode")),
            archive_review=args.archive_review,
            archive_entries=args.archive_entry,
            release_build=args.release_build,
            files=args.files,
            confirmed_extra=args.confirm_extra,
        )
    if cmd == "post-pr":
        return prep.post_pr(
            _json(args.next),
            product_name=args.product_name,
            next_version=args.next_version,
            changelog_file=(_json(args.load).get("config") or {}).get("changelog_file"),
            files=args.files,
            confirmed_extra=args.confirm_extra,
        )
    if cmd == "signing-eligibility":
        return signing.eligibility(_json(args.load), verify_rc_identical=args.verify_rc_identical)
    load = _json(args.load)
    template = Path(args.template).read_text(encoding="utf-8")
    return signing.workflow(load, template, project=args.project) | signing.config_diff(
        load, infra_ticket=args.infra_ticket
    )
