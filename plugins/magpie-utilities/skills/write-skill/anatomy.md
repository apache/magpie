<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# What a skill is made of

Read this once, when the shape is unfamiliar. Step 3's scaffolding
script produces it for you.

## The three loading levels

This is the reason to keep a body short, and the rule that decides where
any given paragraph belongs.

1. **`name`, `description`, `when_to_use`** are always in context, for
   every skill at once, so the agent can match a request to a skill.
   Keep them to a couple of lines.
2. **The `SKILL.md` body** loads when the skill triggers. Everything
   here is paid for on every invocation, whether or not the run needs
   it.
3. **Sibling files and `scripts/`** load only when a step says to read
   them. Scripts never enter the context at all.

So: a rule that must bind on every run belongs in the body. Anything a
run needs only sometimes — a schema, a table, a catalogue, a rationale —
belongs in a sibling the body points at.

## The directory

```text
skills/<skill-name>/
├── SKILL.md              required
│   ├── frontmatter       name (= directory name), description,
│   │                     when_to_use, capability, license: Apache-2.0
│   ├── SPDX + placeholder-convention comments
│   ├── # <skill-name>
│   ├── ## Inputs         usually
│   ├── ## Prerequisites  usually
│   ├── ## Step 1..N      the skill's own logic
│   ├── ## Hard rules
│   └── ## References
├── <detail>.md           load-on-demand prose
├── scripts/              deterministic helpers
└── assets/               output templates
```

`capability` takes one value, or a YAML list when a skill genuinely
spans phases. The values are in
[`docs/labels-and-capabilities.md`](../../../../docs/labels-and-capabilities.md).

The pre-flight block every skill carries is generated, not written: it
is propagated from one source by `tools/dev/check-shared-blocks.py`, and
hand-editing a copy is reverted on the next run.
