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

// Magpie's secure setup for Pi, as one user-scope extension.
//
// Pi runs every tool call without asking and has no sandbox, so this
// extension supplies the three layers the Claude Code reference setup has:
//
// - the action guard: every bash command goes to Magpie's agent-guard engine
//   (`--pi`) before it runs, and a deny blocks the call;
// - permission rules from the Claude baseline (policy.ts): denied commands
//   are blocked, asked ones need the user's confirmation (and are blocked
//   when there is no UI), and native reads and writes of credential paths,
//   Pi's own configuration and the agent's settings are refused;
// - an OS sandbox for bash, through @anthropic-ai/sandbox-runtime (the engine
//   Claude Code's sandbox uses) with the baseline's filesystem and network
//   rules. If the sandbox cannot start, bash is refused rather than run bare.
//
// It is installed per user, never per repository: `pi install
// git:github.com/apache/magpie` loads it through the root package.json. It
// reads no project configuration, so a repository cannot weaken it.

import { spawn, spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import type { BashOperations, ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { createBashTool } from "@earendil-works/pi-coding-agent";
import { type Baseline, candidates, Policy } from "./policy.ts";

const ENGINE = fileURLToPath(new URL("../../agent-guard/src/agent_guard/__init__.py", import.meta.url));
const BASELINE = fileURLToPath(new URL("../../sandbox-lint/expected.json", import.meta.url));
const FILE_TOOLS: Record<string, "read" | "tree" | "write"> = {
	read: "read",
	grep: "tree",
	find: "tree",
	ls: "tree",
	write: "write",
	edit: "write",
};

/** The guard's deny reason, or null. A missing engine fails open, like every guard adapter. */
function guard(command: string, cwd: string): string | null {
	const result = spawnSync("python3", [ENGINE, "--pi"], {
		input: JSON.stringify({ command, cwd }),
		encoding: "utf8",
	});
	return result.status === 2 ? result.stdout.trim() || "agent-guard denied this command" : null;
}

// Loaded at session start rather than imported, so a missing dependency
// leaves the guard and rules working and refuses bash with a clear reason.
type SandboxRuntime = typeof import("@anthropic-ai/sandbox-runtime").SandboxManager;
let SandboxManager: SandboxRuntime;

function sandboxedOperations(): BashOperations {
	return {
		async exec(command, cwd, { onData, signal, timeout }) {
			const wrapped = await SandboxManager.wrapWithSandbox(command);
			return new Promise((resolvePromise, reject) => {
				const child = spawn("bash", ["-c", wrapped], { cwd, detached: true, stdio: ["ignore", "pipe", "pipe"] });
				const kill = () => {
					try {
						if (child.pid) process.kill(-child.pid, "SIGKILL");
					} catch {
						child.kill("SIGKILL");
					}
				};
				let timedOut = false;
				const timer =
					timeout !== undefined && timeout > 0
						? setTimeout(() => {
								timedOut = true;
								kill();
							}, timeout * 1000)
						: undefined;
				child.stdout?.on("data", onData);
				child.stderr?.on("data", onData);
				signal?.addEventListener("abort", kill, { once: true });
				child.on("error", (err) => {
					if (timer) clearTimeout(timer);
					reject(err);
				});
				child.on("close", (code) => {
					if (timer) clearTimeout(timer);
					signal?.removeEventListener("abort", kill);
					if (signal?.aborted) reject(new Error("aborted"));
					else if (timedOut) reject(new Error(`timeout:${timeout}`));
					else resolvePromise({ exitCode: code });
				});
			});
		},
	};
}

export default function (pi: ExtensionAPI) {
	const policy = new Policy(JSON.parse(readFileSync(BASELINE, "utf8")) as Baseline);
	const cwd = process.cwd();
	const plainBash = createBashTool(cwd);
	const sandboxedBash = createBashTool(cwd, { operations: sandboxedOperations() });
	let sandbox: "starting" | "ready" | string = "starting";

	pi.registerFlag("magpie-no-sandbox", {
		description: "Run bash without Magpie's OS sandbox for this session (the guard and rules still apply)",
		type: "boolean",
		default: false,
	});

	pi.on("session_start", async (_event, ctx) => {
		if (pi.getFlag("magpie-no-sandbox")) {
			sandbox = "disabled by --magpie-no-sandbox";
			if (ctx.hasUI) ctx.ui.notify("Magpie: bash runs without the OS sandbox (--magpie-no-sandbox)", "warning");
			return;
		}
		try {
			SandboxManager = (await import("@anthropic-ai/sandbox-runtime")).SandboxManager;
			await SandboxManager.initialize(policy.sandboxConfig(cwd));
			sandbox = "ready";
		} catch (err) {
			sandbox = `the OS sandbox could not start: ${err instanceof Error ? err.message : String(err)}`;
			if (ctx.hasUI) ctx.ui.notify(`Magpie: ${sandbox}; bash is refused`, "error");
		}
	});

	pi.on("session_shutdown", async () => {
		if (sandbox === "ready") await SandboxManager.reset().catch(() => undefined);
	});

	pi.on("tool_call", async (event, ctx) => {
		const kind = FILE_TOOLS[event.toolName];
		if (kind) {
			const path = typeof event.input.path === "string" ? event.input.path : ".";
			// Resolve once: every check, the prompt and the tool use this target.
			const target = candidates(path, ctx.cwd).at(-1) ?? path;
			const check = { read: policy.readDenied, tree: policy.treeDenied, write: policy.writeDenied }[kind];
			const reason = check.call(policy, path, ctx.cwd) ?? check.call(policy, target, ctx.cwd);
			if (reason) return { block: true, reason: `Magpie: ${reason}` };
			if (kind === "write" && (policy.outsideWorkspace(path, ctx.cwd) || policy.outsideWorkspace(target, ctx.cwd))) {
				if (!ctx.hasUI) {
					return {
						block: true,
						reason: `Magpie: writing ${target} outside the working folder needs your approval, which a non-interactive run cannot give`,
					};
				}
				const shown = target.replace(/[\u0000-\u001f\u007f-\u009f]/g, "?");
				if (!(await ctx.ui.confirm("Magpie: write outside the working folder?", `${event.toolName} ${shown}`))) {
					return { block: true, reason: "Magpie: declined by the user" };
				}
				// A link re-pointed while the prompt was open must not inherit the approval.
				if ((candidates(path, ctx.cwd).at(-1) ?? path) !== target || policy.writeDenied(target, ctx.cwd)) {
					return { block: true, reason: `Magpie: ${path} changed while waiting for approval; retry the write` };
				}
			}
			// Hand the tool the checked target, so a link swapped afterwards cannot redirect it.
			if (typeof event.input.path === "string") event.input.path = target;
			return undefined;
		}
		if (event.toolName !== "bash") return undefined;
		const command = typeof event.input.command === "string" ? event.input.command : "";
		const denied = guard(command, ctx.cwd);
		if (denied) return { block: true, reason: denied };
		const decision = policy.decide(command);
		if (decision === "deny") {
			return { block: true, reason: "Magpie: this command is denied to protect credentials and external systems; run it from your own terminal if needed" };
		}
		if (decision === "ask") {
			if (!ctx.hasUI) return { block: true, reason: "Magpie: this command needs your approval, which a non-interactive run cannot give" };
			if (!(await ctx.ui.confirm("Magpie: allow this command?", command))) {
				return { block: true, reason: "Magpie: declined by the user" };
			}
		}
		if (decision !== "unsandboxed" && sandbox !== "ready" && !String(sandbox).startsWith("disabled")) {
			return { block: true, reason: `Magpie: ${sandbox}; bash is refused rather than run without it` };
		}
		return undefined;
	});

	// The decisions above run first; this only chooses where an approved command runs.
	pi.registerTool({
		...plainBash,
		label: "bash (Magpie sandbox)",
		async execute(id, params, signal, onUpdate, ctx) {
			const outside = sandbox !== "ready" || policy.decide(params.command) === "unsandboxed";
			return (outside ? plainBash : sandboxedBash).execute(id, params, signal, onUpdate, ctx);
		},
	});

	pi.on("user_bash", () => (sandbox === "ready" ? { operations: sandboxedOperations() } : undefined));
}
