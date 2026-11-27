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
import type { ContributorSweepState } from './types.js';
import {
  buildContributorLauncherAction,
  classifyWriteTarget,
  CONTRIBUTOR_QUEUE_COMMAND,
  CONTRIBUTOR_QUEUE_STATE_KEY,
  getContributorSweepState,
  handleContributorQueueCommand,
  handleContributorSweepBashToolCall,
  handleContributorSweepPress,
  handleContributorSweepWriteToolCall,
  handleRenderContributorSweepPane,
  isAllowedContributorSkill,
  isConfinedContributorPath,
  isValidGitHubHandle,
  MAX_CANDIDATES,
  parseContributorSweepPayload,
  register,
  renderContributorSweepPane,
  sanitizeContributorText,
  setContributorSweepState,
  SWEEP_ACTION_FILENAME,
  SWEEP_QUEUE_FILENAME,
} from './contributor-sweep-pane.js';

function assert(cond: unknown, msg: string = 'Assertion failed'): asserts cond {
  if (!cond) throw new Error(msg);
}

function assertStrictEqual<T>(actual: T, expected: T, msg?: string): void {
  if (actual !== expected) {
    throw new Error(
      msg || `Expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`
    );
  }
}

function createMockEngine(overrides: Record<string, any> = {}): any {
  const store = new Map<string, any>();
  return {
    session: {
      root: async () => '/repo',
      cwd: async () => '/repo',
      ...(overrides.session || {}),
    },
    state: {
      get: async (ref: { plugin: string; key: string }) => {
        const k = `${ref.plugin}.${ref.key}`;
        return store.has(k) ? { value: store.get(k), version: 1 } : { value: null, version: 0 };
      },
      set: async (ref: { plugin: string; key: string }, value: any) => {
        const k = `${ref.plugin}.${ref.key}`;
        store.set(k, value);
        return { version: 1 };
      },
      ...(overrides.state || {}),
    },
    ui: {
      invalidate: () => {},
      open: async () => {},
      resolve: (e: any) => (e?.component === 'Pane' ? {} : {}),
      ...(overrides.ui || {}),
    },
    fs: {
      stat: async () => {
        throw Object.assign(new Error('ENOENT'), { code: 'ENOENT' });
      },
      read: async () => '',
      write: async () => {},
      ...(overrides.fs || {}),
    },
    command: {
      register: async () => {},
      ...(overrides.command || {}),
    },
  };
}

describe('contributor-sweep-pane mod (family:contributor-growth)', () => {
  describe('ambient type assignability', () => {
    test('ContributorSweepState satisfies PluginState ambient schema', () => {
      const sample: ContributorSweepState = {
        items: [
          {
            handle: 'octocat',
            displayName: 'The Octocat',
            stage: 'ready',
            prCount: 14,
            reviewCount: 22,
            window: '6m',
            note: 'Consistent core reviews',
            updatedAt: '2026-11-27T00:00:00Z',
          },
        ],
        activeFilter: 'all',
        selectedHandle: 'octocat',
        lastLaunchedAction: null,
        syncError: null,
        updatedAt: '2026-11-27T00:00:00Z',
      };
      assertStrictEqual(CONTRIBUTOR_QUEUE_STATE_KEY, 'magpie-contributor-growth.contributorSweepState');
      assertStrictEqual(sample.items[0]?.handle, 'octocat');
    });
  });

  describe('sanitization & handle validation', () => {
    test('strips ANSI CSI/OSC, BiDi overrides, and C0/C1 controls', () => {
      const dirty = '\x1b[31mEvil\x1b[0m \u202Espoof\u202C\x07\n\t"ok"';
      assertStrictEqual(sanitizeContributorText(dirty, 80), 'Evil spoof "ok"');
    });

    test('validates GitHub handles and allowed launcher skills strictly', () => {
      assertStrictEqual(isValidGitHubHandle('octocat-dev'), true);
      assertStrictEqual(isValidGitHubHandle('a'), true);
      assertStrictEqual(isValidGitHubHandle('-bad'), false);
      assertStrictEqual(isValidGitHubHandle('bad handle'), false);
      assertStrictEqual(isValidGitHubHandle('bad;rm -rf'), false);
      assertStrictEqual(isAllowedContributorSkill('activity-sweep'), true);
      assertStrictEqual(isAllowedContributorSkill('nomination'), true);
      assertStrictEqual(isAllowedContributorSkill('candidate-screen' as any), false);
    });
  });

  describe('isConfinedContributorPath', () => {
    test('accepts exact queue and action filenames under workspace root', () => {
      assertStrictEqual(
        isConfinedContributorPath(`/repo/${SWEEP_QUEUE_FILENAME}`, '/repo'),
        true
      );
      assertStrictEqual(
        isConfinedContributorPath(`/repo/${SWEEP_ACTION_FILENAME}`, '/repo'),
        true
      );
    });

    test('rejects traversal, null bytes, nested paths, and empty cwd', () => {
      assertStrictEqual(
        isConfinedContributorPath(`/repo/../${SWEEP_QUEUE_FILENAME}`, '/repo'),
        false
      );
      assertStrictEqual(
        isConfinedContributorPath(`/repo/sub/${SWEEP_QUEUE_FILENAME}`, '/repo'),
        false
      );
      assertStrictEqual(
        isConfinedContributorPath(`/repo/${SWEEP_QUEUE_FILENAME}\0`, '/repo'),
        false
      );
      assertStrictEqual(isConfinedContributorPath(SWEEP_QUEUE_FILENAME, ''), false);
    });
  });

  describe('parseContributorSweepPayload', () => {
    test('parses valid payload, deduplicates handles, and bounds to MAX_CANDIDATES', () => {
      const items = Array.from({ length: MAX_CANDIDATES + 5 }, (_, i) => ({
        handle: `user-${i}`,
        displayName: `User ${i}`,
        stage: i % 2 === 0 ? 'ready' : 'watch',
        prCount: i,
        reviewCount: i + 1,
        window: '6m',
        note: 'Active reviewer',
      }));
      items.push({
        handle: 'USER-0',
        displayName: 'Duplicate',
        stage: 'hold',
        prCount: 99,
        reviewCount: 99,
        window: '6m',
        note: 'dup',
      });

      const res = parseContributorSweepPayload(JSON.stringify({ items }), '2026-11-27T00:00:00Z');
      assert(res.ok);
      assertStrictEqual(res.state.items.length, MAX_CANDIDATES);
      assertStrictEqual(res.state.selectedHandle, 'user-0');
    });

    test('rejects empty or malformed payloads cleanly', () => {
      assertStrictEqual(parseContributorSweepPayload('').ok, false);
      assertStrictEqual(parseContributorSweepPayload('{bad').ok, false);
      assertStrictEqual(parseContributorSweepPayload('{}').ok, false);
    });
  });

  describe('renderContributorSweepPane & buildContributorLauncherAction', () => {
    test('builds safe launcher action omitting private notes', () => {
      const action = buildContributorLauncherAction('octocat', 'nomination', '2026-11-27T00:00:00Z');
      assert(action);
      assertStrictEqual(action.command, '/magpie-contributor-growth:nomination octocat');
      assertStrictEqual((action as any).note, undefined);
      assertStrictEqual(buildContributorLauncherAction('bad handle', 'nomination'), null);
    });

    test('renders filter tabs, Sweep/Nominate buttons, and suppresses Staged when syncError is set', () => {
      const Box = (props: any) => ({ type: 'Box', props });
      const Text = (props: any) => ({ type: 'Text', props });
      const Button = (props: any) => ({ type: 'Button', props });

      const state: ContributorSweepState = {
        items: [
          {
            handle: 'octocat',
            displayName: 'Octocat',
            stage: 'ready',
            prCount: 10,
            reviewCount: 15,
            window: '6m',
            note: 'Strong PR reviews',
            updatedAt: '2026-11-27T00:00:00Z',
          },
        ],
        activeFilter: 'all',
        selectedHandle: 'octocat',
        lastLaunchedAction: {
          handle: 'octocat',
          skill: 'nomination',
          command: '/magpie-contributor-growth:nomination octocat',
          stagedAt: '2026-11-27T00:00:00Z',
        },
        syncError: null,
        updatedAt: '2026-11-27T00:00:00Z',
      };

      const okOut = JSON.stringify(renderContributorSweepPane(Box, Text, Button, state));
      assert(okOut.includes('cs:launch:activity-sweep:octocat'));
      assert(okOut.includes('cs:launch:nomination:octocat'));
      assert(okOut.includes('Staged: /magpie-contributor-growth:nomination octocat'));

      const errOut = JSON.stringify(
        renderContributorSweepPane(Box, Text, Button, {
          ...state,
          syncError: 'Refusing to write to symlink or non-regular file',
        })
      );
      assert(errOut.includes('Warning: Refusing to write to symlink or non-regular file'));
      assertStrictEqual(errOut.includes('Staged:'), false);
    });
  });

  describe('runtime lifecycle integration', () => {
    test('handleContributorQueueCommand reads confined regular file, sets state, and opens Pane', async () => {
      const files: Record<string, string> = {
        [`/repo/${SWEEP_QUEUE_FILENAME}`]: JSON.stringify({
          items: [
            {
              handle: 'alice-dev',
              displayName: 'Alice',
              stage: 'ready',
              prCount: 12,
              reviewCount: 20,
              window: '6m',
              note: 'Ready for committer nomination',
            },
          ],
        }),
      };
      let opened = false;
      const mock$ = createMockEngine({
        ui: {
          open: async () => {
            opened = true;
          },
        },
        fs: {
          stat: async (p: string) =>
            p in files
              ? { kind: 'file', size: (files[p] ?? '').length, mtimeMs: 0, isLink: false }
              : (() => {
                  throw Object.assign(new Error('ENOENT'), { code: 'ENOENT' });
                })(),
          read: async (p: string) => files[p] ?? '',
        },
      });

      const msg = await handleContributorQueueCommand(mock$);
      assert(msg.includes('1 candidate(s) (1 ready'));
      assertStrictEqual(opened, true);
      const state = await getContributorSweepState(mock$);
      assertStrictEqual(state?.selectedHandle, 'alice-dev');
    });

    test('handleContributorQueueCommand refuses symlink or non-regular file before $.fs.read', async () => {
      let readCalled = false;
      const mock$ = createMockEngine({
        fs: {
          stat: async () => ({ kind: 'file', size: 0, mtimeMs: 0, isLink: true }),
          read: async () => {
            readCalled = true;
            return '{}';
          },
        },
      });

      const msg = await handleContributorQueueCommand(mock$);
      assert(msg.includes('refusing to read symlink or non-regular file'));
      assertStrictEqual(readCalled, false);
      assertStrictEqual(await getContributorSweepState(mock$), null);
    });

    test('Write and Bash tool.call auto-hydrate, skip git check-ignore, and refuse symlinks', async () => {
      const files: Record<string, string> = {};
      let opened = false;
      const cwdQueue = `/repo/subdir/${SWEEP_QUEUE_FILENAME}`;
      const cwdAction = `/repo/subdir/${SWEEP_ACTION_FILENAME}`;
      const payload = JSON.stringify({
        items: [
          {
            handle: 'bob-dev',
            displayName: 'Bob',
            stage: 'watch',
            prCount: 5,
            reviewCount: 8,
            window: '6m',
            note: 'Growing review activity',
          },
        ],
      });

      const mock$ = createMockEngine({
        session: {
          cwd: async () => '/repo/subdir',
          root: async () => '/repo',
        },
        ui: {
          open: async () => {
            opened = true;
          },
        },
        fs: {
          stat: async (p: string) =>
            p in files
              ? { kind: 'file', size: (files[p] ?? '').length, mtimeMs: 0, isLink: false }
              : (() => {
                  throw Object.assign(new Error('ENOENT'), { code: 'ENOENT' });
                })(),
          read: async (p: string) => files[p] ?? '',
          write: async (p: string, c: string) => {
            files[p] = c;
          },
        },
      });

      // git check-ignore must not hydrate
      await handleContributorSweepBashToolCall(
        mock$,
        { command: `git check-ignore -q ${SWEEP_QUEUE_FILENAME}` },
        async () => ({ exitCode: 0 })
      );
      assertStrictEqual(opened, false);

      // Write tool.call hydrates from cwd and press stages action beside it
      await handleContributorSweepWriteToolCall(
        mock$,
        { file_path: cwdQueue },
        async () => {
          files[cwdQueue] = payload;
          return { ok: true };
        }
      );
      assertStrictEqual(opened, true);
      const state = await getContributorSweepState(mock$);
      assertStrictEqual(state?.queuePath, cwdQueue);

      await handleContributorSweepPress(
        mock$,
        { element: 'cs:launch:activity-sweep:bob-dev' },
        () => {}
      );
      assert(cwdAction in files);
      const action = JSON.parse(files[cwdAction] ?? '');
      assertStrictEqual(action.command, '/magpie-contributor-growth:activity-sweep bob-dev');

      // Mutating git clears state
      await handleContributorSweepBashToolCall(mock$, { command: 'git checkout main' }, () => {});
      assertStrictEqual(await getContributorSweepState(mock$), null);
    });

    test('register command.run returns { text } matching CommandRunResult shape', async () => {
      const handlers: Record<string, Function> = {};
      const fakeOn = (event: string, optsOrFn: any, maybeFn?: Function) => {
        const fn = typeof optsOrFn === 'function' ? optsOrFn : maybeFn;
        if (fn) handlers[event] = fn;
      };
      register(fakeOn);

      const mock$ = createMockEngine();
      const commandRun = handlers['command.run'];
      assert(commandRun);
      const res = await commandRun(mock$, { command: CONTRIBUTOR_QUEUE_COMMAND }, () => {});
      assert(typeof res?.text === 'string' && res.text.includes('No local queue file found'));
      assertStrictEqual(res?.output, undefined);
      assertStrictEqual(await classifyWriteTarget(mock$, '/repo/missing.json'), 'missing');
    });
  });
});
