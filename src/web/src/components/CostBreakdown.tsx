import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Metrics } from "../lib/types";
import { paletteFor } from "../lib/palette";
import { useThemeMode } from "../lib/useThemeMode";
import { inr } from "../lib/format";

interface Props {
  mpc: Metrics;
  learned: Metrics;
}

export default function CostBreakdown({ mpc, learned }: Props) {
  const mode = useThemeMode();
  const p = paletteFor(mode);
  const axis = mode === "dark" ? "#a3a3a3" : "#525252";

  const data = [
    {
      name: "MPC",
      energy: mpc.total_energy_cost,
      demand: mpc.demand_charge_incurred,
    },
    {
      name: "Learned",
      energy: learned.total_energy_cost,
      demand: learned.demand_charge_incurred,
    },
  ];

  return (
    <section>
      <h2 className="mb-1 text-lg font-semibold text-neutral-900 dark:text-neutral-100 mt-6">
        Cost breakdown
      </h2>
      <p className="mb-3 text-sm text-neutral-500 dark:text-neutral-400">
        Total bill split into energy cost and demand charge.
      </p>
      <div className="rounded-xl border border-neutral-200 bg-white p-4 dark:border-neutral-800 dark:bg-neutral-900">
        <ResponsiveContainer width="100%" height={340}>
          <BarChart data={data} barCategoryGap="45%">
            <CartesianGrid stroke={p.gridline} vertical={false} />
            <XAxis
              dataKey="name"
              tick={{ fill: axis, fontSize: 13 }}
              axisLine={{ stroke: p.gridline }}
              tickLine={false}
            />
            <YAxis
              tick={{ fill: axis, fontSize: 12 }}
              axisLine={false}
              tickLine={false}
              tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}k`}
              width={52}
            />
            <Tooltip
              cursor={{ fill: `rgba(${p.shade}, 0.06)` }}
              formatter={(value: number, name) => [
                inr(value),
                name === "energy" ? "Energy cost" : "Demand charge",
              ]}
              contentStyle={{
                background: p.surface,
                border: `1px solid ${p.gridline}`,
                borderRadius: 8,
                color: axis,
              }}
            />
            <Legend
              formatter={(value) =>
                value === "energy" ? "Energy cost" : "Demand charge"
              }
            />
            {/* 2px surface stroke gives the between-segment gap the mark specs call for. */}
            <Bar
              dataKey="energy"
              stackId="cost"
              fill={p.energy}
              stroke={p.surface}
              strokeWidth={2}
            />
            <Bar
              dataKey="demand"
              stackId="cost"
              fill={p.demand}
              stroke={p.surface}
              strokeWidth={2}
              radius={[4, 4, 0, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
