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

// Run Goose inside sandbox-runtime, in approve mode.
//
// Usage: node launch.ts <goose binary> [goose args...]
// `agent-iso goose` calls this from the installed plugin after stripping the
// environment. It writes the srt settings for the current directory to a
// private temporary file, then runs `srt -s <file> -- <goose> <args>` with
// GOOSE_MODE=approve, so Goose asks before every tool call. It refuses to
// start Goose unsandboxed: a missing runtime is an error, not a fallback.

import { spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { type Baseline, Policy } from "../pi/policy.ts";
import { gooseSandboxSettings } from "./settings.ts";

const PLUGIN = fileURLToPath(new URL("../../../", import.meta.url)).replace(/\/$/, "");
const BASELINE = join(PLUGIN, "tools", "sandbox-lint", "expected.json");
const SRT = join(PLUGIN, "node_modules", "@anthropic-ai", "sandbox-runtime", "dist", "cli.js");

const [goose, ...args] = process.argv.slice(2);
if (!goose) {
	process.stderr.write("usage: launch.ts <goose binary> [goose args...]\n");
	process.exit(64);
}
if (!existsSync(SRT)) {
	process.stderr.write(
		`[goose-iso] sandbox runtime missing at ${SRT}\n` +
			`  install it with: npm ci --omit=dev --legacy-peer-deps --ignore-scripts --prefix ${PLUGIN}\n`,
	);
	process.exit(1);
}

const policy = new Policy(JSON.parse(readFileSync(BASELINE, "utf8")) as Baseline);
const settings = gooseSandboxSettings(policy, process.cwd(), PLUGIN, process.env);
const dir = mkdtempSync(join(tmpdir(), "magpie-goose-"));
const file = join(dir, "srt-settings.json");
writeFileSync(file, JSON.stringify(settings, null, 2), { mode: 0o600 });

process.stderr.write(
	`[goose-iso] sandboxed (srt), GOOSE_MODE=approve; model hosts: ${settings.network.allowedDomains.slice(-3).join(", ")}\n`,
);
const result = spawnSync(process.execPath, [SRT, "-s", file, "--", goose, ...args], {
	stdio: "inherit",
	env: { ...process.env, GOOSE_MODE: "approve" },
});
rmSync(dir, { recursive: true, force: true });
process.exit(result.status ?? 1);
