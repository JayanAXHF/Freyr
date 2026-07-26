import type { Metrics } from '../lib/types';
import { num } from '../lib/format';

interface Props {
  mpc: Metrics;
  learned: Metrics;
}

interface Row {
  label: string;
  key: keyof Metrics;
  digits: number;
}

const ROWS: Row[] = [
  { label: 'Energy cost (₹)', key: 'total_energy_cost', digits: 2 },
  { label: 'Demand charge (₹)', key: 'demand_charge_incurred', digits: 2 },
  { label: 'Total bill (₹)', key: 'total_bill', digits: 2 },
  { label: 'Peak (kVA)', key: 'peak_kva', digits: 2 },
  { label: 'Shed load (kWh)', key: 'shed_load_kwh', digits: 2 },
  { label: 'Shed events', key: 'shed_events', digits: 0 },
  { label: 'Unmet load (kWh)', key: 'unmet_load_kwh', digits: 2 },
  { label: 'Unmet events', key: 'unmet_events', digits: 0 },
  { label: 'Solar self-consumption', key: 'solar_self_consumption', digits: 3 },
];

export default function MetricsTable({ mpc, learned }: Props) {
  // Service-quality gate mirrors the Streamlit table: learned shed must stay
  // within 1.5x of MPC's (shed count too) to count savings as legitimate.
  const serviceOk =
    learned.shed_load_kwh <= mpc.shed_load_kwh * 1.5 &&
    learned.shed_events <= mpc.shed_events * 1.5;
  const savingsPct = serviceOk
    ? (1 - learned.total_bill / mpc.total_bill) * 100
    : NaN;

  return (
    <section>
      <h2 className="mb-3 text-lg font-semibold text-neutral-900 dark:text-neutral-100">
        Full metrics
      </h2>
      <div className="overflow-x-auto rounded-xl border border-neutral-200 dark:border-neutral-800">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-neutral-50 text-left text-neutral-500 dark:bg-neutral-900 dark:text-neutral-400">
              <th className="px-4 py-2 font-medium">Metric</th>
              <th className="px-4 py-2 text-right font-medium">MPC</th>
              <th className="px-4 py-2 text-right font-medium">Learned</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-neutral-100 dark:divide-neutral-800">
            {ROWS.map((row) => (
              <tr key={row.key} className="text-neutral-800 dark:text-neutral-200">
                <td className="px-4 py-2">{row.label}</td>
                <td className="px-4 py-2 text-right tabular-nums">
                  {num(mpc[row.key] as number, row.digits)}
                </td>
                <td className="px-4 py-2 text-right tabular-nums">
                  {num(learned[row.key] as number, row.digits)}
                </td>
              </tr>
            ))}
            <tr className="text-neutral-800 dark:text-neutral-200">
              <td className="px-4 py-2">Service quality OK</td>
              <td className="px-4 py-2 text-right">—</td>
              <td className="px-4 py-2 text-right">{serviceOk ? '✅' : '❌'}</td>
            </tr>
            <tr className="font-medium text-neutral-900 dark:text-neutral-100">
              <td className="px-4 py-2">Savings vs MPC</td>
              <td className="px-4 py-2 text-right">—</td>
              <td className="px-4 py-2 text-right tabular-nums text-emerald-600 dark:text-emerald-400">
                {Number.isNaN(savingsPct) ? '—' : `${savingsPct.toFixed(2)}%`}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  );
}
