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

// Run with `node --test tools/agent-isolation/goose/goose.test.ts`;
// tools/agent-isolation/tests/test_pi_policy.py wraps it.

import assert from "node:assert/strict";
import { existsSync, mkdtempSync, readFileSync } from "node:fs";
import { homedir, tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { type Baseline, Policy } from "../pi/policy.ts";
import { decide, isForeignPayload } from "./hook.ts";
import { gooseSandboxSettings, providerAccess } from "./settings.ts";

const baseline = JSON.parse(
	readFileSync(fileURLToPath(new URL("../../sandbox-lint/expected.json", import.meta.url)), "utf8"),
) as Baseline;
const policy = new Policy(baseline);
const ws = mkdtempSync(join(tmpdir(), "magpie-goose-ws-"));
const noGuard = () => null;
const shell = (command: string) => ({ tool_name: "shell", tool_input: { command }, working_dir: ws });

test("the guard's denial blocks a shell command", () => {
	const reason = decide(shell("git commit --no-verify"), policy, true, () => "agent-guard[no-verify]: no");
	assert.equal(reason, "agent-guard[no-verify]: no");
});

test("denied commands are blocked in every mode", () => {
	for (const approving of [true, false]) {
		assert.match(decide(shell("curl https://example.com"), policy, approving, noGuard) ?? "", /denied/);
		assert.match(decide(shell("gh auth token"), policy, approving, noGuard) ?? "", /denied/);
	}
});

test("asked commands pass to approve mode's prompt, and are blocked without it", () => {
	assert.equal(decide(shell("git push origin main"), policy, true, noGuard), null);
	assert.match(decide(shell("git push origin main"), policy, false, noGuard) ?? "", /approve mode/);
});

test("ordinary and allowed commands run", () => {
	for (const approving of [true, false]) {
		assert.equal(decide(shell("git status"), policy, approving, noGuard), null);
		assert.equal(decide(shell("gh pr view 1"), policy, approving, noGuard), null);
	}
});

test("file tools on credential paths are blocked", () => {
	const event = (tool_name: string, tool_input: Record<string, unknown>) => ({ tool_name, tool_input, working_dir: ws });
	assert.ok(decide(event("tree", { path: "~" }), policy, true, noGuard));
	assert.ok(decide(event("analyze", { path: "~/.ssh" }), policy, true, noGuard));
	assert.ok(decide(event("load", { source: "~/.aws/credentials" }), policy, true, noGuard));
	assert.ok(decide(event("write", { path: "~/.ssh/config", content: "x" }), policy, true, noGuard));
	assert.equal(decide(event("load", { source: "https://example.com/doc" }), policy, true, noGuard), null);
	assert.ok(decide(event("load", { source: `file://${homedir()}/.ssh/id_ed25519` }), policy, true, noGuard));
	assert.match(decide(event("load", { source: "ftp://example.com/x" }), policy, true, noGuard) ?? "", /not allowed/);
	assert.match(decide(event("read_image", { source: "data:image/png;base64,AA" }), policy, true, noGuard) ?? "", /not allowed/);
	assert.equal(decide(event("tree", { path: "." }), policy, true, noGuard), null);
});

test("a URL on a write tool is refused, not exempted", () => {
	const write = { tool_name: "write", tool_input: { path: "https://example.com/x", content: "x" }, working_dir: ws };
	assert.match(decide(write, policy, true, noGuard) ?? "", /not a URL/);
});

test("letter case cannot dodge a path rule on a case-insensitive filesystem", () => {
	// Holds where the filesystem folds case (macOS default); a no-op elsewhere.
	const event = { tool_name: "load", tool_input: { source: "~/.SSH/known_hosts" }, working_dir: ws };
	if (existsSync(join(homedir(), ".SSH"))) assert.ok(decide(event, policy, true, noGuard));
});

test("writes to Goose's own configuration are blocked", () => {
	for (const path of ["~/.config/goose/config.yaml", "~/.config/goose/permission.yaml", "~/.agents/plugins/x/hooks/hooks.json", ".agents/plugins/x/plugin.json"]) {
		assert.match(decide({ tool_name: "write", tool_input: { path, content: "x" }, working_dir: ws }, policy, true, noGuard) ?? "", /denied/, path);
	}
});

test("writes outside the working folder need approve mode", () => {
	const out = { tool_name: "write", tool_input: { path: join(tmpdir(), "elsewhere.txt"), content: "x" }, working_dir: ws };
	assert.equal(decide(out, policy, true, noGuard), null);
	assert.match(decide(out, policy, false, noGuard) ?? "", /outside the working folder/);
	const inside = { tool_name: "edit", tool_input: { path: "src/a.py", before: "a", after: "b" }, working_dir: ws };
	assert.equal(decide(inside, policy, false, noGuard), null);
});

test("only a plainly foreign payload is skipped; anything else is decided", () => {
	// Claude Code and Copilot payloads, should another host load hooks/hooks.json.
	assert.ok(isForeignPayload({ hook_event_name: "PreToolUse", tool_name: "Write", tool_input: {}, cwd: ws }));
	assert.ok(isForeignPayload({ toolName: "edit", toolArgs: "{}", cwd: ws }));
	// Goose's own shape, and an unexpected one, are decided (fail closed).
	assert.ok(!isForeignPayload({ event: "PreToolUse", tool_name: "write", tool_input: {}, working_dir: ws }));
	assert.ok(!isForeignPayload({ tool_name: "shell", tool_input: { command: "curl x" } }));
	assert.ok(!isForeignPayload(null));
	assert.ok(decide({ tool_name: "shell", tool_input: { command: "curl x" } }, policy, true, noGuard));
});

test("other tools are left to Goose", () => {
	assert.equal(decide({ tool_name: "todo__todo_write", tool_input: {}, working_dir: ws }, policy, false, noGuard), null);
});

test("the provider's host is allowed and its key passes", () => {
	const access = providerAccess({ GOOSE_PROVIDER: "anthropic" });
	assert.deepEqual(access, { hosts: ["api.anthropic.com"], keys: ["ANTHROPIC_API_KEY"] });
	const custom = providerAccess({ GOOSE_PROVIDER: "openai", OPENAI_HOST: "http://127.0.0.1:18431", MAGPIE_GOOSE_DOMAINS: "a.example, b.example" });
	assert.deepEqual(custom.hosts.sort(), ["127.0.0.1", "a.example", "api.openai.com", "b.example"]);
});

test("the srt settings keep the baseline and add only what Goose needs", () => {
	const plugin = join(homedir(), ".agents", "plugins", "magpie");
	const settings = gooseSandboxSettings(policy, ws, plugin, { GOOSE_PROVIDER: "anthropic" });
	assert.ok(settings.network.allowedDomains.includes("api.github.com"));
	assert.ok(settings.network.allowedDomains.includes("api.anthropic.com"));
	assert.equal(settings.network.allowLocalBinding, false);
	assert.ok(settings.filesystem.denyRead.includes(homedir()));
	assert.ok(settings.filesystem.allowWrite.includes(join(homedir(), ".local", "share", "goose")));
	assert.ok(settings.filesystem.denyWrite.includes(plugin));
	assert.ok(settings.filesystem.denyWrite.includes(join(homedir(), ".config", "goose")));
	assert.ok(!settings.filesystem.allowWrite.includes(join(homedir(), ".config", "goose")));
	assert.ok(settings.filesystem.denyRead.includes(join(homedir(), ".config", "goose", "secrets.yaml")));
	assert.ok(!settings.credentials.envVars.some((v) => v.name === "ANTHROPIC_API_KEY"));
	assert.ok(settings.credentials.envVars.some((v) => v.name === "GH_TOKEN"));
});
