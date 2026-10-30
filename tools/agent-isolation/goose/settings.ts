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

// The sandbox-runtime (`srt`) settings Goose runs under.
//
// Goose has no sandbox and no way for a hook to wrap a shell command, so the
// whole Goose process runs inside srt, with the Claude baseline's filesystem,
// network and credential rules (policy.ts) plus what Goose itself needs: its
// config, data and state directories, the plugin it runs from, and the model
// provider's API host. Its permission and plugin settings stay read-only, so
// a command cannot switch off approve mode or the hook.

import { readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { expandPath, type Policy, withReal, withSystemReal } from "../pi/policy.ts";

/** Goose's own permission, mode and plugin settings: never writable from inside. */
export const GOOSE_CONFIG_PATHS = [
	"~/.config/goose/config.yaml",
	"~/.config/goose/permission.yaml",
	"~/.config/goose/permissions",
	"~/.config/goose/settings.json",
	"~/.config/goose/settings.local.json",
	"~/.agents/plugins",
	".agents/plugins",
	".config/goose",
	".goose",
];

/** Goose's configuration: readable, never writable from inside. */
const GOOSE_CONFIG = "~/.config/goose";
/** Directories Goose writes during a session (sessions database, logs, caches). */
const GOOSE_STATE = ["~/.local/share/goose", "~/.local/state/goose", "~/.cache/goose"];
/**
 * Goose's file-based secret store. Everything Goose can read, a command it
 * runs can read too, so the provider key comes in through the environment
 * (AGENT_ISO_ALLOW) and this file stays out of the sandbox.
 */
export const GOOSE_SECRETS = ["~/.config/goose/secrets.yaml"];

/** API hosts per GOOSE_PROVIDER, and the variable holding each provider's key. */
const PROVIDERS: Record<string, { hosts: string[]; key?: string }> = {
	anthropic: { hosts: ["api.anthropic.com"], key: "ANTHROPIC_API_KEY" },
	openai: { hosts: ["api.openai.com"], key: "OPENAI_API_KEY" },
	google: { hosts: ["generativelanguage.googleapis.com"], key: "GOOGLE_API_KEY" },
	gemini_cli: { hosts: ["generativelanguage.googleapis.com", "oauth2.googleapis.com"] },
	openrouter: { hosts: ["openrouter.ai"], key: "OPENROUTER_API_KEY" },
	groq: { hosts: ["api.groq.com"], key: "GROQ_API_KEY" },
	xai: { hosts: ["api.x.ai"], key: "XAI_API_KEY" },
	mistral: { hosts: ["api.mistral.ai"], key: "MISTRAL_API_KEY" },
	ollama: { hosts: ["localhost", "127.0.0.1"] },
};
const HOST_VARS = ["OPENAI_HOST", "ANTHROPIC_HOST", "OLLAMA_HOST", "OPENROUTER_HOST", "GOOGLE_HOST"];

function configuredProvider(env: NodeJS.ProcessEnv): string | undefined {
	if (env.GOOSE_PROVIDER) return env.GOOSE_PROVIDER;
	try {
		const config = readFileSync(join(homedir(), ".config", "goose", "config.yaml"), "utf8");
		return /^GOOSE_PROVIDER:\s*["']?([\w.-]+)/m.exec(config)?.[1];
	} catch {
		return undefined;
	}
}

function hostOf(value: string): string | undefined {
	try {
		return new URL(/^[a-z][a-z0-9+.-]*:\/\//i.test(value) ? value : `https://${value}`).hostname;
	} catch {
		return undefined;
	}
}

/** The model provider's API hosts and key variable, from Goose's configuration and the environment. */
export function providerAccess(env: NodeJS.ProcessEnv): { hosts: string[]; keys: string[] } {
	const name = configuredProvider(env);
	const known = name ? PROVIDERS[name] : undefined;
	const hosts = new Set(known?.hosts ?? []);
	for (const v of HOST_VARS) {
		const host = env[v] ? hostOf(env[v] as string) : undefined;
		if (host) hosts.add(host);
	}
	for (const extra of (env.MAGPIE_GOOSE_DOMAINS ?? "").split(/[\s,]+/).filter(Boolean)) hosts.add(extra);
	return { hosts: [...hosts], keys: known?.key ? [known.key] : [] };
}

/** The srt settings for one Goose launch in `cwd`, rooted at the plugin directory `plugin`. */
export function gooseSandboxSettings(policy: Policy, cwd: string, plugin: string, env: NodeJS.ProcessEnv) {
	const base = policy.sandboxConfig(cwd);
	const provider = providerAccess(env);
	const state = GOOSE_STATE.map((p) => expandPath(p, cwd));
	return {
		...base,
		network: {
			...base.network,
			allowedDomains: [...new Set([...base.network.allowedDomains, ...provider.hosts])],
			// A local model (Ollama, an OpenAI-compatible server) listens on loopback.
			allowLocalBinding: provider.hosts.some((h) => h === "localhost" || h === "127.0.0.1"),
		},
		filesystem: {
			...base.filesystem,
			denyRead: withReal([...base.filesystem.denyRead, ...GOOSE_SECRETS.map((p) => expandPath(p, cwd))]),
			allowRead: withSystemReal([...base.filesystem.allowRead, expandPath(GOOSE_CONFIG, cwd), ...state, plugin, expandPath("~/.agents", cwd)]),
			allowWrite: withSystemReal([...base.filesystem.allowWrite, ...state]),
			denyWrite: withReal([
				...base.filesystem.denyWrite,
				plugin,
				expandPath(GOOSE_CONFIG, cwd),
				...GOOSE_CONFIG_PATHS.map((p) => expandPath(p, cwd)),
			]),
		},
		// The provider's key must reach Goose; every other baseline credential stays out.
		credentials: {
			envVars: base.credentials.envVars.filter((v) => !provider.keys.includes(v.name)),
		},
	};
}
