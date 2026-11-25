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

import type {
  FormattedTokenMeter,
  SessionUsageData,
  TokenMeterColor,
  TokenMeterConfig,
  TokenMeterMode,
} from './types.js';

export const DEFAULT_WARN_PERCENT = 70;
export const DEFAULT_CRITICAL_PERCENT = 85;
export const CONFIG_CACHE_TTL_MS = 10_000;

export const DEFAULT_CONFIG: TokenMeterConfig = {
  enabled: true,
  mode: 'always',
  warnPercent: DEFAULT_WARN_PERCENT,
  criticalPercent: DEFAULT_CRITICAL_PERCENT,
};

let cachedConfig: TokenMeterConfig | null = null;
let cachedCwd: string | null = null;
let cachedConfigTimestamp = 0;

/**
 * Resets the in-memory configuration cache (useful for testing).
 */
export function resetConfigCache(): void {
  cachedConfig = null;
  cachedCwd = null;
  cachedConfigTimestamp = 0;
}

/**
 * Formats token counts into concise human-readable notations (e.g. 850, 38.4k, 200k, 1.3M).
 * Non-finite or negative values format safely as "0".
 */
export function formatTokenCount(tokens: number): string {
  if (!Number.isFinite(tokens) || tokens <= 0) return '0';

  if (tokens < 1_000) {
    return Math.round(tokens).toString();
  }

  if (tokens < 1_000_000) {
    const val = tokens / 1_000;
    const rounded = Math.round(val * 10) / 10;
    return (Number.isInteger(rounded) ? rounded.toFixed(0) : rounded.toFixed(1)) + 'k';
  }

  const val = tokens / 1_000_000;
  const rounded = Math.round(val * 10) / 10;
  return (Number.isInteger(rounded) ? rounded.toFixed(0) : rounded.toFixed(1)) + 'M';
}

/**
 * Computes context saturation percentage safely, preventing NaN and division by zero.
 * Returns null when max is undefined, non-positive, or non-finite.
 */
export function computeContextSaturation(used: number, max?: number): number | null {
  if (max === undefined || max === null || !Number.isFinite(max) || max <= 0) {
    return null;
  }
  if (!Number.isFinite(used) || used <= 0) {
    return 0;
  }
  return (used / max) * 100;
}

/**
 * Formats monetary USD cost into a standard string representation ($X.XX or <$0.01).
 * Returns null if cost is undefined, non-numeric, or negative.
 */
export function formatCost(costUsd?: number): string | null {
  if (costUsd === undefined || costUsd === null || !Number.isFinite(costUsd) || costUsd < 0) {
    return null;
  }
  if (costUsd > 0 && costUsd < 0.01) {
    return '<$0.01';
  }
  return `$${costUsd.toFixed(2)}`;
}

/**
 * Normalizes raw session usage payload from $.session.usage().
 * Primary shape matches Claude Code mod API:
 *   { startedAt, context: { tokens?, window, percent? }, rateLimits, cost?: { usd } }
 * Fallbacks safely to legacy / flat payloads if present.
 */
export function normalizeUsageData(raw: any): SessionUsageData | null {
  if (!raw || typeof raw !== 'object') {
    return null;
  }

  const ctx = raw.context ?? {};
  const rawTokens =
    ctx.tokens ??
    raw.totalTokens ??
    raw.total_tokens ??
    (Number(raw.inputTokens ?? 0) + Number(raw.outputTokens ?? 0));
  const tokens = Number(rawTokens);

  if (!Number.isFinite(tokens) || tokens <= 0) {
    return null;
  }

  const rawWindow =
    ctx.window ??
    raw.maxTokens ??
    raw.max_tokens ??
    raw.contextWindow ??
    raw.context_window ??
    raw.max_context_tokens;
  const window =
    rawWindow !== undefined &&
    rawWindow !== null &&
    Number.isFinite(Number(rawWindow)) &&
    Number(rawWindow) > 0
      ? Number(rawWindow)
      : undefined;

  let percent: number | undefined;
  if (ctx.percent !== undefined && ctx.percent !== null && Number.isFinite(Number(ctx.percent))) {
    percent = Math.max(0, Math.min(100, Number(ctx.percent)));
  } else if (window && window > 0) {
    percent = Math.max(0, Math.min(100, (tokens / window) * 100));
  }

  const rawCost = raw.cost?.usd ?? raw.costUsd ?? raw.cost_usd ?? raw.cost;
  const costUsd =
    rawCost !== undefined &&
    rawCost !== null &&
    Number.isFinite(Number(rawCost)) &&
    Number(rawCost) >= 0
      ? Number(rawCost)
      : undefined;

  return {
    tokens,
    window,
    percent,
    costUsd,
  };
}

/**
 * Strips comments from a TOML line respecting single and double quote boundaries.
 */
function stripTomlComment(line: string): string {
  let inDouble = false;
  let inSingle = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"' && !inSingle) {
      inDouble = !inDouble;
    } else if (ch === "'" && !inDouble) {
      inSingle = !inSingle;
    } else if (ch === '#' && !inDouble && !inSingle) {
      return line.slice(0, i);
    }
  }
  return line;
}

/**
 * Lightweight, zero-dependency parser for token-meter.toml configuration.
 * Strips comments outside quotes. Threshold ordering (warnPercent < criticalPercent)
 * is validated after merging with defaults in resolveTokenMeterConfig.
 */
export function parseTokenMeterToml(content: string): Partial<TokenMeterConfig> {
  const result: Partial<TokenMeterConfig> = {};
  if (typeof content !== 'string' || !content.trim()) return result;

  const lines = content.split('\n');
  for (const rawLine of lines) {
    const cleanLine = stripTomlComment(rawLine);
    const trimmed = cleanLine.trim();
    if (!trimmed || trimmed.startsWith('[')) continue;

    const eqIdx = trimmed.indexOf('=');
    if (eqIdx === -1) continue;

    const key = trimmed.slice(0, eqIdx).trim().toLowerCase();
    const rawVal = trimmed.slice(eqIdx + 1).trim();

    if (key === 'enabled') {
      result.enabled = rawVal === 'true' || rawVal === '1';
    } else if (key === 'mode') {
      const cleanVal = rawVal.replace(/^["']|["']$/g, '').trim().toLowerCase();
      if (cleanVal === 'threshold-only' || cleanVal === 'always') {
        result.mode = cleanVal as TokenMeterMode;
      }
    } else if (key === 'warn_percent' || key === 'warnpercent') {
      const num = parseFloat(rawVal);
      if (Number.isFinite(num) && num >= 0 && num <= 100) {
        result.warnPercent = num;
      }
    } else if (key === 'critical_percent' || key === 'criticalpercent') {
      const num = parseFloat(rawVal);
      if (Number.isFinite(num) && num >= 0 && num <= 100) {
        result.criticalPercent = num;
      }
    }
  }

  return result;
}

/**
 * Normalizes and resolves a relative path against a base directory without Node built-ins.
 */
function resolveRelativePath(baseDir: string, targetPath: string): string {
  const normTarget = targetPath.replace(/\\/g, '/').replace(/\/+$/, '');
  if (normTarget.startsWith('/') || /^[A-Za-z]:\//.test(normTarget)) {
    return normTarget;
  }
  const normBase = baseDir.replace(/\\/g, '/').replace(/\/+$/, '');
  const parts = normBase ? normBase.split('/') : [];
  for (const seg of normTarget.split('/')) {
    if (!seg || seg === '.') continue;
    if (seg === '..') {
      const first = parts[0];
      if (parts.length > 1 || (parts.length === 1 && first && !/^[A-Za-z]:$/.test(first))) {
        parts.pop();
      }
    } else {
      parts.push(seg);
    }
  }
  return parts.join('/') || '/';
}

/**
 * Returns the parent directory of a normalized forward-slash path.
 */
function parentDir(normPath: string): string {
  const idx = normPath.lastIndexOf('/');
  if (idx <= 0) return idx === 0 ? '/' : '.';
  return normPath.slice(0, idx);
}

/**
 * Resolves `<git-common-dir>` and (for linked worktrees) the main checkout root.
 */
async function resolveGitDirs(
  normCwd: string,
  safeRead: (path: string) => Promise<string | null>
): Promise<{ gitCommonDir: string; mainCheckout: string | null }> {
  const dotGitPath = `${normCwd}/.git`;
  const dotGitContent = await safeRead(dotGitPath);
  if (dotGitContent) {
    const match = dotGitContent.match(/^gitdir:\s*(.+)$/m);
    if (match && match[1]) {
      const gitDir = resolveRelativePath(normCwd, match[1].trim());
      const commonDirContent = await safeRead(`${gitDir}/commondir`);
      const gitCommonDir = commonDirContent?.trim()
        ? resolveRelativePath(gitDir, commonDirContent.trim())
        : gitDir;
      const mainCheckout = gitCommonDir.endsWith('/.git') ? parentDir(gitCommonDir) : null;
      return { gitCommonDir, mainCheckout };
    }
  }
  return { gitCommonDir: dotGitPath, mainCheckout: null };
}

/**
 * Resolves token meter configuration by checking personal layer first,
 * falling back to .apache-magpie-overrides/, and then defaults.
 * Cache is keyed by the session root (cwd).
 */
export async function resolveTokenMeterConfig(options?: {
  envValue?: string;
  readFile?: (path: string) => Promise<string | null>;
  cwd?: string;
  now?: number;
}): Promise<TokenMeterConfig> {
  const envVal = (options?.envValue ?? '').trim().toLowerCase();
  const envDisabled = envVal === '0' || envVal === 'false' || envVal === 'disabled';

  if (envDisabled) {
    return { ...DEFAULT_CONFIG, enabled: false };
  }

  const now = options?.now ?? Date.now();
  const normCwd = (options?.cwd || '.').replace(/\\/g, '/').replace(/\/$/, '');

  if (
    cachedConfig &&
    cachedCwd === normCwd &&
    now - cachedConfigTimestamp < CONFIG_CACHE_TTL_MS
  ) {
    return cachedConfig;
  }

  let fileConfig: Partial<TokenMeterConfig> = {};

  if (options?.readFile) {
    const safeRead = async (p: string): Promise<string | null> => {
      try {
        return await options.readFile!(p);
      } catch {
        return null;
      }
    };

    const [{ gitCommonDir, mainCheckout }, lockContent] = await Promise.all([
      resolveGitDirs(normCwd, safeRead),
      safeRead(`${normCwd}/.apache-magpie.lock`),
    ]);

    const isAdopted = lockContent !== null;
    const candidatePaths: string[] = [];

    if (isAdopted) {
      // Adopted repo: in-tree .apache-magpie-local -> main checkout's .apache-magpie-local (linked worktree) -> .apache-magpie-overrides
      candidatePaths.push(`${normCwd}/.apache-magpie-local/token-meter.toml`);
      if (mainCheckout && mainCheckout !== normCwd) {
        candidatePaths.push(`${mainCheckout}/.apache-magpie-local/token-meter.toml`);
      }
      candidatePaths.push(`${normCwd}/.apache-magpie-overrides/token-meter.toml`);
    } else {
      // Unadopted repo: <git-common-dir>/apache-magpie -> legacy in-tree .apache-magpie-local -> .apache-magpie-overrides
      candidatePaths.push(
        `${gitCommonDir}/apache-magpie/token-meter.toml`,
        `${normCwd}/.apache-magpie-local/token-meter.toml`,
        `${normCwd}/.apache-magpie-overrides/token-meter.toml`
      );
    }

    for (const p of candidatePaths) {
      const content = await safeRead(p);
      if (content) {
        fileConfig = parseTokenMeterToml(content);
        break;
      }
    }
  }

  let warnPercent = fileConfig.warnPercent ?? DEFAULT_CONFIG.warnPercent;
  let criticalPercent = fileConfig.criticalPercent ?? DEFAULT_CONFIG.criticalPercent;
  if (warnPercent >= criticalPercent) {
    warnPercent = DEFAULT_WARN_PERCENT;
    criticalPercent = DEFAULT_CRITICAL_PERCENT;
  }

  const config: TokenMeterConfig = {
    enabled: fileConfig.enabled ?? DEFAULT_CONFIG.enabled,
    mode: fileConfig.mode ?? DEFAULT_CONFIG.mode,
    warnPercent,
    criticalPercent,
  };

  cachedConfig = config;
  cachedCwd = normCwd;
  cachedConfigTimestamp = now;
  return config;
}

/**
 * Formats the badge text, saturation, and color tier for the AbovePrompt banner.
 */
export function formatTokenMeterBand(
  usage: SessionUsageData,
  config: TokenMeterConfig = DEFAULT_CONFIG
): FormattedTokenMeter | null {
  if (!config.enabled) return null;
  if (!usage || usage.tokens <= 0) return null;

  const saturation =
    usage.percent !== undefined
      ? usage.percent
      : computeContextSaturation(usage.tokens, usage.window);

  if (config.mode === 'threshold-only') {
    if (saturation === null || saturation < config.warnPercent) {
      return null;
    }
  }

  let color: TokenMeterColor = 'info';
  if (saturation !== null) {
    if (saturation >= config.criticalPercent) {
      color = 'error';
    } else if (saturation >= config.warnPercent) {
      color = 'warning';
    }
  }

  const usedStr = formatTokenCount(usage.tokens);
  let text = `[Context Meter] ${usedStr}`;

  if (usage.window && usage.window > 0) {
    const maxStr = formatTokenCount(usage.window);
    const pctStr = saturation !== null ? `${saturation.toFixed(1)}%` : '';
    text += ` / ${maxStr} tokens (${pctStr} context used)`;
  } else {
    text += ' tokens';
  }

  const costStr = formatCost(usage.costUsd);
  if (costStr) {
    text += ` \u00B7 ${costStr} session cost`;
  }

  return {
    text,
    color,
    percentage: saturation,
    tokens: usage.tokens,
    window: usage.window,
    costUsd: usage.costUsd,
  };
}

/**
 * Pure component renderer: renders the AbovePrompt band using resolved Box and Text components.
 */
export function renderTokenMeterBandComponent(
  Box: any,
  Text: any,
  formatted: FormattedTokenMeter | null
): any {
  if (!formatted || !Box || !Text) return null;

  return Box({
    padding: 0,
    children: [
      Text({
        children: [formatted.text],
        color: formatted.color,
        bold: true,
      }),
    ],
  });
}

/**
 * Event handler for Claude Code ui.render { component: 'AbovePrompt' }.
 */
export async function handleRenderAbovePrompt(
  $: any,
  e: any,
  next: any
): Promise<any> {
  try {
    // Step aside when a survey holds the band
    if (e?.props?.hasSurvey) {
      if (typeof next === 'function') return next(e);
      return;
    }

    let envVal: string | undefined;
    try {
      envVal = await $.env.get('MAGPIE_TOKEN_METER');
    } catch {
      // Safe fallback when $.env is not available
    }

    const normalizedEnvVal = (envVal ?? '').trim().toLowerCase();
    if (normalizedEnvVal === '0' || normalizedEnvVal === 'false' || normalizedEnvVal === 'disabled') {
      if (typeof next === 'function') return next(e);
      return;
    }

    let rawUsage: any;
    try {
      rawUsage = await $.session.usage();
    } catch {
      if (typeof next === 'function') return next(e);
      return;
    }

    const usage = normalizeUsageData(rawUsage);
    if (!usage || usage.tokens <= 0) {
      if (typeof next === 'function') return next(e);
      return;
    }

    let cwd = '.';
    try {
      cwd = await $.session.root();
    } catch {
      // Fallback to default '.'
    }

    const config = await resolveTokenMeterConfig({
      envValue: envVal,
      cwd,
      readFile: async (p: string) => {
        try {
          return await $.fs.read(p);
        } catch {
          return null;
        }
      },
    });

    const formatted = formatTokenMeterBand(usage, config);
    if (!formatted) {
      if (typeof next === 'function') return next(e);
      return;
    }

    try {
      const { Box, Text } = $.ui.resolve(e);
      if (Box && Text) {
        return renderTokenMeterBandComponent(Box, Text, formatted);
      }
    } catch {
      // Clean fallback
    }
  } catch {
    // Fail open cleanly
  }

  if (typeof next === 'function') {
    return next(e);
  }
}
