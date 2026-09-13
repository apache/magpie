<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Hand-off

The agent bows out and pings a human under any of the four
trigger conditions defined in
[`docs/mentoring/spec.md` § Hand-off protocol](../../../../docs/mentoring/spec.md#hand-off-protocol).
This file gives the runtime: how to detect each trigger and
what the hand-off comment looks like.

---

## When to hand off

| # | Trigger | Detection |
|---|---|---|
| 1 | Thread reached `max_agent_turns`. | Count comments authored by `<viewer>` in the thread. If the count equals `max_agent_turns` and the thread is not yet resolved, the next move is a hand-off, not another draft. Default ceiling is `2`. |
| 2 | Contributor pushed back on a substantive point. | After the agent has answered a why-question once (template 4 in [`comment-templates.md`](comment-templates.md)), the next contributor message that disagrees ("I don't think that applies here", "but in my case…", "that doesn't make sense") triggers hand-off. The skill answers the *why* once; it does not argue. |
| 3 | Topic entered `out_of_scope_topics`. | Re-run the out-of-scope check (step 3 of the runtime loop in [`SKILL.md`](SKILL.md#runtime-loop)) on every new contributor message. If a previously in-scope thread mentions any `out_of_scope_topics` entry (security, deprecation, license, project-specific architecture, etc.), hand off. |
| 4 | Contributor explicitly asked for a human. | Match against "can a maintainer", "can someone from the team", "is anyone there", "can a human", "can a real person", or any request whose subject is the contributor wanting non-agent attention. Always-fires; takes priority over the other three. |

The triggers are checked in order **4 → 3 → 1 → 2** on every
new contributor turn. The first one that fires runs the
hand-off and the skill exits the thread.

---

## Hand-off comment

One template, used for all four triggers. It does **not**
summarise the conversation — the maintainer reads the thread.

Placeholders:

- `<maintainer_team_handle>` — from
  `<project-config>/mentoring-config.md → maintainer_team_handle`.
- `<open_question>` — one short sentence describing what is
  unresolved. The skill drafts this; it must reference the
  thread, not interpret it.
- `<ai_attribution_footer>` — same footer as on regular
  mentoring comments.

```markdown
<maintainer_team_handle> — handing this off: <open_question>

<ai_attribution_footer>
```

The skill prints the rendered hand-off and waits for
maintainer confirmation before posting, the same as for any
regular comment. It does **not** auto-post hand-offs — a
mis-rendered hand-off pings a whole team and the cost of an
unnecessary ping is higher than the cost of a small delay.

After the hand-off posts, the skill records the trigger that
fired (1 / 2 / 3 / 4) and the thread URL in the audit log,
then exits. The skill does not return to the thread on a
later invocation; once handed off, the thread is the
maintainer's.

---

## What the hand-off comment never contains

- A summary of the thread.
- A guess at what the maintainer should do next.
- Apology for handing off ("sorry I couldn't help more").
- A retry offer ("let me know if I can take another look").
- An additional convention pointer or doc link beyond the
  one-line `<open_question>`.

The reason: the maintainer's job in the next message is to
read the thread and answer the contributor in the maintainer's
own voice. Anything the agent adds at hand-off time pre-loads
the maintainer's read of the conversation and is net-negative.
