import type { APIRoute } from 'astro';
import {
  CacheMissingError,
  getConfig,
  getDays,
  getMeta,
  getMetrics,
  isStale,
} from '../../lib/cache';
import type { SummaryResponse } from '../../lib/types';

export const prerender = false;

export const GET: APIRoute = async () => {
  try {
    const [metrics, meta, config, days] = await Promise.all([
      getMetrics(),
      getMeta(),
      getConfig(),
      getDays(),
    ]);
    const stale = await isStale(meta);
    const savingsPct = metrics.mpc.total_bill
      ? (1 - metrics.ppo.total_bill / metrics.mpc.total_bill) * 100
      : 0;

    const body: SummaryResponse = {
      mpc: metrics.mpc,
      learned: metrics.ppo,
      meta,
      savingsPct,
      stale,
      days,
      tariffBlocks: config.tariff_blocks,
    };
    return new Response(JSON.stringify(body), {
      headers: { 'content-type': 'application/json' },
    });
  } catch (err) {
    if (err instanceof CacheMissingError) {
      return new Response(JSON.stringify({ error: err.message }), {
        status: 503,
        headers: { 'content-type': 'application/json' },
      });
    }
    throw err;
  }
};
