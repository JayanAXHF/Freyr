import type { Meta } from '../lib/types';
import { inr } from '../lib/format';

interface Props {
  learnedBill: number;
  mpcBill: number;
  savingsPct: number;
  stale: boolean;
  meta: Meta;
}

export default function HeroBanner({
  learnedBill,
  mpcBill,
  savingsPct,
  stale,
  meta,
}: Props) {
  return (
    <section className="space-y-4">
      {stale && (
        <div
          role="alert"
          className="rounded-lg border border-amber-400/60 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-500/40 dark:bg-amber-950/40 dark:text-amber-200"
        >
          ⚠️ The deployed model is newer than this cache. Re-run{' '}
          <code className="rounded bg-amber-100 px-1 dark:bg-amber-900/60">
            uv run python scripts_precompute_dashboard.py
          </code>{' '}
          to refresh the numbers.
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
          <div className="text-sm font-medium text-neutral-500 dark:text-neutral-400">
            Learned policy — monthly bill
          </div>
          <div className="mt-2 text-4xl font-semibold tabular-nums text-neutral-900 dark:text-neutral-50">
            {inr(learnedBill)}
          </div>
          <div className="mt-2 inline-flex items-center gap-1 text-sm font-medium text-emerald-600 dark:text-emerald-400">
            <span aria-hidden>▼</span>
            {savingsPct.toFixed(1)}% vs MPC
          </div>
        </div>

        <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
          <div className="text-sm font-medium text-neutral-500 dark:text-neutral-400">
            MPC baseline
          </div>
          <div className="mt-2 text-4xl font-semibold tabular-nums text-neutral-900 dark:text-neutral-50">
            {inr(mpcBill)}
          </div>
        </div>

        <div className="rounded-2xl border border-neutral-200 bg-neutral-50 p-6 text-sm leading-relaxed text-neutral-600 dark:border-neutral-800 dark:bg-neutral-900/50 dark:text-neutral-400">
          Seed-{meta.seed} 30-day forecast-driven run. The learned policy
          arbitrages the battery like MPC and bills below it while holding
          service quality. <span className="font-medium">savings</span> is
          measured against MPC.
        </div>
      </div>
    </section>
  );
}
