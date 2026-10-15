# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
"""Issues as files: the contract operations over a descriptor-shaped folder."""

from __future__ import annotations

import datetime as _dt
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from . import metadata as md
from . import sections
from .descriptor import DESCRIPTOR_NAME, Descriptor
from .vcs import WorkingCopy
from .vcs import detect as detect_vcs


class TrackerError(Exception):
    """Carries the contract exit code."""

    def __init__(self, message: str, code: int) -> None:
        super().__init__(message)
        self.code = code


def not_found(message: str) -> TrackerError:
    return TrackerError(message, 3)


def refused(message: str) -> TrackerError:
    return TrackerError(message, 4)


def _today() -> str:
    return _dt.datetime.now(_dt.UTC).strftime("%Y-%m-%d")


def _now() -> str:
    return _dt.datetime.now(_dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug[:48].rstrip("-") or "report"


_SKIP_NAMES = {"readme.md", "index.md", "template.md", "_template.md", "license.md"}


@dataclass
class Entry:
    """Where one issue lives."""

    id: str
    number: int
    path: Path  # the issue markdown file
    container: Path  # folder (folder layout) or the file itself
    state_dir: str  # "" unless state.mode == "directory"


class Tracker:
    def __init__(self, root: Path, desc: Descriptor, wc: WorkingCopy | None = None) -> None:
        self.root = root
        self.desc = desc
        self.wc = wc or detect_vcs(root)

    # ------------------------------------------------------------ locating

    def _bases(self) -> list[tuple[str, Path]]:
        if self.desc.state.mode != "directory":
            return [("", self.root)]
        out = []
        if self.root.is_dir():
            for child in sorted(self.root.iterdir()):
                if child.is_dir() and not child.name.startswith(".") and self._is_state_dir(child.name):
                    out.append((child.name, child))
        names = {name for name, _ in out}
        for name in (self.desc.state.open_dir, self.desc.state.closed_dir):
            if name not in names:
                out.append((name, self.root / name))
        return out

    def _is_state_dir(self, name: str) -> bool:
        st = self.desc.state
        known = {v.lower() for v in [*st.open_values, *st.closed_values, st.open_dir, st.closed_dir]}
        return name.lower() in known

    def _issue_file(self, folder: Path, ident: str) -> Path:
        return folder / self.desc.issue_file.replace("{id}", ident)

    def entries(self) -> list[Entry]:
        rx = self.desc.id.regex()
        out: list[Entry] = []
        for state_dir, base in self._bases():
            if not base.is_dir():
                continue
            for child in sorted(base.iterdir()):
                if child.name.startswith(".") or child.name.lower() in _SKIP_NAMES:
                    continue
                if self.desc.layout == "folder-per-issue":
                    if not child.is_dir():
                        continue
                    m = rx.match(child.name)
                    issue = self._issue_file(child, child.name)
                    if m and issue.is_file():
                        out.append(Entry(child.name, int(m.group("num")), issue, child, state_dir))
                else:
                    if not (child.is_file() and child.suffix == ".md"):
                        continue
                    m = rx.match(child.stem)
                    if m:
                        out.append(Entry(child.stem, int(m.group("num")), child, child, state_dir))
        return out

    def resolve(self, ident: str) -> Entry:
        ident = ident.strip()
        number: int | None = int(ident) if ident.isdigit() else None
        for entry in self.entries():
            if entry.id == ident or (number is not None and entry.number == number):
                return entry
            # A slugged name is also addressable by its bare ID.
            if entry.id.startswith(ident + "-") and self.desc.id.regex().match(ident):
                return entry
        raise not_found(f"no tracker {ident!r} under {self.root}")

    # ------------------------------------------------------------ guards

    def require_writable(self) -> None:
        if not self.desc.access_restricted:
            raise refused(
                f"{self.root / DESCRIPTOR_NAME} does not record access_restricted: true. "
                "The local tracker holds embargoed reports; a human must confirm the repository "
                "is access-restricted (`magpie-local-tracker init|detect --write --access-restricted`) "
                "before anything is written to it."
            )

    # ------------------------------------------------------------ reading

    def _read(self, entry: Entry) -> tuple[md.Metadata, str]:
        return md.split(entry.path.read_text(encoding="utf-8"))

    def _write(self, entry: Entry, meta: md.Metadata, body: str) -> None:
        key = self.desc.keys.get("updated", "")
        if key and (key in meta.values or meta.style != "none"):
            meta.values[key] = _today()
        entry.path.write_text(md.render(meta, body), encoding="utf-8")

    def _split_managed(self, body: str) -> tuple[str, str]:
        """Split off the trailing sections this tool manages inside the issue file."""
        managed = []
        if self.desc.comments_mode == "section":
            managed.append(self.desc.comments_heading)
        if self.desc.rollup_mode == "section":
            managed.append(self.desc.rollup_heading)
        cut = len(body)
        for heading in managed:
            found = sections.find_section(body, heading, 2)
            if found:
                lines = body.split("\n")
                cut = min(cut, len("\n".join(lines[: found[0]])))
        return body[:cut], body[cut:]

    def _title(self, meta: md.Metadata, body: str) -> str:
        if self.desc.title_source == "key":
            key = meta.find_key([self.desc.keys["title"]])
            value = meta.values.get(key) if key else None
            if isinstance(value, str):
                return value
        m = re.search(r"^# (.+)$", body, re.MULTILINE)
        return m.group(1).strip() if m else ""

    def _list(self, meta: md.Metadata, role: str) -> list[str]:
        key = meta.find_key([self.desc.keys.get(role, "")]) if self.desc.keys.get(role) else None
        value = meta.values.get(key) if key else None
        if isinstance(value, list):
            return list(value)
        if isinstance(value, str) and value:
            return [v.strip() for v in value.split(",") if v.strip()]
        return []

    def _scalar(self, meta: md.Metadata, role: str) -> str | None:
        key = meta.find_key([self.desc.keys.get(role, "")]) if self.desc.keys.get(role) else None
        value = meta.values.get(key) if key else None
        if isinstance(value, list):
            return ", ".join(value) or None
        return value

    def _state(self, entry: Entry, meta: md.Metadata) -> tuple[str, str]:
        st = self.desc.state
        closed = {v.lower() for v in st.closed_values}
        if st.mode == "directory":
            raw = entry.state_dir
            return ("closed" if raw.lower() in closed or raw == st.closed_dir else "open"), raw
        raw = self._scalar(meta, "state") or st.open_value
        return ("closed" if raw.lower() in closed else "open"), raw

    def url(self, path: Path) -> str:
        rel = self.wc.rel(path) if self.wc.kind != "none" else path.as_posix()
        return self.desc.url_template.format(path=rel) if self.desc.url_template else rel

    def _comments_text(self, entry: Entry, body: str) -> str:
        if self.desc.comments_mode == "section":
            found = sections.find_section(body, self.desc.comments_heading, 2)
            if not found:
                return ""
            _, start, end = found
            return "\n".join(body.split("\n")[start:end])
        path = self._comments_path(entry)
        return path.read_text(encoding="utf-8") if path.is_file() else ""

    def _comments_path(self, entry: Entry) -> Path:
        if self.desc.layout == "folder-per-issue":
            return entry.container / self.desc.comments_file
        return entry.container.with_name(f"{entry.id}.{self.desc.comments_file}")

    def _rollup_path(self, entry: Entry) -> Path:
        if self.desc.layout == "folder-per-issue":
            return entry.container / self.desc.rollup_file
        return entry.container.with_name(f"{entry.id}.{self.desc.rollup_file}")

    def _attachments_dir(self, entry: Entry) -> Path:
        if self.desc.layout == "folder-per-issue":
            return entry.container / self.desc.attachments_dir
        return entry.container.parent / self.desc.attachments_dir / entry.id

    def summary(self, entry: Entry) -> dict[str, object]:
        meta, body = self._read(entry)
        state, _raw = self._state(entry, meta)
        return {
            "id": entry.id,
            "title": self._title(meta, body),
            "state": state,
            "labels": self._list(meta, "labels"),
            "updated": self._scalar(meta, "updated"),
            "url": self.url(entry.path),
        }

    def view(self, ident: str, with_comments: bool = False) -> dict[str, object]:
        entry = self.resolve(ident)
        meta, body = self._read(entry)
        main, _ = self._split_managed(body)
        state, raw = self._state(entry, meta)
        out: dict[str, object] = {
            "id": entry.id,
            "title": self._title(meta, body),
            "state": state,
            "status": raw,
            "labels": self._list(meta, "labels"),
            "assignees": self._list(meta, "assignees"),
            "milestone": self._scalar(meta, "milestone"),
            "author": self._scalar(meta, "author"),
            "created": self._scalar(meta, "created"),
            "updated": self._scalar(meta, "updated"),
            "body": main.strip("\n") + "\n",
            "url": self.url(entry.path),
            "path": str(entry.path),
        }
        if with_comments:
            out["comments"] = [
                {"id": c.id, "author": c.author, "created": c.created, "body": c.body}
                for c in sections.parse_comments(self._comments_text(entry, body))
            ]
        return out

    def list_issues(
        self, state: str = "open", labels: list[str] | None = None, search: str = "", limit: int = 100
    ) -> list[dict[str, object]]:
        wanted = {lb.lower() for lb in labels or []}
        out = []
        for entry in sorted(self.entries(), key=lambda e: e.number, reverse=True):
            item = self.summary(entry)
            if state != "all" and item["state"] != state:
                continue
            have = {str(lb).lower() for lb in item["labels"]}  # type: ignore[attr-defined]
            if not wanted <= have:
                continue
            if search and search.lower() not in entry.path.read_text(encoding="utf-8").lower():
                continue
            out.append(item)
            if len(out) >= limit:
                break
        return out

    def labels(self) -> list[str]:
        seen: set[str] = set()
        for entry in self.entries():
            meta, _ = self._read(entry)
            seen.update(self._list(meta, "labels"))
        return sorted(seen)

    def field_get(self, ident: str, heading: str) -> dict[str, object]:
        entry = self.resolve(ident)
        _, body = self._read(entry)
        main, _ = self._split_managed(body)
        return {"id": entry.id, "heading": heading, "value": sections.get_field(main, heading)}

    # ------------------------------------------------------------ writing

    def _set(self, meta: md.Metadata, role: str, value: md.Value) -> None:
        key = self.desc.keys.get(role, "")
        if not key:
            return
        meta.values[meta.find_key([key]) or key] = value

    def create(self, title: str, body: str, labels: list[str], author: str = "") -> dict[str, object]:
        self.require_writable()
        title = " ".join(title.split())
        if not title:
            raise TrackerError("the title file is empty", 2)
        number = max((e.number for e in self.entries()), default=0) + 1
        ident = self.desc.id.render(number, slugify(title))
        st = self.desc.state
        base = self.root / st.open_dir if st.mode == "directory" else self.root
        if self.desc.layout == "folder-per-issue":
            container = base / ident
            path = self._issue_file(container, ident)
        else:
            container = path = base / f"{ident}.md"
        if container.exists():
            raise refused(f"{container} already exists")
        meta = md.Metadata(style=self.desc.metadata, list_style=self.desc.list_style)
        if self.desc.metadata == "none":
            meta.style = "none"
        if self.desc.title_source == "key":
            self._set(meta, "title", title)
        self._set(meta, "state", st.open_value)
        self._set(meta, "labels", list(labels))
        self._set(meta, "assignees", [])
        self._set(meta, "milestone", None)
        if author:
            self._set(meta, "author", author)
        self._set(meta, "created", _today())
        self._set(meta, "updated", _today())
        text = body.strip("\n") + "\n"
        if self.desc.title_source == "h1":
            text = f"# {title}\n\n{text}"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(md.render(meta, text), encoding="utf-8")
        return {"id": ident, "url": self.url(path), "path": str(path)}

    def edit(
        self,
        ident: str,
        add_labels: list[str],
        remove_labels: list[str],
        add_assignees: list[str],
        remove_assignees: list[str],
        milestone: str | None,
        clear_milestone: bool,
        title: str | None,
        body: str | None,
    ) -> dict[str, object]:
        self.require_writable()
        entry = self.resolve(ident)
        meta, current = self._read(entry)
        for role, add, remove in (
            ("labels", add_labels, remove_labels),
            ("assignees", add_assignees, remove_assignees),
        ):
            if add or remove:
                values = [v for v in self._list(meta, role) if v.lower() not in {r.lower() for r in remove}]
                values += [a for a in add if a.lower() not in {v.lower() for v in values}]
                self._set(meta, role, values)
        if clear_milestone:
            self._set(meta, "milestone", None)
        elif milestone is not None:
            self._set(meta, "milestone", milestone)
        if title is not None:
            title = " ".join(title.split())
            if self.desc.title_source == "key":
                self._set(meta, "title", title)
            else:
                current = re.sub(r"^# .+$", f"# {title}", current, count=1, flags=re.MULTILINE)
        if body is not None:
            _, managed = self._split_managed(current)
            head = ""
            if self.desc.title_source == "h1":
                m = re.match(r"^# .+\n", current)
                head = m.group(0) + "\n" if m and not body.lstrip().startswith("# ") else ""
            current = head + body.strip("\n") + "\n" + ("\n" + managed.lstrip("\n") if managed else "")
        self._write(entry, meta, current)
        return {"id": entry.id, "url": self.url(entry.path)}

    def field_set(self, ident: str, heading: str, value: str) -> dict[str, object]:
        self.require_writable()
        entry = self.resolve(ident)
        meta, body = self._read(entry)
        main, managed = self._split_managed(body)
        new_main, created = sections.set_field(main, heading, value, self.desc.field_heading_level)
        self._write(entry, meta, new_main + ("\n" + managed.lstrip("\n") if managed else ""))
        return {"id": entry.id, "heading": heading, "created": created}

    def comment(self, ident: str, body: str, author: str) -> dict[str, object]:
        self.require_writable()
        entry = self.resolve(ident)
        meta, text = self._read(entry)
        existing = self._comments_text(entry, text)
        cid = sections.next_comment_id(existing)
        level = 3 if self.desc.comments_mode == "section" else 2
        rendered = sections.render_comment(cid, author or "@unknown", _now(), body, level)
        if self.desc.comments_mode == "section":
            text = sections.append_to_section(text, self.desc.comments_heading, 2, rendered)
            self._write(entry, meta, text)
        else:
            path = self._comments_path(entry)
            prefix = existing.rstrip("\n") + "\n\n" if existing.strip() else f"# Comments on {entry.id}\n\n"
            path.write_text(prefix + rendered, encoding="utf-8")
            self._write(entry, meta, text)
        return {"id": entry.id, "comment_id": cid, "url": self.url(entry.path)}

    def set_state(self, ident: str, closed: bool, reason: str = "completed") -> dict[str, object]:
        self.require_writable()
        entry = self.resolve(ident)
        meta, body = self._read(entry)
        st = self.desc.state
        value = (
            (st.not_planned_value if reason == "not-planned" else st.closed_value)
            if closed
            else st.open_value
        )
        if st.mode == "field":
            self._set(meta, "state", value)
            self._write(entry, meta, body)
            return {"id": entry.id, "state": "closed" if closed else "open"}
        if self.desc.keys.get("state") and meta.find_key([self.desc.keys["state"]]):
            self._set(meta, "state", value)
        self._write(entry, meta, body)
        target_dir = self.root / (st.closed_dir if closed else st.open_dir)
        moves = [entry.container]
        if self.desc.layout == "file-per-issue":
            for extra in (self._comments_path(entry), self._rollup_path(entry), self._attachments_dir(entry)):
                if extra.exists():
                    moves.append(extra)
        for src in moves:
            rel = src.relative_to(entry.container.parent)
            dst = target_dir / rel
            if src.resolve() != dst.resolve():
                self.wc.move(src, dst)
        return {"id": entry.id, "state": "closed" if closed else "open"}

    def _rollup_name(self) -> str:
        return self.wc.top.name if self.wc.kind != "none" else self.root.name

    def _read_rollup(self, entry: Entry) -> tuple[str | None, md.Metadata, str]:
        meta, body = self._read(entry)
        if self.desc.rollup_mode == "section":
            found = sections.find_section(body, self.desc.rollup_heading, 2)
            if not found:
                return None, meta, body
            _, start, end = found
            return "\n".join(body.split("\n")[start:end]).strip("\n"), meta, body
        path = self._rollup_path(entry)
        return (path.read_text(encoding="utf-8") if path.is_file() else None), meta, body

    def _write_rollup(self, entry: Entry, meta: md.Metadata, body: str, rollup: str) -> None:
        if self.desc.rollup_mode == "section":
            found = sections.find_section(body, self.desc.rollup_heading, 2)
            lines = body.split("\n")
            if found:
                _, start, end = found
                body = "\n".join([*lines[:start], "", rollup.strip("\n"), "", *lines[end:]])
            else:
                body = sections.append_to_section(body, self.desc.rollup_heading, 2, rollup)
            self._write(entry, meta, body)
        else:
            self._rollup_path(entry).write_text(rollup, encoding="utf-8")
            self._write(entry, meta, body)

    def rollup_append(self, ident: str, action: str, body: str, user: str, now: str) -> dict[str, object]:
        self.require_writable()
        entry = self.resolve(ident)
        existing, meta, text = self._read_rollup(entry)
        entry_text = sections.render_entry(now[:10], user, action, body)
        self._write_rollup(
            entry, meta, text, sections.rollup_append(existing, self._rollup_name(), entry_text)
        )
        return {"id": entry.id, "url": self.url(self._rollup_target(entry))}

    def rollup_amend_latest(self, ident: str, action: str, body: str) -> dict[str, object]:
        self.require_writable()
        entry = self.resolve(ident)
        existing, meta, text = self._read_rollup(entry)
        amended = sections.rollup_amend_latest(existing or "", action, body)
        if amended is None:
            raise refused(
                f"the latest rollup entry on {entry.id} is not a {action!r} entry; refusing to amend"
            )
        self._write_rollup(entry, meta, text, amended)
        return {"id": entry.id, "url": self.url(self._rollup_target(entry))}

    def _rollup_target(self, entry: Entry) -> Path:
        return entry.path if self.desc.rollup_mode == "section" else self._rollup_path(entry)

    def attach(self, ident: str, source: Path, name: str | None) -> dict[str, object]:
        self.require_writable()
        entry = self.resolve(ident)
        if not source.is_file():
            raise not_found(f"{source} is not a file")
        safe = Path(name or source.name).name
        if safe in ("", ".", ".."):
            raise TrackerError("invalid attachment name", 2)
        target = self._attachments_dir(entry) / safe
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        return {"id": entry.id, "name": safe, "url": self.url(target)}
