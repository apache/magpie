// SPDX-License-Identifier: Apache-2.0
// https://www.apache.org/licenses/LICENSE-2.0

// Node helper for test_gemini_runtime.py against Gemini 0.59.0's own APIs.
// No model invocation, authentication, user-config writes, or real credentials.
// See the pytest entry points and opt-in environment variables in test_gemini_runtime.py.
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const bundle = path.resolve(process.argv[2]);
const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../../..');
const pkg = JSON.parse(fs.readFileSync(path.join(bundle, '../package.json'), 'utf8'));
assert.equal(pkg.version, '0.59.0', 'Revalidate bundle API assumptions before testing another version');
// Resolve imports from the installed entry point: old hashed chunks can remain
// after an upgrade, so directory order must not select the runtime under test.
const entry = fs.readFileSync(path.join(bundle, 'gemini.js'), 'utf8');
const coreFile = entry.match(/import\("\.\/(dist-[^"]+\.js)"\)/)?.[1];
const cliFile = entry.match(/import\("\.\/(gemini-[^"]+\.js)"\)/)?.[1];
assert.ok(coreFile && cliFile, 'Revalidate the Gemini entry point imports');
const cliSource = fs.readFileSync(path.join(bundle, cliFile), 'utf8');
const settingsFile = [...cliSource.matchAll(/import\s*\{([^}]+)\}\s*from\s*"\.\/([^"]+)"/g)]
  .find(match => /\bloadSettings\b/.test(match[1]))?.[2];
assert.ok(settingsFile, 'Gemini settings loader import is missing');
// Keep fixtures outside /tmp: Linux tool sandboxes replace /tmp with a tmpfs.
const fixture = fs.mkdtempSync(path.join(repo, '.gemini-native-probe-'));
process.env.GEMINI_CLI_HOME = path.join(fixture, 'user');
process.env.GEMINI_CLI_SYSTEM_SETTINGS_PATH = path.join(fixture, 'no-system-settings.json');
process.env.GEMINI_CLI_SYSTEM_DEFAULTS_PATH = path.join(fixture, 'no-system-defaults.json');
try {
  const core = await import(pathToFileURL(path.join(bundle, coreFile)));
  core.debugLogger.debug = () => {};
  const settings = JSON.parse(fs.readFileSync(path.join(repo, '.gemini/settings.json'), 'utf8'));
  const workspace = path.join(fixture, 'workspace with spaces');
  fs.mkdirSync(path.join(workspace, '.gemini/policies'), { recursive: true });
  fs.mkdirSync(path.join(process.env.GEMINI_CLI_HOME, '.gemini'), { recursive: true });
  fs.writeFileSync(path.join(process.env.GEMINI_CLI_HOME, '.gemini/trustedFolders.json'),
    JSON.stringify({ [workspace]: 'TRUST_FOLDER' }));
  fs.writeFileSync(path.join(workspace, '.gemini/settings.json'), JSON.stringify(settings));
  const policyPath = path.join(workspace, '.gemini/policies/magpie.toml');
  fs.copyFileSync(path.join(repo, '.gemini/policies/magpie.toml'), policyPath);
  const { loadSettings } = await import(pathToFileURL(path.join(bundle, settingsFile)));
  process.chdir(workspace);
  const effective = loadSettings(workspace);
  assert.deepEqual(effective.errors, []);
  assert.equal(effective.merged.security.toolSandboxing, true);
  assert.equal(effective.merged.security.disableYoloMode, true);
  assert.deepEqual(effective.merged.policyPaths, settings.policyPaths);
  const policyPaths = effective.merged.policyPaths.map(p => path.resolve(p.replace(/^~/, process.env.GEMINI_CLI_HOME)));
  const loaded = await core.loadPoliciesFromToml([policyPath], () => core.USER_POLICY_TIER);
  assert.deepEqual(loaded.errors, [], 'Gemini must accept every rule, including its safe-regex check');
  assert.ok(loaded.rules.length > 0);
  const manager = core.createSandboxManager(
    { enabled: settings.security.toolSandboxing },
    { workspace, modeConfig: { network: false, readonly: false, approvedTools: [], allowOverrides: true } },
    'default',
  );
  const samples = [
    ['run_shell_command', { command: 'git push origin main' }, 'ask_user'],
    ['run_shell_command', { command: 'git -C . push --force origin main' }, 'ask_user'],
    ['run_shell_command', { command: 'gh pr create --title example' }, 'ask_user'],
    ['run_shell_command', { command: 'gh api graphql -f query=mutation' }, 'ask_user'],
    ['run_shell_command', { command: 'gh pr view 1' }, 'allow'],
    ['run_shell_command', { command: 'gh issue list --repo example/project' }, 'allow'],
    ['run_shell_command', { command: 'gh auth status' }, 'allow'],
    ['run_shell_command', { command: 'gh auth status --show-token' }, 'ask_user'],
    ['run_shell_command', { command: 'git status' }, 'allow'],
    ['run_shell_command', { command: 'git status --short' }, 'allow'],
    ['run_shell_command', { command: 'git status --porcelain' }, 'allow'],
    ['run_shell_command', { command: 'git status -sb' }, 'allow'],
    ['run_shell_command', { command: 'git diff --stat' }, 'allow'],
    ['run_shell_command', { command: 'git log --oneline' }, 'allow'],
    ['run_shell_command', { command: 'git ls-files' }, 'allow'],
    ['run_shell_command', { command: 'git -c core.pager=example status' }, 'ask_user'],
    ['run_shell_command', { command: 'git diff --stat --output=example.txt' }, 'ask_user'],
    ['run_shell_command', { command: 'git status --short && git push origin main' }, 'ask_user'],
    ['run_shell_command', { command: 'gh pr view 1 && gh pr close 1' }, 'ask_user'],
    ['run_shell_command', { command: 'gh pr view 1 > example.txt' }, 'ask_user'],
    ['run_shell_command', { command: 'gh pr view "$(touch example.txt)"' }, 'ask_user'],
    ['run_shell_command', { command: 'gh pr view 1 && gh auth token' }, 'deny'],
    ['run_shell_command', { command: 'cat ~/.ssh/id_rsa' }, 'ask_user'],
    ['run_shell_command', { command: 'python3 -c "print(1)"' }, 'ask_user'],
    ['run_shell_command', { command: 'gh auth token' }, 'deny'],
    ['run_shell_command', { command: 'gh auth token --help' }, 'deny'],
    ['run_shell_command', { command: 'gh auth refresh' }, 'deny'],
    ['run_shell_command', { command: 'echo ok && curl https://example.com' }, 'deny'],
    ['run_shell_command', { command: 'bash -c "curl https://example.com"' }, 'deny'],
    ['run_shell_command', { command: 'npm publish' }, 'deny'],
    ['read_file', { file_path: '/home/example/.ssh/id_rsa' }, 'deny'],
    ['read_file', { file_path: 'C:\\Users\\example\\.aws\\credentials' }, 'deny'],
    ['read_file', { file_path: '/home/example/.config/apache-magpie/gmail-oauth.json' }, 'deny'],
    ['read_file', { file_path: '/home/example/.gemini/oauth_creds.json' }, 'deny'],
    ['read_file', { file_path: 'nested/deep/.env.production.local' }, 'deny'],
    ['read_many_files', { paths: ['README.md', '.env'] }, 'deny'],
    ['write_file', { file_path: '.gemini/policies/override.toml', content: '' }, 'deny'],
    ['replace', { file_path: 'AGENTS.md', old_string: 'old', new_string: 'new' }, 'deny'],
    ['write_file', { file_path: 'example.txt', content: 'example' }, 'ask_user'],
    ['replace', { file_path: 'example.txt', old_string: 'old', new_string: 'new' }, 'ask_user'],
    ['mcp_example-server_create', { body: 'example' }, 'ask_user'],
  ];
  let decisions = 0;
  for (const mode of ['default', 'autoEdit', 'plan', 'yolo']) {
    for (const interactive of [true, false]) {
      const config = await core.createPolicyEngineConfig({
        policyPaths, disableAlwaysAllow: settings.security.disableAlwaysAllow,
      }, mode, undefined, interactive);
      const engine = new core.PolicyEngine({ ...config, sandboxManager: manager });
      for (const [name, args, expected] of samples) {
        const result = await engine.check({ name, args });
        const planDenied = mode === 'plan' && expected !== 'allow' && (name === 'run_shell_command' || name === 'write_file' ||
          name === 'replace' || name.startsWith('mcp_'));
        const decision = planDenied ? 'deny' : expected;
        assert.equal(result.decision, decision,
          `${mode}/${interactive}: ${name} ${JSON.stringify(args)}`);
        if (!interactive && decision === 'ask_user') {
          await assert.rejects(core.checkPolicy({
            request: { name, args, isClientInitiated: false }, tool: { name },
          }, { getPolicyEngine: () => engine, isInteractive: () => false }), /non-interactive mode/);
        }
        decisions++;
      }
    }
  }
  console.log(`Gemini ${pkg.version}: ${loaded.rules.length} parsed rules; ${decisions} native policy decisions passed.`);
  if (process.argv.includes('--sandbox')) {
    assert.equal(os.platform(), 'linux', 'The live filesystem probe currently covers Linux only');
    // A synthetic home outside the workspace: never probe the operator's secrets.
    const outside = path.join(process.env.GEMINI_CLI_HOME, 'home-read-probe.txt');
    fs.writeFileSync(outside, 'synthetic-outside-sentinel');
    const run = async (command, args) => {
      const prepared = await manager.prepareCommand({ command, args, cwd: workspace,
        env: { PATH: process.env.PATH, HOME: process.env.GEMINI_CLI_HOME }, policy: { networkAccess: false } });
      try {
        // This version passes NUL-separated bwrap arguments through fd 8.
        assert.equal(prepared.program, 'sh');
        const bwrapArgs = fs.readFileSync(prepared.args[4], 'utf8').split('\0');
        assert.ok(bwrapArgs.some((arg, i) => arg === '--ro-bind' &&
          bwrapArgs[i + 1] === '/' && bwrapArgs[i + 2] === '/'),
          'Recheck the documented Linux read boundary if the root mount changes');
        return spawnSync(prepared.program, prepared.args, {
          cwd: prepared.cwd, env: prepared.env, encoding: 'utf8', timeout: 15000,
        });
      } finally { prepared.cleanup?.(); }
    };
    const read = await run('cat', [outside]);
    assert.equal(read.status, 0, read.stderr);
    assert.equal(read.stdout, 'synthetic-outside-sentinel', 'Document the broad-read boundary accurately');
    await assert.rejects(run('__read', [outside]), /Path traversal or unauthorized access/);
    const write = await run('sh', ['-c', 'printf changed > "$1"', '_', outside]);
    assert.notEqual(write.status, 0, 'An unapproved write outside the workspace must fail');
    assert.equal(fs.readFileSync(outside, 'utf8'), 'synthetic-outside-sentinel');
    const local = await run('sh', ['-c', 'printf local > local.txt']);
    assert.equal(local.status, 0, local.stderr);
    assert.equal(fs.readFileSync(path.join(workspace, 'local.txt'), 'utf8'), 'local');
    fs.writeFileSync(path.join(workspace, 'network.py'),
      'import socket\ns=socket.socket()\ns.settimeout(1)\ns.connect(("192.0.2.1", 443))\n');
    const network = await run('python3', [path.join(workspace, 'network.py')]);
    assert.notEqual(network.status, 0);
    assert.match(network.stderr, /Network is unreachable/);
    console.log('Linux native sandbox: --ro-bind / /; synthetic home outside workspace remains readable.');
    console.log('Native __read rejects the same outside path.');
    console.log('Workspace write allowed; outside write and network blocked.');
  }
} finally {
  process.chdir(repo);
  fs.rmSync(fixture, { recursive: true, force: true });
}
