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
"""Assemble release-announce-draft's Step 0 verdict and render its Step 2 and 3 drafts.

The functions are pure: they take what `release-config preflight` / `load
--skill announce-draft` printed and the facts the agent read from the planning
issue, and return the step's JSON contract. Nothing here sends mail, opens or
merges a PR, or touches the network (Golden rules 1 and 2).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from release_management.shell import dq, w

NOT_PROMOTED = "planning issue does not carry the promoted label: complete Step 10 (release-promote) first"
DEFAULT_SUBJECT = "[ANNOUNCE] <Product Name> <version> released"
SITE_SKIP_REASON = (
    "site_repo is not configured in release-management-config.md; no site-bump PR will be opened."
)
DESCRIPTION_PLACEHOLDER = "<one-sentence description>"
BACKENDS = ("announce-list", "github-release-notes", "site-post", "discord-channel")
NON_ASF_BACKEND_UNSET = (
    "release_announce_backend is unset: announce-list is the default for ASF projects only, and this project is "
    "not one — set release_announce_backend in release-management-config.md to {choices}"
)


class RenderError(ValueError):
    """The draft cannot be rendered as configured; the skill surfaces this and stops."""


# --------------------------------------------------------------------------- Step 0


def verdict(
    preflight: dict[str, Any], *, promoted: bool, planning_issue_found: bool = True
) -> dict[str, Any]:
    """Step 0: the tool's blockers plus the `promoted` label check it cannot see.

    The tool sets `promote_clear_after_utc` only when the promote-wait gate is its
    sole blocker; a failing label check makes it a second blocker, so it is nulled.
    """
    values = preflight.get("values") or {}
    blockers = [str(b) for b in preflight.get("blockers") or []]
    if not planning_issue_found:
        blockers.append(
            f"no planning issue found for {values.get('version') or '<version>'}: pass --planning-issue <url>"
        )
    elif not promoted:
        blockers.append(NOT_PROMOTED)
    if values.get("non_asf") and not values.get("release_announce_backend"):
        blockers.append(
            NON_ASF_BACKEND_UNSET.format(choices=" / ".join(b for b in BACKENDS if b != "announce-list"))
        )
    clear = values.get("promote_clear_after_utc")
    if len(blockers) != 1:
        clear = None
    read = (
        ["outcomes/promote-wait.md"]
        if values.get("promote_wait_active") and not values.get("skip_promote_wait_override")
        else []
    )
    return {
        "verdict": "blocked" if blockers else "proceed",
        "blockers": blockers,
        "skip_promote_wait_override": bool(values.get("skip_promote_wait_override")),
        "non_asf": bool(values.get("non_asf")),
        "promote_clear_after_utc": clear,
        "read": read,
    }


# --------------------------------------------------------------------------- Step 2


@dataclass
class Announce:
    """The resolved inputs the drafts are rendered from."""

    version: str
    meta: dict[str, Any]
    product_name: str = "<Product Name>"
    project_name: str = "<Project Name>"
    warnings: list[str] = field(default_factory=list)

    @classmethod
    def from_load(
        cls, loaded: dict[str, Any], *, product_name: str | None = None, project_name: str | None = None
    ) -> Announce:
        meta = loaded.get("metadata") or {}
        version = meta.get("version")
        if not version:
            raise RenderError(
                "release-config load output has no version: run it with --skill announce-draft <version>"
            )
        product = product_name or "<Product Name>"
        project = project_name or (product.removeprefix("Apache ") if product_name else "<Project Name>")
        return cls(version=str(version), meta=meta, product_name=product, project_name=project)

    @property
    def backend(self) -> str:
        return str(self.meta.get("release_announce_backend") or "announce-list")

    def sub(self, text: str, extra: dict[str, str] | None = None) -> str:
        """Substitute every spelling of the release placeholders a template may carry."""
        pairs = {
            "<Product Name>": self.product_name,
            "<product_name>": self.product_name,
            "<product-name>": self.product_name,
            "<Project Name>": self.project_name,
            "<version>": self.version,
        } | (extra or {})
        out = text
        for key, value in pairs.items():
            out = out.replace(key, value)
        return out

    def given(self, value: str | None, placeholder: str, what: str) -> str:
        if value:
            return value
        self.warnings.append(f"{what} is unknown: the draft carries {placeholder}; never invent it")
        return placeholder


def is_dist_url(url: str) -> bool:
    return urlparse(url).netloc.lower() == "dist.apache.org"


def _skip_line(reason: str) -> str:
    return (
        f"[SKIP-PROMOTE-WAIT: promote-wait gate overridden; the RM\naccepted this with the reason: {reason}.]"
    )


# Any wording of the sender reminder names a bare `@apache.org` (an address,
# account, sender …); a full address such as `announce@apache.org` is not one.
SENDER_REMINDER = re.compile(r"(?<![\w.+-])@apache\.org\b", re.IGNORECASE)

REMINDER = (
    "NOTE: This email must be sent from your @apache.org address. The\n"
    "{announce_list} rejects non-@apache.org senders (for ASF projects)."
)


def _announce_list_body(
    a: Announce,
    *,
    subject: str,
    download: str,
    changelog: str,
    keys: str,
    description: str,
    dev_list: str,
    users_list: str,
    convenience: list[tuple[str, str]],
    skip_reason: str | None,
) -> str:
    announce_list = a.given(a.meta.get("announce_list"), "<announce_list>", "announce_list")
    cc = [str(c) for c in a.meta.get("announce_cc_lists") or []]
    header = [f"To: {announce_list}"]
    if cc:
        header.append(f"Cc: {', '.join(cc)}")
    header.append(f"Subject: {subject}")
    parts = [
        "\n".join(header),
        REMINDER.format(announce_list=announce_list),
        f"The Apache {a.project_name} community is pleased to announce the release\nof {a.product_name} {a.version}.",
        f"{a.product_name} is {description}.",
        f"This release is available for download at the project Download Page:\n  {download}",
        f"Release notes / changelog for {a.version}:\n  {changelog}",
        f"Keys used to sign the release artifacts:\n  {keys}",
    ]
    if convenience:
        parts.append(
            "Convenience artefacts, built from the released source, are also available:\n"
            + "\n".join(f"  {kind}: {location}" for kind, location in convenience)
        )
    parts.append(
        f"Questions, feedback, and contributions are welcome on the\n{dev_list}. "
        f"General user support is available on {users_list}."
    )
    if skip_reason:
        parts.append(_skip_line(skip_reason))
    return "\n\n".join(parts)


def _github_release_notes(
    a: Announce,
    *,
    download: str,
    changelog: str,
    keys: str | None,
    description: str,
    convenience: list[tuple[str, str]],
    skip_reason: str | None,
) -> str:
    downloads = [f"- Download page: {download}"]
    if keys:
        downloads.append(f"- Keys used to sign the release artifacts: {keys}")
    downloads += [f"- {kind}: {location}" for kind, location in convenience]
    parts = [
        f"{a.product_name} {a.version} has been released.",
        f"{a.product_name} is {description}.",
        "## Downloads\n\n" + "\n".join(downloads),
        f"## Changelog\n\n- Release notes / changelog for {a.version}: {changelog}",
    ]
    if skip_reason:
        parts.append(_skip_line(skip_reason))
    return "\n\n".join(parts)


def _site_post(
    a: Announce, *, download: str, changelog: str, description: str, skip_reason: str | None
) -> str:
    parts = [
        f"## {a.product_name} {a.version} released",
        f"The {a.project_name} community is pleased to announce the release of {a.product_name} {a.version}.",
        f"{a.product_name} is {description}.",
        f"Download it from the [Download Page]({download}); "
        f"the [release notes / changelog for {a.version}]({changelog}) list what changed.",
    ]
    if skip_reason:
        parts.append(_skip_line(skip_reason))
    return "\n\n".join(parts)


def _discord(a: Announce, *, download: str, changelog: str, description: str, skip_reason: str | None) -> str:
    lines = [
        f"{a.product_name} {a.version} is released! {a.product_name} is {description}.",
        "",
        f"- Download page: {download}",
        f"- Changelog: {changelog}",
    ]
    if skip_reason:
        lines += ["", _skip_line(skip_reason)]
    return "\n".join(lines)


def step2(
    a: Announce,
    *,
    download_page: str | None,
    changelog_url: str | None,
    skip_reason: str | None = None,
    canned_body: str | None = None,
    description: str | None = None,
    dev_list: str | None = None,
    users_list: str | None = None,
    convenience: list[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    """Step 2: the subject and the backend-shaped body."""
    backend = a.backend
    if backend not in BACKENDS:
        raise RenderError(f"unknown release_announce_backend {backend!r}")
    subject = a.sub(str(a.meta.get("subject_template") or DEFAULT_SUBJECT))
    download = a.given(download_page, "<download_page_url>", "the Download Page URL")
    if is_dist_url(download):
        a.warnings.append(
            f"the Download Page URL {download} is a direct dist.apache.org URL: ask the RM for the project's "
            "Download Page URL before the body is finalised (Golden rule 5)"
        )
    changelog = a.given(changelog_url, "<changelog_url>", "the changelog URL")
    keys_url = a.meta.get("keys_url")
    desc = description or DESCRIPTION_PLACEHOLDER
    items = convenience or []
    reminder_added = False
    if canned_body:
        announce_list = str(a.meta.get("announce_list") or "<announce_list>")
        cc = ", ".join(str(c) for c in a.meta.get("announce_cc_lists") or [])
        body = a.sub(
            canned_body,
            {
                "<announce_list>": announce_list,
                "<announce-list>": announce_list,
                "<announce_cc_lists>": cc,
                "<announce-cc-lists>": cc,
                "<download_page_url>": download,
                "<download-page-url>": download,
                "<changelog_url>": changelog,
                "<changelog-url>": changelog,
                "<keys_url>": str(keys_url or "<keys_url>"),
                "<keys-url>": str(keys_url or "<keys_url>"),
                "<dev-list>": dev_list or "<dev-list>",
                "<users-list>": users_list or "<users-list>",
            },
        ).strip()
        if backend == "announce-list" and not SENDER_REMINDER.search(body):
            body = REMINDER.format(announce_list=announce_list) + "\n\n" + body
            reminder_added = True
            a.warnings.append(
                "canned_body had no @apache.org sender reminder: it was prepended (Golden rule 4)"
            )
        if skip_reason and skip_reason not in body:
            body += "\n\n" + _skip_line(skip_reason)
    elif backend == "announce-list":
        body = _announce_list_body(
            a,
            subject=subject,
            download=download,
            changelog=changelog,
            keys=a.given(keys_url, "<keys_url>", "keys_file_url"),
            description=desc,
            dev_list=dev_list or "<dev-list>",
            users_list=users_list or "<users-list>",
            convenience=items,
            skip_reason=skip_reason,
        )
    elif backend == "github-release-notes":
        body = _github_release_notes(
            a,
            download=download,
            changelog=changelog,
            keys=keys_url,
            description=desc,
            convenience=items,
            skip_reason=skip_reason,
        )
    elif backend == "site-post":
        body = _site_post(
            a, download=download, changelog=changelog, description=desc, skip_reason=skip_reason
        )
    else:
        body = _discord(a, download=download, changelog=changelog, description=desc, skip_reason=skip_reason)
    return {
        "subject": subject,
        "body": body,
        "backend": backend,
        "skip_promote_wait_logged": bool(skip_reason),
        "asf_address_reminder_present": backend == "announce-list",
        "download_page_is_dist": is_dist_url(download),
        "reminder_prepended": reminder_added,
        "warnings": a.warnings,
    }


# --------------------------------------------------------------------------- Step 3


def step3(
    a: Announce,
    *,
    files: list[str] | None = None,
    confirmed_extra: list[str] | None = None,
    body_file: str = "<scratch>/announce-pr-body.md",
) -> dict[str, Any]:
    """Step 3: the site-bump PR title, body and scope; skipped without `site_repo`."""
    site_repo = a.meta.get("site_repo")
    if not site_repo:
        return {"skipped": True, "reason": SITE_SKIP_REASON}
    allowed = [str(f) for f in a.meta.get("site_pr_files") or []]
    proposed = files or allowed
    confirmed = set(confirmed_extra or [])
    in_scope = [f for f in proposed if f in allowed or f in confirmed]
    violations = [f for f in proposed if f not in allowed and f not in confirmed]
    title = f"chore: update site for {a.product_name} {a.version} release"
    body = "\n".join(
        [
            f"Site bump for {a.product_name} {a.version}.",
            "",
            "Files updated:",
            *(f"- {f}" for f in in_scope),
            "",
            "Constraints:",
            "- Download links use the closer.lua CDN selector, not direct dist.apache.org URLs.",
            "- Merge after the [ANNOUNCE] email is sent.",
            "",
            "Generated by `release-announce-draft` (magpie-release-announce-draft).",
        ]
    )
    return {
        "pr_title": title,
        "pr_body": body,
        "files_in_scope": in_scope,
        "scope_violations": violations,
        "confirmed_out_of_scope": [f for f in in_scope if f not in allowed],
        "proposed": True,
        "site_repo": site_repo,
        "pr_command": f"gh pr create --web --repo {w(site_repo)} --title {dq(title)} --body-file {w(body_file)} --base main",
    }
