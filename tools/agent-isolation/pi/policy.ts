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

// Magpie's permission policy for Pi, derived from the Claude Code baseline.
//
// Pi has no approval prompts and no sandbox of its own, so the Magpie
// extension (magpie.ts) supplies both. Its decisions come from this module,
// which reads tools/sandbox-lint/expected.json — the same baseline the Claude
// Code profile is linted against — so the two profiles cannot drift apart.
// It imports nothing from Pi, so `node --test` exercises it on its own.

import { homedir, tmpdir } from "node:os";
import { isAbsolute, join, relative, resolve, sep } from "node:path";

export interface Baseline {
	permissions?: { allow?: string[]; ask?: string[]; deny?: string[] };
	sandbox?: {
		excludedCommands?: string[];
		filesystem?: { denyRead?: string[]; allowRead?: string[]; allowWrite?: string[] };
		network?: { allowedDomains?: string[]; enableWeakerNetworkIsolation?: boolean };
		credentials?: { envVars?: { name: string; mode: string }[] };
	};
}

/** What the extension does with a bash command, most restrictive first. */
export type CommandDecision = "deny" | "ask" | "unsandboxed" | "sandboxed";

/**
 * Pi's own configuration: settings, trust decisions, extensions and project
 * packages. An agent that could write these could widen its own permissions.
 */
export const PI_CONFIG_PATHS = ["~/.pi/agent", ".pi"];

/** A `Bash(...)` rule's pattern as an anchored regex; `*` matches anything. */
function bashPattern(rule: string): RegExp | null {
	const match = /^Bash\((.*)\)$/s.exec(rule);
	if (!match) return null;
	let pattern = match[1];
	// `cmd *` also matches the bare `cmd`, as in Claude Code.
	const trailing = pattern.endsWith(" *");
	if (trailing) pattern = pattern.slice(0, -2);
	const body = pattern
		.split("*")
		.map((part) => part.replace(/[.+?^${}()|[\]\\]/g, "\\$&"))
		.join(".*");
	return new RegExp(`^${body}${trailing ? "( .*)?" : ""}$`, "s");
}

function bashPatterns(rules: string[] | undefined): RegExp[] {
	return (rules ?? []).map(bashPattern).filter((p): p is RegExp => p !== null);
}

/**
 * Split a command line on `&&`, `||`, `;`, `|` and newlines outside quotes.
 * A friction layer, not a shell parser: the guard and the sandbox enforce.
 */
export function segments(command: string): string[] {
	const out: string[] = [];
	let current = "";
	let quote: string | null = null;
	for (let i = 0; i < command.length; i++) {
		const ch = command[i];
		if (quote) {
			if (ch === "\\" && quote === '"' && i + 1 < command.length) {
				current += ch + command[++i];
				continue;
			}
			if (ch === quote) quote = null;
			current += ch;
		} else if (ch === "'" || ch === '"') {
			quote = ch;
			current += ch;
		} else if (ch === ";" || ch === "\n" || ch === "|" || (ch === "&" && command[i + 1] === "&")) {
			if (ch === "&" || (ch === "|" && command[i + 1] === "|")) i++;
			out.push(current);
			current = "";
		} else {
			current += ch;
		}
	}
	out.push(current);
	return out.map((s) => s.trim()).filter((s) => s.length > 0);
}

// Constructs that run or redirect beyond the visible command: such a line
// never leaves the sandbox, whatever its first word.
const SHELL_ESCAPES = /[`<>]|\$\(|\$\{|&\s*$|&[^&]/;

export class Policy {
	readonly baseline: Baseline;
	readonly deny: RegExp[];
	readonly ask: RegExp[];
	readonly allow: RegExp[];
	readonly excluded: RegExp[];

	constructor(baseline: Baseline) {
		this.baseline = baseline;
		const p = baseline.permissions ?? {};
		this.deny = bashPatterns(p.deny);
		this.ask = bashPatterns(p.ask);
		this.allow = bashPatterns(p.allow);
		this.excluded = bashPatterns((baseline.sandbox?.excludedCommands ?? []).map((c) => `Bash(${c})`));
	}

	/** Deny > ask > allow, as in Claude Code; unlisted commands run sandboxed. */
	decide(command: string): CommandDecision {
		const parts = segments(command);
		const any = (patterns: RegExp[]) => parts.some((s) => patterns.some((p) => p.test(s)));
		if (any(this.deny)) return "deny";
		const single = parts.length === 1 && !SHELL_ESCAPES.test(command);
		const excluded = single && this.excluded.some((p) => p.test(parts[0]));
		if (any(this.ask)) return "ask";
		if (!excluded) return "sandboxed";
		// Outside the sandbox only what the baseline allows runs unprompted.
		return this.allow.some((p) => p.test(parts[0])) ? "unsandboxed" : "ask";
	}

	/** Why a native read of `path` is refused, or null. */
	readDenied(path: string, cwd: string): string | null {
		for (const rule of this.baseline.permissions?.deny ?? []) {
			const m = /^Read\((.*)\)$/.exec(rule);
			if (m && pathMatches(m[1], path, cwd)) return `reading ${path} is denied (${rule})`;
		}
		return null;
	}

	/** Why a native write of `path` is refused, or null. */
	writeDenied(path: string, cwd: string): string | null {
		const read = this.readDenied(path, cwd);
		if (read) return read;
		for (const rule of this.baseline.permissions?.deny ?? []) {
			const m = /^Edit\((.*)\)$/.exec(rule);
			if (m && pathMatches(m[1], path, cwd)) return `writing ${path} is denied (${rule})`;
		}
		for (const config of PI_CONFIG_PATHS) {
			if (pathMatches(`${config}/**`, path, cwd)) {
				return `writing ${path} is denied: Pi's configuration must be edited from your own terminal`;
			}
		}
		return null;
	}

	/** The sandbox-runtime configuration for sandboxed bash commands. */
	sandboxConfig(cwd: string) {
		const sb = this.baseline.sandbox ?? {};
		const editDenies = (this.baseline.permissions?.deny ?? [])
			.map((r) => /^Edit\((.*)\)$/.exec(r)?.[1])
			.filter((p): p is string => p !== undefined)
			.map((p) => expandPath(p.replace(/\/\*\*$/, ""), cwd));
		return {
			network: {
				allowedDomains: sb.network?.allowedDomains ?? [],
				deniedDomains: [],
			},
			filesystem: {
				denyRead: (sb.filesystem?.denyRead ?? []).map((p) => expandPath(p, cwd)),
				allowRead: (sb.filesystem?.allowRead ?? []).map((p) => expandPath(p, cwd)),
				allowWrite: [cwd, tmpdir(), "/tmp", ...(sb.filesystem?.allowWrite ?? [])].map((p) => expandPath(p, cwd)),
				denyWrite: [...editDenies, ...PI_CONFIG_PATHS.map((p) => expandPath(p, cwd))],
			},
			credentials: { envVars: sb.credentials?.envVars ?? [] },
			enableWeakerNetworkIsolation: sb.network?.enableWeakerNetworkIsolation,
		};
	}
}

/** `~/x` to the home directory, `//x` to `/x`, a relative path under `cwd`. */
export function expandPath(path: string, cwd: string): string {
	let out: string;
	if (path === "~" || path.startsWith("~/")) out = join(homedir(), path.slice(1));
	else if (path.startsWith("//")) out = path.slice(1);
	else out = isAbsolute(path) ? path : resolve(cwd, path);
	// `~/.cache/` and `~/.cache` name the same directory.
	return out.length > 1 && out.endsWith("/") ? out.slice(0, -1) : out;
}

/** A path glob as an anchored regex: `**\/` any directories, `**` anything, `*` one segment. */
function globRegex(glob: string): RegExp {
	let out = "";
	for (let i = 0; i < glob.length; i++) {
		const ch = glob[i];
		if (ch === "*" && glob[i + 1] === "*") {
			i++;
			if (glob[i + 1] === "/") {
				i++;
				out += "(?:.*/)?";
			} else {
				out += ".*";
			}
		} else if (ch === "*") {
			out += "[^/]*";
		} else {
			out += ch.replace(/[.+?^${}()|[\]\\]/g, "\\$&");
		}
	}
	return new RegExp(`^${out}$`, "s");
}

/** Match a Claude path rule (`~/.ssh/**`, `//**\/.env`, `.claude/x.json`). */
export function pathMatches(rule: string, path: string, cwd: string): boolean {
	const target = resolve(cwd, path === "~" || path.startsWith("~/") ? join(homedir(), path.slice(1)) : path).split(sep).join("/");
	const base = expandPath(rule, cwd).split(sep).join("/");
	if (base.includes("*")) return globRegex(base).test(target);
	const rel = relative(base, target);
	return rel === "" || (!rel.startsWith("..") && !isAbsolute(rel));
}
