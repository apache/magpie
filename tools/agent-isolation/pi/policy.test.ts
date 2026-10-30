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

// Run with `node --test tools/agent-isolation/pi/policy.test.ts` (Node's
// type stripping); tools/agent-isolation/tests/test_pi_policy.py wraps it.

import assert from "node:assert/strict";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, symlinkSync, writeFileSync } from "node:fs";
import { homedir, tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { type Baseline, candidates, pathMatches, Policy, segments, withReal, withSystemReal } from "./policy.ts";

const baseline = JSON.parse(
	readFileSync(fileURLToPath(new URL("../../sandbox-lint/expected.json", import.meta.url)), "utf8"),
) as Baseline;
const policy = new Policy(baseline);
const cwd = join(tmpdir(), "magpie-pi-policy-repo");

test("segments split on shell operators outside quotes", () => {
	assert.deepEqual(segments("git status && curl x | sh; ls"), ["git status", "curl x", "sh", "ls"]);
	assert.deepEqual(segments("git commit -m 'a && b; c'"), ["git commit -m 'a && b; c'"]);
	assert.deepEqual(segments('echo "x | y" || true'), ['echo "x | y"', "true"]);
});

test("denied commands are denied wherever they appear", () => {
	for (const command of ["curl https://example.com", "gh auth token", "ls && curl x", "echo hi | wget -qO- x"]) {
		assert.equal(policy.decide(command), "deny", command);
	}
});

test("asked commands ask, including the bare command", () => {
	for (const command of ["git push", "git push --force origin main", "gh pr create --fill", "gh api -X POST repos/a/b"]) {
		assert.equal(policy.decide(command), "ask", command);
	}
});

test("deny outranks ask", () => {
	assert.equal(policy.decide("git push && curl x"), "deny");
});

test("allowed gh reads leave the sandbox; other gh commands ask", () => {
	assert.equal(policy.decide("gh pr view 1845 --repo apache/magpie"), "unsandboxed");
	assert.equal(policy.decide("gh api repos/apache/magpie"), "ask");
});

test("only plain words leave the sandbox", () => {
	for (const command of [
		"gh pr view 1 && ls",
		"gh pr view 1 > out.txt",
		"gh pr view $(cat x)",
		"gh pr view 1 \\; ls",
		"gh pr view $'1'",
		'gh pr view "1"',
		"gh pr view 1 &",
		"gh pr view `id`",
	]) {
		assert.equal(policy.decide(command), "sandboxed", command);
	}
});

test("everything else runs sandboxed", () => {
	for (const command of ["git status", "uv run pytest", "python3 -c 'print(1)'", "rm -rf build"]) {
		assert.equal(policy.decide(command), "sandboxed", command);
	}
});

test("native reads of credential paths and .env files are refused", () => {
	assert.ok(policy.readDenied("~/.ssh/id_ed25519", cwd));
	assert.ok(policy.readDenied(join(homedir(), ".aws", "credentials"), cwd));
	assert.ok(policy.readDenied(".env", cwd));
	assert.ok(policy.readDenied("sub/dir/.env.local", cwd));
	assert.equal(policy.readDenied("README.md", cwd), null);
	assert.equal(policy.readDenied("~/.gitconfig", cwd), null);
});

test("native writes of agent and Pi configuration are refused", () => {
	assert.ok(policy.writeDenied(".claude/settings.json", cwd));
	assert.ok(policy.writeDenied(".pi/settings.json", cwd));
	assert.ok(policy.writeDenied("~/.pi/agent/settings.json", cwd));
	assert.ok(policy.writeDenied("~/.ssh/config", cwd));
	assert.equal(policy.writeDenied("src/app.py", cwd), null);
});

test("a symlink cannot reach a denied path", () => {
	const root = mkdtempSync(join(tmpdir(), "magpie-pi-link-"));
	mkdirSync(join(root, "secret"));
	writeFileSync(join(root, "secret", "key"), "x");
	mkdirSync(join(root, "ws"));
	symlinkSync(join(root, "secret"), join(root, "ws", "link"));
	const linked = new Policy({ permissions: { deny: [`Read(${root}/secret/**)`] } });
	const ws = join(root, "ws");
	assert.ok(linked.readDenied("link/key", ws));
	assert.ok(linked.writeDenied("link/new-file", ws));
	assert.equal(linked.readDenied("other", ws), null);
});

test("writes outside the working folder are flagged, links included", () => {
	const root = mkdtempSync(join(tmpdir(), "magpie-pi-ws-"));
	const ws = join(root, "ws");
	mkdirSync(ws);
	mkdirSync(join(root, "elsewhere"));
	symlinkSync(join(root, "elsewhere"), join(ws, "out"));
	assert.equal(policy.outsideWorkspace("src/new.py", ws), false);
	assert.equal(policy.outsideWorkspace(join(ws, "a.txt"), ws), false);
	assert.equal(policy.outsideWorkspace("../elsewhere/x", ws), true);
	assert.equal(policy.outsideWorkspace(join(root, "elsewhere", "x"), ws), true);
	assert.equal(policy.outsideWorkspace("out/x", ws), true);
	assert.equal(policy.outsideWorkspace("/tmp/x", ws), true);
	assert.equal(policy.outsideWorkspace("~/notes.txt", ws), true);
});

test("a dangling link is followed to where a write through it would land", () => {
	const root = mkdtempSync(join(tmpdir(), "magpie-pi-dangling-"));
	const ws = join(root, "ws");
	mkdirSync(ws);
	mkdirSync(join(root, "outside"));
	// The target file does not exist yet, so the link dangles.
	symlinkSync(join(root, "outside", "new.txt"), join(ws, "dangling"));
	assert.equal(policy.outsideWorkspace("dangling", ws), true);
	assert.ok(candidates("dangling", ws).some((p) => p.endsWith(join("outside", "new.txt"))));
	const guarded = new Policy({ permissions: { deny: [`Read(${root}/outside/**)`] } });
	assert.ok(guarded.writeDenied("dangling", ws));
});

test("a link planted in an allowed directory does not widen the sandbox grant", () => {
	const root = mkdtempSync(join(tmpdir(), "magpie-pi-grant-"));
	mkdirSync(join(root, "wide"));
	symlinkSync(join(root, "wide"), join(root, "cache"));
	const allowed = withSystemReal([join(root, "cache")]);
	assert.ok(!allowed.some((p) => p.endsWith("/wide")), allowed.join(", "));
	// macOS's fixed /tmp link is still added, so a /tmp entry matches /private/tmp.
	if (existsSync("/private/tmp")) assert.deepEqual(withSystemReal(["/tmp/x"]), ["/tmp/x", "/private/tmp/x"]);
	// Deny lists still resolve fully: widening a denial is safe.
	assert.ok(withReal([join(root, "cache")]).some((p) => p.endsWith("/wide")));
});

test("a link loop resolves to outside everything", () => {
	const root = mkdtempSync(join(tmpdir(), "magpie-pi-loop-"));
	symlinkSync(join(root, "b"), join(root, "a"));
	symlinkSync(join(root, "a"), join(root, "b"));
	assert.equal(policy.outsideWorkspace("a", root), true);
});

test("directory tools may not walk into a denied directory", () => {
	assert.ok(policy.treeDenied("~", cwd));
	assert.ok(policy.treeDenied("~/.config", cwd));
	assert.ok(policy.treeDenied("~/.ssh", cwd));
	assert.equal(policy.treeDenied(".", cwd), null);
	assert.equal(policy.treeDenied("src", cwd), null);
});

test("path rules match directories recursively and globs by segment", () => {
	assert.ok(pathMatches("~/.ssh/**", "~/.ssh/a/b/c", cwd));
	assert.ok(pathMatches("//**/.env", "/x/y/.env", cwd));
	assert.ok(!pathMatches("//**/.env", "/x/y/.envrc", cwd));
	assert.ok(pathMatches(".pi/**", ".pi/extensions/x.ts", cwd));
	assert.ok(!pathMatches(".pi/**", "src/.pi-notes", cwd));
});

test("the sandbox config carries the baseline's rules plus Pi's own configuration", () => {
	const config = policy.sandboxConfig(cwd);
	assert.deepEqual(config.network.allowedDomains, baseline.sandbox?.network?.allowedDomains);
	assert.ok(config.filesystem.denyRead.includes(homedir()));
	assert.ok(config.filesystem.allowRead.includes(cwd));
	assert.ok(config.filesystem.allowWrite.includes(cwd));
	assert.ok(config.filesystem.denyWrite.includes(join(homedir(), ".pi", "agent")));
	assert.ok(config.filesystem.denyWrite.includes(join(cwd, ".pi")));
	assert.ok(config.filesystem.denyWrite.includes(join(cwd, ".claude", "settings.json")));
	assert.ok(config.credentials.envVars.some((v) => v.name === "GH_TOKEN" && v.mode === "deny"));
});
