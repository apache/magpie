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
import type { PrStatsPaneState } from './types.js';
import {
  PR_STATS_STATE_KEY,
  extractStatsJsonPathFromCommand,
  parsePrStatsPayload,
  renderPrStatsPane,
  resolveConfinedStatsPath,
  sanitizeStatsText,
  toStatsJsonPath,
} from './pr-stats-pane.js';
import {
  classifyWriteTarget,
  getPrStatsState,
  handleBashToolCall,
  handlePrStatsCommand,
  handlePrStatsUiPress,
  handleRenderPane,
  handleRenderPrStatsPane,
} from './review-findings.js';

function assert(cond: unknown, msg?: string): asserts cond {
  if (!cond) throw new Error(msg ?? 'Assertion failed');
}

function assertStrictEqual<T>(actual: T, expected: T, msg?: string): void {
  if (actual !== expected) {
    throw new Error(
      msg ?? `Expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`
    );
  }
}

function createMockEngine(overrides: Record<string, any> = {}) {
  const store: Record<string, any> = {};
  const commands: any[] = [];
  return {
    store,
    commands,
    state: {
      get: (a: any) => {
        const k = typeof a === 'string' ? a : a?.key;
        return { isSet: k in store, value: k in store ? store[k] : null };
      },
      set: (a: any, wrapped: any) => {
        const k = typeof a === 'string' ? a : a?.key;
        const prev = k in store ? store[k] : null;
        const nextVal =
          typeof wrapped === 'function'
            ? wrapped(prev)
            : wrapped && typeof wrapped === 'object' && 'value' in wrapped
              ? wrapped.value
              : wrapped;
        store[k] = nextVal;
      },
      ...overrides.state,
    },
    ui: {
      invalidate: () => {},
      open: async () => {},
      resolve: () => ({
        Box: (props: any) => ({ type: 'Box', props }),
        Text: (props: any) => ({ type: 'Text', props }),
        Button: (props: any) => ({ type: 'Button', props }),
      }),
      ...overrides.ui,
    },
    command: {
      register: async (c: any) => {
        commands.push(c);
      },
      ...overrides.command,
    },
    session: {
      cwd: async () => '/repo',
      root: async () => '/repo',
      ...overrides.session,
    },
    fs: {
      stat: async () => {
        throw Object.assign(new Error('ENOENT'), { code: 'ENOENT' });
      },
      read: async () => '',
      ...overrides.fs,
    },
  };
}

function sampleIntermediates(overrides: Record<string, any> = {}) {
  return {
    fetched_at: '2026-11-27T12:00:00Z',
    repo: 'apache/magpie',
    viewer: 'Kaap10',
    cutoff: '2026-10-16T00:00:00Z',
    open_count: 42,
    closed_count: 118,
    ready_count: 7,
    untriaged_count: 11,
    untriaged_4w_count: 3,
    engaged_count: 19,
    ai_triaged_count: 25,
    recommendation_count: 4,
    funnel: {
      ready: 7,
      responded: 12,
      waiting_manual: 5,
      waiting_ai: 4,
      untriaged: 11,
      other: 3,
    },
    pressure_areas: [
      {
        area: 'area:security',
        score: 18,
        contribs: 9,
        age_4w: 1,
        age_1to4w: 3,
        age_rec: 5,
      },
      {
        area: 'area:scheduler',
        score: 34,
        contribs: 15,
        age_4w: 3,
        age_1to4w: 6,
        age_rec: 6,
      },
    ],
    weekly_velocity_totals: {
      merged: 96,
      closed_not_merged: 22,
    },
    partial: false,
    cap_note: null,
    ...overrides,
  };
}

describe('pr-stats-pane mod (family:pr-management)', () => {
  describe('ambient type assignability', () => {
    test('PrStatsPaneState satisfies PluginState ambient schema', () => {
      const sample: PrStatsPaneState = {
        repo: 'apache/magpie',
        fetchedAt: '2026-11-27T12:00:00Z',
        cutoff: '2026-10-16T00:00:00Z',
        jsonPath: '/tmp/dashboard.json',
        healthRating: 'Healthy',
        openCount: 42,
        closedCount: 118,
        readyCount: 7,
        untriagedCount: 11,
        untriaged4wCount: 3,
        engagedCount: 19,
        aiTriagedCount: 25,
        recommendationCount: 4,
        funnel: {
          ready: 7,
          responded: 12,
          waiting_manual: 5,
          waiting_ai: 4,
          untriaged: 11,
          other: 3,
        },
        pressureAreas: [
          {
            area: 'area:scheduler',
            score: 34,
            contribs: 15,
            age_4w: 3,
            age_1to4w: 6,
            age_rec: 6,
          },
        ],
        weeklyVelocityTotals: { merged: 96, closed_not_merged: 22 },
        partial: false,
        capNote: null,
        syncError: null,
        isOpen: true,
        updatedAt: '2026-11-27T12:00:00Z',
      };
      const ambient: PrStatsPaneState = sample;
      assertStrictEqual(PR_STATS_STATE_KEY, 'magpie-pr-management.prStatsPaneState');
      assertStrictEqual(ambient.repo, 'apache/magpie');
    });
  });

  describe('sanitization & path extraction', () => {
    test('strips ANSI CSI/OSC, BiDi overrides, and C0/C1 controls', () => {
      const dirty = '\x1b[31mEvil\x1b[0m \u202Espoof\u202C\x07\n\t"ok"';
      assertStrictEqual(sanitizeStatsText(dirty, 80), 'Evil spoof ok');
    });

    test('toStatsJsonPath mirrors Path.with_suffix(.json)', () => {
      assertStrictEqual(toStatsJsonPath('/tmp/scratch/dashboard.html'), '/tmp/scratch/dashboard.json');
      assertStrictEqual(toStatsJsonPath('/tmp/scratch/dashboard.md'), '/tmp/scratch/dashboard.json');
      assertStrictEqual(toStatsJsonPath('/tmp/scratch/dashboard'), '/tmp/scratch/dashboard.json');
      assertStrictEqual(toStatsJsonPath('/tmp/my.stats.html'), '/tmp/my.stats.json');
    });

    test('extractStatsJsonPathFromCommand parses --out and rejects traversal', () => {
      assertStrictEqual(
        extractStatsJsonPathFromCommand(
          'uv run --project tools/pr-management pr-management stats build --saved-dir /tmp/s --viewer Kaap10 --out /tmp/scratch/dashboard.html'
        ),
        '/tmp/scratch/dashboard.json'
      );
      assertStrictEqual(
        extractStatsJsonPathFromCommand(
          'pr-management stats build --out="/tmp/my dir/out.html"'
        ),
        '/tmp/my dir/out.json'
      );
      assertStrictEqual(
        extractStatsJsonPathFromCommand('pr-management stats build --saved-dir /tmp/s'),
        'dashboard.json'
      );
      assertStrictEqual(
        extractStatsJsonPathFromCommand('pr-management stats build --out ../../etc/passwd.html'),
        null
      );
      assertStrictEqual(extractStatsJsonPathFromCommand('git status'), null);
    });

    test('resolveConfinedStatsPath confines reads to session roots and scratch dirs', () => {
      assertStrictEqual(
        resolveConfinedStatsPath('/tmp/scratch/dashboard.json', '/repo', '/repo'),
        '/tmp/scratch/dashboard.json'
      );
      assertStrictEqual(
        resolveConfinedStatsPath('out/dashboard.json', '/repo', '/repo'),
        '/repo/out/dashboard.json'
      );
      assertStrictEqual(
        resolveConfinedStatsPath('/etc/passwd.json', '/repo', '/repo'),
        null
      );
      assertStrictEqual(
        resolveConfinedStatsPath('/tmp/../etc/passwd.json', '/repo', '/repo'),
        null
      );
    });
  });

  describe('parsePrStatsPayload & renderPrStatsPane', () => {
    test('parses intermediates JSON, sorts pressure_areas descending, and keeps aggregate-only fields', () => {
      const payload = JSON.stringify(sampleIntermediates({ health_rating: 'Watch' }));
      const res = parsePrStatsPayload(payload, '/tmp/dashboard.json', '2026-11-27T12:00:00Z');
      assert(res.ok);
      assertStrictEqual(res.state.repo, 'apache/magpie');
      assertStrictEqual(res.state.healthRating, 'Watch');
      assertStrictEqual(res.state.openCount, 42);
      assertStrictEqual(res.state.pressureAreas[0]?.area, 'area:scheduler');
      assertStrictEqual(res.state.pressureAreas[1]?.area, 'area:security');
      assertStrictEqual((res.state as any).viewer, undefined);
    });

    test('renders health rating, funnel, pressure areas, and partial/cap_note warning banner', () => {
      const Box = (props: any) => ({ type: 'Box', props });
      const Text = (props: any) => ({ type: 'Text', props });
      const Button = (props: any) => ({ type: 'Button', props });

      const parsed = parsePrStatsPayload(
        JSON.stringify(
          sampleIntermediates({
            health_rating: 'Needs Attention',
            partial: true,
            cap_note: 'Closed PR search capped at 1000 results',
          })
        ),
        '/tmp/dashboard.json',
        '2026-11-27T12:00:00Z'
      );
      assert(parsed.ok);

      const rendered = JSON.stringify(renderPrStatsPane(Box, Text, Button, parsed.state));
      assert(rendered.includes('PR Backlog Stats — apache/magpie (Needs Attention)'));
      assert(rendered.includes('Warning: Partial snapshot (fetch cut short) — Closed PR search capped at 1000 results'));
      assert(rendered.includes('Open: 42 • Ready: 7 • Untriaged: 11 (>4w: 3)'));
      assert(rendered.includes('Funnel: ready=7 | responded=12'));
      assert(rendered.includes('Velocity (window): merged=96 | closed_not_merged=22'));
      assert(rendered.includes('area:scheduler'));
      assert(rendered.includes('ps:refresh'));
      assert(rendered.includes('ps:close'));
    });
  });

  describe('runtime lifecycle & coexistence', () => {
    test('classifyWriteTarget refuses symlinks and non-regular files before $.fs.read', async () => {
      const symlink$ = createMockEngine({
        fs: {
          stat: async () => ({ kind: 'file', size: 100, mtimeMs: 0, isLink: true }),
        },
      });
      assertStrictEqual(await classifyWriteTarget(symlink$, '/tmp/dashboard.json'), 'unsafe');

      const dir$ = createMockEngine({
        fs: {
          stat: async () => ({ kind: 'directory', size: 0, mtimeMs: 0, isLink: false }),
        },
      });
      assertStrictEqual(await classifyWriteTarget(dir$, '/tmp/dashboard.json'), 'unsafe');
    });

    test('Bash hook hydrates from .json sidecar after next(e) and opens Pane', async () => {
      const jsonPath = '/tmp/scratch/dashboard.json';
      const files: Record<string, string> = {
        [jsonPath]: JSON.stringify(sampleIntermediates({ health_rating: 'Healthy' })),
      };
      let opened = false;
      const mock$ = createMockEngine({
        ui: {
          open: async () => {
            opened = true;
          },
          invalidate: () => {},
        },
        fs: {
          stat: async (p: string) => {
            if (p in files) return { kind: 'file', size: files[p]!.length, mtimeMs: 0, isLink: false };
            throw Object.assign(new Error('ENOENT'), { code: 'ENOENT' });
          },
          read: async (p: string) => files[p] ?? '',
        },
      });

      const out = await handleBashToolCall(
        mock$,
        {
          command:
            'uv run --project tools/pr-management pr-management stats build --saved-dir /tmp/s --viewer Kaap10 --out /tmp/scratch/dashboard.html',
        },
        async () => ({ exitCode: 0 })
      );
      assertStrictEqual(out.exitCode, 0);
      assertStrictEqual(opened, true);
      const savedState = await getPrStatsState(mock$);
      assertStrictEqual(savedState?.healthRating, 'Healthy');
      assertStrictEqual(savedState?.isOpen, true);
    });

    test('ui.render and ui.press delegate cleanly to next(e) when inactive or non-ps button', async () => {
      const mock$ = createMockEngine();
      let delegatedRender = false;
      await handleRenderPrStatsPane(mock$, { site: 'Pane' }, async () => {
        delegatedRender = true;
        return 'other-pane';
      });
      assertStrictEqual(delegatedRender, true);

      let delegatedPress = false;
      await handlePrStatsUiPress(mock$, { id: 'rf:accept' }, async () => {
        delegatedPress = true;
      });
      assertStrictEqual(delegatedPress, true);
    });

    test('ps:close hides pane and /magpie-pr-stats re-opens and returns { text }', async () => {
      const jsonPath = '/tmp/scratch/dashboard.json';
      const files: Record<string, string> = {
        [jsonPath]: JSON.stringify(sampleIntermediates({ health_rating: 'Healthy' })),
      };
      const mock$ = createMockEngine({
        fs: {
          stat: async (p: string) => {
            if (p in files) return { kind: 'file', size: files[p]!.length, mtimeMs: 0, isLink: false };
            throw Object.assign(new Error('ENOENT'), { code: 'ENOENT' });
          },
          read: async (p: string) => files[p] ?? '',
        },
      });

      const cmdRes = await handlePrStatsCommand(mock$, { args: jsonPath });
      assert(cmdRes.text.includes('PR Backlog Stats (apache/magpie: Healthy'));
      assertStrictEqual((await getPrStatsState(mock$))?.isOpen, true);

      await handlePrStatsUiPress(mock$, { id: 'ps:close' }, async () => {});
      assertStrictEqual((await getPrStatsState(mock$))?.isOpen, false);

      let delegatedAfterClose = false;
      await handleRenderPrStatsPane(mock$, { site: 'Pane' }, async () => {
        delegatedAfterClose = true;
      });
      assertStrictEqual(delegatedAfterClose, true);
    });

    test('open PR stats pane takes precedence over stale reviewFindingsState and yields on ps:close', async () => {
      const jsonPath = '/tmp/scratch/dashboard.json';
      const files: Record<string, string> = {
        [jsonPath]: JSON.stringify(sampleIntermediates({ health_rating: 'Healthy' })),
      };
      const mock$ = createMockEngine({
        fs: {
          stat: async (p: string) => {
            if (p in files) return { kind: 'file', size: files[p]!.length, mtimeMs: 0, isLink: false };
            throw Object.assign(new Error('ENOENT'), { code: 'ENOENT' });
          },
          read: async (p: string) => files[p] ?? '',
        },
      });

      mock$.store['reviewFindingsState'] = {
        prNumber: 42,
        findings: [
          {
            id: 'f1',
            file: 'foo.ts',
            line: 10,
            severity: 'minor',
            body: 'Existing review finding',
            action: 'accept',
          },
        ],
        summary: {
          blockingCount: 0,
          majorCount: 0,
          minorCount: 1,
          nitCount: 0,
          total: 1,
          anchoredCount: 1,
          unanchoredCount: 0,
        },
        selectedIndex: 0,
      };

      await handlePrStatsCommand(mock$, { args: jsonPath });
      const statsRendered = JSON.stringify(await handleRenderPane(mock$, { site: 'Pane' }, async () => null));
      assert(statsRendered.includes('PR Backlog Stats — apache/magpie (Healthy)'));

      await handlePrStatsUiPress(mock$, { id: 'ps:close' }, async () => {});
      const findingsRendered = JSON.stringify(await handleRenderPane(mock$, { site: 'Pane' }, async () => null));
      assert(findingsRendered.includes('Existing review finding'));
    });
  });
});
