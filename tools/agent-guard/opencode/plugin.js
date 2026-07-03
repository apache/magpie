// Licensed to the Apache Software Foundation (ASF) under one
// or more contributor license agreements.  See the NOTICE file
// distributed with this work for additional information
// regarding copyright ownership.  The ASF licenses this file
// to you under the Apache License, Version 2.0 (the
// "License"); you may not use this file except in compliance
// with the License.  You may obtain a copy of the License at
//
//   http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing,
// software distributed under the License is distributed on an
// "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
// KIND, either express or implied.  See the License for the
// specific language governing permissions and limitations
// under the License.

// agent-guard for OpenCode.
//
// This is the OpenCode counterpart of the Claude Code `PreToolUse` hook: it
// registers on OpenCode's `tool.execute.before` hook, inspects every `bash`
// command *before it runs*, and blocks the ones a framework guard denies by
// throwing — OpenCode aborts a tool call whose `tool.execute.before` handler
// throws, and surfaces the message to the model, mirroring a Claude deny.
//
// The guard *decisions* are not reimplemented here. This plugin is a thin
// adapter that forwards the command to the very same Python engine the Claude
// hook uses (`agent-guard.py --opencode`), so both harnesses enforce an
// identical rule set from one source of truth. Exit code 2 = deny (reason on
// stdout); anything else = allow (fail-open, exactly like the Claude path, so a
// guard glitch never wedges the session).
//
// Wiring: drop this file in `.opencode/plugin/` (project) or
// `~/.config/opencode/plugin/` (global). Point it at the engine with
// `MAGPIE_AGENT_GUARD=/abs/path/to/agent-guard.py`; it otherwise defaults to
// the adopter tree's `.claude/hooks/agent-guard.py`, so a repo already set up
// for Claude Code needs no extra copy of the script.

import { spawnSync } from "node:child_process";
import { join } from "node:path";

/** @type {import("@opencode-ai/plugin").Plugin} */
export const AgentGuardPlugin = async ({ worktree }) => {
  const engine =
    process.env.MAGPIE_AGENT_GUARD ||
    join(worktree ?? process.cwd(), ".claude", "hooks", "agent-guard.py");

  return {
    "tool.execute.before": async (input, output) => {
      if (input.tool !== "bash") return;
      const command = output?.args?.command;
      if (!command) return;

      const result = spawnSync("python3", [engine, "--opencode"], {
        input: JSON.stringify({ command, cwd: worktree }),
        encoding: "utf8",
      });

      // 2 = deny (reason printed to stdout). Any other status — success, a
      // missing engine, a Python error — is treated as allow so the guard can
      // never hard-block the user on its own failure.
      if (result.status === 2) {
        throw new Error(
          result.stdout.trim() || "agent-guard denied this command",
        );
      }
    },
  };
};
