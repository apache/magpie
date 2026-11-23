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
  DEFAULT_AGENT,
  DEFAULT_ATTRIBUTION,
  DEFAULT_COAUTHOR_EMAIL,
  evaluateCommitCommand,
  formatAttribution,
  joinPath,
  parseAttributionToml,
  register,
  resolveAttribution,
  sanitizeTrailer,
} from './commit-attribution.js';

function assert(condition: any, message?: string): void {
  if (!condition) {
    throw new Error(message || 'Assertion failed');
  }
}

function assertStrictEqual(actual: any, expected: any, message?: string): void {
  if (actual !== expected) {
    throw new Error(
      message || `Expected ${JSON.stringify(expected)} but got ${JSON.stringify(actual)}`
    );
  }
}

function assertDeepStrictEqual(actual: any, expected: any): void {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    throw new Error(
      `Expected deep equality: ${JSON.stringify(expected)} !== ${JSON.stringify(actual)}`
    );
  }
}

describe('Commit Attribution mod (family:utilities)', () => {
  describe('joinPath', () => {
    test('normalizes single and multiple path segments without node:path', () => {
      assertStrictEqual(joinPath('a', 'b', 'c'), 'a/b/c');
      assertStrictEqual(joinPath('a/b/', '/c/d'), 'a/b/c/d');
      assertStrictEqual(joinPath('a\\b', 'c\\d'), 'a/b/c/d');
      assertStrictEqual(joinPath('a', '..', 'b'), 'b');
      assertStrictEqual(joinPath('/root', 'sub', '..', 'target'), '/root/target');
      assertStrictEqual(joinPath('', '  ', 'valid'), 'valid');
      assertStrictEqual(joinPath(), '.');
    });

    test('supports Windows drive letters as absolute path boundaries', () => {
      assertStrictEqual(joinPath('C:\\repo', '.apache-magpie-overrides', 'commit-attribution.toml'), 'C:/repo/.apache-magpie-overrides/commit-attribution.toml');
      assertStrictEqual(joinPath('D:/repo/sub', '..', 'target'), 'D:/repo/target');
    });
  });

  describe('sanitizeTrailer', () => {
    test('preserves clean single-line trailers verbatim', () => {
      assertStrictEqual(
        sanitizeTrailer('Generated-by: Claude Code'),
        'Generated-by: Claude Code'
      );
      assertStrictEqual(
        sanitizeTrailer('Co-authored-by: Claude Code <noreply@anthropic.com>'),
        'Co-authored-by: Claude Code <noreply@anthropic.com>'
      );
    });

    test('strips ANSI CSI and OSC escape sequences', () => {
      const contaminated =
        '\x1b[31mGenerated-by:\x1b[0m \x1b]0;Title\x07Claude Code';
      assertStrictEqual(sanitizeTrailer(contaminated), 'Generated-by: Claude Code');
    });

    test('strips Unicode BiDi override characters', () => {
      const contaminated =
        'Generated-by: \u202Eedoc edualC\u202C (Claude Code)';
      assertStrictEqual(
        sanitizeTrailer(contaminated),
        'Generated-by: edoc edualC (Claude Code)'
      );
    });

    test('strips line terminators, control characters, and shell metacharacters', () => {
      const multiline = 'Generated-by: Claude Code\r\n`rm -rf /` $HOME "evil"\x00\x07';
      assertStrictEqual(
        sanitizeTrailer(multiline),
        'Generated-by: Claude Coderm -rf / HOME evil'
      );
    });

    test('handles non-string values gracefully', () => {
      assertStrictEqual(sanitizeTrailer(null), '');
      assertStrictEqual(sanitizeTrailer(undefined), '');
      assertStrictEqual(sanitizeTrailer(123), '');
    });
  });

  describe('parseAttributionToml', () => {
    test('parses valid conventions with double quotes and comments', () => {
      const toml = `
# Which trailer an agent-assisted commit carries
convention = "generated-by" # default
template = "Generated-by: {agent}"
`;
      const result = parseAttributionToml(toml);
      assert(result !== null);
      assertStrictEqual(result?.convention, 'generated-by');
      assertStrictEqual(result?.template, 'Generated-by: {agent}');
    });

    test('parses single quoted and unquoted values case-insensitively', () => {
      const toml1 = "convention = 'ASSISTED-BY'";
      const result1 = parseAttributionToml(toml1);
      assert(result1 !== null);
      assertStrictEqual(result1?.convention, 'assisted-by');

      const toml2 = 'convention = co-authored-by';
      const result2 = parseAttributionToml(toml2);
      assert(result2 !== null);
      assertStrictEqual(result2?.convention, 'co-authored-by');

      const toml3 = 'convention = "none"';
      const result3 = parseAttributionToml(toml3);
      assertStrictEqual(result3?.convention, 'none');

      const toml4 = 'convention = "contributor-choice"';
      const result4 = parseAttributionToml(toml4);
      assertStrictEqual(result4?.convention, 'contributor-choice');
    });

    test('preserves quoted # inside template strings', () => {
      const toml = `
convention = "custom"
template = "Generated-by: {agent} #ai-review"
`;
      const result = parseAttributionToml(toml);
      assert(result !== null);
      assertStrictEqual(result?.convention, 'custom');
      assertStrictEqual(result?.template, 'Generated-by: {agent} #ai-review');
    });

    test('returns null for missing, empty, or unparsable inputs', () => {
      assertStrictEqual(parseAttributionToml(''), null);
      assertStrictEqual(parseAttributionToml('   '), null);
      assertStrictEqual(parseAttributionToml(null), null);
      assertStrictEqual(parseAttributionToml(undefined), null);
      assertStrictEqual(parseAttributionToml('# Just comments\n# nothing else'), null);
      assertStrictEqual(parseAttributionToml('unrelated_key = "value"'), null);
      assertStrictEqual(parseAttributionToml('convention = "unsupported-value"'), null);
    });
  });

  describe('formatAttribution', () => {
    test('formats generated-by convention', () => {
      const resolved = formatAttribution({ convention: 'generated-by' });
      assertStrictEqual(resolved.convention, 'generated-by');
      assertStrictEqual(resolved.trailerText, 'Generated-by: Claude Code');
      assertStrictEqual(resolved.trailerKey, 'Generated-by');
      assertStrictEqual(resolved.trailerValue, 'Claude Code');
    });

    test('formats assisted-by convention with and without model', () => {
      const resolvedWithout = formatAttribution({ convention: 'assisted-by' });
      assertStrictEqual(resolvedWithout.trailerText, 'Assisted-by: Claude Code');

      const resolvedWith = formatAttribution(
        { convention: 'assisted-by' },
        DEFAULT_AGENT,
        DEFAULT_COAUTHOR_EMAIL,
        'Claude 3.7 Sonnet'
      );
      assertStrictEqual(resolvedWith.trailerText, 'Assisted-by: Claude Code:Claude 3.7 Sonnet');
    });

    test('formats co-authored-by convention', () => {
      const resolved = formatAttribution({ convention: 'co-authored-by' });
      assertStrictEqual(resolved.convention, 'co-authored-by');
      assertStrictEqual(
        resolved.trailerText,
        'Co-authored-by: Claude Code <noreply@anthropic.com>'
      );
      assertStrictEqual(resolved.trailerKey, 'Co-authored-by');
      assertStrictEqual(
        resolved.trailerValue,
        'Claude Code <noreply@anthropic.com>'
      );
    });

    test('formats none convention as null trailer', () => {
      const resolved = formatAttribution({ convention: 'none' });
      assertStrictEqual(resolved.convention, 'none');
      assertStrictEqual(resolved.trailerText, null);
      assertStrictEqual(resolved.trailerKey, null);
      assertStrictEqual(resolved.trailerValue, null);
    });

    test('formats custom convention with model placeholder substituted or stripped', () => {
      const template = 'AI-Tooling: {agent} ({model})';
      const resolvedWith = formatAttribution(
        { convention: 'custom', template },
        'Claude Code',
        'noreply@anthropic.com',
        'Opus 4'
      );
      assertStrictEqual(resolvedWith.trailerText, 'AI-Tooling: Claude Code (Opus 4)');

      const resolvedWithout = formatAttribution(
        { convention: 'custom', template },
        'Claude Code',
        'noreply@anthropic.com'
      );
      assertStrictEqual(resolvedWithout.trailerText, 'AI-Tooling: Claude Code');
    });

    test('falls back safely when custom template is missing, lacks colon, or has invalid key', () => {
      const resolved1 = formatAttribution({ convention: 'custom' });
      assertStrictEqual(resolved1.convention, 'generated-by');
      assertStrictEqual(resolved1.trailerText, 'Generated-by: Claude Code');

      const resolved2 = formatAttribution({
        convention: 'custom',
        template: 'InvalidWithoutColon',
      });
      assertStrictEqual(resolved2.convention, 'generated-by');
      assertStrictEqual(resolved2.trailerText, 'Generated-by: Claude Code');

      const resolved3 = formatAttribution({
        convention: 'custom',
        template: 'Invalid Key With Spaces: Value',
      });
      assertStrictEqual(resolved3.convention, 'generated-by');
    });
  });

  describe('resolveAttribution precedence and fail-closed rules', () => {
    test('project layer wins when convention is not contributor-choice', () => {
      const projectToml = 'convention = "assisted-by"';
      const personalToml = 'convention = "co-authored-by"';

      const resolved = resolveAttribution(projectToml, personalToml);
      assertStrictEqual(resolved.convention, 'assisted-by');
      assertStrictEqual(resolved.trailerText, 'Assisted-by: Claude Code');
    });

    test('project contributor-choice defers to personal layer', () => {
      const projectToml = 'convention = "contributor-choice"';
      const personalToml = 'convention = "co-authored-by"';

      const resolved = resolveAttribution(projectToml, personalToml);
      assertStrictEqual(resolved.convention, 'co-authored-by');
      assertStrictEqual(
        resolved.trailerText,
        'Co-authored-by: Claude Code <noreply@anthropic.com>'
      );
    });

    test('absent project layer defers to personal layer', () => {
      const personalToml = 'convention = "none"';
      const resolved = resolveAttribution(null, personalToml);
      assertStrictEqual(resolved.convention, 'none');
      assertStrictEqual(resolved.trailerText, null);
    });

    test('FAIL-CLOSED: corrupted project TOML resolves strictly to generated-by (never defers to personal layer)', () => {
      const corrupted = 'conventon = "typo" [[[ broken';
      const personalToml = 'convention = "co-authored-by"';

      const resolved = resolveAttribution(corrupted, personalToml);
      assertStrictEqual(resolved.convention, 'generated-by');
      assertStrictEqual(resolved.trailerText, 'Generated-by: Claude Code');
    });

    test('FAIL-CLOSED: invalid convention in project TOML resolves strictly to generated-by', () => {
      const invalid = 'convention = "invalid-value"';
      const personalToml = 'convention = "co-authored-by"';

      const resolved = resolveAttribution(invalid, personalToml);
      assertStrictEqual(resolved.convention, 'generated-by');
      assertStrictEqual(resolved.trailerText, 'Generated-by: Claude Code');
    });

    test('absent both layers defaults to generated-by', () => {
      const resolved = resolveAttribution(null, null);
      assertStrictEqual(resolved.convention, 'generated-by');
      assertStrictEqual(resolved.trailerText, 'Generated-by: Claude Code');
    });
  });

  describe('evaluateCommitCommand', () => {
    test('permits non-git and non-commit commands', () => {
      const resolved = resolveAttribution(null, null);
      assertDeepStrictEqual(evaluateCommitCommand('npm test', resolved), {
        blocked: false,
      });
      assertDeepStrictEqual(evaluateCommitCommand('git status', resolved), {
        blocked: false,
      });
      assertDeepStrictEqual(evaluateCommitCommand('git diff HEAD~1', resolved), {
        blocked: false,
      });
      assertDeepStrictEqual(evaluateCommitCommand('', resolved), {
        blocked: false,
      });
      assertDeepStrictEqual(
        evaluateCommitCommand('git commit-tree 1234', resolved),
        { blocked: false }
      );
    });

    test('permits commands when MAGPIE_ALLOW_COAUTHOR=1 or MAGPIE_GUARD_OFF=1 is set', () => {
      const resolved = resolveAttribution(null, null);
      const cmd =
        'MAGPIE_ALLOW_COAUTHOR=1 git commit -m "feat: patch" --trailer "Co-authored-by: Alice <alice@example.com>"';
      assertDeepStrictEqual(evaluateCommitCommand(cmd, resolved), {
        blocked: false,
      });

      const cmdGuardOff =
        'MAGPIE_GUARD_OFF=1 git commit -m "feat: patch" --trailer "Co-authored-by: Alice <alice@example.com>"';
      assertDeepStrictEqual(evaluateCommitCommand(cmdGuardOff, resolved), {
        blocked: false,
      });
    });

    test('evaluates compound shell pipelines without false positives', () => {
      const resolved = resolveAttribution(null, null);
      const compound1 =
        'git commit -m "docs: release" && echo "co-authored-by: is forbidden"';
      assertDeepStrictEqual(evaluateCommitCommand(compound1, resolved), {
        blocked: false,
      });

      const compound2 =
        'git grep "co-authored-by:" && git commit -m "chore: test"';
      assertDeepStrictEqual(evaluateCommitCommand(compound2, resolved), {
        blocked: false,
      });
    });

    test('blocks git commit with Co-Authored-By when convention is generated-by', () => {
      const resolved = resolveAttribution(null, null);
      const evalResult = evaluateCommitCommand(
        'git commit -m "feat: something" --trailer "Co-authored-by: Claude Code <noreply@anthropic.com>"',
        resolved
      );
      assertStrictEqual(evalResult.blocked, true);
      assert(evalResult.reason?.includes('agent-guard[commit-trailer]'));
      assert(evalResult.reason?.includes('Generated-by: Claude Code'));
    });

    test('blocks git commit with Co-Authored-By when convention is none with proper guidance', () => {
      const resolved = formatAttribution({ convention: 'none' });
      const evalResult = evaluateCommitCommand(
        'git commit -m "feat: something" --trailer "Co-authored-by: Claude Code <noreply@anthropic.com>"',
        resolved
      );
      assertStrictEqual(evalResult.blocked, true);
      assert(evalResult.reason?.includes("convention is 'none'"));
      assert(evalResult.reason?.includes('(do not include attribution trailers)'));
    });

    test('permits git commit with Co-Authored-By when convention is co-authored-by', () => {
      const resolved = resolveAttribution('convention = "co-authored-by"', null);
      const evalResult = evaluateCommitCommand(
        'git commit -m "feat: something" --trailer "Co-authored-by: Claude Code <noreply@anthropic.com>"',
        resolved
      );
      assertStrictEqual(evalResult.blocked, false);
    });

    test('permits git commit with Co-Authored-By when custom convention uses Co-Authored-By key', () => {
      const resolved = formatAttribution({
        convention: 'custom',
        template: 'Co-Authored-By: {agent} <bot@example.org>',
      });
      const evalResult = evaluateCommitCommand(
        'git commit -m "feat: something" --trailer "Co-authored-by: Claude Code <bot@example.org>"',
        resolved
      );
      assertStrictEqual(evalResult.blocked, false);
    });

    test('ReDoS safety: evaluates commands with consecutive whitespace instantaneously', () => {
      const resolved = resolveAttribution(null, null);
      const evilCmd = 'git ' + ' '.repeat(500) + 'status';
      const start = Date.now();
      const evalResult = evaluateCommitCommand(evilCmd, resolved);
      const duration = Date.now() - start;
      assertStrictEqual(evalResult.blocked, false);
      assert(duration < 50, `Expected instant evaluation (<50ms), took ${duration}ms`);
    });
  });

  describe('Claude Code Hook Integration', () => {
    test('attribution.text hook answers with formatted trailer from project config', async () => {
      let registeredHandler: any;
      const fakeOn = (event: string, handler: any) => {
        if (event === 'attribution.text') {
          registeredHandler = handler;
        }
      };

      register(fakeOn);
      assert(typeof registeredHandler === 'function');

      const fakeSession = {
        session: {
          root: async () => '/fake/workspace',
        },
        fs: {
          read: async (p: string) => {
            if (p.includes('.apache-magpie-overrides')) {
              return 'convention = "assisted-by"';
            }
            return null;
          },
        },
      };

      const result = await registeredHandler(fakeSession);
      assertStrictEqual(result?.text, 'Assisted-by: Claude Code');
    });

    test('attribution.text hook falls back to unadopted .git/apache-magpie personal layer', async () => {
      let registeredHandler: any;
      const fakeOn = (event: string, handler: any) => {
        if (event === 'attribution.text') {
          registeredHandler = handler;
        }
      };

      register(fakeOn);

      const fakeSession = {
        session: {
          root: async () => '/fake/workspace',
        },
        fs: {
          read: async (p: string) => {
            if (p.includes('.git/apache-magpie') || p.includes('.git\\apache-magpie')) {
              return 'convention = "co-authored-by"';
            }
            return null;
          },
        },
      };

      const result = await registeredHandler(fakeSession);
      assertStrictEqual(
        result?.text,
        'Co-authored-by: Claude Code <noreply@anthropic.com>'
      );
    });

    test('attribution.text hook falls back to generated-by when fs throws', async () => {
      let registeredHandler: any;
      const fakeOn = (event: string, handler: any) => {
        if (event === 'attribution.text') {
          registeredHandler = handler;
        }
      };

      register(fakeOn);

      const fakeSession = {
        session: {
          root: async () => {
            throw new Error('EACCES: permission denied');
          },
        },
        fs: {
          read: async () => {
            throw new Error('EACCES');
          },
        },
      };

      const result = await registeredHandler(fakeSession);
      assertStrictEqual(result?.text, 'Generated-by: Claude Code');
    });

    test('tool.call Bash hook blocks unauthorized co-authored-by commits', async () => {
      let registeredHandler: any;
      const fakeOn = (event: string, filterOrHandler: any, maybeHandler?: any) => {
        if (event === 'tool.call') {
          registeredHandler = maybeHandler || filterOrHandler;
        }
      };

      register(fakeOn);
      assert(typeof registeredHandler === 'function');

      let nextCalled = false;
      const fakeNext = () => {
        nextCalled = true;
      };

      const fakeSession = {
        session: {
          root: async () => '/fake/workspace',
        },
        fs: {
          read: async () => null, // defaults to generated-by
        },
      };

      const denyResult = await registeredHandler(
        fakeSession,
        { command: 'git commit -m "msg" --trailer "Co-authored-by: Claude <noreply>"' },
        fakeNext
      );

      assertStrictEqual(denyResult?.decision, 'deny');
      assert(denyResult?.reason?.includes('agent-guard[commit-trailer]'));
      assertStrictEqual(nextCalled, false);
    });

    test('tool.call Bash hook calls next for permitted commands', async () => {
      let registeredHandler: any;
      const fakeOn = (event: string, filterOrHandler: any, maybeHandler?: any) => {
        if (event === 'tool.call') {
          registeredHandler = maybeHandler || filterOrHandler;
        }
      };

      register(fakeOn);

      let nextArg: any;
      const fakeNext = (arg: any) => {
        nextArg = arg;
        return { ok: true };
      };

      const fakeSession = {
        session: {
          root: async () => '/fake/workspace',
        },
        fs: {
          read: async () => null,
        },
      };

      const event = { command: 'git status' };
      const result = await registeredHandler(fakeSession, event, fakeNext);
      assertStrictEqual(result?.ok, true);
      assertStrictEqual(nextArg, event);
    });
  });
});
