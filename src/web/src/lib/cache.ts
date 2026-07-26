// Live readers for the on-disk dashboard cache (outputs/dashboard/*.json),
// written by src/shriteq/eval/dashboard_cache.py. The Astro API routes call
// these on every request so the page always reflects the current cache.

import { promises as fs } from "node:fs";
import path from "node:path";
import type {
  Controller,
  DispatchPoint,
  Meta,
  Metrics,
  TariffBlock,
} from "./types";

// Default: <repo-root>/outputs/dashboard, resolved from the web/ working dir.
// Override with DASHBOARD_CACHE_DIR for other layouts.
const CACHE_DIR =
  process.env.DASHBOARD_CACHE_DIR ??
  path.resolve(process.cwd(), "..", "..", "outputs", "dashboard");

// The repo root is two levels up from the cache dir; meta.model_path is
// relative to it.
const REPO_ROOT = path.resolve(CACHE_DIR, "..", "..");

interface RawTrace {
  timestamp: string;
  soc: number;
  battery_charge_kw: number;
  battery_discharge_kw: number;
  grid_import_kw: number;
  controller: string;
}

interface RawSeries {
  timestamp: string;
  load: number;
  solar: number;
}

interface Config {
  tariff_blocks: TariffBlock[];
  demand_charge_inr_per_kva_month: number;
  tz: string;
  timestep_minutes: number;
}

// mtime-keyed memo: parsing the ~2MB traces.json on every request is wasteful,
// but the cache only changes when the precompute script reruns. Re-read only
// when the file's mtime advances.
const memo = new Map<string, { mtime: number; value: unknown }>();

async function readJson<T>(file: string): Promise<T> {
  const full = path.join(CACHE_DIR, file);
  const stat = await fs.stat(full);
  const cached = memo.get(full);
  if (cached && cached.mtime === stat.mtimeMs) {
    return cached.value as T;
  }
  const value = JSON.parse(await fs.readFile(full, "utf8")) as T;
  memo.set(full, { mtime: stat.mtimeMs, value });
  return value;
}

export class CacheMissingError extends Error {}

async function readOrThrow<T>(file: string): Promise<T> {
  try {
    return await readJson<T>(file);
  } catch (err) {
    if ((err as NodeJS.ErrnoException).code === "ENOENT") {
      throw new CacheMissingError(
        `Missing ${file} in ${CACHE_DIR}. Run: uv run python scripts_precompute_dashboard.py`,
      );
    }
    throw err;
  }
}

export interface Metricsish {
  mpc: Metrics;
  ppo: Metrics;
}

/** The date portion (YYYY-MM-DD) of an ISO timestamp, in its original offset. */
function dayOf(iso: string): string {
  return iso.slice(0, 10);
}

/** "HH:MM" from an ISO timestamp, in its original offset (no TZ conversion). */
function hhmm(iso: string): string {
  return iso.slice(11, 16);
}

export async function getMetrics(): Promise<Metricsish> {
  return readOrThrow<Metricsish>("metrics.json");
}

export async function getMeta(): Promise<Meta> {
  return readOrThrow<Meta>("meta.json");
}

export async function getConfig(): Promise<Config> {
  return readOrThrow<Config>("config.json");
}

export async function getDays(): Promise<string[]> {
  const traces = await readOrThrow<RawTrace[]>("traces.json");
  const days = new Set<string>();
  for (const row of traces) days.add(dayOf(row.timestamp));
  return [...days].sort();
}

/** True when the deployed model on disk is newer than the cached run. */
export async function isStale(meta: Meta): Promise<boolean> {
  if (meta.model_mtime == null) return false;
  try {
    const stat = await fs.stat(path.join(REPO_ROOT, meta.model_path));
    // Python st_mtime is in seconds; Node mtimeMs is milliseconds.
    return stat.mtimeMs / 1000 > meta.model_mtime;
  } catch {
    return false;
  }
}

const CONTROLLER_KEY: Record<Controller, string> = {
  learned: "ppo",
  mpc: "mpc",
};

export async function getDispatch(
  day: string,
  controller: Controller,
): Promise<{ points: DispatchPoint[]; tariffBlocks: TariffBlock[] }> {
  const [traces, series, config] = await Promise.all([
    readOrThrow<RawTrace[]>("traces.json"),
    readOrThrow<RawSeries[]>("series.json"),
    getConfig(),
  ]);

  const key = CONTROLLER_KEY[controller];
  const seriesByTs = new Map<string, RawSeries>();
  for (const row of series) {
    if (dayOf(row.timestamp) === day) seriesByTs.set(row.timestamp, row);
  }

  const points: DispatchPoint[] = [];
  for (const row of traces) {
    if (row.controller !== key || dayOf(row.timestamp) !== day) continue;
    const s = seriesByTs.get(row.timestamp);
    points.push({
      timestamp: row.timestamp,
      label: hhmm(row.timestamp),
      load: s?.load ?? 0,
      solar: s?.solar ?? 0,
      gridImport: row.grid_import_kw,
      batteryNet: row.battery_discharge_kw - row.battery_charge_kw,
      socPct: row.soc * 100,
    });
  }
  points.sort((a, b) => a.timestamp.localeCompare(b.timestamp));
  return { points, tariffBlocks: config.tariff_blocks };
}
