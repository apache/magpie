// SPDX-License-Identifier: Apache-2.0
//
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

import { describe, test } from 'claude-code/testing';
import { executeMagpieStatus, type ProcessRunner, type ProcessRunResult } from './status-command.ts';

function assert(condition: any, message?: string): void {
  if (!condition) {
    throw new Error(message || 'Assertion failed');
  }
}

function assertStrictEqual(actual: any, expected: any, message?: string): void {
  if (actual !== expected) {
    throw new Error(message || `Expected ${JSON.stringify(expected)} but got ${JSON.stringify(actual)}`);
  }
}

function assertDeepStrictEqual(actual: any, expected: any): void {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    throw new Error(`Expected deep equality: ${JSON.stringify(expected)} !== ${JSON.stringify(actual)}`);
  }
}

describe('magpie-status mod command (Pilot 2)', () => {
  const workspaceDir = '/test/workspace';
  const scriptPath = '/test/plugin/skills/status/scripts/collect_status.py';
  const MOCK_MD_OUTPUT = '## apache-magpie adoption — test\n\n**verdict:** ✔ healthy';
  const MOCK_JSON_OUTPUT = '{\n  "verdict": "healthy"\n}';

  describe('executeMagpieStatus logic', () => {
    test('invokes python3 with default markdown format and workspace repo', async () => {
      const calls: Array<{ argv: readonly string[]; init?: any }> = [];
      const runner: ProcessRunner = async (argv, init) => {
        calls.push({ argv, init });
        return { exitCode: 0, stdout: MOCK_MD_OUTPUT, stderr: '' };
      };

      const result = await executeMagpieStatus(runner, scriptPath, workspaceDir);
      assertStrictEqual(result.text, MOCK_MD_OUTPUT);
      assertStrictEqual(calls.length, 1);
      assertDeepStrictEqual(calls[0]?.argv, [
        'python3',
        scriptPath,
        '--format',
        'md',
        '--repo',
        workspaceDir,
      ]);
      assertStrictEqual(calls[0]?.init?.cwd, workspaceDir);
      assertStrictEqual(calls[0]?.init?.env?.PYTHONIOENCODING, 'utf-8');
    });

    test('honors --format json flag and requests pretty-printed JSON', async () => {
      const calls: Array<{ argv: readonly string[] }> = [];
      const runner: ProcessRunner = async (argv) => {
        calls.push({ argv });
        return { exitCode: 0, stdout: MOCK_JSON_OUTPUT, stderr: '' };
      };

      const result = await executeMagpieStatus(runner, scriptPath, workspaceDir, '--format json');
      assertStrictEqual(result.text, MOCK_JSON_OUTPUT);
      assertStrictEqual(calls.length, 1);
      assertDeepStrictEqual(calls[0]?.argv, [
        'python3',
        scriptPath,
        '--format',
        'json',
        '--pretty',
        '--repo',
        workspaceDir,
      ]);
    });

    test('honors --format=json syntax and case-insensitivity', async () => {
      const calls: Array<{ argv: readonly string[] }> = [];
      const runner: ProcessRunner = async (argv) => {
        calls.push({ argv });
        return { exitCode: 0, stdout: MOCK_JSON_OUTPUT, stderr: '' };
      };

      const result1 = await executeMagpieStatus(runner, scriptPath, workspaceDir, '--format=json');
      assertStrictEqual(result1.text, MOCK_JSON_OUTPUT);

      const result2 = await executeMagpieStatus(runner, scriptPath, workspaceDir, '--FORMAT JSON');
      assertStrictEqual(result2.text, MOCK_JSON_OUTPUT);
      assertStrictEqual(calls.length, 2);
    });

    test('honors --json flag alias', async () => {
      const calls: Array<{ argv: readonly string[] }> = [];
      const runner: ProcessRunner = async (argv) => {
        calls.push({ argv });
        return { exitCode: 0, stdout: MOCK_JSON_OUTPUT, stderr: '' };
      };

      const result = await executeMagpieStatus(runner, scriptPath, workspaceDir, '--json');
      assertStrictEqual(result.text, MOCK_JSON_OUTPUT);
      assertStrictEqual(calls.length, 1);
      assertDeepStrictEqual(calls[0]?.argv, [
        'python3',
        scriptPath,
        '--format',
        'json',
        '--pretty',
        '--repo',
        workspaceDir,
      ]);
    });

    test('falls back cleanly to python when python3 command throws (e.g. ENOENT)', async () => {
      const calls: string[][] = [];
      const runner: ProcessRunner = async (argv) => {
        calls.push([...argv]);
        if (argv[0] === 'python3') {
          throw new Error('spawn python3 ENOENT');
        }
        return { exitCode: 0, stdout: MOCK_MD_OUTPUT, stderr: '' };
      };

      const result = await executeMagpieStatus(runner, scriptPath, workspaceDir);
      assertStrictEqual(result.text, MOCK_MD_OUTPUT);
      assertStrictEqual(calls.length, 2);
      assertStrictEqual(calls[0]?.[0], 'python3');
      assertStrictEqual(calls[1]?.[0], 'python');
      assertDeepStrictEqual(calls[1]?.slice(1), [
        scriptPath,
        '--format',
        'md',
        '--repo',
        workspaceDir,
      ]);
    });

    test('falls back to python when python3 exits with non-zero exit code', async () => {
      const calls: string[][] = [];
      const runner: ProcessRunner = async (argv) => {
        calls.push([...argv]);
        if (argv[0] === 'python3') {
          return { exitCode: 127, stdout: '', stderr: 'python3 not found' };
        }
        return { exitCode: 0, stdout: MOCK_MD_OUTPUT, stderr: '' };
      };

      const result = await executeMagpieStatus(runner, scriptPath, workspaceDir);
      assertStrictEqual(result.text, MOCK_MD_OUTPUT);
      assertStrictEqual(calls.length, 2);
      assertStrictEqual(calls[0]?.[0], 'python3');
      assertStrictEqual(calls[1]?.[0], 'python');
    });

    test('returns actionable diagnostic error when both python3 and python fail', async () => {
      const runner: ProcessRunner = async () => {
        return { exitCode: 1, stdout: '', stderr: 'No module named internal_magpie' };
      };

      const result = await executeMagpieStatus(runner, scriptPath, workspaceDir);
      assert(result.text.includes('Unable to execute deterministic status collector'));
      assert(result.text.includes('No module named internal_magpie'));
      assert(result.text.includes('/magpie-setup status'));
    });

    test('prefers python error when python3 exits with 127 (not found)', async () => {
      const runner: ProcessRunner = async (argv) => {
        if (argv[0] === 'python3') {
          return { exitCode: 127, stdout: '', stderr: 'python3: command not found' };
        }
        return { exitCode: 1, stdout: '', stderr: 'SyntaxError: invalid syntax in collect_status.py' };
      };

      const result = await executeMagpieStatus(runner, scriptPath, workspaceDir);
      assert(result.text.includes('SyntaxError: invalid syntax in collect_status.py'));
    });
  });

  describe('Claude Code hook registration and /magpie-status command execution', () => {
    test('registers and executes /magpie-status returning stdout in session transcript', async ($: any, on: any) => {
      const registeredCommands: any[] = [];
      on('command.register', (_: any, e: any) => {
        registeredCommands.push(e);
        return { value: undefined };
      });

      on('session.start', () => ({ cwd: '/test/workspace' }));
      on('session.root', () => ({ value: '/test/workspace' }));
      on('fs.exists', () => ({ value: false }));
      on('fs.read', () => ({ value: '' }));
      on('ui.render', () => ({ type: 'Box', children: [] }));

      on('process.run', (_: any, e: any) => {
        return {
          value: {
            exitCode: 0,
            stdout: MOCK_MD_OUTPUT,
            stderr: '',
          },
        };
      });

      await $.session.start({ surface: 'terminal', isInteractive: true, cwd: '/test/workspace' });

      // Verify that magpie-status was registered with immediate: true
      const reg = registeredCommands.find((c) => c.name === 'magpie-status');
      assert(reg, 'Expected magpie-status command to be registered');
      assertStrictEqual(reg.name, 'magpie-status');
      assertStrictEqual(reg.immediate, true);

      // Verify command execution
      const answer = await $.command.run({ command: 'magpie-status', args: '' });
      assertStrictEqual(answer.text, MOCK_MD_OUTPUT);
    });

    test('executes /magpie-status with --format json returning formatted JSON', async ($: any, on: any) => {
      on('command.register', () => ({ value: undefined }));
      on('session.start', () => ({ cwd: '/test/workspace' }));
      on('session.root', () => ({ value: '/test/workspace' }));
      on('fs.exists', () => ({ value: false }));
      on('fs.read', () => ({ value: '' }));
      on('ui.render', () => ({ type: 'Box', children: [] }));

      let receivedArgv: readonly string[] = [];
      on('process.run', (_: any, e: any) => {
        receivedArgv = e.argv || [];
        return {
          value: {
            exitCode: 0,
            stdout: MOCK_JSON_OUTPUT,
            stderr: '',
          },
        };
      });

      await $.session.start({ surface: 'terminal', isInteractive: true, cwd: '/test/workspace' });

      const answer = await $.command.run({ command: 'magpie-status', args: '--format json' });
      assertStrictEqual(answer.text, MOCK_JSON_OUTPUT);
      assert(receivedArgv.includes('--format'), 'Expected argv to include --format');
      assert(receivedArgv.includes('json'), 'Expected argv to include json');
      assert(receivedArgv.includes('--pretty'), 'Expected argv to include --pretty');
    });
  });
});
