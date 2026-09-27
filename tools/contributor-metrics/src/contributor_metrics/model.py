# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
"""Data model shared by fetch and score."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any, Literal

Kind = Literal["pr", "issue", "review", "thread", "triage"]
CLASSES = ("P", "R", "C")


@dataclass(frozen=True)
class Item:
    """One countable unit of activity. Never carries comment bodies."""

    id: str
    kind: Kind
    url: str
    thread: str
    created_at: str
    merged: bool = False
    closed_unmerged: bool = False
    substantive: bool = False
    areas: tuple[str, ...] = ()
    pushback_candidate: str = ""  # URL of the maintainer comment that matched a phrase, or ""

    def to_json(self) -> dict[str, Any]:
        d = asdict(self)
        d["areas"] = list(self.areas)
        return d

    @classmethod
    def from_json(cls, d: Mapping[str, Any]) -> Item:
        return cls(**{**d, "areas": tuple(d.get("areas", ()))})


_KEYS: dict[str, tuple[str, float]] = {
    "automated": ("automated_contribution_weight", 0.25),
    "restatement": ("restatement_comment_weight", 0.0),
    "closed": ("closed_after_pushback_weight", 0.0),
    "penalty": ("automated_pushback_penalty", 0.25),
}


@dataclass(frozen=True)
class Weights:
    automated: float = 0.25
    restatement: float = 0.0
    closed: float = 0.0
    penalty: float = 0.25

    @classmethod
    def from_mapping(cls, m: Mapping[str, Any]) -> tuple[Weights, list[str]]:
        """Resolve the four config keys; a bad value falls back to its default with a note."""
        values: dict[str, float] = {}
        notes: list[str] = []
        for attr, (key, default) in _KEYS.items():
            raw = m.get(key)
            if raw is None:
                values[attr] = default
                continue
            try:
                v = float(raw)
            except (TypeError, ValueError):
                notes.append(f"{key}={raw!r} is not a number; using default {default}")
                values[attr] = default
                continue
            if not 0.0 <= v <= 1.0:
                notes.append(f"{key}={v} is outside 0-1; using default {default}")
                values[attr] = default
                continue
            values[attr] = v
        return cls(**values), notes

    def weight_of(self, cls_: str | None) -> float:
        return {"P": self.automated, "R": self.restatement, "C": self.closed}.get(cls_ or "", 1.0)

    def to_json(self) -> dict[str, float]:
        return {key: getattr(self, attr) for attr, (key, _) in _KEYS.items()}
