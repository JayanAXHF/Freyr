// Categorical + role palette, ported from the Streamlit dashboard
// (src/shriteq/app/dashboard.py _LIGHT / _DARK). Controllers keep the same two
// hues in every comparison chart: MPC blue, learned orange. The MPC/learned
// pair is validated by the dataviz palette validator (CVD ΔE ~25, all checks
// pass) in both light and dark on the surfaces below.

export type ThemeMode = 'light' | 'dark';

export interface Palette {
  mpc: string;
  learned: string;
  load: string;
  grid: string;
  solar: string;
  battery: string;
  soc: string;
  energy: string;
  demand: string;
  /** neutral ink for tariff shading, as "r, g, b" for rgba() */
  shade: string;
  surface: string;
  gridline: string;
}

export const LIGHT: Palette = {
  mpc: '#2a78d6',
  learned: '#eb6834',
  load: '#2a78d6',
  grid: '#e34948',
  solar: '#eda100',
  battery: '#1baf7a',
  soc: '#4a3aa7',
  energy: '#2a78d6',
  demand: '#eb6834',
  shade: '17, 17, 17',
  surface: '#fcfcfb',
  gridline: '#e4e4e2',
};

export const DARK: Palette = {
  mpc: '#3987e5',
  learned: '#d95926',
  load: '#3987e5',
  grid: '#e66767',
  solar: '#c98500',
  battery: '#199e70',
  soc: '#9085e9',
  energy: '#3987e5',
  demand: '#d95926',
  shade: '255, 255, 255',
  surface: '#1a1a19',
  gridline: '#33332f',
};

export function paletteFor(mode: ThemeMode): Palette {
  return mode === 'dark' ? DARK : LIGHT;
}
