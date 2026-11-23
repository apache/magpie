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
  computeContextSaturation,
  formatCost,
  formatTokenCount,
  formatTokenMeterBand,
  handleRenderAbovePrompt,
  normalizeUsageData,
  parseTokenMeterToml,
  renderTokenMeterBandComponent,
  resetConfigCache,
  resolveTokenMeterConfig,
} from './token-meter-band.js';
import type { SessionUsageData, TokenMeterConfig } from './types.js';

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

describe('token-meter-band mod', () => {
  describe('formatTokenCount', () => {
    test('formats boundary and invalid inputs safely to 0', () => {
      assertStrictEqual(formatTokenCount(0), '0');
      assertStrictEqual(formatTokenCount(-50), '0');
      assertStrictEqual(formatTokenCount(NaN), '0');
      assertStrictEqual(formatTokenCount(Infinity), '0');
      assertStrictEqual(formatTokenCount(-Infinity), '0');
    });

    test('formats small integers (<1000) as raw numbers', () => {
      assertStrictEqual(formatTokenCount(1), '1');
      assertStrictEqual(formatTokenCount(42), '42');
      assertStrictEqual(formatTokenCount(850), '850');
      assertStrictEqual(formatTokenCount(999), '999');
    });

    test('formats thousands with k suffix and 1 decimal place or integer', () => {
      assertStrictEqual(formatTokenCount(1_000), '1k');
      assertStrictEqual(formatTokenCount(1_450), '1.5k');
      assertStrictEqual(formatTokenCount(38_400), '38.4k');
      assertStrictEqual(formatTokenCount(200_000), '200k');
      assertStrictEqual(formatTokenCount(999_900), '999.9k');
    });

    test('formats millions with M suffix and 1 decimal place or integer', () => {
      assertStrictEqual(formatTokenCount(1_000_000), '1M');
      assertStrictEqual(formatTokenCount(1_250_000), '1.3M');
      assertStrictEqual(formatTokenCount(2_000_000), '2M');
      assertStrictEqual(formatTokenCount(10_500_000), '10.5M');
    });
  });

  describe('computeContextSaturation', () => {
    test('computes percentage safely for standard ratios', () => {
      const sat = computeContextSaturation(38_400, 200_000);
      assert(sat !== null);
      assertStrictEqual(Math.round(sat! * 10) / 10, 19.2);
    });

    test('handles 0 and negative used tokens', () => {
      assertStrictEqual(computeContextSaturation(0, 200_000), 0);
      assertStrictEqual(computeContextSaturation(-100, 200_000), 0);
    });

    test('computes saturated percentage correctly', () => {
      const sat = computeContextSaturation(190_000, 200_000);
      assert(sat !== null);
      assertStrictEqual(Math.round(sat! * 10) / 10, 95);
    });

    test('returns null when maxTokens is missing, 0, negative, or invalid', () => {
      assertStrictEqual(computeContextSaturation(500, undefined), null);
      assertStrictEqual(computeContextSaturation(500, 0), null);
      assertStrictEqual(computeContextSaturation(500, -200_000), null);
      assertStrictEqual(computeContextSaturation(500, NaN), null);
      assertStrictEqual(computeContextSaturation(500, Infinity), null);
    });
  });

  describe('formatCost', () => {
    test('returns null for undefined, null, non-numeric, or negative cost', () => {
      assertStrictEqual(formatCost(undefined), null);
      assertStrictEqual(formatCost(null as any), null);
      assertStrictEqual(formatCost(NaN), null);
      assertStrictEqual(formatCost(-0.5), null);
    });

    test('formats cost in cents and dollars', () => {
      assertStrictEqual(formatCost(0), '$0.00');
      assertStrictEqual(formatCost(0.14), '$0.14');
      assertStrictEqual(formatCost(1.5), '$1.50');
      assertStrictEqual(formatCost(12.345), '$12.35');
    });

    test('formats fractional cents under $0.01', () => {
      assertStrictEqual(formatCost(0.005), '<$0.01');
      assertStrictEqual(formatCost(0.0001), '<$0.01');
    });
  });

  describe('normalizeUsageData', () => {
    test('normalizes engine mod API shape: context { tokens, window, percent } and cost { usd }', () => {
      const raw = {
        startedAt: 12345678,
        context: {
          tokens: 38_400,
          window: 200_000,
          percent: 19.2,
        },
        cost: {
          usd: 0.14,
        },
      };
      const normalized = normalizeUsageData(raw);
      assert(normalized !== null);
      assertStrictEqual(normalized!.tokens, 38_400);
      assertStrictEqual(normalized!.window, 200_000);
      assertStrictEqual(normalized!.percent, 19.2);
      assertStrictEqual(normalized!.costUsd, 0.14);
    });

    test('normalizes legacy flat shape with input/output tokens safely', () => {
      const raw = {
        inputTokens: 10_000,
        outputTokens: 5_000,
        contextWindow: 200_000,
        costUsd: 0.14,
      };
      const normalized = normalizeUsageData(raw);
      assert(normalized !== null);
      assertStrictEqual(normalized!.tokens, 15_000);
      assertStrictEqual(normalized!.window, 200_000);
      assertStrictEqual(normalized!.costUsd, 0.14);
    });

    test('returns null for non-object, empty, or 0-token usage', () => {
      assertStrictEqual(normalizeUsageData(null), null);
      assertStrictEqual(normalizeUsageData(undefined), null);
      assertStrictEqual(normalizeUsageData('string'), null);
      assertStrictEqual(normalizeUsageData({ context: { tokens: 0 } }), null);
      assertStrictEqual(normalizeUsageData({ context: { tokens: -5 } }), null);
      assertStrictEqual(normalizeUsageData({ inputTokens: 0, outputTokens: 0 }), null);
    });
  });

  describe('parseTokenMeterToml', () => {
    test('parses toml content with keys and comments', () => {
      const toml = `
# Apache Magpie Token Meter Configuration
[token_meter]
enabled = false
mode = "threshold-only"
warn_percent = 65
critical_percent = 90
`;
      const parsed = parseTokenMeterToml(toml);
      assertStrictEqual(parsed.enabled, false);
      assertStrictEqual(parsed.mode, 'threshold-only');
      assertStrictEqual(parsed.warnPercent, 65);
      assertStrictEqual(parsed.criticalPercent, 90);
    });

    test('preserves # inside quoted values', () => {
      const toml = `
mode = "threshold-only" # real comment
`;
      const parsed = parseTokenMeterToml(toml);
      assertStrictEqual(parsed.mode, 'threshold-only');
    });

    test('rejects configuration where warn_percent >= critical_percent', () => {
      const toml = `
warn_percent = 90
critical_percent = 80
`;
      const parsed = parseTokenMeterToml(toml);
      // Both discarded to fall back to default thresholds
      assertStrictEqual(parsed.warnPercent, undefined);
      assertStrictEqual(parsed.criticalPercent, undefined);
    });

    test('handles empty or whitespace strings', () => {
      assertDeepStrictEqual(parseTokenMeterToml(''), {});
      assertDeepStrictEqual(parseTokenMeterToml('   \n\n# comment\n'), {});
    });

    test('ignores invalid numeric percentages', () => {
      const toml = `
warn_percent = 150
critical_percent = -10
`;
      const parsed = parseTokenMeterToml(toml);
      assertStrictEqual(parsed.warnPercent, undefined);
      assertStrictEqual(parsed.criticalPercent, undefined);
    });
  });

  describe('resolveTokenMeterConfig', () => {
    test('returns default configuration when no file or env present', async () => {
      resetConfigCache();
      const cfg = await resolveTokenMeterConfig({
        now: 1000,
      });
      assertStrictEqual(cfg.enabled, true);
      assertStrictEqual(cfg.mode, 'always');
      assertStrictEqual(cfg.warnPercent, 70);
      assertStrictEqual(cfg.criticalPercent, 85);
    });

    test('MAGPIE_TOKEN_METER envValue disables meter', async () => {
      resetConfigCache();
      const cfg1 = await resolveTokenMeterConfig({ envValue: '0' });
      assertStrictEqual(cfg1.enabled, false);

      const cfg2 = await resolveTokenMeterConfig({ envValue: 'false' });
      assertStrictEqual(cfg2.enabled, false);

      const cfg3 = await resolveTokenMeterConfig({ envValue: 'disabled' });
      assertStrictEqual(cfg3.enabled, false);
    });

    test('reads personal layer (.apache-magpie-local) before project layer (.apache-magpie-overrides)', async () => {
      resetConfigCache();
      const readPaths: string[] = [];
      const mockReadFile = async (path: string) => {
        readPaths.push(path);
        if (path.includes('.apache-magpie-local')) {
          return 'warn_percent = 60\ncritical_percent = 80';
        }
        if (path.includes('.apache-magpie-overrides')) {
          return 'warn_percent = 75\ncritical_percent = 90';
        }
        return null;
      };

      const cfg = await resolveTokenMeterConfig({
        cwd: '/work/repo',
        readFile: mockReadFile,
      });

      assertStrictEqual(cfg.warnPercent, 60);
      assertStrictEqual(cfg.criticalPercent, 80);
      // Confirmed personal layer was read first and matched
      assert(readPaths[0]?.includes('.apache-magpie-local'));
    });

    test('keys cache by cwd path and invalidates across roots', async () => {
      resetConfigCache();
      let readCount = 0;
      const mockReadFile = async (path: string) => {
        readCount++;
        if (path.startsWith('/work/repo1')) return 'warn_percent = 60';
        if (path.startsWith('/work/repo2')) return 'warn_percent = 80';
        return null;
      };

      const cfg1 = await resolveTokenMeterConfig({
        cwd: '/work/repo1',
        readFile: mockReadFile,
        now: 1000,
      });
      assertStrictEqual(cfg1.warnPercent, 60);
      assertStrictEqual(readCount, 1);

      // Same root within TTL reuses cache
      const cfg1Cached = await resolveTokenMeterConfig({
        cwd: '/work/repo1',
        readFile: mockReadFile,
        now: 5000,
      });
      assertStrictEqual(cfg1Cached.warnPercent, 60);
      assertStrictEqual(readCount, 1);

      // Different root invalidates/re-reads
      const cfg2 = await resolveTokenMeterConfig({
        cwd: '/work/repo2',
        readFile: mockReadFile,
        now: 5000,
      });
      assertStrictEqual(cfg2.warnPercent, 80);
      assert(readCount > 1);
    });
  });

  describe('formatTokenMeterBand', () => {
    const config: TokenMeterConfig = {
      enabled: true,
      mode: 'always',
      warnPercent: 70,
      criticalPercent: 85,
    };

    test('formats info tier (<70% saturation) with cost', () => {
      const usage: SessionUsageData = {
        tokens: 38_400,
        window: 200_000,
        percent: 19.2,
        costUsd: 0.14,
      };
      const formatted = formatTokenMeterBand(usage, config);
      assert(formatted !== null);
      assertStrictEqual(
        formatted!.text,
        '[Context Meter] 38.4k / 200k tokens (19.2% context used) \u00B7 $0.14 session cost'
      );
      assertStrictEqual(formatted!.color, 'info');
      assertStrictEqual(Math.round(formatted!.percentage! * 10) / 10, 19.2);
    });

    test('formats warning tier (70% - 84.9%)', () => {
      const usage: SessionUsageData = {
        tokens: 150_000,
        window: 200_000,
        percent: 75.0,
        costUsd: 0.55,
      };
      const formatted = formatTokenMeterBand(usage, config);
      assert(formatted !== null);
      assertStrictEqual(
        formatted!.text,
        '[Context Meter] 150k / 200k tokens (75.0% context used) \u00B7 $0.55 session cost'
      );
      assertStrictEqual(formatted!.color, 'warning');
    });

    test('formats critical / error tier (>=85%)', () => {
      const usage: SessionUsageData = {
        tokens: 180_000,
        window: 200_000,
        percent: 90.0,
      };
      const formatted = formatTokenMeterBand(usage, config);
      assert(formatted !== null);
      assertStrictEqual(
        formatted!.text,
        '[Context Meter] 180k / 200k tokens (90.0% context used)'
      );
      assertStrictEqual(formatted!.color, 'error');
    });

    test('formats cleanly when window is omitted', () => {
      const usage: SessionUsageData = {
        tokens: 38_400,
        costUsd: 0.14,
      };
      const formatted = formatTokenMeterBand(usage, config);
      assert(formatted !== null);
      assertStrictEqual(
        formatted!.text,
        '[Context Meter] 38.4k tokens \u00B7 $0.14 session cost'
      );
      assertStrictEqual(formatted!.color, 'info');
      assertStrictEqual(formatted!.percentage, null);
    });

    test('suppresses display when mode is threshold-only and saturation is below threshold', () => {
      const thresholdConfig: TokenMeterConfig = {
        enabled: true,
        mode: 'threshold-only',
        warnPercent: 70,
        criticalPercent: 85,
      };
      const usageBelow: SessionUsageData = {
        tokens: 15_000,
        window: 200_000,
        percent: 7.5,
      };
      assertStrictEqual(formatTokenMeterBand(usageBelow, thresholdConfig), null);

      const usageAbove: SessionUsageData = {
        tokens: 150_000,
        window: 200_000,
        percent: 75.0,
      };
      const formattedAbove = formatTokenMeterBand(usageAbove, thresholdConfig);
      assert(formattedAbove !== null);
      assertStrictEqual(formattedAbove!.color, 'warning');
    });

    test('returns null when config.enabled is false', () => {
      const disabledConfig: TokenMeterConfig = { ...config, enabled: false };
      const usage: SessionUsageData = {
        tokens: 15_000,
      };
      assertStrictEqual(formatTokenMeterBand(usage, disabledConfig), null);
    });
  });

  describe('renderTokenMeterBandComponent', () => {
    test('renders Box and Text components with formatted text and color', () => {
      const mockBox = (props: any) => ({ type: 'Box', ...props });
      const mockText = (props: any) => ({ type: 'Text', ...props });

      const formatted = {
        text: '[Context Meter] 38.4k / 200k tokens (19.2% context used)',
        color: 'info' as const,
        percentage: 19.2,
        tokens: 38_400,
      };

      const rendered = renderTokenMeterBandComponent(mockBox, mockText, formatted);
      assert(rendered !== null);
      assertStrictEqual(rendered.type, 'Box');
      assertStrictEqual(rendered.padding, 0);
      assertStrictEqual(rendered.children.length, 1);
      assertStrictEqual(rendered.children[0].type, 'Text');
      assertStrictEqual(rendered.children[0].color, 'info');
      assertStrictEqual(rendered.children[0].bold, true);
      assertStrictEqual(rendered.children[0].children[0], formatted.text);
    });

    test('returns null if parameters are missing', () => {
      assertStrictEqual(renderTokenMeterBandComponent(null, null, null), null);
      assertStrictEqual(renderTokenMeterBandComponent(() => {}, null, null), null);
    });
  });

  describe('handleRenderAbovePrompt lifecycle hook', () => {
    test('yields immediately when e.props.hasSurvey is true', async () => {
      let nextCalled = false;
      const mock$ = {
        session: {
          usage: async () => ({ context: { tokens: 50_000 } }),
        },
      };
      const next = (evt: any) => {
        nextCalled = true;
        return 'survey-yield';
      };

      const res = await handleRenderAbovePrompt(
        mock$,
        { component: 'AbovePrompt', props: { hasSurvey: true } },
        next
      );
      assertStrictEqual(nextCalled, true);
      assertStrictEqual(res, 'survey-yield');
    });

    test('calls next(e) and bypasses when MAGPIE_TOKEN_METER=0 via $.env', async () => {
      let nextCalled = false;
      const mock$ = {
        env: {
          get: async (name: string) => (name === 'MAGPIE_TOKEN_METER' ? '0' : undefined),
        },
        session: {
          usage: async () => ({ context: { tokens: 50_000 } }),
        },
      };
      const next = (evt: any) => {
        nextCalled = true;
        return 'next-result';
      };

      const res = await handleRenderAbovePrompt(mock$, { component: 'AbovePrompt' }, next);
      assertStrictEqual(nextCalled, true);
      assertStrictEqual(res, 'next-result');
    });

    test('calls next(e) when $.session.usage is missing or throws', async () => {
      let nextCount = 0;
      const next = () => {
        nextCount++;
        return 'bypass';
      };

      // Missing usage
      const mockMissing$ = { session: {} };
      const res1 = await handleRenderAbovePrompt(mockMissing$, {}, next);
      assertStrictEqual(res1, 'bypass');
      assertStrictEqual(nextCount, 1);

      // Throwing usage
      const mockThrowing$ = {
        session: {
          usage: async () => {
            throw new Error('Engine usage unavailable');
          },
        },
      };
      const res2 = await handleRenderAbovePrompt(mockThrowing$, {}, next);
      assertStrictEqual(res2, 'bypass');
      assertStrictEqual(nextCount, 2);
    });

    test('renders banner component when usage is valid', async () => {
      resetConfigCache();
      const mock$ = {
        session: {
          usage: async () => ({
            startedAt: Date.now(),
            context: {
              tokens: 38_400,
              window: 200_000,
              percent: 19.2,
            },
            cost: { usd: 0.14 },
          }),
          root: async () => '/work/repo',
        },
        fs: {
          read: async () => null,
        },
        ui: {
          resolve: (e: any) => ({
            Box: (p: any) => ({ type: 'Box', ...p }),
            Text: (p: any) => ({ type: 'Text', ...p }),
          }),
        },
      };

      let nextCalled = false;
      const next = () => {
        nextCalled = true;
      };

      const component = await handleRenderAbovePrompt(mock$, { component: 'AbovePrompt' }, next);
      assertStrictEqual(nextCalled, false);
      assert(component !== null);
      assertStrictEqual(component.type, 'Box');
      assertStrictEqual(component.children[0].type, 'Text');
      assertStrictEqual(
        component.children[0].children[0],
        '[Context Meter] 38.4k / 200k tokens (19.2% context used) \u00B7 $0.14 session cost'
      );
      assertStrictEqual(component.children[0].color, 'info');
    });
  });
});
