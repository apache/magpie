"""Tests for tag_bare_code_fences in inject-knowledge-base.py.

Covers the nested-code-fence regression (#1008): a four-backtick block
containing a bare three-backtick fence must not invert the parser state.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SPEC = importlib.util.spec_from_file_location(
    "inject_knowledge_base", _HERE / "inject-knowledge-base.py"
)
mod = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = mod  # register before exec so @dataclass can resolve the module
_SPEC.loader.exec_module(mod)
tag_bare_code_fences = mod.tag_bare_code_fences


def test_bare_fence_gets_default_language():
    out = tag_bare_code_fences("```\ncode\n```")
    assert out == "```text\ncode\n```"


def test_fence_with_language_is_untouched():
    text = "```python\nprint(1)\n```"
    assert tag_bare_code_fences(text) == text


def test_indentation_preserved():
    out = tag_bare_code_fences("  ```\n  code\n  ```")
    assert out.startswith("  ```text")


def test_nested_four_backtick_block_does_not_invert_state():
    # opening 4-backtick (has language) wraps an inner bare 3-backtick fence;
    # the inner fence is literal content and must be left alone; after the
    # block closes, a later bare 3-backtick fence must still be tagged.
    text = "\n".join(
        [
            "````markdown",
            "```",
            "inner bare fence inside block",
            "````",
            "```",
            "later bare fence",
            "```",
        ]
    )
    out = tag_bare_code_fences(text)
    lines = out.split("\n")
    assert lines[1] == "```", "inner bare fence should be left untouched"
    assert lines[3] == "````", "closing four-backtick fence should be untouched"
    assert lines[4] == "```text", f"later bare fence should be tagged: {lines[4]!r}"
    assert lines[6] == "```", "later closing fence should be untouched"


def test_shorter_fence_inside_block_is_literal():
    # a 3-backtick line inside a 4-backtick block is content, not a close
    out = tag_bare_code_fences("````\n```\n````")
    assert out == "````\n```\n````"


def test_longer_closing_fence_closes_shorter_block():
    # CommonMark: a closing fence with at least as many backticks closes the block.
    out = tag_bare_code_fences("```\ncode\n````\n```")
    lines = out.split("\n")
    assert lines[0] == "```text", "opening bare fence tagged"
    assert lines[2] == "````", "longer fence closes the block"
    assert lines[3] == "```text", "trailing bare fence tagged after close"
