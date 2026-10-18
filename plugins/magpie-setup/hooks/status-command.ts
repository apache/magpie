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
 * Executes collect_status.py deterministically via process runner (python3 or python).
 */
export async function executeMagpieStatus(
  runProcess: ProcessRunner,
  scriptPath: string,
  workspaceDir: string,
  rawArgs?: string
): Promise<{ text: string }> {
  const args = (rawArgs || '').trim();
  const isJson = /(?:--format[=\s]+json|--json)(?:\s|$)/i.test(args);

  const collectorArgs: string[] = isJson
    ? [scriptPath, '--format', 'json', '--pretty', '--repo', workspaceDir]
    : [scriptPath, '--format', 'md', '--repo', workspaceDir];

  const runInit = {
    cwd: workspaceDir,
    env: { PYTHONIOENCODING: 'utf-8' },
    timeoutMs: PROCESS_TIMEOUT_MS,
  };

  // Try python3 first, fallback to python
  let result: ProcessRunResult | undefined;
  let executionError: Error | undefined;

  try {
    result = await runProcess(['python3', ...collectorArgs], runInit);
  } catch (err: any) {
    executionError = err instanceof Error ? err : new Error(String(err));
  }

  // If python3 failed to run (e.g. command not found) or returned non-zero, try python
  if (!result || result.exitCode !== 0) {
    try {
      const fallbackResult = await runProcess(['python', ...collectorArgs], runInit);
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
    '⚠️ Apache Magpie: Unable to execute deterministic status collector (`collect_status.py`).',
  ];
  if (result?.stderr?.trim()) {
    errorLines.push(`Error: ${result.stderr.trim()}`);
  } else if (executionError?.message) {
    errorLines.push(`Error: ${executionError.message}`);
  }
  errorLines.push(
    'Please verify that Python 3 is installed and available on PATH, or invoke the full workflow via `/magpie-setup status`.'
  );

  return { text: errorLines.join('\n\n') };
}

export default executeMagpieStatus;
