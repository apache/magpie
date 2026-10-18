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
import {
  executeMagpieSkills,
  joinPath,
  type ProcessRunner,
  type ProcessRunResult,
} from './skills-command.ts';

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

describe('magpie-skills mod command (Pilot 3)', () => {
  const workspaceDir = '/test/workspace';
  const scriptPath = '/test/plugin/skills/list-skills/scripts/list_skills.py';
  const MOCK_SKILLS_OUTPUT =
    'Skills installed for this repository (74 total)\n==================================================\n\nsetup/ (8)\n  setup  Install, update, or verify Apache Magpie';
  const MOCK_VERBOSE_OUTPUT =
    'Skills installed for this repository (74 total)\n==================================================\n\nsetup/ (8)\n  setup\n      Install, update, or verify Apache Magpie';

  describe('joinPath helper', () => {
    test('normalizes single and multiple path segments without node:path', () => {
      assertStrictEqual(joinPath(), '.');
      assertStrictEqual(joinPath(''), '.');
      assertStrictEqual(joinPath('a', 'b', 'c'), 'a/b/c');
      assertStrictEqual(joinPath('a/', '/b/', '/c'), 'a/b/c');
      assertStrictEqual(joinPath('/root', 'dir', 'file.txt'), '/root/dir/file.txt');
      assertStrictEqual(joinPath('a', '..', 'b'), 'b');
      assertStrictEqual(joinPath('a', '.', 'b'), 'a/b');
      assertStrictEqual(joinPath('a/b/c', '../..'), 'a');
    });
  });

  describe('executeMagpieSkills logic', () => {
    test('invokes python3 with default workspace repo passed to --root', async () => {
      const calls: Array<{ argv: readonly string[]; init?: any }> = [];
      const runner: ProcessRunner = async (argv, init) => {
        calls.push({ argv, init });
        return { exitCode: 0, stdout: MOCK_SKILLS_OUTPUT, stderr: '' };
      };

      const result = await executeMagpieSkills(runner, scriptPath, workspaceDir);
      assertStrictEqual(result.text, MOCK_SKILLS_OUTPUT);
      assertStrictEqual(calls.length, 1);
      assertDeepStrictEqual(calls[0]?.argv, [
        'python3',
        scriptPath,
        '--root',
        workspaceDir,
      ]);
      assertStrictEqual(calls[0]?.init?.cwd, workspaceDir);
      assertStrictEqual(calls[0]?.init?.env?.PYTHONIOENCODING, 'utf-8');
      assertStrictEqual(calls[0]?.init?.timeoutMs, 30_000);
    });

    test('honors --verbose flag', async () => {
      const calls: Array<{ argv: readonly string[] }> = [];
      const runner: ProcessRunner = async (argv) => {
        calls.push({ argv });
        return { exitCode: 0, stdout: MOCK_VERBOSE_OUTPUT, stderr: '' };
      };

      const result = await executeMagpieSkills(runner, scriptPath, workspaceDir, '--verbose');
      assertStrictEqual(result.text, MOCK_VERBOSE_OUTPUT);
      assertStrictEqual(calls.length, 1);
      assertDeepStrictEqual(calls[0]?.argv, [
        'python3',
        scriptPath,
        '--root',
        workspaceDir,
        '--verbose',
      ]);
    });

    test('honors -v shorthand flag and case-insensitivity', async () => {
      const calls: Array<{ argv: readonly string[] }> = [];
      const runner: ProcessRunner = async (argv) => {
        calls.push({ argv });
        return { exitCode: 0, stdout: MOCK_VERBOSE_OUTPUT, stderr: '' };
      };

      const result1 = await executeMagpieSkills(runner, scriptPath, workspaceDir, '-v');
      assertStrictEqual(result1.text, MOCK_VERBOSE_OUTPUT);

      const result2 = await executeMagpieSkills(runner, scriptPath, workspaceDir, '--VERBOSE');
      assertStrictEqual(result2.text, MOCK_VERBOSE_OUTPUT);
      assertStrictEqual(calls.length, 2);
    });

    test('honors --root custom path argument', async () => {
      const customRoot = '/custom/repo/path';
      const calls: Array<{ argv: readonly string[]; init?: any }> = [];
      const runner: ProcessRunner = async (argv, init) => {
        calls.push({ argv, init });
        return { exitCode: 0, stdout: MOCK_SKILLS_OUTPUT, stderr: '' };
      };

      const result = await executeMagpieSkills(
        runner,
        scriptPath,
        workspaceDir,
        `--root ${customRoot}`
      );
      assertStrictEqual(result.text, MOCK_SKILLS_OUTPUT);
      assertStrictEqual(calls.length, 1);
      assertDeepStrictEqual(calls[0]?.argv, [
        'python3',
        scriptPath,
        '--root',
        customRoot,
      ]);
      assertStrictEqual(calls[0]?.init?.cwd, workspaceDir);
    });

    test('honors --root custom path argument with spaces and double quotes', async () => {
      const customRootWithSpaces = 'C:\\Users\\Jane Doe\\Projects\\repo';
      const calls: Array<{ argv: readonly string[]; init?: any }> = [];
      const runner: ProcessRunner = async (argv, init) => {
        calls.push({ argv, init });
        return { exitCode: 0, stdout: MOCK_SKILLS_OUTPUT, stderr: '' };
      };

      const result = await executeMagpieSkills(
        runner,
        scriptPath,
        workspaceDir,
        `--root "${customRootWithSpaces}"`
      );
      assertStrictEqual(result.text, MOCK_SKILLS_OUTPUT);
      assertStrictEqual(calls.length, 1);
      assertDeepStrictEqual(calls[0]?.argv, [
        'python3',
        scriptPath,
        '--root',
        customRootWithSpaces,
      ]);
      assertStrictEqual(calls[0]?.init?.cwd, workspaceDir);
    });

    test('honors --root custom path argument with spaces and single quotes', async () => {
      const customRootWithSpaces = '/path with spaces/my-repo';
      const calls: Array<{ argv: readonly string[]; init?: any }> = [];
      const runner: ProcessRunner = async (argv, init) => {
        calls.push({ argv, init });
        return { exitCode: 0, stdout: MOCK_SKILLS_OUTPUT, stderr: '' };
      };

      const result = await executeMagpieSkills(
        runner,
        scriptPath,
        workspaceDir,
        `--root='${customRootWithSpaces}' -v`
      );
      assertStrictEqual(result.text, MOCK_SKILLS_OUTPUT);
      assertStrictEqual(calls.length, 1);
      assertDeepStrictEqual(calls[0]?.argv, [
        'python3',
        scriptPath,
        '--root',
        customRootWithSpaces,
        '--verbose',
      ]);
      assertStrictEqual(calls[0]?.init?.cwd, workspaceDir);
    });

    test('honors --root=custom path syntax', async () => {
      const customRoot = '/custom/another-repo';
      const calls: Array<{ argv: readonly string[] }> = [];
      const runner: ProcessRunner = async (argv) => {
        calls.push({ argv });
        return { exitCode: 0, stdout: MOCK_SKILLS_OUTPUT, stderr: '' };
      };

      const result = await executeMagpieSkills(
        runner,
        scriptPath,
        workspaceDir,
        `--root=${customRoot} --verbose`
      );
      assertStrictEqual(result.text, MOCK_SKILLS_OUTPUT);
      assertStrictEqual(calls.length, 1);
      assertDeepStrictEqual(calls[0]?.argv, [
        'python3',
        scriptPath,
        '--root',
        customRoot,
        '--verbose',
      ]);
    });

    test('falls back to workspaceDir when --root is passed without path and followed by flag', async () => {
      const calls: Array<{ argv: readonly string[] }> = [];
      const runner: ProcessRunner = async (argv) => {
        calls.push({ argv });
        return { exitCode: 0, stdout: MOCK_VERBOSE_OUTPUT, stderr: '' };
      };

      const result = await executeMagpieSkills(
        runner,
        scriptPath,
        workspaceDir,
        '--root --verbose'
      );
      assertStrictEqual(result.text, MOCK_VERBOSE_OUTPUT);
      assertStrictEqual(calls.length, 1);
      assertDeepStrictEqual(calls[0]?.argv, [
        'python3',
        scriptPath,
        '--root',
        workspaceDir,
        '--verbose',
      ]);
    });

    test('honors --help and -h flags, passing --help directly to list_skills.py', async () => {
      const HELP_OUTPUT = 'usage: list_skills.py [-h] [--verbose] [--root ROOT]';
      const calls: Array<{ argv: readonly string[] }> = [];
      const runner: ProcessRunner = async (argv) => {
        calls.push({ argv });
        return { exitCode: 0, stdout: HELP_OUTPUT, stderr: '' };
      };

      const result1 = await executeMagpieSkills(runner, scriptPath, workspaceDir, '--help');
      assertStrictEqual(result1.text, HELP_OUTPUT);
      assertDeepStrictEqual(calls[0]?.argv, ['python3', scriptPath, '--help']);

      const result2 = await executeMagpieSkills(runner, scriptPath, workspaceDir, '-h');
      assertStrictEqual(result2.text, HELP_OUTPUT);
      assertDeepStrictEqual(calls[1]?.argv, ['python3', scriptPath, '--help']);
      assertStrictEqual(calls.length, 2);
    });

    test('falls back cleanly to python when python3 command throws (e.g. ENOENT)', async () => {
      const calls: string[][] = [];
      const runner: ProcessRunner = async (argv) => {
        calls.push([...argv]);
        if (argv[0] === 'python3') {
          throw new Error('spawn python3 ENOENT');
        }
        return { exitCode: 0, stdout: MOCK_SKILLS_OUTPUT, stderr: '' };
      };

      const result = await executeMagpieSkills(runner, scriptPath, workspaceDir);
      assertStrictEqual(result.text, MOCK_SKILLS_OUTPUT);
      assertStrictEqual(calls.length, 2);
      assertStrictEqual(calls[0]?.[0], 'python3');
      assertStrictEqual(calls[1]?.[0], 'python');
      assertDeepStrictEqual(calls[1]?.slice(1), [
        scriptPath,
        '--root',
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
        return { exitCode: 0, stdout: MOCK_SKILLS_OUTPUT, stderr: '' };
      };

      const result = await executeMagpieSkills(runner, scriptPath, workspaceDir);
      assertStrictEqual(result.text, MOCK_SKILLS_OUTPUT);
      assertStrictEqual(calls.length, 2);
      assertStrictEqual(calls[0]?.[0], 'python3');
      assertStrictEqual(calls[1]?.[0], 'python');
    });

    test('returns actionable diagnostic error when both python3 and python fail', async () => {
      const runner: ProcessRunner = async () => {
        return { exitCode: 1, stdout: '', stderr: 'No module named stdlib_error' };
      };

      const result = await executeMagpieSkills(runner, scriptPath, workspaceDir);
      assert(result.text.includes('Unable to execute deterministic skills indexer'));
      assert(result.text.includes('No module named stdlib_error'));
      assert(result.text.includes('/magpie-utilities list-skills'));
    });

    test('prefers python error when python3 exits with 127 (not found)', async () => {
      const runner: ProcessRunner = async (argv) => {
        if (argv[0] === 'python3') {
          return { exitCode: 127, stdout: '', stderr: 'python3: command not found' };
        }
        return { exitCode: 1, stdout: '', stderr: 'SyntaxError: invalid syntax in list_skills.py' };
      };

      const result = await executeMagpieSkills(runner, scriptPath, workspaceDir);
      assert(result.text.includes('SyntaxError: invalid syntax in list_skills.py'));
    });
  });

  describe('Claude Code hook registration and /magpie-skills command execution', () => {
    test('registers and executes /magpie-skills returning stdout in session transcript', async ($: any, on: any) => {
      const registeredCommands: any[] = [];
      on('command.register', (_: any, e: any) => {
        registeredCommands.push(e);
        return { value: undefined };
      });

      on('session.start', () => ({ cwd: '/test/workspace' }));
      on('session.root', () => ({ value: '/test/workspace' }));

      on('process.run', (_: any, e: any) => {
        return {
          value: {
            exitCode: 0,
            stdout: MOCK_SKILLS_OUTPUT,
            stderr: '',
          },
        };
      });

      await $.session.start({ surface: 'terminal', isInteractive: true, cwd: '/test/workspace' });

      // Verify that magpie-skills was registered with immediate: true
      const reg = registeredCommands.find((c) => c.name === 'magpie-skills');
      assert(reg, 'Expected magpie-skills command to be registered');
      assertStrictEqual(reg.name, 'magpie-skills');
      assertStrictEqual(reg.immediate, true);

      // Verify command execution
      const answer = await $.command.run({ command: 'magpie-skills', args: '' });
      assertStrictEqual(answer.text, MOCK_SKILLS_OUTPUT);
    });

    test('executes /magpie-skills with --verbose returning formatted output', async ($: any, on: any) => {
      on('command.register', () => ({ value: undefined }));
      on('session.start', () => ({ cwd: '/test/workspace' }));
      on('session.root', () => ({ value: '/test/workspace' }));

      let receivedArgv: readonly string[] = [];
      on('process.run', (_: any, e: any) => {
        receivedArgv = e.argv || [];
        return {
          value: {
            exitCode: 0,
            stdout: MOCK_VERBOSE_OUTPUT,
            stderr: '',
          },
        };
      });

      await $.session.start({ surface: 'terminal', isInteractive: true, cwd: '/test/workspace' });

      const answer = await $.command.run({ command: 'magpie-skills', args: '--verbose' });
      assertStrictEqual(answer.text, MOCK_VERBOSE_OUTPUT);
      assert(receivedArgv.includes('--verbose'), 'Expected argv to include --verbose');
      assert(receivedArgv.includes('--root'), 'Expected argv to include --root');
    });
  });
});
