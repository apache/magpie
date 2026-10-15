# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
"""The format descriptor: how one tracker folder lays out its reports.

``detect`` writes it once, from the reports already in the folder (or the
default below when there are none); every other operation reads it, so the
tool writes new reports exactly the way the team already does. It lives at
``<root>/.magpie-tracker.json`` and is committed with the reports, which keeps
everyone on the team writing the same shape.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

DESCRIPTOR_NAME = ".magpie-tracker.json"
SCHEMA_VERSION = 1


@dataclass
class IdFormat:
    prefix: str = "SEC-"
    width: int = 4
    # Existing names like ``2024-007-xss-in-login`` carry a slug after the
    # number; new reports then get one too, derived from the title.
    slug: bool = False

    def regex(self) -> re.Pattern[str]:
        return re.compile("^" + re.escape(self.prefix) + r"(?P<num>\d+)(?:-(?P<slug>[A-Za-z0-9-]+))?$")

    def render(self, number: int, slug: str = "") -> str:
        base = f"{self.prefix}{number:0{self.width}d}"
        return f"{base}-{slug}" if self.slug and slug else base


@dataclass
class StateFormat:
    # ``field``: a metadata key holds the state. ``directory``: the report sits
    # in a sub-folder per state (``open/``, ``closed/``) and moving it is the
    # state change.
    mode: str = "field"
    open_value: str = "open"
    closed_value: str = "closed"
    not_planned_value: str = "closed"
    open_values: list[str] = field(default_factory=lambda: ["open"])
    closed_values: list[str] = field(default_factory=lambda: ["closed"])
    open_dir: str = "open"
    closed_dir: str = "closed"


@dataclass
class Descriptor:
    version: int = SCHEMA_VERSION
    # ``folder-per-issue``: <root>/<ID>/<issue_file>. ``file-per-issue``: <root>/<ID>.md.
    layout: str = "folder-per-issue"
    issue_file: str = "issue.md"
    metadata: str = "front-matter"
    list_style: str = "inline"
    # role -> the concrete metadata key. A role whose key is ``""`` is not
    # stored (e.g. no ``milestone`` in a team's reports).
    keys: dict[str, str] = field(
        default_factory=lambda: {
            "title": "title",
            "state": "state",
            "labels": "labels",
            "assignees": "assignees",
            "milestone": "milestone",
            "author": "reporter",
            "created": "created",
            "updated": "updated",
        }
    )
    # ``key`` (metadata) or ``h1`` (first ``# `` heading of the body).
    title_source: str = "key"
    field_heading_level: int = 3
    id: IdFormat = field(default_factory=IdFormat)
    state: StateFormat = field(default_factory=StateFormat)
    # ``file``: <ID>/comments.md. ``section``: a heading inside the issue file.
    comments_mode: str = "file"
    comments_file: str = "comments.md"
    comments_heading: str = "Comments"
    rollup_mode: str = "file"
    rollup_file: str = "status-rollup.md"
    rollup_heading: str = "Status rollup"
    attachments_dir: str = "attachments"
    # Optional URL to browse a report, ``{path}`` = path relative to the
    # repository root (e.g. a private ViewVC / gitweb URL).
    url_template: str = ""
    # Set only by a human, through `init|detect --write --access-restricted`,
    # after checking who can read the repository. Every write refuses while it
    # is false: the folder holds embargoed vulnerability reports.
    access_restricted: bool = False
    access_note: str = ""
    notes: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=False) + "\n"

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Descriptor:
        raw = dict(data)
        id_raw = raw.pop("id", {}) or {}
        state_raw = raw.pop("state", {}) or {}
        known = set(cls.__dataclass_fields__)
        desc = cls(**{k: v for k, v in raw.items() if k in known})  # type: ignore[arg-type]
        if isinstance(id_raw, dict):
            desc.id = IdFormat(**{k: v for k, v in id_raw.items() if k in IdFormat.__dataclass_fields__})
        if isinstance(state_raw, dict):
            desc.state = StateFormat(
                **{k: v for k, v in state_raw.items() if k in StateFormat.__dataclass_fields__}
            )
        default_keys = Descriptor().keys
        desc.keys = {**default_keys, **desc.keys}
        return desc


def load(root: Path) -> Descriptor:
    path = root / DESCRIPTOR_NAME
    if not path.is_file():
        raise FileNotFoundError(
            f"{path} not found — run `magpie-local-tracker detect --write` (or `init`) first"
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return Descriptor.from_dict(data)


def save(root: Path, desc: Descriptor) -> Path:
    path = root / DESCRIPTOR_NAME
    path.write_text(desc.to_json(), encoding="utf-8")
    return path
