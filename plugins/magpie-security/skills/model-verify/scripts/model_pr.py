#!/usr/bin/env python3
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

"""Open one security-model / discoverability pull request on a repository.

Collapses the repeated ``fork -> clone -> write the AGENTS.md -> SECURITY.md ->
model scaffold (create or append) -> commit -> push -> open the PR`` sequence
into a single invocation. Two modes:

  in-repo model   ``--model PATH``    lands ``PATH`` as the model file and wires
                                      ``AGENTS.md -> SECURITY.md -> <model>``
  pointer         ``--pointer URL``   wires ``AGENTS.md -> SECURITY.md -> URL``
                                      for a satellite repository that defers to
                                      an umbrella model held elsewhere

The file-merge core is a set of pure functions with no I/O: they take the
*existing* file content (or ``None`` when the file is absent) and return the new
content. They are idempotent, they create a file when it is missing, and when it
is present they append exactly one section -- they never edit existing prose.
That branch is the fiddly part of the job and the part worth testing; the git
and PR side effects live in ``cmd_open`` below.

The branch is pushed to a fork (``--fork-owner``, default: the authenticated
user of the source-control CLI). The PR is opened with ``gh pr create --web`` by
default, so the human reviews the rendered title, body, and diff in the browser
and clicks Submit themselves. ``--submit`` creates it non-interactively and
``--dry-run`` builds the files and prints the staged diff without committing,
pushing, or opening anything.
"""

from __future__ import annotations

import argparse
import contextlib
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

# ---------------------------------------------------------------------------
# License headers
# ---------------------------------------------------------------------------
#
# Every file this script writes into someone else's repository has to survive
# that repository's own license check. Which header does that is a per-project
# fact, so it is a flag rather than a constant:
#
#   ``apache-full``  the canonical Apache-2.0 boilerplate, wrapped in an HTML
#                    comment so it stays invisible in rendered Markdown. Older
#                    Apache RAT releases (0.13 is still in use) match only this
#                    form -- they do not recognise the SPDX identifier -- so a
#                    project gated on RAT needs it to pass without a `.ratignore`
#                    exemption.
#   ``spdx``         the two-line SPDX identifier. Shorter, and what most
#                    non-Apache projects expect.
#   ``none``         add nothing; the project's checker wants something else, or
#                    the repository has no license gate on Markdown at all.

_APACHE_FULL_HEADER = (
    "<!--\n"
    "Licensed to the Apache Software Foundation (ASF) under one\n"
    "or more contributor license agreements.  See the NOTICE file\n"
    "distributed with this work for additional information\n"
    "regarding copyright ownership.  The ASF licenses this file\n"
    "to you under the Apache License, Version 2.0 (the\n"
    '"License"); you may not use this file except in compliance\n'
    "with the License.  You may obtain a copy of the License at\n"
    "\n"
    "  http://www.apache.org/licenses/LICENSE-2.0\n"
    "\n"
    "Unless required by applicable law or agreed to in writing,\n"
    "software distributed under the License is distributed on an\n"
    '"AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY\n'
    "KIND, either express or implied.  See the License for the\n"
    "specific language governing permissions and limitations\n"
    "under the License.\n"
    "-->"
)

_SPDX_HEADER = (
    "<!-- SPDX-License-Identifier: Apache-2.0\n     https://www.apache.org/licenses/LICENSE-2.0 -->"
)

LICENSE_HEADERS: dict[str, str] = {
    "apache-full": _APACHE_FULL_HEADER,
    "spdx": _SPDX_HEADER,
    "none": "",
}

DEFAULT_LICENSE_HEADER = "spdx"
DEFAULT_MODEL_NAME = "THREAT_MODEL.md"
DEFAULT_BRANCH_PREFIX = "security-model"


def ensure_license_header(content: str, kind: str = DEFAULT_LICENSE_HEADER) -> str:
    """Prepend the configured license header unless ``content`` already carries one.

    Idempotent. Only a header the file *opens* with counts: a model document that
    merely mentions the Apache License somewhere in its prose still needs a real
    header, because a license checker scans the top of the file.
    """
    header = LICENSE_HEADERS[kind]
    stripped = content.lstrip()
    if not header:
        return stripped
    head = "\n".join(stripped.splitlines()[:30]).lower()
    already_headered = stripped.startswith("<!--") and (
        "apache license" in head or "licenses/license-2.0" in head or "spdx-license-identifier:" in head
    )
    if already_headered:
        return content
    return f"{header}\n\n{stripped}"


def branch_name(kind: str, date: str, prefix: str = DEFAULT_BRANCH_PREFIX) -> str:
    """Branch name for a model / discoverability PR.

    ``kind`` is ``threat-model`` when a model file is landed in-repo and
    ``discoverability`` when only the pointer chain is wired, so the branch name
    says which of the two shapes the reviewer is looking at before they open the
    diff -- e.g. ``security-model/discoverability-2026-09-08``.
    """
    return f"{prefix}/{kind}-{date}"


def clone_cmd(repo_url: str, base: str | None, dest: str) -> list[str]:
    """``git clone`` argv for the upstream checkout.

    When ``base`` names a non-default branch, clone *that* branch directly so the
    head branch is cut from the intended base. Cloning the default branch and
    then targeting a different base makes the PR diff the whole
    default-versus-base delta rather than just the scaffold files.
    """
    cmd = ["git", "clone", "--depth", "1"]
    if base:
        cmd += ["--branch", base]
    cmd += [repo_url, dest]
    return cmd


# ---------------------------------------------------------------------------
# Pure file builders
# ---------------------------------------------------------------------------


def _agents_security_section(security_note: str = "") -> str:
    extra = f"\n\n{security_note.strip()}" if security_note.strip() else ""
    return (
        "## Security\n\n"
        "Security model: [SECURITY.md](./SECURITY.md)\n\n"
        "Agents that scan this repository should consult `SECURITY.md` and the\n"
        "threat model it links before reporting issues." + extra
    )


def build_agents_md(
    existing: str | None,
    repo_name: str,
    security_note: str = "",
    license_header: str = DEFAULT_LICENSE_HEADER,
) -> str:
    """Return ``AGENTS.md`` content carrying a ``## Security`` section that points
    at ``SECURITY.md``.

    Creates the file when ``existing`` is ``None``; appends the one section
    otherwise. Idempotent -- ``existing`` is returned unchanged when it already
    has a ``## Security`` heading.
    """
    section = _agents_security_section(security_note)
    if existing is None:
        header = LICENSE_HEADERS[license_header]
        preamble = f"{header}\n\n" if header else ""
        return (
            f"{preamble}"
            f"# Agent guide for {repo_name}\n\n"
            "This file is read by automated agents (security scanners, code\n"
            "analyzers, AI assistants) operating on this repository. It points\n"
            "them at the human-authored references they should consult before\n"
            "producing output.\n\n"
            f"{section}\n"
        )
    if "## Security" in existing:
        return existing
    return f"{existing.rstrip()}\n\n{section}\n"


def _security_threat_section(model_ref: str) -> str:
    return (
        "## Threat model\n\n"
        "What the project treats as in scope and out of scope, the security\n"
        "properties it provides and disclaims, the adversary model, and how\n"
        f"findings are triaged are documented in {model_ref}.\n"
    )


def build_security_md(
    existing: str | None,
    repo: str,
    model_ref: str,
    report_to: str | None = None,
    report_policy_url: str | None = None,
    license_header: str = DEFAULT_LICENSE_HEADER,
) -> str:
    """Return ``SECURITY.md`` content carrying a ``## Threat model`` section that
    links ``model_ref``.

    ``model_ref`` is already-rendered Markdown: a relative link such as
    ``[THREAT_MODEL.md](./THREAT_MODEL.md)`` for an in-repo model, or an autolink
    such as ``<https://.../THREAT_MODEL.md>`` for a pointer.

    Creates a minimal policy file when ``existing`` is ``None``; appends the one
    section otherwise. Idempotent -- ``existing`` is returned unchanged when it
    already has a ``## Threat model`` heading. Creating the file needs a private
    reporting address (``report_to``), because a `SECURITY.md` that tells a
    reporter nothing about where to send a report is worse than none at all.
    """
    section = _security_threat_section(model_ref)
    if existing is None:
        if not report_to:
            raise ValueError(
                "creating SECURITY.md needs --report-to (the project's private "
                "vulnerability-reporting address); pass it, or point --pointer / "
                "--model at a repo that already has SECURITY.md"
            )
        header = LICENSE_HEADERS[license_header]
        preamble = f"{header}\n\n" if header else ""
        policy_line = (
            f"`{repo}` follows the [project security process]({report_policy_url}).\n"
            if report_policy_url
            else ""
        )
        return (
            f"{preamble}"
            "# Security policy\n\n"
            "## Reporting a vulnerability\n\n"
            f"{policy_line}"
            f"Please report suspected vulnerabilities privately to `{report_to}`.\n"
            "Do not open public issues or pull requests for security reports.\n\n"
            f"{section}"
        )
    if "## Threat model" in existing:
        return existing
    return f"{existing.rstrip()}\n\n{section}"


def model_reference(model_name: str | None, pointer: str | None) -> str:
    """Render the Markdown reference `SECURITY.md` should link the model by.

    A pointer is wrapped as an autolink so the sentence-final period the template
    appends stays *outside* the link. Without the angle brackets a link checker
    grabs ``https://example.invalid/THREAT_MODEL.md.`` -- trailing dot included --
    and reports a 404 on a URL nobody wrote.
    """
    if pointer:
        return f"<{pointer}>"
    return f"[{model_name}](./{model_name})"


# ---------------------------------------------------------------------------
# Side effects
# ---------------------------------------------------------------------------


def _run(cmd: list[str], cwd: str | None = None, capture: bool = False) -> str:
    """Run a command, echoing it to stderr; raise on a non-zero exit."""
    print(f"$ {' '.join(cmd)}", file=sys.stderr)
    result = subprocess.run(cmd, cwd=cwd, text=True, capture_output=capture, check=False)
    if result.returncode != 0:
        if capture:
            sys.stderr.write(result.stdout or "")
            sys.stderr.write(result.stderr or "")
        raise SystemExit(f"command failed ({result.returncode}): {' '.join(cmd)}")
    return (result.stdout or "").strip() if capture else ""


def _remove_tree(path: Path) -> None:
    """Remove a directory tree or file, clearing read-only attributes on Windows."""

    def _on_error(func: object, p: str, _: object) -> None:
        with contextlib.suppress(OSError):
            if not os.path.islink(p):
                st = os.stat(p)
                os.chmod(p, st.st_mode | stat.S_IWRITE)
        func(p)  # type: ignore[operator]

    if path.is_symlink():
        path.unlink()
    elif path.is_file():
        with contextlib.suppress(OSError):
            os.chmod(path, path.stat().st_mode | stat.S_IWRITE)
        path.unlink()
    elif path.is_dir():
        if sys.version_info >= (3, 12):
            shutil.rmtree(path, onexc=lambda func, p, exc: _on_error(func, p, exc))
        else:
            shutil.rmtree(path, onerror=_on_error)


def _validate_model_name_lexical(model_name: str) -> Path:
    """Validate lexical structure of model_name without needing a clone directory."""
    raw = model_name.strip()
    if not raw or raw in (".", "..") or raw.startswith(("/", "\\")) or ":" in raw:
        raise SystemExit(f"--model-name must be a relative path within the repository, got {model_name!r}")
    p = Path(raw)
    if p.is_absolute() or p.drive or p.root or ".." in p.parts:
        raise SystemExit(f"--model-name must be a relative path within the repository, got {model_name!r}")
    return p


def _assert_path_within_clone(clone: Path, p: Path, model_name: str) -> Path:
    """Ensure resolved model path does not escape clone root."""
    target = (clone / p).resolve()
    if not target.is_relative_to(clone.resolve()) or target == clone.resolve():
        raise SystemExit(f"--model-name escapes the repository: {model_name!r}")
    return p


def _validate_model_name(clone: Path, model_name: str) -> Path:
    """Validate lexical structure and assert containment within clone."""
    p = _validate_model_name_lexical(model_name)
    return _assert_path_within_clone(clone, p, model_name)


def _read_or_none(path: Path) -> str | None:
    return path.read_text(encoding="utf-8") if path.exists() else None


def cmd_open(args: argparse.Namespace) -> int:
    if "/" not in args.repo:
        raise SystemExit(f"--repo must be <owner>/<name>, got {args.repo!r}")
    _, name = args.repo.split("/", 1)
    repo_url = f"https://github.com/{args.repo}.git"

    model_path: Path | None = None
    if args.model:
        if not Path(args.model).is_file():
            raise SystemExit(f"--model file not found: {args.model}")
        model_path = _validate_model_name_lexical(args.model_name)
    if args.body_file and not Path(args.body_file).is_file():
        raise SystemExit(f"--body-file not found: {args.body_file}")

    if args.fork_owner:
        fork_owner = args.fork_owner
    elif args.dry_run:
        try:
            fork_owner = _run(["gh", "api", "user", "--jq", ".login"], capture=True)
        except (SystemExit, FileNotFoundError):
            fork_owner = "<fork-owner>"
    else:
        fork_owner = _run(["gh", "api", "user", "--jq", ".login"], capture=True)

    kind = "threat-model" if args.model else "discoverability"
    branch = args.branch or branch_name(kind, args.date, args.branch_prefix)

    is_temp_workroot = not args.workdir
    workroot = Path(args.workdir) if args.workdir else Path(tempfile.mkdtemp(prefix="model-pr-"))
    clone = workroot / name

    try:
        if clone.exists() or clone.is_symlink():
            if args.workdir and not args.overwrite:
                raise SystemExit(
                    f"Destination directory already exists in --workdir: {clone}. "
                    "Pass --overwrite to reuse it or use a clean --workdir."
                )
            _remove_tree(clone)

        # Make sure the fork exists (a no-op when it already does), then clone the
        # upstream. Most repositories reject a direct branch push from a
        # non-committer, so the head branch lives on the fork either way.
        if not args.dry_run:
            _run(["gh", "repo", "fork", args.repo, "--clone=false"], capture=True)
        _run(clone_cmd(repo_url, args.base, str(clone)), capture=True)
        base = args.base or _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=str(clone), capture=True)
        _run(["git", "checkout", "-q", "-b", branch], cwd=str(clone))

        if args.model and model_path is not None:
            _assert_path_within_clone(clone, model_path, args.model_name)
            model_text = ensure_license_header(
                Path(args.model).read_text(encoding="utf-8"), args.license_header
            )
            target_model = clone / model_path
            target_model.parent.mkdir(parents=True, exist_ok=True)
            target_model.write_text(model_text, encoding="utf-8")
            files = [model_path.as_posix(), "SECURITY.md", "AGENTS.md"]
        else:
            files = ["SECURITY.md", "AGENTS.md"]
        model_ref = model_reference(
            model_path.as_posix() if args.model and model_path else None, args.pointer
        )

        (clone / "SECURITY.md").write_text(
            build_security_md(
                _read_or_none(clone / "SECURITY.md"),
                args.repo,
                model_ref,
                report_to=args.report_to,
                report_policy_url=args.report_policy_url,
                license_header=args.license_header,
            ),
            encoding="utf-8",
        )
        (clone / "AGENTS.md").write_text(
            build_agents_md(
                _read_or_none(clone / "AGENTS.md"),
                name,
                args.agents_note,
                license_header=args.license_header,
            ),
            encoding="utf-8",
        )

        _run(["git", "add", *files], cwd=str(clone))
        _run(["git", "--no-pager", "diff", "--cached"], cwd=str(clone))
        if args.dry_run:
            print(f"\n[dry-run] would commit + push {branch} to {fork_owner} and open a PR on {args.repo}")
            return 0

        subject = args.title or (
            "Add a draft threat model, SECURITY.md, and AGENTS.md for security-model discoverability"
            if args.model
            else "Add SECURITY.md and AGENTS.md for security-model discoverability"
        )
        _run(["git", "commit", "-q", "-m", subject], cwd=str(clone))
        _run(
            ["git", "remote", "add", "fork", f"https://github.com/{fork_owner}/{name}.git"],
            cwd=str(clone),
        )
        _run(["git", "push", "-q", "-u", "fork", branch], cwd=str(clone), capture=True)

        pr_cmd = [
            "gh",
            "pr",
            "create",
            "--repo",
            args.repo,
            "--head",
            f"{fork_owner}:{branch}",
            "--base",
            base,
            "--title",
            subject,
        ]
        pr_cmd += ["--body-file", args.body_file] if args.body_file else ["--body", subject]
        # `--web` is the second gate: the human reads the rendered diff in the
        # browser and clicks Submit. `--submit` skips it, and is for the case where
        # that read-through already happened.
        pr_cmd += [] if args.submit else ["--web"]
        out = _run(pr_cmd, cwd=str(clone), capture=True)
        if out:
            print(out)
        print(f"\nDone: {args.repo} branch {branch} (base {base}) pushed to {fork_owner}.", file=sys.stderr)
        return 0
    finally:
        if is_temp_workroot:
            _remove_tree(workroot)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="model_pr.py",
        description="Open a security-model / discoverability pull request on a repository.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("open", help="Open one model / discoverability PR.")
    p.add_argument("--repo", required=True, help="Target repository as <owner>/<name>.")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--model", help="Path to a model document to land in the repository.")
    g.add_argument("--pointer", help="URL of an umbrella model held in another repository.")
    p.add_argument("--model-name", default=DEFAULT_MODEL_NAME, help="In-repo model filename.")
    p.add_argument("--date", required=True, help="Date stamp for the branch (YYYY-MM-DD).")
    p.add_argument("--branch", help="Override the generated branch name.")
    p.add_argument("--branch-prefix", default=DEFAULT_BRANCH_PREFIX, help="Branch-name prefix.")
    p.add_argument("--base", help="Base branch (default: the repository's default branch).")
    p.add_argument("--fork-owner", help="Fork to push to (default: the authenticated user).")
    p.add_argument("--agents-note", default="", help="Extra note for the AGENTS.md Security section.")
    p.add_argument("--report-to", help="Private vulnerability-reporting address, for a new SECURITY.md.")
    p.add_argument(
        "--report-policy-url", help="URL of the project's security process, for a new SECURITY.md."
    )
    p.add_argument(
        "--license-header",
        choices=sorted(LICENSE_HEADERS),
        default=DEFAULT_LICENSE_HEADER,
        help="License header for files this run creates (default: %(default)s).",
    )
    p.add_argument("--title", help="PR title, also the commit subject.")
    p.add_argument("--body-file", help="Path to the PR body Markdown.")
    p.add_argument("--workdir", help="Where to clone (default: a temporary directory).")
    p.add_argument(
        "--overwrite", action="store_true", help="Allow overwriting an existing clone in --workdir."
    )
    p.add_argument("--submit", action="store_true", help="Create the PR directly instead of --web.")
    p.add_argument("--dry-run", action="store_true", help="Build the files and show the diff; write nothing.")
    return parser


DISPATCH = {"open": cmd_open}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return DISPATCH[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
