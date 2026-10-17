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

export interface ProcessRunResult {
  exitCode: number;
  stdout: string;
  stderr: string;
}

export type ProcessRunner = (
  argv: readonly string[],
  init?: { cwd?: string; env?: Record<string, string>; timeoutMs?: number }
) => Promise<ProcessRunResult>;

const PROCESS_TIMEOUT_MS = 30_000;

/**
 * Joins path segments normalizing slashes without depending on node:path.
 */
export function joinPath(...segments: string[]): string {
  const nonEmpties = segments.filter((s) => s && s.trim().length > 0);
  if (nonEmpties.length === 0) return '.';

  const isAbsolute = segments[0]?.startsWith('/') || segments[0]?.startsWith('\\');
  const parts: string[] = [];

  for (const seg of nonEmpties) {
    const split = seg.split(/[/\\]+/);
    for (const p of split) {
      if (p === '..') {
        if (parts.length > 0 && parts[parts.length - 1] !== '..') {
          parts.pop();
        } else if (!isAbsolute) {
          parts.push('..');
        }
      } else if (p !== '.' && p !== '') {
        parts.push(p);
      }
    }
  }

  const result = parts.join('/');
  if (isAbsolute) {
    return '/' + result;
  }
  return result || '.';
}

/**
 * Executes list_skills.py deterministically via process runner (python3 or python).
 */
export async function executeMagpieSkills(
  runProcess: ProcessRunner,
  scriptPath: string,
  workspaceDir: string,
  rawArgs?: string
): Promise<{ text: string }> {
  const args = (rawArgs || '').trim();
  const isHelp = /(?:--help|-h)(?:\s|$)/i.test(args);

  let scriptArgs: string[];
  if (isHelp) {
    scriptArgs = [scriptPath, '--help'];
  } else {
    const isVerbose = /(?:--verbose|-v)(?:\s|$)/i.test(args);
    const rootMatch = args.match(/(?:--root[=\s]+)(?:"([^"]+)"|'([^']+)'|([^\s]+))/i);
    const rootCandidate = rootMatch
      ? (rootMatch[1] ?? rootMatch[2] ?? rootMatch[3]).trim()
      : '';
    const targetRoot =
      rootCandidate && !rootCandidate.startsWith('-') ? rootCandidate : workspaceDir;

    scriptArgs = [scriptPath, '--root', targetRoot];
    if (isVerbose) {
      scriptArgs.push('--verbose');
    }
  }

  const runInit = {
    cwd: workspaceDir,
    env: { PYTHONIOENCODING: 'utf-8' },
    timeoutMs: PROCESS_TIMEOUT_MS,
  };

  // Try python3 first, fallback to python
  let result: ProcessRunResult | undefined;
  let executionError: Error | undefined;

  try {
    result = await runProcess(['python3', ...scriptArgs], runInit);
  } catch (err: any) {
    executionError = err instanceof Error ? err : new Error(String(err));
  }

  // If python3 failed to run (e.g. command not found) or returned non-zero, try python
  if (!result || result.exitCode !== 0) {
    try {
      const fallbackResult = await runProcess(['python', ...scriptArgs], runInit);
      if (fallbackResult.exitCode === 0 || !result || result.exitCode === 127) {
        result = fallbackResult;
        if (fallbackResult.exitCode === 0) {
          executionError = undefined;
        }
      }
    } catch (fallbackErr: any) {
      if (!executionError) {
        executionError = fallbackErr instanceof Error ? fallbackErr : new Error(String(fallbackErr));
      }
    }
  }

  if (result && result.exitCode === 0) {
    return { text: result.stdout.trimEnd() };
  }

  const errorLines = [
    '⚠️ Apache Magpie: Unable to execute deterministic skills indexer (`list_skills.py`).',
  ];
  if (result?.stderr?.trim()) {
    errorLines.push(`Error: ${result.stderr.trim()}`);
  } else if (executionError?.message) {
    errorLines.push(`Error: ${executionError.message}`);
  }
  errorLines.push(
    'Please verify that Python 3 is installed and available on PATH, or invoke the full workflow via `/magpie-utilities list-skills`.'
  );

  return { text: errorLines.join('\n\n') };
}

/**
 * Event hook registration entry point for Claude Code.
 */
export function register(on: any): void {
  // 1. Hook session.start to register slash command
  on('session.start', async ($: any, e: any, next: any) => {
    try {
      await $.command.register({
        name: 'magpie-skills',
        description: 'List installed Apache Magpie skills (zero-token)',
        argumentHint: '[-v|--verbose] [--root <path>] [-h|--help]',
        immediate: true,
      });
    } catch {
      // Safe no-op on command register exception
    }

    if (typeof next === 'function') {
      return next(e);
    }
  });

  // 2. Hook command.run on magpie-skills
  on('command.run', { command: 'magpie-skills' }, async ($: any, e: any) => {
    try {
      const workspaceDir = await $.session.root();
      const pluginDir = $.plugin.root;
      const scriptPath = joinPath(
        pluginDir,
        'skills',
        'list-skills',
        'scripts',
        'list_skills.py'
      );

      return await executeMagpieSkills(
        (argv, init) => $.process.run(argv, init),
        scriptPath,
        workspaceDir,
        e.args
      );
    } catch (err: any) {
      return {
        text: `⚠️ Apache Magpie: Unexpected error executing /magpie-skills: ${err?.message || String(err)}`,
      };
    }
  });
}

export default register;
