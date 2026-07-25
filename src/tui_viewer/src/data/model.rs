//! Serde types mirroring the JSON payload from `shriteq.app.payload`.
//!
//! Some fields are part of the wire contract but not yet rendered (e.g. the
//! per-event shed/unmet counts); they are kept so the model stays faithful to
//! the server payload.
#![allow(dead_code)]

use serde::Deserialize;

#[derive(Debug, Clone, Deserialize)]
pub struct Snapshot {
    #[serde(default)]
    pub seed: i64,
    pub now: Now,
    #[serde(default)]
    pub forecast: Vec<ForecastPoint>,
    pub benchmark: Benchmark,
    #[serde(default)]
    pub trace: Trace,
}

#[derive(Debug, Clone, Deserialize)]
pub struct Now {
    pub load_kw: f64,
    pub solar_kw: f64,
    pub soc: f64,
    pub tariff_block: i64,
    pub billing_peak_kva: f64,
}

#[derive(Debug, Clone, Deserialize)]
pub struct ForecastPoint {
    pub t: String,
    pub load_kw: f64,
    pub solar_kw: f64,
    pub grid_import_kw: f64,
}

#[derive(Debug, Clone, Deserialize)]
pub struct Benchmark {
    pub mpc: BenchmarkRow,
    pub learned: BenchmarkRow,
}

#[derive(Debug, Clone, Deserialize)]
pub struct BenchmarkRow {
    pub total_energy_cost: f64,
    pub demand_charge_incurred: f64,
    pub total_bill: f64,
    pub peak_kva: f64,
    pub unmet_load_kwh: f64,
    pub unmet_events: f64,
    pub shed_load_kwh: f64,
    pub shed_events: f64,
    pub solar_self_consumption: f64,
    #[serde(default)]
    pub service_quality_ok: bool,
    #[serde(default)]
    pub savings_pct: Option<f64>,
}

#[derive(Debug, Clone, Default, Deserialize)]
pub struct Trace {
    #[serde(default)]
    pub timestamps: Vec<String>,
    #[serde(default)]
    pub learned: TraceLearned,
    #[serde(default)]
    pub mpc: TraceMpc,
    #[serde(default)]
    pub rolling_peak_learned: Vec<f64>,
}

#[derive(Debug, Clone, Default, Deserialize)]
pub struct TraceLearned {
    #[serde(default)]
    pub grid_import_kw: Vec<f64>,
    #[serde(default)]
    pub soc: Vec<f64>,
}

#[derive(Debug, Clone, Default, Deserialize)]
pub struct TraceMpc {
    #[serde(default)]
    pub grid_import_kw: Vec<f64>,
}

impl Trace {
    pub fn len(&self) -> usize {
        self.timestamps.len()
    }

    pub fn is_empty(&self) -> bool {
        self.timestamps.is_empty()
    }
}
