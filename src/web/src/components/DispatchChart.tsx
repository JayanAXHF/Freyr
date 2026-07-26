import { useEffect, useMemo, useState } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Controller, DispatchResponse, TariffBlock } from "../lib/types";
import { paletteFor } from "../lib/palette";
import { useThemeMode } from "../lib/useThemeMode";
import { num } from "../lib/format";

interface Props {
  days: string[];
  initialDay: string;
}

const CONTROLLERS: Controller[] = ["learned", "mpc"];

/** Hour → "HH:MM" category label; 24 clamps to the last 15-min slot. */
function hourLabel(hour: number): string {
  if (hour >= 24) return "23:45";
  return `${String(hour).padStart(2, "0")}:00`;
}

function TariffBands({
  blocks,
  shade,
}: {
  blocks: TariffBlock[];
  shade: string;
}) {
  const prices = blocks.map((b) => b.price_inr_per_kwh);
  const low = Math.min(...prices);
  const high = Math.max(...prices);
  return (
    <>
      {blocks.map((b) => {
        const opacity =
          0.05 + ((b.price_inr_per_kwh - low) / (high - low || 1)) * 0.25;
        return (
          <ReferenceArea
            key={b.start_hour}
            x1={hourLabel(b.start_hour)}
            x2={hourLabel(b.end_hour)}
            fill={`rgba(${shade}, ${opacity.toFixed(3)})`}
            fillOpacity={1}
            stroke="none"
            ifOverflow="hidden"
          />
        );
      })}
    </>
  );
}

export default function DispatchChart({ days, initialDay }: Props) {
  const mode = useThemeMode();
  const p = paletteFor(mode);
  const axis = mode === "dark" ? "#a3a3a3" : "#525252";

  const [day, setDay] = useState(initialDay);
  const [controller, setController] = useState<Controller>("learned");
  const [data, setData] = useState<DispatchResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetch(`/api/dispatch?day=${day}&controller=${controller}`)
      .then((r) => r.json())
      .then((body: DispatchResponse) => {
        if (!cancelled) setData(body);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [day, controller]);

  const points = data?.points ?? [];
  const blocks = data?.tariffBlocks ?? [];

  const tooltipStyle = useMemo(
    () => ({
      background: p.surface,
      border: `1px solid ${p.gridline}`,
      borderRadius: 8,
      color: axis,
      fontSize: 12,
    }),
    [p.surface, p.gridline, axis],
  );

  const tickEvery = (label: string, i: number) => (i % 12 === 0 ? label : "");

  return (
    <section>
      <h2 className="mb-1 text-lg font-semibold text-neutral-900 dark:text-neutral-100 mt-6">
        Daily dispatch
      </h2>
      <p className="mb-3 text-sm text-neutral-500 dark:text-neutral-400">
        Battery charges in the cheap ₹5 overnight block and discharges into the
        ₹10 evening peak. Shading = tariff price (darker is pricier).
      </p>

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-sm text-neutral-600 dark:text-neutral-300">
          <span className="font-medium">Day</span>
          <select
            value={day}
            onChange={(e) => setDay(e.target.value)}
            className="rounded-md border border-neutral-300 bg-white px-2 py-1 text-sm text-neutral-900 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-100"
          >
            {days.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        </label>

        <div className="inline-flex overflow-hidden rounded-md border border-neutral-300 dark:border-neutral-700">
          {CONTROLLERS.map((c) => (
            <button
              key={c}
              type="button"
              onClick={() => setController(c)}
              className={`px-3 py-1 text-sm capitalize transition-colors ${
                controller === c
                  ? "bg-neutral-900 text-white dark:bg-neutral-100 dark:text-neutral-900"
                  : "bg-white text-neutral-600 hover:bg-neutral-100 dark:bg-neutral-800 dark:text-neutral-300 dark:hover:bg-neutral-700"
              }`}
            >
              {c}
            </button>
          ))}
        </div>
        {loading && <span className="text-sm text-neutral-400">loading…</span>}
      </div>

      <div className="space-y-2 rounded-xl border border-neutral-200 bg-white p-4 dark:border-neutral-800 dark:bg-neutral-900">
        {/* Panel 1: power flows */}
        <ResponsiveContainer width="100%" height={360}>
          <ComposedChart
            data={points}
            margin={{ top: 8, right: 12, bottom: 0, left: 0 }}
          >
            <TariffBands blocks={blocks} shade={p.shade} />
            <CartesianGrid stroke={p.gridline} vertical={false} />
            <XAxis
              dataKey="label"
              tick={{ fill: axis, fontSize: 11 }}
              tickFormatter={tickEvery}
              axisLine={{ stroke: p.gridline }}
              tickLine={false}
              interval={0}
            />
            <YAxis
              tick={{ fill: axis, fontSize: 11 }}
              axisLine={false}
              tickLine={false}
              width={44}
              label={{
                value: "Power (kW)",
                angle: -90,
                position: "insideLeft",
                fill: axis,
                fontSize: 11,
              }}
            />
            <Tooltip
              contentStyle={tooltipStyle}
              formatter={(v: number, n) => [`${num(v, 2)} kW`, n]}
            />
            <Legend />
            <Area
              type="monotone"
              dataKey="solar"
              name="Solar"
              stroke={p.solar}
              strokeWidth={1.5}
              fill={p.solar}
              fillOpacity={0.18}
            />
            <Area
              type="monotone"
              dataKey="batteryNet"
              name="Battery (+ discharge / − charge)"
              stroke={p.battery}
              strokeWidth={1.5}
              fill={p.battery}
              fillOpacity={0.18}
            />
            <Line
              type="monotone"
              dataKey="load"
              name="Load"
              stroke={p.load}
              strokeWidth={2}
              dot={false}
            />
            <Line
              type="monotone"
              dataKey="gridImport"
              name="Grid import"
              stroke={p.grid}
              strokeWidth={2}
              dot={false}
            />
          </ComposedChart>
        </ResponsiveContainer>

        {/* Panel 2: state of charge (own axis — never dual-axis) */}
        <ResponsiveContainer width="100%" height={140}>
          <ComposedChart
            data={points}
            margin={{ top: 4, right: 12, bottom: 0, left: 0 }}
          >
            <TariffBands blocks={blocks} shade={p.shade} />
            <CartesianGrid stroke={p.gridline} vertical={false} />
            <XAxis
              dataKey="label"
              tick={{ fill: axis, fontSize: 11 }}
              tickFormatter={tickEvery}
              axisLine={{ stroke: p.gridline }}
              tickLine={false}
              interval={0}
            />
            <YAxis
              domain={[0, 100]}
              tick={{ fill: axis, fontSize: 11 }}
              axisLine={false}
              tickLine={false}
              width={44}
              label={{
                value: "SOC (%)",
                angle: -90,
                position: "insideLeft",
                fill: axis,
                fontSize: 11,
              }}
            />
            <Tooltip
              contentStyle={tooltipStyle}
              formatter={(v: number) => [`${num(v, 1)}%`, "SOC"]}
            />
            <Area
              type="monotone"
              dataKey="socPct"
              name="SOC"
              stroke={p.soc}
              strokeWidth={2}
              fill={p.soc}
              fillOpacity={0.15}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
