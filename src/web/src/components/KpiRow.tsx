import type { Metrics } from '../lib/types';
import { inr, num } from '../lib/format';

interface Props {
  mpc: Metrics;
  learned: Metrics;
}

interface KpiSpec {
  label: string;
  key: keyof Metrics;
  format: (v: number) => string;
  lowerIsBetter: boolean;
  scale?: number;
}

const SPECS: KpiSpec[] = [
  { label: 'Total bill', key: 'total_bill', format: (v) => inr(v), lowerIsBetter: true },
  { label: 'Energy cost', key: 'total_energy_cost', format: (v) => inr(v), lowerIsBetter: true },
  { label: 'Demand charge', key: 'demand_charge_incurred', format: (v) => inr(v), lowerIsBetter: true },
  { label: 'Peak', key: 'peak_kva', format: (v) => `${num(v, 1)} kVA`, lowerIsBetter: true },
  {
    label: 'Solar self-use',
    key: 'solar_self_consumption',
    format: (v) => `${num(v, 0)}%`,
    lowerIsBetter: false,
    scale: 100,
  },
];

function Kpi({ spec, mpc, learned }: { spec: KpiSpec; mpc: Metrics; learned: Metrics }) {
  const scale = spec.scale ?? 1;
  const mpcValue = (mpc[spec.key] as number) * scale;
  const learnedValue = (learned[spec.key] as number) * scale;
  const delta = learnedValue - mpcValue;
  // "Better" = the delta points the good direction.
  const better = spec.lowerIsBetter ? delta < 0 : delta > 0;
  const sign = delta < 0 ? '-' : '+';
  const deltaColor = better
    ? 'text-emerald-600 dark:text-emerald-400'
    : 'text-red-600 dark:text-red-400';

  return (
    <div className="rounded-xl border border-neutral-200 bg-white p-4 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
      <div className="text-xs font-medium uppercase tracking-wide text-neutral-500 dark:text-neutral-400">
        {spec.label}
      </div>
      <div className="mt-1 text-2xl font-semibold tabular-nums text-neutral-900 dark:text-neutral-50">
        {spec.format(learnedValue)}
      </div>
      <div className={`mt-1 text-sm font-medium tabular-nums ${deltaColor}`}>
        {sign}
        {spec.format(Math.abs(delta)).replace(/^-/, '')} vs MPC
      </div>
    </div>
  );
}

export default function KpiRow({ mpc, learned }: Props) {
  return (
    <section>
      <h2 className="mb-3 text-lg font-semibold text-neutral-900 dark:text-neutral-100">
        MPC vs learned
      </h2>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {SPECS.map((spec) => (
          <Kpi key={spec.key} spec={spec} mpc={mpc} learned={learned} />
        ))}
      </div>
    </section>
  );
}
