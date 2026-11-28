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
  resolvePersonalLayerDir,
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
      stat: async (p: string) => {
        if (p === '/repo/.git') {
          return { kind: 'directory', size: 0, mtimeMs: 0, isLink: false };
        }
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
            prCount: 14,
            reviewCount: 22,
            window: '6m',
            note: 'Consistent core reviews',
            updatedAt: '2026-11-27T00:00:00Z',
          },
        ],
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

  describe('personal-layer resolution & confinement', () => {
    test('accepts exact filenames under <git-common-dir>/apache-magpie and rejects working tree', () => {
      const personalDir = '/repo/.git/apache-magpie';
      assertStrictEqual(
        isConfinedContributorPath(`${personalDir}/${SWEEP_QUEUE_FILENAME}`, personalDir),
        true
      );
      assertStrictEqual(
        isConfinedContributorPath(`${personalDir}/${SWEEP_ACTION_FILENAME}`, personalDir),
        true
      );
      assertStrictEqual(
        isConfinedContributorPath(`/repo/${SWEEP_ACTION_FILENAME}`, personalDir),
        false
      );
      assertStrictEqual(
        isConfinedContributorPath(`${personalDir}/../${SWEEP_QUEUE_FILENAME}`, personalDir),
        false
      );
      assertStrictEqual(
        isConfinedContributorPath(`${personalDir}/${SWEEP_QUEUE_FILENAME}\0`, personalDir),
        false
      );
      assertStrictEqual(isConfinedContributorPath(SWEEP_QUEUE_FILENAME, ''), false);
    });

    test('resolvePersonalLayerDir supports linked worktrees and refuses symlinked .git', async () => {
      const linked$ = createMockEngine({
        fs: {
          stat: async (p: string) => {
            if (p === '/wt/.git') {
              return { kind: 'file', size: 40, mtimeMs: 0, isLink: false };
            }
            throw Object.assign(new Error('ENOENT'), { code: 'ENOENT' });
          },
          read: async (p: string) => {
            if (p === '/wt/.git') return 'gitdir: /main/.git/worktrees/wt\n';
            if (p === '/main/.git/worktrees/wt/commondir') return '../..\n';
            return '';
          },
        },
      });
      assertStrictEqual(
        await resolvePersonalLayerDir(linked$, '/wt'),
        '/main/.git/apache-magpie'
      );

      const symlinkGit$ = createMockEngine({
        fs: {
          stat: async () => ({ kind: 'directory', size: 0, mtimeMs: 0, isLink: true }),
        },
      });
      assertStrictEqual(await resolvePersonalLayerDir(symlinkGit$, '/repo'), null);
    });
  });

  describe('parseContributorSweepPayload', () => {
    test('sorts shuffled candidates alphabetically by handle (case-insensitively) before bounding', () => {
      const items = [
        { handle: 'zoe', displayName: 'Zoe', prCount: 20, reviewCount: 30, window: '6m', note: '' },
        { handle: 'Alpha', displayName: 'Alpha', prCount: 2, reviewCount: 3, window: '6m', note: '' },
        { handle: 'mike', displayName: 'Mike', prCount: 10, reviewCount: 15, window: '6m', note: '' },
        { handle: 'bob', displayName: 'Bob', prCount: 5, reviewCount: 7, window: '6m', note: '' },
      ];

      const res = parseContributorSweepPayload(JSON.stringify({ items }), '2026-11-27T00:00:00Z');
      assert(res.ok);
      assertStrictEqual(
        res.state.items.map((it) => it.handle).join(','),
        'Alpha,bob,mike,zoe'
      );
      assertStrictEqual(res.state.selectedHandle, 'Alpha');
      assertStrictEqual((res.state.items[0] as any).stage, undefined);
    });

    test('deduplicates handles case-insensitively and bounds to MAX_CANDIDATES', () => {
      const items = Array.from({ length: MAX_CANDIDATES + 5 }, (_, i) => ({
        handle: `user-${String(i).padStart(3, '0')}`,
        displayName: `User ${i}`,
        prCount: i,
        reviewCount: i + 1,
        window: '6m',
        note: 'Active reviewer',
      }));
      items.push({
        handle: 'USER-000',
        displayName: 'Duplicate',
        prCount: 99,
        reviewCount: 99,
        window: '6m',
        note: 'dup',
      });

      const res = parseContributorSweepPayload(JSON.stringify({ items }), '2026-11-27T00:00:00Z');
      assert(res.ok);
      assertStrictEqual(res.state.items.length, MAX_CANDIDATES);
      assertStrictEqual(res.state.selectedHandle, 'user-000');
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

    test('renders plain counts without verdict badges, and suppresses Staged when syncError is set', () => {
      const Box = (props: any) => ({ type: 'Box', props });
      const Text = (props: any) => ({ type: 'Text', props });
      const Button = (props: any) => ({ type: 'Button', props });

      const state: ContributorSweepState = {
        items: [
          {
            handle: 'octocat',
            displayName: 'Octocat',
            prCount: 10,
            reviewCount: 15,
            window: '6m',
            note: 'Strong PR reviews',
            updatedAt: '2026-11-27T00:00:00Z',
          },
        ],
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
      assert(okOut.includes('10 PRs · 15 reviews (6m)'));
      assert(okOut.includes('Staged: /magpie-contributor-growth:nomination octocat'));
      assertStrictEqual(okOut.includes('[READY]'), false);
      assertStrictEqual(okOut.includes('[WATCH]'), false);

      const errOut = JSON.stringify(
        renderContributorSweepPane(Box, Text, Button, {
          ...state,
          syncError: 'Refusing to write to symlink or non-regular file',
        })
      );
      assert(errOut.includes('Warning: Refusing to write to symlink or non-regular file'));
      assertStrictEqual(errOut.includes('Staged:'), false);
    });

    test('renders a shuffled payload in alphabetical order of handle (case-insensitively)', () => {
      const Box = (props: any) => ({ type: 'Box', props });
      const Text = (props: any) => ({ type: 'Text', props });
      const Button = (props: any) => ({ type: 'Button', props });

      const parsed = parseContributorSweepPayload(
        JSON.stringify({
          items: [
            { handle: 'zoe', displayName: 'Zoe', prCount: 20, reviewCount: 30, window: '6m', note: '' },
            { handle: 'Alpha', displayName: 'Alpha', prCount: 2, reviewCount: 3, window: '6m', note: '' },
            { handle: 'mike', displayName: 'Mike', prCount: 10, reviewCount: 15, window: '6m', note: '' },
            { handle: 'bob', displayName: 'Bob', prCount: 5, reviewCount: 7, window: '6m', note: '' },
          ],
        }),
        '2026-11-27T00:00:00Z'
      );
      assert(parsed.ok);

      const rendered = JSON.stringify(renderContributorSweepPane(Box, Text, Button, parsed.state));
      const iAlpha = rendered.indexOf('@Alpha');
      const iBob = rendered.indexOf('@bob');
      const iMike = rendered.indexOf('@mike');
      const iZoe = rendered.indexOf('@zoe');
      assert(iAlpha !== -1 && iBob !== -1 && iMike !== -1 && iZoe !== -1);
      assert(iAlpha < iBob && iBob < iMike && iMike < iZoe);
    });
  });

  describe('runtime lifecycle integration', () => {
    test('handleContributorQueueCommand reads from <git-common-dir>/apache-magpie and opens Pane', async () => {
      const queuePath = `/repo/.git/apache-magpie/${SWEEP_QUEUE_FILENAME}`;
      const files: Record<string, string> = {
        [queuePath]: JSON.stringify({
          items: [
            {
              handle: 'zoe-dev',
              displayName: 'Zoe',
              prCount: 12,
              reviewCount: 20,
              window: '6m',
              note: '',
            },
            {
              handle: 'alice-dev',
              displayName: 'Alice',
              prCount: 8,
              reviewCount: 11,
              window: '6m',
              note: '',
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
          stat: async (p: string) => {
            if (p === '/repo/.git') {
              return { kind: 'directory', size: 0, mtimeMs: 0, isLink: false };
            }
            if (p in files) {
              return { kind: 'file', size: (files[p] ?? '').length, mtimeMs: 0, isLink: false };
            }
            throw Object.assign(new Error('ENOENT'), { code: 'ENOENT' });
          },
          read: async (p: string) => files[p] ?? '',
        },
      });

      const msg = await handleContributorQueueCommand(mock$);
      assert(msg.includes('2 candidate(s)'));
      assertStrictEqual(opened, true);
      const state = await getContributorSweepState(mock$);
      assertStrictEqual(state?.selectedHandle, 'alice-dev');
      assertStrictEqual(state?.queuePath, queuePath);
    });

    test('handleContributorQueueCommand refuses symlink or non-regular file before $.fs.read', async () => {
      let readCalled = false;
      const queuePath = `/repo/.git/apache-magpie/${SWEEP_QUEUE_FILENAME}`;
      const mock$ = createMockEngine({
        fs: {
          stat: async (p: string) => {
            if (p === '/repo/.git') {
              return { kind: 'directory', size: 0, mtimeMs: 0, isLink: false };
            }
            if (p === queuePath) {
              return { kind: 'file', size: 0, mtimeMs: 0, isLink: true };
            }
            throw Object.assign(new Error('ENOENT'), { code: 'ENOENT' });
          },
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

    test('Write/Bash hydrate under <git-common-dir>/apache-magpie and press stages action there (not in working tree)', async () => {
      const files: Record<string, string> = {};
      let opened = false;
      const personalQueue = `/repo/.git/apache-magpie/${SWEEP_QUEUE_FILENAME}`;
      const personalAction = `/repo/.git/apache-magpie/${SWEEP_ACTION_FILENAME}`;
      const payload = JSON.stringify({
        items: [
          {
            handle: 'bob-dev',
            displayName: 'Bob',
            prCount: 5,
            reviewCount: 8,
            window: '6m',
            note: 'Growing review activity',
          },
        ],
      });

      const mock$ = createMockEngine({
        ui: {
          open: async () => {
            opened = true;
          },
        },
        fs: {
          stat: async (p: string) => {
            if (p === '/repo/.git') {
              return { kind: 'directory', size: 0, mtimeMs: 0, isLink: false };
            }
            if (p in files) {
              return { kind: 'file', size: (files[p] ?? '').length, mtimeMs: 0, isLink: false };
            }
            throw Object.assign(new Error('ENOENT'), { code: 'ENOENT' });
          },
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

      // Write tool.call to working-tree path is ignored (only <git-common-dir>/apache-magpie is accepted)
      await handleContributorSweepWriteToolCall(
        mock$,
        { file_path: `/repo/${SWEEP_QUEUE_FILENAME}` },
        async () => ({ ok: true })
      );
      assertStrictEqual(opened, false);

      // Write tool.call to <git-common-dir>/apache-magpie hydrates and press stages action beside it
      await handleContributorSweepWriteToolCall(
        mock$,
        { file_path: personalQueue },
        async () => {
          files[personalQueue] = payload;
          return { ok: true };
        }
      );
      assertStrictEqual(opened, true);
      const state = await getContributorSweepState(mock$);
      assertStrictEqual(state?.queuePath, personalQueue);

      await handleContributorSweepPress(
        mock$,
        { element: 'cs:launch:nomination:bob-dev' },
        () => {}
      );
      assert(personalAction in files);
      assertStrictEqual(`/repo/${SWEEP_ACTION_FILENAME}` in files, false);
      const action = JSON.parse(files[personalAction] ?? '');
      assertStrictEqual(action.command, '/magpie-contributor-growth:nomination bob-dev');

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
