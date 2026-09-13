#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
"""Generate each family's *Works well with* block, and guard the registry.

A maintainer who has just installed the security family goes looking for a
scanner; one who installed `utilities` to author a skill goes looking for a
way to think about the skill before writing it. Magpie ships neither, and the
honest answer to both is a third-party package — a different one depending on
which agent they run.

That answer was nowhere. The install flow already offers MCP servers per
family, because a skill that needs a mail backend is useless without one; a
companion skill package is the same shape of advice one step further out, and
the same place is where it belongs.

Two things make this worth generating rather than writing by hand:

- **It is per family AND per harness.** Superpowers installs on six agents,
  each with its own command; Claude Security installs on one. Printed as prose
  in ten family READMEs that is forty-odd facts to keep straight, and the first
  one to rot tells a Codex user to run a Claude Code command.
- **It must never read as a dependency.** Every family works with none of these
  installed, and `docs/vendor-neutrality.md` is a live metric in this
  repository. Generating the block from one registry keeps the framing fixed:
  what it adds, whose it is, and which harnesses can have it.

The registry is `companion-skills.json`; its header comment carries the rules
for an entry. This script validates the shape, refuses an entry that cannot
say what it adds to the family it claims, and regenerates the blocks with
`--fix`.

Run from the repo root:

    python3 tools/dev/check-companion-skills.py
    python3 tools/dev/check-companion-skills.py --fix
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REGISTRY = Path("tools/dev/companion-skills.json")
PLUGINS = Path("plugins")

BEGIN = "<!-- BEGIN generated: companion-skills (tools/dev/check-companion-skills.py --fix) -->"
END = "<!-- END generated: companion-skills -->"

DOCS_DIR_OVERRIDES = {"issue": "issue-management"}

# The harnesses Magpie itself documents an install for, in the order the
# marketplace reference uses. A registry entry may name only these: a package
# available somewhere Magpie does not run is not advice this framework can give.
HARNESSES = {
    "claude-code": "Claude Code",
    "codex": "OpenAI Codex CLI",
    "copilot": "VS Code / GitHub Copilot",
    "gemini": "Google Gemini CLI",
    "cursor": "Cursor",
    "opencode": "OpenCode",
}

REQUIRED_FIELDS = {"id", "title", "vendor", "url", "what", "why", "harnesses"}


def families() -> list[str]:
    return sorted(p.name.removeprefix("magpie-") for p in PLUGINS.glob("magpie-*") if (p / "skills").is_dir())


def docs_readme(family: str) -> Path:
    return Path("docs") / DOCS_DIR_OVERRIDES.get(family, family) / "README.md"


def load() -> tuple[list[dict], list[str]]:
    try:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [], [f"{REGISTRY}: cannot read ({exc})"]

    entries = data.get("companions")
    if not isinstance(entries, list):
        return [], [f"{REGISTRY}: 'companions' is missing or not a list"]

    errors: list[str] = []
    known = set(families())
    seen: set[str] = set()
    for entry in entries:
        cid = entry.get("id", "<no id>")
        if missing := REQUIRED_FIELDS - set(entry):
            errors.append(f"{REGISTRY}: '{cid}' is missing {', '.join(sorted(missing))}")
            continue
        if cid in seen:
            errors.append(f"{REGISTRY}: duplicate entry '{cid}'")
        seen.add(cid)
        if not isinstance(entry["why"], dict) or not entry["why"]:
            errors.append(
                f"{REGISTRY}: '{cid}' has no 'why' — an entry that cannot say what it "
                f"adds to a named family is an advert, not a recommendation"
            )
            continue
        for family in entry["why"]:
            if family not in known:
                errors.append(f"{REGISTRY}: '{cid}' claims family '{family}', which does not exist")
        if not isinstance(entry["harnesses"], dict) or not entry["harnesses"]:
            errors.append(f"{REGISTRY}: '{cid}' names no harness it is available on")
            continue
        for harness in entry["harnesses"]:
            if harness not in HARNESSES:
                errors.append(
                    f"{REGISTRY}: '{cid}' names harness '{harness}', which is not one "
                    f"Magpie documents an install for ({', '.join(sorted(HARNESSES))})"
                )
        if not str(entry["url"]).startswith("https://"):
            errors.append(f"{REGISTRY}: '{cid}' url is not https")
    return entries, errors


def render(family: str, entries: list[dict]) -> str:
    mine = [e for e in entries if family in e.get("why", {})]
    if not mine:
        return ""

    lines = [
        BEGIN,
        "",
        "### Works well with",
        "",
        "Third-party packages, none of them required: this family works with none of",
        "them installed, and Magpie neither bundles nor depends on any. They are named",
        "because they are what a maintainer goes looking for next, and because the",
        "answer differs by agent.",
        "",
    ]
    for entry in sorted(mine, key=lambda e: e["id"]):
        lines += [
            f"**[{entry['title']}]({entry['url']})** — {entry['vendor']}",
            "",
            f"{entry['what']}",
            "",
            f"*With this family:* {entry['why'][family]}",
            "",
        ]
        available = [HARNESSES[h] for h in HARNESSES if h in entry["harnesses"]]
        if len(available) == 1:
            lines += [f"Available on **{available[0]}** only.", ""]
        else:
            lines += [f"Available on {', '.join(f'**{a}**' for a in available)}.", ""]
        if note := entry.get("note"):
            lines += [f"{note}", ""]

    lines += [
        "Install commands per agent are in",
        "[**Companion skill packages**](../setup/companion-skills.md).",
        "",
        END,
    ]
    return "\n".join(lines)


def splice(body: str, block: str) -> str | None:
    """Replace the generated block, insert it, or remove it when empty."""
    has = BEGIN in body and END in body
    if has:
        start = body.index(BEGIN)
        end = body.index(END) + len(END)
        if not block:
            # Trim the blank line the block left behind.
            tail = body[end:]
            return body[:start].rstrip("\n") + "\n\n" + tail.lstrip("\n")
        return body[:start] + block + body[end:]
    if not block:
        return body
    anchor = "### Try these first\n"
    if anchor not in body:
        return None
    return body.replace(anchor, block + "\n\n" + anchor, 1)


def reference_page(entries: list[dict]) -> str:
    """The one page carrying the install commands, per package per harness."""
    lines = [
        "<!-- SPDX-License-Identifier: Apache-2.0",
        "     https://www.apache.org/licenses/LICENSE-2.0 -->",
        "",
        BEGIN,
        "",
        "# Companion skill packages",
        "",
        "Magpie ships skills for maintaining a project. Some of the things a",
        "maintainer wants next are not maintenance — scanning your own code for",
        "vulnerabilities, or having a method for thinking through a change before",
        "writing it — and other people have built those well. This page names them.",
        "",
        "**None of them is a dependency.** Every Magpie family works with none of these",
        "installed. Magpie bundles no third-party skill, fetches none automatically,",
        "and takes no position on which vendor you should prefer; each entry says",
        "whose it is and which agents can run it, so the choice stays yours.",
        "",
        "Where a package exists for only one agent, that is stated rather than",
        "smoothed over. A recommendation you cannot act on is worse than none.",
        "",
    ]
    for entry in sorted(entries, key=lambda e: e["id"]):
        fams = ", ".join(f"`{f}`" for f in sorted(entry["why"]))
        lines += [
            f"## [{entry['title']}]({entry['url']})",
            "",
            f"**Vendor:** {entry['vendor']} · **Pairs with:** {fams}",
            "",
            entry["what"],
            "",
        ]
        if note := entry.get("note"):
            lines += [note, ""]
        for key, label in HARNESSES.items():
            if key not in entry["harnesses"]:
                continue
            lines += [f"**{label}**", "", "```text", entry["harnesses"][key], "```", ""]
        missing = [HARNESSES[k] for k in HARNESSES if k not in entry["harnesses"]]
        if missing:
            lines += [
                f"Not available on {', '.join(missing)}.",
                "",
            ]
    lines += [
        "## Adding to this page",
        "",
        "The source is [`tools/dev/companion-skills.json`](../../tools/dev/companion-skills.json),",
        "whose header carries the rules an entry has to meet — chiefly that it can say",
        "what it adds to a *named* Magpie family, and that it lists every agent it runs",
        "on with that agent's own install command. Run",
        "`python3 tools/dev/check-companion-skills.py --fix` to regenerate this page and",
        "the blocks in the family READMEs.",
        "",
        END,
        "",
    ]
    return "\n".join(lines)


def check(fix: bool) -> list[str]:
    entries, errors = load()
    if errors:
        return errors

    page = Path("docs/setup/companion-skills.md")
    want_page = reference_page(entries)
    have_page = page.read_text(encoding="utf-8") if page.is_file() else ""
    # Only the generated region is compared: doctoc and the SPDX stamper add
    # their own lines above it on commit, and rewriting those every run would
    # fight them forever.
    if BEGIN in have_page and END in have_page:
        start, end = have_page.index(BEGIN), have_page.index(END) + len(END)
        merged = (
            have_page[:start]
            + want_page[want_page.index(BEGIN) : want_page.index(END) + len(END)]
            + have_page[end:]
        )
    else:
        merged = want_page
    if merged != have_page:
        if fix:
            page.parent.mkdir(parents=True, exist_ok=True)
            page.write_text(merged, encoding="utf-8")
            print(f"{page}: regenerated")
        else:
            errors.append(f"{page}: out of step with {REGISTRY} — run with --fix")

    for family in families():
        readme = docs_readme(family)
        if not readme.is_file():
            errors.append(f"{readme}: missing")
            continue
        body = readme.read_text(encoding="utf-8")
        updated = splice(body, render(family, entries))
        if updated is None:
            errors.append(f"{readme}: no '### Try these first' heading to insert before")
            continue
        if updated == body:
            continue
        if fix:
            readme.write_text(updated, encoding="utf-8")
            print(f"{readme}: regenerated the companion block")
        else:
            errors.append(f"{readme}: out of step with {REGISTRY} — run with --fix")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fix", action="store_true", help="regenerate the page and the blocks")
    parser.add_argument("files", nargs="*", help="(ignored; present for pre-commit)")
    args = parser.parse_args([] if argv is None else argv)

    if not PLUGINS.is_dir():
        print("check-companion-skills: run from the repository root", file=sys.stderr)
        return 2

    errors = check(fix=args.fix)
    if errors:
        print("check-companion-skills: the companion registry is out of step.\n", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    entries, _ = load()
    pairs = sum(len(e["why"]) for e in entries)
    print(f"check-companion-skills: OK ({len(entries)} packages, {pairs} family pairings).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
