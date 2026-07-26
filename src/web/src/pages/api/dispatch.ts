import type { APIRoute } from 'astro';
import { CacheMissingError, getDispatch } from '../../lib/cache';
import type { Controller, DispatchResponse } from '../../lib/types';

export const prerender = false;

export const GET: APIRoute = async ({ url }) => {
  const day = url.searchParams.get('day');
  const controllerParam = url.searchParams.get('controller') ?? 'learned';
  const controller: Controller = controllerParam === 'mpc' ? 'mpc' : 'learned';

  if (!day) {
    return new Response(JSON.stringify({ error: 'missing ?day=YYYY-MM-DD' }), {
      status: 400,
      headers: { 'content-type': 'application/json' },
    });
  }

  try {
    const { points, tariffBlocks } = await getDispatch(day, controller);
    const body: DispatchResponse = { day, controller, points, tariffBlocks };
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
