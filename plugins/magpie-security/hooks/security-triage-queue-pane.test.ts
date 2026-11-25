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
import type { SecurityTriageQueueState } from './types.js';
import {
  buildLauncherAction,
  handleQueueCommand,
  handleRenderSecurityQueuePane,
  handleSecurityQueueBashToolCall,
  handleSecurityQueuePress,
  isAllowedLauncherSkill,
  isConfinedQueuePath,
  isValidQueueItemId,
  MAX_QUEUE_ITEMS,
  parseSecurityQueuePayload,
  QUEUE_ACTION_FILENAME,
  QUEUE_INPUT_FILENAME,
  renderSecurityQueuePane,
  sanitizeSecurityText,
  SECURITY_QUEUE_PANE_ID,
  SECURITY_QUEUE_STATE_KEY,
} from './security-triage-queue-pane.js';

function assert(condition: unknown, message?: string): asserts condition {
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

function createMockEngine(overrides: any = {}): any {
  const store = new Map<string, any>();
  return {
    state: {
      get: (atom: any) => ({
        isSet: store.has(atom.key),
        value: store.has(atom.key) ? store.get(atom.key) : null,
      }),
      set: (atom: any, wrapped: any) => {
        const nextVal =
          wrapped && typeof wrapped === 'object' && 'value' in wrapped
            ? wrapped.value
            : wrapped;
        store.set(atom.key, nextVal);
        return { isSet: true, value: nextVal };
      },
    },
    ui: {
      invalidate: () => {},
      open: async () => {},
      resolve: () => ({
        Box: (p: any) => ({ type: 'Box', ...p }),
        Text: (p: any) => ({ type: 'Text', ...p }),
        Button: (p: any) => ({ type: 'Button', ...p }),
      }),
    },
    session: {
      root: async () => '/workspace/tracker',
      cwd: async () => '/workspace/tracker',
    },
    ...overrides,
  };
}

describe('security-triage-queue-pane mod (family:security)', () => {
  describe('ambient type assignability', () => {
    test('SecurityTriageQueueState satisfies PluginState ambient schema', () => {
      const state: SecurityTriageQueueState = {
        items: [
          {
            id: '#1042',
            title: 'Path traversal in archive loader',
            stage: 'needs-cve',
            severity: 'high',
            cveId: null,
            needsCve: true,
            updatedAt: '2026-11-25T10:00:00Z',
          },
        ],
        activeFilter: 'all',
        selectedItemId: '#1042',
        lastLaunchedAction: null,
        syncError: null,
        updatedAt: '2026-11-25T10:00:00Z',
      };
      assertStrictEqual(state.items.length, 1);
      assertStrictEqual(state.items[0]?.needsCve, true);
    });
  });

  describe('sanitizeSecurityText & ID validation', () => {
    test('strips ANSI CSI/OSC, BiDi overrides, and C0/C1 controls while preserving quotes', () => {
      const dirty = '\x1b[31mAlert\x1b[0m \x1b]0;Title\x07\u202E "don\'t" <leak>\x00\r\nline2';
      assertStrictEqual(sanitizeSecurityText(dirty, 120), 'Alert "don\'t" <leak> line2');
    });

    test('truncates at maxLen and returns empty string for non-string', () => {
      assertStrictEqual(sanitizeSecurityText('A'.repeat(150), 100), 'A'.repeat(100));
      assertStrictEqual(sanitizeSecurityText(null), '');
      assertStrictEqual(sanitizeSecurityText(42), '');
    });

    test('rejects unsafe item IDs containing spaces, semicolons, or slashes', () => {
      assert(isValidQueueItemId('#1042'));
      assert(isValidQueueItemId('GHSA-abcd-1234-efgh'));
      assert(!isValidQueueItemId('#1042; rm -rf /'));
      assert(!isValidQueueItemId('../etc/passwd'));
      assert(!isValidQueueItemId(''));
    });

    test('validates allowed launcher skills strictly', () => {
      assert(isAllowedLauncherSkill('issue-sync'));
      assert(isAllowedLauncherSkill('cve-allocate'));
      assert(isAllowedLauncherSkill('issue-triage'));
      assert(!isAllowedLauncherSkill('arbitrary-skill'));
    });
  });

  describe('isConfinedQueuePath', () => {
    test('accepts exact queue and action filenames under workspace root', () => {
      assert(isConfinedQueuePath(`/workspace/tracker/${QUEUE_INPUT_FILENAME}`, '/workspace/tracker'));
      assert(isConfinedQueuePath(`/workspace/tracker/${QUEUE_ACTION_FILENAME}`, '/workspace/tracker'));
    });

    test('rejects path traversal, null bytes, nested paths, and empty cwd', () => {
      assert(!isConfinedQueuePath(`/workspace/tracker/../${QUEUE_INPUT_FILENAME}`, '/workspace/tracker'));
      assert(!isConfinedQueuePath(`/workspace/tracker/sub/${QUEUE_INPUT_FILENAME}`, '/workspace/tracker'));
      assert(!isConfinedQueuePath(`/workspace/tracker/${QUEUE_INPUT_FILENAME}\0`, '/workspace/tracker'));
      assert(!isConfinedQueuePath('/etc/passwd', '/workspace/tracker'));
      assert(!isConfinedQueuePath(`/workspace/tracker/${QUEUE_INPUT_FILENAME}`, ''));
    });
  });

  describe('parseSecurityQueuePayload', () => {
    test('parses valid queue payload and bounds items to MAX_QUEUE_ITEMS', () => {
      const rawItems = Array.from({ length: MAX_QUEUE_ITEMS + 15 }, (_, idx) => ({
        id: `#${idx + 1}`,
        title: `Advisory ${idx + 1}`,
        stage: idx % 2 === 0 ? 'needs-sync' : 'needs-cve',
        severity: 'high',
        cveId: null,
        needsCve: true,
      }));
      const parsed = parseSecurityQueuePayload(JSON.stringify({ items: rawItems }), '2026-11-25T10:00:00Z');
      assert(parsed.ok);
      assertStrictEqual(parsed.state.items.length, MAX_QUEUE_ITEMS);
      assertStrictEqual(parsed.state.selectedItemId, '#1');
    });

    test('rejects empty or malformed payloads cleanly', () => {
      assertStrictEqual(parseSecurityQueuePayload('').ok, false);
      assertStrictEqual(parseSecurityQueuePayload('{bad-json').ok, false);
      assertStrictEqual(parseSecurityQueuePayload('{}').ok, false);
    });
  });

  describe('renderSecurityQueuePane & buildLauncherAction', () => {
    test('builds safe launcher action without advisory title text', () => {
      const action = buildLauncherAction('#1042', 'cve-allocate', '2026-11-25T10:00:00Z');
      assert(action !== null);
      assertStrictEqual(action!.command, '/magpie-security:cve-allocate #1042');
      assertStrictEqual((action as any).title, undefined);
      assertStrictEqual(buildLauncherAction('#1042; bad', 'cve-allocate'), null);
    });

    test('renders tabs, conditional [Allocate CVE] button, and staged footer', () => {
      const Box = (p: any) => ({ type: 'Box', ...p });
      const Text = (p: any) => ({ type: 'Text', ...p });
      const Button = (p: any) => ({ type: 'Button', ...p });
      const state: SecurityTriageQueueState = {
        items: [
          {
            id: '#1042',
            title: 'Issue needing CVE',
            stage: 'needs-cve',
            severity: 'critical',
            cveId: null,
            needsCve: true,
            updatedAt: '2026-11-25T10:00:00Z',
          },
        ],
        activeFilter: 'all',
        selectedItemId: '#1042',
        lastLaunchedAction: {
          itemId: '#1042',
          skill: 'cve-allocate',
          command: '/magpie-security:cve-allocate #1042',
          stagedAt: '2026-11-25T10:00:00Z',
        },
        syncError: null,
        updatedAt: '2026-11-25T10:00:00Z',
      };

      const tree = renderSecurityQueuePane(Box, Text, Button, state);
      assert(tree !== null);
      const serialized = JSON.stringify(tree);
      assert(serialized.includes('[Allocate CVE]'));
      assert(serialized.includes('Staged: /magpie-security:cve-allocate #1042'));
    });
  });

  describe('runtime lifecycle integration', () => {
    test('handleQueueCommand reads confined file, sets state, and calls $.ui.open', async () => {
      let openedId = '';
      const mock$ = createMockEngine({
        fs: {
          read: async (p: string) =>
            p === `/workspace/tracker/${QUEUE_INPUT_FILENAME}`
              ? JSON.stringify({
                  items: [
                    {
                      id: '#2001',
                      title: 'Report awaiting sync',
                      stage: 'needs-sync',
                      severity: 'medium',
                    },
                  ],
                })
              : null,
        },
        ui: {
          invalidate: () => {},
          open: async (opts: any) => {
            openedId = opts?.id;
          },
          resolve: () => ({
            Box: (p: any) => ({ type: 'Box', ...p }),
            Text: (p: any) => ({ type: 'Text', ...p }),
            Button: (p: any) => ({ type: 'Button', ...p }),
          }),
        },
      });

      const out = await handleQueueCommand(mock$);
      assert(out.includes('1 item(s)'));
      assertStrictEqual(openedId, SECURITY_QUEUE_PANE_ID);

      // Matching Pane render succeeds
      const rendered = handleRenderSecurityQueuePane(
        mock$,
        { component: 'Pane', requestId: SECURITY_QUEUE_PANE_ID },
        () => 'passthrough'
      );
      assertStrictEqual(rendered.type, 'Box');

      // Mismatched requestId passes through
      const passthrough = handleRenderSecurityQueuePane(
        mock$,
        { component: 'Pane', requestId: 'other-pane' },
        () => 'passthrough'
      );
      assertStrictEqual(passthrough, 'passthrough');
    });

    test('handleSecurityQueuePress stages launcher action and fails open on $.fs.write error', async () => {
      const mock$ = createMockEngine({
        fs: {
          write: async () => {
            throw new Error('EACCES');
          },
        },
      });
      mock$.state.set(
        { plugin: 'magpie-security', key: 'triageQueueState' },
        {
          value: {
            items: [
              {
                id: '#2001',
                title: 'Sensitive report title',
                stage: 'needs-sync',
                severity: 'high',
                cveId: null,
                needsCve: true,
                updatedAt: '2026-11-25T10:00:00Z',
              },
            ],
            activeFilter: 'all',
            selectedItemId: '#2001',
            lastLaunchedAction: null,
            syncError: null,
            updatedAt: '2026-11-25T10:00:00Z',
          },
        }
      );

      await handleSecurityQueuePress(mock$, { buttonId: 'sq:launch:issue-sync:#2001' }, () => {});
      const updated = mock$.state.get({ plugin: 'magpie-security', key: 'triageQueueState' }).value;
      assertStrictEqual(updated.lastLaunchedAction.command, '/magpie-security:issue-sync #2001');
      assert(updated.syncError.includes(QUEUE_ACTION_FILENAME));

      // Unprefixed buttonId from another pane passes through untouched
      let passedThrough = false;
      await handleSecurityQueuePress(mock$, { buttonId: 'close' }, () => {
        passedThrough = true;
      });
      assertStrictEqual(passedThrough, true);

      // Spoofed itemId not in state.items is ignored
      await handleSecurityQueuePress(mock$, { buttonId: 'sq:launch:issue-sync:#9999' }, () => {});
      assertStrictEqual(
        mock$.state.get({ plugin: 'magpie-security', key: 'triageQueueState' }).value.lastLaunchedAction.itemId,
        '#2001'
      );

      // Mutating git command clears state (supports both e.command and e.input.command)
      handleSecurityQueueBashToolCall(mock$, { command: 'git checkout main' }, () => {});
      assertStrictEqual(
        mock$.state.get({ plugin: 'magpie-security', key: 'triageQueueState' }).value,
        null
      );
    });
  });
});
