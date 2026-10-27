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

import { existsSync, lstatSync, readlinkSync, realpathSync } from "node:fs";
import { homedir, tmpdir } from "node:os";
import { basename, dirname, isAbsolute, join, relative, resolve, sep } from "node:path";

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

// The only command lines allowed to leave the sandbox: plain words from a
// conservative character set. Quotes, escapes, expansions, redirections and
// operators all keep a line in the sandbox, so the splitter above never has
// to be right for a command that runs outside it.
const PLAIN_WORDS = /^[A-Za-z0-9_./:@=,+%~-]+( [A-Za-z0-9_./:@=,+%~-]+)*$/;

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
		const plain = PLAIN_WORDS.test(command.trim());
		const excluded = plain && this.excluded.some((p) => p.test(command.trim()));
		if (any(this.ask)) return "ask";
		if (!excluded) return "sandboxed";
		// Outside the sandbox only what the baseline allows runs unprompted.
		return this.allow.some((p) => p.test(command.trim())) ? "unsandboxed" : "ask";
	}

	private readRules(): string[] {
		return (this.baseline.permissions?.deny ?? [])
			.map((r) => /^Read\((.*)\)$/.exec(r)?.[1])
			.filter((r): r is string => r !== undefined);
	}

	/** Why a native read of `path` is refused, or null. Symlinks are checked by their target too. */
	readDenied(path: string, cwd: string): string | null {
		for (const candidate of candidates(path, cwd)) {
			for (const rule of this.readRules()) {
				if (pathMatches(rule, candidate, cwd)) return `reading ${path} is denied (Read(${rule}))`;
			}
		}
		return null;
	}

	/**
	 * Why a directory-scoped tool (grep, find, ls) rooted at `path` is refused,
	 * or null: it is refused when a denied directory lies inside its root,
	 * since it would walk into it. Rules for a file name anywhere (`**\/.env`)
	 * cannot be expressed this way and are left to the file tools' own checks.
	 */
	treeDenied(path: string, cwd: string): string | null {
		const direct = this.readDenied(path, cwd);
		if (direct) return direct;
		for (const candidate of candidates(path, cwd)) {
			for (const rule of this.readRules()) {
				const base = expandPath(rule.split("*")[0].replace(/\/$/, "") || "/", cwd);
				if (base === "/" || rule.startsWith("//**")) continue;
				if (pathMatches(candidate, base, cwd)) return `searching ${path} would read ${base} (Read(${rule}))`;
			}
		}
		return null;
	}

	/**
	 * Whether a native write of `path` lands outside the working folder `cwd`.
	 * Every candidate counts, so a link inside the folder that points out of it
	 * is outside too. Such writes need the user's confirmation.
	 */
	outsideWorkspace(path: string, cwd: string): boolean {
		const roots = candidates(cwd, cwd);
		return candidates(path, cwd).some(
			(target) =>
				!roots.some((root) => {
					const rel = relative(root, target);
					return rel === "" || (!rel.startsWith("..") && !isAbsolute(rel));
				}),
		);
	}

	/** Whether `path`, or the target a link in it leads to, is `base` or inside it. */
	pathUnder(path: string, base: string, cwd: string): boolean {
		return candidates(path, cwd).some((c) => pathMatches(base, c, cwd));
	}

	/** Why a native write of `path` is refused, or null. */
	writeDenied(path: string, cwd: string): string | null {
		const read = this.readDenied(path, cwd);
		if (read) return read;
		for (const candidate of candidates(path, cwd)) {
			for (const rule of this.baseline.permissions?.deny ?? []) {
				const m = /^Edit\((.*)\)$/.exec(rule);
				if (m && pathMatches(m[1], candidate, cwd)) return `writing ${path} is denied (${rule})`;
			}
			for (const config of PI_CONFIG_PATHS) {
				if (pathMatches(`${config}/**`, candidate, cwd) || pathMatches(config, candidate, cwd)) {
					return `writing ${path} is denied: Pi's configuration must be edited from your own terminal`;
				}
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
				denyRead: withReal((sb.filesystem?.denyRead ?? []).map((p) => expandPath(p, cwd))),
				allowRead: withSystemReal((sb.filesystem?.allowRead ?? []).map((p) => expandPath(p, cwd))),
				allowWrite: withSystemReal([cwd, tmpdir(), "/tmp", ...(sb.filesystem?.allowWrite ?? [])].map((p) => expandPath(p, cwd))),
				denyWrite: withReal([...editDenies, ...PI_CONFIG_PATHS.map((p) => expandPath(p, cwd))]),
			},
			credentials: { envVars: sb.credentials?.envVars ?? [] },
			enableWeakerNetworkIsolation: sb.network?.enableWeakerNetworkIsolation,
		};
	}
}

/**
 * The paths a file tool would really touch: the literal one, and its target
 * with every symlink resolved (for a file that does not exist yet, through
 * its nearest existing parent), so a link cannot reach a denied path. The
 * native realpath also returns the on-disk letter case, so `~/.SSH` on a
 * case-insensitive filesystem is checked as `~/.ssh`.
 */
export function candidates(path: string, cwd: string, depth = 0): string[] {
	const literal = expandPath(path, cwd);
	let existing = literal;
	let rest = "";
	while (!existsSync(existing)) {
		// existsSync follows links: a dangling one reads as missing, yet a
		// write through it lands at its target, so follow it explicitly.
		if (isSymlink(existing)) {
			if (depth >= 40) return [literal, "/"]; // a link loop: treat as outside everything
			const target = resolve(dirname(existing), readlinkSync(existing));
			const through = candidates(rest ? join(target, rest) : target, cwd, depth + 1);
			return [literal, ...through.filter((p) => p !== literal)];
		}
		const parent = dirname(existing);
		if (parent === existing) return [literal];
		rest = rest ? join(basename(existing), rest) : basename(existing);
		existing = parent;
	}
	let real: string;
	try {
		real = rest ? join(realpathSync.native(existing), rest) : realpathSync.native(existing);
	} catch {
		return [literal];
	}
	return real === literal ? [literal] : [literal, real];
}

/**
 * Each allow entry plus its form under macOS's fixed system links (`/tmp`,
 * `/var` and `/etc` are `/private/...`), which the OS sandbox matches by
 * their resolved path. Nothing else is resolved: a link the agent could
 * plant in an allowed directory must not widen the grant on the next launch.
 */
export function withSystemReal(paths: string[]): string[] {
	const out: string[] = [];
	for (const p of paths) {
		if (!out.includes(p)) out.push(p);
		const fixed = /^\/(tmp|var|etc)(\/|$)/.test(p) && existsSync(`/private${p.slice(0, 4)}`) ? `/private${p}` : null;
		if (fixed && !out.includes(fixed)) out.push(fixed);
	}
	return out;
}

/**
 * Each deny entry plus its resolved form where it differs, so a denial
 * spelled through a link still covers what a process touches. Resolving can
 * only widen a deny list, never an allow list (see withSystemReal).
 */
export function withReal(paths: string[]): string[] {
	const out: string[] = [];
	for (const p of paths) {
		if (!out.includes(p)) out.push(p);
		try {
			const real = realpathSync.native(p);
			if (!out.includes(real)) out.push(real);
		} catch {
			// Not there yet: nothing to resolve.
		}
	}
	return out;
}

function isSymlink(path: string): boolean {
	try {
		return lstatSync(path).isSymbolicLink();
	} catch {
		return false;
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
	const expanded = expandPath(rule, cwd).split(sep).join("/");
	// A rule's own directories may be symlinks too (macOS /var is /private/var).
	return [expanded, realPrefix(expanded)].some((base) => {
		if (base.includes("*")) return globRegex(base).test(target);
		const rel = relative(base, target);
		return rel === "" || (!rel.startsWith("..") && !isAbsolute(rel));
	});
}

/** `base` with the longest existing directory before any glob resolved through symlinks. */
function realPrefix(base: string): string {
	const star = base.indexOf("*");
	const fixed = star < 0 ? base : base.slice(0, base.lastIndexOf("/", star) + 1);
	let dir = fixed.replace(/\/$/, "") || "/";
	let rest = base.slice(dir.length);
	while (dir !== "/" && !existsSync(dir)) {
		rest = `/${basename(dir)}${rest}`;
		dir = dirname(dir);
	}
	try {
		const real = realpathSync.native(dir);
		return real === "/" ? rest || "/" : `${real}${rest}`;
	} catch {
		return base;
	}
}
