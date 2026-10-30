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

// Magpie's PreToolUse hook for Goose, registered by the root hooks/hooks.json.
//
// Goose hooks can allow or block a tool call, not prompt for it, so the
// prompt comes from Goose itself: `agent-iso goose` runs Goose with
// GOOSE_MODE=approve, which asks before every tool call. This hook supplies
// what approve mode cannot:
//
// - the action guard: every shell command goes to agent-guard (`--goose`);
// - the baseline's deny rules (policy.ts, shared with the Pi extension):
//   denied commands, and file tools on credential paths, `.env` files, agent
//   settings and Goose's own configuration, are blocked in every mode;
// - outside approve mode, nothing to confirm with: commands the baseline
//   asks about, and writes outside the working folder, are blocked too.
//
// The hook reads Goose's event on stdin and blocks with
// {"decision": "block", "reason": ...} on stdout; an empty stdout allows.
// hooks.json sets on_failure: block, so a crash here refuses the tool call.

import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { type Baseline, Policy } from "../pi/policy.ts";
import { GOOSE_CONFIG_PATHS, GOOSE_SECRETS } from "./settings.ts";

const ENGINE = fileURLToPath(new URL("../../agent-guard/src/agent_guard/__init__.py", import.meta.url));
const BASELINE = fileURLToPath(new URL("../../sandbox-lint/expected.json", import.meta.url));

// Goose's developer tools and the argument that names a path.
const READ_TOOLS: Record<string, string> = { tree: "path", analyze: "path", load: "source", read_image: "source" };
const WRITE_TOOLS: Record<string, string> = { write: "path", edit: "path" };

interface GooseEvent {
	event?: string;
	tool_name?: string;
	tool_input?: Record<string, unknown>;
	working_dir?: string;
}

/**
 * Whether a hook payload is plainly another host's. The repository root is
 * also a Claude-format plugin, so Claude Code (`hook_event_name`) or Copilot
 * (`toolName`) may load hooks/hooks.json too; their payloads are left alone.
 * Everything else is treated as Goose's and decided, so an unexpected shape
 * fails closed rather than open.
 */
export function isForeignPayload(payload: unknown): boolean {
	if (typeof payload !== "object" || payload === null) return false;
	const p = payload as Record<string, unknown>;
	return "hook_event_name" in p || "toolName" in p;
}

/** The reason to block this tool call, or null to let Goose (and its approve prompt) decide. */
export function decide(event: GooseEvent, policy: Policy, approving: boolean, guard: (c: string, cwd: string) => string | null): string | null {
	const cwd = typeof event.working_dir === "string" && event.working_dir ? event.working_dir : process.cwd();
	const input = event.tool_input ?? {};
	const name = event.tool_name ?? "";
	if (name === "shell") {
		const command = typeof input.command === "string" ? input.command : "";
		const denied = guard(command, cwd);
		if (denied) return denied;
		const decision = policy.decide(command);
		if (decision === "deny") {
			return "Magpie: this command is denied to protect credentials and external systems; run it from your own terminal if needed";
		}
		// The whole Goose process is sandboxed, so "unsandboxed" (an allowed gh
		// read) needs no prompt here; only what the baseline asks about does.
		if (decision === "ask" && !approving) {
			return "Magpie: this command needs your approval; run Goose through `agent-iso goose` (approve mode) to be asked";
		}
		return null;
	}
	const readArg = READ_TOOLS[name];
	const writeArg = WRITE_TOOLS[name];
	const arg = readArg ?? writeArg;
	if (!arg) return null;
	let path = typeof input[arg] === "string" ? (input[arg] as string) : ".";
	const scheme = /^([a-z][a-z0-9+.-]*):/i.exec(path)?.[1]?.toLowerCase();
	if (scheme && scheme.length > 1) {
		// Only the fetching tools take URLs: a scheme on a write path is refused.
		if (!readArg) return `Magpie: ${name} of ${path} is not allowed: write tools take a file path, not a URL`;
		// A remote page is the sandbox's network allowlist's business; a file
		// URL is a path like any other; anything else is refused outright.
		if (scheme === "http" || scheme === "https") return null;
		if (scheme !== "file") return `Magpie: ${name} of a ${scheme}: source is not allowed`;
		try {
			path = fileURLToPath(path);
		} catch {
			return `Magpie: ${name} of ${path} is not allowed: not a local file URL`;
		}
	}
	for (const secret of GOOSE_SECRETS) {
		if (policy.pathUnder(path, secret, cwd)) return `Magpie: ${path} holds Goose's secrets and cannot be read or written by a tool`;
	}
	if (readArg) {
		const reason = name === "tree" || name === "analyze" ? policy.treeDenied(path, cwd) : policy.readDenied(path, cwd);
		return reason ? `Magpie: ${reason}` : null;
	}
	const reason = policy.writeDenied(path, cwd);
	if (reason) return `Magpie: ${reason}`;
	for (const config of GOOSE_CONFIG_PATHS) {
		if (policy.pathUnder(path, config, cwd)) {
			return `Magpie: writing ${path} is denied: Goose's configuration must be edited from your own terminal`;
		}
	}
	if (!approving && policy.outsideWorkspace(path, cwd)) {
		return `Magpie: writing ${path} outside the working folder needs your approval; run Goose through \`agent-iso goose\` (approve mode) to be asked`;
	}
	return null;
}

function guard(command: string, cwd: string): string | null {
	const result = spawnSync("python3", [ENGINE, "--goose"], { input: JSON.stringify({ command, cwd }), encoding: "utf8" });
	return result.status === 2 ? result.stdout.trim() || "agent-guard denied this command" : null;
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
	const payload: unknown = JSON.parse(readFileSync(0, "utf8") || "{}");
	if (!isForeignPayload(payload)) {
		const event = (typeof payload === "object" && payload !== null ? payload : {}) as GooseEvent;
		const policy = new Policy(JSON.parse(readFileSync(BASELINE, "utf8")) as Baseline);
		const reason = decide(event, policy, process.env.GOOSE_MODE === "approve", guard);
		if (reason) process.stdout.write(`${JSON.stringify({ decision: "block", reason })}\n`);
	}
}
