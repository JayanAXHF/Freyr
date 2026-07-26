// Shared types for the dashboard data contract (mirrors outputs/dashboard/*.json).

export interface Metrics {
  total_energy_cost: number;
  demand_charge_incurred: number;
  total_bill: number;
  peak_kva: number;
  unmet_load_kwh: number;
  unmet_events: number;
  shed_load_kwh: number;
  shed_events: number;
  solar_self_consumption: number;
}

export interface Meta {
  seed: number;
  generated_at: string;
  model_path: string;
  model_mtime: number | null;
}

export interface TariffBlock {
  start_hour: number;
  end_hour: number;
  price_inr_per_kwh: number;
}

export interface SummaryResponse {
  mpc: Metrics;
  learned: Metrics;
  meta: Meta;
  savingsPct: number;
  stale: boolean;
  days: string[]; // ISO date strings, e.g. "2026-01-06"
  tariffBlocks: TariffBlock[];
}

export type Controller = 'learned' | 'mpc';

export interface DispatchPoint {
  timestamp: string; // ISO-8601
  label: string; // "HH:MM"
  load: number;
  solar: number;
  gridImport: number;
  batteryNet: number; // discharge - charge (+ discharge / − charge)
  socPct: number;
}

export interface DispatchResponse {
  day: string;
  controller: Controller;
  points: DispatchPoint[];
  tariffBlocks: TariffBlock[];
}
